from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_sp2_july2008_runs.sh"


def test_july2008_script_uses_approved_case_names_and_window():
    text = SCRIPT.read_text()

    assert "sp2_200807_mam4_free" in text
    assert "sp2_200807_mam4_modis" in text
    assert "RUN_STARTDATE=2008-07-01" in text
    assert "STOP_OPTION=ndays,STOP_N=31" in text
    assert "REST_OPTION=ndays,REST_N=31" in text


def test_july2008_script_submits_real_qsub_main_queue_jobs():
    text = SCRIPT.read_text()

    assert "JOB_QUEUE=main" in text
    assert "JOB_WALLCLOCK_TIME=12:00:00" in text
    assert "case.submit" in text
    assert "--no-batch" not in text


def test_july2008_script_uses_one_derecho_node_layout():
    text = SCRIPT.read_text()

    assert "NTASKS=128" in text
    assert "NTASKS_ATM=\"$NTASKS\"" in text
    assert "MAX_MPITASKS_PER_NODE=\"$NTASKS\"" in text
    assert "MAX_TASKS_PER_NODE=\"$NTASKS\"" in text


def test_july2008_script_distinguishes_free_and_modis_nudged_namelists():
    text = SCRIPT.read_text()

    assert "aod_nudge_on = .false." in text
    assert "aod_nudge_on = .true." in text
    assert "/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/" in text
    assert "MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc" in text
    assert "AODNDG_MODEL_POST" in text
    assert "AODVIS','FSNTC" in text


def test_july2008_script_keeps_high_frequency_output_for_daily_postprocessing():
    text = SCRIPT.read_text()

    assert "nhtfrq = -3" in text
    assert "mfilt = 248" in text
    assert "AODNDG_MASK" in text


def test_july2008_script_writes_user_nl_after_case_setup_creates_files():
    text = SCRIPT.read_text()

    assert 'configure_case_xml "$NUDGED_CASE"\nwrite_nudged_user_nl' in text
    assert 'configure_case_xml "$FREE_CASE"\nwrite_free_user_nl' in text


def test_july2008_script_marks_keepexe_free_clone_build_complete():
    text = SCRIPT.read_text()

    assert "create_clone" in text
    assert "--keepexe" in text
    assert "mark_free_clone_build_complete" in text
    assert "BUILD_COMPLETE=TRUE" in text
    assert "cesm.exe" in text
