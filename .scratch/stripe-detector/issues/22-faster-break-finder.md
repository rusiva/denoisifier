# 22: Faster phase-break finder

**What to build:** A faster `_local_phase.find_phase_breaks` at P 3-4, where the finder's ~230k samples at a 0.5 P stride are re-binned for every coarse, fine and golden-section angle and again in every greedy round. On ticket 13's AC 1 frame (P3, two breaks plus a Fork) the break pass costs about 1.4 s, now the largest single-threaded stage after the bank.

Deferred from ticket 13 (slice 7 dropped; ticket Comments 2026-11-16, `.scratch/stripe-detector/handoffs/13-orchestrator.md`, `13-implementer-4.md` "Slice 7"):
- Ticket 09's proposal (coarse angle scan on strided, capped samples, then fine scan, golden-section refinement and fit on full-density samples within ±4 P of the coarse line) was built as ticket 13 slice 7 (branch `t13-s7`, `b029f7f`). At caps of 10k/20k/40k/80k, every row passed exactly (found, AC 4, labels, line error), and the reported breaks were bit-identical. It still failed the pre-stated "same basin" row on 27-115 of 216 frames, apparently only on searches that found no line. Any cap below a full frame's sample count gives stride ≥ 2, so the coarse scan as built moves the basin of the rejected searches.
- A plain sample cap is out: it moved line error at P 3-5 (full P 4 max 0.17 → 0.75 P; ticket 09).
- Possible directions (none measured): make the coarse scan's argmax robust to stride (e.g. a stride-invariant objective, or several stride phases), cache the binning across angles (`_Samples.scan`), or decide with ticket 09's owner whether same-basin should be required on searches that find no line. That is a criterion change, so the owner rules on it before any look at data.

Explore set: `~/.cache/denoisifier/p13-c1/explore_v2.pkl` (git-ignored; recipe and sha256 in `prototypes/p13/c1/explore.py`; 216 frames on the full_break, fullcap, pair* and bin* tags). Ticket 13's reference outputs: `.scratch/stripe-detector/p13-c1-ref/`. Delete both at this ticket's close.

Go/no-go criteria are written down before any run (ticket 13 plan section 2, slice 7, is the template): same basin; found and AC 4 identical; per-frame |Δ line error| ≤ 0.05 P; per-tag max not worse; plus fresh unregistered frames reserved in `USED_SEEDS` first.

**Blocked by:** 13

**Status:** needs-triage

- [ ] A prototype on the explore set meets criteria stated before the run, or the ticket closes with the reason it can't.
- [ ] If adopted: the AC 1 break-pass stage time (`tests/speed.py`) drops by the measured amount, ticket 09's tests are green, and the break/Fork calibration is re-stored (CLAUDE.md, "After a score-moving change", if scores move).
