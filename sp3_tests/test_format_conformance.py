import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

MAM_LFL = Path("/glade/work/fillmore/CERES-SARB-MAM-LFL")
sys.path.insert(0, str(MAM_LFL))

import mode_external_mix as external_mix  # noqa: E402


REQ = external_mix.REQUIRED_VARIABLES


def synthetic_sp3_file(path: Path) -> None:
    rng = np.random.default_rng(42)
    nlev, nlat, nlon = 4, 3, 5
    ext = (rng.random((nlev, nlat, nlon), dtype=np.float32) * 0.1).astype("f4")
    sca = (ext * np.float32(0.7)).astype("f4")
    asm = np.full_like(ext, 0.6, dtype="f4")
    delp = np.full_like(ext, 1000.0, dtype="f4")

    ds = xr.Dataset(
        {
            "DELP": (("lev", "lat", "lon"), delp),
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), ext),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), sca),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), asm),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), ext.sum(axis=0).astype("f4")),
        },
        coords={
            "lev": np.arange(1, nlev + 1, dtype=np.float32),
            "lat": np.linspace(-90, 90, nlat, dtype=np.float32),
            "lon": np.linspace(0, 360, nlon, endpoint=False, dtype=np.float32),
        },
        attrs={"scheme": "MAM4", "band": "sw01", "wavelength_um": 0.55, "source": "CAM7"},
    )
    ds.to_netcdf(path)


def assert_mam_lfl_conformant(path: Path) -> xr.Dataset:
    ds = xr.open_dataset(path)
    for variable in REQ:
        assert variable in ds, f"missing {variable}"
    assert tuple(ds["Extinction_Layer_Optical_Depth"].dims) in external_mix.SUPPORTED_LAYER_DIMS
    mixed = external_mix.mix_mode_datasets([ds])
    assert "Extinction_Column_Optical_Depth" in mixed
    return ds


def test_sp3_file_is_legal_mam_lfl_input(tmp_path):
    path = tmp_path / "AER_MAM4_SW01.20080701.0.nc"
    synthetic_sp3_file(path)
    assert_mam_lfl_conformant(path)


def test_real_sp3_file_is_legal_mam_lfl_input():
    path = pytest.importorskip("os").environ.get("SP3_SAMPLE_FILE")
    if not path:
        pytest.skip("set SP3_SAMPLE_FILE to validate a real SP3 output file")
    assert_mam_lfl_conformant(Path(path))
