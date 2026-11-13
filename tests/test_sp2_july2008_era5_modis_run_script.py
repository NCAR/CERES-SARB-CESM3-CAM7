from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_sp2_july2008_era5_modis_run.sh"


def test_era5_modis_script_uses_dedicated_case_and_preserves_base_executable():
    text = SCRIPT.read_text()

    assert "sp2_200807_mam4_modis_era5" in text
    assert "sp2_200807_mam4_modis" in text
    assert "create_clone" in text
    assert "--keepexe" in text
    assert "BUILD_COMPLETE=TRUE" in text


def test_era5_modis_script_configures_full_july_run():
    text = SCRIPT.read_text()

    assert "RUN_STARTDATE=2008-07-01" in text
    assert "STOP_OPTION=ndays,STOP_N=31" in text
    assert "REST_OPTION=ndays,REST_N=31" in text
    assert "JOB_QUEUE=main" in text


def test_era5_modis_script_enables_era5_met_nudging():
    text = SCRIPT.read_text()

    assert "Nudge_Model = .true." in text
    assert "/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl/" in text
    assert "ERA5_fv09.cam2.i.%y-%m-%d-%s.nc" in text
    assert "Nudge_Times_Per_Day = 24" in text
    assert "Model_Times_Per_Day = 48" in text
    assert "Nudge_Ucoef = 0.25" in text
    assert "Nudge_Vcoef = 0.25" in text
    assert "Nudge_Tcoef = 0.25" in text
    assert "Nudge_Qcoef = 0.25" in text
    assert "Nudge_PSprof = 0" in text


def test_era5_modis_script_enables_modis_aod_nudging():
    text = SCRIPT.read_text()

    assert "aod_nudge_on = .true." in text
    assert "/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/" in text
    assert "MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc" in text
    assert "aod_times_per_day = 8" in text
    assert "AODNDG_MODEL_POST" in text


def test_era5_modis_script_validates_forcing_coverage_and_generated_namelist():
    text = SCRIPT.read_text()

    assert "era5_count" in text
    assert "-ne 744" in text
    assert "2008-08-01-00000.nc" in text
    assert "validate_era5_grid" in text
    assert '"lev": 32' in text
    assert '("lat", "lon", "hyam", "hybm", "hyai", "hybi")' in text
    assert "preview_namelists --component atm" in text
    assert "verify_atm_in" in text


def test_era5_modis_script_does_not_submit_by_default():
    text = SCRIPT.read_text()

    assert 'if "$SUBMIT"; then' in text
    assert "Not submitted." in text
