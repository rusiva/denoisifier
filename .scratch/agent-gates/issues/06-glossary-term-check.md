# 06: Glossary term check

**What to build:** `make check` rejects avoided terms in docstrings and comments, so review stops spending rounds on vocabulary drift ("amplitude" in 01 F2, "orientation" in 02 S1). The avoided terms come from the `_Avoid_:` lines in `GLOSSARY.md`, cut down to a curated list of terms with a history of drift, so ordinary identifiers such as `Synthetic.clean` and common words such as "signal" are not flagged. This is the lowest-value ticket in the set; drop it first if the set has to shrink. See `../spec.md`.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] A check in `make check` scans docstrings and comments in the package and tests (not identifiers or string data) for the curated terms. At minimum: orientation, amplitude, wavelength, false positive.
- [ ] The curated list is checked against `GLOSSARY.md`: a listed term that is no longer on any `_Avoid_:` line fails the check, so the list can't drift from the glossary.
- [ ] Each failure names the file, line, term and the glossary term to use instead.
- [ ] The current code passes, or the existing hits are fixed in this ticket.
- [ ] Proof: a planted "orientation" in a docstring turns `make check` red with the check's message. The plant is not committed.
