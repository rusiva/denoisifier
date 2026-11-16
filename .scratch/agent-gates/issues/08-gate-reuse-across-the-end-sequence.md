# 08: Reuse work across the heavy end sequence

**What to build:** Cut the wall time of the end-of-ticket gate sequence a score-moving ticket runs (CLAUDE.md, Gates: `make measure` → the stripe calibration driver → the break/Fork driver → `make check-slow` → `make check-held-out` → `make bench` → `make check`). Each step generates its own synthetic frames and analyses them from scratch, though several look at the same frames under the same detector code. As a result, every score-moving lever costs about 2.5-3 h of gates, and ticket planning now drops or defers levers on that cost alone (stripe-detector ticket 13, slices 6-8 and follow-ups 19-21: "each extra score-moving lever costs its own ~3 h re-store"). The owner, 2026-11-16: "that is truly insane how slow the gates have become".

**Evidence, stripe-detector ticket 13's end sequence** (2026-11-16, wall clock from commit and `.gate/` timestamps, idle machine apart from the gate itself, 12 pool workers). These runs already include ticket 13's detector speedup (single-thread analyse 6.8 → about 4.6 s, bank threads capped at 1 in pools):

| Step | Wall | CLAUDE.md budget |
|---|---|---|
| `make measure` (after the review fixes' `make test-fast`) | under 26 min (11:27 → 11:53, including that test-fast) | ~39 min |
| stripe calibration driver | ~10 min (11:53 → 12:03) | ~14 min |
| break/Fork calibration driver | ~8 min (12:03 → 12:11) | ~13 min |
| `make check-slow` | ~14 min (12:12 → 12:26) | 22-23 min |
| `make check-held-out` | ~36 min (12:26 → 13:02) | ~60 min |
| `make bench`, bench record, `make check` | not yet measured | |

The CLAUDE.md budgets are now stale. Re-state them from fresh idle runs as part of this ticket.

**Candidate levers (unmeasured; prototype before choosing):**
1. **Analysis cache:** store per-frame results keyed by a hash of the stamped detector files (`tests/slow_stamp.py` already computes one), the generator recipe and the seed. A gate step then re-uses frames an earlier step scored under identical code. It must never give a stale pass: the key covers every input, a key miss recomputes, and a test proves an edit to any stamped file invalidates the cache.
2. **Feed measure into the drivers:** `make measure` and the calibration drivers share frame recipes. Let the drivers read measure's scores where seeds and code match, rather than regenerate them.
3. **Skip held-out when nothing moved:** `make check-held-out` re-runs only when the package calibration digests (`PACKAGE_CALIBRATION_DIGEST`, `PACKAGE_BREAK_FORK_CALIBRATION_DIGEST`) or the stamped detector code changed since its last green run. That is a narrowing move, so the owner decides.
4. **Profile first:** find how much of each step is generation, analysis or pool start-up. Workers spawn and import scipy per pool, and calibration seeds go through the seed guard. Then pick levers by measured share.

**Constraints:** every lever here edits gate config or the seed guard's surroundings, so each is a weakening move under CLAUDE.md and needs an approval with its reason in Comments. A cache must not cross the seed guard: held-out and calibration seeds never become visible to a step that must not see them. The slow-tier stamp's guarantee stays intact.

**Blocked by:** none (stripe-detector ticket 13 should close first, so the timings above are taken on the final detector)

Status: needs-triage

- [ ] A profile of one full end sequence on an idle machine splits each step's time into generation, analysis and overhead.
- [ ] The chosen levers cut the full sequence's wall time by a stated, measured amount, with every gate's verdict unchanged on a reference run.
- [ ] A test shows a cached result is invalidated by any change to a stamped file or a frame recipe.
- [ ] The CLAUDE.md durations are re-stated from measured runs.

## Comments
