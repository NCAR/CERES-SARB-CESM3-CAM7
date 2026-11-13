from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import netCDF4 as nc
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sp2_tests" / "make_transport_pulse_obs.py"


def test_transport_pulse_generator_writes_pulse_then_fill_windows(tmp_path):
    assert SCRIPT.exists(), "Task 11 pulse-observation generator is missing"

    out = tmp_path / "pulse"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--outdir",
            str(out),
            "--date",
            "00010101",
            "--ndays",
            "1",
            "--times-per-day",
            "4",
            "--pulse-windows",
            "2",
            "--pulse-value",
            "1.25",
            "--pulse-lat-min",
            "25",
            "--pulse-lat-max",
            "45",
            "--pulse-lon-min",
            "160",
            "--pulse-lon-max",
            "220",
        ],
        check=True,
    )

    files = sorted(out.glob("MODIS_VIIRS_AOD_3hr_f09.*.nc"))
    assert [path.name for path in files] == [
        "MODIS_VIIRS_AOD_3hr_f09.00010101.00000.nc",
        "MODIS_VIIRS_AOD_3hr_f09.00010101.21600.nc",
        "MODIS_VIIRS_AOD_3hr_f09.00010101.43200.nc",
        "MODIS_VIIRS_AOD_3hr_f09.00010101.64800.nc",
    ]

    with nc.Dataset(files[0]) as ds:
        assert ds.dimensions["lat"].size == 192
        assert ds.dimensions["lon"].size == 288
        lat = ds.variables["lat"][:]
        lon = ds.variables["lon"][:]
        aod = np.ma.filled(ds.variables["aod_weighted_mean"][:], -999.0)
        pulse = (lat[:, None] >= 25.0) & (lat[:, None] <= 45.0)
        pulse = pulse & (lon[None, :] >= 160.0) & (lon[None, :] <= 220.0)

        assert ds.variables["time"].shape == ()
        assert ds.variables["time_bnds"].shape == (2,)
        assert np.all(aod[pulse] == np.float32(1.25))
        assert np.all(aod[~pulse] == np.float32(-999.0))
        assert np.all(np.ma.filled(ds.variables["aod_count"][:], 0)[pulse] == 10)

    with nc.Dataset(files[2]) as ds:
        later = np.ma.filled(ds.variables["aod_weighted_mean"][:], -999.0)
        assert np.all(later == np.float32(-999.0))


def test_transport_pulse_generator_can_write_all_fill_control(tmp_path):
    assert SCRIPT.exists(), "Task 11 pulse-observation generator is missing"

    out = tmp_path / "fill"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--outdir",
            str(out),
            "--date",
            "00010101",
            "--ndays",
            "1",
            "--times-per-day",
            "2",
            "--pulse-windows",
            "0",
            "--pulse-value",
            "1.0",
            "--pulse-lat-min",
            "25",
            "--pulse-lat-max",
            "45",
            "--pulse-lon-min",
            "160",
            "--pulse-lon-max",
            "220",
        ],
        check=True,
    )

    for path in sorted(out.glob("MODIS_VIIRS_AOD_3hr_f09.*.nc")):
        with nc.Dataset(path) as ds:
            aod = np.ma.filled(ds.variables["aod_weighted_mean"][:], -999.0)
            count = np.ma.filled(ds.variables["aod_count"][:], 0)
        assert np.all(aod == np.float32(-999.0))
        assert np.all(count == 0)
