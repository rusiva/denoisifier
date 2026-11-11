"""``analyse``: find the Striped Regions of a frame and measure each one.

Method: local periodicity plus a near-vertical Angle, not feature size
(ADR 0001); the filter bank lives in ``_local_stripes``.

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
   through the depth peak on its top candidate's core
   (``ratio >= _CORE_FRACTION * peak``).
5. Pixels claimed by two qualifying groups go to the one with the higher
   depth there; groups left empty are dropped. ``score`` is the highest peak
   ratio over what is left (0.0 if nothing), and the reported regions are
   those whose peak ratio is above the threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from denoisifier._local_stripes import (
    _A0,
    _ACROSS,
    _PAD,
    _PERIODS,
    LocalStripes,
    _Spectrum,
    estimate_local_stripes,
)
from denoisifier.report import BoundingBox, Region, Report

_log = logging.getLogger(__name__)

# Provisional verdict threshold, carried over from ticket 03: it was set on the
# old score (the frame's maximum ratio) and is not re-derived on the ticket-05
# score (the highest peak ratio of a qualifying region). Ticket 07 replaces it
# with a calibrated value. Its ticket-03 derivation: the log-midpoint of the
# highest stripe-free max ratio (83.7) and the lowest m = 0.5 max ratio (284.8)
# on calibration seeds 100-199 (256x256, ~100 photons, EMCCD, scorched and
# multiscale Mottle). With the ratio floor _A0 = 3e-3, noise-free stripes
# shallower than about _A0 * sqrt(THRESHOLD) ~ 0.04 are never Striped.
THRESHOLD = 154.0

# Smallest side accepted: 2 x the longest period searched; the sigma = 10
# envelope filter needs at least that.
MIN_SIDE = 40
# The filter bank reflect-pads every frame by _PAD px, valid only below the
# shortest side.
assert _PAD < MIN_SIDE

_ENVELOPE_SIGMA = 10.0
_MASK_FRACTION = 0.1
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
# At most this many candidates are grown per frame (highest peaks first).
_MAX_CANDIDATES = 20
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
# would put the peak on a noise or Mottle outlier).
_CORE_FRACTION = 0.5

_EIGHT = np.ones((3, 3), dtype=bool)
_LOG_BANK_STEP = float(np.log(_PERIODS[1] / _PERIODS[0]))


def analyse(frame: np.ndarray, *, threshold: float = THRESHOLD) -> Report:
    """Find the Striped Regions of ``frame`` and measure each one's Period, Angle and depth.

    ``frame`` is a 2D array of intensities, shape ``(rows, cols)``. It is not
    modified. ``threshold`` (>= 0, may be ``inf``) is the stripe score above
    which a region is reported; it changes which regions are reported, never
    their pixels, bounding boxes or measurements, nor the score.
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
    threshold = float(threshold)
    if not threshold >= 0:
        raise ValueError(f"threshold must be >= 0 (or inf), got {threshold!r}")

    env = gaussian_filter(frame, sigma=_ENVELOPE_SIGMA)
    env_max = env.max()
    if env_max <= 0:
        raise ValueError("envelope max <= 0: frame has no positive light")
    # Only keeps the dark surround out of the regions.
    light = env > _MASK_FRACTION * env_max

    local = estimate_local_stripes(frame, light)
    survivors = _qualifying_regions(frame, light, local)
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
        labels=labels,
    )


@dataclass
class _Candidate:
    peak_ratio: float
    core: np.ndarray  # bool, frame shape
    seed: np.ndarray  # bool, frame shape
    grown: np.ndarray  # bool, frame shape
    period: float
    angle_deg: float


@dataclass
class _Group:
    """Merged candidates, measured as one: Period and Angle on the union of
    the seed areas, depth map re-tuned to them."""

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
    frame: np.ndarray, light: np.ndarray, local: LocalStripes
) -> list[_Survivor]:
    """Every size-qualifying group after overlaps are settled (threshold-free)."""
    if not light.any() or not local.ratio.max() > 0:
        return []
    filters = _Filters(_Spectrum(frame), light)
    candidates = _grow_candidates(local, light, filters)
    groups = _merge(candidates, local, filters)
    # A group shallower than the ratio floor's depth _A0 is not stripes (it
    # is what a constant frame's rounding gives); then the size rule.
    qualifying = [
        g
        for g in groups
        if _seed_depth(g.tuned_depth, g.top_seed) >= _A0 and _passes_size_rule(g, filters)
    ]
    return _settle_overlaps(qualifying)


class _Filters:
    """Re-tuned filters on one shared spectrum of the frame (one forward FFT)."""

    def __init__(self, spec: _Spectrum, light: np.ndarray):
        self.spec = spec
        self.light = light
        self._means: dict[float, np.ndarray] = {}

    def depth(self, period: float, angle_deg: float) -> np.ndarray:
        """Local Modulation Depth ``2|response| / local mean`` of the bank-style
        filter at ``period`` and ``angle_deg``; 0 outside the light."""
        if period not in self._means:
            self._means[period] = self.spec.local_mean(period)
        return _depth(self.spec.gabor(period, angle_deg), self._means[period], self.light)

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
        period, angle_deg = _period_and_angle(
            local, seed, float(local.period[peak]), float(local.angle_deg[peak])
        )
        grown = _grow(filters.depth(period, angle_deg), seed, seed, light)
        candidates.append(_Candidate(peak_ratio, core, seed, grown, period, angle_deg))
        claimed |= grown
    return candidates


def _seed_depth(depth: np.ndarray, seed: np.ndarray) -> float:
    """Median depth over the lit part of ``seed`` (all of it if none is lit)."""
    lit = seed & (depth > 0)
    return float(np.median(depth[lit if lit.any() else seed]))


def _grow(
    depth: np.ndarray, reference: np.ndarray, seed: np.ndarray, light: np.ndarray
) -> np.ndarray:
    """The connected parts of ``depth >= _GROW_FRACTION x`` the median depth on
    ``reference``, inside the light, that touch ``seed``."""
    level = _GROW_FRACTION * _seed_depth(depth, reference)
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


def _period_and_angle(
    local: LocalStripes, area: np.ndarray, bank_period: float, bank_angle: float
) -> tuple[float, float]:
    """Fine Period and Angle over ``area`` from the neighbour-product sum.

    Local frequency from the phase step between neighbours (not np.gradient
    of the phase: central differences are biased at short Periods). Fewer
    than _MIN_PAIRS pairs either way: the bank values are returned."""
    h_pairs = area[:, :-1] & area[:, 1:]
    v_pairs = area[:-1, :] & area[1:, :]
    if h_pairs.sum() < _MIN_PAIRS or v_pairs.sum() < _MIN_PAIRS:
        return bank_period, bank_angle
    bank = local.response
    cx = (bank[:, 1:] * np.conj(bank[:, :-1]))[h_pairs].sum()
    cy = (bank[1:, :] * np.conj(bank[:-1, :]))[v_pairs].sum()
    fx, fy = np.angle(cx) / (2 * np.pi), np.angle(cy) / (2 * np.pi)
    f = np.hypot(fx, fy)
    if not f > 0:
        return bank_period, bank_angle
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
            period, angle_deg = _period_and_angle(local, seed, top.period, top.angle_deg)
            tuned_depth = filters.depth(period, angle_deg)
            grown = _grow(tuned_depth, top.seed, seed, filters.light)
        groups.append(
            _Group(
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


def _near(a: _Candidate, b: _Candidate) -> bool:
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
    """Sub-pixel distance between the crossings of half the peak depth on
    ``core``, along the row (axis 1) or the column (axis 0) through that peak."""
    on_seed = np.where(core, depth, -1.0)
    r, c = np.unravel_index(np.argmax(on_seed), depth.shape)
    line = depth[r, :] if axis == 1 else depth[:, c]
    i0 = int(c if axis == 1 else r)
    level = 0.5 * line[i0]

    def edge(step: int) -> float:
        i = i0
        while 0 <= i + step < len(line) and line[i + step] >= level:
            i += step
        if not 0 <= i + step < len(line):
            return float(i)
        a, b = line[i], line[i + step]
        return float(i + step * (a - level) / (a - b))

    return edge(1) - edge(-1)


def _settle_overlaps(groups: list[_Group]) -> list[_Survivor]:
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
                depth=_seed_depth(g.tuned_depth, g.top_seed),
                pixels=pixels,
                bbox=_bbox(pixels),
                area_px=int(flat.size),
                first_pixel=int(flat[0]),
            )
        )
    return survivors


def _bbox(mask: np.ndarray) -> BoundingBox:
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return BoundingBox(int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1)
