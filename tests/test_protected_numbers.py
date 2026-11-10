"""Protected numbers (ticket agent-gates/03): the live values must match the lockfile.

Editing this file, protected_lock.py or protected_numbers.lock is a weakening
move: owner approval (CLAUDE.md).
"""

import importlib.util
import itertools
import math
import textwrap
from typing import NamedTuple

import numpy as np

from protected_lock import LOCKFILE, canonical, check, protected_modules


def test_protected_numbers_match_the_lockfile():
    problems = check(LOCKFILE.read_text(encoding="utf-8"), protected_modules())
    assert not problems, (
        f"{LOCKFILE.name}: {len(problems)} protected number(s) differ from the lockfile:\n"
        + "\n".join(f"  {p}" for p in problems)
        + f"\nA protected number changed. Editing {LOCKFILE.name} is a weakening move that "
        "needs the owner's approval first (CLAUDE.md); otherwise restore the number."
    )


def test_the_scan_covers_the_detector_and_the_test_module():
    names = [m.__name__ for m in protected_modules()]
    assert {"denoisifier.analysis", "denoisifier._local_stripes", "protected"} <= set(names)


_counter = itertools.count()


def _module(tmp_path, source):
    name = f"_protected_plant_{next(_counter)}"
    path = tmp_path / f"{name}.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE = textwrap.dedent(
    """
    import math
    from math import pi

    LIMIT = 2.5
    NAME = "label"
    FLAG = True
    SEEDS = range(10, 20)
    DERIVED = math.sqrt(LIMIT * 4)

    class Settings:
        GAIN = 3
        label: str

    def f():
        local = 99
        return local
"""
)


def _lock_for(module):
    return "\n".join(
        [
            "# header",
            f"{module.__name__} :: LIMIT :: 2.5",
            f"{module.__name__} :: SEEDS :: range(10, 20)",
            f"{module.__name__} :: DERIVED :: {canonical(math.sqrt(10))}",
            f"{module.__name__} :: Settings.GAIN :: 3",
        ]
    )


def test_matching_lockfile_has_no_problems(tmp_path):
    m = _module(tmp_path, SOURCE)
    assert check(_lock_for(m), [m]) == []


def test_changed_value_is_named(tmp_path):
    m = _module(tmp_path, SOURCE.replace("LIMIT = 2.5", "LIMIT = 2.6"))
    problems = check(_lock_for(m), [m])
    assert f"{m.__name__} :: LIMIT changed: lockfile 2.5, live 2.6" in problems
    # DERIVED follows LIMIT through the expression: its live value changed too.
    assert any(p.startswith(f"{m.__name__} :: DERIVED changed") for p in problems)


def test_new_number_not_in_the_lockfile_is_named(tmp_path):
    m = _module(tmp_path, SOURCE + "\nNEW_TOL = (0, 1e-3)\n")
    assert check(_lock_for(m), [m]) == [
        f"{m.__name__} :: NEW_TOL = (0, 0.001) is a number that is not in the lockfile"
    ]


def test_new_class_level_number_is_named(tmp_path):
    m = _module(tmp_path, SOURCE.replace("GAIN = 3", "GAIN = 3\n    OFFSET = 1"))
    assert check(_lock_for(m), [m]) == [
        f"{m.__name__} :: Settings.OFFSET = 1 is a number that is not in the lockfile"
    ]


def test_removed_or_non_numeric_entry_is_named(tmp_path):
    source = SOURCE.replace("LIMIT = 2.5", 'LIMIT = "2.5"').replace("LIMIT * 4", "10")
    m = _module(tmp_path, source)
    assert check(_lock_for(m), [m]) == [
        f"{m.__name__} :: LIMIT (lockfile 2.5) is no longer a number, or was renamed or removed"
    ]


def test_imported_numbers_are_left_to_their_own_module(tmp_path):
    m = _module(tmp_path, "from math import pi\nimport math\nTAU = 2 * pi\n")
    assert check("", [m]) == [
        f"{m.__name__} :: TAU = {canonical(2 * np.pi)} is a number that is not in the lockfile"
    ]


def test_malformed_and_duplicate_lines_are_named(tmp_path):
    m = _module(tmp_path, "X = 1\n")
    lock = f"{m.__name__} :: X :: 1\n{m.__name__} :: X :: 1\nnot a record\n"
    assert check(lock, [m]) == [
        f"line 2: {m.__name__} :: X is listed twice",
        "line 3 is not `module :: name :: value`: 'not a record'",
    ]


class _Plan(NamedTuple):
    shape: tuple[int, int]
    seeds: range


def test_canonical_text_is_exact_and_names_structure():
    assert canonical(0.1 + 0.2) == "0.30000000000000004"
    assert canonical(np.float64(1.5)) == "1.5"
    assert canonical((3,)) == "(3,)"
    assert canonical(_Plan((2, 3), range(5, 9))) == "_Plan(shape=(2, 3), seeds=range(5, 9))"
    assert canonical(np.array([1.0, 2.5])) == "ndarray[float64, (2,)]([1.0, 2.5])"
    assert canonical({"a": 0.4}) == "{'a': 0.4}"
