"""Ticket 07 synthetic calibration driver: the package's stored calibration and its checks.

Imported by the calibration tests; also runs as a script (background, idle machine):

    uv run --locked python tests/threshold_calibration.py --out PATH [--workers N]
    uv run --locked python tests/threshold_calibration.py --clipped [--workers N]

The first form generates the Calibration Set (STRIPE_FREE_CALIBRATION_SEEDS, 400x1600,
typical settings, 30 Spike events per frame, unclipped) inside its one
``seed_guard.calibrating(...)`` block, scores every frame with the full pipeline
(``stripe_free_score``) and writes the Calibration file. Only plan step 5 (W9) and the
re-store procedure after a score-moving change write the package file
``src/denoisifier/stripe_free_calibration.json`` this way.

``--clipped`` is the one-off measurement of plan 2.8 (step 10): False Alarms on
CLIPPED_FREE_EVALUATION_SEEDS clipped at CLIP_LEVEL_FRACTION x each seed's clean
maximum, on the default path, with the exact 95% interval. A measurement, never a
pass/fail, and never tuned on.

The check functions take a plan and return a result dict; the slow modules
(test_slow_calibration.py, test_held_out_calibration.py) build the full plans and assert
through the ``*_problems`` functions, which the fast tiny-plan test also runs.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, NamedTuple

import numpy as np
import scipy
from scipy.stats import beta

import feasibility
import seed_guard
from cases import CASES
from denoisifier import analyse
from denoisifier._calibration import false_alarm_tolerance, rate_interval, threshold_rank
from denoisifier.calibration import (
    DEFAULT_FALSE_ALARM_RATE,
    Calibration,
    stored_calibration,
    stripe_free_score,
)
from denoisifier.synthetic import Emccd, Synthetic, generate
from protected import (
    CALIBRATED_FREE_SEEDS,
    CALIBRATED_STRIPED_SEEDS,
    CALIBRATION_SHAPE,
    CALIBRATION_SPIKES,
    CALIBRATION_TOLERANCE_LEVEL,
    CLIP_LEVEL_FRACTION,
    CLIPPED_FREE_EVALUATION_SEEDS,
    HELD_OUT_OPTION_FRAMES,
    MIN_DETECTION_RATE,
    OTHER_FALSE_ALARM_RATE,
    STRIPE_FREE_CALIBRATION_SEEDS,
    WEAK_DEPTH,
)
from slow_stamp import busy_warning, loadavg

ROOT = feasibility.ROOT
PACKAGE_FILE = ROOT / "src/denoisifier/stripe_free_calibration.json"
HELD_OUT_MEASUREMENT = ROOT / ".gate/held-out-calibration.json"

# Typical settings (ticket 07): scorched Mottle; Emccd(): about 100 photons at the peak,
# EM gain 300, read noise 50 e, CIC 0.005; CALIBRATION_SPIKES Spike events; no clip.
MOTTLE: Literal["scorched"] = "scorched"
NOISE = Emccd()


def settings(shape: tuple[int, int]) -> dict[str, Any]:
    """How the synthetic Calibration Set is made (generation and analysis parameters):
    recorded in the Calibration's ``settings`` and compared by the checks."""
    return {
        "source": "synthetic",
        "shape": list(shape),
        "mottle": MOTTLE,
        "emccd": asdict(NOISE),
        "spikes": CALIBRATION_SPIKES,
        "modulation_depth": 0.0,
        "clip_level": None,
        "period_angle": "cases.CASES[seed % 10] (no effect at modulation_depth 0)",
        "score": "stripe_free_score: analyse(frame, threshold=inf, clip_level=None).score",
    }


def synthetic(
    seed: int, shape: tuple[int, int], depth: float, *, clip_level: float | None = None
) -> Synthetic:
    """One frame at the typical settings: Period and Angle of ``CASES[seed % 10]``,
    CALIBRATION_SPIKES Spike events, clipped at ``clip_level`` when given."""
    case = CASES[seed % len(CASES)]
    return generate(
        seed=seed,
        shape=shape,
        period=case.period,
        angle_deg=case.angle_deg,
        modulation_depth=depth,
        mottle=MOTTLE,
        noise=NOISE,
        spikes=CALIBRATION_SPIKES,
        clip_level=clip_level,
    )


def run_info(workers: int, t_start: float, load_start: str, frames: int) -> dict[str, Any]:
    """Commit, machine, versions, load and wall clock of a run: recorded, never compared."""
    base = feasibility.run_info(workers)
    wall = time.perf_counter() - t_start
    return {
        **{k: base[k] for k in ("commit", "cpu", "logical_cpus", "workers")},
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "loadavg": {"start": load_start, "end": loadavg()},
        "wall_clock_s": wall,
        "seconds_per_frame": wall / max(frames, 1),
    }


def _calibration_job(job: tuple[int, tuple[int, int]]) -> float:
    seed, shape = job
    return stripe_free_score(synthetic(seed, shape, 0.0).frame)


def calibration_from_seeds(
    seeds: Sequence[int], shape: tuple[int, int], workers: int | None = None
) -> Calibration:
    """The core of the calibration routine (no seed-guard block): score each seed's
    Stripe-free frame in the guarded pool and build the Calibration. Ids are
    ``"seed:N"`` in seed order."""
    workers = feasibility.resolve_workers(workers)
    t0, load = time.perf_counter(), loadavg()
    scores = feasibility.run_pool(_calibration_job, [(s, shape) for s in seeds], workers)
    return Calibration.from_scores(
        [f"seed:{s}" for s in seeds],
        scores,
        shape,
        settings=settings(shape),
        run_info=run_info(workers, t0, load, len(seeds)),
    )


def calibrate_synthetic(workers: int | None = None) -> Calibration:
    """The calibration routine on the Calibration Set: the one place its seeds are
    generated (W2). The block covers its generation and scoring only."""
    with seed_guard.calibrating(STRIPE_FREE_CALIBRATION_SEEDS):
        return calibration_from_seeds(STRIPE_FREE_CALIBRATION_SEEDS, CALIBRATION_SHAPE, workers)


# --- Reproduction (AC 7) ---------------------------------------------------------------


def reproduction_check(
    stored: Calibration,
    calibrate: Callable[[], Calibration] = calibrate_synthetic,
    rates: tuple[float, float] = (DEFAULT_FALSE_ALARM_RATE, OTHER_FALSE_ALARM_RATE),
) -> dict[str, Any]:
    """Re-run the calibration routine and compare it with ``stored``: ids, shape,
    JSON-normalised settings (run_info is not compared), every per-seed score
    exactly, and the Thresholds at ``rates``. Asserts nothing."""
    t0 = time.perf_counter()
    fresh = calibrate()
    same_ids = fresh.ids == stored.ids
    differing: list[str] = []
    max_rel = 0.0
    if same_ids:
        for frame_id, a, b in zip(fresh.ids, fresh.scores, stored.scores, strict=True):
            if a != b:
                differing.append(frame_id)
                max_rel = max(max_rel, abs(a - b) / max(abs(a), abs(b)))
    return {
        "n": len(fresh.scores),
        "ids_equal": same_ids,
        "shape_equal": fresh.shape == stored.shape,
        "settings_equal": fresh.settings == stored.settings,
        "n_differing": len(differing) if same_ids else None,
        "differing": differing,
        "max_rel_diff": max_rel,
        "rates": list(rates),
        "thresholds": [fresh.threshold(r) for r in rates],
        "stored_thresholds": [stored.threshold(r) for r in rates],
        "zero_scores": sum(s == 0.0 for s in fresh.scores),
        "wall_clock_s": time.perf_counter() - t0,
        "run_info": dict(fresh.run_info),
    }


def reproduction_problems(
    result: dict[str, Any], stored_threshold: float, stored_other_threshold: float
) -> list[str]:
    """AC 7's failures: one message each, empty when the routine reproduces."""
    advice = (
        "Follow the re-store procedure (CLAUDE.md, Gates) only when the change was meant "
        "to move scores; an unexpected change is a finding. Never edit this check."
    )
    problems = []
    if not result["ids_equal"]:
        problems.append(f"the re-run's frame ids differ from the stored file's. {advice}")
    if not result["shape_equal"]:
        problems.append(f"the re-run's shape differs from the stored file's. {advice}")
    if not result["settings_equal"]:
        problems.append(f"the re-run's settings differ from the stored file's. {advice}")
    if result["n_differing"]:
        first = ", ".join(result["differing"][:5])
        problems.append(
            f"{result['n_differing']} of {result['n']} per-seed scores differ (first: {first});"
            f" largest relative difference {result['max_rel_diff']:.3g} (tiny on every seed:"
            f" a platform difference; tens of points: a detector change). {advice}"
        )
    want = [stored_threshold, stored_other_threshold]
    for rate, got, expected in zip(result["rates"], result["thresholds"], want, strict=True):
        if got != expected:
            problems.append(
                f"the re-run's threshold at rate {rate} is {got!r}, the protected stored"
                f" threshold is {expected!r}. {advice}"
            )
    return problems


# --- Held-out evaluation (AC 2a, 2b, 3) -----------------------------------------------


def _evaluate_job(
    job: tuple[int, tuple[int, int], float, float | None, float | None, Calibration | None],
) -> dict[str, Any]:
    seed, shape, depth, clip_fraction, option_rate, calibration = job
    clip_level = None
    if clip_fraction is not None:
        clip_level = clip_fraction * float(synthetic(seed, shape, depth).clean.max())
    frame = synthetic(seed, shape, depth, clip_level=clip_level).frame
    kwargs: dict[str, Any] = {} if calibration is None else {"calibration": calibration}
    report = analyse(frame, **kwargs)
    row: dict[str, Any] = {
        "seed": seed,
        "score": report.score,
        "striped": report.striped,
        "threshold": report.threshold,
    }
    if option_rate is not None:
        option = analyse(frame, false_alarm_rate=option_rate, **kwargs)
        row["option"] = {
            "rate": option_rate,
            "score": option.score,
            "striped": option.striped,
            "threshold": option.threshold,
        }
    return row


def evaluate(
    seeds: Sequence[int],
    *,
    shape: tuple[int, int],
    depth: float,
    clip_fraction: float | None = None,
    option_rate: float | None = None,
    option_frames: int = 0,
    calibration: Calibration | None = None,
    workers: int | None = None,
) -> list[dict[str, Any]]:
    """Per seed, the default-path Report's score, verdict and threshold of
    ``analyse(frame)``, in the guarded pool. ``calibration`` is passed to analyse only
    when given (the gate passes None: the stored calibration). With ``option_rate``, the
    first ``option_frames`` seeds are also analysed with that false-alarm rate. With
    ``clip_fraction``, each frame is clipped at that fraction of its clean maximum."""
    jobs = [
        (s, shape, depth, clip_fraction, option_rate if i < option_frames else None, calibration)
        for i, s in enumerate(seeds)
    ]
    return feasibility.run_pool(_evaluate_job, jobs, workers)


class HeldOutPlan(NamedTuple):
    """The held-out evaluation: Stripe-free ``free`` and m = ``depth`` ``striped`` frames
    (CASES[seed % 10]) at ``shape``, on the default path."""

    shape: tuple[int, int]
    free: range
    striped: range
    depth: float
    other_rate: float
    option_frames: int
    level: float
    min_detection_rate: float


HELD_OUT = HeldOutPlan(
    shape=CALIBRATION_SHAPE,
    free=CALIBRATED_FREE_SEEDS,
    striped=CALIBRATED_STRIPED_SEEDS,
    depth=WEAK_DEPTH,
    other_rate=OTHER_FALSE_ALARM_RATE,
    option_frames=HELD_OUT_OPTION_FRAMES,
    level=CALIBRATION_TOLERANCE_LEVEL,
    min_detection_rate=MIN_DETECTION_RATE,
)


def held_out_free(
    plan: HeldOutPlan, calibration: Calibration | None = None, workers: int | None = None
) -> dict[str, Any]:
    """AC 2a and 2b on the Stripe-free held-out frames. Asserts nothing."""
    t0, load = time.perf_counter(), loadavg()
    cal = stored_calibration() if calibration is None else calibration
    rows = evaluate(
        plan.free,
        shape=plan.shape,
        depth=0.0,
        option_rate=plan.other_rate,
        option_frames=plan.option_frames,
        calibration=calibration,
        workers=workers,
    )
    n_cal, big_n = len(cal.scores), len(rows)
    rate = DEFAULT_FALSE_ALARM_RATE
    false_alarms = sum(r["striped"] for r in rows)
    k = threshold_rank(n_cal, rate)
    post = beta(k + false_alarms, n_cal + 1 - k + big_n - false_alarms)
    t_other = cal.threshold(plan.other_rate)
    options = [{**r["option"], "seed": r["seed"], "default": r} for r in rows if "option" in r]
    mismatches = [
        o["seed"]
        for o in options
        if o["score"] != o["default"]["score"]
        or o["threshold"] != t_other
        or o["striped"] != (o["default"]["score"] > t_other)
    ]
    scores = [r["score"] for r in rows]
    return {
        "n": big_n,
        "seeds": [plan.free.start, plan.free.stop - 1],
        "shape": list(plan.shape),
        "calibration_n": n_cal,
        "rate": rate,
        "threshold": cal.threshold(rate),
        "thresholds_seen": sorted({r["threshold"] for r in rows}),
        "false_alarms": false_alarms,
        "tolerance": list(false_alarm_tolerance(n_cal, big_n, rate, plan.level)),
        "posterior_95": [float(post.ppf(0.025)), float(post.ppf(0.975))],
        "other": {
            "rate": plan.other_rate,
            "threshold": t_other,
            "count": sum(s > t_other for s in scores),
            "tolerance": list(false_alarm_tolerance(n_cal, big_n, plan.other_rate, plan.level)),
        },
        "option_frames": [{k: v for k, v in o.items() if k != "default"} for o in options],
        "option_mismatches": mismatches,
        "zero_scores": sum(s == 0.0 for s in scores),
        "max_score": max(scores),
        "scores": scores,
        "wall_clock_s": time.perf_counter() - t0,
        "loadavg": {"start": load, "end": loadavg()},
    }


def held_out_striped(
    plan: HeldOutPlan, calibration: Calibration | None = None, workers: int | None = None
) -> dict[str, Any]:
    """AC 3 on the striped held-out frames: pooled detections and a per-case breakdown
    (reported, not asserted). Asserts nothing."""
    t0, load = time.perf_counter(), loadavg()
    rows = evaluate(
        plan.striped, shape=plan.shape, depth=plan.depth, calibration=calibration, workers=workers
    )
    cases = []
    for case in CASES:
        hit = [r for r in rows if CASES[r["seed"] % len(CASES)] == case]
        if hit:
            cases.append(
                {
                    "period": case.period,
                    "angle_deg": case.angle_deg,
                    "detected": sum(r["striped"] for r in hit),
                    "n": len(hit),
                    "min_score": min(r["score"] for r in hit),
                }
            )
    return {
        "n": len(rows),
        "seeds": [plan.striped.start, plan.striped.stop - 1],
        "shape": list(plan.shape),
        "depth": plan.depth,
        "thresholds_seen": sorted({r["threshold"] for r in rows}),
        "detected": sum(r["striped"] for r in rows),
        "min_detected": math.ceil(plan.min_detection_rate * len(rows) - 1e-9),
        "cases": cases,
        "wall_clock_s": time.perf_counter() - t0,
        "loadavg": {"start": load, "end": loadavg()},
    }


def record(path: Path, part: str, result: dict[str, Any], *, fresh: bool = False) -> None:
    """Write ``result`` under ``part`` in the measurement JSON at ``path`` (a fresh
    file when ``fresh``, else merged with what is there)."""
    doc: dict[str, Any] = {}
    if not fresh and path.exists():
        doc = json.loads(path.read_text())
    doc[part] = result
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def held_out_check(
    plan: HeldOutPlan,
    calibration: Calibration | None = None,
    workers: int | None = None,
    out: Path | None = None,
) -> dict[str, Any]:
    """Both held-out evaluations, written to ``out`` when given. Asserts nothing."""
    result = {
        "free": held_out_free(plan, calibration, workers),
        "striped": held_out_striped(plan, calibration, workers),
    }
    if out is not None:
        record(out, "free", result["free"], fresh=True)
        record(out, "striped", result["striped"])
    return result


def false_alarm_problems(free: dict[str, Any], stored_threshold: float) -> list[str]:
    """AC 2a's failures: the default path must use the stored threshold, and the False
    Alarm count must lie in its tolerance."""
    problems = []
    if free["thresholds_seen"] != [stored_threshold]:
        problems.append(
            f"the default path used thresholds {free['thresholds_seen']}, not the stored"
            f" {stored_threshold!r}"
        )
    lo, hi = free["tolerance"]
    if not lo <= free["false_alarms"] <= hi:
        problems.append(
            f"{free['false_alarms']}/{free['n']} False Alarms at the default rate"
            f" {free['rate']}, outside the tolerance {lo}-{hi}; posterior 95%"
            f" {free['posterior_95']}. A finding (plan section 13, rule 1): no re-seeding,"
            " no change of sizes, level or tolerance"
        )
    return problems


def other_rate_problems(free: dict[str, Any], stored_other_threshold: float) -> list[str]:
    """AC 2b's failures: the count above the other rate's stored threshold in its
    tolerance, and the option path agreeing with the counted verdicts."""
    other = free["other"]
    problems = []
    if other["threshold"] != stored_other_threshold:
        problems.append(
            f"the threshold at rate {other['rate']} is {other['threshold']!r}, not the stored"
            f" {stored_other_threshold!r}"
        )
    lo, hi = other["tolerance"]
    if not lo <= other["count"] <= hi:
        problems.append(
            f"{other['count']}/{free['n']} scores above the rate-{other['rate']} threshold,"
            f" outside the tolerance {lo}-{hi}. A finding (plan section 13, rule 1)"
        )
    if free["option_mismatches"]:
        problems.append(
            f"analyse(frame, false_alarm_rate={other['rate']}) disagrees with the counted"
            f" score, threshold or verdict on option frames {free['option_mismatches']}"
        )
    return problems


def detection_problems(striped: dict[str, Any]) -> list[str]:
    """AC 3's failure: fewer than ``min_detected`` of the striped frames detected, with
    the per-case breakdown."""
    if striped["detected"] >= striped["min_detected"]:
        return []
    cases = ", ".join(
        f"{c['period']}px/{c['angle_deg']}deg {c['detected']}/{c['n']} (min {c['min_score']:.1f})"
        for c in striped["cases"]
    )
    return [
        f"{striped['detected']}/{striped['n']} detected at m = {striped['depth']} at the"
        f" default rate (need {striped['min_detected']}): {cases}. A finding (plan section"
        " 13, rule 1)"
    ]


# --- The one-off clipped measurement (plan 2.8, step 10) --------------------------------


def clipped_measurement(workers: int | None = None) -> dict[str, Any]:
    """False Alarms on CLIPPED_FREE_EVALUATION_SEEDS clipped at CLIP_LEVEL_FRACTION x
    each seed's clean maximum, default path: count and exact 95% interval."""
    workers = feasibility.resolve_workers(workers)
    t0, load = time.perf_counter(), loadavg()
    seeds = CLIPPED_FREE_EVALUATION_SEEDS
    rows = evaluate(
        seeds,
        shape=CALIBRATION_SHAPE,
        depth=0.0,
        clip_fraction=CLIP_LEVEL_FRACTION,
        workers=workers,
    )
    false_alarms = sum(r["striped"] for r in rows)
    return {
        "n": len(rows),
        "seeds": [seeds.start, seeds.stop - 1],
        "clip_level_fraction": CLIP_LEVEL_FRACTION,
        "threshold": stored_calibration().threshold(DEFAULT_FALSE_ALARM_RATE),
        "thresholds_seen": sorted({r["threshold"] for r in rows}),
        "false_alarms": false_alarms,
        "clopper_pearson_95": list(rate_interval(false_alarms, len(rows))),
        "scores": [r["score"] for r in rows],
        "run_info": run_info(workers, t0, load, len(rows)),
    }


def main(argv: list[str] | None = None) -> int:
    seed_guard.install()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, help="write the Calibration JSON here")
    parser.add_argument(
        "--clipped",
        action="store_true",
        help="the one-off clipped measurement (plan step 10) instead of the calibration",
    )
    parser.add_argument(
        "--workers", type=int, default=None, help="worker processes (default: 3/4 of the CPUs)"
    )
    args = parser.parse_args(argv)
    if args.clipped == (args.out is not None):
        parser.error("give exactly one of --out and --clipped")
    warning = busy_warning("threshold_calibration", loadavg())
    if warning is not None:
        print(warning, flush=True)
    if args.clipped:
        result = clipped_measurement(args.workers)
        out = ROOT / ".scratch/stripe-detector/handoffs/07-clipped-measurement.json"
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(
            f"clipped: {result['false_alarms']}/{result['n']} False Alarms at"
            f" {result['threshold']}, exact 95% {result['clopper_pearson_95']}; wrote {out}"
        )
        return 0
    cal = calibrate_synthetic(args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(cal.to_json())
    scores = np.array(cal.scores)
    t1 = cal.threshold(DEFAULT_FALSE_ALARM_RATE)
    print(
        f"calibration: n = {len(scores)}, threshold 1% = {t1!r},"
        f" 5% = {cal.threshold(OTHER_FALSE_ALARM_RATE)!r}, zeros {int((scores == 0).sum())},"
        f" top 20 {sorted(scores.tolist(), reverse=True)[:20]},"
        f" {cal.run_info['seconds_per_frame']:.2f} s/frame; wrote {args.out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
