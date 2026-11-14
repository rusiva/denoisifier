# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

Do not finalize the plan yet: the false-red budget uses an inapplicable baseline, and Q8 requires evidence the saved artifact does not contain. Q2 remains closed. No remaining decision inherently needs the human owner. The requested handoff could not be written because this session is read-only.

Findings:
- [medium] The detection false-red budget does not transfer to the new threshold (.scratch/stripe-detector/handoffs/07-plan.md:201-205)
  The 0.964 detection baseline comes from 100/100 spike-free frames at threshold 85.171. AC3 instead uses spiked frames at a newly estimated threshold. Neither unchanged score code nor the early-warning threshold of approximately 110 establishes the same detection probability. Consequently, the proposed budget test can pass while certifying an unsupported bound. For comparison, at a true detection rate of 0.95, the planned 90/100 check fails 1.147% of the time—already above the entire proposed 1% budget.
  Recommendation: Keep Q2's sizes and execution placement. Remove the unconditional combined-budget claim, or explicitly condition it on a justified detection baseline for the new threshold and population. Preserve the predeclared acceptance rule without tuning it after evaluation.
- [medium] Q8's per-score equality condition cannot be checked from the saved measurement (.scratch/stripe-detector/handoffs/07-orchestrator.md:27)
  The ruling requires regression scores to be bit-identical to the pre-ticket JSON. That file contains counts, the stripe-free maximum, and per-case striped minima; tests/feasibility.py:487–493 discards individual scores. Changes to non-extreme scores can leave every saved statistic unchanged. Comparing those summaries therefore cannot establish the stated condition, particularly while the shared pool is being refactored.
  Recommendation: Make the skip condition verifiable: use an independently obtained per-seed baseline, or explicitly rely on score-path diff review plus serial-versus-pool equivalence checks covering IDs and ordering. Describe saved-summary equality only as supporting evidence. The orchestrator can approve this correction.
- [medium] The folder round-trip test requests an unsupported rate (.scratch/stripe-detector/handoffs/07-plan.md:145)
  AC5 builds a calibration from 12 frames, then expects its JSON round trip to work through analyse at the default 1%. That gives k=floor(0.01×13)=0, so correct validation must raise. The E2 and Q6 rulings fix other parts of this test but leave this unavoidable failure, inviting an erroneous relaxation of the minimum-sample guard.
  Recommendation: Round-trip the 12-frame calibration using false_alarm_rate=0.1, and separately assert that its default 1% request fails clearly. Exercise successful default-rate injection with a calibration containing at least 99 scores.

Next steps:
- Retain Q1, Q3–Q7, Q9, B1–B3, B5, E1–E6 and O2, subject to the corrections above. Q3 remains an explicit synthetic assumption, not verified real-camera knowledge.
- Retain B4 only for named property-focused tests; preserve default-verdict coverage and do not describe the 256×256 GATE_STORED_THRESHOLD as calibrated for other shapes.
- Record the revised Q8/O1 rationale and delegated approvals in ticket Comments. No additional owner question is necessary; leave Q2 untouched.
- Save this review to .scratch/stripe-detector/handoffs/07-codex-review.md from a writable session. Review used read-only git inspection and numerical checks; no files were changed or committed.

[exited with code 0]
