from __future__ import annotations

import importlib.util
import sys
from datetime import date
from datetime import datetime
from pathlib import Path

import netCDF4 as nc
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_modis_era5_grid.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("prepare_modis_era5_grid", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_accumulator_filters_and_bins_to_expected_cells():
    m = _load_module()
    lat = np.array([-1.0, 1.0, 1.0, 80.0, 1.0])
    lon = np.array([-1.0, 1.0, 1.0, 10.0, 1.0])
    time_sec = np.array([10.0, 10.0, 20.0, 10.0, 10.0])
    aod = np.array([0.2, 0.4, 0.6, 9.0, 0.8])
    qa = np.array([1, 1, 1, 1, 0])

    grid = m.Grid(
        lat=np.array([-1.0, 1.0]),
        lon=np.array([1.0, 359.0]),
        lat_edges=np.array([-2.0, 0.0, 2.0]),
        lon_edges=np.array([0.0, 180.0, 360.0]),
    )
    acc = m.Accumulator.empty(nwin=1, nlat=2, nlon=2, stream_names=("terra_dt",))
    m.accumulate_pixels(
        acc,
        grid,
        window_edges=np.array([0.0, 10800.0]),
        lat=lat,
        lon=lon,
        time_seconds=time_sec,
        aod=aod,
        qa=qa,
        qa_min=1,
        aod_min=0.0,
        aod_max=5.0,
        source="terra_dt",
    )

    mean, unc, count = acc.finalize(fill=-999.0)
    assert count.sum() == 3
    assert count[0, 0, 1] == 1  # lon=-1 normalized to 359, lat=-1
    assert count[0, 1, 0] == 2
    assert mean[0, 1, 0] == 0.5
    assert np.isclose(unc[0, 1, 0], np.sqrt(0.02 / 2.0))
    assert mean[0, 0, 0] == -999.0
    assert acc.stream_counts["terra_dt"].sum() == 3


def test_count_weighted_streams_count_dt_and_db_same_pixel_separately():
    m = _load_module()
    grid = m.Grid(
        lat=np.array([0.0]),
        lon=np.array([0.0]),
        lat_edges=np.array([-0.5, 0.5]),
        lon_edges=np.array([-0.5, 0.5]),
    )
    acc = m.Accumulator.empty(
        nwin=1,
        nlat=1,
        nlon=1,
        stream_names=("terra_dt", "terra_db", "aqua_dt", "aqua_db"),
    )
    for source, aod in (
        ("terra_dt", 0.2),
        ("terra_db", 0.6),
        ("aqua_dt", 0.4),
        ("aqua_db", 0.8),
    ):
        m.accumulate_pixels(
            acc,
            grid,
            window_edges=np.array([0.0, 10800.0]),
            lat=np.array([0.0]),
            lon=np.array([0.0]),
            time_seconds=np.array([10.0]),
            aod=np.array([aod]),
            qa=np.array([1]),
            qa_min=1,
            aod_min=0.0,
            aod_max=5.0,
            source=source,
        )

    mean, _unc, count = acc.finalize(fill=-999.0)
    assert count[0, 0, 0] == 4
    assert mean[0, 0, 0] == 0.5
    for source in ("terra_dt", "terra_db", "aqua_dt", "aqua_db"):
        assert acc.stream_counts[source][0, 0, 0] == 1


def test_write_outputs_copy_era5_grid_and_contract_fields(tmp_path):
    m = _load_module()
    era5 = tmp_path / "era5.nc"
    with nc.Dataset(era5, "w") as ds:
        ds.createDimension("lat", 2)
        ds.createDimension("lon", 2)
        ds.createVariable("lat", "f8", ("lat",))[:] = [-1.0, 1.0]
        ds.createVariable("lon", "f8", ("lon",))[:] = [0.0, 180.0]

    grid = m.read_era5_grid(era5)
    mean = np.array([[[0.2, -999.0], [0.4, 0.6]]], dtype=np.float32)
    unc = np.array([[[0.0, -999.0], [0.1, 0.2]]], dtype=np.float32)
    count = np.array([[[1, 0], [2, 3]]], dtype=np.int32)
    out = tmp_path / "out"

    paths = m.write_outputs(
        out,
        grid,
        day=date(2008, 7, 1),
        window_starts=np.array([0.0]),
        mean=mean,
        uncertainty=unc,
        count=count,
        stream_counts={
            "terra_dt": count,
            "terra_db": count * 2,
            "aqua_dt": count * 3,
            "aqua_db": count * 4,
        },
        source_files=5,
        source_granules="MOD04_L2/MYD04_L2",
    )

    assert len(paths) == 1
    with nc.Dataset(paths[0]) as ds:
        np.testing.assert_allclose(ds["lat"][:], [-1.0, 1.0])
        np.testing.assert_allclose(ds["lon"][:], [0.0, 180.0])
        assert ds["aod_weighted_mean"].shape == (2, 2)
        assert ds["aod_weighted_mean_modis"].shape == (2, 2)
        assert ds["aod_count"][:].sum() == 6
        assert ds["aod_count_terra_dt"][:].sum() == 6
        assert ds["aod_count_terra_db"][:].sum() == 12
        assert ds["aod_count_aqua_dt"][:].sum() == 18
        assert ds["aod_count_aqua_db"][:].sum() == 24
        assert ds["aod_weighted_mean"].units == "1"
        assert ds.getncattr("grid") == "ERA5_fv09 lat/lon"
        assert ds.getncattr("source_granules") == "MOD04_L2/MYD04_L2"
        assert ds.getncattr("merge_method") == (
            "count-weighted mean of valid Terra/Aqua Dark Target and Deep Blue observations "
            "per 3-hour grid cell"
        )
        expected_start = (datetime(2008, 7, 1) - datetime(2000, 1, 1)).total_seconds() / 3600
        assert float(ds["time"][:]) == expected_start + 1.5
        np.testing.assert_allclose(ds["time_bnds"][:], [expected_start, expected_start + 3.0])
