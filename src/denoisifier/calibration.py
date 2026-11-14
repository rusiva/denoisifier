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

import functools
import hashlib
import importlib.resources
import json
import multiprocessing
import os
import platform
import time
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy
from numpy.typing import ArrayLike

from denoisifier._calibration import threshold_rank
from denoisifier.frame_io import read_frame
from denoisifier.report import BinFactors

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

    Frames scored at bin factors other than 1x1 record them in ``settings``
    as ``"bin_factors"`` (``calibrate``, ``calibrate_folder``); the
    ``bin_factors`` property reads them back (1x1 when absent).
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

    @property
    def bin_factors(self) -> BinFactors:
        """The bin factors the scores were taken at: ``settings["bin_factors"]``,
        or 1x1 when absent. Raises ValueError when that setting is malformed."""
        if "bin_factors" not in self.settings:
            return BinFactors()
        return BinFactors.from_dict(self.settings["bin_factors"])

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
        # from_scores keeps only finite scores: read the k-th largest directly.
        return float(np.sort(np.asarray(self.scores, dtype=float))[::-1][k - 1])

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


STORED_CALIBRATION_FILE = "stripe_free_calibration.json"


@functools.cache
def stored_calibration() -> Calibration:
    """The Calibration shipped with the package (``STORED_CALIBRATION_FILE``):
    the Stripe Scores of 300 generated Stripe-free 400x1600 frames at typical
    settings (scorched Mottle, about 100 photons at the peak, EMCCD noise, 30
    Spike events per frame, unclipped). Loaded once."""
    text = (
        importlib.resources.files("denoisifier")
        .joinpath(STORED_CALIBRATION_FILE)
        .read_text(encoding="utf-8")
    )
    return Calibration.from_json(text)


def stripe_free_score(
    frame: np.ndarray, *, clip_level: float | None = None, bin_factors: BinFactors | None = None
) -> float:
    """The Stripe Score of ``frame`` as ``analyse`` gives it (spike rejection,
    clip detection, regions), independent of any Threshold: the one scoring
    rule of every calibration path."""
    # Imported here: analysis imports this module for its defaults.
    from denoisifier.analysis import analyse

    return analyse(frame, threshold=np.inf, clip_level=clip_level, bin_factors=bin_factors).score


def _with_bin_factors(settings: Mapping[str, object] | None, bins: BinFactors) -> dict[str, object]:
    """``settings`` plus ``"bin_factors"`` when they are not 1x1 (so 1x1
    settings, and the stored calibration's digest, are unchanged). A
    ``"bin_factors"`` key already in ``settings`` is refused: the recorded
    factors come from ``bin_factors=`` only, the ones the frames were scored at."""
    out = dict(settings or {})
    if "bin_factors" in out:
        raise ValueError(
            "settings may not contain 'bin_factors': pass bin_factors= instead, "
            "which the frames are scored at and which is recorded"
        )
    if bins != BinFactors():
        out["bin_factors"] = bins.to_dict()
    return out


def calibrate(
    frames: Iterable[tuple[str, np.ndarray]],
    *,
    clip_level: float | None = None,
    settings: Mapping[str, object] | None = None,
    run_info: Mapping[str, object] | None = None,
    bin_factors: BinFactors | None = None,
) -> Calibration:
    """A Calibration from ``(id, frame)`` pairs of Stripe-free frames, scored
    serially by ``stripe_free_score``. All frames must have one shape: the
    false-alarm rate depends on it. ``bin_factors`` (default 1x1) are the
    frames' bin factors, passed to ``analyse`` and recorded in ``settings``
    when not 1x1. Raises ValueError on no frames, differing shapes, a
    non-finite score or ``settings`` that already hold ``"bin_factors"``;
    TypeError when ``bin_factors`` is not a ``BinFactors``."""
    bins = BinFactors.of(bin_factors)
    settings = _with_bin_factors(settings, bins)
    ids: list[str] = []
    scores: list[float] = []
    shapes: set[tuple[int, int]] = set()
    for frame_id, frame in frames:
        frame = np.asarray(frame, dtype=float)
        shapes.add((int(frame.shape[0]), int(frame.shape[1])) if frame.ndim == 2 else (0, 0))
        _check_one_shape(shapes)
        ids.append(frame_id)
        scores.append(stripe_free_score(frame, clip_level=clip_level, bin_factors=bins))
    if not ids:
        raise ValueError("no frames to calibrate on")
    (shape,) = shapes
    return Calibration.from_scores(ids, scores, shape, settings=settings, run_info=run_info)


def calibrate_folder(
    folder: str | os.PathLike[str],
    *,
    drop_axis_column: bool = False,
    transpose: bool = False,
    clip_level: float | None = None,
    workers: int = 1,
    bin_factors: BinFactors | None = None,
) -> Calibration:
    """A Calibration from every ``*.csv`` and ``*.asc`` file in ``folder``
    (not recursive; hidden files skipped; sorted by name), read by
    ``read_frame`` with the same options for all, and scored by
    ``stripe_free_score``. Ids are the file names.

    The frames must be Stripe-free and of one shape. Evaluate the result on
    frames other than these: a Calibration Set is never the frames it is
    evaluated on.

    ``workers > 1`` reads and scores the files in a pool of spawned processes;
    a script that calls it so needs the ``if __name__ == "__main__":`` guard.
    ``clip_level`` is passed to ``stripe_free_score`` for every frame (None:
    detected per frame; ``inf``: clip detection off, recorded in ``settings``
    as the text ``"inf"``, since JSON has no infinity). ``bin_factors``
    (default 1x1) are passed to ``analyse`` for every frame and recorded in
    ``settings`` when not 1x1.
    Raises ValueError when ``clip_level`` is NaN, no file matches, a file
    cannot be read (naming the file), or the shapes differ; TypeError when
    ``bin_factors`` is not a ``BinFactors``.
    """
    if clip_level is not None:
        clip_level = float(clip_level)
        if np.isnan(clip_level):
            raise ValueError(f"clip_level must be a number or inf, got {clip_level!r}")
    bins = BinFactors.of(bin_factors)
    root = Path(folder)
    paths = sorted(
        p
        for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in (".csv", ".asc") and not p.name.startswith(".")
    )
    if not paths:
        raise ValueError(f"no .csv or .asc files in {root}")
    t0 = time.perf_counter()
    jobs = [(p, drop_axis_column, transpose, clip_level, bins) for p in paths]
    if workers > 1:
        with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn")) as ex:
            results = list(ex.map(_score_file, jobs))
    else:
        results = [_score_file(job) for job in jobs]
    shapes = {shape for shape, _ in results}
    _check_one_shape(shapes)
    (shape,) = shapes
    settings = _with_bin_factors(
        {
            "source": "folder",
            "drop_axis_column": drop_axis_column,
            "transpose": transpose,
            # JSON has no inf: an infinite clip level (clip detection off) is recorded
            # as its text; None means detected per frame.
            "clip_level": (
                clip_level if clip_level is None or np.isfinite(clip_level) else str(clip_level)
            ),
        },
        bins,
    )
    run_info = {
        "folder": root.resolve().name,
        "workers": workers,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "wall_clock_s": time.perf_counter() - t0,
    }
    return Calibration.from_scores(
        [p.name for p in paths],
        [score for _, score in results],
        shape,
        settings=settings,
        run_info=run_info,
    )


def _score_file(
    job: tuple[Path, bool, bool, float | None, BinFactors],
) -> tuple[tuple[int, int], float]:
    path, drop_axis_column, transpose, clip_level, bin_factors = job
    try:
        frame = read_frame(path, drop_axis_column=drop_axis_column, transpose=transpose).frame
        return (int(frame.shape[0]), int(frame.shape[1])), stripe_free_score(
            frame, clip_level=clip_level, bin_factors=bin_factors
        )
    except (OSError, ValueError) as e:
        raise ValueError(f"{path.name}: {e}") from e


def _check_one_shape(shapes: set[tuple[int, int]]) -> None:
    if len(shapes) > 1:
        raise ValueError(
            f"frames of differing shapes {sorted(shapes)}: a Calibration holds one shape, "
            "since the false-alarm rate depends on it"
        )
