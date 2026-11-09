# 04: Frame reader handles Solis exports

**What to build:** An experimenter can load real Andor Solis CSV exports without silently corrupting the data. A plain grid always keeps **every** column. A Solis axis column (pixel or wavelength) is dropped **only when explicitly requested** (library option and CLI flag). When the first column looks like an axis (strictly increasing) but was kept, the reader adds a warning to its notes. Never guess: a crop on the rising side of the profile can have a real intensity column that counts up. Metadata lines before and after the grid are skipped and noted. Negative values are accepted. Malformed grids fail with a clear error. Reader notes appear in the JSON report.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A plain grid loads with every column kept.
- [ ] A grid with a Solis axis column keeps it by default and includes a warning in the reader notes; with the explicit option it is dropped and the note says so.
- [ ] Regression: a grid whose real first intensity column counts up row by row is kept intact (with a warning only).
- [ ] Metadata lines that aren't numbers, before or after the grid, are skipped and counted in the reader notes.
- [ ] Negative values load unchanged.
- [ ] Uneven row lengths raise a clear error naming the row; a value that isn't a number inside the grid raises a clear error naming its position.
- [ ] The CLI exposes the drop-axis-column option, and reader notes appear in the JSON report.
