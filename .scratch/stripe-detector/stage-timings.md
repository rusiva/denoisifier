# Ticket 13 stage timings (AC 3)

- Commit `c8095cb`; CPU AMD Ryzen AI 7 PRO 360 w/ Radeon 880M; affinity 16; load 2.47 2.24 2.13 1/1183 919315.
- Python 3.11.15, numpy 2.4.6, scipy 1.17.1.
- Default bank threads here: 4 (`_local_stripes.bank_threads`).
- Import `denoisifier.cli`: 0.24 s (`-X importtime`), 0.30 s wall (interpreter + imports).
- Cold CLI on the speed frame (`python -m denoisifier`, default threads): 4.52 s, median (BASE 9.46 s).
- BASE is prototype P1's table at `aae4084` (speed frame, idle, one thread), quoted; P1's typical P 6 warm pipeline was 7.31 s.

| stage | BASE (P1), speed (AC 1) | speed (AC 1), threads 1 | speed (AC 1), threads 4 (default) | typical P6, threads 1 | typical P6, threads 4 (default) | bench timing, threads 1 | bench timing, threads 4 (default) |
|---|---|---|---|---|---|---|---|
| `read_frame` | 0.12-0.15 | 0.149 | 0.158 | 0.162 | 0.147 | 0.145 | 0.142 |
| `analyse` | 8.20 | 6.195 | 4.571 | 3.684 | 2.091 | 3.623 | 2.331 |
| `to_json` | - | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `write_mask_csv` | - | 0.046 | 0.043 | 0.040 | 0.038 | 0.037 | 0.039 |
| warm pipeline (read -> analyse -> to_json) | 8.68 | 6.390 | 4.734 | 3.850 | 2.243 | 3.768 | 2.474 |
| `reject_spikes` | 0.21 (spikes + `_light` + other) | 0.160 | 0.155 | 0.142 | 0.133 | 0.137 | 0.141 |
| `find_clipped` | - | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 |
| `_light` | - | 0.052 | 0.048 | 0.045 | 0.043 | 0.045 | 0.042 |
| `estimate_local_stripes` | 5.63 | 3.251 | 1.628 | 2.974 | 1.435 | 2.770 | 1.452 |
| `_qualifying_regions` | 0.35 | 0.423 | 0.417 | 0.172 | 0.166 | 0.325 | 0.310 |
| `_pre_break_forks` | 0.39 (pre + post) | 0.217 | 0.206 | 0.158 | 0.143 | 0.159 | 0.162 |
| `_with_phase_breaks` | 1.61 | 1.819 | 1.802 | 0.064 | 0.062 | 0.058 | 0.055 |
| `_post_break_forks` | - | 0.240 | 0.226 | 0.106 | 0.106 | 0.129 | 0.124 |

Slices:

- slice 1, lazy cold-start imports: adopted (57ac55c)
- slice 2, bank loop with reused buffers: adopted (df3c78b)
- slice 3, one forward spectrum: adopted (ef79e1f)
- slice 4b, deterministic bank Angle tie-break: adopted (ea359a7)
- slice 5, Gaussians on their support box, pruned inverse FFT: adopted (53a7871)
- slice 6, single-precision bank: dropped (failed 'found identically')
- slice 7, coarse-strided break finder: dropped (failed 'same basin'; ticket 22)
- slice 4, bank threads across Periods: adopted (231aabb)
- slice 8, multirate bank: dropped from this ticket (ticket 19)
