"""Ticket 03 feasibility gate driver: weak stripes (m = 0.2) at 1% False Alarms.

Imported by tests/test_feasibility_gate.py; also runs as a script:

    uv run python tests/feasibility.py [--skip-probe] [--workers N] [--out PATH]

Detected at threshold t means ``analyse(frame).score > t``, the rule analyse
uses for its own verdict. The detector is measured as it is (no tuning).
"""

from __future__ import annotations

import os

# Single-threaded BLAS/OpenMP in the worker processes. Set before NumPy is
# imported here; workers are spawned (not forked), so they import NumPy fresh
# and read these even when a parent (pytest) imported NumPy first.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import multiprocessing  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from collections.abc import Sequence  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from dataclasses import asdict, dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Literal  # noqa: E402
from statistics import median  # noqa: E402

import numpy as np  # noqa: E402
import scipy  # noqa: E402

from cases import CASES  # noqa: E402
from denoisifier import analyse  # noqa: E402
from denoisifier._calibration import (  # noqa: E402
    _order,
    false_alarm_tolerance,
    rate_interval,
    threshold_for_false_alarm_rate,
)
from denoisifier.synthetic import Emccd, generate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / ".scratch/stripe-detector/feasibility-gate.json"

RATE = 0.01
# Scorched Mottle; about 100 photons at the peak, EM gain 300, read noise 50 e, CIC 0.005.
MOTTLE: Literal["scorched"] = "scorched"
NOISE = Emccd()
DEPTH = 0.2

# Gate, judged at 256x256 (plan R3).
SHAPE = (256, 256)
CALIBRATION_SEEDS = range(10_000, 12_000)  # 2000 Stripe-free
HELD_OUT_FREE_SEEDS = range(20_000, 21_000)  # 1000 Stripe-free
HELD_OUT_STRIPED_SEEDS = range(30_000, 30_500)  # 500 at m = 0.2, CASES[seed % 10]: 50 per case

# Full-frame probe (rows x cols). Informs the result; below PROBE_MIN_RATE it
# fails the gate (plan B3).
PROBE_SHAPE = (400, 1600)
PROBE_CALIBRATION_SEEDS = range(70_000, 70_300)  # 300 -> k = 3
PROBE_FREE_SEEDS = range(71_000, 71_200)  # 200
PROBE_STRIPED_SEEDS = range(72_000, 72_100)  # 100, 10 per case
PROBE_MIN_RATE = 0.95

# One 400x1600 frame, m = 0.2, Period 8, Angle 0.
TIMING_SEED = 40_000
TIMING_LIMIT_S = 10.0


def time_full_frame(repeats: int = 3) -> list[float]:
    """Seconds for ``analyse`` on one 400x1600 frame, single process.

    The frame is generated first and one 256x256 warm-up call is made; neither
    is timed.
    """
    frame = _frame(TIMING_SEED, DEPTH, PROBE_SHAPE, (8, 0))
    analyse(_frame(TIMING_SEED, 0.0, SHAPE, (8, 0)))
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        analyse(frame)
        times.append(time.perf_counter() - t0)
    return times


def case_of(seed: int) -> tuple[int, int]:
    """(Period, Angle) for a seed. Stripe-free frames take one too; at m = 0
    it does not change the frame, and the RNG stream is the same."""
    return CASES[seed % len(CASES)]


def _score_one(job: tuple[int, float, tuple[int, int]]) -> float:
    seed, depth, shape = job
    return analyse(_frame(seed, depth, shape, case_of(seed))).score


def _frame(seed: int, depth: float, shape: tuple[int, int], case: tuple[int, int]) -> np.ndarray:
    period, angle_deg = case
    return generate(
        seed=seed, shape=shape, period=period, angle_deg=angle_deg, modulation_depth=depth, mottle=MOTTLE, noise=NOISE
    ).frame


def score_batch(seeds: Sequence[int], depth: float, shape: tuple[int, int], workers: int | None = None) -> np.ndarray:
    """Stripe Scores of generated frames, in seed order whatever the worker count."""
    workers = workers or max(1, (os.cpu_count() or 2) // 2)
    jobs = [(seed, depth, shape) for seed in seeds]
    # Spawned workers import NumPy fresh, so the thread variables set above apply.
    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn")) as ex:
        return np.array(list(ex.map(_score_one, jobs, chunksize=4)), dtype=float)


@dataclass(frozen=True)
class CaseResult:
    period: int
    angle_deg: int
    detected: int
    n: int
    min_score: float
    min_over_threshold: float


@dataclass(frozen=True)
class RateResult:
    shape: tuple[int, int]
    threshold: float
    k: int
    calibration_n: int
    calibration_above: int
    free_n: int
    false_alarms: int
    false_alarm_interval: tuple[float, float]
    false_alarm_tolerance: tuple[int, int]
    striped_n: int
    detected: int
    detection_interval: tuple[float, float]
    cases: tuple[CaseResult, ...]

    @property
    def false_alarm_rate(self) -> float:
        return self.false_alarms / self.free_n

    @property
    def detection_rate(self) -> float:
        return self.detected / self.striped_n

    def per_case_summary(self) -> str:
        return ", ".join(
            f"{c.period}px/{c.angle_deg}deg {c.detected}/{c.n} (min {c.min_over_threshold:.2f}x)" for c in self.cases
        )


def measure(
    cal_seeds: Sequence[int],
    free_seeds: Sequence[int],
    striped_seeds: Sequence[int],
    shape: tuple[int, int],
    workers: int | None = None,
) -> RateResult:
    """Set the 1% threshold on the calibration seeds alone, then score the
    held-out sets against it."""
    cal = score_batch(cal_seeds, 0.0, shape, workers)
    threshold = threshold_for_false_alarm_rate(cal, RATE)
    free = score_batch(free_seeds, 0.0, shape, workers)
    striped = score_batch(striped_seeds, DEPTH, shape, workers)

    false_alarms = int((free > threshold).sum())
    detected = int((striped > threshold).sum())
    case_ids = np.array([case_of(s) for s in striped_seeds])
    cases = []
    for period, angle_deg in CASES:
        sel = striped[(case_ids[:, 0] == period) & (case_ids[:, 1] == angle_deg)]
        if sel.size:
            cases.append(
                CaseResult(
                    period=period,
                    angle_deg=angle_deg,
                    detected=int((sel > threshold).sum()),
                    n=int(sel.size),
                    min_score=float(sel.min()),
                    min_over_threshold=float(sel.min() / threshold),
                )
            )
    return RateResult(
        shape=shape,
        threshold=threshold,
        k=_order(len(cal), RATE),
        calibration_n=len(cal),
        calibration_above=int((cal > threshold).sum()),
        free_n=len(free),
        false_alarms=false_alarms,
        false_alarm_interval=rate_interval(false_alarms, len(free)),
        false_alarm_tolerance=false_alarm_tolerance(len(cal), len(free), RATE),
        striped_n=len(striped),
        detected=detected,
        detection_interval=rate_interval(detected, len(striped)),
        cases=tuple(cases),
    )


def measure_gate(workers: int | None = None) -> RateResult:
    return measure(CALIBRATION_SEEDS, HELD_OUT_FREE_SEEDS, HELD_OUT_STRIPED_SEEDS, SHAPE, workers)


def measure_probe(workers: int | None = None) -> RateResult:
    return measure(PROBE_CALIBRATION_SEEDS, PROBE_FREE_SEEDS, PROBE_STRIPED_SEEDS, PROBE_SHAPE, workers)


def _ranges(**named: range) -> dict[str, list[int]]:
    return {name: [r.start, r.stop - 1] for name, r in named.items()}


def run_info() -> dict:
    """Commit, machine, versions and every setting, for the written result."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()

    # Dirty only for changes to the measured code, not to notes under .scratch.
    commit = git("describe", "--always")
    if git("status", "--porcelain", "--", "src", "tests", "pyproject.toml", "uv.lock"):
        commit += "-dirty"
    cpu = platform.processor()
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return {
        "commit": commit,
        "cpu": cpu,
        "logical_cpus": os.cpu_count(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "rate": RATE,
        "modulation_depth": DEPTH,
        "mottle": MOTTLE,
        "emccd": asdict(NOISE),
        "cases": CASES,
        "gate_shape": SHAPE,
        "probe_shape": PROBE_SHAPE,
        "seeds": _ranges(
            calibration=CALIBRATION_SEEDS,
            held_out_free=HELD_OUT_FREE_SEEDS,
            held_out_striped=HELD_OUT_STRIPED_SEEDS,
            probe_calibration=PROBE_CALIBRATION_SEEDS,
            probe_free=PROBE_FREE_SEEDS,
            probe_striped=PROBE_STRIPED_SEEDS,
            timing=range(TIMING_SEED, TIMING_SEED + 1),
        ),
    }


def _result_dict(r: RateResult) -> dict:
    d = asdict(r)
    d["false_alarm_rate"] = r.false_alarm_rate
    d["detection_rate"] = r.detection_rate
    return d


def _table(name: str, r: RateResult) -> str:
    lo, hi = r.detection_interval
    flo, fhi = r.false_alarm_tolerance
    lines = [
        f"### {name} ({r.shape[0]}x{r.shape[1]})",
        "",
        f"- Threshold {r.threshold:.2f} (k = {r.k} largest of {r.calibration_n} calibration scores)",
        f"- Held-out False Alarms {r.false_alarms}/{r.free_n} = {r.false_alarm_rate:.3f} (tolerance {flo}-{fhi})",
        f"- m = {DEPTH} detected {r.detected}/{r.striped_n} = {r.detection_rate:.3f}, exact 95% CI ({lo:.3f}, {hi:.3f})",
        "",
        "| Period | Angle | detected | min score | min / threshold |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {c.period} | {c.angle_deg} | {c.detected}/{c.n} | {c.min_score:.1f} | {c.min_over_threshold:.2f} |"
        for c in r.cases
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--skip-probe", action="store_true", help="skip the full-frame probe")
    parser.add_argument("--workers", type=int, default=None, help="worker processes (default: half the CPUs)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="JSON result path")
    args = parser.parse_args(argv)

    out: dict = {"run_info": run_info()}
    # Timing first, before any worker pool has run.
    times = time_full_frame()
    out["timing"] = {"shape": PROBE_SHAPE, "seconds": times, "median_s": median(times), "limit_s": TIMING_LIMIT_S}
    print(f"analyse on one 400x1600 frame: {[round(t, 2) for t in times]} s, median {median(times):.2f} s", flush=True)

    gate = measure_gate(args.workers)
    out["gate"] = _result_dict(gate)
    print(_table("Gate", gate), flush=True)
    if not args.skip_probe:
        probe = measure_probe(args.workers)
        out["probe"] = _result_dict(probe)
        print(_table("Full-frame probe", probe), flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
