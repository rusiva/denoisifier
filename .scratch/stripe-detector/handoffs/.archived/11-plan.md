# 11 plan: calibrated fake Phase Breaks and Forks (settled)

- Ticket: `.scratch/stripe-detector/issues/11-calibrated-fake-defects.md`
- BASE: `e06a902`
- Status: settled. Every ruling in `11-rulings.md` is folded in (sources: `11-plan-review.md`
  B1-B5, O1-O5, N1-N8; `11-codex-review.md`; `11-critic.md`). Section 12 lists what was settled.
- Scope boundaries: ticket 17 (score-path fixes under breaks, fake regions) and ticket 18
  (break finder on Fork frames, fake breaks on Fork pairs / edge Forks) stay out. The
  calibration frames hold no Forks and no breaks (ticket 10 Comment), so the rate claimed
  here is the rate on break- and Fork-free striped frames of the declared recipe only (OQ4).
- Nothing here touches the score path: everything is after `score` and `reported` in
  `analyse` (`analysis.py:334-347`). The Stripe Score, the verdict, the stripe Threshold,
  `stripe_free_calibration.json` and `feasibility-gate.json` do not move (section 9). Moving
  break thresholds does move more than the reported breaks: absorb and the second bridge round
  change masks, region merges and measurements (`analysis.py:1249-1253`, `1340-1382`); section 9
  states the gate consequence.

**Names (glossary ruling).** `GLOSSARY.md:85` lists "defect" under Fork's _Avoid_. No public
name, docstring, CLI help, file name or ADR text uses "defect". New names are built from the
existing terms Phase Break and Fork: `break_fork_*` / `BreakFork*` in code, "fake Phase Breaks
and Forks" in prose. The test-side names follow the same rule. No glossary term is added and the
Fork entry is unchanged. (The rulings file and the review documents say "defect"; read it as
"Phase Break or Fork". Mapping: `defect_free_calibration.json` → `break_fork_free_calibration.json`,
`DefectCalibration` → `_BreakForkCalibration`, `defect_false_alarm_rate` →
`break_fork_false_alarm_rate`, `stored_defect_calibration` → `_stored_break_fork_calibration`,
`DEFECT_*` → `BREAK_FORK_*`.)

## 1. Where things stand (BASE `e06a902`)

- **Break acceptance** (`_local_phase._accepted`, line 498): the greedy finder takes the best
  line in a domain (max E over angle/offset), accepts it when `E >= _BREAK_MIN_EVIDENCE`
  (0.1, comparison at line 500), `|jump| >= _BREAK_MIN_JUMP_RAD` (π/4) and the jump spread
  ≤ π/4; else it stops. At most 4 per domain. E is stored on `FoundBreak.evidence` "for ticket
  11". P1 v2 margins: break-free max E 0.082, true π/2 min 0.18 (`_local_phase.py:82-89`).
- **Fork acceptance** (`analysis._region_forks`, line 487): `find_forks` returns every winding
  component with E = component area / (2R)², R = `_FORK_LOOP_PERIODS` · P; the caller keeps
  `E >= min_evidence`. `_region_forks` is shared by `_pre_break_forks` (gate
  `_FORK_GATE_EVIDENCE` 0.2, `:503-514`; decides whether the break pass reads a forks-explained
  field) and `_post_break_forks` (reported, `_FORK_MIN_EVIDENCE` 0.3, `:517-537`). P2 margins:
  fork-free max 0.000, true min 0.31 (ticket 10 Comments).
- **Domains** (`_with_phase_breaks`, line 1319): round 1 runs the finder on (a) every pair of
  reported regions that is `_compatible` and within `_BRIDGE_GAP_PERIODS` (bridge domain:
  both regions plus the gap; a found line counts only if it meets the side shares), then (b)
  each resulting region (`process`). Absorb and the second bridge round act only after a
  found break. With no break found, the pass returns its inputs.
- **Found is not reported** (review N1): `_reported_breaks` drops a found break with no region
  pixel within 0.75 px of its line (`analysis.py:1466, 1474-1476`), and a bridge can merge
  regions without a reported break.
- **Stripe precedent** (ticket 07, ADR 0002): the package stores per-frame scores, not a
  threshold; `Calibration.threshold(rate)` = k-th largest, k = floor(r (n+1)); verdict is
  `score > threshold`; driver `tests/threshold_calibration.py`, reproduction in
  `make check-slow` (`test_slow_calibration.py`), held-out tests in `make check-held-out`.
- The 09/10 acceptance tests in `tests/test_analyse.py` (lines ~1740-2450) call `analyse(frame)`
  on the default path with every seed required to pass ("no extras" included:
  `_assert_region_break_found` asserts exactly one break; `assert_forks_match` no extra Fork).
  No test monkeypatches `_BREAK_MIN_EVIDENCE` / `_FORK_MIN_EVIDENCE`
  (`test_local_phase.py:279,321` read `_FORK_MIN_EVIDENCE`).
  `test_analyse.py:2127-2132` (`test_a_gated_fork_corrects_the_break_pass_field`) injects a
  Fork with E exactly `_FORK_GATE_EVIDENCE`.
- Test doubles that the new finder parameter touches (review B2): `test_phase_break_pass.py:37`
  (`_pass` calls `_with_phase_breaks` with 4 positional arguments), `:87`
  (`lambda *_: [BREAK]`), `:104` (`find(_z, domain, *_)`), `test_analyse.py:1944`
  (`spy(z, domain, *args)`); the `_with_phase_breaks` monkeypatches at `test_analyse.py:1903,
  2015, 2094, 2171`; and the 9 direct `find_phase_breaks` calls in `tests/test_local_phase.py`
  (lines 121, 133, 138, 143, 154, 166, 174, 198, 309), which pass
  `min_evidence=_BREAK_MIN_EVIDENCE` explicitly (closing check N9).

## 2. The two evidence scalars (per calibration frame)

Acceptance on the **reported** side becomes strict `E > T` for both kinds (ADR 0002's
`score > threshold`; needed for the 0.0 atom: a frame with no candidate has S = 0 and must never
be a fake at T = 0). The two strict comparisons are `_accepted` at `_local_phase.py:500`
(breaks) and the reported side of the Fork search (`_post_break_forks`'s use of
`_region_forks`). **The pre-break gate stays `E >= _FORK_GATE_EVIDENCE`** (B1): `_region_forks`
takes its comparison per caller (or `_post_break_forks` applies `> T_f` itself); the gated-fork
test at `test_analyse.py:2127-2132` stays green unchanged.

The scalars bound "found", and "reported" ⊆ "found" (N1), so the statements are one-sided
(conservative):
- "no break found at threshold T" ⇔ `S_b <= T`; hence `S_b <= T` ⇒ no reported break;
- "no Fork found at threshold T" ⇔ `S_f <= T` (on a frame where no break is found);
- `S_b <= T_b` and `S_f <= T_f` ⇒ no reported break and no reported Fork.

**Fork scalar `S_f`** (ticket 10 Comment): the largest E of any `find_forks` candidate in the
post-break search domains of the reported regions, with no breaks explained away (= the
pre-break search's candidates; on a frame where no break is found the two searches coincide).
0.0 when there is no candidate. Refused regions (`_holds_refused`) are skipped as in analyse.

**Break scalar `S_b`**: the smallest T at which the real pass finds nothing, computed from one
trace at no evidence limit, on the field analyse would use (the pre-break gate stays at the
fixed `_FORK_GATE_EVIDENCE`, so the field does not depend on any calibrated threshold):

- for each reported region's domain (`process` with no bridge: its pixels):
  `g = E_1` if the first best line passes the jump and spread rules, else 0 (finder called with
  `max_lines=1`, N7);
- for each bridge pair: run the finder with no evidence limit to get its greedy sequence
  `E_1..E_m` (stops where the jump/spread rule fails or at 4); `g = max over j such that line j
  meets the side shares of min(E_1..E_j)` (a prefix must be accepted to reach line j), else 0;
- `S_b = max g` over all domains, 0.0 when none.

Why the "found" statement holds: at threshold T the finder returns the longest prefix of the
no-limit sequence whose E all exceed T (the best line never depends on T). If nothing is found
at T in any round-1 domain, the pass is the identity and round 2 searches the same domains; if
anything is found, it is a found break in a region domain or a bridge. Monotone in T, so the
frame's crossing is `S_b`. The same argument covers the post-break Fork search: with no break
found it sees the same domains. Whether a found break is also reported (0.75 px rule) only
removes reports, so the bound is conservative. Docstrings and ADR 0003 say "found", never
"exactly reported".

**Seams.**
- `find_phase_breaks(..., *, min_evidence: float, max_lines: int = _MAX_BREAKS)` and
  `_accepted(samples, brk, min_evidence)`; `min_evidence` is required keyword-only (no default,
  so no silent floor path exists). `_with_phase_breaks(..., *, break_threshold: float)` and
  `_post_break_forks(..., *, fork_threshold: float)` likewise required keyword-only. Every
  double and direct caller listed in section 1 is updated in the step that adds the parameter
  (B2).
- **One shared front half** (B5): factor `analysis.py:315-345` (validation, spike rejection,
  regions, `reported`, `refused`, `_Responses`, the gated field) into one private helper,
  e.g. `_front_half(frame, ...) -> _FrontHalf(reported, refused, filters, clipped, responses,
  field, ...)`. `analyse` and `_break_fork_evidence` both call it; no copy.
- `analysis._break_fork_evidence(frame, *, clip_level=None, bin_factors=None) ->
  _BreakForkEvidence(breaks: float, forks: float)`: the front half at the stored stripe
  threshold (1 %), then the two scalars, reusing `_BreakPass.bridge`'s domain and share code
  (factor the share test out; no copy). Private; no public wrapper (O4).

Fast tests pin the bound and the shared path (section 6, T7 and T8).

## 3. Thresholds from the scalars (rate r)

`_BreakForkCalibration` (private, in `calibration.py`, next to `Calibration`; O4): `ids`,
`break_evidence`, `fork_evidence` (per frame, in id order), `shape`, `settings`, `run_info`
(not compared); `from_evidence`, `digest()`, `to_json()` / `from_json()`, and
`thresholds(rate) -> _BreakForkThresholds(breaks, forks)`.

**Rule (OQ2 → fixed r/2 each, ordinary marginal order statistics, floors kept):**
1. `k = threshold_rank(n, r / 2)` (same k for both).
2. `T_f = max(k-th largest S_f, _FORK_MIN_EVIDENCE)`.
3. `T_b = max(k-th largest S_b, _BREAK_MIN_EVIDENCE)`.

Each marginal order statistic gives a per-kind rate of at most k/(n+1) ≤ r/2 on an exchangeable
new frame, so the frame-level rate (any fake break or Fork) is at most r by the union bound. (The
adaptive union rule of the draft is dropped: Codex's analytic counterexample gives 5.305 % at
r = 5 %, n = 300.) ADR 0003 separates this marginal-over-calibration statement from the
uncertainty of the one shipped threshold.

**Floors (OQ1 → (b))**: `_BREAK_MIN_EVIDENCE` and `_FORK_MIN_EVIDENCE` keep their names and
values and become the floors (comments rewritten; no lockfile change). Calibration can only make
thresholds stricter than the ones 09/10 were validated at. `_FORK_GATE_EVIDENCE` stays fixed,
uncalibrated and `>=` (it decides the field, not what is reported; keeping it fixed is what
makes `S_b` well defined). If P1 shows the floors bind at every valid rate, ADR 0003 and the
ticket Comment say so plainly: "the floors set the thresholds; measured rate x of 300"; P1
reports the smallest rate at which either threshold leaves its floor.

**Rate validation**: `0 < r < 1` and `k >= 1`, i.e. `r >= 2/(n+1)` (0.66 % at n = 300); else
ValueError worded like `Calibration.threshold`, stating the smallest valid rate.

**Meaning (O2)**: `DEFAULT_BREAK_FORK_FALSE_ALARM_RATE = 0.05` in `calibration.py` (spec.md:105,
ticket "about once per 20 frames"). The option is the calibrated share of break- and Fork-free
striped frames with at least one fake Phase Break or Fork, **at most r** (floors). One frame can
carry several fakes, so AC 2 checks the total count, the stricter reading. Pre-declared: P1
records fake multiplicity per frame; if the total count exceeds 1.5 × frames-with-fakes at the
candidate thresholds, stop for the orchestrator before freezing (count-based calibration would be
needed).

## 4. Storage and loading ("next to the stripe threshold")

- `src/denoisifier/break_fork_free_calibration.json` beside `stripe_free_calibration.json`
  (package data; same build inclusion as the stripe file; check the wheel picks `*.json`).
  Separate file (OQ3 → (a)): different Calibration Set, and the stripe file's digest and
  reproduction stay untouched. The format is versioned by its evidence semantics:
  `"format": 1`, `"evidence": "break-fork-v1"` (the S_b / S_f definitions of section 2, with
  floors at the recorded constants), and `settings` records the stripe calibration digest it
  depends on (`stored_calibration().digest()`). Frames are `{id, breaks, forks}`.
- `_STORED_BREAK_FORK_CALIBRATION_FILE`, `_stored_break_fork_calibration()`
  (`functools.cache`, `importlib.resources`), like `stored_calibration()`, private.
- **Public surface (O4)**: only `analyse(..., break_fork_false_alarm_rate: float | None = None)`
  and the CLI flag `--break-fork-false-alarm-rate`. No public `defect_calibration=`-style
  parameter, no public calibration class, loader or evidence wrapper. Tests that need other
  thresholds monkeypatch `_stored_break_fork_calibration` with a hand-made
  `_BreakForkCalibration` (B3).
- Threading: `analyse` → `_resolve_break_fork_thresholds(rate)` → `_BreakForkThresholds`; `T_b`
  to `_with_phase_breaks(..., break_threshold=)` → `_BreakPass.find` →
  `find_phase_breaks(min_evidence=T_b)`; `T_f` to `_post_break_forks(..., fork_threshold=)`.
  The pre-break gate keeps `_FORK_GATE_EVIDENCE` at `>=`.
- **Scope of the claim (N3, OQ4)**: the thresholds are calibrated on the regions reported at the
  stored 1 % stripe threshold, unbinned, at 400x1600, full-frame stripes at depth 0.5, the ten
  cases. `threshold=`, `false_alarm_rate=`, `calibration=` (stripe), `bin_factors`, crops,
  partial regions and weaker stripes change which regions and domains the finders see, so the
  claim does not cover them; the mechanics are independent, the claim is not. The `analyse`
  docstring and the CLI help say so and quote P1's arm numbers (section 5). No runtime Report
  warnings for mismatched settings in this ticket (new public Report surface not asked for).
- No Report field added (spec's Report list has none); the thresholds used are not reported.
- **Real-frame recalibration deferred (O4)**: no folder driver for these thresholds; a one-line
  note in `spec.md` near line 112 says real-frame recalibration of the break and Fork thresholds
  is deferred. The private `_BreakForkCalibration.from_json` is the seam for one later.

## 5. Calibration routine, frames, seeds, P1 arms

Driver `tests/break_fork_calibration.py` (new, stamped), shaped like `threshold_calibration.py`:
`settings()`, `synthetic(seed)`, `_evidence_job`, `break_fork_calibration_from_seeds(seeds,
shape, workers)` (core, guarded pool via `feasibility.run_pool`), `calibrate_break_forks()`
holding the **one** `seed_guard.calibrating(BREAK_FORK_FREE_CALIBRATION_SEEDS)` block,
`reproduction_check` / `reproduction_problems`, `held_out_fakes` / `fake_problems`,
`held_out_detection` / `detection_problems`, `main(--out PATH [--workers N])`.

**Calibration frames (OQ4 → (a) as a narrow, declared baseline)**: 400x1600 (`PROBE_SHAPE`),
full-frame stripes, Period/Angle `CASES[seed % 10]`, depth 0.5 (the 09/10 frames' depth),
scorched Mottle, `Emccd()` (about 100 photons at the peak), `CALIBRATION_SPIKES` (30) Spike
events, unclipped, no breaks, no Forks. n = 300. **Every calibration frame must be `striped`**:
the core raises ValueError on a frame that is not (the recipe is wrong; never silently S = 0).

**P1 measurement arms** (prototype seeds, candidate thresholds = base arm's r/2 order statistics
at r = 0.05 with floors):
- base: the calibration recipe (gives the candidate thresholds, quantiles, multiplicity, s/frame);
- (i) full-frame stripes at m = 0.2 (`WEAK_DEPTH`);
- (ii) a partial region in a 400x1600 frame at depth 0.5 (one region over about half the frame,
  from `tests/regions.py`; P1 names the function; this arm can see the 109797 fake-region kind);
- (iii) the base recipe analysed at stripe `false_alarm_rate=0.05`.

Every arm reports its striped count, its non-striped count and its fake rate **over striped
frames** (frames with no reported region cannot carry a fake and would dilute the rate; arm (i)
at m = 0.2 has about 10 % non-striped frames; closing check N12). Pre-declared: any arm with
fake frames above 5 % of its striped frames → stop for the orchestrator (owner question:
which depths and geometries are typical is external knowledge). Otherwise all arm numbers go into
ADR 0003 as the claim's scope, and the docstring restricts the claim to the declared recipe.

Seeds (all new, disjoint from every range in `protected.py`; 111_200-111_599 and
111_733-111_999 stay free for ticket 18):

| name | range | role |
|---|---|---|
| `BREAK_FORK_PROTOTYPE_SEEDS` | 112_000-112_199 | P1 measurement, every arm (step 1); reserved in `USED_SEEDS` |
| `BREAK_FORK_FREE_CALIBRATION_SEEDS` | 113_000-113_299 | Calibration Set; registered in `CALIBRATION_SEEDS` |
| `BREAK_FORK_FREE_HELD_OUT_SEEDS` | 114_000-114_299 | AC 2 held-out, same frame recipe |
| `BREAK_FORK_FREE_HELD_OUT_2_SEEDS` | 114_300-114_599 | reserved second look for AC 2 (OQ6 red rule); in `USED_SEEDS`, unused unless a second look is ruled |
| `BREAK_FORK_DETECTION_HELD_OUT_SEEDS` | 115_000-115_199 | AC 3(c) held-out: 100 break + 100 Fork frames |
| `BREAK_FORK_DETECTION_HELD_OUT_2_SEEDS` | 115_200-115_399 | reserved second look for AC 3(c); in `USED_SEEDS`, unused unless ruled |
| `BREAK_FORK_TINY_*_TEST_SEEDS` | inside 10-99 (e.g. 40-47, reuse allowed) | fast tiny-plan tests |

## 6. Acceptance criteria → tests

| AC | Test | Tier |
|---|---|---|
| 1 repeatable routine | `test_slow_break_fork_calibration.py::test_break_fork_calibration_reproduces_the_stored_thresholds`: re-run `calibrate_break_forks()`, compare ids, shape, settings, every per-frame `(S_b, S_f)` exactly, thresholds at the default rate against `PACKAGE_BREAK_FORK_*`. Size per OQ8 (below): all 300, or the 60-frame prefix 113_000-113_059 (6 per case) with a second test `::test_break_fork_calibration_reproduces_all_frames` marked `held_out` for the full 300 | slow (check-slow); full-300 test in check-held-out if the prefix branch is taken |
| 1 (fast) | `test_break_fork_calibration.py::test_calibrate_break_forks_runs_the_core_on_the_calibration_set_inside_its_block` (spy, as 07); `::test_break_fork_calibration_tiny_plan_is_repeatable`; `::test_break_fork_calibration_frames_are_striped_break_fork_free_spiked_and_unclipped`; `::test_the_core_refuses_a_frame_that_is_not_striped`; `::test_stored_break_fork_calibration_ships_with_the_package`; `::test_stored_break_fork_calibration_is_the_protected_one` (thresholds, ids, shape, settings, evidence version, digest); `::test_stored_break_fork_calibration_names_the_stored_stripe_digest` (N4: the recorded stripe digest equals `stored_calibration().digest()`, so a stale file fails `make check`) | fast |
| 2 fake count ≤ ~1/20 | `test_held_out_break_fork.py::test_held_out_fake_breaks_and_forks_at_the_default_rate`: on `BREAK_FORK_FREE_HELD_OUT_SEEDS`, public `analyse(frame)` default path. Precondition: every frame is `striped` (a red is a finding per the OQ6 red rule). Asserts the **total count** of reported breaks + Forks ≤ the one-sided point at `CALIBRATION_MAX_FALSE_RED` of the single-order-statistic model at r (k = 15 at n = 300, betabinom(300, 15, 286), about 29; the fixer computes it and pins it as a protected number in `test_break_fork_plan_meets_its_false_red_budget`; not `false_alarm_tolerance`'s central (3, 33), N2). The count model is fixed before the held-out run (closing check N11; see "AC 2 count model" below). Also per frame computes `_break_fork_evidence(frame)` and asserts at scale: a reported break ⇒ `S_b > T_b`; a reported Fork ⇒ `S_f > T_f` or a found break; `S_b <= T_b` and `S_f <= T_f` ⇒ no break and no Fork. Records to `.gate/held-out-break-fork.json`: count, frames-with-fakes and its exact upper limit, per-case fakes, every fake (seed, case, kind, E, in a fake region or not), per-case alarm flags | slow + held_out |
| 3 09/10 rates hold | (a) the 09/10 tests in `test_analyse.py`, `test_phase_break_pass.py`, `test_local_phase.py` unchanged in their assertions, now on the stored calibrated thresholds (their real path); (b) `test_analyse.py::test_default_break_fork_thresholds_are_the_stored_ones`: monkeypatch `_stored_break_fork_calibration` with a hand-made calibration whose `thresholds(0.05)` are above both floors (precondition asserted: they differ from the floors), a wrapping spy on `find_phase_breaks` / `_post_break_forks` sees exactly those values; (c) `test_held_out_break_fork.py::test_breaks_still_found_after_calibration` (100 frames, 09 region geometry, `ac2_line`-style jumps from {π/2, 2π/3, π, -π/2, -3π/4}, typical noise; matched by `truth_match.assert_break_matches`, exactly one break) and `::test_forks_still_found_after_calibration` (100 frames, 10's AC 2 geometry), each pooled ≥ `BREAK_FORK_MIN_DETECTION_RATE` (0.95), **plus** the paired "lost by calibration" count on the same frames: true breaks / Forks found at the floors but lost at the stored thresholds, asserted 0; per-case outcomes recorded (OQ5) | (a,b) fast; (c) slow + held_out |
| 4 rate option + CLI | `test_analyse.py::test_break_fork_false_alarm_rate_option_sets_the_finder_thresholds`: monkeypatched hand-made calibration with evidence spread above the floors; precondition `thresholds(0.05) != thresholds(0.2)`; spy wraps the real finders and sees `thresholds(r)` at each rate; `::test_break_fork_false_alarm_rate_out_of_range_is_an_error` (0, 1, below 2/(n+1); message names the smallest valid rate); `::test_break_fork_false_alarm_rate_changes_the_report`: monkeypatched calibration under which one rate removes the break of a 09 frame that another rate keeps (precondition: the two reports differ); `test_cli.py::test_cli_break_fork_false_alarm_rate_reaches_analyse` calls `denoisifier.cli.main([...])` **in-process** (`cli.py:40` takes `argv`; output with `-o` to `tmp_path`) inside the same monkeypatch (the existing subprocess `_run`, `test_cli.py:42-43`, would not see it; closing check B6): the CLI report at the rate equals the library call at that rate and differs from the default-rate report; `::test_cli_zero_break_fork_false_alarm_rate_is_an_error` (in-process); plus one subprocess smoke test `::test_cli_break_fork_false_alarm_rate_flag_is_accepted` (the flag is accepted, and 0 exits with an error) | fast |
| 5 statistical tests slow | `test_break_fork_calibration.py::test_statistical_break_fork_tests_are_slow`: every test in both new slow modules carries `slow` and the `CALIBRATION_TIMEOUT_S` timeout; `held_out` exactly on `test_held_out_break_fork` tests (and on `::test_break_fork_calibration_reproduces_all_frames` if the OQ8 prefix branch is taken), not on the check-slow reproduction | fast |

Supporting (fast):
- T7 `test_break_fork_calibration.py::test_break_evidence_is_where_the_first_break_is_found`:
  on a 09 break frame, a break-free region frame, a spiked full frame and
  `compatible_pair_frame` (bridge domain), `_with_phase_breaks(..., break_threshold=S_b)` on the
  frame's real `reported` regions finds no break and with `nextafter(S_b, 0)` finds at least
  one (when `S_b > 0`). Same for `::test_fork_evidence_is_where_the_first_fork_is_found` on a 10
  AC 2 frame via `_post_break_forks(..., fork_threshold=...)`. Floors make thresholds below
  0.1 / 0.3 unreachable through `analyse`, so T7 drives the private seams (as
  `test_phase_break_pass.py` does).
- T8 (B5) `::test_evidence_bounds_the_public_report`: on the T7 frames, with
  `_stored_break_fork_calibration` monkeypatched (the private seam) to hand-made calibrations
  that put `T_b` / `T_f` just below and just above each frame's scalars, the public
  `analyse(frame)` Report obeys the three implications of section 2. The floors make "just
  below" unreachable when a scalar is under its floor, so the "just below" half runs only on
  frames whose scalar is above the floor, and the test asserts that precondition (the chosen
  thresholds sit above the floors) for every case it checks; otherwise it is not a valid test
  (closing check N10). The "just above" half runs on every T7 frame. `::test_analyse_and_evidence_share_the_front_half`: a
  wrapping spy on `_front_half` sees one call from each (supporting, not alone).
- `::test_break_fork_thresholds_are_marginal_order_statistics_with_floors` (hand data: r/2 each,
  ties at 0, floors, k at 300, smallest valid rate).
- `::test_break_fork_calibration_round_trips_json_and_digest` (format and evidence version
  included).
- `::test_slow_break_fork_checks_run_on_a_tiny_plan` (every `*_problems` function on tiny plans,
  including the at-scale implication check and the paired lost count).
- `::test_break_fork_plan_meets_its_false_red_budget` (AC 2's one-sided bound and its model
  stated; AC 3 bars at 0.95 with N = 100: false red at the 09/10 validated rates computed and
  stated, under `CALIBRATION_MAX_FALSE_RED`).
- `test_local_phase.py::test_a_line_is_accepted_only_above_min_evidence` (strict `>`).
- `test_analyse.py` (existing) `test_a_gated_fork_corrects_the_break_pass_field` stays green
  unchanged: it pins the gate's `>=` (B1).

**AC 2 count model (closing check N11)**: under the r/2 + r/2 rule the union of the two
per-kind events has a frame rate ≤ r, so frames-with-fakes is bounded by the single-order-
statistic model at r (k = 15 at n = 300); the AC 2 bound uses that model's one-sided point
(~29). This is conservative for frames-with-fakes and an approximation for the total count,
which can exceed frames-with-fakes; that excess is covered by P1's 1.5× multiplicity stop rule
(section 3). The budget test's docstring and ADR 0003 state this. The model and the bound are
fixed before the held-out run and never changed after it.

**Per-case alarm level (O2, critic)**: pre-declared, recorded, not asserted (asserting ten cases
would exceed the false-red budget). P1: a case with ≥ 5 fake frames of its 20 (binomial tail
0.26 % at 0.05) is a stop for the orchestrator. Held-out: a case with ≥ 6 fakes of its 30
(tail 0.33 %) sets an alarm flag in the JSON and is a finding for the orchestrator, never a
threshold edit.

## 7. Steps (each ends on `make test-fast` green; test-first)

0. The orchestrator's approvals are recorded in the ticket Comments (done, 2026-11-15). Any
   further approval of section 10 is recorded there before its change.
1. **P1 measurement (stop point).** Scratch script under `.scratch/stripe-detector/handoffs/`
   (not a test). On `BREAK_FORK_PROTOTYPE_SEEDS`, every arm of section 5:
   - `S_b`, `S_f` distributions (the `S_f` distribution at 400x1600 with spikes stated
     explicitly), quantiles at ranks 2.5 % / 5 %, candidate thresholds at r = 0.05 (r/2 each,
     floors), the smallest rate at which either threshold leaves its floor (or "none");
   - fakes per frame (multiplicity), frames-with-fakes, fakes inside fake regions, per case;
   - s/frame of the evidence pass and of `analyse`, and the projected `make check-slow` /
     `make check-held-out` durations under both OQ8 branches;
   - the true-defect E on **every 09/10 test frame**, all parameters including `wide` (B4):
     `m_b` = min(0.18, smallest true-break E over the 09 test frames), `m_f` = min(0.31,
     smallest true-Fork E over the 10 test frames).

   Write `11-prototype-p1.md`. Pre-declared stop rules (any one → stop for the orchestrator):
   - `T_b > _BREAK_MIN_EVIDENCE` and `T_b > m_b − 0.02`, or `T_f > _FORK_MIN_EVIDENCE` and
     `T_f > m_f − 0.02` (with `m_f` ≤ 0.31 this means any rise of `T_f` above its floor stops);
   - total fakes > 1.5 × frames-with-fakes (O2);
   - any arm (i)-(iii) with fake frames above 5 % of its striped frames (OQ4, N12);
   - any case at the P1 per-case alarm level.

   If the floors bind (`T_b` = 0.1, `T_f` = 0.3), proceed, and record it for ADR 0003 and the
   ticket Comment (OQ1). P1 also records the OQ8 branch taken.
2. Finder seam: `min_evidence` (required keyword) and `max_lines` on `find_phase_breaks`,
   strict `>` at `_accepted` (`_local_phase.py:500`), strict `>` on the reported Fork side
   only (gate stays `>=`); constants unchanged and passed explicitly by the callers. Update every
   double and direct caller of section 1 (B2). Every 09/10 test must stay green (tie risk, R3).
3. `_BreakForkCalibration`, `_BreakForkThresholds`, `DEFAULT_BREAK_FORK_FALSE_ALARM_RATE`,
   private loader (unit tests first, on hand-made calibrations). `analyse` is not wired to the
   stored file until the file exists (step 6): no silent fallback to the floors is ever shipped.
4. Shared `_front_half` (B5; pure refactor, bit-identical, `analyse` tests green); `analyse` /
   `_with_phase_breaks` / `_post_break_forks` threading; `break_fork_false_alarm_rate` option;
   CLI flag `--break-fork-false-alarm-rate` (help: "at most this share of striped frames
   without phase breaks or forks show a fake phase break or fork, between 0 and 1 (default:
   0.05); calibrated at the stored stripe threshold, unbinned, 400x1600 full-frame stripes").
   Library tests here use the monkeypatched loader; the CLI tests land at step 6 (N6).
5. `_break_fork_evidence` + T7 + T8.
6. `tests/break_fork_calibration.py` driver, `protected.py` numbers, seed registry, tiny-plan
   tests, the two slow modules, `STAMPED_FILES` additions, the CLI tests. First driver run
   (background, ~13 min; the approved additional source writer, section 10) writes
   `break_fork_free_calibration.json`; wire `analyse`'s default to it; set
   `PACKAGE_BREAK_FORK_*` (lockfile). Then `make check` (N8; it runs every fast test including
   `wide`, `test_phase_break_pass.py` and `test_local_phase.py`; only the final stamp step is
   expected red until `make check-slow`). **A red 09/10 seed here is a stop for the
   orchestrator, never a threshold, floor or seed edit** (B4).
7. Docs: `analyse` docstring (replace "conservative until calibrated (ticket 11); no
   false-break rate is claimed" with the claim, its scope (section 4) and the measured count
   with its exact upper limit), `find_phase_breaks` / `find_forks` notes; ADR 0003 (break and
   Fork thresholds as marginal order statistics at r/2 each of stored per-frame evidence on
   break- and Fork-free striped frames, floors, union bound, the found/reported bound, P1's arm
   numbers as scope, the AC 2 count model (conservative for frames-with-fakes, an approximation for the count,
   covered by the 1.5× rule), the measured held-out count, frames-with-fakes and exact upper
   limit,
   whether the floors bind); `spec.md` one-line note (real-frame recalibration of these
   thresholds deferred); CLAUDE.md and Makefile help wording (approved, section 9). No
   GLOSSARY change.
8. Code review and its fixes, then: if any fix touched the evidence path, the finders, the
   break pass, the front half or the frame recipe, re-run the driver and re-set
   `PACKAGE_BREAK_FORK_*` (approval); then the gates (section 9).

## 8. Runtime (idle, default 12 workers; held-out log rate 2.4 s per full frame)

| new slow test | frames | estimate | tier |
|---|---|---|---|
| reproduction (AC 1), full branch | 300 full | ~12-14 min | `make check-slow` |
| reproduction (AC 1), prefix branch | 60 full in check-slow + 300 full in held-out | ~3 min + ~12-14 min | both |
| `test_held_out_fake_breaks_and_forks_at_the_default_rate` | 300 full, `analyse` + evidence | ~14-20 min (P1 measures) | `make check-held-out` |
| `test_breaks/forks_still_found_after_calibration` (+ paired floor run) | 200 at 512x512 | ~3-5 min | `make check-held-out` |

The evidence pass runs the front half plus the no-limit finder runs (`max_lines=1` in region
domains, the full sequence only for bridge pairs). 07 measured 2.79 s per full frame for the score
path alone (`test_slow_regression.py:18`), so the estimates above are lower bounds until P1
measures them (N7).

**OQ8 → decide from P1**, against the owner's ~20 min check-slow preference
(`07-orchestrator.md:34`): if the full 300-frame reproduction keeps `make check-slow` at
≤ ~25 min idle, reproduce all 300 in check-slow; otherwise the 60-frame prefix (6 per case) in
check-slow and the full 300 reproduced in `make check-held-out` (which the re-store procedure and
the held-out milestones run). P1 records the timing and the branch; the fixer updates the
durations in `test_slow_regression.py`'s module docstring (the one source), CLAUDE.md's Gates
text and the Makefile help. Each new slow test carries `pytest.mark.timeout(
CALIBRATION_TIMEOUT_S)` (2400 s).

## 9. Do scores move? Gates

- Stripe score, verdict, stripe Threshold: unchanged (the change is after `reported`). So **no
  stripe re-store**; `test_slow_calibration.py` must stay green unchanged (a red there is a
  finding).
- Detector output that does move: reported breaks and Forks at the default (only if P1's
  thresholds rise above the floors; ties at exactly 0.1 / 0.3 otherwise), **and with them**
  masks, region merges and measurements wherever absorb or the second bridge round acts on a
  break that is no longer found (`analysis.py:1249-1253`, `1340-1382`; Codex).
- **`make measure` consequence**: `make measure` reads only `analyse(...).score`
  (`tests/feasibility.py:161, 174`), which is computed before the break pass, so no
  `make measure` output moves and no `make measure` runs. The fixer re-checks this at close
  (grep `feasibility.py`, `test_feasibility_gate.py` and `test_slow_regression.py` for masks,
  regions, breaks or Forks); if any of them reads an output that moves, `make measure` runs at the
  fixer (and the stored-threshold update that follows it).
- `analysis.py`, `_local_phase.py`, `calibration.py`, `protected.py` are stamped → `make
  check-slow` is required.
- **Ticket 11's close is a held-out milestone (OQ6 → (a), approved).** Fixer's closing sequence
  (background, idle, one at a time): driver `uv run --locked python
  tests/break_fork_calibration.py --out src/denoisifier/break_fork_free_calibration.json`
  (~13 min; only if step 8 requires a re-run) → `PACKAGE_BREAK_FORK_BREAK_THRESHOLD`,
  `PACKAGE_BREAK_FORK_FORK_THRESHOLD`, `PACKAGE_BREAK_FORK_CALIBRATION_DIGEST` in
  `protected.py` → `make check-slow` → `make check-held-out` (once; the one look at the new
  held-out seeds) → `make check`. No `make bench` (the default path adds a cached JSON load and
  one comparison).
- **Pre-declared red rule** for the held-out look: a red AC 2 or AC 3(c) (including the
  striped precondition, the at-scale implication check and the paired lost count) is a finding
  for the orchestrator. No threshold, floor, recipe or seed is edited in response. A second look
  after any evidence-moving change uses the reserved fresh ranges
  `BREAK_FORK_FREE_HELD_OUT_2_SEEDS` (114_300-114_599) and
  `BREAK_FORK_DETECTION_HELD_OUT_2_SEEDS` (115_200-115_399), never the first ranges again.
- **CLAUDE.md and Makefile help wording** (approved; doc-only gate-config edit, step 7):
  `make check-held-out` also runs at stripe-detector ticket 11's close; the break/Fork driver is
  an additional writer of tracked source outside `make fix` (at ticket 11 step 6 and in the
  re-store procedure); the re-store procedure gains "after a stripe re-store or any change to
  `_local_phase.py`, the break pass, the Fork searches or the shared front half, re-run the
  break/Fork driver, set `PACKAGE_BREAK_FORK_*`, then `make check-slow` → `make check-held-out`
  → `make check`"; check-slow and check-held-out durations per P1. Makefile: the `check-slow`
  and `check-held-out` `##` help strings only (duration; "ticket 07 and 11 close and measure
  milestones only"). The pyproject `held_out` marker text already says "at a ticket's close"
  and is not edited.

## 10. Protected numbers, lockfile edits, weakening moves

**Approved by the orchestrator (2026-11-15, recorded in the ticket Comments):**
- O1/OQ6: `make check-held-out` at ticket 11's close, and the CLAUDE.md + Makefile help text
  wording of section 9 (gate config, doc-only).
- O3: the break/Fork driver as an additional writer of tracked source outside `make fix` (step 6
  and the re-store procedure).
- A5 (B1): strict `>` on the reported comparisons only, named: `_accepted` at
  `_local_phase.py:500` (breaks) and the reported side of the Fork search (`_post_break_forks`
  via `_region_forks`). The pre-break gate stays `>=`.

**Approved when the closing check passes them** (rulings, "Approvals recorded"; record each in
the ticket Comments with its reason when made):
- A1 lockfile additions (`tests/protected_numbers.lock`), new pins, nothing loosened:
  - `calibration.py`: `DEFAULT_BREAK_FORK_FALSE_ALARM_RATE = 0.05`.
  - `protected.py`: `BREAK_FORK_PROTOTYPE_SEEDS`, `BREAK_FORK_FREE_CALIBRATION_SEEDS`,
    `BREAK_FORK_FREE_HELD_OUT_SEEDS`, `BREAK_FORK_FREE_HELD_OUT_2_SEEDS`,
    `BREAK_FORK_DETECTION_HELD_OUT_SEEDS`, `BREAK_FORK_DETECTION_HELD_OUT_2_SEEDS`,
    `BREAK_FORK_TINY_*_TEST_SEEDS`, `BREAK_FORK_REPRODUCTION_PREFIX` (60, only in the OQ8
    prefix branch), `BREAK_FORK_CALIBRATION_SHAPE` (= `PROBE_SHAPE`),
    `BREAK_FORK_CALIBRATION_DEPTH = 0.5`, `BREAK_FORK_FALSE_ALARM_RATE = 0.05` (test-side),
    `BREAK_FORK_MIN_DETECTION_RATE = 0.95`, `BREAK_FORK_DETECTION_BREAK_FRAMES = 100`,
    `BREAK_FORK_DETECTION_FORK_FRAMES = 100`, AC 2's one-sided count bound (pinned in the budget
    test), the per-case alarm levels (P1: 5 of 20; held-out: 6 of 30), the P1 stop margin 0.02
    and arm alarm 0.05 if the P1 script imports them, `PACKAGE_BREAK_FORK_BREAK_THRESHOLD`,
    `PACKAGE_BREAK_FORK_FORK_THRESHOLD`, `PACKAGE_BREAK_FORK_CALIBRATION_DIGEST`;
    `USED_SEEDS += BREAK_FORK_PROTOTYPE_SEEDS, BREAK_FORK_FREE_HELD_OUT_2_SEEDS,
    BREAK_FORK_DETECTION_HELD_OUT_2_SEEDS`.
- A2 seed guard: `CALIBRATION_SEEDS["BREAK_FORK_FREE_CALIBRATION_SEEDS"]` and one new
  `seed_guard.calibrating(...)` block in `calibrate_break_forks` (generation and scoring only).
- A3 slow-tier stamp: edit `tests/slow_stamp.py` `STAMPED_FILES` to **add**
  `break_fork_free_calibration.json`, `tests/break_fork_calibration.py`, the two new slow modules
  and their `tests/` imports (`breaks.py`, `forks.py`, `regions.py`, `truth_match.py`,
  `shared_cache.py`, `binning.py` as imported); `test_stamped_files_cover_the_slow_tier` forces
  it. Strengthens the stamp.
- A4 timeouts: `pytest.mark.timeout(CALIBRATION_TIMEOUT_S)` on the new slow tests (07
  precedent).
- A6 re-store of `PACKAGE_BREAK_FORK_*` after a step-8 driver re-run (lockfile edit).

Not touched: tolerances of 09/10, pass counts, `pyproject` (the `held_out` and `slow` markers
already select the new modules; marker text unchanged), `conftest.py`, skips, suppressions. The
Makefile change is limited to the two help strings approved above (no recipe change).

## 11. Risks

- R1 Fake regions carry high-E fake breaks (109797: E 0.54-0.80). Full-frame calibration frames
  cannot show that mechanism; P1 arm (ii) measures it and arm (iii) its growth at a looser stripe
  threshold. If such frames exceed about 2.5 % of calibration frames, `T_b` rises past the B4
  stop level. P1 decides before anything is frozen (step 1 stop rules).
- R2 Several fakes on one frame make AC 2's count exceed the frame-rate bound: P1's 1.5× rule
  (O2).
- R3 Ties at exactly the floors: Fork E is discrete (area count / (2R)²; at P 5 E = 0.3 is 120
  px), so `>` can drop a Fork that `>=` reported. The 09/10 seed tests catch it at step 2; a
  red is a stop for the orchestrator.
- R4 The break/Fork file goes stale when the stripe calibration or the finders change: the fast
  stripe-digest test (N4) catches a stripe re-store at `make check`; the reproduction in
  check-slow (or held-out, OQ8 prefix branch) catches finder drift; the CLAUDE.md procedure says
  what to do.
- R5 check-slow grows; OQ8's P1-based branch caps it near 25 min.
- R6 If the floors bind, the AC 2 held-out test has little power (bound ~29, expected count near
  0). Mitigation: the measured count and its exact upper limit are the claim users read
  (docstring, ADR 0003), not "the test passed".

## 12. Settled

All open questions (OQ1-OQ8) and review items (B1-B6, O1-O5, N1-N12, Codex's extra, the critic's
missed items, the glossary naming) are ruled in `11-rulings.md` (B6 and N9-N12 under "Closing check") and folded above. Nothing is left
open. Two outcomes are decided by P1 against rules pre-declared here: the OQ8 reproduction size
(section 8) and whether to stop (step 1). Any P1 stop, P1 per-case alarm, red 09/10 seed at step
6, or red held-out look goes to the orchestrator; none is resolved by editing a threshold, floor,
recipe or seed.
