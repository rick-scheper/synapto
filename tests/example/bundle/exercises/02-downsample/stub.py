from __future__ import annotations

from collections.abc import Iterable

from gridsnap.snap import Point, VoxelKey, voxel_key


def downsample(points: Iterable[Point], size: float) -> list[Point]:
    """Replace the points in each occupied voxel by their centroid, in first-seen order."""
    raise NotImplementedError
