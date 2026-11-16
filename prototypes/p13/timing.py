"""PROTOTYPE (ticket 13): short single-process foreground timings of one harness frame.

    uv run --locked python prototypes/p13/timing.py <src> <frames dir> <frame name> [repeats]

Puts ``src`` first on ``sys.path``; times the bank (``estimate_local_stripes``), the break
pass (``_with_phase_breaks``) and the whole ``analyse`` (one untimed warm-up); prints min and
median of each, in seconds.
"""

from __future__ import annotations

import os
import pickle
import statistics
import sys
import time
from pathlib import Path
from typing import Any

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"


def main(argv: list[str]) -> None:
    src, directory, name = argv[0], Path(argv[1]), argv[2]
    repeats = int(argv[3]) if len(argv) > 3 else 3
    sys.path.insert(0, str(Path(src).resolve()))
    from denoisifier import analysis
    from denoisifier.report import BinFactors

    with (directory / "frames.pkl").open("rb") as f:
        frames = {n: (fr, b) for n, fr, b in pickle.load(f)}
    frame, (h, v) = frames[name]
    bins = BinFactors(horizontal=h, vertical=v)
    stages: dict[str, list[float]] = {}

    def timed(stage: str, fn: Any) -> Any:
        def wrapper(*args: Any, **kw: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return fn(*args, **kw)
            finally:
                stages.setdefault(stage, []).append(time.perf_counter() - t0)

        return wrapper

    analysis.estimate_local_stripes = timed("bank", analysis.estimate_local_stripes)
    analysis._with_phase_breaks = timed("breaks", analysis._with_phase_breaks)
    analysis.analyse(frame, bin_factors=bins)
    stages.clear()
    for _ in range(repeats):
        t0 = time.perf_counter()
        analysis.analyse(frame, bin_factors=bins)
        stages.setdefault("analyse", []).append(time.perf_counter() - t0)
    for stage, ts in stages.items():
        print(
            f"{name} {stage}: min {min(ts):.3f} median {statistics.median(ts):.3f} "
            f"({' '.join(f'{t:.2f}' for t in ts)})"
        )


if __name__ == "__main__":
    main(sys.argv[1:])
