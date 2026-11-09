# Periodicity and orientation, not scale, separate stripes from mottle

Mottle in real frames has features from many pixels across down to the stripe period itself (3–20 px). So no frequency band contains only stripes, and an obvious bandpass or FFT-peak filter would also pick up mottle. We therefore detect stripes by **local periodicity**: several consecutive cycles at a consistent period and phase. We also use **near-vertical orientation** (within about ±10°) as a constraint. Mottle has no repeating pattern and no preferred direction, so it fails both tests. A region must span at least 3 periods wide and 2 periods tall before it counts.

## Consequences

- The detector has to estimate local phase. That same local phase is what makes phase breaks and forks detectable, so the two features share one foundation.
- Short runs of 1–2 stripes cannot be told apart from mottle by design, and are never reported.
- The decision threshold is calibrated on synthetic stripe-free frames (envelope + mottle + EMCCD noise) to a target false-alarm rate. It does not come from an analytic noise model. If the real mottle turns out to be directional, this decision needs revisiting.
