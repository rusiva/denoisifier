# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Do not grant the approval bundle unchanged. W4's re-pick is under-specified, two pinned thresholds leave other calibration values unprotected, and new wide marks are missing from the table. These are orchestrator-resolvable; no new human-owner decision is necessary. W7's existing ruling stands.

Findings:
- [medium] W4 does not fully predeclare a mechanical borderline re-pick (.scratch/stripe-detector/handoffs/07-plan.md:309)
  “Lowest unused test seed per entry, from 10 up” leaves the candidate set, meaning of unused, upper bound, duplicate policy and exhaustion behavior undefined. Existing borderline entries share seeds and periods; TEST_SEED_BLOCK is 10–99 and is already reserved in USED_SEEDS. Different reasonable interpretations produce different fixtures. Choosing among them after viewing scores permits selection that turns the window assertion green without fixing code. Selection by the defining score window is motivated, but this wording does not sufficiently constrain it.
  Recommendation: Before step 5, freeze the finite candidate set, existing entry order and periods, all generator settings, uniqueness rule and strict score-window predicate. Stop on exhaustion or analysis errors. Select using the score predicate alone; a subsequent finite-measurement or serialization failure must remain red, never trigger another pick. Record the scan results.
- [medium] Two threshold pins do not protect the stored calibration (.scratch/stripe-detector/handoffs/07-plan.md:58-63)
  The claim that any file edit forces a lockfile edit is false. Only ranks for 1% and 5% are pinned, while every stored score can determine another supported rate. A read-only numerical check with scores 1–300 showed that changing 271 to 270.5 preserves both pinned thresholds but changes the 10% threshold. After a score-path regression affecting an unpinned score, rewriting that JSON entry can make exact reproduction green without a lockfile change. Stamping the file forces another run but does not require approval of the new expected data.
  Recommendation: Protect the complete canonical calibration payload—ordered IDs, scores, shape and settings—with a lockfile-enforced value or digest, excluding observational run_info. Add its initial value to W4 and require explicit approval for subsequent changes. Verify that changing an otherwise unpinned score fails the fast protection check.
- [medium] New inner-loop exclusions are absent from the approval table (.scratch/stripe-detector/handoffs/07-plan.md:204)
  The plan requires seed-parametrised fast tests to use inner_loop.inner(), which adds wide marks after the first two distinct seeds. CLAUDE.md explicitly classifies adding wide to a parameter as a weakening move. W1–W10 contain no approval for these exclusions. Following the plan can therefore let test-fast deselect a failing new parameter without the required selection approval; make check would still catch it.
  Recommendation: Add a separate approval for the named new parameter sets using inner(), preserving INNER_LOOP_SEED_COUNT, coverage of each test case and full make-check selection. Do not authorize marking existing failures wide.

Next steps:
- W1 — approve. Adding the new calibration range while retaining old ranges strengthens separation; it provides no red-to-green escape.
- W2 — approve-with-condition. Limit the allowance to calibration generation and scoring, close it before evaluation, and preserve guard rejection outside it. Resolve the tiny-plan contradiction: test seeds cannot enter calibrating(), which accepts only registered calibration ranges; do not loosen that guard to accommodate them.
- W3 — approve-with-condition. Sharing the pool is motivated. Preserve spawn, initializer, allowance snapshot, ordered results and exception propagation. Require serial/pool equivalence and existing guard-negative tests to stay green unchanged; numerical equality alone does not prove isolation.
- W4 — reject as bundled. Threshold replacement and initial calibration are motivated, but fix the re-pick and complete-payload protection findings before approval. Do not treat this as permission to refresh expectations after a red check.
- W5 — approve. The listed stamp additions are minimal strengthening. No removals, exemptions or changes to stamp-success logic are authorized.
- W6 — approve-with-condition. The measured workload justifies 2400 seconds for the new expensive fixtures. Apply it only to their consuming tests; retain existing timeouts and performance assertions. It intentionally clears otherwise unavoidable fixture timeouts, not detector-performance failures.
- W7 — retain owner approval. The selection, target, marker and background-hook changes implement the ruling. Section 2.12's standing recalibration/source-write policy goes beyond 'held-out tests leave check-slow'; approve it separately through the orchestrator, retaining its prohibition on re-storing unexpected score changes.
- W8 — approve. Rename the sweep kind consistently while preserving parameter membership, coverage and assertions. A label-only expected-value update does not hide a behavioral failure.
- W9 — approve-with-condition. Authorize the initial step-5 artifact from the frozen settings and seeds, with the complete payload protected. No automatic rewrite during checking or continuing authorization to overwrite a failed reproduction baseline.
- W10 — approve-with-condition: approve an explicitly empty list for this implementation. P1 supplies no motivated exception. Any later threshold override needs a new named approval and retained default-verdict coverage; the generic category must not authorize post-failure substitutions.
- Section 7 lockfile — approve-with-condition. Approve the enumerated fixed additions and THRESHOLD removal, freeze exact tiny/folder/pool seed allocations before use, and derive initial stored values solely from the declared run. Hold BORDERLINE_TEST_CASES pending the mechanical rule and add complete-payload protection. Existing tolerances, regression seeds, pass counts and gate/probe thresholds remain outside this approval.
- Record the amended per-item approvals and reasons in ticket Comments before implementation. No item requires new human input on taste, external knowledge or hard-to-revert architecture. Review used read-only diff/code inspection and a numerical counterexample; no full gates were run.

[exited with code 0]
