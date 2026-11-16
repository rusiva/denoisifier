# 02 prototype: P1 (annotate the mypy backlog; does any fix need a runtime conversion?)

- Question: plan-review P1 (with B2). After the plan's commit-6 annotations, how many mypy errors remain or newly appear, and can each be fixed by annotation or `typing.cast` alone?
- Prototype: throwaway branch `worktree-agent-a751e3afb8a91be8a`, commit `413f08a` (parent `2c6ebbd`). Not for merge.
- Tools: mypy 2.4.1, scipy-stubs 1.17.1.5, numpy 2.4.6, scipy 1.17.1, Python 3.11 (`uv run --no-project --with ...`, `mypy --no-incremental`), with the plan's `[tool.mypy]` block verbatim.

## Verdict

**No fix needs a runtime conversion.** Every error clears with an annotation or `cast`. No `float()`, `int()` or `asarray` was added. Commit 6a is not needed for typing. Commit 6 is small: 5 files, +22/-10 lines in `src`. It does not need its own review step.

## Counts

| step | mypy result |
|---|---|
| baseline, plan config + scipy-stubs | `Found 19 errors in 5 files (checked 9 source files)` (matches F5) |
| after annotating to runtime types | `Found 4 errors in 2 files`: these 4 newly surfaced |
| after 3 `cast`s | `Success: no issues found in 9 source files` |

The 4 errors that newly surfaced, and the fix for each:

1. `synthetic.py:191` (`_profile` return) `[no-any-return]`. `np.deg2rad(rng.uniform(...))`, `np.cos` and `np.where` on Python floats are stubbed as `Any`, so the whole expression is `Any`. Runtime: `ndarray` float64 (checked). Fix: `cast(_F64, np.exp(...))`.
2. `synthetic.py:219` (`_standardise` return) `[no-any-return]`. `a.mean()` and `a.std()` are stubbed `Any`. Runtime: float64 ndarray. Fix: `cast(_F64, ...)`.
3. and 4. `_local_stripes.py:87` (`_window(self.fx, self.fy, ...)`) `[arg-type]` x2. numpy stubs `fftfreq` as `NDArray[floating[Any]]`. Runtime: float64. Fix: `cast(NDArray[np.float64], ...)` on the `self.fx`/`self.fy` assignments in `_Spectrum.__init__`, with a one-line comment. The other option is to widen `_window` to `floating[Any]`, but then its return would not match float64 either.

## Annotations chosen (each is the runtime type, checked by a script)

- `synthetic.py`: `_F64 = NDArray[np.float64]`. `_emccd`, `_profile`, `_mottle`, `_grf` and `_standardise` take and return `_F64`. `rng: np.random.Generator`, `shape: tuple[int, int]`, `kind: MottleKind`. All 5 return float64 ndarrays at runtime, including `_emccd` with `em_gain=1` (`n.astype(float)`).
- `_local_stripes.py:_window`: float64 arrays in and out, `period: float`.
- `_calibration.py:_false_alarm_count -> rv_discrete_frozen`: the runtime class is `scipy.stats._distn_infrastructure.rv_discrete_frozen`. scipy-stubs reveals `rv_discrete_frozen[betabinom_gen, float | float64]`, and the bare name passes strict. It is imported from a private module, so the import sits under `if TYPE_CHECKING:` and has no runtime import effect.
- `report.py:27`: `dict[str, bool | float | None]`. The body already converts with `bool()`/`float()`, so there is no change.
- `frame_io.py:24,33`: `os.PathLike[str]`. Annotation only. A bytes `PathLike` would still work at runtime, but mypy would now reject it at call sites. No caller in `src` or `tests` passes one.

## Side notes for the implementer

- `_window`'s new signature is 107 chars (E501). Commit 6 comes after the format commit, so run `make fix`/`ruff format` on it.
- Gate on the prototype tree (`2c6ebbd` + uncommitted annotations, i.e. `2c6ebbd-dirty`, later committed as `413f08a`): `make test-fast` -> exit 0, `208 passed, 4 deselected in 109.04s (0:01:49)`. `make check` and `make check-slow` were not run. Annotations and `cast` have no runtime effect, but the plan's single check-slow after commit 7 still covers commit 6.
