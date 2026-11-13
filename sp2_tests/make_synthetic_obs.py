#!/usr/bin/env python3
"""Generate SP2 contract-conforming synthetic f09 AOD obs files."""

import argparse
import datetime as dt
import os

import numpy as np
from netCDF4 import Dataset


FILL_F = np.float32(-999.0)
FILL_I = np.int32(0)
EPOCH = dt.datetime(2000, 1, 1, 0, 0, 0)


def hours_since_2000(value):
    return (value - EPOCH).total_seconds() / 3600.0


def f09_grid():
    lat = np.linspace(-90.0, 90.0, 192)
    lon = np.arange(0.0, 360.0, 1.25)

    lat_b = np.zeros((lat.size, 2), dtype="f8")
    mid = (lat[:-1] + lat[1:]) / 2.0
    lat_b[1:, 0] = mid
    lat_b[:-1, 1] = mid
    lat_b[0, 0] = -90.0
    lat_b[-1, 1] = 90.0

    lon_b = np.zeros((lon.size, 2), dtype="f8")
    lon_b[:, 0] = lon - 0.625
    lon_b[:, 1] = lon + 0.625
    return lat, lon, lat_b, lon_b


def write_file(path, lat, lon, lat_b, lon_b, value, start_hours, center_hours, end_hours):
    aod = np.full((lat.size, lon.size), FILL_F, dtype="f4")
    jlat = np.where((lat >= 0.0) & (lat <= 40.0))[0]
    ilon = np.where((lon >= 200.0) & (lon <= 280.0))[0]
    aod[np.ix_(jlat, ilon)] = np.float32(value)
    valid = aod > -900.0

    with Dataset(path, "w", format="NETCDF4") as ds:
        ds.createDimension("lat", lat.size)
        ds.createDimension("lon", lon.size)
        ds.createDimension("nbnds", 2)

        vlat = ds.createVariable("lat", "f8", ("lat",))
        vlat[:] = lat
        vlat.units = "degrees_north"
        vlat.standard_name = "latitude"
        vlat.bounds = "lat_bnds"

        vlon = ds.createVariable("lon", "f8", ("lon",))
        vlon[:] = lon
        vlon.units = "degrees_east"
        vlon.standard_name = "longitude"
        vlon.bounds = "lon_bnds"

        ds.createVariable("lat_bnds", "f8", ("lat", "nbnds"))[:] = lat_b
        ds.createVariable("lon_bnds", "f8", ("lon", "nbnds"))[:] = lon_b

        vtime = ds.createVariable("time", "f8", ())
        vtime[...] = center_hours
        vtime.units = "hours since 2000-01-01 00:00:00 UTC"
        vtime.calendar = "gregorian"
        vtime.standard_name = "time"
        vtime.bounds = "time_bnds"
        ds.createVariable("time_bnds", "f8", ("nbnds",))[:] = np.array(
            [start_hours, end_hours], dtype="f8"
        )

        vaod = ds.createVariable(
            "aod_weighted_mean", "f4", ("lat", "lon"), fill_value=FILL_F
        )
        vaod[:] = aod
        vaod.units = "1"
        vaod.long_name = "Merged MODIS+VIIRS column AOD at 550 nm"
        vaod.standard_name = "atmosphere_optical_thickness_due_to_ambient_aerosol_particles"

        vunc = ds.createVariable("aod_uncertainty", "f4", ("lat", "lon"), fill_value=FILL_F)
        vunc[:] = np.where(valid, np.float32(0.05), FILL_F).astype("f4")
        vunc.units = "1"
        vunc.long_name = "1-sigma uncertainty of aod_weighted_mean"

        vcnt = ds.createVariable("aod_count", "i4", ("lat", "lon"), fill_value=FILL_I)
        vcnt[:] = np.where(valid, np.int32(10), FILL_I).astype("i4")
        vcnt.units = "1"
        vcnt.long_name = "number of valid L2 pixels contributing to the cell-window"

        for name, long_name in (
            ("aod_weighted_mean_modis", "MODIS column AOD at 550 nm"),
            ("aod_weighted_mean_viirs", "VIIRS column AOD at 550 nm"),
        ):
            var = ds.createVariable(name, "f4", ("lat", "lon"), fill_value=FILL_F)
            var[:] = aod
            var.units = "1"
            var.long_name = long_name

        ds.Conventions = "CF-1.10"
        ds.title = "SP2 synthetic contract obs (test only)"
        ds.institution = "NCAR"
        ds.source = "synthetic"
        ds.history = "created by make_synthetic_obs.py"
        ds.references = "CERES-SARB-CAM7 SPEC.md section 5"
        ds.qc_thresholds = "synthetic: none"
        ds.merge_method = "synthetic constant box"
        ds.merge_version = "test-0"
        ds.bias_correction_method = "none (synthetic)"
        ds.bias_correction_version = "test-0"
        ds.grid = "f09 FV 0.9x1.25 (192x288)"
        ds.aod_wavelength_nm = 550
        ds.date_created = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        ds.git_commit = "synthetic-test"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--ndays", type=int, default=1)
    parser.add_argument("--times-per-day", type=int, default=8)
    parser.add_argument("--value", type=float, default=0.30)
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    lat, lon, lat_b, lon_b = f09_grid()
    window_sec = 86400 // args.times_per_day
    day0 = dt.datetime(int(args.date[:4]), int(args.date[4:6]), int(args.date[6:8]))

    for day in range(args.ndays):
        for window in range(args.times_per_day):
            start_sec = window * window_sec
            start = day0 + dt.timedelta(days=day, seconds=start_sec)
            end = start + dt.timedelta(seconds=window_sec)
            center = start + dt.timedelta(seconds=window_sec // 2)
            filename = "MODIS_VIIRS_AOD_3hr_f09.%04d%02d%02d.%05d.nc" % (
                start.year,
                start.month,
                start.day,
                start_sec,
            )
            write_file(
                os.path.join(args.outdir, filename),
                lat,
                lon,
                lat_b,
                lon_b,
                args.value,
                hours_since_2000(start),
                hours_since_2000(center),
                hours_since_2000(end),
            )
            print("wrote", filename)


if __name__ == "__main__":
    main()
