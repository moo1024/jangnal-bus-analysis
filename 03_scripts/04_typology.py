"""04_typology — 공백 읍면에 기존 제도를 겹쳐 운영형·얹기형·확인필요형으로 나누고 우선순위 명단을 만든다.

규칙(사전등록, 분류 기준은 그대로이고 이름·해석만 낮췄다 — 변경 이력 #6):
  운영형     : 장날 전용버스 운영이 원문으로 확인된 시군 (01_data/manual/장날전용버스_운영시군.csv — 근거문장·URL 필수)
  얹기형     : 농촌형 교통모델 대상 군(N23 원문 「82개 군 지역 … 울릉군 미참여」 → 울릉군 외 군 전부) 또는 DRT 등록 시군(S2)
               ※ 군 소속 공백 읍면은 정의상 전부 얹기형이다. 그 읍면에 실제로 운행하는지는 확인하지 않았다
  확인필요형 : 위 둘 다 확인 안 됨. 시 지역은 국토부 도시형 교통모델 대상(N23 원문 「78개 시 지역은 국토부가 주관(도시형)」)인데
               시별 시행 명단을 확보하지 못해 보지 않았다 → 「제도 없음」이 아니라 「확인 안 됨」
섬 읍면(본토 폴리곤과 닿지 않는 읍면)은 별도 표시만 한다(판정은 바꾸지 않는다 — 사후 표시).
자료 확인 표시(사후, 판정은 바꾸지 않는다): ① 정류장 0개 읍면 ② 소속 시군의 N1b 가 5개 이하라 BIS 구멍 보류 규칙을 검증할 수 없는 곳.
출력: processed/jangnal_gap_list.csv(우선순위 명단) · processed/typology_summary.csv · numbers.json
"""
import _env; _env.cap()
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd

SEED = 20260725
HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "01_data"
PRO = DATA / "processed"
sys.path.insert(0, str(HERE.parents[3] / "scripts"))
from 수치기록 import add  # noqa: E402
SCOPE = "[인구 2026-09·시장 2025-11-10·정류장 2025-10-31/OSM 2026-10-12·DRT 2025-12-31·농촌형 교통모델 2024 기준, 판정 대상 읍·면]"

d = pd.read_csv(PRO / "eupmyeon_judged.csv", encoding="utf-8-sig", dtype={"adm_cd2": str})
b = d[d.has_pop & ~d.hold].copy()

# DRT 등록(S2)
s2 = pd.read_csv(DATA / "raw/S2_한국교통안전공단_수요응답형대중교통시스템_등록대수_20251231.csv", encoding="cp949")
s2["sido_n"] = s2.시도.replace({"전라북도": "전북특별자치도", "강원도": "강원특별자치도"})
s2["sigun_key"] = s2.sido_n + " " + s2.시군구
s2 = s2[(s2.택시 + s2.버스) > 0]
drt = set(s2.sigun_key)
# 운영형 입력표
op = pd.read_csv(DATA / "manual/장날전용버스_운영시군.csv", encoding="utf-8-sig")
op = op[op.근거문장.notna() & op.출처URL.notna()]
operating = set(op.sigun_key)

b["drt"] = b.sigun_key.isin(drt)
b["rural_model"] = (b.kind == "군") & (b.sigun != "울릉군")
b["type"] = np.select([b.sigun_key.isin(operating), b.rural_model | b.drt], ["운영형", "얹기형"], "확인필요형")
# 자료 확인 표시 — 판정 규칙(사전등록)은 그대로 두고 명단에만 붙인다
cov = pd.read_csv(PRO / "coverage_n1_vs_n1b.csv", encoding="utf-8-sig")
N1B_MAX = 5
n1b_thin = set(cov.loc[cov.n1b <= N1B_MAX, "k"])
b["flag_zero_stop"] = b.n_stop == 0
b["flag_n1b_unverifiable"] = b.sigun_key.isin(n1b_thin)

# 섬 표시: 전체 읍면동 폴리곤 합집합의 최대 덩어리(본토)와 닿지 않는 읍면
g = gpd.read_file(DATA / "raw/HangJeongDong_ver20260701.geojson").to_crs(5179)
u = g.geometry.buffer(50).union_all()
parts = list(u.geoms) if hasattr(u, "geoms") else [u]
main = max(parts, key=lambda p: p.area)
em = gpd.read_file(PRO / "eupmyeon_base.gpkg")
em["adm_cd2"] = em.adm_cd2.astype(str)
em["island"] = ~em.geometry.intersects(main)
b = b.merge(em[["adm_cd2", "island"]], on="adm_cd2", how="left")

gap = b[b.gap].copy()
gap["flag_zero_stop_mainland"] = gap.flag_zero_stop & ~gap.island.fillna(False).astype(bool)
gap["priority_rank"] = gap.pop65.rank(ascending=False, method="first").astype(int)
gap = gap.sort_values("priority_rank")
gap[["priority_rank", "adm_cd2", "adm_nm", "sigun_key", "kind", "type", "island", "pop", "pop65", "old_ratio", "d_market_km",
     "unc_share", "n_vil", "n_stop", "stop_density", "drt", "rural_model", "flag_zero_stop", "flag_zero_stop_mainland",
     "flag_n1b_unverifiable"]].to_csv(PRO / "jangnal_gap_list.csv", index=False, encoding="utf-8-sig")

summ = gap.groupby("type").agg(eupmyeon_n=("adm_cd2", "size"), elderly=("pop65", "sum"), sigun_n=("sigun_key", "nunique")).reindex(["확인필요형", "얹기형", "운영형"]).fillna(0).astype(int)
summ.to_csv(PRO / "typology_summary.csv", encoding="utf-8-sig")
# 시군 단위 유형(공백 읍면이 있는 시군)
sg = gap.groupby("sigun_key").agg(type=("type", "first"), kind=("kind", "first"), n=("adm_cd2", "size"), elderly=("pop65", "sum")).sort_values("elderly", ascending=False)
sg.to_csv(PRO / "typology_sigun.csv", encoding="utf-8-sig")

CAV = {"운영형": "운영형 근거 시군 0곳 — 원문 확인 전이라 0으로 둔다. 「없음」이 아니라 「미확인」",
       "얹기형": "군 소속 공백 읍·면은 정의상 전부 얹기형이다(정의에 의한 분류 — 발견이 아니다). 농촌형 교통모델 군별 명단 미확보로 "
                "「82개 군 중 울릉군 미참여」 원문 줄로 환원했고, 그 읍·면에 실제로 운행하는지는 확인하지 않았다",
       "확인필요형": "「기존 제도 없음」이 아니다. 전부 시 소속이고, N23 원문상 78개 시 지역은 국토부 도시형 교통모델 주관인데 "
                  "시별 시행 명단을 확보하지 못해 확인하지 않았다. 농촌형 교통모델(군)·DRT 등록만 없음을 확인했다"}
tmap = {"확인필요형": ("gap_type_none_n", "gap_type_none_sigun_n", "gap_type_none_elderly_n"),
        "얹기형": ("gap_type_overlay_n", "gap_type_overlay_sigun_n", "gap_type_overlay_elderly_n"),
        "운영형": ("gap_type_running_n", "gap_type_running_sigun_n", "gap_type_running_elderly_n")}
for t, r in summ.iterrows():
    K_N, K_SG, K_OLD = tmap[t]
    add(K_N, int(r.eupmyeon_n), "곳", f"{SCOPE} 장날 이동 공백 읍·면 중 {t} 읍·면 수",
        "공백 읍·면 × (운영형: 장날 전용버스 원문 확인 시군 / 얹기형: 농촌형 교통모델 대상 군·DRT 등록 시군 / "
        "확인필요형: 농촌형 교통모델·DRT 확인 안 됨, 국토부 도시형 교통모델 시행 여부 미확인)",
        n=len(gap), source_dataset="N23+S2+N16", caveat=CAV[t])
    add(K_SG, int(r.sigun_n), "곳", f"{SCOPE} 장날 이동 공백 읍·면이 있는 시·군 중 {t} 시·군 수",
        "공백 읍·면 소속 시·군을 유형별로 셈", n=int(gap.sigun_key.nunique()), source_dataset="N23+S2+N16")
    add(K_OLD, int(r.elderly), "명", f"{SCOPE} {t} 공백 읍·면 65세 이상 인구 합계",
        "유형별 공백 읍·면 S9 65세 이상 합", n=int(r.eupmyeon_n), source_dataset="S9", caveat="실제 장날 이용자 수가 아니다")
add("gap_sigun_n", int(gap.sigun_key.nunique()), "곳", f"{SCOPE} 장날 이동 공백 읍·면이 1곳 이상 있는 시·군 수", "공백 읍·면 소속 시·군 고유 수",
    n=len(gap), source_dataset="N16")
add("gap_island_n", int(gap.island.sum()), "곳", f"{SCOPE} 장날 이동 공백 읍·면 중 섬 읍·면 수(본토 폴리곤과 닿지 않음)",
    "행정동 경계 합집합(50 m 완충) 최대 덩어리와 비접촉", n=len(gap), source_dataset="N16", caveat="섬은 버스가 아니라 배·도선 연계가 필요 — 사후 표시")
add("gap_in_si_n", int((gap.kind == "시").sum()), "곳", f"{SCOPE} 장날 이동 공백 읍·면 중 시(도농복합시) 소속 수",
    "공백 읍·면 중 소속 시군구가 시인 곳", n=len(gap), source_dataset="N16+N23",
    caveat="시 소속 읍·면은 농촌형 교통모델(농식품부·군) 대상이 아니고, 국토부 도시형 교통모델(78개 시) 대상일 수 있으나 시행 여부는 확인하지 않았다")
SCF = SCOPE[:-1] + ", 장날 이동 공백 읍·면]"
add("gap_flag_zero_stop_n", int(gap.flag_zero_stop.sum()), "곳", f"{SCF} 정류장(N1∪OSM)이 0개인 공백 읍·면 수(자료 확인 표시)",
    "공백 읍·면 중 n_stop == 0", n=len(gap), source_dataset="N1+N24",
    caveat="사후 표시이며 판정은 바꾸지 않았다. 섬은 버스 정류장이 없을 수 있으나 육지 읍·면의 0개는 정류장 위치자료 구멍일 가능성이 크다: "
           + "·".join(gap.loc[gap.flag_zero_stop, "adm_nm"].str.split().str[-2:].str.join(" ")))
add("gap_flag_zero_stop_mainland_n", int(gap.flag_zero_stop_mainland.sum()), "곳", f"{SCF} 정류장 0개이면서 섬이 아닌 공백 읍·면 수(자료 구멍 의심)",
    "공백 읍·면 중 n_stop == 0 이고 본토 폴리곤과 닿는 곳", n=len(gap), source_dataset="N1+N24+N16",
    caveat="사후 표시. 판정은 그대로이나 명단에서 「자료 확인 필요」로 다룬다: " + "·".join(gap.loc[gap.flag_zero_stop_mainland, "adm_nm"].str.split().str[-2:].str.join(" ")))
add("gap_flag_n1b_unverifiable_n", int(gap.flag_n1b_unverifiable.sum()), "곳",
    f"{SCF} 소속 시군의 N1b 정류장이 {N1B_MAX}개 이하라 BIS 구멍 보류 규칙(N1/N1b<0.5)을 검증할 수 없는 공백 읍·면 수",
    f"coverage_n1_vs_n1b.csv n1b ≤ {N1B_MAX} 시군 소속 공백 읍·면 — 해당 시군 " + str(int(gap.loc[gap.flag_n1b_unverifiable, "sigun_key"].nunique())) + "곳",
    n=len(gap), source_dataset="N1+N1b", caveat="사후 표시. N1b 가 비면 N1 이 비었는지 비교할 기준이 없다 — 이 읍·면들의 C2·C3 는 검증 불가")
print(summ.to_string()); print(sg.to_string()); print(gap[["priority_rank", "adm_nm", "type", "island", "pop65"]].head(15).to_string())
print("DRT 매칭 시군:", sorted(drt & set(b.sigun_key))[:80])
