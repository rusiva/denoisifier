# 03: Protected numbers

**What to build:** Every number that decides a verdict or a pass is listed in one reviewable lockfile, and `make check` fails if any of them changes silently. Today these numbers are scattered: detector settings in the package, tolerances in test helpers, the slow tier's acceptance limits and seed ranges in the feasibility driver. A widened tolerance (like the ±10° → ±12° spectral band in ticket 02) can land as a one-character diff that nobody notices. With this ticket in place, any such change must also edit the lockfile, and the owner reviews that edit. Adapted from polsigns' protected-dial lockfile check (`~/dev/polsigns/tools/lint_protected_dials.py`); in Python the constants can be read from the syntax tree instead of extracted with regexes. See `../spec.md`.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Test-side numbers live in one test module: Period, Angle and Modulation Depth tolerances, the spectral band, the borderline score window, the slow tier's acceptance limits (false-alarm rate, minimum detection rate, timing limit) and the named seed ranges. Tests import them from there.
- [ ] A check in `make check` compares the live values of the detector's settings (at least `THRESHOLD`, `_A0`, `MIN_SIDE`, `_PAD`, `_MIN_PAIRS`) and every number in that module against a checked-in lockfile. It names each mismatch.
- [ ] A new module-level number in either place that is not in the lockfile also fails the check, so a new setting can't bypass it.
- [ ] The lockfile says at the top that editing it is a weakening move needing owner approval, and CLAUDE.md lists it among the protected surfaces.
- [ ] Proof: a planted change to one tolerance, and separately to `THRESHOLD`, turns `make check` red, naming the number and the lockfile. The plants are not committed.
- [ ] `make check` and `make check-slow` stay green, and the values match the current committed ones exactly. This ticket moves numbers; it never retunes them.
