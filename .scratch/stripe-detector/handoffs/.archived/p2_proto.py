"""PROTOTYPE (throwaway) for ticket stripe-detector/05, review item P2.

Real-pipeline IoU of the grown region mask vs truth (soft mask >= 0.5) with the
region geometry set in Periods. Pipeline = plan 2.3 steps 1-2:
  core = 8-conn components of ratio > THRESHOLD, split by bank Period
  (log gap > 1.5 grid steps), size test bbox >= 3P wide x 2P tall (median bank P);
  per core: neighbour-product Period/Angle on the core, re-tuned filter from ONE
  shared _Spectrum per frame, grow = connected part of
  {depth >= FRAC * median core depth} & light & dilate(core, CAP*P) touching core.
Seeds 410_000.. (outside protected ranges and the reviewer's N8 list).
Run: uv run python p2_proto.py   (from the repo worktree)
"""

import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from denoisifier._local_stripes import _Spectrum, estimate_local_stripes
from denoisifier.analysis import THRESHOLD
from denoisifier.synthetic import Emccd, _emccd, generate

CASES = [(3, 10), (5, 0), (8, 6), (12, -8), (20, -10), (4, -4), (16, 10), (6, -10), (10, 3), (14, -6)]
LOG_STEP = np.log(1.12)
EIGHT = np.ones((3, 3), bool)


def make_frame(seed, P, ang, shape, ra, ca, m=0.5):
    env = generate(seed=seed, shape=shape, modulation_depth=0.0, mottle="scorched", noise=0.0).clean
    y, x = np.mgrid[0 : shape[0], 0 : shape[1]].astype(float)
    cy, cx = shape[0] / 2, shape[1] / 2
    r = np.sqrt(((y - cy) / ra) ** 2 + ((x - cx) / ca) ** 2)
    w = 6 / (2 * np.arctanh(0.8))
    mask = 0.5 * (1 - np.tanh((r - 1) * min(ra, ca) / w))
    t = np.deg2rad(ang)
    clean = env * (1 + m * mask * np.cos(2 * np.pi / P * (x * np.cos(t) + y * np.sin(t))))
    f = _emccd(np.random.default_rng(seed + 7_000_000), clean / clean.max() * 100, Emccd())
    return f, mask >= 0.5


def cores(local):
    lab, n = ndimage.label(local.ratio > THRESHOLD, structure=EIGHT)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        comp = lab[sl] == i
        lp = np.log(local.period[sl][comp])
        u = np.unique(np.round(lp / LOG_STEP).astype(int))
        # split at gaps of >= 2 grid steps (i.e. a missing bank Period)
        groups = np.split(u, np.where(np.diff(u) >= 2)[0] + 1)
        for g in groups:
            sel = np.zeros(lab.shape, bool)
            sub = comp & np.isin(np.round(np.log(local.period[sl]) / LOG_STEP).astype(int), g)
            sel[sl] = sub
            l2, n2 = ndimage.label(sel, structure=EIGHT)
            for j, s2 in enumerate(ndimage.find_objects(l2), 1):
                c = l2 == j
                P = float(np.median(local.period[c]))
                h, w = s2[0].stop - s2[0].start, s2[1].stop - s2[1].start
                out.append((c, P, w >= 3 * P and h >= 2 * P))
    return out


def measure(local, area, Pbank, abank):
    h = area[:, :-1] & area[:, 1:]
    v = area[:-1, :] & area[1:, :]
    if h.sum() < 8 or v.sum() < 8:
        return Pbank, abank
    b = local.response
    cx = (b[:, 1:] * np.conj(b[:, :-1]))[h].sum()
    cy = (b[1:, :] * np.conj(b[:-1, :]))[v].sum()
    fx, fy = np.angle(cx) / (2 * np.pi), np.angle(cy) / (2 * np.pi)
    f = np.hypot(fx, fy)
    return (1 / f, float(np.degrees(np.arctan2(fy, fx)))) if f > 0 else (Pbank, abank)


def grow(spec, local, light, core, Pb, frac, cap):
    peak = np.unravel_index(np.argmax(np.where(core, local.ratio, -1)), core.shape)
    P, a = measure(local, core, Pb, float(local.angle_deg[peak]))
    tuned, mean = spec.gabor(P, a), spec.local_mean(P)
    depth = 2 * np.abs(tuned) / np.maximum(np.abs(mean), 1e-300)
    lvl = frac * np.median(depth[core])
    cand = (depth >= lvl) & light
    if cap is not None:
        cand &= ndimage.distance_transform_edt(~core) <= cap * P
    lab, _ = ndimage.label(cand | core, structure=EIGHT)
    keep = np.isin(lab, np.unique(lab[core])) & (lab > 0)
    return keep, P, a


VARIANTS = [(0.5, 2.0), (0.5, 4.0), (0.5, None), (0.4, 2.0), (0.6, 2.0)]


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def job(args):
    seed, (P, ang), shape, (ra, ca), tag = args
    f, truth = make_frame(seed, P, ang, shape, ra, ca)
    env = gaussian_filter(f, 10)
    light = env > 0.1 * env.max()
    local = estimate_local_stripes(f, light)
    cs = cores(local)
    passing = [(c, Pb) for c, Pb, ok in cs if ok]
    res = {"n_cores": len(cs), "n_pass": len(passing)}
    t0 = time.perf_counter()
    spec = _Spectrum(f)
    t_spec = time.perf_counter() - t0
    for frac, cap in VARIANTS:
        t0 = time.perf_counter()
        masks = [grow(spec, local, light, c, Pb, frac, cap) for c, Pb in passing]
        dt = time.perf_counter() - t0
        union = np.zeros(truth.shape, bool)
        for k, _, _ in masks:
            union |= k
        best = max((iou(k, truth) for k, _, _ in masks), default=0.0)
        Pest = [round(p, 2) for _, p, _ in masks]
        res[(frac, cap)] = (iou(union, truth), best, dt, Pest)
    res["t_spec"] = t_spec
    res["core_iou"] = iou(local.ratio > THRESHOLD, truth)
    return (P, tag), seed, res


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "main"
    jobs = []
    s = 410_000
    seeds_per = 8
    for c in CASES:
        P = c[0]
        for k in range(seeds_per):
            seed = s
            s += 1
            jobs.append((seed, c, (512, 512), (4 * P, 5.3 * P), "4Px5.3P"))
            jobs.append((seed, c, (512, 512), (max(4 * P, 45), max(5.3 * P, 60)), "floor45x60"))
            if P >= 12:
                jobs.append((seed, c, (512, 512), (5 * P, 6.6 * P), "5Px6.6P"))
    print("seeds", jobs[0][0], "..", jobs[-1][0])
    with ProcessPoolExecutor(12) as ex:
        out = list(ex.map(job, jobs))
    d = defaultdict(list)
    for key, seed, r in out:
        d[key].append((seed, r))
    for key in sorted(d):
        rows = d[key]
        print(f"\nP={key[0]} geom={key[1]}  n={len(rows)}  cores/pass={[ (r['n_cores'], r['n_pass']) for _, r in rows]}")
        print(f"   core(ratio>T) IoU median {np.median([r['core_iou'] for _, r in rows]):.3f}")
        for v in VARIANTS:
            un = np.array([r[v][0] for _, r in rows])
            be = np.array([r[v][1] for _, r in rows])
            tt = np.array([r[v][2] for _, r in rows])
            print(f"   frac={v[0]} cap={v[1]}: union IoU med {np.median(un):.3f} min {un.min():.3f} | best-region med {np.median(be):.3f} min {be.min():.3f} | grow s med {np.median(tt):.3f} max {tt.max():.3f}")
        worst = min(rows, key=lambda sr: sr[1][(0.5, 2.0)][0])
        print(f"   worst (0.5,2) seed {worst[0]} P_est {worst[1][(0.5, 2.0)][3]}")
    ts = [r["t_spec"] for _, _, r in out]
    print("\nshared _Spectrum 512x512 s median", round(float(np.median(ts)), 4))
