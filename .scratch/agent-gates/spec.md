# Agent gates

Deterministic checks and gates for agents coding in this repo. Before this work there is no Makefile, no lint or type-check configuration, no test timeout, and `-W error` runs only when an agent remembers it.

The design borrows from two sibling repos: `~/dev/polsigns` and `~/dev/cadmesh`. From them: a two-tier Makefile, `make fix` as the only target that changes files, a fixed ruff rule set including the rules that catch suppressions, strict pytest config with a thread-method timeout, a protected-number lockfile check, regenerate-and-compare checks, and a hook that forces long gate runs into the background. Their conda environments, CMake, LD_PRELOAD shims, model hashes and CI matrix do not apply here.

## Failure modes the gates target

Taken from the stripe-detector reviews (`.scratch/stripe-detector/handoffs/.archived/`) and measured on the repo:

1. **Statistical tests whose margin was luck.** In 02 review B2, the CIC tolerance was about 1σ and failed 30% of seeds.
2. **Hand-calibrated numbers that can silently go stale.** `THRESHOLD`, `_A0` and the borderline set are supported only by numbers in comments. The feasibility gate calibrates its own threshold on every run, so nothing checks the shipped value.
3. **Tolerances widened to make a test pass.** The spectral band went from ±10° to ±12° (02 P6).
4. **NaN and warnings slipping through.** NaN produced invalid JSON (01 B2), and `log(0)` raised a `RuntimeWarning` (02 N2).
5. **Calibration and evaluation seeds overlapping.** Raised in 01 N2; tickets 03 and 07 make separation an acceptance criterion.
6. **Glossary terms drifting.** Review caught "amplitude", "orientation" and "local Stripe Score".
7. **Claims nobody can check.** A handoff said "mypy clean" with no mypy configured. Suite times in handoffs were 2–4× off from what I measured under load.
8. **No lint or formatting checks at all.**
9. **A slow numerical suite.** The non-slow suite takes 3.5–5.5 minutes under load, and the slow tier about 40 minutes, longer than the 10-minute Bash tool limit.

## Decisions

- **Tracer bullets.** Each ticket ships one complete gate path: a planted violation turns the real `make check` or `make check-slow` red with that check's own message. Testing only a helper does not count. Ticket 01 is deliberately thin. Further tickets are not split per tool, because every ticket here pays a full plan, review and implement cycle.
- **Seed separation is enforced at runtime.** The check watches every seed passed to the generator, not literal `seed=` arguments, because most test seeds arrive through parametrize or variables (Codex adversarial review, finding 1).
- **The slow tier is compulsory when the detector changes.** A green `make check-slow` records a hash of the files that affect detector output. `make check` fails when those files differ from the recorded hash (Codex finding 2; owner, 2026-11-10).
- **Timing is split (owner, 2026-11-10).** The compulsory slow tier asserts only a loose wall-clock limit (about 30 s per 1600×400 frame) to catch real slowdowns. Ticket 03's 10 s gate and ticket 13's 5 s target move to a separate `make bench` target, run on an idle machine, that records machine load.
- **Calibration reproduction lives in stripe-detector ticket 07 as one of its acceptance criteria (owner, 2026-11-10).** It is not a ticket here.
