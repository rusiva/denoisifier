"""Stripe cases shared by the tests and the feasibility gate."""

from typing import NamedTuple


class Case(NamedTuple):
    period: int  # px
    angle_deg: int


CASES = [Case(*c) for c in [(3, 10), (5, 0), (8, 6), (12, -8), (20, -10), (4, -4), (16, 10), (6, -10), (10, 3), (14, -6)]]
