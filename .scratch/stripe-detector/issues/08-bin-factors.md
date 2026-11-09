# 08: Bin factors

**What to build:** An experimenter who bins the sensor (possibly unequally) still gets correct detection and measurements. Bin factors (horizontal and vertical, default 1×1) are a library option and a CLI flag. All periods, angles, region-size minimums and positions in the report are in **sensor pixels**. The bin factors change the *detection* as well as the reporting: the search range (period 3–20 px, angle ±10° from vertical) and the 3×2-period region minimum are converted into binned-array coordinates before searching. Any part of the period range that falls below 2 array pixels after binning is reported as a warning.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] With 1×2 binning, stripes at a physical 10° tilt (about 19.4° in the array) are detected and reported as about 10°.
- [ ] With 2×1 binning, a physical period of 12 px is reported as about 12 px (not 6).
- [ ] With 2×1 binning, the report warns that physical periods below 4 px can't be resolved.
- [ ] Region bounding boxes and the mask stay in frame (array) coordinates, while measurements are in sensor pixels; the report says which units each field uses.
- [ ] 1×1 binning gives the same results as no option.
