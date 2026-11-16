# 04: Numerical qualification

**What to build:** Find out, on real macOS hardware, whether the exact-number checks hold, and if they don't, give the owner the measurements to decide a cross-platform policy. Known risk: `tests/test_synthetic.py:195` and `:500` compare SHA-256 hashes of generated frames. With NumPy's X86_V3/V4/AVX512_ICL dispatch disabled on the owner's x86 machine (code and lockfile unchanged), 2,625/65,536 pixels moved by at most 4.55e-13 and the default-frame test failed (Codex review, 2026-11-14). The stored thresholds and the calibration reproduction (`tests/test_slow_calibration.py`, `PACKAGE_CALIBRATION_DIGEST`) were also produced on x86 Linux. That x86 experiment is diagnostic evidence only; it does not stand in for a native macOS run. See `../spec.md`.

**Blocked by:** 03 (or a native run on the friend's Mac)

**Status:** ready-for-agent

- [ ] Recorded: macOS version, chip, Python and numpy/scipy versions of each macOS run used.
- [ ] Run order: the generator hash tests first, then `make test-fast`, then the calibration reproduction (`make check-slow`).
- [ ] For each failing check: the size of the difference (pixels changed, max abs/rel difference, any change in thresholds or downstream scores), not just pass/fail.
- [ ] If everything is green: record it and close; no policy needed.
- [ ] If anything diverges: a written comparison-policy proposal under `## Comments` with justified bounds, which keeps exact same-platform identity checks and stored-artifact integrity checks. Changing an expected value or tolerance, adding a platform condition, or narrowing tests is a listed CLAUDE.md move and is decided through the approval process (Codex review, then orchestrator, owner when undecided) before any code changes.
- [ ] Never: regenerate baselines on macOS, skip or xfail the failing tests, or make the slow tier Linux-only without an approved ruling.

## Comments
