"""PROTOTYPE (throwaway) for ticket 03, plan-review item P1.

Question: at full frame 400x1600, does m = 0.2 clear 90% detection at its own
1% false-alarm threshold set on separate calibration seeds?

Run: PYTHONPATH=src OMP_NUM_THREADS=1 python prototype_03_p1.py [n_cal] [n_striped] [workers]
Detector: analyse() at c0d99ab, unchanged. Detected means score > threshold.
"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.stats import binomtest, betabinom

from denoisifier import analyse
from denoisifier.synthetic import Emccd, generate

SHAPE = (400, 1600)  # rows x cols: full Newton sensor, 1600 wide, 400 tall
TYPICAL = dict(mottle="scorched", noise=Emccd())
DEPTH = 0.2
RATE = 0.01
CASES = [(3, 10), (5, 0), (8, 6), (12, -8), (20, -10), (4, -4), (16, 10), (6, -10), (10, 3), (14, -6)]
# Fresh seed ranges, disjoint from 0-199 (02 tests/threshold), 1000-1399 and
# 2000-2031 (plan section 2) and 10_000-40_000 (plan section 3.2 gate seeds).
CAL_BASE = 50_000
STRIPED_BASE = 60_000


def score_one(args):
    seed, depth = args
    period, angle = CASES[seed % len(CASES)]
    s = generate(seed=seed, shape=SHAPE, period=period, angle_deg=angle,
                 modulation_depth=depth, **TYPICAL)
    t0 = time.perf_counter()
    score = analyse(s.frame).score
    return seed, period, angle, float(score), time.perf_counter() - t0


def run(seeds, depth, workers):
    t0 = time.perf_counter()
    with ProcessPoolExecutor(workers) as ex:
        out = list(ex.map(score_one, [(s, depth) for s in seeds], chunksize=1))
    return out, time.perf_counter() - t0


def main():
    n_cal = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    n_str = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 16

    # Single-process timing first, nothing else running from this script.
    s = generate(seed=STRIPED_BASE - 1, shape=SHAPE, period=8, angle_deg=0,
                 modulation_depth=DEPTH, **TYPICAL)
    analyse(generate(seed=0, shape=(256, 256), **TYPICAL).frame)  # warm-up
    single = []
    for _ in range(3):
        t0 = time.perf_counter()
        analyse(s.frame)
        single.append(time.perf_counter() - t0)
    print("single-process analyse times", single, flush=True)

    # Calibration first; threshold fixed before any striped frame is scored.
    cal, cal_wall = run(range(CAL_BASE, CAL_BASE + n_cal), 0.0, workers)
    cal_scores = np.array([r[3] for r in cal])
    k = int(np.floor(RATE * (n_cal + 1)))
    thr = float(np.sort(cal_scores)[::-1][k - 1])
    print(f"threshold (k={k} largest of {n_cal}) = {thr:.2f}", flush=True)

    st, st_wall = run(range(STRIPED_BASE, STRIPED_BASE + n_str), DEPTH, workers)
    st_scores = np.array([r[3] for r in st])
    det = int((st_scores > thr).sum())
    ci = binomtest(det, n_str).proportion_ci(confidence_level=0.95, method="exact")

    # Sensitivity: how much the threshold can move (true FA of an order-stat
    # threshold ~ Beta(k, n+1-k)); also detection at neighbouring order stats.
    sorted_desc = np.sort(cal_scores)[::-1]
    alt = {f"k={j}": {"thr": float(sorted_desc[j - 1]),
                      "detected": int((st_scores > sorted_desc[j - 1]).sum())}
           for j in range(1, min(k + 4, n_cal) + 1)}

    per_case = {}
    for p, a in CASES:
        sc = np.array([r[3] for r in st if (r[1], r[2]) == (p, a)])
        per_case[f"P{p}/A{a}"] = dict(n=len(sc), detected=int((sc > thr).sum()),
                                      min=float(sc.min()), median=float(np.median(sc)),
                                      min_over_thr=float(sc.min() / thr))

    res = dict(
        shape=SHAPE, depth=DEPTH, rate=RATE, workers=workers,
        cal_seeds=[CAL_BASE, CAL_BASE + n_cal - 1],
        striped_seeds=[STRIPED_BASE, STRIPED_BASE + n_str - 1],
        threshold=thr, k=k,
        true_fa_of_threshold_beta_95=[float(x) for x in
                                      (__import__("scipy.stats").stats.beta(k, n_cal + 1 - k).ppf([0.025, 0.975]))],
        cal_top10=[float(x) for x in sorted_desc[:10]],
        cal_quantiles={q: float(np.quantile(cal_scores, q)) for q in (0.5, 0.9, 0.95, 0.98, 0.99)},
        cal_max_seed=int(cal[int(np.argmax(cal_scores))][0]),
        detected=det, n_striped=n_str, rate_detected=det / n_str,
        ci95=[ci.low, ci.high],
        striped_quantiles={q: float(np.quantile(st_scores, q)) for q in (0.0, 0.05, 0.1, 0.25, 0.5)},
        striped_lowest10=sorted([(float(r[3]), r[0], r[1], r[2]) for r in st])[:10],
        alt_thresholds=alt, per_case=per_case,
        single_process_analyse_s=single,
        worker_analyse_s=dict(
            median=float(np.median([r[4] for r in cal + st])),
            p90=float(np.quantile([r[4] for r in cal + st], 0.9)),
            max=float(max(r[4] for r in cal + st))),
        wall_s=dict(cal=cal_wall, striped=st_wall,
                    per_frame_wall=(cal_wall + st_wall) / (n_cal + n_str)),
        raw=dict(cal=cal, striped=st),
    )
    path = os.environ.get("OUT", "p1_result.json")
    with open(path, "w") as f:
        json.dump(res, f, indent=1)
    summary = {k_: v for k_, v in res.items() if k_ != "raw"}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
