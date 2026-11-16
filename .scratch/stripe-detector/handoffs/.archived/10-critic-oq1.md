# 10 critic: OQ1 / O1, the fork direction convention

Read-only second opinion at BASE `ca48498`. Sources: `10-plan.md` 2.1, 2.4, 9 (OQ1); `10-plan-review.md` O1; `issues/10-forks.md`; `spec.md:50`, `:114`, `:125`; `GLOSSARY.md` (Fork, Phase Jump); `src/denoisifier/report.py:151-175`, `:231-249`, `:269-281`; `src/denoisifier/cli.py:15-17`, `:65-69`, `:119-120`.

## Verdict

**Option A (keep the value in both layouts), with the wording changed.** Not the owner's call: the spec and ticket 09's precedent decide it. Record the ruling in the ticket's Comments and add it to the spec edit proposed at close.

## What the repo already fixes

1. **Analysed frame.** `spec.md:125` gives `charge * atan2(y - y0, x - x0)`. With y the row (increasing downward) and the phase growing with the column (every searched Angle has cos t > 0), a row above the fork gains `+pi * d` from the fork term and a row below gains `-pi * d`. So d = +1 puts one more stripe above: one stripe becomes two going toward row 0. That is story 21's "splitting upward" (`spec.md:50`). The plan and the review agree on this, and I checked the arithmetic.
2. **Under `--transpose`.** Three existing behaviours point the same way:
   - `PhaseBreak.transposed` re-indexes the points and keeps `jump_rad`: "every pixel keeps its side; the jump is unchanged" (`report.py:172-175`). `UNITS["jump_rad"]` ends "same value in both layouts".
   - `angle_deg` is signed and is "always measured on the analysed (transposed) frame" (`cli.py:16`). It is not re-expressed in file coordinates.
   - `in_file_layout` only moves positions (labels, bboxes, lines). No measured value changes.
   Option A is this rule applied to forks: the point is re-indexed and the direction is kept.

## Attack on option A (plan)

- **Unambiguous?** Yes in substance, no in the drafted wording. `UNITS["direction"]` as drafted reads "one more stripe above the fork than below (toward column 0 in file layout when transposed)". "Above" depends on how the user displays the array (`origin="lower"` flips it), and the bracket does not say what is toward column 0. Fix below.
- **"One more stripe" as a count.** The review's B1 shows the literal count over a finite row is not determined by d. Fine as a description, wrong as the only definition. State the split direction, which is local and visible, and keep the count as a gloss.
- **Matches the spec?** Yes in the analysed frame. In file coordinates the `atan2` winding is `-direction` (the review's point). That is only a problem if the public text invites the user to compute a charge in file coordinates. So the public JSON text should not say "charge" at all. The generator's `ForkPoint` docstring can, because the generator has no file layout.
- **Misreading risk.** Low once the text names both layouts in visible terms. The stripe-count form does not depend on the phase sign convention (cos(phi) = cos(-phi)), so a user can check it by eye on either layout.

## Attack on option B (negate in file layout)

- It would be the first Report field whose **value** changes in `in_file_layout`. Every other field is either re-indexed or untouched.
- `analyse(frame.T)` through the library and `--transpose` through the CLI would report opposite directions for the same physical fork. Under A they agree.
- It has no plain reading. +1 would mean "splits toward row 0" in a frame and "splits toward increasing column" in a transposed file. Only the formula survives, and users read story 21's words, not the formula.
- `--transpose` exists so the analysed frame is in sensor orientation (`cli.py:67-69`). "Upward" in story 21 is a sensor-orientation word. B breaks that; A keeps it.
- The formula it preserves is itself convention-bound: the file-coordinate charge needs the phase to grow with the file's row, which no document states.

## Other options, rejected

- A word (`"up"`/`"down"`) or a vector: the spec's schema says `direction ±1` (`spec.md:114`), and a word is wrong in file layout.
- Dropping the direction in file layout: loses story 21 for exactly the users who need `--transpose`.

## Recommended text

- `Fork` docstring and GLOSSARY Fork: "Direction +1: going toward row 0 past the fork, one stripe becomes two (a row on the row-0 side crosses one more stripe). -1: the same going away from row 0."
- `UNITS["direction"]`: `"+1: one stripe becomes two going toward row 0 of the analysed frame (toward column 0 in file layout when transposed); -1 the reverse; same value in both layouts"`.
- `UNITS["point"]`: as the plan has it.
- No "charge" and no "above/below" in the Report text. `ForkPoint` (generator) keeps the `atan2` formula and states that the Report's direction equals it.
- Tests: one test that `in_file_layout` swaps the point and keeps the direction, and one that `analyse(frame.T)`-style input and the transposed report describe the same split side (the review's B1 continuous measure, applied along columns).

## Is it hard to revert? Does it need the owner?

- A sign flip in public JSON is a breaking change, so it deserves care. But the JSON carries its own `units` text, and the choice is not between equal options: story 21, `spec.md:125` and three existing transpose behaviours all select A. B needs a new rule that nothing else in the Report follows.
- No taste question and no outside knowledge is involved. The one assumption is "upward = toward row 0", which is the array convention the spec's forward model already uses.
- So the orchestrator can rule. Tell the owner at close, with the proposed `spec.md:114` line: "`forks`: list of {region, point as (row, col) in frame px, direction ±1: +1 splits toward row 0 of the analysed frame}".
