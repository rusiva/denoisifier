"""PROTOTYPE (throwaway): summarise 06-prototype-p2.py output.
Usage: python 06-prototype-p2-summary.py guard.json free.json rule.json"""

import json
import sys
from collections import defaultdict

import numpy as np

TOL = 0.1
VARS = ["plain", "d9_plan", "d9_gauss02", "d9_inner_box", "d9_inner_g10", "fit_region", "fit_bbox", "local_fit", "local_cens"]


def val(g, v):
    if v == "plain":
        return g["plain"], False
    if v not in g:  # nothing clipped detected: every variant is the plain depth
        return g["plain"], False
    x = g[v]
    return (x["depth"], x["fallback"]) if isinstance(x, dict) else (x, False)


def guard(path):
    res = json.load(open(path))["results"]
    for kind in ("full", "partial"):
        print(f"\n=== guard, {kind} (truth m = 0.5; miss = |err| > {TOL}) ===")
        groups = defaultdict(list)
        for r in res:
            if r["kind"] == kind:
                groups[(r["photons"], "rule" if r["rule"] else r["frac"])].append(r)
        for key in sorted(groups, key=lambda k: (k[0], str(k[1]))):
            rs = groups[key]
            fr = np.array([r["frac"] for r in rs])
            regs = [g for r in rs for g in r["regions"]]
            pa_bad = sum(1 for r in rs if r["striped"] and not all(g["period_ok"] and g["angle_ok"] for g in r["regions"]))
            harm = sum(g["harmonic"] for g in regs)
            multi = sum(len(r["regions"]) > 1 for r in rs)
            nin0 = sum(r["truth_clipped_in_region"] == 0 for r in rs)
            print(f"{key[0]:6.0f} {str(key[1]):5s} frac {fr.min():.2f}-{fr.max():.2f} | frames {len(rs)} "
                  f"striped {sum(r['striped'] for r in rs)} (unclipped {sum(r['ref_striped'] for r in rs)}) "
                  f"P/A-fail {pa_bad} harmonic-regions {harm} multi-region {multi} "
                  f"exact-clip {sum(r['detect_exact'] for r in rs)} no-clip-in-region {nin0}")
            for v in VARS:
                e, fb = [], 0
                for g in regs:
                    d, f = val(g, v)
                    if d is None or not np.isfinite(d):
                        fb += 1
                        continue
                    e.append(d - 0.5)
                    fb += f
                e = np.array(e)
                if not len(e):
                    continue
                p5, med, p95 = np.percentile(e, [5, 50, 95])
                print(f"      {v:11s} miss {int((np.abs(e) > TOL).sum()):2d}/{len(regs):2d} fallback {fb:2d} "
                      f"err p5/med/p95 {p5:+.3f}/{med:+.3f}/{p95:+.3f} max|e| {np.abs(e).max():.3f}")


def free(path):
    d = json.load(open(path))
    res, thr = d["results"], d["GATE_STORED_THRESHOLD"]
    print("\n=== stripe-free, 256x256 scorched (paired with the unclipped frame) ===")
    for p in sorted({r["photons"] for r in res}):
        rs = [r for r in res if r["photons"] == p]
        u = np.array([r["unclipped"] for r in rs])
        print(f"{p:5.0f} photons unclipped: score max {u.max():.1f}, > {thr:.1f}: {(u > thr).sum()}/{len(rs)}")
        for f in d["fracs"]:
            c = np.array([r[str(f)]["score"] for r in rs])
            nreg = sum(len(r[str(f)]["regions"]) for r in rs)
            diff = c - u
            print(f"   clip {f}: score max {c.max():.1f}, higher than unclipped {int((diff > 1e-3).sum())}/{len(rs)} "
                  f"(max rise {diff.max():+.1f}), > {thr:.1f}: {(c > thr).sum()}, regions {nreg}, "
                  f"clipped px median {np.median([r[str(f)]['clipped'] for r in rs]):.0f}")


def rule(path):
    d = json.load(open(path))["results"]
    print("\n=== generator rule: depth of np.minimum(clean, f * clean.max()), noise-free ===")
    for kind in ("full", "partial"):
        rs = [r for r in d if r["kind"] == kind]
        for f in rs[0]["clipped"]:
            e = np.array([r["clipped"][f] - 0.5 for r in rs])
            print(f"  {kind:7s} {f:>4s}: err med {np.median(e):+.3f} range {e.min():+.3f}..{e.max():+.3f}; "
                  f"frames <= -{TOL}: {np.mean(e < -TOL):.2f}, <= -{TOL + 0.05:.2f}: {np.mean(e <= -TOL - 0.05):.2f}")


if __name__ == "__main__":
    guard(sys.argv[1])
    free(sys.argv[2])
    rule(sys.argv[3])
