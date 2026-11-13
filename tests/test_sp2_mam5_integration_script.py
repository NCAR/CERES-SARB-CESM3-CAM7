from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sp2_tests" / "run_integration_mam5.sh"


def test_mam5_script_selects_vbs_use_case_and_guards_against_soae():
    text = SCRIPT.read_text()

    assert "TARGET_USE_CASE=2000_trop_strat_vbs_cam6" in text
    assert 'CAM_NML_USE_CASE="$TARGET_USE_CASE"' in text
    assert "./preview_namelists --component atm" in text
    assert "SOAE" in text
    assert "CaseDocs/atm_in" in text


def test_mam5_script_keeps_mam5_chem_override_assertion():
    text = SCRIPT.read_text()

    assert 'TARGET_CHEM="-chem trop_strat_mam5_t1s1"' in text
    assert "MAM5 chem override not in effect" in text


def test_mam5_script_is_short_smoke_check_without_restart_requirement():
    text = SCRIPT.read_text()

    assert "STOP_OPTION=nhours,STOP_N=3" in text
    assert "REST_OPTION=never" in text
    assert "mfilt = 1" in text
