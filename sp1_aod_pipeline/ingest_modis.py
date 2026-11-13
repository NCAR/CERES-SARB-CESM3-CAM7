"""Adapt DAVINCI MODIS L2 AOD reader output into an SP1 L2Record."""

import numpy as np
import xarray as xr

from davinci_monet.datasets.satellite.modis_l2_aod import MODISL2AODReader

from .records import L2Record, tai93_to_datetime64

_COMBINED = "AOD_550_Dark_Target_Deep_Blue_Combined"


def _modis_record_from_arrays(lat, lon, aod, qa, alg_flag, scan_time, cfg):
    lat = np.asarray(lat).ravel()
    lon = np.asarray(lon).ravel()
    aod = np.asarray(aod, np.float64).ravel()
    qa = np.asarray(qa, np.float64).ravel()
    alg = np.asarray(alg_flag, np.float64).ravel()
    scan_time = np.asarray(scan_time, np.float64).ravel()

    land = alg == 1
    ee0 = np.where(land, cfg.modis_ee_land[0], cfg.modis_ee_ocean[0])
    ee1 = np.where(land, cfg.modis_ee_land[1], cfg.modis_ee_ocean[1])
    sigma = ee0 + ee1 * np.abs(aod)

    return L2Record(
        sensor="modis",
        lat=lat.astype(np.float32),
        lon=lon.astype(np.float32),
        aod=aod.astype(np.float32),
        sigma=sigma.astype(np.float32),
        qa=qa.astype(np.float32),
        time=tai93_to_datetime64(scan_time),
    )


def modis_record_from_dataset(ds, cfg):
    lat = (ds["lat"] if "lat" in ds else ds["Latitude"]).values
    lon = (ds["lon"] if "lon" in ds else ds["Longitude"]).values
    return _modis_record_from_arrays(
        lat,
        lon,
        ds[_COMBINED].values,
        ds[f"{_COMBINED}_QA_Flag"].values,
        ds[f"{_COMBINED}_Algorithm_Flag"].values,
        ds["Scan_Start_Time"].values,
        cfg,
    )


def read_modis_granule(path, cfg):
    if str(path).lower().endswith((".hdf", ".hdf4", ".he2", ".he5")):
        ds = MODISL2AODReader().open([path])
    else:
        ds = xr.open_dataset(path, decode_times=False)
    try:
        return modis_record_from_dataset(ds, cfg)
    finally:
        ds.close()
