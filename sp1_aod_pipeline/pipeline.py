"""Orchestrate one 3-hour SP1 AOD window into one contract file."""

import glob
import os
from datetime import timedelta

import numpy as np

from .aggregate import pixel_window_mask, window_bounds
from .bias import apply_bias, apply_bias_sigma, identity
from .contract import contract_filename, write_contract_file
from .grid import bin_record_to_f09
from .ingest_modis import read_modis_granule
from .ingest_viirs import read_viirs_granule
from .merge import inverse_variance_merge
from .qc import qc_mask
from .records import CellGrid, L2Record


def _recursive_glob(root, pattern):
    if not root or not os.path.exists(root):
        return []
    return sorted(glob.glob(os.path.join(root, "**", pattern), recursive=True))


def find_viirs_granules(directory, day):
    doy = day.timetuple().tm_yday
    dated = _recursive_glob(
        directory, f"AERDB_L2_VIIRS_NOAA20.A{day.year}{doy:03d}.*.nc"
    )
    return dated or _recursive_glob(directory, "AERDB_L2_*.nc")


def find_modis_granules(directory, day):
    doy = day.timetuple().tm_yday
    patterns = [
        f"M?D04_L2.A{day.year}{doy:03d}.*.hdf",
        f"M?D04_L2.A{day.year}{doy:03d}.*.nc",
    ]
    hits = []
    for pattern in patterns:
        hits.extend(_recursive_glob(directory, pattern))
    if hits:
        return sorted(hits)
    return sorted(
        _recursive_glob(directory, "*.hdf") + _recursive_glob(directory, "M?D04_L2*.nc")
    )


def _gather(paths, reader, cfg, start, end):
    record = _read_records(paths, reader, cfg)
    return _window_record(record, start, end)


def _read_records(paths, reader, cfg):
    columns = {name: [] for name in ("lat", "lon", "aod", "sigma", "qa", "time")}
    sensor = None
    for path in paths:
        record = reader(path, cfg)
        sensor = record.sensor
        columns["lat"].append(record.lat)
        columns["lon"].append(record.lon)
        columns["aod"].append(record.aod)
        columns["sigma"].append(record.sigma)
        columns["qa"].append(record.qa)
        columns["time"].append(record.time)
    if not columns["lat"]:
        return None
    return L2Record(
        sensor=sensor or "unknown",
        lat=np.concatenate(columns["lat"]),
        lon=np.concatenate(columns["lon"]),
        aod=np.concatenate(columns["aod"]),
        sigma=np.concatenate(columns["sigma"]),
        qa=np.concatenate(columns["qa"]),
        time=np.concatenate(columns["time"]),
    )


def _window_record(record, start, end):
    if record is None:
        return None
    in_window = pixel_window_mask(record.time, start, end)
    if not in_window.any():
        return None
    return L2Record(
        sensor=record.sensor,
        lat=record.lat[in_window],
        lon=record.lon[in_window],
        aod=record.aod[in_window],
        sigma=record.sigma[in_window],
        qa=record.qa[in_window],
        time=record.time[in_window],
    )


def _sensor_grid(record, qa_min, cfg):
    if record is None:
        return CellGrid.empty()
    valid = qc_mask(
        record.aod,
        record.qa,
        record.sigma,
        record.lat,
        record.lon,
        qa_min,
        cfg.aod_min,
        cfg.aod_max,
        cfg.sigma_max,
    )
    if not valid.any():
        return CellGrid.empty()
    return bin_record_to_f09(record, valid, cfg)


def _write_window(cfg, day, idx, coeffs, modis_day_record, viirs_day_record):
    start, end, _center = window_bounds(day, idx)
    modis_record = _window_record(modis_day_record, start, end)
    viirs_record = _window_record(viirs_day_record, start, end)
    modis_grid = _sensor_grid(modis_record, cfg.modis_qa_min, cfg)
    viirs_grid = _sensor_grid(viirs_record, cfg.viirs_qa_min, cfg)
    viirs_mean = apply_bias(viirs_grid.mean, coeffs)
    viirs_sigma = apply_bias_sigma(viirs_grid.sigma, coeffs)
    mean, sigma, count = inverse_variance_merge(
        modis_grid.mean,
        modis_grid.sigma,
        modis_grid.count,
        viirs_mean,
        viirs_sigma,
        viirs_grid.count,
        cfg,
    )
    attrs = {
        "qc_thresholds": (
            f"viirs_qa>={cfg.viirs_qa_min}; modis_qa>={cfg.modis_qa_min}; "
            f"aod in [{cfg.aod_min},{cfg.aod_max}]; 0<sigma<={cfg.sigma_max}; "
            "finite geolocation"
        ),
        "source": (
            f"MODIS {cfg.modis_product}/{cfg.modis_product_aqua} C{cfg.collection} "
            f"(DT+DB); VIIRS {cfg.viirs_product} C{cfg.viirs_collection}"
        ),
        "bias_correction_method": (
            "AERONET-anchored affine VIIRS->MODIS "
            f"(a_v={coeffs.a_v:.4g}, b_v={coeffs.b_v:.4g}, "
            f"a_m={coeffs.a_m:.4g}, b_m={coeffs.b_m:.4g})"
        ),
    }
    os.makedirs(cfg.out_dir, exist_ok=True)
    out_path = os.path.join(cfg.out_dir, contract_filename(start))
    write_contract_file(
        out_path,
        window_start=start,
        aod_weighted_mean=mean,
        aod_uncertainty=sigma,
        aod_count=count,
        aod_weighted_mean_modis=modis_grid.mean,
        aod_weighted_mean_viirs=viirs_mean,
        global_attrs=attrs,
    )
    return out_path


def process_window(cfg, day, idx, coeffs):
    start, end, _center = window_bounds(day, idx)
    modis_record = _gather(
        find_modis_granules(cfg.modis_dir, day), read_modis_granule, cfg, start, end
    )
    viirs_record = _gather(
        find_viirs_granules(cfg.viirs_dir, day), read_viirs_granule, cfg, start, end
    )
    return _write_window(cfg, day, idx, coeffs, modis_record, viirs_record)


def process_day(cfg, day, coeffs):
    modis_record = _read_records(
        find_modis_granules(cfg.modis_dir, day), read_modis_granule, cfg
    )
    viirs_record = _read_records(
        find_viirs_granules(cfg.viirs_dir, day), read_viirs_granule, cfg
    )
    return [
        _write_window(cfg, day, idx, coeffs, modis_record, viirs_record)
        for idx in range(8)
    ]


def run(cfg, coeffs=None):
    coeffs = coeffs or identity()
    outputs = []
    day = cfg.start
    while day <= cfg.end:
        outputs.extend(process_day(cfg, day, coeffs))
        day += timedelta(days=1)
    return outputs
