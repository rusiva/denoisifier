"""Find stripes in noisy camera intensity frames."""

from denoisifier.analysis import analyse
from denoisifier.frame_io import FrameFile, read_frame
from denoisifier.report import BoundingBox, Region, Report

__all__ = ["BoundingBox", "FrameFile", "Region", "Report", "analyse", "read_frame"]
