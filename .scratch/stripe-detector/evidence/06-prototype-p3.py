"""Ticket 06 pre-freeze check P3 (plan `.scratch/stripe-detector/handoffs/06-plan.md`, step 5b).

Runs the implemented detector (HEAD after steps 0-3) and writes the raw results plus the
values the plan's rules set:

  sweep   - _CLIPPED_WEIGHT_MAX in {0.05, 0.10, 0.20} on full typical frames clipped at 0.4,
            seeds 396_500-396_539: misses, worst depth error, mean error against clip_level=inf.
  margin  - fresh full frames 396_540-396_579 at the chosen cutoff: worst error at 0.4 must be
            <= 0.08, else CLIP_LEVEL_FRACTION = 0.5 (recomputed on the same seeds); 30 photons
            recorded, not asserted.
  eps     - CLIP_DEPTH_EPS = max(0.01, largest per-seed err - err_inf + 0.005) over P3's full
            frames (sweep and margin) and partial frames at the chosen fraction; ceiling 0.02.
  share   - minimum clipped share of the full frames at the chosen fraction (CLIP_MIN_SHARE).
  partial - 512x512 single-region frames 396_580-396_599 at 0.8 (no harm) and the fraction
            (not worse than inf + eps), with the B4 count of clipped pixels inside the region.
  ac3     - paired stripe-free frames 396_600-396_699, no spikes vs SPIKE_STRESS_COUNT spikes,
            and spikes with a clip at SATURATING_CLIP_FACTOR (auto detection): score changes,
            verdicts at THRESHOLD and GATE_STORED_THRESHOLD. SPIKE_SCORE_TOL =
            ceil(1.25 x largest |change|), ceiling 15.
  free    - the same stripe-free seeds, spike-free, clipped at 0.4 and 0.5: regions and scores.
  plateau - false plateaus (find_clipped(frame, None) non-empty) on unclipped integer-valued
            EMCCD frames (em_gain=1, read_noise_e=0) at 30/100/1000 photons, and the Solis
            fixtures.
  timing  - reject_spikes + find_clipped at 400x1600, run alone after the pool: <= 0.3 s.

Run from the repo root, on an idle machine, in the background:
    uv run --locked python .scratch/stripe-detector/evidence/06-prototype-p3.py \
        .scratch/stripe-detector/evidence/06-prototype-p3.json \
        > .scratch/stripe-detector/evidence/06-prototype-p3.txt 2>&1

Seeds: range(396_500, 396_700), reserved in USED_SEEDS at step 0, before this ran.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd() / "tests"))

from cases import CASES  # noqa: E402
from protected import (  # noqa: E402
    ANGLE_TOL_DEG,
    CALIBRATION_SEEDS,
    DEPTH_TOL,
    GATE_STORED_THRESHOLD,
    PERIOD_REL_TOL,
    SATURATING_CLIP_FACTOR,
    SPIKE_STRESS_COUNT,
    USED_SEEDS,
)
from regions import match, single_region, truth_pixels  # noqa: E402

from denoisifier import analysis  # noqa: E402
from denoisifier._data_quality import find_clipped, reject_spikes  # noqa: E402
from denoisifier.analysis import THRESHOLD, analyse  # noqa: E402
from denoisifier.frame_io import read_frame  # noqa: E402
from denoisifier.synthetic import Emccd, generate  # noqa: E402

SWEEP_SEEDS = range(396_500, 396_540)
MARGIN_SEEDS = range(396_540, 396_580)
PARTIAL_SEEDS = range(396_580, 396_600)
AC3_SEEDS = range(396_600, 396_700)
for _s in range(396_500, 396_700):
    assert any(_s in r for r in USED_SEEDS if r == range(396_500, 396_700))
    assert not any(_s in r for r in CALIBRATION_SEEDS.values())

CUTOFFS = (0.05, 0.10, 0.20)
START_CUTOFF = 0.10
FRACTIONS = (0.4, 0.5)
MILD = 0.8
M = 0.5
MARGIN_MAX_ERR = 0.08
EPS_CEILING = 0.02
SCORE_TOL_CEILING = 15
TIMING_BUDGET_S = 0.3
SOLIS = Path("tests/data/solis")


def full_frame(seed, frac, photons=100.0):
    period, angle = CASES[seed % len(CASES)]
    kw = dict(seed=seed, shape=(256, 256), period=period, angle_deg=angle, modulation_depth=M,
              mottle="scorched", noise=Emccd(photons_peak=photons))
    level = frac * generate(**kw).clean.max()
    return generate(**kw, clip_level=level), period, angle


def partial_frame(seed, frac):
    period, angle = CASES[seed % len(CASES)]
    kw = dict(seed=seed, shape=(512, 512), mottle="scorched",
              regions=[single_region(period, angle, depth=M)], noise=Emccd())
    level = frac * generate(**kw).clean.max()
    return generate(**kw, clip_level=level), period, angle


def analyse_at(frame, cutoff):
    """cutoff None: clip_level=inf (no exclusion); else auto detection at that cutoff."""
    if cutoff is None:
        return analyse(frame, clip_level=math.inf)
    analysis._CLIPPED_WEIGHT_MAX = cutoff
    try:
        return analyse(frame)
    finally:
        analysis._CLIPPED_WEIGHT_MAX = START_CUTOFF


def full_job(job):
    seed, frac, photons = job
    s, period, angle = full_frame(seed, frac, photons)
    out = {"seed": seed, "frac": frac, "photons": photons, "case": [period, angle],
           "truth_clipped": s.truth.clipped_pixels,
           "share": s.truth.clipped_pixels / s.frame.size, "by_cutoff": {}}
    for cutoff in (None, *CUTOFFS):
        rep = analyse_at(s.frame, cutoff)
        regs = [{"period": r.period_px, "angle": r.angle_deg, "depth": r.modulation_depth}
                for r in rep.regions]
        ok = rep.striped and bool(regs) and all(
            abs(r["period"] - period) <= PERIOD_REL_TOL * period
            and abs(r["angle"] - angle) <= ANGLE_TOL_DEG
            and abs(r["depth"] - M) <= DEPTH_TOL for r in regs)
        err = max((abs(r["depth"] - M) for r in regs), default=float("nan"))
        out["by_cutoff"]["inf" if cutoff is None else str(cutoff)] = {
            "striped": rep.striped, "regions": regs, "ok": ok, "err": err,
            "clipped_pixels": rep.clipped_pixels, "spike_pixels": rep.spike_pixels}
    return out


def partial_job(job):
    seed, frac = job
    s, period, angle = partial_frame(seed, frac)
    truth = s.truth.regions[0]
    inside = int((s.truth.clipped_mask & truth_pixels(truth)).sum())
    out = {"seed": seed, "frac": frac, "case": [period, angle], "clipped_in_region": inside,
           "truth_clipped": s.truth.clipped_pixels, "by_cutoff": {}}
    for cutoff in (None, *CUTOFFS):
        rep = analyse_at(s.frame, cutoff)
        pairs = match(rep.regions, rep.labels, s.truth.regions)
        regs = [{"period": r.period_px, "angle": r.angle_deg, "depth": r.modulation_depth}
                for r, _ in pairs]
        one = len(regs) == 1
        shape_ok = one and abs(regs[0]["period"] - period) <= PERIOD_REL_TOL * period and abs(
            regs[0]["angle"] - angle) <= ANGLE_TOL_DEG
        err = abs(regs[0]["depth"] - M) if one else float("nan")
        out["by_cutoff"]["inf" if cutoff is None else str(cutoff)] = {
            "regions": regs, "one_region_matches": shape_ok, "err": err,
            "within_tol": shape_ok and err <= DEPTH_TOL}
    return out


def ac3_job(seed):
    kw = dict(seed=seed, shape=(256, 256), modulation_depth=0.0, mottle="scorched", noise=Emccd())
    free = generate(**kw)
    level = SATURATING_CLIP_FACTOR * free.clean.max()
    frames = {"free": free, "spikes": generate(**kw, spikes=SPIKE_STRESS_COUNT),
              "spikes_clip3": generate(**kw, spikes=SPIKE_STRESS_COUNT, clip_level=level)}
    out = {"seed": seed}
    for name, s in frames.items():
        rep = analyse(s.frame)
        gate = analyse(s.frame, threshold=GATE_STORED_THRESHOLD)
        out[name] = {"score": rep.score, "striped": rep.striped, "striped_gate": gate.striped,
                     "spike_pixels": rep.spike_pixels, "truth_spike_pixels": s.truth.spike_pixels,
                     "clipped_pixels": rep.clipped_pixels,
                     "truth_clipped_pixels": s.truth.clipped_pixels}
    return out


def free_job(job):
    seed, frac = job
    kw = dict(seed=seed, shape=(256, 256), modulation_depth=0.0, mottle="scorched", noise=Emccd())
    level = frac * generate(**kw).clean.max()
    s = generate(**kw, clip_level=level)
    rep = analyse(s.frame)
    return {"seed": seed, "frac": frac, "score": rep.score, "striped": rep.striped,
            "regions": [[r.period_px, r.angle_deg] for r in rep.regions],
            "clipped_pixels": rep.clipped_pixels, "truth_clipped": s.truth.clipped_pixels}


def plateau_job(job):
    seed, photons, m = job
    period, angle = CASES[seed % len(CASES)]
    s = generate(seed=seed, shape=(256, 256), period=period, angle_deg=angle, modulation_depth=m,
                 mottle="scorched", noise=Emccd(photons_peak=photons, em_gain=1.0, read_noise_e=0.0))
    assert np.array_equal(s.frame, np.round(s.frame))
    found = find_clipped(s.frame, None)
    top = s.frame.max()
    return {"seed": seed, "photons": photons, "m": m, "false_plateau": int(found.sum()),
            "ties_at_max": int((s.frame == top).sum())}


def solis():
    out = {}
    for name in ("kinetic.asc", "xpos_ypos_crop.asc"):
        for drop in (False, True):
            try:
                frame = read_frame(SOLIS / name, drop_axis_column=drop).frame
            except ValueError as e:
                out[f"{name} drop={drop}"] = {"error": str(e)}
                continue
            top = frame.max()
            out[f"{name} drop={drop}"] = {"shape": list(frame.shape),
                                          "ties_at_max": int((frame == top).sum()),
                                          "false_plateau": int(find_clipped(frame, None).sum()),
                                          "spike_pixels": int(reject_spikes(frame)[1].sum())}
    return out


def timing():
    s = generate(seed=396_599, shape=(400, 1600), period=8.0, angle_deg=5.0, modulation_depth=M,
                 mottle="scorched", noise=Emccd())
    times = []
    for _ in range(21):
        t0 = time.perf_counter()
        reject_spikes(s.frame)
        find_clipped(s.frame, None)
        times.append(time.perf_counter() - t0)
    return {"median_s": float(np.median(times)), "min_s": min(times), "max_s": max(times),
            "runs": len(times)}


def finite_max(values):
    vals = [v for v in values if not math.isnan(v)]
    return max(vals) if vals else float("nan")


def summarise(full, partial, ac3, free, plateau):
    s = {}
    # 1. cutoff sweep (sweep seeds only, fraction 0.4, 100 photons)
    sweep = [r for r in full if r["seed"] in SWEEP_SEEDS and r["frac"] == 0.4 and r["photons"] == 100]
    table = {}
    for c in ("inf", *map(str, CUTOFFS)):
        errs = [r["by_cutoff"][c]["err"] for r in sweep]
        table[c] = {"misses": sum(not r["by_cutoff"][c]["ok"] for r in sweep),
                    "worst_err": finite_max(errs), "mean_err": float(np.nanmean(errs)),
                    "no_region": sum(math.isnan(e) for e in errs)}
    s["sweep"] = table
    # Rule (stated before the run): fewest misses, then smallest worst error; the start
    # value 0.10 stays unless another cutoff is strictly better on (misses, worst error)
    # by more than 0.002 in worst error.
    key = {c: (table[str(c)]["misses"], table[str(c)]["worst_err"]) for c in CUTOFFS}
    best = min(CUTOFFS, key=lambda c: key[c])
    start = key[START_CUTOFF]
    if key[best][0] < start[0] or key[best][1] < start[1] - 0.002:
        cutoff = best
    else:
        cutoff = START_CUTOFF
    s["cutoff"] = cutoff
    c = str(cutoff)

    # 2. margin check on fresh seeds
    def margin_at(frac, photons):
        rows = [r for r in full if r["seed"] in MARGIN_SEEDS and r["frac"] == frac
                and r["photons"] == photons]
        errs = [r["by_cutoff"][c]["err"] for r in rows]
        errs_inf = [r["by_cutoff"]["inf"]["err"] for r in rows]
        return {"misses": sum(not r["by_cutoff"][c]["ok"] for r in rows),
                "worst_err": finite_max(errs), "mean_err": float(np.nanmean(errs)),
                "mean_err_inf": float(np.nanmean(errs_inf)),
                "misses_inf": sum(not r["by_cutoff"]["inf"]["ok"] for r in rows)}

    s["margin"] = {f"{f} @ {p}": margin_at(f, p) for f in FRACTIONS for p in (100.0, 30.0)}
    frac = 0.4 if s["margin"]["0.4 @ 100.0"]["worst_err"] <= MARGIN_MAX_ERR else 0.5
    s["CLIP_LEVEL_FRACTION"] = frac
    if frac == 0.5:
        s["margin_recheck_ok"] = s["margin"]["0.5 @ 100.0"]["worst_err"] <= MARGIN_MAX_ERR

    # 3. eps and share at the chosen fraction (100 photons)
    full_at = [r for r in full if r["frac"] == frac and r["photons"] == 100]
    part_at = [r for r in partial if r["frac"] == frac]
    excess = [(r["seed"], kind, r["by_cutoff"][c]["err"] - r["by_cutoff"]["inf"]["err"])
              for kind, rows in (("full", full_at), ("partial", part_at)) for r in rows]
    finite = [e for e in excess if not math.isnan(e[2])]
    worst = max(finite, key=lambda e: e[2])
    s["excess_worst"] = list(worst)
    s["excess_nan"] = [e[:2] for e in excess if math.isnan(e[2])]
    eps = max(0.01, worst[2] + 0.005)
    s["CLIP_DEPTH_EPS_raw"] = eps
    s["CLIP_DEPTH_EPS"] = math.ceil(eps * 1000) / 1000
    s["eps_within_ceiling"] = s["CLIP_DEPTH_EPS"] <= EPS_CEILING
    s["full_teeth"] = {
        "mean_err": float(np.nanmean([r["by_cutoff"][c]["err"] for r in full_at])),
        "mean_err_inf": float(np.nanmean([r["by_cutoff"]["inf"]["err"] for r in full_at])),
        "misses": sum(not r["by_cutoff"][c]["ok"] for r in full_at), "frames": len(full_at)}
    s["min_share"] = min(r["share"] for r in full_at)
    s["median_share"] = float(np.median([r["share"] for r in full_at]))
    s["clipped_count_exact"] = all(
        r["by_cutoff"][c]["clipped_pixels"] == r["truth_clipped"] for r in full_at)

    # 4. partial frames
    def part(frac_p):
        rows = [r for r in partial if r["frac"] == frac_p]
        return {"min_clipped_in_region": min(r["clipped_in_region"] for r in rows),
                "within_tol": sum(r["by_cutoff"][c]["within_tol"] for r in rows),
                "within_tol_inf": sum(r["by_cutoff"]["inf"]["within_tol"] for r in rows),
                "not_worse_than_inf_plus_eps": sum(
                    r["by_cutoff"][c]["err"] <= r["by_cutoff"]["inf"]["err"] + s["CLIP_DEPTH_EPS"]
                    for r in rows),
                "first5_within_tol": sum(r["by_cutoff"][c]["within_tol"] for r in rows[:5]),
                "frames": len(rows),
                "errs": [[r["seed"], r["by_cutoff"][c]["err"], r["by_cutoff"]["inf"]["err"]]
                         for r in rows]}

    s["partial"] = {str(MILD): part(MILD), str(frac): part(frac)}

    # 5. AC 3
    changes = {}
    for name in ("spikes", "spikes_clip3"):
        d = [r[name]["score"] - r["free"]["score"] for r in ac3]
        changes[name] = {
            "largest_abs": max(abs(x) for x in d), "mean": float(np.mean(d)),
            "verdict_changes_threshold": sum(r[name]["striped"] != r["free"]["striped"] for r in ac3),
            "verdict_changes_gate": sum(r[name]["striped_gate"] != r["free"]["striped_gate"]
                                        for r in ac3),
            "striped_threshold": sum(r[name]["striped"] for r in ac3),
            "striped_gate": sum(r[name]["striped_gate"] for r in ac3)}
    changes["free"] = {"striped_threshold": sum(r["free"]["striped"] for r in ac3),
                       "striped_gate": sum(r["free"]["striped_gate"] for r in ac3),
                       "max_score": max(r["free"]["score"] for r in ac3)}
    s["ac3"] = changes
    largest = max(changes["spikes"]["largest_abs"], changes["spikes_clip3"]["largest_abs"])
    s["SPIKE_SCORE_TOL"] = math.ceil(1.25 * largest)
    s["score_tol_within_ceiling"] = s["SPIKE_SCORE_TOL"] <= SCORE_TOL_CEILING

    # 6. clipped stripe-free frames
    s["free_clipped"] = {
        str(f): {"striped": sum(r["striped"] for r in free if r["frac"] == f),
                 "with_regions": sum(bool(r["regions"]) for r in free if r["frac"] == f),
                 "max_score": max(r["score"] for r in free if r["frac"] == f),
                 "frames": sum(r["frac"] == f for r in free)} for f in FRACTIONS}

    # 7. false plateaus
    s["plateau"] = {f"{p}": {"frames": sum(r["photons"] == p for r in plateau),
                             "false_plateaus": sum(r["false_plateau"] > 0 for r in plateau
                                                   if r["photons"] == p)}
                    for p in (30.0, 100.0, 1000.0)}
    return s


def main():
    out = Path(sys.argv[1])
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "src"], capture_output=True,
                           text=True, check=True).stdout.strip()
    t0 = time.time()
    full_jobs = [(s, f, p) for s in [*SWEEP_SEEDS, *MARGIN_SEEDS] for f in FRACTIONS
                 for p in (100.0, 30.0) if p == 100.0 or s in MARGIN_SEEDS]
    partial_jobs = [(s, f) for s in PARTIAL_SEEDS for f in (MILD, *FRACTIONS)]
    free_jobs = [(s, f) for s in AC3_SEEDS for f in FRACTIONS]
    plateau_jobs = [(s, p, m) for s in range(396_500, 396_600) for p in (30.0, 100.0, 1000.0)
                    for m in (0.0, M)]
    with ProcessPoolExecutor(max_workers=12) as ex:
        partial = list(ex.map(partial_job, partial_jobs))
        print(f"partial done {time.time() - t0:.0f}s", flush=True)
        full = list(ex.map(full_job, full_jobs))
        print(f"full done {time.time() - t0:.0f}s", flush=True)
        ac3 = list(ex.map(ac3_job, AC3_SEEDS))
        print(f"ac3 done {time.time() - t0:.0f}s", flush=True)
        free = list(ex.map(free_job, free_jobs))
        plateau = list(ex.map(plateau_job, plateau_jobs, chunksize=10))
        print(f"free, plateau done {time.time() - t0:.0f}s", flush=True)
    timed = timing()
    print(f"timing {timed}", flush=True)
    raw = {"full": full, "partial": partial, "ac3": ac3, "free": free, "plateau": plateau}
    out.with_suffix(".raw.json").write_text(json.dumps(raw))
    summary = summarise(full, partial, ac3, free, plateau)
    summary["timing"] = timed
    summary["timing_within_budget"] = timed["median_s"] <= TIMING_BUDGET_S
    summary["solis"] = solis()
    out.write_text(json.dumps({"commit": commit + ("-dirty-src" if dirty else ""),
                               "summary": summary, "full": full, "partial": partial, "ac3": ac3,
                               "free": free, "plateau": plateau}, indent=1))
    print(json.dumps(summary, indent=1))
    print("wrote", out, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
