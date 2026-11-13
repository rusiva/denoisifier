"""PROTOTYPE (throwaway), ticket 06 plan-review item P2 (+ B4).

Question: with D7 auto clip detection and the D9 clipped-pixel guard on the
reported depth, are enough valid pixels left on noisy striped frames with
clipped stripe peaks, and is the depth then within DEPTH_TOL of the truth?

Run from a checkout at BASE 4e40bdd (uses its src/ and tests/):
    uv run --locked python .scratch/stripe-detector/handoffs/p2_06_proto.py [out.json]

Seeds: 396_000-396_059 only (plan section 4 reservation). Never calibration seeds.
D9 is monkeypatched into analysis._settle_overlaps; nothing in src/ is edited.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path.cwd() / "tests"))

from cases import CASES  # noqa: E402
from protected import CALIBRATION_SEEDS, DEPTH_TOL  # noqa: E402
from regions import single_region, truth_pixels  # noqa: E402

from denoisifier import analysis  # noqa: E402
from denoisifier._local_stripes import _ACROSS, _ALONG  # noqa: E402
from denoisifier.synthetic import Emccd, generate  # noqa: E402

FULL_SEEDS = range(396_000, 396_040)
PARTIAL_SEEDS = range(396_040, 396_060)
for _s in [*FULL_SEEDS, *PARTIAL_SEEDS]:
    assert not any(_s in r for r in CALIBRATION_SEEDS.values())

PHOTONS = (10.0, 30.0, 100.0, 5000.0)
FRACTIONS = (0.6, 0.7, 0.8, 0.9)
MIN_CLIPPED_PIXELS = 4

# Guard variants: name -> (kind, sigmas, wmax)
VARIANTS = {
    "plan_box2_w01": ("box", 2.0, 0.01),  # D9 as planned
    "box1_w01": ("box", 1.0, 0.01),
    "box2_w05": ("box", 2.0, 0.05),
    "gauss_w01": ("gauss", None, 0.01),  # weight with the local_mean window itself
    "gauss_w02": ("gauss", None, 0.02),
}

CLIPPED = None  # set per frame (bool mask)
SIDE: dict[int, dict] = {}


def find_clipped(frame):
    """D7: a plateau of >= MIN_CLIPPED_PIXELS equal values at the maximum."""
    m = frame.max()
    at = frame == m
    if at.sum() >= MIN_CLIPPED_PIXELS and frame.min() < m:
        return at
    return np.zeros(frame.shape, bool)


def valid_mask(clipped, period, kind, sig, wmax):
    if kind == "box":
        rows = 2 * int(np.ceil(sig * _ALONG * period)) + 1
        cols = 2 * int(np.ceil(sig * _ACROSS * period)) + 1
        w = ndimage.uniform_filter(clipped.astype(float), size=(rows, cols), mode="reflect")
    else:
        w = ndimage.gaussian_filter(
            clipped.astype(float), sigma=(_ALONG * period, _ACROSS * period), mode="reflect"
        )
    return w < wmax


def guarded_depth(depth, pixels, valid):
    use = pixels & valid
    if not use.any():
        return analysis._interior_depth(depth, pixels), True, 0, 0
    distance = ndimage.distance_transform_edt(use)
    interior = distance >= analysis._INTERIOR_FRACTION * distance.max()
    return analysis._median_depth(depth, interior), False, int(use.sum()), int(interior.sum())


_orig_settle = analysis._settle_overlaps


def _settle_patched(groups):
    out = _orig_settle(groups)
    if CLIPPED is None or not CLIPPED.any() or not groups:
        return out
    # same pixel ownership as the original
    claims = np.stack([g.grown for g in groups])
    depths = np.stack([np.where(g.grown, g.tuned_depth, -np.inf) for g in groups])
    owner = np.argmax(depths, axis=0)
    claimed = claims.any(axis=0)
    for k, g in enumerate(groups):
        pixels = claimed & (owner == k)
        if not pixels.any():
            continue
        rec = {
            "group_period": g.period,
            "area": int(pixels.sum()),
            "clipped_in_region": int((CLIPPED & pixels).sum()),
        }
        for name, (kind, sig, wmax) in VARIANTS.items():
            v = valid_mask(CLIPPED, g.period, kind, sig, wmax)
            d, fb, nv, ni = guarded_depth(g.tuned_depth, pixels, v)
            rec[name] = {"depth": d, "fallback": fb, "valid": nv, "interior": ni}
        SIDE[int(np.flatnonzero(pixels)[0])] = rec
    return out


analysis._settle_overlaps = _settle_patched


def run(job):
    global CLIPPED
    kind, seed, photons, frac = job
    period, angle = CASES[seed % len(CASES)]
    if kind == "full":
        s = generate(
            seed=seed, shape=(256, 256), period=period, angle_deg=angle, modulation_depth=0.5,
            mottle="scorched", noise=Emccd(photons_peak=photons),
        )
        region_truth = None
    else:
        s = generate(
            seed=seed, shape=(512, 512), mottle="scorched",
            regions=[single_region(period, angle)], noise=Emccd(photons_peak=photons),
        )
        region_truth = truth_pixels(s.truth.regions[0])
    level = frac * photons
    truth_clip = s.frame >= level
    frame = np.minimum(s.frame, level)  # plan D3, no spikes
    CLIPPED = find_clipped(frame)
    SIDE.clear()
    t0 = time.perf_counter()
    rep = analysis.analyse(frame)  # reported depth = plain (flattened) depth
    dt = time.perf_counter() - t0
    regions = []
    for r in rep.regions:
        own = rep.labels == r.label
        rec = SIDE.get(int(np.flatnonzero(own)[0]), {})
        regions.append(
            {"period": r.period_px, "angle": r.angle_deg, "plain": r.modulation_depth, **rec}
        )
    # Unclipped reference on the same seed (no exclusion needed)
    CLIPPED = None
    ref = analysis.analyse(s.frame)
    return {
        "kind": kind, "seed": seed, "photons": photons, "frac": frac,
        "case": [period, angle], "truth_depth": 0.5,
        "truth_clipped": int(truth_clip.sum()),
        "truth_clipped_in_region": (
            int((truth_clip & region_truth).sum()) if region_truth is not None else None
        ),
        "detected_clipped": int(CLIPPED_COUNT(frame)),
        "detect_exact": bool((find_clipped(frame) == truth_clip).all()),
        "striped": rep.striped, "regions": regions, "t": dt,
        "ref_striped": ref.striped,
        "ref_depths": [r.modulation_depth for r in ref.regions],
    }


def CLIPPED_COUNT(frame):
    return find_clipped(frame).sum()


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "p2_06_results.json")
    jobs = [("full", s, p, f) for p in PHOTONS for f in FRACTIONS for s in FULL_SEEDS]
    jobs += [("partial", s, p, f) for p in PHOTONS for f in FRACTIONS for s in PARTIAL_SEEDS]
    if len(sys.argv) > 2:
        jobs = jobs[:: int(sys.argv[2])]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(run, jobs, chunksize=2))
    out.write_text(json.dumps(res))
    print("wrote", out, len(res), "DEPTH_TOL", DEPTH_TOL, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
