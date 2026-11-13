# Plan: agent-gates ticket 07, seed-breadth split for the inner loop

Base `21487c9`. Step 0 is done: its numbers are in the ticket's Comments (2026-11-13, "step 0"),
log `07-step0-durations.log`. Revised after the plan review (`07-plan-review.md`) with the
orchestrator's rulings (section 12).

**Step-0 times are noisy.** The run started at 1-min load 2.05. It was 1.43x slower than ticket
06's closing `make check` of the same 1009 tests. Identical work varied up to 6x: the same
512x512 frame took 16.70 s in `test_partial_region_*[71]` and 2.62 s in
`test_mask_overlaps_*[71-scorched]`, which is the same `generate` + `analyse` under a different
cache key (B2). The per-case spread in the ticket's step-0 Comment ("10.4 s and 16.7 s for the
Period 3 and 5 cases", "8.8-25.6 s at seed 77") is load spikes, not detector cost. The
implementer's closing Comment corrects that line. Below, times are step-0 sums used as relative
costs. "Idle" estimates are step-0 x 0.70.

Approval scope (ticket Comments, owner, 2026-11-13):
1. the `test-fast` recipe, `-m "not slow and not wide"`;
2. the `wide` marker line in `[tool.pytest.ini_options]`, and the collection-time check in
   `tests/conftest.py`;
3. one **added** lockfile line for the new constant.

Everything below stays inside that scope, except where it is marked **OUT OF SCOPE**.

**Stamped or not** (`tests/slow_stamp.py` `STAMPED_FILES`): `Makefile`, `pyproject.toml`,
`tests/protected.py` and `tests/conftest.py` are stamped, so `make check-slow` is due at the end.
`tests/test_analyse.py`, `tests/regions.py`, `tests/inner_loop.py` (new) and
`tests/test_inner_loop.py` (new) are not stamped.

## 1. The helper: `tests/inner_loop.py` (new, not stamped)

```python
WIDE = pytest.mark.wide

def inner(values, *, keep=INNER_LOOP_SEED_COUNT, key=None, multi=False) -> list:
    """Parametrize values for the seed-breadth split. A value whose key (key(value), default the
    value itself) is among the first `keep` distinct keys, in order, stays plain; every other
    value gets WIDE. multi=True: each value is the tuple of argvalues for several argnames
    (pytest.param(*value, marks=WIDE)); multi=False: one argname, the value as is
    (pytest.param(value, marks=WIDE)), even when that value is a tuple."""

def diagonal(seeds, cases, *, keep=INNER_LOOP_SEED_COUNT) -> list:
    """The full cross-product as multi-argname tuples (seed, *case) or (*case, seed), in the
    order and with the ids of today's stacked parametrize. The inner loop keeps case i once, at
    seeds[i % keep]; every other pair is WIDE."""
```

- The caller states the argname arity with `multi` (review N2). The helpers never infer it from
  `isinstance(value, tuple)`.
- A value that is already a `pytest.param` keeps its own `id` and marks, and gets WIDE added.
- **Ids must not change.** The id diff (section 10) checks this.
- **Home: a new module, imported only by `tests/test_analyse.py` and `tests/test_inner_loop.py`.**
  `tests/conftest.py` must not import it. `test_stamped_files_cover_the_slow_tier`
  (`tests/test_slow_stamp.py:249`) follows `tests/conftest.py`'s local imports, so a conftest import
  would force the module into `STAMPED_FILES`. That is an edit to `tests/slow_stamp.py`, which is
  **OUT OF SCOPE**.
- `tests/inner_loop.py` imports `protected` only for the constant.

## 2. The constant and the lockfile

In `tests/protected.py`, after `TEST_SEED_BLOCK`:

```python
# make test-fast (ticket agent-gates/07): the first this-many seeds of a seed range run in the
# inner loop; the rest are pytest.mark.wide (tests/inner_loop.py) and run in make check only.
INNER_LOOP_SEED_COUNT = 2
```

- **Its value stays 2.** Lowering it is the owner's call, made only after the measured run
  (ruling O1).
- The name must not end in `_TEST_SEED(S)`. `test_seed_sets_are_disjoint_and_unused`
  (`tests/test_feasibility_gate.py:77`) reads such names as seeds and would require 2 to lie in
  `TEST_SEED_BLOCK`.
- One added lockfile line (approval item 3), after line 112
  (`protected :: TEST_SEED_BLOCK :: range(10, 100)`):

  ```
  protected :: INNER_LOOP_SEED_COUNT :: 2
  ```

- No existing lockfile line changes.

## 3. Every parametrization to change (`tests/test_analyse.py`)

- "Inner" means the unmarked items.
- "est." is the step-0 seconds of the inner items, with cache effects included.
- Unlisted parametrizations stay unmarked: the error-path tests at lines 173, 670 and 974,
  `test_report_converts_to_json` at line 211, and every parametrization outside
  `tests/test_analyse.py` (about 26 s in total).

| line | test | today | inner (unmarked) | est. s |
|---|---|---|---|---|
| 92 | `test_stripe_free_mottled_frames_are_not_striped` | 20 seeds | `inner(SEEDS)`: 10, 11 | 1.5 |
| 101 | `test_clear_stripes_in_mottle_are_found_and_measured` | 20 seeds (CASES[seed % 10]) | `inner(SEEDS, keep=len(CASES))`: 10-19, every CASES entry once (Q1) | 6.0 |
| 125 | `test_clear_full_frame_stripes_are_found_and_measured` | 7 zipped cases x 2 noise | all 14 (Period/Angle cases) | 8.2 |
| 144 | `test_profile_only_frame_is_not_striped` | 10 seeds x 3 noise | `inner(PROFILE_ONLY_TEST_SEEDS)` x all noise: 6 | 5.3 |
| 264 | `test_strong_stripes_are_measured` | 5 seeds x Period {5, 12} | `diagonal`: (P5, 20), (P12, 21) | 7.0 |
| 289 | `test_modulation_depth_is_relative_to_local_envelope` | 3 seeds x 2 noise | `inner(ENVELOPE_TEST_SEEDS)` x both: 4 | 2.1 |
| 322 | `test_period_and_angle_extremes_are_detected` | 8 zipped cases | all 8 | 5.8 |
| 334 | `test_multiscale_mottle_is_handled` | 10 seeds | `inner`: 20, 21 | 2.7 |
| 345 | `test_borderline_striped_frame_has_finite_measurements` | 5 BORDERLINE cases | all 5 (frame cases, cheap) | 3.5 |
| 359 | `test_partial_region_is_reported_with_its_measurements` | 10 seeds (512x512) | `inner`: 66, 67; **and pass `"scorched"` explicitly** to `single_region_case` (B2) | 6.4 |
| 376 | `test_depth_is_measured_on_the_region_interior` | 2 regression cases | both | 5.7 |
| 387 | `test_mask_overlaps_the_true_region` | 10 seeds x 2 Mottle | `diagonal`: 66-scorched (now the same cache key as line 359), 67-multiscale | 3.0 |
| 396 | `test_two_regions_with_different_periods_are_reported_separately` | 2 seeds x 3 pairs (640x1024) | 76-(5, 12) only, through the shared cache (section 5) | 6.8 |
| 441 | `test_region_below_the_minimum_is_not_reported` | 2 seeds x 6 cases x 4 shapes | shape x Period cover: 12 (section 4) | 11.0 |
| 451 | `test_region_above_the_minimum_is_reported` | 2 seeds x 6 cases x 3 shapes | shape x Period cover: 9 | 8.5 |
| 462 | `test_stripes_on_one_flank_of_the_envelope_are_found` | 3 seeds (512x512) | `inner`: 66, 67 | 6.5 |
| 495 | `test_dark_area_is_never_reported_as_striped` | 3 seeds x 3 cases + 1 regression | `inner([...ENVELOPE x DARK_CASES...], key=seed, multi=True)`: seeds 20, 21 x 3 cases; then `*DARK_REGRESSION_CASES` appended **unmarked, outside `inner()`** (B3) | 5.4 |
| 623 | `test_verdict_is_striped_exactly_when_a_region_is_reported` | 18 frames x 6 kinds | 33 items (section 4) | 23 |
| 652 | `test_lowering_the_threshold_keeps_reported_regions_unchanged` | 7 frames x 15 pairs | 6 items (section 4), all cached | ~0 |
| 722 | `test_report_counts_spike_pixels` | 10 seeds x 4 kinds | `diagonal`: each kind once, seeds 81 and 83 alternating | 9.0 |
| 739 | `test_saturated_spikes_are_counted_as_spikes` | 10 seeds x 2 kinds | `diagonal`: 2 | 1.3 |
| 828 | `test_spike_free_frames_report_no_spikes` | 66 frames | 22: mottled seeds 10, 11 x both m (4); full-frame all 14 (cases); profile-only 20, 21; phase-break both | 12 |
| 844 | `test_report_counts_clipped_pixels` | 10 seeds | all 10 stay unmarked (aggregate feeder, below) | 11.4 |
| 851 | `test_clipped_and_spike_totals_match_at_a_peak_level_clip` | 10 seeds | `inner`: 81, 83 | 1.2 |
| 880 | `test_spikes_do_not_change_the_verdict_on_stripe_free_frames` | 20 seeds x 2 clip | all 40 unmarked (Q3 (a)); `_spike_pair_scores` caches the free score per seed (below) | ~35 |
| 902 | `test_clipped_stripe_free_frames_are_not_striped` | 20 seeds | `inner`: 10, 11 | 1.2 |
| 947 | `test_clipping_does_not_harm_a_partial_region` | 5 seeds (512x512) | `inner`: 81, 83 | 6.0 |
| 959 | `test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion` | 5 seeds (512x512, 2 analyses) | `inner`: 81, 83 | 11.5 |

Notes:

- **Aggregates over a cache.** Two tests are unparametrized and keep their seed sets, because no
  seed range may change:
  - `test_clipped_stripe_peaks_keep_the_modulation_depth` (line 915) uses all 10 `CLIP_TEST_SEEDS`.
  - `test_spikes_leave_the_typical_stripe_free_score_unchanged` (line 893) uses all 40 `SPIKE_PAIRS`.

  If the parametrized tests that fill their caches were cut, each aggregate would pay the
  remaining analyses as one item, about 9 s and 42 s. So the feeders stay unmarked: cutting them
  saves nothing and creates one slow item.
- **Free-score cache.** `_spike_pair_scores(seed, clip)` analyses the same stripe-free frame for
  `clip=False` and `clip=True`. A `@cache def _free_score(seed)` holds
  `analyse(generate(seed=seed, shape=SHAPE, modulation_depth=0.0, **TYPICAL).frame).score`.
  `_spike_pair_scores` calls it with the same positional spelling every time and still generates
  `free` for `free.clean.max()`. This saves 20 of the 80 analyses, in `make check` too (46.3 s ->
  about 35 s). It returns a float, so it shares no mutable state.
- **`diagonal` changes the parametrize layout**: one `parametrize` with every argname, instead of
  stacked decorators.
  - Argnames go in the id order pytest gave the stacked form, the decorator nearest the function
    first. Today's ids:
    - `test_strong_stripes_are_measured[5-20]`: period-seed;
    - `test_mask_overlaps_the_true_region[66-scorched]`: seed-mottle;
    - `test_report_counts_spike_pixels[typical-m0-81]`: kind-seed;
    - `test_region_below_the_minimum_is_not_reported[78-3--10-both]`: seed-period-angle-shape.
  - Only the run order changes. The id diff proves the ids stay the same.
- **What `inner()` keeps per range:**
  - `SEEDS` (`MOTTLED_TEST_SEEDS`): 10, 11;
  - `PROFILE_ONLY_TEST_SEEDS`, `MULTISCALE_TEST_SEEDS`, `ENVELOPE_TEST_SEEDS`: 20, 21;
  - `REGION_TEST_SEEDS`: 66, 67;
  - `SPIKE_TEST_SEEDS`, `CLIP_TEST_SEEDS`, `PARTIAL_CLIP_TEST_SEEDS`: 81, 83.
- **Lists the coverage tests read.** Every parametrize list that section 6's coverage asserts read
  becomes a module-level name in `tests/test_analyse.py`: `CLEAR_STRIPES_PARAMS`, `VERDICT_PARAMS`,
  `LOWERING_PARAMS`, `BELOW_SIZE_PARAMS`, `ABOVE_SIZE_PARAMS`, `DARK_PARAMS`,
  `TWO_REGION_PARAMS`. The decorator uses that name, so the test reads exactly what pytest
  parametrizes.

## 4. The cross-product subsets

### Verdict test (line 623): every sweep frame, every threshold kind, not their product

Within each family (`free-*`, `striped-*`, `borderline-*`), the frames are seed repetition: the
first 2 of each are kept, in `SWEEP_FRAMES` order. Every single frame is kept.

Inner items:

| frame | kinds kept | items | analyses |
|---|---|---|---|
| `striped-10`, `free-10`, `borderline-22-20`, `constant` | all 6 | 4 x 6 = 24 | 6 each |
| `striped-11`, `free-11`, `borderline-13-5`, `overlapping-extents` | `THRESHOLD`, `zero` | 4 x 2 = 8 | 2 each |
| `two-region` | `THRESHOLD` | 1 | 1, shared with line 396 (section 5) |
| the other 9 frames | none (`wide`) | 0 | 0 |

- **33 items.** Every kind runs on 4 frames, and every frame family runs at least at `THRESHOLD`.
- `zero` on `overlapping-extents` keeps the lowering test's `len(zero.regions) >= 2` assert in the
  inner loop.
- Est. 23 s at step 0: `striped-10` 4.6, `free-10` 6.4, `borderline-22-20` 4.4, `constant` 0.4,
  the four 2-kind frames 7.6.
- **Implementation.** Build `VERDICT_PARAMS` from a table `SWEEP_INNER_KINDS = {name: kinds}`
  whose keys come from code: `f"striped-{MOTTLED_TEST_SEEDS[0]}"`, `f"borderline-{s}-{p}"` from
  `BORDERLINE[0]`, and so on. Do not write new literal seeds. Use argnames `("name", "kind")` in
  that order, so the ids stay `name-kind`.
- **The family reading is recorded** (review N4). The verdict subset keeps borderline 22-20 and
  13-5 (Periods 20 and 5) and drops the Period-8 borderline frames. All 5 borderline frames stay
  in the inner loop through `test_borderline_striped_frame_has_finite_measurements`. The
  implementer writes this reading ("sweep frame kind = family"), with the id lists, into the
  ticket Comment that proves the "every frame kind" criterion.

### Lowering test (line 652): a threshold-pair subset with every kind

On `striped-10` only, the subset is:

| pair (low, high once sorted) | what it checks |
|---|---|
| (`zero`, `THRESHOLD`) | the wide drop: high has regions, and all of them are kept unchanged at 0 |
| (`zero`, `below-score`) | high just under the score: regions are present |
| (`below-score`, `score`) | kind coverage only: `score` reports no regions, so the loop is empty |
| (`above-score`, `inf`) | kind coverage only: no regions on either side |

- Every kind appears: `zero`, `THRESHOLD`, `score`, `above-score`, `below-score`, `inf`.
- Only a pair whose high side is below the score can compare non-empty regions. So the first two
  pairs carry the teeth. The test's comment says the last two are there for kind coverage
  (review N1).
- On `striped-11` and `overlapping-extents`, only (`zero`, `THRESHOLD`) runs. It reads their
  cached verdict analyses.
- `two-region` and `striped-12..14` are all `wide`. `two-region` stays out of the lowering inner
  set because of the "analysed once" rule.
- 6 inner items. All are cached when the verdict test has run first, which is file order (`--ff`
  reorders only after a failure). Est. ~0 s, and at most about 4 s on a cold cache.

### Size tests (lines 441, 451): every shape, every Period, every SIZE_CASE

- Today: 2 seeds x 6 (Period, Angle) x 4 shapes (below), or 3 shapes (above).
- Inner: each (shape i, Period j) pair once, at Angle `(-10, 10)[(i + j) % 2]` and seed
  `MIN_SIZE_TEST_SEEDS[i % 2]`.
- Below: 12 items. Above: 9 items.
- Every shape meets every Period. Every Period meets both Angles, so all 6 `SIZE_CASES` appear in
  each test.
- Est. 11.0 + 8.5 s.
- Not chosen: a 6-item cover, each case once with the shapes cycling. It would save about 10 s
  more, but it leaves some shapes without the P3 or P20 boundary.

## 5. The 640x1024 two-region frame: analysed once (Q2, settled)

Today the frame is analysed 12 times: 6 in line 396 and 6 kinds in the verdict test. The
lowering test reads the cache.

- A `@cache` helper `two_region_case(seed, left, right) -> (Synthetic, Report)` goes in
  `tests/regions.py` (not stamped), next to `single_region_case`. It follows the same pattern as
  `single_region_case`, `_sweep_report` and `_clipped_full_frame`.
- It memoises one identical call: `generate(seed=seed, shape=TWO_REGION_SHAPE, mottle="scorched",
  regions=two_regions(left, right), **TYPICAL)` followed by `analyse(frame)`.
- Line 396 calls `two_region_case(seed, left, right)`. `SWEEP_FRAMES["two-region"]` and
  `_sweep_report("two-region", "THRESHOLD")` call `two_region_case(TWO_REGION_TEST_SEEDS[0],
  *TWO_REGION_PAIRS[0])`. Both sites are positional, so both use the key `(76, 5, 12)`.
- `_sweep_report` gets one `if` for the `two-region`/`THRESHOLD` case. The other kinds still call
  `analyse(frame, threshold=...)` on that frame.
- **No test may mutate the cached Report's arrays.** `two_region_case` sets
  `report.labels.setflags(write=False)` before returning, and the same for every array field of
  the `Report` and `Synthetic` it hands out. A later in-place write then raises, so it cannot
  silently corrupt another test. Every current reader of these arrays only reads. The verdict
  test passes the cached frame to `analyse(frame, threshold=...)`. If `analyse` refuses a
  read-only frame, freeze only the `Report` arrays and record that in the Comments: a
  read-only-frame failure is a finding about `analyse`, not something to fix by touching the
  detector in this ticket.
- Inner: line 396 keeps `76-5-12` only. The verdict test keeps `two-region-THRESHOLD`. The lowering
  test has no `two-region` item. Together that is one analysis.
- Est. 6.8 s.
- `make check` also saves one analysis here.

## 6. The collection-time all-`wide` check, and the committed coverage tests

**Where:** inline in `tests/conftest.py` (approval item 2), with no new local import (section 1):

```python
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    # Partial collections are exempt: --lf drops passed items while collecting
    # (cacheprovider's LFPluginCollWrapper), and a "file::test[id]" arg selects one item.
    if config.getoption("lf", False) or any("::" in arg for arg in config.args):
        return
    only_wide = _functions_with_only_wide_items(items)
    if only_wide:
        raise pytest.UsageError(
            "test functions with only `wide` parameters would leave make test-fast "
            "(ticket agent-gates/07): " + ", ".join(only_wide)
        )
```

- `config.getoption("lf", False)`: plain `getoption("lf")` raises `ValueError` under
  `-p no:cacheprovider` (B1).
- `tryfirst`, so the check sees every collected item before `-m`, `-k` and `--deselect` remove any.
  It fires on the full collection under `make check`, `make check-slow` and `make test-fast`.
- `--ff` is safe: the collection wrapper is registered only for `--lf` (review B1).
- Any `::` arg is exempt, whatever its spelling (`./tests/...`, an absolute path, another cwd;
  review N3). The run is the user's explicit selection.
- Grouping is by function: `item.nodeid.partition("[")[0]`.
- An item is wide when `item.get_closest_marker("wide")` is set. That also catches a function- or
  class-level `@pytest.mark.wide`.
- Exit: `UsageError` gives exit 4 and `ERROR: ...` on stderr, before any test runs.

**The check's test** goes in `tests/test_inner_loop.py` (new, not stamped). The planted function
is written at run time and never committed.

- In `tmp_path`, write:
  - `conftest.py` = the real `tests/conftest.py` text, so the hook under test is the real one;
  - `pytest.ini` with the `slow` and `wide` markers and `strict_markers = true`;
  - `test_planted.py` with an all-`wide` parametrized function, a function marked
    `@pytest.mark.wide` as a whole, and a mixed function built with `inner_loop.inner`.
- Run `[sys.executable, "-m", "pytest", ...]` with `cwd=tmp_path` and
  `PYTHONPATH=<repo>/tests`. Assert:
  1. `--collect-only -q -p no:cacheprovider`: exit 4. Both all-wide names are in the output; the
     mixed one is not.
  2. The same, with the two all-wide functions removed: exit 0.
  3. The all-wide functions present, with a `test_planted.py::name[id]` arg: exit 0.
  4. `--lf` after a recorded failure (B1). The cache provider stays on. Plant a mixed function
     whose `wide` parameter fails. First run: exit 1. Rerun with `--lf`: exit 1 (the test runs and
     fails again), not 4.

  The subprocess runs cost about 3-5 s together.

**Committed coverage asserts** in `tests/test_inner_loop.py`. They `import test_analyse` and
read the module-level lists of section 3. "Inner" means a param without the WIDE mark. The
all-`wide` check guarantees only one item per function; these asserts guarantee the subsets:

- verdict: the inner kinds are every `SWEEP_THRESHOLDS` kind, and the inner frames cover every
  family (`free`, `striped`, `borderline`, `two-region`, `overlapping-extents`, `constant`);
- lowering: the kinds of the inner pairs are every kind, and the inner frames are
  `overlapping-extents` and at least one `striped-*`;
- two-region: exactly one inner item in line 396 (`76-5-12`), exactly one inner verdict
  `two-region` item (`THRESHOLD`), and no inner lowering `two-region` item;
- size: below covers all 4 `SIZE_SHAPES`, above covers its 3 shapes, both cover every
  (shape, Period) and all 6 `SIZE_CASES`;
- dark: the inner cases are all of `DARK_CASES`, and every `DARK_REGRESSION_CASES` entry is
  unmarked;
- clear stripes (Q1): the inner seeds hit every `CASES` index;
- the helpers: `inner` keeps exactly the first `INNER_LOOP_SEED_COUNT` keys and keeps ids; `multi`
  is honoured; `diagonal` returns the full cross-product and keeps each case once;
- Makefile: `make -n test-fast` (the `_dry_run` pattern of `tests/test_slow_stamp.py:296`) has
  `-x --ff` and ends with `-m "not slow and not wide"`.

## 7. Gate config

`Makefile`:

```make
test-fast:                  ## inner loop: first seeds only (not slow, not wide; tests/inner_loop.py), stop at first failure, failures first
	$(PYTEST) -x --ff -m "not slow and not wide"
```

The command-line `-m` replaces `addopts`' `-m "not slow"`. The `check` and `check-slow` recipes
do not change: they are outside the approval.

`pyproject.toml`, `markers`:

```toml
    "wide: seeds and cross-products beyond the inner loop's first ones (tests/inner_loop.py); deselected by make test-fast, run by make check",
```

## 8. CLAUDE.md (Gates)

In the **When** bullet, replace "`make test-fast` after every change (stops at the first failure,
reruns failures first)." with:

> `make test-fast` after every change (stops at the first failure, reruns failures first). It runs
> every test function and case but only the first `INNER_LOOP_SEED_COUNT` seeds (`tests/protected.py`)
> and a covering subset of cross-products (`-m "not slow and not wide"`; the rest carry
> `pytest.mark.wide`, `tests/inner_loop.py`). So a seed-specific failure can first appear at
> `make check`, at the end of the work. After `make check` fails on a `wide` id, `make test-fast`
> deselects that id and goes green: rerun the failing id directly
> (`uv run --locked pytest '<id>'`, or `--lf`), then `make check`.

In the weakening list, the narrowing bullet becomes:

> narrowing the selected tests (`addopts`, `-m`, `-k`, `--deselect`, `testpaths`, the Makefile),
> including adding `wide` to a parameter or a test, or lowering `INNER_LOOP_SEED_COUNT`;

## 9. Projection, and missing the target

**Projection.** The sum of section 3, plus the unparametrized `test_analyse.py` tests (about 8 s)
and the other files (26.4 s), is **about 255 s at step-0 speed, or about 180 s idle** (x 0.70).

- Slowest inner item: the shared two-region analysis, 6.8 s at step 0.
- Next slowest: `test_heavily_clipped_*[81]`, 5.8 s.
- So "slowest test about 10 s or less" holds on these numbers. "About 2 minutes" probably does
  not.
- The big blocks: Q3's spike pairs (about 35 s), the verdict sweep (23 s) and the size covers
  (19.5 s).

**`make check` also gets faster**, for every seed:
- one two-region analysis;
- 20 free-frame analyses (`_free_score`);
- 10 scorched 512x512 analyses (B2's shared key).

That is about 30-40 s at step-0 speed.

**Timing run (implementer, after the code review's fixes, before the closing gates):**
- Run it on an idle machine (1-min load below 2), in the background, logged.
- Command: `PYTEST_ADDOPTS="--durations=10" make test-fast`. It is the real recipe, plus the top-10
  durations.
- Alongside it, a logger appends `uptime` every 30 s.
- Quote: the command, exit status, summary line, wall time, load before and after, and the top 10.
- If one item exceeds 10 s while the logged load was above 2, rerun once (review B4). Quote both
  runs.

**If the measured time is over about 2 min:**
1. The implementer reports the measured numbers and the work goes on to the closing gates'
   preparation. Nothing is cut further, and `INNER_LOOP_SEED_COUNT` stays 2.
2. Before the closing gates, the orchestrator asks the owner **once**, with the measured numbers:
   - (i) accept about 3 min as the ticket's result; or
   - (ii) approve Q3 (b) (**OUT OF SCOPE** today): mark the spike-pair test and its aggregate
     `wide`, with a named exemption in the all-`wide` check. That saves about 35 s.

   Lowering `INNER_LOOP_SEED_COUNT` is a further owner call, at the same time and only if the
   owner raises it.
3. Then come `make check-slow` and `make check`.

## 10. Acceptance criteria and how each is verified (each on its real path)

| criterion | verified by |
|---|---|
| Step 0 | Done: ticket Comment 2026-11-13 "step 0", log `07-step0-durations.log`. |
| `wide` registered; `inner` helper; constant in `tests/protected.py` | `strict_markers` on the real config: a run fails if `wide` is unregistered. `tests/test_inner_loop.py` tests the helpers. `test_protected_numbers_match_the_lockfile` passes with the one added line. |
| `test-fast` selects `not slow and not wide` and keeps `-x --ff` | The `make -n test-fast` assert (section 6) runs on the real Makefile. |
| `check` and `check-slow` select the same ids and counts | The real selections after the change: `uv run --locked pytest --collect-only -q` and `uv run --locked pytest -m slow --collect-only -q`, diffed against `07-ids-check-before.txt` and `07-ids-check-slow-before.txt`. Only the summary line's time may differ. Expected 1009 and 4. Quoted in Comments. |
| `check` runs every test that `test-fast` runs | `uv run --locked pytest -m "not slow and not wide" --collect-only -q`: its ids are a subset of the `check` ids (`comm -23` of the sorted lists is empty). Quoted. |
| Every test function, Period/Angle case, frame kind and threshold kind stays | The function set (`sed 's/\[.*//' \| sort -u`) of the test-fast collection equals that of `check`. The coverage asserts (section 6) read the real parametrize lists. The family reading (N4) is in the Comment. |
| Two-region analysed once; 512x512 region tests keep 2-3 cases | The coverage asserts (one inner item at each site, none in lowering). The real-path count is a one-off check, not committed. A `-p` plugin from the scratchpad wraps `denoisifier.analyse` and `denoisifier.analysis.analyse` before collection, so `tests/test_analyse.py` and `tests/regions.py` bind the wrapper. It counts calls on 640x1024 frames over `uv run --locked pytest -p <plugin> -m "not slow and not wide"`, and the expected count is 1. For 512x512, the test-fast ids show two each for lines 359, 387, 462, 947 and 959. |
| A collection-time all-`wide` check with its own test | `tests/test_inner_loop.py` (section 6) runs the real conftest hook in a subprocess, with cases 1-4. It is green in `make test-fast` and `make check`. |
| No tolerance, expected value, timeout, seed range or pass count changes; nothing deleted or moved to slow | `git diff 21487c9 -- tests/protected_numbers.lock` shows one added line only. `test_protected_numbers_match_the_lockfile` passes. The id diffs give the same 1009 and 4. The `git diff` of `tests/` adds no `timeout`, `skip`, `xfail` or `slow`. |
| `make test-fast` takes about 2 min and its slowest test about 10 s | The timing run of section 9 and, if it misses, the owner's answer. |
| CLAUDE.md text | The section 8 diff. |
| Ends on `make check-slow`, then `make check` | Both are due because stamped files changed. Both are quoted per CLAUDE.md "Handoffs quote the gate". |

## 11. Out-of-scope items

- An edit to `tests/slow_stamp.py`: avoided, because the conftest does not import the helper.
- Q3 (b): only through the owner question of section 9.
- Lowering `INNER_LOOP_SEED_COUNT`: an owner call after the measured run.
- Not done, though possible: `test_stripe_free_mottled_frames_are_not_striped` and the sweep's
  `free-*` frames analyse the same frames as `_free_score`. Sharing them would save more in
  `make check`, but it widens this ticket's test plumbing beyond the rulings.

## 12. Rulings and review findings, folded

| item | ruling / disposition |
|---|---|
| Q1 | All 10 seeds in `clear_stripes_in_mottle`, so every CASES entry runs (section 3). |
| Q2 | Shared `two_region_case` cache. The frame is analysed once, and the cached arrays are read-only (section 5). |
| Q3 | (a): the 40 spike pairs stay unmarked. The free score is cached per seed (section 3). |
| O1 | `INNER_LOOP_SEED_COUNT` stays 2. The "lower to 1" fallback is removed. A miss leads to one owner question with measured numbers (section 9). |
| B1 | Folded. `--lf` and any `::` arg are exempt, with `config.getoption("lf", False)`. Test case 4 covers it (section 6). |
| B2 | Folded. Line 359 passes `"scorched"` explicitly. `two_region_case` is called positionally at both sites (sections 3 and 5). |
| B3 | Folded. `DARK_REGRESSION_CASES` is appended unmarked, outside `inner()`. A coverage assert checks it (sections 3 and 6). |
| B4 | Folded. Per-case cost claims are dropped and step-0 times are treated as noisy. Load is logged during the timing run, with one rerun allowed and both runs quoted (top of the plan, section 9). |
| N1 | Folded: the comment says the last two lowering pairs are there for kind coverage, because only a high side below the score has regions to compare. |
| N2 | Folded: the `multi=` argument, because inferring arity from tuples is ambiguous for one tuple-valued argname. |
| N3 | Folded: any `::` arg is exempt, because `config.args` keeps the user's spelling and a nodeid comparison misses some spellings. |
| N4 | Folded: the family reading goes in the ticket Comment with the id lists, so the criterion's reviewer does not re-derive it. |
| N5 | Folded: Q2 (a) is forced by "analysed once", and it is settled. |
| Orchestrator: free-score cache | Folded (section 3). |
| Orchestrator: 33 verdict items | Corrected (section 4). |
| Orchestrator: rerun advice after a `wide` failure | Folded into the CLAUDE.md text (section 8). |
| Orchestrator: committed coverage asserts | Folded (section 6). |
| Orchestrator: `tests/regions.py` not stamped | Noted (top of the plan, section 5). |
