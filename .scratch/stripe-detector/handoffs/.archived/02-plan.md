# 02 plan: stripes told apart from mottle in EMCCD noise

Ticket: `.scratch/stripe-detector/issues/02-stripes-vs-mottle-in-emccd-noise.md`. Base: `1d07977`.
Context read: `spec.md` (forward model, tolerances, testing decisions), ADR 0001, `GLOSSARY.md`, `docs/agents/domain.md`, ticket 01 plan/review/prototype, ticket 01 code and tests, tickets 03, 05, 06, 07, 09 (so this ticket does not paint them into a corner).

Goal: replace ticket 01's global FFT peak with **local periodicity plus near-vertical orientation** (ADR 0001), and give the generator realistic mottle and the EMCCD chain, so that at ~100 photons at the peak with scorched mottle, stripe-free frames come out Not Striped and m ≥ 0.5 comes out Striped and measured (period, angle, modulation depth).

The method below was checked with a throwaway prototype before writing the plan (§9). Numbers quoted are from it, on **calibration seeds 100–199**; tests use seeds 0–19 only.

Revision 2: folds `02-plan-review.md` B1, B2, N1, N2, N3, N5 and the owner's answers to O1–O4 (§11, now settled). N4 (prototype draw order differs; §4.4 already says re-measure) and N6 (unclamped period/angle; belongs to 05) are left as they are.

## 1. Scope

In: generator mottle (scorched, multiscale) and EMCCD chain; local stripe estimation (period, angle, phase, modulation depth, local stripe-vs-reference ratio); new score and verdict; `modulation_depth` in the Report; provisional threshold.

Out (do not build, no stubs): spikes and clipping (06; the spec's forward model mentions spikes, but 06 owns them), regions/mask/bounding boxes (05), calibrated threshold and the false-alarm option (07), the m = 0.2 gate and the 1600×400 timing (03), bin factors (08), phase breaks and forks (09, 10), CLI changes beyond what the Report change brings for free.

## 2. Module layout and seams

```
src/denoisifier/
  synthetic.py        # + mottle, + Emccd chain, + Synthetic.clean   (generator / test oracle)
  _local_stripes.py   # NEW, private: oriented Gabor bank -> LocalStripes maps
  analysis.py         # analyse(): validation, light mask, score, verdict, measurement
  report.py           # + modulation_depth
tests/
  test_synthetic.py   # + mottle, EMCCD, spectral self-consistency
  test_analyse.py     # + mottle/EMCCD batches, edges, bright/dim depth
  spectrum.py         # NEW test helper: band peak of a frame's spectrum (generator oracle checks only)
  truth_match.py      # + DEPTH_TOL = 0.1, assert_depth_matches
```

Seams under test are unchanged from ticket 01: **`analyse(frame) -> Report`** (main seam, every detector AC), **`generate(...)`** (oracle self-consistency only), CLI (existing smoke tests keep passing; one assertion added). `_local_stripes` is private: tests never import it. It is a separate module because tickets 05, 09 and 10 build regions, breaks and forks on its maps; keeping it behind one function (`estimate_local_stripes`) keeps the filter bank out of `analysis.py` and lets 05+ read maps without reaching into `analyse`.

| Seam | Catches | Misses |
|---|---|---|
| `analyse` | verdict vs truth over seeded batches; period/angle/depth vs truth; envelope-relative depth (crops) | internal map quality away from the measured area |
| `generate` | mottle strength, EMCCD statistics, peak photon count, spectral peak = truth | whether mottle "looks" real (no real frames yet) |
| CLI | JSON carries the new field | measurement accuracy (owned by `analyse`) |

## 3. Generator (`denoisifier.synthetic`)

### 3.1 Interface

```python
MottleKind = Literal["none", "scorched", "multiscale"]

@dataclass(frozen=True)
class Emccd:
    """EMCCD noise chain. Output is in ~photon units (divided by em_gain)."""
    photons_peak: float = 100.0   # photons at the brightest clean pixel
    em_gain: float = 300.0        # 1.0 = EM gain off (no Gamma stage)
    read_noise_e: float = 50.0    # Gaussian read noise std, electrons
    cic: float = 0.005            # spurious charge (clock-induced), mean photons-equivalent per pixel

@dataclass(frozen=True)
class Synthetic:
    frame: np.ndarray
    truth: GroundTruth
    clean: np.ndarray             # NEW: the noise-free frame in the same units as `frame`

def generate(
    *,
    seed: int,
    shape=(256, 256),
    period=8.0,
    angle_deg=0.0,
    modulation_depth=0.6,
    mottle: MottleKind = "none",          # NEW
    mottle_strength: float | None = None, # NEW; None -> typical: scorched 0.4, multiscale 0.35
    noise: float | Emccd = 0.01,          # CHANGED: float = ticket 01's Gaussian fraction of `peak`; Emccd = EMCCD chain
    peak=1000.0,                          # profile peak; used by the Gaussian path only
) -> Synthetic
```

Decisions:
- **One noise knob** (`noise: float | Emccd`), not parallel kwargs: the two noise models are mutually exclusive, and a union type makes "both set" unrepresentable. Ticket 06 adds spikes as a field of `Emccd` or a sibling option; that is its call.
- **Defaults unchanged** (`mottle="none"`, Gaussian 0.01), so every ticket 01 test and frame is bit-identical. New tests pass `mottle="scorched", noise=Emccd()` explicitly. No `TYPICAL` constant is added to `synthetic.py`; `test_analyse.py` defines its own local `TYPICAL` (§7) (N5).
- `GroundTruth` is unchanged (period, angle, depth). Mottle kind/strength and noise settings are inputs the caller already holds.
- `Synthetic.clean` exists because the EMCCD tests need the noise-free frame to check noise statistics, and ticket 06's clipping/spike tests will need it too. It is the clean frame *after* the photon scaling (EMCCD) or `peak` scaling (Gaussian), so `frame - clean` is pure noise.
- Validation (`ValueError`): `mottle` not one of the three; `mottle_strength < 0`, or given with `mottle="none"`; `photons_peak <= 0`; `em_gain < 1`; `read_noise_e < 0`; `cic < 0`; float `noise < 0` (kept).

### 3.2 Forward model (spec, exactly)

```
grf(beta):   isotropic Gaussian random field, power ~ k^-beta (amplitude k^(-beta/2)),
             k = 0 term zeroed, real part, then (g - mean)/std  -> unit std
norm(a):     (a - mean)/std
scorched:    g = norm(tanh(2.5 * grf(3.0)) + 0.4 * grf(1.5));  strength default 0.4
multiscale:  g = grf(2.2);                                      strength default 0.35
mottle     = exp(strength * g)        (1.0 for "none")
clean      = profile * mottle * (1 + m * cos(phase))
Gaussian:    frame = peak*clean + Normal(0, noise*peak)          (ticket 01, unchanged)
EMCCD:       lam = clean / max(clean) * photons_peak + cic
             n   = Poisson(lam)
             out = Gamma(shape=n, scale=em_gain) where n > 0, else 0     if em_gain > 1
                   n                                                    if em_gain == 1
             out = (out + Normal(0, read_noise_e)) / em_gain
             clean_out = clean / max(clean) * photons_peak     (Synthetic.clean; cic excluded)
```

- `rng.gamma` rejects shape 0: draw with `np.maximum(n, 1)` then zero where `n == 0` (or index only `n > 0`).
- **RNG draw order is fixed: profile → stripe phase offset → mottle fields → noise.** Mottle is drawn only when requested, so `mottle="none"` frames stay bit-identical to ticket 01. Consequence used by tests: for a given seed and shape, profile and mottle do not depend on `period`, `angle_deg`, `modulation_depth` or `noise`.
- GRF is generated at the frame shape via `np.fft.fft2` of white noise (periodic; that is fine for a synthetic field).

## 4. Detection method (private; ADR 0001)

### 4.1 Pipeline inside `analyse`

1. Validation unchanged from ticket 01 (2D, `MIN_SIDE = 40`, finite, `env.max() > 0`).
2. Light mask unchanged: `env = gaussian_filter(frame, 10)`, `light = env > 0.1·env.max()`. (Only to keep the dark surround out; it no longer feeds the spectrum.)
3. `local = estimate_local_stripes(frame, light)` (§4.2).
4. `score = local.ratio.max()` (0 outside `light`). `striped = score > THRESHOLD`.
5. If striped, measure (§4.3). Otherwise period, angle, depth are `None`.

Delete ticket 01's global-spectrum code, `A0 = 1e-3`, `THRESHOLD = 500`, `_PAD`, `_MAX_ANGLE_DEG`, and the "Ticket 01 only" comment; replace with a one-line pointer to ADR 0001.

### 4.2 `_local_stripes.estimate_local_stripes(frame, light) -> LocalStripes`

```python
@dataclass(frozen=True)
class LocalStripes:
    """Per-pixel best match over the filter bank. All arrays have the frame's shape."""
    ratio: np.ndarray        # stripe-vs-reference energy ratio (0 outside light); the local Stripe Score
    period: np.ndarray       # bank period (px) with the best ratio at this pixel (0 outside light)
    angle_deg: np.ndarray    # bank Angle (deg) of the best near-vertical filter at that period (0 outside light)
    response: np.ndarray     # complex response at that period and angle; local phase = np.angle
    local_mean: np.ndarray   # same-window local mean at that period; local depth = 2|response|/local_mean
```

The docstring states (N3): `period` and `angle_deg` are the coarse bank grid (periods ×1.12 apart, angles 5° apart). Fine-grained period and Angle over an area come from the neighbour-product sum of `response` over that area (§4.3); ticket 05 applies the same sum per region and must not add a second estimator. `angle_deg` is also the fallback in §4.3.

Method (Fourier domain, one forward FFT of the frame, one inverse FFT per filter):
- Pad the frame by `PAD = 32` px with `mode="reflect"` before the FFT and crop after (`PAD < MIN_SIDE` so reflect padding is always valid).
- **Bank:** 18 periods geometric from 3 to 20 inclusive (`3·(20/3)**(i/17)`, ratio ≈ 1.12). For each period `p`, **stripe filters** at angles −10, −5, 0, 5, 10° and **reference filters** at the same five angles + 90° (near-horizontal).
- **Filter:** complex Gabor, Gaussian in the Fourier domain centred at `f0 = (cos θ, sin θ)/p` (x = column axis, y = row axis, θ = Angle per the glossary sign), with spatial window σ = `1.0·p` across the stripes and `1.5·p` along them (σ_f = 1/(2πσ)), peak gain 1. The across-window spans about three cycles, so a response needs several consecutive cycles in phase: this is where "consistent period and phase" lives. The along-window makes it orientation-selective.
- **Local mean `L`:** the same Gaussian window centred at f = 0 (gain 1 at DC). Because stripes multiply the envelope, `2|G|/L` is the modulation depth relative to the local envelope, at the same scale, with no global envelope estimate.
- **Ratio at period `p`:** `Ev = max over stripe angles |G|²`, `Eh = max over reference angles |G|²`; box-average both over a window `2p` tall × `3p` wide (`uniform_filter`, min size 3); `ratio_p = box(Ev) / max(box(Eh), (A0·|box(L)|/2)²)`, set to 0 outside `light`. `A0 = 3e-3`.
  - The reference is the *same* bank rotated 90°. Mottle and noise are isotropic, so the reference measures their energy at that scale and location: the ratio is self-normalising across light level, EM gain and mottle strength. **This depends on mottle having no preferred direction, which is exactly ADR 0001's stated assumption**; directional real mottle would need ADR 0001 revisited (already a listed consequence).
  - The floor `(A0·L/2)²` is the energy of a depth-A0 modulation. It stops noise-free frames, where both energies are tiny, from scoring on deterministic leakage (ticket 01's B1, again). Comment the measured numbers next to the constant (§9).
- **Per-pixel best:** keep, per pixel, the period whose `ratio_p` is largest, with that period's stripe angle with the largest `|G|²` at that pixel (`angle_deg`), its `response`, and `local_mean`. Do not keep per-period stacks (memory on 1600×400).
- Divisions guarded so no warnings/NaN reach the maps (e.g. `period` is 0 where `ratio` is 0; use `np.errstate` or `where=`).

### 4.3 Measurement (in `analysis.py`)

When `score > THRESHOLD`:
- `peak = argmax(ratio)`, `p_star = local.period[peak]`, `a_star = local.angle_deg[peak]`.
- **Measured area** `A = (ratio > THRESHOLD) & (|ln(period/p_star)| ≤ ln 1.25)` (spec: period roughly constant within a region, ±20%). Evaluate the log only on pixels with `ratio > THRESHOLD` (where `period > 0`), e.g. `np.log(period, where=..., out=...)`, so no `divide by zero` warning is raised (N2; §4.2's "no warnings"). `A` always contains `peak`. Ticket 05 replaces this with real regions; keep it a private helper.
- **Period and angle from local phase:** `cx = Σ response[y, x+1]·conj(response[y, x])`, `cy = Σ response[y+1, x]·conj(response[y, x])`, summed over pixel pairs with both pixels in `A`. `fx = angle(cx)/2π`, `fy = angle(cy)/2π`; `period_px = 1/hypot(fx, fy)`, `angle_deg = degrees(atan2(fy, fx))`. Use the neighbour product, **not** `np.gradient` of the phase: central differences are biased at short periods (prototype gave 6.6 px for a 3 px truth).
- **Fallback for a small or degenerate area (B1).** On a borderline frame (score just above `THRESHOLD`) `A` can be the single-pixel cap of a smooth maximum, with no horizontal or vertical pairs, so `cx` or `cy` is 0 and `period_px` would be `inf` (then `gabor_at` is undefined and `Report.to_json` raises under `allow_nan=False`). Rule: if `A` has fewer than `MIN_PAIRS = 8` horizontal pairs **or** fewer than `MIN_PAIRS` vertical pairs, or `hypot(fx, fy) == 0`, use the bank values at the peak: `period_px = p_star`, `angle_deg = a_star`. The bank grid is coarser than the spec tolerance, which is acceptable for borderline frames; clear stripes (every AC test) have areas of hundreds of pixels and never take this path. Depth is measured the same way in both cases (next bullet; `A` is never empty). Result: `period_px` and `angle_deg` are always finite and `period_px` is in [3, 20] on the fallback path.
- **Modulation depth:** run one more Gabor + local mean tuned to the measured `(period_px, angle_deg)` (expose `gabor_at(frame, period, angle_deg) -> (response, local_mean)` from `_local_stripes`), then `modulation_depth = median(2|response|/local_mean over A)`. Re-tuning removes the bank's grid-mismatch loss (up to ~15% low otherwise). Guard `local_mean > 0` (inside `light` it is), so the depth is finite.
- All three are plain finite `float`s whenever `striped` is True.

### 4.4 Threshold and score

- `THRESHOLD = 150.0`, provisional (07 calibrates). The score is still "higher = more stripe-like, unbounded, not a probability", so the glossary entries hold unchanged.
- Chosen on calibration seeds as the log-midpoint between the highest stripe-free score (75.7, multiscale; scorched max 71.7) and the lowest m = 0.5 score (301 over both mottle kinds): √(75.7·301) ≈ 151. About 2× margin each side. The implementer re-measures these on seeds 100–199 with the real code before committing the constant (numbers will move slightly), and updates the comment; tests never run on those seeds.
- Ticket 03 (m = 0.2 gate) is the place to tune bank widths (`1.0p`/`1.5p`), smoothing window and the per-frame max: prototype m = 0.2 scores were 101–196, i.e. **below this threshold** for some cases. That is expected and not an AC here, but flag it in the handoff for 03.

## 5. Report

Add `modulation_depth: float | None` after `angle_deg` (`None` when not striped). JSON key order: `striped, score, threshold, period_px, angle_deg, modulation_depth`. Docstring: "Modulation Depth relative to the local envelope (GLOSSARY.md)". Like `period_px`/`angle_deg`, it moves into per-region entries in ticket 05 (same accepted break as ticket 01's O2).

## 6. Conventions

- Glossary terms only (Frame, Profile, Mottle, Envelope, Stripes, Modulation Depth, Noise, Period, Angle, Stripe Score, Threshold, Verdict). Not "signal", "contrast", "amplitude", "texture", "background". Internal names: `ratio` is fine; do not call `L` "background" (use `local_mean`).
- Angle sign: unchanged (glossary). The bank uses the same `(fx on columns, fy on rows, atan2(fy, fx))` convention as ticket 01, so no sign flip.
- Frame units: EMCCD frames are ~photons; `analyse` is scale-free (ratio and `2|G|/L` both cancel a global scale), so no unit option.

## 7. Test plan (test-first)

Shared constants in tests: `TYPICAL = dict(mottle="scorched", noise=Emccd())` defined locally in `test_analyse.py`; `SEEDS = range(20)`.
`tests/truth_match.py` gains `DEPTH_TOL = 0.1` and `assert_depth_matches(depth, truth)`; `assert_matches_truth` keeps period/angle.

Suggested TDD order:
1. Generator: mottle strength (drives `_grf`, `_mottle`, draw order).
2. Generator: EMCCD statistics and peak photon count (drives `Emccd`, `Synthetic.clean`).
3. Generator: spectral self-consistency (adds `tests/spectrum.py`).
4. `analyse`: one scorched/EMCCD m = 0.5 frame → striped, period/angle in tolerance (drives the bank and measurement; ticket 01 tests go red here and are brought back green in the same cycle).
5. `analyse`: stripe-free scorched batch → not striped (drives the reference filters and `THRESHOLD`).
6. `analyse`: Report gains `modulation_depth`; depth within tolerance.
7. `analyse`: bright/dim crops.
8. `analyse`: period/angle edges; multiscale batches.
9. `analyse`: borderline frames (drives the §4.3 fallback).
10. CLI: assert the new key.

### 7.1 `tests/test_synthetic.py` (oracle self-consistency)

- `test_mottle_has_the_requested_strength` — parametrise `(kind, strength, expected)`: `("scorched", None, 0.4)`, `("multiscale", None, 0.35)`, `("scorched", 0.2, 0.2)`. Gaussian path, `noise=0.0`, `modulation_depth=0`, seed 0: `s_m = generate(..., mottle=kind, mottle_strength=strength)`, `s_0 = generate(..., mottle="none")`; `np.std(np.log(s_m.frame / s_0.frame))` equals `expected` to 1e-9. (Mottle is the ratio exactly, by the draw order.)
- `test_mottle_none_is_unchanged_from_ticket_01` — `generate(seed=3)` equals `generate(seed=3, mottle="none")` (`array_equal`).
- `test_emccd_peak_photon_count` — `Emccd(photons_peak=250)`, scorched: `s.clean.max() == 250` (to 1e-9).
- `test_emccd_noise_statistics` — parametrise:
  - gain on (`em_gain=300, read_noise_e=0, cic=0`): `r = frame - clean`; `|mean(r)| ≤ 0.02·mean(clean)` and `var(r)/mean(clean)` in [1.9, 2.1] (excess noise factor² = 2).
  - gain off (`em_gain=1, read_noise_e=0, cic=0`): frame is integer-valued (`frame == round(frame)`), `var(r)/mean(clean)` in [0.95, 1.05].
  - read noise (`em_gain=1, read_noise_e=20, cic=0`): `var(r) - mean(clean)` within 5% of 400.
  - cic (`em_gain=1, read_noise_e=0, cic=0.5`, **`photons_peak=1`**): `mean(r)` within 5% of 0.5. At `photons_peak=1`, mean(clean) ≈ 0.38, so the standard error of `mean(r)` is √(0.88/65536) ≈ 0.0037 and the 0.025 tolerance is ≈ 7σ. (B2: at `photons_peak=100` it was ≈ 1σ and failed on 30% of seeds.)
  Use `shape=(256, 256)`, `mottle="none"`, `modulation_depth=0`, seed 0. The gain-on, gain-off and read-noise cases use the default `photons_peak=100`; with 65k pixels their tolerances are many σ wide (Poisson var-of-var at λ~30–100 is ~1%; the review saw 0/50 seed failures for gain on).
- `test_stripe_free_frame_has_no_stripe_peak` — `mottle ∈ {scorched, multiscale}`, seeds 0–9, `noise=0.0`, `modulation_depth=0`: `spectrum.band_peak(frame).vertical_to_horizontal < 10`. Prototype on seeds 0–9: 0.32–3.28 (striped m = 0.5 noise-free: 190–595).
- `test_clean_stripes_put_the_spectral_peak_at_the_true_period_and_angle` — `mottle="none"`, `noise=0.0`, `m=0.5`, `(period, angle)` ∈ {(3, 10), (20, −10), (7.3, 4)}: `band_peak(frame).period/.angle_deg` match truth via `assert_matches_truth`. (Use `mottle="none"`: the AC says "clean striped frame"; with scorched mottle the 20 px / −10° case drifted 1.09° at the band edge.)
- Existing seed and ground-truth tests stay.

`tests/spectrum.py` (test helper, ~25 lines, independent of `analysis.py`): `rel = frame/gaussian_filter(frame, 10) - 1`, Hann window, weighted-mean removal, 4× zero-padded `|FFT|²`; ring = periods 3–20; `vertical` = `fx > 0, |atan2(fy, fx)| ≤ 10°`; `horizontal` = same ring rotated 90°. Returns `period`, `angle_deg` at the vertical-band argmax and `vertical_to_horizontal = max(P[vertical]) / max(P[horizontal])`. This is the prototype's `u.py`.

### 7.2 `tests/test_analyse.py` (main seam)

New (all `shape=(256, 256)`, `**TYPICAL` unless stated):
- `test_stripe_free_mottled_frames_are_not_striped` — seeds 0–19, `modulation_depth=0`: `striped is False`, `period_px`, `angle_deg`, `modulation_depth` all `None`.
- `test_clear_stripes_in_mottle_are_found_and_measured` — seeds 0–19, `m = 0.5`, `(period, angle)` cycling through `[(3,10),(5,0),(8,6),(12,-8),(20,-10),(4,-4),(16,10),(6,-10),(10,3),(14,-6)]` (seed i takes entry i % 10): `striped is True`; `assert_matches_truth`; `assert_depth_matches`.
- `test_strong_stripes_are_measured` — seeds 0–4, `m = 0.8`, periods {5, 12}, angle 6: striped, period/angle/depth in tolerance (the AC says m ≥ 0.5, so cover a value above the floor).
- `test_period_and_angle_extremes_are_detected` — 8 frames, one seed per case: `(period, angle)` ∈ {3, 20} × {−10, 0, 10} plus (3, 5) and (20, −5), case i using seed i (seeds 0–7), `m = 0.5`: striped, `assert_matches_truth` (N5).
- `test_modulation_depth_is_relative_to_local_envelope` — `shape=(256, 640)`, `period=8`, `angle_deg=4`, `m=0.5`, scorched, seeds 0–2, parametrised over `noise ∈ {0.0, Emccd()}`. Analyse two 128×128 crops of the **same** frame, rows `64:192`, with columns chosen from `Synthetic.clean` rather than hard-coded (N1: the fixed flank `0:128` had mean profile only 0.09–0.17 of peak on seeds 0–2, and seed 0 scored 1.7× threshold on a 1.5% area):
  - Slide a 128-column window over columns in steps of 8; `level(c0) = clean[64:192, c0:c0+128].mean() / clean.max()`.
  - **Bright crop:** the window with the highest `level`.
  - **Dim crop:** the window with the highest `level` that is ≤ 0.3, taken on the side of the frame whose edge window is darker (the left or right flank, whichever is dimmer). Precondition asserted in the test: `0.2 ≤ level(dim) ≤ 0.3` and `level(bright) ≥ 2.5 · level(dim)`, so the test fails loudly rather than silently comparing two similar crops if the generator changes. (Same `clean` for both noise cases, by the draw order in §3.2.)
  - Assert: both `striped`; both depths within `DEPTH_TOL` of 0.5; `|depth_bright - depth_dim| ≤ 0.05`. Assert depth only (crops are 128 px; period/angle tolerance is covered elsewhere).
  - Evidence: prototype seeds 100–102 with fixed crops gave core 0.484–0.493, flank 0.467–0.498, but that was `q.py`'s measurement (single best period, no floor), not §4.3. The review re-ran §4.3 on seeds 0–2 with the fixed crops: depths 0.473–0.501, diff ≤ 0.02. The ~0.2–0.3 level window has not been run with §4.3; the implementer checks the margin while making the test green and records the depths in the handoff.
  - Why crops: the AC is about bright vs dim *parts of the profile*, and the Report has one depth per frame until ticket 05. Cropping is ordinary public use (spec story 34) and needs no region masks in the generator (05's work).
- `test_borderline_striped_frame_has_finite_measurements` (B1) — `**TYPICAL`, `m = 0.2`, scorched. The implementer picks (from seeds 0–19, periods {3, 8, 20}) two or three frames whose score lands in `(THRESHOLD, 1.5·THRESHOLD)` with the real code (prototype m = 0.2 scores were 101–196, so such frames exist), and the test asserts that precondition first, so it fails loudly if the threshold or method moves rather than silently testing a clear frame. Then: `report.striped is True`; `period_px`, `angle_deg`, `modulation_depth` are finite; `3 ≤ period_px ≤ 20` is **not** asserted (N6, 05's concern); `json.loads(report.to_json())` succeeds. Also one CLI run on one of these frames exits 0 (§7.3). If no seed reaches the band, widen to periods {3..20} or seeds 0–49 before giving up, and say so in the handoff. Whether the fallback branch itself ran is internal and not asserted; the seam-level guarantee is "finite and serialisable".
- `test_multiscale_mottle_is_handled` — seeds 0–9, `mottle="multiscale"`: `m = 0` → not striped; `m = 0.5` (periods cycling {3, 8, 20}, angle cycling {−10, 0, 10}) → striped with period/angle in tolerance. Not an AC (spec robustness); prototype margins 2× each side.

Changed ticket 01 tests (keep their intent):
- `test_report_converts_to_json`: key list gains `modulation_depth`; type check loops over `period_px, angle_deg, modulation_depth`.
- `test_profile_only_frame_is_not_striped`: also assert `modulation_depth is None`.
- `test_clear_full_frame_stripes_are_found_and_measured`: also `assert_depth_matches` (m = 0.6, Gaussian noise).
- All other ticket 01 tests (constant frame, no positive light, min side, non-2D, non-finite, not modified, score vs threshold) must pass unchanged. Prototype with the new score: profile-only max 72.1 over seeds 0–9 and noise 0/0.001/0.01 (review re-run; seeds 0–4 alone gave ≤ 53), constant `np.ones` ≈ 3e-12, m = 0.6 ≈ 3.5e4–4.3e4, (40, 64) frame scores 25.9.

### 7.3 `tests/test_cli.py`

- `test_cli_writes_json_report_for_striped_csv`: also check `abs(report["modulation_depth"] - 0.6) <= DEPTH_TOL`.
- `test_cli_reports_borderline_frame` (B1): write one of the borderline frames from §7.2 to CSV, run the CLI with `-o`; exit 0 and the JSON parses with finite `period_px`, `angle_deg`, `modulation_depth`.

### 7.4 Runtime

Prototype: ~0.6 s per 256×256 frame. New tests analyse ~130 frames: ~1.5 min single-threaded on top of the existing suite. Acceptable; no `slow` marker (ticket 07 introduces it). Implementer reports the suite time in the handoff. If it exceeds ~3 min, shrink batches to 10 seeds rather than adding markers.

## 8. Acceptance criteria → proving tests

| AC | Proven by | Seam |
|---|---|---|
| Generator: scorched (~0.4), multiscale (~0.35); EMCCD with configurable peak photons, EM gain incl. off, read noise, spurious charge | `test_mottle_has_the_requested_strength`, `test_mottle_none_is_unchanged_from_ticket_01`, `test_emccd_peak_photon_count`, `test_emccd_noise_statistics` (gain on, gain off, read noise, cic) | generator |
| Self-consistency: m = 0 no stripe peak; clean striped frame's spectral peak = true period/angle | `test_stripe_free_frame_has_no_stripe_peak`, `test_clean_stripes_put_the_spectral_peak_at_the_true_period_and_angle` | generator |
| ~100 photons, scorched: stripe-free → not striped; m ≥ 0.5 → striped, across seeds | `test_stripe_free_mottled_frames_are_not_striped` (20 seeds), `test_clear_stripes_in_mottle_are_found_and_measured` (20 seeds, m = 0.5), `test_strong_stripes_are_measured` (m = 0.8) | `analyse` |
| Detected stripes: period, angle, depth within spec tolerances (±5%, ±1°, ±0.1) | same two tests via `assert_matches_truth` + `assert_depth_matches`; ticket 01's full-frame test with depth added; `test_borderline_striped_frame_has_finite_measurements` and `test_cli_reports_borderline_frame` guarantee a striped Report always carries finite, serialisable values (B1) | `analyse`, CLI |
| Depth relative to local envelope: same m in bright and dim parts | `test_modulation_depth_is_relative_to_local_envelope` (noise-free and EMCCD) | `analyse` |
| Periods 3–20 px, tilts ±10° | `test_period_and_angle_extremes_are_detected`; the 20-seed batch also covers 3, 20, ±10 | `analyse` |

Also in scope (no AC): `test_multiscale_mottle_is_handled`; Report/JSON/CLI carry `modulation_depth`. The EMCCD CIC case runs at `photons_peak=1` (B2).

## 9. Prototype evidence (throwaway, not committed)

`/tmp/claude-1000/-home-rusiva-dev-denoisifier/e3eed7db-ace9-4511-bbf2-7585279f9fa6/scratchpad/proto/` — `p.py` (generator per §3.2 and the bank of §4.2), `q.py` (`gabor`), `v.py` (per-pixel maps + §4.3 measurement; the reference), `s.py` (floor `A0`), `u.py` (spectral oracle helper), `r.py` (batches, crops). Run with `PYTHONPATH=. uv run --no-project --with numpy --with scipy python <file> ...`.

| Frames (256×256, EMCCD typical unless noted) | Seeds | Score |
|---|---|---|
| scorched, m = 0 | 100–199 | max 71.7 (top 5 per 25-seed block 25–72) |
| multiscale, m = 0 | 100–149 | max 75.7 |
| scorched and multiscale (separately), m = 0.5, 10 (period, angle) cases incl. 3/20 px, ±10° | 100–109 | min 301 / 309 (the two runs); worst errors over both: period 0.3%, angle 0.24°, depth 0.02 |
| scorched, m = 0.8 | 100–109 | min 710; worst 0.2%, 0.07°, 0.015 |
| scorched, m = 0.2 (not an AC) | 100–105 | 101–196 (some below 150: ticket 03's problem) |
| ticket 01 profile-only, Gaussian noise 0 / 0.001 / 0.01, `A0 = 3e-3` | 0–4 (review: 0–9) | ≤ 47 / ≤ 47 / ≤ 53; seeds 0–9 max 72.1 (with `A0 = 1e-3`: up to 420, a false alarm) |
| review re-run on **test** seeds, plan draw order: scorched m = 0 / multiscale m = 0 / §7.2 m = 0.5 batch | 0–19 / 0–9 / 0–19 | max 60.9 / max 54.4 / min 425, worst period 0.1%, angle 0.5°, depth 0.02 |
| ticket 01 m = 0.6, noise 0 | 0, 5, 6 | 3.7e4–4.3e4 |
| `np.ones((64, 64))` | — | 3e-12 |

Timing: 0.6 s per 256×256; 7.0 s per 1600×400 (complex128, full FFTs, no optimisation). Under ticket 03's 10 s gate but close; levers if needed there: float32/complex64, cropping to the light-mask bounding box, and computing large periods on a 2× decimated frame each give roughly 2×.

## 10. Risks

- **Threshold margin is ~2× on each side** for m = 0.5. The null tail is heavy (max of a ratio map over ~65k pixels × 18 periods). If the implementer's numbers on calibration seeds narrow the gap, widen the box window (e.g. `3p × 3p`) before touching the threshold, and record the change.
- **Score depends on frame size** (max over more pixels on bigger frames). Fine for 02 (fixed 256×256 tests, crops only use depth); ticket 07 calibrates at the real frame size.
- **Isotropy assumption** for the reference: matches ADR 0001; would break on directional mottle.

## 11. Decisions (formerly open questions; settled by the owner)

1. **O1:** `modulation_depth` is a top-level Report field now (§5); it moves into regions with `period_px`/`angle_deg` in ticket 05.
2. **O2:** generator noise API is `noise: float | Emccd` (§3.1); the Gaussian path stays, ticket 01 tests unchanged.
3. **O3:** the bright/dim depth AC is proven with two crops of one frame, the dim crop chosen from `Synthetic.clean` at a profile level of 0.2–0.3 of peak (§7.2, per review N1).
4. **O4:** `A0 = 3e-3` accepted: noise-free stripes shallower than about A0·√THRESHOLD ≈ 0.04 are never Striped.

Still open: none blocking. Carried to later tickets: m = 0.2 scores sit around the threshold (03); unclamped period/angle on borderline frames (N6, 05); the owner's Angle sign check against a real Solis view (from ticket 01).
