from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr
import yaml
from davinci_monet.config.schema import MonetConfig

from scripts.prepare_2008_optics_composites import (
    BAND_KINDS,
    GROUP_MONTHS,
    MONTH_DAYS,
    build_band_composites,
    monthly_run_dir,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT
    / "analyses"
    / "davinci"
    / "era5-modis-aod-nudging-band-optics-2008-composites.yaml"
)
DATA_ROOT = Path("/glade/work/fillmore/Data/CERES-SARB-CAM7")
RUN_DIR = DATA_ROOT / "runs" / ("era5-modis-aod-nudging-band-optics-2008-composites")


def test_composite_config_uses_staged_products_and_global_sarb_suites() -> None:
    cfg = yaml.safe_load(CONFIG.read_text())
    MonetConfig(**cfg)

    assert cfg["analysis"]["start_time"] == "2008-01-01T00:00:00"
    assert cfg["analysis"]["end_time"] == "2008-12-31T23:59:59"
    assert cfg["analysis"]["output_dir"] == str(RUN_DIR)
    assert cfg["analysis"]["domain"] == "global"
    assert not cfg.get("analyses")
    assert set(cfg["sources"]) == set(BAND_KINDS)
    assert set(cfg["plot_suites"]) == set(BAND_KINDS)

    for name, source in cfg["sources"].items():
        assert source["type"] == "generic"
        assert source["files"] == str(RUN_DIR / "products" / name / "analysis.nc")
    for suite in cfg["plot_suites"].values():
        assert suite["preset"] == "sarb_band_aerosol_optics"
        assert suite["overrides"]["show_coastlines"] is True
        assert suite["overrides"]["show_countries"] is False
        assert suite["overrides"]["show_states"] is False
        assert suite["overrides"]["show_gridlines"] is True
        assert suite["overrides"]["gridline_style"] == "-"


def test_monthly_run_dir_selects_complete_march() -> None:
    assert monthly_run_dir(DATA_ROOT, 2).name.endswith("2008-02")
    assert monthly_run_dir(DATA_ROOT, 3).name.endswith("2008-03-complete")
    assert monthly_run_dir(DATA_ROOT, 4).name.endswith("2008-04")


def test_shortwave_composites_preserve_physical_weighting() -> None:
    monthly: dict[int, xr.Dataset] = {}
    for month in range(1, 13):
        extinction = float(month)
        single_scatter_albedo = 0.40 + month / 100.0
        asymmetry = 0.60 + month / 200.0
        monthly[month] = xr.Dataset(
            {
                "column_aod": (("lat", "lon"), [[extinction]]),
                "single_scatter_albedo": (
                    ("lat", "lon"),
                    [[single_scatter_albedo]],
                ),
                "asymmetry": (("lat", "lon"), [[asymmetry]]),
            },
            coords={"lat": [0.0], "lon": [0.0]},
        )

    composites = build_band_composites(monthly, "shortwave")
    assert list(composites["group"].values) == list(GROUP_MONTHS)

    months = GROUP_MONTHS["DJF"]
    weights = np.asarray([MONTH_DAYS[month] for month in months], dtype=float)
    extinction = np.asarray(months, dtype=float)
    ssa = 0.40 + extinction / 100.0
    asymmetry = 0.60 + extinction / 200.0
    expected_aod = np.average(extinction, weights=weights)
    expected_ssa = np.sum(weights * extinction * ssa) / np.sum(weights * extinction)
    expected_asymmetry = np.sum(weights * extinction * ssa * asymmetry) / np.sum(
        weights * extinction * ssa
    )

    assert composites["column_aod"].sel(group="DJF").item() == pytest.approx(
        expected_aod
    )
    assert composites["single_scatter_albedo"].sel(group="DJF").item() == pytest.approx(
        expected_ssa
    )
    assert composites["asymmetry"].sel(group="DJF").item() == pytest.approx(
        expected_asymmetry
    )


def test_longwave_composites_retain_extinction_and_scattering_means() -> None:
    monthly: dict[int, xr.Dataset] = {}
    for month in range(1, 13):
        monthly[month] = xr.Dataset(
            {
                "column_extinction": (("lat", "lon"), [[float(month)]]),
                "column_scattering": (("lat", "lon"), [[float(month) / 2.0]]),
                "asymmetry": (("lat", "lon"), [[0.7]]),
            },
            coords={"lat": [0.0], "lon": [0.0]},
        )

    composites = build_band_composites(monthly, "longwave")
    weights = np.asarray(list(MONTH_DAYS.values()), dtype=float)
    months = np.arange(1.0, 13.0)
    expected_extinction = np.average(months, weights=weights)
    expected_scattering = np.average(months / 2.0, weights=weights)

    assert composites["column_extinction"].sel(group="Annual").item() == pytest.approx(
        expected_extinction
    )
    assert composites["column_scattering"].sel(group="Annual").item() == pytest.approx(
        expected_scattering
    )
    assert composites["asymmetry"].sel(group="Annual").item() == pytest.approx(0.7)
