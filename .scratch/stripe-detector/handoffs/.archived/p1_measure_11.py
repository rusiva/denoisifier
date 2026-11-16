"""Ticket 11 P1 measurement (plan section 7 step 1; a stop point). Scratch, not a test.

    uv run --locked python .scratch/stripe-detector/handoffs/p1_measure_11.py --out OUT.json

Seeds: BREAK_FORK_PROTOTYPE_SEEDS = 112_000-112_199 only (plan section 5), every arm.
Changes nothing under src/ or tests/: the evidence scalars of plan section 2 are
computed here from the package's private pieces, and the candidate thresholds are
applied to ``analyse`` by setting the module-level evidence limits in each worker
(``nextafter(T, inf)``, so acceptance is the planned strict ``E > T``).

Arms (plan section 5):
  base  400x1600 full-frame stripes, depth 0.5, CASES[seed % 10], scorched Mottle,
        Emccd(), 30 Spike events, unclipped; stored 1 % stripe threshold
  i     the same at depth WEAK_DEPTH (0.2)
  ii    one partial region (regions.single_region, semi-axes widened to 180 x 566 px,
        about half the 400x1600 frame), depth 0.5, same noise, Mottle and spikes
  iii   the base frames analysed at stripe false_alarm_rate=0.05
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))

import feasibility  # noqa: E402  (sets the thread variables before NumPy)
import seed_guard  # noqa: E402

import numpy as np  # noqa: E402

import denoisifier._local_phase as lp  # noqa: E402
from denoisifier import analysis as an  # noqa: E402
from denoisifier import analyse  # noqa: E402
from denoisifier._calibration import threshold_rank  # noqa: E402
from denoisifier._data_quality import find_clipped, reject_spikes  # noqa: E402
from denoisifier._local_stripes import estimate_local_stripes  # noqa: E402
from denoisifier.report import BinFactors  # noqa: E402
from denoisifier.synthetic import generate  # noqa: E402
from protected import CALIBRATION_SPIKES, PROBE_SHAPE, WEAK_DEPTH  # noqa: E402
from regions import single_region, truth_pixels  # noqa: E402
from threshold_calibration import MOTTLE, NOISE, synthetic  # noqa: E402
from cases import CASES  # noqa: E402

SEEDS = range(112_000, 112_200)  # BREAK_FORK_PROTOTYPE_SEEDS (plan section 5)
DEPTH = 0.5
RATE = 0.05
HALF_AXES = (180.0, 566.0)  # pi * 180 * 566 = 0.50 of 400 x 1600
ARMS = ("base", "i", "ii", "iii")
FLOOR_B = lp._BREAK_MIN_EVIDENCE
FLOOR_F = lp._FORK_MIN_EVIDENCE


def frame_of(arm: str, seed: int):
    if arm in ("base", "iii"):
        return synthetic(seed, PROBE_SHAPE, DEPTH)
    if arm == "i":
        return synthetic(seed, PROBE_SHAPE, WEAK_DEPTH)
    case = CASES[seed % len(CASES)]
    rows, cols = PROBE_SHAPE
    region = dataclasses.replace(
        single_region(case.period, case.angle_deg, depth=DEPTH, center=((rows - 1) / 2, (cols - 1) / 2)),
        semi_axes=HALF_AXES,
    )
    return generate(
        seed=seed,
        shape=PROBE_SHAPE,
        mottle=MOTTLE,
        noise=NOISE,
        spikes=CALIBRATION_SPIKES,
        regions=[region],
    )


def stripe_rate(arm: str) -> float | None:
    return 0.05 if arm == "iii" else None


# --- the front half of analyse (analysis.py:315-345, copied for the scratch run) ---


def front_half(frame: np.ndarray, false_alarm_rate: float | None):
    bins = BinFactors.of(None)
    threshold, _ = an._resolve_threshold(false_alarm_rate, None, None)
    work, spikes = reject_spikes(frame)
    clipped = find_clipped(frame, None) & ~spikes
    light = an._light(work)
    local = estimate_local_stripes(work, light, bins)
    survivors, filters = an._qualifying_regions(work, light, local, clipped, bins)
    score = max((g.peak_ratio for g in survivors), default=0.0)
    reported = [g for g in survivors if g.peak_ratio > threshold]
    refused = [g for g in reported if an._refused(g, bins)]
    responses = field = None
    gated: list = []
    if filters is not None and reported:
        responses = an._Responses(filters.spec)
        gated = an._pre_break_forks(reported, refused, responses, bins)
        field = responses if not gated else an._ForksExplained(responses, gated, bins)
    return dict(
        bins=bins, threshold=threshold, score=score, reported=reported, refused=refused,
        filters=filters, clipped=clipped, responses=responses, field=field, gated=gated,
    )


# --- the evidence scalars (plan section 2) ---


def greedy_no_limit(z, domain, period, angle_deg, bins, max_lines):
    """find_phase_breaks with no evidence limit: the greedy sequence, stopping where the
    jump or spread rule fails or at max_lines (copy of _local_phase.find_phase_breaks)."""
    if lp.frame_period(period, angle_deg, bins) < lp._BREAK_MIN_FRAME_PERIOD_PX:
        return []
    samples = lp._samples(z, domain, period, angle_deg, bins)
    if samples is None:
        return []
    found = []
    coarse = np.arange(-90 + lp._BREAK_COARSE_STEP_DEG, 90 + 1e-9, lp._BREAK_COARSE_STEP_DEG)
    for _ in range(max_lines):
        best = lp._best_line(samples, coarse)
        if best is None:
            break
        evidence, a, o, jump = best
        if a > 90:
            a, o, jump = a - 180, -o, -jump
        elif a <= -90:
            a, o, jump = a + 180, -o, -jump
        jump = float(lp.wrap_jump(jump))
        t = math.radians(a)
        brk = lp.FoundBreak(
            point=(samples.y0 + o * math.cos(t), samples.x0 - o * math.sin(t)),
            line_angle_deg=float(a),
            jump_rad=float(jump),
            evidence=evidence,
        )
        if not lp._accepted(samples, dataclasses.replace(brk, evidence=math.inf)):
            break
        found.append(brk)
        s = brk.side(samples.y, samples.x)
        g = lp._BREAK_EXPLAIN_SIGMAS * lp._finder_sigma_n(period, angle_deg, a)
        w = np.where(s > 0, samples.w * np.exp(-1j * jump), samples.w)
        samples.w = np.where(np.abs(s) < g, 0, w)
    return found


def bridge_evidence(state, a, b) -> float | None:
    """g of plan section 2 for one bridge pair (copy of _BreakPass.bridge up to the
    finder call); None when the pair is not a bridge domain."""
    if not an._compatible(a, b):
        return None
    pa, pb = a.pixels, b.pixels
    gap = an._BRIDGE_GAP_PERIODS * max(a.period, b.period)
    box = an._bbox(pa)
    pad = int(np.ceil(max(an.frame_px(state.bins, gap, gap)))) + 1
    r0, r1 = max(box.row_start - pad, 0), min(box.row_stop + pad, pa.shape[0])
    c0, c1 = max(box.col_start - pad, 0), min(box.col_stop + pad, pa.shape[1])
    window_b = pb[r0:r1, c0:c1]
    if not window_b.any():
        return None
    if an._edt(~pa[r0:r1, c0:c1], state.bins)[window_b].min() > gap:
        return None
    between = (an._edt(~pa, state.bins) <= gap) & (an._edt(~pb, state.bins) <= gap) & state.light
    top = a if a.peak_ratio >= b.peak_ratio else b
    na, nb = int(pa.sum()), int(pb.sum())
    if na <= nb:
        need_a, need_b = an._BRIDGE_SMALL_SIDE_SHARE, an._BRIDGE_LARGE_SIDE_SHARE
    else:
        need_a, need_b = an._BRIDGE_LARGE_SIDE_SHARE, an._BRIDGE_SMALL_SIDE_SHARE
    z = state.responses.response(top.period, top.angle_deg)
    seq = greedy_no_limit(z, pa | pb | between, top.period, top.angle_deg, state.bins, lp._BREAK_MAX_PER_REGION)
    g, running = 0.0, math.inf
    for brk in seq:
        running = min(running, brk.evidence)
        share_a = float((brk.side(state.y[pa], state.x[pa]) > 0).mean())
        share_b = float((brk.side(state.y[pb], state.x[pb]) > 0).mean())
        if (share_a >= need_a and 1 - share_b >= need_b) or (1 - share_a >= need_a and share_b >= need_b):
            g = max(g, running)
    return g


def evidence(fh) -> dict:
    reported, refused, bins = fh["reported"], fh["refused"], fh["bins"]
    out = dict(S_b=0.0, S_f=0.0, bridge_pairs=0, bridge_max=0.0, region_max=0.0)
    if fh["field"] is None:
        return out
    owned = np.logical_or.reduce([g.pixels for g in reported])
    state = an._BreakPass(fh["filters"], fh["clipped"], owned, fh["field"])
    for g in reported:
        z = state.responses.response(g.period, g.angle_deg)
        seq = greedy_no_limit(z, g.pixels, g.period, g.angle_deg, bins, 1)
        if seq:
            out["region_max"] = max(out["region_max"], seq[0].evidence)
    for i, a in enumerate(reported):
        for b in reported[i + 1 :]:
            gb = bridge_evidence(state, a, b)
            if gb is not None:
                out["bridge_pairs"] += 1
                out["bridge_max"] = max(out["bridge_max"], gb)
    out["S_b"] = max(out["region_max"], out["bridge_max"])
    for g in reported:
        if not an._holds_refused(g, refused):
            for f in an._region_forks(g, owned, fh["responses"], bins, -math.inf):
                out["S_f"] = max(out["S_f"], f.evidence)
    return out


# --- thresholds into the real path (worker-global; strict E > T) ---


def set_thresholds(t_b: float, t_f: float) -> None:
    lp._BREAK_MIN_EVIDENCE = math.nextafter(t_b, math.inf)
    an._FORK_MIN_EVIDENCE = math.nextafter(t_f, math.inf)


def crossing_check(frame, rate, s_b: float, s_f: float) -> dict:
    """T7-style: the real break pass / post-break Fork search finds nothing at T = S and
    something just below (when S > 0); front half at the arm's stripe threshold."""
    fh = front_half(frame, rate)
    res = {}
    if fh["field"] is None:
        return res
    for name, s in (("breaks", s_b), ("forks", s_f)):
        if s <= 0:
            continue
        counts = []
        for t in (s, math.nextafter(s, 0)):
            if name == "breaks":
                set_thresholds(t, FLOOR_F)
                settled = an._with_phase_breaks(fh["reported"], fh["filters"], fh["clipped"], fh["field"])
                counts.append(sum(len(f) for _, f in settled))
            else:
                set_thresholds(FLOOR_B, t)
                settled = [(g, []) for g in fh["reported"]]
                counts.append(len(an._post_break_forks(settled, fh["refused"], fh["responses"], fh["bins"])))
        res[name] = {"at_S": counts[0], "just_below": counts[1]}
    return res


def job(args) -> dict:
    arm, seed, t_b, t_f, with_evidence, validate = args
    t0 = time.perf_counter()
    s = frame_of(arm, seed)
    t1 = time.perf_counter()
    rec: dict = {"arm": arm, "seed": seed, "case": seed % len(CASES), "gen_s": t1 - t0}
    if with_evidence:
        fh = front_half(s.frame, stripe_rate(arm))
        ev = evidence(fh)
        t2 = time.perf_counter()
        rec.update(ev)
        rec["evidence_s"] = t2 - t1
        rec["n_reported"] = len(fh["reported"])
        rec["n_gated"] = len(fh["gated"])
    t2 = time.perf_counter()
    set_thresholds(t_b, t_f)
    report = analyse(s.frame, false_alarm_rate=stripe_rate(arm))
    rec["analyse_s"] = time.perf_counter() - t2
    rec["striped"] = report.striped
    rec["n_regions"] = len(report.regions)
    fake_region = {}
    if arm == "ii":
        truth = truth_pixels(s.truth.regions[0])
        for r in report.regions:
            own = report.labels == r.label
            fake_region[r.label] = bool((own & truth).sum() < 0.5 * own.sum())
    rec["fake_regions"] = sum(fake_region.values())
    rec["breaks"] = [
        {"region": b.region, "jump": b.jump_rad, "line": b.line, "in_fake_region": fake_region.get(b.region, False)}
        for b in report.phase_breaks
    ]
    rec["forks"] = [
        {"region": f.region, "point": f.point, "in_fake_region": fake_region.get(f.region, False)}
        for f in report.forks
    ]
    set_thresholds(FLOOR_B, FLOOR_F)
    if validate and (rec["S_b"] > 0 or rec["S_f"] > 0):
        rec["crossing"] = crossing_check(s.frame, stripe_rate(arm), rec["S_b"], rec["S_f"])
        set_thresholds(FLOOR_B, FLOOR_F)
    return rec


def rank(n, r):
    """threshold_rank, clamped to 1 for smoke runs on a few seeds."""
    return threshold_rank(n, r) if math.floor(r * (n + 1) + 1e-9) >= 1 else 1


def kth_largest(values, k):
    return float(sorted(values, reverse=True)[k - 1])


def quantiles(values, n):
    v = sorted(values, reverse=True)
    out = {"max": v[0], "median": float(np.median(v)), "p90": float(np.quantile(v, 0.9))}
    for name, r in (("rank_2.5pct", 0.025), ("rank_5pct", 0.05)):
        k = rank(n, r)
        out[name] = {"k": k, "value": v[k - 1]}
    return out


def summarise(arm, recs, t_b, t_f, workers):
    n = len(recs)
    striped = [r for r in recs if r["striped"]]
    fake_frames = [r for r in striped if r["breaks"] or r["forks"]]
    total = sum(len(r["breaks"]) + len(r["forks"]) for r in recs)
    in_fake = sum(sum(x["in_fake_region"] for x in r["breaks"] + r["forks"]) for r in recs)
    per_case = {}
    for c in range(len(CASES)):
        cr = [r for r in recs if r["case"] == c]
        per_case[c] = {
            "frames": len(cr),
            "striped": sum(r["striped"] for r in cr),
            "fake_frames": sum(bool(r["breaks"] or r["forks"]) for r in cr),
            "breaks": sum(len(r["breaks"]) for r in cr),
            "forks": sum(len(r["forks"]) for r in cr),
        }
    alarm = [c for c, v in per_case.items() if v["fake_frames"] >= 5]
    s_b = [r["S_b"] for r in recs]
    s_f = [r["S_f"] for r in recs]
    viol = {"break_without_S_b": 0, "fork_without_S_f_or_break": 0, "report_below_both": 0}
    for r in recs:
        if r["breaks"] and not r["S_b"] > t_b:
            viol["break_without_S_b"] += 1
        if r["forks"] and not (r["S_f"] > t_f or r["breaks"]):
            viol["fork_without_S_f_or_break"] += 1
        if r["S_b"] <= t_b and r["S_f"] <= t_f and (r["breaks"] or r["forks"]):
            viol["report_below_both"] += 1
    t = {k: [r[k] for r in recs] for k in ("gen_s", "evidence_s", "analyse_s")}
    return {
        "arm": arm,
        "frames": n,
        "striped": len(striped),
        "not_striped": n - len(striped),
        "fake_frames": len(fake_frames),
        "fake_rate_over_striped": len(fake_frames) / max(len(striped), 1),
        "total_fakes": total,
        "fake_breaks": sum(len(r["breaks"]) for r in recs),
        "fake_forks": sum(len(r["forks"]) for r in recs),
        "multiplicity_ratio": total / len(fake_frames) if fake_frames else None,
        "fakes_in_fake_regions": in_fake,
        "frames_with_fake_regions": sum(r["fake_regions"] > 0 for r in recs),
        "per_case": per_case,
        "per_case_alarm_cases": alarm,
        "S_b": quantiles(s_b, n),
        "S_f": quantiles(s_f, n),
        "S_b_above_floor": sum(x > FLOOR_B for x in s_b),
        "S_f_above_floor": sum(x > FLOOR_F for x in s_f),
        "S_f_positive": sum(x > 0 for x in s_f),
        "S_b_from_bridge": sum(r["bridge_max"] > r["region_max"] for r in recs),
        "frames_with_bridge_pairs": sum(r["bridge_pairs"] > 0 for r in recs),
        "frames_with_gated_forks": sum(r["n_gated"] > 0 for r in recs),
        "implication_violations": viol,
        "timing_median_s": {k: float(np.median(v)) for k, v in t.items()},
        "timing_sum_s": {k: float(np.sum(v)) for k, v in t.items()},
        "fake_list": [
            {"seed": r["seed"], "case": r["case"], "S_b": r["S_b"], "S_f": r["S_f"],
             "breaks": r["breaks"], "forks": r["forks"]}
            for r in fake_frames
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seeds", type=int, default=len(SEEDS), help="first N prototype seeds (smoke runs)")
    args = ap.parse_args()
    seed_guard.install()
    workers = feasibility.resolve_workers(args.workers)
    seeds = list(SEEDS)[: args.seeds]
    from slow_stamp import loadavg

    info = {"load_start": loadavg(), "workers": workers, "seeds": [seeds[0], seeds[-1]]}
    jobs = [
        (arm, seed, FLOOR_B, FLOOR_F, True, True)
        for arm in ARMS
        for seed in seeds
    ]
    t0 = time.perf_counter()
    recs = feasibility.run_pool(job, jobs, workers)
    info["phase1_wall_s"] = time.perf_counter() - t0
    by_arm = {a: [r for r in recs if r["arm"] == a] for a in ARMS}

    base = by_arm["base"]
    n = len(base)
    k = rank(n, RATE / 2)
    t_b = max(kth_largest([r["S_b"] for r in base], k), FLOOR_B)
    t_f = max(kth_largest([r["S_f"] for r in base], k), FLOOR_F)
    c_b = sum(r["S_b"] > FLOOR_B for r in base)
    c_f = sum(r["S_f"] > FLOOR_F for r in base)
    thresholds = {
        "rate": RATE, "n": n, "k": k, "T_b": t_b, "T_f": t_f,
        "floors_bind": t_b == FLOOR_B and t_f == FLOOR_F,
        "base_frames_S_b_above_floor": c_b, "base_frames_S_f_above_floor": c_f,
        "T_b_above_floor_for_rates_below": (2 * (c_b + 1) / (n + 1)) if c_b else None,
        "T_f_above_floor_for_rates_below": (2 * (c_f + 1) / (n + 1)) if c_f else None,
        "smallest_valid_rate": 2 / (n + 1),
    }
    if not thresholds["floors_bind"]:
        jobs2 = [(arm, seed, t_b, t_f, False, False) for arm in ARMS for seed in seeds]
        t0 = time.perf_counter()
        recs2 = feasibility.run_pool(job, jobs2, workers)
        info["phase2_wall_s"] = time.perf_counter() - t0
        for old, new in zip(recs, recs2, strict=True):
            for key in ("striped", "n_regions", "fake_regions", "breaks", "forks"):
                old[key] = new[key]
    info["load_end"] = loadavg()
    crossing = [
        {"arm": r["arm"], "seed": r["seed"], "S_b": r["S_b"], "S_f": r["S_f"], **(r["crossing"] or {})}
        for r in recs if r.get("crossing") is not None
    ]
    crossing_bad = [
        c for c in crossing
        if any(c.get(name, {"at_S": 0, "just_below": 1})["at_S"] != 0 or c.get(name, {"just_below": 1})["just_below"] < 1
               for name in ("breaks", "forks") if name in c)
    ]
    out = {
        "info": info,
        "thresholds": thresholds,
        "arms": {a: summarise(a, by_arm[a], t_b, t_f, workers) for a in ARMS},
        "crossing_checked": len(crossing),
        "crossing_checked_breaks": sum("breaks" in c for c in crossing),
        "crossing_checked_forks": sum("forks" in c for c in crossing),
        "crossing_failures": crossing_bad,
        "records": recs,
    }
    args.out.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "records"}, indent=1, default=float)[:20000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
