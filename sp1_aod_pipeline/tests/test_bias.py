from datetime import date

import numpy as np

from sp1_aod_pipeline.bias import (
    BiasCoeffs,
    apply_bias,
    apply_bias_sigma,
    fit_bias,
    identity,
    resolve_coeffs,
)
from sp1_aod_pipeline.config import RunConfig


def test_fit_recovers_truth_when_modis_is_truth():
    truth = np.array([0.1, 0.2, 0.5, 1.0, 1.5])
    modis = truth.copy()
    viirs = 0.1 + 1.2 * truth

    coeffs = fit_bias(modis, viirs, truth)
    corrected = apply_bias(viirs.astype(np.float32), coeffs)

    assert abs(coeffs.a_m) < 1e-9
    assert abs(coeffs.b_m - 1.0) < 1e-9
    assert np.allclose(corrected, truth, atol=1e-5)
    assert coeffs.rmse_after < 1e-5 < coeffs.rmse_before


def test_apply_bias_is_fill_aware():
    values = np.array([0.5, -999.0, 0.3], np.float32)

    corrected = apply_bias(values, identity())

    assert np.isclose(corrected[0], 0.5)
    assert corrected[1] == -999.0
    assert np.isclose(corrected[2], 0.3)


def test_apply_bias_sigma_scales():
    coeffs = BiasCoeffs(
        a_m=0.0,
        b_m=1.0,
        a_v=0.0,
        b_v=2.0,
        rmse_before=0.0,
        rmse_after=0.0,
        n=3,
    )
    sigma = np.array([0.1, -999.0], np.float32)

    corrected = apply_bias_sigma(sigma, coeffs)

    assert np.isclose(corrected[0], 0.2)
    assert corrected[1] == -999.0


def test_json_roundtrip(tmp_path):
    coeffs = BiasCoeffs(0.01, 1.02, -0.03, 1.1, 0.2, 0.05, 42)
    path = str(tmp_path / "bias.json")

    coeffs.to_json(path)

    assert BiasCoeffs.from_json(path) == coeffs


def test_resolve_coeffs_precedence(tmp_path):
    def cfg(bias_coeff_file):
        return RunConfig(
            modis_dir="m",
            viirs_dir="v",
            out_dir="o",
            start=date(2020, 6, 15),
            end=date(2020, 6, 15),
            bias_coeff_file=bias_coeff_file,
        )

    assert resolve_coeffs(cfg(str(tmp_path / "missing.json"))) == identity()

    saved = BiasCoeffs(0.0, 1.0, -0.02, 1.1, 0.2, 0.05, 7)
    config_path = str(tmp_path / "cfg_coeffs.json")
    saved.to_json(config_path)
    assert resolve_coeffs(cfg(config_path)) == saved

    explicit = BiasCoeffs(0.01, 0.99, 0.0, 1.0, 0.1, 0.03, 3)
    explicit_path = str(tmp_path / "explicit.json")
    explicit.to_json(explicit_path)
    assert resolve_coeffs(cfg(config_path), explicit_path) == explicit
