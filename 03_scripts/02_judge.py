"""02_judge — 장날 이동 공백 읍면 판정(사전등록 4조건 AND) + 가설검정 + 민감도.

입력: processed/eupmyeon_base.gpkg · eupmyeon_villages.csv · eupmyeon_buildings.parquet · markets_periodic.csv · stops_merged.csv
출력: processed/eupmyeon_judged.csv(읍면 전수, 조건별 값·판정) · processed/sensitivity.csv · processed/tests.json
      numbers.json (수치기록.add)

판정 함수는 조건마다 하나씩 둔다. N21(정류장 정차노선 수)이 오면 cond_frequency 의 source="n21" 분기만 채우면 된다.
"""
import _env; _env.cap()
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import stats
from scipy.spatial import cKDTree

SEED = 20260725
rng = np.random.default_rng(SEED)
HERE = Path(__file__).resolve().parent
PRO = HERE.parent / "01_data/processed"
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from 수치기록 import add  # noqa: E402

SCOPE = "[인구 2026-09·시장 2025-11-10·정류장 2025-10-31/OSM 2026-10-12 기준, 전국 읍·면]"
SRC = "N16+S9+N2+N1+N24"
APPROX = "거리는 전부 직선(도보 15분 = 직선 1 km 근사, 실제 보행경로는 더 길다). C2 는 OSM 시민참여 마을 점(place=village·hamlet·isolated_dwelling) 기준이라 법정리 전수가 아니다"

# ── 사전등록 임계 ────────────────────────────────────────
WALK_M = 1000          # 도보 15분 ≈ 직선 1 km (근사)
UNC_SHARE = 0.20       # 마을 중 정류장 도보권 밖 비율
MARKET_KM = 5.0        # 가장 가까운 정기장 직선거리
DENS_Q = 0.25          # 정류장 밀도 하위 25 %
OLD_Q = 0.50           # 고령 비율 중앙값

em = gpd.read_file(PRO / "eupmyeon_base.gpkg")
vil = pd.read_csv(PRO / "eupmyeon_villages.csv", encoding="utf-8-sig", dtype={"adm_cd2": str})
bld = pd.read_parquet(PRO / "eupmyeon_buildings.parquet")
mk = pd.read_csv(PRO / "markets_periodic.csv", encoding="utf-8-sig")
em["adm_cd2"] = em.adm_cd2.astype(str)

# 대표점: 마을 점 무게중심(3개 이상), 아니면 폴리곤 대표점
em["rx"] = np.where(em.n_vil >= 3, em.cx_vil, em.rep_x)
em["ry"] = np.where(em.n_vil >= 3, em.cy_vil, em.rep_y)
em["rep_src"] = np.where(em.n_vil >= 3, "마을 무게중심", "폴리곤 대표점")
mtree = cKDTree(mk[["x", "y"]].values)
em["d_market_km"] = mtree.query(np.c_[em.rx, em.ry])[0] / 1000
em["d_market_km_poly"] = mtree.query(np.c_[em.rep_x, em.rep_y])[0] / 1000
em["stop_density"] = em.n_stop / em.area_km2

stree = cKDTree(pd.read_csv(PRO / "stops_merged.csv")[["x", "y"]].values)
rep_dstop = pd.Series(stree.query(np.c_[em.rx, em.ry])[0], index=em.adm_cd2)


def unc_share(radius_m, unit="village"):
    """읍면별 「정류장 radius_m 밖」 비율. 마을 점이 없으면 대표점 1개로 판정."""
    src = vil if unit == "village" else bld
    s = (src.d_stop > radius_m).groupby(src.adm_cd2).mean()
    out = em.adm_cd2.map(s)
    if unit == "village":
        out = out.fillna((rep_dstop > radius_m).astype(float).reindex(em.adm_cd2).set_axis(em.index))
    return out.values


em["unc_share"] = unc_share(WALK_M)

# 집계 대상: 인구 있음. BIS 구멍 시군은 판정 보류
em["has_pop"] = em["pop"].notna()
em["hold"] = em.bis_gap
base = em[em.has_pop & ~em.hold].copy()
n_all = int(em.has_pop.sum()); n_base = len(base)
DENS_CUT = base.stop_density.quantile(DENS_Q)
OLD_CUT = em.loc[em.has_pop, "old_ratio"].quantile(OLD_Q)


# ── 조건 함수 ───────────────────────────────────────────────────────
def cond_market(df, km=MARKET_KM, col="d_market_km"):
    return df[col] > km


def cond_access(df, share=UNC_SHARE, col="unc_share"):
    return df[col] >= share


def cond_frequency(df, source="density", q_cut=None):
    """「하루 3회」 조건. 이번 판은 정류장 밀도 근사(사전등록 변경 #1).
    N21 확보 시: source="n21" → df["max_routes"] <= 2 로 교체."""
    if source == "density":
        return df.stop_density <= (DENS_CUT if q_cut is None else q_cut)
    if source == "n21":
        return df["max_routes"] <= 2
    raise ValueError(source)


def cond_elderly(df, cut=None):
    return df.old_ratio >= (OLD_CUT if cut is None else cut)


def judge(df, rule="and4", **kw):
    c1 = cond_market(df, kw.get("km", MARKET_KM), kw.get("mcol", "d_market_km"))
    c2 = cond_access(df, kw.get("share", UNC_SHARE), kw.get("ucol", "unc_share"))
    c3 = cond_frequency(df, q_cut=kw.get("dens_cut"))
    c4 = cond_elderly(df, kw.get("old_cut"))
    if rule == "and4":
        return c1 & c2 & c3 & c4
    if rule == "3of4":
        return (c1.astype(int) + c2 + c3 + c4) >= 3
    if rule == "and3_noC3":
        return c1 & c2 & c4
    raise ValueError(rule)


for nm, f in (("C1", cond_market), ("C2", cond_access), ("C3", cond_frequency), ("C4", cond_elderly)):
    em[nm] = f(em).values
em["gap"] = judge(em).values
em["gap_3of4"] = judge(em, "3of4").values
base = em[em.has_pop & ~em.hold].copy()
gap = base[base.gap]

# ── 기록: 기본 규모 ─────────────────────────────────────────────────
add("eupmyeon_total_n", n_all, "곳", f"{SCOPE} 인구가 있는 읍·면 수(행정동 경계 ver20260701 읍·면 1,403곳 중 인구 미연결 1곳 제외)",
    "N16 읍·면 폴리곤 × S9 행정코드 10자리 결합", n=n_all, source_dataset="N16", caveat="달성군 구지면은 KOSIS 코드 불일치로 인구 미연결")
add("eupmyeon_judged_n", n_base, "곳", f"{SCOPE} 판정 대상 읍·면 수(BIS 구멍 시군 읍·면 제외)",
    "인구 있는 읍·면 − BIS 구멍(N1/N1b<0.5) 시군 소속 읍·면", n=n_base, source_dataset="N1+N1b+N16")
_cov = pd.read_csv(PRO / "coverage_n1_vs_n1b.csv", encoding="utf-8-sig", index_col=0)
add("bis_gap_sigun_n", int(((_cov.ratio < 0.5) & (_cov.n1b > 2) & (_cov.index != "(미분류)")).sum()), "곳",
    "[정류장 N1 2025-10-31·N1b 2026-07-03 기준, 전국 시군(광역시는 시도 단위) 156개 비교 가능 키] N1/N1b 정류장 수 비율 0.5 미만 시군 수",
    "시군별 N1 정류장 수 ÷ N1b 버스 정류장 수 < 0.5, N1b 2개 이하 키(코드 오류 2건: 경기도 평창군·충청북도 파주시) 제외", n=156,
    source_dataset="N1+N1b", caveat="비율 0.5 미만 키는 20개이나 2개는 N1b 시군 코드 오류. 18개 중 읍·면이 있는 시군은 16개")
add("eupmyeon_hold_n", int((em.has_pop & em.hold).sum()), "곳", f"{SCOPE} 판정 보류 읍·면 수(BIS 구멍 16개 시군 소속)",
    "coverage_n1_vs_n1b 비율 0.5 미만 시군(N1b 2개 이하 코드오류 키 2건 제외) 소속 읍·면", n=n_all, source_dataset="N1+N1b",
    caveat="정류장 위치자료가 비어 정류장 조건이 과대 판정될 수 있어 집계에서 뺐다")
add("market_gt5km_eupmyeon_n", int(cond_market(base).sum()), "곳", f"{SCOPE} 가장 가까운 정기장까지 직선 5 km 초과 읍·면 수(판정 대상 기준)",
    "읍·면 대표점(마을 점 무게중심) → 정기장 최근접 직선거리", n=n_base, source_dataset="N2+N24+N16", caveat="직선거리이며 도로거리는 더 길다")
add("village_unc1km_pct", round(float((vil.d_stop > WALK_M).mean() * 100), 1), "%",
    f"{SCOPE} 읍·면 마을 점 중 가장 가까운 버스정류장까지 직선 1 km 초과 비율(보류 시군 포함 전체)",
    "OSM place=village·hamlet·isolated_dwelling 점 → N1∪OSM 정류장 최근접 거리", n=len(vil), source_dataset="N24+N1",
    caveat="도보 15분을 직선 1 km 로 근사. OSM 마을 점은 법정리 전수가 아니다", decimals=1)
add("stop_density_q25", round(float(DENS_CUT), 2), "개/km²", f"{SCOPE} 판정 대상 읍·면 정류장 밀도 하위 25% 경계(C3 임계)",
    "판정 대상 읍·면 정류장 수 ÷ 면적의 25백분위", n=n_base, source_dataset="N1+N24+N16", caveat="「하루 3회」 운행 조건의 근사. 운행 횟수가 아니다", decimals=2)
add("old_ratio_median_pct", round(float(OLD_CUT * 100), 1), "%", f"{SCOPE} 읍·면 65세 이상 인구 비율 중앙값(C4 임계)",
    "S9 65세 이상(C2≥70) ÷ 총인구, 읍·면 중앙값", n=n_all, source_dataset="S9", decimals=1)
for c, k, d in (("C1", "cond_c1_n", "시장 5 km 초과"), ("C2", "cond_c2_n", "마을 20% 이상 정류장 1 km 밖"),
                ("C3", "cond_c3_n", "정류장 밀도 하위 25%"), ("C4", "cond_c4_n", "고령 비율 중앙값 이상")):
    cv = {"C1": "직선거리 근사(도로거리는 더 길다)", "C2": APPROX, "C3": "「하루 3회」 운행 조건 대신 정류장 밀도 근사 — 운행 횟수가 아니다",
          "C4": "주민등록 인구 기준"}[c]
    add(k, int(base[c].sum()), "곳", f"{SCOPE} 판정 대상 읍·면 중 조건 {c}({d}) 충족 수", "사전등록 조건 단독 적용", n=n_base, source_dataset=SRC,
        caveat=cv)

g_n = len(gap); g_old = int(gap.pop65.sum())
add("jangnal_gap_eupmyeon_n", g_n, "곳", f"{SCOPE} 장날 이동 공백 읍·면 수(사전등록 4조건 AND, 판정 대상 기준)",
    "C1 시장>5 km AND C2 마을 정류장 1 km 밖≥20% AND C3 정류장 밀도 하위25% AND C4 고령≥중앙값", n=n_base, source_dataset=SRC,
    caveat="C3 는 운행 횟수 대신 정류장 밀도 근사. BIS 구멍 16개 시군 읍·면은 보류로 제외. " + APPROX +
    ". N1b 가 거의 빈 시군(N1b 5개 이하)에서는 BIS 구멍 여부를 검증할 수 없어 정류장 0개 공백 읍·면 등은 04_typology 명단에 자료 확인 표시를 붙였다")
add("jangnal_gap_elderly_n", g_old, "명", f"{SCOPE} 장날 이동 공백 읍·면 65세 이상 인구 합계",
    "공백 판정 읍·면의 S9 65세 이상 인구 합", n=g_n, source_dataset="S9",
    caveat="읍·면 전체 고령인구 합이며 실제 장날 이용자 수가 아니다. 공백 판정은 " + APPROX)
add("jangnal_gap_pct_of_eupmyeon", round(g_n / n_base * 100, 1), "%", f"{SCOPE} 판정 대상 읍·면 중 장날 이동 공백 비율",
    "공백 읍·면 ÷ 판정 대상 읍·면", n=n_base, source_dataset=SRC, decimals=1, caveat=APPROX)
g3 = base[base.gap_3of4]
add("jangnal_gap_3of4_n", len(g3), "곳", f"{SCOPE} 4조건 중 3개 이상 충족 읍·면 수(후보군, 민감도)",
    "사전등록 민감도 — 판정 규칙 4조건 AND → 3/4 충족", n=n_base, source_dataset=SRC)
add("jangnal_gap_3of4_elderly_n", int(g3.pop65.sum()), "명", f"{SCOPE} 3/4 충족 후보군 읍·면 65세 이상 인구 합계",
    "3/4 충족 읍·면 S9 65세 이상 합", n=len(g3), source_dataset="S9", caveat="후보군 — 주 판정이 아니다")

# 보류 읍·면 참고 판정(OSM 보완 정류장 기준)
hold = em[em.has_pop & em.hold]
add("hold_gap_reference_n", int(judge(hold).sum()), "곳", f"{SCOPE} 판정 보류 읍·면 중 같은 규칙을 적용하면 공백인 수(참고값)",
    "보류 시군 읍·면에 4조건 AND 적용(정류장=N1∪OSM)", n=len(hold), source_dataset=SRC,
    caveat="정류장 자료 누락으로 과대 판정 가능 — 집계에 넣지 않는 참고값")

# ── 가설검정 ───────────────────────────────────────────────────────
T = {}


def boot_spearman(x, y, B=2000, batch=250):
    x = np.asarray(x); y = np.asarray(y); n = len(x); out = []
    for _ in range(B // batch):
        idx = rng.integers(0, n, size=(batch, n))
        for r in idx:
            out.append(stats.spearmanr(x[r], y[r]).statistic)
    return np.percentile(out, [2.5, 97.5])


def fisher_ci(r, n):
    z = np.arctanh(r); se = 1 / np.sqrt(n - 3)
    return np.tanh([z - 1.96 * se, z + 1.96 * se])


def rel_tests(x, y, name):
    x = np.asarray(x, float); y = np.asarray(y, float)
    sp = stats.spearmanr(x, y); pe = stats.pearsonr(x, y); kt = stats.kendalltau(x, y)
    perm = stats.permutation_test((x,), lambda a: stats.spearmanr(a, y).statistic, permutation_type="pairings",
                                  n_resamples=2000, random_state=SEED)
    sh = stats.shapiro(x[:5000]); sh2 = stats.shapiro(y[:5000])
    T[name] = {"n": len(x), "spearman": [sp.statistic, sp.pvalue], "spearman_boot_ci": boot_spearman(x, y).tolist(),
               "spearman_fisher_ci": fisher_ci(sp.statistic, len(x)).tolist(),
               "pearson": [pe.statistic, pe.pvalue], "pearson_ci": list(pe.confidence_interval()),
               "kendall": [kt.statistic, kt.pvalue], "perm_p": perm.pvalue,
               "shapiro_p_x": sh.pvalue, "shapiro_p_y": sh2.pvalue,
               "skew_x": stats.skew(x), "skew_y": stats.skew(y)}
    return T[name]


h1 = rel_tests(base.old_ratio, base.unc_share, "H1_old_vs_unc")
h2 = rel_tests(base.d_market_km, base.unc_share, "H2_market_vs_unc")
for key, h, d in (("h1_spearman_rho", h1, "읍·면 65세 이상 비율과 정류장 1 km 밖 마을 비율의 순위상관"),
                  ("h2_spearman_rho", h2, "가장 가까운 정기장 거리와 정류장 1 km 밖 마을 비율의 순위상관")):
    add(key, round(float(h["spearman"][0]), 3), "", f"{SCOPE} {d}(판정 대상 읍·면)",
        "Spearman ρ, 95% CI = 부트스트랩 2,000회 백분위(읍·면 재표본). 정규성 미충족(Shapiro p<0.001)으로 Pearson 대신 채택",
        n=h["n"], ci=[round(v, 3) for v in h["spearman_boot_ci"]], p=float(f"{h['spearman'][1]:.3g}"), source_dataset=SRC,
        caveat="상관이며 인과가 아니다. Bonferroni 기준 0.0167", decimals=3)

# 기법 비교용(H1·H2): Pearson·Kendall
for K_P, K_K, h, d in (("h1_pearson_r", "h1_kendall_tau", h1, "H1(고령 비율 vs 도보권 밖 마을 비율)"),
                       ("h2_pearson_r", "h2_kendall_tau", h2, "H2(정기장 거리 vs 도보권 밖 마을 비율)")):
    add(K_P, round(float(h["pearson"][0]), 3), "", f"{SCOPE} {d} Pearson r — 기법 비교용(채택 안 함)",
        "Pearson 적률상관, 95% CI = Fisher z(scipy). 정규성 미충족(Shapiro p<0.001)으로 부적합", n=h["n"],
        ci=[round(float(v), 3) for v in h["pearson_ci"]], p=float(f"{h['pearson'][1]:.3g}"), source_dataset=SRC, decimals=3,
        caveat=(f"두 변수 분포가 치우쳐(왜도 {h['skew_x']:.1f} / {h['skew_y']:.1f}) 선형 상관이 꼬리 값에 끌린다" if K_P == "h1_pearson_r"
                else f"정기장 거리 분포가 치우쳐(왜도 {h['skew_x']:.1f}, 섬 읍·면의 극단 거리) 이상치에 끌린다"))
    tci = fisher_ci(h["kendall"][0], h["n"])
    add(K_K, round(float(h["kendall"][0]), 3), "", f"{SCOPE} {d} Kendall τ — 기법 비교용",
        "Kendall τ-b, 95% CI = Fisher z 근사", n=h["n"], ci=[round(float(tci[0]), 3), round(float(tci[1]), 3)],
        p=float(f"{h['kendall'][1]:.3g}"), source_dataset=SRC, decimals=3, caveat="CI 는 근사")

# H3 시 vs 군
a = base.loc[base.kind == "시", "unc_share"].values; b = base.loc[base.kind == "군", "unc_share"].values
mw = stats.mannwhitneyu(a, b, alternative="two-sided")
rbc = 1 - 2 * mw.statistic / (len(a) * len(b))      # rank-biserial (시 기준: 양수 = 시가 작다)
lev = stats.levene(a, b); wt = stats.ttest_ind(a, b, equal_var=False)
perm3 = stats.permutation_test((a, b), lambda u, v: np.mean(u) - np.mean(v), n_resamples=2000, random_state=SEED)
bs = []
for _ in range(2000):
    aa = rng.choice(a, len(a)); bb = rng.choice(b, len(b))
    u = stats.mannwhitneyu(aa, bb).statistic; bs.append(1 - 2 * u / (len(a) * len(b)))
T["H3_si_vs_gun"] = {"n_si": len(a), "n_gun": len(b), "median_si": float(np.median(a)), "median_gun": float(np.median(b)),
                     "mean_si": float(a.mean()), "mean_gun": float(b.mean()), "mwu_p": mw.pvalue, "rank_biserial": rbc,
                     "rbc_boot_ci": np.percentile(bs, [2.5, 97.5]).tolist(), "levene_p": lev.pvalue,
                     "welch_t": wt.statistic, "welch_p": wt.pvalue, "welch_ci": list(wt.confidence_interval()),
                     "perm_p": perm3.pvalue}
add("h3_rank_biserial", round(float(rbc), 3), "", f"{SCOPE} 시 소속 읍·면과 군 소속 읍·면의 정류장 1 km 밖 마을 비율 차이 효과크기(rank-biserial, 양수=시 쪽이 낮음)",
    "Mann-Whitney U(양측), 95% CI = 부트스트랩 2,000회 백분위", n=len(a) + len(b),
    ci=[round(v, 3) for v in T["H3_si_vs_gun"]["rbc_boot_ci"]], p=float(f"{mw.pvalue:.3g}"), source_dataset=SRC, decimals=3,
    caveat=f"시 {len(a)}곳·군 {len(b)}곳. 상관이며 인과가 아니다")

add("h3_welch_mean_diff_pp", round(float((a.mean() - b.mean()) * 100), 1), "%p",
    f"{SCOPE} 시 소속 − 군 소속 읍·면 정류장 1 km 밖 마을 비율 평균 차이 — 기법 비교용(채택 안 함)",
    "Welch t검정(Levene p<0.001 등분산 기각), 95% CI = Welch t 구간", n=len(a) + len(b),
    ci=[round(float(v) * 100, 1) for v in wt.confidence_interval()], p=float(f"{wt.pvalue:.3g}"), source_dataset=SRC, decimals=1,
    caveat="정규성 미충족(중앙값 0 에 몰린 분포)이라 Mann-Whitney 를 채택")

# ── 이질성: 시도별·시군별 공백 비율 ─────────────────────────────────
def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


het = []
for col in ("sido_n", "kind"):
    for k, gdf in base.groupby(col):
        lo, hi = wilson(int(gdf.gap.sum()), len(gdf))
        rr = stats.spearmanr(gdf.old_ratio, gdf.unc_share) if len(gdf) >= 10 else None
        het.append({"axis": col, "group": k, "n": len(gdf), "gap_n": int(gdf.gap.sum()), "gap_pct": gdf.gap.mean() * 100,
                    "gap_ci_lo": lo * 100, "gap_ci_hi": hi * 100, "gap_elderly": int(gdf.loc[gdf.gap, "pop65"].sum()),
                    "unc_median": gdf.unc_share.median(), "h1_rho": rr.statistic if rr else np.nan, "h1_p": rr.pvalue if rr else np.nan})
het = pd.DataFrame(het)
het.to_csv(PRO / "heterogeneity.csv", index=False, encoding="utf-8-sig")
_sd = het[(het.axis == "sido_n") & het.h1_p.notna()]
BONF_SIDO = 0.05 / len(_sd)
add("h1_sido_tests_n", int(len(_sd)), "건", f"{SCOPE} 시도별로 쪼갠 H1 Spearman 검정 수(판정 대상 10곳 이상 시도)",
    "heterogeneity.csv 시도 행 중 ρ 계산 가능(n≥10) 행 수", n=n_base, source_dataset=SRC,
    caveat="부산(판정 대상 5곳)은 계산하지 않았다. 시/군 2건은 별도")
add("h1_sido_bonf_pass_n", int((_sd.h1_p < BONF_SIDO).sum()), "건", f"{SCOPE} 시도별 H1 검정 중 Bonferroni(0.05÷검정 수) 기준 통과 수",
    f"p < 0.05/{len(_sd)} — 통과: " + "·".join(_sd.loc[_sd.h1_p < BONF_SIDO, "group"]) +
    " / 보정 전 0.05 만 통과: " + "·".join(_sd.loc[(_sd.h1_p < 0.05) & (_sd.h1_p >= BONF_SIDO), "group"]),
    n=int(len(_sd)), source_dataset=SRC, caveat="이질성 분석 — 상관이며 인과가 아니다. 부호는 시도마다 다르다")
for kd, K_GAP, K_RHO in (("시", "gap_pct_si", "h1_rho_si"), ("군", "gap_pct_gun", "h1_rho_gun")):
    r = het[(het.axis == "kind") & (het.group == kd)].iloc[0]
    add(K_GAP, round(r.gap_pct, 1), "%", f"{SCOPE} {kd} 소속 판정 대상 읍·면 중 공백 비율",
        "4조건 AND 공백 읍·면 ÷ 해당 읍·면, 95% CI = Wilson 구간", n=int(r.n), ci=[round(r.gap_ci_lo, 1), round(r.gap_ci_hi, 1)],
        source_dataset=SRC, decimals=1)
    rho_ci = fisher_ci(r.h1_rho, int(r.n))
    add(K_RHO, round(float(r.h1_rho), 3), "",
        f"{SCOPE} {kd} 소속 읍·면만 본 H1 순위상관(65세 이상 비율 vs 정류장 1 km 밖 마을 비율)",
        "Spearman ρ, 95% CI = Fisher z 변환", n=int(r.n), ci=[round(float(rho_ci[0]), 3), round(float(rho_ci[1]), 3)],
        p=float(f"{r.h1_p:.3g}"), source_dataset=SRC, decimals=3, caveat="이질성 분석 — 상관이며 인과가 아니다")

# ── 민감도 ───────────────────────────────────────────────────────────
S = []
def sens(label, mask, kind):
    S.append({"label": label, "kind": kind, "gap_n": int(mask.sum()), "elderly": int(base.loc[mask[mask].index, "pop65"].sum())})


sens("주 판정(사전등록)", judge(base), "기준")
for r_m in (700, 1500):
    base[f"unc_{r_m}"] = pd.Series(unc_share(r_m), index=em.index).loc[base.index]
    sens(f"도보권 반경 {r_m/1000:g} km", judge(base, ucol=f"unc_{r_m}"), "반경")
for sh in (0.10, 0.30):
    sens(f"도보권 밖 마을 비율 {int(sh*100)}%", judge(base, share=sh), "임계")
for km in (3, 7):
    sens(f"시장 거리 {km} km", judge(base, km=km), "임계")
sens("고령 비율 3분위수(상위 1/3)", judge(base, old_cut=em.loc[em.has_pop, "old_ratio"].quantile(2 / 3)), "임계")
sens("정류장 밀도 하위 1/3", judge(base, dens_cut=base.stop_density.quantile(1 / 3)), "임계")
sens("정류장 밀도 하위 1/5", judge(base, dens_cut=base.stop_density.quantile(0.20)), "임계")
sens("규칙: 4조건 중 3개", judge(base, "3of4"), "규칙")
sens("규칙: C3 제외 3조건 AND", judge(base, "and3_noC3"), "규칙")
sens("대표점: 폴리곤 대표점", judge(base, mcol="d_market_km_poly"), "대표점")
# 건물 기준 C2(건물 100동 이상 읍·면만)
bsub = base[base.n_bld >= 100].copy()
bsub["unc_bld"] = pd.Series(unc_share(WALK_M, "building"), index=em.index).loc[bsub.index]
m_v = judge(bsub); m_b = judge(bsub, ucol="unc_bld")
S.append({"label": f"단위: 건물(100동 이상 읍·면 {len(bsub)}곳만, 마을 기준 {int(m_v.sum())}곳 대비)", "kind": "단위",
          "gap_n": int(m_b.sum()), "elderly": int(bsub.loc[m_b, "pop65"].sum())})
S = pd.DataFrame(S)
S.to_csv(PRO / "sensitivity.csv", index=False, encoding="utf-8-sig")
SCB = f"{SCOPE[:-1]}, 건물 100동 이상 판정 대상 읍·면 {len(bsub)}곳]"
add("sens_unit_village_n", int(m_v.sum()), "곳", f"{SCB} 마을 점 단위 C2 로 판정한 공백 읍·면 수(단위 민감도 비교 기준)",
    "건물 100동 이상 읍·면 부분집합에 주 판정(마을 점 C2) 적용", n=len(bsub), source_dataset=SRC, caveat=APPROX)
add("sens_unit_building_n", int(m_b.sum()), "곳", f"{SCB} 건물 단위 C2 로 판정한 공백 읍·면 수(단위 민감도)",
    "같은 부분집합에서 C2 를 「건물 중 정류장 1 km 밖 비율 ≥ 20%」로 교체", n=len(bsub), source_dataset="N16+S9+N2+N1+N24(건물)",
    caveat="OSM 건물 수록률이 지역마다 달라 주 단위에서 내렸다(사전등록 변경 #4). 분모가 달라 민감도 범위에 넣지 않는다")
add("sens_unit_overlap_n", int((m_v & m_b).sum()), "곳", f"{SCB} 마을 점 단위와 건물 단위 판정에서 함께 공백인 읍·면 수",
    "두 판정의 교집합", n=len(bsub), source_dataset=SRC, caveat=f"단위 선택이 공백 수를 크게 바꾼다. 같은 부분집합에서 도보권 밖 비율 평균이 건물 기준 {bsub.unc_bld.mean()*100:.1f}% · 마을 기준 "
    f"{bsub.unc_share.mean()*100:.1f}% — OSM 건물은 정류장 가까운 중심지에 더 많이 수록돼 있어 건물 기준이 도보권 밖을 적게 잡는다(해석, 검정 아님)")
main_rows = S[S.kind.isin(["기준", "반경", "임계", "규칙", "대표점"])]
add("sensitivity_gap_n_min", int(main_rows.gap_n.min()), "곳", f"{SCOPE} 민감도 12판(임계·반경·판정 규칙·대표점) 중 공백 읍·면 최솟값(건물 단위 판은 분모가 413곳 부분집합이라 범위에서 제외)",
    "사전등록 민감도 전부 적용 후 최솟값 — " + main_rows.loc[main_rows.gap_n.idxmin(), "label"], n=n_base, source_dataset=SRC,
    caveat="신뢰구간이 아니다. 판정 설정을 바꿨을 때의 범위")
add("sensitivity_gap_n_max", int(main_rows.gap_n.max()), "곳", f"{SCOPE} 민감도 12판 중 공백 읍·면 최댓값(건물 단위 판은 분모가 413곳 부분집합이라 범위에서 제외)",
    "사전등록 민감도 전부 적용 후 최댓값 — " + main_rows.loc[main_rows.gap_n.idxmax(), "label"], n=n_base, source_dataset=SRC,
    caveat="신뢰구간이 아니다. 판정 설정을 바꿨을 때의 범위")
# 주 판정 공백이 다른 판에서도 남는 비율(견고성)
keep = []
for lab, msk in (("r700", judge(base, ucol="unc_700")), ("r1500", judge(base, ucol="unc_1500")), ("km3", judge(base, km=3)),
                 ("km7", judge(base, km=7)), ("sh10", judge(base, share=0.1)), ("sh30", judge(base, share=0.3)),
                 ("poly", judge(base, mcol="d_market_km_poly"))):
    keep.append(msk[base.gap].mean() if base.gap.any() else np.nan)
T["robust_retained_share_by_variant"] = keep
# 좁히는 판(조건을 더 엄격하게 → 주 판정의 부분집합)의 잔존율. 넓히는 판(반경 0.7 km·비율 10%·시장 3 km)은 100% 가 자동이라 견고성 근거가 아니다
narrow = (("retained_pct_r1500", "도보권 반경 1.5 km(정류장이 더 멀어야 도보권 밖)", judge(base, ucol="unc_1500")),
          ("retained_pct_sh30", "도보권 밖 마을 비율 30%", judge(base, share=0.3)),
          ("retained_pct_km7", "시장 거리 7 km", judge(base, km=7)),
          ("retained_pct_old33", "고령 비율 상위 1/3", judge(base, old_cut=em.loc[em.has_pop, "old_ratio"].quantile(2 / 3))),
          ("retained_pct_dens20", "정류장 밀도 하위 1/5", judge(base, dens_cut=base.stop_density.quantile(0.20))))
for K, lab, msk in narrow:
    add(K, round(float(msk[base.gap].mean() * 100), 0), "%", f"{SCOPE} 주 판정 공백 읍·면 중 좁히는 판({lab})에서도 공백으로 남는 비율",
        "좁히는 판 공백 ∩ 주 판정 공백 ÷ 주 판정 공백", n=g_n, source_dataset=SRC, decimals=0,
        caveat="신뢰구간이 아니다. 판정 설정을 엄격하게 바꿨을 때의 잔존 비율")
# 견고 공백(사후 보조 지표 — 변경 이력 #8). 주 판정은 그대로 두고, 민감도 12판(주 판정·건물 단위 판 제외,
# main_rows 와 같은 범위) 중 ROBUST_K 판 이상에서 공백인 읍·면을 센다. 정의는 결과를 보기 전에 9/12 로 고정했다.
ROBUST_K = 9
_old33 = em.loc[em.has_pop, "old_ratio"].quantile(2 / 3)
V12 = {"r700": judge(base, ucol="unc_700"), "r1500": judge(base, ucol="unc_1500"),
       "sh10": judge(base, share=0.10), "sh30": judge(base, share=0.30), "km3": judge(base, km=3), "km7": judge(base, km=7),
       "old33": judge(base, old_cut=_old33), "dens33": judge(base, dens_cut=base.stop_density.quantile(1 / 3)),
       "dens20": judge(base, dens_cut=base.stop_density.quantile(0.20)), "3of4": judge(base, "3of4"),
       "noC3": judge(base, "and3_noC3"), "poly": judge(base, mcol="d_market_km_poly")}
assert len(V12) == len(main_rows) - 1 == 12
votes = pd.DataFrame(V12).sum(axis=1)
base["sens_votes12"] = votes
rob = votes >= ROBUST_K
RCV = ("사후 보조 지표(주 판정 아님, 사전등록 문서 변경 이력 #8). 신뢰구간이 아니다. 넓히는 판 6개(반경 0.7 km·비율 10%·시장 3 km·"
       "밀도 하위 1/3·3/4 규칙·C3 제외)는 주 판정 공백이면 자동으로 공백이라, 9판 이상은 좁히는 판 5개·대표점 판 1개 중 3개 이상에서 "
       "남았다는 뜻이다. 좁히는 판은 주 판정의 부분집합이라 주 판정 밖 읍·면은 최대 7판이어서 견고 공백은 모두 주 판정 공백이다")
add("robust_gap_9of12_n", int(rob.sum()), "곳", f"{SCOPE} 민감도 12판 중 9판 이상에서 공백으로 남는 읍·면 수(견고 공백, 판정 대상 기준)",
    "민감도 12판(반경 2·임계 7·규칙 2·대표점 1, 건물 단위 판 제외)별 4조건 판정 → 읍·면별 공백 판 수 ≥ 9", n=n_base,
    source_dataset=SRC, caveat=RCV + ". " + APPROX)
add("robust_gap_9of12_elderly_n", int(base.loc[rob, "pop65"].sum()), "명", f"{SCOPE} 견고 공백(민감도 12판 중 9판 이상) 읍·면 65세 이상 인구 합계",
    "견고 공백 읍·면의 S9 65세 이상 인구 합", n=int(rob.sum()), source_dataset="S9",
    caveat="읍·면 전체 고령인구 합이며 실제 장날 이용자 수가 아니다. " + RCV)
add("robust_gap_9of12_in_main_n", int((rob & base.gap).sum()), "곳", f"{SCOPE} 견고 공백 읍·면 중 주 판정(사전등록 4조건 AND) 공백 {g_n}곳에 드는 수",
    "견고 공백 ∩ 주 판정 공백", n=g_n, source_dataset=SRC, caveat=RCV)
add("robust_gap_9of12_pct_of_main", round(float(rob[base.gap].mean() * 100), 0), "%",
    f"{SCOPE} 주 판정 공백 읍·면 중 견고 공백(민감도 12판 중 9판 이상)인 비율",
    "견고 공백 ∩ 주 판정 공백 ÷ 주 판정 공백", n=g_n, source_dataset=SRC, decimals=0, caveat=RCV)
add("radius_sensitive_n", int((base.gap & ~V12["r1500"]).sum()), "곳",
    f"{SCOPE} 주 판정 공백 읍·면 중 도보권 반경 1.5 km 판에서 공백이 아니게 되는 수(반경에 민감한 곳)",
    "주 판정 공백 − (주 판정 공백 ∩ 반경 1.5 km 판 공백)", n=g_n, source_dataset=SRC,
    caveat="신뢰구간이 아니다. 판정 설정을 바꿨을 때의 차이. 사후 보조 지표(사전등록 문서 변경 이력 #8)")
base[["adm_cd2", "sens_votes12"]].assign(robust=rob.values, gap=base.gap.values).to_csv(
    PRO / "robust_votes.csv", index=False, encoding="utf-8-sig")
print("견고 공백(≥9/12)", int(rob.sum()), "주판정 내", int((rob & base.gap).sum()), "표 분포(주 판정):",
      votes[base.gap].value_counts().sort_index().to_dict())

# C3 임계 기준 집단 비교(사전등록 문구 「전국 읍면」 = 보류 포함 전체로 계산한 판)
DENS_CUT_ALL = em.loc[em.has_pop, "stop_density"].quantile(DENS_Q)
add("sens_c3_cut_allem_n", int(judge(base, dens_cut=DENS_CUT_ALL).sum()), "곳",
    f"{SCOPE} C3 임계를 보류 포함 전체 읍·면 하위 25%({DENS_CUT_ALL:.2f}개/km²)로 계산했을 때 공백 읍·면 수(비교값)",
    "주 판정은 판정 대상(보류 제외)에서 25백분위를 계산 — 사전등록 문구(전국 읍면)와의 차이를 비교. 사전등록 문서 변경 이력 #5",
    n=n_base, source_dataset=SRC, caveat="보류 시군은 정류장 자료가 비어 밀도가 낮게 잡히므로 보류 포함 분위수는 임계를 낮춘다")

# 시장 쪽: 정기장 500 m 안 정류장 없음
d500 = stree.query(mk[["x", "y"]].values)[0]
add("market_no_stop500_n", int((d500 > 500).sum()), "곳", "[시장 2025-11-10·정류장 2025-10-31/OSM 2026-10-12 기준, 전국 정기장] 반경 500 m 안에 버스정류장이 없는 정기장 수",
    "정기장 좌표 → N1∪OSM 정류장 최근접 직선거리 > 500 m", n=len(mk), source_dataset="N2+N1+N24", caveat="BIS 구멍 시군 정기장 포함")
add("markets_periodic_n", len(mk), "곳", "[시장 2025-11-10 기준, 전국] 분석에 쓴 정기장(5일장 주기) 수",
    "전통시장 표준데이터 시장개설주기 날짜형(매일 제외) 411곳 중 좌표 확보 410곳", n=1393, source_dataset="N2",
    caveat="좌표 결측 9곳 중 8곳은 주소의 읍·면 대표점으로 대체, 1곳 제외")

cols = ["adm_cd2", "adm_nm", "sido_n", "sigun", "sigun_key", "kind", "area_km2", "pop", "pop65", "old_ratio", "n_vil", "n_bld",
        "n_stop", "n_stop_n1", "n_stop_osm", "stop_density", "d_market_km", "d_market_km_poly", "unc_share", "rep_src",
        "rx", "ry", "has_pop", "hold", "C1", "C2", "C3", "C4", "gap", "gap_3of4"]
em[cols].to_csv(PRO / "eupmyeon_judged.csv", index=False, encoding="utf-8-sig")
json.dump(T, open(PRO / "tests.json", "w"), ensure_ascii=False, indent=1, default=float)
print("판정 대상", n_base, "공백", g_n, "고령", g_old, "3/4", len(g3))
print("임계: 밀도", round(DENS_CUT, 3), "고령", round(OLD_CUT, 3))
print(base[["C1", "C2", "C3", "C4"]].sum().to_dict())
print(S.to_string())
print(het.to_string())
print(json.dumps(T, ensure_ascii=False, indent=1, default=float))
