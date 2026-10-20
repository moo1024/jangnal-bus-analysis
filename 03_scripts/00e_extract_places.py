"""N24 OSM pbf 에서 마을 점(place=village·hamlet·isolated_dwelling, 그리고 읍면 소재지 town)을 뽑는다.
용도: 농어촌서비스기준의 측정 단위인 「마을」의 대리. 읍면 안 정류장 도보권 비율을 마을 단위로 잰다.
(사전등록 변경 이력 #4 — OSM 건물 수록률이 읍면 중앙값 43동이라 건물 단위를 주 방법에서 내렸다)
pyosmium 필요(OSMLIB). 원본 pbf 는 읽기만 한다.
"""
import _env; _env.cap()
import os, sys, csv
from pathlib import Path
sys.path.insert(0, os.environ.get("OSMLIB", ""))
import osmium

SEED = 20260725
HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "01_data/raw/south-korea-latest.osm.pbf"
OUT = HERE.parent / "01_data/processed/osm_places.csv"
KEEP = {"village", "hamlet", "isolated_dwelling", "town"}


class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__(); s.rows = []

    def node(s, n):
        p = n.tags.get("place")
        if p in KEEP:
            s.rows.append([n.id, p, n.location.lat, n.location.lon, n.tags.get("name", ""), n.tags.get("name:ko", "")])


h = H()
h.apply_file(str(RAW))
with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["osm_id", "place", "lat", "lon", "name", "name_ko"]); w.writerows(h.rows)
from collections import Counter
print(len(h.rows), Counter(r[1] for r in h.rows))
