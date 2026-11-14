# 16: Continuous stripe score

**What to build:** A Stripe Score that changes smoothly under small pixel changes. Today's score is the highest peak ratio over the groups that survive hard gates (minimum size 3x2 Periods, leakage), so a group appearing or vanishing at a gate makes the score jump: replacing about 0.3% of a Stripe-free frame's pixels with their column median moves it between 0 and 15-39, and once from 39.0 to 79.4 (`.scratch/stripe-detector/handoffs/06-critic-3.md`); ticket 07's P1 saw one paired frame go from 60.5 to 8.4 between 30 and 293 Spike events (`.scratch/stripe-detector/handoffs/07-prototype-p1.md`). The calibrated false-alarm rate is unaffected (it is an order statistic over frames), but the score reads poorly as "how close a borderline frame was" (spec story 2).

Options:
- a smooth size and leakage weight on the peak ratio instead of hard gates;
- the score of the best group before gating.

Either is a detector change: `make measure`, a calibration re-store (CLAUDE.md, the re-store procedure) and the held-out tests.

**Blocked by:** 07

**Status:** needs-triage

- [ ] Small pixel changes (the 06 critic-3 column-median replacement) move the score by a bounded amount, stated and tested.
- [ ] The feasibility gate and the calibrated rates of ticket 07 still hold after re-measure and re-store.
