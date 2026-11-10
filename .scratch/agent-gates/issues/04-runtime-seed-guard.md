# 04: Runtime seed guard

**What to build:** No test can judge the detector on a frame generated from a calibration seed, however the seed got there. Most test seeds reach the generator through parametrize or variables, not literal `seed=` arguments, so a check on the source text would miss them (Codex adversarial review, finding 1). Instead, during the test run, every seed passed to the generator is compared with the calibration ranges in the registry from ticket 03. The calibration routines themselves, the feasibility gate's calibration step and ticket 07's routine, are marked as allowed to use those ranges. Everything else fails if it touches one. See `../spec.md`.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Every calibration seed range in use is registered in ticket 03's module: the 100-199 range that `THRESHOLD` was set from, and the feasibility gate's calibration and probe-calibration ranges. The registry's own disjointness check covers all registered ranges, replacing the feasibility-only version.
- [ ] During `make check` and `make check-slow`, every seed passed to the generator outside an explicitly marked calibration context is checked against the calibration ranges. A hit fails that test, naming the seed and the range.
- [ ] The way to mark a calibration context is explicit and easy to find in a diff, and CLAUDE.md lists it as a protected surface.
- [ ] Proof: each of these planted cases turns the gate red with the guard's message: a parametrized test over a calibration seed, a seed computed into a variable that lands in a calibration range, and an evaluation step that draws its frames from the calibration set. The plants are not committed.
- [ ] `make check` and `make check-slow` stay green on the current tests. If an existing test is already caught, that is a finding: record it under `## Comments` and stop for the owner. Do not re-seed it on your own.
