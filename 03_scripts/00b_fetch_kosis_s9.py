"""S9 KOSIS DT_1B04005N(행정구역(읍면동)별/5세별 주민등록인구) 시도별 분할 수집. 키는 open_api 내부에서만 읽는다."""
import sys, json, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import open_api as o
OUT = str(__import__("pathlib").Path(__file__).resolve().parents[1]) + "/01_data/raw/"
meta = o.kosis_meta("101", "DT_1B04005N", "ITM")
reg = [(r["ITM_ID"], r["ITM_NM"]) for r in meta if r.get("OBJ_ID") == "A"]
sidos = [c for c, n in reg if len(c) == 2 and c != "00"]
ages = "+".join(str(a) for a in [0]+list(range(5, 110, 5)))
period = sys.argv[1] if len(sys.argv) > 1 else "202609"
allrows = {}
skipped = []
for s in sidos:
    codes = [c for c, n in reg if len(c) == 10 and c.startswith(s)]
    # 시군구 코드 앞 2자리가 시도코드와 일치(통계청 행정구역 코드)
    if not codes:
        print(s, "읍면동 코드 0건"); continue
    rows = []
    for i in range(0, len(codes), 150):
        chunk = codes[i:i+150]
        try:
            rows += o.kosis_data("101", "DT_1B04005N", "T2", "+".join(chunk), "M", period, period, obj_l2=ages)
        except SystemExit as e:
            print("  [건너뜀]", s, i, str(e)[:80]); skipped.append((s, i))
        time.sleep(0.3)
    allrows[s] = rows
    print(s, len(codes), "읍면동 →", len(rows), "행")
json.dump(allrows, open(OUT + f"S9_KOSIS_DT_1B04005N_T2_{period}.json", "w", encoding="utf-8"), ensure_ascii=False)
print("skipped", skipped)
print("total", sum(len(v) for v in allrows.values()))
