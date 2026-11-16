# 01 plan: first end-to-end version

Ticket: `.scratch/stripe-detector/issues/01-first-end-to-end-version.md`. Base: `ca0a0ee`.
Context read: `spec.md`, `GLOSSARY.md`, ADR 0001, `CLAUDE.md`, tickets 02/04/05/07 (to avoid painting later tickets into a corner).

Revision 2: folds `01-plan-review.md` (B1, B2, N1–N8) and `01-prototype-score.md` (P1) per the dispositions in `01-orchestrator.md`. The user ruled O1–O4 and Q1–Q6 as originally recommended; they are now decisions (§12).

Goal: a thin vertical slice that proves the path **generator → CSV → reader → `analyse` → Report → JSON → CLI**. The detection method is deliberately simple and global; ticket 02 replaces it with local periodicity (ADR 0001). Nothing here should be tuned for mottle or EMCCD noise.

## 1. Project setup

- `uv init --lib` style project at repo root: `pyproject.toml`, `src/denoisifier/`, `tests/`.
- `requires-python = ">=3.11"`. Runtime deps: `numpy`, `scipy` (for `scipy.ndimage.gaussian_filter`). Dev group: `pytest`. No matplotlib yet (ticket 12).
- Build backend: whatever `uv init --lib` emits (`uv_build` or `hatchling`); don't fight it.
- Keep the `README.md` and `.python-version` that `uv init --lib` writes (N6). Set `.python-version` to `3.11` so the suite runs on the declared floor (system Python is 3.14; uv fetches a managed 3.11). If uv cannot fetch 3.11 offline, pin the installed version instead and note that in the handoff. Keep the README to a few lines: what the tool does and the CLI usage line from §8.
- `[project.scripts] denoisifier = "denoisifier.cli:main"`; also `src/denoisifier/__main__.py` calling `cli.main()` so `python -m denoisifier` works.
- `[tool.pytest.ini_options] testpaths = ["tests"]`. No custom markers (the `slow` marker belongs to ticket 07; N7).
- Commit `uv.lock`. Add a `.gitignore` (`.venv/`, `__pycache__/`, `.pytest_cache/`).

## 2. Module layout and seams

```
src/denoisifier/
  __init__.py     # public surface: analyse, Report, read_frame, FrameFile
  __main__.py     # -> cli.main()
  analysis.py     # analyse(frame) -> Report         (seam 1, main seam)
  report.py       # Report dataclass + to_dict/to_json
  frame_io.py     # read_frame(path) -> FrameFile    (seam 2)
  cli.py          # main(argv) -> int                (seam 3, thin)
  synthetic.py    # generator: test oracle, also used by ticket 07 calibration
tests/
  test_analyse.py
  test_read_frame.py
  test_cli.py
  test_synthetic.py
```

Public interface (exported from `denoisifier`): `analyse`, `Report`, `read_frame`, `FrameFile`. The generator lives at `denoisifier.synthetic` and is imported from there (developer tool, not part of the experimenter-facing surface). Everything inside `analysis.py` other than `analyse` is private (`_`-prefixed); tests never import it.

Seams under test (the only three, as the ticket and spec Testing Decisions require):

| Seam | Catches | Misses |
|---|---|---|
| `analyse(frame) -> Report` | verdict and measurements vs ground truth | file parsing, JSON, argv handling |
| `read_frame(path) -> FrameFile` | CSV parsing, shape, value fidelity | anything about stripes |
| CLI (`python -m denoisifier ...` as a subprocess) | wiring, entry point, JSON on disk/stdout, exit codes | measurement accuracy (owned by seam 1) |

The generator gets only light self-consistency tests (it is the oracle, not a seam under test).

## 3. Conventions (settle once, use everywhere)

- Frame: 2D `float64` NumPy array, shape `(rows, cols)`. `y` = row index (increasing downward), `x` = column index.
- Angle: degrees from vertical, `t` in the spec's forward model `phase = 2π/period · (x cos t + y sin t)`. So for `t > 0` the stripe crests satisfy `x cos t + y sin t = const`, i.e. moving down the frame a crest shifts left; equivalently, with row 0 drawn at the top, the top of a stripe leans right. Report angle uses exactly the generator's `t` so tests compare directly, no sign flips. Write this convention in the docstrings of `generate` and `Report.angle_deg` (O1, ruled as planned).
- **GLOSSARY.md (part of this ticket, O1):** add an **Angle** entry under "Stripe structure": "The tilt of the stripes from vertical, in degrees. Row 0 of the frame is the top. Positive means the top of each stripe leans right (moving down the frame, a stripe shifts left). _Avoid_: orientation, rotation, tilt angle." Also add **Period** ("The spacing between neighbouring stripes, in sensor pixels, measured across the stripes. _Avoid_: wavelength, pitch, spacing.") since the Report names both. Owner should still check the sign against one real Solis view; if the viewer draws row 0 at the bottom, the sign flips in one place (generator) plus this entry.
- Period in pixels (sensor pixels; bin factors arrive in ticket 08).
- Glossary terms only: frame, profile, envelope, stripes, modulation depth, noise. Never "signal", "image", "beam", "contrast".

## 4. Generator (`denoisifier.synthetic`)

```python
@dataclass(frozen=True)
class GroundTruth:
    period: float           # px
    angle_deg: float        # from vertical, convention above
    modulation_depth: float

@dataclass(frozen=True)
class Synthetic:
    frame: np.ndarray
    truth: GroundTruth

def generate(
    *,
    seed: int,
    shape: tuple[int, int] = (256, 256),
    period: float = 8.0,
    angle_deg: float = 0.0,
    modulation_depth: float = 0.6,
    noise: float = 0.01,          # additive Gaussian std as a fraction of profile peak
    peak: float = 1000.0,         # profile peak intensity
) -> Synthetic: ...

def write_frame_csv(frame: np.ndarray, path: str | os.PathLike) -> None: ...
```

- RNG: `np.random.default_rng(seed)`; every random draw comes from it. Same seed + same arguments → bit-identical frame.
- Profile: elliptical, rotated, mildly asymmetric Gaussian centred near the frame centre. Use the seed to draw small variations (centre offset a few px, rotation in about ±30°, sigmas around 0.30/0.22 of the frame's width/height, asymmetry by using a ~15% larger sigma on one side of the major axis). Sized so the profile is still clearly above zero across most of the frame (stripes must be "full-frame" and visible).
- Stripes: `clean = profile * (1 + m * cos(phase))`, `phase` from the spec formula with a seeded random phase offset. No region mask (full frame), no breaks, no forks, no mottle; those are later tickets. Keep the formula structure from the spec so ticket 02 adds `* mottle` and swaps the noise stage without reshaping.
- Noise: `frame = clean + Normal(0, noise * peak)`. Negative values allowed.
- `modulation_depth=0` gives a profile-only frame (the "not striped" case).
- `write_frame_csv`: `np.savetxt(path, frame, delimiter=",", fmt="%.9g")`. No header, rows = frame rows.
- Validate arguments lightly (`period > 0`, `0 <= m <= 1`, 2D shape); raise `ValueError`.

## 5. Frame reader (`frame_io.py`)

```python
@dataclass(frozen=True)
class FrameFile:
    frame: np.ndarray            # 2D float64
    notes: tuple[str, ...] = ()  # reader notes; always empty in ticket 01

def read_frame(path: str | os.PathLike) -> FrameFile: ...
```

- Returns a `FrameFile` rather than a bare array now, so ticket 04 can add notes (axis column, metadata skipped, warnings) and a `drop_axis_column=False` keyword without changing callers. This is the spec's "array plus reader notes".
- Implementation for 01: `np.loadtxt(path, delimiter=",", dtype=float, ndmin=2)`. Plain grid, no header, every column kept. Errors from malformed files may propagate as `ValueError` for now (clear errors with row/position are ticket 04).

## 6. `analyse` and Report

```python
def analyse(frame: np.ndarray) -> Report: ...
```

- Keyword-only options are added in later tickets (`bin_factors`, `false_alarm_rate`, ...). Ticket 01 takes none. Do not add speculative options.
- Input: anything `np.asarray(frame, dtype=float)` makes 2D. Raise `ValueError` (clear message) if:
  - not 2D;
  - fewer than `MIN_SIDE = 40` pixels on either side (2 × max period; N8; the σ = 10 envelope filter needs at least that);
  - any non-finite value (NaN handling for clipped pixels is ticket 06);
  - the envelope estimate has no positive light: `env.max() <= 0` (all-zero, constant negative, dark-subtracted all-negative frames; B2);
  - the analysis weight is empty: `sum(w) <= 0` after masking (B2; could not be triggered in the prototype, but it would make the score 0/0).
- Never returns NaN or infinity in any Report field (B2). Constant positive frames (e.g. all 1.0) are valid input: score 0.0, not striped.
- Does not mutate the input (spec: "it only measures").

```python
@dataclass(frozen=True)
class Report:
    striped: bool
    score: float
    threshold: float
    period_px: float | None     # None when not striped
    angle_deg: float | None     # None when not striped; degrees from vertical
    def to_dict(self) -> dict: ...
    def to_json(self, indent: int | None = 2) -> str: ...
```

- `threshold` is included now (spec Report field; ticket 07 requires it and the CLI user needs it to read `score`). It is a provisional module constant in ticket 01.
- Field names carry their units. Ticket 05 introduces `regions`; at that point `period_px`/`angle_deg` move into per-region entries. Accept that schema change then rather than inventing regions now.
- `to_dict` returns plain Python types only (`bool`, `float`, `None`), no NumPy scalars, so `json.dumps` works. `to_json` = `json.dumps(self.to_dict(), indent=indent, allow_nan=False)`; `allow_nan=False` is a backstop so a NaN can never become invalid JSON (B2). Key order: `striped, score, threshold, period_px, angle_deg`.

## 7. Simple detection method (ticket 01 only)

Global, spectral, multiplicative. Private helpers inside `analysis.py`; none are tested directly.

1. **Envelope estimate**: `env = gaussian_filter(frame, sigma=10)`. A Gaussian with σ = 10 px attenuates period-20 stripes to under 1% and shorter periods far more, so `env` is the profile without stripes.
   Guard: if `env.max() <= 0`, raise `ValueError("envelope max <= 0: frame has no positive light")`.
2. **Relative modulation**: `mask = env > 0.1 · env.max()`; `rel = frame / env - 1` on `mask`, else 0. Stripes multiply the envelope, so this flattens the profile and leaves `m · cos(phase)` + noise/env.
3. **Weighting**: `w = clip(env / env.max(), 0, 1) · mask · hann2d` (downweights the noisy dim edges; Hann suppresses edge leakage). Multiplying by `mask` means `sum(w)` normalises over analysed pixels only; the spectrum is unchanged because `rel` is already 0 off the mask. Guard: if `sum(w) <= 0`, raise `ValueError`. Subtract the **weighted** mean of `rel` (`sum(rel·w)/sum(w)`), then form `rel·w`. Comment in code: a plain mean leaves a residual shaped like `w` that leaks into the band (the prototype measured profile-only scores rising from ~15 to ~1500 at noise 0.001 with a plain mean).
4. **Spectrum**: `P = |FFT2(rel·w, zero-padded to 4× each axis)|²`.
5. **Search band**: frequency vectors with period in [3, 20] px and angle within ±10° of vertical, i.e. `f = (fx, fy)` with `fx > 0`, `1/20 ≤ |f| ≤ 1/3`, `|atan2(fy, fx)| ≤ 10°` (plus a small margin, e.g. ±12°, so a 10° truth is not on the edge). Only the `fx > 0` half-plane, to remove the Hermitian duplicate.
6. **Peak**: argmax of `P` in the band, with `fx` along axis 1 (columns) and `fy` along axis 0 (rows). `period = 1/|f|`, `angle_deg = degrees(atan2(fy, fx))`. The prototype met ±5% / ±1° on all 35 cases (periods 3–20, angles ±10°, noise 0–0.1) from the 4×-padded argmax alone, so sub-bin refinement is optional; add a 3-point parabolic fit only if a test needs it.
7. **Score (floored ratio, B1/P1)**:
   ```
   A0        = 1e-3                          # named constant, modulation-depth units
   amp_floor = (A0 * sum(w) / 2) ** 2         # peak power a modulation of depth A0 would give
   score     = P_peak / max(median(P in band), amp_floor)
   ```
   (`2·sqrt(P_peak)/sum(w)` estimates the modulation depth at the peak; the floor is that estimate's power at depth A0.) When noise dominates, the median exceeds the floor and the score is the plain peak-to-median ratio. On noise-free frames the floor takes over, so deterministic leakage at the band edge (the review's B1: plain ratio up to 1.7e5 for a noise-free profile-only frame) scores about 1e-4, while real stripes score about (m/A0)². The floor also keeps the denominator positive on constant frames (no NaN). Comment next to the constants, with the prototype's measured ranges: profile-only 9–17 (noise ≥ 0.1), 0.2–0.4 (noise 0.01), ~0.003 (noise 0.001), ~1e-4 (noise 0); m = 0.2: 1.6e4–4.1e4; m = 0.6: 1.4e5–3.7e5 (N1).
8. **Verdict**: `striped = score > THRESHOLD` with `THRESHOLD = 500`. One condition only, so the verdict is decided by the score. Chosen by the prototyper on calibration seeds **outside the test seeds** (profile-only seeds 100–199, striped seeds 100–134; N2): log-midpoint between the highest profile-only score (16.9) and the lowest m = 0.2 score (1.6e4), about 30× margin each side. Tests use seeds 0–9 and 0–34 only. Provisional; ticket 07 replaces it with a calibrated value.

Why this is acceptable now and not later: ADR 0001 says a global FFT peak would be fooled by mottle. Ticket 01 has no mottle, and ticket 02 explicitly switches to local periodicity. Put a one-line comment at the top of `analyse`'s implementation pointing at ADR 0001 and ticket 02 so nobody mistakes this for the real method.

## 8. CLI (`cli.py`)

```
denoisifier FRAME.csv [-o REPORT.json]
python -m denoisifier FRAME.csv [-o REPORT.json]
```

- `main(argv: list[str] | None = None) -> int`, built with `argparse`.
- Reads with `read_frame`, calls `analyse(frame_file.frame)`, writes `report.to_json()` to `-o` path, or to stdout if `-o` is absent. Trailing newline.
- Errors: catch `OSError` (reading the frame **and** writing `-o`, e.g. missing directory or permission) and `ValueError` (unparsable CSV, `analyse` rejecting the frame, including non-positive frames from B2). One-line message on stderr, no traceback, exit code 1. Usage errors: argparse's exit code 2 (O4, ruled as planned).
- The CLI never writes invalid JSON: it serialises with `Report.to_json()` (`allow_nan=False`), and builds the full string before opening the output file. The `-o` write itself is not atomic (a crash mid-write can leave a partial file); acceptable for 01 (N4).
- No analysis logic in the CLI. Mask CSV (`--mask`), PNG (`--png`), `--drop-axis-column`, bin factors come in tickets 05, 12, 04, 08. Reader notes go into the JSON in ticket 04.

## 9. Test plan (test-first, vertical slices)

Suggested TDD order (one red → green cycle each):

1. `test_synthetic`: same seed → identical frame. (Forces project setup + `uv run pytest` working.)
2. `test_read_frame`: handwritten 2×3 grid → shape `(2, 3)` and exact values.
3. `test_synthetic` + reader: `write_frame_csv` → `read_frame` round-trips a generated frame (`allclose`, rtol 1e-8).
4. `test_analyse`: one striped frame → `striped is True`, period and angle within tolerance. Start with `THRESHOLD = 500` and `A0 = 1e-3` as constants from this step (N3; values from the prototype).
5. `test_analyse`: parametrise over the period/angle/noise table below.
6. `test_analyse`: profile-only frames at noise 0, 0.001, 0.01 → not striped (this is the cycle that drives the floored score).
7. `test_analyse`: degenerate frames (constant, non-positive, too small).
8. `test_analyse`: report converts to JSON.
9. `test_cli`: end to end, including error exits and the console script.

### Concrete tests

`tests/test_synthetic.py` (oracle self-consistency, light)
- `test_same_seed_gives_same_frame`: `generate(seed=3)` twice → `np.array_equal`; `seed=4` differs.
- `test_returns_frame_and_ground_truth`: truth fields equal the arguments passed (period, angle_deg, modulation_depth); frame shape equals `shape`.
- `test_written_csv_reads_back_as_the_same_frame`: `write_frame_csv` to `tmp_path`, `read_frame` → `allclose`. Also confirms the file is a plain comma grid (first line has `cols - 1` commas, no header).

`tests/test_read_frame.py` (seam 2)
- `test_plain_grid_gives_2d_array_of_right_shape`: write `"1.5,2,3\n-4,5e2,6\n"` → shape `(2, 3)`, values `[[1.5, 2, 3], [-4, 500, 6]]` (negatives accepted, spec story 28), `notes == ()`.
- `test_single_row_is_still_2d`: `"1,2,3\n"` → shape `(1, 3)`.
- `test_every_column_is_kept_even_when_first_counts_up`: `"0,5,5\n1,5,5\n2,5,5\n"` → shape `(3, 3)`, first column intact. (Cheap guard for the spec's "never guess"; ticket 04 adds the warning.)

`tests/test_analyse.py` (seam 1)
- `test_clear_full_frame_stripes_are_found_and_measured`, parametrised over `(seed, period, angle_deg)`: `(0, 5, 0)`, `(1, 8, 6)`, `(2, 12, -8)`, `(3, 18, 3)`, `(4, 4, -4)`, `(5, 3, 10)`, `(6, 20, -10)`, crossed with `noise ∈ {0, 0.01}`; `m = 0.6`, shape `(256, 256)`. Assert `report.striped`, `abs(period_px - truth.period) <= 0.05 * truth.period`, `abs(angle_deg - truth.angle_deg) <= 1.0`. Tolerances from spec Further Notes; expected values come from the generator's ground truth, not from re-running the detector's maths. (The 3 px / 20 px / ±10° rows are cheap here because the prototype already met them; they do not replace ticket 02's edge tests under mottle.)
- `test_profile_only_frame_is_not_striped`, parametrised over seeds 0–9 × `noise ∈ {0, 0.001, 0.01}`, `modulation_depth=0`: `not report.striped`, `period_px is None`, `angle_deg is None`. Noise 0 is the case the review showed the plain ratio failing (B1).
- `test_report_has_score_and_threshold`: striped frame score > threshold; profile-only frame score < threshold (guards against the verdict being decided by something other than the score). Still valid: the floored ratio is a single score.
- `test_constant_frame_is_not_striped_and_has_finite_score` (B2): `np.ones((64, 64))` → `striped is False`, `score == 0.0`, `json.loads(report.to_json())` succeeds.
- `test_frame_with_no_positive_light_is_rejected` (B2), parametrised over all-zero and constant −5 frames (64×64): `ValueError`.
- `test_rejects_frame_smaller_than_min_side` (N8): `(39, 64)` → `ValueError`; `(40, 64)` profile-only generated frame → returns a Report.
- `test_report_converts_to_json`: `json.loads(report.to_json())` has keys `striped, score, threshold, period_px, angle_deg` with JSON types bool/number/number/number-or-null; values equal the Report's.
- `test_input_frame_is_not_modified`: copy before, `array_equal` after.
- `test_rejects_non_2d_input`: 1D array → `ValueError`.

`tests/test_cli.py` (seam 3, subprocess via `[sys.executable, "-m", "denoisifier", ...]`)
- `test_cli_writes_json_report_for_striped_csv`: generate striped frame (seed 1), `write_frame_csv`, run CLI with `-o report.json`; exit 0; JSON parses; `striped is True`; `period_px`/`angle_deg` within tolerance of truth.
- `test_cli_prints_json_to_stdout_without_output_flag`: profile-only frame; stdout parses as JSON with `striped is False`.
- `test_cli_fails_cleanly_on_missing_file`: exit 1, message on stderr, no traceback (`"Traceback" not in stderr`).
- `test_cli_fails_cleanly_on_frame_with_no_positive_light` (B2): all-zero 64×64 CSV with `-o report.json` → exit 1, stderr message, no traceback, `report.json` not created.
- `test_cli_fails_cleanly_when_output_dir_missing` (N4): `-o tmp_path/"nope"/"r.json"` → exit 1, stderr message, no traceback.
- `test_console_script_is_installed` (N5): `shutil.which("denoisifier")` is not None (the suite runs under `uv run`, which puts the venv's `bin` on PATH), and running it with `--help` exits 0. This covers the command the experimenter actually types.

## 10. Acceptance criteria → proving tests

| AC | Proven by | Seam |
|---|---|---|
| Project installs, `uv run pytest` runs | whole suite passes from a fresh clone: `uv sync && uv run pytest` (implementer runs it and records output in the handoff) | — |
| Generator seeded; returns frame + truth; writes plain CSV | `test_same_seed_gives_same_frame`, `test_returns_frame_and_ground_truth`, `test_written_csv_reads_back_as_the_same_frame` | generator (oracle) |
| Plain comma grid, no header → 2D array of right shape | `test_plain_grid_gives_2d_array_of_right_shape`, `test_single_row_is_still_2d`, `test_every_column_is_kept_even_when_first_counts_up` | `read_frame` |
| `analyse` returns Report with `striped`, `score`, one global period (px) and angle (deg from vertical) | `test_clear_full_frame_stripes_are_found_and_measured`, `test_report_has_score_and_threshold` | `analyse` |
| Clear full-frame stripes (m ≈ 0.6, low noise) → striped, period/angle within tolerance; profile-only → not striped | `test_clear_full_frame_stripes_are_found_and_measured` (7 cases × noise {0, 0.01}, incl. ± tilts), `test_profile_only_frame_is_not_striped` (10 seeds × noise {0, 0.001, 0.01}) | `analyse` |
| Report → JSON; CLI reads CSV, writes JSON | `test_report_converts_to_json`, `test_constant_frame_is_not_striped_and_has_finite_score`; `test_cli_writes_json_report_for_striped_csv`, `test_cli_prints_json_to_stdout_without_output_flag`, `test_console_script_is_installed`, plus the two CLI error-exit tests | `analyse`/Report, CLI |
| Tests at all three seams | the three files `test_analyse.py`, `test_read_frame.py`, `test_cli.py` exist and pass | all |

Also in scope (not an AC, ruled by the owner under O1): the **Angle** and **Period** entries in `GLOSSARY.md` (§3). Checked in review, not by a test.

## 11. Out of scope for 01 (do not build)

Mottle, EMCCD noise, spikes, clipping, regions/mask, phase breaks, forks, modulation depth in the Report, bin factors, calibration, Solis handling, reader notes content, PNG, speed budget. Leave no stubs or placeholder options for them.

## 12. Decisions (formerly open questions; ruled as recommended)

1. Package name `denoisifier`.
2. Period/angle are `None` (JSON `null`) when not striped.
3. `period_px`/`angle_deg` at the top level of the Report now; ticket 05 moves them into regions (O2).
4. `read_frame` returns `FrameFile(frame, notes)` now (O3).
5. `threshold` is in the Report now (O2).
6. CLI writes JSON to stdout unless `-o`; exit 1 on errors, 2 on usage (O4).
7. Angle sign as §3, documented in `GLOSSARY.md` (O1).
8. Score is the floored ratio, `A0 = 1e-3`, `THRESHOLD = 500` (B1/P1).
9. Non-positive envelope and empty weight raise `ValueError`; no NaN reaches the Report or JSON (B2).

Still open: only the owner's check of the angle sign against one real Solis view (O1); it does not block implementation.
