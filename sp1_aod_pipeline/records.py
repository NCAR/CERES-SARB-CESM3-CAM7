"""Shared data structures and TAI93 time conversion."""

from dataclasses import dataclass

import numpy as np

from .contract import FILL_FLOAT
from .f09_grid import NLAT, NLON

_EPOCH93 = np.datetime64("1993-01-01T00:00:00", "ns")
_MAX_REASONABLE_TAI93_SECONDS = 10_000_000_000.0


def tai93_to_datetime64(sec):
    """Convert TAI93 seconds to datetime64[ns].

    Leap seconds are ignored; SP1 aggregates into 3-hour windows.
    """

    sec = np.asarray(sec, dtype=np.float64).ravel()
    out = np.full(sec.shape, np.datetime64("NaT"), dtype="datetime64[ns]")
    ok = np.isfinite(sec) & (np.abs(sec) <= _MAX_REASONABLE_TAI93_SECONDS)
    nanoseconds = np.rint(sec[ok] * 1_000_000_000.0).astype("timedelta64[ns]")
    out[ok] = _EPOCH93 + nanoseconds
    return out


@dataclass
class L2Record:
    sensor: str
    lat: np.ndarray
    lon: np.ndarray
    aod: np.ndarray
    sigma: np.ndarray
    qa: np.ndarray
    time: np.ndarray


@dataclass
class CellGrid:
    mean: np.ndarray
    sigma: np.ndarray
    count: np.ndarray

    @classmethod
    def empty(cls):
        return cls(
            mean=np.full((NLAT, NLON), FILL_FLOAT, np.float32),
            sigma=np.full((NLAT, NLON), FILL_FLOAT, np.float32),
            count=np.zeros((NLAT, NLON), np.int32),
        )
