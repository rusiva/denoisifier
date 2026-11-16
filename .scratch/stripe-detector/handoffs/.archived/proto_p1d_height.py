"""PROTOTYPE (throwaway), ticket 05 P1 option D: height from a separate short-along filter.

Detection bank unchanged. For the size test, re-tune one extra filter at the
core's measured Period/Angle with sigma_along = SA * P (SA in 0.5, 0.75, 1.0;
1.5 = today's window, for comparison) and take the sub-pixel half-peak height
of its depth map along the column through its depth peak on the core. Width
is the P1 measure (standard window, row through the depth peak).

Shapes: "both" semi_axes (f*P, 1.5*f*P) (2fP tall, 3fP wide); "short"
semi_axes (g*P, 2*P) (2gP tall, 4P wide). f, g in 0.8, 1.0, 1.25, 1.4.

usage: python proto_p1d_height.py REGIME SEED_START   (REGIME: low | typical)
"""

import pickle
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from denoisifier._local_stripes import _ACROSS, _Spectrum, estimate_local_stripes
from denoisifier.synthetic import Emccd, _emccd, generate

T = 154.0
SHAPE = (256, 256)
PERIODS = (3, 5, 8, 12, 20)
ANGLES = (-10.0, 0.0, 10.0)
FACTORS = (0.8, 1.0, 1.25, 1.4)
SAS = (0.5, 0.75, 1.0, 1.5)
M = 0.6
S = "/tmp/claude-1000/-home-rusiva-dev-denoisifier/72618a23-dbd5-4573-9e6c-b83c3532a4a4/scratchpad/"


def window(across, along, period, sa):
    return np.exp(-0.5 * ((across * 2 * np.pi * _ACROSS * period) ** 2 + (along * 2 * np.pi * sa * period) ** 2))


def tuned_depth(spec, period, angle_deg, sa):
    t = np.deg2rad(angle_deg)
    across = spec.fx * np.cos(t) + spec.fy * np.sin(t) - 1.0 / period
    along = -spec.fx * np.sin(t) + spec.fy * np.cos(t)
    resp = spec.filtered(window(across, along, period, sa))
    mean = np.real(spec.filtered(window(spec.fx, spec.fy, period, sa)))
    d = np.zeros(resp.shape)
    np.divide(2 * np.abs(resp), np.abs(mean), out=d, where=np.abs(mean) > 0)
    return d


def frame(seed, P, ang, shape_kind, f, regime):
    mottle = "none" if regime == "low" else "scorched"
    env = generate(seed=seed, shape=SHAPE, modulation_depth=0.0, mottle=mottle, noise=0.0).clean
    rng = np.random.default_rng(seed + 11)
    cy, cx = 128 + rng.uniform(-0.5, 0.5), 128 + rng.uniform(-0.5, 0.5)
    ph0 = rng.uniform(0, 2 * np.pi)
    y, x = np.mgrid[0 : SHAPE[0], 0 : SHAPE[1]].astype(float)
    a, b = (f * P, 1.5 * f * P) if shape_kind == "both" else (f * P, 2.0 * P)
    r = np.sqrt(((y - cy) / a) ** 2 + ((x - cx) / b) ** 2)
    w = 1.0 / (2 * np.arctanh(0.8))
    mask = 0.5 * (1 - np.tanh((r - 1) * min(a, b) / w))
    t = np.deg2rad(ang)
    clean = env * (1 + M * mask * np.cos(2 * np.pi / P * (x * np.cos(t) + y * np.sin(t)) + ph0))
    if regime == "low":
        return clean + rng.normal(0, 0.01 * 1000.0, clean.shape)
    return _emccd(rng, clean / clean.max() * 100, Emccd())


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


def job(arg):
    seed, P, ang, kind, f, regime = arg
    fr = frame(seed, P, ang, kind, f, regime)
    sm = gaussian_filter(fr, 10)
    light = sm > 0.1 * sm.max()
    loc = estimate_local_stripes(fr, light)
    out = {"max_ratio": float(loc.ratio.max())}
    if loc.ratio.max() <= T:
        return (P, ang, kind, f), out
    peak = np.unravel_index(np.argmax(loc.ratio), loc.ratio.shape)
    lab, _ = ndimage.label(loc.ratio > T, structure=np.ones((3, 3)))
    core = lab == lab[peak]
    pe, ae = fine_period(loc, core, (float(loc.period[peak]), float(loc.angle_deg[peak])))
    out["P_est"] = pe
    spec = _Spectrum(fr)
    for sa in SAS:
        d = np.where(light, tuned_depth(spec, pe, ae, sa), 0.0)
        dc = np.where(core, d, -1)
        pr, pc = np.unravel_index(np.argmax(dc), dc.shape)
        lvl = 0.5 * d[pr, pc]
        out[("h", sa)] = span(d[:, pc], pr, lvl) / pe
        if sa == 1.5:
            out["w"] = span(d[pr, :], pc, lvl) / pe
    return (P, ang, kind, f), out


def timing():
    rng = np.random.default_rng(0)
    for shp in ((256, 256), (400, 1600)):
        fr = rng.random(shp)
        t0 = time.perf_counter()
        spec = _Spectrum(fr)
        t1 = time.perf_counter()
        for _ in range(5):
            tuned_depth(spec, 8.0, 3.0, 0.75)
        t2 = time.perf_counter()
        print(f"timing {shp}: _Spectrum {1e3 * (t1 - t0):.1f} ms, extra filter on a shared spectrum {1e3 * (t2 - t1) / 5:.1f} ms per candidate")


if __name__ == "__main__":
    regime, start = sys.argv[1], int(sys.argv[2])
    seeds = range(start, start + 8)
    print(f"regime {regime} seeds {seeds.start}-{seeds.stop - 1}")
    timing()
    jobs = [(s, P, a, k, f, regime) for s in seeds for P in PERIODS for a in ANGLES for k in ("both", "short") for f in FACTORS]
    with ProcessPoolExecutor(14) as ex:
        res = list(ex.map(job, jobs, chunksize=4))
    d = defaultdict(list)
    for k, o in res:
        d[k].append(o)
    with open(f"{S}p1d_{regime}_{start}.pkl", "wb") as fh:
        pickle.dump(dict(d), fh)
    print("done")
