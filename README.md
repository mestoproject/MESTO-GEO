# MESTO GEO

Experimental combined Xray GeoSite and GeoIP databases for MESTO VPN.
**Do not deploy to subscribers until Happ and INCY routing templates are verified on real devices.** Current published releases remain experimental until client routing tests.

## Included sources

- [Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat): baseline Xray `geoip.dat`, `geosite.dat`, categories retained.
- [kyoresuas/ru-direct](https://github.com/kyoresuas/ru-direct): `ru-standard` domain and IP additions.
- [runetfreedom/russia-v2ray-rules-dat](https://github.com/runetfreedom/russia-v2ray-rules-dat): `ru-available-only-inside` domain additions only.
- `custom/*.txt`: MESTO overrides.

## Output categories

- `geosite:mesto-ru`: baseline category-ru + RU Direct standard + only-inside + custom direct.
- `geoip:mesto-ru`: baseline RU geoip + RU Direct standard.
- `geosite:mesto-proxy`: domains that must remain on VPN, **matched before** MESTO-RU.
- All baseline categories are preserved.

Do **not** direct `ru-blocked`, `ru-blocked-all`, or `ru-whitelist` as a blanket rule. GeoIP address geolocation is not the same thing as an operator's whitelist.

## Build

Run `python3 scripts/build_geo.py --output dist` (Python 3.10+; external network required).
CI runs daily at 04:15 UTC and on manual dispatch. It builds and validates GeoIP/GeoSite against Xray-core, creates INCY sidecar SHA-256 files, uploads a **complete draft snapshot** to a versioned GitHub Release, and only then makes it the latest public release. Previous versions remain available for rollback.

Latest published version:
- https://github.com/mestoproject/MESTO-GEO/releases/latest
- https://github.com/mestoproject/MESTO-GEO/releases/latest/download/geoip.dat
- https://github.com/mestoproject/MESTO-GEO/releases/latest/download/geosite.dat
- https://github.com/mestoproject/MESTO-GEO/releases/latest/download/geoip.dat.sha256
- https://github.com/mestoproject/MESTO-GEO/releases/latest/download/geosite.dat.sha256

**Important:** The old legacy tag `latest` is not deleted or overwritten. Stable `/releases/latest/download/` links follow GitHub's latest *published versioned release*, not the tag named latest. Verify the first successful new CI run before using these links.

## Optional independent mirror

Files in `mirror/` implement a verified Caddy mirror on a Linux VPS. The public host `geo.mestolink.com` is an example **not yet deployed or configured in DNS**.

On a chosen VPS, install Caddy, curl, Python 3 and util-linux (`flock`); permit HTTPS 443. Copy `mirror/mesto-geo-mirror-sync.sh` to `/usr/local/sbin/mesto-geo-mirror-sync`, make it executable, copy the service and timer to `/etc/systemd/system/`, create a Caddy site based on `mirror/Caddyfile.example`, then run `systemctl daemon-reload && systemctl enable --now mesto-geo-mirror.timer && systemctl start mesto-geo-mirror.service`. Use HTTPS and confirm it serves both DAT files and matching SHA-256 sidecars. This mirror has an independent **copy** of the last good release, but obtaining new versions still depends on GitHub.

Do not bind the mirror to a VPS port already in use by Reality, Caddy, or RemnaNode. A separate small VPS is usually simplest; if sharing a server, use an existing Caddy HTTPS virtual host and ensure there is no port conflict.

Do not activate client configs until Happ and INCY profile integration and cache/failure behavior have been verified.


## Attribution and licenses

This project combines third-party data, with rights and terms governed by their upstream licenses. See upstream license files and retain their notices when distributing derivative databases. RU Direct declares MIT; Runetfreedom distributes data with a GPLv3 LICENSE. GPLv3 license text is included in the root LICENSE and rolling releases; RU Direct MIT notice is in `licenses/RU-DIRECT-MIT.txt`. Review upstream obligations and attribution before further redistribution.

## Compatibility caveat

Routing must be done locally by the client. A standard Xray JSON template cannot assume each Happ/INCY build downloads arbitrary geodata assets automatically. Test profile delivery on both actual client versions and ensure all required outbound tags are present.
