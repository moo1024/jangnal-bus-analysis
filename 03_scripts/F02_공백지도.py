# -*- coding: utf-8 -*-
import _env; _env.cap()
import sys, shutil
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from plot_style import setup, save
from _figcommon import *

setup(base_pt=8)
plt.rcParams["hatch.linewidth"] = 0.5
C_NONE, C_OVER, C_RUN = "#d9480f", "#1c5fb8", "#1baf7a"

em = gpd.read_file(PRO / "eupmyeon_base.gpkg"); em["adm_cd2"] = em.adm_cd2.astype("int64")
j = csv("eupmyeon_judged.csv")[["adm_cd2", "hold", "gap", "has_pop"]]
gl = csv("jangnal_gap_list.csv")[["adm_cd2", "type"]]
em = em.merge(j, on="adm_cd2", how="left").merge(gl, on="adm_cd2", how="left")
em["hold"] = em["hold"].fillna(False).astype(bool)
mk = csv("markets_periodic.csv")

# 배경: N16 행정동 경계 전체(읍면 밖 동 지역 포함)
bg = gpd.read_file(RAW / "HangJeongDong_ver20260701.geojson").to_crs(5179)
bg["geometry"] = bg.geometry.simplify(400)

W, H = 148, 89
fig = plt.figure(figsize=(W / 25.4, H / 25.4))
ax = fig.add_axes([0.0, 0.0, 0.47, 0.99])
ax.set_axis_off(); ax.set_aspect("equal")
bg.plot(ax=ax, color="#e7e5df", edgecolor="none", zorder=1)
ok = em[~em.hold & em.gap.ne(True)]
ok.plot(ax=ax, color="#fbfaf7", edgecolor="#cfcdc6", linewidth=0.15, zorder=2)
hd = em[em.hold]
hd.plot(ax=ax, facecolor="#fbfaf7", edgecolor="#7a7872", hatch="//////", linewidth=0.15, zorder=3)
for t, c in (("확인필요형", C_NONE), ("얹기형", C_OVER), ("운영형", C_RUN)):
    s = em[em["type"] == t]
    if len(s):
        s.plot(ax=ax, color=c, edgecolor="black", linewidth=0.35, zorder=5)
# 공백 읍·면은 전국 지도에서 작아 보이므로 중심점 고리를 얹는다
g = em[em["type"].notna()].copy()
cen = g.geometry.representative_point()
ax.scatter(cen.x, cen.y, s=26, facecolor="none",
           edgecolor=[C_NONE if t == "확인필요형" else C_OVER for t in g["type"]], linewidth=0.7, zorder=6)
ax.scatter(mk.x, mk.y, s=3.2, marker="^", color="#222", linewidths=0, zorder=4, alpha=.8)
ax.set_xlim(bg.total_bounds[0] - 5000, bg.total_bounds[2] + 5000)
ax.set_ylim(bg.total_bounds[1] - 5000, bg.total_bounds[3] + 5000)

# 우측 패널 — 글자 등급 둘: 제목급 T, 본문급 B (117mm 인쇄 시 8pt 이상)
T, B = 11.5, 10.2
px = fig.add_axes([0.49, 0.0, 0.51, 0.99]); px.set_axis_off()
px.set_xlim(0, 1); px.set_ylim(0, 1)
px.text(0, .985, "장날 이동 공백 읍·면", fontsize=T, weight="bold", va="top")
px.text(0, .925, f"판정 {fmt('eupmyeon_judged_n')}곳 중 {fmt('jangnal_gap_eupmyeon_n')}곳({num('jangnal_gap_pct_of_eupmyeon')}%)\n65세 이상 {fmt('jangnal_gap_elderly_n')}명",
        fontsize=B, va="top", linespacing=1.3)
y = .745
items = [
    (C_NONE, f"확인필요형 {fmt('gap_type_none_n')}곳", "제도 미확인"),
    (C_OVER, f"얹기형 {fmt('gap_type_overlay_n')}곳", "농촌형·DRT 시군"),
    (C_RUN, f"운영형 {fmt('gap_type_running_n')}곳", "원문 확인 0"),
]
def row(y, a, b):
    px.text(.1, y + .018, a, fontsize=B, va="center", weight="bold")
    px.text(.1, y - .035, b, fontsize=B, va="center", color="#444")
for c, a, b in items:
    px.add_patch(plt.Rectangle((0, y - .025), .07, .05, fc=c, ec="black", lw=.4))
    row(y, a, b)
    y -= .112
px.add_patch(plt.Rectangle((0, y - .025), .07, .05, fc="#fbfaf7", ec="#7a7872", hatch="//////", lw=.5))
import re as _re
from _figcommon import _NUM
GAP_SIGUN = _re.search(r"읍·면이 있는 시군은 (\d+)개", _NUM["bis_gap_sigun_n"]["caveat"]).group(1)  # 수치 기록표 caveat 에서 읽음
row(y, f"판정 보류 {fmt('eupmyeon_hold_n')}곳", f"정류장 위치자료 부족 {GAP_SIGUN}개 시군")
y -= .112
px.scatter([.035], [y], s=18, marker="^", color="#222")
row(y, f"정기장 {fmt('markets_periodic_n')}곳", "5일장 개설주기 기준")
px.text(0, .005, "마을·정류장 © OpenStreetMap", fontsize=B, va="bottom", color="#333")
for out in (FIG / "F02_공백지도.png", SHOT / "F02_공백지도.png"):
    save(fig, out, exact_mm=(W, H))
print("OK", len(g), len(hd))
