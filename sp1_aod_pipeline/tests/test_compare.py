from datetime import datetime

import numpy as np
import pandas as pd
import xarray as xr

from sp1_aod_pipeline.contract import FILL_FLOAT, write_contract_file
from sp1_aod_pipeline.f09_grid import f09_lat, f09_lon
from sp1_aod_pipeline.validation.compare import (
    colocate,
    colocate_pointstrategy,
    error_stats,
    season_of,
    seasonal_error_stats,
)


def test_error_stats_uses_davinci_metrics():
    stats = error_stats(np.array([0.5, 0.7, 0.3]), np.array([0.4, 0.7, 0.5]))

    assert stats["n"] == 3
    assert np.isclose(stats["bias"], (0.1 + 0.0 - 0.2) / 3)
    assert np.isclose(stats["mae"], (0.1 + 0.0 + 0.2) / 3)
    assert np.isclose(stats["rmse"], np.sqrt((0.1**2 + 0.0 + 0.2**2) / 3))


def test_colocate_nearest_cell():
    lat = f09_lat()
    lon = f09_lon()
    aod = np.full((192, 288), float(FILL_FLOAT), np.float32)
    aod[96, 1] = 0.42
    ds = xr.Dataset(
        {"aod_weighted_mean": (("lat", "lon"), aod)},
        coords={"lat": lat, "lon": lon},
    )
    df = pd.DataFrame(
        {
            "site": ["S1", "S2"],
            "lat": [float(lat[96]), float(lat[96])],
            "lon": [float(lon[1]), float(lon[1])],
            "time": np.array(
                ["2020-06-15T01:00:00", "2020-06-15T09:00:00"],
                dtype="datetime64[ns]",
            ),
            "aod550": [0.40, 0.99],
        }
    )

    pairs = colocate(ds, df, datetime(2020, 6, 15, 0), datetime(2020, 6, 15, 3))

    assert len(pairs) == 1
    assert pairs.iloc[0]["site"] == "S1"
    assert np.isclose(pairs.iloc[0]["sat"], 0.42)
    assert np.isclose(pairs.iloc[0]["aeronet"], 0.40)


def test_colocate_drops_nan_grid_cells():
    lat = f09_lat()
    lon = f09_lon()
    aod = np.full((192, 288), np.nan, np.float32)
    ds = xr.Dataset(
        {"aod_weighted_mean": (("lat", "lon"), aod)},
        coords={"lat": lat, "lon": lon},
    )
    df = pd.DataFrame(
        {
            "site": ["S1"],
            "lat": [float(lat[96])],
            "lon": [float(lon[1])],
            "time": np.array(["2020-06-15T01:00:00"], dtype="datetime64[ns]"),
            "aod550": [0.40],
        }
    )

    pairs = colocate(ds, df, datetime(2020, 6, 15, 0), datetime(2020, 6, 15, 3))

    assert pairs.empty


def test_seasonal_error_stats():
    assert season_of(np.datetime64("2020-01-15")) == "DJF"
    assert season_of(np.datetime64("2020-07-15")) == "JJA"
    pairs = pd.DataFrame(
        {
            "site": ["A", "B", "C"],
            "aeronet": [0.40, 0.50, 0.30],
            "sat": [0.45, 0.55, 0.20],
            "time": np.array(
                ["2020-01-10", "2020-01-20", "2020-07-05"],
                dtype="datetime64[ns]",
            ),
        }
    )

    stats = seasonal_error_stats(pairs)

    assert set(stats) == {"DJF", "JJA"}
    assert stats["DJF"]["n"] == 2
    assert stats["JJA"]["n"] == 1
    assert np.isclose(stats["JJA"]["mae"], abs(0.20 - 0.30))


def test_colocate_pointstrategy_matches_cell(tmp_path):
    lat = f09_lat()
    lon = f09_lon()
    mean = np.full((192, 288), float(FILL_FLOAT), np.float32)
    uncertainty = np.full((192, 288), float(FILL_FLOAT), np.float32)
    count = np.zeros((192, 288), np.int32)
    ilon = 227
    mean[96, ilon] = 0.42
    uncertainty[96, ilon] = 0.05
    count[96, ilon] = 4
    contract_path = str(tmp_path / "contract.nc")
    write_contract_file(
        contract_path,
        window_start=datetime(2020, 6, 15, 0, 0, 0),
        aod_weighted_mean=mean,
        aod_uncertainty=uncertainty,
        aod_count=count,
    )
    df = pd.DataFrame(
        {
            "site": ["S1"],
            "lat": [float(lat[96])],
            "lon": [float(lon[ilon] - 360.0)],
            "time": np.array(["2020-06-15T01:30:00"], dtype="datetime64[ns]"),
            "aod550": [0.40],
        }
    )

    paired = colocate_pointstrategy(contract_path, df)

    value = float(np.asarray(paired["y_aod_weighted_mean"]).ravel()[0])
    assert np.isclose(value, 0.42, atol=1e-4)
