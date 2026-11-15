"""How close a measured Period, Angle and Modulation Depth, a found Phase Break and found Forks
must be to the generator's ground truth. The tolerances are protected numbers (protected.py)."""

import math

import numpy as np
from scipy.ndimage import gaussian_filter

from binning import bin_truth_mask
from denoisifier._local_phase import wrap_jump
from protected import (
    ANGLE_TOL_DEG,
    BREAK_CHORD_COVER_MIN,
    BREAK_JUMP_TOL_RAD,
    BREAK_LIT_LEVEL,
    BREAK_LIT_SIGMA_PX,
    BREAK_POSITION_TOL_PERIODS,
    BREAK_SIDE_COVER_MIN,
    BREAK_SIDE_EXCLUDE_PERIODS,
    DEPTH_TOL,
    FORK_POSITION_TOL_PERIODS,
    PERIOD_REL_TOL,
)


def assert_matches_truth(period_px, angle_deg, truth):
    assert abs(period_px - truth.period) <= PERIOD_REL_TOL * truth.period
    assert abs(angle_deg - truth.angle_deg) <= ANGLE_TOL_DEG


def assert_depth_matches(depth, truth):
    assert abs(depth - truth.modulation_depth) <= DEPTH_TOL


# --- Phase Breaks (ticket 09, plan 5.1 and 5.3) ----------------------------------------


def _sensor_centres(rows, cols, bins):
    """Sensor (Y, X) of frame pixel centres: v r + (v - 1) / 2, h c + (h - 1) / 2."""
    return bins.vertical * rows + (bins.vertical - 1) / 2, bins.horizontal * cols + (
        bins.horizontal - 1
    ) / 2


def _across_along(truth, y, x):
    """Signed distance from the true line (positive side > 0) and position along it, sensor px."""
    t = math.radians(truth.line_angle_deg)
    dy, dx = y - truth.point[0], x - truth.point[1]
    return math.cos(t) * dy - math.sin(t) * dx, math.cos(t) * dx + math.sin(t) * dy


def _chord(mask, truth, bins):
    """(lo, hi) along the true line of ``mask``'s pixels within half a pixel of it, or None."""
    rows, cols = np.nonzero(mask)
    y, x = _sensor_centres(rows, cols, bins)
    across, along = _across_along(truth, y, x)
    near = np.abs(across) <= 0.5 * max(bins.vertical, bins.horizontal)
    if not near.any():
        return None
    return float(along[near].min()), float(along[near].max())


def break_problems(found, truth, chord_mask, overshoot_mask, period, bins):
    """Why ``found`` (a ``PhaseBreak``) does not match ``truth`` (a ``BreakTruth``) by plan 5.1's
    line, coverage, overshoot and jump rules ([] when it does). ``chord_mask`` and
    ``overshoot_mask`` are frame-shaped bool masks; distances are in sensor px under ``bins``."""
    tol = BREAK_POSITION_TOL_PERIODS * period
    (r0, c0), (r1, c1) = found.line[0], found.line[-1]
    steps = max(1, math.ceil(math.hypot(r1 - r0, c1 - c0)))
    f = np.linspace(0.0, 1.0, steps + 1)
    y, x = _sensor_centres(r0 + f * (r1 - r0), c0 + f * (c1 - c0), bins)
    across, along = _across_along(truth, y, x)
    problems = []
    if np.abs(across).max() > tol:
        problems.append(f"line: {np.abs(across).max():.2f} px from the truth, tol {tol:.2f}")
    chord = _chord(chord_mask, truth, bins)
    if chord is None:
        problems.append("coverage: no chord")
    else:
        lo, hi = float(along.min()), float(along.max())
        cover = max(0.0, min(hi, chord[1]) - max(lo, chord[0])) / max(chord[1] - chord[0], 1e-9)
        if cover < BREAK_CHORD_COVER_MIN:
            problems.append(f"coverage: {cover:.3f} of the chord, min {BREAK_CHORD_COVER_MIN}")
    over = _chord(overshoot_mask, truth, bins)
    if over is not None and (along.min() < over[0] - tol or along.max() > over[1] + tol):
        problems.append(f"overshoot: ends {along.min():.1f}..{along.max():.1f}, chord {over}")
    dy, dx = y[-1] - y[0], x[-1] - x[0]
    t = math.radians(truth.line_angle_deg)
    jump = found.jump_rad if math.cos(t) * dx + math.sin(t) * dy >= 0 else -found.jump_rad
    if abs(wrap_jump(jump - truth.jump_rad)) > BREAK_JUMP_TOL_RAD:
        problems.append(f"jump: {jump:.3f} (direction-aligned) vs {truth.jump_rad:.3f}")
    return problems


def assert_break_matches(found, truth, chord_mask, overshoot_mask, period, bins):
    """Exactly one of ``found`` (the reported ``PhaseBreak``s of one region) matches ``truth``
    (plan 5.1); returns it. Chord: region frames, the truth region (``mask >= 0.5``, binned);
    full frames, ``truth_lit_mask``. Overshoot: region frames, the truth region; full frames,
    the frame-clipped line (an all-True mask), so the bound is vacuous there and region frames
    carry it. "No extras" is the caller's count of ``found``."""
    problems = [break_problems(f, truth, chord_mask, overshoot_mask, period, bins) for f in found]
    matched = [f for f, p in zip(found, problems, strict=True) if not p]
    assert len(matched) == 1, f"{len(matched)} of {len(found)} breaks match: {problems}"
    return matched[0]


def assert_region_covers_both_sides(region_mask, truth_mask, line, period, bins):
    """Plan 5.3: on each side of the true ``line`` (``BreakTruth``), the truth pixels farther
    than BREAK_SIDE_EXCLUDE_PERIODS Periods from it are at least BREAK_SIDE_COVER_MIN in
    ``region_mask``. A side with no such truth pixel fails."""
    rows, cols = np.nonzero(truth_mask)
    across, _ = _across_along(line, *_sensor_centres(rows, cols, bins))
    far = BREAK_SIDE_EXCLUDE_PERIODS * period
    inside = region_mask[rows, cols]
    for name, side in (("positive", across > far), ("negative", across < -far)):
        assert side.any(), f"no truth pixels on the {name} side"
        share = float(inside[side].mean())
        assert share >= BREAK_SIDE_COVER_MIN, f"{name} side covered {share:.3f}"


def truth_lit_mask(synthetic, bins):
    """The generator-side lit mask of a full frame (plan 5.1; never ``analysis._light``): the
    clean frame smoothed at BREAK_LIT_SIGMA_PX at sensor size, block-meaned to the frame, at or
    above BREAK_LIT_LEVEL of its maximum."""
    smooth = gaussian_filter(synthetic.clean, BREAK_LIT_SIGMA_PX)
    frame = bin_truth_mask(smooth, bins.horizontal, bins.vertical)
    return frame >= BREAK_LIT_LEVEL * frame.max()


# --- Forks (ticket 10, plan 5.1) --------------------------------------------------------


def fork_problems(report_forks, truth_forks, period, bins):
    """Why the reported forks (``Fork``s, frame px) do not match the true ones (``ForkTruth``s,
    sensor px) by plan 5.1 ([] when they do): each true fork has exactly one reported fork
    within FORK_POSITION_TOL_PERIODS x ``period`` (Euclidean, sensor geometry; frame pixel r
    has its sensor centre at v r + (v - 1) / 2), with the true direction (as given, never
    either sign); and every reported fork is matched to a true fork, one to one."""
    tol = FORK_POSITION_TOL_PERIODS * period
    found = [_sensor_centres(*f.point, bins) for f in report_forks]
    problems = []
    used: dict[int, int] = {}
    for t, truth in enumerate(truth_forks):
        near = [
            i
            for i, (y, x) in enumerate(found)
            if math.hypot(y - truth.point[0], x - truth.point[1]) <= tol
        ]
        if len(near) != 1:
            problems.append(f"fork {t} at {truth.point}: {len(near)} reported within {tol:.2f}")
            continue
        (i,) = near
        if report_forks[i].direction != truth.direction:
            problems.append(
                f"fork {t}: direction {report_forks[i].direction}, true {truth.direction}"
            )
        if i in used:
            problems.append(f"reported fork {i} matches true forks {used[i]} and {t}")
        used[i] = t
    for i, f in enumerate(report_forks):
        if i not in used:
            problems.append(f"extra fork {f}")
    return problems


def assert_forks_match(report_forks, truth_forks, period, bins):
    """Plan 5.1: the reported forks match the true ones, no extras (``fork_problems``)."""
    problems = fork_problems(report_forks, truth_forks, period, bins)
    assert not problems, problems
