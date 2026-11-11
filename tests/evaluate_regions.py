"""One-off held-out evaluation of ticket 05's acceptance criteria (ruling "Evaluation hygiene").

Runs every analysis acceptance criterion of ticket 05 once on the fresh,
predeclared REGION_EVALUATION_SEEDS, after the region knobs are frozen, and
prints pass counts per criterion. Nothing is tuned on its results. The CLI
criterion (AC 7) is file layout, not detection; tests/test_cli.py covers it.

    uv run --locked python tests/evaluate_regions.py [--out PATH]

Heavy: run it alone, in the background.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import seed_guard
from calibrate_regions import SIZE_SHAPES
from cases import CASES
from denoisifier import analyse
from denoisifier.synthetic import Emccd, StripedRegion, generate
from protected import (
    ANGLE_TOL_DEG,
    BBOX_TOL_PERIODS,
    DARK_FRACTION,
    DEPTH_TOL,
    MASK_IOU_MIN,
    MIN_SIZE_ABOVE_FACTOR,
    MIN_SIZE_BELOW_FACTOR,
    PERIOD_REL_TOL,
    REGION_EVALUATION_SEEDS,
    REGION_FRAME_SHAPE,
    TWO_REGION_PAIRS,
    TWO_REGION_SHAPE,
)
from regions import iou, match, single_region, truth_bbox, two_regions

TYPICAL = dict(noise=Emccd())
SHAPE = (256, 256)
SIZE_CASES = [(p, a) for p in (3, 8, 20) for a in (-10, 10)]


def jobs() -> list[tuple]:
    s = iter(REGION_EVALUATION_SEEDS)
    out: list[tuple] = []
    for i in range(40):  # AC 2 and AC 3 (scorched)
        out.append(("single", next(s), (*CASES[i % 10], "scorched")))
    for i in range(40):  # AC 3 (multiscale)
        out.append(("single", next(s), (*CASES[i % 10], "multiscale")))
    for i in range(30):  # AC 4
        out.append(("two", next(s), TWO_REGION_PAIRS[i % 3]))
    for _ in range(4):  # AC 5
        seed = next(s)
        for p, a in SIZE_CASES:
            for shape in SIZE_SHAPES:
                out.append(("below", seed, (p, a, shape)))
            for shape in ("both", "wide_short", "narrow_tall"):
                out.append(("above", seed, (p, a, shape)))
    for i in range(10):  # AC 6, flank
        out.append(("flank", next(s), tuple(CASES[i % 10])))
    for _ in range(10):  # AC 6, dark area
        seed = next(s)
        for case in ("full-frame-noise-free", "full-frame-typical", "spilling-region"):
            out.append(("dark", seed, (case,)))
    for i in range(20):  # full-frame stripes: every region matches truth
        out.append(("full", next(s), tuple(CASES[i % 10])))
    for _ in range(20):  # stripe-free
        out.append(("free", next(s), ()))
    for i in range(20):  # strong stripes (Period 5 and 12, Angle 6, m = 0.8)
        out.append(("strong", next(s), ((5, 12)[i % 2],)))
    for i in range(12):  # weak region beside a strong one, sharp edges, low noise
        pair = TWO_REGION_PAIRS[i % 3]
        out.append(("neighbour", next(s), (*pair, (i // 3) % 2 == 0)))
    return out


def _matches(region, truth, depth=True) -> bool:
    ok = (
        abs(region.period_px / truth.period - 1) <= PERIOD_REL_TOL
        and abs(region.angle_deg - truth.angle_deg) <= ANGLE_TOL_DEG
    )
    if depth:
        ok = ok and abs(region.modulation_depth - truth.modulation_depth) <= DEPTH_TOL
    return bool(ok)


def run(job) -> dict:
    kind, seed, params = job
    rec: dict = {"kind": kind, "seed": seed, "params": list(params)}
    if kind == "single":
        p, a, mottle = params
        s = generate(
            seed=seed,
            shape=REGION_FRAME_SHAPE,
            mottle=mottle,
            regions=[single_region(p, a)],
            **TYPICAL,
        )
        r = analyse(s.frame)
        (truth,) = s.truth.regions
        tm = truth.mask >= 0.5
        rec["iou"] = iou(r.mask(), tm)
        rec["iou_ok"] = rec["iou"] >= MASK_IOU_MIN
        ok = r.striped and len(r.regions) == 1 and _matches(r.regions[0], truth)
        if ok:
            b, want = r.regions[0].bbox, truth_bbox(tm)
            got = (b.row_start, b.row_stop, b.col_start, b.col_stop)
            ok = all(abs(g - w) <= BBOX_TOL_PERIODS * p for g, w in zip(got, want, strict=True))
        rec["ac2_ok"] = bool(ok)
        rec["n_regions"] = len(r.regions)
    elif kind in ("two", "neighbour"):
        if kind == "two":
            regions = two_regions(*params)
            extra = dict(mottle="scorched", **TYPICAL)
        else:
            left, right, strong_left = params
            depths = (0.6, 0.3) if strong_left else (0.3, 0.6)
            regions = two_regions(left, right, depth=depths, edge_px=1.0, gap_windows=0.5)
            extra = {}
        s = generate(seed=seed, shape=TWO_REGION_SHAPE, regions=regions, **extra)
        r = analyse(s.frame)
        pairs = match(r.regions, r.labels, s.truth.regions)
        ok = len(r.regions) == 2 and len({id(t) for _, t in pairs}) == 2
        ok = ok and all(_matches(reg, t, depth=False) for reg, t in pairs)
        if kind == "two":
            ok = ok and all(
                iou(r.labels == reg.label, t.mask >= 0.5) >= MASK_IOU_MIN for reg, t in pairs
            )
        rec["ok"] = bool(ok)
        rec["n_regions"] = len(r.regions)
    elif kind in ("below", "above"):
        p, a, shape = params
        f = MIN_SIZE_BELOW_FACTOR if kind == "below" else MIN_SIZE_ABOVE_FACTOR
        region = StripedRegion(
            center=(127.5, 127.5),
            semi_axes=SIZE_SHAPES[shape](p, f),
            rotation_deg=0.0,
            edge_px=1.0,
            period=float(p),
            angle_deg=float(a),
            modulation_depth=0.6,
        )
        r = analyse(generate(seed=seed, shape=SHAPE, regions=[region]).frame)
        if kind == "below":
            rec["ok"] = r.regions == () and not r.striped
        else:
            rec["ok"] = (
                len(r.regions) == 1 and abs(r.regions[0].period_px - p) <= PERIOD_REL_TOL * p
            )
        rec["n_regions"] = len(r.regions)
    elif kind == "flank":
        p, a = params
        rows, cols = REGION_FRAME_SHAPE
        region = single_region(p, a, center=((rows - 1) / 2, cols / 4))
        s = generate(
            seed=seed, shape=REGION_FRAME_SHAPE, regions=[region], mottle="scorched", **TYPICAL
        )
        r = analyse(s.frame)
        rec["ok"] = (
            r.striped
            and len(r.regions) == 1
            and r.regions[0].bbox.col_stop <= cols // 2
            and abs(r.regions[0].period_px - p) <= PERIOD_REL_TOL * p
        )
    elif kind == "dark":
        (case,) = params
        kwargs = {
            "full-frame-noise-free": dict(modulation_depth=0.6, noise=0.0),
            "full-frame-typical": dict(modulation_depth=0.6, mottle="scorched", **TYPICAL),
            "spilling-region": dict(
                regions=[StripedRegion((127.5, 127.5), (200.0, 200.0), 0.0, 6.0, 8.0, 4.0, 0.6)],
                noise=0.0,
            ),
        }[case]
        r = analyse(generate(seed=seed, shape=SHAPE, **kwargs).frame)
        profile = generate(seed=seed, shape=SHAPE, regions=(), mottle="none", noise=0.0).clean
        dark = profile < DARK_FRACTION * profile.max()
        rec["ok"] = bool(r.striped and not r.mask()[dark].any())
    elif kind in ("full", "strong"):
        if kind == "full":
            p, a = params
            m = 0.5
        else:
            (p,), a, m = params, 6, 0.8
        s = generate(
            seed=seed,
            shape=SHAPE,
            period=p,
            angle_deg=a,
            modulation_depth=m,
            mottle="scorched",
            **TYPICAL,
        )
        r = analyse(s.frame)
        rec["ok"] = bool(r.striped and all(_matches(reg, s.truth) for reg in r.regions))
        rec["n_regions"] = len(r.regions)
    elif kind == "free":
        r = analyse(
            generate(
                seed=seed, shape=SHAPE, modulation_depth=0.0, mottle="scorched", **TYPICAL
            ).frame
        )
        rec["ok"] = bool(not r.striped and r.regions == () and not r.mask().any())
        rec["score"] = r.score
    rec["ok"] = bool(rec.get("ok", rec.get("ac2_ok")))
    return rec


def summarise(records) -> dict:
    by = defaultdict(list)
    for r in records:
        by[r["kind"]].append(r)
    out = {}
    singles = by["single"]
    out["AC2 partial region (scorched)"] = _count(
        [x for x in singles if x["params"][2] == "scorched"], "ac2_ok"
    )
    for mottle in ("scorched", "multiscale"):
        rows = [x for x in singles if x["params"][2] == mottle]
        out[f"AC3 IoU >= {MASK_IOU_MIN} ({mottle})"] = _count(rows, "iou_ok")
        out[f"AC3 IoU worst ({mottle})"] = min(x["iou"] for x in rows)
        out[f"AC3 IoU median ({mottle})"] = float(np.median([x["iou"] for x in rows]))
    names = {
        "two": "AC4 two regions",
        "below": "AC5 below minimum not reported",
        "above": "AC5 above minimum reported",
        "flank": "AC6 flank found",
        "dark": "AC6 dark area never reported",
        "full": "full frame, every region matches",
        "free": "stripe-free not striped",
        "strong": "strong stripes measured",
        "neighbour": "weak region beside a strong one (R1 guard)",
    }
    for kind, name in names.items():
        out[name] = _count(by[kind], "ok")
    out["failures"] = [
        {k: x[k] for k in ("kind", "seed", "params")}
        for x in records
        if not x["ok"] or (x["kind"] == "single" and not x["iou_ok"])
    ]
    return out


def _count(rows, key) -> str:
    return f"{sum(1 for x in rows if x[key])}/{len(rows)}"


def main(argv=None):
    seed_guard.install()
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args(argv)
    with ProcessPoolExecutor(
        args.workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=seed_guard.install_worker,
        initargs=(seed_guard.worker_allowance(),),
    ) as pool:
        records = list(pool.map(run, jobs()))
    summary = summarise(records)
    args.out.write_text(json.dumps({"summary": summary, "records": records}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
