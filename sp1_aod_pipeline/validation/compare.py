"""AERONET co-location and error statistics for SP1 validation."""

import numpy as np
import pandas as pd
import xarray as xr
from davinci_monet.pairing.strategies.point import PointStrategy
from davinci_monet.stats.metrics import get_metric

from ..contract import EPOCH, FILL_FLOAT

_SEASON = {
    12: "DJF",
    1: "DJF",
    2: "DJF",
    3: "MAM",
    4: "MAM",
    5: "MAM",
    6: "JJA",
    7: "JJA",
    8: "JJA",
    9: "SON",
    10: "SON",
    11: "SON",
}


def error_stats(sat, obs):
    sat = np.asarray(sat, np.float64)
    obs = np.asarray(obs, np.float64)
    n = int(get_metric("N").compute(obs, sat))
    if n == 0:
        return {"n": 0, "bias": float("nan"), "mae": float("nan"), "rmse": float("nan")}
    return {
        "n": n,
        "bias": float(get_metric("MB").compute(obs, sat)),
        "mae": float(get_metric("ME").compute(obs, sat)),
        "rmse": float(get_metric("RMSE").compute(obs, sat)),
    }


def season_of(dt):
    return _SEASON[pd.Timestamp(dt).month]


def _times_utc_naive(values):
    times = pd.to_datetime(values, utc=True)
    if isinstance(times, pd.Series):
        times = times.dt.tz_convert(None)
    else:
        times = times.tz_convert(None)
    return times.to_numpy(dtype="datetime64[ns]")


def _timestamp_utc_naive(value):
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return np.datetime64(timestamp.to_datetime64())


def colocate(ds, aeronet_df, start, end):
    lat = ds["lat"].values
    lon = ds["lon"].values
    aod = ds["aod_weighted_mean"].values
    times = _times_utc_naive(aeronet_df["time"])
    start64 = np.datetime64(start)
    end64 = np.datetime64(end)
    sub = aeronet_df.loc[(times >= start64) & (times < end64)]
    rows = []
    for _, row in sub.iterrows():
        ilat = int(np.argmin(np.abs(lat - row["lat"])))
        site_lon = float(row["lon"]) % 360.0
        distance = np.abs(((lon - site_lon + 180.0) % 360.0) - 180.0)
        ilon = int(np.argmin(distance))
        value = float(aod[ilat, ilon])
        if np.isfinite(value) and value != float(FILL_FLOAT):
            rows.append(
                (
                    row["site"],
                    float(row["aod550"]),
                    value,
                    _timestamp_utc_naive(row["time"]),
                )
            )
    return pd.DataFrame(rows, columns=["site", "aeronet", "sat", "time"])


def seasonal_error_stats(pairs):
    if len(pairs) == 0:
        return {}
    seasons = pairs["time"].map(season_of)
    out = {}
    for season in sorted(set(seasons)):
        sub = pairs[seasons == season]
        out[season] = error_stats(sub["sat"].values, sub["aeronet"].values)
    return out


def colocate_pointstrategy(contract_path, aeronet_df, radius_m=200000.0):
    with xr.open_dataset(contract_path, decode_times=False) as grid:
        data = np.where(
            grid["aod_weighted_mean"].values == float(FILL_FLOAT),
            np.nan,
            grid["aod_weighted_mean"].values,
        )
        center = pd.Timestamp(EPOCH) + pd.to_timedelta(
            float(grid["time"].values), unit="h"
        )
        time = np.array([center.to_datetime64()], dtype="datetime64[ns]")
        y_data = xr.Dataset(
            {"aod_weighted_mean": (("time", "lat", "lon"), data[None])},
            coords={
                "time": time,
                "lat": grid["lat"].values,
                "lon": grid["lon"].values,
            },
        )

    df = aeronet_df.reset_index(drop=True)
    x_data = xr.Dataset(
        {"aeronet": (("time", "site"), df["aod550"].astype(float).values[None])},
        coords={
            "time": time,
            "site": df["site"].astype(str).values,
            "lat": ("site", df["lat"].astype(float).values),
            "lon": ("site", np.mod(df["lon"].astype(float).values, 360.0)),
        },
    )
    return PointStrategy().pair_sources(
        x_data=x_data,
        y_data=y_data,
        radius_of_influence=radius_m,
    )
