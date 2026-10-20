# -*- coding: utf-8 -*-
import _env; _env.cap()
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np
import matplotlib.pyplot as plt
from plot_style import setup, save
from _figcommon import *

setup(base_pt=8)
RED, BLU = "#d9480f", "#1c5fb8"
gl = csv("jangnal_gap_list.csv"); j = csv("eupmyeon_judged.csv")[["adm_cd2", "sido_n"]]
g = gl.merge(j, on="adm_cd2")
short = {"경상북도": "경북", "경상남도": "경남", "강원특별자치도": "강원", "전라남도": "전남", "전북특별자치도": "전북", "충청북도": "충북",
         "경기도": "경기", "대구광역시": "대구", "인천광역시": "인천", "충청남도": "충남", "부산광역시": "부산", "울산광역시": "울산",
         "세종특별자치시": "세종", "제주특별자치도": "제주", "전남광주통합특별시": "전남"}
g["sido"] = g.sido_n.map(lambda s: short.get(s, s))
t = g.groupby(["sido", "type"]).agg(n=("adm_cd2", "size"), el=("pop65", "sum")).unstack(fill_value=0)
n_none = t["n"].get("확인필요형", 0); n_over = t["n"].get("얹기형", 0)
el = t["el"].sum(axis=1)
order = (n_none + n_over).sort_values(ascending=False).index
zero = sorted(set(short.values()) - set(order) - {"전남광주통합특별시"})
W, H = 148, 66
fig = plt.figure(figsize=(W / 25.4, H / 25.4))
y = np.arange(len(order))[::-1]
a1 = fig.add_axes([0.095, 0.33, 0.37, 0.53]); a2 = fig.add_axes([0.575, 0.33, 0.40, 0.53])
a1.barh(y, n_over[order], color=BLU, edgecolor="black", lw=.4, hatch="", label="얹기형", height=.68)
a1.barh(y, n_none[order], left=n_over[order], color=RED, edgecolor="black", lw=.4, hatch="///", label="확인필요형", height=.68)
a2.barh(y, el[order] / 1000, color="#6f6d68", edgecolor="black", lw=.4, height=.68)
tot = (n_none + n_over)[order]
for yi, v in zip(y, tot): a1.text(v + .5, yi, f"{int(v)}", va="center", fontsize=10.2)
for yi, v in zip(y, el[order]): a2.text(v / 1000 + .4, yi, f"{v/1000:.1f}", va="center", fontsize=10.2)
for a in (a1, a2):
    a.set_yticks(y); a.tick_params(labelsize=10.2)
a1.set_yticklabels(order); a2.set_yticklabels([])
a1.set_xlim(0, tot.max() * 1.18); a2.set_xlim(0, el.max() / 1000 * 1.18)
a1.set_xlabel("공백 읍·면 수 (곳)", fontsize=10.2); a2.set_xlabel("65세 이상 인구 (천 명)", fontsize=10.2)
a1.set_title("유형별 읍·면 수", fontsize=11.5, loc="left", weight="bold")
a2.set_title("공백 읍·면의 65세 이상 인구", fontsize=11.5, loc="left", weight="bold")
a1.legend(fontsize=10.2, loc="lower right", frameon=False, handlelength=1.2)
fig.text(0.03, 0.01, f"공백 {len(g)}곳(운영형 {fmt('gap_type_running_n')}곳) · 판정 보류 시군 제외\n공백 0곳: {'·'.join(zero)} · 경북 {int(tot.iloc[0])}곳으로 최다",
         fontsize=10.2, color="#444")
for out in (FIG / "F04_시도별.png", SHOT / "F04_시도별.png"):
    save(fig, out, exact_mm=(W, H))
print("OK", list(order), zero, len(g))
