from datetime import timedelta
from pathlib import Path
import importlib.util
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "monthly_cases", ROOT / "scripts/setup_monthly_2008_cases.py"
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

submit_spec = importlib.util.spec_from_file_location(
    "submit_monthly", ROOT / "scripts/submit_monthly_2008_cases.py"
)
submit = importlib.util.module_from_spec(submit_spec)
sys.path.insert(0, str(ROOT / "scripts"))
submit_spec.loader.exec_module(submit)


@pytest.fixture
def config():
    return yaml.safe_load((ROOT / "config/cesm/monthly_2008_v1.yaml").read_text())


def test_february_and_march_use_model_calendar(config):
    jan, feb, march, *_ = setup.plans(config)
    assert str(jan["start"]) == "2007-12-22 00:00:00"
    assert feb["analysis_records"] == 28 * 8
    assert feb["stop_hours"] == 38 * 24
    assert str(march["start"]) == "2008-02-19 00:00:00"
    assert str(march["stop"]) == "2008-03-08 21:00:00"
    assert march["stop_hours"] == 429
    assert march["analysis_records"] == 63
    assert march["stop"] + timedelta(hours=1) < setup.noleap("2008-03-09")


def test_entire_series_has_ten_day_spinup_and_unique_outputs(config):
    cases = setup.plans(config)
    assert len(cases) == len({p["output_directory"] for p in cases}) == 12
    for p in cases:
        assert p["analysis_start"] - p["start"] == timedelta(days=10)
        assert p["history_records"] == 80 + p["analysis_records"]
        assert p["optics_groups"] == p["history_records"] + 1
    assert str(cases[-1]["stop"]) == "2009-01-01 00:00:00"


def test_rejects_gregorian_and_stops_that_enter_missing_era5(config):
    config["calendar"] = "GREGORIAN"
    with pytest.raises(ValueError, match="NO_LEAP"):
        setup.plans(config)
    config["calendar"] = "NO_LEAP"
    config["months"][2]["stop"] = "2008-03-09T00:00:00"
    with pytest.raises(ValueError, match="missing March 9"):
        setup.plans(config)


def test_march_namelist_keeps_nudging_active_to_cime_stop(config):
    march = setup.plans(config)[2]
    text = setup.namelist(config, march)
    assert "Nudge_Beg_Day = 19" in text
    assert "Nudge_End_Day = 9" in text
    assert "aod_beg_ymd = 20080219" in text
    assert "aod_end_ymd = 20080308" in text
    assert "AOD_f09_3hr_20071222_20081231_v1/" in text
    assert "mfilt = 8" in text


def test_submission_status_parser_uses_successful_case_run_only():
    status = """case.submit starting case.run:100.server
case.submit success case.run:100.server
case.submit success case.st_archive:101.server
"""
    assert submit.submitted_job_ids(status) == ["100.server"]
