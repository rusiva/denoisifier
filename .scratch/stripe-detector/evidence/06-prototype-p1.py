"""PROTOTYPE (throwaway, ticket 06 plan review P1 + critic O1/Q8): spike recall and
false spike pixels of the plan's D5 per-pixel spike test.

Detector emulated (plan D5, with B3, N1, N2 and the critic's O1 applied):
  med   = median of the 6 column neighbours at rows +-1..3 (self excluded), mode "mirror"
  r     = frame - med
  s     = 1.4826 * median(|r|) over 16 px tiles, bilinear back to the frame
  scale = PEAK - percentile(median3(frame), 5)    (B3: above the baseline)
          PEAK = max of median3(frame) ("max3", the plan) or its 10th largest value ("rank10")
  spike = (r > K * s) & (r > FLOOR * scale), on every pixel, clipped or not (O1: no component rule)
Generator emulated (plan D1): `spikes` events of 1-3 px straight streaks (Bresenham-style, N1),
added brightness uniform(2, 10) x clean.max() per pixel, after the noise. The spike RNG is a local
np.random.default_rng((seed, 6)); generate() itself only ever sees the reserved prototype seeds.

Seeds: only range(396_000, 396_400) (plan section 4 reservation). No calibration seeds, no
700_000-700_005 / 700_100-700_139 (critic). Tolerance (fixed requirement): |reported - truth| <=
max(2, 0.05 * truth) per frame.

Run from a checkout root:  uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p1.py OUT.json
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
from scipy.ndimage import map_coordinates, median_filter

from denoisifier.frame_io import read_frame
from denoisifier.synthetic import Emccd, generate

PROTO = range(396_000, 396_400)
CASES = [(3, 10), (5, 0), (8, 6), (12, -8), (20, -10), (4, -4), (16, 10), (6, -10), (10, 3), (14, -6)]
N_SPIKES = 30
N_SEEDS = 40
GRID = [(k, f) for k in (8.0, 6.0, 5.0) for f in (0.5, 0.75, 1.0, 1.25)]
PEAKS = ("max3", "rank10")
EDGE_SHIFT = "--mirror-edges" not in sys.argv


def add_spikes(frame, clean, seed, n=N_SPIKES, bright=(2.0, 10.0)):
    rng = np.random.default_rng((seed, 6))
    rows, cols = frame.shape
    r0, c0 = rng.integers(0, rows, n), rng.integers(0, cols, n)
    lengths = rng.integers(1, 4, n)
    th = rng.uniform(0, np.pi, n)
    br = rng.uniform(*bright, size=(n, 3)) * clean.max()
    out, hit = frame.copy(), np.zeros(frame.shape, bool)
    for i in range(n):
        dr, dc = np.sin(th[i]), np.cos(th[i])
        m = max(abs(dr), abs(dc))
        for t in range(lengths[i]):
            rr, cc = int(round(r0[i] + t * dr / m)), int(round(c0[i] + t * dc / m))
            if 0 <= rr < rows and 0 <= cc < cols:
                out[rr, cc] += br[i, t]
                hit[rr, cc] = True
    return out, hit


def tile_scale(a, tile=16):
    rows, cols = a.shape
    ty, tx = -(-rows // tile), -(-cols // tile)
    pad = np.pad(a, ((0, ty * tile - rows), (0, tx * tile - cols)), mode="edge")  # no NaN: plain np.median
    med = np.median(pad.reshape(ty, tile, tx, tile).transpose(0, 2, 1, 3).reshape(ty, tx, -1), axis=2)
    yy = (np.arange(rows) + 0.5) / tile - 0.5
    xx = (np.arange(cols) + 0.5) / tile - 0.5
    Y, X = np.meshgrid(yy, xx, indexing="ij")
    return map_coordinates(med, [Y, X], order=1, mode="nearest")


def column_median(frame):
    """Median of the 6 column neighbours (rows +-1..3, self excluded). In the 3 rows at each
    edge the window shifts inward (rows 0..6 or R-7..R-1, self excluded) instead of mirroring,
    so a vertical streak at the edge is never its own neighbour (review N2)."""
    fp = np.ones((7, 1), bool)
    fp[3] = False
    med = median_filter(frame, footprint=fp, mode="mirror")
    R = frame.shape[0]
    if EDGE_SHIFT and R >= 7:
        for i in (0, 1, 2, R - 3, R - 2, R - 1):
            lo = 0 if i < 3 else R - 7
            idx = [j for j in range(lo, lo + 7) if j != i]
            med[i] = np.sort(frame[idx], axis=0)[3]  # upper middle, as scipy's rank for 6 values
    return med


def features(frame):
    med = column_median(frame)
    r = frame - med
    s = 1.4826 * tile_scale(np.abs(r))
    sm = median_filter(frame, 3, mode="mirror")
    base = np.percentile(sm, 5)
    flat = sm.ravel()
    peaks = {"max3": flat.max(), "rank10": np.partition(flat, flat.size - 10)[flat.size - 10]}
    return r, s, {p: peaks[p] - base for p in PEAKS}


def detect(feat, peak, k, floor):
    r, s, scale = feat
    return (r > k * s) & (r > floor * scale[peak])


def auto_plateau(frame, min_px=4):
    m = frame.max()
    eq = frame == m
    return eq if (eq.sum() >= min_px and frame.min() < m) else np.zeros(frame.shape, bool)


def within(rep, truth):
    return abs(rep - truth) <= max(2, 0.05 * truth)


# ---------- frame makers ----------
def emccd(ph, m, **kw):
    def make(seed):
        P, a = CASES[seed % 10]
        return generate(seed=seed, period=P, angle_deg=a, modulation_depth=m, mottle="scorched",
                        noise=Emccd(photons_peak=ph, **kw))
    return make


def gauss(noise, P, a, m):
    return lambda seed: generate(seed=seed, period=P, angle_deg=a, modulation_depth=m, noise=noise)


SPIKE_CONFIGS = {
    "emccd 10ph m0": emccd(10, 0.0),
    "emccd 10ph m.5": emccd(10, 0.5),
    "emccd 30ph m0": emccd(30, 0.0),
    "emccd 30ph m.5": emccd(30, 0.5),
    "typical 100ph m0": emccd(100, 0.0),
    "typical 100ph m.5": emccd(100, 0.5),
    "emccd 1000ph m.5": emccd(1000, 0.5),
    "emccd 5000ph m.5": emccd(5000, 0.5),
    "emccd int 100ph m.5": emccd(100, 0.5, em_gain=1.0, read_noise_e=0.0),
    "gauss .01 P3 +10 m.5": gauss(0.01, 3, 10, 0.5),
    "gauss .01 P20 -10 m.5": gauss(0.01, 20, -10, 0.5),
    "gauss 0 P3 +10 m1": gauss(0.0, 3, 10, 1.0),
    "gauss 0 P3 -10 m1": gauss(0.0, 3, -10, 1.0),
    "gauss 0 P20 +10 m1": gauss(0.0, 20, 10, 1.0),
}


def seeds_for(ci):
    return [PROTO.start + (ci * 23 + i) % len(PROTO) for i in range(N_SEEDS)]


def run_spikes(name, make, ci, *, bright=(2.0, 10.0), clip_factor=None):
    """Per (peak, k, floor): truth/recall, frames over tolerance, FP on the spike-free twin.
    With clip_factor: frame (spiked) clipped at clip_factor * clean.max(); truth = every hit pixel
    is a spike (O1), expected clipped report = plateau pixels not flagged = 0."""
    out = {f"{p} {k:g}/{f:g}": dict(truth=0, tp=0, over=0, worst=0, fp_free=[], clipped_rep=[], sat=0)
           for p in PEAKS for k, f in GRID}
    for seed in seeds_for(ci):
        assert seed in PROTO
        syn = make(seed)
        spk, hit = add_spikes(syn.frame, syn.clean, seed, bright=bright)
        free = syn.frame
        if clip_factor is not None:
            C = clip_factor * syn.clean.max()
            spk, free = np.minimum(spk, C), np.minimum(free, C)
        ff, fs = features(free), features(spk)
        plateau = auto_plateau(spk) if clip_factor is not None else None
        for p in PEAKS:
            for k, f in GRID:
                a = out[f"{p} {k:g}/{f:g}"]
                det = detect(fs, p, k, f)
                t = int(hit.sum())
                a["truth"] += t
                a["tp"] += int((det & hit).sum())
                a["over"] += not within(int(det.sum()), t)
                a["worst"] = max(a["worst"], abs(int(det.sum()) - t))
                a["fp_free"].append(int(detect(ff, p, k, f).sum()))
                if plateau is not None:
                    a["clipped_rep"].append(int((plateau & ~det).sum()))
                    a["sat"] += int(plateau.sum())
    res = {}
    for key, a in out.items():
        res[key] = dict(recall=a["tp"] / a["truth"], truth_px=a["truth"], over_tol=a["over"], frames=N_SEEDS,
                        worst_abs_diff=a["worst"], fp_free_mean=float(np.mean(a["fp_free"])),
                        fp_free_max=max(a["fp_free"]), fp_free_frames_nonzero=sum(x > 0 for x in a["fp_free"]))
        if clip_factor is not None:
            res[key].update(clipped_reported_max=max(a["clipped_rep"]), saturated_px_total=a["sat"])
    return res


def phase_break_frames():
    """Noise-0 frames whose lower half is rolled sideways (a hand-made Phase Break)."""
    seed_iter = iter(range(396_300, 396_400))
    for P in (3, 4, 5, 8, 12, 20):
        for a in (0, 10, -10):
            for m in (1.0, 0.5):
                for mottle in ("none", "scorched"):
                    seed = next(seed_iter, None) or 396_399
                    syn = generate(seed=seed, period=P, angle_deg=a, modulation_depth=m, mottle=mottle, noise=0.0)
                    for shift in sorted({1, int(round(P / 2)), int(round(P / 3)) or 1}):
                        f = syn.frame.copy()
                        h = f.shape[0] // 2
                        f[h:] = np.roll(f[h:], shift, axis=1)
                        yield dict(P=P, angle=a, m=m, mottle=mottle, shift=shift, seed=seed), f


def table(title, res):
    lines = [f"\n== {title}", f"  {'detector':16} recall  over-tol  worst  FP-free mean/max (frames>0)"]
    for key, v in res.items():
        extra = f"  clipped_rep_max {v['clipped_reported_max']} sat_px {v['saturated_px_total']}" if "clipped_reported_max" in v else ""
        lines.append(f"  {key:16} {v['recall']:.4f}  {v['over_tol']:2d}/{v['frames']}   {v['worst_abs_diff']:4d}   "
                     f"{v['fp_free_mean']:6.2f} / {v['fp_free_max']:3d} ({v['fp_free_frames_nonzero']}){extra}")
    print("\n".join(lines), flush=True)


def main():
    out_path = sys.argv[1]
    print("edge windows:", "shifted inward" if EDGE_SHIFT else "mirror")
    result = {"seeds": [PROTO.start, PROTO.stop], "n_seeds_per_config": N_SEEDS, "spikes": N_SPIKES, "grid": GRID}
    t0 = time.time()
    result["spikes_2_10"] = {}
    for ci, (name, make) in enumerate(SPIKE_CONFIGS.items()):
        result["spikes_2_10"][name] = r = run_spikes(name, make, ci)
        table(name, r)
    result["boundary_2_2.2"] = {}
    for ci, name in enumerate(("emccd 30ph m.5", "typical 100ph m.5", "emccd 5000ph m.5", "gauss 0 P3 -10 m1")):
        result["boundary_2_2.2"][name] = r = run_spikes(name, SPIKE_CONFIGS[name], 20 + ci, bright=(2.0, 2.2))
        table(f"BOUNDARY brightness 2.0-2.2x: {name}", r)
    result["clip_3x"] = {}
    for ci, name in enumerate(("emccd 30ph m.5", "typical 100ph m0", "typical 100ph m.5", "gauss .01 P3 +10 m.5")):
        result["clip_3x"][name] = r = run_spikes(name, SPIKE_CONFIGS[name], 30 + ci, clip_factor=3.0)
        table(f"CLIP at 3x clean max (spikes saturate): {name}", r)

    print("\n== PHASE BREAK frames (noise 0, lower half rolled sideways): false spike pixels")
    pb = {f"{p} {k:g}/{f:g}": [] for p in PEAKS for k, f in GRID}
    worst = {}
    nframes = 0
    for meta, f in phase_break_frames():
        nframes += 1
        ft = features(f)
        for p in PEAKS:
            for k, fl in GRID:
                n = int(detect(ft, p, k, fl).sum())
                key = f"{p} {k:g}/{fl:g}"
                pb[key].append(n)
                if n > worst.get(key, (0,))[0]:
                    worst[key] = (n, meta)
    result["phase_break"] = {k: dict(frames=nframes, total_fp=sum(v), frames_nonzero=sum(x > 0 for x in v),
                                     worst=worst.get(k)) for k, v in pb.items()}
    for k, v in result["phase_break"].items():
        print(f"  {k:16} frames {v['frames']}  total FP {v['total_fp']}  frames>0 {v['frames_nonzero']}  worst {v['worst']}")

    print("\n== Solis crop (bias ~713; flagged pixels; no truth)")
    fr = np.asarray(read_frame("tests/data/solis/xpos_ypos_crop.asc").frame, float)
    result["solis"] = {}
    for shift, f2 in (("raw", fr), ("+1000", fr + 1000), ("-median/2", fr - np.median(fr) / 2)):
        ft = features(f2)
        result["solis"][shift] = {f"{p} {k:g}/{f:g}": int(detect(ft, p, k, f).sum()) for p in PEAKS for k, f in GRID}
        print(f"  {shift}: max flagged over grid = {max(result['solis'][shift].values())}")

    syn = generate(seed=PROTO.start + 399, shape=(400, 1600), period=8, mottle="scorched", noise=Emccd())
    ts = []
    for _ in range(7):
        t1 = time.perf_counter()
        detect(features(syn.frame), "rank10", 8.0, 1.0)
        ts.append(time.perf_counter() - t1)
    result["timing_400x1600_s"] = float(np.median(ts))
    print(f"\n== timing 400x1600 features+detect: median {np.median(ts):.3f} s   (total run {time.time() - t0:.0f} s)")
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
