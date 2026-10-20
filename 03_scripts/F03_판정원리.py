# -*- coding: utf-8 -*-
import _env; _env.cap()
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np
import matplotlib.pyplot as plt
from plot_style import setup, save
from _figcommon import *

setup(base_pt=8)
RED, BLU, GRY = "#d9480f", "#1c5fb8", "#9a9892"
j = csv("eupmyeon_judged.csv")
b = j[(~j.hold) & j.has_pop].copy()
W, H = 148, 70
fig = plt.figure(figsize=(W / 25.4, H / 25.4))
ax = fig.add_axes([0.095, 0.33, 0.40, 0.54])
dens_cut = num("stop_density_q25")
ymax = 5.0
yv = b.stop_density.clip(upper=ymax)
s = 4 + b.pop65 / b.pop65.max() * 90
other = ~b.gap.astype(bool)
ax.scatter(b.d_market_km[other], yv[other], s=s[other], c=GRY, alpha=.45, linewidths=0, label="나머지")
g = b.gap.astype(bool)
ax.scatter(b.d_market_km[g], yv[g], s=s[g], c=RED, alpha=.9, edgecolors="black", linewidths=.4, label="공백")
ax.set_xscale("log"); ax.set_xlim(0.3, 200); ax.set_ylim(-0.1, ymax + .15)
ax.set_xticks([1, 5, 20, 100]); ax.set_xticklabels(["1", "5 km", "20", "100"])
ax.axvline(5, color="black", lw=.8, ls="--"); ax.axhline(dens_cut, color="black", lw=.8, ls="--")
nq = int(((b.d_market_km > 5) & (b.stop_density <= dens_cut)).sum())
ax.text(190, 3.55, f"C1·C3 만 충족 {nq}곳\n→ 4조건 모두 {int(g.sum())}곳 = 공백(주황)\n점 크기 = 65세 이상 인구",
        ha="right", va="center", fontsize=10.2, linespacing=1.3,
        bbox=dict(fc="white", ec="#888", lw=.4, pad=2.0))
ax.annotate("", xy=(40, 0.45), xytext=(60, 2.55), arrowprops=dict(arrowstyle="-|>", lw=.7, color="#333"))
ax.text(0.33, dens_cut + .08, f"하위 25% ≤ {dens_cut:g}개/km²", fontsize=10.2, va="bottom", bbox=dict(fc="white", ec="none", alpha=.75, pad=1))
ax.set_xlabel("정기장까지 직선거리 (km, 로그)", fontsize=10.2, labelpad=2)
ax.set_ylabel("정류장 밀도 (개/km²)", fontsize=10.2)
ax.tick_params(labelsize=10.2)
ax.set_title("C1 시장 거리 × C3 정류장 밀도", fontsize=11.5, loc="left", weight="bold")

# 조건별 충족 읍·면 수
bx = fig.add_axes([0.775, 0.33, 0.17, 0.54])
labs = ["판정 대상", "C1 시장 5 km 밖", "C2 도보 밖 20%+", "C3 밀도 하위", "C4 고령 비율 중앙값 이상", "4조건 모두"]
vals = [num("eupmyeon_judged_n"), num("cond_c1_n"), num("cond_c2_n"), num("cond_c3_n"), num("cond_c4_n"), num("jangnal_gap_eupmyeon_n")]
cols = ["#d4d2cc", "#9bb7e0", "#9bb7e0", "#9bb7e0", "#9bb7e0", RED]
yy = np.arange(len(vals))[::-1]
bx.barh(yy, vals, color=cols, edgecolor="black", linewidth=.4, height=.62)
for y, v in zip(yy, vals):
    bx.text(v + 25, y, f"{v:,}", fontsize=10.2, va="center", weight="bold")
bx.set_xlim(0, max(vals) * 1.45); bx.set_ylim(-.55, len(vals) - .1)
bx.set_yticks(yy); bx.set_yticklabels(labs, fontsize=10.2); bx.tick_params(length=0); bx.set_xticks([])
for sp in ("top", "right", "bottom", "left"): bx.spines[sp].set_visible(False)
bx.set_title("조건별 충족 읍·면 수", fontsize=11.5, loc="right", weight="bold")
fig.text(0.03, 0.01, f"판정 {fmt('eupmyeon_judged_n')}곳 (정류장 위치자료 부족 시군 {fmt('eupmyeon_hold_n')}곳 보류) · 밀도 5 초과는 5로 표시\n자료: 소진공·국토부·통계지리·KOSIS · © OpenStreetMap",
         fontsize=10.2, color="#444")
for out in (FIG / "F03_판정원리.png", SHOT / "F03_판정원리.png"):
    save(fig, out, exact_mm=(W, H))
print("OK", nq, int(g.sum()))
