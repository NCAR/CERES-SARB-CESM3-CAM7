from datetime import datetime

import numpy as np
import xarray as xr

from sp1_aod_pipeline.config import RunConfig
from sp1_aod_pipeline.ingest_viirs import (
    read_viirs_granule,
    viirs_record_from_dataset,
)
from sp1_aod_pipeline.tests.fixtures import make_viirs_granule


def _cfg():
    return RunConfig(
        modis_dir="m",
        viirs_dir="v",
        out_dir="o",
        start=datetime(2020, 6, 15).date(),
        end=datetime(2020, 6, 15).date(),
    )


def test_read_viirs_granule_via_davinci_reader(tmp_path):
    lat = np.array([[10.0, 10.0], [11.0, 11.0]], np.float32)
    lon = np.array([[20.0, 21.0], [20.0, 21.0]], np.float32)
    aod = np.array([[0.30, -999.0], [0.50, 0.40]], np.float32)
    qa = np.array([[3, 0], [2, 1]], np.float64)
    eu = np.array([[0.10, 0.10], [0.12, 0.08]], np.float32)
    path = str(tmp_path / "AERDB_L2_VIIRS_NOAA20.A2020167.0100.002.x.nc")
    make_viirs_granule(
        path,
        lat=lat,
        lon=lon,
        aod_land=aod,
        qa_land=qa,
        eu_land=eu,
        scan_dt=datetime(2020, 6, 15, 1, 0, 0),
    )
    record = read_viirs_granule(path, _cfg())
    assert record.sensor == "viirs"
    assert record.aod.shape == (4,)
    assert record.aod.dtype == np.float32
    assert np.isclose(record.aod[0], 0.30)
    assert np.isclose(record.sigma[0], 0.10)
    assert record.qa[0] == 3
    assert record.time[0] == np.datetime64("2020-06-15T01:00:00")
    assert not np.isfinite(record.aod[1])


def test_viirs_record_from_dataset_sigma_is_abs_uncertainty():
    ds = xr.Dataset(
        {
            "Aerosol_Optical_Thickness_550_Land": (
                ("Idx_Atrack", "Idx_Xtrack"),
                [[0.2]],
            ),
            "Aerosol_Optical_Thickness_550_Ocean": (
                ("Idx_Atrack", "Idx_Xtrack"),
                [[-999.0]],
            ),
            "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Land": (
                ("Idx_Atrack", "Idx_Xtrack"),
                [[-0.05]],
            ),
            "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Ocean": (
                ("Idx_Atrack", "Idx_Xtrack"),
                [[-999.0]],
            ),
            "Aerosol_Optical_Thickness_QA_Flag_Land": (
                ("Idx_Atrack", "Idx_Xtrack"),
                [[3.0]],
            ),
            "Aerosol_Optical_Thickness_QA_Flag_Ocean": (
                ("Idx_Atrack", "Idx_Xtrack"),
                [[0.0]],
            ),
            "Scan_Start_Time": (("Idx_Atrack", "Idx_Xtrack"), [[0.0]]),
        },
        coords={
            "lat": (("Idx_Atrack", "Idx_Xtrack"), [[0.0]]),
            "lon": (("Idx_Atrack", "Idx_Xtrack"), [[0.0]]),
        },
    )
    record = viirs_record_from_dataset(ds, _cfg())
    assert np.isclose(record.sigma[0], 0.05)
