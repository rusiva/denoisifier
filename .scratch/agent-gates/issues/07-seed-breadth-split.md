# 07: Seed-breadth split for the inner loop

**What to build:** `make test-fast` runs every test function and every distinct case, but only the first seeds of each; `make check` keeps running every seed. Today the inner loop takes almost 10 minutes (1009 tests, 712 of them in `tests/test_analyse.py`, nearly all running `analyse` once or more), and an agent pays that after every change. The cost is the number of analyses times the frame size: about 0.8 s at 256x256, about 3 s at 512x512 and about 9 s at 640x1024 (scaled from the bench's 7.3 s at 400x1600; not measured per test). Most tests repeat one check over 10 to 20 seeds, and the threshold sweep runs 18 frames at 6 thresholds. Target: an inner loop of about 2 minutes on an idle machine.

**Evidence, gate time spent in stripe-detector ticket 06** (2026-11-13, from the workers' transcripts; seconds are pytest's summary lines; the machine was not always idle):

| Tier | Runs (s) | Total |
|---|---|---|
| `make test-fast` (full fast tier) | implementer 1: 426.10, 379.89, 360.58; implementer 2: 438.74; implementer 3: 403.67, 575.99; fixer: 571.99, 595.30, plus one stopped at about 240 | about 66 min (lower bound: runs stopped without a summary line are not counted) |
| `pytest -k "spike or clip"` (acceptance subset) | 206.31, 290.41, 268.36 | about 13 min |
| single-file pytest runs | about 15 | about 1 min |
| `make measure` | one run, 47:21 wall | 47 min |
| `make check` | `1009 passed, 4 deselected in 596.42s` | 10 min |
| `make check-slow` | `4 passed, 1009 deselected in 351.82s` | 6 min |
| **All tiers** | | **about 2 h 23 min** |

The inner loop was nearly half of it. Each fast run grew from about 6-7 min to about 10 min as ticket 06 added its tests (1009 tests at the end), and `make check` at the end re-ran the same 1009 tests once more.

**Blocked by:** none

**Status:** ready-for-agent

- [ ] Step 0, before any change: a `--durations=0` run of the fast tier on an idle machine (background, log, 1-minute load below 2). The per-test times go in Comments and set the subset below.
- [ ] A `wide` marker is registered in `[tool.pytest.ini_options]` (`strict_markers` is on). A small helper marks the extra parameters, so `parametrize("seed", inner(SEEDS))` leaves the first seeds unmarked and gives the others `pytest.mark.wide`. The number of unmarked seeds (start: 2) is a named constant in `tests/protected.py`.
- [ ] `make test-fast` selects `not slow and not wide`, and keeps `-x --ff`. `make check` and `make check-slow` select exactly what they select today: the same test ids and counts before and after, quoted in Comments.
- [ ] `make check` still runs every test that `make test-fast` runs.
- [ ] The inner loop keeps every test function, every Period/Angle case, every frame kind (the sweep frames, the spike frames, the size shapes, the dark cases) and every threshold kind. Only seed repetition and cross-products are cut:
  - seed ranges go to their first seeds;
  - the 15 threshold pairs of `test_lowering_the_threshold_keeps_reported_regions_unchanged` go to a subset in which every threshold kind appears;
  - the 640x1024 two-region frame is analysed once in the inner loop (12 times today), and the 512x512 region tests keep two or three cases.
- [ ] A collection-time check fails the run when a test function has only `wide` parameters, so no test can leave the inner loop silently. It has its own test, with a planted all-`wide` function that is not committed.
- [ ] No tolerance, expected value, timeout, seed range or pass count changes. No test is deleted or moved to the slow tier.
- [ ] `make test-fast` takes about 2 minutes on an idle machine, and its slowest test takes about 10 s or less. Comments quote the command, exit status, pytest's summary line, the wall time, the load before and after, and the `--durations` top 10.
- [ ] CLAUDE.md's Gates section says what `make test-fast` now runs, that a seed-specific failure can first appear at `make check`, and that adding `wide` to a parameter is a narrowing move that needs an approval.
- [ ] The ticket ends on the usual sequence: `make check-slow` (the `Makefile` and `pyproject.toml` are stamped files), then `make check`, both quoted.

**Out of scope**

- pytest-xdist. The prototype (`.scratch/agent-gates/xdist-prototype.md`) ruled it out while the slowest fast test takes more than about 10 s serially. Once this ticket is done, `make check` under `-n 4` is worth a new timing run, as its own ticket.
- Analysing each sweep frame once, not once per threshold. It would also shorten `make check`, but it changes how those tests reach the detector. Not decided.
- Smaller region frames. The 512x512 and 640x1024 shapes come from stripe-detector ticket 05's geometry in Periods and are protected numbers.
- Changed-file test selection (pytest-testmon or by path). Every `analyse` test depends on `analysis.py`, so detector tickets would still pay the full run.

**Risk, accepted by the owner:** a defect that shows on one seed only is found at `make check`, at the end of the work, not in the inner loop.

## Comments

### 2026-11-13 — owner approval (recorded by the session that wrote the ticket)

The owner approved the seed-breadth split in conversation, before any change, after reading the proposal and its risk. Reason: the inner loop takes almost 10 minutes after every change, which the owner called unacceptably slow. The approval covers these weakening moves, and only for this ticket's purpose:

1. Narrowing the tests that `make test-fast` selects to `not slow and not wide` (the `Makefile` recipe of `test-fast`).
2. Gate-config edits needed for it: the `wide` marker line in `[tool.pytest.ini_options]`, and the collection-time check if it goes in `tests/conftest.py`.
3. A lockfile addition for the new constant in `tests/protected.py` (no existing line changes).

Not covered: any change to what `make check` or `make check-slow` select, any tolerance, expected value or timeout, and any edit to `tests/slow_stamp.py` or the `check`/`check-slow` recipes. Those need their own approval.

Evidence behind the estimate, 2026-11-13: test counts from `pytest --collect-only`; `.gate/bench.json` (median 7.32 s at 400x1600, commit `b90b64e`); the xdist prototype's serial run (`732 passed, 4 deselected in 441.83s`, 2026-11-12, before ticket 06's tests). The full suite was not timed for this ticket, because another session's `make measure` was running; step 0 does that.
