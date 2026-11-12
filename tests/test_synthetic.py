import hashlib
import re

import numpy as np
import pytest

from denoisifier.synthetic import Emccd, StripedRegion, generate
from protected import (
    DIGEST_TEST_SEEDS,
    MASK_AREA_REL_TOL,
    MASK_CONTOUR_TOL_PX,
    MASK_EDGE_WIDTH_TOL_PX,
    MASK_SATURATION_TOL,
    MASK_TAIL,
    MOTTLE_NONE_TEST_SEED,
    OUTSIDE_REGIONS_RTOL,
    REGION_GENERATOR_TEST_SEED,
    SAME_SEED_TEST_SEEDS,
    SINGLE_FRAME_TEST_SEED,
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
