import pytest

from candidate import voxel_key


def test_positive_coordinates():
    assert voxel_key((0.5, 1.5, 2.5), 1.0) == (0, 1, 2)


def test_voxel_size_scales_the_index():
    assert voxel_key((0.5, 1.5, 2.5), 0.5) == (1, 3, 5)


def test_negative_coordinates_floor_toward_minus_infinity():
    assert voxel_key((-0.5, -1.5, 0.5), 1.0) == (-1, -2, 0)


def test_non_positive_size_raises():
    with pytest.raises(ValueError):
        voxel_key((0.0, 0.0, 0.0), 0)
