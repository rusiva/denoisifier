"""The slow-tier stamp (ticket agent-gates/05). Stdlib only.

A change to anything that affects detector output can't reach a green
`make check` without a green `make check-slow` on that same code:

    python tests/slow_stamp.py run [--root PATH] -- <pytest command>   # make check-slow
    python tests/slow_stamp.py check [--root PATH]                     # last step of make check

`run` takes an exclusive per-tree lock, refuses while spawn workers of this
tree's venv are running, hashes STAMPED_FILES, runs the command in its own
process group with CHECK_SLOW_RUN_ID set, and writes the stamp only when the
command exits 0, the hashes are unchanged and the slow tier wrote its
measurement with the same run id. A red, interrupted or concurrent run writes
nothing. `check` fails when the stamp is missing or a stamped file differs.

STAMPED_FILES is the one list of the files that affect detector output; it and
the stamp rule are protected surfaces (CLAUDE.md). Local state lives in .gate/
(git-ignored): the lock, the stamp and the measurement.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import FrameType

from protected import BENCH_IDLE_LOAD

ROOT = Path(__file__).resolve().parents[1]

# The files that affect detector output, repo-relative. Every file in
# src/denoisifier/ is in exactly one of STAMPED_FILES and NOT_STAMPED_SRC
# (test_stamped_files_cover_the_slow_tier).
STAMPED_FILES: tuple[str, ...] = tuple(
    sorted(
        [
            # detector
            "src/denoisifier/__init__.py",
            "src/denoisifier/analysis.py",
            "src/denoisifier/_local_stripes.py",
            "src/denoisifier/_data_quality.py",
            # generator
            "src/denoisifier/synthetic.py",
            # calibration
            "src/denoisifier/_calibration.py",
            "src/denoisifier/calibration.py",
            # the slow tier and its tests/ imports (protected.py whole: ruling Q3)
            "tests/test_slow_regression.py",
            "tests/feasibility.py",
            "tests/cases.py",
            "tests/protected.py",
            "tests/seed_guard.py",
            "tests/conftest.py",
            "tests/slow_stamp.py",
            # how it runs, and numerics
            "Makefile",
            "pyproject.toml",
            "uv.lock",
            ".python-version",
        ]
    )
)
# Package files that do not affect detector output.
NOT_STAMPED_SRC: tuple[str, ...] = tuple(
    f"src/denoisifier/{name}"
    for name in ("cli.py", "report.py", "frame_io.py", "__main__.py", "py.typed")
)

GATE_DIR = ".gate"
LOCK = f"{GATE_DIR}/check-slow.lock"
STAMP = f"{GATE_DIR}/check-slow-stamp.json"
MEASUREMENT = f"{GATE_DIR}/check-slow-measurement.json"
RUN_ID_VAR = "CHECK_SLOW_RUN_ID"


def loadavg() -> str:
    """/proc/loadavg as one line, or "unavailable"."""
    try:
        return Path("/proc/loadavg").read_text().strip()
    except OSError:
        return "unavailable"


def busy_warning(label: str, line: str) -> str | None:
    """The heavy gates' warning when the 1-min load in ``line`` (a loadavg()
    line) is above BENCH_IDLE_LOAD: their timings assume an idle machine."""
    if line == "unavailable" or float(line.split()[0]) <= BENCH_IDLE_LOAD:
        return None
    return f"{label}: warning: load average {line} at start; the machine is not idle"


MISSING = "MISSING"

# After SIGINT to the run's process group: how long to wait before SIGTERM,
# then before SIGKILL (spawn workers outlive a killed parent; prototype P1).
_INT_GRACE_S = 10.0
_TERM_GRACE_S = 3.0

_ADVICE = (
    "Run make check-slow in the background (Bash run_in_background, output to a log; about "
    "6 min) and run no other gate meanwhile. The stamp is per working tree: a fresh clone or "
    "worktree needs its own run. Stamped files: tests/slow_stamp.py STAMPED_FILES "
    "(ticket agent-gates/05)."
)


def hash_files(root: Path) -> dict[str, str]:
    """sha256 of each stamped file under ``root``, or MISSING."""
    out = {}
    for rel in STAMPED_FILES:
        try:
            out[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        except FileNotFoundError:
            out[rel] = MISSING
    return out


def _changed(old: dict[str, str], new: dict[str, str]) -> list[str]:
    return sorted(p for p in set(old) | set(new) if old.get(p) != new.get(p))


def check(root: Path) -> int:
    """0 when the stamp matches the stamped files, else 1 with the stale message."""
    try:
        stamp = json.loads((root / STAMP).read_text())
        stamped = stamp["files"]
    except (OSError, ValueError, KeyError, TypeError):
        print(
            "make check: the slow tier is stale. No green make check-slow is recorded in this "
            f"tree ({STAMP} is missing or unreadable). {_ADVICE}"
        )
        return 1
    changed = _changed(stamped, hash_files(root))
    if changed:
        print(
            "make check: the slow tier is stale. Changed since the last green make check-slow: "
            f"{', '.join(changed)}. {_ADVICE}"
        )
        return 1
    return 0


def find_leftover_workers(root: Path, proc_root: Path = Path("/proc")) -> list[int]:
    """PIDs of multiprocessing spawn workers run by this tree's venv.

    Matched on an absolute ``cmdline[0]`` under ``<root>/.venv/bin/``, never on
    ``/proc/<pid>/exe``: the venv's python links to a uv interpreter that every
    uv venv shares (review B4).
    """
    prefix = str(root / ".venv/bin") + "/"
    pids = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        argv = [a.decode(errors="replace") for a in args if a]
        if argv and argv[0].startswith(prefix) and any("multiprocessing.spawn" in a for a in argv):
            pids.append(int(entry.name))
    return sorted(pids)


def _pgid(pid: int) -> int | None:
    try:
        return os.getpgid(pid)
    except OSError:
        return None


class _Interrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


def _interrupt(signum: int) -> None:
    # Ignore further signals while the group is stopped.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise _Interrupted(signum)


class _DeferredSignals:
    """SIGINT/SIGTERM handler that holds a signal while the command starts.

    A signal raised inside Popen would leave the runner without the started
    child's handle, so its group would never be stopped (review SP4). While
    ``starting`` is set the signal is only noted; ``started()`` raises it once
    the handle is known.
    """

    def __init__(self) -> None:
        self.starting = True
        self.pending: int | None = None

    def __call__(self, signum: int, _frame: FrameType | None) -> None:
        if self.starting:
            if self.pending is None:
                self.pending = signum
            return
        _interrupt(signum)

    def started(self) -> None:
        self.starting = False
        if self.pending is not None:
            _interrupt(self.pending)


def _group_alive(proc: subprocess.Popen[bytes], pgid: int) -> bool:
    proc.poll()  # reap the leader, so a zombie does not count
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_group(proc: subprocess.Popen[bytes], pgid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _group_alive(proc, pgid):
            return True
        time.sleep(0.1)
    return not _group_alive(proc, pgid)


def _stop_group(proc: subprocess.Popen[bytes], pgid: int) -> None:
    """SIGINT to the whole group, then SIGTERM, then SIGKILL."""
    for sig, grace in (
        (signal.SIGINT, _INT_GRACE_S),
        (signal.SIGTERM, _TERM_GRACE_S),
        (signal.SIGKILL, _TERM_GRACE_S),
    ):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, sig)
        if _wait_group(proc, pgid, grace):
            return


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _commit(root: Path) -> str:
    out = subprocess.run(
        ["git", "describe", "--always", "--dirty"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def run(root: Path, command: list[str]) -> int:
    """make check-slow: run ``command`` and stamp the files when it is green."""
    gate = root / GATE_DIR
    gate.mkdir(exist_ok=True)
    with (root / LOCK).open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.seek(0)
            try:
                holder = json.loads(lock.read())
            except ValueError:
                holder = {}
            print(
                "make check-slow: another make check-slow is running in this tree "
                f"(pid {holder.get('pid')}, pgid {holder.get('pgid')}); wait for it"
            )
            return 1

        leftovers = find_leftover_workers(root)
        if leftovers:
            pgids = sorted({g for g in map(_pgid, leftovers) if g is not None})
            print(
                "make check-slow: another pool is running in this tree (or leftovers of an "
                f"interrupted run): spawn workers {leftovers}. They would load the run. If "
                "they are leftovers, stop them: "
                + "; ".join(f"kill -INT -- -{g}" for g in pgids)
                + f"; then kill {' '.join(map(str, leftovers))}"
            )
            return 1

        warning = busy_warning("make check-slow", loadavg())
        if warning is not None:
            print(warning, flush=True)

        run_id = uuid.uuid4().hex
        hashes_begin = hash_files(root)
        (root / MEASUREMENT).unlink(missing_ok=True)

        def record(pgid: int | None) -> None:
            lock.seek(0)
            lock.truncate()
            lock.write(json.dumps({"pid": os.getpid(), "pgid": pgid, "run_id": run_id}))
            lock.flush()

        record(None)
        handler = _DeferredSignals()
        old_int = signal.signal(signal.SIGINT, handler)
        old_term = signal.signal(signal.SIGTERM, handler)
        proc: subprocess.Popen[bytes] | None = None
        try:
            proc = subprocess.Popen(
                command,
                cwd=root,
                env={**os.environ, RUN_ID_VAR: run_id},
                start_new_session=True,
            )
            record(proc.pid)  # a new session: its pgid is its pid
            handler.started()  # raises a signal that arrived while starting
            returncode = proc.wait()
        except _Interrupted as interrupted:
            if proc is not None:
                _stop_group(proc, proc.pid)
            print(f"make check-slow: interrupted (signal {interrupted.signum}); no stamp written")
            return 128 + interrupted.signum
        finally:
            signal.signal(signal.SIGINT, old_int)
            signal.signal(signal.SIGTERM, old_term)
        # Workers left in the group after the command exited.
        if _group_alive(proc, proc.pid):
            _stop_group(proc, proc.pid)

        if returncode != 0:
            print(f"make check-slow: red (exit {returncode}); no stamp written")
            return returncode
        changed = _changed(hashes_begin, hash_files(root))
        if changed:
            print(
                "make check-slow: stamped files changed during the run: "
                f"{', '.join(changed)}; no stamp written. Run it again on settled code."
            )
            return 1
        try:
            measurement = json.loads((root / MEASUREMENT).read_text())
        except (OSError, ValueError):
            measurement = None
        if not isinstance(measurement, dict) or measurement.get("run_id") != run_id:
            print(
                f"make check-slow: {MEASUREMENT} is missing or from another run (run id "
                f"{run_id}): the slow tier did not run in this run; no stamp written"
            )
            return 1
        stamp = {
            "run_id": run_id,
            "files": hashes_begin,
            "commit": _commit(root),
            "finished": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
            "measurement": measurement,
        }
        _write_atomic(root / STAMP, json.dumps(stamp, indent=2) + "\n")
        print(f"make check-slow: green; wrote {STAMP}")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("run", "check"):
        p = sub.add_parser(name)
        p.add_argument("--root", type=Path, default=ROOT)
    sub.choices["run"].add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.action == "check":
        return check(root)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("run needs a command after --")
    return run(root, command)


if __name__ == "__main__":
    sys.exit(main())
