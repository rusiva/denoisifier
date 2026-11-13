"""The seed-breadth split of make test-fast (ticket agent-gates/07).

``make test-fast`` deselects ``wide`` parameters; ``make check`` runs them all. ``inner`` and
``diagonal`` build parametrize lists in which only the first seeds, or a covering subset of a
cross-product, stay unmarked; every other parameter gets ``pytest.mark.wide``. Ids and values
do not change. A test function whose parameters are all ``wide`` fails collection
(``tests/conftest.py``), so no test leaves the inner loop silently. Adding ``wide`` to a
parameter is a narrowing move that needs an approval (CLAUDE.md).
"""

from collections.abc import Callable, Iterable, Sequence
from typing import Any

import pytest
from _pytest.mark.structures import ParameterSet

from protected import INNER_LOOP_SEED_COUNT

WIDE = pytest.mark.wide


def _wide(value: Any, multi: bool) -> ParameterSet:
    if isinstance(value, ParameterSet):
        return pytest.param(*value.values, marks=[*value.marks, WIDE], id=value.id)
    return pytest.param(*value, marks=WIDE) if multi else pytest.param(value, marks=WIDE)


def inner(
    values: Iterable[Any],
    *,
    keep: int = INNER_LOOP_SEED_COUNT,
    key: Callable[[Any], Any] | None = None,
    multi: bool = False,
) -> list[Any]:
    """Parametrize values for the seed-breadth split. A value whose key (``key(value)``, by
    default the value itself) is among the first ``keep`` distinct keys, in order, stays as it
    is; every other value gets WIDE. ``multi=True``: each value is the tuple of argvalues for
    several argnames; ``multi=False``: one argname, the value as is, even a tuple. A
    ``pytest.param`` keeps its id and marks; its key is taken from its values."""
    kept: list[Any] = []
    out = []
    for value in values:
        raw = value
        if isinstance(value, ParameterSet):
            raw = tuple(value.values) if multi else value.values[0]
        k = key(raw) if key is not None else raw
        if k not in kept and len(kept) < keep:
            kept.append(k)
        out.append(value if k in kept else _wide(value, multi))
    return out


def diagonal(
    seeds: Sequence[Any],
    cases: Sequence[tuple[Any, ...]],
    *,
    keep: int = INNER_LOOP_SEED_COUNT,
    seed_first: bool = False,
    cover: Callable[[tuple[Any, ...]], bool] | None = None,
) -> list[Any]:
    """The full cross-product of ``cases`` and ``seeds`` as multi-argname tuples,
    ``(*case, seed)`` or, with ``seed_first``, ``(seed, *case)``, in the order and with the ids
    of the stacked parametrize it replaces (the first argname varies slowest). The inner loop
    keeps each case that ``cover`` accepts (default: every case) once; the k-th kept case runs
    at ``seeds[k % keep]``. Every other pair is WIDE."""
    covered = [i for i, case in enumerate(cases) if cover is None or cover(case)]
    inner_seed = {i: seeds[k % min(keep, len(seeds))] for k, i in enumerate(covered)}
    if seed_first:
        pairs = [(i, seed) for seed in seeds for i in range(len(cases))]
    else:
        pairs = [(i, seed) for i in range(len(cases)) for seed in seeds]
    out = []
    for i, seed in pairs:
        value = (seed, *cases[i]) if seed_first else (*cases[i], seed)
        out.append(value if inner_seed.get(i) == seed else _wide(value, multi=True))
    return out
