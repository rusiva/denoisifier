"""Ticket 13 AC 3: per-stage timings of the pipeline (plan section 4).

    uv run --locked python tests/stage_timings.py [--out PATH] [--repeats N]

Wraps the stage functions in the ``analysis`` namespace (``STAGES``) with timers,
runs ``read_frame -> analyse -> to_json -> write_mask_csv`` on the speed frame
(tests/speed.py), ticket 13's typical P 6 frame and the bench timing frame, at one
bank thread and at the shipped default, and writes the per-stage medians as a
Markdown table beside BASE (prototype P1's table, quoted: ``BASE_P1``), with
interpreter + import time (``-X importtime`` total and wall), the cold CLI wall
time (``speed.time_cold_cli``) and the slices adopted and dropped (``SLICES``). Run
it on an idle machine, in the background (a few minutes); it writes
.scratch/stripe-detector/stage-timings.md by default.
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
from protected import PROBE_SHAPE, SPEED_SPIKES, SPEED_TYPICAL_TEST_SEED

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
# read_frame + analyse + to_json: the span make bench times (tests/speed.py).
WARM = "warm pipeline (read -> analyse -> to_json)"

# BASE (aae4084) on the speed frame, idle, one thread: prototype P1's table, quoted
# (.scratch/stripe-detector/handoffs/13-prototype-p1.md; plan section 1). P1 timed the
# Fork searches together and spikes + _light + the rest together.
BASE_P1 = {
    "read_frame": "0.12-0.15",
    "analyse": "8.20",
    "estimate_local_stripes": "5.63",
    "_qualifying_regions": "0.35",
    "_pre_break_forks": "0.39 (pre + post)",
    "_with_phase_breaks": "1.61",
    "reject_spikes": "0.21 (spikes + `_light` + other)",
    WARM: "8.68",
}
BASE_P1_COLD_CLI_S = "9.46"
BASE_P1_TYPICAL_WARM_S = "7.31"

# Ticket 13's slices and what became of each (plan section 2; ticket Comments).
SLICES = (
    ("slice 1, lazy cold-start imports", "adopted (57ac55c)"),
    ("slice 2, bank loop with reused buffers", "adopted (df3c78b)"),
    ("slice 3, one forward spectrum", "adopted (ef79e1f)"),
    ("slice 4b, deterministic bank Angle tie-break", "adopted (ea359a7)"),
    ("slice 5, Gaussians on their support box, pruned inverse FFT", "adopted (53a7871)"),
    ("slice 6, single-precision bank", "dropped (failed 'found identically')"),
    ("slice 7, coarse-strided break finder", "dropped (failed 'same basin'; ticket 22)"),
    ("slice 4, bank threads across Periods", "adopted (231aabb)"),
    ("slice 8, multirate bank", "dropped from this ticket (ticket 19)"),
)


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


def run_once(csv: Path, mask: Path, threads: int | None = None) -> dict[str, float]:
    """One timed ``read_frame -> analyse -> to_json -> write_mask_csv`` on ``csv``,
    the bank on ``threads`` (None: the shipped default): seconds per stage and per
    outer step."""
    from denoisifier import analysis
    from denoisifier.frame_io import read_frame, write_mask_csv

    out: dict[str, float] = {}
    t0 = time.perf_counter()
    frame = read_frame(csv).frame
    out["read_frame"] = time.perf_counter() - t0
    with timed_stages() as spent:
        t0 = time.perf_counter()
        report = analysis._analyse(frame, threads=threads)
        out["analyse"] = time.perf_counter() - t0
    out.update(spent)
    t0 = time.perf_counter()
    report.to_json()
    out["to_json"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    write_mask_csv(report.labels, mask)
    out["write_mask_csv"] = time.perf_counter() - t0
    out[WARM] = out["read_frame"] + out["analyse"] + out["to_json"]
    return out


def frames() -> dict[str, np.ndarray]:
    """The three timed frames: the speed frame (AC 1), the typical P 6 frame
    (no breaks, no Forks; its own seed) and the bench timing frame."""
    from denoisifier.synthetic import Emccd, generate

    typical = generate(
        seed=SPEED_TYPICAL_TEST_SEED,
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


def stage_medians(frame: np.ndarray, repeats: int, threads: int | None) -> dict[str, float]:
    """Median seconds per stage and outer step over ``repeats`` runs, the bank on
    ``threads`` (after one untimed warm-up on the same frame)."""
    from denoisifier.frame_io import write_frame_csv

    with tempfile.TemporaryDirectory() as d:
        csv, mask = Path(d) / "f.csv", Path(d) / "m.csv"
        write_frame_csv(frame, csv)
        run_once(csv, mask, threads)
        runs = [run_once(csv, mask, threads) for _ in range(repeats)]
    return {k: median(r.get(k, 0.0) for r in runs) for k in (*OUTER, WARM, *STAGES)}


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


def markdown(
    results: dict[str, dict[str, float]],
    imports: dict[str, float],
    cold: float,
    default_threads: int,
) -> str:
    """The AC 3 record: ``results`` (column name -> seconds per stage) beside the
    quoted BASE column, with the run's machine, the import and cold CLI times and
    the slices."""
    info = feasibility.run_info(workers=1)
    names = list(results)
    lines = [
        "# Ticket 13 stage timings (AC 3)",
        "",
        f"- Commit `{info['commit']}`; CPU {info['cpu']}; affinity"
        f" {len(os.sched_getaffinity(0))}; load {slow_stamp.loadavg()}.",
        f"- Python {info['python']}, numpy {info['numpy']}, scipy {info['scipy']}.",
        f"- Default bank threads here: {default_threads} (`_local_stripes.bank_threads`).",
        f"- Import `denoisifier.cli`: {imports['importtime_s']:.2f} s (`-X importtime`),"
        f" {imports['wall_s']:.2f} s wall (interpreter + imports).",
        f"- Cold CLI on the speed frame (`python -m denoisifier`, default threads):"
        f" {cold:.2f} s, median (BASE {BASE_P1_COLD_CLI_S} s).",
        f"- BASE is prototype P1's table at `aae4084` (speed frame, idle, one thread),"
        f" quoted; P1's typical P 6 warm pipeline was {BASE_P1_TYPICAL_WARM_S} s.",
        "",
        "| stage | BASE (P1), speed (AC 1) | " + " | ".join(names) + " |",
        "|---|---|" + "---|" * len(names),
    ]
    for key in (*OUTER, WARM, *STAGES):
        label = key if key == WARM else f"`{key}`"
        cells = [BASE_P1.get(key, "-"), *(f"{results[n][key]:.3f}" for n in names)]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "Slices:", ""]
    lines += [f"- {name}: {fate}" for name, fate in SLICES]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    from denoisifier._local_stripes import bank_threads

    seed_guard.install()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)
    default = bank_threads()
    results = {}
    for name, f in frames().items():
        results[f"{name}, threads 1"] = stage_medians(f, args.repeats, 1)
        results[f"{name}, threads {default} (default)"] = stage_medians(f, args.repeats, None)
    imports = import_times()
    cold = median(speed.time_cold_cli(args.repeats))
    text = markdown(results, imports, cold, default)
    args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
