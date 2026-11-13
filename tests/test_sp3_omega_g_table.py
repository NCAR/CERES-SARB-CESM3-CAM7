from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr


MAM_LFL_ROOT = Path(__file__).resolve().parents[1].parent / "CERES-SARB-MAM-LFL"
if str(MAM_LFL_ROOT) not in sys.path:
    sys.path.insert(0, str(MAM_LFL_ROOT))

from mie_lognormal import mode_averaged_cross_sections_um2  # noqa: E402


def _legacy_fixed_index_table(n_quad: int) -> tuple[np.ndarray, np.ndarray]:
    cam_lw_edges_cm = np.array(
        [
            10.0,
            250.0,
            500.0,
            630.0,
            700.0,
            820.0,
            980.0,
            1080.0,
            1180.0,
            1390.0,
            1480.0,
            1800.0,
            2080.0,
            2250.0,
            2390.0,
            2600.0,
            3250.0,
        ],
        dtype=np.float64,
    )
    cam_lw_mid_um = 1.0e4 / (0.5 * (cam_lw_edges_cm[:-1] + cam_lw_edges_cm[1:]))
    sigma_g = np.array([1.8, 1.6, 1.8, 1.6], dtype=np.float64)
    median_radius_um = np.array([0.058, 0.013, 0.65, 0.026], dtype=np.float64)
    omega = np.zeros((16, 4), dtype=np.float32)
    asym = np.zeros((16, 4), dtype=np.float32)
    for iband, wavelength in enumerate(cam_lw_mid_um):
        for imode, (radius, sigma) in enumerate(zip(median_radius_um, sigma_g)):
            mie = mode_averaged_cross_sections_um2(
                1.55,
                0.003,
                float(radius),
                float(sigma),
                float(wavelength),
                n_quad=n_quad,
                n_sigma=4.0,
            )
            ext = max(float(mie["ext"]), 0.0)
            sca = max(float(mie["sca"]), 0.0)
            omega[iband, imode] = np.float32(min(0.9, sca / ext if ext > 0.0 else 0.0))
            asym[iband, imode] = np.float32(np.clip(float(mie["asymmetry"]), -1.0, 1.0))
    return omega, asym


def test_physical_table_uses_real_mie_with_bounds_and_coarse_dominance() -> None:
    from sp3_optics.make_omega_g_table import build_physical_table

    table = build_physical_table(n_quad=8)

    assert table.omega.shape == (16, 4)
    assert table.g.shape == (16, 4)
    assert np.all(table.omega >= 0.0)
    assert np.all(table.omega <= 0.9)
    assert np.all(table.g >= -1.0)
    assert np.all(table.g <= 1.0)

    window_bands = np.array([5, 6, 7])
    coarse_sca = table.sca_um2[window_bands, 2]
    noncoarse_sca = np.sum(table.sca_um2[window_bands], axis=1) - coarse_sca
    assert np.all(coarse_sca > noncoarse_sca)


def test_physical_table_differs_from_legacy_fixed_index_in_window_bands() -> None:
    from sp3_optics.make_omega_g_table import build_physical_table

    table = build_physical_table(n_quad=8)
    legacy_omega, _legacy_g = _legacy_fixed_index_table(n_quad=8)

    window_bands = np.array([5, 6, 7])
    assert np.max(np.abs(table.omega[window_bands] - legacy_omega[window_bands])) > 0.05


def test_legacy_script_delegates_to_sp3_optics_generator() -> None:
    import sp3_optics.make_omega_g_table as current
    import sp3_tests.make_omega_g_table as legacy

    assert legacy.main is current.main
    assert legacy.physical_table is current.physical_table
    assert 2390.0 in legacy.CAM_LW_EDGES_CM
    assert 2680.0 in legacy.CAM_LW_EDGES_CM
    assert 2380.0 not in legacy.CAM_LW_EDGES_CM
    assert 2600.0 not in legacy.CAM_LW_EDGES_CM


def test_legacy_script_is_directly_executable() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(repo_root / "sp3_tests" / "make_omega_g_table.py"),
            "--help",
        ],
        cwd=repo_root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "--omega-zero" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_physical_cli_rejects_invalid_quadrature_before_writing(tmp_path) -> None:
    from sp3_optics.make_omega_g_table import main

    output = tmp_path / "bad_nquad.nc"

    with pytest.raises(SystemExit, match="--n-quad must be >= 2"):
        main(["--output", str(output), "--n-quad", "1"])

    assert not output.exists()


def test_physical_cli_rejects_nonfinite_outputs_before_writing(tmp_path, monkeypatch) -> None:
    import sp3_optics.make_omega_g_table as generator

    output = tmp_path / "bad_nonfinite.nc"

    def bad_physical_table(_n_quad: int) -> tuple[np.ndarray, np.ndarray]:
        return np.full((16, 4), np.nan, dtype=np.float32), np.zeros((16, 4), dtype=np.float32)

    monkeypatch.setattr(generator, "physical_table", bad_physical_table)

    with pytest.raises(SystemExit, match="omega_lw and g_lw must be finite"):
        generator.main(["--output", str(output), "--n-quad", "2"])

    assert not output.exists()


def test_physical_output_attrs_document_sources_and_assumptions(tmp_path) -> None:
    from sp3_optics.make_omega_g_table import main

    output = tmp_path / "aod_lw_omega_g.nc"

    assert main(["--output", str(output), "--n-quad", "8"]) == 0

    with xr.open_dataset(output) as ds:
        attrs = ds.attrs
        assert "mode_physics.mix_mode_state" in attrs["wet_state_source"]
        assert "mie_lognormal.mode_averaged_cross_sections_um2" in attrs["mie_source"]
        assert "/glade/work/fillmore/Data/Optics/MERRA2" in attrs["refindex_source"]
        assert "rrtmgp-gas-lw-g128.nc:bnd_limits_wavenumber" in attrs["cam_lw_edges_source"]
        assert len(attrs["cam_lw_coeff_sha256"]) == 64
        assert attrs["generator"] == "sp3_optics.make_omega_g_table"
        assert attrs["generator_git_commit"]
        assert attrs["mam_lfl_git_commit"]
        assert attrs["representative_modes_source"].startswith("documented T2")
        assert "representative_modes_json" in attrs
        assert "a3" in attrs["representative_modes_json"]
        assert "DU" in attrs["representative_modes_json"]
        assert "representative_rh" in attrs["representative_modes_json"]
        assert "mam_lfl_mode_species_json" in attrs
        assert "a2" in attrs["mam_lfl_mode_species_json"]
        assert "POM" in attrs["mam_lfl_mode_species_json"]


def test_mode_specs_read_cam_physprop_sigma_and_radius() -> None:
    from sp3_optics.make_omega_g_table import load_mode_specs

    specs = load_mode_specs()

    expected = {
        "a1": (1.6, 0.08012490249604053),
        "a2": (1.6, 0.010634848376916334),
        "a3": (1.8, 1.0),
        "a4": (1.600000023841858, 0.015811388345181983),
    }
    assert tuple(specs) == tuple(expected)
    for mode, (sigma_g, radius_um) in expected.items():
        assert specs[mode].sigma_g == pytest.approx(sigma_g)
        assert specs[mode].dry_radius_um == pytest.approx(radius_um)
        assert specs[mode].physprop_path.exists()


def test_cam_lw_edges_use_runtime_rrtmgp_coefficients(tmp_path) -> None:
    from sp3_optics.make_omega_g_table import CAM_LW_EDGES_CM
    from sp3_optics.make_omega_g_table import CAM_RRTMGP_LW_COEFF_PATH
    from sp3_optics.make_omega_g_table import main

    expected = np.array(
        [
            10.0,
            250.0,
            500.0,
            630.0,
            700.0,
            820.0,
            980.0,
            1080.0,
            1180.0,
            1390.0,
            1480.0,
            1800.0,
            2080.0,
            2250.0,
            2390.0,
            2680.0,
            3250.0,
        ],
        dtype=np.float64,
    )

    assert CAM_RRTMGP_LW_COEFF_PATH.exists()
    assert np.array_equal(CAM_LW_EDGES_CM, expected)
    assert 2380.0 not in CAM_LW_EDGES_CM
    assert 2600.0 not in CAM_LW_EDGES_CM

    output = tmp_path / "aod_lw_omega_g_zero.nc"
    main(["--omega-zero", "--output", str(output)])

    with xr.open_dataset(output) as ds:
        edges = np.r_[
            ds["cam_lw_wavenumber_low_cm1"].values,
            ds["cam_lw_wavenumber_high_cm1"].values[-1:],
        ]
        assert np.array_equal(edges, expected.astype(np.float32))


def test_zero_table_writes_zero_omega_and_g(tmp_path) -> None:
    from sp3_optics.make_omega_g_table import main

    output = tmp_path / "aod_lw_omega_g_zero.nc"

    assert main(["--omega-zero", "--output", str(output)]) == 0

    with xr.open_dataset(output) as ds:
        assert ds["omega_lw"].shape == (16, 4)
        assert ds["g_lw"].shape == (16, 4)
        assert np.all(ds["omega_lw"].values == 0.0)
        assert np.all(ds["g_lw"].values == 0.0)
        assert int(ds.attrs["omega_zero"]) == 1
        assert "rrtmgp-gas-lw-g128.nc:bnd_limits_wavenumber" in ds.attrs["cam_lw_edges_source"]
        assert len(ds.attrs["cam_lw_coeff_sha256"]) == 64
        assert ds.attrs["generator"] == "sp3_optics.make_omega_g_table"
