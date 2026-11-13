from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BANDS = ROOT / "src" / "cam" / "aod_optics_bands.F90"
TABLES = ROOT / "src" / "cam" / "aod_optics_lut_tables.F90"


def _strip_fortran_comments(source: str) -> str:
    return "\n".join(line.split("!", 1)[0] for line in source.splitlines())


def _normalize(source: str) -> str:
    return re.sub(r"[\s&]+", "", source.lower())


def test_lut_reader_can_import_hard_coded_lfl_edges() -> None:
    source = _normalize(_strip_fortran_comments(BANDS.read_text()))

    assert "public::lfl_sw_edges_um" in source
    assert "public::lfl_lw_edges_um" in source


def test_lut_reader_validates_mode_count_against_cam_modes() -> None:
    source = _normalize(_strip_fortran_comments(TABLES.read_text()))

    assert "userad_constituents,only:rad_cnst_get_info" in source
    assert "callrad_cnst_get_info(0,nmodes=nmodes_cam)" in source
    assert "if(nmode_lut/=nmodes_cam)" in source


def test_lut_reader_validates_mam4_mode_order_attribute() -> None:
    source = _normalize(_strip_fortran_comments(TABLES.read_text()))

    assert "expected_mode_order='a1,a2,a3,a4'" in source
    assert "callread_required_att(fileid,'mode_order',mode_order)" in source
    assert "if(trim(mode_order)/=expected_mode_order)" in source


def test_lut_reader_validates_lut_band_edges_against_built_in_edges() -> None:
    source = _normalize(_strip_fortran_comments(TABLES.read_text()))

    assert "lfl_sw_edges_um" in source
    assert "lfl_lw_edges_um" in source
    assert "callread_1d_real(fileid,'lfl_sw_edges_um',sw_edges,fname)" in source
    assert "callread_1d_real(fileid,'lfl_lw_edges_um',lw_edges,fname)" in source
    assert "maxval(abs(sw_edges-lfsw_edges_um))" not in source
    assert "maxval(abs(sw_edges-lfl_sw_edges_um))" in source
    assert "maxval(abs(lw_edges-lfl_lw_edges_um))" in source
