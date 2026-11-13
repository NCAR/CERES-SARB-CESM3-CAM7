"""AERONET-anchored affine VIIRS-to-MODIS bias correction."""

import json
import os
from dataclasses import asdict, dataclass

import numpy as np

from .contract import FILL_FLOAT


@dataclass
class BiasCoeffs:
    a_m: float
    b_m: float
    a_v: float
    b_v: float
    rmse_before: float
    rmse_after: float
    n: int

    def to_json(self, path):
        with open(path, "w") as handle:
            json.dump(asdict(self), handle, indent=2)

    @classmethod
    def from_json(cls, path):
        with open(path) as handle:
            return cls(**json.load(handle))


def identity():
    return BiasCoeffs(
        a_m=0.0,
        b_m=1.0,
        a_v=0.0,
        b_v=1.0,
        rmse_before=0.0,
        rmse_after=0.0,
        n=0,
    )


def resolve_coeffs(cfg, bias_path=None):
    if bias_path:
        return BiasCoeffs.from_json(bias_path)
    if cfg.bias_coeff_file and os.path.exists(cfg.bias_coeff_file):
        return BiasCoeffs.from_json(cfg.bias_coeff_file)
    return identity()


def _affine_fit(x, y):
    matrix = np.vstack([np.ones_like(x), x]).T
    coeffs, *_ = np.linalg.lstsq(matrix, y, rcond=None)
    return float(coeffs[0]), float(coeffs[1])


def fit_bias(modis_aod, viirs_aod, aeronet_aod):
    modis = np.asarray(modis_aod, np.float64)
    viirs = np.asarray(viirs_aod, np.float64)
    aeronet = np.asarray(aeronet_aod, np.float64)
    a_m, b_m = _affine_fit(modis, aeronet)
    a_v, b_v = _affine_fit(viirs, aeronet)
    corrected = (a_v + b_v * viirs - a_m) / b_m
    rmse_before = float(np.sqrt(np.mean((viirs - aeronet) ** 2)))
    rmse_after = float(np.sqrt(np.mean((corrected - aeronet) ** 2)))
    return BiasCoeffs(a_m, b_m, a_v, b_v, rmse_before, rmse_after, int(aeronet.size))


def apply_bias(viirs_aod, coeffs):
    fill = float(FILL_FLOAT)
    viirs = np.asarray(viirs_aod, np.float64)
    ok = viirs != fill
    out = np.full(viirs.shape, fill, dtype=np.float64)
    out[ok] = (coeffs.a_v + coeffs.b_v * viirs[ok] - coeffs.a_m) / coeffs.b_m
    return out.astype(np.float32)


def apply_bias_sigma(viirs_sigma, coeffs):
    fill = float(FILL_FLOAT)
    sigma = np.asarray(viirs_sigma, np.float64)
    ok = sigma != fill
    out = np.full(sigma.shape, fill, dtype=np.float64)
    out[ok] = abs(coeffs.b_v / coeffs.b_m) * sigma[ok]
    return out.astype(np.float32)
