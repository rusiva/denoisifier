"""Seeded synthetic frames with known ground truth.

A developer tool and test oracle, not part of the experimenter-facing surface.
The forward model follows the spec:

    clean = profile * mottle * (1 + m * cos(phase))
    phase = 2*pi/period * (x*cos(t) + y*sin(t)) + phase0

With Striped Regions (``StripedRegion``), each region i has its own Period,
Angle and depth under a soft elliptical mask, sharing ``phase0``:

    clean = profile * mottle * (1 + sum_i m_i * mask_i * cos(phase_i))
    mottle = exp(strength * g),  g a unit-std isotropic Gaussian random field
    frame = clean + noise

Noise is either additive Gaussian (``noise`` a float) or the EMCCD chain
(``noise`` an ``Emccd``): Poisson photons plus spurious charge, EM gain as a
Gamma distribution, Gaussian read noise, divided back by the gain.

Data-quality problems come last (``spikes``, ``clip_level``): Spikes add
short bright streaks on top of the noisy frame, then the frame is clipped:

    frame = min(clean + noise + spikes, clip_level)

``GroundTruth.spike_mask`` and ``clipped_mask`` record which pixels each one
touched.

Phase Breaks (``PhaseBreakLine``, ticket 09) add a sharp Phase Jump to the
stripe phase of every Striped Region (spec forward model):

    phase_i += sum_b jump_b * [pixel lies on b's positive side]

``GroundTruth.phase_breaks`` records each line in canonical form
(``BreakTruth``).

Forks (``ForkPoint``, ticket 10) add a winding term to the stripe phase of
every Striped Region and of full-frame stripes (spec forward model):

    phase_i += sum_f direction_f * atan2(y - y0_f, x - x0_f)

so the phase winds by 2 pi around each fork. The term is global: it bends
the stripes near the fork and, weakly, everywhere else (the local frequency
changes by about P / (2 pi r) relative at distance r). ``GroundTruth.forks``
records each fork (``ForkTruth``).
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

_F64 = NDArray[np.float64]

MottleKind = Literal["none", "scorched", "multiscale"]

_TYPICAL_MOTTLE_STRENGTH = {"scorched": 0.4, "multiscale": 0.35}

# Spikes (ticket 06): each event is a straight streak of 1 to this many pixels
# (cosmic-ray hits and hot pixels as single pixels and short streaks).
_SPIKE_MAX_LENGTH = 3
# Each hit pixel gains a brightness uniform in this range times the clean
# frame's maximum: bright only (evidence/06-prototype-p1.md checked the 2.0
# lower end; dim hot pixels are out of the model).
_SPIKE_BRIGHTNESS = (2.0, 10.0)


@dataclass(frozen=True)
class Emccd:
    """EMCCD noise chain. Output is in ~photon units (divided by ``em_gain``).

    ``photons_peak``: photons at the brightest clean pixel. ``em_gain``: EM
    gain; 1.0 turns it off (no Gamma stage). ``read_noise_e``: Gaussian read
    noise std in electrons. ``cic``: spurious charge from clocking, mean
    photon-equivalents per pixel.
    """

    photons_peak: float = 100.0
    em_gain: float = 300.0
    read_noise_e: float = 50.0
    cic: float = 0.005


@dataclass(frozen=True)
class StripedRegion:
    """One soft-edged elliptical Striped Region with its own stripes.

    ``center`` is (row, col) and ``semi_axes`` (rows, cols) before rotation,
    in px, to the mask's 0.5 contour. ``rotation_deg`` rotates the ellipse (it
    is not the stripe Angle). ``edge_px`` is the soft edge: the mask goes from
    0.9 to 0.1 over about ``edge_px`` along the minor axis, and over
    ``edge_px * minor / major`` along the major axis. ``period``, ``angle_deg``
    and ``modulation_depth`` are the region's Period, Angle and Modulation
    Depth (GLOSSARY.md).
    """

    center: tuple[float, float]
    semi_axes: tuple[float, float]
    rotation_deg: float
    edge_px: float
    period: float
    angle_deg: float
    modulation_depth: float


@dataclass(frozen=True)
class RegionTruth:
    """One region's ground truth. ``mask`` is the soft mask (frame shape, 0-1);
    the region's pixels are ``mask >= 0.5``."""

    period: float
    angle_deg: float
    modulation_depth: float
    mask: np.ndarray


@dataclass(frozen=True)
class PhaseBreakLine:
    """A straight Phase Break across the whole frame.

    ``point`` (row, col) is any point on the line, in px. ``line_angle_deg``
    is the line's direction in degrees from horizontal, positive descending
    to the right (row 0 is the top), so a line at ``line_angle_deg == t`` is
    perpendicular to stripes of Angle ``t``. ``jump_rad`` is the stripe
    phase on the positive side of the directed line minus the phase on the
    other side (``BreakTruth`` defines the positive side). The stripe phase
    grows with the column, so a positive jump moves the stripes on the
    positive side toward column 0 by jump / 2 pi Periods.
    """

    point: tuple[float, float]
    line_angle_deg: float
    jump_rad: float


@dataclass(frozen=True)
class BreakTruth:
    """One Phase Break as the generator drew it, in canonical form.

    ``point`` is as given. ``line_angle_deg`` is in (-90, 90]: a line given
    outside that range is flipped (180 deg added or taken off) and its jump
    negated, which is the same line. ``jump_rad`` follows the canonical
    direction, wrapped to (-pi, pi]. With ``d = (cos a, sin a)`` in
    (x = col, y = row), a pixel's side is ``d_x (y - y0) - d_y (x - x0)``;
    ``shifted`` (bool, frame shape) is the positive side, strictly
    (``> 0``), where the jump is added. Pixels exactly on the line are not
    shifted."""

    point: tuple[float, float]
    line_angle_deg: float
    jump_rad: float
    shifted: np.ndarray


@dataclass(frozen=True)
class ForkPoint:
    """A Fork in the stripes. ``point`` (row, col), px. ``direction`` +1 or
    -1, by split direction: +1 when, going toward row 0 past the fork, one
    stripe becomes two (a row on the row-0 side crosses one more stripe);
    -1 the same going away from row 0. The stripe phase gains
    ``direction * atan2(y - y0, x - x0)`` (x the column, y the row,
    increasing downward; equal to spec.md's charge in frame coordinates).
    The Report's ``Fork.direction`` of a found fork equals this value."""

    point: tuple[float, float]
    direction: int


@dataclass(frozen=True)
class ForkTruth:
    """One Fork as the generator drew it: ``point`` (row, col) px and
    ``direction`` (+1 or -1), as ``ForkPoint`` defines them."""

    point: tuple[float, float]
    direction: int


@dataclass(frozen=True)
class GroundTruth:
    """What the generator put into a frame: one ``RegionTruth`` per region.

    A full-frame frame (no ``regions`` given) has one region whose mask is
    all ones. At ``modulation_depth=0`` that region is still listed, with depth
    0, and it is not a Striped Region: filter on ``modulation_depth > 0``
    before treating ``regions`` as the striped set.

    ``period``, ``angle_deg`` and ``modulation_depth`` are the single
    region's values (Period in pixels; Angle in degrees, sign convention in
    GLOSSARY.md); they raise ``ValueError`` unless there is exactly one region.

    ``spike_mask`` (bool, frame shape) holds every pixel a Spike hit, clipped
    or not. ``clipped_mask`` holds the pixels of the spike-free frame at or
    above the clip level that no Spike hit, so the two are disjoint. Both are
    all False without spikes or without a clip level; ``spike_pixels`` and
    ``clipped_pixels`` are their counts.

    ``phase_breaks`` holds one ``BreakTruth`` per Phase Break, in the order
    given (empty without breaks); ``forks`` one ``ForkTruth`` per Fork, in
    the order given (empty without forks).
    """

    regions: tuple[RegionTruth, ...]
    spike_mask: np.ndarray
    clipped_mask: np.ndarray
    phase_breaks: tuple[BreakTruth, ...] = ()
    forks: tuple[ForkTruth, ...] = ()

    @property
    def spike_pixels(self) -> int:
        return int(self.spike_mask.sum())

    @property
    def clipped_pixels(self) -> int:
        return int(self.clipped_mask.sum())

    def _only(self) -> RegionTruth:
        if len(self.regions) != 1:
            raise ValueError(
                f"the frame has {len(self.regions)} regions, not exactly one region; "
                "use GroundTruth.regions"
            )
        return self.regions[0]

    @property
    def period(self) -> float:
        return self._only().period

    @property
    def angle_deg(self) -> float:
        return self._only().angle_deg

    @property
    def modulation_depth(self) -> float:
        return self._only().modulation_depth


@dataclass(frozen=True)
class Synthetic:
    """A generated frame, its ground truth, and ``clean``: the noise-, spike-
    and clip-free frame in the same units as ``frame``, so ``frame - clean`` is
    pure noise (spurious charge included) when ``spikes == 0`` and
    ``clip_level is None``."""

    frame: np.ndarray
    truth: GroundTruth
    clean: np.ndarray


def generate(
    *,
    seed: int,
    shape: tuple[int, int] = (256, 256),
    period: float | None = None,
    angle_deg: float | None = None,
    modulation_depth: float | None = None,
    mottle: MottleKind = "none",
    mottle_strength: float | None = None,
    noise: float | Emccd = 0.01,
    peak: float = 1000.0,
    regions: Sequence[StripedRegion] | None = None,
    spikes: int = 0,
    clip_level: float | None = None,
    phase_breaks: Sequence[PhaseBreakLine] = (),
    forks: Sequence[ForkPoint] = (),
) -> Synthetic:
    """Generate one frame: profile times full-frame stripes, plus noise.

    Without ``regions`` the stripes cover the whole frame; ``period``,
    ``angle_deg`` and ``modulation_depth`` default to 8.0, 0.0 and 0.6. With
    ``regions`` the stripes lie only inside each ``StripedRegion`` (each with
    its own Period, Angle and depth); passing any of those three as well is a
    ``ValueError``, and ``regions=()`` gives a stripe-free frame. Regions may
    overlap as long as the summed ``m_i * mask_i`` stays <= 1 everywhere.
    The RNG stream is the same with or without regions.

    ``period`` and ``angle_deg`` are the Period and Angle (GLOSSARY.md);
    ``angle_deg`` is ``t`` in ``phase = 2*pi/period * (x cos t + y sin t)``
    with ``x`` the column and ``y`` the row (increasing downward). A float
    ``noise`` is the additive Gaussian standard deviation as a fraction of
    ``peak``, the profile peak; an ``Emccd`` selects the EMCCD chain, whose
    scale is set by ``Emccd.photons_peak`` instead of ``peak``.
    ``modulation_depth=0`` gives a profile-only frame.

    ``mottle`` picks the Mottle: ``"scorched"`` (blotchy, saturated; typical
    strength 0.4) or ``"multiscale"`` (power-law; typical strength 0.35).
    ``mottle_strength`` is the std of the log-mottle; ``None`` takes the
    typical value. Mottle is isotropic (ADR 0001).

    ``spikes`` (a non-negative int) adds that many Spike events after the
    noise, for either noise model: each a straight streak of 1 to
    ``_SPIKE_MAX_LENGTH`` pixels in a uniform direction, each pixel brighter by
    ``_SPIKE_BRIGHTNESS`` times ``clean.max()``. Dim hot pixels and long tracks
    are not modelled. ``clip_level`` (finite, frame units, the meaning of
    ``analyse(..., clip_level=)``) then clips the frame to at most that value;
    ``None`` means no clipping (``inf`` is rejected; ``analyse`` accepts it).
    With ``spikes=0`` and ``clip_level=None`` the frame is bit-identical to a
    call without them, and a spiked frame equals the same seed's spike-free
    frame outside the hit pixels.

    ``phase_breaks`` (``PhaseBreakLine``s) shift the stripe phase by each
    line's Phase Jump on its positive side, sharp at the line, in every Striped Region;
    without ``regions`` the stripes, and so the breaks, cover the whole
    frame. Each line is canonicalised first (``BreakTruth``) and returned in
    ``GroundTruth.phase_breaks``; every field must be finite and ``point`` a
    pair (``ValueError``); a jump of 0 changes nothing. Breaks draw nothing
    from the RNG. So:

    1. ``phase_breaks=()`` is bit-identical to a call without it, for every
       noise model;
    2. with breaks, Gaussian ``noise``, ``spikes=0`` and no ``clip_level``,
       ``frame`` and ``clean`` are bit-identical to the break-free call off
       each break's ``shifted`` pixels;
    3. with breaks and EMCCD noise no pixel is claimed equal: the chain
       rescales by ``clean.max()`` and its draws depend on the values.

    ``forks`` (``ForkPoint``s) add ``direction * atan2(y - y0, x - x0)`` to
    the stripe phase of every Striped Region (and of full-frame stripes),
    with the Phase Breaks' term. The term is global: it bends the stripes
    near each fork and, weakly, in every region (relative change in the
    local frequency about ``P / (2 pi r)`` at distance ``r``). Its 2 pi jump
    along the ray to the left of the fork is invisible in the cosine. Each
    fork is returned in ``GroundTruth.forks``; ``point`` must be a finite
    pair and ``direction`` an int (not a bool) equal to +1 or -1
    (``ValueError``). Forks draw nothing from the RNG. So:

    1. ``forks=()`` is bit-identical to a call without it, for every noise
       model;
    2. with forks, Gaussian ``noise``, ``spikes=0`` and no ``clip_level``,
       the added noise ``frame - clean`` is the fork-free call's, within
       float rounding; no pixel off the fork is claimed equal (the term is
       global);
    3. with forks and EMCCD noise no pixel is claimed.

    Once the arguments are valid, the seed is raised as the audit event
    ``denoisifier.synthetic.generate`` (``sys.audit``) just before it seeds the
    RNG; the tests' seed guard listens for it (tests/seed_guard.py).
    """
    if len(shape) != 2 or shape[0] < 1 or shape[1] < 1:
        raise ValueError(f"shape must be two positive sizes, got {shape!r}")
    if regions is not None:
        if period is not None or angle_deg is not None or modulation_depth is not None:
            raise ValueError(
                "period, angle_deg and modulation_depth go in each StripedRegion "
                "when regions are given"
            )
        regions = tuple(regions)
        for r in regions:
            _check_region(r)
    else:
        full = StripedRegion(
            center=(0.0, 0.0),
            semi_axes=(1.0, 1.0),
            rotation_deg=0.0,
            edge_px=1.0,
            period=8.0 if period is None else period,
            angle_deg=0.0 if angle_deg is None else angle_deg,
            modulation_depth=0.6 if modulation_depth is None else modulation_depth,
        )
        _check_stripes(full.period, full.modulation_depth)
    if mottle not in ("none", "scorched", "multiscale"):
        raise ValueError(f"mottle must be 'none', 'scorched' or 'multiscale', got {mottle!r}")
    if mottle_strength is not None:
        if mottle == "none":
            raise ValueError("mottle_strength given with mottle='none'")
        if mottle_strength < 0:
            raise ValueError(f"mottle_strength must be >= 0, got {mottle_strength!r}")
    if isinstance(noise, Emccd):
        _check_emccd(noise)
    elif noise < 0:
        raise ValueError(f"noise must be >= 0, got {noise!r}")
    if isinstance(spikes, bool) or not isinstance(spikes, int | np.integer) or spikes < 0:
        raise ValueError(f"spikes must be a non-negative int, got {spikes!r}")
    if clip_level is not None and not np.isfinite(clip_level):
        raise ValueError(f"clip_level must be finite (None for no clipping), got {clip_level!r}")
    lines = tuple(_canonical_break(b) for b in phase_breaks)
    fork_truths = tuple(_checked_fork(f) for f in forks)

    sys.audit("denoisifier.synthetic.generate", seed)
    rng = np.random.default_rng(seed)
    rows, cols = shape
    y, x = np.mgrid[0:rows, 0:cols].astype(float)
    break_truths = tuple(_break_truth(b, x, y) for b in lines)
    # Breaks and forks add to every phase. Branch so that the break- and fork-free
    # path does no arithmetic at all (claims 1).
    added_phase = _break_phase(break_truths) if break_truths else None
    if fork_truths:
        winding = _fork_phase(fork_truths, x, y)
        added_phase = winding if added_phase is None else added_phase + winding

    # RNG draw order is fixed: profile, stripe phase offset, mottle, noise,
    # then spikes (only when spikes > 0).
    # So for one seed and shape, profile and mottle do not depend on the
    # stripe or noise settings.
    # The Gaussian path scales the profile first, as ticket 01 did, so
    # mottle-free Gaussian frames stay bit-identical to ticket 01.
    scale = 1.0 if isinstance(noise, Emccd) else peak
    profile = scale * _profile(rng, rows, cols, x, y)

    phase0 = rng.uniform(0, 2 * np.pi)

    envelope = profile
    if mottle != "none":
        strength = _TYPICAL_MOTTLE_STRENGTH[mottle] if mottle_strength is None else mottle_strength
        envelope = profile * _mottle(rng, shape, mottle, strength)

    if regions is None:
        # Only full's Period, Angle and depth are used: the stripes cover the frame.
        phase = _phase(x, y, full.period, full.angle_deg, phase0)
        if added_phase is not None:
            phase = phase + added_phase
        clean = envelope * (1 + full.modulation_depth * np.cos(phase))
        truths: tuple[RegionTruth, ...] = (
            RegionTruth(
                period=float(full.period),
                angle_deg=float(full.angle_deg),
                modulation_depth=float(full.modulation_depth),
                mask=np.ones(shape),
            ),
        )
    else:
        masks = [_region_mask(r, x, y) for r in regions]
        depth_sum = np.zeros(shape)
        modulation = np.zeros(shape)
        for r, mask in zip(regions, masks, strict=True):
            depth_sum += r.modulation_depth * mask
            region_phase = _phase(x, y, r.period, r.angle_deg, phase0)
            if added_phase is not None:
                region_phase = region_phase + added_phase
            modulation += r.modulation_depth * mask * np.cos(region_phase)
        if (depth_sum > 1).any():
            raise ValueError(
                "regions overlap with a summed modulation depth above 1 "
                f"(max {depth_sum.max():.3f}); the clean frame would go negative"
            )
        clean = envelope * (1 + modulation)
        truths = tuple(
            RegionTruth(
                period=float(r.period),
                angle_deg=float(r.angle_deg),
                modulation_depth=float(r.modulation_depth),
                mask=mask,
            )
            for r, mask in zip(regions, masks, strict=True)
        )

    if isinstance(noise, Emccd):
        clean = clean / clean.max() * noise.photons_peak
        frame = _emccd(rng, clean, noise)
    else:
        frame = clean + rng.normal(0.0, noise * peak, size=shape)

    frame, spike_mask, clipped_mask = _spike_and_clip(rng, frame, clean, spikes, clip_level)
    return Synthetic(
        frame=frame,
        truth=GroundTruth(
            regions=truths,
            spike_mask=spike_mask,
            clipped_mask=clipped_mask,
            phase_breaks=break_truths,
            forks=fork_truths,
        ),
        clean=clean,
    )


def _spike_and_clip(
    rng: np.random.Generator,
    frame: _F64,
    clean: _F64,
    spikes: int,
    clip_level: float | None,
) -> tuple[_F64, np.ndarray, np.ndarray]:
    """``(frame, spike_mask, clipped_mask)``: ``spikes`` Spike events added to
    the noisy ``frame``, then the clip at ``clip_level``.

    The clipped mask is taken on the spike-free frame (plan D4): its pixels at
    or above the level that no Spike hit (a hit pixel is a Spike pixel,
    clipped or not), so the two masks are disjoint. Without spikes and clip
    the frame is returned as it is (bit-identical; no RNG draw)."""
    spiked, spike_mask = frame, np.zeros(frame.shape, dtype=bool)
    if spikes > 0:
        added = _spikes(rng, frame.shape, spikes, float(clean.max()))
        spiked, spike_mask = frame + added, added > 0
    if clip_level is None:
        return spiked, spike_mask, np.zeros(frame.shape, dtype=bool)
    clipped_mask = (frame >= clip_level) & ~spike_mask
    return np.minimum(spiked, clip_level), spike_mask, clipped_mask


def _spikes(rng: np.random.Generator, shape: tuple[int, int], count: int, top: float) -> _F64:
    """The brightness ``count`` spike events add (frame shape, 0 where none hit).

    Draw order: start rows, start columns, lengths, directions in [0, pi), then
    a brightness for ``_SPIKE_MAX_LENGTH`` pixels per event (unused ones are
    discarded). A streak steps one pixel at a time along its dominant axis, so
    a streak of length L covers L distinct pixels; pixels off the frame are
    dropped, and overlapping hits add.
    """
    rows, cols = shape
    starts_r = rng.integers(0, rows, size=count)
    starts_c = rng.integers(0, cols, size=count)
    lengths = rng.integers(1, _SPIKE_MAX_LENGTH + 1, size=count)
    directions = rng.uniform(0.0, np.pi, size=count)
    low, high = _SPIKE_BRIGHTNESS
    brightness = rng.uniform(low, high, size=(count, _SPIKE_MAX_LENGTH)) * top
    added = np.zeros(shape)
    for i in range(count):
        dr, dc = np.sin(directions[i]), np.cos(directions[i])
        step = max(abs(dr), abs(dc))
        for k in range(int(lengths[i])):
            r = int(starts_r[i] + np.rint(k * dr / step))
            c = int(starts_c[i] + np.rint(k * dc / step))
            if 0 <= r < rows and 0 <= c < cols:
                added[r, c] += brightness[i, k]
    return added


def _check_stripes(period: float, modulation_depth: float) -> None:
    if not period > 0:
        raise ValueError(f"period must be > 0, got {period!r}")
    if not 0 <= modulation_depth <= 1:
        raise ValueError(f"modulation_depth must be in [0, 1], got {modulation_depth!r}")


def _check_region(r: StripedRegion) -> None:
    _check_stripes(r.period, r.modulation_depth)
    if not all(a > 0 for a in r.semi_axes) or len(r.semi_axes) != 2:
        raise ValueError(f"semi_axes must be > 0, got {r.semi_axes!r}")
    if not r.edge_px > 0:
        raise ValueError(f"edge_px must be > 0, got {r.edge_px!r}")


def _phase(x: _F64, y: _F64, period: float, angle_deg: float, phase0: float) -> _F64:
    t = np.deg2rad(angle_deg)
    return cast(_F64, 2 * np.pi / period * (x * np.cos(t) + y * np.sin(t)) + phase0)


def _canonical_break(b: PhaseBreakLine) -> PhaseBreakLine:
    """``b`` validated, with its angle in (-90, 90] and its jump, negated when
    the direction was flipped, wrapped to (-pi, pi]."""
    point = tuple(b.point)
    if len(point) != 2 or not all(math.isfinite(float(v)) for v in point):
        raise ValueError(f"phase break point must be a finite (row, col) pair, got {b.point!r}")
    if not math.isfinite(b.line_angle_deg):
        raise ValueError(f"phase break line_angle_deg must be finite, got {b.line_angle_deg!r}")
    if not math.isfinite(b.jump_rad):
        raise ValueError(f"phase break jump_rad must be finite, got {b.jump_rad!r}")
    angle, jump = float(b.line_angle_deg), float(b.jump_rad)
    if not -90.0 < angle <= 90.0:
        angle = (angle + 180.0) % 360.0 - 180.0  # same direction, in [-180, 180)
        if angle <= -90.0:
            angle, jump = angle + 180.0, -jump
        elif angle > 90.0:
            angle, jump = angle - 180.0, -jump
    jump = -((-jump + math.pi) % (2 * math.pi) - math.pi)  # (-pi, pi]
    return PhaseBreakLine((float(point[0]), float(point[1])), angle, jump)


def _break_truth(b: PhaseBreakLine, x: _F64, y: _F64) -> BreakTruth:
    """The canonical line ``b`` with its strictly positive side (frame shape)."""
    t = math.radians(b.line_angle_deg)
    side = math.cos(t) * (y - b.point[0]) - math.sin(t) * (x - b.point[1])
    return BreakTruth(
        point=b.point, line_angle_deg=b.line_angle_deg, jump_rad=b.jump_rad, shifted=side > 0
    )


def _break_phase(breaks: tuple[BreakTruth, ...]) -> _F64:
    """Sum of each break's Phase Jump on its positive side, sharp at each line."""
    total = np.zeros(breaks[0].shifted.shape)
    for b in breaks:
        total[b.shifted] += b.jump_rad
    return total


def _checked_fork(f: ForkPoint) -> ForkTruth:
    """``f`` validated, as a ``ForkTruth``."""
    point = tuple(f.point)
    if len(point) != 2 or not all(math.isfinite(float(v)) for v in point):
        raise ValueError(f"fork point must be a finite (row, col) pair, got {f.point!r}")
    d = f.direction
    if isinstance(d, bool) or not isinstance(d, int | np.integer) or d not in (1, -1):
        raise ValueError(f"fork direction must be the int +1 or -1, got {d!r}")
    return ForkTruth((float(point[0]), float(point[1])), int(d))


def _fork_phase(forks: tuple[ForkTruth, ...], x: _F64, y: _F64) -> _F64:
    """Sum of each fork's winding term ``direction * atan2(y - y0, x - x0)``."""
    total = np.zeros(x.shape)
    for f in forks:
        total = total + f.direction * np.arctan2(y - f.point[0], x - f.point[1])
    return total


def _region_mask(r: StripedRegion, x: _F64, y: _F64) -> _F64:
    """0.5 * (1 - tanh(d / w)): d the approximate signed distance to the ellipse,
    (normalised radius - 1) * minor semi-axis, and w set so 0.9 -> 0.1 spans edge_px."""
    rot = np.deg2rad(r.rotation_deg)
    dy, dx = y - r.center[0], x - r.center[1]
    v = dy * np.cos(rot) - dx * np.sin(rot)
    u = dy * np.sin(rot) + dx * np.cos(rot)
    radius = np.hypot(v / r.semi_axes[0], u / r.semi_axes[1])
    d = (radius - 1) * min(r.semi_axes)
    w = r.edge_px / (2 * np.arctanh(0.8))
    return cast(_F64, 0.5 * (1 - np.tanh(d / w)))


def _check_emccd(emccd: Emccd) -> None:
    if not emccd.photons_peak > 0:
        raise ValueError(f"photons_peak must be > 0, got {emccd.photons_peak!r}")
    if not emccd.em_gain >= 1:
        raise ValueError(f"em_gain must be >= 1, got {emccd.em_gain!r}")
    if not emccd.read_noise_e >= 0:
        raise ValueError(f"read_noise_e must be >= 0, got {emccd.read_noise_e!r}")
    if not emccd.cic >= 0:
        raise ValueError(f"cic must be >= 0, got {emccd.cic!r}")


def _emccd(rng: np.random.Generator, clean: _F64, emccd: Emccd) -> _F64:
    """Photons + spurious charge -> Poisson -> EM gain (Gamma) -> read noise."""
    n = rng.poisson(clean + emccd.cic)
    if emccd.em_gain > 1:
        electrons = np.zeros(clean.shape)
        lit = n > 0
        electrons[lit] = rng.gamma(n[lit], emccd.em_gain)
    else:
        electrons = n.astype(float)
    electrons = electrons + rng.normal(0.0, emccd.read_noise_e, size=clean.shape)
    return electrons / emccd.em_gain


def _profile(rng: np.random.Generator, rows: int, cols: int, x: _F64, y: _F64) -> _F64:
    """Elliptical, rotated, mildly asymmetric Gaussian with peak 1."""
    cx = (cols - 1) / 2 + rng.uniform(-3, 3)
    cy = (rows - 1) / 2 + rng.uniform(-3, 3)
    rot = np.deg2rad(rng.uniform(-30, 30))
    sigma_major = 0.30 * cols * rng.uniform(0.95, 1.05)
    sigma_minor = 0.22 * rows * rng.uniform(0.95, 1.05)
    dx, dy = x - cx, y - cy
    u = dx * np.cos(rot) + dy * np.sin(rot)
    v = -dx * np.sin(rot) + dy * np.cos(rot)
    # Mild asymmetry: one side of the major axis is ~15% wider.
    sigma_u = np.where(u >= 0, sigma_major * 1.15, sigma_major)
    return cast(_F64, np.exp(-0.5 * ((u / sigma_u) ** 2 + (v / sigma_minor) ** 2)))


def _mottle(
    rng: np.random.Generator, shape: tuple[int, int], kind: MottleKind, strength: float
) -> _F64:
    """Log-normal Mottle, ``exp(strength * g)`` with ``g`` of unit std."""
    if kind == "scorched":
        field = _standardise(np.tanh(2.5 * _grf(rng, shape, 3.0)) + 0.4 * _grf(rng, shape, 1.5))
    else:
        field = _grf(rng, shape, 2.2)
    return np.exp(strength * field)


def _grf(rng: np.random.Generator, shape: tuple[int, int], beta: float) -> _F64:
    """Isotropic Gaussian random field with power ~ k^-beta, unit std."""
    ky = np.fft.fftfreq(shape[0])[:, None]
    kx = np.fft.fftfreq(shape[1])[None, :]
    freq = np.hypot(kx, ky)
    freq[0, 0] = 1.0
    amp = freq ** (-beta / 2)
    amp[0, 0] = 0.0
    field = np.real(np.fft.ifft2(np.fft.fft2(rng.normal(size=shape)) * amp))
    return _standardise(field)


def _standardise(a: _F64) -> _F64:
    """Zero mean, unit std."""
    return cast(_F64, (a - a.mean()) / a.std())
