# 15: Depth of regions with a clipped core

**What to build:** A modulation-depth estimator that stays within tolerance on a Striped Region whose core is clipped. Ticket 06 leaves clipped pixels out of the depth by dropping pixels whose local filter window holds 10% or more of clipped pixels, and falls back to the plain (flattened) depth when nothing is left. On a partial region with about a fifth or more of the region clipped, this reports a low depth, silently per region. The troughs are still there: at a clip of 0.4 of the clean maximum, 74-100% of the interior pixels lie in cycles whose peaks are clipped but whose troughs are intact (`.scratch/stripe-detector/handoffs/06-critic-2.md`, seeds 396_400-396_405, noise-free). So this is an estimator limit, not lost information.

Already tried and failed (`.scratch/stripe-detector/evidence/06-prototype-p2.md`): box and Gaussian window guards (plan D9 and variants), a global weighted fit of mean, cos and sin over the region or its bounding box (biased by the envelope, 34-40/40 misses on full frames), local normalised convolution (12-19/40), and a censoring correction on top of it.

Candidates:
- a censored model fit at the region's known Period and Angle (trough level plus curvature); untested, badly conditioned under scorched Mottle and EMCCD noise;
- the cheap alternative: a per-region warning when a region's clipped share passes a limit, so the user knows its depth is low.

**Open question for the owner (external knowledge, sets the priority):** do real frames ever have a fifth or more of a Striped Region saturated? The repo's only real frames are sCMOS (`tests/data/solis/NOTICE.md`), so nothing here answers it.

**Blocked by:** 06

**Status:** needs-triage

- [ ] On partial regions clipped at 0.4 of the clean maximum (ticket 06's `test_heavily_clipped_partial_region_is_no_worse_than_no_exclusion` frames), the reported depth is within `DEPTH_TOL` of the truth, or the region carries a warning that its depth is unreliable.
- [ ] Full-frame and mild-clip results of ticket 06 do not get worse.
