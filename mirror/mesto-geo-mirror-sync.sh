#!/usr/bin/env bash
# Fetch a complete, verified MESTO GEO snapshot, then switch Caddy to it atomically.
set -Eeuo pipefail
BASE="/srv/mesto-geo"
RELEASES="$BASE/releases"
mkdir -p "$RELEASES"
exec 9>"$BASE/.update.lock"
flock -n 9 || exit 0
API="https://api.github.com/repos/mestoproject/MESTO-GEO/releases/latest"
JSON="$(mktemp)"
TMP="$(mktemp -d "$RELEASES/.incoming.XXXXXXXX")"
trap 'rm -f "$JSON"; rm -rf "$TMP"' EXIT
curl -fsSL --connect-timeout 10 --max-time 45 --retry 3 "$API" -o "$JSON"
python3 - "$JSON" "$TMP/urls.tsv" "$TMP/tag" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
assert not j["draft"] and not j["prerelease"]
names=("geoip.dat","geosite.dat","geoip.dat.sha256","geosite.dat.sha256","SHA256SUMS","manifest.json")
assets={x["name"]:x for x in j["assets"]}
with open(sys.argv[2],"w") as f:
    for name in names:
        a=assets[name]
        assert a["state"]=="uploaded" and a["size"]>0
        f.write(name+"\t"+a["browser_download_url"]+"\n")
with open(sys.argv[3],"w") as f:
    f.write(j["tag_name"])
PY
TAG="$(cat "$TMP/tag")"
[[ "$TAG" =~ ^mesto-geo-[0-9]{8}-[0-9]+-[0-9]+$ ]] || { echo "Unexpected tag $TAG" >&2; exit 1; }
if [[ -d "$RELEASES/$TAG" ]]; then
    echo "Already mirrored $TAG"
    exit 0
fi
while IFS=$'\t' read -r filename url; do
    curl -fsSL --connect-timeout 10 --max-time 240 --retry 3 "$url" -o "$TMP/$filename"
done < "$TMP/urls.tsv"
(cd "$TMP" && sha256sum -c SHA256SUMS)
for kind in geoip geosite; do
    actual="$(sha256sum "$TMP/$kind.dat" | awk '{print $1}')"
    claimed="$(tr -d '\r\n ' < "$TMP/$kind.dat.sha256")"
    [[ "$actual" == "$claimed" ]] || { echo "SHA mismatch for $kind" >&2; exit 1; }
done
python3 - "$TMP" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1])
m=json.loads((p/"manifest.json").read_text())
for kind in ("geoip","geosite"):
    digest=hashlib.sha256((p/(kind+".dat")).read_bytes()).hexdigest()
    assert m["sources_and_outputs"]["output/"+kind]["sha256"]==digest
PY
rm -f "$TMP/urls.tsv" "$TMP/tag"
chmod -R a+rX "$TMP"
mv "$TMP" "$RELEASES/$TAG"
ln -sfn "releases/$TAG" "$BASE/.current-next"
mv -Tf "$BASE/.current-next" "$BASE/current"
echo "Activated mirror version: $TAG"
