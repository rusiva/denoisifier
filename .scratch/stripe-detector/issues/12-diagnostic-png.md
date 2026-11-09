# 12: Diagnostic PNG

**What to build:** An experimenter can check a result by eye. A CLI option writes a PNG showing the frame with the striped-region outlines, phase-break lines and fork markers (direction shown) drawn over it, plus a short caption with the verdict, score, and each region's period and angle.

**Blocked by:** 09, 10

**Status:** ready-for-agent

- [ ] With the option, the CLI writes a PNG; without it, no PNG is written and matplotlib is not imported.
- [ ] The PNG shows the frame with a robust contrast stretch (spikes don't wash it out), region outlines, break lines and fork markers that tell the two directions apart.
- [ ] The caption shows the verdict, score, and each region's period and angle.
- [ ] A smoke test checks that the PNG exists and has the frame's aspect ratio.
