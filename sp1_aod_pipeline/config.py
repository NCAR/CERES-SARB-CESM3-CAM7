"""Run configuration for the SP1 pipeline. Every tunable lives here."""

from dataclasses import dataclass
from datetime import date

import yaml


def _as_date(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value))


@dataclass
class RunConfig:
    modis_dir: str
    viirs_dir: str
    out_dir: str
    start: date
    end: date
    stage_root: str = ""
    modis_qa_min: int = 1
    viirs_qa_min: int = 2
    aod_min: float = 0.0
    aod_max: float = 5.0
    sigma_max: float = 5.0
    modis_ee_land: tuple = (0.05, 0.15)
    modis_ee_ocean: tuple = (0.03, 0.05)
    sigma_floor: float = 1e-3
    bias_coeff_file: str = "bias_coeffs.json"
    modis_product: str = "MOD04_L2"
    modis_product_aqua: str = "MYD04_L2"
    viirs_product: str = "AERDB_L2_VIIRS_NOAA20"
    collection: str = "6.1"
    viirs_collection: str = "2"

    @classmethod
    def from_yaml(cls, path):
        with open(path) as handle:
            data = yaml.safe_load(handle)
        data["start"] = _as_date(data["start"])
        data["end"] = _as_date(data["end"])
        for key in ("modis_ee_land", "modis_ee_ocean"):
            if key in data and data[key] is not None:
                data[key] = tuple(data[key])
        return cls(**data)
