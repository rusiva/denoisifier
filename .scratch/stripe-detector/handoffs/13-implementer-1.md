# Ticket 13 implementer-1 handoff

- Plan: `13-plan.md` (settled). BASE `aae4084`. Branch `main`.
- Machine: 16 logical CPUs, WSL2; idle = `uptime` 1-min load < 1.

## Step 0: C1 explore set persisted

- `~/.cache/denoisifier/p13-c1/explore_v2.pkl`, 334,506,898 bytes, sha256 `8234cab3…d032056` (full hash and the regeneration recipe in `prototypes/p13/c1/explore.py`). 216 records on the C1 tags (full_break 20, fullcap 40, pair2-8 120, bin2x1/bin1x2 36).
- Verbatim ticket 09 `harness2.py` / `eval2.py` copies (not ruff-clean, so outside ruff's scope): `.scratch/stripe-detector/p13-c1-ref/`.
- **Cleanup item (N8):** delete `~/.cache/denoisifier/p13-c1/` at ticket 13's close (or at the finder follow-up's close if slice 7 is dropped).
