"""06_posthoc — 사전등록에 없던 점검(결과를 본 뒤 추가). 주 결과·민감도 범위에 넣지 않는다.

점검 1: 시장을 정기장만이 아니라 상설시장까지 넣으면 C1 이 어떻게 바뀌나(「장날」 질문 밖의 대안 정의).
점검 2: 섬 읍면을 빼면 공백 읍면이 몇 곳 남나.
출력: processed/posthoc.csv · numbers.json(참고값으로만)
"""
import _env; _env.cap()
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer

SEED = 20260725
HERE = Path(__file__).resolve().parent
PRO = HERE.parent / "01_data/processed"
RAW = HERE.parent / "01_data/raw"
sys.path.insert(0, str(HERE.parents[3] / "scripts"))
from 수치기록 import add  # noqa: E402

d = pd.read_csv(PRO / "eupmyeon_judged.csv", encoding="utf-8-sig", dtype={"adm_cd2": str})
gl = pd.read_csv(PRO / "jangnal_gap_list.csv", encoding="utf-8-sig", dtype={"adm_cd2": str})
b = d[d.has_pop & ~d.hold].copy()
n2 = pd.read_csv(RAW / "N2_소상공인시장진흥공단_전통시장_20251110.csv", encoding="utf-8-sig").dropna(subset=["위도", "경도"])
x, y = Transformer.from_crs(4326, 5179, always_xy=True).transform(n2.경도.values, n2.위도.values)
b["d_any_market_km"] = cKDTree(np.c_[x, y]).query(np.c_[b.rx, b.ry])[0] / 1000
c1_any = b.d_any_market_km > 5
gap_any = c1_any & b.C2 & b.C3 & b.C4
isl = set(gl.loc[gl.island, "adm_cd2"])
rows = [{"check": "주 판정(정기장 기준)", "gap_n": int(b.gap.sum())},
        {"check": "상설시장 포함 전체 시장 기준 C1", "gap_n": int(gap_any.sum())},
        {"check": "섬 읍면 제외", "gap_n": int((b.gap & ~b.adm_cd2.isin(isl)).sum())}]
pd.DataFrame(rows).to_csv(PRO / "posthoc.csv", index=False, encoding="utf-8-sig")
SC = "[인구 2026-09·시장 2025-11-10·정류장 2025-10-31/OSM 2026-10-12 기준, 판정 대상 읍·면]"
add("posthoc_gap_anymarket_n", int(gap_any.sum()), "곳", f"{SC} (사후 점검) 상설시장까지 시장으로 보면 4조건 AND 공백 읍·면 수",
    "C1 을 전체 전통시장 최근접 거리 > 5 km 로 바꾸고 C2~C4 동일", n=len(b), source_dataset="N2+N1+N24+S9",
    caveat="사전등록 밖 점검. 장날(정기장) 질문이 아니라 시장 접근 일반 질문이다 — 주 결과 아님")
add("posthoc_gap_noisland_n", int((b.gap & ~b.adm_cd2.isin(isl)).sum()), "곳", f"{SC} (사후 점검) 섬 읍면을 뺀 공백 읍·면 수",
    "주 판정 공백 − 본토 폴리곤 비접촉 읍·면", n=len(b), source_dataset="N16", caveat="연륙교로 이어진 섬도 섬으로 셌다")
print(pd.DataFrame(rows).to_string())
