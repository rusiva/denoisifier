"""PROTOTYPE (throwaway evidence script), ticket 06: plan-review P2 (+ B4) and critic Q4/O2.

Questions:
  rule  - generator side, no detector: the highest clip fraction C/clean.max() at which the
          depth of np.minimum(clean, C) (noise-free; Gabor at the true Period and Angle, median
          over the region's interior) misses DEPTH_TOL by a clear margin.
  guard - on noisy clipped striped frames (D7 auto clip detection), the reported depth with no
          exclusion ("plain"), the plan's D9 guard, a Gaussian-window variant, a global weighted
          fit (mean, cos, sin; clipped weight 0) over the region's pixels and over its bounding
          box, and a local weighted fit (normalised convolution, local_mean-sized window).
          Also: does a second harmonic (P/2) become a region (critic O2)?
  free  - stripe-free frames: clipped vs unclipped score, paired (critic O2).

Run from a BASE (4e40bdd) checkout root:
    uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p2.py rule OUT.json
    uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p2.py guard OUT.json F1 F2 ...
    uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p2.py free OUT.json F1 F2 ...

Seeds: 396_000-396_099 only (plan section 4 reservation range(396_000, 396_400)); never
calibration seeds, never the critic's 700_000-700_005 / 700_100-700_139.
Nothing in src/ is edited: the variants are computed in a monkeypatched _settle_overlaps.
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
from protected import (  # noqa: E402
    ANGLE_TOL_DEG,
    CALIBRATION_SEEDS,
    DEPTH_TOL,
    GATE_STORED_THRESHOLD,
    PERIOD_REL_TOL,
)
from regions import single_region, truth_pixels  # noqa: E402

from denoisifier import analysis  # noqa: E402
from denoisifier._local_stripes import _ACROSS, _ALONG, _Spectrum  # noqa: E402
from denoisifier.synthetic import Emccd, generate  # noqa: E402

FULL_SEEDS = range(396_000, 396_040)
PARTIAL_SEEDS = range(396_040, 396_060)
FREE_SEEDS = range(396_060, 396_100)
for _s in [*FULL_SEEDS, *PARTIAL_SEEDS, *FREE_SEEDS]:
    assert not any(_s in r for r in CALIBRATION_SEEDS.values())
    assert not (700_000 <= _s < 700_006 or 700_100 <= _s < 700_140)

PHOTONS = (10.0, 30.0, 100.0, 5000.0)
RULE_FRACTIONS = tuple(round(f, 2) for f in np.arange(0.95, 0.09, -0.05))
MIN_CLIPPED_PIXELS = 4  # plan D7 start value
M = 0.5

CLIPPED = None  # bool mask of the frame being analysed (set per job)
FRAME = None
SIDE: dict[int, dict] = {}


# ---------------------------------------------------------------- frames


def make(kind, seed, photons, m=M):
    period, angle = CASES[seed % len(CASES)]
    if kind == "full":
        s = generate(seed=seed, shape=(256, 256), period=period, angle_deg=angle,
                     modulation_depth=m, mottle="scorched", noise=Emccd(photons_peak=photons))
        region = np.ones(s.frame.shape, bool)
    else:
        s = generate(seed=seed, shape=(512, 512), mottle="scorched",
                     regions=[single_region(period, angle, depth=m)],
                     noise=Emccd(photons_peak=photons))
        region = truth_pixels(s.truth.regions[0])
    return s, region, period, angle


def find_clipped(frame):
    """Plan D7: a plateau of >= MIN_CLIPPED_PIXELS equal values at the maximum."""
    top = frame.max()
    at = frame == top
    if at.sum() >= MIN_CLIPPED_PIXELS and frame.min() < top:
        return at
    return np.zeros(frame.shape, bool)


# ---------------------------------------------------------------- rule (generator side)


def gabor_depth(img, period, angle, area):
    light = analysis._light(img)
    filt = analysis._Filters(_Spectrum(img), light)
    depth = filt.depth(period, angle)
    return analysis._interior_depth(depth, area & light)


def rule_job(job):
    kind, seed = job
    s, region, period, angle = make(kind, seed, 100.0)
    clean = s.clean  # clean.max() == 100 (photons_peak)
    out = {"kind": kind, "seed": seed, "case": [period, angle],
           "unclipped": gabor_depth(clean, period, angle, region), "clipped": {}}
    for f in RULE_FRACTIONS:
        cc = np.minimum(clean, f * clean.max())
        out["clipped"][str(f)] = gabor_depth(cc, period, angle, region)
    return out


# ---------------------------------------------------------------- depth variants


def interior(mask):
    if not mask.any():
        return mask
    d = ndimage.distance_transform_edt(mask)
    return d >= analysis._INTERIOR_FRACTION * d.max()


def d9(depth, pixels, clipped, period, kind, sig, wmax, own_interior=False):
    if kind == "box":
        rows = 2 * int(np.ceil(sig * _ALONG * period)) + 1
        cols = 2 * int(np.ceil(sig * _ACROSS * period)) + 1
        w = ndimage.uniform_filter(clipped.astype(float), size=(rows, cols))
    else:
        w = ndimage.gaussian_filter(clipped.astype(float), sigma=(_ALONG * period, _ACROSS * period))
    use = pixels & (w < wmax)
    if own_interior:  # the region's own interior first, then drop contaminated pixels
        use = interior(pixels) & (w < wmax)
        if not use.any():
            return analysis._interior_depth(depth, pixels), True, 0
        return analysis._median_depth(depth, use), False, int(use.sum())
    if not use.any():
        return analysis._interior_depth(depth, pixels), True, 0
    inner = interior(use)
    return analysis._median_depth(depth, inner), False, int(inner.sum())


def basis(shape, period, angle):
    y, x = np.mgrid[0 : shape[0], 0 : shape[1]].astype(float)
    t = np.deg2rad(angle)
    ph = 2 * np.pi / period * (x * np.cos(t) + y * np.sin(t))
    return [np.ones(shape), np.cos(ph), np.sin(ph)]


def global_fit(frame, area, clipped, period, angle):
    use = area & ~clipped
    if use.sum() < 10:
        return float("nan")
    b = basis(frame.shape, period, angle)
    A = np.stack([v[use] for v in b], axis=1)
    coef, *_ = np.linalg.lstsq(A, frame[use], rcond=None)
    return float(np.hypot(coef[1], coef[2]) / coef[0])


def local_fit(frame, pixels, clipped, period, angle, min_weight=0.5):
    """Normalised convolution: per-pixel weighted LSQ of mean, cos, sin over a Gaussian window
    sigma (1.5 P along, 1 P across); clipped pixels weight 0. Median over the region's interior
    where the unclipped share of the window is >= min_weight."""
    b = basis(frame.shape, period, angle)
    w = (~clipped).astype(float)
    sig = (_ALONG * period, _ACROSS * period)
    g = lambda a: ndimage.gaussian_filter(a, sigma=sig)  # noqa: E731
    S = np.empty(frame.shape + (3, 3))
    for i in range(3):
        for j in range(i, 3):
            S[..., i, j] = S[..., j, i] = g(w * b[i] * b[j])
    R = np.stack([g(w * frame * b[i]) for i in range(3)], axis=-1)
    share = S[..., 0, 0]
    ok = share >= min_weight
    coef = np.zeros(frame.shape + (3,))
    coef[ok] = np.linalg.solve(S[ok], R[ok][..., None])[..., 0]
    depth = np.zeros(frame.shape)
    good = ok & (coef[..., 0] > 0)
    depth[good] = np.hypot(coef[good, 1], coef[good, 2]) / coef[good, 0]
    inner = interior(pixels) & good
    if not inner.any():
        inner = interior(pixels & good)
    if not inner.any():
        return float("nan"), True, 0
    return float(np.median(depth[inner])), False, int(inner.sum())


def _local_coefs(frame, w, b, sig):
    g = lambda a: ndimage.gaussian_filter(a, sigma=sig)  # noqa: E731
    S = np.empty(frame.shape + (3, 3))
    for i in range(3):
        for j in range(i, 3):
            S[..., i, j] = S[..., j, i] = g(w * b[i] * b[j])
    R = np.stack([g(w * frame * b[i]) for i in range(3)], axis=-1)
    return S, R, g


def local_fit_censored(frame, pixels, clipped, period, angle, k=2.0, passes=3, min_weight=0.3):
    """Local weighted fit that also drops pixels whose fitted (clean) value is within k local
    sigmas of the clip level: there the noise pushes a share of the pixels over the level, so the
    unclipped ones left are a censored, low-biased sample."""
    if not clipped.any():
        return float("nan"), True, 0
    level = float(frame[clipped].max())
    b = basis(frame.shape, period, angle)
    sig = (_ALONG * period, _ACROSS * period)
    w = (~clipped).astype(float)
    for p in range(passes + 1):
        S, R, g = _local_coefs(frame, w, b, sig)
        ok = S[..., 0, 0] >= min_weight
        coef = np.zeros(frame.shape + (3,))
        coef[ok] = np.linalg.solve(S[ok] + 1e-9 * np.eye(3), R[ok][..., None])[..., 0]
        if p == passes:
            break
        model = coef[..., 0] + coef[..., 1] * b[1] + coef[..., 2] * b[2]
        resid2 = g(w * (frame - model) ** 2) / np.maximum(g(w), 1e-9)
        w = ((~clipped) & ok & (model < level - k * np.sqrt(resid2))).astype(float)
    depth = np.zeros(frame.shape)
    good = ok & (coef[..., 0] > 0)
    depth[good] = np.hypot(coef[good, 1], coef[good, 2]) / coef[good, 0]
    inner = interior(pixels) & good
    if not inner.any():
        inner = interior(pixels & good)
    if not inner.any():
        return float("nan"), True, 0
    return float(np.median(depth[inner])), False, int(inner.sum())


_orig_settle = analysis._settle_overlaps


def _settle_patched(groups):
    out = _orig_settle(groups)
    if CLIPPED is None or not groups:
        return out
    claims = np.stack([g.grown for g in groups])
    depths = np.stack([np.where(g.grown, g.tuned_depth, -np.inf) for g in groups])
    owner = np.argmax(depths, axis=0)
    claimed = claims.any(axis=0)
    for k, g in enumerate(groups):
        pixels = claimed & (owner == k)
        if not pixels.any():
            continue
        rec = {"clipped_in_region": int((CLIPPED & pixels).sum()), "area": int(pixels.sum())}
        if CLIPPED.any():
            for name, args in {
                "d9_plan": ("box", 2.0, 0.01),
                "d9_gauss02": ("gauss", None, 0.02),
                "d9_inner_box": ("box", 2.0, 0.01, True),
                "d9_inner_g10": ("gauss", None, 0.10, True),
            }.items():
                d, fb, n = d9(g.tuned_depth, pixels, CLIPPED, g.period, *args)
                rec[name] = {"depth": d, "fallback": fb, "n": n}
        rec["_group"] = (g.period, g.angle_deg)
        SIDE[int(np.flatnonzero(pixels)[0])] = rec
    return out


analysis._settle_overlaps = _settle_patched


RULE_MARGIN = 0.05  # "clear margin": flattened clean depth <= M - DEPTH_TOL - RULE_MARGIN


def rule_fraction(clean, region, period, angle):
    """Per-frame generator-side rule: the highest fraction f (to 0.005) at which the depth of
    np.minimum(clean, f * clean.max()) is <= M - DEPTH_TOL - RULE_MARGIN (bisection; depth
    falls with f on every rule frame)."""
    target = M - DEPTH_TOL - RULE_MARGIN
    lo, hi = 0.02, 1.0  # depth(lo) <= target < depth(hi)
    while hi - lo > 0.005:
        mid = (lo + hi) / 2
        if gabor_depth(np.minimum(clean, mid * clean.max()), period, angle, region) <= target:
            lo = mid
        else:
            hi = mid
    return lo


def guard_job(job):
    global CLIPPED
    kind, seed, photons, frac = job
    s, region, period, angle = make(kind, seed, photons)
    if frac == 0:  # per-frame rule level
        frac = rule_fraction(s.clean, region, period, angle)
        rule = True
    else:
        rule = False
    level = frac * photons  # clean.max() == photons
    truth_clip = s.frame >= level
    frame = np.minimum(s.frame, level)
    CLIPPED = find_clipped(frame)
    SIDE.clear()
    rep = analysis.analyse(frame)
    regions = []
    for r in rep.regions:
        own = rep.labels == r.label
        rec = SIDE.get(int(np.flatnonzero(own)[0]), {})
        rec.pop("_group", None)
        bb = r.bbox
        box = np.zeros(own.shape, bool)
        box[bb.row_start : bb.row_stop, bb.col_start : bb.col_stop] = True
        if CLIPPED.any():
            rec["fit_region"] = global_fit(frame, own, CLIPPED, r.period_px, r.angle_deg)
            rec["fit_bbox"] = global_fit(frame, box, CLIPPED, r.period_px, r.angle_deg)
            d, fb, n = local_fit(frame, own, CLIPPED, r.period_px, r.angle_deg)
            rec["local_fit"] = {"depth": d, "fallback": fb, "n": n}
            d, fb, n = local_fit_censored(frame, own, CLIPPED, r.period_px, r.angle_deg)
            rec["local_cens"] = {"depth": d, "fallback": fb, "n": n}
        period_ok = abs(r.period_px - period) <= PERIOD_REL_TOL * period
        angle_ok = abs(r.angle_deg - angle) <= ANGLE_TOL_DEG
        harmonic = abs(r.period_px - period / 2) <= PERIOD_REL_TOL * period / 2
        regions.append({"period": r.period_px, "angle": r.angle_deg, "plain": r.modulation_depth,
                        "period_ok": period_ok, "angle_ok": angle_ok, "harmonic": harmonic,
                        **rec})
    CLIPPED = None
    ref = analysis.analyse(s.frame)
    return {
        "kind": kind, "seed": seed, "photons": photons, "frac": frac, "rule": rule,
        "case": [period, angle],
        "truth_clipped": int(truth_clip.sum()),
        "truth_clipped_in_region": int((truth_clip & region).sum()),
        "detected_clipped": int(find_clipped(frame).sum()),
        "detect_exact": bool((find_clipped(frame) == truth_clip).all()),
        "striped": rep.striped, "score": rep.score, "regions": regions,
        "ref_striped": ref.striped, "ref_depths": [r.modulation_depth for r in ref.regions],
    }


def free_job(job):
    seed, photons, fracs = job
    s = generate(seed=seed, shape=(256, 256), modulation_depth=0.0, mottle="scorched",
                 noise=Emccd(photons_peak=photons))
    out = {"seed": seed, "photons": photons, "unclipped": analysis.analyse(s.frame).score}
    for f in fracs:
        frame = np.minimum(s.frame, f * photons)
        rep = analysis.analyse(frame)
        out[str(f)] = {"score": rep.score,
                       "regions": [[r.period_px, r.angle_deg] for r in rep.regions],
                       "clipped": int(find_clipped(frame).sum())}
    return out


def main():
    mode, out = sys.argv[1], Path(sys.argv[2])
    fracs = [float(a) for a in sys.argv[3:]]
    if mode == "rule":
        jobs, fn = [("full", s) for s in FULL_SEEDS] + [("partial", s) for s in PARTIAL_SEEDS], rule_job
    elif mode == "guard":
        jobs = [(k, s, p, f) for p in PHOTONS for f in fracs
                for k, seeds in (("full", FULL_SEEDS), ("partial", PARTIAL_SEEDS)) for s in seeds]
        fn = guard_job
    else:
        jobs, fn = [(s, p, fracs) for p in (30.0, 100.0) for s in FREE_SEEDS], free_job
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(fn, jobs, chunksize=2))
    out.write_text(json.dumps({"mode": mode, "fracs": fracs, "DEPTH_TOL": DEPTH_TOL,
                               "GATE_STORED_THRESHOLD": GATE_STORED_THRESHOLD, "results": res}))
    print("wrote", out, len(res), f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
