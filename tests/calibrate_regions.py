"""Region calibration driver (ticket 05, ruling B3): tunes and checks the region knobs.

Runs the analysis on frames from REGION_CALIBRATION_SEEDS only, each generate
call inside ``seed_guard.calibrating(...)``. ``tune`` uses 90_000-90_399 (the
knobs of analysis.py are chosen there); ``info`` uses 90_400-90_599, after the
knobs are frozen, for the informational numbers of the handoff. It writes
.scratch/stripe-detector/region-calibration.json (or ``--out``).

    uv run --locked python tests/calibrate_regions.py tune [--set NAME=VALUE ...]
    uv run --locked python tests/calibrate_regions.py info

``--set`` overrides an analysis.py knob in every worker (a sweep); the JSON
records the overrides. Heavy: run it alone, in the background.
"""

from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

import seed_guard
from cases import CASES
from denoisifier import analyse, analysis
from denoisifier._local_stripes import _Spectrum, estimate_local_stripes
from denoisifier.synthetic import Emccd, StripedRegion, generate
from protected import (
    MIN_SIZE_ABOVE_FACTOR,
    MIN_SIZE_BELOW_FACTOR,
    PROBE_SHAPE,
    REGION_CALIBRATION_SEEDS,
    TWO_REGION_PAIRS,
    TWO_REGION_SHAPE,
    WEAK_DEPTH,
)
from regions import iou, single_region, two_regions

OUT = Path(__file__).parents[1] / ".scratch" / "stripe-detector" / "region-calibration.json"
TUNE = range(REGION_CALIBRATION_SEEDS.start, REGION_CALIBRATION_SEEDS.start + 400)
INFO = range(TUNE.stop, REGION_CALIBRATION_SEEDS.stop)
KNOBS = (
    "_PEAK_FOOTPRINT_PX",
    "_SEED_FRACTION",
    "_MAX_CANDIDATES",
    "_SPLIT_LOG_STEPS",
    "_GROW_FRACTION",
    "_MERGE_PERIOD_RATIO",
    "_MERGE_ANGLE_DEG",
    "_MERGE_GAP_PERIODS",
    "_ABSORB_FRACTION",
    "_CORE_FRACTION",
)
SIZE_PERIODS = (3, 5, 8, 12, 20)
SIZE_ANGLES = (-10, 0, 10)
TYPICAL = dict(noise=Emccd())


def tune_jobs() -> list[tuple]:
    """(kind, seed, params) for the tuning range, partitioned by kind."""
    s = iter(TUNE)
    jobs: list[tuple] = []
    for i in range(100):  # single region, typical: 60 scorched, 40 multiscale
        jobs.append(("single", next(s), (*CASES[i % 10], "scorched" if i < 60 else "multiscale")))
    for i in range(30):  # two regions, typical
        jobs.append(("two", next(s), TWO_REGION_PAIRS[i % 3]))
    for i in range(60):  # full frame m = 0.5, typical
        jobs.append(("full", next(s), CASES[i % 10]))
    for _ in range(60):  # stripe-free, typical
        jobs.append(("free", next(s), ()))
    for i in range(60):  # size rule at low noise with scorched Mottle
        p, a = SIZE_PERIODS[i % 5], SIZE_ANGLES[(i // 5) % 3]
        shape = ("both", "wide_short", "narrow_tall")[(i // 15) % 3]
        f = MIN_SIZE_BELOW_FACTOR if (i // 45) % 2 == 0 else MIN_SIZE_ABOVE_FACTOR
        jobs.append(("size_mottle", next(s), (p, a, shape, f)))
    for i in range(20):  # probe-shaped, m = 0.2, typical
        jobs.append(("probe", next(s), CASES[i % 10]))
    for i in range(30):  # two regions at low noise (leak into the size rule)
        jobs.append(("two_low", next(s), TWO_REGION_PAIRS[i % 3]))
    return jobs


def info_jobs() -> list[tuple]:
    s = iter(INFO)
    jobs: list[tuple] = []
    factors = (0.8, 1.0, 1.25, 1.5, 2.0, 3.0)
    for i in range(120):  # detection vs size at typical noise
        p, a = SIZE_PERIODS[i % 5], SIZE_ANGLES[(i // 5) % 3]
        f = factors[i % 6]
        shape = "both" if i < 60 else "wide_short"
        jobs.append(("size_typical", next(s), (p, a, shape, f)))
    for i in range(80):  # m = 0.2 IoU, typical
        jobs.append(("single_weak", next(s), (*CASES[i % 10], "scorched")))
    return jobs


def size_region(period, angle_deg, shape, f, center):
    axes = {
        "both": (f * period, 1.5 * f * period),
        "wide_short": (f * period, 2.0 * period),
        "narrow_tall": (2.0 * period, 1.5 * f * period),
    }[shape]
    return StripedRegion(
        center=center,
        semi_axes=axes,
        rotation_deg=0.0,
        edge_px=1.0,
        period=float(period),
        angle_deg=float(angle_deg),
        modulation_depth=0.6,
    )


def _frame(kind, seed, params):
    if kind in ("single", "single_weak"):
        p, a, mottle = params
        depth = WEAK_DEPTH if kind == "single_weak" else 0.5
        return generate(
            seed=seed,
            shape=(512, 512),
            mottle=mottle,
            regions=[single_region(p, a, depth=depth)],
            **TYPICAL,
        )
    if kind in ("two", "two_low"):
        noise = TYPICAL if kind == "two" else {}
        return generate(
            seed=seed,
            shape=TWO_REGION_SHAPE,
            mottle="scorched",
            regions=two_regions(*params),
            **noise,
        )
    if kind == "full":
        p, a = params
        return generate(
            seed=seed, period=p, angle_deg=a, modulation_depth=0.5, mottle="scorched", **TYPICAL
        )
    if kind == "free":
        return generate(seed=seed, modulation_depth=0.0, mottle="scorched", **TYPICAL)
    if kind in ("size_mottle", "size_typical"):
        p, a, shape, f = params
        noise = TYPICAL if kind == "size_typical" else {}
        return generate(
            seed=seed,
            mottle="scorched",
            regions=[size_region(p, a, shape, f, (127.5, 127.5))],
            **noise,
        )
    if kind == "probe":
        p, a = params
        return generate(
            seed=seed,
            shape=PROBE_SHAPE,
            period=p,
            angle_deg=a,
            modulation_depth=WEAK_DEPTH,
            mottle="scorched",
            **TYPICAL,
        )
    raise ValueError(kind)


class _CapCounter(logging.Handler):
    def __init__(self):
        super().__init__()
        self.hits = 0

    def emit(self, record):
        if "cap" in record.getMessage():
            self.hits += 1


def _candidate_reach(frame):
    """Candidates (in visiting order, uncapped) needed to reach the top
    qualifying group and the last qualifying group above THRESHOLD."""
    env = gaussian_filter(frame, analysis._ENVELOPE_SIGMA)
    light = env > analysis._MASK_FRACTION * env.max()
    local = estimate_local_stripes(frame, light)
    filters = analysis._Filters(_Spectrum(frame), light)
    cap = analysis._MAX_CANDIDATES
    analysis._MAX_CANDIDATES = 10_000
    try:
        candidates = analysis._grow_candidates(local, light, filters)
    finally:
        analysis._MAX_CANDIDATES = cap
    groups = analysis._merge(candidates, local, filters)
    index = {id(c.seed): i + 1 for i, c in enumerate(candidates)}
    qualifying = [
        (index[id(g.top_seed)], g.peak_ratio)
        for g in groups
        if analysis._passes_size_rule(g, filters)
    ]
    top = max(qualifying, key=lambda q: q[1])[0] if qualifying else 0
    above = max((i for i, r in qualifying if r > analysis.THRESHOLD), default=0)
    return {"n_candidates": len(candidates), "reach_top": top, "reach_reported": above}


def run_job(job, overrides):
    kind, seed, params = job
    for name, value in overrides.items():
        setattr(analysis, name, value)
    counter = _CapCounter()
    logger = logging.getLogger("denoisifier.analysis")
    logger.addHandler(counter)
    logger.setLevel(logging.INFO)
    s = _frame(kind, seed, params)
    t0 = time.perf_counter()
    report = analyse(s.frame)
    seconds = time.perf_counter() - t0
    logger.removeHandler(counter)
    rec = {
        "kind": kind,
        "seed": seed,
        "params": list(params),
        "seconds": seconds,
        "score": report.score,
        "n_regions": len(report.regions),
        "cap_hit": counter.hits > 0,
        "regions": [
            {
                "period": r.period_px,
                "angle": r.angle_deg,
                "depth": r.modulation_depth,
                "area": r.area_px,
            }
            for r in report.regions
        ],
    }
    striped_truth = [t for t in s.truth.regions if t.modulation_depth > 0]
    if kind in ("single", "single_weak", "two", "two_low"):
        rec["iou_union"] = iou(
            report.mask(), np.logical_or.reduce([t.mask >= 0.5 for t in striped_truth])
        )
        rec["per_truth"] = []
        for t in striped_truth:
            tm = t.mask >= 0.5
            best = max(
                report.regions,
                key=lambda r: (report.labels == r.label)[tm].sum(),
                default=None,
            )
            entry = {"period": t.period, "angle": t.angle_deg}
            if best is not None:
                own = report.labels == best.label
                entry.update(
                    iou=iou(own, tm),
                    period_err=best.period_px / t.period - 1,
                    angle_err=best.angle_deg - t.angle_deg,
                    depth_err=best.modulation_depth - t.modulation_depth,
                    label=best.label,
                )
            rec["per_truth"].append(entry)
        if kind in ("two", "two_low"):
            env = generate(
                seed=seed, shape=TWO_REGION_SHAPE, mottle="none", regions=(), noise=0.0
            ).clean  # the Profile: the spot's half maximum, without the Mottle
            rec["truth_inside_half_envelope"] = bool(
                all((env[t.mask >= 0.5] >= 0.5 * env.max()).all() for t in striped_truth)
            )
    if kind in ("full", "probe"):
        truth = s.truth
        rec["bad_regions"] = sum(
            1
            for r in report.regions
            if abs(r.period_px / truth.period - 1) > 0.05 or abs(r.angle_deg - truth.angle_deg) > 1
        )
    if kind in ("probe", "free", "full"):
        rec.update(_candidate_reach(s.frame))
    return rec


def summarise(records):
    by = defaultdict(list)
    for r in records:
        by[r["kind"]].append(r)
    out = {}
    if "single" in by:
        per_p = defaultdict(list)
        for r in by["single"]:
            mottle = r["params"][2]
            per_p[f"{mottle} P{r['params'][0]}"].append(r)
        out["single"] = {
            k: {
                "iou_median": float(np.median([x["iou_union"] for x in v])),
                "iou_worst": float(min(x["iou_union"] for x in v)),
                "counts": sorted(x["n_regions"] for x in v),
                "period_or_angle_misses": sum(
                    1
                    for x in v
                    for t in x["per_truth"]
                    if "period_err" not in t
                    or abs(t["period_err"]) > 0.05
                    or abs(t["angle_err"]) > 1
                ),
            }
            for k, v in sorted(per_p.items())
        }
    for kind in ("two", "two_low"):
        if kind in by:
            out[kind] = {
                "frames": len(by[kind]),
                "exactly_two": sum(1 for x in by[kind] if x["n_regions"] == 2),
                "counts": sorted(x["n_regions"] for x in by[kind]),
                "separate_and_correct": sum(
                    1
                    for x in by[kind]
                    if len({t.get("label") for t in x["per_truth"]}) == 2
                    and all(
                        "period_err" in t
                        and abs(t["period_err"]) <= 0.05
                        and abs(t["angle_err"]) <= 1
                        for t in x["per_truth"]
                    )
                ),
                "per_region_iou_worst": float(
                    min(t.get("iou", 0.0) for x in by[kind] for t in x["per_truth"])
                ),
                "truth_inside_half_envelope": all(
                    x["truth_inside_half_envelope"] for x in by[kind]
                ),
            }
    if "full" in by:
        out["full"] = {
            "frames": len(by["full"]),
            "striped": sum(1 for x in by["full"] if x["n_regions"] > 0),
            "counts": sorted(x["n_regions"] for x in by["full"]),
            "frames_with_mismeasured_region": sum(1 for x in by["full"] if x["bad_regions"]),
        }
    if "free" in by:
        scores = [x["score"] for x in by["free"]]
        out["free"] = {"score_max": max(scores), "score_median": float(np.median(scores))}
    if "size_mottle" in by:
        rows = by["size_mottle"]
        out["size_mottle"] = {
            "below_reported": [
                x["params"] for x in rows if x["params"][3] < 1 and x["n_regions"] > 0
            ],
            "above_missed": [
                x["params"] for x in rows if x["params"][3] > 1 and x["n_regions"] != 1
            ],
            # Above the minimum but no size-qualifying group at all (score 0):
            # a size-rule miss, not a detection miss.
            "above_not_qualifying": [
                x["params"] for x in rows if x["params"][3] > 1 and x["score"] == 0
            ],
        }
    if "probe" in by:
        out["probe"] = {
            "seconds_max": max(x["seconds"] for x in by["probe"]),
            "score_min": min(x["score"] for x in by["probe"]),
            "frames_with_mismeasured_region": sum(1 for x in by["probe"] if x["bad_regions"]),
        }
    reach = [x for k in ("probe", "free", "full") for x in by.get(k, [])]
    if reach:
        out["candidates"] = {
            "cap": analysis._MAX_CANDIDATES,
            "cap_hit_frames": sum(1 for x in records if x["cap_hit"]),
            "reach_top_max": max(x["reach_top"] for x in reach),
            "reach_reported_max": max(x["reach_reported"] for x in reach),
            "n_candidates_max_uncapped": max(x["n_candidates"] for x in reach),
        }
    if "size_typical" in by:
        table = defaultdict(lambda: [0, 0])
        for x in by["size_typical"]:
            key = f"{x['params'][2]} f{x['params'][3]}"
            table[key][0] += x["n_regions"] > 0
            table[key][1] += 1
        out["size_typical_reported"] = {k: f"{a}/{n}" for k, (a, n) in sorted(table.items())}
    if "single_weak" in by:
        per_p = defaultdict(list)
        for x in by["single_weak"]:
            per_p[f"P{x['params'][0]}"].append(x)
        out["single_weak_m0.2"] = {
            k: {
                "reported": sum(1 for x in v if x["n_regions"] > 0),
                "frames": len(v),
                "iou_median": float(np.median([x["iou_union"] for x in v])),
                "iou_worst": float(min(x["iou_union"] for x in v)),
            }
            for k, v in sorted(per_p.items())
        }
    secs = [x["seconds"] for x in records]
    out["seconds_max"] = max(secs)
    return out


def main(argv=None):
    seed_guard.install()
    # One thread per spawned worker: the workers inherit these and import
    # NumPy fresh.
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["tune", "info"])
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--only", action="append", default=[], help="job kinds to run")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args(argv)
    overrides = {}
    for item in args.set:
        name, value = item.split("=")
        if name not in KNOBS:
            raise SystemExit(f"unknown knob {name}")
        overrides[name] = type(getattr(analysis, name))(value)
    seeds = TUNE if args.mode == "tune" else INFO
    jobs = tune_jobs() if args.mode == "tune" else info_jobs()
    if args.only:
        jobs = [j for j in jobs if j[0] in args.only]
    for name, value in overrides.items():
        setattr(analysis, name, value)
    with seed_guard.calibrating(seeds):
        with ProcessPoolExecutor(
            args.workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=seed_guard.install_worker,
            initargs=(seed_guard.worker_allowance(),),
        ) as pool:
            records = list(pool.map(run_job, jobs, [overrides] * len(jobs)))
    result = {
        "mode": args.mode,
        "seeds": [seeds.start, seeds.stop],
        "knobs": {k: getattr(analysis, k) for k in KNOBS},
        "overrides": overrides,
        "summary": summarise(records),
        "records": records,
    }
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
