"""Find stripes in noisy camera intensity frames."""

from denoisifier.analysis import analyse
from denoisifier.frame_io import FrameFile, read_frame
from denoisifier.report import BinFactors, BoundingBox, Region, Report

__all__ = ["BinFactors", "BoundingBox", "FrameFile", "Region", "Report", "analyse", "read_frame"]
