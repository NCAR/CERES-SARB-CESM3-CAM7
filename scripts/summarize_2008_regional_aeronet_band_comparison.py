#!/usr/bin/env python3
"""Generate CAM7-versus-AERONET statistics tables from paired daily products.

The input products are created by
``prepare_2008_regional_aeronet_band_comparison.py``.  Statistics use the
DAVINCI metric implementations with AERONET as the reference (x) and CAM7 as
the comparison (y), so positive mean bias means CAM7 exceeds AERONET.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
from davinci_monet.geography import AEROSOL_REGIONS
from davinci_monet.stats.metrics import get_metric

# Support both ``python -m scripts.summarize_...`` and direct script execution.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.prepare_2008_regional_aod import REGION_DISPLAY_NAMES

DATA_ROOT = Path("/glade/work/fillmore/Data/CERES-SARB-CAM7")
DEFAULT_PRODUCT_DIR = DATA_ROOT / "runs" / (
    "era5-modis-aod-nudging-band-optics-2008-regional-aeronet"
) / "products" / "regional_aeronet_band_comparison"
DEFAULT_TABLE_DIR = REPOSITORY_ROOT / "analyses" / "statistics" / (
    "era5-modis-aod-nudging-band-optics-2008-regional-aeronet"
)
REGIONAL_FILENAME = "regional_statistics.csv"
WAVELENGTH_FILENAME = "wavelength_statistics.csv"
REPORT_FILENAME = "README.md"


@dataclass(frozen=True)
class BandComparison:
    """Metadata required to identify and validate one wavelength pair."""

    code: str
    cam_wavelength_nm: int
    aeronet_wavelength_nm: int


BANDS: Mapping[str, BandComparison] = {
    "ultraviolet": BandComparison("SW02", 340, 340),
    "visible": BandComparison("SW05", 546, 500),
    "near_infrared": BandComparison("SW08", 842, 870),
    "shortwave_infrared": BandComparison("SW11", 1660, 1640),
}

METRICS: Mapping[str, str] = {
    "aeronet_mean": "MX",
    "cam7_mean": "MY",
    "mean_bias": "MB",
    "mean_absolute_error": "ME",
    "rmse": "RMSE",
    "correlation": "R",
}

REGIONAL_FIELDS = (
    "band",
    "cam_band_code",
    "cam_wavelength_nm",
    "aeronet_wavelength_nm",
    "region",
    "region_name",
    "paired_days",
    "site_days",
    "matched_hourly_pairs",
    "mean_active_sites_per_paired_day",
    *METRICS,
)

WAVELENGTH_FIELDS = (
    "band",
    "cam_band_code",
    "cam_wavelength_nm",
    "aeronet_wavelength_nm",
    "regions",
    "paired_region_days",
    "site_days",
    "matched_hourly_pairs",
    "mean_active_sites_per_region_day",
    *METRICS,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--product-dir",
        type=Path,
        default=DEFAULT_PRODUCT_DIR,
        help="Directory containing one <band>/analysis.nc product per comparison",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_TABLE_DIR,
        help="Destination for the CSV and Markdown tables",
    )
    return parser


def paired_statistics(
    aeronet: np.ndarray,
    cam7: np.ndarray,
) -> dict[str, float | int]:
    """Return standard DAVINCI statistics for paired AERONET and CAM7 data."""
    reference = np.asarray(aeronet, dtype="float64")
    comparison = np.asarray(cam7, dtype="float64")
    if reference.shape != comparison.shape:
        raise ValueError("AERONET and CAM7 arrays must have the same shape")
    paired_days = int(get_metric("N").compute(reference, comparison))
    values: dict[str, float | int] = {"paired_days": paired_days}
    for output_name, metric_name in METRICS.items():
        values[output_name] = float(
            get_metric(metric_name).compute(reference, comparison)
        )
    return values


def _validate_product(
    dataset: xr.Dataset,
    path: Path,
    spec: BandComparison,
) -> None:
    expected_attrs = {
        "cam_band_code": spec.code,
        "cam_band_center_nanometers": spec.cam_wavelength_nm,
        "aeronet_channel_nanometers": spec.aeronet_wavelength_nm,
    }
    for name, expected in expected_attrs.items():
        actual = dataset.attrs.get(name)
        if actual != expected:
            raise ValueError(f"{path}: {name} is {actual!r}; expected {expected!r}")


def regional_statistics(
    product_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, tuple[np.ndarray, np.ndarray]]]:
    """Read paired products and return regional rows plus pooled band values."""
    rows: list[dict[str, Any]] = []
    pooled: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    for band, spec in BANDS.items():
        path = product_dir / band / "analysis.nc"
        if not path.is_file():
            raise FileNotFoundError(f"missing paired product: {path}")
        band_aeronet: list[np.ndarray] = []
        band_cam7: list[np.ndarray] = []
        with xr.open_dataset(path) as dataset:
            _validate_product(dataset, path, spec)
            for region in AEROSOL_REGIONS:
                aeronet_name = f"aeronet_{region}"
                cam7_name = f"cam_{region}"
                site_count_name = f"site_count_{region}"
                pair_count_name = f"pair_count_{region}"
                required = (
                    aeronet_name,
                    cam7_name,
                    site_count_name,
                    pair_count_name,
                )
                missing = [name for name in required if name not in dataset]
                if missing:
                    raise ValueError(f"{path}: missing variables {missing}")

                aeronet = np.asarray(dataset[aeronet_name].values, dtype="float64")
                cam7 = np.asarray(dataset[cam7_name].values, dtype="float64")
                valid = np.isfinite(aeronet) & np.isfinite(cam7)
                stats = paired_statistics(aeronet, cam7)
                if not stats["paired_days"]:
                    continue

                site_days = int(
                    np.asarray(dataset[site_count_name].values)[valid].sum()
                )
                matched_pairs = int(
                    np.asarray(dataset[pair_count_name].values)[valid].sum()
                )
                paired_days = int(stats["paired_days"])
                rows.append(
                    {
                        "band": band,
                        "cam_band_code": spec.code,
                        "cam_wavelength_nm": spec.cam_wavelength_nm,
                        "aeronet_wavelength_nm": spec.aeronet_wavelength_nm,
                        "region": region,
                        "region_name": REGION_DISPLAY_NAMES[region],
                        "site_days": site_days,
                        "matched_hourly_pairs": matched_pairs,
                        "mean_active_sites_per_paired_day": site_days / paired_days,
                        **stats,
                    }
                )
                band_aeronet.append(aeronet[valid])
                band_cam7.append(cam7[valid])

        if not band_aeronet:
            raise ValueError(f"{path}: no finite paired regional daily means")
        pooled[band] = (
            np.concatenate(band_aeronet),
            np.concatenate(band_cam7),
        )

    return rows, pooled


def wavelength_statistics(
    regional_rows: Sequence[Mapping[str, Any]],
    pooled: Mapping[str, tuple[np.ndarray, np.ndarray]],
) -> list[dict[str, Any]]:
    """Return equal-region-day pooled statistics for each wavelength pair."""
    rows: list[dict[str, Any]] = []
    for band, spec in BANDS.items():
        band_rows = [row for row in regional_rows if row["band"] == band]
        if not band_rows or band not in pooled:
            raise ValueError(f"no regional statistics available for {band}")
        aeronet, cam7 = pooled[band]
        stats = paired_statistics(aeronet, cam7)
        site_days = sum(int(row["site_days"]) for row in band_rows)
        paired_region_days = int(stats.pop("paired_days"))
        rows.append(
            {
                "band": band,
                "cam_band_code": spec.code,
                "cam_wavelength_nm": spec.cam_wavelength_nm,
                "aeronet_wavelength_nm": spec.aeronet_wavelength_nm,
                "regions": len(band_rows),
                "paired_region_days": paired_region_days,
                "site_days": site_days,
                "matched_hourly_pairs": sum(
                    int(row["matched_hourly_pairs"]) for row in band_rows
                ),
                "mean_active_sites_per_region_day": site_days / paired_region_days,
                **stats,
            }
        )
    return rows


def _csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return "NA" if not np.isfinite(value) else f"{value:.6f}"
    return value


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> None:
    """Write a deterministic CSV table."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row[field]) for field in fields})


def _display_band(band: str) -> str:
    return band.replace("_", " ").title()


def _number(value: Any, digits: int = 4) -> str:
    if isinstance(value, (float, np.floating)):
        return "NA" if not np.isfinite(value) else f"{value:.{digits}f}"
    return str(value)


def render_markdown(
    regional_rows: Sequence[Mapping[str, Any]],
    wavelength_rows: Sequence[Mapping[str, Any]],
    product_dir: Path,
) -> str:
    """Render human-readable summary and regional statistics tables."""
    lines = [
        "# CAM7 vs AERONET Daily Regional AOD Statistics (2008)",
        "",
        "These tables summarize the paired daily regional means used in the "
        "accepted CAM7-versus-AERONET time-series plots.",
        "",
        f"Source products: `{product_dir}`",
        "",
        "AERONET is the reference and CAM7 is the comparison. Mean bias (MB) "
        "is `CAM7 - AERONET`; mean error (ME) is the mean absolute error. "
        "N is the number of paired regional days. Regional daily values first "
        "average matched hours within each site and then give each active site "
        "equal weight. The wavelength summary pools those regional daily values "
        "with equal weight per available region-day.",
        "",
        "The visible comparison uses AERONET 500 nm because its routine coverage "
        "is much broader than the nominally closer 551 nm specialty channel. "
        "South Atlantic Ocean and Southern Africa have no 1640 nm paired days.",
        "",
        "## Wavelength summary",
        "",
        "| CAM band | CAM7 nm | AERONET nm | Regions | N | AERONET mean | CAM7 mean | MB | ME | RMSE | R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in wavelength_rows:
        lines.append(
            "| {band} ({code}) | {cam_nm} | {aeronet_nm} | {regions} | {n} | "
            "{obs} | {cam} | {mb} | {me} | {rmse} | {r} |".format(
                band=_display_band(str(row["band"])),
                code=row["cam_band_code"],
                cam_nm=row["cam_wavelength_nm"],
                aeronet_nm=row["aeronet_wavelength_nm"],
                regions=row["regions"],
                n=row["paired_region_days"],
                obs=_number(row["aeronet_mean"]),
                cam=_number(row["cam7_mean"]),
                mb=_number(row["mean_bias"]),
                me=_number(row["mean_absolute_error"]),
                rmse=_number(row["rmse"]),
                r=_number(row["correlation"]),
            )
        )

    regional_header = (
        "| Region | N | Site-days | Hourly pairs | Mean sites/day | "
        "AERONET mean | CAM7 mean | MB | ME | RMSE | R |"
    )
    regional_separator = (
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    for band, spec in BANDS.items():
        lines.extend(
            [
                "",
                f"## {_display_band(band)}: CAM7 {spec.cam_wavelength_nm} nm vs "
                f"AERONET {spec.aeronet_wavelength_nm} nm",
                "",
                regional_header,
                regional_separator,
            ]
        )
        for row in regional_rows:
            if row["band"] != band:
                continue
            lines.append(
                "| {region} | {n} | {site_days} | {pairs} | {sites:.2f} | "
                "{obs} | {cam} | {mb} | {me} | {rmse} | {r} |".format(
                    region=row["region_name"],
                    n=row["paired_days"],
                    site_days=row["site_days"],
                    pairs=row["matched_hourly_pairs"],
                    sites=row["mean_active_sites_per_paired_day"],
                    obs=_number(row["aeronet_mean"]),
                    cam=_number(row["cam7_mean"]),
                    mb=_number(row["mean_bias"]),
                    me=_number(row["mean_absolute_error"]),
                    rmse=_number(row["rmse"]),
                    r=_number(row["correlation"]),
                )
            )

    lines.extend(
        [
            "",
            "Machine-readable tables: "
            f"[`{WAVELENGTH_FILENAME}`]({WAVELENGTH_FILENAME}) and "
            f"[`{REGIONAL_FILENAME}`]({REGIONAL_FILENAME}).",
            "",
            "Generated by "
            "`scripts/summarize_2008_regional_aeronet_band_comparison.py` "
            "using DAVINCI metric definitions.",
            "",
        ]
    )
    return "\n".join(lines)


def generate(product_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Generate all tables and return a compact result summary."""
    regional_rows, pooled = regional_statistics(product_dir)
    wavelength_rows = wavelength_statistics(regional_rows, pooled)
    write_csv(output_dir / REGIONAL_FILENAME, regional_rows, REGIONAL_FIELDS)
    write_csv(
        output_dir / WAVELENGTH_FILENAME,
        wavelength_rows,
        WAVELENGTH_FIELDS,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / REPORT_FILENAME).write_text(
        render_markdown(regional_rows, wavelength_rows, product_dir),
        encoding="utf-8",
    )
    return {
        "regional_rows": len(regional_rows),
        "wavelength_rows": len(wavelength_rows),
        "output_dir": str(output_dir),
    }


def main() -> None:
    args = _parser().parse_args()
    result = generate(args.product_dir, args.output_dir)
    print(
        f"wrote {result['regional_rows']} regional rows and "
        f"{result['wavelength_rows']} wavelength rows to {result['output_dir']}"
    )


if __name__ == "__main__":
    main()
