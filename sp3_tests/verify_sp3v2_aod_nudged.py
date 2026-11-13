#!/usr/bin/env python3
"""Summarize and gate SP3v2 T10 AOD-nudged diagnostics."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sp3_tests.compare_sp3_methods import COL
from sp3_tests.compare_sp3_methods import VISIBLE_BAND
from sp3_tests.compare_sp3_methods import band_files_by_stamp
from sp3_tests.compare_sp3_methods import h0_stamps
from sp3_tests.compare_sp3_methods import h0_values_for_stamp

FIRST_GUESS = "AODNDG_MODEL_PRE"
ANALYZED = "AODNDG_MODEL_POST"
NUDGE_MASK = "AODNDG_MASK"
OUTPUT_STEM = "sp3v2_t10_aod_nudged_diagnostics_summary"
DEFAULT_EXPECTED_METHOD = "lut"


def attr_is_true(value: Any) -> bool:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value) != 0
    if isinstance(value, (float, np.floating)):
        return bool(np.isfinite(value) and float(value) != 0.0)
    if isinstance(value, str):
        normalized = value.strip().lower().strip(".")
        return normalized in {"1", "t", "true", "y", "yes", "on"}
    return False


def parse_stamp_date(stamp: str) -> str:
    return stamp.split(".", 1)[0].replace("-", "")


def selected_stamps(
    nudged_sp3_dir: Path,
    free_sp3_dir: Path,
    *,
    stamps: Iterable[str] | None = None,
    dates: Iterable[str] | None = None,
    expected_count: int | None = None,
    expected_first_stamp: str | None = None,
    expected_last_stamp: str | None = None,
) -> list[str]:
    nudged = band_files_by_stamp(nudged_sp3_dir, VISIBLE_BAND)
    free = band_files_by_stamp(free_sp3_dir, VISIBLE_BAND)
    selected = sorted(set(nudged).intersection(free))
    wanted_stamps = set(stamps or ())
    if wanted_stamps:
        selected = [stamp for stamp in selected if stamp in wanted_stamps]
        missing = sorted(wanted_stamps.difference(selected))
        if missing:
            raise FileNotFoundError(f"missing common {VISIBLE_BAND} SP3 files for stamp(s): {', '.join(missing)}")
    wanted_dates = {date.replace("-", "") for date in (dates or ())}
    if wanted_dates:
        selected = [stamp for stamp in selected if parse_stamp_date(stamp) in wanted_dates]
    if not selected:
        raise FileNotFoundError(f"no common {VISIBLE_BAND} SP3 stamps selected")
    if expected_count is not None and len(selected) != int(expected_count):
        raise ValueError(f"expected {expected_count} common {VISIBLE_BAND} stamp(s), found {len(selected)}")
    if expected_first_stamp is not None and selected[0] != expected_first_stamp:
        raise ValueError(f"expected first {VISIBLE_BAND} stamp {expected_first_stamp}, found {selected[0]}")
    if expected_last_stamp is not None and selected[-1] != expected_last_stamp:
        raise ValueError(f"expected last {VISIBLE_BAND} stamp {expected_last_stamp}, found {selected[-1]}")
    return selected


def read_sp3_column(path: Path, *, expected_nudged: bool, expected_method: str | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with xr.open_dataset(path) as ds:
        if COL not in ds:
            raise ValueError(f"{path}: missing required field {COL}")
        actual_nudged = attr_is_true(ds.attrs.get("nudged"))
        if expected_nudged and not actual_nudged:
            raise ValueError(f"{path.name}: nudged SP3 file must have global nudged attr true/1")
        if not expected_nudged and actual_nudged:
            raise ValueError(f"{path.name}: free/control SP3 file must not be nudged")
        if expected_method is not None:
            actual_method = str(ds.attrs.get("method", "")).strip().lower()
            if actual_method != expected_method.strip().lower():
                raise ValueError(f"{path.name}: expected SP3 method={expected_method!r}, found {actual_method!r}")
        missing_coords = [name for name in ("lat", "lon") if name not in ds]
        if missing_coords:
            raise ValueError(f"{path}: missing required coordinate(s): {', '.join(missing_coords)}")
        data = np.asarray(ds[COL], dtype=np.float64)
        lat = np.asarray(ds["lat"], dtype=np.float64)
        lon = np.asarray(ds["lon"], dtype=np.float64)
    return data, lat, lon


def verify_same_grid(label: str, data: np.ndarray, lat: np.ndarray, lon: np.ndarray, ref: dict[str, np.ndarray]) -> None:
    if data.shape != tuple(ref["shape"]):
        raise ValueError(f"{label}: grid shape {data.shape} does not match {tuple(ref['shape'])}")
    if lat.shape != ref["lat"].shape:
        raise ValueError(f"{label}: latitude shape {lat.shape} does not match nudged SP3 latitude shape {ref['lat'].shape}")
    if lon.shape != ref["lon"].shape:
        raise ValueError(f"{label}: longitude shape {lon.shape} does not match nudged SP3 longitude shape {ref['lon'].shape}")
    if not np.allclose(lat, ref["lat"], rtol=0.0, atol=1.0e-10):
        raise ValueError(f"{label}: latitude grid does not match nudged SP3 grid")
    if not np.allclose(lon, ref["lon"], rtol=0.0, atol=1.0e-10):
        raise ValueError(f"{label}: longitude grid does not match nudged SP3 grid")


def require_h0_fields(ds: xr.Dataset, path: Path) -> None:
    for variable in (FIRST_GUESS, ANALYZED, NUDGE_MASK):
        if variable not in ds:
            raise ValueError(f"{path}: missing required field {variable}")


def build_h0_index(h0_files: Iterable[Path], selected: list[str]) -> dict[str, Path]:
    index: dict[str, Path] = {}
    h0_files = list(h0_files)
    for path in h0_files:
        with xr.open_dataset(path) as ds:
            require_h0_fields(ds, path)
            if "time" in ds[FIRST_GUESS].dims:
                stamps = h0_stamps(ds, FIRST_GUESS)
                for variable in (ANALYZED, NUDGE_MASK):
                    variable_stamps = h0_stamps(ds, variable)
                    if stamps != variable_stamps:
                        raise ValueError(f"{path}: {FIRST_GUESS} and {variable} time axes do not match")
            elif len(h0_files) == 1 and len(selected) == 1:
                stamps = [selected[0]]
            else:
                raise ValueError(f"{path}: h0 fields have no time axis; select exactly one --stamp")
        for stamp in stamps:
            if stamp not in selected:
                continue
            if stamp in index:
                raise ValueError(f"multiple h0 files provide stamp {stamp}: {index[stamp]} and {path}")
            index[stamp] = path
    missing = [stamp for stamp in selected if stamp not in index]
    if missing:
        raise FileNotFoundError(f"missing h0/h0i records for selected stamp(s): {', '.join(missing)}")
    return index


def h0_grid(ds: xr.Dataset) -> tuple[np.ndarray, np.ndarray] | None:
    if "lat" not in ds or "lon" not in ds:
        return None
    return np.asarray(ds["lat"], dtype=np.float64), np.asarray(ds["lon"], dtype=np.float64)


def read_h0_fields(path: Path, stamp: str, shape: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[np.ndarray, np.ndarray] | None]:
    with xr.open_dataset(path) as ds:
        require_h0_fields(ds, path)
        if "time" in ds[FIRST_GUESS].dims:
            first_guess = h0_values_for_stamp(ds, FIRST_GUESS, stamp)
            analyzed = h0_values_for_stamp(ds, ANALYZED, stamp)
            nudge_mask = h0_values_for_stamp(ds, NUDGE_MASK, stamp)
        else:
            first_guess = np.asarray(ds[FIRST_GUESS], dtype=np.float64)
            analyzed = np.asarray(ds[ANALYZED], dtype=np.float64)
            nudge_mask = np.asarray(ds[NUDGE_MASK], dtype=np.float64)
        grid = h0_grid(ds)
        first_guess = np.asarray(first_guess, dtype=np.float64)
        analyzed = np.asarray(analyzed, dtype=np.float64)
        nudge_mask = np.asarray(nudge_mask, dtype=np.float64)
    if first_guess.shape != shape:
        raise ValueError(f"{path}: {FIRST_GUESS} shape {first_guess.shape} does not match SP3 grid {shape}")
    if analyzed.shape != shape:
        raise ValueError(f"{path}: {ANALYZED} shape {analyzed.shape} does not match SP3 grid {shape}")
    if nudge_mask.shape != shape:
        raise ValueError(f"{path}: {NUDGE_MASK} shape {nudge_mask.shape} does not match SP3 grid {shape}")
    return first_guess, analyzed, nudge_mask, grid


def finite_count(data: np.ndarray) -> int:
    return int(np.isfinite(np.asarray(data, dtype=np.float64)).sum())


def finite_all(data: np.ndarray) -> bool:
    return bool(np.isfinite(np.asarray(data, dtype=np.float64)).all())


def mean_or_nan(data: np.ndarray, mask: np.ndarray | None = None) -> float:
    values = np.asarray(data, dtype=np.float64)
    if mask is not None:
        values = values[mask]
    finite = values[np.isfinite(values)]
    return float(np.nanmean(finite)) if finite.size else float("nan")


def correlation_or_nan(left: np.ndarray, right: np.ndarray, mask: np.ndarray) -> float:
    x = np.asarray(left, dtype=np.float64)[mask]
    y = np.asarray(right, dtype=np.float64)[mask]
    if x.size < 2 or np.nanstd(x) == 0.0 or np.nanstd(y) == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def metric_row(
    record: str,
    first_guess: np.ndarray,
    analyzed: np.ndarray,
    sp3_delta: np.ndarray,
    nudge_mask: np.ndarray,
) -> dict[str, Any]:
    analysis_increment = analyzed - first_guess
    active = np.asarray(nudge_mask, dtype=np.float64) > 0.5
    valid = active & np.isfinite(analysis_increment) & np.isfinite(sp3_delta)
    return {
        "record": record,
        "valid_sample_count": int(valid.sum()),
        "active_nudged_sample_count": int(active.sum()),
        "active_nudged_fraction": mean_or_nan(active.astype(np.float64)),
        "first_guess_finite_count": finite_count(first_guess),
        "analyzed_finite_count": finite_count(analyzed),
        "nudge_mask_finite_count": finite_count(nudge_mask),
        "analysis_increment_finite_count": finite_count(analysis_increment),
        "sp3_sw05_nudged_minus_free_finite_count": finite_count(sp3_delta),
        "first_guess_all_finite": finite_all(first_guess),
        "analyzed_all_finite": finite_all(analyzed),
        "nudge_mask_all_finite": finite_all(nudge_mask),
        "analysis_increment_all_finite": finite_all(analysis_increment),
        "sp3_sw05_nudged_minus_free_all_finite": finite_all(sp3_delta),
        "first_guess_mean": mean_or_nan(first_guess),
        "analyzed_mean": mean_or_nan(analyzed),
        "analysis_increment_mean": mean_or_nan(analysis_increment, valid),
        "analysis_increment_abs_mean": mean_or_nan(np.abs(analysis_increment), valid),
        "sp3_sw05_nudged_minus_free_mean": mean_or_nan(sp3_delta, valid),
        "sp3_sw05_nudged_minus_free_abs_mean": mean_or_nan(np.abs(sp3_delta), valid),
        "coherence_correlation": correlation_or_nan(analysis_increment, sp3_delta, valid),
    }


def aggregate_field(values: list[np.ndarray]) -> np.ndarray:
    if not values:
        raise ValueError("no fields to aggregate")
    if len(values) == 1:
        return values[0].copy()
    return np.nanmean(np.stack(values, axis=0), axis=0)


def compute_diagnostics(
    nudged_sp3_dir: Path,
    free_sp3_dir: Path,
    nudged_h0_files: Iterable[Path],
    *,
    stamps: Iterable[str] | None = None,
    dates: Iterable[str] | None = None,
    expected_method: str | None = DEFAULT_EXPECTED_METHOD,
    expected_stamp_count: int | None = None,
    expected_first_stamp: str | None = None,
    expected_last_stamp: str | None = None,
) -> dict[str, Any]:
    selected = selected_stamps(
        nudged_sp3_dir,
        free_sp3_dir,
        stamps=stamps,
        dates=dates,
        expected_count=expected_stamp_count,
        expected_first_stamp=expected_first_stamp,
        expected_last_stamp=expected_last_stamp,
    )
    h0_index = build_h0_index(nudged_h0_files, selected)
    nudged_files = band_files_by_stamp(nudged_sp3_dir, VISIBLE_BAND)
    free_files = band_files_by_stamp(free_sp3_dir, VISIBLE_BAND)

    rows: list[dict[str, Any]] = []
    first_guess_fields: list[np.ndarray] = []
    analyzed_fields: list[np.ndarray] = []
    mask_fields: list[np.ndarray] = []
    increment_fields: list[np.ndarray] = []
    delta_fields: list[np.ndarray] = []
    grid: dict[str, np.ndarray] | None = None

    for stamp in selected:
        nudged_col, lat, lon = read_sp3_column(
            nudged_files[stamp],
            expected_nudged=True,
            expected_method=expected_method,
        )
        if grid is None:
            grid = {"lat": lat, "lon": lon, "shape": tuple(nudged_col.shape)}
        else:
            verify_same_grid(f"nudged SP3 {stamp}", nudged_col, lat, lon, grid)
        free_col, free_lat, free_lon = read_sp3_column(
            free_files[stamp],
            expected_nudged=False,
            expected_method=expected_method,
        )
        verify_same_grid(f"free/control SP3 {stamp}", free_col, free_lat, free_lon, grid)
        first_guess, analyzed, nudge_mask, h0_coord_grid = read_h0_fields(h0_index[stamp], stamp, nudged_col.shape)
        if h0_coord_grid is not None:
            h0_lat, h0_lon = h0_coord_grid
            verify_same_grid(f"h0/h0i {stamp}", first_guess, h0_lat, h0_lon, grid)
        sp3_delta = nudged_col - free_col
        analysis_increment = analyzed - first_guess

        rows.append(metric_row(stamp, first_guess, analyzed, sp3_delta, nudge_mask))
        first_guess_fields.append(first_guess)
        analyzed_fields.append(analyzed)
        mask_fields.append(nudge_mask)
        increment_fields.append(analysis_increment)
        delta_fields.append(sp3_delta)

    first_guess_all = np.concatenate([field.ravel() for field in first_guess_fields])
    analyzed_all = np.concatenate([field.ravel() for field in analyzed_fields])
    mask_all = np.concatenate([field.ravel() for field in mask_fields])
    delta_all = np.concatenate([field.ravel() for field in delta_fields])
    aggregate = metric_row("aggregate", first_guess_all, analyzed_all, delta_all, mask_all)
    aggregate["stamp_count"] = len(selected)

    if grid is None:
        raise FileNotFoundError("no selected diagnostics were loaded")
    fields = {
        "first_guess": {
            "title": "CAM First-Guess AOD",
            "data": aggregate_field(first_guess_fields),
            "style_preset": "geosit_aod",
        },
        "analyzed": {
            "title": "CAM Analyzed AOD",
            "data": aggregate_field(analyzed_fields),
            "style_preset": "geosit_aod",
        },
        "analysis_increment": {
            "title": "CAM AOD Analysis Increment",
            "data": aggregate_field(increment_fields),
            "cmap": "RdBu_r",
        },
        "sp3_sw05_nudged_minus_free": {
            "title": "SP3 SW05 Nudged Minus Free AOD",
            "data": aggregate_field(delta_fields),
            "cmap": "RdBu_r",
        },
        "nudge_fraction": {
            "title": "AOD Nudge Fraction",
            "data": aggregate_field(mask_fields),
            "cmap": "viridis",
            "vmin": 0.0,
            "vmax": 1.0,
        },
    }

    return {
        "selected_stamps": selected,
        "visible_band": VISIBLE_BAND,
        "expected_method": expected_method,
        "sp3_field": COL,
        "h0_fields": {
            "first_guess": FIRST_GUESS,
            "analyzed": ANALYZED,
            "analysis_increment": f"{ANALYZED} - {FIRST_GUESS}",
            "nudge_mask": NUDGE_MASK,
        },
        "per_stamp": rows,
        "aggregate": aggregate,
        "fields": fields,
        "grid": {"lat": grid["lat"], "lon": grid["lon"]},
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        finite = value[np.isfinite(value)]
        return {
            "shape": list(value.shape),
            "finite_count": int(finite.size),
            "mean": float(np.nanmean(finite)) if finite.size else None,
            "min": float(np.nanmin(finite)) if finite.size else None,
            "max": float(np.nanmax(finite)) if finite.size else None,
        }
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def write_outputs(outdir: Path, diagnostics: dict[str, Any]) -> tuple[Path, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / f"{OUTPUT_STEM}.csv"
    json_path = outdir / f"{OUTPUT_STEM}.json"
    rows = list(diagnostics["per_stamp"]) + [diagnostics["aggregate"]]
    fieldnames = list(rows[0])
    for row in rows[1:]:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if isinstance(value, float) and not np.isfinite(value) else value for key, value in row.items()})
    json_path.write_text(json.dumps(json_safe(diagnostics), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return csv_path, json_path


def diagnostic_gate_failures(diagnostics: dict[str, Any]) -> list[str]:
    aggregate = diagnostics["aggregate"]
    failures: list[str] = []
    if int(aggregate["valid_sample_count"]) <= 0:
        failures.append("no active finite AODNDG/SP3 samples")
    if int(aggregate["active_nudged_sample_count"]) <= 0:
        failures.append("AODNDG_MASK has no active nudged cells")
    correlation = aggregate["coherence_correlation"]
    if not isinstance(correlation, (int, float, np.floating)) or not np.isfinite(float(correlation)):
        failures.append("coherence_correlation is not finite")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nudged-sp3-dir", required=True, type=Path)
    parser.add_argument("--free-sp3-dir", required=True, type=Path)
    parser.add_argument("--nudged-h0-files", required=True, nargs="+", type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--stamp", dest="stamps", action="append", help="SP3/h0 stamp to include, e.g. 20080701.10800")
    parser.add_argument("--date", dest="dates", action="append", help="date to include, e.g. 20080701 or 2008-07-01")
    parser.add_argument("--expected-method", default=DEFAULT_EXPECTED_METHOD, help="required SP3 global method attr; use 'any' to skip")
    parser.add_argument("--expected-stamp-count", type=int, help="require this many common SP3 SW05 stamps")
    parser.add_argument("--expected-first-stamp", help="require this first common SP3 SW05 stamp")
    parser.add_argument("--expected-last-stamp", help="require this last common SP3 SW05 stamp")
    args = parser.parse_args(argv)

    diagnostics = compute_diagnostics(
        args.nudged_sp3_dir,
        args.free_sp3_dir,
        args.nudged_h0_files,
        stamps=args.stamps,
        dates=args.dates,
        expected_method=None if args.expected_method.lower() == "any" else args.expected_method,
        expected_stamp_count=args.expected_stamp_count,
        expected_first_stamp=args.expected_first_stamp,
        expected_last_stamp=args.expected_last_stamp,
    )
    csv_path, json_path = write_outputs(args.outdir, diagnostics)
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    aggregate = diagnostics["aggregate"]
    print(
        "aggregate: "
        f"n={aggregate['valid_sample_count']} "
        f"analysis_increment_mean={aggregate['analysis_increment_mean']:.6g} "
        f"sp3_sw05_nudged_minus_free_mean={aggregate['sp3_sw05_nudged_minus_free_mean']:.6g} "
        f"coherence_correlation={aggregate['coherence_correlation']:.6g}"
    )
    failures = diagnostic_gate_failures(diagnostics)
    if failures:
        print("AOD-nudged diagnostic gate failed: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
