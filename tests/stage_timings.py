"""Ticket 13 AC 3: per-stage timings of the pipeline (plan section 4).

    uv run --locked python tests/stage_timings.py [--out PATH] [--repeats N]

Wraps the stage functions in the ``analysis`` namespace (``STAGES``) with timers,
runs ``read_frame -> analyse -> to_json -> write_mask_csv`` on the speed frame
(tests/speed.py), ticket 13's typical P 6 frame and the bench timing frame, and
writes the per-stage medians as a Markdown table, with interpreter + import time
(``-X importtime`` total and wall) and the cold CLI wall time
(``speed.time_cold_cli``). Run it on an idle machine, in the background (about
1-2 min); it writes .scratch/stripe-detector/stage-timings.md by default.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from pathlib import Path
from statistics import median
from typing import TYPE_CHECKING, Any

# feasibility sets single-threaded BLAS before anything imports NumPy, so it sorts first
# and the package is imported inside the functions.
import feasibility
import seed_guard
import slow_stamp
import speed
from protected import PROBE_SHAPE, SPEED_SPIKES, SPEED_TEST_SEED

if TYPE_CHECKING:
    import numpy as np

ROOT = feasibility.ROOT
DEFAULT_OUT = ROOT / ".scratch/stripe-detector/stage-timings.md"

# The analysis stages, in pipeline order; each is a name in the analysis module.
STAGES = (
    "reject_spikes",
    "find_clipped",
    "_light",
    "estimate_local_stripes",
    "_qualifying_regions",
    "_pre_break_forks",
    "_with_phase_breaks",
    "_post_break_forks",
)
# Around analyse.
OUTER = ("read_frame", "analyse", "to_json", "write_mask_csv")


@contextlib.contextmanager
def timed_stages() -> Iterator[dict[str, float]]:
    """While open, each ``STAGES`` function in ``analysis`` adds its wall seconds
    to the yielded dict under its name (summed over calls)."""
    from denoisifier import analysis

    spent: dict[str, float] = defaultdict(float)
    originals = {name: getattr(analysis, name) for name in STAGES}

    def wrap(name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def timed(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                spent[name] += time.perf_counter() - t0

        return timed

    for name, fn in originals.items():
        setattr(analysis, name, wrap(name, fn))
    try:
        yield spent
    finally:
        for name, fn in originals.items():
            setattr(analysis, name, fn)


def run_once(csv: Path, mask: Path) -> dict[str, float]:
    """One timed ``read_frame -> analyse -> to_json -> write_mask_csv`` on ``csv``:
    seconds per stage and per outer step."""
    from denoisifier import analysis
    from denoisifier.frame_io import read_frame, write_mask_csv

    out: dict[str, float] = {}
    t0 = time.perf_counter()
    frame = read_frame(csv).frame
    out["read_frame"] = time.perf_counter() - t0
    with timed_stages() as spent:
        t0 = time.perf_counter()
        report = analysis.analyse(frame)
        out["analyse"] = time.perf_counter() - t0
    out.update(spent)
    t0 = time.perf_counter()
    report.to_json()
    out["to_json"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    write_mask_csv(report.labels, mask)
    out["write_mask_csv"] = time.perf_counter() - t0
    return out


def frames() -> dict[str, np.ndarray]:
    """The three timed frames: the speed frame (AC 1), the typical P 6 frame
    (no breaks, no Forks; the speed recipe's seed) and the bench timing frame."""
    from denoisifier.synthetic import Emccd, generate

    typical = generate(
        seed=SPEED_TEST_SEED,
        shape=PROBE_SHAPE,
        period=6.0,
        angle_deg=-5.0,
        modulation_depth=0.5,
        mottle="scorched",
        noise=Emccd(),
        spikes=SPEED_SPIKES,
    ).frame
    timing = feasibility._frame(
        feasibility.TIMING_SEED, feasibility.DEPTH, PROBE_SHAPE, feasibility.TIMING_CASE
    )
    return {"speed (AC 1)": speed.speed_frame(), "typical P6": typical, "bench timing": timing}


def stage_medians(frame: np.ndarray, repeats: int) -> dict[str, float]:
    """Median seconds per stage and outer step over ``repeats`` runs (after one
    untimed warm-up on the same frame)."""
    from denoisifier.frame_io import write_frame_csv

    with tempfile.TemporaryDirectory() as d:
        csv, mask = Path(d) / "f.csv", Path(d) / "m.csv"
        write_frame_csv(frame, csv)
        run_once(csv, mask)
        runs = [run_once(csv, mask) for _ in range(repeats)]
    return {k: median(r.get(k, 0.0) for r in runs) for k in (*OUTER, *STAGES)}


def import_times() -> dict[str, float]:
    """``python -X importtime -c 'import denoisifier.cli'``: the cumulative
    import time of ``denoisifier.cli`` and the process's wall time, seconds."""
    t0 = time.perf_counter()
    done = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "import denoisifier.cli"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ},
    )
    wall = time.perf_counter() - t0
    cumulative = 0
    for line in done.stderr.splitlines():
        m = re.match(r"import time:\s+\d+ \|\s+(\d+) \|\s+denoisifier\.cli$", line)
        if m:
            cumulative = int(m.group(1))
    return {"importtime_s": cumulative / 1e6, "wall_s": wall}


def markdown(results: dict[str, dict[str, float]], imports: dict[str, float], cold: float) -> str:
    info = feasibility.run_info(workers=1)
    names = list(results)
    lines = [
        "# Ticket 13 stage timings (AC 3)",
        "",
        f"- Commit `{info['commit']}`; CPU {info['cpu']}; affinity"
        f" {len(os.sched_getaffinity(0))}; load {slow_stamp.loadavg()}.",
        f"- Python {info['python']}, numpy {info['numpy']}, scipy {info['scipy']}.",
        f"- Import `denoisifier.cli`: {imports['importtime_s']:.2f} s (`-X importtime`),"
        f" {imports['wall_s']:.2f} s wall (interpreter + imports).",
        f"- Cold CLI on the speed frame (`python -m denoisifier`): {cold:.2f} s, median.",
        "",
        "| stage | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    for key in (*OUTER, *STAGES):
        lines.append(f"| `{key}` | " + " | ".join(f"{results[n][key]:.3f}" for n in names) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    seed_guard.install()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)
    results = {name: stage_medians(f, args.repeats) for name, f in frames().items()}
    imports = import_times()
    cold = median(speed.time_cold_cli(args.repeats))
    text = markdown(results, imports, cold)
    args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
