"""Synthetic L2 granule builders for tests."""

from datetime import datetime

import netCDF4 as nc
import numpy as np

_EPOCH93 = datetime(1993, 1, 1)


def _tai93(dt):
    return (dt - _EPOCH93).total_seconds()


def make_viirs_granule(path, *, lat, lon, aod_land, qa_land, eu_land, scan_dt):
    """Write a minimal AERDB_L2-shaped NetCDF granule."""

    lat = np.asarray(lat, np.float32)
    lon = np.asarray(lon, np.float32)
    aod_land = np.asarray(aod_land, np.float32)
    qa_land = np.asarray(qa_land, np.float64)
    eu_land = np.asarray(eu_land, np.float32)
    na, nx = lat.shape
    ds = nc.Dataset(path, "w", format="NETCDF4")
    try:
        ds.createDimension("Idx_Atrack", na)
        ds.createDimension("Idx_Xtrack", nx)
        dims = ("Idx_Atrack", "Idx_Xtrack")

        def write(name, values, dtype="f4", fill=None):
            if fill is not None:
                var = ds.createVariable(name, dtype, dims, fill_value=fill)
            else:
                var = ds.createVariable(name, dtype, dims)
            var[:] = values

        write("Latitude", lat)
        write("Longitude", lon)
        write("Aerosol_Optical_Thickness_550_Land", aod_land, fill=-999.0)
        write(
            "Aerosol_Optical_Thickness_550_Ocean",
            np.full((na, nx), -999.0, np.float32),
            fill=-999.0,
        )
        write("Aerosol_Optical_Thickness_550_Expected_Uncertainty_Land", eu_land)
        write(
            "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Ocean",
            np.full((na, nx), -999.0, np.float32),
        )
        write("Aerosol_Optical_Thickness_QA_Flag_Land", qa_land, "f8")
        write("Aerosol_Optical_Thickness_QA_Flag_Ocean", np.zeros((na, nx)), "f8")
        write(
            "Scan_Start_Time",
            np.full((na, nx), _tai93(scan_dt), np.float64),
            "f8",
        )
    finally:
        ds.close()


def make_modis_granule(path, *, lat, lon, aod, qa, alg, scan_dt):
    """Write a MOD04/MYD04-style combined AOD swath as NetCDF."""

    lat = np.asarray(lat, np.float32)
    lon = np.asarray(lon, np.float32)
    aod = np.asarray(aod, np.float64)
    qa = np.asarray(qa, np.int16)
    alg = np.asarray(alg, np.int16)
    na, nx = lat.shape
    ds = nc.Dataset(path, "w", format="NETCDF4")
    try:
        ds.createDimension("Cell_Along_Swath", na)
        ds.createDimension("Cell_Across_Swath", nx)
        dims = ("Cell_Along_Swath", "Cell_Across_Swath")

        def write(name, values, dtype, fill=None):
            if fill is not None:
                var = ds.createVariable(name, dtype, dims, fill_value=fill)
            else:
                var = ds.createVariable(name, dtype, dims)
            var[:] = values

        write("Latitude", lat, "f4")
        write("Longitude", lon, "f4")
        aod_fill = np.where(aod < 0, -999.0, aod).astype(np.float32)
        write("AOD_550_Dark_Target_Deep_Blue_Combined", aod_fill, "f4", fill=-999.0)
        write("AOD_550_Dark_Target_Deep_Blue_Combined_QA_Flag", qa, "i2")
        write("AOD_550_Dark_Target_Deep_Blue_Combined_Algorithm_Flag", alg, "i2")
        write(
            "Scan_Start_Time",
            np.full((na, nx), _tai93(scan_dt), np.float64),
            "f8",
        )
    finally:
        ds.close()
