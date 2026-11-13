#!/usr/bin/env python3
"""Prepare area-weighted 2008 monthly AOD series for DAVINCI regions.

This script performs numeric preprocessing only. Final plots are rendered by
DAVINCI from
``analyses/davinci/era5-modis-aod-nudging-band-optics-2008-regional-aod.yaml``.
Region bounds come directly from DAVINCI's ``aerosol_region`` catalog.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import xarray as xr
from davinci_monet.geography import AEROSOL_REGIONS

DATA_ROOT = Path("/glade/work/fillmore/Data/CERES-SARB-CAM7")
DEFAULT_OUTPUT_DIR = (
    DATA_ROOT / "runs" / ("era5-modis-aod-nudging-band-optics-2008-regional-aod")
)
OUTPUT_PRODUCT = Path("products/regional_aod/analysis.nc")

REGION_DISPLAY_NAMES: Mapping[str, str] = {
    "north_atlantic_ocean": "North Atlantic Ocean",
    "south_atlantic_ocean": "South Atlantic Ocean",
    "north_indian_ocean": "North Indian Ocean",
    "north_africa": "North Africa (Sahara)",
    "southern_africa": "Southern Africa",
    "eastern_us": "Eastern US",
    "western_us": "Western US",
    "canada": "Canada",
    "south_america": "South America",
    "middle_east": "Middle East",
    "east_asia": "East Asia",
    "india": "India",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DATA_ROOT,
        help="CERES-SARB-CAM7 data root containing monthly DAVINCI runs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory used by the regional DAVINCI analysis",
    )
    return parser


def monthly_run_dir(data_root: Path, month: int) -> Path:
    """Return the accepted monthly run directory, including completed March."""
    suffix = f"era5-modis-aod-nudging-band-optics-2008-{month:02d}"
    if month == 3:
        suffix += "-complete"
    return data_root / "runs" / suffix


def _load_monthly_aod(path: Path) -> xr.DataArray:
    if not path.is_file():
        raise FileNotFoundError(f"missing monthly visible-AOD product: {path}")
    with xr.open_dataset(path) as opened:
        dataset = opened.load()
    if "column_aod" not in dataset:
        raise ValueError(f"monthly product has no column_aod: {path}")
    if "group" not in dataset.dims or dataset.sizes["group"] != 1:
        raise ValueError(f"expected one monthly group in {path}, got {dataset.sizes}")
    return dataset["column_aod"].isel(group=0, drop=True)


def area_weighted_mean(
    aod: xr.DataArray,
    extent: tuple[float, float, float, float],
) -> float:
    """Return a missing-value-aware cosine-latitude mean inside ``extent``."""
    if "lat" not in aod.coords or "lon" not in aod.coords:
        raise ValueError("regional AOD requires lat and lon coordinates")
    if aod["lat"].ndim != 1 or aod["lon"].ndim != 1:
        raise ValueError(
            "regional AOD requires one-dimensional lat and lon coordinates"
        )
    if "lat" not in aod.dims or "lon" not in aod.dims:
        raise ValueError("regional AOD requires lat and lon dimensions")

    lon_min, lon_max, lat_min, lat_max = extent
    normalized_lon = ((aod["lon"] + 180.0) % 360.0) - 180.0
    lat_mask = (aod["lat"] >= lat_min) & (aod["lat"] <= lat_max)
    lon_mask = (normalized_lon >= lon_min) & (normalized_lon <= lon_max)
    subset = aod.where(lat_mask & lon_mask, drop=True)
    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise ValueError(f"no grid cells fall inside extent {extent}")

    weights = np.cos(np.deg2rad(subset["lat"])).broadcast_like(subset)
    valid = np.isfinite(subset)
    numerator = (subset * weights).where(valid).sum(("lat", "lon"), skipna=True)
    denominator = weights.where(valid).sum(("lat", "lon"), skipna=True)
    if denominator.size != 1:
        raise ValueError(
            "regional mean input contains unsupported non-spatial dimensions"
        )
    denominator_value = float(denominator.item())
    if not np.isfinite(denominator_value) or denominator_value <= 0.0:
        return float("nan")
    return float((numerator / denominator).item())


def build_regional_timeseries(
    monthly_aod: Mapping[int, xr.DataArray],
) -> xr.Dataset:
    """Build one 12-month time series for every cataloged aerosol region."""
    if set(monthly_aod) != set(range(1, 13)):
        raise ValueError("regional time series require all twelve monthly products")
    if set(REGION_DISPLAY_NAMES) != set(AEROSOL_REGIONS):
        raise ValueError(
            "region display names do not match the DAVINCI aerosol catalog"
        )

    time = np.asarray([np.datetime64(f"2008-{month:02d}-15") for month in range(1, 13)])
    variables: dict[str, xr.DataArray] = {}
    for region, extent in AEROSOL_REGIONS.items():
        values = np.asarray(
            [area_weighted_mean(monthly_aod[month], extent) for month in range(1, 13)],
            dtype="float32",
        )
        variables[region] = xr.DataArray(
            values,
            dims=("time",),
            coords={"time": time},
            attrs={
                "units": "1",
                "display_name": "Visible Aerosol Optical Depth",
                "long_name": (
                    f"Cosine-latitude-weighted monthly mean visible AOD over "
                    f"{REGION_DISPLAY_NAMES[region]}"
                ),
                "region_name": REGION_DISPLAY_NAMES[region],
                "region_extent": ",".join(str(value) for value in extent),
                "wavelength_micrometers": 0.546,
            },
        )

    result = xr.Dataset(variables)
    result.attrs.update(
        {
            "geometry": "grid",
            "analysis_type": "regional_timeseries",
            "source_label": "era5_modis_aod_nudging_band_optics_2008",
            "spatial_weighting": "cosine(latitude), renormalized over finite cells",
            "region_catalog": "DAVINCI aerosol_region",
            "region_reference": "https://doi.org/10.5194/gmd-11-2333-2018",
            "wavelength_micrometers": 0.546,
        }
    )
    return result


def prepare(data_root: Path, output_dir: Path) -> dict[str, object]:
    """Load monthly products and atomically write the regional time series."""
    monthly_aod: dict[int, xr.DataArray] = {}
    inputs: list[str] = []
    for month in range(1, 13):
        path = (
            monthly_run_dir(data_root, month)
            / "products"
            / "visible_optics"
            / "analysis.nc"
        )
        monthly_aod[month] = _load_monthly_aod(path)
        inputs.append(str(path))

    product = build_regional_timeseries(monthly_aod)
    destination = output_dir / OUTPUT_PRODUCT
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".nc.tmp")
    product.to_netcdf(temporary)
    temporary.replace(destination)

    summary: dict[str, object] = {
        "status": "completed",
        "output": str(destination),
        "inputs": inputs,
        "variable": "visible column AOD",
        "wavelength_micrometers": 0.546,
        "spatial_weighting": "cosine(latitude), renormalized over finite cells",
        "region_reference": "https://doi.org/10.5194/gmd-11-2333-2018",
        "regions": {
            name: {
                "display_name": REGION_DISPLAY_NAMES[name],
                "extent": list(extent),
            }
            for name, extent in AEROSOL_REGIONS.items()
        },
    }
    summary_path = output_dir / "regional-aod-preparation.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    args = _parser().parse_args()
    summary = prepare(args.data_root, args.output_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
