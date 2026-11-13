#!/usr/bin/env python
"""Check SP3 per-band output completeness and physical invariants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np
import xarray as xr

EXT = "Extinction_Layer_Optical_Depth"
SCA = "Scattering_Layer_Optical_Depth"
ASM = "Layer_Asymmetry_Parameter"
COL = "Extinction_Column_Optical_Depth"
REQUIRED_VARIABLES = ("DELP", EXT, SCA, ASM, COL)
DEFAULT_BANDS = tuple(f"SW{i:02d}" for i in range(1, 15)) + tuple(f"LW{i:02d}" for i in range(1, 13))


@dataclass(frozen=True)
class Sp3DirectorySummary:
    file_count: int
    group_count: int
    incomplete_groups: dict[str, tuple[str, ...]]
    interval_errors: list[str]
    first_stamp: str | None
    last_stamp: str | None


def parse_sp3_name(path: Path) -> tuple[str, str]:
    parts = path.name.split(".")
    if len(parts) != 4 or parts[-1] != "nc":
        raise ValueError(f"not an SP3 filename: {path.name}")
    band = parts[0].split("_")[-1].upper()
    return band, f"{parts[1]}.{parts[2]}"


def stamp_to_datetime(stamp: str) -> datetime:
    date_text, seconds_text = stamp.split(".")
    return datetime.strptime(date_text, "%Y%m%d") + timedelta(seconds=int(seconds_text))


def summarize_directory(
    indir: Path,
    *,
    expected_bands: Iterable[str] = DEFAULT_BANDS,
    interval_seconds: int = 10800,
) -> Sp3DirectorySummary:
    expected = tuple(band.upper() for band in expected_bands)
    groups: dict[str, set[str]] = {}
    files = sorted(indir.glob("AER_MAM4_*.nc"))
    for path in files:
        band, stamp = parse_sp3_name(path)
        groups.setdefault(stamp, set()).add(band)

    incomplete = {
        stamp: tuple(band for band in expected if band not in bands)
        for stamp, bands in groups.items()
        if any(band not in bands for band in expected)
    }

    stamps = sorted(groups, key=stamp_to_datetime)
    interval_errors = []
    for prev, current in zip(stamps, stamps[1:]):
        delta = (stamp_to_datetime(current) - stamp_to_datetime(prev)).total_seconds()
        if int(delta) != interval_seconds:
            interval_errors.append(f"{prev} -> {current}: {int(delta)} seconds")

    return Sp3DirectorySummary(
        file_count=len(files),
        group_count=len(groups),
        incomplete_groups=incomplete,
        interval_errors=interval_errors,
        first_stamp=stamps[0] if stamps else None,
        last_stamp=stamps[-1] if stamps else None,
    )


def check_physical_invariants(indir: Path, *, tol: float = 1.0e-8) -> dict[str, float]:
    files = sorted(indir.glob("AER_MAM4_*.nc"))
    if not files:
        raise AssertionError(f"no SP3 files found under {indir}")

    max_ext = 0.0
    max_sca = 0.0
    max_sca_minus_ext = -np.inf
    max_abs_asm = 0.0
    for path in files:
        with xr.open_dataset(path) as ds:
            for name in REQUIRED_VARIABLES:
                if name not in ds:
                    raise AssertionError(f"{path.name}: missing {name}")
                values = np.asarray(ds[name].values, dtype=float)
                if not np.all(np.isfinite(values)):
                    raise AssertionError(f"{path.name}: {name} contains non-finite values")

            ext = np.asarray(ds[EXT].values, dtype=float)
            sca = np.asarray(ds[SCA].values, dtype=float)
            asm = np.asarray(ds[ASM].values, dtype=float)
            col = np.asarray(ds[COL].values, dtype=float)

            if np.any(ext < -tol):
                raise AssertionError(f"{path.name}: extinction must be nonnegative")
            if np.any(sca < -tol):
                raise AssertionError(f"{path.name}: scattering must be nonnegative")
            if np.any(sca > ext + tol):
                raise AssertionError(f"{path.name}: expected sca <= ext")
            if np.any(np.abs(asm) > 1.0 + tol):
                raise AssertionError(f"{path.name}: asymmetry must be within [-1, 1]")
            if not np.allclose(col, ext.sum(axis=0), rtol=1.0e-5, atol=1.0e-7):
                raise AssertionError(f"{path.name}: column extinction does not match layer sum")

            max_ext = max(max_ext, float(np.max(ext)))
            max_sca = max(max_sca, float(np.max(sca)))
            max_sca_minus_ext = max(max_sca_minus_ext, float(np.max(sca - ext)))
            max_abs_asm = max(max_abs_asm, float(np.max(np.abs(asm))))

    return {
        "file_count": float(len(files)),
        "max_ext": max_ext,
        "max_sca": max_sca,
        "max_sca_minus_ext": max_sca_minus_ext,
        "max_abs_asm": max_abs_asm,
    }
