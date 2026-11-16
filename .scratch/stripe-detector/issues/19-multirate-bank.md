# 19: Multirate local-stripe bank

**What to build:** A faster stripe bank. Each bank filter's demodulated response is band-limited to its support box (ticket 13, slice 5's `_Spectrum.gaussian` seam), so the energy and the stripe-vs-reference ratio can be computed on a grid decimated to that box (twice the band, for the energy), box-filtered and divided there, and then interpolated to full resolution. The full-resolution `response` and `local_mean` stay, but only for the (Period, Angle) pairs that win somewhere, through slice 5's seam, so `analysis._phase_steps` keeps full-resolution phase.

Deferred from ticket 13 (orchestrator ruling O1, `.scratch/stripe-detector/handoffs/13-orchestrator.md`; plan `13-plan.md`, section 2, "Not adopted"):
- **Estimated, not measured** (ticket 13 planner, measured FFT sizes): the bank's inverse FFTs drop from 2.6-3.0 s to 0.57 s (K = 6, 28 % mean box area) or 0.88 s (K = 8, 42 %). Net of the interpolation and the winners' full-resolution filters, about −1.0 to −1.5 s single thread on top of ticket 13's slice 5; about −0.5 to −0.8 s with slice 6 (complex64 bank); about −0.4 s at 4 threads. That is within ticket 13's ±15 % projection noise.
- **Risk:** the interpolated ratio moves the score and the region peak positions at roughly the 1e-3 relative level, about 100x ticket 13's slices 5-6. Period and Angle accuracy depend on the winner responses staying at full resolution.
- It is score-moving: adopting it needs its own `make measure` and both package re-stores (about 3 h of gates).

Start with a prototype (ticket 13's planned P2, `prototypes/p13/multirate/`, foreground, on ticket 13's equality-harness frames, seeds 601_000-601_099) with its go/no-go criteria written down before it runs. Ticket 13's plan proposed: score within 1e-3 relative; regions, breaks and forks found identically on the harness set; every accuracy test green, `wide` included; bank saving ≥ 0.5 s at the shipped thread count. Fresh, unregistered seeds for any further look go into `USED_SEEDS` first. If adopted, add a short note to ADR 0001 (it changes the computation, not the definition).

**Blocked by:** 13

**Status:** needs-triage

- [ ] A prototype measures the bank saving and the score and peak shifts on the harness frames, against criteria stated before the run.
- [ ] If adopted: the worst-frame warm pipeline (`tests/speed.py`) is faster by the measured amount, every accuracy test is green, and the stored thresholds are re-calibrated (CLAUDE.md, "After a score-moving change").
- [ ] If adopted: ADR 0001 has a note on the multirate computation.
