import pytest

from candidate import downsample


def test_points_in_one_voxel_become_their_centroid():
    assert downsample([(0.0, 0.0, 0.0), (0.5, 0.5, 0.5)], 1.0) == [(0.25, 0.25, 0.25)]


def test_one_point_per_occupied_voxel_in_first_seen_order():
    points = [(1.5, 0.0, 0.0), (0.2, 0.0, 0.0), (1.7, 0.0, 0.0)]
    assert downsample(points, 1.0) == [pytest.approx((1.6, 0.0, 0.0)), (0.2, 0.0, 0.0)]


def test_points_either_side_of_zero_stay_apart():
    assert len(downsample([(-0.1, 0.0, 0.0), (0.1, 0.0, 0.0)], 1.0)) == 2


def test_empty_input():
    assert downsample([], 1.0) == []
