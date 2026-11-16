# 10 P1 prototyper handoff 1 (paused)

PROTOTYPE, throwaway. Do not merge.

- Worktree: `/home/rusiva/dev/denoisifier/.claude/worktrees/agent-a893b57897cdc4f7a`, branch `worktree-agent-a893b57897cdc4f7a`, commit **`59dac3d`** (code under `prototypes/p10_forks/`). BASE `ca48498`.
- No config is frozen yet. No validation seed (111_600-111_999) has been generated or looked at.
- `<SP>` = `/tmp/claude-1000/-home-rusiva-dev-denoisifier/a5c31385-01e3-4bc0-bce8-a97c1d5a1f5a/scratchpad`. A reboot clears it.

## Seed ranges looked at so far

- Explore stage 1: seeds **111_000-111_199**. The harness uses `base + k` per set, so it has used only the first 200 of the 600 explore seeds; sets reuse seeds and differ by frame kind.
- Noise-free checks (`nf.py`): seeds **111_000-111_115** (they set phase0 only).
- Quick checks (`quick.py`, `core.py`, `dbg1.py`, `notch.py`): seeds 111_000-111_019.
- Validation 111_600-111_999: **untouched**.

## In flight

- **Explore stage 1** (`harness.py explore <SP>/explore --workers 15`). It is BASE only (generate + analyse, unchanged code) and stores per frame what the fork step needs.
  - At pause time: 472 of 1566 frames written, ~1 frame/s, about 18 min left.
  - PIDs: 251391/251393/251400 (uv, python, Pool).
  - Log: `<SP>/explore.log`; its last line is `EXIT=<code>` when it finishes.
  - It answers nothing on its own: stage 2 (next steps) reads it.
  - **Restartable**: it skips frames whose `.pkl` already exists. If it was killed, re-run the same command (background, idle machine).
  - To stop it: `kill -INT 251391` (or the Pool parent), then check `pgrep -f "harness.py explore"`.
- Two waiter shells (`until ... sleep`) are also watching the same store. They are harmless and exit when the near-break frames exist.

## Done

1. **Generator patch** (`common.py`): plan 2.1's term `sum d * atan2(y - y0, x - x0)` is added to every phase that `synthetic._phase` returns (full frame and each region), with no RNG draws. **Capture**: a wrapper on `analysis._with_phase_breaks` records the settled regions and their found breaks, sorted as `analyse` labels them (asserted against `report.labels`).
2. **Finder (PQ1 candidate, `finder.py`)**: candidate A in lattice form. O(pixels), all numpy. Steps:
   - Demodulate `break_response` by the median carrier (as `_samples`).
   - Explain away found breaks: multiply the positive side by exp(-i jump). Pixels within `band_sigmas · σn` of the line take the corrected value at the band edge on their own side, so a loop steps across the band.
   - Find residues on 2x2 plaquettes.
   - The winding of the square loop of half-size R about every pixel is a box sum of the residues. It counts only when every loop pixel is valid (|z| ≥ 0.5 median, and in the domain).
   - Take the components of winding +1 and of winding -1. Point = the component's centroid; E = component area / (2R)².
3. **Finding 1: BASE carves the fork out of its region (PQ4/P2, AC 4).**
   - On 20/20 EMCCD single-region frames (seeds 111_000-111_019, all 10 cases, both directions), **the fork's own pixel is not in the reported region**. BASE leaves a notch or hole at the fork; at P 20 it is a slot about 3.5 P wide from the fork to the region edge.
   - IoU drops from 0.90-0.95 to 0.88-0.95 (still ≥ 0.8 on these 20). The frames stay Striped, with one region.
   - So AC 4's "the true fork's nearest frame pixel lies in a reported region" fails on BASE every time. It needs a new reading, or a ticket-17 fix.
   - Searching `g.pixels` alone misses most forks: the loops leave the domain.
   - Prototype choice: the fork search domain is the region **closed** with a disc of `close_periods` = 3 P, holes filled, other regions' pixels removed (`forks.fork_domain`). A found fork can then lie on a pixel outside the region's labels (recorded as `in_pixels`).
4. **First numbers** (explore; R = 2 P, closed 3 P, min_mag 0.5, no E threshold), single set, seeds 111_000-111_059:
   - 51/51 found, right direction, no extras.
   - Position error max 0.44 P (P 3), p95 0.32 P; E min 0.42.
   - 0 candidates of any E on 51 fork-free twins.
   - At R = 1.5 P: 45/45 found, E min 0.19.
5. **Noise-free (`nf.py`, R = 2 P):**
   - Single forks: 96/96 found (P 3, 5, 8, 20; Angles 0, ±10; both directions; 4 offsets). Max error **0.172 P**, p95 0.13.
   - Plane wave, carrier 10 %/3° off, disc cut by an edge: 0 candidates each.
   - Pairs: found at separation ≥ 3 P (P 20: ≥ 2 P). None at 1.5-2 P.
   - **Sharp π break with a fork 1.5-3 P away: the frozen break finder loses the break** in most cases, noise-free:
     - P 5 and P 8: lines at 45° and 90°, at 1.5-2 P;
     - P 20: at every distance up to 3 P;
     - lines at 90°: even at 3 P.
   - When the break is found (3 P, lines 0°/45°, P 5/8), the fork is found at 0.05 P. When the break is lost, the fork is usually lost too, since the π line is not explained away.
   - No fake break was seen in these noise-free runs. PQ5's fake-break question is answered only by the explore data (next step 1).

## Next steps

1. When `<SP>/explore.log` shows `EXIT=0`, run from `prototypes/p10_forks` (with `VIRTUAL_ENV=`):
   - `uv run --locked python forks.py <SP>/explore --workers 15` (default config: R 2 P, closed 3 P);
   - `evaluate.py <SP>/explore_forks.pkl --verbose`;
   - `base_effects.py <SP>/explore_forks.pkl`.

   `base_effects.py` prints three things:
   - The **PQ5 stop-rule** counts: breaks reported on fork frames without a true break, against the fork-free twins. If they are above the twins' counts, **stop and escalate**.
   - The near-break set per distance (1.5/2/3/4/5/6/8 P), for review P1 and PQ3: fork found; break found (09 5.1) against the break-only twin; one break; same region; and which first-line rule (E, jump or spread) lost the break.
   - The BASE effects, for PQ4 and P2.
2. If the stop rule does not fire, choose on explore:
   - R, `close_periods`, `band_sigmas` and the E threshold (PQ1 and PQ2; also try excluding the band instead of stepping across it);
   - then measure pairs (PQ5), edge (PQ6), binned (PQ7) and weak (information only).

   Then **freeze at a commit**, run `harness.py validate <SP>/validate` once (background), then stage 2 and eval with nothing changed.
3. PQ8: run `timing.py` single-process on an idle machine, after every batch job has ended. It times the bench frame (TIMING_SEED) and a P 3 full frame (seed 111_000): BASE analyse, then the fork step split into response (cached in production), domain and find_forks.
4. Write `/home/rusiva/dev/denoisifier/.scratch/stripe-detector/handoffs/10-prototype-p1.md`: frozen config, rates per question, every seed range.

## Open questions for the orchestrator (so far)

- **AC 4 under BASE's fork notch** (finding 1). Either read AC 4 as "the fork lies in the region's closed domain" (or within N P of its pixels), or send the notch to ticket 17. Related: should the fork search domain be the closed region (as prototyped) rather than `g.pixels`? That changes plan 2.2/2.3 and section 0's "only reported regions are searched" wording.
- **Break loss near a fork** (review P1). Noise-free evidence already shows the frozen finder loses π breaks with a fork 1.5-3 P away. So "near" in AC 3 likely needs ≥ 4-5 P and a fresh ruling, unless the explore data says otherwise. The rule cause per distance is pending (next step 1).
- **Negative-set seeds.** The break-only negative set uses the 09 frame **kinds** on prototype seeds, not the 09 test seeds, because the brief allowed only prototype ranges. Running the real test frames is the orchestrator's call.

## Files (worktree `prototypes/p10_forks/`)

- `common.py`: generator patch, analyse capture.
- `finder.py`: the finder and `Config`.
- `harness.py`: stage 1 (frame specs per set and their seed allocation, break-rule diagnostics).
- `forks.py`: stage 2, closed domain.
- `evaluate.py`: the 5.1 match and per-set rates.
- `base_effects.py`: PQ3/4/5, P1, P2.
- `nf.py`: noise-free checks.
- `timing.py`: PQ8.
- `try.py`: quick subset runner.
- Scratch scripts: `quick.py`, `core.py`, `dbg1.py`, `notch.py`.
