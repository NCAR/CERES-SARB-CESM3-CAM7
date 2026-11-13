"""Build committed golden artifacts for SP1 regression tests."""

import os
import tempfile
from datetime import date, datetime

import netCDF4 as nc
import numpy as np

from ..bias import identity
from ..config import RunConfig
from ..f09_grid import f09_lat, f09_lon
from ..pipeline import process_window
from .fixtures import make_modis_granule, make_viirs_granule

GOLDEN = os.path.join(os.path.dirname(__file__), "data", "golden_window.npz")
REAL_VIIRS = (
    "/glade/work/tvmora/VIIRS_original/"
    "AERDB_L2_VIIRS_NOAA20.A2023362.0000.002.2023362124926.nc"
)
_FIELDS = (
    "aod_weighted_mean",
    "aod_uncertainty",
    "aod_count",
    "aod_weighted_mean_modis",
    "aod_weighted_mean_viirs",
)


def build_window(out_dir):
    """Deterministically build one contract file and return its path."""

    modis_dir = os.path.join(out_dir, "m")
    viirs_dir = os.path.join(out_dir, "v")
    output_dir = os.path.join(out_dir, "o")
    for path in (modis_dir, viirs_dir, output_dir):
        os.makedirs(path, exist_ok=True)

    lat = f09_lat()
    lon = f09_lon()
    scan = datetime(2020, 6, 15, 1, 0, 0)
    viirs_cells = [(96, 1), (120, 200)]
    make_viirs_granule(
        os.path.join(viirs_dir, "AERDB_L2_VIIRS_NOAA20.A2020167.0100.002.x.nc"),
        lat=np.array([[float(lat[i]) for i, _ in viirs_cells]], np.float32),
        lon=np.array([[float(lon[j]) for _, j in viirs_cells]], np.float32),
        aod_land=np.array([[0.50, 0.33]], np.float32),
        qa_land=np.array([[3.0, 3.0]]),
        eu_land=np.array([[0.10, 0.08]], np.float32),
        scan_dt=scan,
    )
    modis_cells = [(96, 1), (50, 10)]
    make_modis_granule(
        os.path.join(modis_dir, "MOD04_L2.A2020167.0100.061.nc"),
        lat=np.array([[float(lat[i]) for i, _ in modis_cells]], np.float32),
        lon=np.array([[float(lon[j]) for _, j in modis_cells]], np.float32),
        aod=np.array([[0.70, 0.45]]),
        qa=np.array([[3, 3]]),
        alg=np.array([[1, 1]]),
        scan_dt=scan,
    )
    cfg = RunConfig(
        modis_dir=modis_dir,
        viirs_dir=viirs_dir,
        out_dir=output_dir,
        start=date(2020, 6, 15),
        end=date(2020, 6, 15),
    )
    return process_window(cfg, date(2020, 6, 15), 0, identity())


def read_fields(path):
    dataset = nc.Dataset(path)
    out = {}
    try:
        for field in _FIELDS:
            values = dataset[field][:]
            out[field] = np.ma.filled(values, dataset[field]._FillValue)
    finally:
        dataset.close()
    return out


def main():
    tmpdir = tempfile.mkdtemp()
    fields = read_fields(build_window(tmpdir))
    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    np.savez_compressed(GOLDEN, **fields)
    print("wrote golden", GOLDEN)


if __name__ == "__main__":
    main()
