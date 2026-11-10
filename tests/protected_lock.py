"""Protected-number lockfile check (ticket agent-gates/03).

Every number that decides a verdict or a pass is recorded, with its live value,
in ``protected_numbers.lock``. The protected places are every module- and
class-level name in the ``denoisifier`` package, and every module-level name in
``tests/protected.py``. A name counts as a number when its live value holds an
int, float, complex, NumPy number or range anywhere inside it (tuples, lists,
dicts, NamedTuples, dataclasses and arrays are searched).

``check`` returns one message per mismatch: a value that differs from the
lockfile, a number missing from the lockfile, or a lockfile entry whose name no
longer exists. Values are compared as canonical text from the live objects,
not from the source, so a number reached through an expression or an import is
still caught.

Editing this file, the lockfile or ``test_protected_numbers.py`` is a
weakening move: owner approval (CLAUDE.md).
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import pkgutil
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

import numpy as np

import denoisifier

LOCKFILE = Path(__file__).with_name("protected_numbers.lock")
SEP = " :: "
# Importing denoisifier.__main__ runs the CLI, so it is not scanned.
_NOT_IMPORTABLE = {"denoisifier.__main__"}


def protected_modules() -> list[ModuleType]:
    """Every importable ``denoisifier`` module, then ``tests/protected.py``."""
    names = ["denoisifier"] + [
        m.name for m in pkgutil.walk_packages(denoisifier.__path__, prefix="denoisifier.")
    ]
    names = sorted(n for n in names if n not in _NOT_IMPORTABLE)
    return [importlib.import_module(n) for n in [*names, "protected"]]


def canonical(value: object) -> str:
    """Exact, stable text for a value: floats by their shortest round-trip repr,
    containers element by element, arrays with their dtype and shape."""
    if value is None or isinstance(value, bool | str | bytes):
        return repr(value)
    if isinstance(value, np.ndarray):
        return f"ndarray[{value.dtype}, {value.shape}]({canonical(value.tolist())})"
    if isinstance(value, np.generic):
        return canonical(value.item())
    if isinstance(value, int | float | complex | range):
        return repr(value)
    if isinstance(value, tuple) and hasattr(value, "_fields"):
        return _fields_text(type(value).__name__, value._asdict().items())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        items = ((f.name, getattr(value, f.name)) for f in dataclasses.fields(value))
        return _fields_text(type(value).__name__, items)
    if isinstance(value, tuple):
        inner = ", ".join(canonical(v) for v in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, list):
        return "[" + ", ".join(canonical(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{canonical(k)}: {canonical(v)}" for k, v in value.items()) + "}"
    return f"<{type(value).__module__}.{type(value).__qualname__}>"


def _fields_text(name: str, items: Iterable[tuple[str, object]]) -> str:
    return name + "(" + ", ".join(f"{k}={canonical(v)}" for k, v in items) + ")"


def holds_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float | complex | range | np.number):
        return True
    if isinstance(value, np.ndarray):
        return value.dtype.kind in "iufc" or any(holds_number(v) for v in value.flat)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return any(holds_number(getattr(value, f.name)) for f in dataclasses.fields(value))
    if isinstance(value, tuple | list):
        return any(holds_number(v) for v in value)
    if isinstance(value, dict):
        return any(holds_number(k) or holds_number(v) for k, v in value.items())
    return False


def _bound_names(body: list[ast.stmt]) -> list[str]:
    """Names a module or class body binds by assignment (any depth, outside
    functions and nested classes), in source order."""
    names: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            pass

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            pass

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            pass

        def visit_Lambda(self, node: ast.Lambda) -> None:
            pass

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value is not None:  # a bare annotation binds nothing
                self.generic_visit(node)

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Store) and node.id not in names:
                names.append(node.id)

    for stmt in body:
        Visitor().visit(stmt)
    return names


def live_numbers(module: ModuleType) -> dict[str, str]:
    """``{qualified name: canonical value}`` for every number the module binds
    at module level, or in a top-level class body (``Class.name``). Names it
    imports are left to the module that defines them."""
    assert module.__file__ is not None
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    scopes: list[tuple[str, object, list[ast.stmt]]] = [("", module, tree.body)]
    scopes += [
        (f"{node.name}.", getattr(module, node.name), node.body)
        for node in tree.body
        if isinstance(node, ast.ClassDef) and hasattr(module, node.name)
    ]
    for prefix, owner, body in scopes:
        for name in _bound_names(body):
            if hasattr(owner, name):
                value = getattr(owner, name)
                if holds_number(value):
                    found[f"{module.__name__}{SEP}{prefix}{name}"] = canonical(value)
    return found


def parse_lock(text: str) -> tuple[dict[str, str], list[str]]:
    """``({"module :: name": value}, problems)`` from the lockfile text."""
    entries: dict[str, str] = {}
    problems: list[str] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(SEP, 2)
        if len(parts) != 3:
            problems.append(f"line {line_no} is not `module :: name :: value`: {raw!r}")
            continue
        key = SEP.join(p.strip() for p in parts[:2])
        if key in entries:
            problems.append(f"line {line_no}: {key} is listed twice")
        entries[key] = parts[2].strip()
    return entries, problems


def check(lock_text: str, modules: Iterable[ModuleType]) -> list[str]:
    """One message per difference between the lockfile and the live numbers."""
    entries, problems = parse_lock(lock_text)
    live: dict[str, str] = {}
    scanned: set[str] = set()
    for module in modules:
        scanned.add(module.__name__)
        live.update(live_numbers(module))
    for key, value in live.items():
        if key not in entries:
            problems.append(f"{key} = {value} is a number that is not in the lockfile")
        elif entries[key] != value:
            problems.append(f"{key} changed: lockfile {entries[key]}, live {value}")
    for key, value in entries.items():
        module_name = key.split(SEP, 1)[0]
        if key not in live:
            where = "is no longer a number" if module_name in scanned else "is in no scanned module"
            problems.append(f"{key} (lockfile {value}) {where}, or was renamed or removed")
    return problems
