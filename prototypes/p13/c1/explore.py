"""PROTOTYPE (ticket 13, slice 7): the persisted C1 explore set.

Ticket 09's explore BASE (``explore_v2.pkl``, 1796 records: ``p2/all_explore.pkl`` plus
``base_v2extra.pkl``; ``.scratch/stripe-detector/handoffs/.archived/09-prototyper-3.md``) is
kept outside the repo at ``CACHE`` (git-ignored by location, survives a reboot). C1 uses its
216 frames on the ``full_break``, ``fullcap``, ``pair*`` and ``bin*`` tags. Each record holds
the job (seed, kind, breaks, bins, tag), the true breaks and ticket 09's BASE outputs; the frame
itself is regenerated from the job (``prototypes/p13/c1/frames.py``).

Recipe when the cache is lost (deterministic; check the 216-frame subset's jobs and truth
against a surviving copy with ``SHA256`` if both exist):

    git worktree add <scratch>/p09 108e150
    cd <scratch>/p09
    uv run --locked python prototypes/p09_breaks/harness2.py <out> explore
    uv run --locked python prototypes/p09_breaks/harness2.py <out> v2extra
    # concatenate base_explore.pkl + base_v2extra.pkl (list + list) -> explore_v2.pkl

Verbatim copies of ticket 09's ``harness2.py`` and ``eval2.py`` (outside ruff's scope) are in
``.scratch/stripe-detector/p13-c1-ref/``; eval2's ``match`` is the line-error metric.

Cleanup (review N8): delete ``~/.cache/denoisifier/p13-c1/`` at ticket 13's close, or, if
slice 7 is dropped, at the close of the finder follow-up ticket that names it.
"""

import hashlib
import pickle
from pathlib import Path
from typing import Any

CACHE = Path.home() / ".cache" / "denoisifier" / "p13-c1" / "explore_v2.pkl"
SHA256 = "8234cab3c369d6fb22fb0e6db30f71caa153e821d8b7b3f4f69f5a045d032056"
SIZE = 334_506_898
C1_TAGS = ("full_break", "fullcap", "pair", "bin")


def sha256(path: Path = CACHE) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(tags: tuple[str, ...] = C1_TAGS, verify: bool = False) -> list[dict[str, Any]]:
    """The explore records whose tag starts with one of ``tags``."""
    if verify and sha256() != SHA256:
        raise RuntimeError(f"{CACHE} does not match the recorded sha256")
    with CACHE.open("rb") as f:
        records: list[dict[str, Any]] = pickle.load(f)  # trusted: written by ticket 09's harness
    return [r for r in records if r["job"]["tag"].startswith(tags)]


if __name__ == "__main__":
    print(CACHE, CACHE.stat().st_size == SIZE, sha256() == SHA256, len(load()))
