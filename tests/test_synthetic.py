import re

import numpy as np
import pytest

from denoisifier.synthetic import Emccd, generate
from protected import (
    SAME_SEED_TEST_SEEDS,
    SINGLE_FRAME_ALT_TEST_SEEDS,
    SINGLE_FRAME_TEST_SEED,
    STRIPE_FREE_SPECTRUM_TEST_SEEDS,
)
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
    seed = SINGLE_FRAME_ALT_TEST_SEEDS[2]
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
