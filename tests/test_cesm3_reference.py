from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "update_cesm3_reference.py"
SPEC = importlib.util.spec_from_file_location("update_cesm3_reference", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
REFERENCE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REFERENCE
SPEC.loader.exec_module(REFERENCE)


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_parse_compsets_uses_expanded_atmosphere_token_and_support() -> None:
    parsed = REFERENCE.parse_compsets_xml(
        """prefix
<compsets>
  <compset>
    <alias>F2000dev</alias>
    <lname>2000_CAM70_CLM60%SP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV</lname>
    <science_support grid="f09_f09_mg17"/>
  </compset>
  <compset>
    <alias>FCnudged</alias>
    <lname>HIST_CAM60%CT1S1%NUDG_CLM50%SP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV</lname>
  </compset>
</compsets>
suffix
""",
        ("F2000dev", "FCnudged", "missing"),
    )

    assert REFERENCE.atmosphere_token(parsed[0].long_name) == "CAM70"
    assert parsed[0].support == ("science_support(grid=f09_f09_mg17)",)
    assert REFERENCE.atmosphere_token(parsed[1].long_name) == "CAM60%CT1S1%NUDG"
    assert parsed[2].long_name is None


def test_parse_grid_and_machine_query_output() -> None:
    grids = REFERENCE.parse_grids_text(
        """
alias: f09_f09_mg17 (only for compsets that are not _MOM)
    longname: a%0.9x1.25_l%0.9x1.25_oi%0.9x1.25_r%null_g%null_w%null_z%null_m%gx1v7
""",
        ("f09_f09_mg17",),
    )
    machine = REFERENCE.parse_machine_text(
        """
Machine(s)
  derecho (NCAR): NCAR AMD EPYC system
    os                  CNL
    compilers           intel,gnu,nvhpc,cray
    mpilibs             openmpi,mpich
    max_tasks_per_node  128
""",
        "derecho",
    )

    assert grids[0].long_name.startswith("a%0.9x1.25")
    assert grids[0].constraints == "only for compsets that are not _MOM"
    assert machine.description == "NCAR AMD EPYC system"
    assert ("compilers", "cray,gnu,intel,nvhpc") in machine.fields
    assert ("mpilibs", "mpich,openmpi") in machine.fields
    assert ("max_tasks_per_node", "128") in machine.fields


def test_gitmodules_mixed_indentation_does_not_create_false_checkout(
    tmp_path: Path,
) -> None:
    run_git(tmp_path, "init")
    optional = tmp_path / "libraries" / "FTorch"
    optional.mkdir(parents=True)
    (tmp_path / ".gitmodules").write_text(
        """
[submodule "FTorch"]
\tpath = libraries/FTorch
\turl = https://example.invalid/FTorch
  fxtag = v0.0.5
  fxrequired = ToplevelOptional
""",
        encoding="utf-8",
    )

    components = REFERENCE.parse_gitmodules(tmp_path)

    assert len(components) == 1
    assert components[0].expected_tag == "v0.0.5"
    assert components[0].required == "ToplevelOptional"
    assert components[0].git is None


def test_overlay_fingerprint_tracks_content_not_only_dirty_paths(tmp_path: Path) -> None:
    run_git(tmp_path, "init")
    run_git(tmp_path, "config", "user.name", "CESM Reference Test")
    run_git(tmp_path, "config", "user.email", "cesm-reference@example.invalid")
    source = tmp_path / "source.F90"
    source.write_text("baseline\n", encoding="utf-8")
    run_git(tmp_path, "add", "source.F90")
    run_git(tmp_path, "commit", "-m", "baseline")

    source.write_text("first overlay\n", encoding="utf-8")
    first = REFERENCE.dirty_overlay_fingerprint(tmp_path)
    source.write_text("second overlay\n", encoding="utf-8")
    second = REFERENCE.dirty_overlay_fingerprint(tmp_path)

    assert first != second


def test_namelist_collection_tolerates_checkout_specific_xml(tmp_path: Path) -> None:
    namelist_dir = (
        tmp_path / "components" / "cam" / "bld" / "namelist_files"
    )
    namelist_dir.mkdir(parents=True)
    (namelist_dir / "namelist_definition.xml").write_text(
        """
<namelist_definition>
  <entry id="aod_nudge_on" category="aod_nudging"
         group="aod_nudging_nl" type="logical">
    Toggle (&aod_nudging_nl).
  </entry>
  <entry id="met_nudge" category="nudging" group="met_nl" type="logical"/>
</namelist_definition>
""",
        encoding="utf-8",
    )
    (namelist_dir / "namelist_defaults_cam.xml").write_text(
        """
<namelist_defaults>
  <legacy%member>1.0</legacy%member>
  <aod_nudge_on>.false.</aod_nudge_on>
</namelist_defaults>
""",
        encoding="utf-8",
    )

    entries, met_count = REFERENCE.collect_namelists(tmp_path)

    assert len(entries) == 1
    assert entries[0].name == "aod_nudge_on"
    assert entries[0].default == ".false."
    assert met_count == 1


@pytest.mark.skipif(
    not (
        REFERENCE.DEFAULT_CESM_ROOT / "cime" / "scripts" / "query_config"
    ).is_file(),
    reason="project CESM3 checkout is not available",
)
def test_committed_reference_matches_live_project_checkout() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
