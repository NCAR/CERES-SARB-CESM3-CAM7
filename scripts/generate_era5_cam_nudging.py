#!/usr/bin/env python3
"""Generate hourly CAM f09/L32 meteorological-nudging files from GDEX ERA5.

This is a focused Python translation of the ERA5 path in
``scripts/era5_cam_nudging_seed``.  It intentionally does not reproduce the
many unrelated analysis formats supported by the generic NCL ``makeIC``
program.  The translated numerical choices are:

* bilinear horizontal interpolation from ERA5 N320/L137 to CAM f09;
* wave-one polar treatment for horizontal winds;
* ECMWF-style surface-pressure adjustment for topography differences;
* quadratic log-pressure interpolation for temperature;
* linear pressure interpolation for specific humidity;
* linear log-pressure interpolation for winds; and
* saturation clipping of humidity before and after vertical interpolation.

The canonical 2008 forcing has zero-valued ERA5 source geopotential at both
pole rows during the surface-pressure adjustment.  That legacy behavior is
retained explicitly so newly filled hours do not introduce a pole-row jump at
the boundaries of the existing time series.  The output CAM PHIS field still
comes unchanged from the f09 target template.  Its ESMF center-to-staggered
conversion also has deterministic degenerate-pole behavior in VS; this is
replicated only at the two pole rows for continuity with the existing files.

Generated NetCDF data must remain below the project Data tree.  Existing
outputs are never overwritten.  Use ``--resume`` only to skip files that pass
the complete structural and numeric validator.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Iterable, Mapping

import netCDF4
import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "era5" / "march_2008_gap_v1.yaml"
PROJECT_DATA_ROOT = Path("/glade/work/fillmore/Data/CERES-SARB-CAM7")
ALLOWED_READ_ROOTS = tuple(
    Path(value)
    for value in (
        "/glade/work/fillmore",
        "/glade/u/home/fillmore",
        "/glade/derecho/scratch/fillmore",
        "/gdex/data",
        "/glade/campaign/collections/gdex/data",
        "/glade/campaign/cesm/cesmdata",
        "/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl",
    )
)

OUTPUT_TEMPLATE = "ERA5_fv09.cam2.i.{date}-{seconds:05d}.nc"
SOURCE_SPECS = {
    "T": "0_5_0_0_0_t.regn320sc",
    "U": "0_5_0_2_2_u.regn320uv",
    "V": "0_5_0_2_3_v.regn320uv",
    "PS": "128_134_sp.regn320sc",
    "Q": "0_5_0_1_0_q.regn320sc",
}
SOURCE_VARIABLES = {"T": "T", "U": "U", "V": "V", "PS": "SP", "Q": "Q"}
STATIC_VARIABLES = (
    "P0",
    "lev",
    "ilev",
    "hyai",
    "hybi",
    "hyam",
    "hybm",
    "lat",
    "lon",
    "slat",
    "slon",
    "w_stag",
    "ntrm",
    "ntrn",
    "ntrk",
    "gw",
    "PHIS",
)
DYNAMIC_VARIABLES = ("U", "V", "T", "PS", "Q", "US", "VS")
FIELD_LIMITS = {
    "U": (-240.0, 240.0),
    "V": (-220.0, 220.0),
    "T": (140.0, 360.0),
    "PS": (30_000.0, 110_000.0),
    "Q": (0.0, 0.1),
    "US": (-240.0, 240.0),
    "VS": (-220.0, 220.0),
    "PHIS": (-2_000.0, 100_000.0),
}
SUPPORTED_PROCESSING = {
    "horizontal_interpolation": "bilinear",
    "scalar_poles": "zonal_mean",
    "vector_poles": "zonal_wave_one",
    "surface_pressure_adjustment": "ecmwf_makeic",
    "temperature_vertical_interpolation": "quadratic_log_pressure_opt1",
    "humidity_vertical_interpolation": "linear_pressure_opt1",
    "wind_vertical_interpolation": "linear_log_pressure_opt2",
    "humidity_adjustment": (
        "clip_relative_humidity_0_1_before_and_after_vertical_interpolation"
    ),
    "era5_geopotential_poles": "legacy_zero",
    "staggered_v_poles": "legacy_esmf_degenerate",
}
SUPPORTED_OUTPUT = {
    "format": "NETCDF3_CLASSIC",
    "filename_template": "ERA5_fv09.cam2.i.{date}-{seconds:05d}.nc",
}
GRAVITY = 9.80616
BOLTZMANN = 1.38065e-23
AVOGADRO = 6.02214e26
MOLECULAR_WEIGHT_DRY_AIR = 28.966
R_DRY_AIR = AVOGADRO * BOLTZMANN / MOLECULAR_WEIGHT_DRY_AIR


@dataclass(frozen=True)
class ConversionConfig:
    path: Path
    source_root: Path
    invariant_geopotential: Path
    template_file: Path
    output_directory: Path
    start: datetime
    end: datetime
    reference_date: datetime
    level_chunk_size: int
    expected_dimensions: Mapping[str, int]


@dataclass(frozen=True)
class TargetGrid:
    lat: np.ndarray
    lon: np.ndarray
    slat: np.ndarray
    slon: np.ndarray
    hyam: np.ndarray
    hybm: np.ndarray
    hyai: np.ndarray
    hybi: np.ndarray
    p0: float
    phis: np.ndarray


@dataclass(frozen=True)
class BilinearPlan:
    source_lat: np.ndarray
    source_lon: np.ndarray
    target_lat: np.ndarray
    target_lon: np.ndarray
    reverse_lat: bool
    lat_lo: np.ndarray
    lat_hi: np.ndarray
    lat_weight: np.ndarray
    lon_lo: np.ndarray
    lon_hi: np.ndarray
    lon_weight: np.ndarray
    below_source: np.ndarray
    above_source: np.ndarray

    @classmethod
    def create(
        cls,
        source_lat: np.ndarray,
        source_lon: np.ndarray,
        target_lat: np.ndarray,
        target_lon: np.ndarray,
    ) -> "BilinearPlan":
        src_lat = np.asarray(source_lat, dtype=np.float64)
        src_lon = np.asarray(source_lon, dtype=np.float64)
        dst_lat = np.asarray(target_lat, dtype=np.float64)
        dst_lon = np.asarray(target_lon, dtype=np.float64)
        if src_lat.ndim != 1 or src_lon.ndim != 1:
            raise ValueError("Source latitude and longitude must be one-dimensional")
        reverse_lat = bool(src_lat[0] > src_lat[-1])
        if reverse_lat:
            src_lat = src_lat[::-1].copy()
        if not np.all(np.diff(src_lat) > 0):
            raise ValueError("Source latitudes are not strictly monotonic")
        if not np.all(np.diff(src_lon) > 0):
            raise ValueError("Source longitudes are not strictly increasing")
        if src_lon[0] < 0 or src_lon[-1] >= 360:
            raise ValueError("Source longitudes must use the [0, 360) convention")

        below = dst_lat < src_lat[0]
        above = dst_lat > src_lat[-1]
        clipped_lat = np.clip(dst_lat, src_lat[0], src_lat[-1])
        lat_hi = np.searchsorted(src_lat, clipped_lat, side="right")
        lat_hi = np.clip(lat_hi, 1, src_lat.size - 1)
        lat_lo = lat_hi - 1
        lat_denominator = src_lat[lat_hi] - src_lat[lat_lo]
        lat_weight = (clipped_lat - src_lat[lat_lo]) / lat_denominator

        normalized_lon = np.mod(dst_lon, 360.0)
        extended_lon = np.concatenate((src_lon, [src_lon[0] + 360.0]))
        lon_hi = np.searchsorted(extended_lon, normalized_lon, side="right")
        lon_hi = np.clip(lon_hi, 1, src_lon.size)
        lon_lo = lon_hi - 1
        lon_denominator = extended_lon[lon_hi] - extended_lon[lon_lo]
        lon_weight = (normalized_lon - extended_lon[lon_lo]) / lon_denominator
        lon_hi = np.mod(lon_hi, src_lon.size)

        return cls(
            source_lat=src_lat,
            source_lon=src_lon,
            target_lat=dst_lat,
            target_lon=dst_lon,
            reverse_lat=reverse_lat,
            lat_lo=lat_lo,
            lat_hi=lat_hi,
            lat_weight=lat_weight,
            lon_lo=lon_lo,
            lon_hi=lon_hi,
            lon_weight=lon_weight,
            below_source=below,
            above_source=above,
        )

    def apply(self, values: np.ndarray, *, vector_poles: bool = False) -> np.ndarray:
        """Apply separable bilinear weights to arrays ending in (lat, lon)."""
        data = np.asarray(values)
        if data.shape[-2:] != (self.source_lat.size, self.source_lon.size):
            expected = (self.source_lat.size, self.source_lon.size)
            raise ValueError(f"Source field shape {data.shape[-2:]} != {expected}")
        if self.reverse_lat:
            data = data[..., ::-1, :]

        lat_weight = self.lat_weight.reshape((1,) * (data.ndim - 2) + (-1, 1))
        along_lat = (
            data[..., self.lat_lo, :] * (1.0 - lat_weight)
            + data[..., self.lat_hi, :] * lat_weight
        )
        lon_weight = self.lon_weight.reshape((1,) * (data.ndim - 2) + (1, -1))
        result = (
            along_lat[..., :, self.lon_lo] * (1.0 - lon_weight)
            + along_lat[..., :, self.lon_hi] * lon_weight
        )
        result = np.asarray(result, dtype=np.float64)

        outside = self.below_source | self.above_source
        if np.any(outside):
            if vector_poles:
                _replace_vector_poles(result, self.target_lat, self.target_lon, outside)
            else:
                source_rows = np.where(self.below_source, 0, self.source_lat.size - 1)
                for target_index in np.flatnonzero(outside):
                    mean = np.mean(data[..., source_rows[target_index], :], axis=-1)
                    result[..., target_index, :] = mean[..., None]
        return result


def _replace_vector_poles(
    values: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    mask: np.ndarray | None = None,
) -> None:
    """Replace polar rows with the NCL seed's zonal wave-one fit."""
    if mask is None:
        mask = np.isclose(np.abs(lat), 90.0, rtol=0.0, atol=1e-7)
    radians = np.deg2rad(lon)
    cosine = np.cos(radians)
    sine = np.sin(radians)
    cosine_scale = np.mean(cosine * cosine)
    sine_scale = np.mean(sine * sine)
    for index in np.flatnonzero(mask):
        adjacent = 1 if index == 0 else len(lat) - 2
        row = values[..., adjacent, :]
        anomaly = row - np.mean(row, axis=-1, keepdims=True)
        cosine_amplitude = np.mean(anomaly * cosine, axis=-1) / cosine_scale
        sine_amplitude = np.mean(anomaly * sine, axis=-1) / sine_scale
        values[..., index, :] = (
            cosine_amplitude[..., None] * cosine
            + sine_amplitude[..., None] * sine
        )


def parse_hour(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is not None:
        result = result.astimezone(timezone.utc).replace(tzinfo=None)
    if result.minute or result.second or result.microsecond:
        raise ValueError(f"Timestamp is not on an exact hour: {value}")
    if result.month == 2 and result.day == 29:
        raise ValueError("CAM NO_LEAP forcing cannot include February 29")
    return result


def hourly_range(start: datetime, end: datetime) -> tuple[datetime, ...]:
    if end < start:
        raise ValueError("end precedes start")
    hours = int((end - start).total_seconds() // 3600)
    if start + timedelta(hours=hours) != end:
        raise ValueError("start/end do not span a whole number of hours")
    return tuple(start + timedelta(hours=value) for value in range(hours + 1))


def _noleap_ordinal(value: datetime) -> int:
    if value.month == 2 and value.day == 29:
        raise ValueError("February 29 is invalid in the NO_LEAP calendar")
    month_days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return value.year * 365 + sum(month_days[: value.month - 1]) + value.day - 1


def noleap_day_offset(value: datetime, reference: datetime) -> float:
    day_offset = _noleap_ordinal(value) - _noleap_ordinal(reference)
    return day_offset + value.hour / 24.0


def load_config(path: Path) -> ConversionConfig:
    path = Path(path).resolve()
    with path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if raw.get("schema_version") != 1:
        raise ValueError("ERA5 conversion config schema_version must be 1")
    for key, expected_value in SUPPORTED_PROCESSING.items():
        observed_value = raw.get("processing", {}).get(key)
        if observed_value != expected_value:
            raise ValueError(
                f"Unsupported processing.{key}={observed_value!r}; "
                f"this translation requires {expected_value!r}"
            )
    for key, expected_value in SUPPORTED_OUTPUT.items():
        observed_value = raw.get("output", {}).get(key)
        if observed_value != expected_value:
            raise ValueError(
                f"Unsupported output.{key}={observed_value!r}; "
                f"this translation requires {expected_value!r}"
            )
    start = parse_hour(str(raw["period"]["start"]))
    end = parse_hour(str(raw["period"]["end"]))
    reference = parse_hour(str(raw["period"].get("reference_date", raw["period"]["start"])))
    if reference.hour:
        raise ValueError("reference_date must be at 00 UTC")
    chunk = int(raw.get("processing", {}).get("level_chunk_size", 16))
    if chunk < 1:
        raise ValueError("level_chunk_size must be positive")
    dimensions = raw.get("target", {}).get(
        "expected_dimensions", {"lat": 192, "lon": 288, "lev": 32, "ilev": 33}
    )
    expected = {str(key): int(value) for key, value in dimensions.items()}
    return ConversionConfig(
        path=path,
        source_root=Path(raw["sources"]["gdex_root"]),
        invariant_geopotential=Path(raw["sources"]["invariant_geopotential"]),
        template_file=Path(raw["target"]["template_file"]),
        output_directory=Path(raw["output"]["directory"]),
        start=start,
        end=end,
        reference_date=reference,
        level_chunk_size=chunk,
        expected_dimensions=expected,
    )


def _is_relative_to_any(path: Path, roots: Iterable[Path]) -> bool:
    return any(path.is_relative_to(root) for root in roots)


def checked_read_path(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    if not _is_relative_to_any(absolute, ALLOWED_READ_ROOTS):
        raise ValueError(f"Read path is outside authorized roots: {absolute}")
    resolved = absolute.resolve(strict=True)
    if not _is_relative_to_any(resolved, ALLOWED_READ_ROOTS):
        raise ValueError(f"Read path resolves outside authorized roots: {absolute} -> {resolved}")
    return absolute


def checked_output_directory(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    if not absolute.is_relative_to(PROJECT_DATA_ROOT):
        raise ValueError(f"Output must be below {PROJECT_DATA_ROOT}: {absolute}")
    existing_parent = absolute
    while not existing_parent.exists():
        if existing_parent.parent == existing_parent:
            raise ValueError(f"No existing parent for output path: {absolute}")
        existing_parent = existing_parent.parent
    resolved_parent = existing_parent.resolve(strict=True)
    if not resolved_parent.is_relative_to(PROJECT_DATA_ROOT):
        raise ValueError(
            f"Output parent resolves outside {PROJECT_DATA_ROOT}: "
            f"{existing_parent} -> {resolved_parent}"
        )
    return absolute


def source_bundle_path(source_root: Path, variable: str, timestamp: datetime) -> Path:
    if variable not in SOURCE_SPECS:
        raise ValueError(f"Unsupported ERA5 source variable: {variable}")
    start_hour = timestamp.hour - timestamp.hour % 6
    end_hour = start_hour + 5
    date = timestamp.strftime("%Y%m%d")
    ym = timestamp.strftime("%Y%m")
    spec = SOURCE_SPECS[variable]
    name = (
        f"e5.oper.an.ml.{spec}.{date}{start_hour:02d}_{date}{end_hour:02d}.nc"
    )
    return source_root / "e5.oper.an.ml" / ym / name


def output_path(output_directory: Path, timestamp: datetime) -> Path:
    return output_directory / OUTPUT_TEMPLATE.format(
        date=timestamp.strftime("%Y-%m-%d"), seconds=timestamp.hour * 3600
    )


def _read_target_grid(template_file: Path) -> TargetGrid:
    with netCDF4.Dataset(template_file) as dataset:
        required = set(STATIC_VARIABLES) | set(DYNAMIC_VARIABLES)
        missing = required - set(dataset.variables)
        if missing:
            raise ValueError(f"Template lacks variables: {sorted(missing)}")
        return TargetGrid(
            lat=np.asarray(dataset["lat"][:], dtype=np.float64),
            lon=np.asarray(dataset["lon"][:], dtype=np.float64),
            slat=np.asarray(dataset["slat"][:], dtype=np.float64),
            slon=np.asarray(dataset["slon"][:], dtype=np.float64),
            hyam=np.asarray(dataset["hyam"][:], dtype=np.float64),
            hybm=np.asarray(dataset["hybm"][:], dtype=np.float64),
            hyai=np.asarray(dataset["hyai"][:], dtype=np.float64),
            hybi=np.asarray(dataset["hybi"][:], dtype=np.float64),
            p0=float(np.asarray(dataset["P0"][:]).item()),
            phis=np.asarray(dataset["PHIS"][0], dtype=np.float64),
        )


def _source_time_index(dataset: netCDF4.Dataset, timestamp: datetime) -> int:
    expected = int(timestamp.strftime("%Y%m%d%H"))
    dates = np.asarray(dataset["utc_date"][:], dtype=np.int64)
    matches = np.flatnonzero(dates == expected)
    if matches.size != 1:
        raise ValueError(
            f"Expected one utc_date={expected}, found {matches.size} in {dataset.filepath()}"
        )
    return int(matches[0])


def _source_coordinates(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with netCDF4.Dataset(path) as dataset:
        return (
            np.asarray(dataset["latitude"][:], dtype=np.float64),
            np.asarray(dataset["longitude"][:], dtype=np.float64),
        )


def _read_regridded_2d(
    path: Path,
    source_name: str,
    timestamp: datetime | None,
    plan: BilinearPlan,
) -> np.ndarray:
    with netCDF4.Dataset(path) as dataset:
        variable = dataset[source_name]
        if timestamp is None:
            values = np.asarray(variable[0], dtype=np.float64)
        else:
            values = np.asarray(variable[_source_time_index(dataset, timestamp)], dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError(f"Non-finite values in {path}:{source_name}")
    return plan.apply(values)


def _read_regridded_3d(
    path: Path,
    source_name: str,
    timestamp: datetime,
    plan: BilinearPlan,
    *,
    level_chunk_size: int,
    vector_poles: bool = False,
) -> np.ndarray:
    with netCDF4.Dataset(path) as dataset:
        variable = dataset[source_name]
        time_index = _source_time_index(dataset, timestamp)
        level_count = variable.shape[1]
        result = np.empty(
            (level_count, plan.target_lat.size, plan.target_lon.size), dtype=np.float64
        )
        for begin in range(0, level_count, level_chunk_size):
            end = min(begin + level_chunk_size, level_count)
            values = np.asarray(variable[time_index, begin:end], dtype=np.float64)
            if not np.all(np.isfinite(values)):
                raise ValueError(f"Non-finite values in {path}:{source_name}[{begin}:{end}]")
            result[begin:end] = plan.apply(values, vector_poles=vector_poles)
    return result


def build_pressure(a: np.ndarray, b: np.ndarray, surface_pressure: np.ndarray) -> np.ndarray:
    return (
        np.asarray(a, dtype=np.float64)[:, None, None]
        + np.asarray(b, dtype=np.float64)[:, None, None]
        * np.asarray(surface_pressure, dtype=np.float64)[None, :, :]
    )


def _surface_state(
    temperature: np.ndarray,
    pressure_mid: np.ndarray,
    pressure_interface: np.ndarray,
    surface_pressure: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return NCL makeIC k_bot, T_bot, and extrapolated surface T."""
    nlev, nlat, nlon = temperature.shape
    columns = nlat * nlon
    t = temperature.reshape(nlev, columns)
    pm = pressure_mid.reshape(nlev, columns)
    pi = pressure_interface.reshape(nlev + 1, columns)
    ps = surface_pressure.reshape(columns)
    cumulative_height = np.zeros(columns, dtype=np.float64)
    k_bottom = np.full(columns, -1, dtype=np.int32)
    active = np.ones(columns, dtype=bool)
    for level in range(nlev - 1, -1, -1):
        half_layer = 0.5 * (pi[level + 1] - pi[level]) / pm[level]
        increment = (R_DRY_AIR / GRAVITY) * t[level] * half_layer
        cumulative_height[active] += increment[active]
        found = active & (cumulative_height > 150.0)
        k_bottom[found] = level
        active[found] = False
        cumulative_height[active] += increment[active]
    if np.any(active):
        raise ValueError("Could not find an ERA5 level at least 150 m above the surface")
    column = np.arange(columns)
    t_bottom = t[k_bottom, column]
    p_bottom = pm[k_bottom, column]
    lapse = 0.0065
    surface_temperature = t_bottom * (
        1.0 + lapse * (R_DRY_AIR / GRAVITY) * (ps / p_bottom - 1.0)
    )
    return (
        k_bottom.reshape(nlat, nlon),
        t_bottom.reshape(nlat, nlon),
        surface_temperature.reshape(nlat, nlon),
    )


def adjust_surface_pressure(
    temperature: np.ndarray,
    pressure_mid: np.ndarray,
    pressure_interface: np.ndarray,
    source_phis: np.ndarray,
    target_phis: np.ndarray,
    surface_pressure: np.ndarray,
) -> np.ndarray:
    """Port MAKEIC.f90::psadj."""
    k_bottom, t_bottom, surface_temperature = _surface_state(
        temperature, pressure_mid, pressure_interface, surface_pressure
    )
    p_bottom = np.take_along_axis(
        pressure_mid, k_bottom[None, :, :], axis=0
    )[0]
    del_phis = source_phis - target_phis
    result = np.asarray(surface_pressure, dtype=np.float64).copy()
    changed = np.abs(del_phis) > 0.001
    if not np.any(changed):
        return result

    lapse = np.full(result.shape, 0.0065, dtype=np.float64)
    tsurf = surface_temperature.copy()
    t0 = tsurf + lapse * source_phis / GRAVITY
    warm_lapse = changed & (t0 > 290.5) & (tsurf <= 290.5)
    lapse[warm_lapse] = (
        (290.5 - tsurf[warm_lapse]) * GRAVITY / source_phis[warm_lapse]
    )
    warm_flat = changed & (t0 > 290.5) & (tsurf > 290.5)
    lapse[warm_flat] = 0.0
    tsurf[warm_flat] = 0.5 * (290.5 + tsurf[warm_flat])
    cold = changed & (tsurf < 255.0)
    lapse[cold] = 0.0065
    tsurf[cold] = 0.5 * (255.0 + tsurf[cold])

    x = lapse * del_phis / (GRAVITY * tsurf)
    correction = del_phis / (R_DRY_AIR * tsurf) * (1.0 - x / 2.0 + x * x / 3.0)
    result[changed] = surface_pressure[changed] * np.exp(correction[changed])
    if not np.all(np.isfinite(result)):
        raise ValueError("Surface-pressure adjustment produced non-finite values")
    # Keep variables referenced so an accidental algorithm simplification is obvious.
    del t_bottom, p_bottom
    return result


def _goff_gratch(temperature: float, ice_transition: float = 20.0) -> float:
    freezing = 273.16
    transition = abs(float(ice_transition))
    use_ice = temperature < freezing
    water_value = math.nan
    if temperature >= freezing - transition:
        ps = 1013.246
        boiling = 373.16
        e1 = 11.344 * (1.0 - temperature / boiling)
        e2 = -3.49149 * (boiling / temperature - 1.0)
        f = (
            -7.90298 * (boiling / temperature - 1.0)
            + 5.02808 * math.log10(boiling / temperature)
            - 1.3816 * (10.0**e1 - 1.0) / 10_000_000.0
            + 8.1328 * (10.0**e2 - 1.0) / 1000.0
            + math.log10(ps)
        )
        water_value = 10.0**f * 100.0
        if not use_ice:
            return water_value
    ratio = freezing / temperature
    ice_value = 575.185606e10 * math.exp(
        -(2.01889049 / ratio + 3.56654 * math.log(ratio) + 20.947031 * ratio)
    )
    if temperature < freezing - transition:
        return ice_value
    weight = min((freezing - temperature) / transition, 1.0)
    return weight * ice_value + (1.0 - weight) * water_value


def _saturation_table() -> tuple[np.ndarray, float, float]:
    minimum = 173.16
    maximum = 375.16
    count = int(maximum - minimum + 2.000001)
    table = np.array([_goff_gratch(minimum + index) for index in range(count)])
    return table, minimum, maximum


SATURATION_TABLE, SATURATION_MINIMUM, SATURATION_MAXIMUM = _saturation_table()


def saturation_specific_humidity(
    temperature: np.ndarray, pressure: np.ndarray
) -> np.ndarray:
    bounded = np.clip(temperature, SATURATION_MINIMUM, SATURATION_MAXIMUM)
    offset = bounded - SATURATION_MINIMUM
    lower = np.floor(offset).astype(np.int16)
    fraction = offset - lower
    vapor_pressure = (
        SATURATION_TABLE[lower] * (1.0 - fraction)
        + SATURATION_TABLE[lower + 1] * fraction
    )
    result = 0.622 * vapor_pressure / (pressure - (1.0 - 0.622) * vapor_pressure)
    result = np.minimum(1.0, result)
    result[result < 0.0] = 1.0
    return result


def clip_specific_humidity(
    humidity: np.ndarray, temperature: np.ndarray, pressure: np.ndarray
) -> np.ndarray:
    saturation = saturation_specific_humidity(temperature, pressure)
    relative_humidity = np.clip(humidity / saturation, 0.0, 1.0)
    return relative_humidity * saturation


def _flat_fields(
    values: np.ndarray, source_pressure: np.ndarray, target_pressure: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, int]]:
    if values.shape != source_pressure.shape:
        raise ValueError("Values and source pressure must have identical shapes")
    if values.shape[1:] != target_pressure.shape[1:]:
        raise ValueError("Source and target horizontal shapes differ")
    nlat, nlon = values.shape[1:]
    return (
        values.reshape(values.shape[0], -1),
        source_pressure.reshape(source_pressure.shape[0], -1),
        target_pressure.reshape(target_pressure.shape[0], -1),
        (nlat, nlon),
    )


def vertical_linear_opt1(
    values: np.ndarray,
    source_pressure: np.ndarray,
    target_pressure: np.ndarray,
    *,
    log_pressure: bool = False,
) -> np.ndarray:
    """Port MAKEIC.f90::vert_int_opt1 (moisture fields)."""
    field, source, target, horizontal_shape = _flat_fields(
        values, source_pressure, target_pressure
    )
    nsource, columns = field.shape
    output = np.empty((target.shape[0], columns), dtype=np.float64)
    bracket = np.zeros(columns, dtype=np.int32)
    column = np.arange(columns)
    for level in range(target.shape[0]):
        requested = target[level]
        while True:
            move = (bracket < nsource - 2) & (
                source[bracket + 1, column] <= requested
            )
            if not np.any(move):
                break
            bracket[move] += 1
        p1 = source[bracket, column]
        p2 = source[bracket + 1, column]
        x1 = field[bracket, column]
        x2 = field[bracket + 1, column]
        above = requested < p1
        below = requested >= p2
        interior = ~(above | below)
        output[level, above] = x1[above]
        output[level, below] = x2[below]
        if np.any(interior):
            left = p1[interior]
            right = p2[interior]
            point = requested[interior]
            if log_pressure:
                left, right, point = np.log(left), np.log(right), np.log(point)
            output[level, interior] = (
                x1[interior] * (right - point)
                + x2[interior] * (point - left)
            ) / (right - left)
    return output.reshape((target.shape[0],) + horizontal_shape)


def vertical_linear_opt2(
    values: np.ndarray,
    source_pressure: np.ndarray,
    target_pressure: np.ndarray,
    *,
    log_pressure: bool = True,
) -> np.ndarray:
    """Port MAKEIC.f90::vert_int_opt2 (wind fields)."""
    field, source, target, horizontal_shape = _flat_fields(
        values, source_pressure, target_pressure
    )
    nsource, columns = field.shape
    output = np.empty((target.shape[0], columns), dtype=np.float64)
    bracket = np.zeros(columns, dtype=np.int32)
    column = np.arange(columns)
    for level in range(target.shape[0]):
        requested = target[level]
        while True:
            move = (bracket < nsource - 2) & (
                source[bracket + 1, column] <= requested
            )
            if not np.any(move):
                break
            bracket[move] += 1
        p1 = source[bracket, column]
        p2 = source[bracket + 1, column]
        x1 = field[bracket, column]
        x2 = field[bracket + 1, column]
        above = requested < p1
        below = requested >= p2
        first = (~above) & (~below) & (bracket == 0)
        interior = ~(above | below | first)
        output[level, above] = x1[above]
        output[level, below] = x2[below]
        if np.any(first):
            p3 = source[2, first]
            x3 = field[2, first]
            left, middle, right, point = (
                p1[first], p2[first], p3, requested[first]
            )
            if log_pressure:
                left, middle, right, point = map(
                    np.log, (left, middle, right, point)
                )
            w1 = (point - middle) * (point - right) / (
                (left - middle) * (left - right)
            )
            w2 = (point - left) * (point - right) / (
                (middle - left) * (middle - right)
            )
            w3 = (point - left) * (point - middle) / (
                (right - left) * (right - middle)
            )
            output[level, first] = x1[first] * w1 + x2[first] * w2 + x3 * w3
        if np.any(interior):
            left, right, point = p1[interior], p2[interior], requested[interior]
            if log_pressure:
                left, right, point = np.log(left), np.log(right), np.log(point)
            output[level, interior] = (
                x1[interior] * (right - point)
                + x2[interior] * (point - left)
            ) / (right - left)
    return output.reshape((target.shape[0],) + horizontal_shape)


def vertical_temperature(
    temperature: np.ndarray,
    source_pressure: np.ndarray,
    source_interface_pressure: np.ndarray,
    target_pressure: np.ndarray,
    source_phis: np.ndarray,
    surface_pressure: np.ndarray,
) -> np.ndarray:
    """Port MAKEIC.f90::vert_quad_opt1 using log-pressure coordinates."""
    field, source, target, horizontal_shape = _flat_fields(
        temperature, source_pressure, target_pressure
    )
    nsource, columns = field.shape
    source_phis_flat = source_phis.reshape(columns)
    surface_pressure_flat = surface_pressure.reshape(columns)
    k_bottom, t_bottom_2d, surface_temperature_2d = _surface_state(
        temperature, source_pressure, source_interface_pressure, surface_pressure
    )
    k_bottom = k_bottom.reshape(columns)
    t_bottom = t_bottom_2d.reshape(columns)
    surface_temperature = surface_temperature_2d.reshape(columns)
    column = np.arange(columns)
    p_bottom = source[k_bottom, column]
    output = np.empty((target.shape[0], columns), dtype=np.float64)
    bracket = np.zeros(columns, dtype=np.int32)

    for level in range(target.shape[0]):
        requested = target[level]
        while True:
            p2 = source[bracket + 1, column]
            p3 = source[bracket + 2, column]
            beta = np.divide(
                requested - p2,
                p3 - p2,
                out=np.full(columns, -np.inf),
                where=p2 <= requested,
            )
            move = (p2 <= requested) & (beta >= 0.5) & (bracket < nsource - 3)
            if not np.any(move):
                break
            bracket[move] += 1

        p1 = source[bracket, column]
        p2 = source[bracket + 1, column]
        p3 = source[bracket + 2, column]
        x1 = field[bracket, column]
        x2 = field[bracket + 1, column]
        x3 = field[bracket + 2, column]
        log_p1, log_p2, log_p3 = np.log(p1), np.log(p2), np.log(p3)
        log_point = np.log(requested)
        log_bottom = np.log(p_bottom)
        log_surface = np.log(surface_pressure_flat)

        above = log_point < log_p1
        lower_atmosphere = (
            (log_point >= log_bottom) & (log_point <= log_surface) & ~above
        )
        below_surface = (log_point > log_surface) & ~above
        quadratic = ~(above | lower_atmosphere | below_surface)
        invalid = quadratic & (log_point >= log_p3)
        if np.any(invalid):
            raise ValueError("Temperature interpolation would extrapolate below ERA5 levels")

        output[level, above] = x1[above]
        if np.any(lower_atmosphere):
            output[level, lower_atmosphere] = (
                t_bottom[lower_atmosphere]
                * (log_surface[lower_atmosphere] - log_point[lower_atmosphere])
                + surface_temperature[lower_atmosphere]
                * (log_point[lower_atmosphere] - log_bottom[lower_atmosphere])
            ) / (log_surface[lower_atmosphere] - log_bottom[lower_atmosphere])
        if np.any(below_surface):
            surface = surface_temperature[below_surface]
            geopotential_height = source_phis_flat[below_surface] / GRAVITY
            t_ref_bottom = surface + 2000.0 * 0.0065
            t_ref_top = np.minimum(surface + 2500.0 * 0.0065, 298.0)
            t0 = np.where(
                geopotential_height >= 2500.0,
                np.minimum(surface + geopotential_height * 0.0065, 298.0),
                np.where(
                    geopotential_height >= 2000.0,
                    (
                        t_ref_bottom * (2500.0 - geopotential_height)
                        + t_ref_top * (geopotential_height - 2000.0)
                    )
                    / 500.0,
                    surface + geopotential_height * 0.0065,
                ),
            )
            lapse = np.where(
                geopotential_height >= 2000.0,
                np.maximum(
                    np.divide(
                        t0 - surface,
                        geopotential_height,
                        out=np.zeros_like(surface),
                        where=geopotential_height != 0,
                    ),
                    0.0,
                ),
                0.0065,
            )
            expansion = (
                lapse
                * R_DRY_AIR
                / GRAVITY
                * np.log(
                    requested[below_surface] / surface_pressure_flat[below_surface]
                )
            )
            output[level, below_surface] = surface * (
                1.0 + expansion + expansion**2 / 2.0 + expansion**3 / 6.0
            )
        if np.any(quadratic):
            point = log_point[quadratic]
            left = log_p1[quadratic]
            middle = log_p2[quadratic]
            right = log_p3[quadratic]
            w1 = (point - middle) * (point - right) / (
                (left - middle) * (left - right)
            )
            w2 = (point - left) * (point - right) / (
                (middle - left) * (middle - right)
            )
            w3 = (point - left) * (point - middle) / (
                (right - left) * (right - middle)
            )
            output[level, quadratic] = (
                x1[quadratic] * w1 + x2[quadratic] * w2 + x3[quadratic] * w3
            )
    return output.reshape((target.shape[0],) + horizontal_shape)


def stagger_winds(
    u: np.ndarray, v: np.ndarray, target: TargetGrid
) -> tuple[np.ndarray, np.ndarray]:
    u_plan = BilinearPlan.create(target.lat, target.lon, target.slat, target.lon)
    v_plan = BilinearPlan.create(target.lat, target.lon, target.lat, target.slon)
    us = u_plan.apply(u)
    vs = v_plan.apply(v)

    # The legacy NCL edge_reformat/ESMF path adds a duplicate north-pole row
    # before producing VS.  ESMF then maps the north pole to V(lon=0), while
    # its degenerate south-pole weights repeat the first half-longitude arc.
    # This exact rule is stable across the surrounding canonical 2008 files.
    if (
        target.lat.size != 192
        or target.lon.size != 288
        or not np.isclose(target.lat[0], -90.0)
        or not np.isclose(target.lat[-1], 90.0)
    ):
        raise ValueError("Legacy VS pole compatibility is defined only for CAM f09")
    split = target.lon.size // 2 - 1
    south = vs[..., 0, :].copy()
    vs[..., 0, :] = np.concatenate(
        (south[..., :split], south[..., : target.lon.size - split]), axis=-1
    )
    vs[..., -1, :] = v[..., -1, 0, None]
    return us, vs


def _read_source_coefficients(path: Path) -> tuple[np.ndarray, ...]:
    with netCDF4.Dataset(path) as dataset:
        return tuple(
            np.asarray(dataset[name][:], dtype=np.float64)
            for name in ("a_model", "b_model", "a_half", "b_half")
        )


def convert_timestamp(
    config: ConversionConfig,
    timestamp: datetime,
    target: TargetGrid | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, Path]]:
    """Convert one timestamp and return CAM fields plus exact source paths."""
    paths = {
        name: checked_read_path(source_bundle_path(config.source_root, name, timestamp))
        for name in SOURCE_SPECS
    }
    invariant = checked_read_path(config.invariant_geopotential)
    if target is None:
        target = _read_target_grid(checked_read_path(config.template_file))
    source_lat, source_lon = _source_coordinates(paths["T"])
    plan = BilinearPlan.create(source_lat, source_lon, target.lat, target.lon)

    surface_pressure = np.exp(
        plan.apply(
            np.log(
                _read_native_2d(paths["PS"], SOURCE_VARIABLES["PS"], timestamp)
            )
        )
    )
    source_phis = _read_regridded_2d(invariant, "Z", None, plan)
    pole_rows = np.isclose(np.abs(target.lat), 90.0, rtol=0.0, atol=1e-7)
    source_phis[pole_rows, :] = 0.0
    temperature = _read_regridded_3d(
        paths["T"], "T", timestamp, plan, level_chunk_size=config.level_chunk_size
    )
    humidity = _read_regridded_3d(
        paths["Q"], "Q", timestamp, plan, level_chunk_size=config.level_chunk_size
    )
    u_source = _read_regridded_3d(
        paths["U"],
        "U",
        timestamp,
        plan,
        level_chunk_size=config.level_chunk_size,
        vector_poles=True,
    )
    v_source = _read_regridded_3d(
        paths["V"],
        "V",
        timestamp,
        plan,
        level_chunk_size=config.level_chunk_size,
        vector_poles=True,
    )

    a_model, b_model, a_half, b_half = _read_source_coefficients(paths["T"])
    source_pressure = build_pressure(a_model, b_model, surface_pressure)
    source_interface_pressure = build_pressure(a_half, b_half, surface_pressure)
    humidity = clip_specific_humidity(humidity, temperature, source_pressure)
    adjusted_pressure = adjust_surface_pressure(
        temperature,
        source_pressure,
        source_interface_pressure,
        source_phis,
        target.phis,
        surface_pressure,
    )
    target_pressure = build_pressure(
        target.hyam * target.p0, target.hybm, adjusted_pressure
    )
    output_temperature = vertical_temperature(
        temperature,
        source_pressure,
        source_interface_pressure,
        target_pressure,
        source_phis,
        surface_pressure,
    )
    output_humidity = vertical_linear_opt1(
        humidity, source_pressure, target_pressure, log_pressure=False
    )
    output_humidity = clip_specific_humidity(
        output_humidity, output_temperature, target_pressure
    )
    output_u = vertical_linear_opt2(
        u_source, source_pressure, target_pressure, log_pressure=True
    )
    output_v = vertical_linear_opt2(
        v_source, source_pressure, target_pressure, log_pressure=True
    )
    output_us, output_vs = stagger_winds(output_u, output_v, target)

    fields = {
        "U": output_u,
        "V": output_v,
        "T": output_temperature,
        "PS": adjusted_pressure,
        "Q": output_humidity,
        "US": output_us,
        "VS": output_vs,
    }
    _validate_field_arrays(fields)
    paths["Z"] = invariant
    paths["PHIS"] = checked_read_path(config.template_file)
    return fields, paths


def _read_native_2d(path: Path, source_name: str, timestamp: datetime) -> np.ndarray:
    with netCDF4.Dataset(path) as dataset:
        values = np.asarray(
            dataset[source_name][_source_time_index(dataset, timestamp)], dtype=np.float64
        )
    if not np.all(np.isfinite(values)):
        raise ValueError(f"Non-finite values in {path}:{source_name}")
    return values


def _validate_field_arrays(fields: Mapping[str, np.ndarray]) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for name, (minimum, maximum) in FIELD_LIMITS.items():
        if name not in fields:
            continue
        values = np.asarray(fields[name])
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{name} contains non-finite values")
        observed_minimum = float(np.min(values))
        observed_maximum = float(np.max(values))
        if observed_minimum < minimum or observed_maximum > maximum:
            raise ValueError(
                f"{name} range [{observed_minimum}, {observed_maximum}] "
                f"is outside [{minimum}, {maximum}]"
            )
        metrics[name] = {"min": observed_minimum, "max": observed_maximum}
    return metrics


def _git_revision() -> tuple[str, bool]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return (
        revision.stdout.strip() if revision.returncode == 0 else "unavailable",
        bool(dirty.stdout.strip()) if dirty.returncode == 0 else True,
    )


def write_cam_file(
    path: Path,
    template_file: Path,
    fields: Mapping[str, np.ndarray],
    timestamp: datetime,
    reference_date: datetime,
    source_paths: Mapping[str, Path],
) -> None:
    """Copy the static CAM contract and atomically populate one converted hour."""
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"Temporary output already exists: {temporary}")
    shutil.copyfile(template_file, temporary)
    try:
        with netCDF4.Dataset(temporary, "r+") as dataset:
            dataset["time"][:] = [noleap_day_offset(timestamp, reference_date)]
            dataset["ndbase"][:] = [0]
            dataset["nsbase"][:] = [0]
            dataset["nbdate"][:] = [int(reference_date.strftime("%Y%m%d"))]
            dataset["nbsec"][:] = [0]
            dataset["ndcur"][:] = [
                _noleap_ordinal(timestamp) - _noleap_ordinal(reference_date)
            ]
            dataset["nscur"][:] = [timestamp.hour * 3600]
            dataset["date"][:] = [int(timestamp.strftime("%Y%m%d"))]
            dataset["datesec"][:] = [timestamp.hour * 3600]
            for name in DYNAMIC_VARIABLES:
                dataset[name][0] = np.asarray(fields[name], dtype=np.float32)

            variable_sources = {
                "U": source_paths["U"],
                "V": source_paths["V"],
                "T": source_paths["T"],
                "PS": source_paths["PS"],
                "Q": source_paths["Q"],
                "US": source_paths["U"],
                "VS": source_paths["V"],
                "PHIS": source_paths["PHIS"],
            }
            for name, source in variable_sources.items():
                dataset[name].setncattr("source_file", str(source))

            for attribute in tuple(dataset.ncattrs()):
                if attribute.startswith("source"):
                    dataset.delncattr(attribute)
            revision, dirty = _git_revision()
            dataset.Conventions = "NCAR-CSM"
            dataset.Description = (
                "CAM f09/L32 meteorological nudging fields translated from "
                "GDEX ERA5 model-level analyses"
            )
            for name, source in sorted(source_paths.items()):
                dataset.setncattr(f"source_{name}", str(source))
            dataset.target_grid_template = str(template_file)
            dataset.translation_source = str(
                REPO_ROOT / "scripts" / "era5_cam_nudging_seed"
            )
            dataset.horizontal_interpolation = (
                "bilinear on rectilinear coordinates; zonal-mean scalar poles; "
                "wave-one vector poles"
            )
            dataset.vertical_interpolation = (
                "T=quadratic_log_pressure_opt1; Q=linear_pressure_opt1; "
                "U,V=linear_log_pressure_opt2"
            )
            dataset.hybrid_sigma_pressure = "p(i,j,k) = A(k)*P0 + B(k)*PS(i,j)"
            dataset.ps_adjust = "True; adjusted for ERA5-to-CAM topography differences"
            dataset.q_adjust = "True; relative humidity clipped to [0,1]"
            dataset.interp_log_ps = "True; interpolate ln(PS) rather than PS"
            dataset.RDA_DATASET = "ds633.6"
            dataset.RDA_DATASET_DOI = "10.5065/XV5R-5344"
            dataset.producer = "scripts/generate_era5_cam_nudging.py"
            dataset.producer_git_commit = revision
            dataset.producer_git_dirty = str(dirty).lower()
            dataset.logname = getpass.getuser()
            dataset.host = socket.gethostname()
            dataset.Command = "Python ERA5-to-CAM converter"
            dataset.Date_Written = datetime.now(timezone.utc).isoformat()
            dataset.case = "ERA5_fv09"
            dataset.sync()
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def validate_cam_file(
    path: Path,
    template_file: Path,
    *,
    expected_timestamp: datetime | None = None,
    expected_dimensions: Mapping[str, int] | None = None,
) -> dict:
    expected_dimensions = expected_dimensions or {
        "lat": 192,
        "lon": 288,
        "lev": 32,
        "ilev": 33,
    }
    with netCDF4.Dataset(template_file) as template, netCDF4.Dataset(path) as dataset:
        dimensions = {
            name: len(dataset.dimensions[name])
            for name in expected_dimensions
            if name in dataset.dimensions
        }
        if dimensions != dict(expected_dimensions):
            raise ValueError(f"Dimension mismatch in {path}: {dimensions}")
        required = set(STATIC_VARIABLES) | set(DYNAMIC_VARIABLES)
        missing = required - set(dataset.variables)
        if missing:
            raise ValueError(f"Missing CAM variables in {path}: {sorted(missing)}")
        for name in STATIC_VARIABLES:
            if dataset[name].shape != template[name].shape:
                raise ValueError(f"{name} shape differs from the target template in {path}")
            if not np.allclose(
                dataset[name][:], template[name][:], rtol=0.0, atol=1e-12
            ):
                raise ValueError(f"{name} differs from the target template in {path}")
        for name in DYNAMIC_VARIABLES:
            if dataset[name].shape != template[name].shape:
                raise ValueError(f"{name} shape differs from the target template in {path}")
        fields = {name: np.asarray(dataset[name][0]) for name in DYNAMIC_VARIABLES}
        fields["PHIS"] = np.asarray(dataset["PHIS"][0])
        metrics = _validate_field_arrays(fields)
        if expected_timestamp is not None:
            observed_date = int(np.asarray(dataset["date"][:]).item())
            observed_seconds = int(np.asarray(dataset["datesec"][:]).item())
            if observed_date != int(expected_timestamp.strftime("%Y%m%d")):
                raise ValueError(f"Incorrect date in {path}: {observed_date}")
            if observed_seconds != expected_timestamp.hour * 3600:
                raise ValueError(f"Incorrect datesec in {path}: {observed_seconds}")
        for attribute in (
            "producer",
            "producer_git_commit",
            "horizontal_interpolation",
            "vertical_interpolation",
            "source_T",
            "source_Q",
            "source_U",
            "source_V",
            "source_PS",
            "source_Z",
            "source_PHIS",
        ):
            if attribute not in dataset.ncattrs():
                raise ValueError(f"Missing provenance attribute {attribute} in {path}")
        return {
            "path": str(path),
            "format": dataset.data_model,
            "dimensions": dimensions,
            "date": int(np.asarray(dataset["date"][:]).item()),
            "datesec": int(np.asarray(dataset["datesec"][:]).item()),
            "fields": metrics,
        }


def compare_cam_files(candidate: Path, reference: Path) -> dict:
    result = {"candidate": str(candidate), "reference": str(reference), "fields": {}}
    with netCDF4.Dataset(candidate) as left, netCDF4.Dataset(reference) as right:
        for name in DYNAMIC_VARIABLES:
            if left[name].shape != right[name].shape:
                raise ValueError(f"{name} shape differs: {left[name].shape} != {right[name].shape}")
            sum_squared = 0.0
            sum_difference = 0.0
            maximum = 0.0
            count = 0
            for time_index in range(left[name].shape[0]):
                difference = (
                    np.asarray(left[name][time_index], dtype=np.float64)
                    - np.asarray(right[name][time_index], dtype=np.float64)
                )
                if not np.all(np.isfinite(difference)):
                    raise ValueError(f"Non-finite difference for {name}")
                maximum = max(maximum, float(np.max(np.abs(difference))))
                sum_squared += float(np.sum(difference * difference))
                sum_difference += float(np.sum(difference))
                count += difference.size
            result["fields"][name] = {
                "max_abs": maximum,
                "rmse": math.sqrt(sum_squared / count),
                "mean_bias": sum_difference / count,
            }
            dimensions = left[name].dimensions[1:]
            if "lat" in dimensions and left[name].shape[dimensions.index("lat") + 1] > 2:
                latitude_axis = dimensions.index("lat")
                candidate_values = np.asarray(left[name][0], dtype=np.float64)
                reference_values = np.asarray(right[name][0], dtype=np.float64)
                core_slice = [slice(None)] * candidate_values.ndim
                core_slice[latitude_axis] = slice(1, -1)
                nonpolar_difference = (
                    candidate_values[tuple(core_slice)]
                    - reference_values[tuple(core_slice)]
                )
                result["fields"][name]["nonpolar_max_abs"] = float(
                    np.max(np.abs(nonpolar_difference))
                )
                result["fields"][name]["nonpolar_rmse"] = float(
                    np.sqrt(np.mean(nonpolar_difference * nonpolar_difference))
                )
    return result


def _preflight_template(config: ConversionConfig) -> TargetGrid:
    template = checked_read_path(config.template_file)
    with netCDF4.Dataset(template) as dataset:
        dimensions = {
            name: len(dataset.dimensions[name]) for name in config.expected_dimensions
        }
        if dimensions != dict(config.expected_dimensions):
            raise ValueError(f"Template dimensions {dimensions} != {config.expected_dimensions}")
        if dataset.data_model != "NETCDF3_CLASSIC":
            raise ValueError(f"Template must be NETCDF3_CLASSIC, got {dataset.data_model}")
    return _read_target_grid(template)


def preflight(config: ConversionConfig, *, for_run: bool = False, resume: bool = False) -> dict:
    output_directory = checked_output_directory(config.output_directory)
    target = _preflight_template(config)
    timestamps = hourly_range(config.start, config.end)
    required_paths: dict[Path, set[int]] = {}
    for timestamp in timestamps:
        expected = int(timestamp.strftime("%Y%m%d%H"))
        for source_name in SOURCE_SPECS:
            path = checked_read_path(
                source_bundle_path(config.source_root, source_name, timestamp)
            )
            required_paths.setdefault(path, set()).add(expected)
    invariant = checked_read_path(config.invariant_geopotential)
    with netCDF4.Dataset(invariant) as dataset:
        if "Z" not in dataset.variables:
            raise ValueError(f"Invariant file lacks Z: {invariant}")
    for path, expected_dates in required_paths.items():
        with netCDF4.Dataset(path) as dataset:
            variable_name = next(
                SOURCE_VARIABLES[key]
                for key in SOURCE_SPECS
                if SOURCE_SPECS[key] in path.name
            )
            if variable_name not in dataset.variables:
                raise ValueError(f"{path} lacks {variable_name}")
            dates = set(map(int, np.asarray(dataset["utc_date"][:]).tolist()))
            missing = expected_dates - dates
            if missing:
                raise ValueError(f"{path} lacks UTC records {sorted(missing)}")

    existing = []
    expected_outputs = {output_path(output_directory, value) for value in timestamps}
    for timestamp in timestamps:
        path = output_path(output_directory, timestamp)
        if path.exists() or path.is_symlink():
            existing.append(path)
            if for_run and not resume:
                raise FileExistsError(f"Output already exists (use --resume): {path}")
            if resume:
                validate_cam_file(
                    path,
                    config.template_file,
                    expected_timestamp=timestamp,
                    expected_dimensions=config.expected_dimensions,
                )
    if for_run and output_directory.exists():
        allowed = set(existing)
        if resume:
            allowed.add(output_directory / "manifest.json")
        unexpected = sorted(set(output_directory.iterdir()) - allowed)
        if unexpected:
            sample = ", ".join(str(path) for path in unexpected[:3])
            suffix = " ..." if len(unexpected) > 3 else ""
            raise FileExistsError(
                f"Output directory contains {len(unexpected)} unexpected item(s): "
                f"{sample}{suffix}"
            )
        unknown_outputs = set(existing) - expected_outputs
        if unknown_outputs:  # Defensive; existing is built from expected_outputs.
            raise FileExistsError(f"Unexpected ERA5 outputs: {sorted(unknown_outputs)}")
    return {
        "config": str(config.path),
        "period": {"start": config.start.isoformat(), "end": config.end.isoformat()},
        "hours": len(timestamps),
        "unique_dynamic_source_files": len(required_paths),
        "invariant_geopotential": str(invariant),
        "template_file": str(config.template_file),
        "target_dimensions": dict(config.expected_dimensions),
        "output_directory": str(output_directory),
        "existing_valid_outputs": len(existing),
        "pending_outputs": len(timestamps) - len(existing),
        "target": {
            "lat": int(target.lat.size),
            "lon": int(target.lon.size),
            "lev": int(target.hyam.size),
            "ilev": int(target.hyai.size),
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: Mapping) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(temporary, path)


def run_conversion(config: ConversionConfig, *, resume: bool = False) -> dict:
    report = preflight(config, for_run=True, resume=resume)
    output_directory = checked_output_directory(config.output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    target = _read_target_grid(checked_read_path(config.template_file))
    revision, dirty = _git_revision()
    manifest: dict = {
        "schema_version": 1,
        "status": "running",
        "config": str(config.path),
        "config_sha256": _sha256(config.path),
        "producer_git_commit": revision,
        "producer_git_dirty": dirty,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "period": report["period"],
        "expected_file_count": report["hours"],
        "template_file": str(config.template_file),
        "source_root": str(config.source_root),
        "outputs": [],
    }
    manifest_path = output_directory / "manifest.json"
    completed: list[dict] = []
    for timestamp in hourly_range(config.start, config.end):
        path = output_path(output_directory, timestamp)
        if (path.exists() or path.is_symlink()) and resume:
            validation = validate_cam_file(
                path,
                config.template_file,
                expected_timestamp=timestamp,
                expected_dimensions=config.expected_dimensions,
            )
            validation["sha256"] = _sha256(path)
            validation["resumed"] = True
        else:
            print(f"converting {timestamp.isoformat()} -> {path}", flush=True)
            fields, source_paths = convert_timestamp(config, timestamp, target)
            write_cam_file(
                path,
                config.template_file,
                fields,
                timestamp,
                config.reference_date,
                source_paths,
            )
            validation = validate_cam_file(
                path,
                config.template_file,
                expected_timestamp=timestamp,
                expected_dimensions=config.expected_dimensions,
            )
            validation["sha256"] = _sha256(path)
            validation["resumed"] = False
        completed.append(validation)
        manifest["outputs"] = completed
        _write_json_atomic(manifest_path, manifest)
    manifest["status"] = "completed"
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["observed_file_count"] = len(completed)
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="verify inputs and report planned outputs")
    run = subparsers.add_parser("run", help="generate and validate the configured hours")
    run.add_argument(
        "--resume",
        action="store_true",
        help="skip only existing outputs that pass full validation",
    )
    validate = subparsers.add_parser("validate", help="validate one generated CAM file")
    validate.add_argument("path", type=Path)
    validate.add_argument("--timestamp", type=parse_hour)
    compare = subparsers.add_parser(
        "compare", help="report numeric differences from a canonical CAM file"
    )
    compare.add_argument("candidate", type=Path)
    compare.add_argument("reference", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "preflight":
        result = preflight(config)
    elif args.command == "run":
        result = run_conversion(config, resume=args.resume)
    elif args.command == "validate":
        result = validate_cam_file(
            checked_read_path(args.path),
            checked_read_path(config.template_file),
            expected_timestamp=args.timestamp,
            expected_dimensions=config.expected_dimensions,
        )
    elif args.command == "compare":
        result = compare_cam_files(
            checked_read_path(args.candidate), checked_read_path(args.reference)
        )
    else:  # pragma: no cover - argparse prevents this branch
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
