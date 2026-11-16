"""Summarise p1_recorder_11's JSONL: m_b and m_f (plan section 7 step 1, B4)."""

import json
import sys
from collections import defaultdict

recs = [json.loads(line) for line in open(sys.argv[1])]
breaks = [(r["test"], r["caller"], e) for r in recs if r["kind"] == "break" for e in r["E"]]
# Fork candidates the caller treats as found: reported side (min_evidence 0.3) of analyse,
# or a direct test call (the tests keep E >= _FORK_MIN_EVIDENCE themselves).
forks = [
    (r["test"], r["caller"], e)
    for r in recs
    if r["kind"] == "fork" and (r["limit"] is None or r["limit"] >= 0.3)
    for e in r["E"]
    if e >= 0.3
]
gate_band = [
    (r["test"], e) for r in recs if r["kind"] == "fork" for e in r["E"] if 0 < e < 0.3
]


def low(rows, n=8):
    return sorted(rows, key=lambda t: t[-1])[:n]


by_mod = defaultdict(list)
for t, c, e in breaks:
    by_mod[(t or "?").split("::")[0]].append(e)
print("break E: n", len(breaks), "min", min(e for *_, e in breaks))
for m, v in by_mod.items():
    print("  ", m, "n", len(v), "min", round(min(v), 4))
print("lowest breaks:")
for row in low(breaks):
    print("  ", row)
print("fork E (found side): n", len(forks), "min", min(e for *_, e in forks))
fm = defaultdict(list)
for t, c, e in forks:
    fm[((t or "?").split("::")[0], c == "_region_forks")].append(e)
for m, v in fm.items():
    print("  ", m, "n", len(v), "min", round(min(v), 4))
print("lowest forks:")
for row in low(forks):
    print("  ", row)
print("fork candidates with 0 < E < 0.3:", len(gate_band), low([(t, e) for t, e in gate_band], 5))
print("tests recorded:", len({r["test"] for r in recs}))
