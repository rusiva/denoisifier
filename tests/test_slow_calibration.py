"""The calibration reproduction (ticket 07, AC 7), in `make check-slow`.

The module fixture re-runs the calibration routine on the Calibration Set
(STRIPE_FREE_CALIBRATION_SEEDS, 400x1600; tests/threshold_calibration.py) and
compares it with the package's stored file: ids, shape, JSON-normalised settings,
every per-seed score exactly (ruling Q7) and the Thresholds at 1% and 5%. run_info
is recorded, never compared.

A red here is a finding unless the change was meant to move scores: then follow the
re-store procedure (CLAUDE.md, Gates). Never edit this check.

Duration: about 300 full frames in the guarded pool; see the module docstring of
tests/test_slow_regression.py, the one source for the slow tier's duration. The
per-test timeout covers the fixture of the first test (W6).
"""

import pytest

import protected
import threshold_calibration as tc
from denoisifier.calibration import stored_calibration
from protected import CALIBRATION_TIMEOUT_S

pytestmark = [pytest.mark.slow]


@pytest.fixture(scope="module")
def reproduction() -> dict:
    return tc.reproduction_check(stored_calibration())


@pytest.mark.timeout(CALIBRATION_TIMEOUT_S)
def test_calibration_reproduces_the_stored_thresholds(reproduction):
    problems = tc.reproduction_problems(
        reproduction,
        protected.PACKAGE_STORED_THRESHOLD,
        protected.PACKAGE_STORED_THRESHOLD_5PCT,
    )
    assert problems == [], "\n".join(problems)
