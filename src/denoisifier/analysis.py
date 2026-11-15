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
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple, Protocol

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter

from denoisifier._data_quality import find_clipped, reject_spikes
from denoisifier._local_phase import (
    _BREAK_MIN_FRAME_PERIOD_PX,
    _FORK_GATE_EVIDENCE,
    _FORK_MIN_EVIDENCE,
    FoundBreak,
    FoundFork,
    break_response,
    find_forks,
    find_phase_breaks,
    fork_domain,
    forks_explained,
    frame_period,
    sensor_coordinates,
    sigma_n,
)
from denoisifier._local_stripes import (
    _A0,
    _ACROSS,
    _ALONG,
    _PAD,
    _PERIODS,
    MIN_FRAME_PERIOD_PX,
    LocalStripes,
    UnresolvedPeriods,
    _Spectrum,
    estimate_local_stripes,
    frame_px,
    pixel_size,
    searched_periods,
    sensor_frequency,
    unresolved_periods,
)
from denoisifier.calibration import DEFAULT_FALSE_ALARM_RATE, Calibration, stored_calibration
from denoisifier.report import BinFactors, BoundingBox, Fork, PhaseBreak, Region, Report

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
    bin_factors: BinFactors | None = None,
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
    light area and binned frames are not covered. When a Calibration set the
    Threshold, ``Report.warnings`` notes a frame it does not cover: one of
    other bin factors than the Calibration's (binning makes the Mottle
    directional in the frame: Stripe-free scores rose up to 1.9x at the
    shortest searched Period under 1x2), else one with more pixels than its
    frames. The note never changes the verdict or the Threshold.

    The score can change in steps under small pixel changes, because a group
    appears or vanishes at the size and leakage rules, so it is a calibrated
    verdict statistic more than a smooth measure of how close a frame was.

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

    ``bin_factors`` (``BinFactors``, default 1x1) are the frame's bin factors:
    ``horizontal`` sensor pixels summed along a row, ``vertical`` along a
    column. Period and Angle, the searched range (Periods 3-20 px, Angles
    within 10 deg of vertical) and the 3x2-Period minimum are in sensor
    pixels and are converted into frame coordinates before searching; the
    bboxes, areas, the Mask and the pixel counts stay in frame pixels
    (``Report.UNITS``). Bank Periods at which a stripe or reference filter
    falls under ``MIN_FRAME_PERIOD_PX`` frame pixels (the frame's Nyquist
    limit) are not searched: ``Report.unresolved_period_px``
    and a ``Report.warnings`` entry say so (under 2x1 or 1x2, Periods below
    4 px). Factors that leave no Period searchable raise ``ValueError``.
    The Modulation Depth is measured on the frame as given, not corrected
    for binning: summing h pixels across the stripes damps it by
    ``|sin(pi h f) / (h sin(pi f))|`` at sensor frequency f (under 2x1 about
    x0.97 at 12 px, x0.87 at 6 px and x0.73 at 4.2 px).

    Phase Breaks (``Report.phase_breaks``) are searched after the score and
    the Threshold, in the regions above the Threshold and between adjacent
    compatible ones; the score and the verdict never depend on them. The
    reported regions can: a found break may merge two regions it separates
    into one, fill the slit along it, absorb a break-free region lying in that
    slit, and re-measure the region's Period and Angle away from the break
    (kept only when they fit the stripes at least as well as the measured
    ones). The Modulation Depth is the measured one unless regions merged. A
    frame with no found break gets the same regions, labels and measurements
    as without the search. Only straight lines are searched; a region shorter than about
    8 Periods across a line gets no break on it. The evidence threshold is
    conservative on purpose until it is calibrated (ticket 11); no
    false-break rate is claimed.

    Forks (``Report.forks``) are searched after the score and the Threshold
    too, in the reported regions only (a Fork outside every reported region
    is not reported), Fork first: a search before the break pass, with no
    break explained away; when it finds a Fork with evidence at least
    ``_FORK_GATE_EVIDENCE``, the break pass reads the finder's response with
    those Forks' winding taken out, and otherwise runs as without Forks. The
    reported Forks come from a second search, after the pass, in the settled
    regions, on the uncorrected response with each region's found breaks
    explained away (evidence at least ``_FORK_MIN_EVIDENCE``). On a frame
    where the first search finds no such Fork, the regions, labels,
    measurements, breaks and warnings are those of the break pass alone;
    where it does, the pass can fill, bridge, re-measure and find breaks
    differently. Limits, as measured (``find_forks``): a Fork within about 4
    Periods of its region's edge is not found; two Forks, or a Fork and a
    Phase Break, are resolved 4 Periods apart in a large region and are
    undefined closer. The evidence thresholds are conservative until they
    are calibrated (ticket 11); no false-fork rate is claimed.

    Phase Breaks and Forks are not searched in a region whose stripes fall
    under 2.5 frame pixels along their normal (under binning);
    ``Report.warnings`` then holds, for each such region, "region {label}
    (Period {P} px): phase breaks and forks were not searched at {bins}
    binning: its stripes fall under 2.5 frame pixels along their normal
    ({frame Period})". There a break is not found, and a region it splits
    stays split. A refused region the search joins to another keeps its
    warning, under the label of the region it joined and with its own
    Period, and the region it joined gets no Fork search. A region the break
    pass re-measures under 2.5 frame pixels gets neither Forks nor a warning
    (rare; not measured).
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
    bins = BinFactors.of(bin_factors)
    if not len(searched_periods(bins)):
        raise ValueError(
            f"at {bins} binning no Period from {_PERIODS[0]:g} to {_PERIODS[-1]:g} px "
            f"can be searched: every one falls under {MIN_FRAME_PERIOD_PX:g} frame pixels"
        )
    threshold, used = _resolve_threshold(false_alarm_rate, calibration, threshold)
    if not threshold >= 0:
        raise ValueError(f"threshold must be >= 0 (or inf), got {threshold!r}")
    if clip_level is not None:
        clip_level = float(clip_level)
        if np.isnan(clip_level):
            raise ValueError(f"clip_level must be a number or inf, got {clip_level!r}")

    work, spikes = reject_spikes(frame)
    clipped = find_clipped(frame, clip_level) & ~spikes
    light = _light(work)
    local = estimate_local_stripes(work, light, bins)
    survivors, filters = _qualifying_regions(work, light, local, clipped, bins)
    score = max((g.peak_ratio for g in survivors), default=0.0)
    reported = [g for g in survivors if g.peak_ratio > threshold]
    # Forks and Phase Breaks: after the score and the threshold, never read back by them.
    refused = [g for g in reported if _refused(g, bins)]
    settled: list[tuple[_Survivor, list[FoundBreak]]] = [(g, []) for g in reported]
    responses = None
    if filters is not None and reported:
        responses = _Responses(filters.spec)
        gated = _pre_break_forks(reported, refused, responses, bins)
        field = responses if not gated else _ForksExplained(responses, gated, bins)
        settled = _with_phase_breaks(reported, filters, clipped, field)
    settled.sort(key=lambda r: (-r[0].area_px, -r[0].peak_ratio, r[0].first_pixel))

    labels = np.zeros(frame.shape, dtype=np.int32)
    regions = []
    phase_breaks: list[PhaseBreak] = []
    for k, (g, found) in enumerate(settled, start=1):
        labels[g.pixels] = k
        phase_breaks += _reported_breaks(k, g.pixels, found, bins)
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
    phase_breaks.sort(key=lambda b: (b.region, -abs(b.jump_rad), b.line[0]))
    forks: list[Fork] = []
    if responses is not None:
        forks = _post_break_forks(settled, refused, responses, bins)
    unresolved = unresolved_periods(bins)
    warnings = [] if unresolved is None else [_unresolved_warning(unresolved, bins)]
    # Every region above the threshold lies inside one reported region (the
    # pass only adds pixels), so its first pixel names the region it joined.
    refused.sort(key=lambda g: (int(labels.flat[g.first_pixel]), g.first_pixel))
    warnings += [_refusal_warning(int(labels.flat[g.first_pixel]), g, bins) for g in refused]
    if used is not None:
        warnings += _coverage_note(used, frame.shape, bins)
    return Report(
        striped=bool(score > threshold),
        score=float(score),
        threshold=threshold,
        regions=tuple(regions),
        spike_pixels=int(spikes.sum()),
        clipped_pixels=int(clipped.sum()),
        labels=labels,
        phase_breaks=tuple(phase_breaks),
        forks=tuple(forks),
        bin_factors=bins,
        unresolved_period_px=(
            None if unresolved is None else (unresolved.shortest, unresolved.limit)
        ),
        warnings=tuple(warnings),
    )


def _unresolved_warning(unresolved: UnresolvedPeriods, bins: BinFactors) -> str:
    """The Report warning for the unsearched part of the Period range, naming
    the filters that fall under ``MIN_FRAME_PERIOD_PX`` frame pixels there."""
    limit, under = unresolved.limit, f"under {MIN_FRAME_PERIOD_PX:g} frame pixels"
    if unresolved.by == "stripe":
        return (
            f"Periods below {limit:g} px cannot be resolved at {bins} binning: the stripes "
            f"fall {under}; they were not searched"
        )
    if unresolved.by == "reference":
        return (
            f"Periods below {limit:g} px were not searched at {bins} binning: the 90-deg "
            f"reference filters fall {under} (the stripes do not)"
        )
    return (
        f"Periods below {limit:g} px cannot be resolved at {bins} binning: the stripes and "
        f"their 90-deg reference filters fall {under}; they were not searched"
    )


def _refusal_warning(label: int, region: _Survivor, bins: BinFactors) -> str:
    """The Report warning for a region whose Phase Breaks and Forks were not searched."""
    return (
        f"region {label} (Period {region.period:.3g} px): phase breaks and forks were not "
        "searched at "
        f"{bins} binning: its stripes fall under {_BREAK_MIN_FRAME_PERIOD_PX:g} frame pixels "
        f"along their normal ({frame_period(region.period, region.angle_deg, bins):.3g})"
    )


def _refused(region: _Survivor, bins: BinFactors) -> bool:
    """Whether ``region``'s stripes fall under the finders' frame-period
    limit: it gets a refusal warning and neither a Phase Break nor a Fork
    search."""
    return frame_period(region.period, region.angle_deg, bins) < _BREAK_MIN_FRAME_PERIOD_PX


class _Responses:
    """The finder's response (``break_response``) per (Period, Angle),
    computed once per frame and shared by the Phase Break pass and both Fork
    searches."""

    def __init__(self, spec: _Spectrum):
        self.spec = spec
        self._cache: dict[tuple[float, float], np.ndarray] = {}

    def response(self, period: float, angle_deg: float) -> np.ndarray:
        key = (period, angle_deg)
        if key not in self._cache:
            self._cache[key] = break_response(self.spec, period, angle_deg)
        return self._cache[key]


class _ForksExplained:
    """A view of ``raw`` with the winding of ``forks`` taken out of every
    response (``forks_explained``); ``raw`` is not changed."""

    def __init__(self, raw: _Responses, forks: list[FoundFork], bins: BinFactors):
        self.raw = raw
        self.forks = forks
        self.bins = bins
        self._cache: dict[tuple[float, float], np.ndarray] = {}

    def response(self, period: float, angle_deg: float) -> np.ndarray:
        key = (period, angle_deg)
        if key not in self._cache:
            z = self.raw.response(period, angle_deg)
            self._cache[key] = forks_explained(z, self.forks, self.bins)
        return self._cache[key]


class _ResponseSource(Protocol):
    def response(self, period: float, angle_deg: float) -> np.ndarray: ...


def _holds_refused(region: _Survivor, refused: list[_Survivor]) -> bool:
    """Whether ``region`` holds a pixel of a ``refused`` region (one of them,
    or a region the break pass joined one into): it gets no Fork search."""
    return any((region.pixels & r.pixels).any() for r in refused)


def _region_forks(
    region: _Survivor,
    owned: np.ndarray,
    responses: _ResponseSource,
    bins: BinFactors,
    min_evidence: float,
    breaks: Sequence[FoundBreak] = (),
) -> list[FoundFork]:
    """The Fork candidates of ``region`` with evidence at least
    ``min_evidence``: ``find_forks`` on its ``fork_domain`` (``owned`` = all
    regions' pixels) of its response, ``breaks`` explained away."""
    domain = fork_domain(region.pixels, owned & ~region.pixels, region.period, bins)
    z = responses.response(region.period, region.angle_deg)
    found = find_forks(z, domain, region.period, region.angle_deg, bins, breaks)
    return [f for f in found if f.evidence >= min_evidence]


def _pre_break_forks(
    reported: list[_Survivor], refused: list[_Survivor], responses: _Responses, bins: BinFactors
) -> list[FoundFork]:
    """The pre-break Fork search: every candidate with evidence at least
    _FORK_GATE_EVIDENCE in each reported region that is not ``refused``, no
    Phase Break explained away."""
    owned = np.logical_or.reduce([g.pixels for g in reported])
    out = []
    for g in reported:
        if not _holds_refused(g, refused):
            out += _region_forks(g, owned, responses, bins, _FORK_GATE_EVIDENCE)
    return out


def _post_break_forks(
    settled: list[tuple[_Survivor, list[FoundBreak]]],
    refused: list[_Survivor],
    responses: _Responses,
    bins: BinFactors,
) -> list[Fork]:
    """The reported Forks: the post-break search in each settled region
    (label = position in ``settled`` + 1) holding no pixel of a ``refused``
    region, on the raw response with the region's found breaks explained
    away; candidates with evidence at least _FORK_MIN_EVIDENCE. Ordered by
    region, then point (row-major)."""
    if not settled:
        return []
    owned = np.logical_or.reduce([g.pixels for g, _ in settled])
    out = []
    for label, (g, found) in enumerate(settled, start=1):
        if not _holds_refused(g, refused):
            forks = _region_forks(g, owned, responses, bins, _FORK_MIN_EVIDENCE, found)
            out += _reported_forks(label, forks, bins)
    out.sort(key=lambda f: (f.region, f.point))
    return out


def _reported_forks(label: int, found: list[FoundFork], bins: BinFactors) -> list[Fork]:
    """Each found Fork of region ``label``, its point in frame px."""
    out = []
    for f in found:
        row, col = frame_px(bins, f.point[0], f.point[1])
        out.append(Fork(region=label, point=(float(row), float(col)), direction=f.direction))
    return out


def _resolve_threshold(
    false_alarm_rate: float | None, calibration: Calibration | None, threshold: float | None
) -> tuple[float, Calibration | None]:
    """``(Threshold, Calibration that set it)``: ``threshold`` as given (no
    Calibration), else the calibration's Threshold at the false-alarm rate
    (``None`` takes the stored calibration and ``DEFAULT_FALSE_ALARM_RATE``)."""
    if threshold is not None:
        if false_alarm_rate is not None or calibration is not None:
            raise ValueError("threshold= excludes false_alarm_rate= and calibration=")
        return float(threshold), None
    cal = stored_calibration() if calibration is None else calibration
    rate = DEFAULT_FALSE_ALARM_RATE if false_alarm_rate is None else false_alarm_rate
    return cal.threshold(rate), cal


def _coverage_note(cal: Calibration, shape: tuple[int, ...], bins: BinFactors) -> list[str]:
    """At most one note that ``cal``'s false-alarm rate does not cover this
    frame: other bin factors, else more pixels than its frames. Smaller
    frames are not noted (their rate is expected to be lower). The note never
    changes the verdict or the Threshold."""
    if cal.bin_factors != bins:
        return [
            f"the calibration was made at {cal.bin_factors} binning; its false-alarm rate "
            f"does not cover {bins} frames (binning makes the Mottle directional in the "
            "frame: Stripe-free scores up to 1.9x at the shortest searched Period)"
        ]
    rows, cols = shape
    cal_rows, cal_cols = cal.shape
    if rows * cols > cal_rows * cal_cols:
        return [
            f"frame {rows}x{cols} has more pixels than the calibration's {cal_rows}x{cal_cols}; "
            "its false-alarm rate is not covered"
        ]
    return []


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
    frame: np.ndarray,
    light: np.ndarray,
    local: LocalStripes,
    clipped: np.ndarray,
    bins: BinFactors,
) -> tuple[list[_Survivor], _Filters | None]:
    """Every size-qualifying group after overlaps are settled (threshold-free),
    and the filters they were measured with (None when there was nothing to
    measure). ``clipped`` (bool, frame shape) is left out of each region's
    depth only."""
    if not light.any() or not local.ratio.max() > 0:
        return [], None
    filters = _Filters(_Spectrum(frame, bins), light)
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
    return [
        _refined(s, filters) for s in _settle_overlaps(qualifying, clipped, filters.bins)
    ], filters


class _Filters:
    """Re-tuned filters on one shared spectrum of the frame (one forward FFT).

    The bin factors enter the region steps once, with the spectrum; every
    step reads them as ``filters.bins`` and hands them to the helpers that
    take no ``_Filters`` (``_phase_steps``, ``_near``, ``_settle_overlaps``)."""

    def __init__(self, spec: _Spectrum, light: np.ndarray):
        self.spec = spec
        self.light = light
        self._means: dict[float, np.ndarray] = {}

    @property
    def bins(self) -> BinFactors:
        return self.spec.bins

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
            local.response,
            seed,
            float(local.period[peak]),
            float(local.angle_deg[peak]),
            filters.bins,
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
    response: np.ndarray, area: np.ndarray, period: float, angle_deg: float, bins: BinFactors
) -> tuple[float, float]:
    """Fine Period and Angle over ``area`` from the summed neighbour products
    of the complex ``response``, in sensor px under ``bins`` (each axis's
    frame phase step over its bin factor).

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
    fy, fx = sensor_frequency(bins, np.angle(cy) / (2 * np.pi), np.angle(cx) / (2 * np.pi))
    f = np.hypot(fx, fy)
    if not f > 0:
        return period, angle_deg
    return float(1.0 / f), float(np.degrees(np.arctan2(fy, fx)))


def _merge(candidates: list[_Candidate], local: LocalStripes, filters: _Filters) -> list[_Group]:
    """Complete-linkage groups, greedy in descending peak order, each re-measured."""
    member_lists: list[list[_Candidate]] = []
    for c in candidates:
        for members in member_lists:
            if all(_compatible(c, m) for m in members) and any(
                _near(c, m, filters.bins) for m in members
            ):
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
            period, angle_deg = _phase_steps(
                local.response, seed, top.period, top.angle_deg, filters.bins
            )
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


class _PeriodAndAngle(Protocol):
    """Anything with a stripe Period and Angle (a candidate, a region)."""

    @property
    def period(self) -> float: ...
    @property
    def angle_deg(self) -> float: ...


def _compatible(a: _PeriodAndAngle, b: _PeriodAndAngle) -> bool:
    ratio = max(a.period, b.period) / min(a.period, b.period)
    return ratio <= _MERGE_PERIOD_RATIO and abs(a.angle_deg - b.angle_deg) <= _MERGE_ANGLE_DEG


def _near(a: _Candidate | _Group, b: _Candidate | _Group, bins: BinFactors) -> bool:
    """``a``'s grown extent touches or lies within _MERGE_GAP_PERIODS Periods
    of ``b``'s (sensor px under ``bins``)."""
    if (a.grown & b.grown).any():
        return True
    gap = _MERGE_GAP_PERIODS * max(a.period, b.period)
    box = _bbox(a.grown)
    pad = int(np.ceil(max(frame_px(bins, gap, gap)))) + 1
    r0, r1 = max(box.row_start - pad, 0), min(box.row_stop + pad, a.grown.shape[0])
    c0, c1 = max(box.col_start - pad, 0), min(box.col_stop + pad, a.grown.shape[1])
    window_b = b.grown[r0:r1, c0:c1]
    if not window_b.any():
        return False
    distance = _edt(~a.grown[r0:r1, c0:c1], bins)
    return bool(distance[window_b].min() <= gap)


def _edt(mask: np.ndarray, bins: BinFactors) -> np.ndarray:
    """Euclidean distance transform of ``mask`` in sensor px; ``sampling`` is
    passed only when binned, so the 1x1 call is the unbinned one."""
    if bins == BinFactors():
        return np.asarray(ndimage.distance_transform_edt(mask))
    return np.asarray(ndimage.distance_transform_edt(mask, sampling=pixel_size(bins)))


def _passes_size_rule(group: _Group, filters: _Filters) -> bool:
    """At least 3x2 Periods: half-peak width on the re-tuned depth, half-peak
    height on the short size-only filter (see MIN_HALF_DEPTH_*_PERIODS)."""
    p = group.period
    # The rule is in sensor px; the spans are measured in frame px.
    min_height, min_width = frame_px(
        filters.bins, MIN_HALF_DEPTH_HEIGHT_PERIODS * p, MIN_HALF_DEPTH_WIDTH_PERIODS * p
    )
    width = _half_peak_span(group.tuned_depth, group.top_core, axis=1)
    if width < min_width:
        return False
    height = _half_peak_span(filters.size_depth(p, group.angle_deg), group.top_core, axis=0)
    return bool(height >= min_height)


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
        if own >= s.depth or not _near(s, group, filters.bins):
            continue
        without = np.where(s.grown, filters.mean(s.period), frame)
        rest = _Filters(_Spectrum(without, filters.bins), filters.light)
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
            filters.spec.gabor(period, angle_deg),
            region.pixels,
            period,
            angle_deg,
            filters.bins,
        )
    return dataclasses.replace(region, period=period, angle_deg=angle_deg)


def _settle_overlaps(
    groups: list[_Group], clipped: np.ndarray, bins: BinFactors
) -> list[_Survivor]:
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
                depth=_interior_depth(g.tuned_depth, pixels, clipped, g.period, bins),
                pixels=pixels,
                bbox=_bbox(pixels),
                area_px=int(flat.size),
                first_pixel=int(flat[0]),
            )
        )
    return survivors


def _interior_depth(
    depth: np.ndarray, pixels: np.ndarray, clipped: np.ndarray, period: float, bins: BinFactors
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
    distance = _edt(pixels, bins)
    interior = distance >= _INTERIOR_FRACTION * distance.max()
    if clipped.any():
        sigma = frame_px(bins, _ALONG * period, _ACROSS * period)
        weight = gaussian_filter(clipped.astype(float), sigma=sigma)
        unclipped = interior & (weight < _CLIPPED_WEIGHT_MAX)
        if unclipped.any():
            return _median_depth(depth, unclipped)
    return _median_depth(depth, interior)


def _bbox(mask: np.ndarray) -> BoundingBox:
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return BoundingBox(int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1)


# Phase Breaks (ticket 09): a report-level pass after the threshold, on the
# reported regions only (see _with_phase_breaks). Values: prototype P1 v2 of
# ticket 09 (explore seeds 109_000-109_599, validated once on 110_000-110_399).
# Two reported regions that are _compatible and within this many Periods (the
# larger of the two, sensor px) are searched for a break between them.
_BRIDGE_GAP_PERIODS = 4.0
# A break bridges them when it has at least _BRIDGE_SMALL_SIDE_SHARE of the
# smaller region's pixels on one side and _BRIDGE_LARGE_SIDE_SHARE of the
# larger's on the other.
_BRIDGE_SMALL_SIDE_SHARE = 0.8
_BRIDGE_LARGE_SIDE_SHARE = 0.5
# At most this many second-round bridges (one merge per round).
_BRIDGE_ROUNDS = 3
# The slit along a found break: pixels within _BREAK_FILL_SIGMAS bank step
# widths (sigma_n with _ACROSS, _ALONG) of the line, in the along-line bins of
# _BREAK_FILL_BIN_PERIODS where the region has pixels on both sides within
# _BREAK_FILL_REACH_PERIODS beyond that.
_BREAK_FILL_SIGMAS = 1.0
_BREAK_FILL_REACH_PERIODS = 1.0
_BREAK_FILL_BIN_PERIODS = 0.5
# Period and Angle are re-measured on the region's pixels farther than
# _REMEASURE_EXCLUDE_SIGMAS bank step widths from every found break,
# _REMEASURE_STEPS neighbour-product steps from the reported values, when at
# least _REMEASURE_MIN_AREA_P2 Periods^2 (sensor px^2) remain: one bank Gabor
# footprint, 2 pi _ACROSS _ALONG.
_REMEASURE_EXCLUDE_SIGMAS = 2.0
_REMEASURE_STEPS = 6
_REMEASURE_MIN_AREA_P2 = 9.4
# A region with no break of its own joins a larger region with a break when
# at least this share of its pixels lies in that region's slit (and their
# Periods are within _MERGE_PERIOD_RATIO).
_ABSORB_SLIT_SHARE = 0.6
# A break's reported run: the region's pixels within this many frame pixels
# (the larger pixel side, in sensor px) of the line.
_BREAK_SEGMENT_HALF_WIDTH_PIXELS = 0.75


class _BridgeSide(_PeriodAndAngle, Protocol):
    """A region that can be bridged: a reported region, or a _PassRegion."""

    @property
    def pixels(self) -> np.ndarray: ...
    @property
    def peak_ratio(self) -> float: ...


class _Bridge(NamedTuple):
    """A Phase Break found between two regions, and the gap pixels it spans."""

    gap: np.ndarray
    found: FoundBreak


def _top(members: list[_Survivor]) -> _Survivor:
    """The member with the highest peak ratio: its values start the pass."""
    return max(members, key=lambda g: g.peak_ratio)


@dataclass
class _PassRegion:
    """A region in the Phase Break pass: its members (regions above the
    Threshold), pixels, current Period and Angle, found breaks and slit."""

    members: list[_Survivor]
    pixels: np.ndarray
    period: float
    angle_deg: float
    breaks: list[FoundBreak] = field(default_factory=list)
    slit: np.ndarray | None = None
    merged: bool = False

    @property
    def top(self) -> _Survivor:
        return _top(self.members)

    @property
    def peak_ratio(self) -> float:
        return self.top.peak_ratio

    @property
    def area_px(self) -> int:
        return int(self.pixels.sum())


class _BreakPass:
    """The shared state of one frame's Phase Break pass."""

    def __init__(
        self,
        filters: _Filters,
        clipped: np.ndarray,
        owned: np.ndarray,
        responses: _ResponseSource,
    ):
        self.filters = filters
        self.spec = filters.spec
        self.light = filters.light
        self.bins = filters.bins
        self.clipped = clipped
        self.owned = owned
        rows, cols = np.mgrid[0 : owned.shape[0], 0 : owned.shape[1]]
        self.y, self.x = sensor_coordinates(rows, cols, self.bins)
        self.responses = responses

    def find(self, domain: np.ndarray, period: float, angle_deg: float) -> list[FoundBreak]:
        z = self.responses.response(period, angle_deg)
        return find_phase_breaks(z, domain, period, angle_deg, self.bins)

    def exclusion(self, breaks: list[FoundBreak], period: float, angle_deg: float) -> np.ndarray:
        """Pixels within _REMEASURE_EXCLUDE_SIGMAS bank step widths of any break."""
        out = np.zeros(self.owned.shape, dtype=bool)
        for b in breaks:
            width = _bank_sigma_n(period, angle_deg, b.line_angle_deg)
            out |= np.abs(b.side(self.y, self.x)) <= _REMEASURE_EXCLUDE_SIGMAS * width

        return out

    def bridge(self, a: _BridgeSide, b: _BridgeSide) -> _Bridge | None:
        """The break found between two compatible regions with them on
        opposite sides, and the gap it spans; None when there is none. The
        finder runs at the Period and Angle of the region with the higher
        peak ratio (``a`` on a tie)."""
        if not _compatible(a, b):
            return None
        pa, pb = a.pixels, b.pixels
        gap = _BRIDGE_GAP_PERIODS * max(a.period, b.period)
        box = _bbox(pa)
        pad = int(np.ceil(max(frame_px(self.bins, gap, gap)))) + 1
        r0, r1 = max(box.row_start - pad, 0), min(box.row_stop + pad, pa.shape[0])
        c0, c1 = max(box.col_start - pad, 0), min(box.col_stop + pad, pa.shape[1])
        window_b = pb[r0:r1, c0:c1]
        if not window_b.any():
            return None
        if _edt(~pa[r0:r1, c0:c1], self.bins)[window_b].min() > gap:
            return None
        between = (_edt(~pa, self.bins) <= gap) & (_edt(~pb, self.bins) <= gap) & self.light
        top = a if a.peak_ratio >= b.peak_ratio else b
        na, nb = int(pa.sum()), int(pb.sum())
        if na <= nb:
            need_a, need_b = _BRIDGE_SMALL_SIDE_SHARE, _BRIDGE_LARGE_SIDE_SHARE
        else:
            need_a, need_b = _BRIDGE_LARGE_SIDE_SHARE, _BRIDGE_SMALL_SIDE_SHARE
        for brk in self.find(pa | pb | between, top.period, top.angle_deg):
            share_a = float((brk.side(self.y[pa], self.x[pa]) > 0).mean())
            share_b = float((brk.side(self.y[pb], self.x[pb]) > 0).mean())
            if (share_a >= need_a and 1 - share_b >= need_b) or (
                1 - share_a >= need_a and share_b >= need_b
            ):
                return _Bridge(between, brk)
        return None

    def process(
        self,
        members: list[_Survivor],
        extra: np.ndarray,
        bridge_breaks: list[FoundBreak],
        start: tuple[float, float] | None = None,
    ) -> _PassRegion:
        """Find, re-measure and fill one region made of ``members`` (searched
        on their pixels plus ``extra``)."""
        top = _top(members)
        p0, a0 = start if start is not None else (top.period, top.angle_deg)
        pixels = np.logical_or.reduce([g.pixels for g in members])
        region = _PassRegion(members, pixels, p0, a0, merged=len(members) > 1)
        found = self.find(pixels | extra, p0, a0) or list(bridge_breaks)
        if not found:
            return region
        region.breaks = found
        region.period, region.angle_deg = self.remeasure(pixels, found, p0, a0)
        region.slit = np.zeros(pixels.shape, dtype=bool)
        for b in found:
            pixels = self.fill(region, pixels, b)
        region.pixels = pixels
        return region

    def remeasure(
        self, pixels: np.ndarray, breaks: list[FoundBreak], p0: float, a0: float
    ) -> tuple[float, float]:
        """Period and Angle away from the breaks, kept only when the stripes'
        mean filter response there is at least the starting one's."""
        area = pixels & ~self.exclusion(breaks, p0, a0)
        h, v = self.bins.horizontal, self.bins.vertical
        if not area.any() or area.sum() * h * v < _REMEASURE_MIN_AREA_P2 * p0 * p0:
            return p0, a0
        period, angle_deg = p0, a0
        for _ in range(_REMEASURE_STEPS):
            period, angle_deg = _phase_steps(
                self.spec.gabor(period, angle_deg), area, period, angle_deg, self.bins
            )
        before = float(np.abs(self.spec.gabor(p0, a0)[area]).mean())
        after = float(np.abs(self.spec.gabor(period, angle_deg)[area]).mean())
        return (period, angle_deg) if after >= before else (p0, a0)

    def fill(self, region: _PassRegion, pixels: np.ndarray, b: FoundBreak) -> np.ndarray:
        """``pixels`` plus the slit along ``b`` (see _BREAK_FILL_SIGMAS); the
        slit is added to ``region.slit`` and the new pixels to ``owned``."""
        assert region.slit is not None
        half = _BREAK_FILL_SIGMAS * _bank_sigma_n(region.period, region.angle_deg, b.line_angle_deg)
        reach = half + _BREAK_FILL_REACH_PERIODS * region.period
        side = b.side(self.y, self.x)
        near = pixels & (np.abs(side) <= reach)
        if not near.any():
            return pixels
        along_bin = np.floor(b.along(self.y, self.x) / (_BREAK_FILL_BIN_PERIODS * region.period))
        along_bin = along_bin.astype(np.int64)
        first = int(along_bin[near].min())
        n_bins = int(along_bin[near].max()) - first + 1
        both = (np.bincount(along_bin[near & (side > 0)] - first, minlength=n_bins) > 0) & (
            np.bincount(along_bin[near & (side < 0)] - first, minlength=n_bins) > 0
        )
        along_bin -= first
        inside = (along_bin >= 0) & (along_bin < n_bins)
        in_both_bins = np.zeros(pixels.shape, dtype=bool)
        in_both_bins[inside] = both[along_bin[inside]]
        region.slit |= in_both_bins & (np.abs(side) <= reach)
        add = in_both_bins & (np.abs(side) <= half) & self.light & ~(self.owned & ~pixels)
        self.owned |= add
        return np.asarray(pixels | add)

    def depth(self, region: _PassRegion) -> float:
        """A merged region's Modulation Depth, away from its breaks."""
        p, a = region.period, region.angle_deg
        inner = region.pixels & ~self.exclusion(region.breaks, p, a)
        if not inner.any():
            inner = region.pixels
        tuned = _depth(self.spec.gabor(p, a), self.spec.local_mean(p), self.light)
        return _interior_depth(tuned, inner, self.clipped, p, self.bins)


def _bank_sigma_n(period: float, angle_deg: float, line_angle_deg: float) -> float:
    """The bank filter's step width (sensor px) across a line."""
    return sigma_n(period, angle_deg, line_angle_deg, _ACROSS, _ALONG)


def _with_phase_breaks(
    reported: list[_Survivor],
    filters: _Filters,
    clipped: np.ndarray,
    responses: _ResponseSource,
) -> list[tuple[_Survivor, list[FoundBreak]]]:
    """The reported regions after the Phase Break pass, each with its found
    breaks. Runs after the score and the threshold, which never read it.
    ``responses`` gives the finder's response at each (Period, Angle): the
    raw one, or with the pre-break search's Forks explained away.

    1. Bridge: two _compatible regions within _BRIDGE_GAP_PERIODS are merged
       when a break found on both plus the gap between them has the regions
       on opposite sides (_BRIDGE_*_SIDE_SHARE).
    2. Find: breaks in each resulting region (a merged region with none found
       keeps its bridging breaks).
    3. Re-measure Period and Angle away from the breaks (``remeasure``).
    4. Fill the slit along each break; pixels of another region are never
       taken, and a fill sees the fills before it.
    5. A region with no break of its own lying in another's slit joins it;
       then bridging again on the re-measured values, one merge per round.

    With no found break, the inputs are returned unchanged (the same objects,
    in order). A region that only gained breaks keeps its depth; a merged one
    is re-measured away from its breaks."""
    owned = np.logical_or.reduce([g.pixels for g in reported])
    state = _BreakPass(filters, clipped, owned, responses)

    parent = list(range(len(reported)))

    def root(i: int) -> int:
        while parent[i] != i:
            i = parent[i]
        return i

    bridged: dict[tuple[int, int], _Bridge] = {}
    for i, a in enumerate(reported):
        for j in range(i + 1, len(reported)):
            found = state.bridge(a, reported[j])
            if found is not None:
                bridged[(i, j)] = found
                ri, rj = root(i), root(j)
                if ri != rj:
                    parent[rj] = ri
    groups: dict[int, list[int]] = {}
    for i in range(len(reported)):
        groups.setdefault(root(i), []).append(i)

    regions = []
    for members in groups.values():
        extra = np.zeros(owned.shape, dtype=bool)
        bridge_breaks = []
        for (i, j), bridge in bridged.items():
            if i in members and j in members:
                extra |= bridge.gap
                bridge_breaks.append(bridge.found)
        regions.append(state.process([reported[k] for k in members], extra, bridge_breaks))

    regions = _absorbed_in_slits(regions)
    regions = _bridged_again(state, regions)

    if not any(r.breaks or r.merged for r in regions):
        return [(g, []) for g in reported]
    return [(_settled(state, r), r.breaks) for r in regions]


def _absorbed_in_slits(regions: list[_PassRegion]) -> list[_PassRegion]:
    """Each region with a break, largest first, takes in every smaller region
    with no break of its own that lies in its slit (_ABSORB_SLIT_SHARE) at a
    Period within _MERGE_PERIOD_RATIO."""
    gone: set[int] = set()
    for r in sorted(regions, key=lambda r: -r.area_px):
        if id(r) in gone or not r.breaks or r.slit is None:
            continue
        for small in regions:
            if small is r or id(small) in gone or small.breaks or small.area_px >= r.area_px:
                continue
            if max(small.period, r.period) / min(small.period, r.period) > _MERGE_PERIOD_RATIO:
                continue
            if (small.pixels & r.slit).sum() >= _ABSORB_SLIT_SHARE * small.area_px:
                r.pixels = r.pixels | small.pixels
                r.members = r.members + small.members
                r.merged = True
                gone.add(id(small))
    return [r for r in regions if id(r) not in gone]


def _bridged_again(state: _BreakPass, regions: list[_PassRegion]) -> list[_PassRegion]:
    """Bridging on the re-measured Periods and Angles, one merge per round,
    at most _BRIDGE_ROUNDS rounds; a merged pair is found, re-measured and
    filled again from the higher-peak region's values."""
    for _ in range(_BRIDGE_ROUNDS):
        merged = _bridge_one(state, regions)
        if merged is None:
            break
        regions = merged
    return regions


def _bridge_one(state: _BreakPass, regions: list[_PassRegion]) -> list[_PassRegion] | None:
    """The first pair that bridges, merged; None when no pair does."""
    for i, a in enumerate(regions):
        for j in range(i + 1, len(regions)):
            b = regions[j]
            bridge = state.bridge(a, b)
            if bridge is None:
                continue
            hi = a if a.peak_ratio >= b.peak_ratio else b
            extra = bridge.gap.copy()
            for r in (a, b):
                if r.slit is not None:
                    extra |= r.slit
            new = state.process(
                a.members + b.members, extra, [bridge.found], start=(hi.period, hi.angle_deg)
            )
            new.pixels = new.pixels | a.pixels | b.pixels
            new.merged = True
            return [r for k, r in enumerate(regions) if k not in (i, j)] + [new]
    return None


def _settled(state: _BreakPass, region: _PassRegion) -> _Survivor:
    """The region as a _Survivor; unchanged when it has no break and no merge."""
    if not region.breaks and not region.merged:
        (only,) = region.members
        return only
    top = region.top
    depth = state.depth(region) if region.merged else top.depth
    flat = np.flatnonzero(region.pixels)
    return _Survivor(
        peak_ratio=top.peak_ratio,
        period=region.period,
        angle_deg=region.angle_deg,
        depth=depth,
        pixels=region.pixels,
        bbox=_bbox(region.pixels),
        area_px=int(flat.size),
        first_pixel=int(flat[0]),
    )


def _reported_breaks(
    label: int, pixels: np.ndarray, found: list[FoundBreak], bins: BinFactors
) -> list[PhaseBreak]:
    """Each break's run across its region: the region's pixels within
    _BREAK_SEGMENT_HALF_WIDTH_PIXELS frame pixels of the line, its extreme
    points projected on the line, in frame px, col increasing (row increasing
    on a vertical line). A break with no such pixel is not reported."""
    if not found:
        return []
    rows, cols = np.nonzero(pixels)
    y, x = sensor_coordinates(rows, cols, bins)
    half = _BREAK_SEGMENT_HALF_WIDTH_PIXELS * max(pixel_size(bins))
    out = []
    for b in found:
        on = np.abs(b.side(y, x)) <= half
        if not on.any():
            continue
        u = b.along(y[on], x[on])
        t = math.radians(b.line_angle_deg)
        line = []
        for along in (float(u.min()), float(u.max())):
            row, col = frame_px(
                bins, b.point[0] + along * math.sin(t), b.point[1] + along * math.cos(t)
            )
            line.append((float(row), float(col)))
        out.append(PhaseBreak(region=label, line=tuple(line), jump_rad=b.jump_rad))
    return out
