"""Ticket 03 feasibility gate driver: weak stripes (m = 0.2) at 1% False Alarms.

Imported by tests/test_feasibility_gate.py; also runs as a script:

    uv run python tests/feasibility.py [--skip-probe] [--workers N] [--out PATH]

Detected at threshold t means ``analyse(frame).score > t``, the rule analyse
uses for its own verdict. The detector is measured as it is (no tuning).
"""

from __future__ import annotations

import os

# Imports no NumPy (seed_guard.py), so it can come before the thread variables.
import seed_guard

# Single-threaded BLAS/OpenMP in the worker processes. Set before NumPy is
# imported here; workers are spawned (not forked), so they import NumPy fresh
# and read these even when a parent (pytest) imported NumPy first.
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
for _var in THREAD_VARS:
    os.environ.setdefault(_var, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import multiprocessing  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from collections.abc import Callable, Sequence  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from dataclasses import asdict, dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from statistics import median  # noqa: E402
from typing import Literal, NamedTuple  # noqa: E402

import numpy as np  # noqa: E402
import scipy  # noqa: E402

from cases import CASES, Case  # noqa: E402
from denoisifier import analyse  # noqa: E402
from denoisifier._calibration import (  # noqa: E402
    false_alarm_tolerance,
    rate_interval,
    threshold_for_false_alarm_rate,
    threshold_rank,
)
from denoisifier.synthetic import Emccd, generate  # noqa: E402
from protected import (  # noqa: E402
    FALSE_ALARM_RATE,
    GATE_CALIBRATION_SEEDS,
    GATE_FREE_SEEDS,
    GATE_SHAPE,
    GATE_STORED_THRESHOLD,
    GATE_STRIPED_SEEDS,
    PROBE_CALIBRATION_SEEDS,
    PROBE_FREE_SEEDS,
    PROBE_SHAPE,
    PROBE_STORED_THRESHOLD,
    PROBE_STRIPED_SEEDS,
    REGRESSION_FREE_SEEDS,
    REGRESSION_MAX_FALSE_ALARMS,
    REGRESSION_MIN_DETECTED,
    REGRESSION_PROBE_MIN_DETECTED,
    REGRESSION_PROBE_STRIPED_SEEDS,
    REGRESSION_STRIPED_SEEDS,
    REGRESSION_TIMED_FRAMES,
    SLOW_TIMING_LIMIT_S,
    TIMING_CASE,
    TIMING_LIMIT_S,
    TIMING_SEED,
    WEAK_DEPTH,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / ".scratch/stripe-detector/feasibility-gate.json"

# The rate, depth, shapes, seeds and limits are protected numbers (protected.py).
RATE = FALSE_ALARM_RATE
# Scorched Mottle; about 100 photons at the peak, EM gain 300, read noise 50 e, CIC 0.005.
MOTTLE: Literal["scorched"] = "scorched"
NOISE = Emccd()
DEPTH = WEAK_DEPTH


class SeedPlan(NamedTuple):
    """Frame shape (rows, cols) and seed sets for one measurement. The
    threshold is set on ``calibration`` (Stripe-free) alone; ``free``
    (Stripe-free) and ``striped`` (m = DEPTH) are held out."""

    shape: tuple[int, int]
    calibration: range
    free: range
    striped: range


# Gate, judged at 256x256 (plan R3). Striped frames take CASES[seed % 10].
GATE = SeedPlan(
    shape=GATE_SHAPE,
    calibration=GATE_CALIBRATION_SEEDS,
    free=GATE_FREE_SEEDS,
    striped=GATE_STRIPED_SEEDS,
)

# Full-frame probe. Informs the result; below PROBE_MIN_DETECTION_RATE it
# fails the gate (plan B3).
PROBE = SeedPlan(
    shape=PROBE_SHAPE,
    calibration=PROBE_CALIBRATION_SEEDS,
    free=PROBE_FREE_SEEDS,
    striped=PROBE_STRIPED_SEEDS,
)

# The timing frame is one full frame (PROBE.shape) at TIMING_SEED, m = DEPTH.

# Every seed set, by the name the result JSON records it under.
SEED_SETS: dict[str, range] = {
    "calibration": GATE.calibration,
    "held_out_free": GATE.free,
    "held_out_striped": GATE.striped,
    "probe_calibration": PROBE.calibration,
    "probe_free": PROBE.free,
    "probe_striped": PROBE.striped,
    "timing": range(TIMING_SEED, TIMING_SEED + 1),
}


def _shape_text(shape: tuple[int, int]) -> str:
    return f"{shape[0]}x{shape[1]}"


def time_full_frame(repeats: int = 3) -> list[float]:
    """Seconds for ``analyse`` on one full frame (PROBE.shape), single process.

    The frame is generated first and one warm-up call at GATE.shape is made;
    neither is timed.
    """
    frame = _frame(TIMING_SEED, DEPTH, PROBE.shape, TIMING_CASE)
    analyse(_frame(TIMING_SEED, 0.0, GATE.shape, TIMING_CASE))
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        analyse(frame)
        times.append(time.perf_counter() - t0)
    return times


def time_frames(
    seeds: Sequence[int], depth: float, shape: tuple[int, int], case_for: Callable[[int], Case]
) -> list[tuple[float, float]]:
    """(seconds, Stripe Score) of ``analyse`` on each seed's frame, serial and in
    this process. The frames are generated first and one warm-up call at
    GATE.shape is made; neither is timed."""
    frames = [_frame(seed, depth, shape, case_for(seed)) for seed in seeds]
    analyse(_frame(seeds[0], 0.0, GATE.shape, case_for(seeds[0])))
    out = []
    for frame in frames:
        t0 = time.perf_counter()
        score = analyse(frame).score
        out.append((time.perf_counter() - t0, float(score)))
    return out


def case_of(seed: int) -> Case:
    """Period and Angle for a seed. Stripe-free frames take one too; at m = 0
    it does not change the frame, and the RNG stream is the same."""
    return CASES[seed % len(CASES)]


def _score_one(job: tuple[int, float, tuple[int, int]]) -> float:
    seed, depth, shape = job
    return analyse(_frame(seed, depth, shape, case_of(seed))).score


def _frame(seed: int, depth: float, shape: tuple[int, int], case: Case) -> np.ndarray:
    return generate(
        seed=seed,
        shape=shape,
        period=case.period,
        angle_deg=case.angle_deg,
        modulation_depth=depth,
        mottle=MOTTLE,
        noise=NOISE,
    ).frame


def resolve_workers(workers: int | None = None) -> int:
    """The worker process count: ``workers``, else three quarters of the
    logical CPUs (12 of 16), leaving the rest for other work."""
    if workers:
        return workers
    n = os.cpu_count() or 2
    return max(1, n - n // 4)


def score_batch(
    seeds: Sequence[int], depth: float, shape: tuple[int, int], workers: int | None = None
) -> np.ndarray:
    """Stripe Scores of generated frames, in seed order whatever the worker count."""
    jobs = [(seed, depth, shape) for seed in seeds]
    # Spawned workers import NumPy fresh, so the thread variables set above apply.
    # Each worker installs the seed guard with this process's allowed ranges.
    with ProcessPoolExecutor(
        resolve_workers(workers),
        mp_context=multiprocessing.get_context("spawn"),
        initializer=seed_guard.install_worker,
        initargs=(seed_guard.worker_allowance(),),
    ) as ex:
        return np.array(list(ex.map(_score_one, jobs, chunksize=4)), dtype=float)


def _count_above(scores: np.ndarray, threshold: float) -> int:
    """How many scores are detected at threshold (score > threshold)."""
    return int((scores > threshold).sum())


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
            f"{c.period}px/{c.angle_deg}deg {c.detected}/{c.n} (min {c.min_over_threshold:.2f}x)"
            for c in self.cases
        )

    def to_dict(self) -> dict:
        """All fields plus the two rates, for the result JSON."""
        return {
            **asdict(self),
            "false_alarm_rate": self.false_alarm_rate,
            "detection_rate": self.detection_rate,
        }

    def table(self, name: str) -> str:
        """Markdown summary and per-case table, printed by main()."""
        lo, hi = self.detection_interval
        flo, fhi = self.false_alarm_tolerance
        lines = [
            f"### {name} ({_shape_text(self.shape)})",
            "",
            f"- Threshold {self.threshold:.2f}"
            f" (k = {self.k} largest of {self.calibration_n} calibration scores)",
            f"- Held-out False Alarms {self.false_alarms}/{self.free_n}"
            f" = {self.false_alarm_rate:.3f} (tolerance {flo}-{fhi})",
            f"- m = {DEPTH} detected {self.detected}/{self.striped_n} = {self.detection_rate:.3f},"
            f" exact 95% CI ({lo:.3f}, {hi:.3f})",
            "",
            "| Period | Angle | detected | min score | min / threshold |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {c.period} | {c.angle_deg} | {c.detected}/{c.n}"
            f" | {c.min_score:.1f} | {c.min_over_threshold:.2f} |"
            for c in self.cases
        ]
        return "\n".join(lines)


def _case_results(
    seeds: Sequence[int], scores: np.ndarray, threshold: float
) -> tuple[CaseResult, ...]:
    """Detected count and lowest score per Case of the striped ``seeds``."""
    seed_cases = [case_of(s) for s in seeds]
    cases = []
    for case in CASES:
        case_scores = scores[np.array([c == case for c in seed_cases], dtype=bool)]
        if case_scores.size:
            cases.append(
                CaseResult(
                    period=case.period,
                    angle_deg=case.angle_deg,
                    detected=_count_above(case_scores, threshold),
                    n=int(case_scores.size),
                    min_score=float(case_scores.min()),
                    min_over_threshold=float(case_scores.min() / threshold),
                )
            )
    return tuple(cases)


def measure(plan: SeedPlan, workers: int | None = None) -> RateResult:
    """Set the 1% threshold on the calibration seeds alone, then score the
    held-out sets against it."""
    # The one calibration step: only it may use the calibration seeds (seed_guard.py).
    with seed_guard.calibrating(plan.calibration):
        calibration_scores = score_batch(plan.calibration, 0.0, plan.shape, workers)
    threshold = threshold_for_false_alarm_rate(calibration_scores, RATE)
    free_scores = score_batch(plan.free, 0.0, plan.shape, workers)
    striped_scores = score_batch(plan.striped, DEPTH, plan.shape, workers)

    false_alarms = _count_above(free_scores, threshold)
    detected = _count_above(striped_scores, threshold)
    cases = _case_results(plan.striped, striped_scores, threshold)
    return RateResult(
        shape=plan.shape,
        threshold=threshold,
        k=threshold_rank(len(calibration_scores), RATE),
        calibration_n=len(calibration_scores),
        calibration_above=_count_above(calibration_scores, threshold),
        free_n=len(free_scores),
        false_alarms=false_alarms,
        false_alarm_interval=rate_interval(false_alarms, len(free_scores)),
        false_alarm_tolerance=false_alarm_tolerance(
            len(calibration_scores), len(free_scores), RATE
        ),
        striped_n=len(striped_scores),
        detected=detected,
        detection_interval=rate_interval(detected, len(striped_scores)),
        cases=tuple(cases),
    )


def measure_gate(workers: int | None = None) -> RateResult:
    return measure(GATE, workers)


def measure_probe(workers: int | None = None) -> RateResult:
    return measure(PROBE, workers)


def run_info(workers: int) -> dict:
    """Commit, machine, versions and every setting, for the written result."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()

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
        "workers": workers,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "rate": RATE,
        "modulation_depth": DEPTH,
        "mottle": MOTTLE,
        "emccd": asdict(NOISE),
        "cases": CASES,
        "gate_shape": GATE.shape,
        "probe_shape": PROBE.shape,
        "seeds": {name: [r.start, r.stop - 1] for name, r in SEED_SETS.items()},
    }


def measure_all(workers: int | None = None, probe: bool = True) -> dict:
    """Run info, timing, the gate and (optionally) the probe: the dict main() saves."""
    workers = resolve_workers(workers)
    out: dict = {"run_info": run_info(workers)}
    # Timing first, before any worker pool has run.
    times = time_full_frame()
    out["timing"] = {
        "shape": PROBE.shape,
        "seconds": times,
        "median_s": median(times),
        "limit_s": TIMING_LIMIT_S,
    }
    print(
        f"analyse on one {_shape_text(PROBE.shape)} frame: {[round(t, 2) for t in times]} s,"
        f" median {median(times):.2f} s",
        flush=True,
    )

    gate = measure_gate(workers)
    out["gate"] = gate.to_dict()
    print(gate.table("Gate"), flush=True)
    if probe:
        probe_measurement = measure_probe(workers)
        out["probe"] = probe_measurement.to_dict()
        print(probe_measurement.table("Full-frame probe"), flush=True)
    return out


class RegressionPlan(NamedTuple):
    """The slow tier's regression check (ticket agent-gates/05): fresh seeds
    scored at stored thresholds, with no calibration. The first ``timed``
    ``probe_striped`` seeds are analysed serially and timed; they count in the
    probe total."""

    gate_shape: tuple[int, int]
    probe_shape: tuple[int, int]
    gate_threshold: float
    probe_threshold: float
    striped: range  # gate_shape, m = DEPTH
    free: range  # gate_shape, Stripe-free
    probe_striped: range  # probe_shape, m = DEPTH
    timed: int
    min_detected: int
    max_false_alarms: int
    probe_min_detected: int


REGRESSION = RegressionPlan(
    gate_shape=GATE_SHAPE,
    probe_shape=PROBE_SHAPE,
    gate_threshold=GATE_STORED_THRESHOLD,
    probe_threshold=PROBE_STORED_THRESHOLD,
    striped=REGRESSION_STRIPED_SEEDS,
    free=REGRESSION_FREE_SEEDS,
    probe_striped=REGRESSION_PROBE_STRIPED_SEEDS,
    timed=REGRESSION_TIMED_FRAMES,
    min_detected=REGRESSION_MIN_DETECTED,
    max_false_alarms=REGRESSION_MAX_FALSE_ALARMS,
    probe_min_detected=REGRESSION_PROBE_MIN_DETECTED,
)


def loadavg() -> str:
    """/proc/loadavg as one line, or "unavailable"."""
    try:
        return Path("/proc/loadavg").read_text().strip()
    except OSError:
        return "unavailable"


def thread_settings() -> dict[str, str | None]:
    """The BLAS/OpenMP thread variables as this process sees them."""
    return {v: os.environ.get(v) for v in THREAD_VARS}


def regression_check(plan: RegressionPlan = REGRESSION, workers: int | None = None) -> dict:
    """Score ``plan``'s seeds at its stored thresholds: the counts, per-Case
    breakdown, timed frames and run info. Asserts nothing (the slow tests do)."""
    workers = resolve_workers(workers)
    t_start = time.perf_counter()
    load_start = loadavg()
    # Timing first, before any worker pool has run.
    timed_seeds = plan.probe_striped[: plan.timed]
    timed = time_frames(timed_seeds, DEPTH, plan.probe_shape, case_of)
    pooled = score_batch(plan.probe_striped[plan.timed :], DEPTH, plan.probe_shape, workers)
    probe_scores = np.concatenate([np.array([s for _, s in timed], dtype=float), pooled])
    striped_scores = score_batch(plan.striped, DEPTH, plan.gate_shape, workers)
    free_scores = score_batch(plan.free, 0.0, plan.gate_shape, workers)
    seconds = [t for t, _ in timed]

    def detection(seeds: range, scores: np.ndarray, threshold: float) -> dict:
        return {
            "n": len(seeds),
            "detected": _count_above(scores, threshold),
            "cases": [asdict(c) for c in _case_results(seeds, scores, threshold)],
        }

    return {
        "plan": {
            k: [v.start, v.stop - 1] if isinstance(v, range) else v
            for k, v in plan._asdict().items()
        },
        "striped": detection(plan.striped, striped_scores, plan.gate_threshold),
        "free": {
            "n": len(plan.free),
            "false_alarms": _count_above(free_scores, plan.gate_threshold),
            "max_score": float(free_scores.max()),
        },
        "probe": detection(plan.probe_striped, probe_scores, plan.probe_threshold),
        "timing": {
            "shape": plan.probe_shape,
            "seeds": list(timed_seeds),
            "seconds": seconds,
            "median_s": median(seconds),
            "limit_s": SLOW_TIMING_LIMIT_S,
        },
        "run_info": run_info(workers),
        "wall_clock_s": time.perf_counter() - t_start,
        "loadavg": {"start": load_start, "end": loadavg()},
        "threads": {
            **thread_settings(),
            "note": (
                "test collection imported NumPy before feasibility set these, so BLAS "
                "threading of the in-process timed frames is not pinned (make bench pins it)"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    seed_guard.install()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--skip-probe", action="store_true", help="skip the full-frame probe")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="worker processes (default: three quarters of the CPUs)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="JSON measurement path")
    args = parser.parse_args(argv)

    out = measure_all(args.workers, probe=not args.skip_probe)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
