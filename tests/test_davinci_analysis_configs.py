from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr
import yaml
from davinci_monet.analysis.gridded import GriddedAnalysis
from davinci_monet.config.schema import MonetConfig
from davinci_monet.pipeline.stages.base import PipelineContext, StageStatus
from davinci_monet.pipeline.stages.load import LoadSourcesStage

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "analyses" / "davinci"
DATA_ROOT = "/glade/work/fillmore/Data/CERES-SARB-CAM7"
RAW_DATA_KEYS = {"files", "filename", "source_name"}
BANNED_PUBLIC_SLUGS = ("sp1", "sp2", "sp3")
CONFIG_NAMES = [
    "cam-aod-analysis-july-2008.yaml",
    "cam-aod-monthly-analysis-july-2008.yaml",
    "modis-aod-monthly-analysis-2008-v2.yaml",
    "modis-viirs-aod-monthly-analysis-july-2008.yaml",
]
SP3_BAND_CONFIG_NAME = "sp3-dense3-aodnudged-retry1-daily-band-maps-20080701.yaml"
MODIS_NUDGED_BAND_CONFIG_NAME = "modis-aod-nudging-band-optics-july-2008.yaml"
FULL_MONTH_OPTICS_CONFIG_NAME = (
    "era5-modis-aod-nudging-band-optics-july-2008.yaml"
)
MARCH_2008_COMPLETE_OPTICS_CONFIG_NAME = (
    "era5-modis-aod-nudging-band-optics-2008-03-complete.yaml"
)
SP3_SAMPLE_BANDS = ("sw01", "sw05", "sw10", "sw14", "lw01", "lw06", "lw12")


def _public_strings(value: object, path: tuple[str, ...] = ()) -> list[str]:
    if path and path[-1] in RAW_DATA_KEYS:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            if key_text not in RAW_DATA_KEYS:
                strings.append(key_text)
            strings.extend(_public_strings(child, (*path, key_text)))
        return strings
    if isinstance(value, list):
        strings = []
        for index, child in enumerate(value):
            strings.extend(_public_strings(child, (*path, str(index))))
        return strings
    return []


def _write_sarb_optics_file(path: Path, scale: float) -> None:
    layer_extinction = np.full((2, 2, 2), scale, dtype=np.float32)
    layer_scattering = layer_extinction * 0.5
    layer_asymmetry = np.full((2, 2, 2), 0.7, dtype=np.float32)
    column_extinction = layer_extinction.sum(axis=0)
    ds = xr.Dataset(
        {
            "Extinction_Column_Optical_Depth": (
                ("lat", "lon"),
                column_extinction.astype(np.float32),
            ),
            "Extinction_Layer_Optical_Depth": (
                ("lev", "lat", "lon"),
                layer_extinction,
            ),
            "Scattering_Layer_Optical_Depth": (
                ("lev", "lat", "lon"),
                layer_scattering,
            ),
            "Layer_Asymmetry_Parameter": (
                ("lev", "lat", "lon"),
                layer_asymmetry,
            ),
        },
        coords={"lev": [1, 2], "lat": [-1.0, 1.0], "lon": [0.0, 90.0]},
        attrs={"geometry": "grid"},
    )
    ds.to_netcdf(path)


@pytest.mark.parametrize(
    "name",
    CONFIG_NAMES,
)
def test_davinci_aod_configs_are_descriptive_and_parse(name: str) -> None:
    path = CONFIGS / name
    assert path.exists()
    cfg = yaml.safe_load(path.read_text())
    MonetConfig(**cfg)
    assert not any(slug in name.lower() for slug in BANNED_PUBLIC_SLUGS)
    assert (
        cfg["analysis"]["output_dir"]
        == f"{DATA_ROOT}/runs/{name.removesuffix('.yaml')}"
    )
    assert "/runs/" in cfg["analysis"]["output_dir"]
    assert "analyses" in cfg
    assert cfg["plot_suites"]
    assert cfg["inspection"]["enabled"] is True
    assert cfg["inspection"]["required"] is True
    public_text = "\n".join(_public_strings(cfg))
    public_text_lower = public_text.lower()
    assert not any(slug in public_text_lower for slug in BANNED_PUBLIC_SLUGS)


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_davinci_aod_configs_use_aod_plot_suites(name: str) -> None:
    cfg = yaml.safe_load((CONFIGS / name).read_text())
    analysis_names = set(cfg["analyses"])
    for suite in cfg["plot_suites"].values():
        assert suite["preset"] == "gridded_aod_diagnostics"
        assert suite["source"] in analysis_names
        assert suite["output_subdir"].startswith("plots/")
        assert suite["overrides"]["show_global_mean"] is True
        assert suite["overrides"]["tight_layout"] is True
        assert suite["overrides"]["tight_layout_pad"] == 0.5
    assert "gridded_aod_diagnostics" in cfg["inspection"]["presets"]


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_davinci_aod_configs_use_generic_nested_sources(name: str) -> None:
    cfg = yaml.safe_load((CONFIGS / name).read_text())
    for source in cfg["sources"].values():
        assert source["type"] == "generic"
        assert source["combine"] == "nested"
        assert source["concat_dim"] == "time"
        assert source["parallel"] is False


def test_cam_aod_config_uses_analysis_terms() -> None:
    cfg = yaml.safe_load((CONFIGS / "cam-aod-analysis-july-2008.yaml").read_text())
    assert cfg["analysis"]["start_time"] == "2008-07-01T00:00:00"
    assert cfg["analysis"]["end_time"] == "2008-07-05T23:59:59"
    assert set(cfg["analyses"]) == {"daily_aod", "five_day_aod"}
    assert set(cfg["plot_suites"]) == {"daily_aod", "five_day_aod"}
    for analysis_name in ("daily_aod", "five_day_aod"):
        fields = cfg["analyses"][analysis_name]["fields"]
        roles = cfg["analyses"][analysis_name]["roles"]
        assert "analyzed_aod" in fields
        assert "first_guess_aod" in fields
        assert "analysis_increment_aod" in fields
        assert roles["analysis"] == "analyzed_aod_source"
        assert roles["first_guess"] == "first_guess_aod_source"
    public_text = "\n".join(_public_strings(cfg))
    assert "AODNDG_MODEL_POST" not in public_text
    assert "AODNDG_MODEL_PRE" not in public_text
    assert "CAM7 Analyzed AOD" in public_text
    assert "CAM7 Pre-Correction AOD" in public_text
    assert "CAM7 AOD Correction" in public_text
    assert "MODIS Observed AOD" in public_text
    assert "First-Guess" not in public_text
    assert "First Guess" not in public_text


def test_cam_aod_monthly_config_preserves_five_day_record() -> None:
    monthly = yaml.safe_load(
        (CONFIGS / "cam-aod-monthly-analysis-july-2008.yaml").read_text()
    )
    five_day = yaml.safe_load((CONFIGS / "cam-aod-analysis-july-2008.yaml").read_text())

    assert five_day["analysis"]["end_time"] == "2008-07-05T23:59:59"
    assert monthly["analysis"]["start_time"] == "2008-07-01T00:00:00"
    assert monthly["analysis"]["end_time"] == "2008-07-31T23:59:59"
    assert monthly["analysis"]["output_dir"] == (
        f"{DATA_ROOT}/runs/cam-aod-monthly-analysis-july-2008"
    )
    assert set(monthly["analyses"]) == {"daily_aod", "monthly_aod"}
    assert set(monthly["plot_suites"]) == {"daily_aod", "monthly_aod"}
    assert monthly["analyses"]["monthly_aod"]["groupby"] == "all"
    assert "five_day_aod" not in monthly["analyses"]


def test_modis_viirs_config_declares_monthly_formula_fields() -> None:
    cfg = yaml.safe_load(
        (CONFIGS / "modis-viirs-aod-monthly-analysis-july-2008.yaml").read_text()
    )
    fields = cfg["analyses"]["monthly_aod"]["fields"]
    assert (
        fields["observation_aod"]["formula"]
        == 'weighted_mean(observation, count, dim="time")'
    )
    assert (
        fields["observation_uncertainty_aod"]["formula"]
        == 'weighted_mean(uncertainty, count, dim="time")'
    )
    assert fields["observation_count"]["formula"] == 'sum(count, dim="time")'
    assert (
        fields["observation_fraction"]["formula"] == 'fraction(count > 0, dim="time")'
    )


def test_modis_annual_config_declares_count_weighted_monthly_aod() -> None:
    cfg = yaml.safe_load(
        (CONFIGS / "modis-aod-monthly-analysis-2008-v2.yaml").read_text()
    )
    assert cfg["analysis"]["start_time"] == "2008-01-01T00:00:00"
    assert cfg["analysis"]["end_time"] == "2008-12-31T23:59:59"
    assert cfg["analysis"]["domain"] == "global"
    source = cfg["sources"]["modis_gridded_aod"]
    assert source["files"] == (
        f"{DATA_ROOT}/AOD_f09_3hr_2008_v2/"
        "MODIS_VIIRS_AOD_3hr_f09.2008*.nc"
    )
    analysis = cfg["analyses"]["monthly_aod"]
    assert analysis["groupby"] == "month"
    assert analysis["roles"] == {
        "observation": "aod_weighted_mean",
        "count": "aod_count",
    }
    assert set(analysis["fields"]) == {"observation_aod"}
    field = analysis["fields"]["observation_aod"]
    assert field["formula"] == 'weighted_mean(observation, count, dim="time")'
    assert field["style_preset"] == "geosit_aod"
    suite = cfg["plot_suites"]["monthly_aod"]
    assert suite["group"] == "monthly"
    assert suite["source"] == "monthly_aod"


def test_sarb_optics_config_uses_descriptive_names() -> None:
    path = CONFIGS / "sarb-band-aerosol-optics-july-2008.yaml"
    assert path.exists()
    cfg = yaml.safe_load(path.read_text())
    MonetConfig(**cfg)
    assert (
        cfg["analysis"]["output_dir"]
        == f"{DATA_ROOT}/runs/sarb-band-aerosol-optics-july-2008"
    )
    assert cfg["analysis"]["start_time"] == "2008-07-01T00:00:00"
    assert cfg["analysis"]["end_time"] == "2008-07-11T00:00:00"
    public_text = "\n".join(_public_strings(cfg))
    public_text_lower = public_text.lower()
    assert not any(slug in public_text_lower for slug in BANNED_PUBLIC_SLUGS)
    analysis_names = set(cfg["analyses"])
    assert set(cfg["plot_suites"]) == {"visible_optics", "longwave_window_optics"}
    for suite in cfg["plot_suites"].values():
        assert suite["preset"] == "sarb_band_aerosol_optics"
        assert suite["source"] in analysis_names
        assert suite["output_subdir"].startswith("plots/")
        assert suite["overrides"]["show_global_mean"] is True
        assert suite["overrides"]["tight_layout"] is True
        assert suite["overrides"]["show_countries"] is False
        assert suite["overrides"]["show_states"] is False
    assert "sarb_band_aerosol_optics" in cfg["inspection"]["presets"]


def test_sarb_optics_config_declares_formula_fields() -> None:
    cfg = yaml.safe_load(
        (CONFIGS / "sarb-band-aerosol-optics-july-2008.yaml").read_text()
    )
    for source in cfg["sources"].values():
        assert source["type"] == "generic"
        assert source["combine"] == "nested"
        assert source["concat_dim"] == "time"
        assert source["parallel"] is False
        assert "AER_MAM4_*" not in source["files"]
    assert (
        "AER_MAM4_SW05.200807*.nc"
        in cfg["sources"]["visible_band_optics_files"]["files"]
    )
    assert "sp3v2_verify10_lut_on_camref_dense3_20260709" in (
        cfg["sources"]["visible_band_optics_files"]["files"]
    )
    assert (
        "AER_MAM4_LW06.200807*.nc"
        in cfg["sources"]["longwave_window_optics_files"]["files"]
    )
    visible_fields = cfg["analyses"]["sarb_visible_optics"]["fields"]
    assert (
        visible_fields["visible_column_aod"]["formula"]
        == 'mean(column_extinction, dim="time")'
    )
    assert (
        visible_fields["visible_single_scatter_albedo"]["formula"]
        == 'sum(mean(layer_scattering, dim="time"), dim="z") / sum(mean(layer_extinction, dim="time"), dim="z")'
    )
    assert (
        visible_fields["visible_asymmetry"]["formula"]
        == 'sum(mean(layer_asymmetry * layer_scattering, dim="time"), dim="z") / sum(mean(layer_scattering, dim="time"), dim="z")'
    )
    longwave_fields = cfg["analyses"]["sarb_longwave_window_optics"]["fields"]
    assert (
        longwave_fields["lw_window_scattering"]["formula"]
        == 'sum(mean(layer_scattering, dim="time"), dim="z")'
    )
    assert longwave_fields["lw_window_extinction"]["style_preset"] == "geosit_aod"


def test_modis_nudged_band_optics_config_targets_complete_ten_day_run() -> None:
    cfg = yaml.safe_load((CONFIGS / MODIS_NUDGED_BAND_CONFIG_NAME).read_text())
    MonetConfig(**cfg)

    assert cfg["analysis"]["start_time"] == "2008-07-01T00:00:00"
    assert cfg["analysis"]["end_time"] == "2008-07-10T23:59:59"
    assert cfg["analysis"]["output_dir"] == (
        f"{DATA_ROOT}/runs/modis-aod-nudging-band-optics-july-2008-lw-asymmetry"
    )
    expected_run = "sp3v2_verify10_lut_aodnudged_camref_dense3_retry1_20260709"
    expected_bands = {
        "ultraviolet": "SW02",
        "visible": "SW05",
        "near_infrared": "SW08",
        "shortwave_infrared": "SW11",
        "water_vapor": "LW03",
        "ozone": "LW06",
        "atmospheric_window": "LW07",
        "carbon_dioxide": "LW09",
    }
    assert set(cfg["sources"]) == {f"{name}_band_files" for name in expected_bands}
    assert set(cfg["analyses"]) == {f"{name}_optics" for name in expected_bands}
    assert set(cfg["plot_suites"]) == {f"{name}_optics" for name in expected_bands}
    for name, band in expected_bands.items():
        source = cfg["sources"][f"{name}_band_files"]
        assert expected_run in source["files"]
        assert source["files"].endswith(f"AER_MAM4_{band}.200807*.nc")
        assert source["parallel"] is False
        analysis = cfg["analyses"][f"{name}_optics"]
        assert analysis["source"] == f"{name}_band_files"
        assert analysis["groupby"] == "all"
        suite = cfg["plot_suites"][f"{name}_optics"]
        assert suite["source"] == f"{name}_optics"
        assert suite["preset"] == "sarb_band_aerosol_optics"
        assert suite["output_subdir"].startswith("plots/")
        expected_field_count = 3
        assert len(suite["fields"]) == expected_field_count
        field_titles = [
            options["title"]
            for field, options in suite["overrides"].items()
            if field in suite["fields"]
        ]
        assert len(field_titles) == expected_field_count
        assert all("µm" in title for title in field_titles)
        assert all(band not in title for title in field_titles)

        if band.startswith("LW"):
            source_variables = source["variables"]
            assert source_variables["layer_asymmetry_source"]["source_name"] == (
                "Layer_Asymmetry_Parameter"
            )
            fields = analysis["fields"]
            assert fields["asymmetry"]["formula"] == (
                'sum(mean(layer_asymmetry * layer_scattering, dim="time"), dim="z") '
                '/ sum(mean(layer_scattering, dim="time"), dim="z")'
            )
            assert any(field.endswith("_asymmetry") for field in suite["fields"])

    public_text = "\n".join(_public_strings(cfg)).lower()
    assert not any(slug in public_text for slug in BANNED_PUBLIC_SLUGS)
    for suite in cfg["plot_suites"].values():
        assert suite["overrides"]["show_global_mean"] is True
        assert suite["overrides"]["tight_layout"] is True
        assert suite["overrides"]["tight_layout_pad"] == 0.5
        assert suite["overrides"]["show_countries"] is False
        assert suite["overrides"]["show_states"] is False


def test_full_month_optics_config_targets_registered_july_run() -> None:
    cfg = yaml.safe_load((CONFIGS / FULL_MONTH_OPTICS_CONFIG_NAME).read_text())
    MonetConfig(**cfg)

    assert cfg["analysis"]["start_time"] == "2008-07-01T00:00:00"
    assert cfg["analysis"]["end_time"] == "2008-07-31T23:59:59"
    assert cfg["analysis"]["output_dir"] == (
        f"{DATA_ROOT}/runs/{FULL_MONTH_OPTICS_CONFIG_NAME.removesuffix('.yaml')}"
    )
    expected_case = "sp3_200807_mam4_modis_era5_optics"
    expected_bands = {
        "ultraviolet": "SW02",
        "visible": "SW05",
        "near_infrared": "SW08",
        "shortwave_infrared": "SW11",
        "water_vapor": "LW03",
        "ozone": "LW06",
        "atmospheric_window": "LW07",
        "carbon_dioxide": "LW09",
    }

    assert set(cfg["sources"]) == {f"{name}_band_files" for name in expected_bands}
    assert set(cfg["analyses"]) == {f"{name}_optics" for name in expected_bands}
    assert set(cfg["plot_suites"]) == {f"{name}_optics" for name in expected_bands}
    for name, band in expected_bands.items():
        source = cfg["sources"][f"{name}_band_files"]
        assert expected_case in source["files"]
        assert source["files"].endswith(f"AER_MAM4_{band}.*.nc")
        assert source["parallel"] is False
        analysis = cfg["analyses"][f"{name}_optics"]
        assert analysis["source"] == f"{name}_band_files"
        assert analysis["groupby"] == "all"
        assert all(
            field["long_name"].startswith("Monthly mean")
            for field in analysis["fields"].values()
        )
        suite = cfg["plot_suites"][f"{name}_optics"]
        assert suite["source"] == f"{name}_optics"
        assert suite["preset"] == "sarb_band_aerosol_optics"
        assert suite["output_subdir"].startswith("plots/")
        assert suite["overrides"]["show_coastlines"] is True
        assert suite["overrides"]["show_countries"] is False
        assert suite["overrides"]["show_states"] is False
        assert suite["overrides"]["show_gridlines"] is True
        assert suite["overrides"]["gridline_style"] == "-"

    public_text = "\n".join(_public_strings(cfg)).lower()
    assert not any(slug in public_text for slug in BANNED_PUBLIC_SLUGS)


def test_complete_march_optics_config_combines_original_and_continuation() -> None:
    cfg = yaml.safe_load(
        (CONFIGS / MARCH_2008_COMPLETE_OPTICS_CONFIG_NAME).read_text()
    )
    MonetConfig(**cfg)

    analysis = cfg["analysis"]
    assert analysis["start_time"] == "2008-03-01T00:00:00"
    assert analysis["end_time"] == "2008-03-31T23:59:59"
    assert analysis["domain"] == "global"
    assert analysis["output_dir"] == (
        f"{DATA_ROOT}/runs/era5-modis-aod-nudging-band-optics-2008-03-complete"
    )

    case_root = (
        "/glade/derecho/scratch/fillmore/CERES-SARB-CAM7/monthly_2008_v1/"
        "sp3_200803_mam4_modis_era5_optics_spinup10_v1"
    )
    expected_bands = {
        "ultraviolet": "SW02",
        "visible": "SW05",
        "near_infrared": "SW08",
        "shortwave_infrared": "SW11",
        "water_vapor": "LW03",
        "ozone": "LW06",
        "atmospheric_window": "LW07",
        "carbon_dioxide": "LW09",
    }
    for label, band in expected_bands.items():
        source = cfg["sources"][f"{label}_band_files"]
        assert source["files"] == [
            f"{case_root}/optics/AER_MAM4_{band}.200803*.nc",
            (
                f"{case_root}/optics_continuation_20080308T210000_v1/"
                f"AER_MAM4_{band}.200803*.nc"
            ),
        ]
        assert source["parallel"] is False

        suite = cfg["plot_suites"][f"{label}_optics"]
        assert suite["preset"] == "sarb_band_aerosol_optics"
        assert suite["overrides"]["show_coastlines"] is True
        assert suite["overrides"]["show_countries"] is False
        assert suite["overrides"]["show_states"] is False
        assert suite["overrides"]["show_gridlines"] is True

    public_text = "\n".join(_public_strings(cfg)).lower()
    assert not any(slug in public_text for slug in BANNED_PUBLIC_SLUGS)


def test_sp3_sampled_band_config_uses_davinci_title_rules() -> None:
    cfg = yaml.safe_load((CONFIGS / SP3_BAND_CONFIG_NAME).read_text())
    MonetConfig(**cfg)

    assert cfg["analysis"]["start_time"] == "2008-07-01T00:00:00"
    assert cfg["analysis"]["end_time"] == "2008-07-01T21:00:00"
    assert (
        cfg["analysis"]["output_dir"]
        == f"{DATA_ROOT}/runs/{SP3_BAND_CONFIG_NAME.removesuffix('.yaml')}"
    )
    assert cfg["inspection"]["enabled"] is True
    assert cfg["inspection"]["required"] is True

    expected_sources = {f"{band}_band_optics_files" for band in SP3_SAMPLE_BANDS}
    expected_analyses = {f"{band}_band_optics" for band in SP3_SAMPLE_BANDS}
    assert set(cfg["sources"]) == expected_sources
    assert set(cfg["analyses"]) == expected_analyses
    assert set(cfg["plot_suites"]) == set()
    assert len(cfg["plots"]) == len(SP3_SAMPLE_BANDS) * 2

    for band in SP3_SAMPLE_BANDS:
        source = cfg["sources"][f"{band}_band_optics_files"]
        assert source["type"] == "generic"
        assert source["combine"] == "nested"
        assert source["concat_dim"] == "time"
        assert source["parallel"] is False
        assert f"AER_MAM4_{band.upper()}.20080701.*.nc" in source["files"]
        assert "AER_MAM4_*" not in source["files"]

        analysis = cfg["analyses"][f"{band}_band_optics"]
        assert analysis["type"] == "gridded_analysis"
        assert analysis["source"] == f"{band}_band_optics_files"
        assert analysis["groupby"] == "all"
        fields = analysis["fields"]
        assert fields["column_extinction"]["style_preset"] == "geosit_aod"
        assert fields["column_extinction"]["formula"] == 'mean(column_extinction, dim="time")'
        assert fields["column_mean_asymmetry"]["formula"] == (
            'sum(mean(layer_asymmetry * layer_scattering, dim="time"), dim="z") '
            '/ sum(mean(layer_scattering, dim="time"), dim="z")'
        )

    for plot in cfg["plots"].values():
        title = plot["title"]
        assert "2008" not in title
        assert "SP3" not in title
        assert "Dense3" not in title
        assert "AOD-Nudged" not in title
        assert plot["formats"] == ["pdf"]
        assert plot["show_coastlines"] is True
        assert plot["show_countries"] is False
        assert plot["show_gridlines"] is True
        if plot["variable"] == "column_extinction":
            assert plot["style_preset"] == "geosit_aod"
        else:
            assert plot["vmin"] == 0.0
            assert plot["vmax"] == 1.0


def test_sarb_optics_config_runs_with_standardized_vertical_dimension(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _write_sarb_optics_file(source_dir / "AER_MAM4_SW05.20080701.00000.nc", 1.0)
    _write_sarb_optics_file(source_dir / "AER_MAM4_SW05.20080701.10800.nc", 2.0)
    _write_sarb_optics_file(source_dir / "AER_MAM4_LW06.20080701.00000.nc", 0.2)
    _write_sarb_optics_file(source_dir / "AER_MAM4_LW06.20080701.10800.nc", 0.4)
    cfg = yaml.safe_load(
        (CONFIGS / "sarb-band-aerosol-optics-july-2008.yaml").read_text()
    )
    cfg["analysis"]["output_dir"] = str(tmp_path / "run")
    cfg["sources"]["visible_band_optics_files"]["files"] = str(
        source_dir / "AER_MAM4_SW05.200807*.nc"
    )
    cfg["sources"]["longwave_window_optics_files"]["files"] = str(
        source_dir / "AER_MAM4_LW06.200807*.nc"
    )

    model = MonetConfig(**cfg)
    context = PipelineContext(config=model)
    load_result = LoadSourcesStage().execute(context)

    assert load_result.status is StageStatus.COMPLETED, load_result.error
    assert "z" in context.sources["visible_band_optics_files"].data.dims
    assert "lev" not in context.sources["visible_band_optics_files"].data.dims

    analysis = GriddedAnalysis()
    visible = analysis.analyze(
        context.sources["visible_band_optics_files"].data,
        model.analyses["sarb_visible_optics"],
    )
    longwave = analysis.analyze(
        context.sources["longwave_window_optics_files"].data,
        model.analyses["sarb_longwave_window_optics"],
    )
    np.testing.assert_allclose(visible["visible_column_aod"].values, 3.0)
    np.testing.assert_allclose(visible["visible_single_scatter_albedo"].values, 0.5)
    np.testing.assert_allclose(visible["visible_asymmetry"].values, 0.7, atol=1e-6)
    np.testing.assert_allclose(longwave["lw_window_scattering"].values, 0.3)
    np.testing.assert_allclose(longwave["lw_window_extinction"].values, 0.6)
