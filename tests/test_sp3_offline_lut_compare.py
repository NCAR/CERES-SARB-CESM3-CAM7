from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr


def _a1_species_fields(template: np.ndarray, *, so4_mass: float | np.ndarray) -> dict[str, tuple[tuple[str, ...], np.ndarray]]:
    values = np.asarray(so4_mass, dtype=np.float64)
    if values.shape == ():
        values = np.full_like(template, float(values))
    zeros = np.zeros_like(template, dtype=np.float64)
    return {
        "so4_a1": (("time", "lev", "lat", "lon"), values),
        "pom_a1": (("time", "lev", "lat", "lon"), zeros.copy()),
        "soa_a1": (("time", "lev", "lat", "lon"), zeros.copy()),
        "bc_a1": (("time", "lev", "lat", "lon"), zeros.copy()),
        "dst_a1": (("time", "lev", "lat", "lon"), zeros.copy()),
        "ncl_a1": (("time", "lev", "lat", "lon"), zeros.copy()),
    }


def _write_minimal_lut(path: Path) -> None:
    ncoef = 2
    coords = {
        "sw_band": [1],
        "lw_band": [1],
        "mode": ["a1"],
        "refindex_im": [1, 2],
        "refindex_real": [1, 2],
        "coef_number": [1, 2],
        "spectype": ["BC", "POM", "SOA", "SU", "DU", "SS", "WAT"],
        "lfl_sw_band": [1],
        "lfl_lw_band": [1],
    }
    coeff_shape = (1, 1, 2, 2, ncoef)
    ext = np.zeros(coeff_shape, dtype=np.float64)
    absn = np.zeros(coeff_shape, dtype=np.float64)
    asm = np.zeros(coeff_shape, dtype=np.float64)
    ext[..., 0] = 2.0 * np.log(2.0)
    absn[..., 0] = 2.0 * 0.5
    asm[..., 0] = 2.0 * 0.25
    ds = xr.Dataset(
        {
            "extpsw": (("sw_band", "mode", "refindex_im", "refindex_real", "coef_number"), ext),
            "abspsw": (("sw_band", "mode", "refindex_im", "refindex_real", "coef_number"), absn),
            "asmpsw": (("sw_band", "mode", "refindex_im", "refindex_real", "coef_number"), asm),
            "extplw": (("lw_band", "mode", "refindex_im", "refindex_real", "coef_number"), ext.copy()),
            "absplw": (("lw_band", "mode", "refindex_im", "refindex_real", "coef_number"), absn.copy()),
            "asmplw": (("lw_band", "mode", "refindex_im", "refindex_real", "coef_number"), asm.copy()),
            "refindex_real_sw": (("sw_band", "mode", "refindex_real"), np.asarray([[[1.0, 2.0]]])),
            "refindex_im_sw": (("sw_band", "mode", "refindex_im"), np.asarray([[[0.0, 1.0]]])),
            "refindex_real_lw": (("lw_band", "mode", "refindex_real"), np.asarray([[[1.0, 2.0]]])),
            "refindex_im_lw": (("lw_band", "mode", "refindex_im"), np.asarray([[[0.0, 1.0]]])),
            "sigmag": (("mode",), np.asarray([1.6])),
            "refindex_real_spectype_sw": (
                ("spectype", "lfl_sw_band"),
                np.asarray([[1.0], [1.0], [1.0], [1.5], [1.0], [1.0], [1.33]]),
            ),
            "refindex_im_spectype_sw": (
                ("spectype", "lfl_sw_band"),
                np.asarray([[0.0], [0.0], [0.0], [0.2], [0.0], [0.0], [0.0]]),
            ),
            "refindex_real_spectype_lw": (
                ("spectype", "lfl_lw_band"),
                np.asarray([[1.0], [1.0], [1.0], [1.5], [1.0], [1.0], [1.33]]),
            ),
            "refindex_im_spectype_lw": (
                ("spectype", "lfl_lw_band"),
                np.asarray([[0.0], [0.0], [0.0], [0.2], [0.0], [0.0], [0.0]]),
            ),
        },
        coords=coords,
    )
    ds.to_netcdf(path)


def _write_minimal_h0(path: Path, *, layer_ext: float, layer_sca: float, asm: float) -> None:
    pdel = np.asarray([[[[980.665]]]], dtype=np.float64)
    dry_volume = 1.0e-12
    so4 = dry_volume * 1770.0
    surface_radius = 0.2e-6
    sigma_g = 1.6
    dgnumwet = 2.0 * surface_radius / np.exp(2.0 * np.log(sigma_g) ** 2)
    template = np.zeros((1, 1, 1, 1), dtype=np.float64)
    ds = xr.Dataset(
        {
            "PDELDRY": (("time", "lev", "lat", "lon"), pdel),
            **_a1_species_fields(template, so4_mass=so4),
            "rad_dgnumwet_1": (("time", "lev", "lat", "lon"), np.asarray([[[[dgnumwet]]]], dtype=np.float64)),
            "rad_qaerwat_1": (("time", "lev", "lat", "lon"), np.zeros((1, 1, 1, 1), dtype=np.float64)),
            "date": (("time",), np.asarray([20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800], dtype=np.int32)),
        },
        coords={"time": [0.0], "lev": [1], "lat": [0.0], "lon": [0.0]},
    )
    ds.attrs["expected_layer_ext"] = layer_ext
    ds.attrs["expected_layer_sca"] = layer_sca
    ds.attrs["expected_asm"] = asm
    ds.to_netcdf(path)


def _write_sp3(path: Path, *, layer_ext: float, layer_sca: float, asm: float) -> None:
    ds = xr.Dataset(
        {
            "DELP": (("lev", "lat", "lon"), np.asarray([[[980.665]]], dtype=np.float64)),
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[layer_ext]]], dtype=np.float64)),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[layer_sca]]], dtype=np.float64)),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), np.asarray([[[asm]]], dtype=np.float64)),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[layer_ext]], dtype=np.float64)),
        },
        coords={"lev": [1], "lat": [0.0], "lon": [0.0]},
    )
    ds.to_netcdf(path)


def _write_minimal_fine_lut(path: Path) -> None:
    ds = xr.Dataset(
        {
            "ext": (("n_real", "n_imag", "radius"), np.asarray([[[4.0]]], dtype=np.float64)),
            "abs": (("n_real", "n_imag", "radius"), np.asarray([[[1.0]]], dtype=np.float64)),
            "asm": (("n_real", "n_imag", "radius"), np.asarray([[[0.25]]], dtype=np.float64)),
        },
        coords={"n_real": [1.5], "n_imag": [0.2], "radius": [0.1]},
    )
    ds.to_netcdf(path)


def test_mam_lfl_fine_lut_reconstruction_uses_number_cross_section_normalization(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import STANDARD_GRAVITY
    from sp3_tests.compare_offline_lut import reconstruct_band_mam_lfl_fine

    lut_path = tmp_path / "lut.nc"
    fine_dir = tmp_path / "fine"
    fine_dir.mkdir()
    _write_minimal_lut(lut_path)
    _write_minimal_fine_lut(fine_dir / "mam4_mode1_sw1_larc_c000003.v2.nc")
    number = 2.0e9
    pdel = STANDARD_GRAVITY
    so4 = 1.0e-12 * 1770.0
    h0 = xr.Dataset(
        {
            "PDELDRY": (("time", "lev", "lat", "lon"), np.asarray([[[[pdel]]]], dtype=np.float64)),
            "num_a1": (("time", "lev", "lat", "lon"), np.asarray([[[[number]]]], dtype=np.float64)),
            **_a1_species_fields(np.zeros((1, 1, 1, 1), dtype=np.float64), so4_mass=so4),
            "rad_dgnumwet_1": (("time", "lev", "lat", "lon"), np.asarray([[[[0.2e-6]]]], dtype=np.float64)),
            "rad_qaerwat_1": (("time", "lev", "lat", "lon"), np.zeros((1, 1, 1, 1), dtype=np.float64)),
            "date": (("time",), np.asarray([20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800], dtype=np.int32)),
        },
        coords={"time": [0.0], "lev": [1], "lat": [0.0], "lon": [0.0]},
    )

    with xr.open_dataset(lut_path) as lut:
        offline = reconstruct_band_mam_lfl_fine(
            lut,
            h0,
            "SW01",
            stamp="20080701.10800",
            fine_lut_dir=fine_dir,
        )

    expected_ext = 4.0e-12 * number
    expected_abs = 1.0e-12 * number
    np.testing.assert_allclose(offline["Extinction_Layer_Optical_Depth"], [[[expected_ext]]])
    np.testing.assert_allclose(offline["Scattering_Layer_Optical_Depth"], [[[expected_ext - expected_abs]]])
    np.testing.assert_allclose(offline["Layer_Asymmetry_Parameter"], [[[0.25]]])


def test_eval_coeff_table_uses_cam_half_weight_and_bilinear_interpolation() -> None:
    from sp3_tests.compare_offline_lut import cheb_basis
    from sp3_tests.compare_offline_lut import eval_coeff_table

    basis = cheb_basis(0.2e-6, 2)
    table = np.zeros((2, 2, 2), dtype=np.float64)
    table[:, :, 0] = 2.0
    table[:, :, 1] = 4.0

    value = eval_coeff_table(table, basis, np.asarray([1.0, 2.0]), np.asarray([0.0, 1.0]), 1.5, 0.5)

    assert value == pytest.approx(1.0 + 4.0 * basis[1])


def test_cam_species_map_and_densities_match_t9_mode_defs() -> None:
    from sp3_tests.compare_offline_lut import MODE_SPECIES
    from sp3_tests.compare_offline_lut import SPECIES_DENSITY_KG_M3

    assert ("dst_a2", "DU") in MODE_SPECIES["a2"]
    assert SPECIES_DENSITY_KG_M3 == {
        "BC": 1700.0,
        "POM": 1000.0,
        "SOA": 1000.0,
        "SU": 1770.0,
        "DU": 2600.0,
        "SS": 1900.0,
    }


def test_offline_band_metric_fails_large_gated_asymmetry_outlier(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import _metric_for_band

    offline = xr.Dataset(
        {
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[1.0, 1.0, 1.0]]])),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[0.5, 0.5, 0.5]]])),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), np.asarray([[[0.1, 0.1, 0.9]]])),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[1.0, 1.0, 1.0]])),
        }
    )
    sp3 = offline.copy(deep=True)
    sp3["Layer_Asymmetry_Parameter"].values[:] = np.asarray([[[0.1, 0.1, 0.1]]])

    metric = _metric_for_band(
        offline,
        sp3,
        "LW06",
        "20080701.10800",
        min_tau=1.0e-3,
        min_scattering_tau=1.0e-8,
        ext_ratio_tolerance=0.10,
        ssa_tolerance=0.02,
        asymmetry_tolerance=0.05,
    )

    assert metric.median_abs_asymmetry_difference == pytest.approx(0.0)
    assert metric.max_abs_asymmetry_difference == pytest.approx(0.8)
    assert not metric.passed


def test_offline_band_metric_fails_large_gated_ssa_outlier(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import _metric_for_band

    offline = xr.Dataset(
        {
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[1.0, 1.0, 1.0]]])),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[0.5, 0.5, 0.9]]])),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), np.asarray([[[0.1, 0.1, 0.1]]])),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[1.0, 1.0, 1.0]])),
        }
    )
    sp3 = offline.copy(deep=True)
    sp3["Scattering_Layer_Optical_Depth"].values[:] = np.asarray([[[0.5, 0.5, 0.5]]])

    metric = _metric_for_band(
        offline,
        sp3,
        "SW05",
        "20080701.10800",
        min_tau=1.0e-3,
        min_scattering_tau=1.0e-8,
        ext_ratio_tolerance=0.10,
        ssa_tolerance=0.02,
        asymmetry_tolerance=0.05,
    )

    assert metric.median_abs_ssa_difference == pytest.approx(0.0)
    assert metric.max_abs_ssa_difference == pytest.approx(0.4)
    assert not metric.passed


def test_offline_band_metric_fails_balanced_large_extinction_errors(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import _metric_for_band

    offline = xr.Dataset(
        {
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[0.5, 1.5]]])),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[0.25, 0.75]]])),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), np.asarray([[[0.1, 0.1]]])),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[0.5, 1.5]])),
        }
    )
    sp3 = xr.Dataset(
        {
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[1.0, 1.0]]])),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[0.5, 0.5]]])),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), np.asarray([[[0.1, 0.1]]])),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[1.0, 1.0]])),
        }
    )

    metric = _metric_for_band(
        offline,
        sp3,
        "SW05",
        "20080701.10800",
        min_tau=1.0e-3,
        min_scattering_tau=1.0e-8,
        ext_ratio_tolerance=0.10,
        ssa_tolerance=0.02,
        asymmetry_tolerance=0.05,
    )

    assert metric.median_ext_ratio == pytest.approx(1.0)
    assert metric.median_abs_ext_relative_difference == pytest.approx(0.5)
    assert not metric.passed


def test_offline_band_metric_excludes_low_scattering_ssa_outlier(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import _metric_for_band

    offline = xr.Dataset(
        {
            "Extinction_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[1.0, 1.0, 0.0011]]])),
            "Scattering_Layer_Optical_Depth": (("lev", "lat", "lon"), np.asarray([[[0.5, 0.5, 0.0014]]])),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), np.asarray([[[0.1, 0.1, 0.1]]])),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[1.0, 1.0, 0.0011]])),
        }
    )
    sp3 = offline.copy(deep=True)
    sp3["Scattering_Layer_Optical_Depth"].values[:] = np.asarray([[[0.5, 0.5, 0.0]]])

    metric = _metric_for_band(
        offline,
        sp3,
        "SW05",
        "20080701.10800",
        min_tau=1.0e-3,
        min_scattering_tau=1.5e-3,
        ext_ratio_tolerance=0.10,
        ssa_tolerance=0.02,
        asymmetry_tolerance=0.05,
    )

    assert metric.count == 3
    assert metric.ssa_count == 2
    assert metric.max_abs_ssa_difference == pytest.approx(0.0)
    assert metric.passed


def test_compare_offline_to_sp3_accepts_matching_synthetic_snapshot(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import compare_offline_to_sp3

    lut = tmp_path / "lut.nc"
    h0 = tmp_path / "h0.nc"
    sp3_dir = tmp_path / "sp3"
    sp3_dir.mkdir()
    _write_minimal_lut(lut)
    layer_ext = 2.0e-7
    layer_sca = 1.5e-7
    asm = 0.25
    _write_minimal_h0(h0, layer_ext=layer_ext, layer_sca=layer_sca, asm=asm)
    _write_sp3(sp3_dir / "AER_MAM4_SW01.20080701.10800.nc", layer_ext=layer_ext, layer_sca=layer_sca, asm=asm)

    metrics = compare_offline_to_sp3(
        lut_file=lut,
        h0_file=h0,
        sp3_dir=sp3_dir,
        bands=("SW01",),
        stamp="20080701.10800",
        min_tau=1.0e-12,
        min_scattering_tau=1.0e-12,
    )

    assert len(metrics) == 1
    row = metrics[0]
    assert row.band == "SW01"
    assert row.passed
    assert row.median_ext_ratio == pytest.approx(1.0)
    assert row.max_abs_ssa_difference == pytest.approx(0.0, abs=1.0e-12)
    assert row.max_abs_asymmetry_difference == pytest.approx(0.0, abs=1.0e-12)


def test_select_sample_columns_uses_sp3_column_tau_quantiles() -> None:
    from sp3_tests.compare_offline_lut import _select_sample_columns

    sp3 = xr.Dataset(
        {
            "Extinction_Column_Optical_Depth": (
                ("lat", "lon"),
                np.asarray(
                    [
                        [0.0, 4.0, 2.0],
                        [7.0, np.nan, 5.0],
                    ],
                    dtype=np.float64,
                ),
            )
        }
    )

    assert _select_sample_columns(sp3, sample_columns=3, min_tau=1.0e-3) == [(0, 2), (0, 1), (1, 0)]


def test_direct_mie_sampled_reconstruction_uses_number_cross_section_normalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sp3_tests.compare_offline_lut as compare
    from sp3_optics.lfl_bands import LFL_SW_MIDPOINTS_UM
    from sp3_tests.compare_offline_lut import DIRECT_NORMALIZATION_NUMBER
    from sp3_tests.compare_offline_lut import STANDARD_GRAVITY
    from sp3_tests.compare_offline_lut import reconstruct_band_mam_lfl_direct_mie_sampled

    calls = []

    def fake_mode_average(
        n_real: float,
        n_imag: float,
        *,
        median_radius_um: float,
        sigma_g: float,
        wavelength_um: float,
        n_quad: int,
        n_sigma: float,
    ) -> dict[str, float]:
        calls.append((n_real, n_imag, median_radius_um, sigma_g, wavelength_um, n_quad, n_sigma))
        return {"ext": 4.0, "sca": 3.0, "abs": 1.0, "asymmetry": 0.25}

    monkeypatch.setattr(compare, "_mode_averaged_cross_sections_um2_capped", fake_mode_average)
    lut_path = tmp_path / "lut.nc"
    _write_minimal_lut(lut_path)
    numbers = np.asarray([[[[2.0e9, 3.0e9]]]], dtype=np.float64)
    so4 = np.full_like(numbers, 1.0e-12 * 1770.0)
    h0 = xr.Dataset(
        {
            "PDELDRY": (("time", "lev", "lat", "lon"), np.full_like(numbers, STANDARD_GRAVITY)),
            "num_a1": (("time", "lev", "lat", "lon"), numbers),
            **_a1_species_fields(numbers, so4_mass=so4),
            "rad_dgnumwet_1": (("time", "lev", "lat", "lon"), np.full_like(numbers, 0.2e-6)),
            "rad_qaerwat_1": (("time", "lev", "lat", "lon"), np.zeros_like(numbers)),
            "date": (("time",), np.asarray([20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800], dtype=np.int32)),
        },
        coords={"time": [0.0], "lev": [1], "lat": [0.0], "lon": [0.0, 1.0]},
    )
    sp3 = xr.Dataset(
        {
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[1.0, 2.0]], dtype=np.float64))
        },
        coords={"lat": [0.0], "lon": [0.0, 1.0]},
    )

    with xr.open_dataset(lut_path) as lut:
        offline, sampled_sp3 = reconstruct_band_mam_lfl_direct_mie_sampled(
            lut,
            h0,
            sp3,
            "SW01",
            stamp="20080701.10800",
            sample_columns=2,
            min_tau=1.0e-3,
            n_quad=17,
            n_sigma=4.5,
            normalization=DIRECT_NORMALIZATION_NUMBER,
        )

    expected_ext = np.asarray([[4.0e-12 * 2.0e9, 4.0e-12 * 3.0e9]], dtype=np.float64)
    expected_sca = np.asarray([[3.0e-12 * 2.0e9, 3.0e-12 * 3.0e9]], dtype=np.float64)
    np.testing.assert_allclose(offline["Extinction_Layer_Optical_Depth"], expected_ext)
    np.testing.assert_allclose(offline["Scattering_Layer_Optical_Depth"], expected_sca)
    np.testing.assert_allclose(offline["Layer_Asymmetry_Parameter"], np.asarray([[0.25, 0.25]]))
    np.testing.assert_allclose(offline["Extinction_Column_Optical_Depth"], expected_ext[0])
    np.testing.assert_allclose(sampled_sp3["Extinction_Column_Optical_Depth"], np.asarray([1.0, 2.0]))
    assert offline["Extinction_Layer_Optical_Depth"].dims == ("lev", "sample")
    assert sampled_sp3["Extinction_Column_Optical_Depth"].dims == ("sample",)
    assert [call[4] for call in calls] == [pytest.approx(LFL_SW_MIDPOINTS_UM[0]), pytest.approx(LFL_SW_MIDPOINTS_UM[0])]
    assert [call[5:] for call in calls] == [(17, 4.5), (17, 4.5)]


def test_direct_mie_sampled_reconstruction_can_use_cam_wet_volume_normalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sp3_tests.compare_offline_lut as compare
    from sp3_tests.compare_offline_lut import STANDARD_GRAVITY
    from sp3_tests.compare_offline_lut import _mean_wet_volume_m3
    from sp3_tests.compare_offline_lut import reconstruct_band_mam_lfl_direct_mie_sampled

    def fake_mode_average(*_args: object, **_kwargs: object) -> dict[str, float]:
        return {"ext": 4.0, "sca": 3.0, "abs": 1.0, "asymmetry": 0.25}

    monkeypatch.setattr(compare, "_mode_averaged_cross_sections_um2_capped", fake_mode_average)
    lut_path = tmp_path / "lut.nc"
    _write_minimal_lut(lut_path)
    dryvol = np.asarray([[[[1.0e-12, 2.0e-12]]]], dtype=np.float64)
    h0 = xr.Dataset(
        {
            "PDELDRY": (("time", "lev", "lat", "lon"), np.full_like(dryvol, STANDARD_GRAVITY)),
            **_a1_species_fields(dryvol, so4_mass=dryvol * 1770.0),
            "rad_dgnumwet_1": (("time", "lev", "lat", "lon"), np.full_like(dryvol, 0.2e-6)),
            "rad_qaerwat_1": (("time", "lev", "lat", "lon"), np.zeros_like(dryvol)),
            "date": (("time",), np.asarray([20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800], dtype=np.int32)),
        },
        coords={"time": [0.0], "lev": [1], "lat": [0.0], "lon": [0.0, 1.0]},
    )
    sp3 = xr.Dataset(
        {
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[1.0, 2.0]], dtype=np.float64))
        },
        coords={"lat": [0.0], "lon": [0.0, 1.0]},
    )

    with xr.open_dataset(lut_path) as lut:
        offline, _sampled_sp3 = reconstruct_band_mam_lfl_direct_mie_sampled(
            lut,
            h0,
            sp3,
            "SW01",
            stamp="20080701.10800",
            sample_columns=2,
            min_tau=1.0e-3,
            n_quad=17,
            n_sigma=4.5,
        )

    sigma_g = 1.6
    surface_radius_um = 0.5 * 0.2e-6 * np.exp(2.0 * np.log(sigma_g) ** 2) * 1.0e6
    mean_volume = _mean_wet_volume_m3(surface_radius_um, sigma_g)
    expected_ext = 4.0e-12 * np.asarray([[1.0e-12, 2.0e-12]]) / mean_volume
    expected_sca = 3.0e-12 * np.asarray([[1.0e-12, 2.0e-12]]) / mean_volume
    np.testing.assert_allclose(offline["Extinction_Layer_Optical_Depth"], expected_ext)
    np.testing.assert_allclose(offline["Scattering_Layer_Optical_Depth"], expected_sca)
    assert offline.attrs["direct_normalization"] == "wet-volume"


def test_direct_mie_comparison_requires_sample_columns(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import REFERENCE_METHOD_MAM_LFL_DIRECT_MIE
    from sp3_tests.compare_offline_lut import compare_offline_to_sp3

    lut = tmp_path / "lut.nc"
    h0 = tmp_path / "h0.nc"
    sp3_dir = tmp_path / "sp3"
    sp3_dir.mkdir()
    _write_minimal_lut(lut)
    _write_minimal_h0(h0, layer_ext=1.0, layer_sca=0.5, asm=0.25)
    _write_sp3(sp3_dir / "AER_MAM4_SW01.20080701.10800.nc", layer_ext=1.0, layer_sca=0.5, asm=0.25)

    with pytest.raises(ValueError, match="direct_sample_columns"):
        compare_offline_to_sp3(
            lut_file=lut,
            h0_file=h0,
            sp3_dir=sp3_dir,
            bands=("SW01",),
            stamp="20080701.10800",
            reference_method=REFERENCE_METHOD_MAM_LFL_DIRECT_MIE,
            direct_sample_columns=0,
        )


def test_direct_mie_comparison_validates_quadrature_controls(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import REFERENCE_METHOD_MAM_LFL_DIRECT_MIE
    from sp3_tests.compare_offline_lut import compare_offline_to_sp3

    kwargs = dict(
        lut_file=tmp_path / "missing_lut.nc",
        h0_file=tmp_path / "missing_h0.nc",
        sp3_dir=tmp_path,
        bands=("SW01",),
        stamp="20080701.10800",
        reference_method=REFERENCE_METHOD_MAM_LFL_DIRECT_MIE,
        direct_sample_columns=1,
    )

    with pytest.raises(ValueError, match="direct_n_quad"):
        compare_offline_to_sp3(**kwargs, direct_n_quad=1)
    with pytest.raises(ValueError, match="direct_n_sigma"):
        compare_offline_to_sp3(**kwargs, direct_n_sigma=0.0)
    with pytest.raises(ValueError, match="direct_normalization"):
        compare_offline_to_sp3(**kwargs, direct_normalization="bad")


def test_direct_mie_comparison_records_sample_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sp3_tests.compare_offline_lut as compare
    from sp3_tests.compare_offline_lut import REFERENCE_METHOD_MAM_LFL_DIRECT_MIE
    from sp3_tests.compare_offline_lut import STANDARD_GRAVITY
    from sp3_tests.compare_offline_lut import compare_offline_to_sp3
    from sp3_tests.compare_offline_lut import write_outputs

    def fake_mode_average(*_args: object, **_kwargs: object) -> dict[str, float]:
        return {"ext": 4.0, "sca": 3.0, "abs": 1.0, "asymmetry": 0.25}

    monkeypatch.setattr(compare, "_mode_averaged_cross_sections_um2_capped", fake_mode_average)
    lut = tmp_path / "lut.nc"
    h0_path = tmp_path / "h0.nc"
    sp3_dir = tmp_path / "sp3"
    sp3_dir.mkdir()
    _write_minimal_lut(lut)
    numbers = np.asarray([[[[2.0e9, 3.0e9]]]], dtype=np.float64)
    so4 = np.full_like(numbers, 1.0e-12 * 1770.0)
    h0 = xr.Dataset(
        {
            "PDELDRY": (("time", "lev", "lat", "lon"), np.full_like(numbers, STANDARD_GRAVITY)),
            "num_a1": (("time", "lev", "lat", "lon"), numbers),
            **_a1_species_fields(numbers, so4_mass=so4),
            "rad_dgnumwet_1": (("time", "lev", "lat", "lon"), np.full_like(numbers, 0.2e-6)),
            "rad_qaerwat_1": (("time", "lev", "lat", "lon"), np.zeros_like(numbers)),
            "date": (("time",), np.asarray([20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800], dtype=np.int32)),
        },
        coords={"time": [0.0], "lev": [1], "lat": [0.0], "lon": [0.0, 1.0]},
    )
    h0.to_netcdf(h0_path)
    sp3 = xr.Dataset(
        {
            "Extinction_Layer_Optical_Depth": (
                ("lev", "lat", "lon"),
                np.asarray([[[0.008, 0.012]]], dtype=np.float64),
            ),
            "Scattering_Layer_Optical_Depth": (
                ("lev", "lat", "lon"),
                np.asarray([[[0.006, 0.009]]], dtype=np.float64),
            ),
            "Layer_Asymmetry_Parameter": (("lev", "lat", "lon"), np.asarray([[[0.25, 0.25]]], dtype=np.float64)),
            "Extinction_Column_Optical_Depth": (("lat", "lon"), np.asarray([[0.008, 0.012]], dtype=np.float64)),
        },
        coords={"lev": [1], "lat": [0.0], "lon": [0.0, 1.0]},
    )
    sp3.to_netcdf(sp3_dir / "AER_MAM4_SW01.20080701.10800.nc")

    metrics = compare_offline_to_sp3(
        lut_file=lut,
        h0_file=h0_path,
        sp3_dir=sp3_dir,
        bands=("SW01",),
        stamp="20080701.10800",
        reference_method=REFERENCE_METHOD_MAM_LFL_DIRECT_MIE,
        direct_sample_columns=2,
        direct_n_quad=17,
        min_tau=1.0e-12,
        min_scattering_tau=1.0e-12,
    )
    _, json_path = write_outputs(tmp_path / "out", metrics, reference_method=REFERENCE_METHOD_MAM_LFL_DIRECT_MIE)

    assert metrics[0].sample_count == 2
    assert metrics[0].sample_indices_json == "[[0, 0], [0, 1]]"
    assert metrics[0].direct_normalization == "wet-volume"
    payload = json_path.read_text(encoding="utf-8")
    assert '"sample_count": 2' in payload
    assert '"sample_indices_json": "[[0, 0], [0, 1]]"' in payload
    assert '"direct_normalization": "wet-volume"' in payload


def test_layer_mass_requires_dry_pressure_thickness() -> None:
    from sp3_tests.compare_offline_lut import _layer_mass_kg_m2

    h0 = xr.Dataset(
        {
            "PDEL": (("time", "lev", "lat", "lon"), np.ones((1, 1, 1, 1), dtype=np.float64)),
            "date": (("time",), np.asarray([20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800], dtype=np.int32)),
        }
    )

    with pytest.raises(KeyError, match="rad_pdeldry or PDELDRY"):
        _layer_mass_kg_m2(h0, "20080701.10800")


def test_reconstruction_requires_all_expected_mode_species(tmp_path: Path) -> None:
    from sp3_tests.compare_offline_lut import reconstruct_band

    lut_path = tmp_path / "lut.nc"
    _write_minimal_lut(lut_path)
    shape = (1, 1, 1, 1)
    h0 = xr.Dataset(
        {
            "PDELDRY": (("time", "lev", "lat", "lon"), np.ones(shape, dtype=np.float64)),
            "so4_a1": (("time", "lev", "lat", "lon"), np.ones(shape, dtype=np.float64)),
            "rad_dgnumwet_1": (("time", "lev", "lat", "lon"), np.full(shape, 0.2e-6, dtype=np.float64)),
            "rad_qaerwat_1": (("time", "lev", "lat", "lon"), np.zeros(shape, dtype=np.float64)),
            "date": (("time",), np.asarray([20080701], dtype=np.int32)),
            "datesec": (("time",), np.asarray([10800], dtype=np.int32)),
        },
        coords={"time": [0.0], "lev": [1], "lat": [0.0], "lon": [0.0]},
    )

    with xr.open_dataset(lut_path) as lut, pytest.raises(KeyError, match="pom_a1"):
        reconstruct_band(lut, h0, "SW01", stamp="20080701.10800")


def test_direct_mie_capped_reference_never_calls_mie_above_xcap(monkeypatch: pytest.MonkeyPatch) -> None:
    import sp3_tests.compare_offline_lut as compare
    from sp3_tests.compare_offline_lut import DIRECT_MIE_X_CAP
    from sp3_tests.compare_offline_lut import _mode_averaged_cross_sections_um2_capped

    calls: list[float] = []
    wavelength_um = 0.2

    def fake_cross_sections(_n_real: float, _n_imag: float, radius_um: float, wl_um: float) -> dict[str, float]:
        assert wl_um == wavelength_um
        assert 2.0 * np.pi * radius_um / wl_um <= DIRECT_MIE_X_CAP * (1.0 + 1.0e-12)
        calls.append(radius_um)
        area = np.pi * radius_um**2
        return {"ext": 2.0 * area, "sca": area, "abs": area, "asymmetry": 0.5}

    monkeypatch.setattr(compare, "mam_lfl_mie_cross_sections_um2", fake_cross_sections, raising=False)

    cross = _mode_averaged_cross_sections_um2_capped(
        1.5,
        0.01,
        median_radius_um=20.0,
        sigma_g=1.8,
        wavelength_um=wavelength_um,
        n_quad=9,
        n_sigma=5.0,
    )

    assert calls
    assert np.isfinite(cross["ext"])
    assert np.isfinite(cross["abs"])
    assert np.isfinite(cross["asymmetry"])


def test_metric_rejects_lost_direct_mie_samples() -> None:
    from sp3_tests.compare_offline_lut import _metric_for_band

    offline = xr.Dataset(
        {
            "Extinction_Layer_Optical_Depth": (("lev", "sample"), np.asarray([[1.0, np.nan]])),
            "Scattering_Layer_Optical_Depth": (("lev", "sample"), np.asarray([[0.5, np.nan]])),
            "Layer_Asymmetry_Parameter": (("lev", "sample"), np.asarray([[0.1, np.nan]])),
            "Extinction_Column_Optical_Depth": (("sample",), np.asarray([1.0, np.nan])),
        },
        attrs={"sample_count": 2},
    )
    sp3 = xr.Dataset(
        {
            "Extinction_Layer_Optical_Depth": (("lev", "sample"), np.asarray([[1.0, 2.0]])),
            "Scattering_Layer_Optical_Depth": (("lev", "sample"), np.asarray([[0.5, 1.0]])),
            "Layer_Asymmetry_Parameter": (("lev", "sample"), np.asarray([[0.1, 0.1]])),
            "Extinction_Column_Optical_Depth": (("sample",), np.asarray([1.0, 2.0])),
        }
    )

    with pytest.raises(ValueError, match="sampled direct-MIE columns"):
        _metric_for_band(
            offline,
            sp3,
            "SW01",
            "20080701.10800",
            min_tau=1.0e-3,
            min_scattering_tau=1.0e-8,
            ext_ratio_tolerance=0.10,
            ssa_tolerance=0.02,
            asymmetry_tolerance=0.05,
        )
