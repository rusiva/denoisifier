# 11 code review: fix / owner / pass (orchestrator)

Review from BASE e06a902 to 66c08f0. Standards and Spec axes, both opus, fresh context.

## Fix
- **F1 (Std 1, glossary)**: replace "limit(s)" with threshold vocabulary (`limits = _resolve_break_fork_thresholds(...)`, "evidence limit" in `_region_forks`, `_break_fork_evidence`, `find_phase_breaks` docstrings, `implication_violations(row, limits)`); make Phase Break / Fork capitalisation consistent in `calibration.py` messages and `cli.py` help/docstring per GLOSSARY. Note the glossary gap ("fake Phase Break / Fork" has no entry; False Alarm covers stripe Verdicts only) in the ticket Comments for `/domain-modeling` (docs/agents/domain.md); no GLOSSARY edit.
- **F2 (Std 2)**: fill ADR 0003 "Measured" and the `analyse` docstring's measured count from the `make check-held-out` run (after it).
- **F3 (Std smell, Middle Man)**: drop the `synthetic(...)` wrapper and the `record = tc.record` alias in `tests/break_fork_calibration.py`; call through directly. Output must not change.
- **F4 (Std smell, Mysterious Name)**: rename `_BridgeDomain.pa`/`pb` to `a_pixels`/`b_pixels`.
- **F5 (Spec a1)**: held-out fake records carry each fake's own E (the reported break's / Fork's evidence, not the frame scalar) and a measured `in_fake_region` (reported region overlapping no truth region), per plan §6 AC 2.
- **F6 (Spec a2)**: Makefile `check-held-out` help names `.gate/held-out-break-fork.json` too (approved gate-text edit, ticket Comments).
- **F7 (Spec c1)**: per-case alarm on fakes ≥ `case_alarm` (plan §6 wording; fakes ≥ frames, so stricter than the frame tail); record both fakes and frames per case.
- **F8 (Spec c2, c3)**: ADR 0003's S_b definition and the "Found bounds reported" bullet match the `_break_fork_evidence` docstring (largest min(E_1..E_j) over splitting lines in bridge domains).
- **F9 (implementer-3 open item)**: `tests/slow_stamp.py` stale-stamp message duration text → the new check-slow duration. Orchestrator approval: doc-text only in the stamp file, no logic change, motivated by the documented duration change; record in ticket Comments before the edit.

F3/F4 are behaviour-free renames; F1 is text. None should move break/Fork evidence. If the `make check-slow` reproduction of the stored calibration goes red after them, stop and report (do not re-run the driver or re-set `PACKAGE_BREAK_FORK_*` without the orchestrator).

## Owner
- None blocking. Reported at close: `make check-held-out` now ~60 min (was 17-20), and `make check` took 1684 s at 66c08f0.

## Pass
- **Std smell, Duplicated Code** (`_BreakForkCalibration` vs `Calibration` JSON handling): a shared helper touches the stripe `Calibration` serialisation behind `PACKAGE_CALIBRATION_DIGEST`; out of scope and risky for a re-store; follow-up candidate.
- **Std smell, Data Clumps** (`_FrontHalf` optional fields): judgement call; changing the front half triggers plan step 8's driver re-run for no behaviour gain; the two asserts are explicit.
- **Std smell, Divergent Change** (`_break_fork_evidence` in `analysis.py`): deliberate (review B5: share the front half so the evidence path cannot drift from `analyse`).
- **Std smell, private names across modules**: repo precedent, and O4 keeps the calibration private on purpose.
