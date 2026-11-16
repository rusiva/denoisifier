"""Ticket 11 P1 (plan section 7 step 1, B4): true Phase Break and Fork evidence on every
09/10 test frame. A pytest plugin, scratch, not a test; it changes no test or source:

    P1_RECORD=OUT.jsonl PYTHONPATH=.scratch/stripe-detector/handoffs \\
        uv run --locked pytest -p p1_recorder_11 -m "not slow" -p no:cacheprovider \\
        tests/test_analyse.py tests/test_phase_break_pass.py tests/test_local_phase.py

Loaded before collection, it wraps ``find_phase_breaks`` and ``find_forks`` (in
``_local_phase`` and in ``analysis``, the names the tests and the pass call) and writes
one line per call that returns something: the test id, the caller, the accepted breaks'
E (every accepted break: the 09/10 tests assert no extra break) and every Fork
candidate's E with the caller's evidence limit (``_region_forks``'s ``min_evidence``, or
None for a direct test call). A test that monkeypatches a finder replaces the wrapper,
so injected doubles are not recorded. ``-m "not slow"`` keeps ``wide`` (all parameters).
"""

from __future__ import annotations

import json
import os
import sys

import denoisifier._local_phase as lp
from denoisifier import analysis as an

_OUT = open(os.environ["P1_RECORD"], "a")  # noqa: SIM115
_current = {"id": None}
_orig_breaks = lp.find_phase_breaks
_orig_forks = lp.find_forks


def _write(rec: dict) -> None:
    rec["test"] = _current["id"]
    _OUT.write(json.dumps(rec) + "\n")
    _OUT.flush()


def find_phase_breaks(*args, **kwargs):
    found = _orig_breaks(*args, **kwargs)
    if found:
        caller = sys._getframe(1).f_code.co_name
        _write({"kind": "break", "caller": caller, "E": [b.evidence for b in found],
                "jump": [b.jump_rad for b in found]})
    return found


def find_forks(*args, **kwargs):
    found = _orig_forks(*args, **kwargs)
    if found:
        frame = sys._getframe(1)
        caller = frame.f_code.co_name
        limit = frame.f_locals.get("min_evidence") if caller == "_region_forks" else None
        _write({"kind": "fork", "caller": caller, "limit": limit, "E": [f.evidence for f in found]})
    return found


lp.find_phase_breaks = find_phase_breaks
an.find_phase_breaks = find_phase_breaks
lp.find_forks = find_forks
an.find_forks = find_forks


def pytest_runtest_setup(item):
    _current["id"] = item.nodeid


def pytest_runtest_teardown(item):
    _current["id"] = None
