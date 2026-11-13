from __future__ import annotations

import numpy as np


def test_cam_chebyshev_fit_uses_half_weight_first_coefficient() -> None:
    from sp3_optics.make_lfl_lut import cam_cheb_eval
    from sp3_optics.make_lfl_lut import cam_cheb_fit

    x = np.linspace(-1.0, 1.0, 17)
    values = 1.25 - 0.5 * x + 0.75 * (2.0 * x**2 - 1.0)

    coeff = cam_cheb_fit(x, values, ncoef=3)

    assert np.isclose(coeff[0], np.float64(2.5), atol=1.0e-12)
    assert np.allclose(cam_cheb_eval(x, coeff), values, atol=1.0e-12)


def test_specific_optics_normalization_matches_cam_wet_volume_factor() -> None:
    from sp3_optics.make_lfl_lut import raw_specific_optics
    from sp3_optics.make_lfl_lut import surface_radius_to_number_median_um

    surface_radius_um = 0.2
    sigma_g = 1.6
    number_median_um = surface_radius_to_number_median_um(surface_radius_um, sigma_g)
    cross_sections_um2 = {"ext": 2.0, "sca": 0.75, "abs": 1.25, "asymmetry": 0.4}

    raw = raw_specific_optics(cross_sections_um2, surface_radius_um, sigma_g)

    log_sigma = np.log(sigma_g)
    mean_volume_m3 = (
        (4.0 / 3.0)
        * np.pi
        * (number_median_um * 1.0e-6) ** 3
        * np.exp(4.5 * log_sigma**2)
    )
    expected_ext = 2.0e-12 / (mean_volume_m3 * 1000.0)
    expected_abs = 1.25e-12 / (mean_volume_m3 * 1000.0)

    assert raw["ext"] == np.float64(expected_ext)
    assert raw["abs"] == np.float64(expected_abs)
    assert raw["sca"] == np.float64(0.75e-12 / (mean_volume_m3 * 1000.0))
    assert raw["asm"] == np.float64(0.4)


def test_build_lfl_lut_dataset_contains_lw_scattering_schema() -> None:
    from sp3_optics.lfl_bands import LFL_LW_EDGES_UM
    from sp3_optics.lfl_bands import LFL_SW_EDGES_UM
    from sp3_optics.make_lfl_lut import CHEB_RADIUS_MAX_UM
    from sp3_optics.make_lfl_lut import CHEB_RADIUS_MIN_UM
    from sp3_optics.make_lfl_lut import _normalize_log_surface_radius
    from sp3_optics.make_lfl_lut import build_lut_dataset
    from sp3_optics.make_lfl_lut import cam_cheb_eval

    ds = build_lut_dataset(
        modes=("a4",),
        band_set="lfl",
        n_radius=7,
        n_quad=3,
        ncoef=5,
        max_sw_bands=1,
        max_lw_bands=1,
        max_re=2,
        max_im=2,
    )

    assert ds.sizes["mode"] == 1
    assert ds.sizes["sw_band"] == 1
    assert ds.sizes["lw_band"] == 1
    assert ds.sizes["coef_number"] == 5
    assert ds.sizes["refindex_real"] == 2
    assert ds.sizes["refindex_im"] == 2
    for name in ("extpsw", "abspsw", "asmpsw", "extplw", "absplw", "asmplw"):
        assert name in ds
        assert np.all(np.isfinite(ds[name].values))

    assert np.allclose(ds["lfl_sw_edges_um"].values, np.asarray(LFL_SW_EDGES_UM))
    assert np.allclose(ds["lfl_lw_edges_um"].values, np.asarray(LFL_LW_EDGES_UM))
    assert set(ds["spectype"].values.tolist()) >= {"BC", "DU", "SS", "SU", "WAT"}
    for name in (
        "refindex_real_spectype_sw",
        "refindex_im_spectype_sw",
        "refindex_real_spectype_lw",
        "refindex_im_spectype_lw",
    ):
        assert name in ds
        assert np.all(np.isfinite(ds[name].values))
    assert ds["refindex_real_spectype_sw"].sizes["lfl_sw_band"] == 14
    assert ds["refindex_real_spectype_lw"].sizes["lfl_lw_band"] == 12
    assert ds.attrs["cheb_radius_min_um"] == CHEB_RADIUS_MIN_UM
    assert ds.attrs["cheb_radius_max_um"] == CHEB_RADIUS_MAX_UM
    assert ds.attrs["spectype_refindex_source"] == "/glade/work/fillmore/Data/Optics/MERRA2"
    assert "_mie_curve_um2" in ds.attrs["mie_source"]
    assert "mie_sphere.py" in ds.attrs["mie_source"]

    x_radius = _normalize_log_surface_radius(ds["cheb_surface_radius_um"].values)
    for band_dim, ext_name, abs_name, asm_name in (
        ("sw_band", "extpsw", "abspsw", "asmpsw"),
        ("lw_band", "extplw", "absplw", "asmplw"),
    ):
        ext_coeff = ds[ext_name].isel({band_dim: 0, "mode": 0, "refindex_im": 0, "refindex_real": 0}).values
        abs_coeff = ds[abs_name].isel({band_dim: 0, "mode": 0, "refindex_im": 0, "refindex_real": 0}).values
        asm_coeff = ds[asm_name].isel({band_dim: 0, "mode": 0, "refindex_im": 0, "refindex_real": 0}).values
        ext = np.exp(cam_cheb_eval(x_radius, ext_coeff))
        absn = cam_cheb_eval(x_radius, abs_coeff)
        asm = cam_cheb_eval(x_radius, asm_coeff)
        assert np.all(np.isfinite(ext))
        assert np.all(absn >= -1.0e-8)
        assert np.all(ext - absn >= -1.0e-8)
        assert np.all(np.abs(asm) <= 1.0 + 1.0e-8)


def test_cam_refindex_source_samples_cam_species_physprop_files() -> None:
    from sp3_optics.make_lfl_lut import build_lut_dataset

    ds = build_lut_dataset(
        modes=("a4",),
        band_set="lfl",
        n_radius=5,
        n_quad=3,
        ncoef=5,
        max_sw_bands=1,
        max_lw_bands=1,
        max_re=1,
        max_im=1,
        refindex_source="cam",
    )

    sw05 = {"lfl_sw_band": 4}
    assert ds.attrs["spectype_refindex_source"] == "cam_physprop"
    assert np.isclose(ds["refindex_real_spectype_sw"].sel(spectype="BC").isel(sw05), 1.95)
    assert np.isclose(ds["refindex_im_spectype_sw"].sel(spectype="BC").isel(sw05), 0.79)
    assert np.isclose(ds["refindex_real_spectype_sw"].sel(spectype="POM").isel(sw05), 1.5299999713897705)
    assert np.isclose(ds["refindex_im_spectype_sw"].sel(spectype="POM").isel(sw05), 0.005665010823317644)
    assert np.isclose(ds["refindex_real_spectype_sw"].sel(spectype="WAT").isel(sw05), 1.3336699543428605)


def test_retarget_lut_refindex_preserves_coefficients() -> None:
    from sp3_optics.make_lfl_lut import build_lut_dataset
    from sp3_optics.make_lfl_lut import retarget_lut_refindex

    base = build_lut_dataset(
        modes=("a4",),
        band_set="lfl",
        n_radius=5,
        n_quad=3,
        ncoef=5,
        max_sw_bands=1,
        max_lw_bands=1,
        max_re=1,
        max_im=1,
    )

    retargeted = retarget_lut_refindex(base, "cam")

    np.testing.assert_allclose(retargeted["extpsw"], base["extpsw"])
    np.testing.assert_allclose(retargeted["absplw"], base["absplw"])
    assert retargeted.attrs["refindex_source"] == "cam"
    assert retargeted.attrs["spectype_refindex_source"] == "cam_physprop"
    assert not np.allclose(
        retargeted["refindex_real_spectype_sw"].values,
        base["refindex_real_spectype_sw"].values,
    )


def test_refindex_comparison_report_tabulates_mam_lfl_vs_cam_values() -> None:
    from sp3_optics.make_lfl_lut import refindex_comparison_report

    report = refindex_comparison_report()

    assert report["mam_lfl_source"] == "/glade/work/fillmore/Data/Optics/MERRA2"
    assert report["cam_source"] == "cam_physprop"
    rows = [
        row
        for row in report["sw"]
        if row["band"] == "SW05" and row["spectype"] == "POM"
    ]
    assert len(rows) == 1
    row = rows[0]
    assert np.isclose(row["mam_lfl_real"], 1.53)
    assert row["cam_real"] == np.float64(1.5299999713897705)
    assert row["real_abs_delta"] < 1.0e-6
    assert row["imag_abs_delta"] > 0.0


def test_lfl_default_chebyshev_order_reconstructs_sw01_extinction() -> None:
    from sp3_optics.make_lfl_lut import DEFAULT_LFL_NCOEF
    from sp3_optics.make_lfl_lut import LFL_SW_MIDPOINTS_UM
    from sp3_optics.make_lfl_lut import _stock_template
    from sp3_optics.make_lfl_lut import cam_cheb_eval
    from sp3_optics.make_lfl_lut import cheb_surface_radii_um
    from sp3_optics.make_lfl_lut import fit_optics_node
    from sp3_optics.make_lfl_lut import raw_specific_optics
    from sp3_optics.make_lfl_lut import surface_radius_to_number_median_um
    from sp3_optics.make_lfl_lut import _normalize_log_surface_radius
    from mie_lognormal import mode_averaged_cross_sections_um2

    with _stock_template("a1") as template:
        sigma_g = float(template["sigmag"].values)
        n_real = float(template["refindex_real_sw"].values[0, 0])
        n_imag = float(template["refindex_im_sw"].values[0, 0])

    wavelength_um = float(LFL_SW_MIDPOINTS_UM[0])
    fit_radii = cheb_surface_radii_um(129)
    fit_x = _normalize_log_surface_radius(fit_radii)
    ext_coeff, _, _ = fit_optics_node(
        wavelength_um,
        n_real,
        n_imag,
        sigma_g,
        fit_radii,
        fit_x,
        DEFAULT_LFL_NCOEF,
        mie_radius_grid_size=220,
    )

    eval_radii = np.geomspace(0.012, 20.0, 17)
    eval_x = _normalize_log_surface_radius(eval_radii)
    reconstructed = np.exp(cam_cheb_eval(eval_x, ext_coeff))
    direct = []
    for surface_radius_um in eval_radii:
        mie = mode_averaged_cross_sections_um2(
            n_real,
            abs(n_imag),
            surface_radius_to_number_median_um(float(surface_radius_um), sigma_g),
            sigma_g,
            wavelength_um,
            n_quad=16,
            n_sigma=5.0,
        )
        direct.append(raw_specific_optics(mie, float(surface_radius_um), sigma_g)["ext"])
    relative_error = np.abs(reconstructed - direct) / np.maximum(direct, 1.0e-30)

    assert DEFAULT_LFL_NCOEF > 5
    assert float(np.median(relative_error)) <= 0.01


def test_cam_calibration_report_uses_stock_rrtmg_band_order() -> None:
    from sp3_optics.make_lfl_lut import build_lut_dataset
    from sp3_optics.make_lfl_lut import cam_calibration_report

    generated = build_lut_dataset(
        modes=("a4",),
        band_set="cam",
        n_radius=50,
        n_quad=220,
        ncoef=5,
        max_sw_bands=1,
        max_lw_bands=1,
        max_re=2,
        max_im=2,
    )

    report = cam_calibration_report(
        generated,
        radius_samples=np.geomspace(0.012, 20.0, 24),
    )

    assert report["stock_sources"]["a4"] == "OPAC + miev0"
    assert report["gates"]["ext_median_le_10pct"] is True
    assert "visible_ext_median_le_5pct" in report["gates"]
    assert report["metrics"]["sw_ext_relative_median"] <= 0.10
    assert "sw_abs_relative_median" in report["metrics"]
    assert "visible_ext_relative_median" in report["metrics"]


def test_parallel_lfl_lut_generation_matches_serial_for_tiny_table() -> None:
    from sp3_optics.make_lfl_lut import build_lut_dataset

    serial = build_lut_dataset(
        modes=("a4",),
        band_set="lfl",
        n_radius=5,
        n_quad=3,
        ncoef=5,
        max_sw_bands=1,
        max_lw_bands=1,
        max_re=1,
        max_im=1,
        workers=1,
    )
    parallel = build_lut_dataset(
        modes=("a4",),
        band_set="lfl",
        n_radius=5,
        n_quad=3,
        ncoef=5,
        max_sw_bands=1,
        max_lw_bands=1,
        max_re=1,
        max_im=1,
        workers=2,
    )

    for name in ("extpsw", "abspsw", "asmpsw", "extplw", "absplw", "asmplw"):
        np.testing.assert_allclose(parallel[name], serial[name])
    assert parallel.attrs["workers"] == 2


def test_lfl_lut_generation_rejects_nonpositive_workers() -> None:
    import pytest
    from sp3_optics.make_lfl_lut import build_lut_dataset

    with pytest.raises(ValueError, match="workers"):
        build_lut_dataset(modes=("a4",), max_sw_bands=1, max_lw_bands=0, workers=0)


def test_refindex_axis_densification_preserves_endpoints_and_inserts_linear_nodes() -> None:
    from sp3_optics.make_lfl_lut import _densify_axis

    dense = _densify_axis(np.asarray([1.0, 3.0, 7.0], dtype=np.float64), subdivisions=2)

    np.testing.assert_allclose(dense, np.asarray([1.0, 2.0, 3.0, 5.0, 7.0], dtype=np.float64))


def test_lfl_lut_generation_can_densify_refindex_axes() -> None:
    from sp3_optics.make_lfl_lut import build_lut_dataset

    coarse = build_lut_dataset(
        modes=("a4",),
        band_set="lfl",
        n_radius=5,
        n_quad=3,
        ncoef=5,
        max_sw_bands=1,
        max_lw_bands=1,
        max_re=2,
        max_im=2,
    )
    dense = build_lut_dataset(
        modes=("a4",),
        band_set="lfl",
        n_radius=5,
        n_quad=3,
        ncoef=5,
        max_sw_bands=1,
        max_lw_bands=1,
        max_re=2,
        max_im=2,
        refindex_subdivisions=2,
    )

    assert dense.sizes["refindex_real"] == 3
    assert dense.sizes["refindex_im"] == 3
    assert dense.attrs["refindex_axis_subdivisions"] == 2
    np.testing.assert_allclose(dense["refindex_real_lw"].isel(lw_band=0, mode=0, refindex_real=[0, 2]), coarse["refindex_real_lw"].isel(lw_band=0, mode=0))
