# 06: Spikes and clipped pixels

**What to build:** Data-quality problems typical of EMCCDs don't fool the detector. The generator gains spikes (cosmic-ray hits and hot pixels as single bright pixels and short streaks) and clipping (saturation at a set level). `analyse` always rejects spikes and leaves clipped pixels out of the analysis. Clipping is detected automatically, with an optional clip level to override it. Both counts appear in the report.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The generator can add a configurable number of spikes and clip at a configurable level, and reports both in its ground truth.
- [ ] The report gives `spike_pixels` and `clipped_pixels`, matching the generator's truth within a small tolerance.
- [ ] Stripe-free frames with spikes come out not striped at the same rate as frames without spikes.
- [ ] On striped frames with clipped stripe peaks, modulation depth stays within tolerance (the clipped pixels don't flatten the measurement).
- [ ] The clip level can be overridden through the library option and a CLI flag.
