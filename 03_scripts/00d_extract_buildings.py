"""N24 OSM pbf 에서 건물(building=*) 대표점만 뽑아 processed/ 에 저장한다.
용도: 읍면 안 「사람이 사는 자리」의 대리 지표 — 정류장 도보권 비율과 읍면 대표점(건물 무게중심)을 잰다.
pyosmium 필요(설치 경로는 환경변수 OSMLIB). 원본 pbf 는 읽기만 한다.
제외 태그(사전등록 §판정 규칙에 고정): 농업·창고·산업·차고 등 비주거 부속건물.
"""
import _env; _env.cap()
import os, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, os.environ.get("OSMLIB", ""))
import osmium

SEED = 20260725
HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "01_data/raw/south-korea-latest.osm.pbf"
OUT = HERE.parent / "01_data/processed/osm_buildings.npz"

EXCLUDE = {"industrial", "warehouse", "greenhouse", "farm_auxiliary", "barn", "shed", "garage",
           "garages", "cowshed", "stable", "sty", "silo", "storage_tank", "roof", "carport",
           "construction", "ruins", "hut", "service", "transformer_tower", "bunker", "parking",
           "container", "toilets", "kiosk", "digester", "slurry_tank"}


class H(osmium.SimpleHandler):
    def __init__(s):
        super().__init__()
        s.lat = []; s.lon = []; s.kept = 0; s.dropped = 0

    def way(s, w):
        b = w.tags.get("building")
        if not b or b == "no":
            return
        if b in EXCLUDE:
            s.dropped += 1
            return
        try:
            xs = []; ys = []
            for nd in w.nodes:
                if nd.location.valid():
                    xs.append(nd.lon); ys.append(nd.lat)
            if xs:
                s.lon.append(sum(xs) / len(xs)); s.lat.append(sum(ys) / len(ys)); s.kept += 1
        except Exception:
            pass


h = H()
h.apply_file(str(RAW), locations=True, idx="flex_mem")
np.savez_compressed(OUT, lat=np.asarray(h.lat, dtype=np.float32), lon=np.asarray(h.lon, dtype=np.float32))
print("buildings kept", h.kept, "excluded_by_tag", h.dropped, "->", OUT)
