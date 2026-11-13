from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "preprocess-ceres-data"
    / "scripts"
    / "submit_sp1_preprocessing_pbs.py"
)
CHAINED_SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "preprocess-ceres-data"
    / "scripts"
    / "submit_stage_and_build_pbs.py"
)
SPEC = importlib.util.spec_from_file_location("submit_sp1_preprocessing_pbs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
SUBMIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SUBMIT
SPEC.loader.exec_module(SUBMIT)

STAGE_SCRIPT = ROOT / "scripts" / "stage_obs.py"
STAGE_SPEC = importlib.util.spec_from_file_location("stage_obs", STAGE_SCRIPT)
assert STAGE_SPEC is not None and STAGE_SPEC.loader is not None
STAGE = importlib.util.module_from_spec(STAGE_SPEC)
sys.modules[STAGE_SPEC.name] = STAGE
STAGE_SPEC.loader.exec_module(STAGE)


def make_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    project = tmp_path / "project"
    data = tmp_path / "data"
    modis = data / "raw" / "modis"
    davinci = tmp_path / "davinci"
    for path in (project / "sp1_aod_pipeline", modis, davinci):
        path.mkdir(parents=True)
    (modis / "MOD04_L2.A2008183.0000.061.test.hdf").write_text(
        "fixture",
        encoding="utf-8",
    )
    config = project / "sp1_aod_pipeline" / "config.test.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "modis_dir": str(modis),
                "viirs_dir": "",
                "out_dir": str(data / "aod-v1"),
                "start": "2008-07-01",
                "end": "2008-07-01",
            }
        ),
        encoding="utf-8",
    )
    return project, data, davinci, config


def base_args(
    project: Path,
    data: Path,
    davinci: Path,
    config: Path,
) -> list[str]:
    return [
        str(config),
        "--project-root",
        str(project),
        "--data-root",
        str(data),
        "--davinci-root",
        str(davinci),
        "--python",
        sys.executable,
        "--dry-run",
    ]


def test_dry_run_builds_safe_sp1_qsub_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project, data, davinci, config = make_inputs(tmp_path)

    assert SUBMIT.main(base_args(project, data, davinci, config)) == 0

    command = capsys.readouterr().out
    assert command.startswith("qsub ")
    assert "-q develop" in command
    assert "-l select=1:ncpus=2:mem=4GB" in command
    assert "-l walltime=02:00:00" in command
    assert "-m sp1_aod_pipeline run --config" in command
    assert f"PYTHONPATH={davinci}:{project}" in command
    assert not (data / "logs").exists()


def test_submission_helpers_default_to_shared_develop_queue() -> None:
    assert SUBMIT.DEFAULT_QUEUE == "develop"
    assert SUBMIT.DEFAULT_NCPUS == 2
    assert SUBMIT.DEFAULT_MEMORY == "4GB"
    assert SUBMIT.DEFAULT_WALLTIME == "02:00:00"

    chained = CHAINED_SCRIPT.read_text(encoding="utf-8")
    assert 'DEFAULT_QUEUE = "develop"' in chained
    assert "DEFAULT_NCPUS = 2" in chained
    assert 'DEFAULT_MEMORY = "4GB"' in chained
    assert 'DEFAULT_WALLTIME = "06:00:00"' in chained


def test_submit_refuses_populated_contract_destination(tmp_path: Path) -> None:
    project, data, davinci, config = make_inputs(tmp_path)
    output = data / "aod-v1"
    output.mkdir()
    (output / "MODIS_VIIRS_AOD_3hr_f09.20080701.00000.nc").touch()

    with pytest.raises(SystemExit, match="2"):
        SUBMIT.main(base_args(project, data, davinci, config))


def test_aeronet_dry_run_does_not_create_output_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from davinci_monet.datasets.surface import aeronet

    class Reader:
        pass

    monkeypatch.setattr(aeronet, "AERONETReader", Reader)

    STAGE.stage_aeronet(
        date(2008, 7, 1),
        date(2008, 7, 1),
        str(tmp_path),
        dry=True,
    )

    assert not (tmp_path / "AeroNet").exists()


def test_skill_uses_standard_repo_discovery_path() -> None:
    canonical = ROOT / ".agents" / "skills" / "preprocess-ceres-data"
    legacy = ROOT / "skills" / "preprocess-ceres-data"

    assert (canonical / "SKILL.md").is_file()
    assert legacy.is_symlink()
    assert legacy.resolve() == canonical.resolve()
