#!/usr/bin/env python3
"""Prepare day-weighted 2008 seasonal and annual aerosol-optics products.

This is numeric preprocessing only.  Final plots are rendered by DAVINCI from
``analyses/davinci/era5-modis-aod-nudging-band-optics-2008-composites.yaml``.
The monthly DAVINCI products are sufficient statistics for exact temporal
aggregation: shortwave scattering is AOD times SSA, and the asymmetry
numerator is scattering times asymmetry.  Longwave products already retain
both column extinction and column scattering.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import xarray as xr

DATA_ROOT = Path("/glade/work/fillmore/Data/CERES-SARB-CAM7")
DEFAULT_OUTPUT_DIR = (
    DATA_ROOT / "runs" / ("era5-modis-aod-nudging-band-optics-2008-composites")
)

MONTH_DAYS: Mapping[int, int] = {
    1: 31,
    2: 28,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}

GROUP_MONTHS: Mapping[str, tuple[int, ...]] = {
    "DJF": (1, 2, 12),
    "MAM": (3, 4, 5),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
    "Annual": tuple(range(1, 13)),
}

BAND_KINDS: Mapping[str, str] = {
    "ultraviolet_optics": "shortwave",
    "visible_optics": "shortwave",
    "near_infrared_optics": "shortwave",
    "shortwave_infrared_optics": "shortwave",
    "water_vapor_optics": "longwave",
    "ozone_optics": "longwave",
    "atmospheric_window_optics": "longwave",
    "carbon_dioxide_optics": "longwave",
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
        help="Output directory used by the composite DAVINCI analysis",
    )
    return parser


def monthly_run_dir(data_root: Path, month: int) -> Path:
    suffix = f"era5-modis-aod-nudging-band-optics-2008-{month:02d}"
    if month == 3:
        suffix += "-complete"
    return data_root / "runs" / suffix


def _load_monthly_product(path: Path) -> xr.Dataset:
    if not path.is_file():
        raise FileNotFoundError(f"missing monthly DAVINCI product: {path}")
    with xr.open_dataset(path) as opened:
        dataset = opened.load()
    if "group" not in dataset.dims or dataset.sizes["group"] != 1:
        raise ValueError(f"expected one monthly group in {path}, got {dataset.sizes}")
    return dataset.isel(group=0, drop=True)


def _weighted_mean(
    values: Sequence[xr.DataArray], weights: Sequence[float]
) -> xr.DataArray:
    if len(values) != len(weights) or not values:
        raise ValueError(
            "weighted mean requires equally sized, nonempty values and weights"
        )
    numerators: list[xr.DataArray] = []
    denominators: list[xr.DataArray] = []
    for value, weight in zip(values, weights, strict=True):
        valid = np.isfinite(value)
        numerators.append(value.where(valid, 0.0) * float(weight))
        denominators.append(xr.ones_like(value).where(valid, 0.0) * float(weight))
    numerator = xr.concat(numerators, dim="month_component").sum("month_component")
    denominator = xr.concat(denominators, dim="month_component").sum("month_component")
    return (numerator / denominator.where(denominator > 0.0)).astype("float32")


def _weighted_ratio(
    numerators: Sequence[xr.DataArray],
    denominators: Sequence[xr.DataArray],
    weights: Sequence[float],
) -> xr.DataArray:
    if (
        not numerators
        or len(numerators) != len(denominators)
        or len(numerators) != len(weights)
    ):
        raise ValueError("weighted ratio inputs must be equally sized and nonempty")
    weighted_numerators: list[xr.DataArray] = []
    weighted_denominators: list[xr.DataArray] = []
    for numerator, denominator, weight in zip(
        numerators, denominators, weights, strict=True
    ):
        valid = np.isfinite(numerator) & np.isfinite(denominator)
        weighted_numerators.append(numerator.where(valid, 0.0) * float(weight))
        weighted_denominators.append(denominator.where(valid, 0.0) * float(weight))
    numerator_sum = xr.concat(weighted_numerators, dim="month_component").sum(
        "month_component"
    )
    denominator_sum = xr.concat(weighted_denominators, dim="month_component").sum(
        "month_component"
    )
    return (numerator_sum / denominator_sum.where(denominator_sum > 0.0)).astype(
        "float32"
    )


def _monthly_components(dataset: xr.Dataset, kind: str) -> dict[str, xr.DataArray]:
    if kind == "shortwave":
        required = {"column_aod", "single_scatter_albedo", "asymmetry"}
        missing = required - set(dataset.data_vars)
        if missing:
            raise ValueError(f"shortwave monthly product is missing {sorted(missing)}")
        extinction = dataset["column_aod"]
        scattering = extinction * dataset["single_scatter_albedo"]
    elif kind == "longwave":
        required = {"column_scattering", "column_extinction", "asymmetry"}
        missing = required - set(dataset.data_vars)
        if missing:
            raise ValueError(f"longwave monthly product is missing {sorted(missing)}")
        extinction = dataset["column_extinction"]
        scattering = dataset["column_scattering"]
    else:
        raise ValueError(f"unsupported band kind: {kind}")
    return {
        "extinction": extinction,
        "scattering": scattering,
        "asymmetry_numerator": scattering * dataset["asymmetry"],
    }


def _composite_group(
    monthly: Mapping[int, dict[str, xr.DataArray]],
    months: Sequence[int],
    kind: str,
) -> dict[str, xr.DataArray]:
    weights = [float(MONTH_DAYS[month]) for month in months]
    extinction = [monthly[month]["extinction"] for month in months]
    scattering = [monthly[month]["scattering"] for month in months]
    asymmetry_numerator = [monthly[month]["asymmetry_numerator"] for month in months]
    extinction_mean = _weighted_mean(extinction, weights)
    scattering_mean = _weighted_mean(scattering, weights)
    asymmetry = _weighted_ratio(asymmetry_numerator, scattering, weights)
    if kind == "shortwave":
        return {
            "column_aod": extinction_mean,
            "single_scatter_albedo": _weighted_ratio(scattering, extinction, weights),
            "asymmetry": asymmetry,
        }
    return {
        "column_scattering": scattering_mean,
        "column_extinction": extinction_mean,
        "asymmetry": asymmetry,
    }


def build_band_composites(
    monthly_products: Mapping[int, xr.Dataset], kind: str
) -> xr.Dataset:
    if set(monthly_products) != set(range(1, 13)):
        raise ValueError("composites require all twelve monthly products")
    monthly = {
        month: _monthly_components(dataset, kind)
        for month, dataset in monthly_products.items()
    }
    by_group = {
        name: _composite_group(monthly, months, kind)
        for name, months in GROUP_MONTHS.items()
    }
    group_coord = xr.IndexVariable("group", list(GROUP_MONTHS))
    variables = {
        variable: xr.concat(
            [by_group[group][variable] for group in GROUP_MONTHS], dim=group_coord
        )
        for variable in next(iter(by_group.values()))
    }
    result = xr.Dataset(variables)
    result.attrs.update(
        {
            "geometry": "grid",
            "analysis_type": "calendar_year_composite",
            "source_label": "era5_modis_aod_nudging_band_optics_2008_composites",
            "weighting": "calendar-day weighted from complete monthly means",
            "calendar": "NO_LEAP",
            "djf_definition": "January, February, and December 2008",
        }
    )
    for variable in result.data_vars:
        result[variable].attrs["units"] = "1"
    if kind == "shortwave":
        result["column_aod"].attrs.update(
            display_name="Column Aerosol Optical Depth", style_preset="geosit_aod"
        )
        result["single_scatter_albedo"].attrs["display_name"] = "Single-Scatter Albedo"
    else:
        result["column_scattering"].attrs[
            "display_name"
        ] = "Column Scattering Optical Depth"
        result["column_extinction"].attrs.update(
            display_name="Column Extinction Optical Depth",
            style_preset="geosit_aod",
        )
    result["asymmetry"].attrs["display_name"] = "Asymmetry Parameter"
    return result


def prepare(data_root: Path, output_dir: Path) -> dict[str, object]:
    products_dir = output_dir / "products"
    products_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "status": "completed",
        "calendar": "NO_LEAP",
        "weighting": "calendar-day weighted",
        "groups": {name: list(months) for name, months in GROUP_MONTHS.items()},
        "bands": {},
    }
    band_summary: dict[str, object] = {}
    for band, kind in BAND_KINDS.items():
        monthly_products: dict[int, xr.Dataset] = {}
        inputs: list[str] = []
        for month in range(1, 13):
            path = monthly_run_dir(data_root, month) / "products" / band / "analysis.nc"
            monthly_products[month] = _load_monthly_product(path)
            inputs.append(str(path))
        composite = build_band_composites(monthly_products, kind)
        destination = products_dir / band / "analysis.nc"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".nc.tmp")
        composite.to_netcdf(temporary)
        temporary.replace(destination)
        band_summary[band] = {
            "kind": kind,
            "inputs": inputs,
            "output": str(destination),
            "groups": list(GROUP_MONTHS),
        }
    summary["bands"] = band_summary
    summary_path = output_dir / "composite-preparation.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    args = _parser().parse_args()
    summary = prepare(args.data_root.resolve(), args.output_dir.resolve())
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
