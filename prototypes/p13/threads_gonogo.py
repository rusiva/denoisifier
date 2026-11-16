"""PROTOTYPE (ticket 13, slice 4; plan section 2): the threads go/no-go timing.

``speed.time_speed_pipeline`` on the AC 1 frame at threads 1 and 4, interleaved (1, 4, 1, 4,
...), five of each, one process, foreground, idle machine. Adopt only if the 4-thread median is
at least 0.3 s below and at most 0.85x the 1-thread median.

    uv run --locked python prototypes/p13/threads_gonogo.py
"""

from __future__ import annotations

import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUNDS = 5


def main() -> int:
    sys.path.insert(0, str(ROOT / "tests"))
    import speed

    print("loadavg start", os.getloadavg())
    times: dict[int, list[float]] = {1: [], 4: []}
    for _ in range(ROUNDS):
        for threads in (1, 4):
            (t,), _report = speed.time_speed_pipeline(1, threads=threads)
            times[threads].append(t)
            print(f"threads {threads}: {t:.3f} s", flush=True)
    print("loadavg end", os.getloadavg())
    m1, m4 = statistics.median(times[1]), statistics.median(times[4])
    ok = (m1 - m4 >= 0.3) and (m4 <= 0.85 * m1)
    print(f"median threads 1 {m1:.3f} s, threads 4 {m4:.3f} s")
    print(f"gain {m1 - m4:.3f} s, ratio {m4 / m1:.3f}")
    print("GO" if ok else "NO-GO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
