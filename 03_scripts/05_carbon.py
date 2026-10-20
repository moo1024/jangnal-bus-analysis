"""05_carbon — 장날 합승 노선의 연간 CO2 감축 시나리오(범위로만 보고, 점추정 단정 금지).

산식(읍면 i, 연간):
  승용 대체분_i = N65_i × p × r × s ÷ occ × (2 × d_i × 1.3) × f_i × EF_car
  합승 추가분_i = ceil(N65_i × p × r ÷ cap) × (4 × d_i × 1.3) × f_i × EF_van        (차량당 장날 2회 왕복: 오전 도착·정오 귀가)
  ΔCO2 = Σ(승용 대체분 − 합승 추가분) ÷ 10^6  [tCO2/년]
  N65 = 읍면 65세 이상 인구(S9 2026-09) · d = 읍면 대표점→가장 가까운 정기장 직선거리 · 1.3 = 도로 우회계수(가정)
  f_i = 그 정기장의 2026년 장날 수(시장개설주기 끝자리로 달력 계산)
배출계수(출처):
  CO2/L = 순발열량(에너지법 시행규칙 별표 에너지열량 환산기준, 2022-11-21 개정: 휘발유 30.1 MJ/L·경유 35.3 MJ/L)
          × IPCC 2006 지침 기본 배출계수(Vol.2 Ch.3 Table 3.2.1: 휘발유 69,300·경유 74,100 kgCO2/TJ)
  g/km  = CO2/L ÷ 연비(가정 3단) — 실주행 연비 원문은 미확보라 가정으로 둔다
대상: 주 판정 공백 읍면(사전등록 4조건 AND). 3/4 후보군은 참고로 함께 계산.
치우침 방향(두 가지 모두 감축을 크게 보이게 하는 쪽):
  ① 승합 주행거리를 읍면 대표점↔시장 직선 왕복으로만 잡아 마을을 도는 수집 경로를 뺐다 → 수집경로 계수 1.5·2.0 판을 함께 계산
  ② s_car 에 「얻어타기」가 섞여 있다 — 운전자가 어차피 시장에 간다면 그 승용 이동은 줄지 않는다
"""
import _env; _env.cap()
import itertools, sys, datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

SEED = 20260725
HERE = Path(__file__).resolve().parent
PRO = HERE.parent / "01_data/processed"
sys.path.insert(0, str(HERE.parents[3] / "scripts"))
from 수치기록 import add  # noqa: E402

NCV = {"gasoline": 30.1, "diesel": 35.3}                 # MJ/L, 에너지법 시행규칙 별표
EF_TJ = {"gasoline": 69300, "diesel": 74100}             # kgCO2/TJ, IPCC 2006
CO2_L = {k: NCV[k] * 1e-6 * EF_TJ[k] for k in NCV}       # kgCO2/L
DETOUR = 1.3
CAP = 15
# 얹기형 판(사후 보조 지표 — 변경 이력 #8). 신규 차량 판은 차량당 장날 하루 4구간(오전 마을→시장 탑승·시장→마을 회송,
# 정오 마을→시장 회송·시장→마을 탑승)을 모두 새 운행으로 본다. 얹기형은 농촌형 교통모델 차량이 이미 그 읍·면 노선을 돌고 있다는 제안
# 전제이므로 회송 2구간은 기존 운행 일정에 흡수되고 이용자를 태운 2구간만 장날 추가 회차 거리로 본다(가정 — 실제 운행표 미대조).
NEW_VEHICLE_LEGS = 4     # 신규 차량: 차량당 장날 하루 대표점↔시장 편도 구간 수
OVERLAY_EXTRA_LEGS = 2   # 얹기형: 장날 추가 회차로 새로 생기는 편도 구간 수(탑승 구간만)
# 가정 3단: (감축 작게, 중간, 감축 크게)
A = {
    "p_visit": (0.05, 0.10, 0.15),   # 장날 하루에 시장에 가는 고령 인구 비율
    "r_switch": (0.3, 0.5, 0.7),     # 그중 장날버스 이용 비율
    "s_car": (0.3, 0.5, 0.7),        # 이용자 중 원래 승용차(자가·얻어타기)로 가던 비율
    "occ": (2.0, 1.5, 1.2),          # 승용차 1대당 탑승 인원
    "kmpl_car": (14.0, 12.0, 10.0),  # 휘발유 승용 실주행 연비 km/L
    "kmpl_van": (7.0, 8.5, 10.0),    # 경유 15인승 승합 연비 km/L
}

d = pd.read_csv(PRO / "eupmyeon_judged.csv", encoding="utf-8-sig", dtype={"adm_cd2": str})
mk = pd.read_csv(PRO / "markets_periodic.csv", encoding="utf-8-sig", dtype={"days": str})
year_days = pd.date_range("2026-01-01", "2026-12-31")


def n_market_days(digits: str) -> int:
    ds = {int(x) for x in str(digits).split("+")}
    return int(sum((day.day % 10) in ds for day in year_days))


mk["f"] = mk.days.map(n_market_days)
_, idx = cKDTree(mk[["x", "y"]].values).query(np.c_[d.rx, d.ry])
d["f"] = mk.f.values[idx]


def run(df, p_visit, r_switch, s_car, occ, kmpl_car, kmpl_van, route=1.0, legs=NEW_VEHICLE_LEGS):
    ef_car = CO2_L["gasoline"] / kmpl_car          # kg/km
    ef_van = CO2_L["diesel"] / kmpl_van
    riders = df.pop65 * p_visit * r_switch
    car_km = riders * s_car / occ * 2 * df.d_market_km * DETOUR * df.f
    veh = np.ceil(riders / CAP)
    van_km = veh * legs * df.d_market_km * DETOUR * df.f * route     # route = 마을 수집경로 계수(기본 1.0 = 직선 왕복만)
    return {"car_t": float((car_km * ef_car).sum() / 1000), "van_t": float((van_km * ef_van).sum() / 1000),
            "net_t": float(((car_km * ef_car) - (van_km * ef_van)).sum() / 1000), "vehicles": int(veh.sum()),
            "riders_per_day": float(riders.sum())}


gap = d[d.gap & ~d.hold & d.has_pop]
g34 = d[d.gap_3of4 & ~d.hold & d.has_pop]
rows = []
for tier, i in (("low", 0), ("mid", 1), ("high", 2)):
    kw = {k: v[i] for k, v in A.items()}
    rows.append({"set": "주 판정", "tier": tier, **kw, **run(gap, **kw)})
    rows.append({"set": "3/4 후보군", "tier": tier, **kw, **run(g34, **kw)})
res = pd.DataFrame(rows)
# 한 변수씩(나머지 중간) — 범위가 어디서 나오는지
oat = []
mid = {k: v[1] for k, v in A.items()}
for k, v in A.items():
    for j, lab in ((0, "low"), (2, "high")):
        kw = dict(mid); kw[k] = v[j]
        oat.append({"var": k, "level": lab, "value": v[j], **run(gap, **kw)})
oat = pd.DataFrame(oat)
# 전체 조합(3^6=729) 분포
grid = [run(gap, **dict(zip(A, c))) ["net_t"] for c in itertools.product(*A.values())]
res.to_csv(PRO / "carbon_scenarios.csv", index=False, encoding="utf-8-sig")
oat.to_csv(PRO / "carbon_oat.csv", index=False, encoding="utf-8-sig")
pd.Series(grid, name="net_t").to_csv(PRO / "carbon_grid729.csv", index=False)

SC = "[인구 2026-09·시장 2025-11-10 기준, 2026년 장날 달력, 주 판정 공백 읍·면]"
BIAS = ("치우침: 승합의 마을 수집경로를 빼 승합 배출이 과소(감축 과대 방향), 승용 출발 비율에 얻어타기가 섞여 감축 과대 가능 — "
        "수집경로 계수 판은 co2_cut_t_mid_route15·route20")
SRC = "S9+N2+EF_ncv"
m = res[res.set == "주 판정"].set_index("tier")
for t, K in (("low", "co2_cut_t_low"), ("mid", "co2_cut_t_mid"), ("high", "co2_cut_t_high")):
    add(K, round(m.loc[t, "net_t"], 0), "tCO2/년",
        f"{SC} 장날버스 연간 순 CO2 감축량 — 가정 {'감축 작게' if t=='low' else '중간' if t=='mid' else '감축 크게'} 단(승용 대체분 − 합승 승합 추가분)",
        "시나리오 산식(05_carbon.py 머리말). 배출계수 = 에너지법 시행규칙 별표 순발열량 × IPCC 2006 기본계수 ÷ 연비 가정",
        n=len(gap), source_dataset=SRC, caveat="가정 산정값이며 신뢰구간이 아니다. 실측 아님. 음수면 승합 운행 배출이 더 크다는 뜻. " + BIAS, decimals=0)
for rt, K in ((1.5, "co2_cut_t_mid_route15"), (2.0, "co2_cut_t_mid_route20")):
    add(K, round(run(gap, **mid, route=rt)["net_t"], 0), "tCO2/년",
        f"{SC} 장날버스 연간 순 CO2 감축량 — 중간 가정 + 승합 마을 수집경로 계수 {rt}(직선 왕복 거리 × {rt})",
        "시나리오 산식의 합승 추가분에 수집경로 계수를 곱함(나머지 중간 가정)", n=len(gap), source_dataset=SRC, decimals=0,
        caveat="수집경로 계수는 가정이다(실제 노선 미설계). 신뢰구간이 아니다. 얻어타기 치우침은 반영하지 않았다")
add("co2_grid_min_t", round(min(grid), 0), "tCO2/년", f"{SC} 가정 6개 변수 3단 전체 조합 729판 중 순 감축 최솟값", "3^6 조합 전수 계산",
    n=len(gap), source_dataset=SRC, caveat="신뢰구간이 아니다. 가정 조합의 범위. " + BIAS, decimals=0)
add("co2_grid_max_t", round(max(grid), 0), "tCO2/년", f"{SC} 가정 6개 변수 3단 전체 조합 729판 중 순 감축 최댓값", "3^6 조합 전수 계산",
    n=len(gap), source_dataset=SRC, caveat="신뢰구간이 아니다. 가정 조합의 범위. " + BIAS, decimals=0)
add("co2_grid_negative_pct", round(float(np.mean(np.array(grid) < 0) * 100), 1), "%", f"{SC} 729판 중 순 감축이 음수(승합 배출이 더 큼)인 조합 비율",
    "3^6 조합 전수 중 net<0 비율", n=729, source_dataset=SRC, caveat="가정 조합의 비율이며 확률이 아니다", decimals=1)
add("ops_vehicles_mid", int(m.loc["mid", "vehicles"]), "대", f"{SC} 중간 가정 장날 하루 필요 15인승 승합 대수(공백 읍·면 합)",
    "읍·면별 ceil(65세 이상 × 장날 방문 0.10 × 이용 0.5 ÷ 정원 15) 합", n=len(gap), source_dataset="S9", caveat="가정 산정값. 읍·면당 최소 1대로 올림")
add("riders_per_day_mid", round(m.loc["mid", "riders_per_day"], 0), "명", f"{SC} 중간 가정 장날 하루 장날버스 이용 고령 인구(공백 읍·면 합)",
    "65세 이상 × 0.10 × 0.5 합", n=len(gap), source_dataset="S9", caveat="가정 산정값", decimals=0)
add("co2_per_l_gasoline_kg", round(CO2_L["gasoline"], 3), "kgCO2/L", "[에너지열량 환산기준 2022-11-21 개정·IPCC 2006] 휘발유 1 L 연소 CO2",
    "순발열량 30.1 MJ/L × 69,300 kgCO2/TJ", source_dataset="EF_ncv", caveat="IPCC 2006 기본계수(국가 고유계수 아님)", decimals=3)
add("co2_per_l_diesel_kg", round(CO2_L["diesel"], 3), "kgCO2/L", "[에너지열량 환산기준 2022-11-21 개정·IPCC 2006] 경유 1 L 연소 CO2",
    "순발열량 35.3 MJ/L × 74,100 kgCO2/TJ", source_dataset="EF_ncv", caveat="IPCC 2006 기본계수(국가 고유계수 아님)", decimals=3)
add("market_days_2026_median", int(mk.f.median()), "일", "[2026년 달력, 전국 정기장 410곳] 정기장 1곳의 연간 장날 수 중앙값",
    "시장개설주기 끝자리 2개 × 2026년 날짜 계산", n=len(mk), source_dataset="N2")

# ── 사후 보조 지표(변경 이력 #8): 손익분기·얹기형 판 ─────────────────────
# 손익분기 ① 차량 1대가 장날 하루 태우는 이용자 수 k: 차량 대수를 이용자 ÷ k(연속)로 두면 읍·면마다
#   승용 대체분 − 합승 추가분 = 이용자 × d × 1.3 × f × (2·s·EF_car/occ − NEW_VEHICLE_LEGS·EF_van/k) 이라
#   순감축 0 이 되는 k* = NEW_VEHICLE_LEGS·EF_van·occ / (2·s·EF_car) 는 읍·면과 무관한 하나의 값이다.
ef_car_mid = CO2_L["gasoline"] / mid["kmpl_car"]; ef_van_mid = CO2_L["diesel"] / mid["kmpl_van"]
k_star = NEW_VEHICLE_LEGS * ef_van_mid * mid["occ"] / (2 * mid["s_car"] * ef_car_mid)
k_now = m.loc["mid", "riders_per_day"] / m.loc["mid", "vehicles"]
BE = ("사후 보조 지표(주 결과 아님, 사전등록 문서 변경 이력 #8). 가정값이며 신뢰구간이 아니다. 나머지 가정은 중간 단"
      f"(장날 방문 {mid['p_visit']}·이용 {mid['r_switch']}·승용 출발 {mid['s_car']}·승용 탑승 {mid['occ']}명·연비 승용 {mid['kmpl_car']}·승합 {mid['kmpl_van']} km/L). "
      f"수집경로 계수 1.5 를 곱하면 손익분기 탑승 인원도 1.5배({k_star*1.5:.1f}명)로 올라 15인승 정원에 가까워진다. 얻어타기 치우침은 반영하지 않았다")
add("co2_breakeven_riders", round(float(k_star), 1), "명",
    f"{SC} 중간 가정에서 순 CO2 감축이 0 이 되는 차량 1대당 장날 하루 평균 이용자 수(이 값 이상이면 순감축 양수, 신규 차량 판)",
    f"k* = {NEW_VEHICLE_LEGS}·EF_van·occ ÷ (2·s_car·EF_car), 차량 대수를 이용자 ÷ k 연속값으로 둔 해석해(읍·면 무관). "
    f"참고: 중간 가정의 실제 배정(읍·면별 정원 15 올림)은 차량당 {k_now:.1f}명",
    n=len(gap), source_dataset=SRC, caveat=BE, decimals=1)
# 손익분기 ② 승용 출발 비율 s*: 실제 배정 차량(올림) 그대로, 순감축이 s 에 선형이므로 s* = s_mid × 승합 배출 ÷ 승용 대체분
s_star = mid["s_car"] * m.loc["mid", "van_t"] / m.loc["mid", "car_t"]
add("co2_breakeven_car_pct", round(float(s_star * 100), 1), "%",
    f"{SC} 중간 가정에서 순 CO2 감축이 0 이 되는 이용자 중 원래 승용차로 가던 비율(이 값 이상이면 순감축 양수, 신규 차량 판)",
    "s* = s_mid × 합승 추가분 ÷ 승용 대체분(순감축이 s 에 선형). 차량 대수는 중간 가정 실제 배정(읍·면별 정원 15 올림)",
    n=len(gap), source_dataset=SRC, caveat=BE, decimals=1)
# 얹기형 판: 얹기형 읍·면은 장날 추가 회차 거리(탑승 2구간)만, 확인필요형은 신규 차량 전량
typ = pd.read_csv(PRO / "jangnal_gap_list.csv", encoding="utf-8-sig", dtype={"adm_cd2": str})[["adm_cd2", "type"]]
gt = gap.merge(typ, on="adm_cd2", how="left")
assert gt.type.notna().all() and len(gt) == len(gap)
ov = gt[gt.type == "얹기형"]; nv = gt[gt.type != "얹기형"]
r_ov = run(ov, **mid, legs=OVERLAY_EXTRA_LEGS); r_nv = run(nv, **mid)
net_inc = r_ov["net_t"] + r_nv["net_t"]
add("co2_cut_t_mid_overlay_incremental", round(net_inc, 0), "tCO2/년",
    f"{SC} 장날버스 연간 순 CO2 감축량 — 중간 가정, 얹기형 {len(ov)}곳은 장날 추가 회차 거리만·나머지 {len(nv)}곳은 신규 차량 전량 운행 배출 차감",
    f"얹기형: 합승 추가분 = 차량 × {OVERLAY_EXTRA_LEGS}구간(탑승 구간) × d × 1.3 × f × EF_van / 확인필요형: 신규 차량 {NEW_VEHICLE_LEGS}구간. "
    "승용 대체분은 두 판 동일",
    n=len(gap), source_dataset=SRC, decimals=0,
    caveat="사후 보조 지표(주 결과 아님, 사전등록 문서 변경 이력 #8). 가정 산정값이며 신뢰구간이 아니다. 추가 회차 거리 가정 = 농촌형 교통모델 차량이 "
           "이미 그 읍·면 노선을 운행해 회송 2구간은 기존 일정에 흡수되고 탑승 2구간만 새로 생긴다고 본 것(군별 운행표와 대조하지 않았다 — "
           "얹기형은 정의상 군 소속 전부이고 실제 운행 여부는 미확인). 수집경로 계수·얻어타기 치우침은 반영하지 않았다")
print("손익분기 k*", k_star, "현재", k_now, "s*", s_star, "얹기형판", net_inc, r_ov, r_nv)
print(res.to_string()); print(oat.to_string()); print("grid", min(grid), np.median(grid), max(grid), np.mean(np.array(grid) < 0))
print(CO2_L, mk.f.describe())
