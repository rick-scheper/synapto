"""Downsample a point cloud by keeping one point per voxel."""

from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path

Point = tuple[float, float, float]
VoxelKey = tuple[int, int, int]


def read_xyz(path: str | Path) -> list[Point]:
    """Read whitespace-separated x y z lines; blank lines and # comments are skipped."""
    points = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            x, y, z = (float(v) for v in line.split())
            points.append((x, y, z))
    return points


def voxel_key(point: Point, size: float) -> VoxelKey:
    """The integer index of the voxel of edge ``size`` that contains ``point``.

    Uses floor, not int(): int() truncates toward zero, which would put -0.5
    and 0.5 in the same voxel.
    """
    if size <= 0:
        raise ValueError(f"voxel size must be positive, got {size}")
    x, y, z = point
    return (math.floor(x / size), math.floor(y / size), math.floor(z / size))


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
