"""make bench: the speed gate (ticket agent-gates/05), outside check and check-slow.

    uv run --locked python tests/bench.py [--out PATH]

Times ``analyse`` on the timing frame (feasibility.time_full_frame: TIMING_SEED,
TIMING_CASE, PROBE_SHAPE, one untimed warm-up) BENCH_REPEATS times, single
process with single-threaded BLAS, and records the median with commit, CPU,
load average and versions. Exits 1 when the median exceeds TIMING_LIMIT_S
(ticket 03's 10 s gate); reports ticket 13's TARGET_TIMING_S without failing.
Run it in the background on an idle machine.

By default the record is the git-ignored .gate/bench.json. A tracked record
(--out .scratch/stripe-detector/bench.json) is committed only at ticket 13, for
a handoff's speed claim, or once in ticket agent-gates/05 as the first record.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median

# feasibility sets single-threaded BLAS before it imports NumPy, so it comes first.
import feasibility
import seed_guard
import slow_stamp
from protected import BENCH_IDLE_LOAD, BENCH_REPEATS, TARGET_TIMING_S, TIMING_LIMIT_S

ROOT = feasibility.ROOT
DEFAULT_OUT = f"{slow_stamp.GATE_DIR}/bench.json"


def main(argv: list[str] | None = None) -> int:
    seed_guard.install()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--out", type=Path, default=None, help=f"record path (default {DEFAULT_OUT})"
    )
    args = parser.parse_args(argv)
    out_path: Path = args.out if args.out is not None else ROOT / DEFAULT_OUT

    load_start = feasibility.loadavg()
    seconds = feasibility.time_full_frame(repeats=BENCH_REPEATS)
    load_end = feasibility.loadavg()
    median_s = median(seconds)
    info = feasibility.run_info(workers=1)
    record = {
        "commit": info["commit"],
        "cpu": info["cpu"],
        "logical_cpus": info["logical_cpus"],
        "python": info["python"],
        "numpy": info["numpy"],
        "scipy": info["scipy"],
        "threads": feasibility.thread_settings(),
        "loadavg": {"start": load_start, "end": load_end},
        "shape": feasibility.PROBE.shape,
        "seed": feasibility.TIMING_SEED,
        "case": feasibility.TIMING_CASE,
        "seconds": seconds,
        "median_s": median_s,
        "limit_s": TIMING_LIMIT_S,
        "target_s": TARGET_TIMING_S,
        "meets_limit": median_s <= TIMING_LIMIT_S,
        "meets_target": median_s <= TARGET_TIMING_S,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2) + "\n")

    print(f"analyse on one full frame: {[round(t, 2) for t in seconds]} s, median {median_s:.2f} s")
    print(
        f"ticket 13 target {TARGET_TIMING_S} s: " + ("met" if record["meets_target"] else "not met")
    )
    one_minute = load_start.split()[0] if load_start != "unavailable" else None
    if one_minute is not None and float(one_minute) > BENCH_IDLE_LOAD:
        print(f"make bench: warning: load average {load_start} at start; the machine is not idle")
    print(f"wrote {out_path}")
    if not record["meets_limit"]:
        print(f"make bench: median {median_s:.2f} s exceeds the {TIMING_LIMIT_S} s limit")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
