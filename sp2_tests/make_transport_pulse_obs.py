#!/usr/bin/env python3
"""Generate SP2 transport-proof obs: an initial AOD pulse, then fill-only windows."""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

try:
    from sp2_tests.make_synthetic_obs import FILL_F, FILL_I, f09_grid, hours_since_2000
except ModuleNotFoundError:
    from make_synthetic_obs import FILL_F, FILL_I, f09_grid, hours_since_2000


def parse_date(value: str) -> dt.datetime:
    if len(value) != 8 or not value.isdigit():
        raise argparse.ArgumentTypeError("date must be YYYYMMDD")
    return dt.datetime(int(value[:4]), int(value[4:6]), int(value[6:8]))


def lon_mask(lon: np.ndarray, lon_min: float, lon_max: float) -> np.ndarray:
    if lon_min <= lon_max:
        return (lon >= lon_min) & (lon <= lon_max)
    return (lon >= lon_min) | (lon <= lon_max)


def pulse_mask(
    lat: np.ndarray,
    lon: np.ndarray,
    *,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> np.ndarray:
    lat_valid = (lat >= lat_min) & (lat <= lat_max)
    lon_valid = lon_mask(lon, lon_min, lon_max)
    return lat_valid[:, None] & lon_valid[None, :]


def write_transport_file(
    path: Path,
    lat: np.ndarray,
    lon: np.ndarray,
    lat_b: np.ndarray,
    lon_b: np.ndarray,
    *,
    mask: np.ndarray,
    pulse_value: float,
    active: bool,
    start_hours: float,
    center_hours: float,
    end_hours: float,
) -> int:
    aod = np.full((lat.size, lon.size), FILL_F, dtype="f4")
    if active:
        aod[mask] = np.float32(pulse_value)
    valid = aod > -900.0
    valid_count = int(np.count_nonzero(valid))

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
        ds.title = "SP2 transport pulse contract obs (test only)"
        ds.institution = "NCAR"
        ds.source = "synthetic transport proof"
        ds.history = "created by make_transport_pulse_obs.py"
        ds.references = "CERES-SARB-CAM7 SPEC.md section 5"
        ds.qc_thresholds = "synthetic: none"
        ds.merge_method = "synthetic pulse box"
        ds.merge_version = "transport-proof-0"
        ds.bias_correction_method = "none (synthetic)"
        ds.bias_correction_version = "transport-proof-0"
        ds.grid = "f09 FV 0.9x1.25 (192x288)"
        ds.aod_wavelength_nm = 550
        ds.date_created = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        ds.git_commit = "synthetic-transport-proof"
    return valid_count


def generate(args: argparse.Namespace) -> list[Path]:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    lat, lon, lat_b, lon_b = f09_grid()
    mask = pulse_mask(
        lat,
        lon,
        lat_min=args.pulse_lat_min,
        lat_max=args.pulse_lat_max,
        lon_min=args.pulse_lon_min,
        lon_max=args.pulse_lon_max,
    )

    if 86400 % args.times_per_day != 0:
        raise SystemExit("times-per-day must divide 86400 exactly")
    window_sec = 86400 // args.times_per_day
    day0 = parse_date(args.date)
    written: list[Path] = []

    for day in range(args.ndays):
        for window in range(args.times_per_day):
            global_window = day * args.times_per_day + window
            active = global_window < args.pulse_windows
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
            path = outdir / filename
            valid_count = write_transport_file(
                path,
                lat,
                lon,
                lat_b,
                lon_b,
                mask=mask,
                pulse_value=args.pulse_value,
                active=active,
                start_hours=hours_since_2000(start),
                center_hours=hours_since_2000(center),
                end_hours=hours_since_2000(end),
            )
            print(f"wrote {filename} valid_cells={valid_count}")
            written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--ndays", type=int, required=True)
    parser.add_argument("--times-per-day", type=int, required=True)
    parser.add_argument("--pulse-windows", type=int, required=True)
    parser.add_argument("--pulse-value", type=float, required=True)
    parser.add_argument("--pulse-lat-min", type=float, required=True)
    parser.add_argument("--pulse-lat-max", type=float, required=True)
    parser.add_argument("--pulse-lon-min", type=float, required=True)
    parser.add_argument("--pulse-lon-max", type=float, required=True)
    args = parser.parse_args()
    generate(args)


if __name__ == "__main__":
    main()
