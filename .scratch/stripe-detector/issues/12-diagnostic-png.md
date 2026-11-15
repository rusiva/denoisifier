# 12: Diagnostic PNG

**What to build:** An experimenter can check a result by eye. A CLI option writes a PNG showing the frame with the striped-region outlines, phase-break lines and fork markers (direction shown) drawn over it, plus a short caption with the verdict, score, and each region's period and angle.

**Blocked by:** 09, 10

**Status:** ready-for-agent

- [ ] With the option, the CLI writes a PNG; without it, no PNG is written and matplotlib is not imported.
- [ ] The PNG shows the frame with a robust contrast stretch (spikes don't wash it out), region outlines, break lines and fork markers that tell the two directions apart.
- [ ] The caption shows the verdict, score, and each region's period and angle.
- [ ] A smoke test checks that the PNG exists and has the frame's aspect ratio.

## Comments

- 2026-11-15, from ticket 10 (Forks). The PNG will draw the fake Phase Breaks the break finder reports on close Fork pairs and on Forks near a region edge (ticket 10 Comments, ticket 18). Fork markers are a point plus a direction: +1 = going toward row 0 of the analysed frame past the Fork, one stripe becomes two (toward column 0 in file layout when transposed; the value is the same in both layouts).
