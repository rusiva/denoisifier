"""PROTOTYPE (ticket 13, slice 4b; orchestrator ruling 2026-11-16): the bank's mirror-tie bound.

Reflect padding makes a frame's edge rows and columns mirror lines: there the stripe filters at
+theta and -theta give conjugate responses, so their energies tie up to rounding. This measures,
on every harness frame (``identity.py frames``) and every searched bank Period, the relative
energy difference |e(+t) - e(-t)| / max(e(+t), e(-t)) of the pairs (+-5, +-10) on the mirror
lines (frame rows 0 and H-1, columns 0 and W-1), and, for candidate tie widths eps, how many
pixels anywhere would change their Angle index under "within eps of the max counts as tied,
first index wins".

    uv run --locked python prototypes/p13/tie_bound.py <src> <frames dir> [workers] [float32]

``float32`` runs the bank filters in complex64 (slice 6's rounding) for the same bound.
"""

from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path
from typing import Any

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

CANDIDATES = (1e-12, 1e-11, 1e-10, 1e-9, 1e-8, 1e-7, 1e-6, 1e-5)
_SINGLE = False


def _init(src: str, single: bool) -> None:
    global _SINGLE
    sys.path.insert(0, str(Path(src).resolve()))
    _SINGLE = single


def _one(item: tuple[str, Any, tuple[int, int]]) -> dict[str, Any]:
    import numpy as np

    from denoisifier import analysis
    from denoisifier._data_quality import reject_spikes
    from denoisifier._local_stripes import _STRIPE_ANGLES_DEG, _Spectrum, searched_periods
    from denoisifier.report import BinFactors

    name, frame, (h, v) = item
    bins = BinFactors(horizontal=h, vertical=v)
    work, _ = reject_spikes(np.asarray(frame, dtype=float))
    light = analysis._light(work)
    spec = _Spectrum(work, bins)
    if _SINGLE:
        spec.f = spec.f.astype(np.complex64)
    height, width = work.shape
    mirror = np.zeros(work.shape, dtype=bool)
    mirror[[0, height - 1], :] = True
    mirror[:, [0, width - 1]] = True
    angles = list(_STRIPE_ANGLES_DEG)
    pairs = [(angles.index(-a), angles.index(a)) for a in angles if a > 0]
    worst_mirror = 0.0
    worst_mirror_light = 0.0
    decades = np.zeros(19, dtype=np.int64)  # log10 rel diff in [-18, 0], exact 0 in bin 0
    by_period: dict[float, float] = {}
    changed = dict.fromkeys(CANDIDATES, 0)
    changed_off_mirror = dict.fromkeys(CANDIDATES, 0)
    for p in searched_periods(bins):
        energy = np.stack([np.abs(spec.gabor(p, a)) ** 2 for a in angles])
        for i, j in pairs:
            top = np.maximum(energy[i], energy[j])
            rel = np.divide(
                np.abs(energy[i] - energy[j]), top, out=np.zeros_like(top), where=top > 0
            )
            worst_mirror = max(worst_mirror, float(rel[mirror].max()))
            on = rel[mirror & light]
            if on.size:
                d = np.clip(np.floor(np.log10(np.maximum(on, 1e-18))).astype(int) + 18, 0, 18)
                decades += np.bincount(d, minlength=19)
                by_period[float(p)] = max(by_period.get(float(p), 0.0), float(on.max()))
            if (mirror & light).any():
                worst_mirror_light = max(worst_mirror_light, float(rel[mirror & light].max()))
        first = np.argmax(energy, axis=0)
        e_max = energy.max(axis=0)
        for eps in CANDIDATES:
            tied = np.argmax(energy >= e_max * (1 - eps), axis=0)
            diff = tied != first
            changed[eps] += int(diff.sum())
            changed_off_mirror[eps] += int((diff & ~mirror).sum())
    return dict(
        name=name,
        worst_mirror=worst_mirror,
        worst_mirror_light=worst_mirror_light,
        changed=changed,
        decades=decades,
        by_period=by_period,
        changed_off_mirror=changed_off_mirror,
    )


def main(argv: list[str]) -> int:
    import multiprocessing

    src, directory = argv[0], Path(argv[1])
    workers = int(argv[2]) if len(argv) > 2 else 8
    single = len(argv) > 3 and argv[3] == "float32"
    with (directory / "frames.pkl").open("rb") as f:
        frames = pickle.load(f)  # trusted: written by identity.py frames
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(workers, initializer=_init, initargs=(src, single)) as pool:
        rows = pool.map(_one, frames, chunksize=1)
    worst = max(r["worst_mirror"] for r in rows)
    worst_light = max(r["worst_mirror_light"] for r in rows)
    print(f"{len(rows)} frames, {'complex64' if single else 'complex128'} bank filters")
    print(f"max mirror-pair relative energy difference: {worst:.3e} (light px {worst_light:.3e})")
    top = sorted(rows, key=lambda r: -r["worst_mirror"])[:5]
    print("worst frames: " + ", ".join(f"{r['name']} {r['worst_mirror']:.2e}" for r in top))

    dec = sum(r["decades"] for r in rows)
    print("mirror-line light px (all pairs, Periods) by decade of the relative difference:")
    print("  " + ", ".join(f"1e{k - 18}: {int(n)}" for k, n in enumerate(dec) if n))
    periods = sorted({p for r in rows for p in r["by_period"]})
    print(
        "max per Period (light mirror px): "
        + ", ".join(
            f"{p:.2f}: {max(r['by_period'].get(p, 0.0) for r in rows):.1e}" for p in periods
        )
    )
    print("| eps | px whose Angle index changes (all Periods) | of which off the mirror lines |")
    print("|---|---|---|")
    for eps in CANDIDATES:
        n = sum(r["changed"][eps] for r in rows)
        off = sum(r["changed_off_mirror"][eps] for r in rows)
        print(f"| {eps:.0e} | {n} | {off} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
