# 10 plan: forks (settled)

**Status: settled for implementation** (planner-2, BASE `ca48498`). This version folds the plan review (`10-plan-review.md`: B1, P1-P3, O1, N1-N7), the orchestrator's rulings (`10-orchestrator.md`, Decisions), the critics (`10-critic-oq1.md`, `10-critic-pq5.md`, `10-critic-p2.md`), the prototype results (`10-prototype-p1.md`, `10-prototype-p2.md`) and the owner's rulings of 2026-11-15. Every number is the frozen prototype value. Section 9 lists where each input went. A departure from this plan is a finding for the orchestrator, not a silent fix.

Ticket: `.scratch/stripe-detector/issues/10-forks.md`. BASE `ca48498`.
Spec: `.scratch/stripe-detector/spec.md` stories 20-23, 38, 43, 48; "Report" (spec.md:106: `forks` is a list of point plus direction ±1); forward model (spec.md:125: `+ charge * atan2(y - y0, x - x0)`); tolerances (spec.md:162: fork position within one Period); robustness (spec.md:141: spikes don't cause fake forks).
GLOSSARY: **Fork** (`_Avoid_`: dislocation, defect, branch), **Phase Break**, **Phase Jump**, **Striped Region**, **Period**, **Frame pixel**. ADR 0001: local phase is the shared foundation for breaks and forks.
Precedent: ticket 09 (plan `.archived/09-plan.md`, Comments in `issues/09-phase-breaks.md`). This plan reuses its seams, its seed policy, its coordinate rules (scaled sensor coordinates inside, frame px in the Report, `frame_px` for the conversion) and its gate reasoning.
Downstream: ticket 11 calibrates the fork evidence scalar (fake forks ≤ ~1/20 frames); ticket 12 draws fork markers (point + direction); ticket 13 owns speed (its perf frame has forks). Ticket 17 owns anything score-moving. A new needs-triage ticket (step 9) owns the break finder on fork frames.

## 0. Scope

- **The score path is untouched**, as in 09 scope C. `score`, `striped`, `threshold` and the set of reported (pre-pass) regions are settled before any fork search. No change to `_grow`, `_merge`, `_phase_steps`, `_refined`, the bank or any score-path constant.
- **Fork-first ordering** (orchestrator ruling on the PQ5 stop rule, option 3 of `10-critic-pq5.md`, prototyped as P2):
  1. a **pre-break fork search** on each reported region, no breaks explained away, gate `_FORK_GATE_EVIDENCE`;
  2. no fork passes the gate: the frozen 09 break pass runs exactly as at BASE (same call, same inputs);
  3. a fork passes the gate: the frozen break pass runs unchanged on the response with those forks explained away (`z · exp(-i · Σ d · atan2(Y - Yf, X - Xf))`);
  4. a **post-break fork search** on the settled regions, on the raw response, with the found breaks explained away; forks with E ≥ `_FORK_MIN_EVIDENCE` are reported.
  One round only (P2's round 2 never triggered: 0 frames).
- **Identity claim** (replaces "purely additive"): **on a frame where the pre-break search accepts no fork, regions, labels, measurements, breaks and warnings equal BASE's**, apart from (a) the new `"forks"` key and (b) the refusal sentence's wording (2.3 step 5, approval A4). On a frame where the gate fires, the break pass reads a corrected field, so its fills, bridges, re-measures and breaks can differ from BASE's. P2 measured this: validation B1 728/728 gate-silent reports identical to BASE, gate fired on 0/384 fork-free and break-only frames.
- **The frozen break finder is not changed**: no `_BREAK_*` constant, no rule, no `_samples` refactor (9, N4). Only its input field changes, and only when the gate fires.
- **Only reported regions are searched** (09's Q7). A fork outside every reported region is not reported.
- **BASE effects of a fork on regions** (notch at the fork pixel, Angle moved over 1°, a split region) are score-path effects for ticket 17's Comments (step 9). AC 4 asks only that the frame is still Striped.
- **No speed work here** beyond sharing the response cache; the cost is measured in step 5b (PQ8).

## 1. Where things stand (BASE `ca48498`)

- `synthetic.generate`: `phase = _phase(...) + _break_phase(...)` (`synthetic.py:354`, `:372`), with the break term on every region's phase. Breaks draw nothing from the RNG; the break-free path does no arithmetic (`if break_phase is not None`). `GroundTruth.phase_breaks: tuple[BreakTruth, ...] = ()`.
- `_local_phase.py` (stamped): `break_response`, `_samples`, `find_phase_breaks`, `FoundBreak` (`side`, `along`, `line_angle_deg`, `jump_rad`), `_finder_sigma_n`, `line_side`, `wrap_jump`, `sensor_coordinates`, `frame_period`, `_BREAK_MIN_FRAME_PERIOD_PX = 2.5`. Module docstring: "Nothing here is fork-specific; ticket 10 adds to this module." `test_local_phase.py:125` `test_a_winding_is_not_a_break` pins that a ±1 winding gives no break on a noise-free field.
- `analysis.analyse` (`analysis.py:316-370`): `_with_phase_breaks(reported, filters, clipped)` returns `[(survivor, found_breaks)]`; then the sort, labels, `_reported_breaks`, the refusal warnings (`_refusal_warning`, built from pre-pass `reported`, `analysis.py:345-351`; sentence "phase breaks were not searched at {bins} binning: ...", pinned at `test_analyse.py:1932` and `:1959`; also the `analyse` docstring at `analysis.py:282`). `_BreakPass._responses` (`analysis.py:1034`) is the per-(Period, Angle) `break_response` cache, built inside `_with_phase_breaks`. `filters` is None only with no survivors (`analysis.py:496-502`).
- `report.py` (in `NOT_STAMPED_SRC`): `PhaseBreak(region, line, jump_rad)`, `transposed()` keeps `jump_rad` (`report.py:172-175`), `Report.phase_breaks`; `UNITS` pinned by `REPORT_UNITS`.
- `cli.py`: the module docstring (lines 3-20) and the argparse description list the JSON keys and already miss `phase_breaks` (09 left them; step 8 fixes both).
- **Speed.** `.gate/bench.json` is from `b90b64e`, 104 commits before BASE and before ticket 09 (7.1-7.6 s; 09 adds about 0.1 s on break-free frames, so the headroom is about 2.3 s at best). P2's single-process timing, not idle (load 1.7-2.5), `p2_out/timing.txt`: bench frame BASE 6.39 s, +0.38 s with the ordering; bench + one fork (gate fires, second break pass) +0.47 s; P 3 full frame +0.22 s. The prototype computed the response twice; production shares it.

## 2. Seams

### 2.1 Generator: `denoisifier.synthetic`

```python
@dataclass(frozen=True)
class ForkPoint:
    """A Fork in the stripes. ``point`` (row, col), px. ``direction`` +1 or -1:
    the stripe phase gains direction * atan2(y - y0, x - x0) (x the column, y the
    row, increasing downward; spec.md:125's charge). Direction +1: going toward
    row 0 past the fork, one stripe becomes two (a row on the row-0 side crosses
    one more stripe); -1 the same going away from row 0. The Report's
    ``Fork.direction`` of a found fork equals this value."""
    point: tuple[float, float]
    direction: int

@dataclass(frozen=True)
class ForkTruth:
    point: tuple[float, float]
    direction: int
```

- `generate(..., forks: Sequence[ForkPoint] = ())`; `GroundTruth.forks: tuple[ForkTruth, ...] = ()`, in the order given. Name `ForkPoint` (not `Fork`) because `denoisifier.Fork` is the Report's, as `PhaseBreakLine` and `PhaseBreak` are.
- Phase: `_phase(...) + _break_phase(...) + _fork_phase(x, y, forks)`, `_fork_phase = Σ_f d_f · atan2(y - y0_f, x - x0_f)`, added to **every** region's phase and to the full-frame phase, like breaks. This is exactly what the prototype's monkeypatch did (`common.py::_patched_phase`, added to every `_phase` return). The term is global: it bends stripes near the fork and, weakly, in other regions (relative change in local frequency about `P / (2π r)` at distance `r`). The docstring says so. The 2π jump of `atan2` along the ray to the left of the fork is invisible in `cos`.
- **No RNG draws.** Branch on `if forks:` so the empty path does no arithmetic.
- **Identity claims**, in the `generate` docstring: (1) `forks=()` is bit-identical to BASE for every noise kind (`_BASE_DIGESTS`, EMCCD included); (2) with forks and Gaussian `noise`, `spikes=0`, no clip, the added noise is the same draw as the fork-free call (`frame - clean` equal within float rounding); no off-fork pixel claim; (3) with EMCCD noise, no pixel claim.
- Validation (`ValueError`): `point` a finite pair; `direction` an `int` (not `bool`) equal to +1 or -1.
- Tests place fork points at half-integer coordinates, so no pixel centre sits on a fork.
- Prose avoids "branch", "dislocation", "defect" (GLOSSARY `_Avoid_`) and "amplitude": say "the ray to the left of the fork", "Fork", "magnitude".

### 2.2 Detection: `src/denoisifier/_local_phase.py` (already stamped)

**Port, do not redesign.** The finder is the frozen prototype's. Read it at the freeze commit (the worktree is locked; read only):

```
git -C .claude/worktrees/agent-a893b57897cdc4f7a show 3922e33:prototypes/p10_forks/finder.py   # find_forks (candidate A, lattice form)
git -C .claude/worktrees/agent-a893b57897cdc4f7a show 3922e33:prototypes/p10_forks/forks.py    # fork_domain (closed domain)
git -C .claude/worktrees/agent-a893b57897cdc4f7a show 3922e33:prototypes/p10_forks/p2.py       # the ordering (_wpb), the correction (_patched_response), search() (crop, domain, break shift)
git -C .claude/worktrees/agent-a893b57897cdc4f7a show 3922e33:prototypes/p10_forks/common.py   # generator term
git -C .claude/worktrees/agent-a893b57897cdc4f7a show 3922e33:prototypes/p10_forks/p2_sign.py  # correction-sign and direction checks
git -C .claude/worktrees/agent-a893b57897cdc4f7a show 3922e33:prototypes/p10_forks/p2_harness.py  # nearbig/pairbig geometry (big_region, build)
git -C .claude/worktrees/agent-a893b57897cdc4f7a show 3922e33:prototypes/p10_forks/p2_timing.py   # PQ8 timing
```

Frozen config (`P2()` defaults at `3922e33`; results `9872cb4`):

| Prototype parameter | Value | Production constant (`_local_phase.py`, one lockfile line each, A1) |
|---|---|---|
| finder | A: lattice residues + square-loop winding | (design) |
| `loop_periods` (R, square-loop **half-size**) | 2.0 | `_FORK_LOOP_PERIODS = 2.0` |
| `min_mag` (interior: fraction of the domain median magnitude) | 0.5 | `_FORK_MIN_MAGNITUDE_FRACTION = 0.5` |
| `band_sigmas` (break band, finder σn units) | 2.0 | `_FORK_BREAK_BAND_SIGMAS = 2.0` |
| `close_periods` (domain closing radius) | 3.0 | `_FORK_DOMAIN_CLOSE_PERIODS = 3.0` |
| `e_pre` (gate) | 0.2 | `_FORK_GATE_EVIDENCE = 0.2` |
| `e_final` (reported) | 0.3 | `_FORK_MIN_EVIDENCE = 0.3` |
| `rounds` | 1 | (no constant: one round) |
| `sign` | −1 | (no constant: the correction is `exp(-1j · d · atan2(...))`, the inverse of the generator term; a comment says so) |
| `max_per_region` | unlimited (1000) | **none**: no cap (the frozen config had none; a cap is untested) |

The plan's earlier names `_FORK_LOOP_RADIUS_PERIODS`, `_FORK_GRID_STRIDE_PERIODS` and `_FORK_MAX_PER_REGION` are dropped (lattice form: every pixel is a centre; no cap). The literal guards inside the prototype function (`H < 3`, `hp.sum() < 8`) are ported as they are; if the implementer lifts one to module level, it gets a lockfile line (A1).

```python
@dataclass(frozen=True)
class FoundFork:
    point: tuple[float, float]   # (Y, X), scaled sensor coordinates (v*row, h*col)
    direction: int               # +1 / -1, the generator's convention
    evidence: float              # winding-component area / (2R)^2; for ticket 11; not in the Report

def fork_domain(pixels, others, period, bins) -> np.ndarray:
    """The region closed by a _FORK_DOMAIN_CLOSE_PERIODS · P disc (sensor geometry),
    holes filled, other regions' pixels removed (forks.py::fork_domain, mode "closed")."""

def find_forks(z, domain, period, angle_deg, bins, breaks: Sequence[FoundBreak] = ()) -> list[FoundFork]:
    """[] under _BREAK_MIN_FRAME_PERIOD_PX (same response, same limit). All candidates,
    sorted by evidence, descending; the caller applies the gate or the minimum E."""
```

- **Algorithm (finder.py, port line for line):** crop to the domain's bbox; interior = domain & |z| ≥ `_FORK_MIN_MAGNITUDE_FRACTION` × median |z| over the domain; demodulate by the median wrapped neighbour carrier (row and column); for each found break, multiply its positive side by `exp(-i·jump)`, then give every pixel within `_FORK_BREAK_BAND_SIGMAS · _finder_sigma_n(...)` of the line the value (and validity) of the point at the band's edge on its own side; residues on 2x2 plaquettes of the wrapped neighbour differences (+1 = the generator's +1); the winding about each pixel = box sum of residues over the square of half-size R (R/v by R/h frame px), counted only where every loop pixel is valid and the square lies inside the crop; connected components of centres with winding +1 (or −1) are candidates: point = centroid, E = component area (sensor px²) / (2R)².
- **Ports to watch:** the prototype's `fork_domain` takes `bins` as an `(h, v)` tuple and unpacks `h, v = bins`; production takes `BinFactors`. `p2.search` crops `z` and the domain to the region's bbox and shifts each `FoundBreak.point` into crop coordinates (`point - (r0·v, c0·h)`); production does the same or works in full-frame coordinates with the same arithmetic.
- **No shared-helper refactor of `_samples`.** The finder keeps its own interior and carrier code, as validated (review N4: a refactor risks moving the break finder's output on 09 frames).
- **Limits in the `find_forks` docstring, worded as measured** (P2 validation unless said; copy from `10-prototype-p2.md` "Limits, worded as measured"): forks within about 4 P of a region edge are not found (found at 1, 2, 3 P from the 0.5 contour: validation 0/20, 0/20, 6/20); two forks are resolved at 4 P apart (`pairbig` 26/27, 09-size `pair` 24/27), 3 P apart only partly (both resolved 5/27 large region, 11/27 09-size); a fork and a break 4 P apart are both found in a large region (`nearbig` 39/40), at 3 P 38/40 validation but 50/60 explore, closer than 3 P both are usually lost (1.5 P 7/40, 2 P 8/40): "undefined closer than 4 P". In 09-size regions (semi-axes 5 by 6.6 P) only a core about 1 by 2.6 P is 4 P from the edge, so forks are found only near the centre there. R was tuned only once (R = 1.5 P, rejected by its declared rule).
- Every `_FORK_*` constant is a module-level number: one lockfile line each (A1).

### 2.3 Wiring in `analyse` (`analysis.py`, stamped)

1. **One response cache** for the break pass and both fork searches: lift `_BreakPass._responses` into a small cache object built in `analyse` (keyed by (Period, Angle), computing `break_response(spectrum, P, A)` as now) and hand it to `_with_phase_breaks`. With no correction set, the break pass's calls and arithmetic are unchanged.
2. **Pre-break search** (before `_with_phase_breaks`): for each reported region **that gets no refusal entry** (the warning's own decision, `frame_period(...) ≥ _BREAK_MIN_FRAME_PERIOD_PX` on the pre-pass region), `find_forks(cache.response(P, A), fork_domain(g.pixels, other reported pixels, P, bins), P, A, bins)`; keep candidates with E ≥ `_FORK_GATE_EVIDENCE`.
3. **Break pass.** None kept: `_with_phase_breaks(reported, filters, clipped, cache)` exactly as BASE. Some kept: the same call with a correcting view of the cache, whose `response(P, A)` returns `z · exp(-1j · Σ_f d_f · atan2(Y - Yf, X - Xf))` for **all** kept forks of **all** regions (Y = v·row, X = h·col over the full response grid), for every (Period, Angle) the pass asks for (as `p2._patched_response`). The raw cache is not modified.
4. **Post-break search**, after the sort and labelling (the fork's `region` is the final label): for each settled `(g, found)` that contains no pixel of a refused reported region (review N3: no search in a region that got a refusal entry), `find_forks(cache.response(g.period, g.angle_deg)` **raw**, `fork_domain(g.pixels, other settled pixels, ...)`, `g.period, g.angle_deg, bins, found)`; keep E ≥ `_FORK_MIN_EVIDENCE`. `find_forks`' own frame-period guard stays as the backstop; the rare settled region re-measured under 2.5 frame px then gets neither forks nor a warning (stated in the docstring; note, 9).
5. **Refusals.** The existing sentence becomes "phase breaks and forks were not searched at {bins} binning: ...", one entry per region as now (A4). The `analyse` docstring (`analysis.py:282`) changes with it.
6. `_reported_forks(label, found_forks, bins)`: each point converted with `_local_stripes.frame_px` (never divide by bins by hand), as `Fork(region=label, point=(row, col), direction=d)`. Order of `Report.forks`: by region label, then point in row-major order.
7. `score`, `striped`, `threshold` and the reported regions are computed before step 2 and never read from it.

### 2.4 Report: `denoisifier.report` (OQ1 ruled: option A, `10-critic-oq1.md` wording)

```python
@dataclass(frozen=True)
class Fork:
    """One reported Fork. ``point`` (row, col) in frame px. ``direction`` +1:
    going toward row 0 of the analysed frame past the fork, one stripe becomes
    two (a row on the row-0 side crosses one more stripe); -1 the same going
    away from row 0. In file layout when transposed, read "column 0" for
    "row 0"; the value is the same in both layouts. ``region`` is the label of
    its Striped Region."""
    region: int
    point: tuple[float, float]
    direction: int
    def to_dict(self): {"region": k, "point": [row, col], "direction": d}  # direction a JSON int
    def transposed(self) -> Fork: point swapped, direction kept
```

- `Report.forks: tuple[Fork, ...] = ()`; `to_dict` puts `"forks"` right after `"phase_breaks"`. `in_file_layout` maps `Fork.transposed` (09 precedent: `PhaseBreak.transposed` keeps `jump_rad`).
- `UNITS["point"]`: `"frame px, (row, col); file layout when transposed (swapped)"`. `UNITS["direction"]`: `"+1: one stripe becomes two going toward row 0 of the analysed frame (toward column 0 in file layout when transposed); -1 the reverse; same value in both layouts"`.
- **No "charge" and no "above/below"** in Report, UNITS or GLOSSARY text. Only `ForkPoint` (generator, no file layout) keeps the `atan2` formula.
- Export `Fork` from `denoisifier.__init__`; add it to the `Report` docstring.
- **Frame px** for the point follows 09's O1. The spec.md:114 edit proposed at 09's close gains: "`forks`: list of {region, point as (row, col) in frame px, direction ±1: +1 splits toward row 0 of the analysed frame}" (owner, at close).

### 2.5 CLI

The JSON gains the key. No flag, no stderr change. Prose only: the `cli.py` module docstring and argparse description list `phase_breaks` and `forks` (review N5; step 8).

## 3. Prototypes (done; nothing to re-run)

- **P1** (`10-prototype-p1.md`, worktree commit `e3fa432`): finder candidate A sound (single 199/200, 0 fakes on every fork-free and break-only set). PQ5 stop rule fired: the frozen break finder fakes breaks on fork pairs and edge forks and loses true breaks near a fork (spread rule). Ruled: option 3, run as P2.
- **P2** (`10-prototype-p2.md`, explore `0264a24`, freeze `3922e33`, results `9872cb4`): the fork-first ordering. Explore pass bar "zero fake breaks on single and pair frames" fired (single 1/200, pair 18/160) and was re-ruled by the orchestrator (option D, `10-critic-p2.md` conditions 1-5). R = 1.5 P run taken with a declared rule and rejected (AC 3 at 3 P 43/60): R = 2.0 P frozen.
- **Validation, once**, seeds 111_600-111_732 (2/3 scale; bars declared in `p2_bars.py` at the freeze commit): B1 identity PASS; B2 AC 3 `nearbig` 4 P 39/40 PASS; **B3 FAIL** (AC 2 100 % per cell, 0 wrong directions, but 4 extra forks in limit cells); **B4 FAIL** (`pair` 4 P 24/27 = 88.9 %; `pairbig` 26/27); B5 fake breaks in served geometry 0 PASS. Gate-off twin on limit cells: P2 31 fake-break frames against BASE 38, worse in no cell. **Owner 2026-11-15: B3 and B4 accepted; build with the frozen config.**
- **Denominators** (review N6), validation / explore: single 133 / 200; full 27 / 40 (per Period 6-7 / 10); binned 27 / 40; `nearbig` 40 / 60 per distance; `pairbig` 27 / 40 per separation; `pair` 27 / 40 per separation; edge 20 / 30 per distance; weak 67 / 100; fork-free and break-only 384 / 624. E margin: largest pre-break candidate E on fork-free and break-only frames 0.000 (explore and validation) against the gate 0.2; true-fork E min 0.313 single, 0.333 full, 0.387 binned (explore).

## 4. Implementation steps (each ends on `make test-fast` green; test-first)

0. **Protected numbers and BASE evidence.** Section 7's numbers in `tests/protected.py`; `FORK_PROTOTYPE_SEEDS` and `FORK_VALIDATION_SEEDS` appended to `USED_SEEDS` with a comment; `FORK_TEST_SEEDS` inside `TEST_SEED_BLOCK`; lockfile lines (A1-A2). A BASE-output script (scratchpad, not committed) saves `to_json()` and `labels` at `ca48498` for: clear stripes; two regions; spikes plus clipped; Stripe-free mottled; a 2x1 frame at `BINNING_TEST_SEEDS[2]`; a typical EMCCD region frame; one 09 break frame with a found break; a 09 `two_break_case` frame; a 09 bridged two-region-crossed frame; 09's refusal frame (review N4).
1. **Generator** (tests first, AC 1): `ForkPoint`, `ForkTruth`, `_fork_phase`, `forks=`; module and `generate` docstrings (forward model line, identity claims, global term).
2. **Report**: `Fork`, `Report.forks`, `to_dict`, `UNITS`, `in_file_layout`, export. Extend `test_report_converts_to_json`'s key list and `REPORT_UNITS` (A3). Unit tests on a hand-built Report: `in_file_layout` swaps the point and keeps the direction; JSON int.
3. **Test helpers.** `tests/forks.py`: `fork_region_case(seed, *, direction, offset, breaks=(), noise=EMCCD, period=None, angle_deg=None)` (09-size `single_region`), `big_region(period, angle_deg)` (round, semi-axes `max(FORK_BIG_REGION_SEMI_PERIODS · P, FORK_BIG_REGION_SEMI_FLOOR_PX)`, at the `REGION_FRAME_SHAPE` centre, `REGION_EDGE_PX`, depth 0.5; = `p2_harness.big_region`), `fork_full_frame_case(...)`, `fork_near_break_case(seed)` (big region), `fork_pair_case(seed)` (big region), cached with `normalised_cache`; binned frames through `tests/binning.py`. `tests/truth_match.py`: `fork_problems` / `assert_forks_match(report_forks, truth_forks, period, bins)` (5.1). Helper unit tests on hand-built `Fork` objects (wrong direction fails; an extra fork fails; 1.01 P fails).
4. **`fork_domain` and `find_forks`, ported** (2.2), tests first, on phasor fields. The noise-free unit field is the finder's real input (09 critic-4 1a): `break_response` of a noise-free generated fork frame divided by the depth. Tests:
   - P in {3, 5, 8, 20}, Angles {0, ±10}, both directions: one fork within `FORK_EXACT_POSITION_TOL_PERIODS` (0.25; P1 noise-free max 0.172 P), right direction, E ≥ `_FORK_MIN_EVIDENCE`;
   - a plane wave → `[]`; the same demodulated at a carrier 10 % off in Period and 3° off in Angle → `[]`;
   - a plane wave on a disc cut by a straight edge → `[]`;
   - a sharp π break field (09's helper) → `[]`; the same with a fork `FORK_NEAR_BREAK_PERIODS` from the line and `breaks=` the found break → the fork only;
   - an opposite pair `FORK_PAIR_SEPARATION_PERIODS` apart → both;
   - the frame-period gate → `[]`;
   - `fork_domain`: a convex region is returned unchanged; a notch narrower than the closing disc is filled; another region's pixels are removed.
   (The draft's "opposite pair closer than the loop → `[]`" is dropped: never measured, and part-enclosing loops can leave a component.) The break finder's tests stay green unchanged (no refactor).
5. **Wiring** (2.3), test-first:
   - `test_a_silent_gate_runs_the_break_pass_as_base`: `find_forks` monkeypatched to return only candidates under the gate: the break pass receives the raw cache; the report minus `forks` equals the pass-only report.
   - `test_a_gated_fork_corrects_the_break_pass_field`: a spy on the cache view the break pass reads: with one gated fork, `response(P, A)` equals `z · exp(-1j · d · atan2(Y - Yf, X - Xf))`; the raw cache is untouched; the post search reads the raw response.
   - `test_the_correction_undoes_the_generator_term` (`test_local_phase.py`, noise-free, as `p2_sign.py`, single region P 8 A 6 / P 14 A -6 / P 3 A 10, both directions): the corrected fork response's phase against the fork-free twin's, over region pixels more than 1.5 P from the fork, has resultant length ≥ `FORK_CORRECTION_MIN_RESULTANT` (P2 measured 1.000; the wrong sign 0.09-0.14).
   - `test_refused_regions_are_not_searched_for_forks` (N3): a region with a refusal entry is passed to neither search (spy on `find_forks`).
   - the refusal-sentence change (A4).
   **5b. PQ8 timing (implementer, here).** On an idle machine (`uptime` load under 1; quote it), single process with single-threaded BLAS as `tests/bench.py` sets it, the bench frame (the one `feasibility.time_full_frame` times: `TIMING_SEED`, `TIMING_CASE` P 8 Angle 0, `PROBE_SHAPE` 400x1600; `p2_timing.py` builds the same with `_frame(TIMING_SEED, DEPTH, PROBE.shape, TIMING_CASE)`), the bench frame with one fork at its centre (gate fires), and the P 3 full frame of `p2_timing.py`: median of 5 `analyse` calls, BASE (`git stash` / a `ca48498` checkout, or the fork steps disabled by monkeypatch) and the new code **in the same run**. Quote the numbers in the handoff and the Comments. Budget: ≤ 0.3 s extra on the bench frame. Over 0.3 s: `make bench` at close (step 10; expected, since P2 measured +0.38 s without the shared cache). **Over 1 s extra, or the bench frame's new time ≥ 9 s: stop and report to the orchestrator** (ticket 13 owns speed; no speed work in ticket 10 beyond the shared cache). A red `make bench` at close is the same finding, never a timeout change.
6. **BASE diff.** Re-run step 0's script: every frame equal after dropping the `"forks"` key, `forks == []`, the only other difference the refusal sentence on the refusal frame. Quote it in the handoff.
7. **AC tests on the real path** (section 5) and the supporting tests.
8. **Docs.** `analyse` docstring (fork-first ordering; searched in reported regions; identity claim of section 0; limits as measured, 2.2; E conservative until ticket 11; refusal sentence, `analysis.py:282`). `Report` / `Fork` docstrings (2.4). `cli.py` module docstring and argparse description: add `phase_breaks` and `forks` (N5). GLOSSARY **Fork**: the direction sentence of 2.4 (no "charge", no "above/below") and "around it the stripe phase winds by 2π". ADR 0001, Consequences, one line: "Forks are found from the winding of the same demodulated local phase; forks found first are explained away before the Phase Break pass, which then runs unchanged." `_local_phase.py` module docstring: drop "Nothing here is fork-specific".
9. **Ticket Comments and close-out records** (implementer writes; the fixer re-checks after review fixes and updates numbers that moved). `issues/10-forks.md` gains `## Comments` with, each dated:
   - **Fired bars, as fired** (not "met"):
     - P1: PQ5 stop rule fired (fake breaks on fork pairs 27/60 opposite, edge 25/90, single 1/200; true breaks lost near a fork, spread rule). Ruled by the orchestrator: option 3 (fork-first) as P2.
     - P2 explore: "P2 pass bar 'zero fake breaks on single and pair frames' fired on explore (single 1/200, pair 18/160). Ruled as stated limits because all 19 frames are gate-silent and identical to BASE, and P2 is equal or better than BASE in every cell." (`10-critic-p2.md` condition 1, verbatim.) Re-ruled by the orchestrator, option D, conditions 1-5.
     - Validation: B3 and B4 "bar failed, owner accepted" (owner 2026-11-15), with the measured values and failing frames (`p2_out/bars_failures.txt`); B1, B2, B5 passed.
   - **Rulings**: OQ1 (option A, reason: 09's `PhaseBreak.transposed` precedent, `analyse(frame.T)` and `--transpose` agree); AC 3 reading (5.3); AC 4 reading (5.2); every approval A1-A4 with its reason.
   - **Frozen config** (2.2 table) with commit `3922e33`, results `9872cb4`; denominators and E margin (section 3).
   - **Limits worded as measured** (2.2), including the region sizes, the 3 P pair result in both region sizes, the edge trade (E_final 0.3 cost the 3 P edge cell: 16/30 without a threshold in P1, 2/30 at 0.3), and the ordering's own harms on explore: weak 111059 (a fake break the correction added), `nearbig` 6 P 111050 (a matched line pushed to 3.16 px against 3.0).
   - **Seeds** (section 7) and **speed** (step 5b, `make bench`).
   - **Owner's real-frame ruling** (2026-11-15): "Rare / regions large": limits kept; the follow-up ticket stays low priority.
   - **New ticket** `issues/18-break-finder-on-fork-frames.md`, `**Status:** needs-triage`, `**Blocked by:** 10`, low priority (owner). Content: the break finder on fork frames: fake breaks on opposite pairs 3 P apart in 09-size regions (validation 7/27, BASE 10/27) and on forks within 3 P of an edge (11/20 at 2 P, 5/20 at 3 P, = BASE), the 1.5-3 P hole next to a break (fork and break both lost), and the fork finder's R untuned (one R = 1.5 P run, rejected). Any fix touches `_BREAK_*` or the finder: fresh explore/validation seeds (111_200-111_599 and 111_733-111_999 are unused, section 7) and 09's criteria re-proved.
   - **Note in ticket 11's Comments**: its held-out frames have no forks, so its fake-defect rate will not see the fake breaks on fork frames; the fork evidence scalar (area / (2R)², gate 0.2, report 0.3, true min 0.31) is for it to calibrate; a fake region gets fake forks (09's 109797 kind).
   - **Note in ticket 12's Comments**: the PNG will draw the fake breaks on close fork pairs and edge forks (above); fork markers are point + direction, +1 = one stripe becomes two toward row 0 of the analysed frame.
   - **Note in ticket 17's Comments**: BASE effects of a fork: the fork pixel is never in a reported region (notch; single 0/200, full 0/40); Angle moved over 1° on 29/200 single (explore, max 1.97°; validation 17/133, max 1.68°; twins 0); 111129 (explore single, P 14): BASE splits the region, IoU 0.534, a fake break 0.4 P from the fork the gate cannot see.
10. **Closing**, after the review fixes (fixer): `make bench` (background, idle; step 5b), then `make check-slow` (stamped files change: `synthetic.py`, `analysis.py`, `_local_phase.py`, `tests/protected.py`), then `make check`. No `make measure`, no re-store, no `make check-held-out` (section 6). The fixer confirms step 9's records exist and match the final numbers, and tells the orchestrator the owner items: the OQ1 ruling with the spec.md:114 line (2.4), the AC 4 reading, and the fired/accepted bars.

## 5. Acceptance criteria → tests (real path)

Every AC frame is `generate(..., forks=[...])` (and `phase_breaks=` for AC 3) run through `analyse` at the default calibration; binned frames as the block-summed frame with its bin factors. The CLI test goes through `denoisifier` on a written CSV.

Seeds: `FORK_TEST_SEEDS = range(10, 20)` (test seeds may share; never run with forks before this plan; P1/P2 ran 09's seeds 10-19 only for break-only identity). Case `CASES[seed % 10]`: P 3, 5, 8, 12, 20, 4, 16, 6, 10, 14. `inner(...)` takes the first `INNER_LOOP_SEED_COUNT`; the rest are `wide` by the existing mechanism. No hand-added `wide`. A red seed is a finding for the orchestrator: never a re-pick, a pass count or an exclusion in advance (09's seed policy).

### 5.1 Fork match metric (`truth_match.assert_forks_match`)

A true fork is matched when exactly one reported fork lies within `FORK_POSITION_TOL_PERIODS · P` of it (Euclidean, sensor geometry; frame pixel `r` has its sensor centre at `v·r + (v - 1)/2`, as 09's 5.1) and has the true direction. **No extras**: every reported fork in the frame is matched to a true fork (one to one). Direction is compared as given, never "either sign".

### 5.2 Table

| AC | File :: test | Asserts |
|---|---|---|
| 1 (sign) | `test_synthetic.py::test_a_fork_adds_one_stripe_on_its_split_side[direction, angle]` | **Continuous measure (review B1; a maxima count depends on `phase0`).** Noise-free, `mottle="none"`, full frame `FORK_SIGN_FRAME_SHAPE` (400, 1600), P `FORK_SIGN_TEST_PERIOD` (10), Angle in {0, 10, -10}, fork at the centre (half-integer). `s = clean / env - 1` (env: the `modulation_depth=0` twin). For the rows `FORK_SIGN_ROW_OFFSET_PERIODS · P` (5 P) above and below the fork: analytic phase by `scipy.signal.hilbert` along the row, `np.unwrap`, change from column `2 P` to column `W - 1 - 2 P` (trims the transform's end effects). `(change_top - change_bottom) / 2π` (about 0.96·d; the plane-wave part cancels) **rounds to `direction`**. Docstring: "with +1, going toward row 0 one stripe becomes two (the row-0 side crosses one more stripe)", the frame shape, and why a count is not used. |
| 1 (phase) | `test_synthetic.py::test_fork_phase_is_the_winding_term` | Noise-free: `clean / env - 1` equals the fork-free stripe term turned by `d·atan2(y - y0, x - x0)` within `FORK_PHASE_ATOL`, by 09's `c_0 cos + c_{π/2} sin` construction (`test_phase_break_shifts_every_stripe_on_one_side`); inside `regions` and full frame. |
| 1 (truth) | `test_synthetic.py::test_fork_truth_is_returned` | `GroundTruth.forks` lists each `ForkTruth(point, direction)` in order; invalid point, `direction` 0, 2, 1.0 or `True` raise. |
| 1 (identity) | `test_synthetic.py::test_no_forks_leaves_frames_unchanged` | `forks=()` keeps every `_BASE_DIGESTS` entry; with a fork and Gaussian noise, `frame - clean` equals the fork-free call's within float rounding. |
| 2 | `test_analyse.py::test_forks_are_found_with_their_direction[seed]` | 09-size `regions` geometry (`single_region`, centre (255.5, 255.5)), typical EMCCD, scorched, depth 0.5; one fork at the centre plus a seed-dependent **integer** offset of up to 1 P per axis (so the point stays half-integer; review N2), direction `(+1, -1)[seed % 2]`. 5.1. Also `phase_breaks == ()`. (Validated: single 133/133.) |
| 2 (full frame) | `test_analyse.py::test_fork_in_full_frame_stripes_is_found[seed]` | `FORK_TEST_SEEDS[:4]` (P 3, 5, 8, 12), 400x1600, fork at the centre, alternating directions. 5.1; `phase_breaks == ()`. |
| 2 (sign end to end) | `test_analyse.py::test_reported_fork_direction_matches_the_generator[direction]` | `FORK_SIGN_TEST_SEED`, `regions` geometry, P 10, Angle 0, Gaussian noise, spikes 0: the reported direction equals the generator's for +1 and -1. |
| 3 | `test_analyse.py::test_fork_near_a_phase_break_is_found_and_kept_apart[seed]` | **Large region** (`big_region`: round, semi-axes max(11 P, 60 px), 512x512; the fork ≥ 4.5 P from the 0.5 contour). One break through the centre (line at case Angle + {0, 5, -5}[seed % 3], jump cycling {π/2, π, -3π/4}), one fork `FORK_NEAR_BREAK_PERIODS` (4) · P from the line, ± up to 0.5 P along it, side and direction alternating by seed. 5.3. Docstring: AC 3 is shown in regions this large. (Validated: `nearbig` 4 P 39/40.) |
| 3 (negative) | `test_analyse.py::test_phase_break_frames_have_no_fork[...]` | The frame kinds of the 09 suite (review P3): AC 2 and AC 3 break frames, full-frame break frames, `break_pair`, `two_break_case`, `compatible_pair_frame`, the two-region crossed (bridged) frame, the binned break frames (`breaks.py`'s shared cache, the 09 seeds and `inner`): `forks == ()`, **and** the report minus `forks` and `labels` equal the report with `find_forks` monkeypatched to `[]` (gate silent, identity of section 0). |
| 4 | `test_analyse.py::test_frame_with_forks_is_striped[...]` | Every AC 2, AC 2 full and AC 3 frame (shared cache): `report.striped`; and **closed-domain reading** (orchestrator, from `10-critic-pq5.md` "AC 4"; replaces the draft's "fork pixel in a reported region", which BASE fails 0/200 by carving a notch): for each matched fork, `fork_domain(labels == fork.region, other labels' pixels, that region's Period, bins)` holds the true point's nearest frame pixel. (Validated 133/133 single, 27/27 full, 130/130 nearbig.) |
| 4 (measurements) | not written | BASE moves the Angle over 1° on fork frames (29/200 explore, 17/133 validation); the numbers go to ticket 17 (step 9). |
| 5 | `test_analyse.py::test_report_lists_forks` | On the AC 2 frame of `FORK_TEST_SEEDS[0]`: `to_dict()["forks"]` is a list of `{"region", "point", "direction"}`; `point` a [row, col] pair; `direction` an `int` in {1, -1} (not `bool`); `region` a reported label; `json.loads(to_json())` round-trips; key order pinned in `test_report_converts_to_json`. A fork-free frame gives `[]`. |
| 5 (CLI) | `test_cli.py::test_cli_reports_forks` | A CSV with one fork: one entry. With `--transpose` on a transposed file: point swapped, direction equal. stderr empty. |

### 5.3 AC 3 reading (ruled; recorded in Comments)

"A fork near a phase break is still found and kept separate from the break" means, on one frame: the fork is matched by 5.1; the break is matched by 09's `assert_break_matches` (09 is done, so the parenthetical's "only the fork is checked" no longer applies); exactly one reported fork and exactly one reported break, both in the same region. **"Near" = `FORK_NEAR_BREAK_PERIODS` = 4 P**, in a region large enough that the fork is about 4 P from its edge (orchestrator ruling, `10-critic-p2.md` section 2). 3 P is not claimed (explore 50/60 under 09's 90 % bar). Closer than 4 P is stated as undefined in the docstring and Comments, with the rates of 2.2.

### 5.4 Supporting tests

- `test_frames_without_forks_report_none[frame]` (**zero fakes and identity, real path**): the `REGION_TEST_SEEDS` single-region frames, the `TWO_REGION_TEST_SEEDS` frames, one 2x1 frame at `BINNING_TEST_SEEDS[2]`, one Stripe-free frame and `SPIKE_TEST_SEEDS[:2]` spiked frames (spec.md:141): `forks == ()`, and `to_dict()` minus `"forks"` and `labels` equal the report with `find_forks` monkeypatched to `[]`.
- `test_two_forks_are_both_found[seed]`: `big_region`, forks `FORK_PAIR_SEPARATION_PERIODS` (4) · P apart, tilt ± up to 20°, opposite directions on even seeds and equal on odd, every `FORK_TEST_SEEDS` case via `inner` (no Period floor: `pairbig` 4 P held across P 3-20; `FORK_PAIR_MIN_PERIOD` dropped). 5.1 for both. Large region because the 09-size `pair` cell missed its bar (B4, owner-accepted).
- `test_fork_outside_the_regions_is_not_reported`: a fork outside the region's 0.5 contour by more than `_FORK_LOOP_PERIODS · P`: `forks == ()`. And at `threshold=inf`: no regions, `forks == ()`.
- `test_forks_are_not_searched_under_the_frame_period_limit`: 09's refusal frame plus a fork: `forks == ()`, the reworded refusal sentence.
- `test_binned_fork_is_found[bins, seed]`: 2x1 and 1x2, `BINNING_TEST_SEEDS[2:]` (P 8, 12), full frame. 5.1 in sensor geometry.
- The wiring tests (step 5) and the `find_forks` / `fork_domain` unit tests (step 4).

## 6. Do scores move? Gates

**No, by construction.** Both fork searches run after the score and the threshold, on the reported regions; the corrected field reaches only the break pass, which 09 already placed after the threshold. Default generator frames (`forks=()`) are bit-identical, so every slow-tier, calibration and feasibility frame is unchanged. So: no `make measure`, no stored-threshold update, no calibration re-store, no `make check-held-out`; ticket 10 is not a measure milestone. Closing sequence (fixer, step 10): `make bench`, `make check-slow`, `make check` (each background, idle machine, one at a time). The handoff quotes the step-6 diff, the step-5b timing and each gate's line.

## 7. Approvals, seeds and protected numbers

Approval-needing moves (CLAUDE.md "Weakening moves"), to be approved by the orchestrator **before** the change, each recorded with its reason in the ticket Comments:

- **A1. Lockfile additions** (`tests/protected_numbers.lock`) for the six `_FORK_*` constants of 2.2 in `_local_phase.py`, and any module-level number added to `analysis.py`. New pins; nothing loosened.
- **A2. Lockfile additions** for the protected numbers below, and the `USED_SEEDS` list extended by `FORK_PROTOTYPE_SEEDS` and `FORK_VALIDATION_SEEDS` (as 08 and 09 did). `test_seed_sets_are_disjoint_and_unused` stays green.
- **A3. Expected-value extensions** (no check removed): `test_report_converts_to_json`'s key list gains `forks`; `REPORT_UNITS` gains `point` and `direction`.
- **A4. Expected-value change**: the refusal sentence in `test_analyse.py:1932` and `:1959` becomes "phase breaks and forks were not searched ...". Reason: the same limit now refuses both searches; one sentence per region keeps 09's one-entry-per-region rule. Alternative (rejected): a second sentence per region.
- **Not an approval, but stamped:** `tests/protected.py` and three stamped source files change, so `make check-slow` is due before `make check` (step 10). No change to `STAMPED_FILES` or `NOT_STAMPED_SRC` (`tests/forks.py` is not imported by the slow tier).
- **Not touched**: existing tolerances (`PERIOD_REL_TOL`, `ANGLE_TOL_DEG`, `MASK_IOU_MIN`, every `BREAK_*`), skip/xfail, suppressions, hand-added `wide`, `INNER_LOOP_SEED_COUNT`, timeouts, gate config, the seed guard and `CALIBRATION_SEEDS`, the stored calibration, the pass counts, every `_BREAK_*` constant and the break finder's code. Any of these becoming necessary (e.g. a red AC seed) is a finding for the orchestrator first.

**Seeds.** Reserve exactly what was looked at (P1, P2, the critics' re-runs used stored data only):
- `FORK_PROTOTYPE_SEEDS = range(111_000, 111_200)`: P1 and P2 explore (every set uses `base + k` with k < 200; noise-free checks, quick scripts and timing fall inside).
- `FORK_VALIDATION_SEEDS = range(111_600, 111_733)`: the one validation run (2/3 scale).
- **111_200-111_599 and 111_733-111_999 stay unused**: never generated. They are **not** reserved, and are named in the follow-up ticket (step 9) as free for its fresh explore/validation. The comment on the `USED_SEEDS` lines says so.
- 09's test seeds 10-19 (identity runs) are already in `TEST_SEED_BLOCK`; `feasibility.TIMING_SEED` is already used.

| Number | Value | Notes |
|---|---|---|
| `FORK_TEST_SEEDS` | `range(10, 20)` | in `TEST_SEED_BLOCK`; shares with `PHASE_BREAK_TEST_SEEDS` (allowed) |
| `FORK_POSITION_TOL_PERIODS` | `1.0` | spec.md:162 |
| `FORK_EXACT_POSITION_TOL_PERIODS` | `0.25` | noise-free unit tests; P1 noise-free max 0.172 P (96/96) |
| `FORK_NEAR_BREAK_PERIODS` | `4.0` | AC 3 (5.3) |
| `FORK_PAIR_SEPARATION_PERIODS` | `4.0` | 5.4, step 4 |
| `FORK_BIG_REGION_SEMI_PERIODS` | `11.0` | `big_region` (AC 3, pairs) |
| `FORK_BIG_REGION_SEMI_FLOOR_PX` | `60.0` | `big_region` |
| `FORK_CORRECTION_MIN_RESULTANT` | `0.99` | step 5 correction test (measured 1.000; wrong sign ≤ 0.14) |
| `FORK_SIGN_TEST_SEED` | `FORK_TEST_SEEDS[0]` | 5.2 sign end to end |
| `FORK_SIGN_TEST_PERIOD` | `10` | 5.2 sign tests |
| `FORK_SIGN_ROW_OFFSET_PERIODS` | `5` | generator sign test |
| `FORK_SIGN_FRAME_SHAPE` | `(400, 1600)` | generator sign test (wide rows, B1) |
| `FORK_PHASE_ATOL` | `1e-9` | generator phase test |
| `FORK_PROTOTYPE_SEEDS` | `range(111_000, 111_200)` | in `USED_SEEDS` |
| `FORK_VALIDATION_SEEDS` | `range(111_600, 111_733)` | in `USED_SEEDS` |

`FORK_PAIR_MIN_PERIOD` (draft) is dropped: not needed (`pairbig` 4 P held at every `CASES` Period).

## 8. Risks

- **Fake breaks on fork frames outside the served geometry** (close opposite pairs in 09-size regions, forks within about 4 P of an edge, BASE-split regions): BASE behaviour the gate cannot reach; stated limits, the new ticket 18, notes for 11 and 12.
- **The ordering's own cost on fork frames**: on explore one fake break added (weak 111059) and one matched line pushed out of tolerance (111050); none on validation. Stated in Comments.
- **Fake forks** where the response is dim; the magnitude floor, the break explain-away and E ≥ 0.3 guard them (0 on every fork-free and break-only set); ticket 11 calibrates. A fake region gets fake forks too.
- **Speed**: the pre-break search runs on every reported region, and a gated fork costs a second break pass. Measured in step 5b; `make bench` at close; over budget → orchestrator.
- **Red AC seeds**: AC 2, 3 and pairs were validated at 2/3 scale (B4 `pair` missed its bar). A red seed is a finding, never a re-pick.
- **Weak stripes** (depth 0.2): no claim (striped 48/67 on validation).

## 9. Where each input went

| Input | Disposition |
|---|---|
| Review B1 (AC 1 sign test depends on `phase0`) | Folded: 5.2 AC 1 (sign) uses the rounded unwrapped analytic-phase difference on a 400x1600 frame. |
| Review P1 (near-break distances) | Answered by P1/P2: the spread rule lost the break at every distance; fork-first ordering fixed it at 4 P in a large region (3, 5.3). |
| Review P2 (BASE on AC 3 frames, fork pixel in region) | Answered: fork pixel never in a region; AC 4 reading replaced (5.2 AC 4); AC 3 on the large region. |
| Review P3 (negative set = the 09 suite) | Folded: 5.2 AC 3 (negative) runs every 09 frame kind, with the identity check. |
| Review O1 / plan OQ1 (direction, transpose) | Ruled option A by the orchestrator; wording from `10-critic-oq1.md` in 2.1, 2.4, step 8; owner told at close (step 10). |
| Review N1 (stale bench) | Folded: section 1; step 5b times BASE and new code in one run. |
| Review N2 (half-integer point in AC 2) | Folded: integer offsets (5.2 AC 2). |
| Review N3 (refusal vs search) | Folded: 2.3 steps 2 and 4 use the warning's decision; step 5 test. Residual (a region re-measured under 2.5 px after the pass gets no forks and no warning) is stated in the docstring: **note**, rare, not measured on any validated set. |
| Review N4 (`_samples` refactor) | Folded: no refactor (2.2); step 0 diff gains `two_break_case` and a bridged frame. |
| Review N5 (CLI docs) | Folded: 2.5, step 8. |
| Review N6 (denominators) | Folded: section 3; Comments (step 9). |
| Review N7 (verified claims) | Nothing to change; `analysis.py:282` docstring included in step 8. |
| PQ1-PQ7 | Answered by P1/P2: frozen config 2.2; PQ3 = 4 P; PQ4 → AC 4 reading and ticket 17; PQ5 → fork-first ordering; PQ6 → edge limit about 4 P; PQ7 binned 40/40 explore, 27/27 validation. |
| PQ8 (timing, not idle) | Step 5b (implementer, idle, single process, bench frame); `make bench` at close; escalation line. |
| P2 fired bar, option D | Section 3; step 9 records it as fired and re-ruled, conditions 1-5 (bars declared at freeze: done; limits as measured: 2.2; follow-up and notes: step 9; owner told: step 10). |
| Owner 2026-11-15 | B3/B4 accepted (section 3, step 9 "bar failed, owner accepted"); real frames "rare / regions large": limits kept, ticket 18 low priority. |
| Critics' plan edits | Section-0 identity wording (0); AC 3 on the large region (5.2, 5.3); AC 4 closed-domain reading (5.2); limits as measured (2.2). |
| Draft notes N1-N6 | N1 frame px: kept (2.4). N2 AC 3 reading: ruled (5.3). N3 global term: kept (2.1). N4 depth 0.5 typical: kept (5.2, 8). N5 only reported regions: kept, but "forks never change regions" is replaced by the identity claim of section 0. N6 GLOSSARY: step 8. |

**Open:** none blocking. One **note**: the N3 residual above.
