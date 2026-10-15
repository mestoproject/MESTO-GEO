#!/usr/bin/env python3
"""MESTO GEO: build Xray-compatible GeoSite/GeoIP protobuf DAT assets.

Uses the existing binary protobuf records (preserving standard categories),
plus independent MESTO categories. Standard-library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = {
    "base": "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/",
    "ru_direct": "https://github.com/kyoresuas/ru-direct/releases/latest/download/",
    "runet": "https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/",
}
MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError("Truncated varint")
        byte = data[offset]
        offset += 1
        result |= (byte & 127) << shift
        if byte < 128:
            return result, offset
    raise ValueError("Invalid varint")


def write_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("Negative varint")
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def fields(data: bytes):
    offset = 0
    while offset < len(data):
        key, offset = read_varint(data, offset)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ValueError("Invalid protobuf field zero")
        if wire == 0:
            value, offset = read_varint(data, offset)
        elif wire == 1:
            value = data[offset: offset + 8]
            offset += 8
            if len(value) != 8:
                raise ValueError("Truncated fixed64")
        elif wire == 2:
            size, offset = read_varint(data, offset)
            if size > len(data) - offset:
                raise ValueError("Truncated length-delimited field")
            value = data[offset:offset + size]
            offset += size
        elif wire == 5:
            value = data[offset:offset + 4]
            offset += 4
            if len(value) != 4:
                raise ValueError("Truncated fixed32")
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire}")
        yield number, wire, value


def string_field(number: int, text: str) -> bytes:
    return bytes_field(number, text.encode("utf-8"))


def bytes_field(number: int, value: bytes) -> bytes:
    return write_varint((number << 3) | 2) + write_varint(len(value)) + value


def parse_dat(blob: bytes) -> tuple[list[bytes], dict[str, list[bytes]]]:
    """GeoSiteList and GeoIPList use identical outer field numbering."""
    raw_entries = []
    categories = {}
    for number, wire, entry in fields(blob):
        if number != 1 or wire != 2:
            raise ValueError("Unexpected top-level DAT field")
        raw_entries.append(entry)
        country = None
        records = []
        for field_no, field_wire, value in fields(entry):
            if field_no == 1 and field_wire == 2:
                country = value.decode("utf-8").lower()
            elif field_no == 2 and field_wire == 2:
                records.append(value)
        if not country:
            raise ValueError("Missing DAT category name")
        if country in categories:
            raise ValueError(f"Duplicate DAT category {country}")
        categories[country] = records
    if not raw_entries:
        raise ValueError("Empty DAT")
    return raw_entries, categories


def required(categories: dict[str, list[bytes]], name: str, source: str) -> list[bytes]:
    values = categories.get(name)
    if not values:
        raise ValueError(f"Missing/empty category {name!r} in {source}")
    return values


def build_category(name: str, records: list[bytes]) -> bytes:
    # Raw nested Domain/CIDR protobuf records preserve original attributes.
    unique = list(dict.fromkeys(records))
    if not unique:
        raise ValueError(f"Empty merged category: {name}")
    return string_field(1, name.upper()) + b"".join(bytes_field(2, rec) for rec in unique)


def pack_dat(base_entries: list[bytes], extra: dict[str, list[bytes]]) -> bytes:
    preserved = []
    for entry in base_entries:
        code = next(
            (v.decode("utf-8").lower() for n, w, v in fields(entry)
             if n == 1 and w == 2), None
        )
        if code not in extra:
            preserved.append(entry)
    return b"".join(bytes_field(1, e) for e in preserved) + b"".join(
        bytes_field(1, build_category(name, records))
        for name, records in sorted(extra.items())
    )


def download(url: str) -> bytes:
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "MESTO-GEO/1.0"}
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                blob = response.read(MAX_DOWNLOAD_BYTES + 1)
            if len(blob) > MAX_DOWNLOAD_BYTES or len(blob) < 1024:
                raise ValueError(f"Unexpected download size: {len(blob)}")
            return blob
        except Exception as error:
            last_error = error
            if attempt != 2:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Download failed: {url}: {last_error}")


def domain_records(path: pathlib.Path) -> list[bytes]:
    """Encode domain:example.org as Domain.Type=RootDomain (field 1=2)."""
    import ipaddress

    output = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        domain = raw.split("#", 1)[0].strip().lower()
        if not domain:
            continue
        if domain.startswith("domain:"):
            domain = domain[7:]
        if not domain or "." not in domain or any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789-." for c in domain
        ):
            raise ValueError(f"{path}:{lineno}: invalid domain {domain}")
        labels = domain.split(".")
        if any(not x or len(x) > 63 or x.startswith("-") or x.endswith("-") for x in labels):
            raise ValueError(f"{path}:{lineno}: invalid label")
        try:
            ipaddress.ip_address(domain)
        except ValueError:
            pass
        else:
            raise ValueError(f"{path}:{lineno}: use domains, not IP addresses")
        output.append(write_varint((1 << 3) | 0) + write_varint(2)
                      + string_field(2, domain))
    if not output:
        raise ValueError(f"Empty domains file: {path}")
    return output


def build(outdir: pathlib.Path):
    originals = {}
    manifests = {}
    for key, url_prefix in SOURCES.items():
        originals[key] = {}
        for kind in ("geosite", "geoip"):
            url = url_prefix + kind + ".dat"
            blob = download(url)
            raw_entries, categories = parse_dat(blob)
            originals[key][kind] = (raw_entries, categories)
            manifests[f"{key}/{kind}"] = {
                "url": url,
                "sha256": hashlib.sha256(blob).hexdigest(),
                "bytes": len(blob),
                "categories": len(categories)
            }

    bsite, bsites = originals["base"]["geosite"]
    _, rsites = originals["ru_direct"]["geosite"]
    _, nsites = originals["runet"]["geosite"]
    bip, bips = originals["base"]["geoip"]
    _, rips = originals["ru_direct"]["geoip"]

    sites = {
        "mesto-ru": (
            required(bsites, "category-ru", "base")
            + required(rsites, "ru-standard", "ru_direct")
            + required(nsites, "ru-available-only-inside", "runet")
            + domain_records(ROOT / "custom" / "direct-domains.txt")
        ),
        "mesto-proxy": domain_records(ROOT / "custom" / "proxy-domains.txt")
    }
    ips = {
        "mesto-ru": (
            required(bips, "ru", "base")
            + required(rips, "ru-standard", "ru_direct")
        )
    }

    outdir.mkdir(parents=True, exist_ok=True)
    for kind, baseline, additions in (
        ("geosite", bsite, sites),
        ("geoip", bip, ips),
    ):
        data = pack_dat(baseline, additions)
        _, parsed = parse_dat(data)
        if "mesto-ru" not in parsed:
            raise AssertionError("Missing MESTO-RU")
        if kind == "geosite" and len(parsed["mesto-ru"]) < 100:
            raise AssertionError("Suspiciously small MESTO-RU geosite")
        if kind == "geoip" and len(parsed["mesto-ru"]) < 100:
            raise AssertionError("Suspiciously small MESTO-RU geoip")
        path = outdir / (kind + ".dat")
        path.write_bytes(data)
        manifests[f"output/{kind}"] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "categories": len(parsed),
            "mesto_ru_records": len(parsed["mesto-ru"]),
        }

    (outdir / "manifest.json").write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources_and_outputs": manifests,
            "notes": "MESTO-RU is a convenience union; it does not guarantee Russian IP or reachability."
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(json.dumps(manifests, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist")
    args = parser.parse_args()
    build(pathlib.Path(args.output))


if __name__ == "__main__":
    main()
