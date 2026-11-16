"""Local phase: Phase Breaks found from the demodulated local phase of a
region (ADR 0001; ticket 09).

A Phase Break is a straight line across which the stripe phase jumps. The
finder works on its own narrow Gabor response ``break_response`` (a window of
``_BREAK_SIGMA_ACROSS_PERIODS`` Periods across the stripes and
``_BREAK_SIGMA_ALONG_PERIODS`` along them, so the jump is blurred over about
one Period), divided by the local mean with the same window. Inside a domain
(a region's pixels, or two regions plus the gap between them) the response is
demodulated by its median carrier and sampled on a grid; for each candidate
line, a two-magnitude model (one complex value on each side, blended by the
window's step response across the line) is fitted to the samples near it, and
the fraction of the samples' power the model explains over a single value is
the line's evidence ``E``. The best line is accepted when ``E``, the jump and
the jump's spread along the line pass their limits; it is then explained
away and the search repeats (greedy, at most ``_BREAK_MAX_PER_REGION``).

Coordinates: scaled sensor coordinates, ``Y = vertical bin x row`` and
``X = horizontal bin x col`` (frame pixel index times its bin factor, see
``_local_stripes.pixel_size``). Every length is in Periods of the region's
sensor Period, so in sensor px. A line at angle ``a`` (degrees, canonical in
``(-90, 90]``) has direction ``(cos a, sin a)`` in ``(X, Y)``; its positive
side is where ``side = cos a (Y - Y0) - sin a (X - X0) > 0``, and the jump is
the phase on the positive side minus the phase on the other side, wrapped to
``(-pi, pi]`` (``wrap_jump``), the Phase Jump's range in the GLOSSARY. The
stripe phase grows with ``X cos A + Y sin A``.

Forks (ticket 10) are found from the winding of the same response
(``find_forks``); ``forks_explained`` takes found Forks out of it before the
Phase Break pass.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from scipy import ndimage
from scipy.special import ndtr

from denoisifier._local_stripes import _Spectrum, _window_sigmas, pixel_size
from denoisifier.report import BinFactors

# The finder's window sigmas, in Periods, across and along the stripes. They
# set both the narrow response (break_response) and the fitted step's width
# across a line (_sigma_n). A narrow along window keeps the jump sharp across
# a break that runs across the stripes (prototype P1, ticket 09).
_BREAK_SIGMA_ACROSS_PERIODS = 1.0
_BREAK_SIGMA_ALONG_PERIODS = 0.5
# The interior: domain pixels whose response magnitude is at least this
# fraction of its median over the domain.
_BREAK_MIN_MAGNITUDE_FRACTION = 0.5
# A domain with fewer interior pixels, or fewer horizontal or vertical
# interior neighbour pairs, gets no break.
_BREAK_MIN_INTERIOR_PX = 50
_BREAK_MIN_NEIGHBOUR_PAIRS = 8
# Sample grid stride (Periods, per axis; at least one frame px). No cap on
# the sample count: a cap moved the line error at Periods 3-5 (P1 v2).
_BREAK_SAMPLE_STRIDE_PERIODS = 0.5
# Offsets from a candidate line are binned at this width (Periods).
_BREAK_BIN_PERIODS = 0.25
# The two-magnitude fit uses the samples within this many Periods of the line.
_BREAK_FIT_HALF_WINDOW_PERIODS = 4.0
# A fit window counts only with at least this much sample area (Periods^2)
# on each side of the line.
_BREAK_MIN_SIDE_AREA_P2 = 6.0
# Search: coarse line angles over (-90, 90] every _BREAK_COARSE_STEP_DEG;
# then fine angles within +- _BREAK_FINE_SPAN_DEG of the best, every
# _BREAK_FINE_STEP_DEG, offsets within _BREAK_FINE_OFFSET_SPAN_PERIODS of the
# coarse offset; then, on long lines, a golden-section search within
# +- half a fine step, offsets within _BREAK_REFINE_OFFSET_SPAN_PERIODS, down
# to the angle at which the line's end moves _BREAK_LINE_TOL_PERIODS.
_BREAK_COARSE_STEP_DEG = 3.0
_BREAK_FINE_SPAN_DEG = 3.0
_BREAK_FINE_STEP_DEG = 0.5
_BREAK_FINE_OFFSET_SPAN_PERIODS = 2.0
_BREAK_LINE_TOL_PERIODS = 0.1
_BREAK_REFINE_OFFSET_SPAN_PERIODS = 1.0
# Acceptance. E is the fraction of the samples' power near the line that the
# two-magnitude model explains beyond one value: break-free frames reached
# 0.082 at most, true breaks of pi/2 0.18 at least (P1 v2, seeds
# 109_000-109_599). E is the one scalar ticket 11 calibrates (ADR 0003):
# _BREAK_MIN_EVIDENCE is the floor of the calibrated break threshold, which
# E must exceed (strict); the jump and spread rules stay fixed. The spread:
# the two side bands are cut into _BREAK_SEGMENTS pieces along the line; each piece with at least
# _BREAK_MIN_PIECE_SAMPLES samples on each side gives its own jump, and every
# one must lie within _BREAK_JUMP_SPREAD_RAD of the line's jump.
_BREAK_MIN_EVIDENCE = 0.1
_BREAK_MIN_JUMP_RAD = math.pi / 4
_BREAK_SEGMENTS = 3
_BREAK_MIN_PIECE_SAMPLES = 3
_BREAK_JUMP_SPREAD_RAD = math.pi / 4
# Explain-away zone and side-band gap: this many step widths (_sigma_n) from
# the line.
_BREAK_EXPLAIN_SIGMAS = 2.0
_BREAK_MAX_PER_REGION = 4
# Frame-period gate (frame px along the stripe normal). The finder's across
# window (1 Period) puts its passband edge at k sigma at (1/P)(1 + k/2pi),
# which reaches the frame's Nyquist limit at a frame Period of
# 2(1 + k/2pi) = 2.5 for k = pi/2. A second, stricter limit beside
# MIN_FRAME_PERIOD_PX (2.0), for the finder only. Measured (2x1, seeds
# 110_400-110_459): at frame Period 2.0 the finder found no true break and
# faked one on a break-free frame; at 2.1-2.25 its lines were 1.3-1.8
# Periods off.
_BREAK_MIN_FRAME_PERIOD_PX = 2.5

# Forks (ticket 10; prototype P2 frozen at worktree commit 3922e33). The
# winding is counted around a square loop of half-size _FORK_LOOP_PERIODS
# Periods about every pixel. Interior: domain pixels whose response magnitude
# is at least _FORK_MIN_MAGNITUDE_FRACTION of its median over the domain.
# Around each found Phase Break, a band of _FORK_BREAK_BAND_SIGMAS finder step
# widths (_finder_sigma_n) is stepped across. The domain is the region closed
# by a disc of _FORK_DOMAIN_CLOSE_PERIODS Periods. A candidate's evidence E
# is its winding component's area over the loop's area: the pre-break search
# keeps E >= _FORK_GATE_EVIDENCE, the reported forks E above the calibrated
# Fork threshold (strict; ticket 11, ADR 0003), whose floor is
# _FORK_MIN_EVIDENCE (largest on fork-free and break-only frames 0.000; true
# forks at least 0.31, P2 explore).
_FORK_LOOP_PERIODS = 2.0
_FORK_MIN_MAGNITUDE_FRACTION = 0.5
_FORK_BREAK_BAND_SIGMAS = 2.0
_FORK_DOMAIN_CLOSE_PERIODS = 3.0
_FORK_GATE_EVIDENCE = 0.2
_FORK_MIN_EVIDENCE = 0.3


@dataclass(frozen=True)
class FoundBreak:
    """One accepted Phase Break, in scaled sensor coordinates.

    ``point`` (Y, X) is on the line; ``line_angle_deg`` is canonical in
    ``(-90, 90]``; ``jump_rad`` in ``(-pi, pi]`` is the phase on the positive
    side minus the other side; ``evidence`` is E (for ticket 11; not reported)."""

    point: tuple[float, float]
    line_angle_deg: float
    jump_rad: float
    evidence: float

    def side(self, y: np.ndarray, x: np.ndarray) -> np.ndarray:
        """Signed distance (sensor px) from the line; positive on the positive side."""
        return line_side(y, x, self.point, self.line_angle_deg)

    def along(self, y: np.ndarray, x: np.ndarray) -> np.ndarray:
        """Position (sensor px) along the line's direction, from ``point``."""
        t = math.radians(self.line_angle_deg)
        return np.asarray(math.cos(t) * (x - self.point[1]) + math.sin(t) * (y - self.point[0]))


def line_side(
    y: np.ndarray, x: np.ndarray, point: tuple[float, float], line_angle_deg: float
) -> np.ndarray:
    """Signed distance (sensor px) of (``y``, ``x``) from the line through
    ``point`` (Y, X) at ``line_angle_deg``: ``cos a (Y - Y0) - sin a (X - X0)``,
    positive on the line's positive side."""
    t = math.radians(line_angle_deg)
    return np.asarray(math.cos(t) * (y - point[0]) - math.sin(t) * (x - point[1]))


def wrap_jump(a: np.ndarray | float) -> np.ndarray:
    """``a`` (radians) wrapped to ``(-pi, pi]``, the Phase Jump's range; a
    value already in that range is returned exactly."""
    a = np.asarray(a, dtype=float)
    turned = a - 2 * np.pi * np.ceil((a - np.pi) / (2 * np.pi))
    return np.asarray(np.where((a > -np.pi) & (a <= np.pi), a, turned))


def sensor_coordinates(
    rows: np.ndarray, cols: np.ndarray, bins: BinFactors
) -> tuple[np.ndarray, np.ndarray]:
    """Scaled sensor coordinates (Y, X) of frame pixel indices ``rows`` and
    ``cols``: each index times its bin factor (see the module docstring)."""
    v, h = pixel_size(bins)
    return (rows * v).astype(float), (cols * h).astype(float)


def frame_period(period: float, angle_deg: float, bins: BinFactors) -> float:
    """The Period in frame px along the stripe normal, for a sensor
    ``period`` at stripe Angle ``angle_deg`` under ``bins``."""
    t = math.radians(angle_deg)
    return 1.0 / math.hypot(
        bins.horizontal * math.cos(t) / period, bins.vertical * math.sin(t) / period
    )


def sigma_n(
    period: float, angle_deg: float, line_angle_deg: float, across: float, along: float
) -> float:
    """The width (sensor px) across a line at ``line_angle_deg`` of a window
    with sigmas ``across`` and ``along`` Periods across and along stripes at
    ``angle_deg``."""
    d = math.radians(angle_deg - line_angle_deg)
    return math.hypot(across * period * math.sin(d), along * period * math.cos(d))


def _finder_sigma_n(period: float, angle_deg: float, line_angle_deg: float) -> float:
    return sigma_n(
        period,
        angle_deg,
        line_angle_deg,
        _BREAK_SIGMA_ACROSS_PERIODS,
        _BREAK_SIGMA_ALONG_PERIODS,
    )


def break_response(spectrum: _Spectrum, period: float, angle_deg: float) -> np.ndarray:
    """``z = 2 x (finder Gabor) / (local mean with the same window)``, complex,
    frame shape: the finder's narrow response at the sensor ``period`` and
    ``angle_deg`` on the shared spectrum; 0 where the local mean is not
    positive."""
    sigma_across, sigma_along = _window_sigmas(
        period, _BREAK_SIGMA_ACROSS_PERIODS, _BREAK_SIGMA_ALONG_PERIODS
    )
    response = spectrum.gaussian(period, angle_deg, sigma_across, sigma_along)
    mean = np.real(spectrum.gaussian(None, 0.0, sigma_across, sigma_along))
    z = np.zeros(response.shape, dtype=complex)
    np.divide(2 * response, mean, out=z, where=mean > 0)
    return z


class _LineFit(NamedTuple):
    """One fitted line: its E, angle (degrees; may lie outside (-90, 90]
    before canonicalisation), offset from the samples' mean (sensor px) and
    jump (radians)."""

    evidence: float
    angle_deg: float
    offset: float
    jump: float


@dataclass
class _Scan:
    """Every valid (angle, offset) window of a scan with its E and jump."""

    angle: np.ndarray
    offset: np.ndarray
    evidence: np.ndarray
    jump: np.ndarray

    def fit(self, i: int) -> _LineFit:
        return _LineFit(
            float(self.evidence[i]),
            float(self.angle[i]),
            float(self.offset[i]),
            float(self.jump[i]),
        )

    def best(self) -> _LineFit:
        """The window with the highest E."""
        return self.fit(int(np.argmax(self.evidence)))

    def best_near(self, offset: float, span: float) -> _LineFit | None:
        """The window with the highest E within ``span`` of ``offset``; None
        when there is none."""
        near = np.flatnonzero(np.abs(self.offset - offset) <= span)
        if not len(near):
            return None
        return self.fit(int(near[np.argmax(self.evidence[near])]))


class _Samples:
    """The demodulated samples of one domain and the two-magnitude fit on them."""

    def __init__(
        self,
        w: np.ndarray,
        y: np.ndarray,
        x: np.ndarray,
        cell_area: float,
        period: float,
        angle_deg: float,
    ):
        self.w = w
        self.y, self.x = y, x
        self.y0, self.x0 = float(y.mean()), float(x.mean())
        self.period = period
        self.angle_deg = angle_deg
        self.bin = _BREAK_BIN_PERIODS * period
        self.half = round(_BREAK_FIT_HALF_WINDOW_PERIODS / _BREAK_BIN_PERIODS)
        self.min_side = _BREAK_MIN_SIDE_AREA_P2 * period * period / cell_area
        self.extent = float(np.hypot(np.ptp(y), np.ptp(x)))

    def offsets(self, line_angle_deg: float) -> np.ndarray:
        """Signed distance of each sample from the line through the samples' mean."""
        return line_side(self.y, self.x, (self.y0, self.x0), line_angle_deg)

    def scan(self, angles: np.ndarray) -> _Scan | None:
        """The fit at every offset bin of every angle in ``angles``; None when
        no angle has the offset extent of a full window (small regions)."""
        k = self.half
        rk = np.arange(-k, k)
        out: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
        nonzero = (np.abs(self.w) > 0).astype(float)
        magnitude = np.abs(self.w)
        for a in angles:
            s = self.offsets(float(a))
            lo = float(s.min())
            nb = int((s.max() - lo) / self.bin) + 1
            if nb < 2 * k + 1:
                continue
            idx = np.clip(((s - lo) / self.bin).astype(np.int64), 0, nb - 1)
            zr = np.bincount(idx, weights=self.w.real, minlength=nb)
            zi = np.bincount(idx, weights=self.w.imag, minlength=nb)
            n = np.bincount(idx, weights=nonzero, minlength=nb)
            m = np.bincount(idx, weights=magnitude, minlength=nb)
            step = ndtr(
                (rk + 0.5) * self.bin / _finder_sigma_n(self.period, self.angle_deg, float(a))
            )
            rest = 1 - step

            def cor(v: np.ndarray, kernel: np.ndarray) -> np.ndarray:
                return np.correlate(v, kernel, "valid")

            s11, s12, s22 = cor(n, rest * rest), cor(n, rest * step), cor(n, step * step)
            b1 = cor(zr, rest) + 1j * cor(zi, rest)
            b2 = cor(zr, step) + 1j * cor(zi, step)
            n_minus = cor(n, (rk < 0).astype(float))
            n_plus = cor(n, (rk >= 0).astype(float))
            count = n_minus + n_plus
            mean_magnitude = cor(m, np.ones(2 * k)) / np.maximum(count, 1)
            det = s11 * s22 - s12**2
            valid = (n_minus >= self.min_side) & (n_plus >= self.min_side) & (det > 0)
            det = np.where(det > 0, det, 1)
            c_minus = (s22 * b1 - s12 * b2) / det
            c_plus = (s11 * b2 - s12 * b1) / det
            jump = np.angle(c_plus * np.conj(c_minus))
            explained = np.real(np.conj(c_minus) * b1 + np.conj(c_plus) * b2) - np.abs(
                b1 + b2
            ) ** 2 / np.maximum(count, 1)
            evidence = np.where(
                valid, explained / np.maximum(count * mean_magnitude**2, 1e-30), -1.0
            )
            centre = np.arange(len(evidence)) + k
            out.append((np.full(len(evidence), float(a)), lo + centre * self.bin, evidence, jump))
        if not out:
            return None
        return _Scan(*(np.concatenate(col) for col in zip(*out, strict=True)))

    def best_near(self, angle: float, offset: float, span: float) -> _LineFit | None:
        """The best window at ``angle`` within ``span`` of ``offset``; None
        when there is none."""
        found = self.scan(np.array([angle]))
        if found is None:
            return None
        return found.best_near(offset, span)


def find_phase_breaks(
    z: np.ndarray,
    domain: np.ndarray,
    period: float,
    angle_deg: float,
    bins: BinFactors,
    *,
    min_evidence: float,
    max_lines: int = _BREAK_MAX_PER_REGION,
) -> list[FoundBreak]:
    """The Phase Breaks in ``domain`` (bool, frame shape) of the finder's
    response ``z`` (``break_response`` at ``period`` and ``angle_deg``, sensor
    px), greedy, at most ``max_lines``, in the order found. A line is accepted
    when its E is above ``min_evidence`` (strict) and its jump and spread pass
    their fixed rules; the search stops at the first line that is not. The
    best line never depends on ``min_evidence``, so the result at a higher
    threshold is a prefix of the result at a lower one.

    ``[]`` when ``frame_period(period, angle_deg, bins)`` is under
    _BREAK_MIN_FRAME_PERIOD_PX (the caller reports the refusal), when the
    domain's interior is too small, and when no line passes the acceptance
    rules. A line at a given angle is fitted only where the domain's samples
    extend at least 2 x _BREAK_FIT_HALF_WINDOW_PERIODS across it (along its
    normal), so a region shorter than about that across a break gets no break
    on it (a wide, short region can still hold a slightly tilted line, at an
    angle where its extent is enough): measured, heights of 3-5
    Periods changed nothing on 20 frames each, 8 Periods found the break on
    18-19 of 20; 6-7 Periods are undefined. The angle's golden-section search
    assumes one E peak within half a fine step."""
    if frame_period(period, angle_deg, bins) < _BREAK_MIN_FRAME_PERIOD_PX:
        return []
    samples = _samples(z, domain, period, angle_deg, bins)
    if samples is None:
        return []
    found: list[FoundBreak] = []
    coarse = np.arange(-90 + _BREAK_COARSE_STEP_DEG, 90 + 1e-9, _BREAK_COARSE_STEP_DEG)
    for _ in range(max_lines):
        best = _best_line(samples, coarse)
        if best is None:
            break
        evidence, a, o, jump = best
        if a > 90:
            a, o, jump = a - 180, -o, -jump
        elif a <= -90:
            a, o, jump = a + 180, -o, -jump
        jump = float(wrap_jump(jump))
        t = math.radians(a)
        brk = FoundBreak(
            point=(samples.y0 + o * math.cos(t), samples.x0 - o * math.sin(t)),
            line_angle_deg=float(a),
            jump_rad=float(jump),
            evidence=evidence,
        )
        if not _accepted(samples, brk, min_evidence):
            break
        found.append(brk)
        s = brk.side(samples.y, samples.x)
        g = _BREAK_EXPLAIN_SIGMAS * _finder_sigma_n(period, angle_deg, a)
        w = np.where(s > 0, samples.w * np.exp(-1j * jump), samples.w)
        samples.w = np.where(np.abs(s) < g, 0, w)
    return found


def _bounding_box(mask: np.ndarray) -> tuple[slice, slice]:
    """The (rows, cols) slices of the smallest box holding every set pixel
    of ``mask`` (bool, 2D, at least one pixel set)."""
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return slice(int(rows[0]), int(rows[-1]) + 1), slice(int(cols[0]), int(cols[-1]) + 1)


def _samples(
    z: np.ndarray, domain: np.ndarray, period: float, angle_deg: float, bins: BinFactors
) -> _Samples | None:
    """The demodulated interior samples of ``domain``; None when it is too small."""
    if not domain.any():
        return None
    crop = _bounding_box(domain)
    r0, c0 = crop[0].start, crop[1].start
    zc, dom = z[crop], domain[crop]
    magnitude = np.abs(zc)
    interior = dom & (magnitude >= _BREAK_MIN_MAGNITUDE_FRACTION * np.median(magnitude[dom]))
    if interior.sum() < _BREAK_MIN_INTERIOR_PX:
        return None
    h_pairs = interior[:, :-1] & interior[:, 1:]
    v_pairs = interior[:-1, :] & interior[1:, :]
    if h_pairs.sum() < _BREAK_MIN_NEIGHBOUR_PAIRS or v_pairs.sum() < _BREAK_MIN_NEIGHBOUR_PAIRS:
        return None
    kx = float(np.median(np.angle(zc[:, 1:] * np.conj(zc[:, :-1]))[h_pairs]))
    ky = float(np.median(np.angle(zc[1:, :] * np.conj(zc[:-1, :]))[v_pairs]))
    v, h = bins.vertical, bins.horizontal
    stride_r = max(1, int(_BREAK_SAMPLE_STRIDE_PERIODS * period / v))
    stride_c = max(1, int(_BREAK_SAMPLE_STRIDE_PERIODS * period / h))
    grid = np.zeros_like(interior)
    grid[::stride_r, ::stride_c] = True
    rr, cc = np.nonzero(interior & grid)
    w = zc[rr, cc] * np.exp(-1j * (kx * cc + ky * rr))
    y, x = sensor_coordinates(rr + r0, cc + c0, bins)
    return _Samples(
        w,
        y,
        x,
        float(stride_r * stride_c * h * v),
        period,
        angle_deg,
    )


def _best_line(samples: _Samples, coarse: np.ndarray) -> _LineFit | None:
    """The best line (offset from the samples' mean): coarse scan, fine scan,
    then golden-section refinement on long lines. The angle may lie outside
    (-90, 90]; the caller canonicalises it."""
    first = samples.scan(coarse)
    if first is None:
        return None
    best = first.best()
    a0, o0 = best.angle_deg, best.offset
    fine = np.arange(
        a0 - _BREAK_FINE_SPAN_DEG, a0 + _BREAK_FINE_SPAN_DEG + 1e-9, _BREAK_FINE_STEP_DEG
    )
    second = samples.scan(fine)
    if second is not None:
        fine_best = second.best_near(o0, _BREAK_FINE_OFFSET_SPAN_PERIODS * samples.period)
        if fine_best is not None:
            best = fine_best
    tol = math.degrees(_BREAK_LINE_TOL_PERIODS * samples.period / max(samples.extent, 1.0))
    if tol < _BREAK_FINE_STEP_DEG / 2:
        best = _golden(samples, best, tol)
    return best


def _golden(samples: _Samples, best: _LineFit, tol: float) -> _LineFit:
    """Golden-section search of the angle within +- half a fine step of
    ``best``, down to ``tol`` degrees; the result replaces ``best`` only when
    its E is higher. Assumes one E peak in that interval."""
    a, o = best.angle_deg, best.offset
    span = _BREAK_REFINE_OFFSET_SPAN_PERIODS * samples.period
    lo, hi = a - _BREAK_FINE_STEP_DEG / 2, a + _BREAK_FINE_STEP_DEG / 2
    ratio = (math.sqrt(5) - 1) / 2
    c1, c2 = hi - ratio * (hi - lo), lo + ratio * (hi - lo)
    f1, f2 = samples.best_near(c1, o, span), samples.best_near(c2, o, span)
    while hi - lo > tol and f1 is not None and f2 is not None:
        if f1.evidence >= f2.evidence:
            hi, c2, f2 = c2, c1, f1
            c1 = hi - ratio * (hi - lo)
            f1 = samples.best_near(c1, o, span)
        else:
            lo, c1, f1 = c1, c2, f2
            c2 = lo + ratio * (hi - lo)
            f2 = samples.best_near(c2, o, span)
    for candidate in (f1, f2):
        if candidate is not None and candidate.evidence > best.evidence:
            best = candidate
    return best


def _accepted(samples: _Samples, brk: FoundBreak, min_evidence: float) -> bool:
    """E is above ``min_evidence`` (strict) and the jump and the jump's
    spread along the line pass their limits."""
    if not brk.evidence > min_evidence or abs(brk.jump_rad) < _BREAK_MIN_JUMP_RAD:
        return False
    period = samples.period
    gap = _BREAK_EXPLAIN_SIGMAS * _finder_sigma_n(period, samples.angle_deg, brk.line_angle_deg)
    band = max(1.0, _BREAK_FIT_HALF_WINDOW_PERIODS - gap / period) * period
    s = brk.side(samples.y, samples.x)
    u = brk.along(samples.y, samples.x)
    minus = (s >= -gap - band) & (s < -gap)
    plus = (s >= gap) & (s < gap + band)
    either = minus | plus
    if not either.any():
        return False
    edges = np.linspace(u[either].min(), u[either].max() + 1e-9, _BREAK_SEGMENTS + 1)
    pieces = []
    for piece in range(_BREAK_SEGMENTS):
        inside = (u >= edges[piece]) & (u < edges[piece + 1])
        m, p = minus & inside, plus & inside
        if m.sum() < _BREAK_MIN_PIECE_SAMPLES or p.sum() < _BREAK_MIN_PIECE_SAMPLES:
            continue
        pieces.append(float(np.angle(samples.w[p].sum() * np.conj(samples.w[m].sum()))))
    if not pieces:
        return False
    spread = float(np.max(np.abs(wrap_jump(np.array(pieces) - brk.jump_rad))))
    return spread <= _BREAK_JUMP_SPREAD_RAD


@dataclass(frozen=True)
class FoundFork:
    """One Fork candidate, in scaled sensor coordinates.

    ``point`` (Y, X) is the centroid of its winding component; ``direction``
    is +1 or -1, the generator's convention (``synthetic.ForkPoint``);
    ``evidence`` is E, the component's area over the loop's area (for ticket
    11; not reported)."""

    point: tuple[float, float]
    direction: int
    evidence: float


def fork_domain(
    pixels: np.ndarray, others: np.ndarray, period: float, bins: BinFactors
) -> np.ndarray:
    """The Fork search domain of a region (bool, frame shape): its
    ``pixels`` closed by a disc of _FORK_DOMAIN_CLOSE_PERIODS x ``period``
    sensor px (sensor geometry) inside their bounding box, holes filled,
    ``others`` (other regions' pixels) left out. The closing gives back the
    notch the region growth carves at a fork."""
    out = np.zeros(pixels.shape, dtype=bool)
    if not pixels.any():
        return out
    box = _bounding_box(pixels)
    pix = pixels[box]
    v, h = pixel_size(bins)
    rho = _FORK_DOMAIN_CLOSE_PERIODS * period
    pr, pc = math.ceil(rho / v) + 1, math.ceil(rho / h) + 1
    padded = np.pad(pix, ((pr, pr), (pc, pc)))
    dilated = ndimage.distance_transform_edt(~padded, sampling=(v, h)) <= rho
    closed = ~(ndimage.distance_transform_edt(dilated, sampling=(v, h)) <= rho)
    closed = closed[pr:-pr, pc:-pc] | pix
    out[box] = ndimage.binary_fill_holes(closed) & ~others[box]
    return out


def _box_sum(a: np.ndarray, rows: tuple[int, int], cols: tuple[int, int]) -> np.ndarray:
    """Sum of ``a`` over the box [r - above, r + below] x [c - left, c +
    right] about each pixel, zero-padded, for ``rows`` = (above, below) and
    ``cols`` = (left, right); the shape of ``a``."""
    (above, below), (left, right) = rows, cols
    padded = np.pad(a, ((above + 1, below), (left + 1, right)))
    total = padded.cumsum(0).cumsum(1)
    k1, k2 = above + below + 1, left + right + 1
    return np.asarray(total[k1:, k2:] - total[:-k1, k2:] - total[k1:, :-k2] + total[:-k1, :-k2])


def find_forks(
    z: np.ndarray,
    domain: np.ndarray,
    period: float,
    angle_deg: float,
    bins: BinFactors,
    breaks: Sequence[FoundBreak] = (),
) -> list[FoundFork]:
    """Every Fork candidate in ``domain`` (bool, frame shape, see
    ``fork_domain``) of the finder's response ``z`` (``break_response`` at
    ``period`` and ``angle_deg``), sorted by evidence, descending; the caller
    applies _FORK_GATE_EVIDENCE or _FORK_MIN_EVIDENCE. ``breaks`` (found in
    the same region) are explained away first.

    Method (lattice residues and square-loop winding): the domain's interior
    (magnitude at least _FORK_MIN_MAGNITUDE_FRACTION of its median) is
    demodulated by its median neighbour carrier. Each break's positive side
    is turned back by its jump, and every pixel within
    _FORK_BREAK_BAND_SIGMAS step widths of its line takes the value of the
    point at the band's edge on its own side, so a loop steps across the
    band. The phase residue of each 2x2 plaquette (+1 = the generator's +1)
    summed over the square of half-size _FORK_LOOP_PERIODS Periods about a
    pixel is the winding there; it counts only where every loop pixel is
    valid and the square lies inside the domain's box. Each connected set of
    pixels with winding +1 (or -1) is one candidate at its centroid.

    ``[]`` when ``frame_period(period, angle_deg, bins)`` is under
    _BREAK_MIN_FRAME_PERIOD_PX (the same response and limit as the break
    finder) and when the domain is too small.

    Limits, as measured (prototype P2, validation seeds unless said; Periods
    P of the region): forks within about 4 P of a region's edge are not
    found (at 1, 2 and 3 P from the 0.5 contour: 0/20, 0/20, 6/20). Two
    forks 4 P apart are both found (a large region 26/27, a 09-size region
    24/27); 3 P apart only partly (both found 5/27 in a large region, 11/27
    in a 09-size one). A fork and a Phase Break 4 P apart are both found in a
    large region (39/40); at 3 P, 38/40 (explore 50/60); closer than 3 P both
    are usually lost (1.5 P 7/40, 2 P 8/40): undefined closer than 4 P. In a
    09-size region (semi-axes 5 by 6.6 P) only a core about 1 by 2.6 P lies
    4 P from the edge, so forks are found only near its centre. The loop
    size was tuned once (1.5 P was tried and rejected)."""
    if frame_period(period, angle_deg, bins) < _BREAK_MIN_FRAME_PERIOD_PX:
        return []
    if not domain.any():
        return []
    v, h = pixel_size(bins)
    crop = _bounding_box(domain)
    r0, c0 = crop[0].start, crop[1].start
    zc, dom = z[crop], domain[crop]
    magnitude = np.abs(zc)
    median = float(np.median(magnitude[dom]))
    interior = dom & (magnitude >= _FORK_MIN_MAGNITUDE_FRACTION * median)
    height, width = zc.shape
    if height < 3 or width < 3:
        return []
    h_pairs = interior[:, :-1] & interior[:, 1:]
    v_pairs = interior[:-1, :] & interior[1:, :]
    if h_pairs.sum() < 8 or v_pairs.sum() < 8:
        return []
    kx = float(np.median(np.angle(zc[:, 1:] * np.conj(zc[:, :-1]))[h_pairs]))
    ky = float(np.median(np.angle(zc[1:, :] * np.conj(zc[:-1, :]))[v_pairs]))
    rr, cc = np.mgrid[0:height, 0:width]
    demodulated = zc * np.exp(-1j * (kx * cc + ky * rr))
    valid = interior.copy()
    if breaks:
        demodulated, valid = _stepped_across(
            demodulated, valid, dom, breaks, (r0, c0), period, angle_deg, bins
        )
    dx = np.angle(demodulated[:, 1:] * np.conj(demodulated[:, :-1]))
    dy = np.angle(demodulated[1:, :] * np.conj(demodulated[:-1, :]))
    circulation = dx[:-1, :] + dy[:, 1:] - dx[1:, :] - dy[:, :-1]
    # Plaquette (r, c) lies between pixels r..r+1 and c..c+1.
    residues = np.rint(circulation / (2 * np.pi)).astype(np.int64)
    loop = _FORK_LOOP_PERIODS * period
    lr = max(1, round(loop / v))
    lc = max(1, round(loop / h))
    # The winding about pixel (r, c): plaquettes r-lr..r+lr-1, c-lc..c+lc-1
    # (residues padded to the crop's shape; plaquette row and column
    # height-1 and width-1 do not exist).
    winding = _box_sum(np.pad(residues, ((0, 1), (0, 1))), (lr, lr - 1), (lc, lc - 1))
    bad = (~valid).astype(np.int64)
    ring_bad = _box_sum(bad, (lr, lr), (lc, lc)) - _box_sum(bad, (lr - 1, lr - 1), (lc - 1, lc - 1))
    # The whole square must lie inside the crop.
    loop_valid = ring_bad == 0
    loop_valid[:lr, :] = loop_valid[-lr:, :] = False
    loop_valid[:, :lc] = loop_valid[:, -lc:] = False
    out = []
    for d in (1, -1):
        labelled, n = ndimage.label(loop_valid & (winding == d))
        if not n:
            continue
        index = np.arange(1, n + 1)
        count = ndimage.sum_labels(np.ones_like(labelled), labelled, index)
        cy, cx = sensor_coordinates(
            ndimage.mean(rr, labelled, index) + r0, ndimage.mean(cc, labelled, index) + c0, bins
        )
        for k in range(n):
            area = float(count[k]) * v * h
            out.append(
                FoundFork(
                    point=(float(cy[k]), float(cx[k])),
                    direction=d,
                    evidence=area / (2 * loop) ** 2,
                )
            )
    out.sort(key=lambda f: -f.evidence)
    return out


def forks_explained(z: np.ndarray, forks: Sequence[FoundFork], bins: BinFactors) -> np.ndarray:
    """``z`` (a finder response, frame shape) with each fork's winding taken
    out: ``z * exp(-i sum d atan2(Y - Yf, X - Xf))`` over the whole grid, in
    scaled sensor coordinates. The minus sign undoes the generator's
    ``+d atan2`` term (``synthetic.ForkPoint``). A new array; ``z`` is not
    changed."""
    if not forks:
        return z.copy()
    rows, cols = np.mgrid[0 : z.shape[0], 0 : z.shape[1]]
    y, x = sensor_coordinates(rows, cols, bins)
    winding = np.zeros(z.shape)
    for f in forks:
        winding += f.direction * np.arctan2(y - f.point[0], x - f.point[1])
    return np.asarray(z * np.exp(-1j * winding))


def _stepped_across(
    demodulated: np.ndarray,
    valid: np.ndarray,
    dom: np.ndarray,
    breaks: Sequence[FoundBreak],
    origin: tuple[int, int],
    period: float,
    angle_deg: float,
    bins: BinFactors,
) -> tuple[np.ndarray, np.ndarray]:
    """``demodulated`` (cropped at ``origin``) with each break's positive
    side turned back by its jump, and each pixel within
    _FORK_BREAK_BAND_SIGMAS step widths of a line given the value and
    validity of the point at the band's edge on its own side."""
    v, h = pixel_size(bins)
    r0, c0 = origin
    height, width = demodulated.shape
    rr, cc = np.mgrid[0:height, 0:width]
    y, x = sensor_coordinates(rr + r0, cc + c0, bins)
    for b in breaks:
        demodulated = np.where(
            b.side(y, x) > 0, demodulated * np.exp(-1j * b.jump_rad), demodulated
        )
    for b in breaks:
        side = b.side(y, x)
        half_width = _FORK_BREAK_BAND_SIGMAS * _finder_sigma_n(period, angle_deg, b.line_angle_deg)
        band = np.abs(side) < half_width
        if not band.any():
            continue
        t = math.radians(b.line_angle_deg)
        ny, nx = math.cos(t), -math.sin(t)  # the gradient of side in (Y, X)
        band_side = side[band]
        shift = np.where(band_side >= 0, half_width - band_side, -half_width - band_side)
        shift += np.where(band_side >= 0, 0.5, -0.5) * max(v, h)
        ty = np.rint((y[band] + shift * ny) / v).astype(int) - r0
        tx = np.rint((x[band] + shift * nx) / h).astype(int) - c0
        inside = (ty >= 0) & (ty < height) & (tx >= 0) & (tx < width)
        source_ok = np.zeros(band_side.shape, dtype=bool)
        values = np.zeros(band_side.shape, dtype=complex)
        source_ok[inside] = valid[ty[inside], tx[inside]]
        values[inside] = demodulated[ty[inside], tx[inside]]
        at = np.nonzero(band)
        demodulated = demodulated.copy()
        demodulated[at] = values
        valid = valid.copy()
        valid[at] = source_ok & dom[at]
    return demodulated, valid
