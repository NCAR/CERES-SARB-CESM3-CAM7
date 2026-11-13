import os
from datetime import date

import numpy as np
import pytest

from sp1_aod_pipeline.config import RunConfig
from sp1_aod_pipeline.ingest_viirs import read_viirs_granule
from sp1_aod_pipeline.qc import qc_mask
from sp1_aod_pipeline.tests.make_golden import (
    GOLDEN,
    REAL_VIIRS,
    build_window,
    read_fields,
)


def test_golden_window_regression(tmp_path):
    assert os.path.exists(GOLDEN), (
        "Golden missing; generate+commit it once with: "
        "PYTHONPATH=$ROOT $PY -m sp1_aod_pipeline.tests.make_golden"
    )
    expected = np.load(GOLDEN)
    current = read_fields(build_window(str(tmp_path)))

    for key in (
        "aod_weighted_mean",
        "aod_uncertainty",
        "aod_weighted_mean_modis",
        "aod_weighted_mean_viirs",
    ):
        assert np.allclose(current[key], expected[key], atol=1e-6), key
    assert np.array_equal(current["aod_count"], expected["aod_count"])
    assert current["aod_count"][96, 1] == 2
    assert current["aod_count"][120, 200] == 1
    assert current["aod_count"][50, 10] == 1


def test_real_viirs_sample_invariants():
    if not os.path.exists(REAL_VIIRS):
        pytest.skip(f"real VIIRS sample not present: {REAL_VIIRS}")
    cfg = RunConfig(
        modis_dir="m",
        viirs_dir="v",
        out_dir="o",
        start=date(2020, 6, 15),
        end=date(2020, 6, 15),
    )

    record = read_viirs_granule(REAL_VIIRS, cfg)

    assert record.sensor == "viirs"
    assert record.aod.shape == (402 * 400,)
    assert np.isfinite(record.lat).all()
    assert np.isfinite(record.lon).all()
    assert record.time.shape == record.aod.shape
    finite_time = ~np.isnat(record.time)
    if finite_time.any():
        first_time = record.time[finite_time][0]
        assert first_time.astype("datetime64[Y]").astype(int) + 1970 == 2023
    else:
        assert np.isnat(record.time).all()
    valid = qc_mask(
        record.aod,
        record.qa,
        record.sigma,
        record.lat,
        record.lon,
        cfg.viirs_qa_min,
        cfg.aod_min,
        cfg.aod_max,
        cfg.sigma_max,
    )
    assert valid.shape == (402 * 400,)
    assert valid.dtype == bool
