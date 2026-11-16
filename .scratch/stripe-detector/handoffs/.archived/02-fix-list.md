# 02 code-review fix list (review from 1d07977; commits 631c3af, d3b1150)

Owner ruling:
- **P4**: set `THRESHOLD` to the plan §4.4 rule: log-midpoint of the highest stripe-free score and the lowest m=0.5 score on calibration seeds 100-199 (currently ~sqrt(83.7*363) ≈ 174). Re-measure with the real code, update the comment, and re-check every test that depends on the threshold. The borderline set (scores 1x-1.5x threshold, plan §7.2) must be re-chosen for the new value.

Fixes:
- **S1**: GLOSSARY uses **Angle**, not "orientation": fix `_local_stripes.py:6`, the `analysis.py` module docstring and similar comments.
- **S2**: `LocalStripes.ratio` docstring calls it "the local Stripe Score"; Stripe Score is a per-frame glossary term. Describe it as a local energy ratio without the glossary term.
- **S4**: `_local_stripes._PAD = 32` relies on `MIN_SIDE` in `analysis.py`, and the `A0` comment reasons about `THRESHOLD`. Make the coupling explicit (an assert or a shared constant).
- **S5**: rename unclear names where cheap: `hot`, `p_star`, `g` (reused for the Gabor response in `analysis._measure`), `_norm` (it standardises), `e: Emccd`, `k`, `win`.
- **S6**: consistent visibility: public constants only for API (`THRESHOLD`, `MIN_SIDE`), with internal tunables underscored (`MIN_PAIRS`, and `PERIODS`, `STRIPE_ANGLES_DEG`, `A0` in the private module) unless tests need them.
- **S7**: `report.to_dict` repeats `None if x is None else float(x)` three times; use a helper.
- **S8**: `tests/test_cli.py` imports `BORDERLINE`, `borderline_frame` from `test_analyse`; move them to a non-test helper module (like `tests/truth_match.py`, `tests/spectrum.py`).
- **Nits**: three blank lines before `_mottle` in `synthetic.py`; two blank lines before the first new test in `test_synthetic.py`.
- **P1**: write `.scratch/stripe-detector/handoffs/02-implementer-handoff.md` with what plan §4.4, §7.2 and §7.4 asked the implementer to record: the measured thresholds and margins (after P4), bright/dim crop levels and depths with their margin, the full-suite time, and the m=0.2 score range flagged for ticket 03. Also record the deviations: spectral oracle band ±12° (plan §7.1 said ±10°), dim crop taken from the profile-only `clean` (plan §11 O3 said mottled `clean`).

Not fixing: S3, S9, S10, P2, P3, P5, P6.
