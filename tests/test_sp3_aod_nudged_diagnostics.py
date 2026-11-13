from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr


def _write_sp3_sw05(
    path: Path,
    values: np.ndarray,
    *,
    nudged: object | None = None,
    method: object | None = "lut",
) -> None:
    attrs = {}
    if nudged is not None:
        attrs["nudged"] = nudged
    if method is not None:
        attrs["method"] = method
    data = np.asarray(values, dtype=np.float32)
    ds = xr.Dataset(
        {"Extinction_Column_Optical_Depth": (("lat", "lon"), data)},
        coords={
            "lat": np.asarray([-1.0, 1.0], dtype=np.float32),
            "lon": np.asarray([0.0, 120.0, 240.0], dtype=np.float32),
        },
        attrs=attrs,
    )
    ds.to_netcdf(path)


def _write_h0(
    path: Path,
    first_guess: np.ndarray,
    analyzed: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    lat: np.ndarray | None = None,
    lon: np.ndarray | None = None,
    date: int = 20080701,
    datesec: int = 10800,
) -> None:
    first_guess_data = np.asarray(first_guess, dtype=np.float32)
    analyzed_data = np.asarray(analyzed, dtype=np.float32)
    mask_data = np.ones_like(first_guess_data, dtype=np.float32) if mask is None else np.asarray(mask, dtype=np.float32)
    ds = xr.Dataset(
        {
            "AODNDG_MODEL_PRE": (("time", "lat", "lon"), first_guess_data[None, :, :]),
            "AODNDG_MODEL_POST": (("time", "lat", "lon"), analyzed_data[None, :, :]),
            "AODNDG_MASK": (("time", "lat", "lon"), mask_data[None, :, :]),
            "date": (("time",), np.asarray([date], dtype=np.int32)),
            "datesec": (("time",), np.asarray([datesec], dtype=np.int32)),
        },
        coords={
            "time": [0.0],
            "lat": np.asarray([-1.0, 1.0] if lat is None else lat, dtype=np.float32),
            "lon": np.asarray([0.0, 120.0, 240.0] if lon is None else lon, dtype=np.float32),
        },
    )
    ds.to_netcdf(path)


def test_compute_diagnostics_reports_aggregate_coherence_metrics(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3v2_aod_nudged import compute_diagnostics

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    free = np.asarray([[0.10, 0.20, 0.30], [0.40, 0.50, 0.60]], dtype=np.float32)
    sp3_delta = np.asarray([[0.02, 0.04, np.nan], [-0.01, 0.00, 0.03]], dtype=np.float32)
    first_guess = np.asarray([[0.11, 0.22, 0.33], [0.44, 0.55, 0.66]], dtype=np.float32)
    analysis_increment = sp3_delta * 0.5
    analyzed = first_guess + analysis_increment
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", free + sp3_delta, nudged=1)
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", free, nudged=0)
    h0 = tmp_path / "nudged.cam.h0i.2008-07-01-10800.nc"
    _write_h0(h0, first_guess, analyzed)

    diagnostics = compute_diagnostics(nudged_dir, free_dir, [h0], stamps=[stamp])
    aggregate = diagnostics["aggregate"]

    assert diagnostics["selected_stamps"] == [stamp]
    assert aggregate["valid_sample_count"] == 5
    assert aggregate["active_nudged_sample_count"] == 6
    assert aggregate["first_guess_finite_count"] == 6
    assert aggregate["analyzed_finite_count"] == 5
    assert aggregate["nudge_mask_finite_count"] == 6
    assert aggregate["analysis_increment_mean"] == pytest.approx(float(np.nanmean(analysis_increment)))
    assert aggregate["sp3_sw05_nudged_minus_free_mean"] == pytest.approx(float(np.nanmean(sp3_delta)))
    assert aggregate["coherence_correlation"] == pytest.approx(1.0)
    assert aggregate["analysis_increment_all_finite"] is False
    assert aggregate["sp3_sw05_nudged_minus_free_all_finite"] is False
    assert set(diagnostics["fields"]) == {
        "first_guess",
        "analyzed",
        "analysis_increment",
        "sp3_sw05_nudged_minus_free",
        "nudge_fraction",
    }


def test_compute_diagnostics_uses_aodndg_mask_for_active_cell_coherence(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3v2_aod_nudged import compute_diagnostics

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    free = np.full((2, 3), 0.2, dtype=np.float32)
    sp3_delta = np.asarray([[0.01, 0.02, 9.0], [0.03, 0.04, 9.0]], dtype=np.float32)
    first_guess = np.full((2, 3), 0.2, dtype=np.float32)
    analyzed = first_guess + np.asarray([[0.01, 0.02, -9.0], [0.03, 0.04, -9.0]], dtype=np.float32)
    mask = np.asarray([[1, 1, 0], [1, 1, 0]], dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", free + sp3_delta, nudged=1)
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", free, nudged=0)
    h0 = tmp_path / "nudged.h0.nc"
    _write_h0(h0, first_guess, analyzed, mask=mask)

    aggregate = compute_diagnostics(nudged_dir, free_dir, [h0], stamps=[stamp])["aggregate"]

    assert aggregate["active_nudged_sample_count"] == 4
    assert aggregate["valid_sample_count"] == 4
    assert aggregate["analysis_increment_mean"] == pytest.approx(0.025)
    assert aggregate["sp3_sw05_nudged_minus_free_mean"] == pytest.approx(0.025)
    assert aggregate["coherence_correlation"] == pytest.approx(1.0)


def test_write_outputs_and_cli_use_analysis_terminology(tmp_path: Path) -> None:
    import sp3_tests.verify_sp3v2_aod_nudged as module

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    outdir = tmp_path / "out"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    free = np.full((2, 3), 0.2, dtype=np.float32)
    delta = np.asarray([[0.01, 0.02, 0.03], [0.04, 0.05, 0.06]], dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", free + delta, nudged=".true.")
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", free, nudged="false")
    h0 = tmp_path / "nudged.h0.nc"
    _write_h0(h0, free, free + delta)

    result = module.main(
        [
            "--nudged-sp3-dir",
            str(nudged_dir),
            "--free-sp3-dir",
            str(free_dir),
            "--nudged-h0-files",
            str(h0),
            "--outdir",
            str(outdir),
            "--stamp",
            stamp,
        ]
    )

    assert result == 0
    json_path = outdir / "sp3v2_t10_aod_nudged_diagnostics_summary.json"
    csv_path = outdir / "sp3v2_t10_aod_nudged_diagnostics_summary.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "analysis_increment_mean" in payload["aggregate"]
    assert "first_guess_finite_count" in payload["aggregate"]
    assert "analyzed_finite_count" in payload["aggregate"]
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["record"] for row in rows] == [stamp, "aggregate"]
    assert "analysis_increment_mean" in rows[0]
    assert "sp3_sw05_nudged_minus_free_mean" in rows[0]


def test_compute_diagnostics_rejects_missing_or_false_nudged_attr(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3v2_aod_nudged import compute_diagnostics

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    data = np.full((2, 3), 0.2, dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=0)
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=0)
    h0 = tmp_path / "nudged.h0.nc"
    _write_h0(h0, data, data)

    with pytest.raises(ValueError, match="nudged.*attr"):
        compute_diagnostics(nudged_dir, free_dir, [h0], stamps=[stamp])


def test_compute_diagnostics_rejects_nudged_free_control_file(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3v2_aod_nudged import compute_diagnostics

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    data = np.full((2, 3), 0.2, dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=1)
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged="yes")
    h0 = tmp_path / "nudged.h0.nc"
    _write_h0(h0, data, data)

    with pytest.raises(ValueError, match="free/control.*must not be nudged"):
        compute_diagnostics(nudged_dir, free_dir, [h0], stamps=[stamp])


def test_compute_diagnostics_rejects_non_lut_method(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3v2_aod_nudged import compute_diagnostics

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    data = np.full((2, 3), 0.2, dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=1, method="remap")
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=0)
    h0 = tmp_path / "nudged.h0.nc"
    _write_h0(h0, data, data)

    with pytest.raises(ValueError, match="expected SP3 method='lut'"):
        compute_diagnostics(nudged_dir, free_dir, [h0], stamps=[stamp])


def test_compute_diagnostics_rejects_incomplete_expected_stamp_window(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3v2_aod_nudged import compute_diagnostics

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    data = np.full((2, 3), 0.2, dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=1)
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=0)
    h0 = tmp_path / "nudged.h0.nc"
    _write_h0(h0, data, data)

    with pytest.raises(ValueError, match="expected 2 common"):
        compute_diagnostics(nudged_dir, free_dir, [h0], expected_stamp_count=2)


def test_compute_diagnostics_requires_aodndg_fields(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3v2_aod_nudged import compute_diagnostics

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    data = np.full((2, 3), 0.2, dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=1)
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=0)
    h0 = tmp_path / "nudged.h0.nc"
    xr.Dataset(
        {
            "AODNDG_MODEL_PRE": (("time", "lat", "lon"), data[None, :, :]),
            "date": (("time",), np.asarray([20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800], dtype=np.int32)),
        },
        coords={"time": [0.0], "lat": [-1.0, 1.0], "lon": [0.0, 120.0, 240.0]},
    ).to_netcdf(h0)

    with pytest.raises(ValueError, match="AODNDG_MODEL_POST"):
        compute_diagnostics(nudged_dir, free_dir, [h0], stamps=[stamp])


def test_compute_diagnostics_rejects_h0_coordinate_mismatch(tmp_path: Path) -> None:
    from sp3_tests.verify_sp3v2_aod_nudged import compute_diagnostics

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    data = np.full((2, 3), 0.2, dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=1)
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", data, nudged=0)
    h0 = tmp_path / "nudged.h0.nc"
    _write_h0(h0, data, data, lat=np.asarray([-2.0, 2.0], dtype=np.float32))

    with pytest.raises(ValueError, match="latitude grid"):
        compute_diagnostics(nudged_dir, free_dir, [h0], stamps=[stamp])


def test_cli_returns_nonzero_for_no_active_nudged_cells(tmp_path: Path) -> None:
    import sp3_tests.verify_sp3v2_aod_nudged as module

    nudged_dir = tmp_path / "nudged_sp3"
    free_dir = tmp_path / "free_sp3"
    outdir = tmp_path / "out"
    nudged_dir.mkdir()
    free_dir.mkdir()
    stamp = "20080701.10800"
    free = np.full((2, 3), 0.2, dtype=np.float32)
    delta = np.asarray([[0.01, 0.02, 0.03], [0.04, 0.05, 0.06]], dtype=np.float32)
    _write_sp3_sw05(nudged_dir / f"AER_MAM4_SW05.{stamp}.nc", free + delta, nudged=1)
    _write_sp3_sw05(free_dir / f"AER_MAM4_SW05.{stamp}.nc", free, nudged=0)
    h0 = tmp_path / "nudged.h0.nc"
    _write_h0(h0, free, free + delta, mask=np.zeros((2, 3), dtype=np.float32))

    result = module.main(
        [
            "--nudged-sp3-dir",
            str(nudged_dir),
            "--free-sp3-dir",
            str(free_dir),
            "--nudged-h0-files",
            str(h0),
            "--outdir",
            str(outdir),
            "--stamp",
            stamp,
        ]
    )

    assert result == 1
    assert (outdir / "sp3v2_t10_aod_nudged_diagnostics_summary.json").exists()
