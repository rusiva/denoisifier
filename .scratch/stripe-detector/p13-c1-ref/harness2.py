"""PROTOTYPE (ticket 09, P1-2, scope C) -- throwaway. Generate break / break-free frames
and run BASE ``analyse`` once, caching what the post-threshold pass needs:
every survivor (reported or not: R2) with its pixels, refined Period/Angle, depth and
peak ratio, plus the threshold and truth. The frame itself is regenerated later
(``frame_of``), it is cheap.

Breaks are injected by monkeypatching synthetic._phase (no RNG draws), as in harness.py.

Run: uv run --locked python prototypes/p09_breaks/harness2.py <outdir> explore|validate
"""

import math
import pickle
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

import denoisifier.analysis as A  # noqa: E402
import denoisifier.synthetic as S  # noqa: E402
from cases import CASES  # noqa: E402
from denoisifier import BinFactors, analyse  # noqa: E402
from regions import TYPICAL, single_region, truth_pixels, two_regions  # noqa: E402

REGION_SHAPE = (512, 512)
FULL_SHAPE = (400, 1600)
PI = math.pi
J2 = (PI / 2, 2 * PI / 3, PI, -PI / 2, -3 * PI / 4)  # plan 5.2 AC 2 jumps
AC3 = [(45, PI / 2), (45, PI), (90, PI / 2), (90, PI), (-60, PI / 2), (-60, PI)]

BREAKS: list = []  # (Y, X, line_angle_deg, jump) sensor px
_orig_phase = S._phase


def _phase_with_breaks(x, y, period, angle_deg, phase0):
    p = _orig_phase(x, y, period, angle_deg, phase0)
    for r0, c0, a, j in BREAKS:
        t = math.radians(a)
        side = math.cos(t) * (y - r0) - math.sin(t) * (x - c0) > 0
        p = np.where(side, p + j, p)
    return p


S._phase = _phase_with_breaks

CAPTURED: list = []
_orig_q = A._qualifying_regions


def _capture(*args, **kw):
    out = _orig_q(*args, **kw)
    CAPTURED.append(out)
    return out


A._qualifying_regions = _capture


def generate_job(job):
    """-> (frame as analysed, synthetic, true breaks (Y, X, a, j) sensor px, bins)."""
    seed = job["seed"]
    case = CASES[seed % 10]
    if "period" in job:  # v2: explicit Period / Angle (frame-period gate measurement)
        case = type(case)(job["period"], job.get("angle", case.angle_deg))
    h, v = job.get("bins", (1, 1))
    depth = job.get("depth", 0.5)
    if job["kind"] == "region":
        shape = REGION_SHAPE
        reg = single_region(case.period, case.angle_deg, depth=depth)
        center = reg.center
        kw = dict(regions=[reg])
    elif job["kind"] == "two":
        p = job["two_period"]
        a2 = case.angle_deg + job.get("angle_offset", 0.0)
        regs = two_regions(p, p, angle_deg=(case.angle_deg, a2), gap_windows=job["gap_windows"])
        shape = (640, 1024)
        center = ((shape[0] - 1) / 2, (shape[1] - 1) / 2)
        kw = dict(regions=regs)
    elif job["kind"] == "small":
        shape = REGION_SHAPE
        reg = single_region(case.period, case.angle_deg, depth=depth)
        reg = S.StripedRegion(center=reg.center, semi_axes=(job["height"] / 2 * case.period, reg.semi_axes[1]),
                              rotation_deg=0.0, edge_px=reg.edge_px, period=reg.period,
                              angle_deg=reg.angle_deg, modulation_depth=depth)
        center = reg.center
        kw = dict(regions=[reg])
    else:
        shape = FULL_SHAPE
        center = ((shape[0] * v - 1) / 2, (shape[1] * h - 1) / 2)
        kw = dict(period=float(case.period), angle_deg=float(case.angle_deg), modulation_depth=depth)
    sensor_shape = (shape[0] * v, shape[1] * h)
    true_breaks = []
    BREAKS.clear()
    for off, a, j in job.get("breaks", []):
        off = off * (job["two_period"] if job["kind"] == "two" else case.period)  # offsets in Periods along the normal
        t = math.radians(a)
        b = (center[0] + off * math.cos(t), center[1] - off * math.sin(t), a, j)
        BREAKS.append(b)
        true_breaks.append(b)
    s = S.generate(seed=seed, shape=sensor_shape, mottle=job.get("mottle", "scorched"), **kw, **TYPICAL)
    BREAKS.clear()
    frame = s.frame
    if (h, v) != (1, 1):
        frame = frame.reshape(shape[0], v, shape[1], h).sum(axis=(1, 3))
    return frame, s, true_breaks, (h, v)


def run(job):
    CAPTURED.clear()
    frame, s, true_breaks, (h, v) = generate_job(job)
    t0 = time.perf_counter()
    rep = analyse(frame, bin_factors=BinFactors(horizontal=h, vertical=v))
    t_an = time.perf_counter() - t0
    (surv,) = CAPTURED
    case = CASES[job["seed"] % 10]
    if "period" in job:
        case = type(case)(job["period"], job.get("angle", case.angle_deg))
    res = dict(job=job, case=tuple(case), striped=rep.striped, score=rep.score, threshold=rep.threshold,
               n_regions=len(rep.regions), true_breaks=true_breaks, t_analyse=t_an, shape=frame.shape,
               base_regions=[(r.label, r.period_px, r.angle_deg, r.modulation_depth, r.area_px) for r in rep.regions],
               base_labels=np.packbits(rep.labels > 0),
               survivors=[dict(peak_ratio=g.peak_ratio, period=g.period, angle_deg=g.angle_deg, depth=g.depth,
                               pixels=np.packbits(g.pixels), area_px=g.area_px, first_pixel=g.first_pixel)
                          for g in surv])
    if job["kind"] in ("region", "small"):
        res["truth"] = np.packbits(truth_pixels(s.truth.regions[0]))
    elif job["kind"] == "two":
        res["truth_regions"] = [np.packbits(truth_pixels(t)) for t in s.truth.regions]
    else:
        from scipy.ndimage import gaussian_filter

        c = gaussian_filter(s.clean, case.period)
        if (h, v) != (1, 1):
            c = c.reshape(frame.shape[0], v, frame.shape[1], h).mean(axis=(1, 3))
        res["truth"] = np.packbits(c >= 0.1 * c.max())  # lit area (chord domain)
    return res


def jobs_v2_extra():
    """v2 explore additions (109_000-109_599 only): more split-type frames, the break-present
    two-region negative, full frames at P 3-6 for the sample-cap ablation."""
    out = []
    for s in range(109_000, 109_600, 10):  # P 3 seeds (s % 10 == 0), line 45, jump pi
        if s not in (109_530, 109_550, 109_510, 109_520, 109_540, 109_560, 109_570, 109_580, 109_590, 109_500):
            out.append(dict(kind="region", seed=s, breaks=[(0.0, 45.0, PI)], tag="splitx"))
    out += two_break(109_120)
    k = 0
    for s in range(109_200, 109_300):
        if s % 10 in (0, 5, 1, 7):  # P 3, 4, 5, 6
            out.append(dict(kind="full", seed=s, breaks=[(0.0, 0.0, (PI / 2, PI)[k % 2])], tag="fullcap"))
            k += 1
    return out


def two_break(lo):
    """Two real regions, equal Period, Angles 3 or 10 deg apart (> _MERGE_ANGLE_DEG), gap 2 P or
    3 P, one frame-wide horizontal break through both: must stay two regions."""
    out = []
    for k, s in enumerate(range(lo, lo + 20)):
        out.append(dict(kind="two", seed=s, two_period=(5, 8, 12, 6)[k % 4], gap_windows=(2 / 3, 1.0)[(k // 4) % 2],
                        angle_offset=(3.0, 10.0)[(k // 2) % 2], breaks=[(0.0, 0.0, (PI, PI / 2)[k % 2])],
                        tag="two_break"))
    return out


def jobs_gate():
    """Frame-period gate measurement (fresh seeds 110_400-110_459): full frames under 2x1,
    Angle 0, sensor Period 4.0-5.5 (frame Period 2.0-2.75 along the normal), break and free."""
    out = []
    for k, P in enumerate((4.0, 4.2, 4.5, 4.8, 5.0, 5.5)):
        for s in range(110_400 + 10 * k, 110_410 + 10 * k):
            out.append(dict(kind="full", seed=s, period=P, angle=0.0, bins=(2, 1), breaks=[(0.0, 0.0, PI)], tag=f"gate{P}"))
            out.append(dict(kind="full", seed=s, period=P, angle=0.0, bins=(2, 1), breaks=[], tag=f"gatefree{P}"))
    return out


def jobs_validate2():
    """v2 validation, once: fresh seeds 110_000-110_399, with split-type and pair frames."""
    lo, n = 110_000, 400
    out = _ac_jobs(lo, n)
    for s in range(lo, lo + 100):
        out.append(dict(kind="region", seed=s, breaks=[], mottle="multiscale", tag="free_ms"))
    for k, s in enumerate(range(110_300, 110_320)):
        out.append(dict(kind="full", seed=s, breaks=[(0.0, 0.0, PI / 2 if k % 2 == 0 else PI)], tag="full_break"))
        out.append(dict(kind="full", seed=s, breaks=[], tag="full_free"))
    for k, s in enumerate(range(110_320, 110_340)):
        out.append(dict(kind="two", seed=s, two_period=(5, 8, 12, 6)[k % 4], gap_windows=(2 / 3, 1.0)[(k // 4) % 2],
                        breaks=[], tag="two_free"))
    out += two_break(110_340)
    for sep in (2, 3, 4, 5, 6, 8):
        for s in range(110_340, 110_360):
            out.append(dict(kind="full", seed=s, tag=f"pair{sep}", breaks=[(-sep / 2, 0.0, PI / 2), (sep / 2, 0.0, PI)]))
    for hgt in (3, 4, 5, 6, 8):
        for s in range(110_360, 110_380):
            out.append(dict(kind="small", seed=s, height=hgt, tag=f"small{hgt}", breaks=[(0.0, 0.0, PI / 2)]))
    for bins in ((2, 1), (1, 2)):
        for s in range(110_380, 110_400):
            if s % 10 == 0:
                continue
            out.append(dict(kind="full", seed=s, tag=f"bin{bins[0]}x{bins[1]}", bins=bins, breaks=[(0.0, 0.0, PI)]))
    for s in range(lo, lo + n, 10):  # split-type: P 3, line 45, jump pi
        out.append(dict(kind="region", seed=s, breaks=[(0.0, 45.0, PI)], tag="split"))
    return out


def _ac_jobs(lo, n):
    out = []
    half = n // 2
    for k in range(n):
        s = lo + k
        case = CASES[s % 10]
        if k < half:
            a = case.angle_deg + (0, 5, -5)[s % 3]
            j = J2[(k // 10) % 5]
            out.append(dict(kind="region", seed=s, breaks=[(0.0, float(a), j)], tag="ac2"))
        else:
            a, j = AC3[((k - half) // 10) % 6]
            out.append(dict(kind="region", seed=s, breaks=[(0.0, float(a), j)], tag="ac3"))
        out.append(dict(kind="region", seed=s, breaks=[], tag="free"))
    return out


def jobs(which):
    if which == "v2extra":
        return jobs_v2_extra()
    if which == "gate":
        return jobs_gate()
    if which == "validate2":
        return jobs_validate2()
    lo, n = (109_000, 600) if which == "explore" else (109_600, 400)
    out = []
    half = n // 2
    for k in range(n):
        s = lo + k
        case = CASES[s % 10]
        if k < half:
            a = case.angle_deg + (0, 5, -5)[s % 3]
            j = J2[(k // 10) % 5]
            out.append(dict(kind="region", seed=s, breaks=[(0.0, float(a), j)], tag="ac2"))
        else:
            a, j = AC3[((k - half) // 10) % 6]
            out.append(dict(kind="region", seed=s, breaks=[(0.0, float(a), j)], tag="ac3"))
        out.append(dict(kind="region", seed=s, breaks=[], tag="free"))
    for s in range(lo, lo + 100):
        out.append(dict(kind="region", seed=s, breaks=[], mottle="multiscale", tag="free_ms"))
    fl = 109_400 if which == "explore" else 109_900
    for k, s in enumerate(range(fl, fl + 20)):
        j = PI / 2 if k % 2 == 0 else PI
        out.append(dict(kind="full", seed=s, breaks=[(0.0, 0.0, j)], tag="full_break"))
        out.append(dict(kind="full", seed=s, breaks=[], tag="full_free"))
    # break-free pairs of compatible neighbouring regions (R1): gap 2 P and 3 P
    tl = 109_100 if which == "explore" else 109_620
    for k, s in enumerate(range(tl, tl + 20)):
        out.append(dict(kind="two", seed=s, two_period=(5, 8, 12, 6)[k % 4], gap_windows=(2 / 3, 1.0)[(k // 4) % 2],
                        breaks=[], tag="two_free"))
    pl = 109_440 if which == "explore" else 109_940
    for sep in (2, 3, 4, 5, 6, 8):
        for s in range(pl, pl + 20):
            out.append(dict(kind="full", seed=s, tag=f"pair{sep}",
                            breaks=[(-sep / 2, 0.0, PI / 2), (sep / 2, 0.0, PI)]))
    sl = 109_460 if which == "explore" else 109_980
    for hgt in (3, 4, 5, 6, 8):
        for s in range(sl, sl + 20):
            out.append(dict(kind="small", seed=s, height=hgt, tag=f"small{hgt}", breaks=[(0.0, 0.0, PI / 2)]))
    bl = 109_500 if which == "explore" else 109_960
    for bins in ((2, 1), (1, 2)):
        for s in range(bl, bl + 20):
            if s % 10 == 0:  # P = 3 is unresolved under binning
                continue
            out.append(dict(kind="full", seed=s, tag=f"bin{bins[0]}x{bins[1]}", bins=bins,
                            breaks=[(0.0, 0.0, PI)]))
    if which == "explore":  # handoff-1 split frames (P 3, line 45 deg, jump pi), old geometry
        for s in (109_530, 109_550, 109_510, 109_520, 109_540, 109_560, 109_570, 109_580, 109_590, 109_500):
            out.append(dict(kind="region", seed=s, breaks=[(0.0, 45.0, PI)], tag="split"))
    if which == "explore":  # information only: weaker depth (critic 2, 3.1)
        for s in range(lo, lo + 60):
            case = CASES[s % 10]
            out.append(dict(kind="region", seed=s, depth=0.25, tag="weak",
                            breaks=[(0.0, float(case.angle_deg), J2[(s - lo) // 10 % 5])]))
    return out


if __name__ == "__main__":
    out = Path(sys.argv[1])
    which = sys.argv[2]
    js = jobs(which)
    if len(sys.argv) > 3:  # tag-prefix filter, output suffix
        js = [j for j in js if j["tag"].startswith(tuple(sys.argv[3].split(",")))]
        which = which + "_" + sys.argv[4]
    t = time.time()
    with Pool(15) as pool:
        results = pool.map(run, js, chunksize=2)
    with open(out / f"base_{which}.pkl", "wb") as f:
        pickle.dump(results, f, protocol=5)
    print("done", len(results), round(time.time() - t, 1))
