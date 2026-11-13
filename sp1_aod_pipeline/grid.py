"""Bin L2 pixels onto f09 using DAVINCI's binning engine."""

import numpy as np

from davinci_monet.pairing.grid_binning import (
    bin_swath_to_grid,
    bin_swath_to_grid_uncertainty,
    edges_from_centers,
    normalize_grid,
    normalize_uncertainty_grid,
)

from .contract import FILL_FLOAT
from .f09_grid import NLAT, NLON, f09_lat, f09_lon
from .records import CellGrid


def _prep(rec, valid, cfg):
    valid = np.asarray(valid, dtype=bool)
    lat = np.asarray(rec.lat, np.float64)[valid]
    lon = np.asarray(rec.lon, np.float64)[valid]
    aod = np.asarray(rec.aod, np.float64)[valid]
    sigma = np.maximum(np.asarray(rec.sigma, np.float64)[valid], cfg.sigma_floor)
    lon = ((lon + 0.625) % 360.0) - 0.625
    lat_edges = edges_from_centers(f09_lat())
    lon_edges = edges_from_centers(f09_lon())
    time_edges = np.array([0.0, 1.0])
    time_values = np.zeros(aod.shape[0])
    return lat, lon, aod, sigma, lat_edges, lon_edges, time_edges, time_values


def bin_record_to_f09(rec, valid, cfg):
    lat, lon, aod, sigma, lat_edges, lon_edges, time_edges, time_values = _prep(
        rec, valid, cfg
    )
    shape = (1, NLON, NLAT)
    count = np.zeros(shape, dtype=np.int64)
    weight = np.zeros(shape)
    weighted_sum = np.zeros(shape)
    bin_swath_to_grid_uncertainty(
        time_edges,
        lon_edges,
        lat_edges,
        time_values,
        lon,
        lat,
        aod,
        sigma,
        count,
        weight,
        weighted_sum,
    )
    mean_grid, sigma_grid = normalize_uncertainty_grid(count, weight, weighted_sum)
    mean2d = mean_grid[0].T
    sigma2d = sigma_grid[0].T
    count2d = count[0].T.astype(np.int32)
    mean2d = np.where(np.isnan(mean2d), float(FILL_FLOAT), mean2d).astype(np.float32)
    sigma2d = np.where(np.isnan(sigma2d), float(FILL_FLOAT), sigma2d).astype(np.float32)
    return CellGrid(mean=mean2d, sigma=sigma2d, count=count2d)


def simple_mean_grid(rec, valid, cfg):
    lat, lon, aod, _sigma, lat_edges, lon_edges, time_edges, time_values = _prep(
        rec, valid, cfg
    )
    shape = (1, NLON, NLAT)
    count = np.zeros(shape, dtype=np.int64)
    data_sum = np.zeros(shape)
    bin_swath_to_grid(
        time_edges,
        lon_edges,
        lat_edges,
        time_values,
        lon,
        lat,
        aod,
        count,
        data_sum,
    )
    normalize_grid(count, data_sum)
    mean2d = data_sum[0].T
    return np.where(np.isnan(mean2d), float(FILL_FLOAT), mean2d).astype(np.float32)
