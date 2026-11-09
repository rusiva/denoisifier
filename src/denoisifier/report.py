"""The Report that ``analyse`` returns."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Report:
    """What ``analyse`` found in one frame.

    ``striped`` is decided by ``score > threshold``. ``period_px`` is the
    stripe period in sensor pixels, measured across the stripes.
    ``angle_deg`` is the tilt of the stripes from vertical, in degrees: row 0
    is the top of the frame, and positive means the top of each stripe leans
    right (moving down the frame, a stripe shifts left). Both are ``None``
    when the frame is not striped.
    """

    striped: bool
    score: float
    threshold: float
    period_px: float | None
    angle_deg: float | None

    def to_dict(self) -> dict:
        """Plain Python types only, so ``json.dumps`` works."""
        return {
            "striped": bool(self.striped),
            "score": float(self.score),
            "threshold": float(self.threshold),
            "period_px": None if self.period_px is None else float(self.period_px),
            "angle_deg": None if self.angle_deg is None else float(self.angle_deg),
        }

    def to_json(self, indent: int | None = 2) -> str:
        # allow_nan=False: a NaN can never become invalid JSON.
        return json.dumps(self.to_dict(), indent=indent, allow_nan=False)
