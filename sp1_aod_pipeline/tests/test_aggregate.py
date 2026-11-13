from datetime import date, datetime

import numpy as np

from sp1_aod_pipeline import aggregate as ag


def test_window_bounds():
    start, end, center = ag.window_bounds(date(2020, 6, 15), 1)

    assert start == datetime(2020, 6, 15, 3)
    assert end == datetime(2020, 6, 15, 6)
    assert center == datetime(2020, 6, 15, 4, 30)


def test_window_index():
    assert ag.window_index(datetime(2020, 6, 15, 0, 0)) == 0
    assert ag.window_index(datetime(2020, 6, 15, 2, 59)) == 0
    assert ag.window_index(datetime(2020, 6, 15, 3, 0)) == 1
    assert ag.window_index(datetime(2020, 6, 15, 23, 59)) == 7


def test_pixel_window_mask_half_open_and_nat():
    times = np.array(
        [
            "2020-06-15T03:00:00",
            "2020-06-15T05:59:00",
            "2020-06-15T06:00:00",
            "NaT",
        ],
        dtype="datetime64[ns]",
    )

    mask = ag.pixel_window_mask(
        times, datetime(2020, 6, 15, 3), datetime(2020, 6, 15, 6)
    )

    assert mask.tolist() == [True, True, False, False]


def test_enumerate_windows():
    windows = ag.enumerate_windows(date(2020, 6, 15), date(2020, 6, 16))

    assert len(windows) == 16
    assert windows[0] == (date(2020, 6, 15), 0)
    assert windows[-1] == (date(2020, 6, 16), 7)
