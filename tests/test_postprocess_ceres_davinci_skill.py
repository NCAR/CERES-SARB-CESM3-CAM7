from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "postprocess-ceres-davinci"
SUBMIT_SCRIPT = SKILL / "scripts" / "submit_analysis_pbs.py"
PBS_REFERENCE = SKILL / "references" / "pbs-execution.md"

SPEC = importlib.util.spec_from_file_location("submit_analysis_pbs", SUBMIT_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
SUBMIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SUBMIT
SPEC.loader.exec_module(SUBMIT)


def test_submission_helper_defaults_to_shared_develop_queue() -> None:
    assert SUBMIT.DEFAULT_QUEUE == "develop"
    assert SUBMIT.DEFAULT_NCPUS == 4
    assert SUBMIT.DEFAULT_MEMORY == "32GB"
    assert SUBMIT.DEFAULT_WALLTIME == "04:00:00"


def test_pbs_reference_documents_shared_default_and_explicit_main_override() -> None:
    reference = PBS_REFERENCE.read_text(encoding="utf-8")

    assert "Submission queue: `develop`" in reference
    assert "shared `cpudev` execution queue" in reference
    assert "Use `--queue main` only" in reference
