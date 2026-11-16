# Ticket 10 code-review fix list (review base ca48498, HEAD 41739a3)

Sources: standards review S1-S14, spec review P1-P3 (orchestrator log, Workers section; findings quoted below by id).

Constraint for every detector-code fix (`src/denoisifier/_local_phase.py`, `analysis.py`): behaviour must be bit-identical. Prove it with the all-seed fork run (`uv run --locked pytest tests/test_analyse.py tests/test_cli.py -k fork`) plus `tests/test_local_phase.py` and `tests/test_phase_break_pass.py` green, and do not touch the score path (`_merge`, `_compatible`, anything before the break pass). If a refactor would change any output, drop it and record it as passed with the reason.

## Fix
- S1 `tests/test_analyse.py:2147` literal `atol=1e-12`: move to `tests/protected.py` as a named protected number (+ lockfile line; new pin, not a weakening).
- S2 `src/denoisifier/synthetic.py:164` "the spec's charge": define by split direction as the OQ1 ruling words it (you may cite spec.md's charge as the equal frame-coordinate quantity, as the GLOSSARY does, but don't define by it).
- S3 `_local_phase.py:659` `ok` -> a descriptive name (e.g. `loop_valid`).
- S4 `_local_phase.py:675` hand conversion `(cy[k] + r0) * v` -> `sensor_coordinates`; `tests/test_analyse.py:2324` use `truth_match`'s helper instead of re-rolling it. Only if bit-identical.
- S5 bounding-box crop `flatnonzero(x.any(axis=...))`: one helper in `_local_phase.py`, used by the `_local_phase.py` sites (411/545/615). Leave `analysis.py:1063` alone if it is on the score path or outside the break/fork pass.
- S6 `find_forks` winding box sum -> `_box_sum`. Only if bit-identical.
- S7 (second half only) `_pre_break_forks` / `_post_break_forks` share one search helper (owned -> fork_domain -> response -> find_forks -> evidence filter). The `_Responses`/`_ForksExplained` memo shape: pass (two small classes, reads clearly).
- S8 one "refused region" rule (`analysis.py:489` vs `:514`): one helper, both sites.
- S9 renames: `g` band half-width (`_local_phase.py:723`), `sb`, `w`, `p`, `s` in `find_forks`/`_stepped_across`, `_k` in `tests/forks.py:43`. Use GLOSSARY terms.
- S10 `(1, -1)[seed % 2]` at `tests/test_analyse.py:2177`, `:2434` -> `forks.ac2_direction`.
- S11 `test_frame_with_forks_is_striped` -> use `truth_match.fork_problems` matching.
- S13 drop the `_pytest` private import (`tests/test_analyse.py:11`); duck-type on `.values`/`.marks` or use `pytest.param` objects' public API.
- S14 `analysis.py:429` placeholder-less f-string.
- P1 add the joined case to `test_refused_regions_are_not_searched_for_forks`: a refused region joined into a searchable one gets no post-break search (spy on `find_forks`); test first, it must fail if the overlap check at `analysis.py:497` is removed.
- P2 `test_frame_with_forks_is_striped`: assert a matched Fork exists before checking the domain clause.

## Pass
- S7 memo shape: two small, clear classes; extraction adds indirection for no gain.
- S12 `ForkPoint` == `ForkTruth` fields: kept for symmetry with `BreakLine`/`BreakTruth`; the truth type is the generator's return contract and may grow (as BreakTruth's `shifted`).
- P3 identity vs BASE has no committed test: the plan (5.2, 5.4) specified the patched-current form; the step-6 BASE diff is the evidence. Record the step-6 result (27 frames, what differed) in the ticket Comments if not already there.

## Close-out (after fixes, in this order)
1. Ticket Comments: fixer entry listing each fix/pass id with one line, and the gate quotes below.
2. Gates (CLAUDE.md, plan step 10): scores not meant to move, so NO `make measure`. `make bench` (background, idle) -> `make check-slow` (background, idle, ~16-20 min) -> `make check`. Quote each: command, exit, pytest summary line, `git rev-parse --short HEAD` (+ -dirty). If `make check-slow`'s regression or calibration (AC 7) goes red, stop and report: that is a finding, not a re-store.
3. Tick the ticket's AC checkboxes that the green gates back; leave `Status:` as the repo's convention for closed tickets (check what 09 did).
