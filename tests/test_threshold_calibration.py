"""The synthetic calibration driver (ticket 07, tests/threshold_calibration.py): fast tests.

The slow modules (test_slow_calibration.py, test_held_out_calibration.py) build the full
plans and assert on the driver's result dicts through the driver's ``*_problems``
functions; the tiny-plan test here runs the same code on test seeds at a small shape.
"""

import importlib
import importlib.resources
import json
import math

import numpy as np
from scipy.stats import betabinom

import feasibility
import seed_guard
import threshold_calibration as tc
from denoisifier import analyse
from denoisifier._calibration import false_alarm_tolerance, threshold_rank
from denoisifier.calibration import (
    DEFAULT_FALSE_ALARM_RATE,
    Calibration,
    stored_calibration,
    stripe_free_score,
)
from denoisifier.synthetic import generate
from protected import (
    CALIBRATED_FREE_SEEDS,
    CALIBRATED_STRIPED_SEEDS,
    CALIBRATION_MAX_FALSE_RED,
    CALIBRATION_SHAPE,
    CALIBRATION_TIMEOUT_S,
    CALIBRATION_TINY_FREE_TEST_SEEDS,
    CALIBRATION_TINY_STRIPED_TEST_SEEDS,
    CALIBRATION_TINY_TEST_SEEDS,
    CALIBRATION_TOLERANCE_LEVEL,
    HELD_OUT_OPTION_FRAMES,
    MIN_DETECTION_RATE,
    OTHER_FALSE_ALARM_RATE,
    PACKAGE_CALIBRATION_DIGEST,
    PACKAGE_STORED_THRESHOLD,
    PACKAGE_STORED_THRESHOLD_5PCT,
    RUN_POOL_TEST_SEEDS,
    STRIPE_FREE_CALIBRATION_SEEDS,
    WEAK_DEPTH,
)

TINY_SHAPE = (64, 128)


def test_run_pool_matches_serial_scoring():
    """The gate's pooled scoring (feasibility.score_batch, two spawn workers) gives the
    per-seed scores of serial analyse on the same frames, in the seeds' order (plan C2)."""
    seeds = list(RUN_POOL_TEST_SEEDS)[::-1]  # not ascending: order must follow the input
    shape = TINY_SHAPE
    pooled = feasibility.score_batch(seeds, WEAK_DEPTH, shape, workers=2)
    serial = []
    for seed in seeds:
        case = feasibility.CASES[seed % len(feasibility.CASES)]
        frame = generate(
            seed=seed,
            shape=shape,
            period=case.period,
            angle_deg=case.angle_deg,
            modulation_depth=WEAK_DEPTH,
            mottle="scorched",
            noise=feasibility.NOISE,
        ).frame
        serial.append(analyse(frame, threshold=np.inf).score)
    assert pooled.tolist() == serial
    assert any(s > 0 for s in serial), "every frame scored 0: the comparison has no teeth"


def _tiny(workers):
    return tc.calibration_from_seeds(CALIBRATION_TINY_TEST_SEEDS, TINY_SHAPE, workers=workers)


def test_calibrate_synthetic_tiny_plan_is_repeatable():
    one = _tiny(1)
    two = _tiny(2)
    assert one == two  # run_info (wall clock, workers) is not compared
    assert one.ids == tuple(f"seed:{s}" for s in CALIBRATION_TINY_TEST_SEEDS)
    assert one.shape == TINY_SHAPE
    assert one.settings == json.loads(json.dumps(tc.settings(TINY_SHAPE)))
    serial = [
        stripe_free_score(tc.synthetic(seed, TINY_SHAPE, 0.0).frame)
        for seed in CALIBRATION_TINY_TEST_SEEDS
    ]
    assert one.scores == tuple(serial)
    # n = 4: rate 0.2 -> k = 1 (the largest); rate 0.4 -> k = 2.
    ranked = sorted(serial, reverse=True)
    assert one.threshold(0.2) == ranked[0]
    assert one.threshold(0.4) == ranked[1]
    assert one.run_info["workers"] == 1
    assert one.run_info["wall_clock_s"] > 0


def test_calibrate_synthetic_runs_the_core_on_the_calibration_set_inside_its_block(
    monkeypatch,
):
    """W2: the Calibration Set is scored only inside seed_guard.calibrating(...)."""
    calls = []

    def core(seeds, shape, workers=None):
        calls.append((seeds, shape, workers, seed_guard.worker_allowance()))
        return "calibration"

    monkeypatch.setattr(tc, "calibration_from_seeds", core)
    assert seed_guard.installed()
    assert STRIPE_FREE_CALIBRATION_SEEDS not in (seed_guard.worker_allowance() or ())
    assert tc.calibrate_synthetic(3) == "calibration"
    ((seeds, shape, workers, allowed),) = calls
    assert (seeds, shape, workers) == (STRIPE_FREE_CALIBRATION_SEEDS, CALIBRATION_SHAPE, 3)
    assert allowed is not None
    assert STRIPE_FREE_CALIBRATION_SEEDS in allowed
    assert STRIPE_FREE_CALIBRATION_SEEDS not in (seed_guard.worker_allowance() or ())


def test_calibration_frames_are_stripe_free_spiked_and_unclipped():
    s = tc.synthetic(CALIBRATION_TINY_TEST_SEEDS[0], TINY_SHAPE, 0.0)
    assert s.truth.spike_pixels > 0
    assert s.truth.clipped_pixels == 0
    settings = tc.settings(TINY_SHAPE)
    assert settings["modulation_depth"] == 0.0
    assert settings["spikes"] == 30
    assert settings["mottle"] == "scorched"
    assert settings["source"] == "synthetic"


def _tiny_stored():
    """A tiny stand-in for the stored calibration, with enough scores (199) for the
    default 1%: k = 2 -> 2nd largest; 5%: k = 10."""
    scores = np.linspace(0.0, 60.0, 199)
    return Calibration.from_scores([f"f{i}" for i in range(199)], scores, TINY_SHAPE)


TINY_HELD_OUT = tc.HeldOutPlan(
    shape=TINY_SHAPE,
    free=CALIBRATION_TINY_FREE_TEST_SEEDS,
    striped=CALIBRATION_TINY_STRIPED_TEST_SEEDS,
    depth=WEAK_DEPTH,
    other_rate=OTHER_FALSE_ALARM_RATE,
    option_frames=2,
    level=CALIBRATION_TOLERANCE_LEVEL,
    min_detection_rate=0.9,
)


def test_slow_calibration_checks_run_on_a_tiny_plan(tmp_path):
    # Reproduction (AC 7): a fresh run against itself has no problems.
    stored = _tiny(2)
    t1, t5 = stored.threshold(0.25), stored.threshold(0.5)
    result = tc.reproduction_check(stored, lambda: _tiny(2), rates=(0.25, 0.5))
    assert result["n"] == len(CALIBRATION_TINY_TEST_SEEDS)
    assert result["n_differing"] == 0
    assert tc.reproduction_problems(result, t1, t5) == []
    assert result["wall_clock_s"] > 0
    # ... and against a stored file with one changed score, it names the seed.
    scores = list(stored.scores)
    scores[1] += 10.0
    changed = Calibration.from_scores(stored.ids, scores, stored.shape, settings=stored.settings)
    bad = tc.reproduction_check(changed, lambda: _tiny(1), rates=(0.25, 0.5))
    problems = tc.reproduction_problems(bad, t1, t5)
    assert bad["n_differing"] == 1
    assert bad["differing"] == [stored.ids[1]]
    text = "\n".join(problems)
    assert f"1 of {len(scores)} per-seed scores differ" in text
    assert stored.ids[1] in text
    assert "largest relative difference" in text
    assert "never edit this check" in text.lower()
    other_settings = Calibration.from_scores(
        stored.ids, stored.scores, stored.shape, settings={"x": 1}
    )
    other = tc.reproduction_check(other_settings, lambda: _tiny(1), rates=(0.25, 0.5))
    assert any("settings" in p for p in tc.reproduction_problems(other, t1, t5))
    assert any("threshold" in p for p in tc.reproduction_problems(result, t1 + 1, t5))

    # Held out (AC 2a, 2b, 3), against a tiny calibration passed through calibration=.
    cal = _tiny_stored()
    out = tmp_path / "held-out.json"
    held = tc.held_out_check(TINY_HELD_OUT, calibration=cal, workers=2, out=out)
    free, striped = held["free"], held["striped"]
    assert free["n"] == len(CALIBRATION_TINY_FREE_TEST_SEEDS)
    assert free["thresholds_seen"] == [cal.threshold(DEFAULT_FALSE_ALARM_RATE)]
    assert free["tolerance"] == list(
        false_alarm_tolerance(199, free["n"], DEFAULT_FALSE_ALARM_RATE, CALIBRATION_TOLERANCE_LEVEL)
    )
    assert 0 <= free["false_alarms"] <= free["n"]
    assert len(free["posterior_95"]) == 2
    assert free["other"]["threshold"] == cal.threshold(OTHER_FALSE_ALARM_RATE)
    assert len(free["option_frames"]) == 2
    assert free["option_mismatches"] == []
    assert striped["n"] == len(CALIBRATION_TINY_STRIPED_TEST_SEEDS)
    assert sum(c["n"] for c in striped["cases"]) == striped["n"]
    assert striped["min_detected"] == 9
    assert json.loads(out.read_text()) == json.loads(json.dumps(held))
    t_default = cal.threshold(DEFAULT_FALSE_ALARM_RATE)
    t_other = cal.threshold(OTHER_FALSE_ALARM_RATE)
    assert isinstance(tc.false_alarm_problems(free, t_default), list)
    assert any("threshold" in p for p in tc.false_alarm_problems(free, t_default + 1))
    too_many = {**free, "false_alarms": free["tolerance"][1] + 1}
    assert any("False Alarms" in p for p in tc.false_alarm_problems(too_many, t_default))
    assert isinstance(tc.other_rate_problems(free, t_other), list)
    mismatched = {**free, "option_mismatches": [CALIBRATION_TINY_FREE_TEST_SEEDS[0]]}
    assert any("option" in p for p in tc.other_rate_problems(mismatched, t_other))
    missed = {**striped, "detected": 0}
    (message,) = tc.detection_problems(missed)
    assert f"0/{striped['n']} detected" in message
    assert "px/" in message  # the per-case breakdown


def test_evaluate_on_clipped_frames_clips_at_a_fraction_of_the_clean_max():
    seed = CALIBRATION_TINY_FREE_TEST_SEEDS[0]
    (row,) = tc.evaluate([seed], shape=TINY_SHAPE, depth=0.0, clip_fraction=0.4, workers=1)
    clean = tc.synthetic(seed, TINY_SHAPE, 0.0)
    clipped = tc.synthetic(seed, TINY_SHAPE, 0.0, clip_level=0.4 * float(clean.clean.max()))
    assert clipped.truth.clipped_pixels > 0
    report = analyse(clipped.frame)
    assert (row["score"], row["striped"], row["threshold"]) == (
        report.score,
        report.striped,
        report.threshold,
    )


def test_statistical_calibration_tests_are_slow():
    """AC 6: every test of both calibration modules is slow; the held-out ones carry
    held_out (so make check-slow leaves them out), the reproduction does not; each has
    the W6 timeout."""
    found = {}
    for name in ("test_slow_calibration", "test_held_out_calibration"):
        module = importlib.import_module(name)
        module_marks = [m.mark if hasattr(m, "mark") else m for m in module.pytestmark]
        for attr, fn in vars(module).items():
            if attr.startswith("test_") and callable(fn):
                marks = module_marks + list(getattr(fn, "pytestmark", []))
                found[f"{name}::{attr}"] = {m.name: m for m in marks}
    assert found
    for test, marks in found.items():
        assert "slow" in marks, test
        assert marks["timeout"].args == (CALIBRATION_TIMEOUT_S,), test
        assert ("held_out" in marks) == test.startswith("test_held_out_calibration"), test
    assert "test_slow_calibration::test_calibration_reproduces_the_stored_thresholds" in found


def _false_red(n_cal, n_free, rate, level):
    lo, hi = false_alarm_tolerance(n_cal, n_free, rate, level)
    k = math.floor(rate * (n_cal + 1) + 1e-9)
    count = betabinom(n_free, k, n_cal + 1 - k)
    return 1.0 - (count.cdf(hi) - count.cdf(lo - 1)), (lo, hi)


def test_calibration_plan_meets_its_false_red_budget():
    """AC 2a and 2b together are red with an unchanged, correctly calibrated detector at
    most CALIBRATION_MAX_FALSE_RED of the time (Bonferroni; plan section 5). AC 3 is not in
    this budget (plan C1)."""
    n, big_n = len(STRIPE_FREE_CALIBRATION_SEEDS), len(CALIBRATED_FREE_SEEDS)
    p1, tol1 = _false_red(n, big_n, DEFAULT_FALSE_ALARM_RATE, CALIBRATION_TOLERANCE_LEVEL)
    p5, tol5 = _false_red(n, big_n, OTHER_FALSE_ALARM_RATE, CALIBRATION_TOLERANCE_LEVEL)
    # Worked in plan section 5: 0-13 and 3-33 of 300; 0.19% + 0.29%.
    assert (tol1, tol5) == ((0, 13), (3, 33))
    assert p1 + p5 <= CALIBRATION_MAX_FALSE_RED
    assert tol5[0] >= 1


def test_the_full_plans_are_the_protected_ones():
    plan = tc.HELD_OUT
    assert plan.shape == CALIBRATION_SHAPE == (400, 1600)
    assert plan.free is CALIBRATED_FREE_SEEDS
    assert plan.striped is CALIBRATED_STRIPED_SEEDS
    assert plan.depth == WEAK_DEPTH
    assert plan.other_rate == OTHER_FALSE_ALARM_RATE
    assert plan.option_frames == HELD_OUT_OPTION_FRAMES
    assert plan.level == CALIBRATION_TOLERANCE_LEVEL
    assert plan.min_detection_rate == MIN_DETECTION_RATE


# --- The stored calibration (plan 2.2, W4(b)): make check, no analysis ------------------


def test_stored_calibration_ships_with_the_package():
    resource = importlib.resources.files("denoisifier").joinpath("stripe_free_calibration.json")
    assert resource.is_file()
    assert Calibration.from_json(resource.read_text(encoding="utf-8")) == stored_calibration()


def test_stored_calibration_is_the_protected_one():
    """Any edit to the shipped file forces a lockfile edit (an approval): its thresholds,
    ids, shape, settings and the digest of its whole payload are protected numbers."""
    stored = stored_calibration()
    assert stored.threshold(DEFAULT_FALSE_ALARM_RATE) == PACKAGE_STORED_THRESHOLD
    assert stored.threshold(OTHER_FALSE_ALARM_RATE) == PACKAGE_STORED_THRESHOLD_5PCT
    assert stored.ids == tuple(f"seed:{s}" for s in STRIPE_FREE_CALIBRATION_SEEDS)
    assert stored.shape == CALIBRATION_SHAPE
    assert stored.settings == json.loads(json.dumps(tc.settings(CALIBRATION_SHAPE)))
    assert int(stored.digest(), 16) == PACKAGE_CALIBRATION_DIGEST


def test_stored_threshold_ranks_are_untied_and_positive():
    """At k(1%) = 3 and k(5%) = 15 the k-th largest stored score is strictly above the
    (k+1)-th and above 0 (the 0.0 atom is far from both ranks)."""
    stored = stored_calibration()
    ranked = sorted(stored.scores, reverse=True)
    n = len(ranked)
    for rate, want_k in ((DEFAULT_FALSE_ALARM_RATE, 3), (OTHER_FALSE_ALARM_RATE, 15)):
        k = threshold_rank(n, rate)
        assert k == want_k
        assert ranked[k - 1] > ranked[k], f"rank {k} is tied"
        assert ranked[k - 1] > 0
        assert stored.threshold(rate) == ranked[k - 1]
