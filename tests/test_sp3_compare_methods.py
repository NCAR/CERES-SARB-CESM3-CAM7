from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr


def _write_sp3(path: Path, *, ext: float, sca: float, asm: float) -> None:
    nlev, nlat, nlon = 2, 2, 3
    ext_data = np.full((nlev, nlat, nlon), ext, dtype=np.float32)
    sca_data = np.full((nlev, nlat, nlon), sca, dtype=np.float32)
    asm_data = np.full((nlev, nlat, nlon), asm, dtype=np.float32)
    ds = xr.Dataset(
        {
            "DELP": (("lev", "lat", "lon"), np.full_like(ext_data, 1000.0)),
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), ext_data),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), sca_data),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), asm_data),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), ext_data.sum(axis=0)),
        },
        coords={
            "lev": np.arange(1, nlev + 1, dtype=np.float32),
            "lat": np.linspace(-10.0, 10.0, nlat, dtype=np.float32),
            "lon": np.linspace(0.0, 360.0, nlon, endpoint=False, dtype=np.float32),
        },
    )
    ds.to_netcdf(path)


def _write_h0(path: Path, variable: str, values: np.ndarray, *, date: int = 20080701, datesec: int = 10800) -> None:
    data = np.asarray(values, dtype=np.float32)
    ds = xr.Dataset(
        {
            variable: (("time", "lat", "lon"), data[None, :, :]),
            "date": (("time",), np.asarray([date], dtype=np.int32)),
            "datesec": (("time",), np.asarray([datesec], dtype=np.int32)),
        },
        coords={
            "time": [0.0],
            "lat": np.linspace(-10.0, 10.0, data.shape[0], dtype=np.float32),
            "lon": np.linspace(0.0, 360.0, data.shape[1], endpoint=False, dtype=np.float32),
        },
    )
    ds.to_netcdf(path)


def test_compare_methods_reports_lut_to_remap_column_metrics(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_directories

    remap = tmp_path / "remap"
    lut = tmp_path / "lut"
    remap.mkdir()
    lut.mkdir()
    _write_sp3(remap / "AER_MAM4_SW05.20080701.00000.nc", ext=0.2, sca=0.1, asm=0.5)
    _write_sp3(lut / "AER_MAM4_SW05.20080701.00000.nc", ext=0.1, sca=0.08, asm=0.6)

    metrics = compare_directories(remap, lut, bands=["SW05"])

    assert len(metrics) == 1
    row = metrics[0]
    assert row.band == "SW05"
    assert row.common_times == 1
    assert row.count == 6
    assert row.remap_column_mean == pytest.approx(0.4)
    assert row.lut_column_mean == pytest.approx(0.2)
    assert row.median_ratio == pytest.approx(0.5)
    assert row.median_abs_relative_difference == pytest.approx(0.5)
    assert row.mean_abs_relative_difference == pytest.approx(0.5)


def test_compare_methods_computes_metrics_over_all_time_space_samples(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_directories

    remap = tmp_path / "remap"
    lut = tmp_path / "lut"
    remap.mkdir()
    lut.mkdir()
    _write_sp3(remap / "AER_MAM4_SW05.20080701.00000.nc", ext=0.1, sca=0.05, asm=0.5)
    _write_sp3(lut / "AER_MAM4_SW05.20080701.00000.nc", ext=0.2, sca=0.10, asm=0.5)
    _write_sp3(remap / "AER_MAM4_SW05.20080701.10800.nc", ext=0.3, sca=0.15, asm=0.5)
    _write_sp3(lut / "AER_MAM4_SW05.20080701.10800.nc", ext=0.2, sca=0.10, asm=0.5)

    row = compare_directories(remap, lut, bands=["SW05"])[0]

    assert row.common_times == 2
    assert row.count == 12
    assert row.mean_abs_relative_difference == pytest.approx(2.0 / 3.0)


def test_column_ssa_and_asymmetry_are_scattering_weighted(tmp_path):
    from sp3_tests.compare_sp3_methods import column_asymmetry, column_ssa

    path = tmp_path / "AER_MAM4_LW06.20080701.00000.nc"
    _write_sp3(path, ext=0.25, sca=0.1, asm=0.7)

    with xr.open_dataset(path) as ds:
        np.testing.assert_allclose(column_ssa(ds), np.full((2, 3), 0.4))
        np.testing.assert_allclose(column_asymmetry(ds), np.full((2, 3), 0.7))


def test_load_band_mean_preserves_scattering_weighted_asymmetry_over_time(tmp_path):
    from sp3_tests.compare_sp3_methods import column_asymmetry, load_band_mean

    indir = tmp_path / "sp3"
    indir.mkdir()
    _write_sp3(indir / "AER_MAM4_LW06.20080701.00000.nc", ext=0.2, sca=0.1, asm=0.0)
    _write_sp3(indir / "AER_MAM4_LW06.20080701.10800.nc", ext=0.2, sca=0.3, asm=1.0)

    averaged = load_band_mean(indir, "LW06")

    np.testing.assert_allclose(column_asymmetry(averaged), np.full((2, 3), 0.75))


def test_cam_visible_overlap_comparison_remaps_lfl_sw_bands_to_aodvis(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_lfl_visible_to_h0
    from sp3_tests.compare_sp3_methods import lfl_visible_overlap_column

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    _write_sp3(sp3 / "AER_MAM4_SW04.20080701.10800.nc", ext=0.3, sca=0.1, asm=0.4)
    _write_sp3(sp3 / "AER_MAM4_SW05.20080701.10800.nc", ext=0.2, sca=0.1, asm=0.4)
    _write_sp3(sp3 / "AER_MAM4_SW06.20080701.10800.nc", ext=0.1, sca=0.1, asm=0.4)
    combined, weights = lfl_visible_overlap_column(sp3, ["20080701.10800"])
    assert [band for band, _ in weights] == ["SW04", "SW05", "SW06"]

    h0 = tmp_path / "h0.nc"
    _write_h0(h0, "AODVISdn", combined)

    comparison = compare_lfl_visible_to_h0(sp3, h0, stamp="20080701.10800")

    assert comparison.band == "CAMVIS"
    assert comparison.stamp_count == 1
    assert comparison.stamps == "20080701.10800"
    assert comparison.mean_abs_relative_difference == pytest.approx(0.0, abs=1.0e-7)


def test_h0_visible_overlap_requires_stamp_for_multi_time_h0(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_lfl_visible_to_h0

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    for stamp in ("20080701.10800", "20080701.21600"):
        _write_sp3(sp3 / f"AER_MAM4_SW04.{stamp}.nc", ext=0.3, sca=0.1, asm=0.4)
        _write_sp3(sp3 / f"AER_MAM4_SW05.{stamp}.nc", ext=0.2, sca=0.1, asm=0.4)
        _write_sp3(sp3 / f"AER_MAM4_SW06.{stamp}.nc", ext=0.1, sca=0.1, asm=0.4)
    h0 = tmp_path / "h0.nc"
    data = np.ones((2, 2, 3), dtype=np.float32)
    xr.Dataset(
        {
            "AODVISdn": (("time", "lat", "lon"), data),
            "date": (("time",), np.asarray([20080701, 20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800, 21600], dtype=np.int32)),
        },
        coords={
            "time": [0.0, 1.0],
            "lat": np.linspace(-10.0, 10.0, 2, dtype=np.float32),
            "lon": np.linspace(0.0, 360.0, 3, endpoint=False, dtype=np.float32),
        },
    ).to_netcdf(h0)

    with pytest.raises(ValueError, match="--h0-stamp"):
        compare_lfl_visible_to_h0(sp3, h0)


def test_h0_comparison_requires_stamp_when_sp3_has_multiple_times(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_band_to_h0

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    _write_sp3(sp3 / "AER_MAM4_SW05.20080701.10800.nc", ext=0.2, sca=0.1, asm=0.4)
    _write_sp3(sp3 / "AER_MAM4_SW05.20080701.21600.nc", ext=0.4, sca=0.1, asm=0.4)
    h0 = tmp_path / "h0.nc"
    _write_h0(h0, "AODVISdn", np.ones((2, 3), dtype=np.float32))

    with pytest.raises(ValueError, match="--h0-stamp"):
        compare_band_to_h0(sp3, h0, band="SW05")


def test_h0_comparison_rejects_unvalidated_stamp(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_band_to_h0

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    _write_sp3(sp3 / "AER_MAM4_SW05.20080701.10800.nc", ext=0.2, sca=0.1, asm=0.4)
    h0 = tmp_path / "h0.nc"
    _write_h0(h0, "AODVISdn", np.ones((2, 3), dtype=np.float32), date=20080702, datesec=10800)

    with pytest.raises(ValueError, match="could not match"):
        compare_band_to_h0(sp3, h0, band="SW05", stamp="20080701.10800")


def test_h0_comparison_masks_on_h0_denominator(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_band_to_h0

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    _write_sp3(sp3 / "AER_MAM4_SW05.20080701.10800.nc", ext=0.2, sca=0.1, asm=0.4)
    h0 = tmp_path / "h0.nc"
    _write_h0(h0, "AODVISdn", np.zeros((2, 3), dtype=np.float32))

    with pytest.raises(ValueError, match="no finite nonzero cells"):
        compare_band_to_h0(sp3, h0, band="SW05", stamp="20080701.10800")


def test_visible_overlap_comparison_aggregates_multiple_h0_files(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_lfl_visible_to_h0_files
    from sp3_tests.compare_sp3_methods import lfl_visible_overlap_column

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    h0_files = []
    expected_columns = []
    for idx, (date, seconds, scale) in enumerate(((20080701, 10800, 1.0), (20080702, 21600, 2.0))):
        stamp = f"{date}.{seconds:05d}"
        _write_sp3(sp3 / f"AER_MAM4_SW04.{stamp}.nc", ext=0.3 * scale, sca=0.1, asm=0.4)
        _write_sp3(sp3 / f"AER_MAM4_SW05.{stamp}.nc", ext=0.2 * scale, sca=0.1, asm=0.4)
        _write_sp3(sp3 / f"AER_MAM4_SW06.{stamp}.nc", ext=0.1 * scale, sca=0.1, asm=0.4)
        combined, _ = lfl_visible_overlap_column(sp3, [stamp])
        expected_columns.append(combined)
        h0 = tmp_path / f"h0_{idx}.nc"
        _write_h0(h0, "AODVISdn", combined, date=date, datesec=seconds)
        h0_files.append(h0)

    comparison = compare_lfl_visible_to_h0_files(sp3, h0_files)

    assert comparison.band == "CAMVIS"
    assert comparison.h0_variable == "AODVISdn"
    assert comparison.stamp_count == 2
    assert comparison.stamps == "20080701.10800 20080702.21600"
    assert comparison.count == sum(column.size for column in expected_columns)
    assert comparison.mean_abs_relative_difference == pytest.approx(0.0, abs=1.0e-7)
    assert comparison.median_ratio == pytest.approx(1.0)


def test_raw_band_h0_comparison_aggregates_multiple_h0_files(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_band_to_h0_files

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    h0_files = []
    expected_columns = []
    for idx, (date, seconds, scale) in enumerate(((20080701, 10800, 1.0), (20080702, 21600, 2.0))):
        stamp = f"{date}.{seconds:05d}"
        _write_sp3(sp3 / f"AER_MAM4_SW05.{stamp}.nc", ext=0.2 * scale, sca=0.1, asm=0.4)
        expected = np.full((2, 3), 0.4 * scale, dtype=np.float32)
        expected_columns.append(expected)
        h0 = tmp_path / f"h0_raw_{idx}.nc"
        _write_h0(h0, "AODVISdn", expected, date=date, datesec=seconds)
        h0_files.append(h0)

    comparison = compare_band_to_h0_files(sp3, h0_files, band="SW05")

    assert comparison.band == "SW05"
    assert comparison.stamp_count == 2
    assert comparison.stamps == "20080701.10800 20080702.21600"
    assert comparison.count == sum(column.size for column in expected_columns)
    assert comparison.mean_abs_relative_difference == pytest.approx(0.0, abs=1.0e-7)
    assert comparison.median_ratio == pytest.approx(1.0)


def test_aggregate_h0_comparison_requires_expected_stamp_count(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_band_to_h0_files

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    stamp = "20080701.10800"
    _write_sp3(sp3 / f"AER_MAM4_SW05.{stamp}.nc", ext=0.2, sca=0.1, asm=0.4)
    h0 = tmp_path / "h0.nc"
    _write_h0(h0, "AODVISdn", np.full((2, 3), 0.4, dtype=np.float32), date=20080701, datesec=10800)

    with pytest.raises(ValueError, match="expected 2 h0 stamp"):
        compare_band_to_h0_files(sp3, [h0], band="SW05", expected_stamp_count=2)


def test_aggregate_h0_comparison_rejects_duplicate_stamps(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_band_to_h0_files

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    stamp = "20080701.10800"
    _write_sp3(sp3 / f"AER_MAM4_SW05.{stamp}.nc", ext=0.2, sca=0.1, asm=0.4)
    h0_a = tmp_path / "h0_a.nc"
    h0_b = tmp_path / "h0_b.nc"
    values = np.full((2, 3), 0.4, dtype=np.float32)
    _write_h0(h0_a, "AODVISdn", values, date=20080701, datesec=10800)
    _write_h0(h0_b, "AODVISdn", values, date=20080701, datesec=10800)

    with pytest.raises(ValueError, match="duplicate h0 stamp"):
        compare_band_to_h0_files(sp3, [h0_a, h0_b], band="SW05")


def test_aggregate_h0_comparison_requires_expected_stamp_set(tmp_path):
    from sp3_tests.compare_sp3_methods import compare_band_to_h0_files

    sp3 = tmp_path / "sp3"
    sp3.mkdir()
    stamp = "20080701.10800"
    _write_sp3(sp3 / f"AER_MAM4_SW05.{stamp}.nc", ext=0.2, sca=0.1, asm=0.4)
    h0 = tmp_path / "h0.nc"
    _write_h0(h0, "AODVISdn", np.full((2, 3), 0.4, dtype=np.float32), date=20080701, datesec=10800)

    with pytest.raises(ValueError, match="stamp set mismatch"):
        compare_band_to_h0_files(sp3, [h0], band="SW05", expected_stamps=["20080702.10800"])


def test_cli_writes_raw_and_camvis_aod_comparisons_for_multi_h0_files(tmp_path):
    import json

    from sp3_tests.compare_sp3_methods import lfl_visible_overlap_column
    from sp3_tests.compare_sp3_methods import main

    remap = tmp_path / "remap"
    lut = tmp_path / "lut"
    outdir = tmp_path / "out"
    remap.mkdir()
    lut.mkdir()
    h0_files = []
    for idx, (date, seconds, scale) in enumerate(((20080701, 10800, 1.0), (20080702, 21600, 2.0))):
        stamp = f"{date}.{seconds:05d}"
        for directory in (remap, lut):
            _write_sp3(directory / f"AER_MAM4_SW04.{stamp}.nc", ext=0.3 * scale, sca=0.1, asm=0.4)
            _write_sp3(directory / f"AER_MAM4_SW05.{stamp}.nc", ext=0.2 * scale, sca=0.1, asm=0.4)
            _write_sp3(directory / f"AER_MAM4_SW06.{stamp}.nc", ext=0.1 * scale, sca=0.1, asm=0.4)
        combined, _ = lfl_visible_overlap_column(lut, [stamp])
        h0 = tmp_path / f"h0_cli_{idx}.nc"
        _write_h0(h0, "AODVISdn", combined, date=date, datesec=seconds)
        h0_files.append(h0)

    result = main(
        [
            "--remap-dir",
            str(remap),
            "--lut-dir",
            str(lut),
            "--outdir",
            str(outdir),
            "--bands",
            "SW05",
            "--h0-files",
            *(str(path) for path in h0_files),
            "--h0-visible-overlap",
            "--h0-include-raw-band",
            "--expected-h0-stamp-count",
            "2",
            "--expected-h0-stamps",
            "20080701.10800",
            "20080702.21600",
        ]
    )

    assert result == 0
    payload = json.loads((outdir / "sp3v2_method_comparison_summary.json").read_text(encoding="utf-8"))
    assert [row["band"] for row in payload["aod_comparisons"]] == ["SW05", "CAMVIS"]
    assert [row["stamp_count"] for row in payload["aod_comparisons"]] == [2, 2]
    assert payload["aod_comparison"]["band"] == "CAMVIS"
    assert (outdir / "sp3v2_aod_comparison_summary.csv").exists()


def test_cli_h0_files_requires_at_least_one_path(tmp_path):
    from sp3_tests.compare_sp3_methods import main

    with pytest.raises(SystemExit):
        main(
            [
                "--remap-dir",
                str(tmp_path / "remap"),
                "--lut-dir",
                str(tmp_path / "lut"),
                "--outdir",
                str(tmp_path / "out"),
                "--h0-files",
                "--h0-visible-overlap",
            ]
        )
