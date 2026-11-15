"""Ticket 11 break and Fork calibration driver: the package's stored break and Fork
calibration and its checks (plan .scratch/stripe-detector/handoffs/11-plan.md, section 5).

Imported by the break and Fork calibration tests; also runs as a script (background, idle
machine, about 13 min):

    uv run --locked python tests/break_fork_calibration.py --out PATH [--workers N]

It generates the Calibration Set (BREAK_FORK_FREE_CALIBRATION_SEEDS: 400x1600 full-frame
stripes at depth BREAK_FORK_CALIBRATION_DEPTH, CASES[seed % 10], the ticket-07 typical
settings with 30 Spike events, unclipped, no Phase Breaks, no Forks) inside its one
``seed_guard.calibrating(...)`` block, computes each frame's break and Fork evidence
(``analysis._break_fork_evidence``: S_b, S_f) and writes the file. Every calibration frame
must be Striped at the stored stripe Threshold; the core refuses one that is not. Only
ticket 11 step 6 and the re-store procedure (CLAUDE.md, Gates) write the package file
``src/denoisifier/break_fork_free_calibration.json`` this way.

The check functions take a plan and return a result dict; the slow modules
(test_slow_break_fork_calibration.py, test_held_out_break_fork.py) build the full plans and
assert through the ``*_problems`` functions, which the fast tiny-plan test also runs.
"""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any, NamedTuple
from unittest import mock

import numpy as np
from scipy.stats import betabinom

import feasibility
import seed_guard
import threshold_calibration as tc
from breaks import ac2_line, break_region_case, region_breaks
from cases import CASES
from denoisifier import BinFactors, analyse, analysis
from denoisifier._calibration import rate_interval, threshold_rank
from denoisifier._local_phase import _BREAK_MIN_EVIDENCE, _FORK_MIN_EVIDENCE
from denoisifier.calibration import (
    _BREAK_FORK_EVIDENCE_VERSION,
    _BreakForkCalibration,
    _BreakForkThresholds,
    stored_calibration,
)
from denoisifier.report import Report
from denoisifier.synthetic import Synthetic
from forks import ac2_case
from protected import (
    BREAK_FORK_CALIBRATION_DEPTH,
    BREAK_FORK_CALIBRATION_SHAPE,
    BREAK_FORK_CASE_ALARM_FRAMES,
    BREAK_FORK_DETECTION_BREAK_FRAMES,
    BREAK_FORK_DETECTION_FORK_FRAMES,
    BREAK_FORK_DETECTION_HELD_OUT_SEEDS,
    BREAK_FORK_FALSE_ALARM_RATE,
    BREAK_FORK_FREE_CALIBRATION_SEEDS,
    BREAK_FORK_FREE_HELD_OUT_SEEDS,
    BREAK_FORK_MAX_FAKES,
    BREAK_FORK_MIN_DETECTION_RATE,
    CALIBRATION_SPIKES,
)
from regions import truth_pixels
from slow_stamp import busy_warning, loadavg
from truth_match import break_problems, fork_problems

ROOT = feasibility.ROOT
PACKAGE_FILE = ROOT / "src/denoisifier/break_fork_free_calibration.json"
HELD_OUT_MEASUREMENT = ROOT / ".gate/held-out-break-fork.json"
ONE_BY_ONE = BinFactors()


def settings(shape: tuple[int, int], depth: float = BREAK_FORK_CALIBRATION_DEPTH) -> dict[str, Any]:
    """How the Calibration Set is made and read: recorded in the calibration's ``settings``
    and compared by the checks. ``stripe_calibration_digest`` is the stored stripe
    calibration's digest, whose 1 % Threshold decides the regions the finders see."""
    return {
        "source": "synthetic",
        "shape": list(shape),
        "mottle": tc.MOTTLE,
        "emccd": asdict(tc.NOISE),
        "spikes": CALIBRATION_SPIKES,
        "modulation_depth": depth,
        "clip_level": None,
        "period_angle": "cases.CASES[seed % 10], full-frame stripes",
        "phase_breaks": 0,
        "forks": 0,
        "evidence": _BREAK_FORK_EVIDENCE_VERSION,
        "scalars": "analysis._break_fork_evidence(frame): stored 1 % stripe threshold, unbinned",
        "floors": {"breaks": _BREAK_MIN_EVIDENCE, "forks": _FORK_MIN_EVIDENCE},
        "stripe_calibration_digest": stored_calibration().digest(),
    }


def _evidence_job(job: tuple[int, tuple[int, int], float]) -> tuple[float, float, bool]:
    seed, shape, depth = job
    ev = analysis._break_fork_evidence(tc.synthetic(seed, shape, depth).frame)
    return ev.breaks, ev.forks, ev.striped


def break_fork_calibration_from_seeds(
    seeds: Sequence[int],
    shape: tuple[int, int],
    workers: int | None = None,
    *,
    depth: float = BREAK_FORK_CALIBRATION_DEPTH,
) -> _BreakForkCalibration:
    """The core of the calibration routine (no seed-guard block): each seed's evidence in
    the guarded pool. Ids are ``"seed:N"`` in seed order. Raises ValueError when a frame is
    not Striped (a frame with no reported region carries no evidence: the recipe is wrong,
    and its S = 0 would silently loosen the thresholds)."""
    workers = feasibility.resolve_workers(workers)
    t0, load = time.perf_counter(), loadavg()
    rows = feasibility.run_pool(_evidence_job, [(s, shape, depth) for s in seeds], workers)
    flat = [s for s, (_, _, striped) in zip(seeds, rows, strict=True) if not striped]
    if flat:
        raise ValueError(
            f"{len(flat)} of {len(rows)} calibration frames are not Striped at the stored"
            f" stripe Threshold (seeds {flat[:10]}): every calibration frame must be"
        )
    return _BreakForkCalibration.from_evidence(
        [f"seed:{s}" for s in seeds],
        [b for b, _, _ in rows],
        [f for _, f, _ in rows],
        shape,
        settings=settings(shape, depth),
        run_info=tc.run_info(workers, t0, load, len(seeds)),
    )


def calibrate_break_forks(
    workers: int | None = None, *, prefix: int | None = None
) -> _BreakForkCalibration:
    """The calibration routine on the Calibration Set (its first ``prefix`` seeds when
    given): the one place its seeds are generated. The block covers generation and the
    evidence pass only."""
    with seed_guard.calibrating(BREAK_FORK_FREE_CALIBRATION_SEEDS):
        seeds = BREAK_FORK_FREE_CALIBRATION_SEEDS
        if prefix is not None:
            seeds = seeds[:prefix]
        return break_fork_calibration_from_seeds(seeds, BREAK_FORK_CALIBRATION_SHAPE, workers)


# --- Reproduction (AC 1) ---------------------------------------------------------------


def reproduction_check(
    stored: _BreakForkCalibration,
    calibrate: Callable[[], _BreakForkCalibration],
    rate: float = BREAK_FORK_FALSE_ALARM_RATE,
) -> dict[str, Any]:
    """Re-run the calibration routine (all frames, or a prefix of them) and compare it
    with the first frames of ``stored``: ids, shape, JSON-normalised settings (run_info is
    not compared), every per-frame (S_b, S_f) exactly. ``thresholds`` are those at
    ``rate`` of ``stored`` with the re-run frames put in place of their stored ones (the
    stored thresholds when everything reproduces). Asserts nothing."""
    t0 = time.perf_counter()
    fresh = calibrate()
    m = len(fresh.ids)
    same_ids = fresh.ids == stored.ids[:m]
    differing: list[str] = []
    if same_ids:
        for i, frame_id in enumerate(fresh.ids):
            got = (fresh.break_evidence[i], fresh.fork_evidence[i])
            want = (stored.break_evidence[i], stored.fork_evidence[i])
            if got != want:
                differing.append(f"{frame_id} {got} != stored {want}")
    spliced = None
    if same_ids:
        spliced = _BreakForkCalibration.from_evidence(
            stored.ids,
            fresh.break_evidence + stored.break_evidence[m:],
            fresh.fork_evidence + stored.fork_evidence[m:],
            stored.shape,
            settings=stored.settings,
        )
    return {
        "n": m,
        "stored_n": len(stored.ids),
        "ids_equal": same_ids,
        "shape_equal": fresh.shape == stored.shape,
        "settings_equal": fresh.settings == stored.settings,
        "n_differing": len(differing) if same_ids else None,
        "differing": differing,
        "rate": rate,
        "thresholds": None if spliced is None else asdict(spliced.thresholds(rate)),
        "stored_thresholds": asdict(stored.thresholds(rate)),
        "above_floor": {
            "breaks": sum(b > _BREAK_MIN_EVIDENCE for b in fresh.break_evidence),
            "forks": sum(f > _FORK_MIN_EVIDENCE for f in fresh.fork_evidence),
        },
        "wall_clock_s": time.perf_counter() - t0,
        "run_info": dict(fresh.run_info),
    }


def reproduction_problems(
    result: dict[str, Any], stored_break_threshold: float, stored_fork_threshold: float
) -> list[str]:
    """AC 1's failures: one message each, empty when the routine reproduces."""
    advice = (
        "After a change to the stripe calibration, _local_phase.py, the break pass, the Fork"
        " searches or the shared front half, follow the re-store procedure (CLAUDE.md, Gates);"
        " an unexpected change is a finding. Never edit this check."
    )
    problems = []
    if not result["ids_equal"]:
        problems.append(f"the re-run's frame ids differ from the stored file's. {advice}")
    if not result["shape_equal"]:
        problems.append(f"the re-run's shape differs from the stored file's. {advice}")
    if not result["settings_equal"]:
        problems.append(f"the re-run's settings differ from the stored file's. {advice}")
    if result["n_differing"]:
        first = "; ".join(result["differing"][:5])
        problems.append(
            f"{result['n_differing']} of {result['n']} per-frame (S_b, S_f) differ (first:"
            f" {first}). {advice}"
        )
    want = {"breaks": stored_break_threshold, "forks": stored_fork_threshold}
    for name, label in (("thresholds", "re-run's"), ("stored_thresholds", "stored file's")):
        got = result[name]
        if got is not None and got != want:
            problems.append(
                f"the {label} thresholds at rate {result['rate']} are {got}, the protected"
                f" ones are {want}. {advice}"
            )
    return problems


# --- Held-out fakes (AC 2) -------------------------------------------------------------


class FakesPlan(NamedTuple):
    """Break- and Fork-free striped frames of the calibration recipe at ``shape``."""

    shape: tuple[int, int]
    seeds: range
    depth: float
    max_fakes: int
    case_alarm: int


HELD_OUT_FAKES = FakesPlan(
    shape=BREAK_FORK_CALIBRATION_SHAPE,
    seeds=BREAK_FORK_FREE_HELD_OUT_SEEDS,
    depth=BREAK_FORK_CALIBRATION_DEPTH,
    max_fakes=BREAK_FORK_MAX_FAKES,
    case_alarm=BREAK_FORK_CASE_ALARM_FRAMES,
)


def reported_with_evidence(frame: np.ndarray) -> tuple[Report, list[float], list[float]]:
    """``analyse(frame)`` on the default path, with each reported Phase Break's and Fork's
    own evidence E, in the Report's order. The Report carries no E, so this wraps the two
    private steps that turn found breaks and Forks into reported ones; their output is
    unchanged."""
    real_breaks, real_forks = analysis._reported_breaks, analysis._reported_forks
    evidence: dict[int, tuple[object, float]] = {}

    def breaks(label: int, pixels: np.ndarray, found: list[Any], bins: BinFactors) -> list[Any]:
        out = []
        for b in found:  # one at a time: a break with no pixel on its line is not reported
            for reported in real_breaks(label, pixels, [b], bins):
                evidence[id(reported)] = (reported, b.evidence)
                out.append(reported)
        return out

    def forks(label: int, found: list[Any], bins: BinFactors) -> list[Any]:
        out = real_forks(label, found, bins)
        for reported, f in zip(out, found, strict=True):
            evidence[id(reported)] = (reported, f.evidence)
        return out

    with (
        mock.patch.object(analysis, "_reported_breaks", breaks),
        mock.patch.object(analysis, "_reported_forks", forks),
    ):
        report = analyse(frame)
    return (
        report,
        [evidence[id(b)][1] for b in report.phase_breaks],
        [evidence[id(f)][1] for f in report.forks],
    )


def fake_entries(
    seed: int, report: Report, break_e: list[float], fork_e: list[float], truth: np.ndarray
) -> list[dict[str, Any]]:
    """One record per reported break and Fork of a break- and Fork-free frame (each a fake):
    its own E and whether its reported region overlaps no pixel of ``truth`` (the truth
    regions' pixels)."""
    case = CASES[seed % len(CASES)]
    out = []
    for kind, found, evidence in (
        ("breaks", report.phase_breaks, break_e),
        ("forks", report.forks, fork_e),
    ):
        for item, e in zip(found, evidence, strict=True):
            region = report.labels == item.region
            out.append(
                {
                    "seed": seed,
                    "period": case.period,
                    "angle_deg": case.angle_deg,
                    "kind": kind,
                    "region": int(item.region),
                    "evidence": float(e),
                    "in_fake_region": not bool((region & truth).any()),
                }
            )
    return out


def _fakes_job(job: tuple[int, tuple[int, int], float]) -> dict[str, Any]:
    seed, shape, depth = job
    s = tc.synthetic(seed, shape, depth)
    report, break_e, fork_e = reported_with_evidence(s.frame)
    ev = analysis._break_fork_evidence(s.frame)
    truth = np.logical_or.reduce([truth_pixels(r) for r in s.truth.regions])
    return {
        "seed": seed,
        "striped": report.striped,
        "evidence_striped": ev.striped,
        "breaks": len(report.phase_breaks),
        "forks": len(report.forks),
        "s_b": ev.breaks,
        "s_f": ev.forks,
        "fakes": fake_entries(seed, report, break_e, fork_e, truth),
    }


def implication_violations(row: dict[str, Any], thresholds: _BreakForkThresholds) -> list[str]:
    """Plan section 2 at scale, on one frame's report and evidence: a reported break =>
    S_b > T_b; a reported Fork => S_f > T_f or a found break (S_b > T_b); S_b <= T_b and
    S_f <= T_f => no break and no Fork."""
    found_break = row["s_b"] > thresholds.breaks
    out = []
    if row["breaks"] and not found_break:
        out.append(f"seed {row['seed']}: a reported break with S_b {row['s_b']} <= T_b")
    if row["forks"] and not (row["s_f"] > thresholds.forks or found_break):
        out.append(f"seed {row['seed']}: a reported Fork with S_f {row['s_f']} <= T_f, no break")
    return out


def case_summary(rows: list[dict[str, Any]], case_alarm: int) -> list[dict[str, Any]]:
    """Per case (``CASES[seed % 10]``) with frames: frames, fakes, frames with a fake, and
    the alarm flag, set when the case has at least ``case_alarm`` fakes (plan section 6;
    fakes >= frames with a fake, so stricter than a frame count). Recorded, not asserted."""
    out = []
    for case in CASES:
        hit = [r for r in rows if CASES[r["seed"] % len(CASES)] == case]
        if hit:
            fakes = sum(r["breaks"] + r["forks"] for r in hit)
            out.append(
                {
                    "period": case.period,
                    "angle_deg": case.angle_deg,
                    "n": len(hit),
                    "fakes": fakes,
                    "frames_with_fakes": sum(1 for r in hit if r["breaks"] or r["forks"]),
                    "alarm": fakes >= case_alarm,
                }
            )
    return out


def held_out_fakes(
    plan: FakesPlan,
    workers: int | None = None,
    thresholds: Callable[[], _BreakForkThresholds] | None = None,
) -> dict[str, Any]:
    """AC 2 on the held-out break- and Fork-free striped frames, default path. Per frame the
    reported breaks and Forks and the evidence; the total count, frames with a fake and the
    exact (Clopper-Pearson) 95 % upper limit of their rate, per case, every fake and the
    implication check at scale. ``thresholds`` gives the default-path thresholds (default:
    the stored calibration's at the default rate). Asserts nothing."""
    t0, load = time.perf_counter(), loadavg()
    used = (thresholds or (lambda: analysis._resolve_break_fork_thresholds(None)))()
    rows = feasibility.run_pool(
        _fakes_job, [(s, plan.shape, plan.depth) for s in plan.seeds], workers
    )
    fakes = [f for r in rows for f in r["fakes"]]
    violations = [v for r in rows for v in implication_violations(r, used)]
    with_fakes = [r for r in rows if r["breaks"] or r["forks"]]
    cases = case_summary(rows, plan.case_alarm)
    n = len(rows)
    return {
        "n": n,
        "seeds": [plan.seeds.start, plan.seeds.stop - 1],
        "shape": list(plan.shape),
        "depth": plan.depth,
        "thresholds": asdict(used),
        "not_striped": [r["seed"] for r in rows if not r["striped"]],
        "evidence_disagrees": [r["seed"] for r in rows if r["striped"] != r["evidence_striped"]],
        "count": sum(r["breaks"] + r["forks"] for r in rows),
        "breaks": sum(r["breaks"] for r in rows),
        "forks": sum(r["forks"] for r in rows),
        "max_fakes": plan.max_fakes,
        "frames_with_fakes": len(with_fakes),
        "frames_with_fakes_upper_95": rate_interval(len(with_fakes), n)[1] if n else None,
        "cases": cases,
        "alarm_cases": [f"{c['period']}px/{c['angle_deg']}deg" for c in cases if c["alarm"]],
        "fakes": fakes,
        "implication_violations": violations,
        "above_thresholds": {
            "breaks": sum(r["s_b"] > used.breaks for r in rows),
            "forks": sum(r["s_f"] > used.forks for r in rows),
        },
        "wall_clock_s": time.perf_counter() - t0,
        "loadavg": {"start": load, "end": loadavg()},
    }


def fake_problems(result: dict[str, Any], stored: _BreakForkThresholds) -> list[str]:
    """AC 2's failures: the default path must use the stored thresholds, every frame must be
    Striped, the implications must hold, and the total count must be at most ``max_fakes``.
    A red is a finding (plan section 9): no threshold, floor, recipe or seed is edited."""
    finding = "A finding for the orchestrator (plan section 9); a second look uses the _2 seeds"
    problems = []
    if result["thresholds"] != asdict(stored):
        problems.append(
            f"the default path used thresholds {result['thresholds']}, not the stored {stored}"
        )
    if result["not_striped"]:
        problems.append(
            f"{len(result['not_striped'])} held-out frames are not Striped (first:"
            f" {result['not_striped'][:10]}). {finding}"
        )
    if result["evidence_disagrees"]:
        problems.append(
            f"analyse and the evidence pass disagree on Striped for seeds"
            f" {result['evidence_disagrees'][:10]}"
        )
    for v in result["implication_violations"][:10]:
        problems.append(f"implication violated: {v}")
    if result["count"] > result["max_fakes"]:
        problems.append(
            f"{result['count']} fake breaks and Forks ({result['breaks']}, {result['forks']}) on"
            f" {result['frames_with_fakes']} of {result['n']} frames, above {result['max_fakes']}."
            f" {finding}"
        )
    return problems


# --- Held-out detection (AC 3(c)) -------------------------------------------------------


class DetectionPlan(NamedTuple):
    """09 AC 2 break frames and 10 AC 2 Fork frames (512x512 regions, typical noise)."""

    breaks: range
    forks: range
    min_detection_rate: float


HELD_OUT_DETECTION = DetectionPlan(
    breaks=BREAK_FORK_DETECTION_HELD_OUT_SEEDS[:BREAK_FORK_DETECTION_BREAK_FRAMES],
    forks=BREAK_FORK_DETECTION_HELD_OUT_SEEDS[
        BREAK_FORK_DETECTION_BREAK_FRAMES : BREAK_FORK_DETECTION_BREAK_FRAMES
        + BREAK_FORK_DETECTION_FORK_FRAMES
    ],
    min_detection_rate=BREAK_FORK_MIN_DETECTION_RATE,
)


def _floor_calibration() -> _BreakForkCalibration:
    """A calibration whose thresholds are the floors at every valid rate (all evidence 0)."""
    n = len(BREAK_FORK_FREE_CALIBRATION_SEEDS)
    zeros = [0.0] * n
    return _BreakForkCalibration.from_evidence(
        [f"floor:{i}" for i in range(n)], zeros, zeros, BREAK_FORK_CALIBRATION_SHAPE
    )


def _break_found(s: Synthetic, report: Any) -> bool:
    """09's AC 2 rule (test_analyse._assert_region_break_found): in the reported region
    holding most of the truth region, exactly one break, and it matches the truth."""
    (line,) = s.truth.phase_breaks
    (region,) = s.truth.regions
    mask = truth_pixels(region)
    if not report.regions:
        return False
    label = max(report.regions, key=lambda r: (mask & (report.labels == r.label)).sum()).label
    found = region_breaks(report, label)
    return len(found) == 1 and not break_problems(
        found[0], line, mask, mask, region.period, ONE_BY_ONE
    )


def _fork_found(s: Synthetic, report: Any) -> bool:
    """10's AC 2 rule (test_forks_are_found_with_their_direction): the forks match the
    truth, no extras, and no break is reported."""
    period = s.truth.regions[0].period
    return not fork_problems(report.forks, s.truth.forks, period, ONE_BY_ONE) and (
        report.phase_breaks == ()
    )


def _detection_job(job: tuple[str, int]) -> dict[str, Any]:
    kind, seed = job
    if kind == "breaks":
        line_angle, jump = ac2_line(seed)
        s, report = break_region_case(seed, jump, line_angle)
        found = _break_found
        meta = {"jump": jump, "line_angle_deg": line_angle}
    else:
        s, report = ac2_case(seed)
        found = _fork_found
        meta = {}
    with mock.patch.object(analysis, "_stored_break_fork_calibration", _floor_calibration):
        floor_report = analyse(s.frame)
    case = CASES[seed % len(CASES)]
    return {
        "kind": kind,
        "seed": seed,
        "period": case.period,
        "angle_deg": case.angle_deg,
        **meta,
        "found": found(s, report),
        "found_at_floors": found(s, floor_report),
    }


def held_out_detection(plan: DetectionPlan, workers: int | None = None) -> dict[str, Any]:
    """AC 3(c): per kind, the frames whose true break or Fork is found on the default path
    (the stored thresholds), the pooled count against ``min_detection_rate``, and the paired
    count of those found at the floors but lost at the stored thresholds; per-case outcomes
    recorded. Asserts nothing."""
    t0, load = time.perf_counter(), loadavg()
    jobs = [("breaks", s) for s in plan.breaks] + [("forks", s) for s in plan.forks]
    rows = feasibility.run_pool(_detection_job, jobs, workers)
    out: dict[str, Any] = {}
    for kind in ("breaks", "forks"):
        hit = [r for r in rows if r["kind"] == kind]
        per_case = Counter((r["period"], r["angle_deg"]) for r in hit if not r["found"])
        out[kind] = {
            "n": len(hit),
            "found": sum(r["found"] for r in hit),
            "found_at_floors": sum(r["found_at_floors"] for r in hit),
            "min_found": math.ceil(plan.min_detection_rate * len(hit) - 1e-9),
            "lost_by_calibration": [
                r["seed"] for r in hit if r["found_at_floors"] and not r["found"]
            ],
            "missed": [r for r in hit if not r["found"]],
            "missed_per_case": [
                {"period": p, "angle_deg": a, "missed": c} for (p, a), c in sorted(per_case.items())
            ],
        }
    out["wall_clock_s"] = time.perf_counter() - t0
    out["loadavg"] = {"start": load, "end": loadavg()}
    return out


def detection_problems(result: dict[str, Any], kind: str) -> list[str]:
    """AC 3(c)'s failures for ``kind`` ("breaks" or "forks"): fewer than ``min_found`` found,
    or any found at the floors but lost at the stored thresholds."""
    r = result[kind]
    finding = "A finding for the orchestrator (plan section 9); a second look uses the _2 seeds"
    problems = []
    if r["found"] < r["min_found"]:
        missed = ", ".join(
            f"{m['seed']} ({m['period']}px/{m['angle_deg']}deg)" for m in r["missed"]
        )
        problems.append(
            f"{r['found']}/{r['n']} {kind} found on the default path (need {r['min_found']});"
            f" missed: {missed}. {finding}"
        )
    if r["lost_by_calibration"]:
        problems.append(
            f"{kind} found at the floors but lost at the stored thresholds on seeds"
            f" {r['lost_by_calibration']}. {finding}"
        )
    return problems


# --- Budget (the plan's pre-declared count model) ---------------------------------------


def fake_count_bound(n_cal: int, n_held_out: int, rate: float, max_false_red: float) -> int:
    """AC 2's count bound: the smallest b with P(X > b) <= ``max_false_red`` under the
    single-order-statistic model at ``rate``, X ~ betabinom(n_held_out, k, n_cal + 1 - k),
    k = floor(rate (n_cal + 1)). Under the r/2 + r/2 rule the frame-level rate is at most r,
    so this is conservative for frames with a fake and an approximation for the total count
    (several fakes on one frame: P1's 1.5x multiplicity rule, plan section 3)."""
    k = threshold_rank(n_cal, rate)
    count = betabinom(n_held_out, k, n_cal + 1 - k)
    b = 0
    while count.sf(b) > max_false_red:
        b += 1
    return b


def main(argv: list[str] | None = None) -> int:
    seed_guard.install()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, required=True, help="write the calibration here")
    parser.add_argument(
        "--workers", type=int, default=None, help="worker processes (default: 3/4 of the CPUs)"
    )
    args = parser.parse_args(argv)
    warning = busy_warning("break_fork_calibration", loadavg())
    if warning is not None:
        print(warning, flush=True)
    cal = calibrate_break_forks(args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(cal.to_json())
    thresholds = cal.thresholds(BREAK_FORK_FALSE_ALARM_RATE)
    print(
        f"break and Fork calibration: n = {len(cal.ids)}, thresholds at"
        f" {BREAK_FORK_FALSE_ALARM_RATE}: {thresholds}, S_b max {max(cal.break_evidence)!r},"
        f" S_f max {max(cal.fork_evidence)!r}, S_b > 0 on"
        f" {sum(b > 0 for b in cal.break_evidence)}, S_f > 0 on"
        f" {sum(f > 0 for f in cal.fork_evidence)}, digest {cal.digest()},"
        f" {cal.run_info['seconds_per_frame']:.2f} s/frame; wrote {args.out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
