# Stripe detector

Status: ready-for-agent

## Problem Statement

I record 2D intensity frames with an Andor Newton 971 EMCCD. A physical effect I study sometimes forms **stripes** in these frames: a roughly periodic, near-vertical pattern that multiplies the light spot. The frames are noisy. The spot itself is not a clean Gaussian: it is a distorted **profile** multiplied by **mottle**, random "scorched-earth" brightness variation without a repeating pattern, whose features can be as small as the stripe spacing. The stripes' **modulation depth** can be comparable to the envelope itself, but it can also be weak. The stripes often cover only part of the spot, and their periodic structure is broken by **phase breaks** (lines where the stripes shift sideways) and **forks** (points where a stripe splits or ends).

Judging by eye whether a frame shows stripes, where they are, and how they are broken is slow, subjective, and unreliable for weak stripes. Mottle at stripe size makes it easy to "see" stripes that aren't there, and the result of the experiment depends on not doing that.

## Solution

A Python tool, usable as a library and as a command-line program, that takes one **frame** (a CSV of floating-point intensities) and reports:

- whether stripes are present, as a calibrated score plus a yes/no verdict. The default threshold falsely flags 1% of stripe-free frames.
- each **striped region**: a mask, plus its period, angle and modulation depth.
- each **phase break**: where it runs and how large its phase jump is.
- each **fork**: where it is and which way it points.
- data-quality counts: **spikes** rejected and clipped pixels excluded.

It only measures: it never changes or "cleans" the frame. A **synthetic generator** produces realistic frames with known ground truth, so the detector can be developed, tested and calibrated before real labelled frames exist.

## User Stories

### Analysing a frame

1. As an experimenter, I want to run one command on a frame CSV and get a stripe verdict, so that I can tell quickly whether the effect occurred in that exposure.
2. As an experimenter, I want a continuous stripe score alongside the yes/no verdict, so that I can see how close a borderline frame was to the threshold.
3. As an experimenter, I want the default verdict to falsely flag about 1% of stripe-free frames, so that a "stripes found" claim can be trusted.
4. As an experimenter, I want to change the false-alarm rate, so that I can trade missed weak stripes against false alarms for a given study.
5. As an experimenter, I want stripes with modulation depth 0.2 or more to be found in at least 90% of frames at my typical noise level and the default 1% false-alarm rate, so that real but moderate effects are not missed.
6. As an experimenter, I want stripes found even when they cover only part of the envelope, so that local occurrences of the effect are not missed.
7. As an experimenter, I want a separate entry for each striped region in a frame, so that I can study regions with different periods independently.
8. As an experimenter, I want each striped region's period in pixels, so that I can relate it to the physics of the effect.
9. As an experimenter, I want each striped region's angle from vertical, so that I can track tilts of up to about ±10°.
10. As an experimenter, I want each striped region's modulation depth, so that I can quantify how strong the effect is apart from overall brightness.
11. As an experimenter, I want each striped region's bounding box, so that I can find it quickly in the frame.
12. As an experimenter, I want a mask of the striped regions with the same shape as the frame, so that I can overlay it or use it in my own analysis.
13. As an experimenter, I want regions smaller than 3 periods wide or 2 periods tall to go unreported, so that short mottle features that look like stripes are not counted.
14. As an experimenter, I want periods from 3 to 20 pixels to be detectable, so that the full range of the effect is covered.
15. As an experimenter, I want blotchy mottle at stripe size to be rejected as non-stripes, so that the "scorched" spot texture is not mistaken for the effect.

### Phase breaks and forks

16. As an experimenter, I want each phase break found and reported as a line, so that I can see where the stripe pattern shifts.
17. As an experimenter, I want each phase break's jump size, so that I can tell small shifts (about π/2) from half-period shifts (about π).
18. As an experimenter, I want phase breaks with jumps of π/2 or more found reliably, so that significant shifts are always caught.
19. As an experimenter, I want phase breaks found whatever angle they run at, even though they usually cross the stripes roughly horizontally, so that unusual breaks are not missed.
20. As an experimenter, I want each fork reported as a point, so that I can see where stripes split or end.
21. As an experimenter, I want each fork's direction (splitting upward or downward), so that I can tell different kinds of fork apart.
22. As an experimenter, I want fake phase breaks and forks to be rare, at most about one per 20 defect-free striped frames, so that reported defects can be trusted.
23. As an experimenter, I want a frame with phase breaks or forks still recognised as striped, so that defects never hide the effect itself.

### Data quality

24. As an experimenter, I want cosmic-ray spikes and hot pixels rejected automatically, so that they don't create fake fine detail or fake forks.
25. As an experimenter, I want the number of rejected spike pixels reported, so that I can spot exposures heavily hit by spikes.
26. As an experimenter, I want clipped (saturated) pixels found and left out of the analysis, so that flattened stripe peaks don't distort the modulation depth.
27. As an experimenter, I want the number of clipped pixels reported, so that I know when to lower the EM gain.
28. As an experimenter, I want negative intensity values (for example after dark subtraction) accepted, so that my processed frames work without changes.

### Reading frames

29. As an experimenter, I want to pass a plain comma-separated grid of floats with no header, so that my exported frames work directly.
30. As an experimenter, I want to tell the reader explicitly to drop an extra first column from Andor Solis (pixel or wavelength axis), and be warned when the first column looks like an axis but was kept, so that axis values are never analysed as intensities and real pixels are never thrown away by guesswork.
31. As an experimenter, I want Solis header and footer metadata lines skipped, so that exports with metadata still load.
32. As an experimenter, I want the tool to tell me when it dropped an axis column or skipped metadata lines, so that nothing changes my data silently.
33. As an experimenter, I want a clear error for files with uneven rows or values that aren't numbers, so that a corrupt export fails loudly instead of giving a wrong answer.
34. As an experimenter, I want full-sensor 1600×400 frames and smaller crops accepted, so that I can analyse whatever region I recorded.
35. As an experimenter, I want to give horizontal and vertical bin factors, so that periods and angles stay correct if I bin unequally.

### Outputs

36. As an experimenter, I want the CLI to write a JSON report, so that I can collect results across many frames in scripts.
37. As an experimenter, I want the CLI to write the striped-region mask as a CSV laid out like the input, so that it lines up pixel for pixel with my frame.
38. As an experimenter, I want an optional diagnostic PNG showing the frame with the mask, breaks and forks drawn over it, so that I can check the result by eye.
39. As an experimenter, I want one frame analysed in under about 5 seconds on a laptop CPU, so that I can analyse frames while the experiment is running.
40. As a scripting user, I want to call the analysis as a library function on an in-memory array, so that I can build it into my own pipelines without going through files.
41. As a scripting user, I want the library to return a structured report object rather than text, so that I can use the results directly in code.

### Synthetic data

42. As a developer, I want a synthetic generator that builds frame = (profile × mottle) × (1 + stripe modulation) + EMCCD noise, so that the detector can be tested where the right answers are known.
43. As a developer, I want the generator to return its ground truth (region mask, period, angle, modulation depth, break lines and jumps, fork points and directions), so that tests can compare the report against it.
44. As a developer, I want the profile to be an elliptical, rotated, mildly asymmetric Gaussian, so that it matches the real spot.
45. As a developer, I want "scorched" mottle (blotchy patches with fine grit) as the typical case, and multiscale mottle as a harder case, so that the detector is tested against both.
46. As a developer, I want EMCCD noise (shot noise, then EM gain, then read noise, plus spurious charge from clocking and spikes) with every part configurable, so that synthetic frames are as noisy as real ones.
47. As a developer, I want the noise level set by peak photon count, from about 5000 down to about 10, so that the full range of light levels is covered.
48. As a developer, I want to place phase breaks with any jump and line, and forks with either direction, so that defect detection can be tested systematically.
49. As a developer, I want partial striped regions with soft edges, so that region mapping is tested realistically.
50. As a developer, I want the generator to give the same frame for the same seed, so that test failures can be reproduced.
51. As a developer, I want to write generated frames as CSV, so that the CLI can be tested end to end on realistic files.
52. As a developer, I want the false-alarm thresholds calibrated from generated stripe-free frames, so that the default 1% rate means something until real frames are available.

### Later validation

53. As an experimenter, I want to recalibrate the thresholds on my own stripe-free frames later, so that the false-alarm rate holds on real data and not only on synthetic data.

## Implementation Decisions

- **Domain language** follows the root glossary: Frame, Profile, Mottle, Envelope, Stripes, Noise, Spike, Modulation Depth, Striped Region, Phase Break, Fork. Code, report fields and docs use these terms. "Signal" is not used.
- **Stack**: Python 3.11+, NumPy/SciPy, matplotlib (only for the diagnostic PNG). The project is managed with `uv` and laid out as a `src/` package. No GPU.
- **Modules**:
  - **Frame reading.** Reads a CSV file into a 2D float array, plus *reader notes* (axis column dropped, metadata lines skipped, warnings). A plain grid always keeps every column. A Solis axis column is dropped **only when explicitly requested**. Guessing is not allowed: a crop on the rising side of the profile can have a real intensity column that counts up. When the first column looks like an axis (strictly increasing) but was kept, the reader adds a warning to its notes. It skips lines that aren't numbers before and after the grid, and raises a clear error on uneven rows or values that aren't numbers inside the grid.
  - **Analysis.** The single public entry point: take a frame (2D array) and options, return a Report. Options: horizontal and vertical bin factors (default 1×1), stripe false-alarm rate (default 0.01), defect false-alarm rate (default about 1 per 20 frames), clip level (detected automatically by default, can be overridden). Internally, in order: spike rejection, clipped-pixel exclusion, envelope estimation, local stripe estimation (local period, angle, phase, modulation depth, coherence), region segmentation, and phase-break and fork finding from the local phase. None of these internal steps is part of the public interface.
  - **Report.** A structured result: `striped` (bool), `score` (float), `threshold` (float), `regions` (list of: mask or region label, period in px, angle from vertical in degrees, modulation depth, bounding box), `phase_breaks` (list of: region, line as (row, col) points in frame px, jump in radians), `forks` (list of: point, direction ±1), `spike_pixels` (int), `clipped_pixels` (int), `reader_notes` (when the frame came from a file). It converts to JSON, and can produce the full-frame mask as an array.
  - **Synthetic generator.** Builds frames from the forward model below. Every part is configurable and seeded, and it returns the frame together with its ground truth. It also writes frames to CSV.
  - **CLI.** A thin wrapper: reads a frame, runs the analysis, writes the JSON report and the mask CSV, and optionally the diagnostic PNG. It contains no analysis logic.
- **Detection principle (ADR 0001)**: stripes are told apart from mottle by local periodicity (several consecutive cycles at a consistent period and phase) and by near-vertical orientation, not by size. Mottle overlaps stripes in size, so no frequency band contains only stripes. The detector must estimate *local phase*; break and fork detection are built on that same local phase.
- **Search range**: period 3–20 px, angle within about ±10° of vertical. A region counts only if it is at least 3 periods wide and 2 periods tall. Within a region the period is roughly constant (about ±20%), but different regions may have different periods.
- **Stripes multiply** the envelope: a stripe-free frame would be envelope × 1, so modulation depth is measured relative to the local envelope, not as an absolute amplitude.
- **Calibration**: the stripe score threshold and the defect thresholds are calibrated empirically on generated frames: stripe-free frames for the stripe score, and striped frames without defects for breaks and forks. Typical settings are "scorched" mottle and about 100 photons at the peak. Thresholds are stored with the package, and can be recalibrated later on real frames. Calibration and evaluation always use **separate seeds**: thresholds are set on calibration seeds and the rates are checked on held-out seeds, so the measured false-alarm rate is not understated.
  Real-frame recalibration of the Phase Break and Fork thresholds is deferred (ticket 11, ADR 0003): only the stripe threshold can be recalibrated on real frames for now.
- **Feasibility gate**: before regions, phase breaks or forks are built, the basic detector must show at least 90% detection of m = 0.2 at 1% false alarms (scorched mottle, ~100 photons at the peak, held-out seeds), and must analyse a 1600×400 frame in 10 s or less. If not, work stops for a human decision.
- **Pixel geometry**: all periods, angles, region-size minimums and positions in the report are in **sensor pixels** (unbinned, square). Bin factors (default 1×1) change the *detection* as well as the reporting: the search range (period 3–20 px, angle ±10° from vertical) and the 3×2-period region minimum are converted into binned-array coordinates before searching. For example, a physical 10° tilt under 1×2 binning appears at about 19.4° in the array. Any part of the period range that falls below 2 array pixels after binning cannot be resolved; it is reported as a warning, not silently skipped.
- **Forward model** (from the throwaway prototype; this encodes the agreed model more precisely than prose):

  ```
  envelope = profile(elliptical, rotated, mildly asymmetric Gaussian) * mottle
  mottle   = exp(strength * g)            # log-normal, keeps it positive
    scorched:   g = norm(tanh(2.5 * grf(beta=3.0)) + 0.4 * grf(beta=1.5)), strength ~0.4
    multiscale: g = grf(beta=2.2), strength ~0.35
    (grf = isotropic Gaussian random field, power ~ k^-beta, unit std)
  phase    = 2π/period * (x cos t + y sin t)        # t = tilt from vertical
           + jump * [pixel lies beyond break line]  # phase break
           + charge * atan2(y - y0, x - x0)          # fork, charge ±1
  clean    = envelope * (1 + m * region_mask * cos(phase))  # soft-edged region mask
  EMCCD:   n ~ Poisson(clean/max * photons_peak + cic)
           out = Gamma(shape=n, scale=em_gain) if em_gain > 1 else n
           out += Normal(0, read_e); add short bright streaks for spikes
           report out / em_gain   (~photon units)
  typical: photons_peak ~100, em_gain 300, read_e 50, cic 0.005
  ```

## Testing Decisions

- **What makes a good test**: it exercises only external behaviour through a public seam, and compares outputs with known truth. It never checks internals such as filter choices, intermediate maps, or the order of steps. Tests are written test-first.
- **Seam 1, the analysis entry point (main seam; almost all tests live here).** Tests generate frames with the synthetic generator and compare the Report with the ground truth:
  - Verdict: stripe-free frames → not striped. Striped frames with m ≥ 0.2 at typical noise → striped.
  - Measurements within tolerances: period, angle, modulation depth, mask overlap with the true region, break position and jump, fork position and direction.
  - Statistical calibration checks over seeded batches: the false-alarm rate on stripe-free frames is about 1% (within binomial tolerance); detection of m = 0.2 at typical noise is reliable; fake defects on defect-free striped frames stay at or below about 1 per 20 frames.
  - Robustness: spikes don't cause fake forks and are counted; clipped pixels are counted and don't distort modulation depth; multiscale mottle is still handled; noise across the range of about 5000 to about 30 photons at the peak.
  - Edge cases: a region just below the 3×2-period minimum is not reported; periods at 3 px and 20 px; tilts at ±10°; two regions with different periods; a break running at an unusual angle; correct periods and angles under unequal binning.
  - Performance: a 1600×400 frame analyses within the time budget (marked so it can be skipped on slow CI).
- **Seam 2, frame reading.** Small handwritten CSV files: plain grid; grid with a Solis axis column (dropped only when requested); a real intensity column that counts up (kept, with a warning); grid with metadata lines before and after; negative values; uneven rows → error; value that isn't a number inside the grid → error. Reader notes are checked.
- **Seam 3, CLI end to end.** A few smoke tests write a generated frame to CSV, run the CLI, and check that the JSON report, mask CSV and (when asked) PNG exist, have the right shapes, and agree with each other.
- **Generator (test oracle).** Only light self-consistency tests: same seed → same frame; m = 0 → no stripe peak in the spectrum; the true period and angle match the spectral peak of a clean, noise-free striped frame.
- **Prior art**: none, the repo is empty. The throwaway prototype (forward model above) is the reference for generator behaviour.

## Out of Scope

- Removing or suppressing stripes, or any other change to the frame.
- Combining several frames in a sequence (averaging, tracking over time) and time-based periodicity such as flicker.
- Fetching frames from the camera or controlling it. The tool reads saved files only.
- File formats other than CSV.
- Spectroscopic frames where one axis is wavelength.
- Stripes far from vertical (beyond about ±10°), crossing stripe sets, or periods outside 3–20 px.
- Calibration on real frames. The code must allow it, but it happens later when labelled real frames exist.
- GUI (phase 2).

## Further Notes

- The measurement tolerances are not fixed by the user yet. Start from these and adjust if they turn out unrealistic at typical noise: period ±5%, angle ±1°, modulation depth ±0.1, mask overlap (intersection over union) ≥ 0.8, break and fork positions within one period, break jump ±π/4.
- Stripe-size mottle (especially multiscale) is the hardest case. Short runs of 1–2 stripes cannot, by design, be told apart from mottle (ADR 0001).
- ADR 0001 must be revisited if real mottle turns out to have a preferred direction (vertical streaks).
- Sensor facts (Newton 971: 1600×400, square pixels) come from memory and have not been checked against Andor documentation.
- The repo is named "denoisifier", but this feature finds stripes; it does not remove noise.
