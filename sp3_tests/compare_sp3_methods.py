#!/usr/bin/env python3
"""Compare SP3 remap and LFL-native LUT aerosol optics outputs."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import xarray as xr

from sp3_optics.lfl_bands import LFL_SW_EDGES_UM

EXT = "Extinction_Layer_Optical_Depth"
SCA = "Scattering_Layer_Optical_Depth"
ASM = "Layer_Asymmetry_Parameter"
COL = "Extinction_Column_Optical_Depth"
DEFAULT_BANDS = tuple(f"SW{i:02d}" for i in range(1, 15)) + tuple(f"LW{i:02d}" for i in range(1, 13))
VISIBLE_BAND = "SW05"
CAM_VISIBLE_BAND = "CAMVIS"
CAM_VISIBLE_LOW_CM = 16000.0
CAM_VISIBLE_HIGH_CM = 22650.0


@dataclass(frozen=True)
class BandComparison:
    band: str
    common_times: int
    count: int
    remap_column_mean: float
    lut_column_mean: float
    median_ratio: float
    median_abs_relative_difference: float
    mean_abs_relative_difference: float
    median_ssa_difference: float
    median_asymmetry_difference: float


@dataclass(frozen=True)
class AodComparison:
    band: str
    h0_variable: str
    stamp_count: int
    stamps: str
    count: int
    band_column_mean: float
    h0_mean: float
    median_ratio: float
    mean_abs_relative_difference: float


def normalize_band(band: str) -> str:
    text = band.strip().upper()
    if len(text) == 4 and (text.startswith("SW") or text.startswith("LW")):
        return text
    raise ValueError(f"unsupported band name {band!r}")


def parse_sp3_name(path: Path) -> tuple[str, str]:
    parts = path.name.split(".")
    if len(parts) != 4 or parts[-1] != "nc":
        raise ValueError(f"not an SP3 filename: {path.name}")
    return parts[0].split("_")[-1].upper(), f"{parts[1]}.{parts[2]}"


def band_files_by_stamp(indir: Path, band: str) -> dict[str, Path]:
    wanted = normalize_band(band)
    files: dict[str, Path] = {}
    for path in sorted(indir.glob(f"*_{wanted}.*.nc")):
        found_band, stamp = parse_sp3_name(path)
        if found_band == wanted:
            files[stamp] = path
    if not files:
        raise FileNotFoundError(f"no SP3 files for {wanted} under {indir}")
    return files


def load_band_mean(indir: Path, band: str, stamps: Iterable[str] | None = None) -> xr.Dataset:
    files_by_stamp = band_files_by_stamp(indir, band)
    selected_stamps = sorted(files_by_stamp) if stamps is None else sorted(stamps)
    datasets = []
    for stamp in selected_stamps:
        try:
            path = files_by_stamp[stamp]
        except KeyError as exc:
            raise FileNotFoundError(f"{indir} has no {band} file for stamp {stamp}") from exc
        with xr.open_dataset(path) as ds:
            datasets.append(ds.load())
    if not datasets:
        raise FileNotFoundError(f"no selected {band} files under {indir}")
    if len(datasets) == 1:
        return datasets[0]
    accum = datasets[0].copy(deep=True)
    for name in (EXT, SCA, COL, "DELP"):
        if name in accum:
            values = [np.asarray(ds[name], dtype=float) for ds in datasets]
            accum[name].values[:] = np.nanmean(np.stack(values, axis=0), axis=0)
    if SCA in accum and ASM in accum:
        sca_values = [np.asarray(ds[SCA], dtype=float) for ds in datasets]
        asm_values = [np.asarray(ds[ASM], dtype=float) for ds in datasets]
        sca_stack = np.stack(sca_values, axis=0)
        moment_stack = sca_stack * np.stack(asm_values, axis=0)
        sca_mean = np.nanmean(sca_stack, axis=0)
        moment_mean = np.nanmean(moment_stack, axis=0)
        accum[ASM].values[:] = np.divide(
            moment_mean,
            sca_mean,
            out=np.zeros_like(moment_mean),
            where=sca_mean > 1.0e-12,
        )
    return accum


def common_stamps(left: Path, right: Path, band: str) -> list[str]:
    left_files = band_files_by_stamp(left, band)
    right_files = band_files_by_stamp(right, band)
    stamps = sorted(set(left_files).intersection(right_files))
    if not stamps:
        raise FileNotFoundError(f"no common {band} stamps between {left} and {right}")
    return stamps


def layer_to_column(ds: xr.Dataset, variable: str) -> np.ndarray:
    data = ds[variable]
    if "time" in data.dims:
        data = data.mean("time")
    if "lev" in data.dims:
        data = data.sum("lev")
    return np.asarray(data, dtype=float)


def column_ssa(ds: xr.Dataset) -> np.ndarray:
    sca = layer_to_column(ds, SCA)
    ext = np.asarray(ds[COL], dtype=float)
    return np.divide(sca, ext, out=np.zeros_like(ext), where=ext > 1.0e-12)


def column_asymmetry(ds: xr.Dataset) -> np.ndarray:
    sca = np.asarray(ds[SCA], dtype=float)
    asm = np.asarray(ds[ASM], dtype=float)
    if sca.ndim == 4:
        sca = np.nanmean(sca, axis=0)
        asm = np.nanmean(asm, axis=0)
    sca_col = np.nansum(sca, axis=0)
    weighted = np.nansum(sca * asm, axis=0)
    return np.divide(weighted, sca_col, out=np.zeros_like(sca_col), where=sca_col > 1.0e-12)


def finite_pair(reference: np.ndarray, candidate: np.ndarray, min_reference: float = 1.0e-12) -> tuple[np.ndarray, np.ndarray]:
    ref = np.asarray(reference, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    mask = np.isfinite(ref) & np.isfinite(cand) & (np.abs(ref) > min_reference)
    return ref[mask], cand[mask]


def selected_single_stamp(sp3_dir: Path, band: str, stamp: str | None, label: str | None = None) -> list[str]:
    if stamp is not None:
        return [stamp]
    files_by_stamp = band_files_by_stamp(sp3_dir, band)
    if len(files_by_stamp) == 1:
        return sorted(files_by_stamp)
    display = label or normalize_band(band)
    raise ValueError(f"{display}: multiple SP3 times under {sp3_dir}; pass --h0-stamp for h0 comparison")


def _stamp_seconds(stamp: str) -> int:
    try:
        return int(stamp.split(".")[-1])
    except ValueError as exc:
        raise ValueError(f"could not parse seconds from SP3 stamp {stamp!r}") from exc


def _stamp_date(stamp: str) -> int:
    text = stamp.split(".")[0].replace("-", "")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"could not parse date from SP3 stamp {stamp!r}") from exc


def _time_axis_values(ds: xr.Dataset, name: str, expected_size: int) -> np.ndarray | None:
    if name not in ds:
        return None
    values = np.asarray(ds[name].values)
    if values.ndim == 0:
        values = np.full(expected_size, values.item())
    values = values.reshape(-1)
    if values.size != expected_size:
        raise ValueError(f"h0 {name!r} has {values.size} values but expected {expected_size} time records")
    return values


def h0_values_for_stamp(ds: xr.Dataset, variable: str, stamp: str | None) -> np.ndarray:
    h0 = ds[variable]
    if "time" not in h0.dims:
        if stamp is not None:
            raise ValueError(f"{variable}: cannot validate --h0-stamp {stamp!r} because h0 variable has no time axis")
        return np.asarray(h0, dtype=float)
    if h0.sizes["time"] == 1 and stamp is None:
        return np.asarray(h0.isel(time=0), dtype=float)
    if stamp is None:
        raise ValueError(f"{variable} has multiple h0 times; pass --h0-stamp to select the matching SP3 time")
    time_size = int(h0.sizes["time"])
    date_values = _time_axis_values(ds, "date", time_size)
    if date_values is None:
        raise ValueError(f"{variable}: cannot validate --h0-stamp {stamp!r} because h0 lacks a time-indexed date field")
    date_mask = date_values.astype(np.int64) == _stamp_date(stamp)
    seconds = _stamp_seconds(stamp)
    for time_name in ("datesec", "nscur"):
        values = _time_axis_values(ds, time_name, time_size)
        if values is None:
            continue
        matches = np.flatnonzero(date_mask & (values.astype(np.int64) == seconds))
        if matches.size == 1:
            return np.asarray(h0.isel(time=int(matches[0])), dtype=float)
        if matches.size > 1:
            raise ValueError(f"{variable}: --h0-stamp {stamp!r} matched multiple h0 records")
    raise ValueError(f"{variable}: could not match --h0-stamp {stamp!r} to h0 date and datesec/nscur")


def h0_stamps(ds: xr.Dataset, variable: str) -> list[str]:
    h0 = ds[variable]
    if "time" not in h0.dims:
        raise ValueError(f"{variable}: h0 variable has no time axis")
    time_size = int(h0.sizes["time"])
    date_values = _time_axis_values(ds, "date", time_size)
    if date_values is None:
        raise ValueError(f"{variable}: h0 file lacks a time-indexed date field")
    for time_name in ("datesec", "nscur"):
        seconds_values = _time_axis_values(ds, time_name, time_size)
        if seconds_values is not None:
            return [
                f"{int(date):08d}.{int(seconds):05d}"
                for date, seconds in zip(date_values.astype(np.int64), seconds_values.astype(np.int64))
            ]
    raise ValueError(f"{variable}: h0 file lacks datesec/nscur time fields")


def compare_band(remap_dir: Path, lut_dir: Path, band: str) -> BandComparison:
    normalized = normalize_band(band)
    stamps = common_stamps(remap_dir, lut_dir, normalized)
    remap_col_values: list[np.ndarray] = []
    lut_col_values: list[np.ndarray] = []
    remap_ssa_values: list[np.ndarray] = []
    lut_ssa_values: list[np.ndarray] = []
    remap_g_values: list[np.ndarray] = []
    lut_g_values: list[np.ndarray] = []
    for stamp in stamps:
        remap = load_band_mean(remap_dir, normalized, [stamp])
        lut = load_band_mean(lut_dir, normalized, [stamp])
        remap_col_stamp, lut_col_stamp = finite_pair(remap[COL].values, lut[COL].values)
        if remap_col_stamp.size:
            remap_col_values.append(remap_col_stamp)
            lut_col_values.append(lut_col_stamp)
        remap_ssa_stamp, lut_ssa_stamp = finite_pair(column_ssa(remap), column_ssa(lut), min_reference=0.0)
        if remap_ssa_stamp.size:
            remap_ssa_values.append(remap_ssa_stamp)
            lut_ssa_values.append(lut_ssa_stamp)
        remap_g_stamp, lut_g_stamp = finite_pair(column_asymmetry(remap), column_asymmetry(lut), min_reference=0.0)
        if remap_g_stamp.size:
            remap_g_values.append(remap_g_stamp)
            lut_g_values.append(lut_g_stamp)
    remap_col = np.concatenate(remap_col_values) if remap_col_values else np.asarray([], dtype=float)
    lut_col = np.concatenate(lut_col_values) if lut_col_values else np.asarray([], dtype=float)
    if remap_col.size == 0:
        raise ValueError(f"{normalized}: no finite nonzero remap column cells")
    remap_ssa = np.concatenate(remap_ssa_values) if remap_ssa_values else np.asarray([], dtype=float)
    lut_ssa = np.concatenate(lut_ssa_values) if lut_ssa_values else np.asarray([], dtype=float)
    remap_g = np.concatenate(remap_g_values) if remap_g_values else np.asarray([], dtype=float)
    lut_g = np.concatenate(lut_g_values) if lut_g_values else np.asarray([], dtype=float)
    ratio = lut_col / remap_col
    rel = np.abs(lut_col - remap_col) / np.abs(remap_col)
    return BandComparison(
        band=normalized,
        common_times=len(stamps),
        count=int(remap_col.size),
        remap_column_mean=float(np.nanmean(remap_col)),
        lut_column_mean=float(np.nanmean(lut_col)),
        median_ratio=float(np.nanmedian(ratio)),
        median_abs_relative_difference=float(np.nanmedian(rel)),
        mean_abs_relative_difference=float(np.nanmean(rel)),
        median_ssa_difference=float(np.nanmedian(lut_ssa - remap_ssa)) if remap_ssa.size else float("nan"),
        median_asymmetry_difference=float(np.nanmedian(lut_g - remap_g)) if remap_g.size else float("nan"),
    )


def compare_directories(remap_dir: Path, lut_dir: Path, bands: Iterable[str] = DEFAULT_BANDS) -> list[BandComparison]:
    return [compare_band(remap_dir, lut_dir, band) for band in bands]


def compare_band_to_h0(
    sp3_dir: Path,
    h0_file: Path,
    *,
    band: str = VISIBLE_BAND,
    h0_variable: str = "AODVISdn",
    stamp: str | None = None,
) -> AodComparison:
    stamps = selected_single_stamp(sp3_dir, band, stamp)
    sp3 = load_band_mean(sp3_dir, band, stamps)
    with xr.open_dataset(h0_file) as ds:
        h0_values = h0_values_for_stamp(ds, h0_variable, stamps[0])
    h0_col, band_col = finite_pair(h0_values, sp3[COL].values)
    if h0_col.size == 0:
        raise ValueError(f"{band}: no finite nonzero cells for {h0_variable} comparison")
    ratio = band_col / h0_col
    rel = np.abs(band_col - h0_col) / np.abs(h0_col)
    return AodComparison(
        band=normalize_band(band),
        h0_variable=h0_variable,
        stamp_count=1,
        stamps=stamps[0],
        count=int(band_col.size),
        band_column_mean=float(np.nanmean(band_col)),
        h0_mean=float(np.nanmean(h0_col)),
        median_ratio=float(np.nanmedian(ratio)),
        mean_abs_relative_difference=float(np.nanmean(rel)),
    )


def _lfl_sw_wavenumber_interval(band_index: int) -> tuple[float, float]:
    left = 1.0e4 / float(LFL_SW_EDGES_UM[band_index - 1])
    right = 1.0e4 / float(LFL_SW_EDGES_UM[band_index])
    return (min(left, right), max(left, right))


def lfl_visible_overlap_weights() -> list[tuple[str, float]]:
    cam_low, cam_high = sorted((CAM_VISIBLE_LOW_CM, CAM_VISIBLE_HIGH_CM))
    denominator = cam_high - cam_low
    weights: list[tuple[str, float]] = []
    for band_index in range(1, len(LFL_SW_EDGES_UM)):
        band_low, band_high = _lfl_sw_wavenumber_interval(band_index)
        overlap = max(0.0, min(cam_high, band_high) - max(cam_low, band_low))
        if overlap > 0.0:
            weights.append((f"SW{band_index:02d}", overlap / denominator))
    if not weights:
        raise ValueError("CAM visible band has no overlap with LFL SW bands")
    return weights


def lfl_visible_overlap_column(sp3_dir: Path, stamps: Iterable[str] | None = None) -> tuple[np.ndarray, list[tuple[str, float]]]:
    weights = lfl_visible_overlap_weights()
    combined: np.ndarray | None = None
    for band, weight in weights:
        ds = load_band_mean(sp3_dir, band, stamps)
        column = np.asarray(ds[COL], dtype=float) * float(weight)
        combined = column if combined is None else combined + column
    if combined is None:
        raise ValueError("no LFL visible overlap columns were loaded")
    return combined, weights


def compare_lfl_visible_to_h0(
    sp3_dir: Path,
    h0_file: Path,
    *,
    h0_variable: str = "AODVISdn",
    stamp: str | None = None,
) -> AodComparison:
    first_band = lfl_visible_overlap_weights()[0][0]
    stamps = selected_single_stamp(sp3_dir, first_band, stamp, label=CAM_VISIBLE_BAND)
    column, _ = lfl_visible_overlap_column(sp3_dir, stamps)
    with xr.open_dataset(h0_file) as ds:
        h0_values = h0_values_for_stamp(ds, h0_variable, stamps[0])
    h0_col, band_col = finite_pair(h0_values, column)
    if h0_col.size == 0:
        raise ValueError(f"{CAM_VISIBLE_BAND}: no finite nonzero cells for {h0_variable} comparison")
    ratio = band_col / h0_col
    rel = np.abs(band_col - h0_col) / np.abs(h0_col)
    return AodComparison(
        band=CAM_VISIBLE_BAND,
        h0_variable=h0_variable,
        stamp_count=1,
        stamps=stamps[0],
        count=int(band_col.size),
        band_column_mean=float(np.nanmean(band_col)),
        h0_mean=float(np.nanmean(h0_col)),
        median_ratio=float(np.nanmedian(ratio)),
        mean_abs_relative_difference=float(np.nanmean(rel)),
    )


def compare_lfl_visible_to_h0_files(
    sp3_dir: Path,
    h0_files: Iterable[Path],
    *,
    h0_variable: str = "AODVISdn",
    expected_stamp_count: int | None = None,
    expected_stamps: Iterable[str] | None = None,
) -> AodComparison:
    h0_values_all: list[np.ndarray] = []
    sp3_values_all: list[np.ndarray] = []
    contributing_stamps: list[str] = []
    expected_stamp_set = set(expected_stamps or ())
    for h0_file in h0_files:
        with xr.open_dataset(h0_file) as ds:
            for stamp in h0_stamps(ds, h0_variable):
                if stamp in contributing_stamps:
                    raise ValueError(f"{CAM_VISIBLE_BAND}: duplicate h0 stamp {stamp}")
                column, _ = lfl_visible_overlap_column(sp3_dir, [stamp])
                h0_values = h0_values_for_stamp(ds, h0_variable, stamp)
                h0_col, band_col = finite_pair(h0_values, column)
                if not h0_col.size:
                    raise ValueError(f"{CAM_VISIBLE_BAND}: no finite nonzero cells for {h0_variable} comparison at {stamp}")
                h0_values_all.append(h0_col)
                sp3_values_all.append(band_col)
                contributing_stamps.append(stamp)
    if not h0_values_all:
        raise ValueError(f"{CAM_VISIBLE_BAND}: no finite nonzero cells for {h0_variable} comparison")
    if expected_stamp_count is not None and len(contributing_stamps) != int(expected_stamp_count):
        raise ValueError(
            f"{CAM_VISIBLE_BAND}: expected {expected_stamp_count} h0 stamp(s), found {len(contributing_stamps)}"
        )
    if expected_stamp_set and set(contributing_stamps) != expected_stamp_set:
        missing = " ".join(sorted(expected_stamp_set.difference(contributing_stamps)))
        extra = " ".join(sorted(set(contributing_stamps).difference(expected_stamp_set)))
        raise ValueError(f"{CAM_VISIBLE_BAND}: h0 stamp set mismatch; missing={missing!r} extra={extra!r}")
    h0_col = np.concatenate(h0_values_all)
    band_col = np.concatenate(sp3_values_all)
    ratio = band_col / h0_col
    rel = np.abs(band_col - h0_col) / np.abs(h0_col)
    return AodComparison(
        band=CAM_VISIBLE_BAND,
        h0_variable=h0_variable,
        stamp_count=len(contributing_stamps),
        stamps=" ".join(contributing_stamps),
        count=int(band_col.size),
        band_column_mean=float(np.nanmean(band_col)),
        h0_mean=float(np.nanmean(h0_col)),
        median_ratio=float(np.nanmedian(ratio)),
        mean_abs_relative_difference=float(np.nanmean(rel)),
    )


def compare_band_to_h0_files(
    sp3_dir: Path,
    h0_files: Iterable[Path],
    *,
    band: str = VISIBLE_BAND,
    h0_variable: str = "AODVISdn",
    expected_stamp_count: int | None = None,
    expected_stamps: Iterable[str] | None = None,
) -> AodComparison:
    normalized = normalize_band(band)
    h0_values_all: list[np.ndarray] = []
    sp3_values_all: list[np.ndarray] = []
    contributing_stamps: list[str] = []
    expected_stamp_set = set(expected_stamps or ())
    for h0_file in h0_files:
        with xr.open_dataset(h0_file) as ds:
            for stamp in h0_stamps(ds, h0_variable):
                if stamp in contributing_stamps:
                    raise ValueError(f"{normalized}: duplicate h0 stamp {stamp}")
                sp3_ds = load_band_mean(sp3_dir, normalized, [stamp])
                h0_values = h0_values_for_stamp(ds, h0_variable, stamp)
                h0_col, band_col = finite_pair(h0_values, np.asarray(sp3_ds[COL], dtype=float))
                if not h0_col.size:
                    raise ValueError(f"{normalized}: no finite nonzero cells for {h0_variable} comparison at {stamp}")
                h0_values_all.append(h0_col)
                sp3_values_all.append(band_col)
                contributing_stamps.append(stamp)
    if not h0_values_all:
        raise ValueError(f"{normalized}: no finite nonzero cells for {h0_variable} comparison")
    if expected_stamp_count is not None and len(contributing_stamps) != int(expected_stamp_count):
        raise ValueError(f"{normalized}: expected {expected_stamp_count} h0 stamp(s), found {len(contributing_stamps)}")
    if expected_stamp_set and set(contributing_stamps) != expected_stamp_set:
        missing = " ".join(sorted(expected_stamp_set.difference(contributing_stamps)))
        extra = " ".join(sorted(set(contributing_stamps).difference(expected_stamp_set)))
        raise ValueError(f"{normalized}: h0 stamp set mismatch; missing={missing!r} extra={extra!r}")
    h0_col = np.concatenate(h0_values_all)
    band_col = np.concatenate(sp3_values_all)
    ratio = band_col / h0_col
    rel = np.abs(band_col - h0_col) / np.abs(h0_col)
    return AodComparison(
        band=normalized,
        h0_variable=h0_variable,
        stamp_count=len(contributing_stamps),
        stamps=" ".join(contributing_stamps),
        count=int(band_col.size),
        band_column_mean=float(np.nanmean(band_col)),
        h0_mean=float(np.nanmean(h0_col)),
        median_ratio=float(np.nanmedian(ratio)),
        mean_abs_relative_difference=float(np.nanmean(rel)),
    )


def write_comparison_outputs(
    outdir: Path,
    band_metrics: list[BandComparison],
    *,
    aod_comparison: AodComparison | None = None,
    aod_comparisons: Iterable[AodComparison] | None = None,
) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "sp3v2_method_comparison_summary.csv"
    json_path = outdir / "sp3v2_method_comparison_summary.json"
    aod_rows = [asdict(item) for item in (aod_comparisons or ([] if aod_comparison is None else [aod_comparison]))]
    rows = [asdict(metric) for metric in band_metrics]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else list(BandComparison.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(rows)
    if aod_rows:
        aod_csv_path = outdir / "sp3v2_aod_comparison_summary.csv"
        with aod_csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(aod_rows[0]))
            writer.writeheader()
            writer.writerows(aod_rows)
    payload = {
        "band_metrics": rows,
        "aod_comparison": asdict(aod_comparison) if aod_comparison is not None else (aod_rows[0] if aod_rows else None),
        "aod_comparisons": aod_rows,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remap-dir", required=True, type=Path)
    parser.add_argument("--lut-dir", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--bands", nargs="*", default=list(DEFAULT_BANDS), help="SP3 bands to compare; default all")
    parser.add_argument("--h0-file", type=Path, help="optional CAM h0/h0i file for visible-band AOD comparison")
    parser.add_argument("--h0-files", nargs="+", type=Path, help="optional CAM h0/h0i files for aggregate visible-band AOD comparison")
    parser.add_argument("--h0-variable", default="AODVISdn")
    parser.add_argument("--h0-band", default=VISIBLE_BAND)
    parser.add_argument("--h0-stamp", help="SP3 stamp to compare against the single h0 record, e.g. 20080701.10800")
    parser.add_argument("--expected-h0-stamp-count", type=int, help="require this many h0 records in aggregate AOD comparisons")
    parser.add_argument("--expected-h0-stamps", nargs="+", help="require these exact h0 stamps in aggregate AOD comparisons")
    parser.add_argument(
        "--h0-visible-overlap",
        action="store_true",
        help="compare LFL SW bands remapped onto CAM visible band instead of one SP3 band",
    )
    parser.add_argument(
        "--h0-include-raw-band",
        action="store_true",
        help="when using --h0-files --h0-visible-overlap, also write the raw --h0-band comparison",
    )
    args = parser.parse_args(argv)

    bands = DEFAULT_BANDS if args.bands == ["all"] else tuple(normalize_band(band) for band in args.bands)
    band_metrics = compare_directories(args.remap_dir, args.lut_dir, bands=bands)
    aod = None
    aod_comparisons: list[AodComparison] = []
    if args.h0_file is not None and args.h0_files:
        parser.error("--h0-file and --h0-files are mutually exclusive")
    if args.expected_h0_stamp_count is not None and not args.h0_files:
        parser.error("--expected-h0-stamp-count requires --h0-files")
    if args.expected_h0_stamps and not args.h0_files:
        parser.error("--expected-h0-stamps requires --h0-files")
    if args.expected_h0_stamp_count is not None and args.expected_h0_stamp_count <= 0:
        parser.error("--expected-h0-stamp-count must be positive")
    if args.h0_files:
        if not args.h0_visible_overlap:
            parser.error("--h0-files requires --h0-visible-overlap")
        if args.h0_include_raw_band:
            aod_comparisons.append(
                compare_band_to_h0_files(
                    args.lut_dir,
                    args.h0_files,
                    band=args.h0_band,
                    h0_variable=args.h0_variable,
                    expected_stamp_count=args.expected_h0_stamp_count,
                    expected_stamps=args.expected_h0_stamps,
                )
            )
        aod_comparisons.append(
            compare_lfl_visible_to_h0_files(
                args.lut_dir,
                args.h0_files,
                h0_variable=args.h0_variable,
                expected_stamp_count=args.expected_h0_stamp_count,
                expected_stamps=args.expected_h0_stamps,
            )
        )
        aod = aod_comparisons[-1]
    elif args.h0_file is not None:
        if args.h0_include_raw_band:
            parser.error("--h0-include-raw-band is only supported with --h0-files --h0-visible-overlap")
        if args.h0_visible_overlap:
            aod = compare_lfl_visible_to_h0(
                args.lut_dir,
                args.h0_file,
                h0_variable=args.h0_variable,
                stamp=args.h0_stamp,
            )
        else:
            aod = compare_band_to_h0(
                args.lut_dir,
                args.h0_file,
                band=args.h0_band,
                h0_variable=args.h0_variable,
                stamp=args.h0_stamp,
            )
        aod_comparisons = [aod]
    elif args.h0_include_raw_band:
        parser.error("--h0-include-raw-band requires --h0-files --h0-visible-overlap")
    csv_path, json_path = write_comparison_outputs(
        args.outdir,
        band_metrics,
        aod_comparison=aod,
        aod_comparisons=aod_comparisons,
    )
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    for metric in band_metrics:
        print(
            f"{metric.band}: ratio={metric.median_ratio:.6g} "
            f"median_abs_rel={metric.median_abs_relative_difference:.6g} "
            f"mean_abs_rel={metric.mean_abs_relative_difference:.6g} "
            f"ssa_delta={metric.median_ssa_difference:.6g} "
            f"g_delta={metric.median_asymmetry_difference:.6g}"
        )
    for aod_metric in aod_comparisons:
        print(
            f"{aod_metric.band} vs {aod_metric.h0_variable}: ratio={aod_metric.median_ratio:.6g} "
            f"mean_abs_rel={aod_metric.mean_abs_relative_difference:.6g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
