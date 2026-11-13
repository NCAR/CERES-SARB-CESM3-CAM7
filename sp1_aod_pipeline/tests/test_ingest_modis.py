from datetime import datetime

import numpy as np
import xarray as xr

from sp1_aod_pipeline.config import RunConfig
from sp1_aod_pipeline.ingest_modis import (
    _modis_record_from_arrays,
    modis_record_from_dataset,
    read_modis_granule,
)
from sp1_aod_pipeline.tests.fixtures import make_modis_granule


def _cfg():
    return RunConfig(
        modis_dir="m",
        viirs_dir="v",
        out_dir="o",
        start=datetime(2020, 6, 15).date(),
        end=datetime(2020, 6, 15).date(),
    )


def test_pure_transform_ee_selection():
    lat = np.array([0.0, 1.0])
    lon = np.array([0.0, 1.0])
    aod = np.array([0.4, 0.4])
    qa = np.array([3, 3])
    alg = np.array([1, 0])
    scan_time = np.array([0.0, 0.0])
    record = _modis_record_from_arrays(lat, lon, aod, qa, alg, scan_time, _cfg())
    assert record.sensor == "modis"
    assert np.isclose(record.sigma[0], 0.05 + 0.15 * 0.4)
    assert np.isclose(record.sigma[1], 0.03 + 0.05 * 0.4)


def test_read_modis_granule_roundtrip_netcdf(tmp_path):
    lat = np.array([[10.0, 10.0], [11.0, 11.0]], np.float32)
    lon = np.array([[20.0, 21.0], [20.0, 21.0]], np.float32)
    aod = np.array([[0.30, -1.0], [0.50, 0.40]])
    qa = np.array([[3, 0], [2, 1]])
    alg = np.array([[1, 1], [0, 1]])
    path = str(tmp_path / "MOD04_L2.A2020167.0100.061.nc")
    make_modis_granule(
        path,
        lat=lat,
        lon=lon,
        aod=aod,
        qa=qa,
        alg=alg,
        scan_dt=datetime(2020, 6, 15, 1, 0, 0),
    )
    record = read_modis_granule(path, _cfg())
    assert record.aod.shape == (4,)
    assert np.isclose(record.aod[0], 0.30, atol=1e-3)
    assert np.isnan(record.aod[1])
    assert record.time[0] == np.datetime64("2020-06-15T01:00:00")


def test_modis_record_from_dataset_reads_standardized_coords():
    ds = xr.Dataset(
        {
            "AOD_550_Dark_Target_Deep_Blue_Combined": (("y", "x"), [[0.6]]),
            "AOD_550_Dark_Target_Deep_Blue_Combined_QA_Flag": (
                ("y", "x"),
                [[3]],
            ),
            "AOD_550_Dark_Target_Deep_Blue_Combined_Algorithm_Flag": (
                ("y", "x"),
                [[1]],
            ),
            "Scan_Start_Time": (("y", "x"), [[0.0]]),
        },
        coords={
            "lat": (("y", "x"), [[5.0]]),
            "lon": (("y", "x"), [[6.0]]),
        },
    )
    record = modis_record_from_dataset(ds, _cfg())
    assert np.isclose(record.aod[0], 0.6)
    assert np.isclose(record.sigma[0], 0.05 + 0.15 * 0.6)
