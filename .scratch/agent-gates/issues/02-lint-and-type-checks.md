# 02: Lint and type checks

**What to build:** `make check` rejects unformatted code, lint findings, unused or blanket suppressions and type errors in the package. `make fix` is the only way formatting and autofixes get applied. The current backlog is cleared, so the gate starts green. See `../spec.md`.

**Blocked by:** 01

**Status:** resolved

- [x] ruff runs in the gate with a fixed rule set (start from polsigns/cadmesh's `E F W I UP B ARG PGH RUF`, plus `NPY` and `PT`), and with a format check. Narrowing the set is a weakening move under the CLAUDE.md protocol.
- [x] mypy runs in strict mode over the package in the gate. Test code is out of scope unless a later decision widens it.
- [x] `make fix` applies ruff autofixes and formatting. No other target changes files.
- [x] The existing backlog is cleared (14 findings and 6 unformatted files when measured on 2026-11-10). Fixes that change behaviour are kept out of this ticket. If one is needed, it gets its own commit, and `make check` and `make check-slow` stay green.
- [x] Proof: a planted unused `noqa`, a planted blanket `type: ignore` and a planted type error each turn `make check` red with the tool's own message. The plants are not committed.
- [x] The tool versions are locked in `uv.lock`.

## Comments

**Owner rulings (owner, 2026-11-10), asked before the change.** Plan: `.scratch/agent-gates/handoffs/02-plan.md`, review: `02-plan-review.md`.

- **Q1 (conftest), approved:** drop the unused `config` argument of `pytest_configure` and rewrap the docstring in `tests/conftest.py`. No `noqa` and no `per-file-ignores`. Commit `2769ee4`.
- **Q2 (scope), approved:** `extend-exclude = [".scratch"]`. The tracked evidence scripts (`.scratch/stripe-detector/evidence/03-premeasure.py`, `03-prototype-p1.py`, 11 findings) stay byte-identical and are not linted.
- **Q3 (scipy typing), approved:** add `scipy-stubs` to the dev group. No `ignore_missing_imports` override.
- **Q4 (approval), yes:** this ticket's text approves the gate-config edits its criteria need: the `Makefile` (criteria 1-3), the new `[tool.ruff]`/`[tool.mypy]` sections (criteria 1-2) and the `ruff`/`mypy`/`scipy-stubs` dev-group pins (criterion 6).
- **Ruff scope (plan B1), covered by Q4:** `include = ["*.py","*.pyi","pyproject.toml"]` keeps Markdown out of ruff's scope. ruff 0.17.4's default `include` would also format the ```` ```python ```` fences in CLAUDE.md, GLOSSARY.md, README.md and `docs/**`, which the ticket never asked for. Ruff never ran on Markdown before this ticket, so this does not narrow an existing gate, and the Q4 ruling covers the new `[tool.ruff]` config.
- **CLAUDE.md:** the gate-config list now names `[tool.ruff]`, `[tool.mypy]` and the `ruff`/`mypy`/`scipy-stubs` pins (strengthening). Commit `cf338f3`.
- **B3/O5, approved:** `make check` runs a `git grep` step (`no-inline-mypy`) that fails on `# mypy: ignore-errors` and `# mypy: disable-error-code` in ruff's scope, because both pass ruff and mypy. It fails closed (review N7): any `git grep` exit other than 0 or 1 fails the gate.

**Baseline (implementer, 2026-11-10, at `2c6ebbd`, with the final `[tool.ruff]` config).** Tools: ruff 0.17.4, mypy 2.4.1, scipy-stubs 1.17.1.5 (<3.12) / 1.18.1.1 (>=3.12).

- `uv run --locked ruff format --check` → `6 files would be reformatted, 15 files already formatted` (`_calibration.py`, `_local_stripes.py`, `tests/cases.py`, `tests/feasibility.py`, `tests/test_analyse.py`, `tests/test_feasibility_gate.py`).
- `uv run --locked ruff check --statistics` → 44 findings: 24 E501, 8 PT011, 5 PT006, 5 I001, 1 ARG001, 1 F401. After `ruff check --fix --exit-zero && ruff format`, 21 remain (8 PT011, 7 E501, 5 PT006, 1 ARG001), cleared by hand in `fe46657`, `78aaff4`, `2769ee4`. The ticket's "14 findings" matched no rule set or line length tried; these numbers replace it.
- `uv run --locked mypy` (strict, `src/denoisifier`) → `Found 19 errors in 5 files (checked 9 source files)` with scipy-stubs (22 in 6 without). Cleared in `d70dc4b` by annotating to runtime types plus 3 `typing.cast`s; prototype `413f08a` (throwaway branch `worktree-agent-a751e3afb8a91be8a`) differs from it only in formatting.
- **No behaviour-changing fix was needed.** No conversion (`float()`, `np.asarray()`) was added for typing; the removed `_A0` import in `analysis.py` was unused. The 18 pre-existing `# noqa: E402` in `tests/feasibility.py` are all used and stay. This ticket adds no suppression.

**Known holes (N4).** `# fmt: skip` / `# fmt: off` pass the gate. A `# type: ignore[code]` in `tests/` is not flagged when unused, because mypy does not check tests (ruff's PGH003 still rejects a blanket one). Both follow from the ticket's scope.

**Gate runs (implementer, 2026-11-10, HEAD `cf338f3-dirty`).** Dirty means uncommitted Markdown under `.scratch/` only: modified `agent-gates/issues/05-required-slow-tier.md`, `stripe-detector/issues/02-stripes-vs-mottle-in-emccd-noise.md` and `07-calibrated-stripe-score.md`, and untracked `agent-gates/handoffs/` and `stripe-detector/handoffs/`. None of it is in the gate's scope (`.scratch` is excluded from ruff and `no-inline-mypy`, and mypy and pytest do not read it).

- `make check` → exit 0. `21 files already formatted`, `All checks passed!`, `Success: no issues found in 9 source files`, `208 passed, 4 deselected in 70.66s (0:01:10)`.
- `make check-slow` (background, log `.scratch/agent-gates/handoffs/02-check-slow.log`) → exit 0, `4 passed, 208 deselected in 2257.86s (0:37:37)`. Started 17:54:23, `/proc/loadavg` `2.32 2.54 2.21`; processes from another project were running (listed in the log), so the run was not on an idle machine. It is green regardless.
- `make lint` → exit 0; `make test-fast` → exit 0, `208 passed, 4 deselected in 81.26s (0:01:21)`. `git status --porcelain` was the same before and after `make check`, `make lint` and `make test-fast` (the caches write their own `.gitignore`).
- `make -n check` shows `uv lock --check`, the `git grep` step, `uv run --locked ruff format --check`, `uv run --locked ruff check`, `uv run --locked mypy`, `uv run --locked pytest`.
- `grep -A2 'name = "ruff"\|name = "mypy"\|name = "scipy-stubs"' uv.lock` → `ruff` `0.17.4`, `mypy` `2.4.1`, `scipy-stubs` `1.17.1.5` and `1.18.1.1`; `uv lock --check` exits 0.
- Fail closed (N7): `make -C <non-git dir> -f <repo>/Makefile no-inline-mypy` → `fatal: not a git repository ...`, `make check: git grep failed (exit 128); inline mypy suppressions not checked`, exit 2.

**Plant proofs (implementer, 2026-11-10, HEAD `cf338f3-dirty`, dirty as above).** One at a time in untracked `src/denoisifier/zz_plant.py`, each through `make check`. Each ended with `make: *** [Makefile:NN: <target>] Error 1`, make exit 2, before pytest ran. The file was deleted afterwards and `git status --porcelain -- src tests` was empty. `git log -p 2c6ebbd..` has no `zz_plant`.

- `x=1` → `unformatted: File would be reformatted`, `--> src/denoisifier/zz_plant.py:1:2`, `1 file would be reformatted, 21 files already formatted`.
- `import os` → ``F401 [*] `os` imported but unused``.
- (a) unused noqa, `X = 1  # noqa: E501` → ``RUF100 [*] Unused `noqa` directive (unused: `E501`)``.
- (b) blanket type: ignore, `A: int = "s"  # type: ignore` → `PGH003 Use specific rule codes when ignoring type issues` (ruff stops make first). `uv run --locked mypy` on the same plant → `src/denoisifier/zz_plant.py:1: error: "type: ignore" comment without error code (consider "type: ignore[assignment]" instead)  [ignore-without-code]`, exit 1.
- (c) type error, `def f() -> int:` / `return "s"` → `src/denoisifier/zz_plant.py:2: error: Incompatible return value type (got "str", expected "int")  [return-value]`.
- (d) `# mypy: ignore-errors` above plant (c) → `src/denoisifier/zz_plant.py:1:# mypy: ignore-errors`, `make check: inline mypy suppression found (ticket agent-gates/02)`. Same with `# mypy: disable-error-code="return-value"` → `src/denoisifier/zz_plant.py:1:# mypy: disable-error-code="return-value"` and the same message.
- Blanket `X = 1  # noqa` → ``RUF100 [*] Unused blanket `noqa` directive`` and ``PGH004 Use specific rule codes when using `noqa` ``.
- Unused `X: int = 1  # type: ignore[assignment]` → ruff `All checks passed!`, then mypy `error: Unused "type: ignore" comment  [unused-ignore]`.
- `make fix` on `import sys` / `import os` / `x=os.sep` → `Found 2 errors (2 fixed, 0 remaining).`, `1 file reformatted, 21 files left unchanged`, exit 0. Result: `import os`, blank line, `x = os.sep`. No tracked file changed.

**Code review fix: every inline mypy config comment (fixer, 2026-11-10, on `02f6999-dirty`, dirty as in Gate runs plus the uncommitted `Makefile` change).** The review found that `no-inline-mypy` matched only `ignore-errors` and `disable-error-code`. mypy also accepts the underscore spellings (`# mypy: ignore_errors=True`, `# mypy: disable_error_code=...`) and per-file switches that loosen strict mode (`# mypy: allow-untyped-defs`), and all of them pass ruff and mypy. mypy reads inline config only from lines that start with `# mypy: ` (`mypy/util.py` `get_mypy_comments`). The step now rejects any `#\s*mypy:` in its pathspec, a superset of that. Its message is now `inline mypy config comment found`. Strengthening, covered by Q4 and B3/O5. `git grep --untracked -nE '#\s*mypy:' -- '*.py' '*.pyi' ':!.scratch'` on the clean tree → exit 1, no matches.

- Plants, one at a time in untracked `src/denoisifier/zz_plant.py`, each placed above a body that strict mypy rejects (`def f() -> int:` / `return "s"`, or untyped `def g(x):` / `return x`, which without the comment gives `error: Function is missing a type annotation  [no-untyped-def]`). For each: `uv run --locked mypy` → exit 0 and `ruff check` → exit 0, so the hole was real. `make check` → `src/denoisifier/zz_plant.py:1:<comment>`, `make check: inline mypy config comment found (ticket agent-gates/02)`, `make: *** [Makefile:29: no-inline-mypy] Error 1`, make exit 2. The spellings were `# mypy: ignore_errors=True`, `# mypy: disable_error_code="return-value"`, `# mypy: allow-untyped-defs`, `# mypy: allow_untyped_defs=True`, `# mypy: ignore-errors` and `# mypy: disable-error-code="return-value"`.
- The file was deleted after each plant, and `git status --porcelain -- src tests` was empty afterwards. No plant is committed.
- Still fails closed: `make -C <non-git dir> -f <repo>/Makefile no-inline-mypy` → `fatal: not a git repository ...`, `make check: git grep failed (exit 128); inline mypy config comments not checked`, exit 2.
