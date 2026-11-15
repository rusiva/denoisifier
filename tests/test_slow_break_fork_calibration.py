"""The break and Fork calibration reproduction (ticket 11, AC 1), in `make check-slow`.

The module fixture re-runs the calibration routine on the first
BREAK_FORK_REPRODUCTION_PREFIX frames of the Calibration Set
(BREAK_FORK_FREE_CALIBRATION_SEEDS, 6 per case; tests/break_fork_calibration.py) and compares
them with the package's stored file: ids, shape, JSON-normalised settings, every per-frame
(S_b, S_f) exactly, and the thresholds at the default rate. run_info is recorded, never
compared. The full 300 frames are reproduced in `make check-held-out`
(test_held_out_break_fork.py; P1's OQ8 prefix branch).

A red here is a finding unless the change was meant to move the evidence: then follow the
re-store procedure (CLAUDE.md, Gates). Never edit this check.

Duration: 60 full frames in the guarded pool (about 2.5 min idle); see the module docstring of
tests/test_slow_regression.py, the one source for the slow tier's duration.
"""

import pytest

import break_fork_calibration as bfc
from denoisifier.calibration import _stored_break_fork_calibration
from protected import (
    BREAK_FORK_REPRODUCTION_PREFIX,
    CALIBRATION_TIMEOUT_S,
    PACKAGE_BREAK_FORK_BREAK_THRESHOLD,
    PACKAGE_BREAK_FORK_FORK_THRESHOLD,
)

pytestmark = [pytest.mark.slow]


@pytest.fixture(scope="module")
def reproduction() -> dict:
    return bfc.reproduction_check(
        _stored_break_fork_calibration(),
        lambda: bfc.calibrate_break_forks(prefix=BREAK_FORK_REPRODUCTION_PREFIX),
    )


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_break_fork_calibration_reproduces_the_stored_thresholds(reproduction):
    assert reproduction["n"] == BREAK_FORK_REPRODUCTION_PREFIX
    problems = bfc.reproduction_problems(
        reproduction, PACKAGE_BREAK_FORK_BREAK_THRESHOLD, PACKAGE_BREAK_FORK_FORK_THRESHOLD
    )
    assert problems == [], "\n".join(problems)
