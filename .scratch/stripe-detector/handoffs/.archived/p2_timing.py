"""PROTOTYPE (throwaway): per-frame cost of the growth step, one shared _Spectrum per frame.
Seeds 411_000.. Single process; run on an idle machine."""
import time
import numpy as np
from scipy.ndimage import gaussian_filter
from denoisifier._local_stripes import _Spectrum, estimate_local_stripes, gabor_at
from denoisifier.synthetic import Emccd, generate
import importlib.util, sys
spec_ = importlib.util.spec_from_file_location("p2", __file__.replace("p2_timing.py", "p2_proto.py"))
p2 = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(p2)

for seed, shape, P, ang, m in [(411_000, (512, 512), 8, 6, 0.5), (411_001, (400, 1600), 8, 6, 0.5),
                               (411_002, (400, 1600), 8, 6, 0.2), (411_003, (400, 1600), 20, -10, 0.2)]:
    f = generate(seed=seed, shape=shape, period=P, angle_deg=ang, modulation_depth=m, mottle="scorched", noise=Emccd()).frame
    env = gaussian_filter(f, 10); light = env > 0.1 * env.max()
    t0 = time.perf_counter(); local = estimate_local_stripes(f, light); t_bank = time.perf_counter() - t0
    t0 = time.perf_counter(); cs = p2.cores(local); t_cores = time.perf_counter() - t0
    passing = [(c, Pb) for c, Pb, ok in cs if ok]
    reps = []
    for _ in range(3):
        t0 = time.perf_counter()
        sp = _Spectrum(f)
        for c, Pb in passing:
            p2.grow(sp, local, light, c, Pb, 0.5, 2.0)
        reps.append(time.perf_counter() - t0)
    t0 = time.perf_counter(); sp = _Spectrum(f); t_spec = time.perf_counter() - t0
    if passing:
        t0 = time.perf_counter(); p2.grow(sp, local, light, passing[0][0], passing[0][1], 0.5, 2.0); t_one = time.perf_counter() - t0
    else:
        t_one = float("nan")
    t0 = time.perf_counter(); gabor_at(f, 8.0, 0.0); t_gab = time.perf_counter() - t0
    print(f"{shape} P{P} m{m}: bank {t_bank:.2f}s | cores+split {t_cores:.3f}s ({len(cs)} cores, {len(passing)} pass) | "
          f"growth total (shared spectrum) median {np.median(reps):.3f}s | spectrum {t_spec:.3f}s | one region {t_one:.3f}s | gabor_at (own FFT) {t_gab:.3f}s")
