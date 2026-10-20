"""01_clean — 읍면 기본표를 만든다(분석 단위: 읍·면, 그 아래 건물).

입력(raw, 읽기만): N16 경계 · S9 인구 · N2 시장 · N1 정류장 · N24 OSM 정류장·시장 · (processed) OSM 건물·커버리지표
출력(processed):
  markets_periodic.csv   정기장 좌표·장날 끝자리·좌표 출처·OSM 대조
  stops_merged.csv       N1 ∪ OSM 정류장(30 m 중복 제거), EPSG:5179
  eupmyeon_base.gpkg     읍면 폴리곤 + 인구·고령·대표점·건물 수·정류장 수
  quality_log.json       품질 진단(결측·중복·대체 건수)
좌표계: EPSG:5179(미터). 거리는 전부 직선거리.
"""
import _env; _env.cap()
import json, re, sys
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
from pyproj import Transformer

SEED = 20260725
np.random.seed(SEED)
HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "01_data/raw"
PRO = HERE.parent / "01_data/processed"
TF = Transformer.from_crs(4326, 5179, always_xy=True)
Q = {}

# ── 1. 읍면 폴리곤 ────────────────────────────────────────────────
g = gpd.read_file(RAW / "HangJeongDong_ver20260701.geojson")
Q["n16_polygons"] = len(g)
em = g[g.adm_nm.str.endswith(("읍", "면"))].copy().to_crs(5179)
Q["eupmyeon_polygons"] = len(em)
em["sigun"] = em.sggnm.str.replace(r"^(.+?시).+구$", r"\1", regex=True)
em["kind"] = np.where(em.sigun.str.endswith("군"), "군", "시")
em["sido_n"] = em.sidonm.replace({"전남광주통합특별시": "전라남도"})
METRO = ("특별시", "광역시", "세종", "제주")
em["cov_key"] = [s if any(m in s for m in METRO) else f"{s} {c}" for s, c in zip(em.sido_n, em.sigun)]
em["sigun_key"] = em.sido_n + " " + em.sigun
em["area_km2"] = em.geometry.area / 1e6
em["rep_poly"] = em.geometry.representative_point()

# ── 2. 인구(S9, 2026-09) ─────────────────────────────────────────
raw9 = json.load(open(RAW / "S9_KOSIS_DT_1B04005N_T2_202609.json", encoding="utf-8"))
rows = [r for v in raw9.values() for r in (v if isinstance(v, list) else [])]
s9 = pd.DataFrame(rows)[["C1", "C2", "DT"]]
s9["C2"] = s9.C2.astype(int); s9["DT"] = pd.to_numeric(s9.DT, errors="coerce")
Q["s9_dt_na"] = int(s9.DT.isna().sum())
pop = s9[s9.C2 == 0].groupby("C1").DT.sum().rename("pop")
old = s9[s9.C2 >= 70].groupby("C1").DT.sum().rename("pop65")   # C2 70 = 65-69세
em = em.merge(pd.concat([pop, old], axis=1), left_on="adm_cd2", right_index=True, how="left")
Q["eupmyeon_pop_missing"] = int(em["pop"].isna().sum())
Q["eupmyeon_pop_missing_names"] = em.loc[em["pop"].isna(), "adm_nm"].tolist()
em["old_ratio"] = em.pop65 / em["pop"]

# ── 3. 정기장(N2) ────────────────────────────────────────────────
n2 = pd.read_csv(RAW / "N2_소상공인시장진흥공단_전통시장_20251110.csv", encoding="utf-8-sig")
Q["markets_total"] = len(n2)
per = n2[n2.시장개설주기.str.contains("일") & (n2.시장개설주기 != "매일")].copy()
Q["markets_periodic"] = len(per)
Q["markets_period_unparsed"] = int((~n2.시장개설주기.str.match(r"^(매일|(\d+일\+?)+)$")).sum())
per["days"] = per.시장개설주기.str.findall(r"(\d+)일").map(lambda L: "+".join(sorted({str(int(x) % 10) for x in L})))
per["coord_src"] = np.where(per.위도.notna(), "표준데이터", "")
# 좌표 결측 → 주소의 읍·면 폴리곤 대표점
em_lookup = {(s, c, a.split()[-1]): p for s, c, a, p in zip(em.sido_n, em.sigun, em.adm_nm, em.rep_poly)}
def addr_eupmyeon(addr):
    if not isinstance(addr, str):
        return None
    toks = addr.split()
    for t in toks:
        if re.fullmatch(r".+(읍|면)", t):
            for (s, c, a), p in em_lookup.items():
                if a == t and c in addr:
                    return p
    return None
xs, ys = TF.transform(per.경도.fillna(0).values, per.위도.fillna(0).values)
per["x"], per["y"] = xs, ys
for i in per.index[per.위도.isna()]:
    p = addr_eupmyeon(per.at[i, "소재지지번주소"]) or addr_eupmyeon(per.at[i, "소재지도로명주소"])
    if p is not None:
        per.at[i, "x"], per.at[i, "y"], per.at[i, "coord_src"] = p.x, p.y, "주소 읍면 대표점"
    else:
        per.at[i, "coord_src"] = "좌표 없음(제외)"
Q["markets_periodic_coord_missing"] = int(n2.loc[per.index, "위도"].isna().sum())
Q["markets_periodic_coord_from_addr"] = int((per.coord_src == "주소 읍면 대표점").sum())
Q["markets_periodic_dropped"] = per.loc[per.coord_src == "좌표 없음(제외)", "시장명"].tolist()
per = per[per.coord_src != "좌표 없음(제외)"].copy()
# OSM marketplace 300 m 대조(좌표 교차검증)
om = pd.read_csv(RAW / "N24_osm_marketplace_20261013.csv", encoding="utf-8-sig")
ox, oy = TF.transform(om.lon.values, om.lat.values)
d, _ = cKDTree(np.c_[ox, oy]).query(np.c_[per.x, per.y])
per["osm_dist_m"] = d.round(0)
# 시장 좌표가 주소 시군 밖에 찍힌 경우(좌표 오류 의심)
mk = gpd.GeoDataFrame(per, geometry=gpd.points_from_xy(per.x, per.y), crs=5179)
allg = g.to_crs(5179)[["sggnm", "sidonm", "geometry"]]
j = gpd.sjoin(mk, allg, how="left", predicate="within")
j = j[~j.index.duplicated()]
addr = per.소재지지번주소.fillna(per.소재지도로명주소).fillna("")
sig = j.sggnm.fillna("").str.replace(r"^(.+?시).+구$", r"\1", regex=True)
per["coord_in_addr_sigun"] = [bool(s) and (s in a) for s, a in zip(sig, addr)]
Q["markets_periodic_coord_outside_addr_sigun"] = int((~per.coord_in_addr_sigun).sum())
per[["시장명", "시장유형", "시장개설주기", "days", "소재지지번주소", "소재지도로명주소", "x", "y",
     "coord_src", "osm_dist_m", "coord_in_addr_sigun"]].to_csv(PRO / "markets_periodic.csv", index=False, encoding="utf-8-sig")

# ── 4. 정류장(N1 ∪ OSM) ──────────────────────────────────────────
n1 = pd.read_csv(RAW / "N1_2025정류장현황(EUCKR)_20251209.csv", encoding="cp949", low_memory=False)
Q["n1_rows"] = len(n1)
n1 = n1.dropna(subset=["위도", "경도"])
n1 = n1[(n1.위도.between(33, 39)) & (n1.경도.between(124, 132))]
Q["n1_rows_valid_coord"] = len(n1)
x1, y1 = TF.transform(n1.경도.values, n1.위도.values)
P1 = np.c_[x1, y1]
# N1 내부 중복(같은 좌표 반복 등록)은 10 m 격자로 1개로
k1 = pd.DataFrame(np.round(P1 / 10).astype(np.int64)).drop_duplicates().index
P1 = P1[k1]
Q["n1_unique_10m"] = len(P1)
ob = pd.read_csv(RAW / "N24_osm_bus_stop_20261013.csv", encoding="utf-8-sig")
xo, yo = TF.transform(ob.lon.values, ob.lat.values)
PO = np.c_[xo, yo]
dd, _ = cKDTree(P1).query(PO)
PO_new = PO[dd > 30]
Q["osm_bus_stop_rows"] = len(ob)
Q["osm_bus_stop_added_gt30m"] = len(PO_new)
st = pd.DataFrame(np.r_[P1, PO_new], columns=["x", "y"])
st["src"] = ["N1"] * len(P1) + ["OSM"] * len(PO_new)
st.to_csv(PRO / "stops_merged.csv", index=False)

# ── 5. 건물 → 읍면 ──────────────────────────────────────────────
b = np.load(PRO / "osm_buildings.npz")
bx, by = TF.transform(b["lon"].astype(float), b["lat"].astype(float))
bg = gpd.GeoDataFrame({"bx": bx, "by": by}, geometry=gpd.points_from_xy(bx, by), crs=5179)
bj = gpd.sjoin(bg, em[["adm_cd2", "geometry"]], how="inner", predicate="within")
Q["osm_buildings_total"] = len(bg)
Q["osm_buildings_in_eupmyeon"] = len(bj)
tree_st = cKDTree(st[["x", "y"]].values)
bj["d_stop"], _ = tree_st.query(np.c_[bj.bx, bj.by])
bj[["adm_cd2", "bx", "by", "d_stop"]].to_parquet(PRO / "eupmyeon_buildings.parquet", index=False)
agg = bj.groupby("adm_cd2").agg(n_bld=("bx", "size"), cx_bld=("bx", "mean"), cy_bld=("by", "mean"))
em = em.merge(agg, left_on="adm_cd2", right_index=True, how="left")
em["n_bld"] = em.n_bld.fillna(0).astype(int)

# ── 5b. 마을 점(OSM place) → 읍면 (사전등록 변경 #4: 주 단위) ─────────
pl = pd.read_csv(PRO / "osm_places.csv", encoding="utf-8-sig")
pl = pl[pl.place.isin(["village", "hamlet", "isolated_dwelling"])]
px, py = TF.transform(pl.lon.values, pl.lat.values)
pgd = gpd.GeoDataFrame(pl.assign(vx=px, vy=py), geometry=gpd.points_from_xy(px, py), crs=5179)
vj = gpd.sjoin(pgd, em[["adm_cd2", "geometry"]], how="inner", predicate="within")
vj["d_stop"], _ = tree_st.query(np.c_[vj.vx, vj.vy])
Q["osm_villages_total"] = len(pl)
Q["osm_villages_in_eupmyeon"] = len(vj)
vj[["adm_cd2", "osm_id", "name", "place", "vx", "vy", "d_stop"]].to_csv(PRO / "eupmyeon_villages.csv", index=False, encoding="utf-8-sig")
vagg = vj.groupby("adm_cd2").agg(n_vil=("vx", "size"), cx_vil=("vx", "mean"), cy_vil=("vy", "mean"))
em = em.merge(vagg, left_on="adm_cd2", right_index=True, how="left")
em["n_vil"] = em.n_vil.fillna(0).astype(int)
Q["eupmyeon_vil_lt3"] = int((em.n_vil < 3).sum())

# 정류장 수(읍면 안)
sg = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.x, st.y), crs=5179)
sj = gpd.sjoin(sg, em[["adm_cd2", "geometry"]], how="inner", predicate="within")
cnt = sj.groupby(["adm_cd2", "src"]).size().unstack(fill_value=0)
em = em.merge(cnt.rename(columns={"N1": "n_stop_n1", "OSM": "n_stop_osm"}), left_on="adm_cd2", right_index=True, how="left")
for c in ("n_stop_n1", "n_stop_osm"):
    em[c] = em[c].fillna(0).astype(int)
em["n_stop"] = em.n_stop_n1 + em.n_stop_osm

# BIS 구멍(N1/N1b < 0.5) — N1b 가 2개 이하인 키는 N1b 코드 오류로 보고 제외
cov = pd.read_csv(PRO / "coverage_n1_vs_n1b.csv", encoding="utf-8-sig", index_col=0)
gap = cov[(cov.ratio < 0.5) & (cov.n1b > 2) & (cov.index != "(미분류)")]
Q["coverage_ratio_lt05_keys_all"] = int(((cov.ratio < 0.5) & (cov.index != "(미분류)")).sum())
Q["coverage_ratio_lt05_keys_artifact"] = cov[(cov.ratio < 0.5) & (cov.n1b <= 2)].index.tolist()
Q["bis_gap_sigun"] = gap.index.tolist()
em["bis_gap"] = em.cov_key.isin(set(gap.index))
Q["bis_gap_sigun_matched_in_eupmyeon"] = sorted(em.loc[em.bis_gap, "cov_key"].unique().tolist())
Q["eupmyeon_in_bis_gap"] = int(em.bis_gap.sum())

out = em.drop(columns=["rep_poly"]).copy()
out["rep_x"] = em.rep_poly.x; out["rep_y"] = em.rep_poly.y
out.to_file(PRO / "eupmyeon_base.gpkg", driver="GPKG")
Q["n_bld_quantiles_eupmyeon"] = out.n_bld.quantile([0, .1, .25, .5, .75, .9]).round(0).to_dict()
Q["eupmyeon_bld_lt30"] = int((out.n_bld < 30).sum())
Q["eupmyeon_zero_stop"] = int((out.n_stop == 0).sum())
json.dump(Q, open(PRO / "quality_log.json", "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(Q, ensure_ascii=False, indent=1, default=str))
