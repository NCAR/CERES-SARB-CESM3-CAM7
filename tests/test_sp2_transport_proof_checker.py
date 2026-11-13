from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import netCDF4 as nc
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sp2_tests" / "check_transport_proof.py"


def _load_module():
    assert SCRIPT.exists(), "Task 11 transport checker is missing"
    spec = importlib.util.spec_from_file_location("sp2_check_transport_proof", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_h0(path: Path, *, nudged: bool, late_mask_value: float = 0.0) -> None:
    aod = np.full((4, 2, 3), 0.1, dtype="f4")
    mask = np.zeros((4, 2, 3), dtype="f4")
    if nudged:
        aod[0:2, 0, 0:2] = 0.8
        aod[2:, 0, 2] = 0.3
        mask[0:2, 0, 0:2] = 1.0
        mask[2:, :, :] = late_mask_value

    with nc.Dataset(path, "w") as ds:
        ds.createDimension("time", 4)
        ds.createDimension("lat", 2)
        ds.createDimension("lon", 3)
        ds.createVariable("lat", "f4", ("lat",))[:] = [30.0, 50.0]
        ds.createVariable("lon", "f4", ("lon",))[:] = [170.0, 190.0, 230.0]
        ds.createVariable("AODVIS", "f4", ("time", "lat", "lon"))[:] = aod
        if nudged:
            ds.createVariable("AODNDG_MASK", "f4", ("time", "lat", "lon"))[:] = mask


def _write_pulse_obs(path: Path) -> None:
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat", 2)
        ds.createDimension("lon", 3)
        ds.createVariable("aod_weighted_mean", "f4", ("lat", "lon"), fill_value=np.float32(-999.0))[:] = [
            [1.0, 1.0, -999.0],
            [-999.0, -999.0, -999.0],
        ]


def test_transport_checker_passes_when_anomaly_moves_outside_original_mask(tmp_path):
    module = _load_module()
    nudged = tmp_path / "nudged.nc"
    free = tmp_path / "free.nc"
    obs = tmp_path / "obs.nc"
    _write_h0(nudged, nudged=True)
    _write_h0(free, nudged=False)
    _write_pulse_obs(obs)

    metrics = module.transport_metrics(nudged, free, obs, post_start_index=2)

    assert metrics["post_mask_max"] == 0.0
    assert metrics["outside_abs_max"] > 0.0
    assert metrics["outside_frac"] > 0.0
    assert module.proof_passes(metrics, outside_frac_min=0.2, outside_max_min=0.01)


def test_transport_checker_fails_when_late_nudging_mask_is_nonzero(tmp_path):
    module = _load_module()
    nudged = tmp_path / "nudged.nc"
    free = tmp_path / "free.nc"
    obs = tmp_path / "obs.nc"
    _write_h0(nudged, nudged=True, late_mask_value=0.25)
    _write_h0(free, nudged=False)
    _write_pulse_obs(obs)

    metrics = module.transport_metrics(nudged, free, obs, post_start_index=2)

    assert metrics["post_mask_max"] == 0.25
    assert not module.proof_passes(metrics, outside_frac_min=0.2, outside_max_min=0.01)


def test_transport_checker_accepts_separate_diag_file(tmp_path):
    module = _load_module()
    nudged = tmp_path / "nudged_aod.nc"
    diag = tmp_path / "nudged_diag.nc"
    free = tmp_path / "free.nc"
    obs = tmp_path / "obs.nc"
    _write_h0(nudged, nudged=True)
    _write_h0(diag, nudged=True)
    _write_h0(free, nudged=False)
    _write_pulse_obs(obs)

    metrics = module.transport_metrics(
        nudged,
        free,
        obs,
        nudged_diag_h0=diag,
        post_start_index=2,
    )

    assert metrics["post_mask_max"] == 0.0
    assert module.proof_passes(metrics, outside_frac_min=0.2, outside_max_min=0.01)
