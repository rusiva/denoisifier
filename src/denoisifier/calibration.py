"""Calibration: the Threshold as an order statistic of Stripe-free scores (ADR 0002).

A ``Calibration`` holds the Stripe Score of every frame of a Calibration Set
(Stripe-free frames, generated or real, never the frames it is evaluated on),
the frame shape they were scored at, how the set was made (``settings``) and
how the run went (``run_info``). ``Calibration.threshold(rate)`` is the
Threshold at a requested false-alarm rate: the k-th largest score, with
k = floor(rate * (n + 1)).

The package ships one Calibration (``stored_calibration()``): 300 generated
Stripe-free 400x1600 frames at typical settings. ``analyse`` uses it at
``DEFAULT_FALSE_ALARM_RATE`` unless told otherwise.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike

from denoisifier._calibration import threshold_for_false_alarm_rate, threshold_rank

DEFAULT_FALSE_ALARM_RATE = 0.01


def _json_normalised(value: Mapping[str, object]) -> dict[str, object]:
    """``value`` as it reads back from JSON (tuples become lists)."""
    out = json.loads(json.dumps(dict(value), allow_nan=False))
    assert isinstance(out, dict)
    return out


@dataclass(frozen=True)
class Calibration:
    """Stripe Scores of a Calibration Set, and the Threshold they give.

    ``ids`` name the frames (``"seed:100000"`` for generated ones, file names
    for a folder); ``scores`` are in ``ids`` order. ``shape`` is the frame
    shape (rows, cols) the scores were taken at: the rate holds for frames of
    that shape (on smaller frames the false-alarm rate is expected to be
    lower). ``settings`` record how the set was made and are compared;
    ``run_info`` (commit, machine, versions, wall clock) is recorded and never
    compared: two Calibrations that differ only in ``run_info`` are equal.
    Both are kept JSON-normalised. Build one with ``from_scores``.
    """

    ids: tuple[str, ...]
    scores: tuple[float, ...]
    shape: tuple[int, int]
    settings: Mapping[str, object] = field(default_factory=dict)
    run_info: Mapping[str, object] = field(default_factory=dict, compare=False)

    @classmethod
    def from_scores(
        cls,
        ids: Sequence[str],
        scores: ArrayLike,
        shape: tuple[int, int],
        *,
        settings: Mapping[str, object] | None = None,
        run_info: Mapping[str, object] | None = None,
    ) -> Calibration:
        """A Calibration of ``scores`` (one per id, all finite)."""
        a = np.asarray(scores, dtype=float).ravel()
        ids = tuple(str(i) for i in ids)
        if a.size == 0:
            raise ValueError("a Calibration needs at least one score; got no scores")
        if len(ids) != a.size:
            raise ValueError(f"{len(ids)} ids for {a.size} scores")
        if len(set(ids)) != len(ids):
            raise ValueError("ids must be unique")
        if not np.all(np.isfinite(a)):
            raise ValueError("scores must all be finite")
        if len(shape) != 2 or min(int(s) for s in shape) < 1:
            raise ValueError(f"shape must be two positive sizes, got {shape!r}")
        return cls(
            ids=ids,
            scores=tuple(float(s) for s in a),
            shape=(int(shape[0]), int(shape[1])),
            settings=_json_normalised(settings or {}),
            run_info=_json_normalised(run_info or {}),
        )

    def threshold(self, rate: float) -> float:
        """The Threshold at false-alarm rate ``rate``: the k-th largest score,
        k = floor(rate * (n + 1)). If the Calibration Set and a new Stripe-free
        frame are exchangeable, the frame's score exceeds it with probability
        k / (n + 1), about ``rate``.

        The smallest requestable rate is 1 / (n + 1) (0.33% at n = 300); a
        smaller one raises ValueError, and so does a rate outside (0, 1) or one
        too high for n (k > n).

        Ties: the score has an atom at 0.0 (frames with no qualifying region)
        and may repeat. When the k-th largest score is tied with lower ones (for
        example a requested rate above the share of positive scores gives a
        threshold of 0.0), fewer than k scores exceed it, and the realised rate
        is below the request, never above.
        """
        rate = float(rate)
        if not 0.0 < rate < 1.0:
            raise ValueError(f"false-alarm rate must be between 0 and 1 (exclusive), got {rate!r}")
        n = len(self.scores)
        k = threshold_rank(n, rate)
        if k > n:
            raise ValueError(
                f"a false-alarm rate of {rate} is too high for {n} scores: "
                f"at most {n / (n + 1):.6g}"
            )
        return threshold_for_false_alarm_rate(self.scores, rate)

    def digest(self) -> str:
        """SHA-256 (hex) of the canonical JSON of ids, scores, shape and
        settings (sorted keys, no spaces, floats by their shortest repr);
        ``run_info`` is left out."""
        payload = {
            "ids": list(self.ids),
            "scores": list(self.scores),
            "shape": list(self.shape),
            "settings": self.settings,
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        """The Calibration file: format, shape, settings, run_info and one
        ``{id, score}`` per frame, in order."""
        doc = {
            "format": 1,
            "shape": list(self.shape),
            "settings": self.settings,
            "run_info": self.run_info,
            "frames": [{"id": i, "score": s} for i, s in zip(self.ids, self.scores, strict=True)],
        }
        return json.dumps(doc, indent=2, allow_nan=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> Calibration:
        """Read a Calibration file written by ``to_json``. Raises ValueError on
        an unknown format, a non-finite score or a malformed file."""

        def refuse(constant: str) -> float:
            raise ValueError(f"a Calibration file may not contain {constant}")

        try:
            doc = json.loads(text, parse_constant=refuse)
            if doc.get("format") != 1:
                raise ValueError(f"unknown Calibration file format {doc.get('format')!r}")
            frames = doc["frames"]
            return cls.from_scores(
                [f["id"] for f in frames],
                [f["score"] for f in frames],
                (doc["shape"][0], doc["shape"][1]),
                settings=doc.get("settings", {}),
                run_info=doc.get("run_info", {}),
            )
        except (KeyError, TypeError, IndexError, AttributeError) as e:
            raise ValueError(f"malformed Calibration file: {e!r}") from None
