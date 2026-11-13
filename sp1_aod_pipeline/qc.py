"""Pure per-pixel QC filters for L2 AOD pixels."""

import numpy as np


def qc_mask(aod, qa, sigma, lat, lon, qa_min, aod_min, aod_max, sigma_max):
    """Return an element-wise valid mask for AOD retrieval pixels."""

    aod = np.asarray(aod, dtype=np.float64)
    qa = np.asarray(qa, dtype=np.float64)
    sigma = np.asarray(sigma, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    return (
        np.isfinite(aod)
        & np.isfinite(qa)
        & np.isfinite(sigma)
        & np.isfinite(lat)
        & np.isfinite(lon)
        & (qa >= qa_min)
        & (aod >= aod_min)
        & (aod <= aod_max)
        & (sigma > 0.0)
        & (sigma <= sigma_max)
    )
