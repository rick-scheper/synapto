from __future__ import annotations

from collections.abc import Iterable

from gridsnap.snap import Point, VoxelKey, voxel_key


def downsample(points: Iterable[Point], size: float) -> list[Point]:
    """Replace the points in each occupied voxel by their centroid, in first-seen order."""
    sums: dict[VoxelKey, list[float]] = {}
    for x, y, z in points:
        acc = sums.setdefault(voxel_key((x, y, z), size), [0.0, 0.0, 0.0, 0.0])
        acc[0] += x
        acc[1] += y
        acc[2] += z
        acc[3] += 1
    return [(sx / n, sy / n, sz / n) for sx, sy, sz, n in sums.values()]
