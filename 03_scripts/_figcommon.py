# -*- coding: utf-8 -*-
"""그림 스크립트 공통 — 수치 기록표·처리 결과 읽기 (값 하드코딩 없음)."""
import json
from pathlib import Path
import pandas as pd

AN = Path(__file__).resolve().parents[1]
SLUG = AN.parent
PRO = AN / "01_data" / "processed"
RAW = AN / "01_data" / "raw"
FIG = AN / "04_figures"
SHOT = SLUG / "04_작성본" / "screenshots"
_NUM = json.loads((AN / "05_results" / "numbers.json").read_text(encoding="utf-8"))["numbers"]


def num(key):
    return _NUM[key]["value"]


def fmt(key, d=0):
    v = num(key)
    return f"{v:,.{d}f}" if isinstance(v, (int, float)) else str(v)


def csv(name):
    return pd.read_csv(PRO / name, encoding="utf-8-sig")
