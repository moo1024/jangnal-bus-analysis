"""N24 Geofabrik 한국 pbf 에서 highway=bus_stop / public_transport=platform(버스) / amenity=marketplace 만 추출.
pyosmium 필요(설치 경로는 환경변수 OSMLIB). 좌표는 노드·폐곡선 중심(way·relation 은 대표점).

분석이 읽는 고정본은 raw/N24_osm_*_20261013.csv(sha256 은 manifest.json)이다.
이 스크립트는 raw/ 에 쓰지 않는다 — 재추출본은 processed/ 에 쓰고 고정본과 sha256 을 대조한다.
processed/ 에 재추출본이 이미 있으면 다시 추출하지 않는다(--force 로 강제).
"""
import _env; _env.cap()
import os, sys, csv, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
RAWD = HERE.parent / "01_data/raw"
PRO = HERE.parent / "01_data/processed"
RAW = RAWD / "south-korea-latest.osm.pbf"
NAMES = {"bus_stop": "N24_osm_bus_stop_20261013.csv", "marketplace": "N24_osm_marketplace_20261013.csv"}


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


outs = {k: PRO / f"reextract_{v}" for k, v in NAMES.items()}
if all(p.exists() for p in outs.values()) and "--force" not in sys.argv:
    for k, p in outs.items():
        print(k, "재추출본 있음 — 건너뜀. 고정본과 sha256 일치:", _sha(p) == _sha(RAWD / NAMES[k]))
    sys.exit(0)
sys.path.insert(0, os.environ.get("OSMLIB", ""))
import osmium  # noqa: E402
class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.bus = []; s.mkt = []
    def _rec(s, kind, o, lon, lat):
        t = o.tags
        row = [kind, o.id, lat, lon, t.get("name", ""), t.get("name:ko", ""), t.get("ref", ""), t.get("opening_hours", ""), t.get("operator", ""), t.get("shelter", ""), t.get("bench", "")]
        return row
    def node(s, n):
        t = n.tags
        if t.get("highway") == "bus_stop" or (t.get("public_transport") in ("platform", "stop_position") and t.get("bus") == "yes"):
            s.bus.append(s._rec("node", n, n.location.lon, n.location.lat))
        if t.get("amenity") == "marketplace":
            s.mkt.append(s._rec("node", n, n.location.lon, n.location.lat))
    def way(s, w):
        if w.tags.get("amenity") == "marketplace":
            try:
                ls = [(nd.lon, nd.lat) for nd in w.nodes if nd.location.valid()]
                if ls: s.mkt.append(s._rec("way", w, sum(x for x, _ in ls)/len(ls), sum(y for _, y in ls)/len(ls)))
            except Exception: pass
h = H()
h.apply_file(str(RAW), locations=True)
hdr = ["osm_type", "osm_id", "lat", "lon", "name", "name_ko", "ref", "opening_hours", "operator", "shelter", "bench"]
for nm, rows in (("bus_stop", h.bus), ("marketplace", h.mkt)):
    with open(outs[nm], "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(hdr); w.writerows(rows)
    fixed = RAWD / NAMES[nm]
    print(nm, len(rows), "고정본과 sha256 일치:", fixed.exists() and _sha(outs[nm]) == _sha(fixed))
