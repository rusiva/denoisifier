# Ticket 09, critic 5: the `two_break` negative on seed 12

Reviewed at `b23ce21` (tree dirty only in `.scratch/`). Question: approve replacing the absolute assertion of `test_two_regions_crossed_by_one_break_stay_apart` with a pass-relative one?

## Verdict

**(b): fix the helper. Do not approve (a).** Keep the test's assertion as it is.

## What I checked

`uv run --locked pytest 'tests/test_analyse.py::test_two_regions_crossed_by_one_break_stay_apart[12]' -rf` → `1 failed in 6.69s`: region 1 covers 0.96 and 0.99 of the two truth cores.

All ten seeds, built against pass-free (`_with_phase_breaks` replaced as in `_pass_free`). Each entry is (label, Period, Angle, [share of left core, share of right core]):

| Seed | True Angles | Pass-free | Built | Breaks found |
|---|---|---|---|---|
| 10 | 10, **13** | 2 regions, apart | 2, apart | 2 |
| 11 | 0, 3 | 2, apart | 2, apart | 2 |
| 12 | 6, **16** | **1 region, [0.84, 0.98], Angle 8.27** | 1, [0.96, 0.99] | 4 |
| 13 | -8, 2 | 2, apart | 2, apart | 2 |
| 14 | -10, -7 | **3** (left core split 0.40 / 0.39) | 2, apart | 2 |
| 15 | -4, -1 | 2, apart | identical | 0 |
| 16 | 10, **20** | 2, apart | 2, apart | 2 |
| 17 | -10, 0 | 2, apart | 2, apart | 2 |
| 18 | 3, 6 | 2, apart | 2, apart | 2 |
| 19 | -6, -3 | 2, apart | 2, apart | 5 |

- The implementer's claim holds: on seed 12 BASE already reports one region over both cores, so the pass is not the cause.
- The cause is the frame. `two_break_layout` sets the second Angle to `A + offset` with no bound, so seeds 10, 12 and 16 have a region at 13°, 16° and 20°. The detector searches ±10° (`_STRIPE_ANGLES_DEG`, spec lines 110 and 156: beyond about ±10° is out of scope).
- The helper copies the prototype exactly (`harness2.py` at `3768dd2`, line 78). The prototype had the same frame: validation seed 110342 is the same layout (k = 2, `CASES[2]`, 16°) and is the "BASE 1" entry in `09-prototype-p1.md`. The prototype counted merges against BASE; the plan's test (5.4) asserts an absolute result and did not carry that over. So this is a plan and helper defect, not a detector defect.

## Why not (a)

- **The count form is wrong.** "The pass must not reduce the region count" fails on seed 14, where the pass correctly joins BASE's two fragments of the left region (3 regions to 2).
- **The core form makes seed 12 vacuous.** "No built region covers both cores unless a pass-free region already does" passes on seed 12 whatever the pass does there. That is 1 of 10 seeds proving nothing, and a later BASE regression that merges more frames would turn more seeds vacuous without a red test.
- It changes the check to fit a red result, which is the move "Fix the code, never the check" forbids, when the defect is in the test's input.

## The rule for the implementer

In `two_break_layout` only, keep both Angles inside the searched range by mirroring the offset:

```python
second = a + offset if abs(a + offset) <= 10.0 else a - offset
return p, g, (a, second), ...
```

- Leave the assertion, `BREAK_SIDE_COVER_MIN`, the seeds and the rest of the layout unchanged. Update the helper's docstring to say both Angles lie within ±10°.
- Take the bound from a named constant, not a new literal in the helper, if one fits (a new number in `tests/protected.py` is a lockfile edit and needs its own approval).
- This is a single change. If a mirrored seed is red, that is a finding to report, not a reason to adjust the layout again.
- Record in the ticket Comments: the reason (the frame was outside the spec's search range), the three seeds changed, and the per-seed table of regions and breaks found, which the plan already asks for.
- Note for ticket 17, not for this ticket: BASE merges an in-range region with a 16° neighbour at a 2 P gap (seed 12, P 12).

## Effect on the other seeds

- Seeds 11, 13, 14, 15, 17, 18, 19: frames and assertion unchanged, so nothing is weakened.
- Seeds 10, 12, 16 get new frames at (10, 7), (6, -4) and (10, 0). I ran them once with the rule above fixed beforehand:

| Seed | Angles | Pass-free | Built | Breaks found |
|---|---|---|---|---|
| 12 | 6, -4 | 2, apart | 2, apart ([0, 0.97], [0.96, 0]) | 2 |
| 10 | 10, 7 | 2, apart | 2, apart | 2 |
| 16 | 10, 0 | 2 ([0.25, 0.77], [0.71, 0]) | 2 ([0.27, 0.96], [0.71, 0]) | 1 |

- All three pass the unchanged assertion. Seed 12 becomes a live negative (BASE keeps the regions apart and breaks are found), which it was not before.
- Seed 16 is the closest: one region holds 0.27 of the other core, against the 0.5 limit, and BASE already has 0.25 of that.
- One loss: seeds 10 and 16 no longer exercise an out-of-range neighbour (13°, 20°). That is outside the spec, and the test's docstring never claimed it.
- Seed 15 finds no break, so it is not a live negative in either version. That is unchanged and belongs in the handoff's per-seed list.

## Approval

The helper change alters a test's input on a red test, so record it in the ticket Comments with the reason above. It is not one of the listed weakening moves: no tolerance, expected value, selection or protected number changes. Changing the assertion (a) would be one, and I recommend refusing it.
