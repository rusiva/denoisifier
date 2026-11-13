# Plan: agent-gates ticket 07, seed-breadth split for the inner loop

Base `21487c9`. Step 0 is done; its numbers are in the ticket's Comments (2026-11-13, "step 0"),
log `07-step0-durations.log`. Times below are **step-0 times**, measured at 1-min load about 2.
That run was 1.43x slower than ticket 06's closing `make check` of the same 1009 tests, so an
"idle" estimate is shown as step-0 x 0.70.

Approval scope (ticket Comments, owner, 2026-11-13): (1) the `test-fast` recipe, `-m "not slow and not wide"`;
(2) the `wide` marker line in `[tool.pytest.ini_options]`, and the collection-time check if it goes in
`tests/conftest.py`; (3) one **added** lockfile line for the new constant. Everything below stays inside
it, except where it is marked **OUT OF SCOPE**.

## 1. The helper: `tests/inner_loop.py` (new, not stamped)

```python
WIDE = pytest.mark.wide

def inner(values, *, keep=INNER_LOOP_SEED_COUNT, key=None) -> list:
    """Parametrize values for the seed-breadth split. A value whose key (key(value), default the
    value itself) is among the first `keep` distinct keys, in order, stays a plain value; every
    other value becomes pytest.param(*value or value, marks=WIDE), with its id unchanged."""

def diagonal(seeds, cases, *, keep=INNER_LOOP_SEED_COUNT) -> list:
    """Every (seed, *case) pair of the full cross-product, in the order and with the ids the
    stacked parametrize gave. The inner loop keeps case i once, at seeds[i % keep]; every other
    pair is WIDE. For cross-products (seed x kind, seed x mottle, ...)."""
```

- Values that are tuples go in as `pytest.param(*value, ...)`; values that are already
  `pytest.param` keep their own `id` and marks, and get WIDE added. Ids must not change: the
  id diff (section 9) is the check.
- **Home: a new module, imported only by `tests/test_analyse.py`.** Not by `tests/conftest.py`:
  `test_stamped_files_cover_the_slow_tier` (`tests/test_slow_stamp.py:249`) follows the local
  imports of `tests/conftest.py`, so a conftest import of `inner_loop` would force
  `tests/inner_loop.py` into `STAMPED_FILES`, which is an edit to `tests/slow_stamp.py` and is
  **OUT OF SCOPE** of the approval. `tests/inner_loop.py` imports `protected` (stamped) only for
  the constant.
- Its own tests: `tests/test_inner_loop.py` (section 6).

## 2. The constant and the lockfile

`tests/protected.py`, after `TEST_SEED_BLOCK`:

```python
# make test-fast (ticket agent-gates/07): the first this-many seeds of a seed range run in the
# inner loop; the rest are pytest.mark.wide (tests/inner_loop.py) and run in make check only.
INNER_LOOP_SEED_COUNT = 2
```

The name must not end in `_TEST_SEED` or `_TEST_SEEDS`: `test_seed_sets_are_disjoint_and_unused`
(`tests/test_feasibility_gate.py:77`) reads those as seeds and would require 2 to lie in
`TEST_SEED_BLOCK`. One added lockfile line (approval item 3), after line 112
(`protected :: TEST_SEED_BLOCK :: range(10, 100)`):

```
protected :: INNER_LOOP_SEED_COUNT :: 2
```

No existing line changes. `tests/protected.py` is stamped, so `make check-slow` is due anyway.

## 3. Every parametrization to change (`tests/test_analyse.py`)

"Inner" = unmarked items. "est." = step-0 seconds of the inner items, cache effects included.
Unlisted parametrizations (error-path tests at lines 173, 670, 974; `test_report_converts_to_json`
line 211; every parametrization outside `tests/test_analyse.py`, about 26 s in total) stay unmarked.

| line | test | today | inner (unmarked) | est. s |
|---|---|---|---|---|
| 92 | `test_stripe_free_mottled_frames_are_not_striped` | 20 seeds | `inner(SEEDS)`: 10, 11 | 1.5 |
| 101 | `test_clear_stripes_in_mottle_are_found_and_measured` | 20 seeds (CASES[seed % 10]) | **Q1**, recommended `inner(SEEDS, keep=len(CASES))`: 10-19, every CASES entry once | 6.0 |
| 125 | `test_clear_full_frame_stripes_are_found_and_measured` | 7 zipped cases x 2 noise | all 14 (Period/Angle cases) | 8.2 |
| 144 | `test_profile_only_frame_is_not_striped` | 10 seeds x 3 noise | `inner(PROFILE_ONLY_TEST_SEEDS)` x all noise: 6 | 5.3 |
| 264 | `test_strong_stripes_are_measured` | 5 seeds x Period {5, 12} | `diagonal`: (P5, 20), (P12, 21) | 7.0 |
| 289 | `test_modulation_depth_is_relative_to_local_envelope` | 3 seeds x 2 noise | `inner(ENVELOPE_TEST_SEEDS)` x both: 4 | 2.1 |
| 322 | `test_period_and_angle_extremes_are_detected` | 8 zipped cases | all 8 | 5.8 |
| 334 | `test_multiscale_mottle_is_handled` | 10 seeds | `inner`: 20, 21 | 2.7 |
| 345 | `test_borderline_striped_frame_has_finite_measurements` | 5 BORDERLINE cases | all 5 (frame cases, cheap) | 3.5 |
| 359 | `test_partial_region_is_reported_with_its_measurements` | 10 seeds (512x512) | `inner`: 66 (P16, 10 deg), 67 (P6, -10 deg) | 6.4 |
| 376 | `test_depth_is_measured_on_the_region_interior` | 2 regression cases | both | 5.7 |
| 387 | `test_mask_overlaps_the_true_region` | 10 seeds x 2 Mottle | `diagonal`: 66-scorched (cached by line 359), 67-multiscale | 3.0 |
| 396 | `test_two_regions_with_different_periods_are_reported_separately` | 2 seeds x 3 pairs (640x1024) | 76-(5, 12) only: see section 5 | 6.8 |
| 441 | `test_region_below_the_minimum_is_not_reported` | 2 seeds x 6 cases x 4 shapes | shape x Period cover: 12 (section 4) | 11.0 |
| 451 | `test_region_above_the_minimum_is_reported` | 2 seeds x 6 cases x 3 shapes | shape x Period cover: 9 | 8.5 |
| 462 | `test_stripes_on_one_flank_of_the_envelope_are_found` | 3 seeds (512x512) | `inner`: 66, 67 | 6.5 |
| 495 | `test_dark_area_is_never_reported_as_striped` | 3 seeds x 3 cases + 1 regression | `inner(..., key=seed)`: seeds 20, 21 x 3 cases, plus the regression case unmarked | 5.4 |
| 623 | `test_verdict_is_striped_exactly_when_a_region_is_reported` | 18 frames x 6 kinds | 23 items (section 4) | 23 |
| 652 | `test_lowering_the_threshold_keeps_reported_regions_unchanged` | 7 frames x 15 pairs | 6 items (section 4), all cached | ~0 |
| 722 | `test_report_counts_spike_pixels` | 10 seeds x 4 kinds | `diagonal`: each kind once, seeds 81 / 83 alternating | 9.0 |
| 739 | `test_saturated_spikes_are_counted_as_spikes` | 10 seeds x 2 kinds | `diagonal`: 2 | 1.3 |
| 828 | `test_spike_free_frames_report_no_spikes` | 66 frames | mottled seeds 10, 11 x both m (4); full-frame all 14 (cases); profile-only 20, 21; phase-break both: 22 | 12 |
| 844 | `test_report_counts_clipped_pixels` | 10 seeds | **all 10 stay unmarked** (see below) | 11.4 |
| 851 | `test_clipped_and_spike_totals_match_at_a_peak_level_clip` | 10 seeds | `inner`: 81, 83 | 1.2 |
| 880 | `test_spikes_do_not_change_the_verdict_on_stripe_free_frames` | 20 seeds x 2 clip | **Q3**; recommended all 40 unmarked | 46.3 |
| 902 | `test_clipped_stripe_free_frames_are_not_striped` | 20 seeds | `inner`: 10, 11 | 1.2 |
| 947 | `test_clipping_does_not_harm_a_partial_region` | 5 seeds (512x512) | `inner`: 81, 83 | 6.0 |
| 959 | `test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion` | 5 seeds (512x512, 2 analyses) | `inner`: 81, 83 | 11.5 |

Notes:

- **Aggregates over a cache.** `test_clipped_stripe_peaks_keep_the_modulation_depth` (line 915,
  all 10 `CLIP_TEST_SEEDS`) and `test_spikes_leave_the_typical_stripe_free_score_unchanged`
  (line 893, all 40 `SPIKE_PAIRS`) are unparametrized and must keep their seed sets (no seed range
  changes). If the parametrized tests that fill their caches are cut, the aggregate pays the
  remaining analyses as one item: about 9 s and 42 s. So the feeders stay unmarked: cutting them
  saves nothing and makes one slow item. For line 880 this is Q3.
- **`diagonal` changes the parametrize layout** (one `parametrize` with all argnames, instead of
  stacked decorators). Argnames go in the id order pytest gave the stacked form: the decorator
  nearest the function first. Today's ids: `test_strong_stripes_are_measured[5-20]` (period-seed),
  `test_mask_overlaps_the_true_region[66-scorched]` (seed-mottle),
  `test_report_counts_spike_pixels[typical-m0-81]` (kind-seed),
  `test_region_below_the_minimum_is_not_reported[78-3--10-both]` (seed-period-angle-shape).
  Only the run order changes; the id diff proves the ids are the same.
- `inner(SEEDS)` on `SEEDS = MOTTLED_TEST_SEEDS` gives 10, 11; on `PROFILE_ONLY_TEST_SEEDS`,
  `MULTISCALE_TEST_SEEDS`, `ENVELOPE_TEST_SEEDS` 20, 21; on `REGION_TEST_SEEDS` 66, 67; on
  `SPIKE_TEST_SEEDS`/`CLIP_TEST_SEEDS`/`PARTIAL_CLIP_TEST_SEEDS` 81, 83.

## 4. The cross-product subsets

### Verdict test (line 623): every sweep frame, every threshold kind, not their product

Frames are seed repetition within each family (`free-*`, `striped-*`, `borderline-*`: first 2
each, in `SWEEP_FRAMES` order), plus every single frame. Inner items:

| frame | kinds kept | analyses |
|---|---|---|
| `striped-10`, `free-10`, `borderline-22-20`, `constant` | all 6 | 6 each |
| `striped-11`, `free-11`, `borderline-13-5`, `overlapping-extents` | `THRESHOLD`, `zero` | 2 each |
| `two-region` | `THRESHOLD` | 1, shared with line 396 (section 5) |
| the other 9 frames | none (`wide`) | 0 |

23 items, every kind on 4 frames, every frame kind on at least one kind. `zero` on
`overlapping-extents` keeps the lowering test's `len(zero.regions) >= 2` assert in the inner loop.
Est. 23 s (step 0: `striped-10` 4.6, `free-10` 6.4, `borderline-22-20` 4.4, `constant` 0.4, the
four 2-kind frames 7.6). Implementation: build the list explicitly as
`[(name, kind) or pytest.param(name, kind, marks=WIDE)]` from a small table
`SWEEP_INNER_KINDS = {"striped-10": SWEEP_THRESHOLDS, ...}`; argnames `("name", "kind")` in that
order, so ids stay `name-kind`. The table must be written from names derived in code
(`f"striped-{MOTTLED_TEST_SEEDS[0]}"`, `BORDERLINE[0]`), not new literals; a literal seed in the
test module is a number outside `tests/protected.py`, which ticket agent-gates/03 forbids in spirit.

### Lowering test (line 652): a threshold-pair subset with every kind

Subset `LOWERING_INNER_PAIRS`, on `striped-10` only:

| pair (low, high once sorted) | what it checks |
|---|---|
| (`zero`, `THRESHOLD`) | the wide drop: high has regions, all kept unchanged at 0 |
| (`zero`, `below-score`) | high just under the score: regions present |
| (`below-score`, `score`) | the verdict boundary: high has none, low has them |
| (`above-score`, `inf`) | both above the score: no regions either side |

Every kind (`zero`, `THRESHOLD`, `score`, `above-score`, `below-score`, `inf`) appears.
Only pairs whose high side is below the score (`zero`, `THRESHOLD`, `below-score`) can compare
non-empty regions, so the first two are the ones with teeth; the last two keep the
`score`/`above-score`/`inf` kinds in. On `striped-11` and `overlapping-extents`:
(`zero`, `THRESHOLD`) only, which reads their cached verdict analyses. `two-region` and
`striped-12..14`: all `wide`. 6 inner items, all cached when the verdict test ran first (file
order, and `--ff` only reorders after a failure): est. ~0 s, at most ~4 s on a cold cache.

### Size tests (lines 441, 451): every shape and every Period, every SIZE_CASE

Today: 2 seeds x 6 (Period, Angle) x 4 shapes (below) / 3 shapes (above). Inner: each
(shape i, Period j) pair once, Angle `(-10, 10)[(i + j) % 2]`, seed `MIN_SIZE_TEST_SEEDS[i % 2]`.
Below: 12 items, above: 9 items. Every shape meets every Period; every Period meets both
Angles, so all 6 `SIZE_CASES` appear in each test. Est. 11.0 + 8.5 s. (A 6-item cover, each case
once with shapes cycling, would save about 10 s more but leaves some shapes without the P3 or P20
boundary; not recommended.)

## 5. The 640x1024 two-region frame: once in the inner loop

Today 12 analyses (6 in line 396, 6 kinds in the verdict test; the lowering test reads the cache).
Inner: line 396 keeps `76-5-12` only, which is the same `generate` call as the sweep's `two-region`
frame (`TWO_REGION_TEST_SEEDS[0]`, `TWO_REGION_PAIRS[0]`, scorched, `Emccd()`), and the verdict test
keeps `two-region-THRESHOLD`. That is two analyses of the same frame unless they share one.
**Q2**, recommended (a): a `@cache` helper `two_region_case(seed, left, right) -> (Synthetic, Report)`
in `tests/regions.py`, next to `single_region_case` (same pattern), used by line 396, and
`_sweep_report("two-region", "THRESHOLD")` returns its report (one `if` in `_sweep_report`; the
frame lambda in `SWEEP_FRAMES` can use `two_region_case(...)[0].frame`). The verdict test then
asserts on the same `Report` the two-region test checked; nothing asserted changes. Under
`make check` this also saves one analysis. Est. 6.8 s (step 0's `76-5-12`).

## 6. The collection-time all-`wide` check

**Where:** `tests/conftest.py` (approval item 2), inline, with no new local import (see section 1):

```python
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    only_wide = _functions_with_only_wide_items(items, config.args)
    if only_wide:
        raise pytest.UsageError(
            "test functions with only `wide` parameters would leave make test-fast "
            "(ticket agent-gates/07): " + ", ".join(only_wide)
        )
```

- `tryfirst` so it sees every collected item before `-m`, `-k`, `--deselect` and `--lf` remove
  any (the mark and main plugins deselect in their own `modifyitems`; cacheprovider's is a
  wrapper that filters after the plain hooks). So it fires under `make check`, `make check-slow`
  and `make test-fast` alike, on the full collection.
- Group by function: `item.nodeid.partition("[")[0]`. "Wide" = `item.get_closest_marker("wide")`,
  which also catches a function- or class-level `@pytest.mark.wide`.
- **Exemption:** a function named in `config.args` with a parameter id (an arg containing `[`
  whose part before `[` is that function's nodeid) is skipped, so
  `pytest 'tests/test_analyse.py::test_x[12]'` (rerunning one wide seed) is not refused. A
  function that pytest collects only in part for any other reason does not exist today.
- Exit: `UsageError` gives exit 4 and `ERROR: ...` on stderr, before any test runs.

**Its test** (`tests/test_inner_loop.py`, new, not stamped; the planted function is written at
run time, never committed): in `tmp_path`, write `conftest.py` = the real `tests/conftest.py`
text, a `pytest.ini` with the `slow`/`wide` markers and `strict_markers = true`, and
`test_planted.py` with: an all-`wide` parametrized function, a function marked
`@pytest.mark.wide` as a whole, and a mixed function built with `inner_loop.inner`. Run
`[sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]` with
`cwd=tmp_path`, `PYTHONPATH=<repo>/tests`. Assert:

1. exit 4, both planted all-wide names in the output, the mixed one not;
2. with the two all-wide functions removed: exit 0;
3. with the all-wide functions present and a parameter-level node id of one of them as the arg: exit 0.

Also in `tests/test_inner_loop.py`: `inner` keeps exactly the first `INNER_LOOP_SEED_COUNT`
keys unmarked and keeps ids; `diagonal` keeps each case once and returns the full cross-product;
and `make -n test-fast` (the `_dry_run` pattern of `tests/test_slow_stamp.py:296`) ends with
`-m "not slow and not wide"` and still has `-x --ff`. The subprocess costs about 1-2 s.

## 7. Gate config

`Makefile`:

```make
test-fast:                  ## inner loop: first seeds only (not slow, not wide; tests/inner_loop.py), stop at first failure, failures first
	$(PYTEST) -x --ff -m "not slow and not wide"
```

The command-line `-m` replaces the `addopts` `-m "not slow"`; `check` and `check-slow` recipes do
not change (outside the approval: they must not).

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
> `pytest.mark.wide`, `tests/inner_loop.py`), so a seed-specific failure can first appear at
> `make check`, at the end of the work.

In the weakening list, the narrowing bullet becomes:

> narrowing the selected tests (`addopts`, `-m`, `-k`, `--deselect`, `testpaths`, the Makefile),
> including adding `wide` to a parameter or a test, or lowering `INNER_LOOP_SEED_COUNT`;

## 9. Projection

Sum of section 3 plus the unparametrized `test_analyse.py` tests (~8 s) and the other files
(26.4 s), with Q1-Q3 as recommended: **about 265 s at step-0 speed, about 185 s scaled to an
idle machine** (x 0.70). Slowest inner item: the shared two-region analysis, 6.8 s at step 0
(8.8 s at seed 77 is not in the inner loop); next `test_heavily_clipped_*[81]` 5.8 s.
So "slowest test about 10 s or less" holds; "about 2 minutes" does **not** on these numbers.

The rest is three blocks: Q3's 46 s, the verdict sweep 23 s, the size covers 19.5 s.
Further cuts, each with its saving at step-0 speed:

| move | saves | scope |
|---|---|---|
| `INNER_LOOP_SEED_COUNT = 1` | about 25 s | in scope (a new constant's starting value; the ticket says "start: 2") |
| Q3 option (b): the spike aggregate and its feeder `wide` | about 44 s | **OUT OF SCOPE**: drops a test function; needs an owner approval and an exemption in the check |
| 6-item size covers | about 10 s | in scope, weaker (section 4) |
| verdict test: the second frame of each family `wide` | about 6 s | in scope |

Recommendation: implement as recommended, measure (`make test-fast` on an idle machine), and decide
with the measured number. If it is over about 150 s, set `INNER_LOOP_SEED_COUNT = 1` before asking
the owner about Q3 (b).

## 10. Acceptance criteria and how each is verified

| criterion | verified by |
|---|---|
| Step 0 | done: ticket Comment 2026-11-13 "step 0", log `07-step0-durations.log` |
| `wide` registered; `inner` helper; constant in `tests/protected.py` | `strict_markers` (a run with an unregistered `wide` fails); `tests/test_inner_loop.py`; `test_protected_numbers_match_the_lockfile` with the one added line |
| `test-fast` selects `not slow and not wide`, keeps `-x --ff` | `make -n test-fast` test (section 6); Makefile diff |
| `check` and `check-slow` select the same ids and counts | `uv run --locked pytest --collect-only -q` and `... -m slow --collect-only -q` after, diffed against `07-ids-check-before.txt` / `07-ids-check-slow-before.txt` (only the summary line's time may differ): 1009 and 4; quoted in Comments |
| `check` runs every test `test-fast` runs | `pytest -m "not slow and not wide" --collect-only -q` ids are a subset of the `check` ids (`comm -23` of the sorted lists is empty); quoted |
| every test function, Period/Angle case, frame kind, threshold kind stays | function set (`sed 's/\[.*//' \| sort -u`) of the test-fast collection equals that of `check`; the case/frame/kind lists of sections 3-4 checked against the test-fast ids by the reviewer; the collection check itself for functions |
| two-region analysed once; 512x512 region tests keep 2-3 cases the test-fast ids: one line-396 id (`76-5-12`), one verdict `two-region` id (`THRESHOLD`), no lowering `two-region` id; with Q2's shared cache that is one analysis (a one-off, uncommitted check: a `conftest`-free wrapper counting `analyse` calls on a 640x1024 frame over `pytest -m "not slow and not wide" -k "two_region or two-region"`, expected 1). 512x512: two ids each for lines 359, 387, 462, 947, 959 |
| collection-time all-`wide` check with its own test | `tests/test_inner_loop.py` (section 6), green in `make test-fast` and `make check` |
| no tolerance, expected value, timeout, seed range or pass count changes; nothing deleted or moved to slow | `git diff 21487c9 -- tests/protected_numbers.lock` shows one added line only; `test_protected_numbers_match_the_lockfile`; id diffs (same 1009 / 4); `git diff` of `tests/` has no `timeout`, `skip`, `xfail`, `slow` additions |
| `make test-fast` about 2 min, slowest about 10 s | background run with `--durations=10` appended by hand (`uv run --locked pytest -x --ff -m "not slow and not wide" --durations=10`, plus the `make test-fast` run itself), idle machine, load before/after, summary line, wall time, top 10 quoted |
| CLAUDE.md text | section 8 diff |
| ends on `make check-slow`, then `make check` | `Makefile`, `pyproject.toml`, `tests/protected.py`, `tests/conftest.py` are stamped; both quoted per CLAUDE.md "Handoffs quote the gate" |

## 11. Open questions

- **Q1** (`test_clear_stripes_in_mottle_are_found_and_measured`, line 101): its Period/Angle case
  comes from `CASES[seed % 10]`, so 2 seeds keep 2 of the 10 cases. (a) keep one seed per case
  (`keep=len(CASES)`, 10 items, +4.8 s): the ticket's "every Period/Angle case" holds for the test
  that measures Period and Angle; (b) 2 seeds, CASES covered only by other tests at other sizes.
  Recommended (a). The other seed-derived-case tests (spike, clip, region tests) are about
  counts and masks, not Period/Angle, and take the plain seed cut; the 512x512 ones are covered by
  the ticket's "two or three cases".
- **Q2** (section 5): (a) shared `two_region_case` cache, once; (b) no sharing, the frame is
  analysed twice (+6.8 s), test code untouched apart from marks. Recommended (a).
- **Q3** (lines 880/893): (a) keep all 40 verdict pairs unmarked, 46 s in the inner loop, no
  slow item; (b) owner approval to mark both `wide` with a named exemption in the collection
  check: drops a test function from the inner loop, against the ticket; (c) cut the feeder to 2
  seeds, the aggregate pays about 42 s as one item, failing "slowest about 10 s". Recommended (a).
- **Step-0 load.** The run started at 1-min load 2.05 (pre-check 1.18) and was 1.43x slower than
  ticket 06's `make check`. Re-running step 0 costs 14 min; the relative costs that set the subset
  would not change. Recommended: no re-run; the end-of-ticket timing run is the one that counts.
