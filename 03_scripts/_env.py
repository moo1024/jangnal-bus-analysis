"""계산 스레드 수를 제한한다(분석 PC 의 다른 작업에 양보)."""
import os


def cap(threads: str = "4", **_):
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(v, str(threads))
