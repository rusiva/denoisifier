"""Runtime seed guard (ticket agent-gates/04): no test judges the detector on a
frame generated from a calibration seed, however the seed got there."""

import math
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import numpy as np
import pytest

import feasibility
import seed_guard
from denoisifier.synthetic import generate
from protected import (
    A0_CALIBRATION_SEEDS,
    CALIBRATION_SEEDS,
    GATE_CALIBRATION_SEEDS,
    PROBE_CALIBRATION_SEEDS,
)
from seed_guard import SeedGuardError

TESTS = Path(__file__).resolve().parent
SMALL = (40, 40)


def _message(seed, name):
    return re.escape(f"seed {seed} is in calibration range {name} = {CALIBRATION_SEEDS[name]!r}")


def test_guard_is_installed_for_the_run():
    assert seed_guard.installed()


@pytest.mark.parametrize("name", list(CALIBRATION_SEEDS))
def test_generate_refuses_each_calibration_range(name):
    r = CALIBRATION_SEEDS[name]
    for seed in (r[0], r[-1]):
        with pytest.raises(SeedGuardError, match=_message(seed, name)):
            generate(seed=seed, shape=SMALL)
    generate(seed=r[-1] + 1, shape=SMALL)
    if r[0] > 0:
        generate(seed=r[0] - 1, shape=SMALL)


def test_calibrating_allows_only_its_range():
    gate_seed = GATE_CALIBRATION_SEEDS[0]
    with seed_guard.calibrating(GATE_CALIBRATION_SEEDS):
        generate(seed=gate_seed, shape=SMALL)
        with pytest.raises(
            SeedGuardError, match=_message(PROBE_CALIBRATION_SEEDS[0], "PROBE_CALIBRATION_SEEDS")
        ):
            generate(seed=PROBE_CALIBRATION_SEEDS[0], shape=SMALL)
        with pytest.raises(
            SeedGuardError, match=_message(A0_CALIBRATION_SEEDS[0], "A0_CALIBRATION_SEEDS")
        ):
            generate(seed=A0_CALIBRATION_SEEDS[0], shape=SMALL)
    with pytest.raises(SeedGuardError, match=_message(gate_seed, "GATE_CALIBRATION_SEEDS")):
        generate(seed=gate_seed, shape=SMALL)

    # An exception inside the block still closes it.
    with pytest.raises(RuntimeError), seed_guard.calibrating(GATE_CALIBRATION_SEEDS):
        raise RuntimeError
    with pytest.raises(SeedGuardError, match=_message(gate_seed, "GATE_CALIBRATION_SEEDS")):
        generate(seed=gate_seed, shape=SMALL)

    # Only a non-empty, step-1 part of one registered range can be allowed.
    for bad, why in [
        (range(0, 10_000_000), "not inside one registered calibration range"),
        (range(10_000, 10_000), "empty range"),
        (range(10_000, 10_100, 2), "needs step 1"),
        ([10_000], "takes a range"),
    ]:
        with pytest.raises(ValueError, match=why), seed_guard.calibrating(bad):
            pass


def test_guard_reaches_the_feasibility_workers():
    seeds = [GATE_CALIBRATION_SEEDS[0]]
    t0 = time.perf_counter()
    with pytest.raises(SeedGuardError, match=_message(seeds[0], "GATE_CALIBRATION_SEEDS")):
        feasibility.score_batch(seeds, 0.0, SMALL, workers=1)
    with seed_guard.calibrating(GATE_CALIBRATION_SEEDS):
        scores = feasibility.score_batch(seeds, 0.0, SMALL, workers=1)
    print(f"two single-seed worker batches: {time.perf_counter() - t0:.1f} s")
    assert scores.shape == (1,)
    assert np.isfinite(scores[0])


def test_measure_calibrates_inside_the_block_and_evaluates_outside(monkeypatch):
    plan = feasibility.SeedPlan(SMALL, GATE_CALIBRATION_SEEDS[:99], range(40, 50), range(50, 60))
    calls = []

    def fake(seeds, depth, shape, workers=None):
        # Real generate first, so a calibration seed outside the block fails
        # with the guard's own message; then the block must be no wider.
        scores = np.array(
            [
                feasibility._frame(seed, depth, shape, feasibility.case_of(seed)).std()
                for seed in seeds
            ]
        )
        expected = (plan.calibration,) if seeds is plan.calibration else ()
        assert seed_guard.worker_allowance() == expected
        calls.append((seeds, workers))
        return scores

    monkeypatch.setattr(feasibility, "score_batch", fake)
    result = feasibility.measure(plan)
    assert calls == [(plan.calibration, None), (plan.free, None), (plan.striped, None)]
    assert result.calibration_n == 99
    assert math.isfinite(result.threshold)


def test_non_int_seed_is_refused():
    with pytest.raises(SeedGuardError, match="is not an int"):
        generate(seed=[10_000], shape=SMALL)


SCRIPT = textwrap.dedent(
    """
    import sys
    from pathlib import Path

    import feasibility
    from protected import GATE_CALIBRATION_SEEDS

    def measure_all(workers=None, probe=True):
        feasibility.score_batch([GATE_CALIBRATION_SEEDS[0]], 0.0, (40, 40), 1)
        return {}

    feasibility.measure_all = measure_all
    sys.exit(feasibility.main(["--out", sys.argv[1]]))
    """
)


def test_feasibility_script_guards_itself_and_its_workers(tmp_path):
    out = tmp_path / "result.json"
    t0 = time.perf_counter()
    # The conftest never loads in this process: main() must install the guard.
    run = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(out)],
        cwd=TESTS,
        capture_output=True,
        text=True,
        timeout=45,
    )
    print(f"standalone feasibility run: {time.perf_counter() - t0:.1f} s")
    assert run.returncode != 0
    assert "SeedGuardError" in run.stderr
    assert "seed 10000 is in calibration range GATE_CALIBRATION_SEEDS" in run.stderr
    assert not out.exists()
