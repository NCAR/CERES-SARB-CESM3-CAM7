from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from sp3_tests.check_sp3_outputs import check_physical_invariants, summarize_directory


def write_sp3_file(
    path: Path,
    *,
    ext_value: float = 0.2,
    sca_value: float = 0.1,
    asm_value: float = 0.6,
) -> None:
    nlev, nlat, nlon = 2, 3, 4
    ext = np.full((nlev, nlat, nlon), ext_value, dtype=np.float32)
    sca = np.full((nlev, nlat, nlon), sca_value, dtype=np.float32)
    asm = np.full((nlev, nlat, nlon), asm_value, dtype=np.float32)
    ds = xr.Dataset(
        {
            "DELP": (("lev", "lat", "lon"), np.full_like(ext, 1000.0)),
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), ext),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), sca),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), asm),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), ext.sum(axis=0)),
        },
        coords={
            "lev": np.arange(1, nlev + 1, dtype=np.float32),
            "lat": np.linspace(-90.0, 90.0, nlat, dtype=np.float32),
            "lon": np.linspace(0.0, 360.0, nlon, endpoint=False, dtype=np.float32),
        },
    )
    ds.to_netcdf(path)


def test_summarize_directory_reports_complete_time_groups(tmp_path):
    for stamp in ("20080701.00000", "20080701.10800"):
        for band in ("SW01", "SW02"):
            write_sp3_file(tmp_path / f"AER_MAM4_{band}.{stamp}.nc")

    summary = summarize_directory(tmp_path, expected_bands=("SW01", "SW02"), interval_seconds=10800)

    assert summary.file_count == 4
    assert summary.group_count == 2
    assert summary.incomplete_groups == {}
    assert summary.interval_errors == []


def test_summarize_directory_flags_missing_band(tmp_path):
    write_sp3_file(tmp_path / "AER_MAM4_SW01.20080701.00000.nc")
    write_sp3_file(tmp_path / "AER_MAM4_SW02.20080701.00000.nc")
    write_sp3_file(tmp_path / "AER_MAM4_SW01.20080701.10800.nc")

    summary = summarize_directory(tmp_path, expected_bands=("SW01", "SW02"), interval_seconds=10800)

    assert summary.file_count == 3
    assert summary.incomplete_groups == {"20080701.10800": ("SW02",)}


def test_check_physical_invariants_rejects_invalid_layer_values(tmp_path):
    write_sp3_file(tmp_path / "AER_MAM4_SW01.20080701.00000.nc", sca_value=0.25, asm_value=1.2)

    with pytest.raises(AssertionError, match="sca <= ext"):
        check_physical_invariants(tmp_path)
