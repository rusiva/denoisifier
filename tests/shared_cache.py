"""Caches shared by the analyse tests (ticket agent-gates/07).

Several tests analyse the same frame: ``analysed`` keys one ``generate`` + ``analyse`` per call
of ``generate``, and ``normalised_cache`` memoises a test helper. Both bind the call to the
signature, defaults applied, so every spelling of one call (positional, keyword, a default
spelt out or left out) is one entry, and a different spelling cannot silently miss. Every
array they hand out is read-only, so no test can change what another test reads.
"""

import dataclasses
import functools
import inspect
from collections.abc import Callable
from typing import Any

import numpy as np

from denoisifier import Report, analyse
from denoisifier.synthetic import Synthetic, generate


def freeze(value: Any) -> None:
    """Make every array of a (nested) dataclass or tuple read-only, in place."""
    if isinstance(value, np.ndarray):
        value.setflags(write=False)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            freeze(getattr(value, field.name))
    elif isinstance(value, tuple):
        for item in value:
            freeze(item)


def normalised_cache(
    fn: Callable[..., Any], *, signature: inspect.Signature | None = None
) -> Callable[..., Any]:
    """``functools.cache`` of ``fn``, keyed by the call bound to ``signature`` (default: fn's
    own) with its defaults applied; the result is frozen (``freeze``)."""
    sig = signature or inspect.signature(fn)

    @functools.cache
    def cached(*args: Any, **kwargs: Any) -> Any:
        result = fn(*args, **kwargs)
        freeze(result)
        return result

    @functools.wraps(fn)
    def call(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return cached(*bound.args, **bound.kwargs)

    return call


def _analysed(**generate_kwargs: Any) -> tuple[Synthetic, Report]:
    s = generate(**generate_kwargs)
    return s, analyse(s.frame)


#: ``(generate(**kwargs), analyse(frame))`` at the default threshold, once per distinct call
#: of ``generate``. The arguments must be hashable (no ``regions`` list).
analysed = normalised_cache(_analysed, signature=inspect.signature(generate))
