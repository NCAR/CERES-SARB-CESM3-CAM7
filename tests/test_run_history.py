import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "run_history.py"
SPEC = importlib.util.spec_from_file_location("run_history_script", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
run_history = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_history)


def test_committed_run_history_is_valid_and_index_is_current():
    records = run_history.load_records(ROOT / "run_history" / "records")

    assert run_history.validate_records(records) == []
    assert (ROOT / "run_history" / "index.md").read_text() == run_history.render_index(
        records
    )
    schema = json.loads((ROOT / "run_history" / "schema.json").read_text())
    assert schema["properties"]["schema_version"]["const"] == 1


def test_run_history_index_sorts_newest_first(tmp_path):
    older = {
        "execution_date": "2026-01-01",
        "run_id": "older--20260101",
        "case_name": "older",
        "configuration": {"compset": "F2000dev", "resolution": "f09"},
        "status": {"stage": "prepared"},
        "outputs": {"primary": "/tmp/older"},
        "validation": {"numeric": {"status": "pending"}, "davinci": {"status": "pending"}},
    }
    newer = {
        "execution_date": "2026-02-01",
        "run_id": "newer--20260201",
        "case_name": "newer",
        "configuration": {"compset": "F2000dev", "resolution": "f09"},
        "status": {"stage": "model-complete"},
        "outputs": {"primary": "/tmp/newer"},
        "validation": {"numeric": {"status": "passed"}, "davinci": {"status": "pending"}},
    }

    rendered = run_history.render_index(
        [(tmp_path / "older.yaml", older), (tmp_path / "newer.yaml", newer)]
    )

    assert rendered.index("newer--20260201") < rendered.index("older--20260101")


def test_duplicate_scheduler_job_id_is_rejected(tmp_path):
    base = {
        "schema_version": 1,
        "case_name": "case",
        "run_kind": "cesm",
        "execution_date": "2026-01-01",
        "purpose": "test",
        "simulation": {},
        "configuration": {"compset": "F2000dev", "resolution": "f09"},
        "scheduler": {"job_id": "123.server"},
        "status": {
            "stage": "model-complete",
            "model_outcome": "succeeded",
            "summary": "done",
        },
        "outputs": {"primary": "/tmp/output"},
        "validation": {
            category: {"status": "pending", "summary": "pending"}
            for category in run_history.VALIDATION_CATEGORIES
        },
        "provenance": {"recorded_at": "2026-01-01", "sources": ["test"]},
    }
    first = {**base, "run_id": "first--20260101"}
    second = {**base, "run_id": "second--20260101"}

    errors = run_history.validate_records(
        [(tmp_path / "first--20260101.yaml", first), (tmp_path / "second--20260101.yaml", second)]
    )

    assert any("duplicate scheduler.job_id" in error for error in errors)
