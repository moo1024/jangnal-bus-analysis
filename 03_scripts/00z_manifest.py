"""raw/ 파일 sha256·크기·행수를 manifest.json 에 고정한다. 수집일시는 최초 기록값을 유지한다(재실행해도 안 바뀐다)."""
import hashlib, json, os, datetime, glob
RAW = "../01_data/raw/"; OUT = "../01_data/manifest.json"
SRC = {
 "N2": ("N2_소상공인시장진흥공단_전통시장_20251110.csv", "https://www.data.go.kr/data/15012894/standard.do", "csv"),
 "N1": ("N1_2025정류장현황(EUCKR)_20251209.csv", "https://www.data.go.kr/data/15067528/fileData.do", "csv"),
 "N1b": ("N1b_국토교통부_정류장현황_260703.csv", "https://www.data.go.kr/data/15128614/fileData.do", "csv"),
 "S2": ("S2_한국교통안전공단_수요응답형대중교통시스템_등록대수_20251231.csv", "https://www.data.go.kr/data/15064502/fileData.do", "csv"),
 "S3": ("S3_용도별차종별시군구별_일평균자동차주행거리_2019.csv", "https://www.data.go.kr/data/15088483/fileData.do", "csv"),
 "EF_inventory": ("EF_국가온실가스인벤토리_1990_2023.csv", "https://www.data.go.kr/data/15049589/fileData.do", "csv"),
 "EF_notice": ("EF_환경부고시_자동차온실가스배출허용기준_2025-165.xml", "https://www.law.go.kr/DRF/lawService.do?target=admrul&ID=2100000266944", "xml"),
 "S9": ("S9_KOSIS_DT_1B04005N_T2_202609.json", "KOSIS org=101 tbl=DT_1B04005N itm=T2 prd=M 202609 (scripts/00b_fetch_kosis_s9.py)", "json"),
 "N16": ("HangJeongDong_ver20260701.geojson", "https://raw.githubusercontent.com/vuski/admdongkor/master/ver20260701/HangJeongDong_ver20260701.geojson", "geojson"),
 "N16_license": ("admdongkor_LICENSE-DATA.txt", "https://raw.githubusercontent.com/vuski/admdongkor/master/LICENSE-DATA", "txt"),
 "N24_pbf": ("south-korea-latest.osm.pbf", "https://download.geofabrik.de/asia/south-korea-latest.osm.pbf", "pbf"),
 "N24_bus_stop": ("N24_osm_bus_stop_20261013.csv", "pbf 에서 00c_extract_osm.py 로 추출", "csv"),
 "N24_marketplace": ("N24_osm_marketplace_20261013.csv", "pbf 에서 00c_extract_osm.py 로 추출", "csv"),
 "N23_pdf": ("N23_농식품부_농촌형교통모델_보도자료_2025-05-02.pdf", "https://www.mafra.go.kr/bbs/home/792/587555/download.do", "pdf"),
 "EF_ncv": ("EF_에너지법시행규칙_010281.xml", "https://www.law.go.kr/DRF/lawService.do?target=law&ID=010281 (scripts/law_text.py, 별표 에너지열량 환산기준 2022-11-21 개정)", "xml"),
 "N23_korea_kr": ("N23_korea_kr_156744162.html", "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156744162", "html"),
}
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def rows(p, kind):
    if kind == "csv":
        for enc in ("utf-8-sig", "cp949"):
            try:
                with open(p, encoding=enc) as f: return sum(1 for _ in f) - 1
            except UnicodeDecodeError: continue
    if kind == "geojson": return len(json.load(open(p, encoding="utf-8"))["features"])
    if kind == "json": return sum(len(v) for v in json.load(open(p, encoding="utf-8")).values())
    return None
old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"files": {}}
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
files = {}
for k, (fn, url, kind) in SRC.items():
    p = RAW + fn
    if not os.path.exists(p): continue
    prev = old["files"].get(k, {})
    files[k] = {"file": fn, "url": url, "bytes": os.path.getsize(p), "sha256": sha(p), "rows": rows(p, kind),
                "collected_at": prev.get("collected_at") if prev.get("sha256") == sha(p) else now}
extra = {f: sha(f) for f in glob.glob(RAW + "api_*")}
json.dump({"generated": now, "files": files}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(files), "files fixed")
