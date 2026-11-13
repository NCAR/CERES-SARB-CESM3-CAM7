from datetime import datetime

import numpy as np

from sp1_aod_pipeline.config import RunConfig
from sp1_aod_pipeline.f09_grid import f09_lat, f09_lon
from sp1_aod_pipeline.grid import bin_record_to_f09, simple_mean_grid
from sp1_aod_pipeline.records import L2Record


def _cfg():
    return RunConfig(
        modis_dir="m",
        viirs_dir="v",
        out_dir="o",
        start=datetime(2020, 6, 15).date(),
        end=datetime(2020, 6, 15).date(),
    )


def _rec(lat, lon, aod, sigma):
    n = len(lat)
    return L2Record(
        "viirs",
        np.array(lat, np.float32),
        np.array(lon, np.float32),
        np.array(aod, np.float32),
        np.array(sigma, np.float32),
        np.full(n, 3, np.float32),
        np.full(n, np.datetime64("2020-06-15T01:00:00"), "datetime64[ns]"),
    )


def test_two_pixels_same_cell_inverse_variance():
    lat0 = float(f09_lat()[96])
    lon0 = float(f09_lon()[1])
    rec = _rec([lat0, lat0], [lon0, lon0], [0.4, 0.8], [0.1, 0.2])
    grid = bin_record_to_f09(rec, np.array([True, True]), _cfg())
    w1, w2 = 1 / 0.1**2, 1 / 0.2**2
    expected = (w1 * 0.4 + w2 * 0.8) / (w1 + w2)
    assert np.isclose(grid.mean[96, 1], expected, atol=1e-5)
    assert np.isclose(grid.sigma[96, 1], np.sqrt(1 / (w1 + w2)), atol=1e-5)
    assert grid.count[96, 1] == 2


def test_empty_cells_are_fill():
    rec = _rec([float(f09_lat()[96])], [1.25], [0.5], [0.1])
    grid = bin_record_to_f09(rec, np.array([True]), _cfg())
    assert grid.count.sum() == 1
    assert (grid.mean == -999.0).sum() == 192 * 288 - 1
    assert grid.mean.dtype == np.float32
    assert grid.count.dtype == np.int32


def test_lon_wrap_assigns_cell_zero():
    rec = _rec([float(f09_lat()[96])], [359.9], [0.6], [0.1])
    grid = bin_record_to_f09(rec, np.array([True]), _cfg())
    assert grid.count[96, 0] == 1


def test_near_pole_pixels_map_to_polar_rows():
    lon0 = float(f09_lon()[1])
    grid = bin_record_to_f09(
        _rec([-89.9, 89.9], [lon0, lon0], [0.3, 0.3], [0.1, 0.1]),
        np.array([True, True]),
        _cfg(),
    )
    assert grid.count[0, 1] == 1
    assert grid.count[191, 1] == 1


def test_invalid_pixels_excluded():
    lat0 = float(f09_lat()[96])
    lon0 = float(f09_lon()[1])
    rec = _rec([lat0, lat0], [lon0, lon0], [0.4, 9.9], [0.1, 0.1])
    grid = bin_record_to_f09(rec, np.array([True, False]), _cfg())
    assert grid.count[96, 1] == 1
    assert np.isclose(grid.mean[96, 1], 0.4)


def test_simple_mean_grid_is_count_average():
    lat0 = float(f09_lat()[96])
    lon0 = float(f09_lon()[1])
    rec = _rec([lat0, lat0], [lon0, lon0], [0.4, 0.8], [0.1, 0.2])
    mean = simple_mean_grid(rec, np.array([True, True]), _cfg())
    assert np.isclose(mean[96, 1], (0.4 + 0.8) / 2, atol=1e-5)
    assert mean.dtype == np.float32
    assert float(mean[0, 0]) == -999.0
