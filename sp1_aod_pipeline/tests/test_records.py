from datetime import datetime

import numpy as np

from sp1_aod_pipeline.records import CellGrid, L2Record, tai93_to_datetime64


def test_tai93_to_datetime64():
    sec = (datetime(2020, 6, 15, 1) - datetime(1993, 1, 1)).total_seconds()
    out = tai93_to_datetime64(np.array([sec, np.nan]))
    assert out[0] == np.datetime64("2020-06-15T01:00:00")
    assert np.isnat(out[1])


def test_tai93_huge_fill_values_become_nat_without_warning(recwarn):
    out = tai93_to_datetime64(np.array([9.96921e36, -9.96921e36]))
    assert np.isnat(out).all()
    assert len(recwarn) == 0


def test_cellgrid_empty_shapes_and_fill():
    grid = CellGrid.empty()
    assert grid.mean.shape == (192, 288)
    assert grid.mean.dtype == np.float32
    assert float(grid.mean[0, 0]) == -999.0
    assert float(grid.sigma[0, 0]) == -999.0
    assert grid.count.dtype == np.int32
    assert int(grid.count.max()) == 0


def test_l2record_holds_arrays():
    record = L2Record(
        "viirs",
        np.zeros(2, np.float32),
        np.zeros(2, np.float32),
        np.zeros(2, np.float32),
        np.ones(2, np.float32),
        np.full(2, 3, np.float32),
        np.full(2, np.datetime64("2020-06-15T00:00:00"), "datetime64[ns]"),
    )
    assert record.sensor == "viirs"
    assert record.aod.shape == (2,)
