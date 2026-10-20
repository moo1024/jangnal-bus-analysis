"""보고서에 인용한 수치를 05_results/numbers.json 에 기록한다.

모든 수치는 계산한 스크립트가 직접 기록하고, 보고서는 이 파일의 값만 인용한다.
"""
import inspect
import json
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "05_results" / "numbers.json"


def add(key, value, unit="", description="", method="", script="", line_ref="",
        n=None, ci=None, p=None, source_dataset="", caveat="", decimals=None, **_):
    d = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
    caller = inspect.stack()[1]
    d[key] = {"value": value, "unit": unit, "description": description, "method": method,
              "script": script or Path(caller.filename).name, "line": caller.lineno,
              "n": n, "ci": list(ci) if ci is not None else None, "p": p,
              "source_dataset": source_dataset, "caveat": caveat}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d[key]
