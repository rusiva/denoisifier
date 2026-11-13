"""Stripe cases shared by the tests and the feasibility gate."""

from collections.abc import Callable
from typing import Any, NamedTuple

from denoisifier.synthetic import Synthetic, generate


class Case(NamedTuple):
    period: int  # px
    angle_deg: int


CASES = [
    Case(*c)
    for c in [
        (3, 10),
        (5, 0),
        (8, 6),
        (12, -8),
        (20, -10),
        (4, -4),
        (16, 10),
        (6, -10),
        (10, 3),
        (14, -6),
    ]
]


def case_frame(seed: int, **kwargs: Any) -> Synthetic:
    """``generate(seed=seed, **kwargs)`` with the Period and Angle of
    ``CASES[seed % len(CASES)]``."""
    case = CASES[seed % len(CASES)]
    return generate(seed=seed, period=case.period, angle_deg=case.angle_deg, **kwargs)


def clipped_at(
    fraction: float, make: Callable[..., Synthetic], **kwargs: Any
) -> tuple[Synthetic, float]:
    """``(make(clip_level=level, **kwargs), level)``, where ``level`` is
    ``fraction`` times the clean maximum of the same frame without the clip."""
    level = fraction * float(make(**kwargs).clean.max())
    return make(clip_level=level, **kwargs), level
