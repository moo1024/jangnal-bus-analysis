#!/usr/bin/env python3
"""이 파일은 뭐? — 추진배경(문제 제기)에 쓸 외부 자료의 원표 수치를 수치 기록표에 올린다.

구성(배경 3단)
  ① 실태 : 수송부문 온실가스와 도로 비중 / 농어촌 대중교통 격차 / 교통약자 규모
  ② 정책 : 2035 국가 온실가스 감축목표(수송 60.2%) / 2025 잠정배출량
  ③ 공백 : 목표 수준과 현재 수준의 간격, 농어촌 최소서비스 미충족 비율

출처는 SOURCES.md 「배경근거용 원표 자료」 절에 등재되어 있다.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[2]
sys.path.insert(0, str(HERE))

from 수치기록 import add  # noqa: E402

SRC_KOTI = "koti_transport_ghg_by_mode"
SRC_MCEE25 = "mcee_ghg_provisional_2025"
SRC_NDC35 = "korea_kr_ndc2035_sector"
SRC_KREI = "krei_rural_service_standard_2024"
SRC_MOLIT = "molit_transport_vulnerable_2024"

# ── ① 실태: KOTI 「수송분야 부문별 온실가스 배출량 현황」 표 (단위 천tCO2eq, 2006 IPCC 지침) ──
KOTI = {  # 연도: (국내항공, 도로수송, 철도, 국내해운, 기타수송)
    2018: (1594, 95307, 320, 1038, 505),
    2022: (1744, 95093, 200, 1395, 70),
}
KOTI_TOTAL_PRINTED = {2018: 96764, 2022: 96502}  # 원표의 「합계」 칸(구성항목 합과 2000 어긋남 — 원표 오기로 판단)
KOTI_TEXT_2022_TOTAL = 98502                     # 원표 위 문장의 2022 합계 — 구성항목 합과 일치

# ② 정책
MCEE_2025_TRANSPORT = 94590   # 천tCO2eq (보도자료 「9,459만톤」), 전년 대비 -2.9%
NDC35_TRANSPORT_PCT = 60.2    # 2018 대비 감축률(%) — 범위 하한 60.2 (상한 62.8은 별도 보도, 미인용)

# ① 농어촌 / 교통약자
RURAL_CITIES_TOTAL = 139
RURAL_CITIES_3PLUS = 6
EUPMYEON_TOTAL, EUPMYEON_SHORT = 1408, 310
HAENGJEONG_TOTAL, HAENGJEONG_SHORT = 2150, 84
HEADWAY_FARM, HEADWAY_NONFARM = 98.4, 55.3
HEADWAY_MYEON, HEADWAY_EUP = 88.5, 47.2
VULN_POP_MAN = 1613      # 만명
TOTAL_POP_MAN = 5122     # 만명
VULN_RATIO_PRINTED = 31.5


def main() -> None:
    for y, parts in KOTI.items():
        assert sum(parts) == (KOTI_TEXT_2022_TOTAL if y == 2022 else 98764), f"{y} 구성항목 합 확인"
    t18, t22 = sum(KOTI[2018]), sum(KOTI[2022])
    r18, r22 = KOTI[2018][1], KOTI[2022][1]

    add(key="transport_ghg_2018_k", value=t18, unit="천tCO2eq",
        description="[2018년 단년, 2006 IPCC 지침, 전국] 수송분야 온실가스 배출량 = 원표 5개 구성항목(국내항공·도로·철도·국내해운·기타) 합",
        method="KOTI 표의 구성항목을 합산(원표 「합계」 칸은 96,764 로 인쇄돼 있으나 구성항목 합은 98,764 — 원표 오기로 보고 합산값 사용)",
        source_dataset=SRC_KOTI, n=5,
        caveat="2차 가공 표(KOTI)이며 원천은 GIR 국가 온실가스 인벤토리. 원표 합계 칸과 2000 차이남")
    add(key="transport_ghg_2022_k", value=t22, unit="천tCO2eq",
        description="[2022년 단년, 2006 IPCC 지침, 전국] 수송분야 온실가스 배출량 = 구성항목 합",
        method="KOTI 표 구성항목 합산. KOTI 본문 문장 「98,502 천톤」과 일치(표 합계 칸 96,502 는 오기)",
        source_dataset=SRC_KOTI, n=5, caveat="위와 같음")
    add(key="road_ghg_2022_k", value=r22, unit="천tCO2eq",
        description="[2022년 단년, 전국] 도로수송 온실가스 배출량 (KOTI 원표값)", method="원문 값(계산 아님)",
        source_dataset=SRC_KOTI)
    add(key="road_share_2022_pct", value=round(r22 / t22 * 100, 2), unit="%",
        description="[2022년 단년, 전국] 수송분야 온실가스 중 도로수송 비중 (공고의 「약 97%」 대조값)",
        method="도로수송 95,093 / 수송 합계 98,502 × 100", source_dataset=SRC_KOTI, n=5,
        caveat="공고 서술 「약 97%」는 96.5% 를 반올림한 수준. 인용 시 96.5% 로 쓴다")
    add(key="road_share_2018_pct", value=round(r18 / t18 * 100, 2), unit="%",
        description="[2018년 단년, 전국] 수송분야 온실가스 중 도로수송 비중", method="95,307 / 98,764 × 100",
        source_dataset=SRC_KOTI, n=5)

    # ② 정책
    add(key="transport_ghg_2025_prov_k", value=MCEE_2025_TRANSPORT, unit="천tCO2eq",
        description="[2025년 잠정, 2006 IPCC 지침, 전국] 수송부문 온실가스 배출량 (기후에너지환경부 보도자료 「9,459만톤」)",
        method="원문 값(만톤→천톤 환산)", source_dataset=SRC_MCEE25,
        caveat="잠정치이며 확정 인벤토리에서 바뀔 수 있다. 전년 대비 2.9% 감소로 보도됨")
    add(key="ndc2035_transport_cut_pct", value=NDC35_TRANSPORT_PCT, unit="%",
        description="[2035년 목표, 2018년 대비, 전국 수송 부문] 수송 부문 감축률 하한(60.2%) — 2035 NDC 부문별 안",
        method="원문 값(계산 아님)", source_dataset=SRC_NDC35, n=1,
        caveat="목표치다(실적 아님). 2035 NDC 는 53~61% 범위 안이며 수송 상한은 62.8% 로 별도 보도")
    tgt = round(t18 * (1 - NDC35_TRANSPORT_PCT / 100))
    add(key="ndc2035_transport_target_k", value=tgt, unit="천tCO2eq",
        description="[2035년 목표 수준] 2018년 수송 배출량에 60.2% 감축을 적용한 수준",
        method="98,764 × (1 − 0.602)", source_dataset=SRC_NDC35, n=1,
        caveat="목표치다. 2018 기준을 KOTI 구성항목 합으로 둔 우리 환산이며 정부가 공표한 절대량이 아니다")
    cut25 = round((t18 - MCEE_2025_TRANSPORT) / t18 * 100, 2)
    add(key="transport_cut_2025_vs_2018_pct", value=cut25, unit="%",
        description="[2025 잠정 vs 2018, 전국] 수송 배출량 감소율", method="(98,764 − 94,590) / 98,764 × 100",
        source_dataset=SRC_MCEE25, n=2, caveat="2018은 확정치·2025는 잠정치")
    add(key="ndc2035_gap_pp", value=round(NDC35_TRANSPORT_PCT - cut25, 2), unit="%p",
        description="[2025 잠정 기준] 2035 감축목표 60.2% 대비 현재까지 감축률의 간격",
        method="60.2 − 감소율(2025 vs 2018)", source_dataset=SRC_NDC35, n=2,
        caveat="목표치와 잠정 실적의 차이")

    # ① 농어촌
    add(key="rural_city_bus3_n", value=RURAL_CITIES_3PLUS, unit="개",
        description="[2024 농어촌서비스기준 이행실태 점검·평가, 전체 139개 농어촌 시·군] 하루 3회 이상 버스 이용 가능한 시·군 수",
        method="원문 값", n=RURAL_CITIES_TOTAL, source_dataset=SRC_KREI,
        caveat="원문(KREI 보고서) 미확보 — 농민신문 보도 2차 인용")
    add(key="rural_city_bus3_pct", value=round(RURAL_CITIES_3PLUS / RURAL_CITIES_TOTAL * 100, 1), unit="%",
        description="[2024, 139개 농어촌 시·군] 하루 3회 이상 버스 이용 가능 시·군 비율", method="6 / 139 × 100",
        n=RURAL_CITIES_TOTAL, source_dataset=SRC_KREI, caveat="2차 인용. 기사 표기 4.3%")
    add(key="eupmyeon_below_min_pct", value=round(EUPMYEON_SHORT / EUPMYEON_TOTAL * 100, 1), unit="%",
        description="[2024 대중교통 현황 조사, 읍·면 1,408곳] 대중교통 최소서비스 미충족 지역 비율", method="310 / 1,408 × 100",
        n=EUPMYEON_TOTAL, source_dataset=SRC_KREI, caveat="2차 인용(농민신문). 기사 표기 22.0%")
    add(key="haengjeong_below_min_pct", value=round(HAENGJEONG_SHORT / HAENGJEONG_TOTAL * 100, 1), unit="%",
        description="[2024, 행정동 2,150곳] 대중교통 최소서비스 미충족 비율", method="84 / 2,150 × 100",
        n=HAENGJEONG_TOTAL, source_dataset=SRC_KREI, caveat="2차 인용. 기사 표기 3.9%")
    add(key="headway_farm_min", value=HEADWAY_FARM, unit="분",
        description="[2024 농어업인 복지실태조사, 농어촌 지역] 농어가 평균 대중교통 배차간격", method="원문 값",
        source_dataset=SRC_KREI, caveat="농촌진흥청 조사를 농민신문이 인용한 2차 자료. 표본 규모 미확인")
    add(key="headway_gap_farm_min", value=round(HEADWAY_FARM - HEADWAY_NONFARM, 1), unit="분",
        description="[2024, 농어촌 지역] 농어가 대 비농어가 배차간격 격차 (98.4 − 55.3)", method="98.4 − 55.3",
        source_dataset=SRC_KREI, n=2, caveat="2차 인용. 기사 표기 43.1분")
    add(key="headway_gap_myeon_eup_min", value=round(HEADWAY_MYEON - HEADWAY_EUP, 1), unit="분",
        description="[2024, 농어촌 지역] 면 대 읍 평균 배차간격 격차 (88.5 − 47.2)", method="88.5 − 47.2",
        source_dataset=SRC_KREI, n=2, caveat="2차 인용. 기사 표기 41.3분")

    # ① 교통약자
    add(key="transport_vulnerable_man", value=VULN_POP_MAN, unit="만명",
        description="[2024년 말, 전국] 교통약자 인구 (고령자·장애인·임산부·영유아 동반자·어린이 등)", method="원문 값",
        n=TOTAL_POP_MAN, source_dataset=SRC_MOLIT, caveat="국토교통부 보도를 철도일보가 전재한 2차 자료")
    add(key="transport_vulnerable_pct", value=round(VULN_POP_MAN / TOTAL_POP_MAN * 100, 1), unit="%",
        description="[2024년 말, 전국] 전체 인구(5,122만명) 중 교통약자 비율", method="1,613 / 5,122 × 100",
        n=TOTAL_POP_MAN, source_dataset=SRC_MOLIT, caveat=f"기사 표기 {VULN_RATIO_PRINTED}%. 2차 인용")


if __name__ == "__main__":
    main()
