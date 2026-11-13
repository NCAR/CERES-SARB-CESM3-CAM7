from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sp2_tests" / "run_transport_proof.sh"


def test_transport_run_script_uses_separate_dev_case_names():
    assert SCRIPT.exists(), "Task 11 transport run script is missing"
    text = SCRIPT.read_text()

    assert "sp2_transport_pulse" in text
    assert "sp2_transport_free" in text
    assert "sp2_200807_mam4_modis" not in text
    assert "sp2_200807_mam4_free" not in text


def test_transport_run_script_configures_two_day_hourly_history():
    assert SCRIPT.exists(), "Task 11 transport run script is missing"
    text = SCRIPT.read_text()

    assert "RUN_STARTDATE=0001-01-01" in text
    assert "STOP_OPTION=${SP2_TRANSPORT_STOP_OPTION:-ndays}" in text
    assert "STOP_N=${SP2_TRANSPORT_STOP_N:-2}" in text
    assert "HISTORY_NHTFRQ=${SP2_TRANSPORT_NHTFRQ:--1}" in text
    assert "MFILT=${SP2_TRANSPORT_MFILT:-48}" in text
    assert "nhtfrq = ${HISTORY_NHTFRQ}" in text
    assert "mfilt = ${MFILT}" in text


def test_transport_run_script_keeps_nudging_on_for_both_cases_with_different_obs():
    assert SCRIPT.exists(), "Task 11 transport run script is missing"
    text = SCRIPT.read_text()

    assert "aod_nudge_on = .true." in text
    assert "aod_obs_path = '${obs_dir}/'" in text
    assert 'write_transport_user_nl "$NUDGED_CASE" "$PULSE_OBS_DIR"' in text
    assert 'write_transport_user_nl "$FREE_CASE" "$FILL_OBS_DIR"' in text
    assert "AODNDG_MODEL_PRE" in text
    assert "AODNDG_MODEL_POST" in text
    assert "AODNDG_MASK" in text
    assert "AODVIS" in text


def test_transport_run_script_uses_own_build_root_and_can_run_no_batch():
    assert SCRIPT.exists(), "Task 11 transport run script is missing"
    text = SCRIPT.read_text()

    assert "create_newcase" in text
    assert "create_clone" in text
    assert "--keepexe" in text
    assert "build_case_conda_free" in text
    assert "./case.submit --no-batch" in text
    assert "guard_case_names" in text
