"""Ticket 11: the break and Fork thresholds from stored per-frame evidence on break- and
Fork-free striped frames (plan `.scratch/stripe-detector/handoffs/11-plan.md`)."""

from __future__ import annotations

import importlib
import importlib.resources
import json
import math
from functools import cache

import pytest
from scipy.stats import betabinom, binom

import break_fork_calibration as bfc
import seed_guard
import threshold_calibration as tc
from breaks import ac2_line, break_region_case, compatible_pair_frame
from denoisifier import analyse, analysis
from denoisifier._calibration import threshold_rank
from denoisifier._local_phase import _BREAK_MIN_EVIDENCE, _FORK_MIN_EVIDENCE
from denoisifier.calibration import (
    DEFAULT_BREAK_FORK_FALSE_ALARM_RATE,
    _BreakForkCalibration,
    _BreakForkThresholds,
    _stored_break_fork_calibration,
    stored_calibration,
)
from forks import ac2_case
from protected import (
    BREAK_FORK_CALIBRATION_DEPTH,
    BREAK_FORK_CALIBRATION_SHAPE,
    BREAK_FORK_CASE_ALARM_FRAMES,
    BREAK_FORK_DETECTION_BREAK_FRAMES,
    BREAK_FORK_DETECTION_FORK_FRAMES,
    BREAK_FORK_DETECTION_HELD_OUT_SEEDS,
    BREAK_FORK_FALSE_ALARM_RATE,
    BREAK_FORK_FREE_CALIBRATION_SEEDS,
    BREAK_FORK_FREE_HELD_OUT_SEEDS,
    BREAK_FORK_MAX_FAKES,
    BREAK_FORK_MIN_DETECTION_RATE,
    BREAK_FORK_REPRODUCTION_PREFIX,
    BREAK_FORK_TINY_BREAK_TEST_SEEDS,
    BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS,
    BREAK_FORK_TINY_FORK_TEST_SEEDS,
    BREAK_FORK_TINY_FREE_TEST_SEEDS,
    CALIBRATION_MAX_FALSE_RED,
    CALIBRATION_SEEDS,
    CALIBRATION_TIMEOUT_S,
    FORK_TEST_SEEDS,
    PACKAGE_BREAK_FORK_BREAK_THRESHOLD,
    PACKAGE_BREAK_FORK_CALIBRATION_DIGEST,
    PACKAGE_BREAK_FORK_FORK_THRESHOLD,
    PHASE_BREAK_TEST_SEEDS,
    PROBE_SHAPE,
)


def _calibration(breaks, forks, **kwargs):
    ids = [f"seed:{i}" for i in range(len(breaks))]
    return _BreakForkCalibration.from_evidence(ids, breaks, forks, (400, 1600), **kwargs)


def test_default_break_fork_false_alarm_rate_is_five_percent():
    """About once per 20 frames (ticket 11, spec)."""
    assert DEFAULT_BREAK_FORK_FALSE_ALARM_RATE == 0.05


def test_break_fork_thresholds_are_marginal_order_statistics_with_floors():
    """r/2 for each kind: k = floor(r/2 (n + 1)) of each kind's evidence, never under its floor."""
    n = 300
    # Distinct values above both floors, largest first: 0.9, 0.899, ...
    high = [0.9 - 0.001 * i for i in range(n)]
    cal = _calibration(high, list(reversed(high)))
    # n = 300, r = 0.05: k = floor(0.025 * 301) = 7, the 7th largest.
    assert cal.thresholds(0.05) == _BreakForkThresholds(breaks=high[6], forks=high[6])
    # r = 0.2: k = floor(0.1 * 301) = 30.
    assert cal.thresholds(0.2) == _BreakForkThresholds(breaks=high[29], forks=high[29])

    # Ties at 0 (no candidate on most frames): the floors set the thresholds.
    zeros = [0.0] * n
    assert _calibration(zeros, zeros).thresholds(0.05) == _BreakForkThresholds(
        breaks=_BREAK_MIN_EVIDENCE, forks=_FORK_MIN_EVIDENCE
    )
    # One kind above its floor, the other at it.
    mixed = _calibration([0.5] * 10 + [0.0] * (n - 10), [0.2] * n)
    assert mixed.thresholds(0.05) == _BreakForkThresholds(breaks=0.5, forks=_FORK_MIN_EVIDENCE)


def test_break_fork_thresholds_smallest_valid_rate_is_two_over_n_plus_one():
    cal = _calibration([0.0] * 300, [0.0] * 300)
    cal.thresholds(2 / 301)  # k = 1
    with pytest.raises(ValueError, match=r"0\.00664"):
        cal.thresholds(0.006)
    for bad in (0.0, 1.0, -0.1, 1.5, math.nan):
        with pytest.raises(ValueError, match="between 0 and 1"):
            cal.thresholds(bad)


def test_break_fork_calibration_refuses_malformed_evidence():
    with pytest.raises(ValueError, match="finite and at least 0"):
        _calibration([0.1, math.inf], [0.0, 0.0])
    with pytest.raises(ValueError, match="finite and at least 0"):
        _calibration([0.1, -0.1], [0.0, 0.0])
    with pytest.raises(ValueError, match="1 ids for 2"):
        _calibration([0.1], [0.0, 0.0])
    with pytest.raises(ValueError, match="unique"):
        _BreakForkCalibration.from_evidence(["a", "a"], [0, 0], [0, 0], (400, 1600))


def test_break_fork_calibration_round_trips_json_and_digest():
    cal = _calibration(
        [0.0, 0.25, 0.125],
        [0.5, 0.0, 0.0],
        settings={"depth": 0.5, "shape": (400, 1600)},
        run_info={"wall_clock_s": 1.0},
    )
    doc = json.loads(cal.to_json())
    assert doc["format"] == 1
    assert doc["evidence"] == "break-fork-v1"
    assert doc["frames"][1] == {"id": "seed:1", "breaks": 0.25, "forks": 0.0}
    back = _BreakForkCalibration.from_json(cal.to_json())
    assert back == cal
    assert back.run_info == {"wall_clock_s": 1.0}
    assert back.digest() == cal.digest()

    other_run = _calibration(
        [0.0, 0.25, 0.125], [0.5, 0.0, 0.0], settings={"depth": 0.5, "shape": (400, 1600)}
    )
    assert other_run.digest() == cal.digest()
    moved = _calibration(
        [0.0, 0.25, 0.125], [0.5, 0.0, 1e-9], settings={"depth": 0.5, "shape": (400, 1600)}
    )
    assert moved.digest() != cal.digest()

    for key, value in (("format", 2), ("evidence", "break-fork-v0")):
        bad = dict(doc, **{key: value})
        with pytest.raises(ValueError, match=key):
            _BreakForkCalibration.from_json(json.dumps(bad))
    with pytest.raises(ValueError, match="malformed"):
        _BreakForkCalibration.from_json('{"format": 1, "evidence": "break-fork-v1"}')


# --- The evidence scalars against the real path (plan section 2, T7 and T8) ----------------


def _evidence_frames():
    """(name, frame) of T7: a 09 break frame, a break-free region frame, a spiked full frame at
    the calibration recipe and a compatible pair (the bridge domain)."""
    seed = PHASE_BREAK_TEST_SEEDS[0]
    line_angle, jump = ac2_line(seed)
    return [
        ("break", break_region_case(seed, jump, line_angle)[0].frame),
        ("break-free region", break_region_case(seed, None, line_angle)[0].frame),
        ("spiked full frame", tc.synthetic(seed, PROBE_SHAPE, 0.5).frame),
        ("compatible pair", compatible_pair_frame(seed).frame),
    ]


def _fork_frame():
    return ac2_case(FORK_TEST_SEEDS[0])[0].frame


@cache
def _evidence(name):
    frames = dict(_evidence_frames(), fork=_fork_frame())
    frame = frames[name]
    return frame, analysis._break_fork_evidence(frame)


EVIDENCE_NAMES = ["break", "break-free region", "spiked full frame", "compatible pair", "fork"]


def _found_breaks(frame, threshold):
    front = _front(frame)
    if front.field is None:
        return 0
    settled = analysis._with_phase_breaks(
        front.reported, front.filters, front.clipped, front.field, break_threshold=threshold
    )
    return sum(len(found) for _, found in settled)


def _found_forks(frame, threshold):
    front = _front(frame)
    if front.responses is None:
        return 0
    settled = [(g, []) for g in front.reported]
    return len(
        analysis._post_break_forks(
            settled, front.refused, front.responses, front.bins, fork_threshold=threshold
        )
    )


def _front(frame):
    return analysis._front_half(
        frame,
        false_alarm_rate=None,
        calibration=None,
        threshold=None,
        clip_level=None,
        bin_factors=None,
    )


@pytest.mark.parametrize("name", EVIDENCE_NAMES)
def test_break_evidence_is_where_the_first_break_is_found(name):
    """T7: the break pass on the frame's reported regions finds no break at S_b and at least
    one just below it (when S_b > 0)."""
    frame, evidence = _evidence(name)
    assert evidence.breaks >= 0
    assert _found_breaks(frame, evidence.breaks) == 0
    if evidence.breaks > 0:
        assert _found_breaks(frame, math.nextafter(evidence.breaks, 0)) >= 1
    if name == "break":
        assert evidence.breaks > _BREAK_MIN_EVIDENCE


@pytest.mark.parametrize("name", EVIDENCE_NAMES)
def test_fork_evidence_is_where_the_first_fork_is_found(name):
    """T7: the post-break Fork search with no break explained away finds no Fork at S_f and at
    least one just below it (when S_f > 0)."""
    frame, evidence = _evidence(name)
    assert evidence.forks >= 0
    assert _found_forks(frame, evidence.forks) == 0
    if evidence.forks > 0:
        assert _found_forks(frame, math.nextafter(evidence.forks, 0)) >= 1
    if name == "fork":
        assert evidence.forks > _FORK_MIN_EVIDENCE


def _hand(breaks, forks):
    """A 300-frame calibration whose thresholds at the default rate (k = 7) are ``breaks`` and
    ``forks`` raised to the floors: 10 frames at those values, the rest at 0."""
    n, high = 300, 10
    return _calibration([breaks] * high + [0.0] * (n - high), [forks] * high + [0.0] * (n - high))


def test_evidence_bounds_the_public_report(monkeypatch):
    """T8: with the stored calibration replaced by ones that put the thresholds just above and
    (where the scalar is above its floor) just below each frame's scalars, the public report
    obeys: a reported break => S_b > T_b; a reported Fork => S_f > T_f or a break; S_b <= T_b
    and S_f <= T_f => no break and no Fork."""
    below_checked = 0
    for name in EVIDENCE_NAMES:
        frame, ev = _evidence(name)
        choices_b = [math.nextafter(ev.breaks, math.inf)]
        choices_f = [math.nextafter(ev.forks, math.inf)]
        if ev.breaks > _BREAK_MIN_EVIDENCE:
            choices_b.append(math.nextafter(ev.breaks, 0))
        if ev.forks > _FORK_MIN_EVIDENCE:
            choices_f.append(math.nextafter(ev.forks, 0))
        for t_b in choices_b:
            for t_f in choices_f:
                cal = _hand(t_b, t_f)
                limits = cal.thresholds(DEFAULT_BREAK_FORK_FALSE_ALARM_RATE)
                # N10: a "just below" threshold sits above its floor, so it is the one used.
                if t_b < ev.breaks:
                    assert limits.breaks == t_b
                    below_checked += 1
                if t_f < ev.forks:
                    assert limits.forks == t_f
                    below_checked += 1
                monkeypatch.setattr(analysis, "_stored_break_fork_calibration", lambda c=cal: c)
                report = analyse(
                    frame, break_fork_false_alarm_rate=DEFAULT_BREAK_FORK_FALSE_ALARM_RATE
                )
                if report.phase_breaks:
                    assert ev.breaks > limits.breaks, name
                if report.forks:
                    assert ev.forks > limits.forks or ev.breaks > limits.breaks, name
                if ev.breaks <= limits.breaks and ev.forks <= limits.forks:
                    assert report.phase_breaks == (), name
                    assert report.forks == (), name
    assert below_checked >= 2


def test_analyse_and_evidence_share_the_front_half(monkeypatch):
    """B5 (supporting): one call of the shared front half from each."""
    calls = []
    real = analysis._front_half

    def spy(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(analysis, "_front_half", spy)
    frame = _evidence_frames()[0][1]
    analyse(frame)
    assert len(calls) == 1
    analysis._break_fork_evidence(frame)
    assert len(calls) == 2


# --- The driver (tests/break_fork_calibration.py): fast, on tiny plans ---------------------

TINY_SHAPE = (96, 192)


def _tiny(workers):
    return bfc.break_fork_calibration_from_seeds(
        BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS, TINY_SHAPE, workers=workers
    )


def test_break_fork_calibration_tiny_plan_is_repeatable():
    one = _tiny(1)
    two = _tiny(2)
    assert one == two  # run_info (wall clock, workers) is not compared
    assert one.ids == tuple(f"seed:{s}" for s in BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS)
    assert one.shape == TINY_SHAPE
    assert one.settings == json.loads(json.dumps(bfc.settings(TINY_SHAPE)))
    serial = [
        analysis._break_fork_evidence(bfc.synthetic(seed, TINY_SHAPE).frame)
        for seed in BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS
    ]
    assert one.break_evidence == tuple(e.breaks for e in serial)
    assert one.fork_evidence == tuple(e.forks for e in serial)
    assert one.run_info["workers"] == 1
    assert one.run_info["wall_clock_s"] > 0


def test_calibrate_break_forks_runs_the_core_on_the_calibration_set_inside_its_block(
    monkeypatch,
):
    """A2: the Calibration Set (or its prefix) is generated only inside its one
    seed_guard.calibrating(...) block."""
    calls = []

    def core(seeds, shape, workers=None):
        calls.append((seeds, shape, workers, seed_guard.worker_allowance()))
        return "calibration"

    monkeypatch.setattr(bfc, "break_fork_calibration_from_seeds", core)
    assert seed_guard.installed()
    assert BREAK_FORK_FREE_CALIBRATION_SEEDS not in (seed_guard.worker_allowance() or ())
    assert bfc.calibrate_break_forks(3) == "calibration"
    assert bfc.calibrate_break_forks(prefix=BREAK_FORK_REPRODUCTION_PREFIX) == "calibration"
    (full, prefix) = calls
    assert full[:3] == (BREAK_FORK_FREE_CALIBRATION_SEEDS, BREAK_FORK_CALIBRATION_SHAPE, 3)
    assert prefix[:3] == (
        BREAK_FORK_FREE_CALIBRATION_SEEDS[:BREAK_FORK_REPRODUCTION_PREFIX],
        BREAK_FORK_CALIBRATION_SHAPE,
        None,
    )
    for *_, allowed in calls:
        assert allowed is not None
        assert BREAK_FORK_FREE_CALIBRATION_SEEDS in allowed
    assert BREAK_FORK_FREE_CALIBRATION_SEEDS not in (seed_guard.worker_allowance() or ())


def test_break_fork_calibration_frames_are_striped_break_fork_free_spiked_and_unclipped():
    s = bfc.synthetic(BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS[0], TINY_SHAPE)
    assert s.truth.spike_pixels > 0
    assert s.truth.clipped_pixels == 0
    assert s.truth.phase_breaks == ()
    assert s.truth.forks == ()
    (region,) = s.truth.regions  # full-frame stripes
    assert region.mask.shape == s.frame.shape
    assert (region.mask == 1).all()
    assert region.modulation_depth == BREAK_FORK_CALIBRATION_DEPTH
    assert analyse(s.frame).striped
    settings = bfc.settings(BREAK_FORK_CALIBRATION_SHAPE)
    assert settings["modulation_depth"] == BREAK_FORK_CALIBRATION_DEPTH == 0.5
    assert settings["spikes"] == 30
    assert settings["mottle"] == "scorched"
    assert settings["clip_level"] is None
    assert (settings["phase_breaks"], settings["forks"]) == (0, 0)
    assert settings["evidence"] == "break-fork-v1"
    assert settings["floors"] == {"breaks": _BREAK_MIN_EVIDENCE, "forks": _FORK_MIN_EVIDENCE}
    assert BREAK_FORK_CALIBRATION_SHAPE == PROBE_SHAPE


def test_the_core_refuses_a_frame_that_is_not_striped():
    """A frame with no reported region would enter as S = 0 and loosen the thresholds."""
    with pytest.raises(ValueError, match="not Striped"):
        bfc.break_fork_calibration_from_seeds(
            BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS[:2], TINY_SHAPE, workers=1, depth=0.0
        )


def _tiny_stored():
    """A tiny stand-in for the stored calibration: 299 frames, so k = 7 at 5 %, thresholds at
    the floors (all evidence 0)."""
    zeros = [0.0] * 299
    return _BreakForkCalibration.from_evidence(
        [f"f{i}" for i in range(299)], zeros, zeros, TINY_SHAPE
    )


TINY_FAKES = bfc.FakesPlan(
    shape=TINY_SHAPE,
    seeds=BREAK_FORK_TINY_FREE_TEST_SEEDS,
    depth=BREAK_FORK_CALIBRATION_DEPTH,
    max_fakes=0,
    case_alarm_frames=1,
)
TINY_DETECTION = bfc.DetectionPlan(
    breaks=BREAK_FORK_TINY_BREAK_TEST_SEEDS,
    forks=BREAK_FORK_TINY_FORK_TEST_SEEDS,
    min_detection_rate=BREAK_FORK_MIN_DETECTION_RATE,
)


def test_slow_break_fork_checks_run_on_a_tiny_plan(tmp_path):
    # Reproduction (AC 1): a fresh run against itself has no problems, as a prefix too.
    stored = _tiny(2)
    t = stored.thresholds(0.9)
    result = bfc.reproduction_check(stored, lambda: _tiny(2), rate=0.9)
    assert result["n"] == len(BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS)
    assert result["n_differing"] == 0
    assert bfc.reproduction_problems(result, t.breaks, t.forks) == []
    prefix = bfc.reproduction_check(
        stored,
        lambda: bfc.break_fork_calibration_from_seeds(
            BREAK_FORK_TINY_CALIBRATION_TEST_SEEDS[:2], TINY_SHAPE, workers=1
        ),
        rate=0.9,
    )
    assert (prefix["n"], prefix["stored_n"]) == (2, 4)
    assert bfc.reproduction_problems(prefix, t.breaks, t.forks) == []
    # ... and against a stored file with one changed value, it names the frame.
    moved = _BreakForkCalibration.from_evidence(
        stored.ids,
        stored.break_evidence,
        (*stored.fork_evidence[:1], 0.75, *stored.fork_evidence[2:]),
        stored.shape,
        settings=stored.settings,
    )
    bad = bfc.reproduction_check(moved, lambda: _tiny(1), rate=0.9)
    assert bad["n_differing"] == 1
    text = "\n".join(bfc.reproduction_problems(bad, t.breaks, t.forks))
    assert "1 of 4 per-frame (S_b, S_f) differ" in text
    assert stored.ids[1] in text
    assert "never edit this check" in text.lower()
    other = _BreakForkCalibration.from_evidence(
        stored.ids, stored.break_evidence, stored.fork_evidence, stored.shape, settings={"x": 1}
    )
    other_result = bfc.reproduction_check(other, lambda: _tiny(1), rate=0.9)
    assert any("settings" in p for p in bfc.reproduction_problems(other_result, t.breaks, t.forks))
    assert any("thresholds" in p for p in bfc.reproduction_problems(result, t.breaks + 1, t.forks))

    # Held-out fakes (AC 2), at the tiny calibration's thresholds.
    limits = _tiny_stored().thresholds(BREAK_FORK_FALSE_ALARM_RATE)
    fakes = bfc.held_out_fakes(TINY_FAKES, workers=2, thresholds=lambda: limits)
    assert fakes["n"] == len(BREAK_FORK_TINY_FREE_TEST_SEEDS)
    assert fakes["thresholds"] == {"breaks": limits.breaks, "forks": limits.forks}
    assert sum(c["n"] for c in fakes["cases"]) == fakes["n"]
    assert 0 <= fakes["frames_with_fakes"] <= fakes["n"]
    assert 0 < fakes["frames_with_fakes_upper_95"] < 1
    assert fakes["implication_violations"] == []
    assert isinstance(bfc.fake_problems(fakes, limits), list)
    other_limits = _BreakForkThresholds(breaks=limits.breaks + 1, forks=limits.forks)
    assert any("thresholds" in p for p in bfc.fake_problems(fakes, other_limits))
    many = {**fakes, "count": 1, "breaks": 1, "frames_with_fakes": 1}
    assert any("above 0" in p for p in bfc.fake_problems(many, limits))
    flat = {**fakes, "not_striped": [BREAK_FORK_TINY_FREE_TEST_SEEDS[0]]}
    assert any("not Striped" in p for p in bfc.fake_problems(flat, limits))
    # The implication check at scale flags a report the evidence does not bound.
    row = {"seed": 1, "breaks": 1, "forks": 1, "s_b": 0.05, "s_f": 0.2}
    assert len(bfc.implication_violations(row, limits)) == 2
    assert bfc.implication_violations({**row, "s_b": 0.5}, limits) == []
    assert bfc.implication_violations({**row, "breaks": 0, "s_f": 0.5}, limits) == []
    bfc.record(tmp_path / "m.json", "fakes", fakes, fresh=True)

    # Held-out detection (AC 3(c)), with the paired count at the floors.
    detection = bfc.held_out_detection(TINY_DETECTION, workers=2)
    for kind, seeds in (("breaks", TINY_DETECTION.breaks), ("forks", TINY_DETECTION.forks)):
        r = detection[kind]
        assert r["n"] == len(seeds)
        assert r["min_found"] == len(seeds)  # ceil(0.95 * 2)
        assert r["found"] == r["found_at_floors"] == len(seeds)
        assert r["lost_by_calibration"] == []
        assert bfc.detection_problems(detection, kind) == []
        missed = {
            **detection,
            kind: {**r, "found": 0, "missed": [{"seed": 1, "period": 3, "angle_deg": 0}]},
        }
        assert any("found on the default path" in p for p in bfc.detection_problems(missed, kind))
        lost = {**detection, kind: {**r, "lost_by_calibration": [seeds[0]]}}
        assert any("lost at the stored" in p for p in bfc.detection_problems(lost, kind))
    bfc.record(tmp_path / "m.json", "detection", detection)
    assert set(json.loads((tmp_path / "m.json").read_text())) == {"fakes", "detection"}


def test_the_detection_floor_calibration_gives_the_floors():
    """The paired run's stand-in: its thresholds are the floors at every valid rate."""
    floors = _BreakForkThresholds(breaks=_BREAK_MIN_EVIDENCE, forks=_FORK_MIN_EVIDENCE)
    for rate in (0.01, BREAK_FORK_FALSE_ALARM_RATE, 0.5):
        assert bfc._floor_calibration().thresholds(rate) == floors


def test_break_fork_plan_meets_its_false_red_budget():
    """AC 2's count model (plan section 6, N11), fixed before the held-out look: under the
    r/2 + r/2 rule a new frame carries a fake with probability at most r, so frames with a
    fake follow at most the single-order-statistic model at r (k = 15 at n = 300),
    betabinom(300, 15, 286); its one-sided point at CALIBRATION_MAX_FALSE_RED is the bound.
    Conservative for frames with a fake, an approximation for the total count (several fakes
    on one frame are covered by P1's 1.5x multiplicity rule, plan section 3).

    AC 3(c): pooled bars at BREAK_FORK_MIN_DETECTION_RATE of N = 100 per kind. At the
    validated rates of 09 (AC 2 region frames, v2 validation 199/200,
    09-prototype-p1.md) and 10 (AC 2 single, validation 133/133, 10-prototype-p2.md), the
    false red is binom(100, p).cdf(94): 1.2e-5 and 0. All three together stay under
    CALIBRATION_MAX_FALSE_RED."""
    n_cal, n_held = len(BREAK_FORK_FREE_CALIBRATION_SEEDS), len(BREAK_FORK_FREE_HELD_OUT_SEEDS)
    assert (n_cal, n_held) == (300, 300)
    bound = bfc.fake_count_bound(
        n_cal, n_held, BREAK_FORK_FALSE_ALARM_RATE, CALIBRATION_MAX_FALSE_RED
    )
    assert bound == BREAK_FORK_MAX_FAKES == 29
    k = threshold_rank(n_cal, BREAK_FORK_FALSE_ALARM_RATE)
    assert k == 15
    count = betabinom(n_held, k, n_cal + 1 - k)
    ac2 = float(count.sf(bound))
    assert ac2 <= CALIBRATION_MAX_FALSE_RED < float(count.sf(bound - 1))

    bars = []
    for frames, (found, n) in (
        (BREAK_FORK_DETECTION_BREAK_FRAMES, (199, 200)),
        (BREAK_FORK_DETECTION_FORK_FRAMES, (133, 133)),
    ):
        assert frames == 100
        need = math.ceil(BREAK_FORK_MIN_DETECTION_RATE * frames - 1e-9)
        assert need == 95
        bars.append(float(binom(frames, found / n).cdf(need - 1)))
    assert bars[0] < 1e-4
    assert ac2 + sum(bars) <= CALIBRATION_MAX_FALSE_RED


def test_the_full_break_fork_plans_are_the_protected_ones():
    fakes, det = bfc.HELD_OUT_FAKES, bfc.HELD_OUT_DETECTION
    assert fakes.shape == BREAK_FORK_CALIBRATION_SHAPE
    assert fakes.seeds is BREAK_FORK_FREE_HELD_OUT_SEEDS
    assert fakes.depth == BREAK_FORK_CALIBRATION_DEPTH
    assert fakes.max_fakes == BREAK_FORK_MAX_FAKES
    assert fakes.case_alarm_frames == BREAK_FORK_CASE_ALARM_FRAMES
    assert len(det.breaks) == BREAK_FORK_DETECTION_BREAK_FRAMES
    assert len(det.forks) == BREAK_FORK_DETECTION_FORK_FRAMES
    assert set(det.breaks) | set(det.forks) == set(BREAK_FORK_DETECTION_HELD_OUT_SEEDS)
    assert not set(det.breaks) & set(det.forks)
    assert det.min_detection_rate == BREAK_FORK_MIN_DETECTION_RATE
    assert BREAK_FORK_FALSE_ALARM_RATE == DEFAULT_BREAK_FORK_FALSE_ALARM_RATE
    assert BREAK_FORK_REPRODUCTION_PREFIX == 6 * 10
    assert BREAK_FORK_FREE_CALIBRATION_SEEDS in CALIBRATION_SEEDS.values()


def test_statistical_break_fork_tests_are_slow():
    """AC 5: every test of both new slow modules is slow with the calibration timeout;
    held_out exactly on the held-out module (the full reproduction included), not on the
    check-slow reproduction."""
    found = {}
    for name in ("test_slow_break_fork_calibration", "test_held_out_break_fork"):
        module = importlib.import_module(name)
        module_marks = [m.mark if hasattr(m, "mark") else m for m in module.pytestmark]
        for attr, fn in vars(module).items():
            if attr.startswith("test_") and callable(fn):
                marks = module_marks + list(getattr(fn, "pytestmark", []))
                found[f"{name}::{attr}"] = {m.name: m for m in marks}
    for test, marks in found.items():
        assert "slow" in marks, test
        assert marks["timeout"].args == (CALIBRATION_TIMEOUT_S,), test
        assert ("held_out" in marks) == test.startswith("test_held_out_break_fork"), test
    assert set(found) == {
        "test_slow_break_fork_calibration::test_break_fork_calibration_reproduces_the_stored_thresholds",
        "test_held_out_break_fork::test_held_out_fake_breaks_and_forks_at_the_default_rate",
        "test_held_out_break_fork::test_breaks_still_found_after_calibration",
        "test_held_out_break_fork::test_forks_still_found_after_calibration",
        "test_held_out_break_fork::test_break_fork_calibration_reproduces_all_frames",
    }


# --- The stored break and Fork calibration: make check, no analysis ------------------------


def test_stored_break_fork_calibration_ships_with_the_package():
    resource = importlib.resources.files("denoisifier").joinpath("break_fork_free_calibration.json")
    assert resource.is_file()
    assert (
        _BreakForkCalibration.from_json(resource.read_text(encoding="utf-8"))
        == _stored_break_fork_calibration()
    )


def test_stored_break_fork_calibration_is_the_protected_one():
    """Any edit to the shipped file forces a lockfile edit (an approval): its thresholds, ids,
    shape, settings, evidence version and the digest of its whole payload are protected."""
    stored = _stored_break_fork_calibration()
    assert stored.thresholds(DEFAULT_BREAK_FORK_FALSE_ALARM_RATE) == _BreakForkThresholds(
        breaks=PACKAGE_BREAK_FORK_BREAK_THRESHOLD, forks=PACKAGE_BREAK_FORK_FORK_THRESHOLD
    )
    assert stored.ids == tuple(f"seed:{s}" for s in BREAK_FORK_FREE_CALIBRATION_SEEDS)
    assert stored.shape == BREAK_FORK_CALIBRATION_SHAPE
    assert stored.settings == json.loads(json.dumps(bfc.settings(BREAK_FORK_CALIBRATION_SHAPE)))
    assert json.loads(bfc.PACKAGE_FILE.read_text())["evidence"] == "break-fork-v1"
    assert int(stored.digest(), 16) == PACKAGE_BREAK_FORK_CALIBRATION_DIGEST


def test_stored_break_fork_calibration_names_the_stored_stripe_digest():
    """N4: the break and Fork evidence was taken at the stored stripe Threshold; a stripe
    re-store without a break and Fork re-store fails here, at make check."""
    stored = _stored_break_fork_calibration()
    assert stored.settings["stripe_calibration_digest"] == stored_calibration().digest()


def test_default_thresholds_are_the_stored_calibrations_at_the_default_rate():
    assert analysis._resolve_break_fork_thresholds(None) == (
        _stored_break_fork_calibration().thresholds(DEFAULT_BREAK_FORK_FALSE_ALARM_RATE)
    )
