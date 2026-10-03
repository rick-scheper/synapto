from __future__ import annotations

import math

from gridsnap.snap import Point, VoxelKey


def voxel_key(point: Point, size: float) -> VoxelKey:
    """The integer index of the voxel of edge ``size`` that contains ``point``."""
    if size <= 0:
        raise ValueError(f"voxel size must be positive, got {size}")
    x, y, z = point
    return (math.floor(x / size), math.floor(y / size), math.floor(z / size))
