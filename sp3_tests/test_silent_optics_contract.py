from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text()


def test_sp3_sw_tap_suppresses_cam_history_side_effects():
    source = text("src/cam/aod_optics_tap.F90")

    assert "do_outfld=.false." in source


def test_sp2_aod_diagnostic_suppresses_cam_history_side_effects():
    source = text("src/cam/aod_nudging_optics.F90")

    assert "do_outfld=.false." in source


def test_cam_optics_patch_supports_silent_sw_diagnostics():
    patch = text("src/cam/aerosol_optics_cam.F90.diff")

    assert "logical, optional, intent(in) :: do_outfld" in patch
    assert "emit_diagnostics = do_outfld" in patch
    assert "if (emit_diagnostics) call output_tot_diags" in patch
