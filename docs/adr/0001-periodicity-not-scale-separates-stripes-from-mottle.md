# Periodicity and orientation, not scale, separate stripes from mottle

Mottle in real frames has features from many pixels across down to the stripe period itself (3–20 px). So no frequency band contains only stripes, and an obvious bandpass or FFT-peak filter would also pick up mottle. We therefore detect stripes by **local periodicity**: several consecutive cycles at a consistent period and phase. We also use **near-vertical orientation** (within about ±10°) as a constraint. Mottle has no repeating pattern and no preferred direction, so it fails both tests. A region must span at least 3 periods wide and 2 periods tall before it counts.

## Consequences

- The detector has to estimate local phase. That same local phase is what makes phase breaks and forks detectable, so the two features share one foundation.
- Phase breaks are found from the demodulated local phase of each reported region (a two-magnitude fit across straight lines), after the threshold.
- Short runs of 1–2 stripes cannot be told apart from mottle by design, and are never reported.
- Binning (ticket 08) makes isotropic Mottle directional in the frame. Measured at 1x2: Stripe-free max ratio 1.88x at 4.19 px, 1.06-1.27x at 4.69-12.8 px. The bin-transfer compensation was measured and rejected (it over-corrects 1x2 to 0.8-0.9x and inflates 2x1 up to 1.9x); binned frames are outside the calibration's claim, and the Report notes it. References count toward the searchable range (`searched_periods`).
- The decision threshold is calibrated on synthetic stripe-free frames (envelope + mottle + EMCCD noise) to a target false-alarm rate. It does not come from an analytic noise model. If the real mottle turns out to be directional, this decision needs revisiting.
