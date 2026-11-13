from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_sp2_vp7_profile_runs.sh"


def test_vp7_profile_script_uses_separate_dev_case_names():
    text = SCRIPT.read_text()

    assert "sp2_vp7_200807_mam4_modis" in text
    assert "sp2_vp7_200807_mam4_free" in text
    assert "sp2_200807_mam4_modis" not in text
    assert "sp2_200807_mam4_free" not in text


def test_vp7_profile_script_outputs_3d_aerosol_and_pair_fields():
    text = SCRIPT.read_text()

    assert "dst_a1:I" in text
    assert "'dst_a1'" not in text
    assert "AODVIS" in text
    assert "FSNTC" in text
    assert "AODNDG_RATIO" in text
    assert "AODNDG_MASK" in text
    assert "HISTORY_NHTFRQ=${SP2_VP7_NHTFRQ:-6}" in text
    assert "MFILT=$SP2_VP7_MFILT" in text
    assert "mfilt = ${MFILT}" in text


def test_vp7_profile_script_uses_short_develop_run_and_own_build():
    text = SCRIPT.read_text()

    assert "JOB_QUEUE=${SP2_VP7_JOB_QUEUE:-develop}" in text
    assert "JOB_WALLCLOCK_TIME=${SP2_VP7_JOB_WALLCLOCK_TIME:-01:00:00}" in text
    assert "NTASKS=${SP2_VP7_NTASKS:-32}" in text
    assert "STOP_OPTION=${SP2_VP7_STOP_OPTION:-nsteps}" in text
    assert "STOP_N=${SP2_VP7_STOP_N:-6}" in text
    assert "HISTORY_NHTFRQ=${SP2_VP7_NHTFRQ:-6}" in text
    assert "COUPLING_NCPL=${SP2_VP7_COUPLING_NCPL:-48}" in text
    assert 'ROF_NCPL="$COUPLING_NCPL"' in text
    assert "nhtfrq = ${HISTORY_NHTFRQ}" in text
    assert "create_newcase" in text
    assert "build_case_conda_free" in text
    assert "--keepexe" in text
    assert 'create_free_case "$NUDGED_CASE"' in text
