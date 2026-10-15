# MESTO GEO

Experimental combined Xray GeoSite and GeoIP databases for MESTO VPN.
**Do not deploy to subscribers until Happ and INCY routing templates are verified on real devices.** The rolling release is public but unapproved for production distribution.

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
CI workflow runs daily 04:15 UTC and on demand, checks the DAT files using Xray-core and publishes a rolling GitHub Release tagged `latest`. It refuses unexpectedly large size changes compared with the previous release. RemnaWave subscriptions are unchanged until client-side validation.\n\nDownload links:\n- https://github.com/mestoproject/MESTO-GEO/releases/latest/download/geoip.dat\n- https://github.com/mestoproject/MESTO-GEO/releases/latest/download/geosite.dat\n- https://github.com/mestoproject/MESTO-GEO/releases/latest/download/manifest.json\n\nA release will exist only after the first successful run of the new workflow.

## Attribution and licenses

This project combines third-party data, with rights and terms governed by their upstream licenses. See upstream license files and retain their notices when distributing derivative databases. RU Direct declares MIT; Runetfreedom distributes data with a GPLv3 LICENSE. GPLv3 license text is included in the root LICENSE and rolling releases; RU Direct MIT notice is in `licenses/RU-DIRECT-MIT.txt`. Review upstream obligations and attribution before further redistribution.

## Compatibility caveat

Routing must be done locally by the client. A standard Xray JSON template cannot assume each Happ/INCY build downloads arbitrary geodata assets automatically. Test profile delivery on both actual client versions and ensure all required outbound tags are present.
