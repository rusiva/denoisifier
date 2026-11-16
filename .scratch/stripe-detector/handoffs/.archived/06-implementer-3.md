# 06 implementer 3: handoff (5c acceptance red, stopped)

## Done

- Ticket 06 Comments: the orchestrator's AC 3 ruling (2026-11-13) and the 5a non-contiguous-tuple record. Ticket 07: one appended line on the hard group gating (uncommitted; the owner's edits are in the same file, never staged).
- Commit `bb07c77`: freeze `_CLIPPED_WEIGHT_MAX = 0.05`, `CLIP_LEVEL_FRACTION = 0.4`, `CLIP_MIN_SHARE = 0.02`, `CLIP_DEPTH_EPS = 0.01`, new `SPIKE_SCORE_MEDIAN_TOL = 5` (`SPIKE_SCORE_TOL` was never added). Lockfile lines added. `make test-fast` on that tree before the commit: exit 0, `773 passed, 4 deselected in 403.67s`.
- AC 2-5 tests: implementer 2's patch plus AC 3 as ruled (per-seed verdicts at `THRESHOLD` and `GATE_STORED_THRESHOLD` from a cached pair; a separate test of the median |score change| over all 40 pairs). Lint and mypy clean. **Not committed**: `06-implementer-3-ac-tests.patch` (applies to `tests/test_analyse.py` at `bb07c77`); `tests/test_analyse.py` restored.

## Acceptance: red (2 of 226 selected)

Command: `uv run --locked pytest tests/test_analyse.py -q -rf -k "spike or clip"`, EXIT=1, `2 failed, 224 passed, 486 deselected in 206.31s`; log `06-implementer-3-acceptance.log`. All AC 3 tests (verdicts and the median) and all AC 4/5 tests passed.

1. `test_report_counts_spike_pixels[pass-mark-m0.5-90]`: `striped` False, score 149.7 < `THRESHOLD` 154. The spike count passes (62 vs truth 61). **Not caused by spikes**: the same frame without spikes also scores 149.7, not striped (1 false spike pixel). The test asserts full detection on 30-photon scorched m 0.5 frames, below the detector's reach on this seed. Open: whether the region check belongs in the pass-mark case (a test-design question, not mine to decide after seeing the result).
2. `test_spike_count_ignores_the_baseline`: `ValueError: envelope max <= 0` in `analysis._light`. Test-design defect: `shifted = frame - frame.max() / 2` uses the spiked frame's max (about 9.9 x the clean max), so only 0.05% of pixels stay positive. A shift by `s.clean.max() / 2` (or the spike-free `frame` max) would test what the docstring says. Not changed: the instruction was stop on red.

No re-tuning or loosening was done.

## Rerun after the orchestrator's test-construction ruling: still red (1 of 226)

`06-implementer-3-ac-tests.patch` now carries both corrections (it replaces the earlier patch; it applies at `bb07c77`). Same command: EXIT=1, `1 failed, 225 passed, 486 deselected in 290.41s`; log `06-implementer-3-acceptance-2.log`. The paired AC 2 check passes, including pass-mark seed 90.

`test_spike_count_ignores_the_baseline` still raises `envelope max <= 0`. On seed 81 (typical m 0.5) `clean.max()` is 100, but the frame smoothed at `_ENVELOPE_SIGMA` peaks at 44.1 (the mottle and profile spread the light out). A shift of 50 leaves 2.9% of pixels positive and the smoothed peak at -5.9. `median_filter(f, 3).max()` is also about the clean peak, so it fails the same way. A shift that keeps the light would be below the smoothed peak, for example half of `gaussian_filter(s.clean, _ENVELOPE_SIGMA).max()` (about 22), or the clean median (9.7). Choosing one is a new ruling. The ticket 06 Comment on the ruling is in the working tree but not committed.
