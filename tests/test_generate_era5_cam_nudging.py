from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path
import sys

import netCDF4
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_era5_cam_nudging.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_era5_cam_nudging", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_source_bundle_and_output_names_are_hourly():
    m = _load_module()
    timestamp = datetime(2008, 3, 10, 17)
    source = m.source_bundle_path(Path("/gdex/data/d633006"), "Q", timestamp)
    assert source.name == (
        "e5.oper.an.ml.0_5_0_1_0_q.regn320sc."
        "2008031012_2008031017.nc"
    )
    output = m.output_path(Path("/data"), timestamp)
    assert output.name == "ERA5_fv09.cam2.i.2008-03-10-61200.nc"


def test_noleap_offsets_and_february_29_rejection():
    m = _load_module()
    reference = datetime(2008, 2, 28)
    assert m.noleap_day_offset(datetime(2008, 3, 1, 12), reference) == 1.5
    with pytest.raises(ValueError, match="February 29"):
        m.parse_hour("2008-02-29T00:00:00")


def test_bilinear_plan_interpolates_and_wraps_longitude():
    m = _load_module()
    source_lat = np.array([-1.0, 1.0])
    source_lon = np.array([0.0, 180.0])
    values = np.array([[-1.0, 1.0], [1.0, 3.0]])
    plan = m.BilinearPlan.create(
        source_lat,
        source_lon,
        np.array([0.0]),
        np.array([90.0, 270.0]),
    )
    np.testing.assert_allclose(plan.apply(values), [[1.0, 1.0]])


def test_scalar_and_vector_poles_follow_seed_conventions():
    m = _load_module()
    source_lat = np.array([-80.0, 80.0])
    source_lon = np.arange(0.0, 360.0, 90.0)
    scalar = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]])
    target_lat = np.array([-90.0, -80.0, 80.0, 90.0])
    plan = m.BilinearPlan.create(source_lat, source_lon, target_lat, source_lon)
    scalar_result = plan.apply(scalar)
    np.testing.assert_allclose(scalar_result[0], np.mean(scalar[0]))
    np.testing.assert_allclose(scalar_result[-1], np.mean(scalar[-1]))

    wave = np.cos(np.deg2rad(source_lon))[None, :] * np.array([[2.0], [4.0]])
    vector_result = plan.apply(wave, vector_poles=True)
    np.testing.assert_allclose(vector_result[0], wave[0], atol=1e-14)
    np.testing.assert_allclose(vector_result[-1], wave[1], atol=1e-14)


def test_pressure_and_linear_vertical_interpolation():
    m = _load_module()
    ps = np.array([[1000.0]])
    pressure = m.build_pressure(np.array([10.0, 20.0]), np.array([0.1, 0.5]), ps)
    np.testing.assert_allclose(pressure[:, 0, 0], [110.0, 520.0])

    source_pressure = np.array([100.0, 500.0, 1000.0])[:, None, None]
    target_pressure = np.array([50.0, 300.0, 750.0, 1100.0])[:, None, None]
    values = np.array([1.0, 5.0, 10.0])[:, None, None]
    result = m.vertical_linear_opt1(values, source_pressure, target_pressure)
    np.testing.assert_allclose(result[:, 0, 0], [1.0, 3.0, 7.5, 10.0])


def test_wind_interpolation_is_constant_above_and_below():
    m = _load_module()
    source_pressure = np.array([100.0, 200.0, 400.0, 800.0])[:, None, None]
    target_pressure = np.array([50.0, 150.0, 600.0, 900.0])[:, None, None]
    values = np.array([1.0, 2.0, 4.0, 8.0])[:, None, None]
    result = m.vertical_linear_opt2(
        values, source_pressure, target_pressure, log_pressure=True
    )
    assert result[0, 0, 0] == 1.0
    assert result[-1, 0, 0] == 8.0
    assert np.all(np.isfinite(result))


def test_surface_pressure_is_unchanged_for_identical_topography():
    m = _load_module()
    ps = np.array([[100_000.0]])
    a_mid = np.array([100.0, 1000.0, 10_000.0, 40_000.0, 80_000.0])
    b_mid = np.zeros(5)
    a_interface = np.array([10.0, 500.0, 5000.0, 20_000.0, 60_000.0, 100_000.0])
    b_interface = np.zeros(6)
    pm = m.build_pressure(a_mid, b_mid, ps)
    pi = m.build_pressure(a_interface, b_interface, ps)
    temperature = np.full((5, 1, 1), 280.0)
    phis = np.array([[1000.0]])
    adjusted = m.adjust_surface_pressure(temperature, pm, pi, phis, phis, ps)
    np.testing.assert_array_equal(adjusted, ps)


def test_humidity_clipping_bounds_relative_humidity():
    m = _load_module()
    temperature = np.array([[[280.0, 280.0]]])
    pressure = np.array([[[90_000.0, 90_000.0]]])
    saturation = m.saturation_specific_humidity(temperature, pressure)
    humidity = np.array([[[-1.0, saturation.item(1) * 2.0]]])
    clipped = m.clip_specific_humidity(humidity, temperature, pressure)
    np.testing.assert_allclose(clipped[0, 0], [0.0, saturation.item(1)])


def test_staggered_v_reproduces_legacy_f09_pole_mapping():
    m = _load_module()
    lat = np.linspace(-90.0, 90.0, 192)
    lon = np.arange(288, dtype=np.float64) * 1.25
    target = m.TargetGrid(
        lat=lat,
        lon=lon,
        slat=0.5 * (lat[:-1] + lat[1:]),
        slon=lon - 0.625,
        hyam=np.array([0.0]),
        hybm=np.array([1.0]),
        hyai=np.array([0.0, 0.0]),
        hybi=np.array([0.0, 1.0]),
        p0=100_000.0,
        phis=np.zeros((192, 288)),
    )
    u = np.zeros((1, 192, 288))
    v = np.broadcast_to(np.arange(288, dtype=np.float64), u.shape).copy()
    _, vs = m.stagger_winds(u, v, target)
    ordinary = 0.5 * (np.roll(v, 1, axis=-1) + v)
    expected_south = np.concatenate(
        (ordinary[..., 0, :143], ordinary[..., 0, :145]), axis=-1
    )
    np.testing.assert_allclose(vs[..., 0, :], expected_south)
    np.testing.assert_allclose(
        vs[..., -1, :], np.broadcast_to(v[..., -1, 0, None], vs[..., -1, :].shape)
    )
    np.testing.assert_allclose(vs[..., 1:-1, :], ordinary[..., 1:-1, :])


def _make_template(path: Path) -> None:
    with netCDF4.Dataset(path, "w", format="NETCDF3_CLASSIC") as ds:
        for name, size in (
            ("lat", 2),
            ("lon", 2),
            ("slat", 1),
            ("slon", 2),
            ("lev", 2),
            ("ilev", 3),
            ("time", None),
            ("scalar", 1),
        ):
            ds.createDimension(name, size)
        for name in ("time",):
            ds.createVariable(name, "f8", ("time",))[:] = [0.0]
        for name in ("ndbase", "nsbase", "nbdate", "nbsec"):
            ds.createVariable(name, "i4", ("scalar",))[:] = [0]
        for name in ("ndcur", "nscur", "date", "datesec"):
            ds.createVariable(name, "i4", ("time",))[:] = [0]
        ds.createVariable("P0", "f8", ("scalar",))[:] = [100_000.0]
        for name, dim, values in (
            ("lat", "lat", [-90.0, 90.0]),
            ("lon", "lon", [0.0, 180.0]),
            ("slat", "slat", [0.0]),
            ("slon", "slon", [-90.0, 90.0]),
            ("lev", "lev", [100.0, 900.0]),
            ("ilev", "ilev", [0.0, 500.0, 1000.0]),
            ("hyam", "lev", [0.1, 0.0]),
            ("hybm", "lev", [0.0, 0.9]),
            ("hyai", "ilev", [0.0, 0.0, 0.0]),
            ("hybi", "ilev", [0.0, 0.5, 1.0]),
            ("w_stag", "slat", [1.0]),
            ("gw", "lat", [1.0, 1.0]),
        ):
            ds.createVariable(name, "f8", (dim,))[:] = values
        for name in ("ntrm", "ntrn", "ntrk"):
            ds.createVariable(name, "i4", ("scalar",))[:] = [-1]
        for name in ("U", "V", "T", "Q"):
            ds.createVariable(name, "f4", ("time", "lev", "lat", "lon"))[:] = 0
        ds.createVariable("PS", "f4", ("time", "lat", "lon"))[:] = 0
        ds.createVariable("US", "f4", ("time", "lev", "slat", "lon"))[:] = 0
        ds.createVariable("VS", "f4", ("time", "lev", "lat", "slon"))[:] = 0
        ds.createVariable("PHIS", "f4", ("time", "lat", "lon"))[:] = 0


def test_writer_is_atomic_and_updates_cam_time_and_provenance(tmp_path):
    m = _load_module()
    template = tmp_path / "template.nc"
    output = tmp_path / "out.nc"
    _make_template(template)
    fields = {
        "U": np.ones((2, 2, 2)),
        "V": np.ones((2, 2, 2)) * 2,
        "T": np.ones((2, 2, 2)) * 280,
        "Q": np.ones((2, 2, 2)) * 0.001,
        "PS": np.ones((2, 2)) * 90_000,
        "US": np.ones((2, 1, 2)),
        "VS": np.ones((2, 2, 2)) * 2,
    }
    source_paths = {
        name: tmp_path / f"{name}.nc"
        for name in (*m.SOURCE_SPECS, "Z", "PHIS")
    }
    timestamp = datetime(2008, 3, 10, 6)
    m.write_cam_file(
        output,
        template,
        fields,
        timestamp,
        datetime(2008, 3, 9),
        source_paths,
    )
    with netCDF4.Dataset(output) as ds:
        assert ds.data_model == "NETCDF3_CLASSIC"
        assert int(ds["date"][:].item()) == 20080310
        assert int(ds["datesec"][:].item()) == 21600
        assert float(ds["time"][:].item()) == 1.25
        assert ds.getncattr("producer") == "scripts/generate_era5_cam_nudging.py"
        assert str(ds.getncattr("source_T")).endswith("T.nc")
        assert str(ds.getncattr("source_Z")).endswith("Z.nc")
        assert str(ds["T"].getncattr("source_file")).endswith("T.nc")
        assert str(ds["PHIS"].getncattr("source_file")).endswith("PHIS.nc")
        np.testing.assert_allclose(ds["T"][0], 280.0)
    with pytest.raises(FileExistsError, match="overwrite"):
        m.write_cam_file(
            output,
            template,
            fields,
            timestamp,
            datetime(2008, 3, 9),
            source_paths,
        )
