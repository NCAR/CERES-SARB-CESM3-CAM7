from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr
import yaml
from davinci_monet.config.schema import MonetConfig
from davinci_monet.geography import AEROSOL_REGIONS

from scripts.prepare_2008_regional_aod import (
    DEFAULT_OUTPUT_DIR,
    OUTPUT_PRODUCT,
    REGION_DISPLAY_NAMES,
    area_weighted_mean,
    build_regional_timeseries,
    monthly_run_dir,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT
    / "analyses"
    / "davinci"
    / "era5-modis-aod-nudging-band-optics-2008-regional-aod.yaml"
)


def test_regional_config_defines_catalog_sources_and_pdf_plots() -> None:
    cfg = yaml.safe_load(CONFIG.read_text())
    MonetConfig(**cfg)

    assert cfg["analysis"]["output_dir"] == str(DEFAULT_OUTPUT_DIR)
    assert cfg["analysis"]["domain"] == "global"
    assert set(cfg["sources"]) == set(AEROSOL_REGIONS)
    assert cfg["plot_suites"] == {}
    assert cfg["pairs"] == {}

    product = str(DEFAULT_OUTPUT_DIR / OUTPUT_PRODUCT)
    for region, source in cfg["sources"].items():
        assert source["type"] == "generic"
        assert source["files"] == product
        assert source["variables"]["aod"]["source_name"] == region
        assert source["variables"]["aod"]["units"] == "1"
        assert source["variables"]["aod"]["style_preset"] == "geosit_aod"

    individual = {name: plot for name, plot in cfg["plots"].items() if "source" in plot}
    overlays = {name: plot for name, plot in cfg["plots"].items() if "sources" in plot}
    assert len(individual) == len(AEROSOL_REGIONS)
    assert len(overlays) == 4
    assert {plot["source"] for plot in individual.values()} == set(AEROSOL_REGIONS)
    assert all(plot["variable"] == "aod" for plot in individual.values())
    assert all(plot["formats"] == ["pdf"] for plot in cfg["plots"].values())
    assert all("2008" not in plot["title"] for plot in cfg["plots"].values())
    assert all(len(plot["sources"]) >= 3 for plot in overlays.values())
    assert cfg["inspection"] == {
        "enabled": True,
        "required": True,
        "presets": [],
        "preview_format": "png",
    }


def test_monthly_run_dir_selects_completed_march() -> None:
    data_root = Path("/data")
    assert monthly_run_dir(data_root, 2).name.endswith("2008-02")
    assert monthly_run_dir(data_root, 3).name.endswith("2008-03-complete")
    assert monthly_run_dir(data_root, 4).name.endswith("2008-04")


def test_area_weighted_mean_renormalizes_around_missing_cells() -> None:
    aod = xr.DataArray(
        [[1.0, np.nan], [3.0, 5.0]],
        dims=("lat", "lon"),
        coords={"lat": [0.0, 60.0], "lon": [-10.0, 10.0]},
    )

    result = area_weighted_mean(aod, (-20.0, 20.0, -5.0, 65.0))

    assert result == pytest.approx(2.5)


def test_area_weighted_mean_normalizes_zero_to_360_longitudes() -> None:
    aod = xr.DataArray(
        [[100.0, 2.0, 3.0, 100.0]],
        dims=("lat", "lon"),
        coords={"lat": [35.0], "lon": [230.0, 240.0, 260.0, 270.0]},
    )

    result = area_weighted_mean(aod, AEROSOL_REGIONS["western_us"])

    assert result == pytest.approx(2.5)


def test_build_regional_timeseries_contains_all_months_and_regions() -> None:
    monthly = {
        month: xr.DataArray(
            np.full((7, 11), float(month)),
            dims=("lat", "lon"),
            coords={
                "lat": [-60.0, -30.0, 0.0, 15.0, 30.0, 45.0, 60.0],
                "lon": [
                    -160.0,
                    -120.0,
                    -100.0,
                    -80.0,
                    -40.0,
                    0.0,
                    20.0,
                    40.0,
                    80.0,
                    120.0,
                    160.0,
                ],
            },
        )
        for month in range(1, 13)
    }

    result = build_regional_timeseries(monthly)

    assert set(result.data_vars) == set(AEROSOL_REGIONS)
    assert result.sizes == {"time": 12}
    np.testing.assert_array_equal(result["time"].dt.month, np.arange(1, 13))
    for region in AEROSOL_REGIONS:
        np.testing.assert_allclose(result[region], np.arange(1.0, 13.0))
        assert result[region].attrs["region_name"] == REGION_DISPLAY_NAMES[region]


def test_build_regional_timeseries_requires_all_months() -> None:
    with pytest.raises(ValueError, match="all twelve"):
        build_regional_timeseries({})
