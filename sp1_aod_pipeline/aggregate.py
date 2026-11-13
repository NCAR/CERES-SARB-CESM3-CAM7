"""3-hourly window bookkeeping."""

from datetime import datetime, timedelta

import numpy as np

from .contract import WINDOW_LENGTH_SEC, WINDOW_SECONDS


def window_bounds(day, idx):
    start = datetime(day.year, day.month, day.day) + timedelta(
        seconds=WINDOW_SECONDS[idx]
    )
    end = start + timedelta(seconds=WINDOW_LENGTH_SEC)
    center = start + timedelta(seconds=WINDOW_LENGTH_SEC // 2)
    return start, end, center


def window_index(time):
    seconds_of_day = time.hour * 3600 + time.minute * 60 + time.second
    return min(seconds_of_day // WINDOW_LENGTH_SEC, 7)


def pixel_window_mask(times, start, end):
    values = np.asarray(times)
    start64 = np.datetime64(start)
    end64 = np.datetime64(end)
    finite = ~np.isnat(values)
    return finite & (values >= start64) & (values < end64)


def enumerate_windows(start_date, end_date):
    out = []
    day = start_date
    while day <= end_date:
        for idx in range(8):
            out.append((day, idx))
        day = day + timedelta(days=1)
    return out
