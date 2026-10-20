"""03_cluster — 규칙 판정 vs K-means vs Ward 비교(같은 4변수, 표준화).

입력: processed/eupmyeon_judged.csv (판정 대상 = 인구 있음 & 보류 아님)
출력: processed/cluster_compare.csv · processed/cluster_k_scan.csv · numbers.json
비교 지표: ARI(규칙 이진 판정 vs 「공백 군집」 이진), ARI(규칙 vs 전체 군집 라벨), 일치·불일치 읍면 수.
「공백 군집」 = 중심의 (z시장거리 + z도보권밖비율 − z정류장밀도 + z고령비율) 이 가장 큰 군집(사전 고정).
"""
import _env; _env.cap()
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.mixture import GaussianMixture

SEED = 20260725
HERE = Path(__file__).resolve().parent
PRO = HERE.parent / "01_data/processed"
sys.path.insert(0, str(HERE.parents[3] / "scripts"))
from 수치기록 import add  # noqa: E402
SCOPE = "[인구 2026-09·시장 2025-11-10·정류장 2025-10-31/OSM 2026-10-12 기준, 판정 대상 읍·면]"

d = pd.read_csv(PRO / "eupmyeon_judged.csv", encoding="utf-8-sig", dtype={"adm_cd2": str})
b = d[d.has_pop & ~d.hold].copy()
X = pd.DataFrame({"z_mkt": np.log1p(b.d_market_km), "z_unc": b.unc_share,
                  "z_dens": np.log1p(b.stop_density), "z_old": b.old_ratio})
Z = StandardScaler().fit_transform(X)
W = np.array([1, 1, -1, 1])   # 공백 방향
rule = b.gap.values.astype(int)

scan = []
for k in range(3, 7):
    km = KMeans(k, n_init=20, random_state=SEED).fit(Z)
    wd = AgglomerativeClustering(k, linkage="ward").fit(Z)
    scan.append({"k": k, "kmeans_inertia": km.inertia_, "kmeans_silhouette": silhouette_score(Z, km.labels_),
                 "ward_silhouette": silhouette_score(Z, wd.labels_)})
scan = pd.DataFrame(scan)
# 엘보우: 관성 감소율이 직전 대비 가장 크게 꺾이는 k(2차 차분 최대)
inert = scan.kmeans_inertia.values
second = np.r_[np.nan, inert[:-2] - 2 * inert[1:-1] + inert[2:], np.nan]
scan["inertia_2nd_diff"] = second
scan.to_csv(PRO / "cluster_k_scan.csv", index=False, encoding="utf-8-sig")
k_sil = int(scan.loc[scan.kmeans_silhouette.idxmax(), "k"])


def gap_cluster(labels):
    cen = pd.DataFrame(Z).groupby(labels).mean().values @ W
    gid = int(np.argmax(cen))
    return (labels == gid).astype(int), gid


km = KMeans(k_sil, n_init=20, random_state=SEED).fit(Z)
wd = AgglomerativeClustering(k_sil, linkage="ward").fit(Z)
gm = GaussianMixture(k_sil, random_state=SEED, n_init=5).fit(Z)
labs = {"K-means": km.labels_, "Ward": wd.labels_, "GMM": gm.predict(Z)}
rows = [{"method": "규칙 판정(사전등록 4조건 AND)", "k": 2, "gap_n": int(rule.sum()), "ari_binary_vs_rule": 1.0,
         "ari_labels_vs_rule": 1.0, "both": int(rule.sum()), "rule_only": 0, "cluster_only": 0,
         "silhouette": np.nan, "elderly_in_gap": int(b.loc[rule == 1, "pop65"].sum())}]
for nm, lab in labs.items():
    gb, gid = gap_cluster(lab)
    rows.append({"method": nm, "k": k_sil, "gap_n": int(gb.sum()), "ari_binary_vs_rule": adjusted_rand_score(rule, gb),
                 "ari_labels_vs_rule": adjusted_rand_score(rule, lab), "both": int((gb & rule).sum()),
                 "rule_only": int((rule & (1 - gb)).sum()), "cluster_only": int((gb & (1 - rule)).sum()),
                 "silhouette": silhouette_score(Z, lab), "elderly_in_gap": int(b.loc[gb == 1, "pop65"].sum())})
    b[f"cl_{nm}"] = lab; b[f"gapcl_{nm}"] = gb
cmp_ = pd.DataFrame(rows)
cmp_["ari_kmeans_vs_ward_labels"] = adjusted_rand_score(labs["K-means"], labs["Ward"])
cmp_.to_csv(PRO / "cluster_compare.csv", index=False, encoding="utf-8-sig")
# 군집별 프로파일
prof = []
for nm in ("K-means", "Ward"):
    for c, g in b.groupby(f"cl_{nm}"):
        prof.append({"method": nm, "cluster": c, "n": len(g), "d_market_km_med": g.d_market_km.median(),
                     "unc_share_med": g.unc_share.median(), "stop_density_med": g.stop_density.median(),
                     "old_ratio_med": g.old_ratio.median(), "rule_gap_n": int(g.gap.sum()), "is_gap_cluster": int(g[f"gapcl_{nm}"].iloc[0])})
pd.DataFrame(prof).to_csv(PRO / "cluster_profile.csv", index=False, encoding="utf-8-sig")
b[["adm_cd2"] + [c for c in b.columns if c.startswith(("cl_", "gapcl_"))]].to_csv(PRO / "cluster_labels.csv", index=False, encoding="utf-8-sig")

add("kmeans_k_selected", k_sil, "개", f"{SCOPE} K-means 군집 수(실루엣 최대, k=3~6 탐색)", "표준화 4변수(log 시장거리·도보권 밖 비율·log 정류장밀도·고령비율), n_init=20",
    n=len(b), source_dataset="N16+S9+N2+N1+N24", caveat="엘보우(관성 2차 차분)도 함께 보고 — cluster_k_scan.csv")
for nm, key in (("K-means", "ari_rule_vs_kmeans"), ("Ward", "ari_rule_vs_ward"), ("GMM", "ari_rule_vs_gmm")):
    r = cmp_[cmp_.method == nm].iloc[0]
    add(key, round(float(r.ari_binary_vs_rule), 3), "", f"{SCOPE} 규칙 판정(공백/비공백)과 {nm} 「공백 군집」의 일치도(ARI)",
        f"Adjusted Rand Index, k={k_sil}. 공백 군집 = 중심의 공백 방향 합성값 최대 군집. 일치 {int(r.both)}곳·규칙만 {int(r.rule_only)}곳·군집만 {int(r.cluster_only)}곳",
        n=len(b), source_dataset="N16+S9+N2+N1+N24", caveat="점추정. 군집은 k·표준화 방식에 따라 경계가 바뀐다", decimals=3)
for nm, K in (("K-means", "silhouette_kmeans"), ("Ward", "silhouette_ward"), ("GMM", "silhouette_gmm")):
    add(K, round(float(cmp_.loc[cmp_.method == nm, "silhouette"].iloc[0]), 3), "", f"{SCOPE} {nm} k={k_sil} 실루엣 계수",
        "sklearn silhouette_score(유클리드, 표준화 4변수)", n=len(b), source_dataset="N16+S9+N2+N1+N24", decimals=3,
        caveat="군집 분리도 점추정 — 0.25~0.5 는 약한~보통 구조")
add("cluster_gap_n_kmeans", int(cmp_.loc[cmp_.method == "K-means", "gap_n"].iloc[0]), "곳", f"{SCOPE} K-means 공백 군집 읍·면 수",
    f"K-means k={k_sil}", n=len(b), source_dataset="N16+S9+N2+N1+N24")
print(scan.to_string()); print(cmp_.to_string()); print(pd.DataFrame(prof).to_string())
