from datetime import date, datetime

import netCDF4 as nc
import numpy as np

from sp1_aod_pipeline.__main__ import main
from sp1_aod_pipeline.bias import identity
from sp1_aod_pipeline.config import RunConfig
from sp1_aod_pipeline.contract import contract_filename, validate_contract_file
from sp1_aod_pipeline.f09_grid import f09_lat, f09_lon
from sp1_aod_pipeline.pipeline import process_window, run
from sp1_aod_pipeline.records import L2Record
from sp1_aod_pipeline.tests.fixtures import make_modis_granule, make_viirs_granule


def _cfg(tmp_path):
    modis_dir = tmp_path / "modis"
    viirs_dir = tmp_path / "viirs"
    out_dir = tmp_path / "out"
    for path in (modis_dir, viirs_dir, out_dir):
        path.mkdir()
    return RunConfig(
        modis_dir=str(modis_dir),
        viirs_dir=str(viirs_dir),
        out_dir=str(out_dir),
        start=date(2020, 6, 15),
        end=date(2020, 6, 15),
    )


def test_process_window_viirs_and_modis(tmp_path):
    cfg = _cfg(tmp_path)
    latc = float(f09_lat()[96])
    lonc = float(f09_lon()[1])
    scan = datetime(2020, 6, 15, 1, 0, 0)
    make_viirs_granule(
        str(tmp_path / "viirs" / "AERDB_L2_VIIRS_NOAA20.A2020167.0100.002.x.nc"),
        lat=np.array([[latc]], np.float32),
        lon=np.array([[lonc]], np.float32),
        aod_land=np.array([[0.50]], np.float32),
        qa_land=np.array([[3.0]]),
        eu_land=np.array([[0.10]], np.float32),
        scan_dt=scan,
    )
    make_modis_granule(
        str(tmp_path / "modis" / "MOD04_L2.A2020167.0100.061.nc"),
        lat=np.array([[latc]], np.float32),
        lon=np.array([[lonc]], np.float32),
        aod=np.array([[0.70]]),
        qa=np.array([[3]]),
        alg=np.array([[1]]),
        scan_dt=scan,
    )

    out = process_window(cfg, date(2020, 6, 15), 0, identity())

    assert out.endswith(contract_filename(datetime(2020, 6, 15, 0, 0, 0)))
    ok, errors = validate_contract_file(out)
    assert ok, errors
    ds = nc.Dataset(out)
    ds.set_auto_mask(False)
    try:
        viirs_weight = 1 / 0.10**2
        modis_weight = 1 / 0.155**2
        expected = (viirs_weight * 0.50 + modis_weight * 0.70) / (
            viirs_weight + modis_weight
        )
        assert np.isclose(float(ds["aod_weighted_mean"][96, 1]), expected, atol=1e-3)
        assert int(ds["aod_count"][96, 1]) == 2
        assert float(ds["aod_weighted_mean"][0, 0]) == -999.0
        assert ds.getncattr("qc_thresholds") != "unset"
        assert ds.getncattr("git_commit") != ""
    finally:
        ds.close()


def test_process_window_no_data_writes_all_fill(tmp_path):
    cfg = _cfg(tmp_path)

    out = process_window(cfg, date(2020, 6, 15), 5, identity())

    ds = nc.Dataset(out)
    ds.set_auto_mask(False)
    try:
        assert float(ds["aod_weighted_mean"][:].min()) == -999.0
        assert int(ds["aod_count"][:].max()) == 0
    finally:
        ds.close()


def test_cli_validate_accepts_contract_file(tmp_path, capsys):
    cfg = _cfg(tmp_path)
    out = process_window(cfg, date(2020, 6, 15), 0, identity())

    main(["validate", out])

    captured = capsys.readouterr()
    assert f"OK {out}" in captured.out


def test_run_reads_daily_granules_once_per_day(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    path = tmp_path / "modis" / "MOD04_L2.A2020167.0100.061.nc"
    path.write_text("placeholder")
    calls = []
    latc = float(f09_lat()[96])
    lonc = float(f09_lon()[1])
    times = np.array(
        [datetime(2020, 6, 15, hour, 30) for hour in range(0, 24, 3)],
        dtype="datetime64[ns]",
    )

    def fake_reader(granule_path, run_config):
        calls.append(granule_path)
        n = len(times)
        return L2Record(
            sensor="modis",
            lat=np.full(n, latc, dtype=np.float32),
            lon=np.full(n, lonc, dtype=np.float32),
            aod=np.full(n, 0.5, dtype=np.float32),
            sigma=np.full(n, 0.1, dtype=np.float32),
            qa=np.full(n, 3.0, dtype=np.float32),
            time=times,
        )

    monkeypatch.setattr("sp1_aod_pipeline.pipeline.read_modis_granule", fake_reader)

    outputs = run(cfg)

    assert len(outputs) == 8
    assert calls == [str(path)]
