"""Runtime seed guard (ticket agent-gates/04).

No test may judge the detector on a frame generated from a calibration seed.
``denoisifier.synthetic.generate`` raises the audit event
``denoisifier.synthetic.generate`` with its seed; the hook installed here
refuses any seed in a registered calibration range (``protected.CALIBRATION_SEEDS``)
unless it lies inside an active ``calibrating(...)`` block for that range.

Installed for every pytest run (tests/conftest.py), by ``feasibility.main()``,
and in ``feasibility.score_batch``'s workers (``install_worker``). This module,
those installs, the initializer and every ``calibrating(`` block are a
protected surface: adding, widening or moving a block, or removing an install,
is a weakening move (CLAUDE.md).

It imports no NumPy: feasibility.py imports it before setting its thread
variables, which must come before NumPy is imported.
"""

from __future__ import annotations

import contextlib
import operator
import sys
from collections.abc import Iterator

from protected import CALIBRATION_SEEDS

EVENT = "denoisifier.synthetic.generate"

_allowed: list[range] = []
_installed = False
_install_allowance: tuple[range, ...] = ()


class SeedGuardError(BaseException):
    """A calibration seed reached the generator outside its calibrating block.

    A BaseException, so a test's ``except Exception`` cannot swallow it."""


def _hook(event: str, args: tuple) -> None:
    if event != EVENT:
        return
    try:
        seed = operator.index(args[0])
    except TypeError:
        raise SeedGuardError(
            f"seed {args[0]!r} is not an int; the seed guard cannot check it"
            " (ticket agent-gates/04)"
        ) from None
    for name, r in CALIBRATION_SEEDS.items():
        if seed in r and not any(seed in a for a in _allowed):
            raise SeedGuardError(
                f"seed {seed} is in calibration range {name} = {r!r}, outside a"
                " seed_guard.calibrating(...) block. Evaluate on held-out seeds"
                " (ticket agent-gates/04); a new or wider calibrating block is a"
                " protected-surface change (CLAUDE.md)."
            )


def install(allowed: tuple[range, ...] = ()) -> None:
    """Turn the guard on in this process, allowing ``allowed`` ranges.

    Audit hooks cannot be removed, so the hook is added once. A later call
    with the same allowance changes nothing; one with a different allowance
    raises ValueError, since it could not take effect."""
    global _installed, _install_allowance
    allowed = tuple(allowed)
    if _installed:
        if allowed != _install_allowance:
            raise ValueError(
                f"seed guard already installed with allowance {_install_allowance!r};"
                f" cannot change it to {allowed!r} (ticket agent-gates/04)"
            )
        return
    _install_allowance = allowed
    _allowed[:] = list(allowed)
    sys.addaudithook(_hook)
    _installed = True


def installed() -> bool:
    return _installed


@contextlib.contextmanager
def calibrating(seeds: range) -> Iterator[None]:
    """Allow the calibration seeds ``seeds`` inside the block, and no others.

    ``seeds`` must be a non-empty, step-1 range inside one registered
    calibration range. THIS IS THE CALIBRATION MARKER: every use is a
    protected surface (CLAUDE.md)."""
    if not isinstance(seeds, range):
        raise ValueError(f"calibrating() takes a range, got {seeds!r} (ticket agent-gates/04)")
    if len(seeds) == 0:
        raise ValueError(f"calibrating() got an empty range {seeds!r} (ticket agent-gates/04)")
    if seeds.step != 1:
        raise ValueError(f"calibrating() needs step 1, got {seeds!r} (ticket agent-gates/04)")
    if not any(seeds[0] in r and seeds[-1] in r for r in CALIBRATION_SEEDS.values()):
        raise ValueError(
            f"calibrating({seeds!r}) is not inside one registered calibration range"
            " (protected.CALIBRATION_SEEDS; ticket agent-gates/04)"
        )
    _allowed.append(seeds)
    try:
        yield
    finally:
        _allowed.remove(seeds)


def worker_allowance() -> tuple[range, ...] | None:
    """What a worker process needs to mirror this one: ``None`` when the
    guard is off here, else the ranges allowed right now."""
    return tuple(_allowed) if _installed else None


def install_worker(allowance: tuple[range, ...] | None) -> None:
    """Pool initializer: install the guard with ``worker_allowance()``'s snapshot."""
    if allowance is not None:
        install(allowance)
