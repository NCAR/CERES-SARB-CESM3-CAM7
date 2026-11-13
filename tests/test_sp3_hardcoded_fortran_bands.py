from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORTRAN = ROOT / "src" / "cam" / "aod_optics_bands.F90"
NAMELIST = ROOT / "src" / "cam" / "namelist" / "namelist_definition.xml"

EXPECTED_SW_EDGES_UM = (
    0.1754,
    0.3225,
    0.3575,
    0.4375,
    0.4975,
    0.595,
    0.6896,
    0.794,
    0.889,
    1.042,
    1.41,
    1.9048,
    2.5,
    3.5088,
    4.0,
)
EXPECTED_LW_EDGES_UM = (
    4.54,
    5.26,
    5.88,
    7.14,
    8.0,
    9.09,
    10.2,
    12.5,
    14.9,
    18.5,
    25.0,
    35.7,
    100.0,
)


def _strip_fortran_comments(source: str) -> str:
    lines = []
    for line in source.splitlines():
        lines.append(line.split("!", 1)[0])
    return "\n".join(lines)


def _normalize(source: str) -> str:
    return re.sub(r"[\s&]+", "", source.lower())


def _extract_parameter_array(source: str, name: str) -> tuple[float, ...]:
    match = re.search(
        rf"real\s*\(\s*r8\s*\)\s*,\s*parameter\s*::\s*{name}\s*"
        r"\(\s*\d+\s*\)\s*=\s*\(/(?P<body>.*?)\/\)",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None, f"missing real(r8), parameter :: {name}(...) array"
    tokens = re.findall(
        r"(?<![A-Za-z_])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][-+]?\d+)?(?=_r8|\b)",
        match.group("body"),
    )
    return tuple(float(token.replace("d", "e").replace("D", "E")) for token in tokens)


def _aod_optics_bands_init_body(source: str) -> str:
    match = re.search(
        r"subroutine\s+aod_optics_bands_init\b(?P<body>.*?)"
        r"end\s+subroutine\s+aod_optics_bands_init",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None
    return match.group("body")


def test_no_glade_default_band_file_fallback_remains() -> None:
    source = _strip_fortran_comments(FORTRAN.read_text())

    assert "DEFAULT_BAND_FILE" not in source
    assert "/glade/work/fillmore/Data/Optics/SARB/LFL_bands.nc" not in source


def test_fortran_declares_hard_coded_lfl_edge_arrays() -> None:
    source = _strip_fortran_comments(FORTRAN.read_text())

    assert _extract_parameter_array(source, "LFL_SW_EDGES_UM") == EXPECTED_SW_EDGES_UM
    assert _extract_parameter_array(source, "LFL_LW_EDGES_UM") == EXPECTED_LW_EDGES_UM


def test_empty_band_file_uses_built_in_edges_without_netcdf_read() -> None:
    body = _aod_optics_bands_init_body(_strip_fortran_comments(FORTRAN.read_text()))
    match = re.search(
        r"if\s*\(\s*trim\s*\(\s*band_file_in\s*\)\s*==\s*''\s*\)\s*then"
        r"(?P<empty>.*?)\belse\b(?P<nonempty>.*?)end\s+if",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None, "aod_optics_bands_init must branch on empty band_file_in"

    empty_branch = _normalize(match.group("empty"))
    nonempty_branch = _normalize(match.group("nonempty"))

    assert "sw_edges=lfl_sw_edges_um" in empty_branch
    assert "lw_edges=lfl_lw_edges_um" in empty_branch
    assert "read_band_edges" not in empty_branch
    assert (
        "callread_band_edges(trim(band_file_in),sw_edges,lw_edges)"
        in nonempty_branch
    )


def test_namelist_documents_empty_builtin_and_nonempty_netcdf_override() -> None:
    text = NAMELIST.read_text()
    match = re.search(
        r'<entry id="aod_optics_band_file"(?P<body>.*?)</entry>',
        text,
        flags=re.DOTALL,
    )
    assert match is not None
    body = match.group("body")
    body_lower = body.lower()

    assert "project default lfl_bands.nc" not in body_lower
    assert "empty uses built-in hard-coded sarb/lfl edges" in body_lower
    assert "non-empty" in body_lower
    assert "netcdf" in body_lower
