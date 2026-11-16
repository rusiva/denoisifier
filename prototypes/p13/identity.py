"""PROTOTYPE (ticket 13, plan section 3.1): the equality harness. Kept for the ticket.

Runs ``analyse`` on a fixed frame set (seeds 601_000-601_099) in a given source tree and
pickles each frame's report and ``LocalStripes``; then compares two such runs.

    # frames once (working tree generator), then a run per tree, then the comparison
    uv run --locked python prototypes/p13/identity.py frames <dir>
    git worktree add <scratch>/ref <commit>
    uv run --locked python prototypes/p13/identity.py run <scratch>/ref/src <dir> ref.pkl
    uv run --locked python prototypes/p13/identity.py run src <dir> new.pkl [threads]
    uv run --locked python prototypes/p13/identity.py compare ref.pkl new.pkl exact|tol

``run`` puts the given ``src`` first on ``sys.path``, so ``denoisifier`` is imported from
that tree. ``exact`` is plain equality of every field (floats exactly, arrays
``array_equal`` with NaN equal). ``tol`` prints one pass/fail row per criterion (``tol.py``).
"""

from __future__ import annotations

import math
import os
import pickle
import sys
from pathlib import Path
from typing import Any

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

ROOT = Path(__file__).resolve().parents[2]
SEED_BASE = 601_000
FRAME_SHAPE = (400, 1600)


def _frames() -> list[tuple[str, Any, tuple[int, int]]]:
    """(name, frame, (horizontal, vertical) bins), generated with the working tree."""
    sys.path.insert(0, str(ROOT / "tests"))
    import numpy as np

    import feasibility  # its frame recipe is the bench timing frame
    from binning import bin_sensor_frame
    from cases import CASES
    from denoisifier.synthetic import Emccd, ForkPoint, PhaseBreakLine, generate
    from regions import single_region

    emccd = Emccd()
    full = dict(modulation_depth=0.5, mottle="scorched", noise=emccd)
    out: list[tuple[str, Any, tuple[int, int]]] = []

    a = 3.0
    worst = generate(
        seed=SEED_BASE,
        shape=FRAME_SHAPE,
        period=3.0,
        angle_deg=a,
        spikes=30,
        phase_breaks=[
            PhaseBreakLine((130.0, 500.0), a + 4.0, math.pi),
            PhaseBreakLine((280.0, 1100.0), a - 3.0, -2.0),
        ],
        forks=[ForkPoint((200.5, 800.5), 1)],
        **full,
    )
    out.append(("ac1_worst", worst.frame, (1, 1)))
    typ = generate(
        seed=SEED_BASE + 1, shape=FRAME_SHAPE, period=6.0, angle_deg=-5.0, spikes=30, **full
    )
    out.append(("typical_p6", typ.frame, (1, 1)))
    bench = feasibility._frame(
        feasibility.TIMING_SEED,
        feasibility.DEPTH,
        feasibility.PROBE.shape,
        feasibility.TIMING_CASE,
    )
    out.append(("bench_timing", bench, (1, 1)))

    for k in range(10):
        s = SEED_BASE + 10 + k
        c = CASES[s % 10]
        f = generate(seed=s, shape=FRAME_SHAPE, period=c.period, angle_deg=c.angle_deg, **full)
        out.append((f"full_{s}", f.frame, (1, 1)))
    region_kw = dict(shape=(512, 512), mottle="scorched", noise=emccd)
    for k in range(10):
        for kind, base in (("region", 20), ("break", 30), ("fork", 40), ("breakfork", 50)):
            s = SEED_BASE + base + k
            c = CASES[s % 10]
            reg = single_region(c.period, c.angle_deg)
            cy, cx = reg.center
            breaks, forks = [], []
            if kind in ("break", "breakfork"):
                breaks = [PhaseBreakLine((cy, cx), float(c.angle_deg), math.pi)]
            if kind == "fork":
                forks = [ForkPoint((cy, cx), 1)]
            if kind == "breakfork":
                forks = [ForkPoint((cy + round(3 * c.period), cx), -1)]
            f = generate(seed=s, regions=[reg], phase_breaks=breaks, forks=forks, **region_kw)
            out.append((f"{kind}_{s}", f.frame, (1, 1)))

    for s, (h, v) in ((SEED_BASE + 62, (2, 1)), (SEED_BASE + 63, (1, 2))):
        c = CASES[s % 10]
        sensor = (FRAME_SHAPE[0] * v, FRAME_SHAPE[1] * h)
        f = generate(seed=s, shape=sensor, period=c.period, angle_deg=c.angle_deg, **full)
        out.append((f"bin{h}x{v}_{s}", bin_sensor_frame(f.frame, h, v), (h, v)))
    s = SEED_BASE + 64
    c = CASES[s % 10]
    clean = generate(seed=s, shape=FRAME_SHAPE, period=c.period, angle_deg=c.angle_deg, **full)
    level = 0.8 * float(clean.clean.max())
    f = generate(
        seed=s,
        shape=FRAME_SHAPE,
        period=c.period,
        angle_deg=c.angle_deg,
        clip_level=level,
        **full,
    )
    out.append((f"clipped_{s}", f.frame, (1, 1)))
    s = SEED_BASE + 65
    c = CASES[s % 10]
    f = generate(seed=s, shape=(256, 256), period=c.period, angle_deg=c.angle_deg, **full)
    out.append((f"crop256_{s}", f.frame, (1, 1)))
    s = SEED_BASE + 66
    f = generate(seed=s, shape=FRAME_SHAPE, regions=(), mottle="scorched", noise=emccd, spikes=30)
    out.append((f"free_{s}", f.frame, (1, 1)))
    assert all(np.isfinite(fr).all() for _, fr, _ in out)
    return out


def write_frames(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    frames = _frames()
    with (directory / "frames.pkl").open("wb") as f:
        pickle.dump(frames, f, protocol=5)
    print(f"wrote {len(frames)} frames to {directory / 'frames.pkl'}")


_THREADS: int | None = None
TIE_GAP_KEPT = 1e-6


def _one(item: tuple[str, Any, tuple[int, int]]) -> tuple[str, dict[str, Any]]:
    import dataclasses

    import numpy as np

    from denoisifier import analysis
    from denoisifier.report import BinFactors

    name, frame, (h, v) = item
    captured: list[Any] = []
    original = analysis.estimate_local_stripes

    def capture(*args: Any, **kw: Any) -> Any:
        local = original(*args, **kw)
        captured.append(local)
        return local

    analysis.estimate_local_stripes = capture
    from denoisifier import _local_stripes

    original_match = _local_stripes._match_period
    tie: dict[str, Any] = {}

    def match(spec: Any, p: float, light: Any, buffers: Any) -> Any:
        # The top-two stripe energy gap (e1 - e2) / e1 at the winning Period, recomputed from the
        # stripe responses left in the buffers (np.abs then square, as the bank does).
        m = original_match(spec, p, light, buffers)
        e = np.abs(buffers.stripe) ** 2
        top2 = np.sort(e, axis=0)[-2:]
        with np.errstate(invalid="ignore", divide="ignore"):
            gap = (top2[1] - top2[0]) / top2[1]
        if "best" not in tie:
            tie["best"] = np.zeros(light.shape)
            tie["gap"] = np.full(light.shape, np.inf)
        better = m.ratio > tie["best"]
        tie["best"][better] = m.ratio[better]
        tie["gap"][better] = gap[better]
        return m

    _local_stripes._match_period = match
    try:
        bins = BinFactors(horizontal=h, vertical=v)
        if _THREADS is not None:
            private = analysis._analyse
            report = private(frame, bin_factors=bins, threads=_THREADS)
        else:
            report = analysis.analyse(frame, bin_factors=bins)
    finally:
        analysis.estimate_local_stripes = original
        _local_stripes._match_period = original_match
    (local,) = captured
    near = np.nonzero(tie["gap"] < TIE_GAP_KEPT)
    rec = {
        "report": dataclasses.asdict(report),
        "local": {k: np.asarray(getattr(local, k)) for k in dataclasses.asdict(local)},
        # Pixels whose top-two stripe energy gap at the winning Period is below TIE_GAP_KEPT.
        "tie_gap": (near, tie["gap"][near]),
    }
    return name, rec


def _init(src: str, threads: int | None) -> None:
    global _THREADS
    sys.path.insert(0, src)
    _THREADS = threads
    import denoisifier

    assert str(Path(denoisifier.__file__).resolve()).startswith(src), denoisifier.__file__


def run(src: Path, directory: Path, out: Path, threads: int | None, workers: int) -> None:
    import multiprocessing

    with (directory / "frames.pkl").open("rb") as f:
        frames = pickle.load(f)
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(workers, initializer=_init, initargs=(str(src.resolve()), threads)) as pool:
        results = dict(pool.imap(_one, frames, chunksize=1))
    with out.open("wb") as f:
        pickle.dump(results, f, protocol=5)
    print(f"wrote {len(results)} records to {out} (src {src}, threads {threads})")


def _equal(a: Any, b: Any, path: str, diffs: list[str]) -> None:
    import numpy as np

    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        a, b = np.asarray(a), np.asarray(b)
        if a.shape != b.shape or a.dtype != b.dtype or not np.array_equal(a, b, equal_nan=True):
            diffs.append(f"{path}: arrays differ")
    elif isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            diffs.append(f"{path}: keys {sorted(a)} != {sorted(b)}")
            return
        for k in a:
            _equal(a[k], b[k], f"{path}.{k}", diffs)
    elif isinstance(a, list | tuple) and isinstance(b, list | tuple):
        if len(a) != len(b):
            diffs.append(f"{path}: length {len(a)} != {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _equal(x, y, f"{path}[{i}]", diffs)
    elif isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return
    elif type(a) is not type(b) or a != b:
        diffs.append(f"{path}: {a!r} != {b!r}")


def compare_exact(ref: dict[str, Any], new: dict[str, Any]) -> bool:
    diffs: list[str] = []
    _equal(ref, new, "", diffs)
    for d in diffs[:40]:
        print("DIFF", d)
    print(
        f"exact: {len(ref)} frames, {len(diffs)} differences -> {'PASS' if not diffs else 'FAIL'}"
    )
    return not diffs


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "frames":
        write_frames(Path(argv[1]))
        return 0
    if cmd == "run":
        threads = int(argv[4]) if len(argv) > 4 and argv[4] != "-" else None
        workers = int(argv[5]) if len(argv) > 5 else 4
        run(Path(argv[1]), Path(argv[2]), Path(argv[3]), threads, workers)
        return 0
    if cmd == "compare":
        with Path(argv[1]).open("rb") as f:
            ref = pickle.load(f)
        with Path(argv[2]).open("rb") as f:
            new = pickle.load(f)
        if argv[3] == "exact":
            return 0 if compare_exact(ref, new) else 1
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import tol

        return 0 if tol.compare(ref, new, argv[4] if len(argv) > 4 else "slice5") else 1
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
