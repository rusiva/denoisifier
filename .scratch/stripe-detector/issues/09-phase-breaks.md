# 09: Phase breaks

**What to build:** The report shows where the stripe pattern is broken by a sideways shift. The generator gains phase breaks: a straight-ish line with a chosen angle and phase jump, with every stripe on one side shifted. `analyse` finds phase breaks from the local phase (ADR 0001) and reports each one as a line with its jump size in radians. Breaks usually cross the stripes roughly horizontally, but detection must not depend on that.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] The generator places phase breaks with any line angle and jump, and returns the true line and jump.
- [ ] Breaks with jumps of π/2 or more are found at typical noise; the reported line is within one period of the truth and the jump within ±π/4.
- [ ] A break running at an unusual angle (far from horizontal) is still found.
- [ ] A frame with phase breaks is still recognised as striped, and its region is not split into fake separate regions.
- [ ] The report lists `phase_breaks`, each with a line and a jump.
