import copy
import hashlib
import math
import re

import numpy as np
import pytest
from scipy import ndimage

from cases import case_frame, clipped_at
from denoisifier import synthetic
from denoisifier.synthetic import Emccd, PhaseBreakLine, StripedRegion, generate
from protected import (
    BREAK_PHASE_ATOL,
    CLIP_LEVEL_FRACTION,
    DIGEST_TEST_SEEDS,
    MASK_AREA_REL_TOL,
    MASK_CONTOUR_TOL_PX,
    MASK_EDGE_WIDTH_TOL_PX,
    MASK_SATURATION_TOL,
    MASK_TAIL,
    MOTTLE_NONE_TEST_SEED,
    OUTSIDE_REGIONS_RTOL,
    PHASE_BREAK_TEST_SEEDS,
    REGION_GENERATOR_TEST_SEED,
    SAME_SEED_TEST_SEEDS,
    SATURATING_CLIP_FACTOR,
    SINGLE_FRAME_TEST_SEED,
    SPIKE_GENERATOR_TEST_SEED,
    SPIKE_TEST_COUNT,
    STREAK_TEST_SEEDS,
    STRIPE_FREE_SPECTRUM_TEST_SEEDS,
)
from regions import truth_pixels
from spectrum import band_peak
from truth_match import assert_matches_truth


def test_same_seed_gives_same_frame():
    seed, other = SAME_SEED_TEST_SEEDS
    a = generate(seed=seed)
    b = generate(seed=seed)
    c = generate(seed=other)
    assert np.array_equal(a.frame, b.frame)
    assert not np.array_equal(a.frame, c.frame)


def test_returns_frame_and_ground_truth():
    s = generate(
        seed=SINGLE_FRAME_TEST_SEED,
        shape=(64, 80),
        period=7.5,
        angle_deg=-4.0,
        modulation_depth=0.3,
    )
    assert s.frame.shape == (64, 80)
    assert s.truth.period == 7.5
    assert s.truth.angle_deg == -4.0
    assert s.truth.modulation_depth == 0.3


@pytest.mark.parametrize(
    ("kind", "strength", "expected"),
    [("scorched", None, 0.4), ("multiscale", None, 0.35), ("scorched", 0.2, 0.2)],
)
def test_mottle_has_the_requested_strength(kind, strength, expected):
    common = dict(seed=SINGLE_FRAME_TEST_SEED, noise=0.0, modulation_depth=0.0)
    mottled = generate(**common, mottle=kind, mottle_strength=strength)
    plain = generate(**common, mottle="none")
    assert np.std(np.log(mottled.frame / plain.frame)) == pytest.approx(expected, abs=1e-9)


def test_mottle_none_is_unchanged_from_ticket_01():
    seed = MOTTLE_NONE_TEST_SEED
    assert np.array_equal(generate(seed=seed).frame, generate(seed=seed, mottle="none").frame)


def test_emccd_peak_photon_count():
    s = generate(seed=SINGLE_FRAME_TEST_SEED, mottle="scorched", noise=Emccd(photons_peak=250))
    assert s.clean.max() == pytest.approx(250, abs=1e-9)


def _noise_residual(emccd):
    s = generate(
        seed=SINGLE_FRAME_TEST_SEED,
        shape=(256, 256),
        mottle="none",
        modulation_depth=0.0,
        noise=emccd,
    )
    return s, s.frame - s.clean


def test_emccd_with_gain_has_excess_noise_factor_two():
    s, r = _noise_residual(Emccd(em_gain=300, read_noise_e=0, cic=0))
    mean_clean = s.clean.mean()
    assert abs(r.mean()) <= 0.02 * mean_clean
    assert 1.9 <= r.var() / mean_clean <= 2.1


def test_emccd_with_gain_off_counts_whole_photons():
    s, r = _noise_residual(Emccd(em_gain=1, read_noise_e=0, cic=0))
    assert np.array_equal(s.frame, np.round(s.frame))
    assert 0.95 <= r.var() / s.clean.mean() <= 1.05


def test_emccd_read_noise_adds_its_variance():
    s, r = _noise_residual(Emccd(em_gain=1, read_noise_e=20, cic=0))
    assert abs((r.var() - s.clean.mean()) - 400) <= 0.05 * 400


def test_emccd_spurious_charge_adds_its_mean():
    # photons_peak=1 keeps the shot-noise error on the mean far below the tolerance.
    _, r = _noise_residual(Emccd(photons_peak=1, em_gain=1, read_noise_e=0, cic=0.5))
    assert abs(r.mean() - 0.5) <= 0.05 * 0.5


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (dict(mottle="speckled"), "mottle must be 'none', 'scorched' or 'multiscale'"),
        (dict(mottle="none", mottle_strength=0.3), "mottle_strength given with mottle='none'"),
        (dict(mottle="scorched", mottle_strength=-0.1), "mottle_strength must be >= 0"),
        (dict(noise=-0.1), "noise must be >= 0"),
        (dict(noise=Emccd(photons_peak=0)), "photons_peak must be > 0"),
        (dict(noise=Emccd(em_gain=0.5)), "em_gain must be >= 1"),
        (dict(noise=Emccd(read_noise_e=-1)), "read_noise_e must be >= 0"),
        (dict(noise=Emccd(cic=-0.1)), "cic must be >= 0"),
        (dict(spikes=-1), "spikes must be a non-negative int"),
        (dict(spikes=1.5), "spikes must be a non-negative int"),
        (dict(clip_level=np.nan), "clip_level must be finite"),
        (dict(clip_level=np.inf), "clip_level must be finite"),
    ],
)
def test_rejects_invalid_settings(kwargs, message):
    with pytest.raises(ValueError, match="^" + re.escape(message)):
        generate(seed=0, **kwargs)


@pytest.mark.parametrize("seed", STRIPE_FREE_SPECTRUM_TEST_SEEDS)
@pytest.mark.parametrize("mottle", ["scorched", "multiscale"])
def test_stripe_free_frame_has_no_stripe_peak(mottle, seed):
    s = generate(seed=seed, mottle=mottle, noise=0.0, modulation_depth=0.0)
    assert band_peak(s.frame).vertical_to_horizontal < 10


@pytest.mark.parametrize(("period", "angle_deg"), [(3, 10), (20, -10), (7.3, 4)])
def test_clean_stripes_put_the_spectral_peak_at_the_true_period_and_angle(period, angle_deg):
    s = generate(
        seed=SINGLE_FRAME_TEST_SEED,
        mottle="none",
        noise=0.0,
        modulation_depth=0.5,
        period=period,
        angle_deg=angle_deg,
    )
    peak = band_peak(s.frame)
    assert_matches_truth(peak.period, peak.angle_deg, s.truth)


# --- Striped Regions (ticket 05) ---------------------------------------------

# SHA-256 of generate(seed, **kwargs).frame.tobytes(), computed at BASE 87005b9
# before the regions change. They are tied to the numpy/scipy pinned in uv.lock:
# after a dependency bump re-pin them, with the reason recorded in the ticket.
_BASE_DIGESTS = {
    "default": [
        "43435527d812c8eb166efd8f17dfc05535b48aadc1bce131a32b6403617f845d",
        "cb7d6b1298b298616d9a56b9aad65fc1980022f8286c35e22d8d9c30220108b5",
        "f04735d8d970d8600c5f55861bced3652d34956408b21aac45f10ea946fb6eaa",
    ],
    "scorched": [
        "787bc74992fb80a5e241cd001c666a7db488033fa69d143b4122580ca277339b",
        "7aa1a5616a24041ec6f38602db6e51148e21c3731668a1f163f0f4361f586ed0",
        "1b76c377d0d32fb1f0552f2984cf6be38b06151e3834a10d812ecbed4b13c58b",
    ],
    "scorched-emccd": [
        "ba68054d79191fa060dc36ae6b25611a38df005cfd102e451cf1c4f8fe9fc186",
        "4ffb8c4bd42f94c2ff015baf9cdbaf04d0468137d7ea19eb1897c70ea6f23c6a",
        "5b8bc7758fd8cac39d558434fd3dec43a118bce3d47bd96a97e328890dafc3d8",
    ],
}
_DIGEST_KWARGS = {
    "default": {},
    "scorched": {"mottle": "scorched"},
    "scorched-emccd": {"mottle": "scorched", "noise": Emccd()},
}


@pytest.mark.parametrize("kind", list(_BASE_DIGESTS))
def test_default_frames_are_unchanged_by_regions(kind):
    """Full-frame frames stay bit-identical to BASE; regions=() equals m = 0."""
    for seed, digest in zip(DIGEST_TEST_SEEDS, _BASE_DIGESTS[kind], strict=True):
        frame = generate(seed=seed, **_DIGEST_KWARGS[kind]).frame
        assert hashlib.sha256(frame.tobytes()).hexdigest() == digest
        no_regions = generate(seed=seed, regions=(), **_DIGEST_KWARGS[kind])
        flat = generate(seed=seed, modulation_depth=0.0, **_DIGEST_KWARGS[kind])
        assert np.array_equal(no_regions.frame, flat.frame)


def _region(**overrides):
    base = dict(
        center=(64.0, 80.0),
        semi_axes=(30.0, 45.0),
        rotation_deg=0.0,
        edge_px=6.0,
        period=8.0,
        angle_deg=0.0,
        modulation_depth=0.5,
    )
    base.update(overrides)
    return StripedRegion(**base)


def test_regions_have_soft_edged_elliptical_masks():
    a, b, edge = 30.0, 45.0, 6.0
    s = generate(
        seed=REGION_GENERATOR_TEST_SEED,
        shape=(128, 160),
        regions=[_region(semi_axes=(a, b), edge_px=edge)],
        noise=0.0,
    )
    (truth,) = s.truth.regions
    mask = truth.mask
    assert mask.shape == (128, 160)
    assert mask[64, 80] == pytest.approx(1.0, abs=MASK_SATURATION_TOL)
    assert mask[0, 0] < MASK_SATURATION_TOL
    # A ray along the minor axis (rows), downward from the centre.
    ray = mask[64:, 80]
    assert np.all(np.diff(ray) <= 0)
    # The 0.5 contour is at the ellipse.
    crossing = np.interp(0.5, ray[::-1], np.arange(len(ray))[::-1])
    assert abs(crossing - a) <= MASK_CONTOUR_TOL_PX
    # The 0.9 -> 0.1 band is edge_px wide along the minor axis.
    r90 = np.interp(0.9, ray[::-1], np.arange(len(ray))[::-1])
    r10 = np.interp(0.1, ray[::-1], np.arange(len(ray))[::-1])
    assert abs((r10 - r90) - edge) <= MASK_EDGE_WIDTH_TOL_PX
    assert truth_pixels(truth).sum() == pytest.approx(np.pi * a * b, rel=MASK_AREA_REL_TOL)


def test_each_region_has_its_own_period_and_angle():
    left = _region(center=(128.0, 128.0), semi_axes=(90.0, 90.0), period=5.0, angle_deg=4.0)
    right = _region(center=(128.0, 384.0), semi_axes=(90.0, 90.0), period=12.0, angle_deg=-6.0)
    common = dict(seed=REGION_GENERATOR_TEST_SEED, shape=(256, 512), mottle="none", noise=0.0)
    s = generate(**common, regions=[left, right])
    for region, cols in zip(s.truth.regions, (slice(64, 192), slice(320, 448)), strict=True):
        peak = band_peak(s.frame[64:192, cols])
        assert_matches_truth(peak.period, peak.angle_deg, region)
    plain = generate(**common, regions=())
    far = (s.truth.regions[0].mask < MASK_TAIL) & (s.truth.regions[1].mask < MASK_TAIL)
    assert far.any()
    # tanh never reaches 0, so equal up to the mask's tail.
    assert np.allclose(s.clean[far], plain.clean[far], rtol=OUTSIDE_REGIONS_RTOL, atol=0)


def test_ground_truth_lists_regions():
    default = generate(seed=REGION_GENERATOR_TEST_SEED, period=7.0, modulation_depth=0.4)
    (only,) = default.truth.regions
    assert np.array_equal(only.mask, np.ones((256, 256)))
    assert (only.period, only.angle_deg, only.modulation_depth) == (7.0, 0.0, 0.4)
    assert default.truth.period == 7.0
    two = generate(
        seed=REGION_GENERATOR_TEST_SEED,
        shape=(128, 320),
        regions=[_region(center=(64.0, 80.0)), _region(center=(64.0, 240.0), period=12.0)],
    )
    assert [r.period for r in two.truth.regions] == [8.0, 12.0]
    with pytest.raises(ValueError, match="exactly one region"):
        _ = two.truth.period


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            dict(regions=[_region()], period=5.0),
            "period, angle_deg and modulation_depth go in each StripedRegion",
        ),
        (dict(regions=[_region()], modulation_depth=0.5), "period, angle_deg and modulation_depth"),
        (dict(regions=[_region(semi_axes=(0.0, 10.0))]), "semi_axes must be > 0"),
        (dict(regions=[_region(edge_px=0.0)]), "edge_px must be > 0"),
        (dict(regions=[_region(period=0.0)]), "period must be > 0"),
        (dict(regions=[_region(modulation_depth=1.5)]), "modulation_depth must be in [0, 1]"),
        (
            dict(regions=[_region(modulation_depth=0.6), _region(modulation_depth=0.6)]),
            "regions overlap with a summed modulation depth above 1",
        ),
    ],
)
def test_rejects_invalid_regions(kwargs, message):
    with pytest.raises(ValueError, match="^" + re.escape(message)):
        generate(seed=REGION_GENERATOR_TEST_SEED, shape=(128, 160), **kwargs)


# --- Spikes and Clipped Pixels (ticket 06) -----------------------------------


_TYPICAL = dict(modulation_depth=0.5, mottle="scorched", noise=Emccd())


def _typical(seed, **kwargs):
    """256x256, scorched Mottle, EMCCD at 100 photons, m 0.5, CASES[seed % 10]."""
    return case_frame(seed, **_TYPICAL, **kwargs)


@pytest.mark.parametrize("kind", list(_BASE_DIGESTS))
def test_spike_free_unclipped_frames_are_unchanged(kind):
    """spikes=0, clip_level=None is the default call, bit for bit, with empty masks."""
    for seed in DIGEST_TEST_SEEDS:
        default = generate(seed=seed, **_DIGEST_KWARGS[kind])
        explicit = generate(seed=seed, spikes=0, clip_level=None, **_DIGEST_KWARGS[kind])
        assert np.array_equal(default.frame, explicit.frame)
        assert np.array_equal(default.clean, explicit.clean)
        for truth in (default.truth, explicit.truth):
            assert truth.spike_mask.shape == truth.clipped_mask.shape == default.frame.shape
            assert truth.spike_pixels == truth.clipped_pixels == 0


def test_spikes_add_bright_streaks_and_are_in_the_truth():
    seed = SPIKE_GENERATOR_TEST_SEED
    free = _typical(seed)
    spiked = _typical(seed, spikes=SPIKE_TEST_COUNT)
    mask = spiked.truth.spike_mask
    assert mask.dtype == bool
    assert np.array_equal(spiked.frame[~mask], free.frame[~mask])
    assert np.array_equal(spiked.clean, free.clean)
    excess = (spiked.frame - free.frame)[mask]
    assert excess.min() >= synthetic._SPIKE_BRIGHTNESS[0] * spiked.clean.max()
    n = spiked.truth.spike_pixels
    assert n == mask.sum()
    assert SPIKE_TEST_COUNT <= n <= synthetic._SPIKE_MAX_LENGTH * SPIKE_TEST_COUNT
    _, components = ndimage.label(mask, structure=np.ones((3, 3)))
    assert components <= SPIKE_TEST_COUNT
    assert spiked.truth.clipped_pixels == 0
    assert not spiked.truth.clipped_mask.any()


def test_streaks_cover_their_length(monkeypatch):
    """A streak inside the frame covers exactly as many distinct pixels as the
    length the generator drew for it, in one straight 8-connected run."""
    drawn = []

    def spy(rng, shape, count, top):
        replay = copy.deepcopy(rng)  # draw order D2: start rows, start columns, lengths
        replay.integers(0, shape[0], size=count)
        replay.integers(0, shape[1], size=count)
        drawn.append(replay.integers(1, synthetic._SPIKE_MAX_LENGTH + 1, size=count))
        return original(rng, shape, count, top)

    original = synthetic._spikes
    monkeypatch.setattr(synthetic, "_spikes", spy)
    lengths = []
    for seed in STREAK_TEST_SEEDS:
        s = generate(seed=seed, shape=(64, 64), modulation_depth=0.0, noise=0.0, spikes=1)
        free = generate(seed=seed, shape=(64, 64), modulation_depth=0.0, noise=0.0)
        (length,) = drawn.pop()
        hit = s.frame > free.frame
        assert np.array_equal(hit, s.truth.spike_mask)
        rows, cols = np.nonzero(hit)
        if rows.min() > 0 and cols.min() > 0 and rows.max() < 63 and cols.max() < 63:
            assert hit.sum() == length
            # One straight 8-connected run: one step per pixel along the longer extent.
            assert max(np.ptp(rows), np.ptp(cols)) + 1 == length
        else:
            assert 1 <= hit.sum() <= length
        lengths.append(int(length))
    assert len(set(lengths)) > 1


class _Draws:
    """Stands in for the RNG of one Spike event: start (32, 32), the longest
    length, the given direction and brightness 1 (x top)."""

    def __init__(self, direction):
        n = synthetic._SPIKE_MAX_LENGTH
        self._draws = iter([[32], [32], [n], [direction], np.ones((1, n))])

    def integers(self, _low, _high, size):
        draw = np.asarray(next(self._draws))
        assert draw.shape == np.shape(np.empty(size))
        return draw

    uniform = integers


@pytest.mark.parametrize("direction_deg", [0, 30, 42, 45, 48, 60, 90, 132, 135, 138, 179])
def test_streaks_cover_their_length_in_every_direction(direction_deg):
    """Hand-built draws: a streak of _SPIKE_MAX_LENGTH covers that many distinct pixels
    in every direction, near 45 and 135 degrees too (rounding k x (cos, sin) hits
    one pixel twice there, N1)."""
    n = synthetic._SPIKE_MAX_LENGTH
    added = synthetic._spikes(_Draws(np.deg2rad(direction_deg)), (64, 64), 1, 1.0)
    rows, cols = np.nonzero(added)
    assert len(rows) == n
    assert np.all(added[rows, cols] == 1.0)
    assert max(np.ptp(rows), np.ptp(cols)) + 1 == n


def test_clip_level_saturates_the_frame_and_is_in_the_truth():
    seed = SPIKE_GENERATOR_TEST_SEED
    unclipped = _typical(seed)
    clipped, level = clipped_at(CLIP_LEVEL_FRACTION, _typical, seed=seed)
    assert clipped.frame.max() == level
    assert np.array_equal(clipped.truth.clipped_mask, unclipped.frame >= level)
    rest = ~clipped.truth.clipped_mask
    assert np.array_equal(clipped.frame[rest], unclipped.frame[rest])
    assert np.all(clipped.frame[~rest] == level)
    assert clipped.truth.clipped_pixels > 0
    assert clipped.truth.spike_pixels == 0
    assert np.array_equal(clipped.clean, unclipped.clean)


def test_spike_and_clipped_masks_are_disjoint():
    """Every hit pixel is in spike_mask, clipped or not; clipped_mask holds the
    spike-free frame's pixels at or above the level that no spike hit."""
    seed = SPIKE_GENERATOR_TEST_SEED
    free = _typical(seed)
    level = SATURATING_CLIP_FACTOR * free.clean.max()
    spiked = _typical(seed, spikes=SPIKE_TEST_COUNT)
    both = _typical(seed, spikes=SPIKE_TEST_COUNT, clip_level=level)
    spikes, clipped = both.truth.spike_mask, both.truth.clipped_mask
    assert np.array_equal(spikes, spiked.truth.spike_mask)
    assert not (spikes & clipped).any()
    assert np.array_equal(clipped, (free.frame >= level) & ~spikes)
    assert np.array_equal(both.frame, np.minimum(spiked.frame, level))
    assert (both.frame[spikes] == level).any()
    assert (both.frame[spikes] < level).any()


# --- Phase Breaks (ticket 09) ---------------------------------------------------

_BREAK_POINT = (127.5, 127.5)  # half-integer: no pixel centre lies on a line through it


def _wrap(a):
    """``a`` wrapped to (-pi, pi]."""
    return -((-a + math.pi) % (2 * math.pi) - math.pi)


def _canonical(angle_deg, jump):
    """The plan's canonical line (2.1): angle in (-90, 90], jump with its sign, wrapped."""
    a = (angle_deg + 180.0) % 360.0 - 180.0
    if a <= -90.0:
        a, jump = a + 180.0, -jump
    elif a > 90.0:
        a, jump = a - 180.0, -jump
    return a, _wrap(jump)


def _side(shape, point, angle_deg):
    """The strict positive side of the directed line: d_x (y - y0) - d_y (x - x0) > 0."""
    y, x = np.mgrid[0 : shape[0], 0 : shape[1]].astype(float)
    t = math.radians(angle_deg)
    return math.cos(t) * (y - point[0]) - math.sin(t) * (x - point[1]) > 0


def _broken(angle_deg, jump, **kwargs):
    return generate(
        seed=PHASE_BREAK_TEST_SEEDS[0],
        noise=0.0,
        phase_breaks=[PhaseBreakLine(_BREAK_POINT, angle_deg, jump)],
        **kwargs,
    )


@pytest.mark.parametrize("jump", [math.pi / 2, math.pi, 2.0])
@pytest.mark.parametrize("angle", [0, 10, 45, 90, -60, 135])
def test_phase_break_shifts_every_stripe_on_one_side(angle, jump):
    """AC 1: the canonical jump is added to the stripe phase on the canonical positive side
    (strict), and nothing else changes."""
    s = _broken(angle, jump)
    (truth,) = s.truth.phase_breaks
    canonical_angle, canonical_jump = _canonical(angle, jump)
    assert truth.point == _BREAK_POINT
    assert truth.line_angle_deg == pytest.approx(canonical_angle, abs=BREAK_PHASE_ATOL)
    assert truth.jump_rad == pytest.approx(canonical_jump, abs=BREAK_PHASE_ATOL)
    assert np.array_equal(truth.shifted, _side(s.frame.shape, _BREAK_POINT, canonical_angle))
    assert truth.shifted.any()
    assert not truth.shifted.all()
    free = generate(seed=PHASE_BREAK_TEST_SEEDS[0], noise=0.0)
    off = ~truth.shifted
    assert np.array_equal(s.clean[off], free.clean[off])
    env = generate(seed=PHASE_BREAK_TEST_SEEDS[0], noise=0.0, modulation_depth=0.0).clean
    quarter = generate(
        seed=PHASE_BREAK_TEST_SEEDS[0],
        noise=0.0,
        phase_breaks=[PhaseBreakLine(_BREAK_POINT, canonical_angle, math.pi / 2)],
    ).clean
    on = truth.shifted
    c_j, c_0, c_q = (c[on] / env[on] - 1 for c in (s.clean, free.clean, quarter))
    expected = c_0 * math.cos(canonical_jump) + c_q * math.sin(canonical_jump)
    assert np.max(np.abs(c_j - expected)) <= BREAK_PHASE_ATOL


_DIGEST_BREAK = PhaseBreakLine(point=(100.5, 60.5), line_angle_deg=20.0, jump_rad=math.pi)


@pytest.mark.parametrize("kind", ["default", "scorched", "scorched-emccd"])
def test_no_phase_breaks_leaves_frames_unchanged(kind):
    """B1: phase_breaks=() is the BASE frame bit for bit (every noise kind); with one break,
    Gaussian noise, no spikes and no clip, frame and clean are bit-identical off ``shifted``.
    No pixel claim is made for EMCCD noise with a break."""
    for seed, digest in zip(DIGEST_TEST_SEEDS, _BASE_DIGESTS[kind], strict=True):
        s = generate(seed=seed, phase_breaks=(), **_DIGEST_KWARGS[kind])
        assert hashlib.sha256(s.frame.tobytes()).hexdigest() == digest
        assert s.truth.phase_breaks == ()
    if kind == "scorched-emccd":
        return
    for seed in DIGEST_TEST_SEEDS:
        free = generate(seed=seed, **_DIGEST_KWARGS[kind])
        broken = generate(seed=seed, phase_breaks=[_DIGEST_BREAK], **_DIGEST_KWARGS[kind])
        off = ~broken.truth.phase_breaks[0].shifted
        assert np.array_equal(broken.frame[off], free.frame[off])
        assert np.array_equal(broken.clean[off], free.clean[off])
        assert not np.array_equal(broken.frame, free.frame)


@pytest.mark.parametrize("a", [100, 270, -90])
def test_phase_break_truth_is_canonical(a):
    """A line given outside (-90, 90] is flipped, its jump negated and wrapped; (a, j) and
    (a - 180, -j) are one line, so they give the same truth and the same frame."""
    jump = 2.5
    s = _broken(a, jump)
    flipped = _broken(a - 180, -jump)
    (truth,) = s.truth.phase_breaks
    (other,) = flipped.truth.phase_breaks
    want_angle, want_jump = _canonical(a, jump)
    assert -90 < truth.line_angle_deg <= 90
    assert truth.line_angle_deg == pytest.approx(want_angle, abs=BREAK_PHASE_ATOL)
    assert truth.jump_rad == pytest.approx(want_jump, abs=BREAK_PHASE_ATOL)
    assert truth.jump_rad == pytest.approx(_wrap(-jump), abs=BREAK_PHASE_ATOL)
    assert np.array_equal(truth.shifted, _side(s.frame.shape, _BREAK_POINT, want_angle))
    assert other.line_angle_deg == truth.line_angle_deg
    assert other.jump_rad == pytest.approx(truth.jump_rad, abs=BREAK_PHASE_ATOL)
    assert np.array_equal(other.shifted, truth.shifted)
    assert np.allclose(flipped.clean, s.clean, rtol=0, atol=BREAK_PHASE_ATOL)


def test_phase_breaks_apply_inside_regions_and_over_the_whole_frame():
    region = StripedRegion(
        center=(127.5, 127.5),
        semi_axes=(60.0, 80.0),
        rotation_deg=0.0,
        edge_px=6.0,
        period=8.0,
        angle_deg=0.0,
        modulation_depth=0.5,
    )
    line = PhaseBreakLine(_BREAK_POINT, 0.0, math.pi)
    for kwargs in (dict(regions=[region]), dict()):
        free = generate(seed=PHASE_BREAK_TEST_SEEDS[0], noise=0.0, **kwargs)
        broken = generate(seed=PHASE_BREAK_TEST_SEEDS[0], noise=0.0, phase_breaks=[line], **kwargs)
        shifted = broken.truth.phase_breaks[0].shifted
        lit = free.truth.regions[0].mask >= 0.5
        # A jump of pi negates the stripe term wherever stripes are drawn and shifted.
        env = generate(
            seed=PHASE_BREAK_TEST_SEEDS[0],
            noise=0.0,
            regions=() if kwargs else None,
            **({} if kwargs else dict(modulation_depth=0.0)),
        ).clean
        at = shifted & lit
        assert at.sum() > 1000
        assert np.allclose(
            broken.clean[at] / env[at] - 1, 1 - free.clean[at] / env[at], atol=BREAK_PHASE_ATOL
        )
        assert np.array_equal(broken.clean[~shifted], free.clean[~shifted])


def test_pixels_on_a_phase_break_line_are_not_shifted():
    s = generate(
        seed=PHASE_BREAK_TEST_SEEDS[0],
        noise=0.0,
        phase_breaks=[PhaseBreakLine((100.0, 60.0), 0.0, math.pi)],
    )
    shifted = s.truth.phase_breaks[0].shifted
    assert not shifted[:101].any()
    assert shifted[101:].all()


def test_zero_jump_is_a_no_op():
    s = _broken(30.0, 0.0)
    assert np.array_equal(s.clean, generate(seed=PHASE_BREAK_TEST_SEEDS[0], noise=0.0).clean)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (PhaseBreakLine((np.nan, 1.0), 0.0, 1.0), "phase break point must be"),
        (PhaseBreakLine((1.0, 2.0, 3.0), 0.0, 1.0), "phase break point must be"),
        (PhaseBreakLine((1.0, 2.0), np.inf, 1.0), "phase break line_angle_deg must be finite"),
        (PhaseBreakLine((1.0, 2.0), 0.0, np.nan), "phase break jump_rad must be finite"),
    ],
)
def test_rejects_invalid_phase_breaks(line, message):
    with pytest.raises(ValueError, match="^" + re.escape(message)):
        generate(seed=PHASE_BREAK_TEST_SEEDS[0], phase_breaks=[line])


def test_positive_jump_moves_stripes_toward_column_zero():
    """C1, noise-free: a jump of +pi/2 below a 10-deg line moves the stripes there toward
    column 0 by a quarter Period (5 px at P 20)."""
    period = 20
    common = dict(seed=PHASE_BREAK_TEST_SEEDS[0], noise=0.0, period=period, angle_deg=0.0)
    free = generate(**common)
    broken = generate(**common, phase_breaks=[PhaseBreakLine(_BREAK_POINT, 10.0, math.pi / 2)])
    env = generate(seed=PHASE_BREAK_TEST_SEEDS[0], noise=0.0, modulation_depth=0.0).clean
    row = 220
    assert broken.truth.phase_breaks[0].shifted[row].all()
    b = broken.clean[row] / env[row] - 1
    f = free.clean[row] / env[row] - 1
    lags = range(-period // 2, period // 2)
    inner = slice(period, len(b) - period)
    # b(x) = f(x - lag) at the best lag.
    score = {lag: float(np.dot(b[inner], np.roll(f, lag)[inner])) for lag in lags}
    assert max(score, key=lambda lag: score[lag]) == -period // 4
