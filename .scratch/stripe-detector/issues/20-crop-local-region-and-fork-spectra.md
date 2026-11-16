# 20: Crop-local spectra for the region and Fork steps

**What to build:** A cheaper region and Fork pass. After ticket 13, the worst 400x1600 frame (P3, two Phase Breaks, one Fork) still spends about 0.75 s in `_qualifying_regions`, the size-rule and leakage filters, `_BreakPass.depth` and the pre- and post-break Fork searches. Each of them filters the full padded frame spectrum per candidate, although it only reads one region's crop. Compute these filters on a crop-local spectrum (the region's bounding box plus a margin of a few filter widths) and run fewer full-frame filters per candidate.

From ticket 13 (orchestrator ruling O2, `.scratch/stripe-detector/handoffs/13-orchestrator.md`; plan `13-plan.md`, sections 2 and 6): the ticket closes at about 2.8 s cold per frame (projected, 4 threads); the owner asked for runtime cut as far as computation allows, down to about 1 s (ticket 13 Comments, 2026-11-15). Ticket 09 measured the FFT filters at a flat 0.17-0.20 s per region on the break pass (ticket 13 Comments, 2026-11-14).

A crop changes the circular wrap and the edge handling of each filter, so it is expected to move scores, depths and break and Fork evidence: it needs pre-stated equivalence criteria, a null screen on fresh seeds, `make measure` and both package re-stores. Ticket 13's 5-smooth pad experiment is a warning: a changed wrap moved edge-pixel ratios by up to +190 %.

**Blocked by:** 13

**Status:** needs-triage

- [ ] The region and Fork steps on the worst frame (`tests/speed.py`) are measurably faster, recorded in `.scratch/stripe-detector/stage-timings.md`.
- [ ] Regions, Phase Breaks and Forks are found as before on the equality-harness frames, within tolerances stated before the change.
- [ ] Every calibration and accuracy test passes; stored thresholds are re-calibrated if the output changed.
