# 02: Stripes told apart from mottle in EMCCD noise

**What to build:** The detector keeps working on realistic frames. Mottled envelopes with EMCCD noise and no stripes come out not striped, and clear stripes come out striped and measured. The generator gains "scorched" and "multiscale" mottle and the EMCCD noise chain. The forward model is in the spec, from the prototype: log-normal mottle from isotropic Gaussian random fields; Poisson, then EM gain as a Gamma distribution, then Gaussian read noise, plus spurious charge from clocking. Detection is switched to **local periodicity plus near-vertical orientation** (ADR 0001): several consecutive cycles at a consistent period and phase, within about ±10° of vertical. It does not rely on size, because mottle overlaps stripes in size. The detector estimates local period, angle, phase and modulation depth; later tickets build on that local phase.

**Blocked by:** 01

**Status:** resolved

- [x] The generator supports scorched mottle (typical strength about 0.4) and multiscale mottle (about 0.35), and the EMCCD chain with configurable photon count at the peak, EM gain (including off), read noise and spurious charge.
- [x] Generator self-consistency: m = 0 gives no stripe peak in the spectrum; on a clean striped frame, the true period and angle match the spectral peak.
- [x] At about 100 photons at the peak with scorched mottle: stripe-free frames come out not striped, and frames with m ≥ 0.5 come out striped, across a batch of seeds (provisional threshold; formal calibration comes later).
- [x] For detected stripes, the report's period, angle and modulation depth are within the spec's tolerances.
- [x] Modulation depth is measured relative to the local envelope: it is the same for the same m in bright and dim parts of the profile.
- [x] Periods from 3 to 20 px and tilts up to ±10° are detected.

## Comments

Done in `631c3af` (generator: mottle and EMCCD chain), `d3b1150` (local periodicity and orientation detector) and `c0d99ab` (code-review fixes); 187 tests pass (`uv run pytest`, about 7 min). Criteria ticked after checking each against its tests in `tests/test_synthetic.py` and `tests/test_analyse.py`.
