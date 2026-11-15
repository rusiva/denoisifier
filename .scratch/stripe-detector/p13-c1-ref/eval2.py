"""PROTOTYPE (ticket 09, P1-2) -- throwaway. Run the scope-C post pass on a BASE cache from
harness2.py and score it. Usage:
  uv run --locked python prototypes/p09_breaks/eval2.py <base.pkl> '<json post overrides>' '<json finder overrides>' [tag-prefix filter]
"""

import collections
import json
import math
import pickle
import sys
import time
from multiprocessing import Pool
from types import SimpleNamespace

import numpy as np

import denoisifier.analysis as A
import finder as F
import harness2 as H
import post as PP
from denoisifier._data_quality import find_clipped, reject_spikes
from denoisifier._local_stripes import _Spectrum

TOL_P = 1.0
JUMP_TOL = math.pi / 4
COVER_MIN = 0.6
ANGLE_TOL = 1.0
IOU_MIN = 0.8
SIDE_MIN = 0.5
SIDE_FAR_P = 2.5
LIT_SIGMA_PX = 10.0  # v2: generator-side lit mask, one fixed sigma (critic 3, section 2)
LIT_LEVEL = 0.1
DEPTH_TOL = 0.1


def canon(a, j):
    if a > 90:
        a, j = a - 180, -j
    elif a <= -90:
        a, j = a + 180, -j
    return a, float(F.wrap(j))


def unpack(b, shape):
    return np.unpackbits(b, count=shape[0] * shape[1]).reshape(shape).astype(bool)


def match(found, tb, mask, period, bins, over_mask=None):
    h, v = bins
    Yt, Xt, a, j = tb
    a, j = canon(a, j)
    t = math.radians(a)
    if found.get("segment") is None:
        return dict(ok=False, why="no segment")
    P0, P1 = (np.array(p) for p in found["segment"])
    L = np.linalg.norm(P1 - P0)
    k = np.linspace(0, 1, max(2, int(L) + 1))
    pts = P0[None] + k[:, None] * (P1 - P0)[None]
    dist = np.abs(math.cos(t) * (pts[:, 0] - Yt) - math.sin(t) * (pts[:, 1] - Xt))
    line_err = float(dist.max() / period)
    rr, cc = np.nonzero(mask)
    Ym, Xm = rr * v, cc * h
    s = math.cos(t) * (Ym - Yt) - math.sin(t) * (Xm - Xt)
    on = np.abs(s) <= 0.5 * max(h, v)
    um = math.cos(t) * (Xm - Xt) + math.sin(t) * (Ym - Yt)
    ch = (um[on].min(), um[on].max())
    u = math.cos(t) * (pts[:, 1] - Xt) + math.sin(t) * (pts[:, 0] - Yt)
    cover = max(0.0, min(u.max(), ch[1]) - max(u.min(), ch[0])) / (ch[1] - ch[0])
    if over_mask is not None:  # v2: overshoot against the generator's stripe extent
        ro, co = np.nonzero(over_mask)
        so = math.cos(t) * (ro * v - Yt) - math.sin(t) * (co * h - Xt)
        uo = math.cos(t) * (co * h - Xt) + math.sin(t) * (ro * v - Yt)
        ono = np.abs(so) <= 0.5 * max(h, v)
        cho = (uo[ono].min(), uo[ono].max())
    else:
        cho = ch
    over = max(cho[0] - u.min(), u.max() - cho[1], 0.0) / period
    fj = found["jump"]
    if math.cos(math.radians(found["angle"] - a)) < 0:  # direction only (critic 2, 3.2)
        fj = -fj
    jerr = abs(float(F.wrap(fj - j)))
    return dict(line_err=line_err, cover=cover, over=over, jump_err=jerr, angle_found=found["angle"],
                ok=line_err <= TOL_P and cover >= COVER_MIN and over <= TOL_P and jerr <= JUMP_TOL)


def both_sides(region, T, tb, period, bins):
    h, v = bins
    Yt, Xt, a, _ = tb
    t = math.radians(a)
    rr, cc = np.nonzero(T)
    s = math.cos(t) * (rr * v - Yt) - math.sin(t) * (cc * h - Xt)
    far = np.abs(s) > SIDE_FAR_P * period
    inr = region[rr, cc]
    out = []
    for sgn in (1, -1):
        sel = far & (sgn * s > 0)
        out.append(float(inr[sel].mean()) if sel.any() else 0.0)  # v2: an empty side fails
    return min(out)


def evaluate(args):
    res, prm, fprm = args
    job = res["job"]
    frame, s, _, bins = H.generate_job(job)
    shape = frame.shape
    work, spikes = reject_spikes(frame)
    clipped = find_clipped(frame, None) & ~spikes
    light = A._light(work)
    spec = _Spectrum(work, A.BinFactors(horizontal=bins[0], vertical=bins[1]))
    surv = [SimpleNamespace(**dict(g, pixels=unpack(g["pixels"], shape))) for g in res["survivors"]]
    o = PP.run(work, light, clipped, spec, bins, surv, res["threshold"], prm, fprm)
    period = job.get("period", res["case"][0])
    true_angle = job.get("angle", res["case"][1])
    if o.changed:
        regs = [dict(pixels=r["pixels"], period=r["period"], angle=r["angle_deg"], depth=r["depth"],
                     breaks=r["breaks"], merged=r["merged"]) for r in o.regions]
    else:
        rep = [g for g in surv if g.peak_ratio > res["threshold"]]
        regs = [dict(pixels=g.pixels, period=g.period, angle=g.angle_deg, depth=g.depth, breaks=[], merged=False)
                for g in rep]
    out = dict(tag=job["tag"], seed=job["seed"], job=job, case=res["case"], striped=res["striped"],
               n_base=res["n_regions"], n=len(regs), changed=o.changed, t_post=o.t, r2=o.r2,
               n_breaks=len(o.breaks), bridges=o.bridges, merged=any(r["merged"] for r in regs),
               t_analyse=res["t_analyse"])
    out["warnings"] = len(o.warnings)
    out["absorbed"] = o.absorbed
    out["bridges2_ok"] = sum(b["ok"] for b in o.bridges2)
    out["all_breaks"] = [(round(f["E"], 3), round(f.get("coh", -1), 3)) for f in o.breaks]
    if job["kind"] == "two":
        out["n_true"] = len(res["truth_regions"])
    if "truth" in res:
        T = unpack(res["truth"], shape)
        over_mask = None
        if job["kind"] == "full":  # v2: cover vs generator lit mask (fixed sigma), overshoot vs the frame
            from scipy.ndimage import gaussian_filter
            c = gaussian_filter(s.clean, LIT_SIGMA_PX)
            if tuple(bins) != (1, 1):
                c = c.reshape(shape[0], bins[1], shape[1], bins[0]).mean(axis=(1, 3))
            T = c >= LIT_LEVEL * c.max()
            over_mask = np.ones(shape, bool)
        if regs:
            main = max(regs, key=lambda r: (r["pixels"] & T).sum())
            out["angle_err"] = abs((main["angle"] - true_angle + 90) % 180 - 90)
            out["period_err"] = abs(main["period"] / period - 1)
            out["depth"] = main["depth"]
            true_depth = job.get("depth", 0.5)
            out["depth_err"] = abs(main["depth"] - true_depth)
            mb = max((g for g in surv if g.peak_ratio > res["threshold"]), key=lambda g: (g.pixels & T).sum(), default=None)
            if mb is not None:
                out["base_depth_err"] = abs(mb.depth - true_depth)
                out["base_angle_err"] = abs((mb.angle_deg - true_angle + 90) % 180 - 90)
            if o.changed:
                mr = max(o.regions, key=lambda r: (r["pixels"] & T).sum())
                out["rm"] = mr["rm"]
            union = np.logical_or.reduce([r["pixels"] for r in regs])
            if job["kind"] in ("region", "small"):
                out["iou"] = float((union & T).sum() / (union | T).sum())
                out["base_iou"] = float((unpack(res["base_labels"], shape) & T).sum()
                                        / (unpack(res["base_labels"], shape) | T).sum())
            ms = []
            for tb in res["true_breaks"]:
                cand = [dict(match(f, tb, T, period, bins, over_mask), E=f["E"], coh=f.get("coh", -1)) for f in main["breaks"]]
                good = [m for m in cand if m["ok"]]
                best = min(cand, key=lambda m: (not m["ok"], m.get("line_err", 9) + m.get("jump_err", 9))) if cand else dict(ok=False, why="none")
                best = dict(best)
                best["unique"] = len(good) == 1 and len(main["breaks"]) == len(res["true_breaks"])
                if True:
                    best["sides"] = both_sides(main["pixels"], T, tb, period, bins)
                ms.append(best)
            out["matches"] = ms
            out["found_ok"] = bool(ms) and all(m["unique"] for m in ms)
            if res["true_breaks"]:
                out["ac4"] = bool(res["striped"] and len(regs) == 1 and min(m["sides"] for m in ms) >= SIDE_MIN)
        else:
            out["found_ok"] = False
            out["ac4"] = False
    return out


def run_all(results, prm, fprm, procs=15):
    with Pool(procs) as pool:
        return pool.map(evaluate, [(r, prm, fprm) for r in results], chunksize=2)


def cell(e):
    j = e["job"]
    if e["tag"] == "ac2":
        return f"ac2 j={j['breaks'][0][2]:+.2f}"
    if e["tag"] == "ac3":
        return f"ac3 a={j['breaks'][0][1]:+.0f} j={j['breaks'][0][2]:.2f}"
    return e["tag"]


def table(ev):
    rows = collections.OrderedDict()
    for e in sorted(ev, key=cell):
        d = rows.setdefault(cell(e), collections.Counter())
        d["n"] += 1
        d["found"] += e.get("found_ok", False)
        d["ac4"] += e.get("ac4", False)
        d["iou<0.8"] += e.get("iou", 1.0) < IOU_MIN
        d["ang>1"] += e.get("angle_err", 0) > ANGLE_TOL
        d["per>5%"] += e.get("period_err", 0) > 0.05
        d["changed"] += e["changed"]
        d["merged"] += e["merged"]
        d["r2"] += e["r2"] > 0
        d["nreg!=1"] += e["n"] != 1
    return rows


def print_table(ev):
    rows = table(ev)
    keys = ["n", "found", "ac4", "iou<0.8", "ang>1", "per>5%", "changed", "merged", "r2", "nreg!=1"]
    print(f"{'cell':26s} " + " ".join(f"{k:>8s}" for k in keys))
    for c, d in rows.items():
        print(f"{c:26s} " + " ".join(f"{d[k]:8d}" for k in keys))
    brk = [e for e in ev if e["tag"] in ("ac2", "ac3")]
    if brk:
        print("max angle err on break frames %.2f; min iou %.3f; max line err %.2f" % (
            max(e.get("angle_err", 0) for e in brk), min(e.get("iou", 1) for e in brk),
            max((m.get("line_err", 0) for e in brk for m in e.get("matches", [])), default=0)))
    tp = [e["t_post"] for e in ev]
    print("t_post mean %.3f p95 %.3f max %.3f" % (np.mean(tp), np.percentile(tp, 95), np.max(tp)))


def failures(ev):
    for e in ev:
        if (e["tag"] in ("ac2", "ac3", "full_break", "split") or e["tag"].startswith(("bin", "pair"))) and not (e.get("found_ok") and e.get("ac4", True)
                                                              and e.get("angle_err", 0) <= ANGLE_TOL
                                                              and e.get("iou", 1) >= IOU_MIN):
            ms = [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items()} for m in e.get("matches", [])]
            print(cell(e), e["seed"], e["case"], "n", e["n"], "found", e.get("found_ok"), "ac4", e.get("ac4"),
                  "ang %.2f iou %.3f" % (e.get("angle_err", -1), e.get("iou", -1)), ms)
        if e["tag"] in ("free", "free_ms", "full_free", "two_free") and e["changed"]:
            print("CHANGED", e["tag"], e["seed"], e["case"], e["n_breaks"], e["merged"])


if __name__ == "__main__":
    results = pickle.load(open(sys.argv[1], "rb"))
    prm = dict(PP.POST)
    fprm = dict(F.FINDER)
    if len(sys.argv) > 2:
        prm.update(json.loads(sys.argv[2]))
    if len(sys.argv) > 3:
        fprm.update(json.loads(sys.argv[3]))
    if len(sys.argv) > 4:
        results = [r for r in results if r["job"]["tag"].startswith(tuple(sys.argv[4].split(",")))]
    t = time.time()
    ev = run_all(results, prm, fprm)
    print("post", prm, "\nfinder", fprm, "\ntime", round(time.time() - t, 1))
    print_table(ev)
    failures(ev)
    tagname = sys.argv[5] if len(sys.argv) > 5 else "last"
    pickle.dump(ev, open(sys.argv[1] + f".{tagname}.eval.pkl", "wb"))
