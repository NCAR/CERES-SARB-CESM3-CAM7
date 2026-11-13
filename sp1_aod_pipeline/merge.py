"""Inverse-variance merge of MODIS and VIIRS per-cell grids."""

import numpy as np

from .contract import FILL_FLOAT


def inverse_variance_merge(a_mean, a_sigma, a_count, b_mean, b_sigma, b_count, cfg):
    fill = float(FILL_FLOAT)
    a_mean = np.asarray(a_mean)
    b_mean = np.asarray(b_mean)
    a_ok = a_mean != fill
    b_ok = b_mean != fill

    a_values = np.where(a_ok, a_mean, 0.0).astype(np.float64)
    b_values = np.where(b_ok, b_mean, 0.0).astype(np.float64)
    a_sigma = np.maximum(np.asarray(a_sigma, np.float64), cfg.sigma_floor)
    b_sigma = np.maximum(np.asarray(b_sigma, np.float64), cfg.sigma_floor)

    a_weight = np.where(a_ok, 1.0 / a_sigma**2, 0.0)
    b_weight = np.where(b_ok, 1.0 / b_sigma**2, 0.0)
    total_weight = a_weight + b_weight
    has_data = total_weight > 0

    mean = np.full(a_values.shape, fill, dtype=np.float64)
    sigma = np.full(a_values.shape, fill, dtype=np.float64)
    mean[has_data] = (
        a_weight[has_data] * a_values[has_data]
        + b_weight[has_data] * b_values[has_data]
    ) / total_weight[has_data]
    sigma[has_data] = np.sqrt(1.0 / total_weight[has_data])

    count = np.where(a_ok, a_count, 0) + np.where(b_ok, b_count, 0)
    return mean.astype(np.float32), sigma.astype(np.float32), count.astype(np.int32)
