# 01: First end-to-end version: stripes found on a clean frame

**What to build:** A first thin version that works end to end. An experimenter can run the CLI on a CSV frame that has clear, full-frame stripes and get a JSON report saying the frame is striped, with one global period and angle. Set up the Python project (`uv`, `src/` layout, `pytest`) and a minimal seeded synthetic generator: a profile (elliptical, rotated, mildly asymmetric Gaussian) times stripes covering the whole frame, plus simple additive noise. The generator returns the frame together with its ground truth (period, angle, modulation depth). Later tickets replace the detection method; this ticket only proves the path from generator to reader to `analyse` to report to CLI. Context: `.scratch/stripe-detector/spec.md`, `GLOSSARY.md`, ADR 0001.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Project installs and tests run with `uv run pytest`.
- [ ] The generator is seeded (same seed gives the same frame), returns frame plus ground truth, and can write a frame as a plain CSV grid.
- [ ] Reading a plain comma-separated grid of floats with no header gives a 2D array of the right shape.
- [ ] `analyse(frame)` returns a Report with `striped`, `score`, and one global period (in pixels) and angle (degrees from vertical).
- [ ] On generated frames with clear full-frame stripes (m about 0.6, low noise), the report is striped and its period and angle match the ground truth within tolerance (spec, Further Notes). A frame with only the profile is not striped.
- [ ] The Report converts to JSON. The CLI reads a CSV frame and writes the JSON report.
- [ ] Tests exist at all three seams: `analyse`, reading a frame, and the CLI end to end.
