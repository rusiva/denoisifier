# Slow-tier regression plan: derivation

The pass counts of the slow tier's regression check (`tests/test_slow_regression.py`, ticket agent-gates/05) and the operating rule that `tests/test_slow_regression_plan.py` re-checks in `make check`. Moved here from the ticket's plan (`.scratch/agent-gates/handoffs/05-plan.md`, "Exact-binomial derivation"), which is not tracked; the protected numbers are in `tests/protected.py`. Labels in parentheses (F1, O1, O2, W4, W5) name that plan's findings, rulings and weakening moves.

The derivation below was made at the ticket agent-gates/05 baseline. The false-alarm term's p0 has since changed (see "The false-alarm baseline"); `test_regression_plan_meets_the_operating_rule` recomputes every term from the current `feasibility-gate.json`.

**Model.** Each frame is scored once at a fixed stored threshold, with no per-run calibration. Detected means `score > threshold`. Counts are Binomial(n, p).
- The stripe-free set is i.i.d.
- The striped sets are stratified (n/10 per case), so their counts are Poisson-binomial. That has no more variance than a binomial with the same mean. The review verified that Hoeffding's bound applies to both tails used, so the binomial bounds below are conservative.
- The three sets use disjoint seeds, so they are independent.

**Operating rule** (ticket agent-gates/05, with the joint budget):
- (i) **P(any of the three regression assertions is red) ≤ 1%** when every true rate sits at the pessimistic end of the stored baseline's exact 95% CI (for false alarms, since ticket stripe-detector/05: the rank-based bound below).
- (ii) Each check passes a bad detector with probability ≤ 5%:
  - 256×256 detection at 0.90;
  - 256×256 false alarms at 0.04;
  - 400×1600 detection at the declared 0.70 (O1).

**Selection rule** (fixed before any run). The sizes are fixed at n = 300 / 800 / 30 (800 became 850 in "Pass probability of the rule"). Over all (c, a, c_p) that meet (i) and (ii), take the triple that **minimises the largest pass-bad probability**. Under the independent model the union is computed exactly as 1 - Π(1 - p_i). It is also checked against the Bonferroni sum, so (i) holds even without independence.

## The three checks at fixed sizes

The three checks, at the pessimistic ends from F1:
- **256×256 detection** (n = 300, p0 = 0.96353): P_fr(c) = BinomCDF(c-1; 300, p0) and P_pb(c) = BinomSF(c-1; 300, 0.90).
- **256×256 false alarms** (n = 800, p0 = 0.014369): P_fr(a) = BinomSF(a; 800, p0) and P_pb(a) = BinomCDF(a; 800, 0.04).
- **400×1600 detection** (n = 30, p0 = 0.96378): P_fr(c_p) = BinomCDF(c_p-1; 30, p0) and P_pb(c_p) = BinomSF(c_p-1; 30, 0.70).

These are the per-check values that meet (ii):

| check | count | P_fr | P_pb |
|---|---|---|---|
| detection | c = 279 | 0.172% | 4.58% |
| detection | c = 280 | 0.371% | 2.87% |
| detection | c = 281 | 0.766% | 1.71% |
| false alarms | a = 20 | 0.706% | 1.44% |
| false alarms | a = 21 | 0.350% | 2.38% |
| false alarms | a = 22 | 0.167% | 3.77% |
| probe | c_p = 26 | 0.416% | 3.02% (at 0.90: 82.5%) |
| probe | c_p = 25 | 0.063% | **7.66%**: fails (ii) |

So c_p = 26 is forced. Exhaustive search (a one-off script, not kept) finds exactly three triples that meet (i) and (ii):

| (c, a, c_p) | P_fr: det / FA / probe | union (exact) | Bonferroni sum | largest P_pb |
|---|---|---|---|---|
| **(280, 22, 26)** | 0.371% / 0.167% / 0.416% | **0.951%** | 0.954% | **3.77%** |
| (279, 21, 26) (Codex) | 0.172% / 0.350% / 0.416% | 0.936% | 0.938% | 4.58% |
| (279, 22, 26) | 0.172% / 0.167% / 0.416% | 0.753% | 0.755% | 4.58% |

The per-check minimax (280, 21, 26) has a union of 1.133% and is ruled out. The ticket's start (281, 20, …) is ruled out too: 0.766% + 0.706% alone exceeds 1%.

**Chosen:** detected **≥ 280 of 300**, false alarms **≤ 22 of 800**, full-frame detected **≥ 26 of 30**. Union false red 0.951%. Pass-bad 2.87%, 3.77% and 3.02%.
- At the point estimates (0.98, 0.007, ≈ 0.99), the per-check false reds are 1.0e-6, 2.5e-8 and 1.2e-5.
- A full-frame detector at the full measurement's own bar of 0.95 passes ≥ 26/30 with probability 98.4%. One at 0.90 passes 82.5%. That is the O1 dissent, recorded and not hidden.
- The 30 s timing assertion is a deterministic limit, not a statistical one, so it is outside the budget. It is load-tolerant, not immune to load (W4).

## The false-alarm baseline (owner approval, ticket stripe-detector/05)

2026-11-12, recorded in `.scratch/stripe-detector/issues/05-striped-regions-and-mask.md` Comments. The false-alarm term's p0 is no longer the held-out count's exact CI end. The stored threshold is the k-th largest of n calibration scores, so its true rate is Beta(k, n + 1 - k), and the held-out count x of N updates it to Beta(k + x, n + 1 - k + N - x). The rule test takes p0 = that distribution's 97.5% quantile (`REGRESSION_FREE_RATE_BOUND_QUANTILE`), reading k, n, x, N from `feasibility-gate.json`; at `317744b`, Beta(32, 2969) gives 1.4636% and a false-red term of 0.209%. The guarantee is averaged over calibration draws, not conditional on one fixed threshold, and assumes i.i.d. continuous Stripe-free scores with no tie at rank k (`test_stored_threshold_rank_is_untied` guards the ranks above k; `test_free_rate_bound_covers_the_true_rate_for_continuous_scores` checks the coverage on uniform scores). Reason: the stored threshold is a calibration rank, so the held-out count is betabinom(N, k, n + 1 - k) for any detector, and under the old term the rule passed only about 38% of measures for any detector (`.scratch/stripe-detector/handoffs/.archived/05-implementer-7.md`). Pass counts, sizes, budgets and bad rates unchanged.

## Pass probability of the rule (owner approval, ticket agent-gates/05)

2026-11-13, recorded in `.scratch/agent-gates/issues/05-required-slow-tier.md` Comments. A fresh `make measure` of an unchanged detector draws a new held-out count x, which is betabinom(N, k, n + 1 - k) for any detector, so whether the rule above passes is itself random. `test_an_unchanged_detector_passes_the_rule_on_most_measures` sums that pmf exactly over every x at which the rule passes (detection terms held at the stored baseline) and asserts at least `REGRESSION_MIN_PASS_PROBABILITY` = 0.95.

At 800 Stripe-free frames and a ≤ 22 limit, the rule passed up to x = 15 only: **91.5%**, a false red on about 1 measure in 12. The limit could not rise at 800 frames: a ≤ 23 limit passes a bad detector (4%) 5.7% of the time, over (ii). The fix is a larger set (`k = 20, n = 2000, N = 1000`, the stored measurement's):

| Stripe-free frames | largest limit meeting (ii) | P(pass), unchanged detector |
|---|---|---|
| 800 | 22 | 91.5% |
| **850** | **24** | **96.3%** |
| 900 | 26 | 98.5% |
| 1000 | 29 | 99.1% |

**Chosen:** 850 frames (`range(81_000, 81_850)`, still 85 per case), false alarms **≤ 24 of 850**. The cost is 50 more 256×256 frames in `make check-slow`, a few seconds.

## Timing frames (O2)

The first `REGRESSION_TIMED_FRAMES = 3` seeds of the 30 full-frame seeds are analysed serially in-process and timed. Their scores count once toward the ≥ 26/30. The other 27 go through the pool.

## Determinism

Seeds are fixed, so a run is deterministic. The 1% applies to the draw of the seeds, and to each detector change that keeps the true rates. A red first run on the unchanged detector is a **finding**: stop for the owner. Do not re-seed and do not touch the pass counts.

## Wall clock (estimate)

- Pool: 1100 small frames (1150 since the 850-frame ruling) + 27 × 12.6 ≈ 1440 small-frame units × 0.17-0.21 s ≈ 4-5 min.
- Serial timing: about 25 s. Three pool spawns: a few seconds.
- **Estimate: about 5-6 min.** Measured and recorded in Comments.

## The rule as a test

`test_regression_plan_meets_the_operating_rule` is non-slow and runs in `make check`. From the saved JSON's counts and the protected constants, it recomputes:
- the exact CI ends;
- the union (exact, 1 - Π(1 - p_i)) and the Bonferroni sum, each ≤ `REGRESSION_MAX_FALSE_RED`;
- each P_pb ≤ `REGRESSION_MAX_PASS_BAD` at its declared bad rate.

So when `make measure` stores a worse baseline, `make check` goes red. Re-deriving the counts is then an owner-approved W5, never a silent edit.
