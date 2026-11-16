"""PROTOTYPE (throwaway) for ticket stripe-detector/05, plan-review item P1.

Question: is there a blur-corrected size rule that separates a region at
0.8x the 3x2-Period minimum from one at 1.25x / 1.4x, on every Period and
Angle, at mottle "none", Gaussian noise 0.01, m 0.6?

Frames: profile from generate(seed, m=0, mottle, noise=0).clean (256x256),
times (1 + m * mask * cos(phase)), plan 2.1 tanh mask, edge_px 1, semi-axes
(f*P, 1.5*f*P) -> 0.5-contour bbox 2fP tall x 3fP wide. Random stripe phase
and sub-pixel centre jitter per seed. Seeds 390_000.. (outside every
registered range and the reviewer's N8 list).

Measures per frame (all bbox h, w in units of the detector's own Period):
  core   : the ratio > T component holding the ratio peak (Q2-A)
  hd_med : core grown to re-tuned depth >= 0.5 * median depth on the core,
           within light and a 2P dilation of the core (plan 2.3 step 2, Q2-B)
  hd_pk  : same with 0.5 * max depth on the core (half of the region's peak)
The Period/Angle used for re-tuning and for normalising is the core's
neighbour-product estimate (same sum as analysis._measure).

Run: uv run --locked python <this file> [noise] [mottle]
"""

import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from denoisifier._local_stripes import estimate_local_stripes, gabor_at
from denoisifier.synthetic import generate

T = 154.0
SHAPE = (256, 256)
PERIODS = (3, 5, 8, 12, 20)
ANGLES = (-10.0, 0.0, 10.0)
FACTORS = (0.6, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4)
SEEDS = range(int(sys.argv[4]) if len(sys.argv) > 4 else 390_000, (int(sys.argv[4]) if len(sys.argv) > 4 else 390_000) + 8)
M = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6
if len(sys.argv) > 5:
    FACTORS = (0.8, 1.0, 1.25, 1.4)


def frame(seed, P, ang, f, noise, mottle):
    env = generate(seed=seed, shape=SHAPE, modulation_depth=0.0, mottle=mottle, noise=0.0).clean
    rng = np.random.default_rng(seed + 11)
    cy, cx = 128 + rng.uniform(-0.5, 0.5), 128 + rng.uniform(-0.5, 0.5)
    ph0 = rng.uniform(0, 2 * np.pi)
    y, x = np.mgrid[0 : SHAPE[0], 0 : SHAPE[1]].astype(float)
    a, b = f * P, 1.5 * f * P
    r = np.sqrt(((y - cy) / a) ** 2 + ((x - cx) / b) ** 2)
    w = 1.0 / (2 * np.arctanh(0.8))  # edge_px = 1
    mask = 0.5 * (1 - np.tanh((r - 1) * min(a, b) / w))
    t = np.deg2rad(ang)
    clean = env * (1 + M * mask * np.cos(2 * np.pi / P * (x * np.cos(t) + y * np.sin(t)) + ph0))
    return clean + rng.normal(0, noise * 1000.0, clean.shape)


def fine_period(local, area, fallback):
    h = area[:, :-1] & area[:, 1:]
    v = area[:-1, :] & area[1:, :]
    if h.sum() < 4 or v.sum() < 4:
        return fallback
    bank = local.response
    cx = (bank[:, 1:] * np.conj(bank[:, :-1]))[h].sum()
    cy = (bank[1:, :] * np.conj(bank[:-1, :]))[v].sum()
    fx, fy = np.angle(cx) / (2 * np.pi), np.angle(cy) / (2 * np.pi)
    fr = np.hypot(fx, fy)
    return (1 / fr, float(np.degrees(np.arctan2(fy, fx)))) if fr > 0 else fallback


def span(line, i0, lvl):
    def edge(step):
        i = i0
        while 0 <= i + step < len(line) and line[i + step] >= lvl:
            i += step
        if not 0 <= i + step < len(line):
            return float(i)
        a, b = line[i], line[i + step]
        return i + step * (a - lvl) / (a - b)
    return edge(1) - edge(-1)


def bbox(m):
    rows, cols = np.nonzero(m)
    return rows.max() - rows.min() + 1, cols.max() - cols.min() + 1


def job(arg):
    seed, P, ang, f, noise, mottle = arg
    fr = frame(seed, P, ang, f, noise, mottle)
    sm = gaussian_filter(fr, 10)
    light = sm > 0.1 * sm.max()
    loc = estimate_local_stripes(fr, light)
    out = {"max_ratio": float(loc.ratio.max())}
    if loc.ratio.max() <= T:
        return (P, ang, f), out
    peak = np.unravel_index(np.argmax(loc.ratio), loc.ratio.shape)
    lab, _ = ndimage.label(loc.ratio > T, structure=np.ones((3, 3)))
    core = lab == lab[peak]
    pe, ae = fine_period(loc, core, (float(loc.period[peak]), float(loc.angle_deg[peak])))
    out["P_est"] = pe
    h, w = bbox(core)
    out["core"] = (h / pe, w / pe)
    tuned, mean = gabor_at(fr, pe, ae)
    depth = np.zeros(fr.shape)
    np.divide(2 * np.abs(tuned), np.abs(mean), out=depth, where=light & (np.abs(mean) > 0))
    near = ndimage.binary_dilation(core, iterations=max(1, round(2 * pe))) & light
    for name, lvl in (("hd_med", 0.5 * np.median(depth[core])), ("hd_pk", 0.5 * depth[core].max())):
        lab2, _ = ndimage.label((depth >= lvl) & near, structure=np.ones((3, 3)))
        grown = np.isin(lab2, np.unique(lab2[core])) & (lab2 > 0)
        h, w = bbox(grown)
        out[name] = (h / pe, w / pe)
    # Sub-pixel half-peak extent: linear-interpolated crossings of 0.5 * peak
    # depth along the row and the column through the depth peak on the core.
    dc = np.where(core, depth, -1)
    pr, pc = np.unravel_index(np.argmax(dc), dc.shape)
    lvl = 0.5 * depth[pr, pc]
    out["hd_sub"] = (span(depth[:, pc], pr, lvl) / pe, span(depth[pr, :], pc, lvl) / pe)
    return (P, ang, f), out


def analytic_reference():
    """Noise-free, flat envelope, no Mottle: half-peak bbox of |mask (*) window|, in Periods."""
    res = {}
    for P in PERIODS:
        n = 512
        y, x = np.mgrid[0:n, 0:n].astype(float)
        a, b = P, 1.5 * P
        r = np.sqrt(((y - 256) / a) ** 2 + ((x - 256) / b) ** 2)
        w = 1.0 / (2 * np.arctanh(0.8))
        mask = 0.5 * (1 - np.tanh((r - 1) * min(a, b) / w))
        fr = 1000 * (1 + M * mask * np.cos(2 * np.pi / P * x))
        tuned, mean = gabor_at(fr, P, 0.0)
        d = 2 * np.abs(tuned) / mean
        hh, ww = bbox(d >= 0.5 * d.max())
        res[P] = (hh / P, ww / P)
    return res


if __name__ == "__main__":
    noise = float(sys.argv[1]) if len(sys.argv) > 1 else 0.01
    mottle = sys.argv[2] if len(sys.argv) > 2 else "none"
    print(f"noise {noise} mottle {mottle} m {M} seeds {SEEDS.start}-{SEEDS.stop - 1}")
    print("analytic half-peak bbox (h, w) in P of an exactly 3x2-P region:", analytic_reference())
    jobs = [(s, P, a, f, noise, mottle) for s in SEEDS for P in PERIODS for a in ANGLES for f in FACTORS]
    with ProcessPoolExecutor(14) as ex:
        res = list(ex.map(job, jobs, chunksize=4))
    d = defaultdict(list)
    for k, o in res:
        d[k].append(o)
    import pickle

    with open(f"/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/p1_{mottle}_{noise}_{M}.pkl", "wb") as fh:
        pickle.dump(dict(d), fh)
    for k in sorted(d):
        os_ = d[k]
        det = sum("core" in o for o in os_)
        line = [f"P{k[0]:>2} A{k[1]:+4.0f} f{k[2]:.2f} det {det}/{len(os_)} maxr {min(o['max_ratio'] for o in os_):.0f}-{max(o['max_ratio'] for o in os_):.0f}"]
        for name in ("core", "hd_med", "hd_pk", "hd_sub"):
            v = np.array([o[name] for o in os_ if name in o])
            if len(v):
                line.append(f"{name} h {v[:, 0].min():.2f}-{v[:, 0].max():.2f} w {v[:, 1].min():.2f}-{v[:, 1].max():.2f}")
        print(" | ".join(line))
