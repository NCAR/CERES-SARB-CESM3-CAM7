from datetime import datetime

import numpy as np

from sp1_aod_pipeline.config import RunConfig
from sp1_aod_pipeline.merge import inverse_variance_merge


def _cfg():
    return RunConfig(
        modis_dir="m",
        viirs_dir="v",
        out_dir="o",
        start=datetime(2020, 6, 15).date(),
        end=datetime(2020, 6, 15).date(),
    )


def _g(val, sig, cnt, shape=(2, 2)):
    return (
        np.full(shape, val, np.float32),
        np.full(shape, sig, np.float32),
        np.full(shape, cnt, np.int32),
    )


def test_both_present_inverse_variance():
    am, asig, ac = _g(0.5, 0.1, 3)
    bm, bsig, bc = _g(0.7, 0.2, 5)

    mean, sigma, count = inverse_variance_merge(am, asig, ac, bm, bsig, bc, _cfg())

    w1, w2 = 1 / 0.1**2, 1 / 0.2**2
    expected = (w1 * 0.5 + w2 * 0.7) / (w1 + w2)
    assert np.isclose(mean[0, 0], expected, atol=1e-5)
    assert np.isclose(sigma[0, 0], np.sqrt(1 / (w1 + w2)), atol=1e-5)
    assert count[0, 0] == 8


def test_one_present_uses_it():
    am, asig, ac = _g(-999.0, -999.0, 0)
    bm, bsig, bc = _g(0.3, 0.15, 4)

    mean, sigma, count = inverse_variance_merge(am, asig, ac, bm, bsig, bc, _cfg())

    assert np.isclose(mean[0, 0], 0.3)
    assert np.isclose(sigma[0, 0], 0.15)
    assert count[0, 0] == 4


def test_neither_present_is_fill():
    am, asig, ac = _g(-999.0, -999.0, 0)
    bm, bsig, bc = _g(-999.0, -999.0, 0)

    mean, sigma, count = inverse_variance_merge(am, asig, ac, bm, bsig, bc, _cfg())

    assert mean[0, 0] == -999.0
    assert sigma[0, 0] == -999.0
    assert count[0, 0] == 0
    assert mean.dtype == np.float32
    assert count.dtype == np.int32
