#!/usr/bin/env python3
"""Read-only operational and structural summary for a CERES CESM case."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


OPTICS_RE = re.compile(
    r"^AER_MAM4_(?P<band>SW\d{2}|LW\d{2})\."
    r"(?P<stamp>\d{8}\.\d{5})\.nc$"
)
STANDARD_BANDS = {
    *(f"SW{index:02d}" for index in range(1, 15)),
    *(f"LW{index:02d}" for index in range(1, 13)),
}
AOD_FIELDS = (
    "AODVIS",
    "FSNTC",
    "AODNDG_MASK",
    "AODNDG_MODEL_PRE",
    "AODNDG_MODEL_POST",
    "AODNDG_OBS",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize PBS, CIME, CAM history, and SP3 output evidence."
    )
    parser.add_argument("case_dir", type=Path, help="CIME case directory")
    parser.add_argument("--run-dir", type=Path, help="Override RUNDIR from env_run.xml")
    parser.add_argument(
        "--optics-dir",
        type=Path,
        help="SP3 per-band directory (default: sibling optics/ next to run/)",
    )
    parser.add_argument(
        "--inspect-netcdf",
        action="store_true",
        help="Open CAM history metadata and inspect record coverage",
    )
    parser.add_argument("--expected-h0a-records", type=int)
    parser.add_argument("--expected-h0i-records", type=int)
    parser.add_argument(
        "--require-h0i-variable",
        action="append",
        default=[],
        help="Require a variable in every CAM h0i file; repeat as needed",
    )
    parser.add_argument("--expected-optics-groups", type=int)
    parser.add_argument("--expected-optics-bands", type=int, default=26)
    parser.add_argument("--expected-first-stamp")
    parser.add_argument("--expected-last-stamp")
    return parser


def _case_rundir(case_dir: Path) -> Path | None:
    env_run = case_dir / "env_run.xml"
    if not env_run.is_file():
        return None
    try:
        root = ET.parse(env_run).getroot()
    except (ET.ParseError, OSError):
        return None
    for element in root.iter():
        if element.attrib.get("id") != "RUNDIR":
            continue
        value = element.attrib.get("value")
        if value:
            return Path(value).expanduser()
        if element.text and element.text.strip():
            return Path(element.text.strip()).expanduser()
    return None


def _latest_job_id(case_status: str) -> str | None:
    matches = re.findall(r"case\.(?:submit|run).*?(\d+\.[A-Za-z0-9_.-]+)", case_status)
    return matches[-1] if matches else None


def _qstat_value(output: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(.*?)\s*$", output, re.MULTILINE)
    return match.group(1) if match else None


def _scheduler_summary(job_id: str | None, warnings: list[str]) -> dict[str, Any]:
    if job_id is None:
        return {"job_id": None, "available": False}
    if shutil.which("qstat") is None:
        warnings.append("qstat is unavailable; scheduler history was not checked")
        return {"job_id": job_id, "available": False}
    try:
        completed = subprocess.run(
            ["qstat", "-xf", job_id],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        warnings.append(f"qstat failed for {job_id}: {exc}")
        return {"job_id": job_id, "available": False}
    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        warnings.append(
            f"qstat history unavailable for {job_id} (exit {completed.returncode})"
        )
        return {"job_id": job_id, "available": False}
    return {
        "job_id": job_id,
        "available": True,
        "job_state": _qstat_value(output, "job_state"),
        "exit_status": _qstat_value(output, "Exit_status"),
        "walltime": _qstat_value(output, "resources_used.walltime"),
        "memory": _qstat_value(output, "resources_used.mem"),
        "start_time": _qstat_value(output, "stime"),
        "end_time": _qstat_value(output, "obittime"),
        "queue": _qstat_value(output, "queue"),
    }


def _history_summary(
    files: list[Path],
    *,
    inspect_netcdf: bool,
    required_variables: tuple[str, ...] = (),
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    result: dict[str, Any] = {
        "file_count": len(files),
        "files": [str(path) for path in files],
        "time_records": None,
        "first_record": None,
        "last_record": None,
        "aod_fields": [],
    }
    if not inspect_netcdf or not files:
        return result, errors

    try:
        import xarray as xr
    except ImportError:
        errors.append("xarray is required for --inspect-netcdf; use the davinci environment")
        return result, errors

    total_records = 0
    first_record: str | None = None
    last_record: str | None = None
    common_variables: set[str] | None = None

    for path in files:
        try:
            with xr.open_dataset(path, decode_times=False) as dataset:
                variables = set(dataset.variables)
                common_variables = (
                    variables
                    if common_variables is None
                    else common_variables.intersection(variables)
                )
                records = int(dataset.sizes.get("time", 0))
                total_records += records
                if records and "date" in dataset and "datesec" in dataset:
                    dates = dataset["date"].values
                    seconds = dataset["datesec"].values
                    current_first = f"{int(dates[0])}:{int(seconds[0])}"
                    current_last = f"{int(dates[-1])}:{int(seconds[-1])}"
                    first_record = first_record or current_first
                    last_record = current_last
        except Exception as exc:  # xarray/netCDF backends expose several exception types
            errors.append(f"cannot inspect {path}: {exc}")

    common_variables = common_variables or set()
    result["time_records"] = total_records
    result["first_record"] = first_record
    result["last_record"] = last_record
    result["aod_fields"] = [name for name in AOD_FIELDS if name in common_variables]
    missing = [name for name in required_variables if name not in common_variables]
    if missing:
        errors.append(f"CAM h0i files are missing required variables: {missing}")
    return result, errors


def _optics_summary(optics_dir: Path | None) -> dict[str, Any]:
    if optics_dir is None or not optics_dir.is_dir():
        return {
            "directory": str(optics_dir) if optics_dir is not None else None,
            "exists": False,
            "file_count": 0,
            "group_count": 0,
            "complete_group_count": 0,
            "partial_group_count": 0,
            "first_stamp": None,
            "last_stamp": None,
            "partial_groups": {},
        }

    groups: dict[str, set[str]] = defaultdict(set)
    file_count = 0
    for path in optics_dir.iterdir():
        if not path.is_file():
            continue
        match = OPTICS_RE.match(path.name)
        if match is None:
            continue
        file_count += 1
        groups[match.group("stamp")].add(match.group("band"))

    partial = {
        stamp: sorted(STANDARD_BANDS - bands)
        for stamp, bands in groups.items()
        if bands != STANDARD_BANDS
    }
    stamps = sorted(groups)
    return {
        "directory": str(optics_dir),
        "exists": True,
        "file_count": file_count,
        "group_count": len(groups),
        "complete_group_count": len(groups) - len(partial),
        "partial_group_count": len(partial),
        "first_stamp": stamps[0] if stamps else None,
        "last_stamp": stamps[-1] if stamps else None,
        "partial_groups": dict(list(sorted(partial.items()))[:10]),
    }


def summarize(args: argparse.Namespace) -> dict[str, Any]:
    case_dir = args.case_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    case_status_path = case_dir / "CaseStatus"
    if case_status_path.is_file():
        case_status = case_status_path.read_text(encoding="utf-8", errors="replace")
    else:
        case_status = ""
        errors.append(f"missing CaseStatus: {case_status_path}")

    job_id = _latest_job_id(case_status)
    scheduler = _scheduler_summary(job_id, warnings)
    model_success = "model execution success" in case_status
    case_success = "case.run success" in case_status
    case_started = "case.run starting" in case_status

    run_dir = args.run_dir or _case_rundir(case_dir)
    if run_dir is not None:
        run_dir = run_dir.expanduser().resolve()
    if run_dir is None:
        errors.append("could not resolve RUNDIR; pass --run-dir")
        h0a_files: list[Path] = []
        h0i_files: list[Path] = []
    elif not run_dir.is_dir():
        errors.append(f"run directory does not exist: {run_dir}")
        h0a_files = []
        h0i_files = []
    else:
        h0a_files = sorted(run_dir.glob("*.cam.h0a.*.nc"))
        h0i_files = sorted(run_dir.glob("*.cam.h0i.*.nc"))

    inspect_history = bool(
        args.inspect_netcdf
        or args.expected_h0a_records is not None
        or args.expected_h0i_records is not None
        or args.require_h0i_variable
    )
    h0a, h0a_errors = _history_summary(
        h0a_files, inspect_netcdf=inspect_history
    )
    h0i, h0i_errors = _history_summary(
        h0i_files,
        inspect_netcdf=inspect_history,
        required_variables=tuple(args.require_h0i_variable),
    )
    errors.extend(h0a_errors)
    errors.extend(h0i_errors)

    optics_dir = args.optics_dir
    if optics_dir is None and run_dir is not None:
        candidate = run_dir.parent / "optics"
        if candidate.is_dir() or args.expected_optics_groups is not None:
            optics_dir = candidate
    if optics_dir is not None:
        optics_dir = optics_dir.expanduser().resolve()
    optics = _optics_summary(optics_dir)

    expectation_checks: dict[str, dict[str, Any]] = {}

    def check(name: str, observed: Any, expected: Any) -> None:
        passed = observed == expected
        expectation_checks[name] = {
            "observed": observed,
            "expected": expected,
            "passed": passed,
        }
        if not passed:
            errors.append(f"{name}: expected {expected!r}, observed {observed!r}")

    if args.expected_h0a_records is not None:
        check("h0a_time_records", h0a["time_records"], args.expected_h0a_records)
    if args.expected_h0i_records is not None:
        check("h0i_time_records", h0i["time_records"], args.expected_h0i_records)
    if args.expected_optics_groups is not None:
        check("optics_group_count", optics["group_count"], args.expected_optics_groups)
        check("optics_partial_group_count", optics["partial_group_count"], 0)
        check(
            "optics_file_count",
            optics["file_count"],
            args.expected_optics_groups * args.expected_optics_bands,
        )
    if args.expected_first_stamp is not None:
        check("optics_first_stamp", optics["first_stamp"], args.expected_first_stamp)
    if args.expected_last_stamp is not None:
        check("optics_last_stamp", optics["last_stamp"], args.expected_last_stamp)

    scheduler_state = scheduler.get("job_state")
    if scheduler.get("exit_status") not in (None, "0"):
        errors.append(f"PBS Exit_status is {scheduler.get('exit_status')}")

    if scheduler_state in {"Q", "H", "W"}:
        stage = "queued"
    elif scheduler_state in {"R", "E", "B"} or (case_started and not case_success):
        stage = "running"
    elif case_success and model_success:
        stage = "model-complete"
    elif job_id is not None:
        stage = "queued"
    else:
        stage = "prepared"

    expectations_requested = bool(
        args.expected_h0a_records is not None
        or args.expected_h0i_records is not None
        or args.require_h0i_variable
        or args.expected_optics_groups is not None
        or args.expected_first_stamp is not None
        or args.expected_last_stamp is not None
    )
    expectations_passed = all(
        item["passed"] for item in expectation_checks.values()
    ) and not h0a_errors and not h0i_errors
    if case_success and model_success and expectations_requested and expectations_passed:
        stage = "structurally-complete"

    tail = [line for line in case_status.splitlines() if line.strip()][-20:]
    return {
        "case_dir": str(case_dir),
        "case_name": case_dir.name,
        "run_dir": str(run_dir) if run_dir is not None else None,
        "highest_evidence_stage": stage,
        "case_status": {
            "model_execution_success": model_success,
            "case_run_success": case_success,
            "tail": tail,
        },
        "scheduler": scheduler,
        "history": {"h0a": h0a, "h0i": h0i},
        "optics": optics,
        "expectation_checks": expectation_checks,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    args = _parser().parse_args()
    result = summarize(args)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
