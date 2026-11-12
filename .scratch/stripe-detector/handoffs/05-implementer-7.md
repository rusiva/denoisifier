# 05 implementer handoff 7: STOPPED before any change (ruling B cannot work by construction)

Ticket: `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md`. Plan `05-plan.md`. BASE 87005b9.
Previous: `05-implementer-6.md`. Brief: owner ruling B (fix the detector so held-out False Alarms fall, then
`make measure`; pass counts, sample sizes and rule constants unchanged).

## Stop

I stopped on the brief's third condition ("can't bring False Alarms down enough for the operating rule
without hurting detection"). No detector change can lower the expected held-out False Alarm count. I
changed no code and ran no gate.

### Why a detector fix cannot work

1. **The Threshold is a 1% quantile of the detector's own Stripe-free scores.** `make measure` sets the gate
   Threshold to the k = 20th largest of 2000 calibration Stripe-free scores (`feasibility-gate.md`, "Threshold
   rule"). Held-out Stripe-free frames come from the same generator, so they are exchangeable with the
   calibration frames. A held-out frame then exceeds the Threshold with probability k/(n+1) = 20/2001, about
   1.0%, **whatever the detector is**. Any detector change moves the Threshold with the scores; the expected
   held-out count stays at 10.0/1000. The count follows `betabinom(1000, 20, 1982)` (the 3-18 band the gate
   already asserts).
2. **The operating rule needs at most 8/1000 held-out False Alarms.** `test_regression_plan_meets_the_operating_rule`
   uses the upper end of the exact CI on the held-out count. With the unchanged constants
   (`REGRESSION_MAX_FALSE_ALARMS = 22` of 800, and the probe part at 0.0042):

   | Held-out FA | CI high | P(false red), FA part |
   |---|---|---|
   | 7 | 1.44% | 0.0017 |
   | 8 | 1.57% | 0.0048 (the union is about 0.009: passes) |
   | 9 | 1.70% | 0.0118 (red) |
   | 12 | 2.09% | 0.0804 (red, now) |

3. **So `make measure` passes the rule only about 38% of the time for any detector**:
   `betabinom(1000, 20, 1982).cdf(8) = 0.377`. Ticket 03's 7/1000 was a lucky draw (P(<= 7) = 0.27), not a
   better detector. A "fix" followed by a re-measure is a re-roll of the held-out draw. Re-rolling until the
   rule is green tunes on held-out results, which the seed hygiene forbids.

### The premise in the brief

"Stripe-free score max on calibration went from about 2 to 48" misreads `region-calibration.json`. In
`summary.free`, the **median** went from 2.12 (`ce42580`, first freeze) to 15.4 (`2107a40`) and then 14.3
(`c99a069`). The **max** was already 47.9 at the first freeze, and 48.1 since. The median shift is real (the R1
size-rule climb and widest run, `2107a40`, report more small regions). It sits far below the 1% tail, though,
and the tail is what sets the Threshold. The gate Threshold went *down* (74.1 to 49.7): the Stripe-free tail is
lower than at ticket 03, and every striped case scored at least 1.34x the Threshold.

### Real false-red risk of the regression check

The real risk is small. At the design rate (1.0%), `binom.sf(22, 800, 0.01) = 1e-5`. At the 97.5% quantile of
the Threshold's true rate, Beta(20, 1982) gives 1.48%, and `binom.sf(22, 800, 0.0148) = 0.0024`. The rule test
is red only because it plugs in the held-out count's own CI end. That CI is wide at n = 1000 and centred on a
random draw.

## Options for the owner (none taken; each needs the owner's approval)

- **(a)** Derive `fa0` in the rule test from the Threshold's Beta(k, n+1-k) upper quantile (1.48%) instead of
  the held-out CI. That is the quantity the regression check actually guards, and the rule passes with today's
  constants. It edits the rule test, a weakening-class change.
- **(b)** Re-derive the pass counts or sample sizes. The orchestrator found that 1600 free seeds with limit 49
  meet both rules at 12/1000.
- **(c)** Enlarge the held-out Stripe-free set in `make measure`, so the CI narrows towards 1%. This takes new
  seeds and a longer measure. At n = 1000, even the expected count of 10 is red.

## Commits

- This handoff and a ticket Comment only. No source or test change.

## Gate quotes

- No gate was run: the tree's source and tests are unchanged since `1fd3635`. The last quotes are in
  `05-implementer-6.md` (`make test-fast` at `317744b`: exit 0, `728 passed, 4 deselected in 350.31s`).
  `test_regression_plan_meets_the_operating_rule` is still red at `1fd3635`.
- `git rev-parse --short HEAD` before this commit: `1fd3635`. Tree dirty only in others' `.scratch` notes.

## In flight

Nothing. No background jobs are running.

## Next step

1. The owner picks (a), (b) or (c), or another option.
2. Then `make check-slow` in the background, then `make check`, then the final handoff.

## Pointers

- `tests/test_slow_regression_plan.py`: the rule test.
- `tests/protected.py` lines 54-81: the constants.
- `.scratch/stripe-detector/feasibility-gate.{json,md}`: the threshold rule and the counts.
- `.scratch/stripe-detector/region-calibration.json`: `summary.free`.
