# 21: Batch or watch mode for analysis during acquisition

**What to build:** A long-lived way to analyse many frames, so that the interpreter and import start (about 0.45-0.55 s after ticket 13: numpy and `scipy.ndimage/fft/special`) and any warm-up are paid once, not per frame. Two candidate shapes: a batch CLI that takes several CSV files, or a `--watch` folder mode that analyses each new frame as Solis writes it.

From ticket 13 (orchestrator ruling O2, `.scratch/stripe-detector/handoffs/13-orchestrator.md`; plan `13-plan.md`, sections 6-7): the planner rated it the cheapest route to under about 1 s per frame during acquisition. After ticket 13 the cold per-frame CLI call is projected at about 2.8 s and the warm pipeline at about 2.3 s on the worst frame; the import floor plus `read_frame` alone is about 0.6 s.

This is a new public interface and changes how the experimenter runs the tool, so the owner triages it (shape, output naming, what happens to partially written files and to a frame that fails). Do not start before that ruling.

**Blocked by:** 13

**Status:** needs-triage

- [ ] The owner has ruled on the shape (batch, watch, or neither) and its interface.
- [ ] Per-frame wall time after the first frame is recorded on the worst frame next to the spec, against the cold CLI time.
- [ ] Each frame's report equals the single-frame CLI's report for the same file.
