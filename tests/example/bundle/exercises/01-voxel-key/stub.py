from __future__ import annotations

import math

from gridsnap.snap import Point, VoxelKey


def voxel_key(point: Point, size: float) -> VoxelKey:
    """The integer index of the voxel of edge ``size`` that contains ``point``."""
    raise NotImplementedError
