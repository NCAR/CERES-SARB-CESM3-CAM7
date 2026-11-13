"""AERONET cache loading and 550 nm interpolation for SP1 validation."""

import os
from datetime import timedelta

import numpy as np
import pandas as pd
import xarray as xr

AERONET_CACHE = "/glade/work/fillmore/Data/CERES-SARB-CAM7/AeroNet"
CACHE_TEMPLATE = "AeroNet_%Y%m%d.nc"
_AOD500 = "aod_500nm"
_ANGSTROM = "440-675_angstrom_exponent"


def aod_550_from_500(aod500, angstrom):
    aod500 = np.asarray(aod500, np.float64)
    angstrom = np.asarray(angstrom, np.float64)
    return aod500 * (550.0 / 500.0) ** (-angstrom)


def _to_long(ds):
    if "y" in ds.dims:
        ds = ds.squeeze("y", drop=True)
    site_dim = "site" if "site" in ds.dims else ("x" if "x" in ds.dims else None)

    out = xr.Dataset(
        {
            "aod550": ds[_AOD500] * (550.0 / 500.0) ** (-ds[_ANGSTROM]),
            "aod500": ds[_AOD500],
        }
    )
    if "siteid" in ds.variables:
        out["site_name"] = ds["siteid"]
    for source_names, dest_name in (
        (("lat", "latitude"), "lat"),
        (("lon", "longitude"), "lon"),
    ):
        for source_name in source_names:
            if source_name not in ds.variables:
                continue
            values = ds[source_name]
            extra_dims = [dim for dim in values.dims if dim != site_dim]
            out[dest_name] = values.mean(dim=extra_dims) if extra_dims else values
            break

    df = out.to_dataframe().reset_index()
    name_column = "site_name" if "site_name" in df.columns else site_dim
    df = df.rename(columns={name_column: "site"})
    df["site"] = df["site"].astype(str)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    valid = np.isfinite(df["aod500"]) & (df["aod500"] > 0.0) & np.isfinite(df["aod550"])
    return df.loc[valid, ["site", "lat", "lon", "time", "aod550"]].reset_index(
        drop=True
    )


def load_aeronet_file(path):
    with xr.open_dataset(path) as ds:
        return _to_long(ds)


def _download_day(day, cache_dir):
    from davinci_monet.datasets.surface.aeronet import AERONETReader

    dataset = AERONETReader().open(
        dates=[
            day.strftime("%Y-%m-%d"),
            (day + timedelta(days=1)).strftime("%Y-%m-%d"),
        ],
        product="AOD20",
        freq="H",
    )
    os.makedirs(cache_dir, exist_ok=True)
    dataset.to_netcdf(os.path.join(cache_dir, day.strftime(CACHE_TEMPLATE)))
    return _to_long(dataset)


def load_aeronet_days(days, cache_dir=AERONET_CACHE, download=True):
    frames = []
    for day in days:
        path = os.path.join(cache_dir, day.strftime(CACHE_TEMPLATE))
        if os.path.exists(path):
            frames.append(load_aeronet_file(path))
        elif download:
            frames.append(_download_day(day, cache_dir))
    columns = ["site", "lat", "lon", "time", "aod550"]
    return (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=columns)
    )
