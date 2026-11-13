from __future__ import annotations

import csv

import numpy as np
import pytest

from scripts.summarize_2008_regional_aeronet_band_comparison import (
    BANDS,
    DEFAULT_TABLE_DIR,
    REGIONAL_FILENAME,
    REPORT_FILENAME,
    WAVELENGTH_FILENAME,
    paired_statistics,
)


def test_paired_statistics_use_aeronet_as_reference() -> None:
    statistics = paired_statistics(
        np.asarray([1.0, 2.0, np.nan, 3.0]),
        np.asarray([2.0, 2.0, 100.0, 4.0]),
    )

    assert statistics["paired_days"] == 3
    assert statistics["aeronet_mean"] == pytest.approx(2.0)
    assert statistics["cam7_mean"] == pytest.approx(8.0 / 3.0)
    assert statistics["mean_bias"] == pytest.approx(2.0 / 3.0)
    assert statistics["mean_absolute_error"] == pytest.approx(2.0 / 3.0)
    assert statistics["rmse"] == pytest.approx(np.sqrt(2.0 / 3.0))
    assert statistics["correlation"] == pytest.approx(0.8660254038)


def test_checked_in_tables_have_expected_rows_and_schema() -> None:
    with (DEFAULT_TABLE_DIR / REGIONAL_FILENAME).open(
        encoding="utf-8", newline=""
    ) as stream:
        regional = list(csv.DictReader(stream))
    with (DEFAULT_TABLE_DIR / WAVELENGTH_FILENAME).open(
        encoding="utf-8", newline=""
    ) as stream:
        wavelengths = list(csv.DictReader(stream))

    assert len(regional) == 46
    assert len(wavelengths) == len(BANDS) == 4
    assert {row["band"] for row in regional} == set(BANDS)
    assert {row["band"] for row in wavelengths} == set(BANDS)
    assert all(int(row["paired_days"]) > 0 for row in regional)
    assert all(-1.0 <= float(row["correlation"]) <= 1.0 for row in regional)
    assert all(float(row["mean_absolute_error"]) >= 0.0 for row in regional)
    assert all(float(row["rmse"]) >= 0.0 for row in regional)
    assert (DEFAULT_TABLE_DIR / REPORT_FILENAME).is_file()


def test_report_documents_metric_direction_and_pooling() -> None:
    report = (DEFAULT_TABLE_DIR / REPORT_FILENAME).read_text(encoding="utf-8")

    assert "Mean bias (MB) is `CAM7 - AERONET`" in report
    assert "equal weight per available region-day" in report
    assert "CAM7 546 nm vs AERONET 500 nm" in report
    assert "DAVINCI metric definitions" in report
