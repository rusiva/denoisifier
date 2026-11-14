"""The slow-tier stamp (ticket agent-gates/05): a green `make check-slow` stamps
the files that affect detector output, and `make check` fails when they differ.

The runner is tested for real on a tmp root holding copies of STAMPED_FILES,
with the pytest command replaced by small `python -c` stubs.
"""

import ast
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import slow_stamp
from protected import BENCH_IDLE_LOAD
from slow_stamp import ROOT, STAMPED_FILES

STAMP = Path(".gate/check-slow-stamp.json")
MEASUREMENT = Path(".gate/check-slow-measurement.json")

# A stub of the slow tier: writes the measurement with this run's id, exits 0.
GREEN = (
    "import json, os, pathlib; p = pathlib.Path('.gate/check-slow-measurement.json'); "
    "p.write_text(json.dumps({'run_id': os.environ['CHECK_SLOW_RUN_ID'], 'ok': 1}))"
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for rel in STAMPED_FILES:
        src = ROOT / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return tmp_path


def run(root: Path, code: str) -> int:
    return slow_stamp.main(["run", "--root", str(root), "--", sys.executable, "-c", code])


def check(root: Path) -> int:
    return slow_stamp.main(["check", "--root", str(root)])


def test_green_run_writes_the_stamp_and_check_passes(root, capsys):
    assert run(root, GREEN) == 0
    stamp = json.loads((root / STAMP).read_text())
    assert set(stamp["files"]) == set(STAMPED_FILES)
    assert stamp["measurement"]["ok"] == 1
    assert stamp["run_id"] == stamp["measurement"]["run_id"]
    capsys.readouterr()
    assert check(root) == 0


def test_stamped_edit_makes_check_fail_naming_only_that_file(root, capsys):
    assert run(root, GREEN) == 0
    with (root / "src/denoisifier/analysis.py").open("a") as f:
        f.write("# plant\n")
    capsys.readouterr()
    assert check(root) == 1
    out = capsys.readouterr().out
    assert out.strip() == (
        "make check: the slow tier is stale. Changed since the last green make check-slow: "
        "src/denoisifier/analysis.py. Run make check-slow in the background (Bash "
        "run_in_background, output to a log; about 6 min) and run no other gate meanwhile. "
        "The stamp is per working tree: a fresh clone or worktree needs its own run. "
        "Stamped files: tests/slow_stamp.py STAMPED_FILES (ticket agent-gates/05)."
    )


def test_missing_stamp_makes_check_fail(root, capsys):
    assert check(root) == 1
    out = capsys.readouterr().out
    assert "No green make check-slow is recorded in this tree" in out
    assert "Run make check-slow in the background" in out


def test_red_run_writes_nothing_and_keeps_the_old_stamp(root):
    assert run(root, GREEN) == 0
    before = (root / STAMP).read_bytes()
    assert run(root, GREEN + "; raise SystemExit(3)") == 3
    assert (root / STAMP).read_bytes() == before


def test_red_first_run_writes_no_stamp(root):
    assert run(root, "raise SystemExit(1)") == 1
    assert not (root / STAMP).exists()


def test_stamped_file_edited_during_the_run_writes_nothing(root, capsys):
    code = GREEN + "; open('src/denoisifier/synthetic.py', 'a').write('# edit')"
    assert run(root, code) == 1
    assert "src/denoisifier/synthetic.py" in capsys.readouterr().out
    assert not (root / STAMP).exists()


@pytest.mark.parametrize(
    "code",
    [
        "pass",  # the slow tier never wrote its measurement
        "import pathlib; pathlib.Path('.gate/check-slow-measurement.json')"
        '.write_text(\'{"run_id": "another"}\')',
    ],
    ids=["missing", "another-run"],
)
def test_green_run_without_this_runs_measurement_writes_nothing(root, code, capsys):
    assert run(root, code) == 1
    assert "missing or from another run" in capsys.readouterr().out
    assert not (root / STAMP).exists()


def test_a_second_run_is_refused_while_the_lock_is_held(root, capsys):
    (root / ".gate").mkdir()
    with (root / ".gate/check-slow.lock").open("a+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held.write(json.dumps({"pid": 4242, "pgid": 4343, "run_id": "x"}))
        held.flush()
        assert run(root, GREEN) == 1
    assert capsys.readouterr().out.strip() == (
        "make check-slow: another make check-slow is running in this tree "
        "(pid 4242, pgid 4343); wait for it"
    )
    assert not (root / STAMP).exists()


def test_sigterm_to_the_runner_stops_its_whole_process_group(root):
    # The command spawns a child in its group (like a spawn pool's workers) and sleeps.
    code = (
        "import subprocess, sys, time; "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
        "open('.gate/child.pid', 'w').write(str(p.pid)); time.sleep(120)"
    )
    script = str(ROOT / "tests/slow_stamp.py")
    runner = subprocess.Popen(
        [sys.executable, script, "run", "--root", str(root), "--", sys.executable, "-c", code]
    )
    child_pid_file = root / ".gate/child.pid"
    deadline = time.monotonic() + 20
    while not child_pid_file.exists() or not child_pid_file.read_text():
        assert time.monotonic() < deadline, "the stub never started"
        time.sleep(0.05)
    child = int(child_pid_file.read_text())
    runner.send_signal(signal.SIGTERM)
    assert runner.wait(timeout=15) == 128 + signal.SIGTERM
    deadline = time.monotonic() + 15
    while Path(f"/proc/{child}").exists() and "Z" not in _state(child):
        assert time.monotonic() < deadline, f"child {child} outlived the runner's group stop"
        time.sleep(0.05)
    assert not (root / STAMP).exists()


def test_a_signal_while_the_command_starts_still_stops_its_group(root, monkeypatch, capsys):
    # SIGTERM lands after the child exists but before Popen has returned (review SP4).
    started: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen

    def popen_then_signal(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        started.append(child)
        os.kill(os.getpid(), signal.SIGTERM)
        return child

    monkeypatch.setattr(slow_stamp.subprocess, "Popen", popen_then_signal)
    try:
        assert run(root, "import time; time.sleep(120)") == 128 + signal.SIGTERM
        assert started, "the command never started"
        assert started[0].poll() is not None, "the started command outlived the runner"
    finally:
        for child in started:
            if child.poll() is None:
                child.kill()
                child.wait()
    assert "interrupted (signal 15)" in capsys.readouterr().out
    assert not (root / STAMP).exists()


def _state(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return "Z"


def _fake_process(proc: Path, pid: int, argv: list[str], exe: str | None = None) -> None:
    d = proc / str(pid)
    d.mkdir(parents=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    if exe:
        (d / "exe").symlink_to(exe)


def test_leftover_workers_are_matched_on_this_trees_venv(tmp_path):
    tree = tmp_path / "tree"
    shared = "/home/u/.local/share/uv/python/cpython-3.11-linux/bin/python3.11"
    spawn = ["-c", "from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=5)"]
    proc = tmp_path / "proc"
    _fake_process(proc, 100, [f"{tree}/.venv/bin/python3", *spawn, "--multiprocessing-fork"])
    _fake_process(proc, 101, ["/other/.venv/bin/python3", *spawn, "--multiprocessing-fork"])
    # exe resolves to the shared uv interpreter; cmdline[0] is not this venv.
    _fake_process(proc, 102, [shared, *spawn], exe=f"{tree}/.venv/bin/python3")
    _fake_process(proc, 103, [f"{tree}/.venv/bin/python", f"{tree}/.venv/bin/pytest", "-m"])
    _fake_process(proc, 104, [f"{tree}/.venv/bin/python3", *spawn])
    (proc / "self").mkdir()
    (proc / "105").mkdir()  # exited: no cmdline
    assert slow_stamp.find_leftover_workers(tree, proc) == [100, 104]


def _slow_modules() -> set[str]:
    """tests/*.py that use pytest.mark.slow, with their transitive tests/ imports."""
    tests = ROOT / "tests"

    def uses_slow(tree: ast.AST) -> bool:
        return any(
            isinstance(n, ast.Attribute)
            and n.attr == "slow"
            and isinstance(n.value, ast.Attribute)
            and n.value.attr == "mark"
            for n in ast.walk(tree)
        )

    def local_imports(tree: ast.AST) -> set[str]:
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                names.add(n.module.split(".")[0])
        return {f"tests/{m}.py" for m in names if (tests / f"{m}.py").exists()}

    trees = {f"tests/{p.name}": ast.parse(p.read_text()) for p in tests.glob("*.py")}
    todo = [rel for rel, tree in trees.items() if uses_slow(tree)] + ["tests/conftest.py"]
    seen: set[str] = set()
    while todo:
        rel = todo.pop()
        if rel not in seen:
            seen.add(rel)
            todo.extend(local_imports(trees[rel]))
    return seen


def test_stamped_files_cover_the_slow_tier():
    package = {
        p.relative_to(ROOT).as_posix() for p in (ROOT / "src/denoisifier").iterdir() if p.is_file()
    }
    stamped = set(STAMPED_FILES)
    not_stamped = set(slow_stamp.NOT_STAMPED_SRC)
    assert not stamped & not_stamped
    unclassified = package - stamped - not_stamped
    assert not unclassified, (
        f"classify {sorted(unclassified)} in tests/slow_stamp.py: STAMPED_FILES if it can "
        "affect detector output, else NOT_STAMPED_SRC"
    )
    missing = _slow_modules() - stamped
    assert not missing, f"the slow tier imports unstamped files: {sorted(missing)}"
    assert "tests/test_slow_regression.py" in _slow_modules()


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "GLOSSARY.md",
        "docs/adr/0001-plant.md",
        "src/denoisifier/cli.py",
        "src/denoisifier/report.py",
        "src/denoisifier/frame_io.py",
        "src/denoisifier/__main__.py",
        "tests/test_cli.py",
        "tests/test_analyse.py",
    ],
)
def test_docs_cli_report_and_non_slow_tests_never_need_the_slow_tier(root, path):
    assert path not in STAMPED_FILES
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("before\n")
    assert run(root, GREEN) == 0
    target.write_text("after\n")
    assert check(root) == 0


def test_the_stamp_is_git_ignored_local_state():
    for rel in (slow_stamp.STAMP, slow_stamp.LOCK, slow_stamp.MEASUREMENT, ".gate/bench.json"):
        result = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT, check=False)
        assert result.returncode == 0, f"{rel} is not git-ignored"


def _dry_run(target: str) -> str:
    # Under `make check` the outer make's MAKEFLAGS/MAKELEVEL would add
    # "Entering/Leaving directory" lines.
    env = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL")}
    return subprocess.run(
        ["make", "-n", "--no-print-directory", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout


def test_check_ends_with_the_stamp_check():
    assert _dry_run("check").strip().splitlines()[-1].endswith("python tests/slow_stamp.py check")


def test_check_slow_runs_the_slow_tier_under_the_runner():
    last = _dry_run("check-slow").strip().splitlines()[-1]
    assert "python tests/slow_stamp.py run -- " in last
    assert last.endswith('pytest -m "slow and not held_out"')


def test_check_held_out_selects_the_held_out_tests_and_stays_out_of_check():
    last = _dry_run("check-held-out").strip().splitlines()[-1]
    assert last.endswith("pytest -m held_out")
    assert "slow_stamp.py" not in _dry_run("check-held-out")
    assert "held_out" not in _dry_run("check")


@pytest.mark.parametrize("target", ["check", "check-slow"])
def test_bench_and_the_full_measurement_stay_out_of_the_gates(target):
    text = _dry_run(target)
    assert "bench.py" not in text
    assert "feasibility.py" not in text


BUSY = "3.50 2.00 1.00 2/900 4242"
IDLE = "0.20 0.30 0.40 1/900 4242"


@pytest.mark.parametrize(
    ("line", "warns"),
    [(BUSY, True), (IDLE, False), (f"{BENCH_IDLE_LOAD} 0 0 1/1 1", False), ("unavailable", False)],
)
def test_busy_warning_flags_a_one_minute_load_above_the_idle_load(line, warns):
    warning = slow_stamp.busy_warning("make x", line)
    if warns:
        assert warning == f"make x: warning: load average {line} at start; the machine is not idle"
    else:
        assert warning is None


@pytest.mark.parametrize(("line", "warns"), [(BUSY, True), (IDLE, False)])
def test_check_slow_warns_at_start_on_a_busy_machine(root, monkeypatch, capsys, line, warns):
    monkeypatch.setattr(slow_stamp, "loadavg", lambda: line)
    assert run(root, GREEN) == 0
    assert ("make check-slow: warning: load average" in capsys.readouterr().out) is warns
