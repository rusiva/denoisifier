# 02 plan: lint and type checks

- Ticket: `.scratch/agent-gates/issues/02-lint-and-type-checks.md`
- Spec: `.scratch/agent-gates/spec.md`
- BASE: `2c6ebbd`
- Review: `.scratch/agent-gates/handoffs/02-plan-review.md`. B1, B2, B3 (via O5) and N1-N5 are folded in below. N6 needs no change.
- Prototype: `.scratch/agent-gates/handoffs/02-prototype-p1.md`, reference commit `413f08a` on branch `worktree-agent-a751e3afb8a91be8a` (throwaway, not for merge).
- Status: **settled.** The owner ruled on every open question (see "Owner rulings"). Nothing is open.

## Owner rulings (2026-11-10)

Copy these into the ticket's `## Comments` in commit 8.

- **Q1 (conftest), approved:** drop the unused `config` argument of `pytest_configure` and rewrap the docstring in `tests/conftest.py`. No `noqa` and no `per-file-ignores`.
- **Q2 (scope), approved:** `extend-exclude = [".scratch"]`. The tracked evidence scripts stay byte-identical and are not linted.
- **Q3 (scipy typing), approved:** add `scipy-stubs` to the dev group. There is no `ignore_missing_imports` override.
- **Q4 (approval), yes:** the ticket's text approves the gate-config edits its criteria need: the Makefile, the new `[tool.ruff]`/`[tool.mypy]` sections, and the dev-group pins. Record this in the ticket's Comments with a pointer to the criteria.
- **CLAUDE.md gate-config list:** include the addition (see "CLAUDE.md").
- **B3/O5, approved:** `make check` gets a `git grep` step that fails on `# mypy: ignore-errors` and `# mypy: disable-error-code` in the linted scope, with a planted proof (AC-5d).

## Findings that shape the plan

Everything was measured 2026-11-10 at `2c6ebbd` without changing any repo file. The review re-measured it on a `git archive HEAD` copy, and I re-measured the path-less commands with the final `[tool.ruff]` block below.

**F1. Tool versions:** ruff 0.17.4, mypy 2.4.1 (compiled), scipy-stubs 1.17.1.5. scipy-stubs follows the lock's existing Python fork: 1.17.1.5 for <3.12 and 1.18.1.1 for >=3.12, matching scipy 1.17.1 and 1.18.1. numpy 2.4.6 ships its own types. Per the review, `uv lock` adds only ast-serialize, librt, mypy, mypy-extensions, numpy-typing-compat, optype, pathspec, ruff, scipy-stubs and typing-extensions.

**F2. Formatting (B1 folded in).** ruff 0.17.4's default `include` also picks up `*.md`: it formats ```` ```python ```` fences in CLAUDE.md, GLOSSARY.md, README.md, `docs/**`. That is scope the ticket never asked for. So `[tool.ruff]` sets `include = ["*.py", "*.pyi", "pyproject.toml"]`, and Markdown is out of the format gate. With the final config, the Makefile's actual path-less `ruff format --check` reports **`6 files would be reformatted, 15 files already formatted`**. The 6 are `src/denoisifier/_calibration.py`, `src/denoisifier/_local_stripes.py`, `tests/cases.py`, `tests/feasibility.py`, `tests/test_analyse.py` and `tests/test_feasibility_gate.py`, which matches the ticket's 6. Ruff's default line length of 88 gives 10 files and 62 E501 findings. 120 gives 7 files, because the formatter re-joins lines already wrapped at 100. The code was written to 100, so 100 is chosen.

**F3. Lint backlog (N1, N5 folded in).** Path-less `ruff check --statistics` with the final config finds **44 findings** before any fix: 24 E501, 8 PT011, 5 PT006, 5 I001, 1 ARG001, 1 F401. The I001 count is 5, not 7, because `src = ["src", "tests"]` makes the test helpers first-party. After `ruff check --fix --exit-zero && ruff format`, **21 remain**:

| rule | n | where | fix |
|---|---|---|---|
| PT011 `pytest.raises(ValueError)` too broad | 8 | `test_analyse.py` 97,102,109,116; `test_calibration.py` 26,32,39; `test_synthetic.py` 88 | add `match=` (rules below) |
| E501 | 7 | `_calibration.py:55` (f-string in `raise ValueError`), `tests/conftest.py:1` (docstring), `tests/feasibility.py` 227,228,237, `test_feasibility_gate.py:120`, `truth_match.py:1` (docstring) | rewrap. Split the f-string by implicit concatenation so the message stays byte-identical |
| PT006 parametrize names not a tuple | 5 | `test_analyse.py` 42,213,235; `test_synthetic.py` 26,99 | change `"a,b"` to `("a", "b")` by hand (ruff marks it unsafe). Test ids do not change |
| ARG001 unused `config` | 1 | `tests/conftest.py:6` | Q1 ruling: drop the argument |

Line numbers in the table are after the format. The safe autofixes are 5 I001 and 1 F401, which removes `_A0`, imported but unused in `src/denoisifier/analysis.py:12`. It appears there only in a comment, and nothing imports `denoisifier.analysis._A0`, including the `.scratch` evidence scripts. Removing it changes no behaviour.

**PT011 `match=` rules (N2).** `match` is a regex. Take it from the code's own `raise` on the path under test, not from a numpy `ValueError` raised elsewhere. The messages contain `(`, `.` and interpolated numbers (e.g. `_calibration.py:55`), so use `re.escape(...)` on a literal or a fixed literal prefix. Check each test still fails when the matched `raise` is removed: temporarily comment it out, run, then revert.

The ticket's "14 findings" matched no rule set or line length I tried. Comments record the numbers above with their commands, not 14.

**F4. Existing suppressions.** `tests/feasibility.py` has 18 `# noqa: E402` on the imports after the `OMP_NUM_THREADS` loop. With `E` selected, all 18 are used, so RUF100 does not flag them. They predate this ticket and stay. No `type: ignore` and no inline `# mypy:` comment exists. This plan adds no suppression.

**F5. mypy backlog and the P1 prototype (B2 folded in).** `mypy` (strict, package only) gives 22 errors in 6 files without stubs. 3 of them are `import-untyped` for scipy. With scipy-stubs: **`Found 19 errors in 5 files (checked 9 source files)`**. All are `no-untyped-def`/`no-untyped-call`/`type-arg`. The prototype annotated them to their runtime types. That exposed 4 new errors, which 3 `typing.cast`s clear. Result: `Success: no issues found in 9 source files`. **No runtime conversion is needed.** Commit 6 is +22/-10 lines in 5 files:
- `synthetic.py`: `_F64 = NDArray[np.float64]`. `_emccd`, `_profile`, `_mottle`, `_grf`, `_standardise` take and return `_F64`. `rng: np.random.Generator`, `shape: tuple[int, int]`, `kind: MottleKind`. Two casts: the `_profile` return (`cast(_F64, np.exp(...))`, because the numpy ufuncs on Python floats are stubbed `Any`) and the `_standardise` return (`a.mean()`/`a.std()` are stubbed `Any`).
- `_local_stripes.py`: `_window(across: NDArray[np.float64], along: NDArray[np.float64], period: float) -> NDArray[np.float64]`. Third cast: `cast(NDArray[np.float64], ...)` on the `self.fx`/`self.fy` assignments in `_Spectrum.__init__`, because `fftfreq` is stubbed `NDArray[floating[Any]]`. Add a one-line comment. The new `_window` signature is 107 characters, so run `make fix` (or `uv run --locked ruff format`) before committing.
- `_calibration.py`: `_false_alarm_count(...) -> rv_discrete_frozen`. It is imported from `scipy.stats._distn_infrastructure` under `if TYPE_CHECKING:`, so it has no runtime import effect.
- `report.py:27`: `dict[str, bool | float | None]`. The body already converts with `bool()`/`float()`.
- `frame_io.py:24,33`: `os.PathLike[str]`. No caller in `src` or `tests` passes a bytes path.

**Rule for commit 6 (B2):** each annotation states the type the code returns today (`np.float64`, `NDArray[np.float64]`, the scipy-stubs frozen type). Where mypy cannot follow, use `typing.cast`, which does nothing at runtime. A `float()`, `int()`, `np.asarray()` or any other conversion added to satisfy mypy is a **behaviour change**. It goes into its own commit (see "Behaviour-changing fixes"). The prototype shows none is needed, so if the implementer finds itself adding one, it has drifted from `413f08a` and should compare against it.

**F6. Plant messages, measured** with this config:
- unused `# noqa: E501`: `RUF100 [*] Unused \`noqa\` directive (unused: \`E501\`)`
- blanket `# noqa`: `RUF100 [*] Unused blanket \`noqa\` directive` and `PGH004 Use specific rule codes when using \`noqa\``
- blanket `# type: ignore`: ruff reports `PGH003 Use specific rule codes when ignoring type issues`. mypy reports `"type: ignore" comment without error code (consider "type: ignore[assignment]" instead)  [ignore-without-code]` when the comment covers a real error, and `Unused "type: ignore" comment  [unused-ignore]` when it does not.
- type error: `error: Incompatible return value type (got "str", expected "int")  [return-value]`
- inline mypy config (B3): ruff and mypy both pass `# mypy: ignore-errors` and `# mypy: disable-error-code="return-value"`, so they need the `git grep` step. Measured on a scratch copy with the exact recipe below. An untracked `src/.../zz_plant.py` and an untracked `tests/zz2.py` each print `path:line:# mypy: ...`, then `make check: inline mypy suppression found (ticket agent-gates/02)`, and make exits 2. A file under `.scratch/` is ignored. The clean tree exits 0.

**F7. Caches.** `.ruff_cache/` and `.mypy_cache/` each write their own `.gitignore` containing `*`, so no `.gitignore` edit is needed (verified in AC-3).

**F8. Tracked Python outside the package:** `.scratch/stripe-detector/evidence/03-premeasure.py` and `03-prototype-p1.py` (11 findings). Excluded by the Q2 ruling.

**Known holes, stated in Comments (N4):** `# fmt: skip` and `# fmt: off` (formatter suppressions) pass the gate. So does a `# type: ignore[code]` in `tests/`: mypy does not check tests, so an unused one there is never flagged, although ruff's PGH003 still rejects a blanket one. Both follow from the ticket's scope: mypy covers the package only, and no rule rejects formatter pragmas.

## Design choices

### pyproject.toml

```toml
[dependency-groups]
dev = [
    "mypy>=2.4.1",
    "pytest>=9.2.0",
    "pytest-timeout>=2.4.0",
    "ruff>=0.17.4",
    "scipy-stubs>=1.17.1.5",
]

# Lint and format gate (ticket agent-gates/02). Editing this or [tool.mypy] is a gate-config
# change: owner approval (CLAUDE.md). Narrowing `select` or `include`, or adding `ignore`,
# `per-file-ignores` or `extend-exclude` entries, is a weakening move.
[tool.ruff]
line-length = 100
include = ["*.py", "*.pyi", "pyproject.toml"]   # code only; Markdown fences are not gated
src = ["src", "tests"]                          # test helpers (cases, borderline, truth_match) sort as first-party
extend-exclude = [".scratch"]                   # evidence records stay byte-identical (owner, 2026-11-10)

[tool.ruff.lint]
# polsigns/cadmesh's set minus S (the ticket's list), plus NPY and PT.
# RUF100 rejects unused noqa; PGH003/PGH004 reject blanket type: ignore / noqa.
select = ["E", "F", "W", "I", "UP", "B", "ARG", "PGH", "RUF", "NPY", "PT"]

# Type gate: strict, package only (test code out of scope until a later decision widens it).
# Inline `# mypy:` suppressions are rejected by the Makefile's no-inline-mypy step.
[tool.mypy]
strict = true                                  # includes warn_unused_ignores
files = ["src/denoisifier"]
enable_error_code = ["ignore-without-code"]    # mypy's own rejection of a blanket type: ignore
```

- No `target-version`: ruff reads it from `requires-python = ">=3.11"`. No `python_version` for mypy: it uses the locked 3.11 interpreter.
- No `ignore` and no `per-file-ignores`. No `[[tool.mypy.overrides]]` (Q3 ruling).
- The pins use the repo's `>=` floor convention. `uv.lock` holds the exact versions, and every target runs `uv run --locked`. Check that `uv lock`'s "Added" lines name only the packages in F1.

### Makefile

```make
# Agent gates (tickets agent-gates/01-02). Editing this file is a gate-config change: owner approval (CLAUDE.md).
UV     := uv run --locked
PYTEST := $(UV) pytest

.PHONY: check check-slow test-fast fix lock-check lint no-inline-mypy

check: lock-check lint      ## gate: lock, format, lint, types, then every non-slow test
	$(PYTEST)

check-slow: lock-check      ## the slow tier (duration: tests/test_feasibility_gate.py): background, nothing else meanwhile
	$(PYTEST) -m slow

test-fast:                  ## inner loop: stop at first failure, failures first
	$(PYTEST) -x --ff

lock-check:
	uv lock --check

lint: no-inline-mypy        ## read-only: format check, ruff, mypy (scope and rules: pyproject.toml)
	$(UV) ruff format --check
	$(UV) ruff check
	$(UV) mypy

no-inline-mypy:             ## file-wide mypy suppressions pass both tools; reject them in the linted scope
	@if git grep --untracked -nE '#\s*mypy:\s*(ignore-errors|disable-error-code)' -- '*.py' '*.pyi' ':!.scratch'; then \
	  echo "make check: inline mypy suppression found (ticket agent-gates/02)"; exit 1; fi

fix:                        ## the ONLY target that changes files: ruff autofixes, then formatting
	$(UV) ruff check --fix --exit-zero
	$(UV) ruff format
```

- `no-inline-mypy`'s scope matches ruff's: every `*.py`/`*.pyi` except `.scratch/`. That covers `tests/` too, so the step stays right if mypy's scope is later widened. `--untracked` makes it see new, not-yet-added files (an agent's fresh file, and the plants). Ignored files (`.venv`) are skipped. The pathspec leaves out Markdown, so docs that quote the directive (this plan, the ticket) do not trip it. The step is read-only.
- `lint` runs before pytest: it takes seconds, and a red lint stops the run before the 80 s suite. Make stops at the first failing line, so a format failure hides later findings. The loop is `make fix`, then `make check`.
- Scope lives in pyproject: `ruff` with no path means the project root, filtered by `include`/`extend-exclude`, and `mypy` with no path means `files`. The only scope outside pyproject is `no-inline-mypy`'s pathspec, which mirrors ruff's.
- `ruff check` in `lint` never gets `--fix`. Ruff's default `fix = false` is left as is.
- `fix` uses `--exit-zero` so findings ruff cannot fix (PT011, E501) are printed and `ruff format` still runs. It does not use `--unsafe-fixes`.
- `check-slow` and `test-fast` do not lint. `check-slow` is the measurement tier, and `test-fast` is the inner loop.

### CLAUDE.md (owner: include)

In the weakening-move bullet, change the gate-config list to: "... editing gate config (the `Makefile`, `[tool.pytest.ini_options]`, `[tool.ruff]`, `[tool.mypy]`, `tests/conftest.py`, and the `pytest`/`pytest-timeout`/`ruff`/`mypy`/`scipy-stubs` pins and other `[dependency-groups].dev` gate tools)". It is a strengthening edit and goes in commit 7.

## Behaviour-changing fixes

None is expected, and the P1 prototype confirmed none is needed for typing. Mechanical fixes: formatting, import sorting, removing the `_A0` import, E501 rewraps (strings byte-identical), PT006 tuples, annotations, and `typing.cast`. Test strengthening (PT011 `match=`) is normal test work and gets its own commit.

If one turns out to be needed, it gets its own commit (6a, before 6). Examples: a runtime conversion added for typing (B2), or a real bug exposed by an annotation. The commit message names the behaviour change, `make check` and a background `make check-slow` are green on that commit, and a line goes in the ticket's Comments. If it would also change a tolerance, a threshold or a saved measurement, stop and ask the owner.

## Commit sequence

Every commit is green on `make check` as it stands at that commit; `lint` is wired in only at 7 (review N6). Run `make test-fast` after each change.

1. **Add ruff, mypy and scipy-stubs to the dev group; lock.** `pyproject.toml` dev group, `uv.lock`.
2. **Configure ruff; apply `ruff format` and the safe autofixes.** The `[tool.ruff]` blocks, plus the output of `uv run --locked ruff check --fix --exit-zero && uv run --locked ruff format` (the future `make fix`). The commit is purely mechanical, and its message says so. A reviewer can reproduce it by running the two commands on the parent and diffing. It touches the 6 files in F2 and the I001/F401 files. `synthetic.py` and `spectrum.py` gain only a blank line after their imports. `tests/conftest.py` is not touched.
3. **Clear the remaining lint by hand:** PT006 tuples and the E501 rewraps, except conftest's. Mechanical.
4. **Name the expected message in every `pytest.raises(ValueError)`** (PT011, rules under F3). Test strengthening.
5. **`tests/conftest.py`:** `def pytest_configure() -> None:` and a rewrapped docstring (Q1 ruling). Behaviour is identical: pluggy accepts a hookimpl that takes a subset of the hookspec's arguments. Check: `make test-fast` is green, and `PYTHONWARNINGS` still reaches the CLI subprocesses (the `test_cli.py` tests stay green).
6. **Configure mypy strict over the package; annotate to runtime types, with 3 `cast`s** (F5; reference diff `413f08a`). `[tool.mypy]` plus `synthetic.py`, `_local_stripes.py`, `_calibration.py`, `report.py`, `frame_io.py`. Run `make fix` before committing (the `_window` E501).
7. **Wire `lint` and `no-inline-mypy` into `make check` and ruff into `make fix`; extend the CLAUDE.md gate-config list.** `Makefile`, `CLAUDE.md`. From here `make check` enforces everything.
8. **Record ticket 02 evidence and tick its criteria.** In the ticket's `## Comments`: the owner rulings (Q4's approval stated explicitly), the F2/F3/F5 baseline commands and counts, the prototype pointer, the known holes (N4), the plant transcripts and the gate quotes.

`make check-slow` runs once, after commit 7, in the background on an idle machine. Commits 2 and 6 touched the detector, generator and calibration files, and ticket 05's hash is not in yet. The last run took 37 min 15 s (`.archived/01-check-slow-fix.log`). Run nothing else meanwhile. Log to `.scratch/agent-gates/handoffs/02-check-slow.log`, with `/proc/loadavg` at the start.

## Acceptance criteria -> change -> verification

Every proof runs the real `make check` (or `make fix`) on the real tree. Plants go one at a time in an untracked `src/denoisifier/zz_plant.py`, which is inside ruff's, mypy's and `no-inline-mypy`'s scope, and are deleted afterwards. After each proof, `git status --porcelain -- src tests` must be empty. Each transcript goes in Comments: command, the tool's lines, make's `Error 1` line, exit status 2.

1. **ruff with the fixed rule set and a format check.** `make -n check` shows `ruff format --check` and `ruff check` under `uv run --locked`. Plant `x=1`: `make check` prints `Would reformat: src/denoisifier/zz_plant.py` and `1 file would be reformatted`, exit 2. Plant an unused `import os`: `F401`. The `select` line equals the ticket's list.
2. **mypy strict over the package.** `make -n check` shows `mypy`. `make check` prints `Success: no issues found in 9 source files`. Test code is not in `files`.
3. **`make fix` applies fixes and formatting; nothing else changes files.** Plant `import sys\nimport os\nx=os.sep`. Expected diff after `make fix` (N3): `import sys` is deleted (F401, a safe fix), and `x=os.sep` becomes `x = os.sep`. The result is `import os\n\nx = os.sep\n` or whatever ruff prints; quote it. `git diff` on tracked files stays empty. Then, on a clean tree, `make check`, `make test-fast` and `make lint` each leave `git status --porcelain` unchanged (F7).
4. **Backlog cleared, gate starts green.** `make check` at commit 7 exits 0. It prints `21 files already formatted` (the 15 plus the 6 now formatted; quote what is printed), `All checks passed!`, `Success: no issues found in 9 source files`, and pytest's summary (expect `208 passed, 4 deselected`). `make check-slow` in the background exits 0 with `4 passed, 208 deselected`. Comments list the before-counts with their path-less commands: F2 `6 files would be reformatted, 15 files already formatted`; F3 44, then 21 after the fix; F5 19 errors. They also state that no behaviour-changing fix was needed, or name the separate commit.
5. **Plant proofs** (`make check`, each red with the tool's own message, exit 2):
   a. Unused noqa, `X = 1  # noqa: E501`: `RUF100 [*] Unused \`noqa\` directive (unused: \`E501\`)`.
   b. Blanket type: ignore, `A: int = "s"  # type: ignore`: `PGH003 Use specific rule codes when ignoring type issues` (ruff stops make first). To show mypy's layer as well, run `uv run --locked mypy` on the same plant: `[ignore-without-code]`.
   c. Type error, `def f() -> int:\n    return "s"`: `error: Incompatible return value type (got "str", expected "int")  [return-value]`.
   d. Inline mypy suppression (B3/O5). Use `# mypy: ignore-errors` on line 1, with plant (c) below it, so that without the step the file would pass both tools. Output: `src/denoisifier/zz_plant.py:1:# mypy: ignore-errors`, then `make check: inline mypy suppression found (ticket agent-gates/02)`. Repeat with `# mypy: disable-error-code="return-value"`.
   Extras, cheap: blanket `# noqa` gives PGH004. An unused `# type: ignore[assignment]` on a clean line gives mypy `[unused-ignore]`.
   No plant is committed: `git log -p 2c6ebbd..` shows no `zz_plant`.
6. **Tool versions locked.** `grep -A2 'name = "ruff"\|name = "mypy"\|name = "scipy-stubs"' uv.lock` shows the exact versions. `uv lock --check` exits 0. Ticket 01 already proved the lock is enforced (a stale lock makes `uv lock --check` fail).

Handoff quotes follow CLAUDE.md: command, exit status, pytest's summary line, and `git rev-parse --short HEAD` (plus `-dirty`).

Settled without a question (from the draft, unchallenged by review): `line-length = 100` (F2); `src = ["src", "tests"]`; lint before pytest in `check`; no `--unsafe-fixes` in `fix`; one `check-slow` run, after commit 7.
