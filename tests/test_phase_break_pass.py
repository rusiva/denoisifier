"""The Phase Break pass in ``analyse`` (ticket 09, plan 2.3) on hand-built regions, with the
finder replaced by a fixed answer where the test is about the pass, not the finder."""

import math

import numpy as np
import pytest

import denoisifier.analysis as analysis
from cases import CASES
from denoisifier import BinFactors, analyse
from denoisifier._local_phase import FoundBreak
from denoisifier._local_stripes import _Spectrum
from denoisifier.synthetic import generate
from protected import PHASE_BREAK_TEST_SEEDS, REGION_TEST_SEEDS
from regions import single_region_case

ONE = BinFactors()
SHAPE = (200, 200)
PERIOD = 8.0
LINE_ROW = 99.5
# A horizontal break between rows 99 and 100.
BREAK = FoundBreak(point=(LINE_ROW, 0.0), line_angle_deg=0.0, jump_rad=math.pi, evidence=1.0)


def _filters():
    frame = generate(
        seed=PHASE_BREAK_TEST_SEEDS[0], shape=SHAPE, period=PERIOD, angle_deg=0.0, noise=0.0
    ).frame
    return analysis._Filters(_Spectrum(frame, ONE), np.ones(SHAPE, dtype=bool))


def _survivor(pixels, angle_deg, peak_ratio, period=PERIOD):
    flat = np.flatnonzero(pixels)
    return analysis._Survivor(
        peak_ratio=peak_ratio,
        period=period,
        angle_deg=angle_deg,
        depth=0.5,
        pixels=pixels,
        bbox=analysis._bbox(pixels),
        area_px=int(flat.size),
        first_pixel=int(flat[0]),
    )


def _box(rows, cols, slit=0):
    """A box with a gap of ``slit`` rows on each side of LINE_ROW."""
    y, x = np.mgrid[0 : SHAPE[0], 0 : SHAPE[1]]
    box = (y >= rows[0]) & (y < rows[1]) & (x >= cols[0]) & (x < cols[1])
    return box & (np.abs(y - LINE_ROW) > slit)


def test_the_pass_returns_its_inputs_when_no_break_is_found(monkeypatch):
    """A break-free frame: the pass hands back the very same region objects, with no breaks."""
    seen = {}
    original = analysis._with_phase_breaks

    def spy(reported, filters, clipped):
        out = original(reported, filters, clipped)
        seen["in"], seen["out"] = reported, out
        return out

    monkeypatch.setattr(analysis, "_with_phase_breaks", spy)
    seed = REGION_TEST_SEEDS[0]
    case = CASES[seed % 10]
    # The case is cached for the run, so analyse its frame here: the spy must see this call.
    s, _ = single_region_case(seed, case.period, case.angle_deg)
    report = analyse(s.frame)
    assert len(report.regions) == 1
    assert [g for g, _ in seen["out"]] == seen["in"]
    assert all(g is h for (g, _), h in zip(seen["out"], seen["in"], strict=True))
    assert all(found == [] for _, found in seen["out"])
    assert report.phase_breaks == ()


def test_fills_of_two_regions_never_overlap(monkeypatch):
    """Two regions side by side, both across the break with a slit along it: their along-line
    bins share columns 100-103, so both would fill there; the first fill owns them."""
    monkeypatch.setattr(analysis, "find_phase_breaks", lambda *_: [BREAK])
    left = _survivor(_box((40, 160), (20, 102), slit=2), 0.0, 10.0)
    right = _survivor(_box((40, 160), (102, 180), slit=2), 5.0, 9.0)
    out = analysis._with_phase_breaks([left, right], _filters(), np.zeros(SHAPE, dtype=bool))
    assert len(out) == 2
    a, b = (g.pixels for g, _ in out)
    assert a.sum() > left.area_px  # both filled
    assert b.sum() > right.area_px
    assert not (a & b).any()


@pytest.mark.parametrize("own_break", [False, True])
def test_absorb_never_takes_a_region_with_its_own_break(monkeypatch, own_break):
    """A small region in a larger region's slit joins it only when it has no break of its own."""
    big_pixels = _box((40, 160), (20, 180), slit=4)
    small_pixels = _box((96, 104), (60, 140)) & ~big_pixels

    def find(_z, domain, *_):
        return [BREAK] if own_break or (domain & big_pixels).any() else []

    monkeypatch.setattr(analysis, "find_phase_breaks", find)
    big = _survivor(big_pixels, 0.0, 10.0)
    small = _survivor(small_pixels, 5.0, 9.0)  # not _compatible: no bridge
    out = analysis._with_phase_breaks([big, small], _filters(), np.zeros(SHAPE, dtype=bool))
    assert len(out) == (2 if own_break else 1)


def test_phase_breaks_only_in_reported_regions():
    """At threshold=inf nothing is reported, so nothing is searched."""
    from breaks import break_region_case

    s, _ = break_region_case(10, math.pi, 0.0)
    report = analyse(s.frame, threshold=math.inf)
    assert report.regions == ()
    assert report.phase_breaks == ()
