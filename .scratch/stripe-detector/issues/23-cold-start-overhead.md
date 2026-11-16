# 23: Cold-start overhead of the per-frame CLI

**What to build:** Bring the cold per-frame CLI call under ticket 13's 5 s target by cutting process start-up and first-call costs. Prefer fixes that leave the output bit-identical, since those need no re-store. On ticket 13's AC 1 frame at its close (idle machine, `handoffs/13-fixer-bench-record-miss-2.json`):
- the warm pipeline median is 4.03 s;
- the cold CLI median is 5.22 s;
- the CLI import is ~0.35 s (ticket 13, slice 1).

That leaves about 0.85 s per cold call unexplained. Candidates (unmeasured): `scipy.fft` backend and plan set-up on first call, start-up of the bank's thread pool, first-touch allocation of the bank buffers, the TIFF read path, and imports pulled in lazily during `analyse`.

Start by profiling one cold CLI call against one warm call, on the AC 1 frame (`tests/speed.py`), splitting the gap by stage. Take fixes in order of measured share. A fix that moves output goes through CLAUDE.md, "After a score-moving change".

**Blocked by:** 13

**Status:** needs-triage

- [ ] A profile splits the cold-vs-warm gap on the AC 1 frame into named costs.
- [ ] `make bench`'s cold CLI median is at or below `TARGET_TIMING_S` on an idle machine, with output bit-identical to ticket 13's close (or re-stored per CLAUDE.md if not).
- [ ] The tracked `.scratch/stripe-detector/bench.json` is rewritten with the passing record.
