# 04: Frame reader handles Solis exports

**What to build:** An experimenter can load real Andor Solis CSV exports without silently corrupting the data. A plain grid always keeps **every** column. A Solis axis column (pixel or wavelength) is dropped **only when explicitly requested** (library option and CLI flag). When the first column looks like an axis (strictly increasing) but was kept, the reader adds a warning to its notes. Never guess: a crop on the rising side of the profile can have a real intensity column that counts up. Metadata lines before and after the grid are skipped and noted. Negative values are accepted. Malformed grids fail with a clear error. Reader notes appear in the JSON report.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] A plain grid loads with every column kept.
- [x] A grid with a Solis axis column keeps it by default and includes a warning in the reader notes; with the explicit option it is dropped and the note says so.
- [x] Regression: a grid whose real first intensity column counts up row by row is kept intact (with a warning only).
- [x] Metadata lines that aren't numbers, before or after the grid, are skipped and counted in the reader notes.
- [x] Negative values load unchanged.
- [x] Uneven row lengths raise a clear error naming the row; a value that isn't a number inside the grid raises a clear error naming its position.
- [x] The CLI exposes the drop-axis-column option, and reader notes appear in the JSON report.

## Comments

**Implementer (2026-11-11).** Built per `.scratch/stripe-detector/handoffs/04-plan.md` (Settled S1-S9), test-first, commits `20a569a`, `510f92c`, `bb0d1a8`, `5bf2287`, `beefc76`. No stamped file, protected number or gate config changed; no weakening move.

Gate: `make check` exit 0; `326 passed, 4 deselected in 123.50s (0:02:03)`; slow-tier stamp check passed; HEAD `beefc76` (tree dirty only with the pre-existing 02/07 issue edits and untracked handoff dirs).

Known gap: no real Andor Solis export is in the repo, so the assumed layout (comma-delimited rows, text-keyed metadata lines, axis in column 0, no trailing comma, no numeric header row) is unverified. Real-Solis compatibility is not proven; a real-file fixture may follow in a later ticket.
