from datetime import date

import numpy as np
import pandas as pd
import xarray as xr

from sp1_aod_pipeline.validation import aeronet
from sp1_aod_pipeline.validation.aeronet import aod_550_from_500, load_aeronet_file


def test_aod_550_from_500():
    expected = 0.22 * (550.0 / 500.0) ** (-1.0)

    assert np.isclose(aod_550_from_500(np.array([0.22]), np.array([1.0]))[0], expected)


def _make_yx_cache(path):
    time = pd.date_range("2010-01-01", periods=2, freq="h")
    xr.Dataset(
        {
            "aod_500nm": (
                ("time", "y", "x"),
                np.array([[[0.220, -1.0]], [[-999.0, 0.30]]]),
            ),
            "440-675_angstrom_exponent": (
                ("time", "y", "x"),
                np.array([[[1.0, 1.2]], [[1.1, 0.8]]]),
            ),
        },
        coords={
            "time": time,
            "y": [0],
            "x": ("x", np.array([0, 1])),
            "siteid": ("x", np.array(["Sao_Paulo", "GSFC"])),
            "latitude": ("x", np.array([-23.5, 39.0])),
            "longitude": ("x", np.array([-46.7, -76.8])),
        },
    ).to_netcdf(path)


def _make_reader_schema_cache(path):
    time = pd.date_range("2010-01-02", periods=2, freq="h")
    sites = np.array(["Sao_Paulo", "GSFC"])
    xr.Dataset(
        {
            "aod_500nm": (
                ("time", "site"),
                np.array([[0.220, -1.0], [-999.0, 0.30]]),
            ),
            "440-675_angstrom_exponent": (
                ("time", "site"),
                np.array([[1.0, 1.2], [1.1, 0.8]]),
            ),
            "latitude": (
                ("time", "site"),
                np.array([[-23.5, 39.0], [-23.5, 39.0]]),
            ),
            "longitude": (
                ("time", "site"),
                np.array([[-46.7, -76.8], [-46.7, -76.8]]),
            ),
        },
        coords={"time": time, "site": sites},
    ).to_netcdf(path)


def test_load_aeronet_file_yx_cache_schema(tmp_path):
    path = tmp_path / "AeroNet_20100101.nc"
    _make_yx_cache(str(path))

    df = load_aeronet_file(str(path))

    assert len(df) == 2
    row = df[df.site == "Sao_Paulo"].iloc[0]
    assert np.isclose(row.lat, -23.5)
    assert np.isclose(row.lon, -46.7)
    assert np.isclose(row.aod550, 0.220 * (550.0 / 500.0) ** (-1.0), atol=1e-6)
    assert {"site", "lat", "lon", "time", "aod550"} <= set(df.columns)
    assert str(row.time).endswith("+00:00")


def test_load_aeronet_file_reader_schema(tmp_path):
    path = tmp_path / "AeroNet_20100102.nc"
    _make_reader_schema_cache(str(path))

    df = load_aeronet_file(str(path))

    assert len(df) == 2
    row = df[df.site == "GSFC"].iloc[0]
    assert np.isclose(row.lat, 39.0)
    assert np.isclose(row.lon, -76.8)
    assert np.isclose(row.aod550, 0.30 * (550.0 / 500.0) ** (-0.8), atol=1e-6)


def test_load_aeronet_days_uses_cache_or_download(monkeypatch, tmp_path):
    cached = tmp_path / "AeroNet_20100101.nc"
    _make_yx_cache(str(cached))
    calls = []

    def fake_download(day, cache_dir):
        calls.append((day, cache_dir))
        return pd.DataFrame(
            {
                "site": ["Downloaded"],
                "lat": [10.0],
                "lon": [20.0],
                "time": [pd.Timestamp("2010-01-02T00:00:00Z")],
                "aod550": [0.1],
            }
        )

    monkeypatch.setattr(aeronet, "_download_day", fake_download)

    df = aeronet.load_aeronet_days(
        [date(2010, 1, 1), date(2010, 1, 2)], cache_dir=str(tmp_path), download=True
    )

    assert len(df) == 3
    assert calls == [(date(2010, 1, 2), str(tmp_path))]
