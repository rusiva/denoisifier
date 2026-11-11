# 06: Glossary term check

**What to build:** `make check` rejects avoided terms in docstrings and comments, so review stops spending rounds on vocabulary drift ("amplitude" in 01 F2, "orientation" in 02 S1). The avoided terms come from the `_Avoid_:` lines in `GLOSSARY.md`, cut down to a curated list of terms with a history of drift, so ordinary identifiers such as `Synthetic.clean` and common words such as "signal" are not flagged. This is the lowest-value ticket in the set; drop it first if the set has to shrink. See `../spec.md`.

**Blocked by:** 02

**Status:** resolved

- [x] A check in `make check` scans docstrings and comments in the package and tests (not identifiers or string data) for the curated terms. At minimum: orientation, amplitude, wavelength, false positive.
- [x] The curated list is checked against `GLOSSARY.md`: a listed term that is no longer on any `_Avoid_:` line fails the check, so the list can't drift from the glossary.
- [x] Each failure names the file, line, term and the glossary term to use instead.
- [x] The current code passes, or the existing hits are fixed in this ticket.
- [x] Proof: a planted "orientation" in a docstring turns `make check` red with the check's message. The plant is not committed.

## Comments

**Implementation (implementer, 2026-11-11, HEAD `fb8c5c8-dirty`).** Dirty means the new `tests/test_glossary_terms.py` plus the uncommitted `.scratch/` Markdown that was already there at the start.

- The check is `tests/test_glossary_terms.py`, which runs in `make check`'s `$(PYTEST)` step. That means no change to the `Makefile` or other gate config, and no approval needed. Nothing in `STAMPED_FILES` changed, so the slow-tier stamp stays fresh.
- `CURATED = ("orientation", "amplitude", "wavelength", "false positive")`. It scans module, class, function and attribute docstrings (bare string statements, taken as raw source) and `#` comments in `src/denoisifier/**/*.py` and `tests/**/*.py`. Matching ignores case, allows a plural `s`/`es` and works across line breaks (consecutive comment lines are joined). Identifiers and other string literals are not scanned (`test_scan_flags_docstrings_and_comments_only`).
- Replacements come from `GLOSSARY.md`: each `_Avoid_:` term maps to the `**Entry**:` above it. A curated term that no `_Avoid_:` line names fails `test_curated_terms_are_avoided_in_the_glossary`. Checked by temporarily adding `"signal strength"`: `CURATED in test_glossary_terms.py lists ['signal strength'], which no `_Avoid_:` line in GLOSSARY.md names.` (reverted).
- Existing hits: none. `grep -rniE` for the four terms over `src` and `tests` found nothing.
- Proof: untracked `tests/zz_plant.py` containing `"""Stripe orientation, planted for ticket agent-gates/06."""`, then `make check` → exit 2, `tests/zz_plant.py:1: "orientation" is avoided in GLOSSARY.md; use "Angle" instead`, `1 failed, 296 passed, 4 deselected in 114.65s (0:01:54)`. The plant was then deleted, and `git status --porcelain -- src tests` showed only the new test file. A plant in `src/denoisifier/` also trips `test_stamped_files_cover_the_slow_tier` (an unclassified src file), so the proof uses `tests/`.
- `make check` (clean) → exit 0, `297 passed, 4 deselected in 87.12s (0:01:27)`, and `slow_stamp.py check` passed.
- Known holes: avoided terms in GLOSSARY.md itself, Markdown and string data are out of scope. The **Phase Break** definition in GLOSSARY.md said "Period and orientation stay the same", using an avoided term; changed to "angle" at the owner's request (2026-11-11).
