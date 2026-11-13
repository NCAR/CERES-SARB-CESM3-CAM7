"""Adapt DAVINCI VIIRS AERDB_L2 reader output into an SP1 L2Record."""

import numpy as np

from davinci_monet.datasets.satellite.viirs_l2_aerdb import VIIRSL2AERDBReader

from .records import L2Record, tai93_to_datetime64


def viirs_record_from_dataset(ds, cfg):
    """Merge VIIRS land/ocean surfaces, preferring valid land retrievals."""

    aod_land = ds["Aerosol_Optical_Thickness_550_Land"].values
    aod_ocean = ds["Aerosol_Optical_Thickness_550_Ocean"].values
    qa_land = ds["Aerosol_Optical_Thickness_QA_Flag_Land"].values
    qa_ocean = ds["Aerosol_Optical_Thickness_QA_Flag_Ocean"].values
    eu_land = ds["Aerosol_Optical_Thickness_550_Expected_Uncertainty_Land"].values
    eu_ocean = ds["Aerosol_Optical_Thickness_550_Expected_Uncertainty_Ocean"].values
    lat = (ds["lat"] if "lat" in ds else ds["Latitude"]).values
    lon = (ds["lon"] if "lon" in ds else ds["Longitude"]).values
    scan_start_time = ds["Scan_Start_Time"].values

    land = np.isfinite(aod_land) & (np.asarray(qa_land, np.float64) > 0)
    aod = np.where(land, aod_land, aod_ocean)
    qa = np.where(land, qa_land, qa_ocean)
    expected_uncertainty = np.where(land, eu_land, eu_ocean)
    sigma = np.abs(expected_uncertainty)

    return L2Record(
        sensor="viirs",
        lat=np.asarray(lat).ravel().astype(np.float32),
        lon=np.asarray(lon).ravel().astype(np.float32),
        aod=np.asarray(aod).ravel().astype(np.float32),
        sigma=np.asarray(sigma).ravel().astype(np.float32),
        qa=np.asarray(qa).ravel().astype(np.float32),
        time=tai93_to_datetime64(scan_start_time),
    )


def read_viirs_granule(path, cfg):
    ds = VIIRSL2AERDBReader().open([path])
    try:
        return viirs_record_from_dataset(ds, cfg)
    finally:
        ds.close()
