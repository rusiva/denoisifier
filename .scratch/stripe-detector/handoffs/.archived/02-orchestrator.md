# 02 orchestrator log (CLOSED)

- Ticket: .scratch/stripe-detector/issues/02-stripes-vs-mottle-in-emccd-noise.md
- BASE: 1d07977de81d31ab505682dd961bb25f1cb800e6
- Args: MIN_MODEL=opus, WORKER_LIMIT=150000, SELF_LIMIT=150000
- Plan path: .scratch/stripe-detector/handoffs/02-plan.md (written)
- Plan-review path: .scratch/stripe-detector/handoffs/02-plan-review.md (written)

## Workers
- planner ac52bf7add7650bab (opus, watcher armed): write 02-plan.md from ticket/spec/ADR/01 artifacts; report open questions. Status: done. Plan written (pending→written). Prototype in session scratchpad proto/ (v.py reference): Gabor vertical-vs-horizontal energy, threshold 150; stripe-free max 75.7, m=0.5 min 301; m=0.2 scored 101-196 (risk for 03); 1600x400 in 7.0 s.
  Planner open questions: O1 modulation_depth top-level Report field now (rec: now); O2 noise API `noise: float | Emccd` union (rec: union); O3 bright/dim depth AC via two crops of one frame (rec: crops, prototyped, agree within 0.03); O4 accept A0=3e-3 floor, stripes <~0.04 never flagged (rec: accept; A0=1e-3 false-flagged).
- plan reviewer aea59660892e9094c (opus, blind, watcher armed): review into 02-plan-review.md. Status: done (2 breaks, O1-O4 owner, 6 notes). Closing check: all closed, no new items. Scripts in session scratchpad review/.


- implementer aba1e5267e800dcde (opus, watcher armed): build plan rev 2 test-first with tdd skill, commit to main, full suite at end. Status: done. Commits 631c3af (generator: mottle, Emccd, Synthetic.clean) and d3b1150 (Gabor bank _local_stripes, analyse, Report.modulation_depth, tests). Full suite green: 187 tests, -W error, mypy clean. Notes: tests passed before code change (old FFT separated batches; depth tests forced new method); threshold kept 150 (free max 83.7, m=0.5 min 363); m=0.2 scores 80-205 (03 risk); deviations: spectral helper band ±12° (±10° failed 20px/-10°), crop levels from profile not mottled clean, borderline frames include period 5 fallback path.

- fixer a82fe9e12e2cdc130 (opus, watcher armed): apply 02-fix-list.md, full suite -W error, commit to main. Status: done. Commit c0d99ab; 187 passed -W error, mypy clean. THRESHOLD=154.0 = log-midpoint over seeds 100-199 both mottle kinds (free max 83.7 scorched; m=0.5 min 284.8 multiscale seed 195 4px/-4°); 1.84x/1.85x. The ~174 in the user question was scorched/seeds 100-119 only. Wrote 02-implementer-handoff.md. Borderline set re-chosen (tests/borderline.py).

## Review item dispositions
- B1 break (measurement no fallback for 1-px area -> inf period -> to_json raises): fold.
- B2 break (spurious-charge stats test tolerance ~1 SE, fails 30% seeds): fold (photons_peak=1 or 5 SE).
- N1 fold: choose dim crop from Synthetic.clean at ~0.2-0.3 of peak and use the §4.3 method numbers; current margin thin.
- N2 fold: avoid log(0) warning (mask/errstate).
- N3 fold: LocalStripes docstring says per-region angle via same neighbour-product sum.
- N4 pass: plan already tells implementer to re-measure with real code; reviewer confirmed margins survive.
- N5 fold: wording fix + state frame count of extremes test.
- N6 pass: out-of-range reports harmless for 02 tests; belongs to 05 (clamp/flag).
- O1-O4 owner: user ruled all as recommended (O1 depth top-level now; O2 `noise: float | Emccd`; O3 two crops, dim per N1; O4 accept A0=3e-3).

## Code review
- Running from BASE 1d07977 (commits 631c3af, d3b1150): standards reviewer acc5d259316d83c6d, spec reviewer a0fb9289800352f65 (both opus, watchers armed). Findings numbered S*/P*.
- Standards report (done; no hard violations): S1 "orientation" vs glossary Angle; S2 per-pixel "local Stripe Score" not in glossary; S3 mottle-kind in 4 places + isinstance(noise, Emccd) x3; S4 _PAD/A0 coupled to analysis.py MIN_SIDE/THRESHOLD; S5 names hot/p_star/g/_norm/e/k/win; S6 MIN_PAIRS public vs _PERIOD_SPREAD; S7 report.to_dict None-or-float x3; S8 test_cli imports from test_analyse; S9 test data clump / assert pair; S10 _crop_columns placement; nits blank lines. Spec report (done; no blocking gaps, 187 green): P1 implementer handoff missing (depth margins, suite time, m=0.2 flag for 03); P2 spikes deferred to 06; P3 no scope creep; P4 THRESHOLD 150 not log-midpoint ~174 (plan rule), margin 1.8x; P5 dim crop from profile-only frame not mottled clean; P6 oracle band ±12° not ±10°.
- Dispositions:
  - fix S1: glossary says Angle, not orientation (docstrings/comments).
  - fix S2: don't stretch "Stripe Score" to per-pixel; describe as local energy ratio (avoids glossary change).
  - fix S4: make _PAD/A0 coupling to MIN_SIDE/THRESHOLD explicit (assert or shared constant).
  - fix S5: rename unclear names (g reuse, _norm->standardise, hot, p_star, e, k, win) where cheap.
  - fix S6: consistent visibility (MIN_PAIRS private like _PERIOD_SPREAD; tunables in private module).
  - fix S7: helper for None-or-float in report.to_dict.
  - fix S8: move BORDERLINE/borderline_frame to a non-test helper module.
  - fix nits: blank lines.
  - fix P1: write 02-implementer-handoff.md with depth margins, suite time, m=0.2 flag for 03.
  - owner P4: user ruled use log-midpoint (~174) per plan rule (against rec to keep 150) -> fix list. Applied rule gives 154 (174 was an underestimate of the m=0.5 low); surfaced to user at close for confirmation.
  - pass S3: two mottle kinds; table/noise-stage refactor premature, revisit when 06 adds spikes.
  - pass S9/S10: test-helper shape, low value.
  - pass P2: deliberate deferral to 06 per plan §1.
  - pass P3: nothing to act on.
  - pass P5: profile-only crop matches AC wording ("parts of the profile") better than plan.
  - pass P6: ±12° justified by grid-edge failure at 20px/-10°; harmless for m=0 check.

## Next
CLOSED 2026-11-10. Commits 631c3af, d3b1150, c0d99ab. Owner item open with user: confirm THRESHOLD 154 (rule over both mottle kinds) vs 174 (scorched only). Files archived to .archived/.
