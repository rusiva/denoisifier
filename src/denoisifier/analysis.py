"""``analyse``: find the Striped Regions of a frame and measure each one.

Method: local periodicity plus a near-vertical Angle, not feature size
(ADR 0001); the filter bank lives in ``_local_stripes``.

Data quality comes first (``_data_quality``). Spike pixels (cosmic-ray hits
and hot pixels: single pixels and short streaks, at least the frame's
peak-over-pedestal scale brighter than their column neighbours) are found and
replaced by their column neighbours' median in a working copy; every later
step runs on that copy, and the caller's frame is never changed. Clipped
Pixels (at or above the clip level: by default a plateau of at least
``_MIN_CLIPPED_PIXELS`` equal values at the frame's maximum, or the caller's
``clip_level``) that are not Spike pixels are left out of the Modulation
Depth only; detection, Period, Angle, region growth and the mask use them as
they are. This does not recover the depth when a large share of a region is
clipped (above about a fifth): the reported depth then drifts toward the
flattened value, silently per region, and ``Report.clipped_pixels`` is the
frame-level warning.

Regions are built without reference to the threshold, so the verdict, the
score and the reported regions always agree:

1. Seeds: local maxima of the bank's ratio inside the light, visited from the
   highest down. A seed area is the connected part of
   ``ratio >= _SEED_FRACTION * peak`` around the peak, split by bank Period.
2. Each candidate gets its Period and Angle from the neighbour-product sum on
   its seed area, and is grown on the depth map of one filter re-tuned to
   them, out to ``_GROW_FRACTION`` of the median depth on the seed area.
3. Fragments of one stripe set are merged by complete linkage on Period,
   Angle and distance; a candidate that is not merged but grows mostly over
   an earlier group's extent (``_ABSORB_FRACTION``) is dropped as a fragment
   of it.
4. Each group must be at least 3x2 Periods (width x height), measured as
   half-peak widths with a blur correction (``MIN_HALF_DEPTH_*_PERIODS``)
   around the depth peak reached from its top candidate's core
   (``ratio >= _CORE_FRACTION * peak``).
5. A qualifying group that is leakage of a stronger candidate near it (its
   depth collapses when that candidate's stripes are taken out,
   ``_LEAK_FRACTION``) is dropped.
6. Pixels claimed by two qualifying groups go to the one with the higher
   depth there; groups left empty are dropped. ``score`` is the highest peak
   ratio over what is left (0.0 if nothing), and the reported regions are
   those whose peak ratio is above the threshold. Each one's Period and Angle
   are refined on its pixels with a filter re-tuned to them; its depth is the
   median over its interior (``_INTERIOR_FRACTION``), leaving out interior
   pixels near Clipped Pixels (``_CLIPPED_WEIGHT_MAX``).
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from denoisifier._data_quality import find_clipped, reject_spikes
from denoisifier._local_stripes import (
    _A0,
    _ACROSS,
    _ALONG,
    _PAD,
    _PERIODS,
    LocalStripes,
    _Spectrum,
    estimate_local_stripes,
)
from denoisifier.calibration import DEFAULT_FALSE_ALARM_RATE, Calibration, stored_calibration
from denoisifier.report import BoundingBox, Region, Report

_log = logging.getLogger(__name__)

# The verdict threshold is not a constant here: by default it is the stored
# calibration's (``calibration.stored_calibration()``) Threshold at
# ``DEFAULT_FALSE_ALARM_RATE`` (ticket 07, ADR 0002). With the ratio floor
# _A0 = 3e-3, noise-free stripes shallower than about _A0 * sqrt(T) are never
# Striped at a threshold T (about 0.03 at the stored 1% Threshold).

# Smallest side accepted: 2 x the longest period searched; the sigma = 10
# envelope filter needs at least that.
MIN_SIDE = 40
# The filter bank reflect-pads every frame by _PAD px, valid only below the
# shortest side.
assert _PAD < MIN_SIDE

_ENVELOPE_SIGMA = 10.0
_LIGHT_FRACTION = 0.1
# The light is the smoothed frame (_ENVELOPE_SIGMA) above _LIGHT_FRACTION of
# the peak of the frame smoothed with this smaller sigma (px). Smoothing at
# _ENVELOPE_SIGMA flattens the Mottle's bright spots, lowering the maximum
# about 1.2-2x, while it raises the dark surround near the spot's edge and
# the frame's edge: the level fell to about 5% of the Profile's maximum
# (ruling B on the fresh-range misses; on 300 full-frame calibration frames,
# 90_000-90_299, light pixels where the Profile is below 5%: 29 frames at
# sigma 10, 0 at 3). Sigma 3 still averages EMCCD noise over about 100 px.
_LIGHT_PEAK_SIGMA = 3.0
# Fewer horizontal or vertical neighbour pairs than this in a seed area and
# the bank Period and Angle at the peak are used instead.
_MIN_PAIRS = 8

# Size rule (spec: regions under 3 Periods wide or 2 Periods tall are not
# reported). Width: the sub-pixel half-peak width of the re-tuned depth along
# the row through its peak, in measured Periods; the across window
# (sigma 1 Period) blurs it, so an exactly 3-Period-wide region measures about
# 3.1 Periods and the rule reports from about 1.05x the minimum width up
# (prototype P1, seeds 390_000-390_007). Height: the bank's along window
# (sigma 1.5 Periods) cannot resolve 2 Periods, so the height is measured on a
# size-only filter with an along window of SIZE_ALONG_PERIODS; an exactly
# 2-Period-tall region measures about 1.9 Periods (prototype P1-D, seeds
# 391_000-391_007). Detection, score, Period, Angle and depth never use it.
MIN_HALF_DEPTH_WIDTH_PERIODS = 3.24
MIN_HALF_DEPTH_HEIGHT_PERIODS = 1.93
SIZE_ALONG_PERIODS = 0.5

# Region knobs, tuned on REGION_CALIBRATION_SEEDS (tests/calibrate_regions.py;
# .scratch/stripe-detector/region-calibration.json).
# Seeds are local maxima of the ratio over this footprint (px).
_PEAK_FOOTPRINT_PX = 9
# A seed area is the connected part of ratio >= this x its peak ratio.
_SEED_FRACTION = 0.1
# At most this many candidates are grown per frame (highest peaks first). Plan
# rule (N9): at least twice the most candidates any region calibration frame
# needed to reach its last qualifying group, threshold-free and after every
# filter (30, a two-region frame; 36 grown at most, uncapped; probe-shaped
# frames needed 8 of at most 11; tests/calibrate_regions.py, ``reach_last_member``).
_MAX_CANDIDATES = 60
# A seed area whose bank Periods leave a gap of this many bank steps is split.
_SPLIT_LOG_STEPS = 2
# The grown extent keeps depth >= this x the median depth on the seed area.
_GROW_FRACTION = 0.6
# Complete-linkage merge: every pair of members within this Period ratio and
# Angle difference, each member within this many Periods of another.
_MERGE_PERIOD_RATIO = 1.2
_MERGE_ANGLE_DEG = 2.0
_MERGE_GAP_PERIODS = 2.0
# A candidate that grows mostly (more than this fraction of its grown extent)
# over an earlier group's grown extent is a fragment of that group, measured
# off its own Angle near an edge: it is dropped, not reported or merged.
_ABSORB_FRACTION = 0.5
# The size rule's depth peak is looked for on the top candidate's core: the
# connected part of ratio >= this x its peak ratio (the seed area of
# prototype P1, where the size constants were fitted; a larger seed area
# would put the peak on Noise or a bright spot of the Mottle).
_CORE_FRACTION = 0.5
# Leakage: a size-qualifying group near a stronger candidate (higher peak
# ratio, qualifying or not) is that candidate's leakage when its depth on its
# seed area falls below this fraction once the stronger candidate's stripes are
# taken out of the frame (its grown extent set to the local mean). Sharp-edged
# stripes leak response into a halo at nearby Periods and Angles.
_LEAK_FRACTION = 0.5
# Period and Angle of a reported region: the neighbour-product sum of a filter
# re-tuned to the current estimate, over the region's pixels, this many times.
_REFINE_STEPS = 2
# Reported Modulation Depth: the median over the region's interior, its pixels
# at least this fraction of the largest distance from the region's edge
# (_interior_depth). On 556 calibration regions (90_000-90_189: depths 0.2-0.8,
# both Mottles, typical and low noise, full frames, two regions) its error was
# -0.044 to +0.023, against -0.177 to +0.018 for the median over the top
# seed area (33 beyond DEPTH_TOL).
_INTERIOR_FRACTION = 0.5
# The Modulation Depth leaves out interior pixels where the clipped share,
# smoothed over the bank's local-mean window (sigma _ALONG x _ACROSS
# Periods), reaches this (_interior_depth; prototype P2's d9_inner_g10, the
# best of the tested estimators). Set by the pre-freeze check P3 from 0.05,
# 0.10 and 0.20 (evidence/06-prototype-p3.md).
_CLIPPED_WEIGHT_MAX = 0.05

_EIGHT = np.ones((3, 3), dtype=bool)
_LOG_BANK_STEP = float(np.log(_PERIODS[1] / _PERIODS[0]))


def analyse(
    frame: np.ndarray,
    *,
    false_alarm_rate: float | None = None,
    calibration: Calibration | None = None,
    threshold: float | None = None,
    clip_level: float | None = None,
) -> Report:
    """Find the Striped Regions of ``frame`` and measure each one's Period, Angle and depth.

    ``frame`` is a 2D array of intensities, shape ``(rows, cols)``. It is not
    modified.

    The Threshold, the Stripe Score above which a region is reported, is by
    default the stored calibration's at a 1% false-alarm rate
    (``DEFAULT_FALSE_ALARM_RATE``): an order statistic of the Stripe Scores of
    300 generated Stripe-free 400x1600 frames at typical settings (scorched
    Mottle, about 100 photons at the peak, EMCCD noise, 30 Spike events per
    frame, unclipped). ``false_alarm_rate`` picks another rate (``0 < rate <
    1``; the smallest requestable rate is 1/(n + 1)), ``calibration`` another
    Calibration (for example one made on real frames with
    ``calibration.calibrate_folder``), and ``threshold`` (>= 0, may be
    ``inf``) gives the Threshold directly, excluding the other two. The
    Threshold changes which regions are reported, never their pixels,
    bounding boxes or measurements, nor the score; ``Report.threshold`` is the
    one used.

    The stated rate holds for unclipped frames of 400x1600 at typical
    settings. On crops and smaller frames it is expected to be lower (a
    smaller light area), but that is not guaranteed; frames with a larger
    light area and binned frames are not covered. The score can change in
    steps under small pixel changes, because a group appears or vanishes at
    the size and leakage rules, so it is a calibrated verdict statistic more
    than a smooth measure of how close a frame was.

    Spike pixels are always rejected first: replaced by the median of their
    column neighbours in a working copy that every later step uses. The count
    is reliable from about 30 photons at the peak; hot pixels dimmer than
    the frame's peak-over-pedestal scale and long tracks are not rejected.

    ``clip_level`` (frame units) overrides the automatic clip detection:
    pixels at or above it are Clipped Pixels; ``inf`` means nothing is
    clipped; ``NaN`` raises ``ValueError``. ``None`` (the default) detects a
    plateau of equal values at the frame's maximum; a constant frame shows no
    level, and a per-pixel dark subtraction breaks the plateau (give the
    level then). Clipped Pixels are left out of the Modulation Depth only.

    ``Report.spike_pixels`` counts the pixels rejected as Spikes;
    ``Report.clipped_pixels`` the Clipped Pixels that are not Spike pixels,
    so a Spike saturated inside the clip plateau of a bright region is
    counted as clipped.
    """
    frame = np.asarray(frame, dtype=float)
    if frame.ndim != 2:
        raise ValueError(f"frame must be 2D, got {frame.ndim}D")
    if min(frame.shape) < MIN_SIDE:
        raise ValueError(
            f"frame is {frame.shape[0]}x{frame.shape[1]}; "
            f"both sides must be at least {MIN_SIDE} pixels"
        )
    if not np.all(np.isfinite(frame)):
        raise ValueError("frame contains non-finite values (NaN or infinity)")
    threshold = _resolve_threshold(false_alarm_rate, calibration, threshold)
    if not threshold >= 0:
        raise ValueError(f"threshold must be >= 0 (or inf), got {threshold!r}")
    if clip_level is not None:
        clip_level = float(clip_level)
        if np.isnan(clip_level):
            raise ValueError(f"clip_level must be a number or inf, got {clip_level!r}")

    work, spikes = reject_spikes(frame)
    clipped = find_clipped(frame, clip_level) & ~spikes
    light = _light(work)
    local = estimate_local_stripes(work, light)
    survivors = _qualifying_regions(work, light, local, clipped)
    score = max((g.peak_ratio for g in survivors), default=0.0)
    reported = [g for g in survivors if g.peak_ratio > threshold]
    reported.sort(key=lambda g: (-g.area_px, -g.peak_ratio, g.first_pixel))

    labels = np.zeros(frame.shape, dtype=np.int32)
    regions = []
    for k, g in enumerate(reported, start=1):
        labels[g.pixels] = k
        regions.append(
            Region(
                label=k,
                period_px=g.period,
                angle_deg=g.angle_deg,
                modulation_depth=g.depth,
                bbox=g.bbox,
                area_px=g.area_px,
            )
        )
    return Report(
        striped=bool(score > threshold),
        score=float(score),
        threshold=threshold,
        regions=tuple(regions),
        spike_pixels=int(spikes.sum()),
        clipped_pixels=int(clipped.sum()),
        labels=labels,
    )


def _resolve_threshold(
    false_alarm_rate: float | None, calibration: Calibration | None, threshold: float | None
) -> float:
    """The Threshold ``analyse`` uses: ``threshold`` as given, else the
    calibration's Threshold at the false-alarm rate (``None`` takes the
    stored calibration and ``DEFAULT_FALSE_ALARM_RATE``)."""
    if threshold is not None:
        if false_alarm_rate is not None or calibration is not None:
            raise ValueError("threshold= excludes false_alarm_rate= and calibration=")
        return float(threshold)
    cal = stored_calibration() if calibration is None else calibration
    rate = DEFAULT_FALSE_ALARM_RATE if false_alarm_rate is None else false_alarm_rate
    return cal.threshold(rate)


def _light(frame: np.ndarray) -> np.ndarray:
    """The lit part of the frame; only keeps the dark surround out of the
    regions (see _LIGHT_PEAK_SIGMA)."""
    env = gaussian_filter(frame, sigma=_ENVELOPE_SIGMA)
    if env.max() <= 0:
        raise ValueError("envelope max <= 0: frame has no positive light")
    peak = gaussian_filter(frame, sigma=_LIGHT_PEAK_SIGMA).max()
    return np.asarray(env > _LIGHT_FRACTION * peak)


@dataclass
class _Candidate:
    peak_ratio: float
    core: np.ndarray  # bool, frame shape
    seed: np.ndarray  # bool, frame shape
    grown: np.ndarray  # bool, frame shape
    period: float
    angle_deg: float
    depth: float  # median depth on the seed area, at the candidate's tuning (leakage test)


@dataclass
class _Group:
    """Merged candidates, measured as one: Period and Angle on the union of
    the seed areas, depth map re-tuned to them."""

    members: list[_Candidate]
    peak_ratio: float
    top_core: np.ndarray
    top_seed: np.ndarray
    seed: np.ndarray
    grown: np.ndarray
    period: float
    angle_deg: float
    tuned_depth: np.ndarray


@dataclass
class _Survivor:
    """A size-qualifying group with its settled pixels and measurements."""

    peak_ratio: float
    period: float
    angle_deg: float
    depth: float
    pixels: np.ndarray
    bbox: BoundingBox
    area_px: int
    first_pixel: int


def _qualifying_regions(
    frame: np.ndarray, light: np.ndarray, local: LocalStripes, clipped: np.ndarray
) -> list[_Survivor]:
    """Every size-qualifying group after overlaps are settled (threshold-free).
    ``clipped`` (bool, frame shape) is left out of each region's depth only."""
    if not light.any() or not local.ratio.max() > 0:
        return []
    filters = _Filters(_Spectrum(frame), light)
    candidates = _grow_candidates(local, light, filters)
    groups = _merge(candidates, local, filters)
    # A group shallower than the ratio floor's depth _A0 is not stripes (it
    # is what a constant frame's rounding gives); then the size rule, then
    # the leakage test.
    qualifying = [
        g
        for g in groups
        if _median_depth(g.tuned_depth, g.top_seed) >= _A0
        and _passes_size_rule(g, filters)
        and not _is_leakage(g, candidates, frame, filters)
    ]
    return [_refined(s, filters) for s in _settle_overlaps(qualifying, clipped)]


class _Filters:
    """Re-tuned filters on one shared spectrum of the frame (one forward FFT)."""

    def __init__(self, spec: _Spectrum, light: np.ndarray):
        self.spec = spec
        self.light = light
        self._means: dict[float, np.ndarray] = {}

    def mean(self, period: float) -> np.ndarray:
        """The bank-style filter's local mean at ``period`` (cached)."""
        if period not in self._means:
            self._means[period] = self.spec.local_mean(period)
        return self._means[period]

    def depth(self, period: float, angle_deg: float) -> np.ndarray:
        """Local Modulation Depth ``2|response| / local mean`` of the bank-style
        filter at ``period`` and ``angle_deg``; 0 outside the light."""
        return _depth(self.spec.gabor(period, angle_deg), self.mean(period), self.light)

    def size_depth(self, period: float, angle_deg: float) -> np.ndarray:
        """The same with the along window of SIZE_ALONG_PERIODS (size rule only)."""
        t = np.deg2rad(angle_deg)
        spec = self.spec
        across = spec.fx * np.cos(t) + spec.fy * np.sin(t) - 1.0 / period
        along = -spec.fx * np.sin(t) + spec.fy * np.cos(t)
        response = spec.filtered(_size_window(across, along, period))
        mean = np.real(spec.filtered(_size_window(spec.fx, spec.fy, period)))
        return _depth(response, mean, self.light)


def _size_window(across: np.ndarray, along: np.ndarray, period: float) -> np.ndarray:
    sigma_across = 1.0 / (2 * np.pi * _ACROSS * period)
    sigma_along = 1.0 / (2 * np.pi * SIZE_ALONG_PERIODS * period)
    return np.asarray(np.exp(-0.5 * ((across / sigma_across) ** 2 + (along / sigma_along) ** 2)))


def _depth(response: np.ndarray, mean: np.ndarray, light: np.ndarray) -> np.ndarray:
    depth = np.zeros(response.shape)
    np.divide(2 * np.abs(response), mean, out=depth, where=light & (mean > 0))
    return depth


def _grow_candidates(local: LocalStripes, light: np.ndarray, filters: _Filters) -> list[_Candidate]:
    """Seed, split, measure and grow candidates from the highest ratio peaks down."""
    ratio = local.ratio
    is_peak = (
        (ratio == ndimage.maximum_filter(ratio, size=_PEAK_FOOTPRINT_PX)) & (ratio > 0) & light
    )
    rows, cols = np.nonzero(is_peak)
    order = np.argsort(-ratio[rows, cols], kind="stable")
    bank_step = np.zeros(ratio.shape, dtype=int)
    bank_step[light] = np.round(np.log(local.period[light] / _PERIODS[0]) / _LOG_BANK_STEP)

    candidates: list[_Candidate] = []
    claimed = np.zeros(ratio.shape, dtype=bool)
    for i in order:
        peak = (int(rows[i]), int(cols[i]))
        if claimed[peak]:
            continue
        if len(candidates) == _MAX_CANDIDATES:
            _log.info(
                "candidate cap %d reached; highest unvisited peak ratio %.1f",
                _MAX_CANDIDATES,
                float(ratio[peak]),
            )
            break
        peak_ratio = float(ratio[peak])
        # Pixels an earlier (higher) candidate grew over are not seeds again.
        free = ~claimed
        seed = _component((ratio >= _SEED_FRACTION * peak_ratio) & free, peak)
        seed = _split_by_period(seed, bank_step, peak)
        core = seed & _component((ratio >= _CORE_FRACTION * peak_ratio) & free, peak)
        period, angle_deg = _phase_steps(
            local.response, seed, float(local.period[peak]), float(local.angle_deg[peak])
        )
        depth = filters.depth(period, angle_deg)
        grown = _grow(depth, seed, seed, light)
        candidates.append(
            _Candidate(peak_ratio, core, seed, grown, period, angle_deg, _median_depth(depth, seed))
        )
        claimed |= grown
    return candidates


def _median_depth(depth: np.ndarray, area: np.ndarray) -> float:
    """Median depth over the lit part of ``area`` (all of it if none is lit)."""
    lit = area & (depth > 0)
    return float(np.median(depth[lit if lit.any() else area]))


def _grow(
    depth: np.ndarray, reference: np.ndarray, seed: np.ndarray, light: np.ndarray
) -> np.ndarray:
    """The connected parts of ``depth >= _GROW_FRACTION x`` the median depth on
    ``reference``, inside the light, that touch ``seed``."""
    level = _GROW_FRACTION * _median_depth(depth, reference)
    return _touching((depth >= level) & light, seed)


def _component(mask: np.ndarray, at: tuple[int, int]) -> np.ndarray:
    labels, _ = ndimage.label(mask, structure=_EIGHT)
    return np.asarray(labels == labels[at])


def _touching(mask: np.ndarray, seed: np.ndarray) -> np.ndarray:
    """The connected parts of ``mask`` that touch ``seed``."""
    labels, _ = ndimage.label(mask, structure=_EIGHT)
    keep = np.unique(labels[seed])
    return np.asarray(np.isin(labels, keep[keep > 0]))


def _split_by_period(seed: np.ndarray, bank_step: np.ndarray, peak: tuple[int, int]) -> np.ndarray:
    """Cut the seed area at gaps of _SPLIT_LOG_STEPS bank steps; keep the peak's part."""
    steps = np.unique(bank_step[seed])
    cuts = np.nonzero(np.diff(steps) >= _SPLIT_LOG_STEPS)[0]
    if not len(cuts):
        return seed
    parts = np.split(steps, cuts + 1)
    own = next(p for p in parts if bank_step[peak] in p)
    return _component(seed & np.isin(bank_step, own), peak)


def _phase_steps(
    response: np.ndarray, area: np.ndarray, period: float, angle_deg: float
) -> tuple[float, float]:
    """Fine Period and Angle over ``area`` from the summed neighbour products
    of the complex ``response``.

    Local frequency from the phase step between neighbours (not np.gradient
    of the phase: central differences are biased at short Periods).
    ``(period, angle_deg)`` (the starting estimate) is returned when there are
    fewer than _MIN_PAIRS pairs either way or no phase step."""
    h_pairs = area[:, :-1] & area[:, 1:]
    v_pairs = area[:-1, :] & area[1:, :]
    if h_pairs.sum() < _MIN_PAIRS or v_pairs.sum() < _MIN_PAIRS:
        return period, angle_deg
    cx = (response[:, 1:] * np.conj(response[:, :-1]))[h_pairs].sum()
    cy = (response[1:, :] * np.conj(response[:-1, :]))[v_pairs].sum()
    fx, fy = np.angle(cx) / (2 * np.pi), np.angle(cy) / (2 * np.pi)
    f = np.hypot(fx, fy)
    if not f > 0:
        return period, angle_deg
    return float(1.0 / f), float(np.degrees(np.arctan2(fy, fx)))


def _merge(candidates: list[_Candidate], local: LocalStripes, filters: _Filters) -> list[_Group]:
    """Complete-linkage groups, greedy in descending peak order, each re-measured."""
    member_lists: list[list[_Candidate]] = []
    for c in candidates:
        for members in member_lists:
            if all(_compatible(c, m) for m in members) and any(_near(c, m) for m in members):
                members.append(c)
                break
        else:
            if not any(_absorbed(c, members) for members in member_lists):
                member_lists.append([c])

    groups = []
    for members in member_lists:
        top = members[0]
        if len(members) == 1:
            period, angle_deg, seed = top.period, top.angle_deg, top.seed
            tuned_depth = filters.depth(period, angle_deg)
            grown = top.grown
        else:
            # Re-measured and re-grown as one. The level comes from the top
            # member's seed area: a lower member's seed can lie in the skirt
            # of the stripes, where the depth is lower.
            seed = np.logical_or.reduce([m.seed for m in members])
            period, angle_deg = _phase_steps(local.response, seed, top.period, top.angle_deg)
            tuned_depth = filters.depth(period, angle_deg)
            grown = _grow(tuned_depth, top.seed, seed, filters.light)
        groups.append(
            _Group(
                members=members,
                peak_ratio=top.peak_ratio,
                top_core=top.core,
                top_seed=top.seed,
                seed=seed,
                grown=grown,
                period=period,
                angle_deg=angle_deg,
                tuned_depth=tuned_depth,
            )
        )
    return groups


def _absorbed(c: _Candidate, members: list[_Candidate]) -> bool:
    """``c`` grows mostly over the members' grown extents (see _ABSORB_FRACTION)."""
    union = np.logical_or.reduce([m.grown for m in members])
    return bool((c.grown & union).sum() > _ABSORB_FRACTION * c.grown.sum())


def _compatible(a: _Candidate, b: _Candidate) -> bool:
    ratio = max(a.period, b.period) / min(a.period, b.period)
    return ratio <= _MERGE_PERIOD_RATIO and abs(a.angle_deg - b.angle_deg) <= _MERGE_ANGLE_DEG


def _near(a: _Candidate | _Group, b: _Candidate | _Group) -> bool:
    """``a``'s grown extent touches or lies within _MERGE_GAP_PERIODS Periods of ``b``'s."""
    if (a.grown & b.grown).any():
        return True
    gap = _MERGE_GAP_PERIODS * max(a.period, b.period)
    box = _bbox(a.grown)
    pad = int(np.ceil(gap)) + 1
    r0, r1 = max(box.row_start - pad, 0), min(box.row_stop + pad, a.grown.shape[0])
    c0, c1 = max(box.col_start - pad, 0), min(box.col_stop + pad, a.grown.shape[1])
    window_b = b.grown[r0:r1, c0:c1]
    if not window_b.any():
        return False
    distance = ndimage.distance_transform_edt(~a.grown[r0:r1, c0:c1])
    return bool(distance[window_b].min() <= gap)


def _passes_size_rule(group: _Group, filters: _Filters) -> bool:
    """At least 3x2 Periods: half-peak width on the re-tuned depth, half-peak
    height on the short size-only filter (see MIN_HALF_DEPTH_*_PERIODS)."""
    p = group.period
    width = _half_peak_span(group.tuned_depth, group.top_core, axis=1)
    if width < MIN_HALF_DEPTH_WIDTH_PERIODS * p:
        return False
    height = _half_peak_span(filters.size_depth(p, group.angle_deg), group.top_core, axis=0)
    return bool(height >= MIN_HALF_DEPTH_HEIGHT_PERIODS * p)


def _half_peak_span(depth: np.ndarray, core: np.ndarray, axis: int) -> float:
    """Sub-pixel half-peak extent of ``depth`` along the rows (axis 1) or the
    columns (axis 0).

    The peak is the local maximum reached by climbing ``depth`` from its
    largest value on ``core``: the ratio peaks where the reference energy is
    low, which can be in the blurred skirt just outside sharp-edged stripes.
    The extent is the widest run, along ``axis``, of the connected part of
    ``depth >= 0.5 x peak`` that holds the peak, with linear-interpolated ends.
    For a compact, centrally symmetric region this is the run through the
    peak; unlike that run, it is not cut short where a line through the peak
    grazes the edge of the light."""
    on_core = np.where(core, depth, -1.0)
    start = np.unravel_index(np.argmax(on_core), depth.shape)
    peak = _climb(depth, (int(start[0]), int(start[1])))
    level = 0.5 * depth[peak]
    part = _component(depth >= level, peak)
    return _widest_run(depth if axis == 1 else depth.T, part if axis == 1 else part.T, level)


def _climb(depth: np.ndarray, at: tuple[int, int]) -> tuple[int, int]:
    """Steepest ascent on ``depth`` (8 neighbours) from ``at`` to a local maximum."""
    r, c = at
    while True:
        r0, c0 = max(r - 1, 0), max(c - 1, 0)
        window = depth[r0 : r + 2, c0 : c + 2]
        k = np.unravel_index(np.argmax(window), window.shape)
        nr, nc = r0 + int(k[0]), c0 + int(k[1])
        if not depth[nr, nc] > depth[r, c]:
            return r, c
        r, c = nr, nc


def _widest_run(depth: np.ndarray, part: np.ndarray, level: float) -> float:
    """The longest run of ``part`` along a row, its ends interpolated where
    ``depth`` crosses ``level`` (at the frame's edge, the edge pixel)."""
    edges = np.diff(np.pad(part, ((0, 0), (1, 1))).astype(np.int8), axis=1)
    rows, first = np.nonzero(edges == 1)
    _, stop = np.nonzero(edges == -1)
    last = stop - 1
    left = first.astype(float)
    inner = first > 0
    a, b = depth[rows[inner], first[inner]], depth[rows[inner], first[inner] - 1]
    left[inner] -= (a - level) / (a - b)
    right = last.astype(float)
    inner = stop < depth.shape[1]
    a, b = depth[rows[inner], last[inner]], depth[rows[inner], stop[inner]]
    right[inner] += (a - level) / (a - b)
    return float((right - left).max())


def _is_leakage(
    group: _Group, candidates: list[_Candidate], frame: np.ndarray, filters: _Filters
) -> bool:
    """``group`` is leakage of a stronger candidate near it (see _LEAK_FRACTION)."""
    own = _median_depth(group.tuned_depth, group.top_seed)
    for s in candidates:
        if s.peak_ratio <= group.peak_ratio or any(s is m for m in group.members):
            continue
        # Leaked depth is below its source's; and leakage reaches about a window.
        if own >= s.depth or not _near(s, group):
            continue
        without = np.where(s.grown, filters.mean(s.period), frame)
        rest = _Filters(_Spectrum(without), filters.light)
        if _median_depth(rest.depth(group.period, group.angle_deg), group.top_seed) < (
            _LEAK_FRACTION * own
        ):
            return True
    return False


def _refined(region: _Survivor, filters: _Filters) -> _Survivor:
    """Period and Angle re-measured on the region's pixels with a filter
    re-tuned to them (see _REFINE_STEPS): the bank's response is tuned to the
    nearest bank Angle and Period, and noise in it pulls the estimate there."""
    period, angle_deg = region.period, region.angle_deg
    for _ in range(_REFINE_STEPS):
        period, angle_deg = _phase_steps(
            filters.spec.gabor(period, angle_deg), region.pixels, period, angle_deg
        )
    return dataclasses.replace(region, period=period, angle_deg=angle_deg)


def _settle_overlaps(groups: list[_Group], clipped: np.ndarray) -> list[_Survivor]:
    """Give each pixel claimed by several groups to the one with the highest
    depth there; drop groups left empty; measure the rest."""
    if not groups:
        return []
    claims = np.stack([g.grown for g in groups])
    depths = np.stack([np.where(g.grown, g.tuned_depth, -np.inf) for g in groups])
    owner = np.argmax(depths, axis=0)
    claimed = claims.any(axis=0)
    survivors = []
    for k, g in enumerate(groups):
        pixels = claimed & (owner == k)
        if not pixels.any():
            continue
        flat = np.flatnonzero(pixels)
        survivors.append(
            _Survivor(
                peak_ratio=g.peak_ratio,
                period=g.period,
                angle_deg=g.angle_deg,
                depth=_interior_depth(g.tuned_depth, pixels, clipped, g.period),
                pixels=pixels,
                bbox=_bbox(pixels),
                area_px=int(flat.size),
                first_pixel=int(flat[0]),
            )
        )
    return survivors


def _interior_depth(
    depth: np.ndarray, pixels: np.ndarray, clipped: np.ndarray, period: float
) -> float:
    """Median depth over the interior of a region: its pixels at least
    _INTERIOR_FRACTION of the deepest pixel's distance from the region's edge.

    The across window (sigma 1 Period) blurs the depth near the edge; a seed
    area that reaches into that skirt measured up to 0.18 low (ruling A on the
    fresh-range misses).

    Clipped Pixels: interior pixels where the clipped share, smoothed over the
    local-mean window at ``period``, reaches _CLIPPED_WEIGHT_MAX are left out;
    when that leaves nothing, the plain interior is used. This does not
    recover the depth when a large share of a region is clipped (above about a
    fifth): the reported depth then drifts toward the flattened value, with
    no per-region flag; ``Report.clipped_pixels`` is the frame-level warning."""
    distance = ndimage.distance_transform_edt(pixels)
    interior = distance >= _INTERIOR_FRACTION * distance.max()
    if clipped.any():
        weight = gaussian_filter(clipped.astype(float), sigma=(_ALONG * period, _ACROSS * period))
        unclipped = interior & (weight < _CLIPPED_WEIGHT_MAX)
        if unclipped.any():
            return _median_depth(depth, unclipped)
    return _median_depth(depth, interior)


def _bbox(mask: np.ndarray) -> BoundingBox:
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return BoundingBox(int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1)
