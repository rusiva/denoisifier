# 05: Striped regions and mask

**What to build:** The report says *where* the stripes are. The generator gains partial striped regions with soft edges, including several regions with different periods in one frame, and returns the true region masks. `analyse` splits the frame into striped regions and reports each one with its period, angle, modulation depth and bounding box. It also produces a mask with the same shape as the frame. Regions under 3 periods wide or 2 periods tall are not reported. The CLI writes the mask as a CSV laid out like the input.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] The generator places one or more soft-edged elliptical striped regions, each with its own period, and returns their true masks.
- [ ] The report lists each region with its period, angle, modulation depth and bounding box; the frame-level verdict is striped if any region is reported.
- [ ] Mask overlap with the true region (intersection over union) is at least the spec's tolerance at typical noise.
- [ ] Two regions with different periods in one frame are reported separately with the correct periods.
- [ ] A region just below the 3×2-period minimum is not reported; one just above it is.
- [ ] Stripes covering only part of the envelope are found; the dark area outside the envelope is never reported as striped.
- [ ] The CLI writes the mask CSV with the same rows and columns as the input frame.
