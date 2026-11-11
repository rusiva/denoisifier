"""The Report that ``analyse`` returns."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Report:
    """What ``analyse`` found in one frame.

    ``striped`` is decided by ``score > threshold``. ``period_px`` is the
    Period in sensor pixels; ``angle_deg`` is the Angle in degrees, with the
    sign convention in GLOSSARY.md. ``modulation_depth`` is the Modulation
    Depth relative to the local Envelope (GLOSSARY.md). All three are
    ``None`` when the frame is not striped. ``reader_notes`` are the frame
    reader's notes when the frame came from a file (the CLI sets them), and
    ``None`` otherwise (``analyse`` leaves them ``None``).
    """

    striped: bool
    score: float
    threshold: float
    period_px: float | None
    angle_deg: float | None
    modulation_depth: float | None
    reader_notes: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, bool | float | list[str] | None]:
        """Plain Python types only, so ``json.dumps`` works.

        ``reader_notes`` is included, as a list, only when it is not ``None``.
        """
        d: dict[str, bool | float | list[str] | None] = {
            "striped": bool(self.striped),
            "score": float(self.score),
            "threshold": float(self.threshold),
            "period_px": _float_or_none(self.period_px),
            "angle_deg": _float_or_none(self.angle_deg),
            "modulation_depth": _float_or_none(self.modulation_depth),
        }
        if self.reader_notes is not None:
            d["reader_notes"] = list(self.reader_notes)
        return d

    def to_json(self) -> str:
        # allow_nan=False: a NaN can never become invalid JSON.
        return json.dumps(self.to_dict(), indent=2, allow_nan=False)


def _float_or_none(value: float | None) -> float | None:
    return None if value is None else float(value)
