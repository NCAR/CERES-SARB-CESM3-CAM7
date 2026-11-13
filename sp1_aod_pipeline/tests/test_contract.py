from datetime import datetime

import netCDF4 as nc
import numpy as np

from sp1_aod_pipeline import contract as c
from sp1_aod_pipeline.f09_grid import NLAT, NLON


def _fields():
    mean = np.full((NLAT, NLON), -999.0, np.float32)
    unc = np.full((NLAT, NLON), -999.0, np.float32)
    cnt = np.zeros((NLAT, NLON), np.int32)
    mean[10, 20] = 0.42
    unc[10, 20] = 0.05
    cnt[10, 20] = 7
    return mean, unc, cnt


def test_filename():
    assert (
        c.contract_filename(datetime(2020, 6, 15, 3, 0, 0))
        == "MODIS_VIIRS_AOD_3hr_f09.20200615.10800.nc"
    )
    assert c.contract_filename(datetime(2020, 6, 15, 0, 0, 0)).endswith(".00000.nc")


def test_write_then_validate_ok(tmp_path):
    mean, unc, cnt = _fields()
    out = str(tmp_path / "x.nc")
    c.write_contract_file(
        out,
        window_start=datetime(2020, 6, 15, 0, 0, 0),
        aod_weighted_mean=mean,
        aod_uncertainty=unc,
        aod_count=cnt,
        aod_weighted_mean_modis=mean,
        aod_weighted_mean_viirs=mean,
        global_attrs={"qc_thresholds": "viirs_qa>=2", "source": "test"},
    )
    ok, errs = c.validate_contract_file(out)
    assert ok, errs


def test_time_is_scalar_center_and_bnds(tmp_path):
    mean, unc, cnt = _fields()
    out = str(tmp_path / "y.nc")
    c.write_contract_file(
        out,
        window_start=datetime(2000, 1, 1, 0, 0, 0),
        aod_weighted_mean=mean,
        aod_uncertainty=unc,
        aod_count=cnt,
    )
    ds = nc.Dataset(out)
    t = ds["time"]
    assert t.ndim == 0
    assert abs(float(t[...]) - 1.5) < 1e-9
    assert np.allclose(ds["time_bnds"][:], [0.0, 3.0])
    assert t.units == c.TIME_UNITS and t.calendar == c.TIME_CALENDAR
    ds.close()


def test_fill_and_dtypes(tmp_path):
    mean, unc, cnt = _fields()
    out = str(tmp_path / "z.nc")
    c.write_contract_file(
        out,
        window_start=datetime(2020, 6, 15, 0, 0, 0),
        aod_weighted_mean=mean,
        aod_uncertainty=unc,
        aod_count=cnt,
    )
    ds = nc.Dataset(out)
    v = ds["aod_weighted_mean"]
    assert v.dtype == np.float32 and float(v._FillValue) == -999.0 and v.units == "1"
    assert ds["aod_count"].dtype == np.int32 and int(ds["aod_count"]._FillValue) == 0
    assert ds.getncattr("Conventions") == "CF-1.10"
    ds.close()


def test_validator_flags_bad_grid(tmp_path):
    out = str(tmp_path / "bad.nc")
    ds = nc.Dataset(out, "w")
    ds.createDimension("lat", NLAT)
    ds.createDimension("lon", NLON)
    ds.createDimension("nbnds", 2)
    ds.createVariable("lat", "f8", ("lat",))[:] = np.zeros(NLAT)
    ds.close()
    ok, errs = c.validate_contract_file(out)
    assert not ok
    assert any("lat" in err for err in errs)
