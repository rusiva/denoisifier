# 18: The Phase Break finder on frames with Forks

**What to build:** Phase Breaks found right on frames that also hold Forks, where ticket 10's fork-first ordering cannot reach. Ticket 10 left the frozen ticket-09 break finder unchanged and explains away only the Forks its pre-break search finds (gate `_FORK_GATE_EVIDENCE`); a Fork it does not see is a winding the break finder reads as a break. Measured in ticket 10's prototype P2 (`.scratch/stripe-detector/handoffs/10-prototype-p2.md`; freeze `3922e33`, results `9872cb4`, validation seeds 111_600-111_732):

- **Fake breaks on opposite Fork pairs 3 Periods apart in 09-size regions** (semi-axes 5 by 6.6 P): validation 7/27 frames (BASE 10/27).
- **Fake breaks on Forks within 3 Periods of a region edge:** 11/20 at 2 P, 5/20 at 3 P (equal to BASE). Such Forks are not found (the fork finder needs about 4 P inside the edge), so the gate is silent.
- **The 1.5-3 Period hole next to a break:** a Fork and a Phase Break closer than about 3 P are usually both lost (1.5 P 7/40, 2 P 8/40; 3 P 38/40 validation, 50/60 explore).
- **The fork finder's loop size is untuned:** one run at R = 1.5 P, taken with a declared rule and rejected (AC 3 at 3 P 43/60); R = 2.0 P frozen.

Real frames: the owner ruled (2026-11-15) these are rare and the regions large; low priority.

Any fix touches the `_BREAK_*` constants, the break finder or the fork finder. It needs fresh explore and validation seeds (111_200-111_599 and 111_733-111_999 were never generated and are free; ticket 10's Comments), and ticket 09's criteria re-proved, with ticket 10's.

**Blocked by:** 10

**Status:** needs-triage

- [ ] On fork-pair and edge-fork frames, fake Phase Breaks are no more frequent than on fork-free frames of the same geometry.
- [ ] A Fork and a Phase Break closer than 4 Periods are both found, at a stated distance.
- [ ] Ticket 09's and ticket 10's acceptance criteria still hold.
