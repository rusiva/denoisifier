"""The seed-breadth split of make test-fast (ticket agent-gates/07): the helpers that mark
parameters `wide`, the collection-time check that no test function is all `wide`, and the
subsets the inner loop keeps."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import test_analyse
from cases import CASES
from inner_loop import diagonal, inner
from protected import DARK_REGRESSION_CASES, TWO_REGION_PAIRS, TWO_REGION_TEST_SEEDS


def _is_wide(param):
    return any(m.name == "wide" for m in getattr(param, "marks", ()))


def _values(param):
    """A parametrize value as pytest sees it, without its marks."""
    return tuple(param.values) if hasattr(param, "marks") else param


def test_inner_keeps_the_first_seeds_plain_and_marks_the_rest_wide():
    params = inner(range(10, 15), keep=2)
    assert params[:2] == [10, 11]
    assert [_is_wide(p) for p in params] == [False, False, True, True, True]
    assert [p.values for p in params[2:]] == [(12,), (13,), (14,)]


def test_inner_keys_values_and_keeps_every_value_of_a_kept_key():
    pairs = [(20, "a"), (20, "b"), (21, "a"), (21, "b"), (22, "a")]
    params = inner(pairs, keep=2, key=lambda v: v[0], multi=True)
    assert params[:4] == pairs[:4]
    assert _is_wide(params[4])
    assert params[4].values == (22, "a")


def test_inner_without_multi_keeps_a_tuple_as_one_value():
    params = inner([(1, 2), (3, 4)], keep=1)
    assert params[0] == (1, 2)
    assert params[1].values == ((3, 4),)


def test_inner_keeps_the_id_and_marks_of_a_param():
    skip = pytest.mark.skipif(False, reason="planted")
    params = inner([pytest.param(1, id="one"), pytest.param(2, id="two", marks=skip)], keep=1)
    assert params[0].id == "one"
    assert not _is_wide(params[0])
    assert params[1].id == "two"
    assert {m.name for m in params[1].marks} == {"skipif", "wide"}


def test_inner_is_capped_by_the_number_of_keys():
    assert inner([5], keep=2) == [5]


def test_diagonal_is_the_full_cross_product_in_stacked_order():
    seed_last = diagonal(range(20, 23), [(5,), (12,)], keep=2)
    assert [_values(p) for p in seed_last] == [
        (5, 20),
        (5, 21),
        (5, 22),
        (12, 20),
        (12, 21),
        (12, 22),
    ]
    seed_first = diagonal(range(66, 68), [("a",), ("b",)], keep=2, seed_first=True)
    assert [_values(p) for p in seed_first] == [(66, "a"), (66, "b"), (67, "a"), (67, "b")]


def test_diagonal_keeps_each_case_once_on_the_first_seeds_in_turn():
    params = diagonal((81, 83, 84), [("p",), ("q",), ("r",)], keep=2)
    plain = [p for p in params if not _is_wide(p)]
    assert plain == [("p", 81), ("q", 83), ("r", 81)]
    assert len(params) - len(plain) == 6


# --- The collection-time all-`wide` check (tests/conftest.py) ------------------------------

TESTS = Path(__file__).parent

PLANTED_MIXED = """
import pytest
from inner_loop import inner


@pytest.mark.parametrize("seed", inner(range(10, 13)))
def test_mixed(seed):
    pass
"""

PLANTED_ALL_WIDE = """

@pytest.mark.parametrize("seed", [pytest.param(s, marks=pytest.mark.wide) for s in (1, 2)])
def test_all_wide_params(seed):
    pass


@pytest.mark.wide
@pytest.mark.parametrize("seed", [1, 2])
def test_wide_as_a_whole(seed):
    pass
"""

# A mixed function whose `wide` parameter fails: the natural `--lf` rerun after make check.
PLANTED_WIDE_FAILURE = """
import pytest
from inner_loop import inner


@pytest.mark.parametrize("seed", inner(range(10, 13)))
def test_wide_seed_fails(seed):
    assert seed < 12
"""


def _plant(root, source):
    root.mkdir()
    (root / "conftest.py").write_text((TESTS / "conftest.py").read_text())
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    slow: planted\n    wide: planted\nstrict_markers = true\n"
    )
    (root / "test_planted.py").write_text(source)
    return root


def _pytest(root, *args):
    env = {**os.environ, "PYTHONPATH": str(TESTS)}
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_a_function_with_only_wide_parameters_fails_collection(tmp_path):
    root = _plant(tmp_path / "planted", PLANTED_MIXED + PLANTED_ALL_WIDE)
    result = _pytest(root, "--collect-only", "-q", "-p", "no:cacheprovider")
    assert result.returncode == 4, result.stdout + result.stderr
    (error,) = [line for line in result.stderr.splitlines() if "only `wide`" in line]
    assert "test_planted.py::test_all_wide_params" in error
    assert "test_planted.py::test_wide_as_a_whole" in error
    assert "test_mixed" not in error


def test_functions_with_an_inner_parameter_pass_collection(tmp_path):
    root = _plant(tmp_path / "planted", PLANTED_MIXED)
    result = _pytest(root, "--collect-only", "-q", "-p", "no:cacheprovider")
    assert result.returncode == 0, result.stdout + result.stderr


def test_an_explicit_item_selection_is_exempt(tmp_path):
    root = _plant(tmp_path / "planted", PLANTED_MIXED + PLANTED_ALL_WIDE)
    arg = "test_planted.py::test_all_wide_params[1]"
    result = _pytest(root, "--collect-only", "-q", "-p", "no:cacheprovider", arg)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_file_arg_next_to_an_item_arg_is_still_checked(tmp_path):
    root = _plant(tmp_path / "planted", PLANTED_MIXED + PLANTED_ALL_WIDE)
    (root / "test_other.py").write_text("def test_other():\n    pass\n")
    args = ["test_planted.py", "test_other.py::test_other"]
    result = _pytest(root, "--collect-only", "-q", "-p", "no:cacheprovider", *args)
    assert result.returncode == 4, result.stdout + result.stderr
    assert "test_planted.py::test_all_wide_params" in result.stderr


def test_a_last_failed_rerun_of_a_wide_seed_runs_it(tmp_path):
    root = _plant(tmp_path / "lf", PLANTED_WIDE_FAILURE)
    assert _pytest(root, "-q").returncode == 1
    rerun = _pytest(root, "-q", "--lf")
    assert rerun.returncode == 1, rerun.stdout + rerun.stderr
    assert "1 failed" in rerun.stdout


def test_make_test_fast_deselects_wide_and_keeps_its_flags():
    # Under `make check` the outer make's MAKEFLAGS/MAKELEVEL would add
    # "Entering/Leaving directory" lines.
    env = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL")}
    dry_run = subprocess.run(
        ["make", "-n", "--no-print-directory", "test-fast"],
        cwd=TESTS.parent,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout
    (line,) = dry_run.strip().splitlines()
    assert " pytest -x --ff " in line
    assert line.endswith('-m "not slow and not wide"')


# --- The subsets the inner loop keeps (tests/test_analyse.py) ------------------------------


def _inner(params):
    return [_values(p) for p in params if not _is_wide(p)]


def test_clear_stripes_run_every_case_in_the_inner_loop():
    seeds = _inner(test_analyse.CLEAR_STRIPES_PARAMS)
    assert {seed % len(CASES) for seed in seeds} == set(range(len(CASES)))


def test_the_verdict_sweep_keeps_every_threshold_kind_and_frame_family():
    pairs = _inner(test_analyse.VERDICT_PARAMS)
    assert {kind for _, kind in pairs} == set(test_analyse.SWEEP_THRESHOLDS)
    families = {re.sub(r"(-\d+)+$", "", name) for name, _ in pairs}
    assert families == {
        "free",
        "striped",
        "borderline",
        "two-region",
        "overlapping-extents",
        "constant",
    }
    all_names = {_values(p)[0] for p in test_analyse.VERDICT_PARAMS}
    assert all_names == set(test_analyse.SWEEP_FRAMES)


def test_the_lowering_test_keeps_every_threshold_kind():
    triples = _inner(test_analyse.LOWERING_PARAMS)
    assert {k for _, a, b in triples for k in (a, b)} == set(test_analyse.SWEEP_THRESHOLDS)
    names = {name for name, _, _ in triples}
    assert "overlapping-extents" in names
    assert any(name.startswith("striped-") for name in names)


def test_the_two_region_frame_is_analysed_once_in_the_inner_loop():
    assert _inner(test_analyse.TWO_REGION_PARAMS) == [
        (TWO_REGION_TEST_SEEDS[0], *TWO_REGION_PAIRS[0])
    ]
    verdict = [kind for name, kind in _inner(test_analyse.VERDICT_PARAMS) if name == "two-region"]
    assert verdict == ["THRESHOLD"]
    assert not [t for t in _inner(test_analyse.LOWERING_PARAMS) if t[0] == "two-region"]


@pytest.mark.parametrize(
    ("params", "shapes"),
    [
        ("BELOW_SIZE_PARAMS", ["both", "wide_short", "four_by_one", "narrow_tall"]),
        ("ABOVE_SIZE_PARAMS", ["both", "wide_short", "narrow_tall"]),
    ],
)
def test_the_size_tests_meet_every_shape_and_period(params, shapes):
    kept = _inner(getattr(test_analyse, params))
    periods = {p for p, _ in test_analyse.SIZE_CASES}
    assert {(shape, period) for _, period, _, shape in kept} == {
        (shape, period) for shape in shapes for period in periods
    }
    assert {(period, angle) for _, period, angle, _ in kept} == set(test_analyse.SIZE_CASES)
    assert {_values(p)[3] for p in getattr(test_analyse, params)} == set(shapes)


def test_the_dark_test_keeps_every_case_and_the_regression_cases():
    params = test_analyse.DARK_PARAMS
    assert {case for _, case in _inner(params)} == set(test_analyse.DARK_CASES)
    for case in DARK_REGRESSION_CASES:
        (param,) = [p for p in params if _values(p) == case]
        assert not _is_wide(param)
