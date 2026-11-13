#!/usr/bin/env python3
"""Validate CERES run-history records and render their deterministic index."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - CLI environment failure
    raise SystemExit(
        "PyYAML is required; use /glade/work/fillmore/miniforge3/envs/davinci/bin/python"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDS_DIR = PROJECT_ROOT / "run_history" / "records"
DEFAULT_INDEX = PROJECT_ROOT / "run_history" / "index.md"
DEFAULT_SCHEMA = PROJECT_ROOT / "run_history" / "schema.json"

RUN_KINDS = {"cesm", "offline", "build"}
STAGES = {
    "prepared",
    "queued",
    "running",
    "model-complete",
    "structurally-complete",
    "numeric-gates-passed",
    "davinci-inspection-passed",
    "scientifically-accepted",
    "partial",
    "failed",
    "cancelled",
}
MODEL_OUTCOMES = {
    "not-run",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "partial",
}
VALIDATION_STATUSES = {
    "pending",
    "passed",
    "failed",
    "blocked",
    "not-applicable",
    "not-recorded",
}
VALIDATION_CATEGORIES = ("structural", "numeric", "davinci", "science")
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "run_id",
    "case_name",
    "run_kind",
    "execution_date",
    "purpose",
    "simulation",
    "configuration",
    "status",
    "outputs",
    "validation",
    "provenance",
}
ALLOWED_TOP_LEVEL = REQUIRED_TOP_LEVEL | {"scheduler", "results"}
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be a mapping")
        return {}
    return value


def load_records(records_dir: Path = DEFAULT_RECORDS_DIR) -> list[tuple[Path, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    if not records_dir.is_dir():
        return records
    for path in sorted(records_dir.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        records.append((path, loaded if isinstance(loaded, dict) else {}))
    return records


def validate_record(path: Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prefix = path.name
    missing = sorted(REQUIRED_TOP_LEVEL - set(record))
    extra = sorted(set(record) - ALLOWED_TOP_LEVEL)
    if missing:
        errors.append(f"{prefix}: missing top-level fields: {missing}")
    if extra:
        errors.append(f"{prefix}: unsupported top-level fields: {extra}")

    if record.get("schema_version") != 1:
        errors.append(f"{prefix}: schema_version must be 1")

    run_id = record.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        errors.append(f"{prefix}: invalid run_id {run_id!r}")
    elif path.stem != run_id:
        errors.append(f"{prefix}: filename must match run_id {run_id!r}")

    for field in ("case_name", "purpose"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            errors.append(f"{prefix}: {field} must be a non-empty string")

    if record.get("run_kind") not in RUN_KINDS:
        errors.append(f"{prefix}: invalid run_kind {record.get('run_kind')!r}")
    execution_date = record.get("execution_date")
    if not isinstance(execution_date, str) or not DATE_RE.fullmatch(execution_date):
        errors.append(f"{prefix}: execution_date must be quoted YYYY-MM-DD")

    _mapping(record.get("simulation"), f"{prefix}: simulation", errors)
    configuration = _mapping(
        record.get("configuration"), f"{prefix}: configuration", errors
    )
    for field in ("compset", "resolution"):
        if field not in configuration:
            errors.append(f"{prefix}: configuration.{field} is required")

    status = _mapping(record.get("status"), f"{prefix}: status", errors)
    if status.get("stage") not in STAGES:
        errors.append(f"{prefix}: invalid status.stage {status.get('stage')!r}")
    if status.get("model_outcome") not in MODEL_OUTCOMES:
        errors.append(
            f"{prefix}: invalid status.model_outcome {status.get('model_outcome')!r}"
        )
    if not isinstance(status.get("summary"), str) or not status["summary"].strip():
        errors.append(f"{prefix}: status.summary must be a non-empty string")

    outputs = _mapping(record.get("outputs"), f"{prefix}: outputs", errors)
    if not isinstance(outputs.get("primary"), str) or not outputs["primary"].strip():
        errors.append(f"{prefix}: outputs.primary must be a non-empty string")

    validation = _mapping(
        record.get("validation"), f"{prefix}: validation", errors
    )
    for category in VALIDATION_CATEGORIES:
        item = _mapping(
            validation.get(category), f"{prefix}: validation.{category}", errors
        )
        if item.get("status") not in VALIDATION_STATUSES:
            errors.append(
                f"{prefix}: invalid validation.{category}.status "
                f"{item.get('status')!r}"
            )
        if not isinstance(item.get("summary"), str) or not item["summary"].strip():
            errors.append(
                f"{prefix}: validation.{category}.summary must be non-empty"
            )

    provenance = _mapping(
        record.get("provenance"), f"{prefix}: provenance", errors
    )
    if not isinstance(provenance.get("recorded_at"), str):
        errors.append(f"{prefix}: provenance.recorded_at must be a quoted string")
    sources = provenance.get("sources")
    if not isinstance(sources, list) or not sources or not all(
        isinstance(item, str) and item for item in sources
    ):
        errors.append(f"{prefix}: provenance.sources must be a non-empty string list")

    results = record.get("results", [])
    if not isinstance(results, list) or not all(isinstance(item, str) for item in results):
        errors.append(f"{prefix}: results must be a list of strings")
    return errors


def validate_records(
    records: list[tuple[Path, dict[str, Any]]],
) -> list[str]:
    errors: list[str] = []
    if not records:
        return ["no run-history records found"]
    seen_ids: dict[str, Path] = {}
    seen_jobs: dict[str, Path] = {}
    for path, record in records:
        errors.extend(validate_record(path, record))
        run_id = record.get("run_id")
        if isinstance(run_id, str):
            if run_id in seen_ids:
                errors.append(
                    f"{path.name}: duplicate run_id also used by {seen_ids[run_id].name}"
                )
            seen_ids[run_id] = path
        scheduler = record.get("scheduler")
        if isinstance(scheduler, dict):
            job_id = scheduler.get("job_id")
            if isinstance(job_id, str) and job_id:
                if job_id in seen_jobs:
                    errors.append(
                        f"{path.name}: duplicate scheduler.job_id {job_id!r} also used by "
                        f"{seen_jobs[job_id].name}"
                    )
                seen_jobs[job_id] = path
    return errors


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_index(records: list[tuple[Path, dict[str, Any]]]) -> str:
    ordered = sorted(
        records,
        key=lambda item: (
            str(item[1].get("execution_date", "")),
            str(item[1].get("run_id", "")),
        ),
        reverse=True,
    )
    lines = [
        "# Run History Index",
        "",
        "Generated from `run_history/records/*.yaml` by `scripts/run_history.py`.",
        "Do not edit the table directly.",
        "",
        "| Date | Run | Case | Compset / Resolution | Stage | Numeric | DAVINCI | Primary Output |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for path, record in ordered:
        configuration = record.get("configuration") or {}
        status = record.get("status") or {}
        validation = record.get("validation") or {}
        outputs = record.get("outputs") or {}
        run_id = _cell(record.get("run_id"))
        link = f"[`{run_id}`](records/{path.name})"
        config = f"{_cell(configuration.get('compset'))} / {_cell(configuration.get('resolution'))}"
        numeric = _cell((validation.get("numeric") or {}).get("status"))
        davinci = _cell((validation.get("davinci") or {}).get("status"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(record.get("execution_date")),
                    link,
                    f"`{_cell(record.get('case_name'))}`",
                    config,
                    _cell(status.get("stage")),
                    numeric,
                    davinci,
                    f"`{_cell(outputs.get('primary'))}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "See [`docs/run-history.md`](../docs/run-history.md) for the record contract and",
            "maintenance commands.",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_command(args: argparse.Namespace) -> int:
    records = load_records(args.records_dir)
    errors = validate_records(records)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    with args.schema.open(encoding="utf-8") as handle:
        json.load(handle)
    print(f"validated {len(records)} run-history record(s)")
    return 0


def _render_command(args: argparse.Namespace) -> int:
    records = load_records(args.records_dir)
    errors = validate_records(records)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    rendered = render_index(records)
    if args.check:
        current = args.index.read_text(encoding="utf-8") if args.index.is_file() else ""
        if current != rendered:
            print(f"run-history index is stale: {args.index}", file=sys.stderr)
            return 1
        print(f"run-history index is current ({len(records)} records)")
        return 0
    args.index.parent.mkdir(parents=True, exist_ok=True)
    args.index.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.index} ({len(records)} records)")
    return 0


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--records-dir", type=Path, default=DEFAULT_RECORDS_DIR)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    _common(validate_parser)
    validate_parser.set_defaults(handler=_validate_command)

    render_parser = subparsers.add_parser("render")
    _common(render_parser)
    render_parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    render_parser.add_argument("--check", action="store_true")
    render_parser.set_defaults(handler=_render_command)
    return parser


def main() -> int:
    args = _parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
