# 07 plan: adversarial critique of Q1-Q9

Critic, fresh context, 2026-11-14. Read: the ticket (working tree), CLAUDE.md Gates, `07-plan.md`, `07-orchestrator.md`, `src/denoisifier/` (`analysis.py`, `_calibration.py`, `synthetic.py`, `cli.py`, `__init__.py`), `tests/protected.py`, `tests/feasibility.py`, `tests/slow_stamp.py`, `tests/test_slow_regression.py`, `Makefile`, `pyproject.toml`, `feasibility-gate.json`, `.gate/check-slow-measurement.json`, `docs/regression-plan.md`, spec.md, agent-gates ticket 05 and its orchestrator log, ticket 06 Comments. Numbers recomputed with scipy (`uv run --locked python`); no generator or detector run, no seed looked at.

"Owner" below means: taste between equivalent options, knowledge not in the repo, or hard to revert.

## Summary

| Q | Plan's choice | Verdict | Owner |
|---|---|---|---|
| Q1 | 400x1600 only | Right | no |
| Q2 | 300/300/100, all in check-slow | Sizes right; the cost is understated and it reverses an owner ruling | **yes** |
| Q3 | 30 spikes per frame | Right; the choice is immaterial at this calibration's precision | no (tell the owner) |
| Q4 | keep the score, follow-up issue | Right | no |
| Q5 | one-off clipped measurement + scope | Right | no |
| Q6 | full API surface | Mostly right; drop or rename `Report.false_alarm_rate`; do not use `python -m denoisifier.calibration` | no |
| Q7 | exact equality | Right, with a diagnostic in the failure message | no |
| Q8 | skip `make measure` | Right, with a stated proof | no |
| Q9 | same threshold for every shape, documented | Right | no |

Serious problems outside Q1-Q9: E1 (runtime and timeout), E2 (wrong fact about the real fixture), E3 (`or` on the rate), E4 (`python -m` on a module the package imports), E5 (no rule for a red closing run), E6 (wrong power numbers at 5%). Details at the end.

## Number checks

Recomputed; all match the plan unless marked.

- k = floor(r x 301): 3 and 15. Correct.
- Beta(3, 298) central 95%: 0.207%-2.387%. Beta(15, 286): 2.83%-7.71%. Correct.
- betabinom(300, 3, 298) at level 0.995: (0, 13), false red 0.186%. betabinom(300, 15, 286): (3, 33), false red 0.294%. Correct.
- At level 0.95: (0, 9) with 1.84% and (6, 27) with 3.73%. Correct.
- P(pass 2a) at a true 3% / 4% / 5%: 92.9% / 68.4% / 35.8%. Correct.
- **Wrong:** P(pass 2b) "at 10%: 34%; at 12%: <5%". Binomial(300, p) in [3, 33] gives **75% at 10%, 34% at 12%, 7.5% at 14%, 2.8% at 15%**. The plan's figures are shifted by two points. 2b is weaker than the plan says.
- 2b when a 5% request gets the 1% threshold: P(count >= 3) = 50%. The plan says "the edge"; it is a coin flip, so 2b gives no protection there. The fast option test and the unit test of k carry it, as the plan says.
- AC 3: pass-bad 9.9% at 0.85, 0.57% at 0.80; false red 1.15% at 0.95, 0.02% at 0.97, 0.10% at 0.964. Correct.
- n = 1000: k = 10, Beta(10, 991) = 0.48%-1.70%. Correct.
- Clipped one-off: betabinom(200, 3, 298) at 0.995 = (0, 10); P(<= 10 | 3%) = 96%. Correct.
- Spikes: 30 per 256x256 is 293 per 400x1600 (640 000 / 65 536 = 9.77). Correct.
- Seed ranges 100_000-104_099: nothing registered between 95_300 and 300_001. Correct.
- Detector code since the last measure (`git diff --stat fd59d0c HEAD -- src tests/feasibility.py`): empty. Correct, and it supports Q8.
- **Runtime: understated.** See E1.

## Q1: frame shape of the shipped calibration

Against the plan: under (a) nearly every frame in the repo's own tests (256x256, 512x512, 640x1024) is analysed at a threshold calibrated for another shape, so the default rate claim is checked on one shape only. "Conservative on crops" is an expectation, not a measurement: a 256x256 generated frame is not a crop of a 400x1600 frame. And 640x1024 has slightly more pixels than 400x1600.

For the plan:
- Repo data support the direction: the 1% threshold is 49.7 at 256x256 and 85.2 at 400x1600; of 850 fresh 256x256 frames the highest score is 101.5 and 4 exceed 49.7, so at about 85 the 256x256 rate is far below 1%.
- Sensitivity on small frames improves against today: the default drops from 154 to about 85.
- 02 plan section 10 already recorded "ticket 07 calibrates at the real frame size", and spec story 34 names 1600x400 as the full sensor.
- (b) is wrong on real frames, (c) doubles the recurring cost and still leaves other shapes open, (d) is a detector change.

Verdict: (a). Write "expected lower on crops" in the docs, not "at most 1%" as a guarantee; say that a larger light area than the calibration's is not covered.

Owner: no. The stored format records its shape and no user holds a calibration file yet (version 0.1.0), so a later table or area correction is a data and loader change.

## Q2: sample sizes, and where the held-out tests run

The sizes are defensible. The placement is not the planner's or the orchestrator's to decide.

1. **It reverses an owner ruling.** Agent-gates ticket 05, "Slow-tier shrink (owner ruling, 2026-11-10)": the compulsory `check-slow` is a regression check at stored thresholds, "not stripe-detector ticket 03 at full precision". The 05 orchestrator then ruled O1 = B on the strength of the owner's "small" and "about 6 min", and refused a 15 min variant. agent-gates spec problem 9 names the old 40 min slow tier as the thing to remove. The plan puts check-slow back at about 40 min.
2. **The cost is higher than +28 min** (E1): +32 to +41 min by `make measure`'s own measured rate, so check-slow is about 38-47 min idle and up to twice that under load. Every worktree and every later ticket that edits a stamped file pays it (`tests/protected.py` is stamped whole, so any test-seed edit pays it).
3. **The recurring held-out runs buy little.** Seeds are fixed, so AC 2 and AC 3 are deterministic functions of the stored file, the detector and the generator. AC 7's exact per-seed reproduction turns red on any change to stripe-free scores before AC 2 can move. The existing regression check already guards weak-stripe detection on fresh seeds. What the recurring 400 held-out frames add is a full-frame detection check with spikes at the shipped threshold; AC 2a at (0, 13) of 300 has almost no power of its own (93% pass at a true 3%).
4. AC 7 is an owner ruling too, so the reproduction (300 full frames, about +14-17 min) is in check-slow whatever is chosen. check-slow cannot stay at 6 min under any option; the owner should know that.
5. Moving the held-out tests out of `-m slow` (option c) is a Makefile and marker edit, an owner approval by CLAUDE.md. So both (a) and (c) need the owner.

n = 300 or 1000: n = 1000 would cost +46 to +58 min for the reproduction alone on every check-slow. Not worth it for a synthetic calibration that real frames are meant to replace. Keep 300, and state plainly that the shipped "1%" is known to 0.2%-2.4%, and that the smallest rate a user can request is 1/301 = 0.33%.

Verdict: keep 300 / 300 / 100. Ask the owner one question with real costs:
- (a) everything in check-slow: about 38-47 min idle per run;
- (c) reproduction only in check-slow (about 20-23 min), held-out AC 2 and AC 3 run at milestones with `make measure` (about +20 min there) and once at this ticket's close.

My recommendation is (c): the reproduction already pins the stripe-free scores exactly. Whichever is chosen, AC 6 ("marked slow") is met.

Owner: **yes**. It is a gate-time budget that overrides an earlier owner ruling, and (c) needs an owner approval anyway.

## Q3: spikes per calibration frame

Against the plan: the repo holds no real spike rate (spec says only "typical settings are scorched mottle and about 100 photons"; the ticket adds "spikes present" with no count). 30 is a guess, and physically a high one: sea-level cosmic-ray rates on silicon are a few events per cm² per minute, and the Newton 971 sensor is 1.64 cm², so a seconds-long exposure sees fewer than one event.

For the plan:
- The choice barely moves the threshold. 30 events of at most 3 pixels is at most 90 of 640 000 pixels (0.014%). Ticket 06 measured a median paired score change of 0.18-1.35 with spikes. The threshold itself is the 3rd largest of 300 and is uncertain by a factor of about 3 in rate. The spike count is well inside that noise.
- 293 (option b) is 0.14% of the pixels, near the 0.3% at which critic 3 saw gating jumps of 15-39 points. That is a stress setting, not a typical one.
- 30 still exercises spike rejection on every calibration frame, which is the ticket's point. A realistic 0-1 would leave it almost untested.
- Recalibration on real frames (story 53) replaces the number.

Verdict: 30, as `CALIBRATION_SPIKES`, recorded in the ADR as an assumption ("above the expected real rate; chosen so that spike rejection is exercised"). Do not reuse `SPIKE_TEST_COUNT`: same value, different density.

Owner: no. Tell the owner the assumed value in the closing Comment; a different real rate is a re-run and re-store later, cheap and already supported.

## Q4: score jumps from hard group gating

Against the plan: story 2 promises a continuous score that shows how close a borderline frame was; a score that moves 39 to 79 under a 0.3% pixel change does not deliver it, and each ticket that stores thresholds on this score raises the cost of fixing it.

For the plan:
- The false-alarm rate is a property of the score's distribution over frames. An order-statistic threshold is valid for any score, continuous or not, when calibration and new frames are exchangeable. The jumps are in the calibration scores.
- A continuous score is a detector change: `make measure`, new stored thresholds, ticket 05's region tests. That is its own ticket.
- The comment asks for the jumps to be carried, not fixed here.

One addition: the score has an atom at 0. A requested rate above the share of positive scores gives a threshold of 0 or a tie, and the realised rate is then below the request. Say so in the `Calibration.threshold` docstring; the unit test of ties already covers it.

Verdict: (a). Owner: no (keeping the score is the reversible choice).

## Q5: clipped stripe-free frames

Against the plan: a one-off number that changes no code and no check is a note, not a guarantee, and it costs 8-12 min.

For the plan: the 2026-11-13 Comment asks for exactly one of two things, a measurement on a few hundred clipped frames or a scope statement. The plan does both. Putting it in check-slow (b) adds 8-12 min per run for frames that are not exchangeable with the Calibration Set, so there is no valid tolerance to assert.

Corrections:
- Do not call (0, 10) a tolerance for these frames; the plan says this in section 5 but section 2.8 still words it as pass or fail. Report the count and its exact (Clopper-Pearson) interval.
- Run it at the frozen code, after the code-review fixes, so the recorded number is for the shipped detector.

Verdict: (a). Owner: no.

## Q6: API surface

Not pure taste; the spec settles most of it.

- `analyse(false_alarm_rate=)`: the spec's Analysis options list it. Required.
- `calibration=` and `calibrate_folder`: story 53 and AC 5. Required.
- CLI `--false-alarm-rate`: story 4 is an experimenter's story, and experimenters use the CLI (stories 36, 37). Include it, and `--calibration FILE`, without which a recalibration cannot be used from the CLI.
- `Report.false_alarm_rate`: the spec's Report field list does not have it and AC 4 does not need it. It also states a rate that is not the true one on any frame whose shape differs from the calibration's (Q9). Leave it out, or name it for what it is (the requested rate). Adding a field later is easy; removing one is not.
- `python -m denoisifier.calibration`: see E4. Use a module the package does not import, or a console script.

Also E3: the plan's `false_alarm_rate or DEFAULT_FALSE_ALARM_RATE` turns a rate of 0 into the default silently.

Verdict: (a) without the Report field, with the entry point changed. Owner: no.

## Q7: reproduction exactness

Against the plan: NumPy picks SIMD code paths per CPU, and some transcendental functions differ in the last bit between them. On another machine an exact check could go red with no fault, and by "fix the code, never the check" the only way out is an approved tolerance.

For the plan:
- The stamp and `.gate/` are per working tree; the project runs on one machine. The fast tier already pins SHA-256 digests of generated frames (`test_synthetic.py`, `_BASE_DIGESTS`), so bit-identical generation is already assumed.
- A tolerance of 1e-9 cannot absorb a gating flip anyway.
- Exact equality is what "reproduces the stored threshold(s)" means, and it is the strict choice; loosening later is one approved number.

Addition: on a mismatch the message reports the count of differing seeds and the largest relative difference, so a platform difference (all tiny) can be told from a detector change (tens of points) without a second run.

Verdict: (a). Owner: no.

## Q8: `make measure` at close

Against the plan: the orchestrator log lists `make measure` as a closing gate; CLAUDE.md names ticket 07 as a measure milestone; detector output (verdicts and reported regions) does move when the default threshold drops from 154 to about 85.

For the plan:
- CLAUDE.md: "`make measure` (only when the detector changed since the last measure...)". `make measure` uses only `analyse(...).score` (`feasibility._score_one`) and calibrates its own thresholds. `analysis.py` computes the score before the threshold is applied (lines 228 and 246), and the sweep tests pin that.
- No file under `src/` has changed since the last measure (`fd59d0c`).
- A measure of an unchanged score path would rewrite the same two thresholds for 39-47 min.

Conditions for skipping, to be quoted in the handoff:
1. the diff of `analysis.py`, `_local_stripes.py`, `_data_quality.py` and `synthetic.py` against `fd59d0c` touches only the threshold's source;
2. the closing check-slow's regression measurement equals the pre-ticket one bit for bit on its scores (for example `free.max_score` = 101.51738269624258 and the per-case `min_score` values in `.gate/check-slow-measurement.json` at `3f09325`). Save a copy of that file before the first run overwrites it.

If either fails, the score moved and `make measure` runs. Record the timed full-frame median as well: more frames report regions at the lower threshold, and nothing else in this ticket would show a slowdown.

Verdict: (a) with the two conditions. Owner: no.

## Q9: frames of another shape

(c) breaks story 34. Between (a) and (b): the direction that matters is frames with a larger light area than the calibration's, or binned frames, where the true rate can be above the stated one. That is ticket 08's ground (bin factors change the analysed shape). A new Report notes field now would be designed twice.

Verdict: (a). Add one line to ticket 08's Comments: decide there whether a shape or binning mismatch with the calibration is noted in the Report. This is one more reason not to ship `Report.false_alarm_rate` as a bare 0.01.

Owner: no.

## Serious problems outside Q1-Q9

**E1. Runtime is understated and the timeout is too tight.**
- The plan's 2.4 s per full frame comes from a 5 min run with 27 pooled full frames. `make measure` is the only long run with many full frames (600, plus 3500 small): CLAUDE.md's 39 min gives about 2.75 s per full frame, and the 47 min measured in ticket 06 gives about 3.5 s.
- 700 frames: 28 min at 2.4 s, **32 min at 2.75 s, 41 min at 3.5 s**. check-slow: about 38-47 min idle.
- CLAUDE.md says another project's load can double gate times. One module fixture of 700 frames under `timeout(3600)` then fails on time (64-82 min).
- Fix: three module-scoped fixtures (reproduction, held-out stripe-free, held-out striped), each paid by the first test that uses it, so each test's timer covers 100-300 frames. A per-test mark of about 2400 s then has a real factor of two. This is a smaller W6 than the plan's.
- Step 5 and step 9 take about 14-18 min and 9-12 min, not 12 and 8.

**E2. The real fixture is 64x64, not 20x20.** `read_frame("tests/data/solis/xpos_ypos_crop.asc", drop_axis_column=True)` returns shape (64, 64), above `MIN_SIDE` = 40. So AC 5 test (d), "refuses the real 20x20 crop", would not raise; and section 2.6's reason for not using a real export is false. Use the real file in the folder test (with generated 64x64 frames beside it), and use `kinetic.asc` (the reader refuses it, naming the file) for the reader-error case.

**E3. `false_alarm_rate or DEFAULT_FALSE_ALARM_RATE`** (section 2.3) maps a rate of 0.0 to 1% without an error. Use `is None`, for `calibration` too, and add the rate-0 case to the option test.

**E4. `python -m denoisifier.calibration` runs a module the package already imported** (`__init__` imports `analysis`, which will import `calibration`). runpy then warns ("found in sys.modules ... prior to execution") and executes the module a second time, giving two `Calibration` classes. Silencing the warning is a weakening move. Put the entry point in a module nothing imports, or add a `[project.scripts]` entry (a `pyproject.toml` edit: stamped, and it needs the usual approval).

**E5. No rule for a red closing run.** The held-out seeds are looked at once, by the final check-slow. The plan does not say what happens when AC 2 or AC 3 is red there. Write it now: a red is a finding for the owner; no re-seeding, no change of n, of the spike count or of the tolerance level after the look. One early warning is legitimate and free: at step 5, compare the new threshold with the stored probe's weakest case (period 3, lowest score 116.1 at m = 0.2, spike-free, `feasibility-gate.json`). The threshold is a 3rd-largest of 300 on new seeds, so it differs from 85.17 by sampling noise, not only by spikes as section 11 says; the 256x256 tail is heavy (1% point 49.7, highest of 850 is 101.5). If it lands near or above about 110, report before going on.

**E6. Wrong power figures for 2b** (see Number checks). Correct the table; the fast budget test should not encode the wrong figures.

Smaller points:
- AC 3 is pooled: 90 of 100 passes with one whole case (10 frames) lost. The per-case breakdown is only in the message. Either accept that in words or add a per-case floor before the look.
- Keep `THRESHOLD_CALIBRATION_SEEDS` in the `CALIBRATION_SEEDS` registry when `analysis.THRESHOLD` is removed; removing a registered range is a weakening move, and seeds 100-199 stay spent.
- Section 5's two budgets (this module's 1%, the regression check's 1%) add: say that check-slow's overall false-red bound becomes 2%.
- Ticket 11 will calibrate "at typical settings with spikes present" too. Whatever the owner rules in Q2 sets the pattern for its check-slow cost.

## Items from `07-plan-review.md` (added at the coordinator's request)

| Item | Reviewer's recommendation | Verdict | Owner |
|---|---|---|---|
| B4 | settle with prototype P1, then pre-declare a rule per affected test | Right, with two limits on P1 | no |
| O1 | skip `make measure`, recorded as a departure from CLAUDE.md | Skip is right; it is not a departure | no |
| O2 | add a CLAUDE.md Gates line for the re-store procedure (A); `make measure` runs the driver later (B) | A is right | no (the line goes to the owner with W7's wording) |

### B4: no resolution rule for fast-tier flips at the lower default threshold

The reviewer is right that the plan defers the decision to the moment the flips are seen, which is selection after the fact. The coupling it found is real: `_local_stripes.py:34-37` records that profile-only frames score up to about 72, and the new threshold is a 3rd-largest of 300 on new seeds, so a value near 72 is possible.

Against the reviewer's fix:
- "A test about another property passes `threshold=` explicitly" changes what an existing test checks. It is a weakening move, and choosing 154 would keep the provisional number alive in the tests. If an explicit value is used on 256x256 frames, it is `GATE_STORED_THRESHOLD`, that shape's measured 1% threshold, which ticket 06's AC 3 test already uses. Each such test is named and approved before step 6, not after.
- The optional part of P1 (about 50 full frames on 104_000-104_099 "for T's neighbourhood") cannot locate a 1% point: k = floor(0.01 x 51) = 0. It gives the share of zero scores and nothing else. It must not feed back into Q3: fix the spike count first, or the count is tuned on an outcome.

What P1 can do legitimately: the score does not depend on the threshold, so the score of every fast-tier frame can be listed today from test seeds only. That gives, per test, the highest threshold at which it would flip.

Rule to pre-declare (orchestrator approves, recorded in Comments before step 5):
1. A test whose subject is the default verdict keeps the default. A flip there is a finding for the orchestrator, not a seed move.
2. A test of another property on a small frame (spike or clip pairing, two-region, minimum size) may take `GATE_STORED_THRESHOLD` explicitly only if it is on the list approved before step 5.
3. Profile-only frames are not in the Calibration Set's population (no Mottle, low Gaussian noise), so no rate is claimed for them. If the new threshold lands below their top score, that is a real false verdict on a clean frame: stop and report, as E5's early warning already asks.

Owner: no. It is a rule the orchestrator can set from the repo; nothing in it is hard to revert.

### O1: is skipping `make measure` (Q8) the owner's call?

The reviewer agrees with skipping and tags it "owner" only because CLAUDE.md lists ticket 07 as a measure milestone. Read the two sentences together:
- "When": the closing sequence is "`make measure` (only when the detector changed since the last measure; then the stored thresholds), `make check-slow`, `make check`".
- "Write targets": measure "runs at milestones where detector output is meant to move (stripe-detector 05, 07, 13)".

The first sentence states the condition; the second lists where the condition was expected to hold. No file under `src/` has changed since the last measure (`fd59d0c`), and the plan changes only where the threshold comes from, which `make measure` never reads (it uses `.score` and calibrates its own thresholds). So skipping follows CLAUDE.md; it does not depart from it. The ticket's own owner Comment (2026-11-12) points the same way: one measure at most, and only when a detector change forces it.

Verdict: skip, on the two conditions given under Q8 (diff limited to the threshold source; regression scores bit-identical to the pre-ticket measurement). Record the ruling and both pieces of evidence in the ticket Comments, and correct the orchestrator log's "Milestone gates" line.

Owner: no. If either condition fails, the measure runs and there is nothing to ask.

### O2: the standing re-store procedure after this ticket

The reviewer is right that the plan leaves a new standing duty in a red test's message only. After this ticket, every change that moves stripe-free scores (tickets 08, 13, a continuous score) needs: the driver re-run, the package JSON rewritten (a source write outside `make fix`), `PACKAGE_STORED_THRESHOLD*` re-stored with an approval. CLAUDE.md's "After `make measure`" names only the gate and probe thresholds, and "Write targets" says `make fix` is the only target that changes source; the driver is then a second writer that CLAUDE.md does not list.

- Option A (a CLAUDE.md Gates line) is right. It tightens the rules and loosens nothing. Earlier tickets changed CLAUDE.md as part of their work (`ee2f774`, `615b0b2`), so the edit itself is ordinary ticket work.
- Option B (`make measure` runs the driver) is a Makefile edit, an owner approval, and adds 14-18 min to a 39-47 min run. Not now.
- The line must also say when the re-store is *not* allowed: an AC 7 red after a change that was not meant to move scores is a finding, not a re-store. Otherwise the procedure becomes the way to turn AC 7 green.
- Add the driver's `--out` write to the "Write targets" paragraph, next to `make measure`'s tracked JSON.

Owner: no for the decision. The wording goes to the owner in the same message as W7's duration line and Q2, since Q2's answer sets the duration that paragraph quotes.

### A conflict between the review's N2 and this critique's E1

The review's N2 says +28 min is probably pessimistic (about 20 min), from a serial cost ratio of 8.6 between the two shapes. E1 says it is optimistic (32-41 min). The serial ratio does not carry to the 12-worker pool: serially a 256x256 frame takes about 0.7 s, yet the pool delivers one per 0.19 s of wall clock, about a third of what 12 independent workers would give, so the pool is limited by something that scales with frame size. `make measure` is the only measured long run dominated by full frames: with a ratio of 8.6 it would take about 27 min (3500 + 600 x 8.6 units at 0.19 s), and it takes 39 (CLAUDE.md) to 47 min (ticket 06). Use the measure-derived 2.75-3.5 s per full frame for the owner's Q2 figure, and measure the real number at step 5, which is 300 full frames in the same pool.
