# 06: Spikes and clipped pixels

**What to build:** Data-quality problems typical of EMCCDs don't fool the detector. The generator gains spikes (cosmic-ray hits and hot pixels as single bright pixels and short streaks) and clipping (saturation at a set level). `analyse` always rejects spikes and leaves clipped pixels out of the analysis. Clipping is detected automatically, with an optional clip level to override it. Both counts appear in the report.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The generator can add a configurable number of spikes and clip at a configurable level, and reports both in its ground truth.
- [ ] The report gives `spike_pixels` and `clipped_pixels`, matching the generator's truth within a small tolerance.
- [ ] Stripe-free frames with spikes come out not striped at the same rate as frames without spikes.
- [ ] On striped frames with clipped stripe peaks, modulation depth stays within tolerance (the clipped pixels don't flatten the measurement).
- [ ] The clip level can be overridden through the library option and a CLI flag.

## Comments

- 2026-11-13, ruling (orchestrator, `.scratch/stripe-detector/handoffs/06-orchestrator.md`, Decisions Q4/O2; critic `06-critic.md` O2): clipped pixels are left out of the **modulation depth** only, not out of the whole analysis. Detection, Period, Angle, region growth and the Mask use them as they are. Reason: story 26's purpose clause is the depth ("so that flattened stripe peaks don't distort the modulation depth"), and clipping keeps the stripes' phase and periodicity; leaving clipped pixels out of growth and the filters would put holes into the Mask and work against the mask criterion. The docstrings say "left out of the modulation depth".
- 2026-11-13, AC 4 is met only in part (orchestrator, final ruling on `.scratch/stripe-detector/handoffs/06-critic-2.md` item 1). It holds at the unchanged `DEPTH_TOL` on full frames clipped at 0.4 of the clean maximum (tested with teeth against `clip_level=inf`), and on a partial region with a mild clip (0.8, a no-harm guard). On a partial region where about a fifth or more of the region is clipped, the reported depth is low, toward the flattened value; there the test asserts only that the depth is not worse than with no exclusion. Reason: an estimator limit, not lost information. On such regions the peaks are clipped but the troughs are intact in nearly every cycle (critic 2's check on seeds 396_400-396_405: 74-100% of interior pixels at a clip of 0.4), and no tested estimator (window guards, weighted fits, normalised convolution; `evidence/06-prototype-p2.md`) uses them. The fallback is silent per region; `clipped_pixels` is the warning. Follow-up: issue 15.
- 2026-11-13, approval (orchestrator, `06-orchestrator.md`, Decisions Q1): add `src/denoisifier/_data_quality.py` to `STAMPED_FILES` in `tests/slow_stamp.py`. Reason: the new spike and clip module affects detector output, and `test_stamped_files_cover_the_slow_tier` requires every file in `src/denoisifier/` to be classified. The change only widens the stamp; it loosens nothing.
