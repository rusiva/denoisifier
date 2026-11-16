#!/usr/bin/env python3
"""Watch context fill from on-disk transcripts; the measured agent is not involved.

Usage:
  fill-watch.py <agentId> [limit=200000]   watch a worker
  fill-watch.py self [limit=200000]        watch this session's own window
      Watch modes are for Bash run_in_background. Silent until ONE event line,
      then exit:
        ROTATE agent=<id> fill=<n> limit=<n>   the worker crossed its limit
        SELF fill=<n> limit=<n>                the orchestrator crossed its limit
        ERROR <target> <reason>                cannot measure; never a pass
  fill-watch.py --now <agentId|self>
      One-shot: prints fill and seconds since the transcript last grew.
      Exit 2 if not found.

Fill = input + cache_creation_input + cache_read_input tokens of the newest
assistant usage record: the size of the last prompt the model saw.

Transcripts:
  worker  newest ~/.claude/projects/*/*/subagents/agent-<id>.jsonl, re-resolved
          every poll, so it follows a worker re-homed under a new session after
          /clear and worktree slugs.
  self    ~/.claude/projects/*/$CLAUDE_CODE_SESSION_ID.jsonl (main chain only;
          sub-agent records never land there).

Env: FILL_WATCH_INTERVAL poll seconds (default 30).
"""

import glob
import json
import os
import sys
import time

PROJECTS = os.path.expanduser("~/.claude/projects")
INTERVAL = float(os.environ.get("FILL_WATCH_INTERVAL", "30"))
GRACE_POLLS = 10  # a fresh worker has no transcript or usage record yet
MAX_FAILS = 3
TAIL_BYTES = 4 << 20


def newest(pattern):
    paths = glob.glob(pattern)
    return max(paths, key=os.path.getmtime) if paths else None


def transcript(target):
    if target == "self":
        sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
        return newest(os.path.join(PROJECTS, "*", f"{sid}.jsonl")) if sid else None
    name = f"agent-{target}.jsonl"
    return newest(os.path.join(PROJECTS, "*", "*", "subagents", name))


def usage_fill(raw):
    if b'"usage"' not in raw:
        return None
    try:
        rec = json.loads(raw)
    except ValueError:
        return None
    if rec.get("type") != "assistant":
        return None
    u = (rec.get("message") or {}).get("usage") or {}
    cc = u.get("cache_creation_input_tokens")
    if cc is None and isinstance(u.get("cache_creation"), dict):
        cc = sum(v for v in u["cache_creation"].values() if isinstance(v, int))
    n = (
        (u.get("input_tokens") or 0)
        + (cc or 0)
        + (u.get("cache_read_input_tokens") or 0)
    )
    return n or None  # synthetic messages carry zero usage


def fill(path):
    """Fill of the newest assistant usage record, or None if there is none yet."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size > TAIL_BYTES:
            f.seek(size - TAIL_BYTES)
            f.readline()  # drop the partial first line
        lines = f.readlines()
    for raw in reversed(lines):
        n = usage_fill(raw)
        if n:
            return n
    if size > TAIL_BYTES:  # last record sits further back
        with open(path, "rb") as f:
            for raw in reversed(f.readlines()):
                n = usage_fill(raw)
                if n:
                    return n
    return None


def emit(line, code=0):
    print(line, flush=True)
    sys.exit(code)


def watch(target, limit):
    label = "self" if target == "self" else f"agent={target}"
    seen = False
    empty = fails = 0
    while True:
        path = transcript(target)
        n = None
        if path:
            try:
                n = fill(path)
                fails = 0
            except OSError as e:
                fails += 1
                if fails >= MAX_FAILS:
                    emit(f"ERROR {label} unreadable transcript {path}: {e}", 2)
        if n:
            seen = True
            if n >= limit:
                emit(
                    f"SELF fill={n} limit={limit}"
                    if target == "self"
                    else f"ROTATE agent={target} fill={n} limit={limit}"
                )
        elif not seen:
            empty += 1
            if target == "self" or empty > GRACE_POLLS:
                what = (
                    f"no usage record in {path}"
                    if path
                    else f"no transcript under {PROJECTS}"
                )
                emit(f"ERROR {label} {what}", 2)
        time.sleep(INTERVAL)


def now(target):
    path = transcript(target)
    if not path:
        emit(f"ERROR {target} transcript not found", 2)
    n = fill(path)
    age = int(time.time() - os.path.getmtime(path))
    emit(f"{target} fill={n or 0} age={age}s file={path}")


def main(argv):
    if len(argv) == 2 and argv[0] == "--now":
        now(argv[1])
    elif len(argv) in (1, 2) and not argv[0].startswith("-"):
        watch(argv[0], int(argv[1]) if len(argv) == 2 else 200000)
    else:
        emit(__doc__.strip(), 2)


if __name__ == "__main__":
    main(sys.argv[1:])
