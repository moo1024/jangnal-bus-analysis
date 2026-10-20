# 장날버스 — 전국 읍·면 장날 이동 공백 분석 코드

정기 5일장까지의 거리, 정류장 도보권 밖 마을 비율, 정류장 밀도, 고령 인구 비율 네 조건으로
전국 읍·면의 「장날 이동 공백」을 판정하고, 기존 농촌형 교통모델·DRT 제도와 겹쳐
운영형·얹기형·확인필요형으로 나누는 분석 코드.

## 구성

| 폴더 | 내용 |
|---|---|
| `03_scripts/` | 수집 → 정제 → 판정·검정 → 군집 비교 → 유형 분류 → 탄소 시나리오 → 그림 |
| `05_results/numbers.json` | 보고서에 인용한 모든 수치(값·산식·표본 수·신뢰구간·출처) |
| `05_results/tables/` | 공백 읍·면 92곳 우선순위 명단(`jangnal_gap_list.csv`)·읍·면별 판정값·민감도·유형·군집 비교·탄소 시나리오 |
| `01_data/SOURCES.md` | 데이터별 출처·기준 시점·라이선스·수집 방법 |
| `01_data/manifest.json` | 원자료 파일 sha256(같은 원자료인지 확인용) |
| `04_figures/` | 보고서 그림 |

원자료는 용량·재배포 조건 때문에 넣지 않았다. `SOURCES.md` 의 URL 에서 받아 `01_data/raw/` 에 두고
`manifest.json` 해시로 같은 파일인지 확인한다.

## 실행 순서

```bash
pip install pandas numpy geopandas scipy scikit-learn pyproj matplotlib osmium
cd 03_scripts
export OSMLIB=<pyosmium 설치 경로>     # 00c·00d·00e 만 필요
export KOSIS_API_KEY=<발급 키>          # 00b(인구 재수집) 만 필요

python 00b_fetch_kosis_s9.py    # KOSIS 읍·면 인구 (재수집 시)
python 00c_extract_osm.py       # OSM 정류장·시장 재추출 (검증용)
python 00d_extract_buildings.py # OSM 건물 대표점 (민감도용)
python 00e_extract_places.py    # OSM 마을 점 (주 분석 단위)
python 00z_manifest.py          # 원자료 sha256 고정
python 01_clean.py              # 읍·면 기본표
python 02_judge.py              # 4조건 판정·가설검정·민감도 12판
python 03_cluster.py            # 규칙 판정 vs K-means·Ward·GMM 비교
python 04_typology.py           # 운영형·얹기형·확인필요형 + 우선순위 명단
python 05_carbon.py             # 탄소 시나리오(가정 3단)
python 06_posthoc.py            # 사후 점검
python F02_공백지도.py; python F03_판정원리.py; python F04_시도별.py
```

- 판정 임계(시장 거리 5 km, 도보권 1 km, 정류장 밀도 하위 25%, 고령 비율 중앙값)는 판정 계산 전에 정했다.
- 난수 시드는 20260725 로 고정했다(부트스트랩·순열검정 2,000회, 군집).
