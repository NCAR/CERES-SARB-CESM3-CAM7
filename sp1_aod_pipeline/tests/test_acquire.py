from pathlib import Path

import pytest

from sp1_aod_pipeline import acquire


def test_collection_specs_are_correct():
    assert acquire.SP1_COLLECTIONS["mod04"].short_name == "MOD04_L2"
    assert acquire.SP1_COLLECTIONS["mod04"].version == "6.1"
    assert acquire.SP1_COLLECTIONS["myd04"].short_name == "MYD04_L2"
    assert acquire.SP1_COLLECTIONS["myd04"].version == "6.1"
    viirs = acquire.SP1_COLLECTIONS["aerdb_noaa20"]
    assert viirs.short_name == "AERDB_L2_VIIRS_NOAA20"
    assert viirs.version == "2"


def test_stage_sp1_dry_run_searches_without_download(tmp_path):
    calls = {}

    results = acquire.stage_sp1(
        "mod04",
        "2020-06-15",
        "2020-06-16",
        str(tmp_path),
        dry_run=True,
        login=lambda: calls.setdefault("login", True),
        search=lambda spec, temporal: ["g1", "g2"],
        download=lambda results, dest: pytest.fail("download in dry run"),
    )

    assert calls["login"] is True
    assert list(results) == ["g1", "g2"]
    assert not (tmp_path / "modis" / "terra").exists()


def test_stage_sp1_downloads_into_spec_subpath(tmp_path):
    seen = {}

    def download(results, dest):
        seen["dest"] = dest
        return [Path(dest) / "f.nc"]

    out = acquire.stage_sp1(
        "aerdb_noaa20",
        "2020-06-15",
        "2020-06-16",
        str(tmp_path),
        login=lambda: None,
        search=lambda spec, temporal: ["g1"],
        download=download,
    )

    assert Path(seen["dest"]) == tmp_path / "viirs" / "noaa20"
    assert (tmp_path / "viirs" / "noaa20").is_dir()
    assert out == [tmp_path / "viirs" / "noaa20" / "f.nc"]
