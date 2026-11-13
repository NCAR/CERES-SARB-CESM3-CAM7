#!/usr/bin/env python3
"""Submit validated monthly 2008 CIME cases and record their PBS job IDs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml

import setup_monthly_2008_cases as setup


def submitted_job_ids(status_text: str) -> list[str]:
    return re.findall(r"case\.submit success case\.run:(\S+)", status_text)


def verify_ready(config: dict, plan: dict) -> None:
    case = setup.safe_path(plan["case_directory"], writable=True)
    setup.verify_build(config, case)
    values = setup.case_values(case)
    expected = {
        "CALENDAR": "NO_LEAP",
        "RUN_STARTDATE": plan["start"].strftime("%Y-%m-%d"),
        "STOP_OPTION": "nhours",
        "STOP_N": str(plan["stop_hours"]),
        "BUILD_COMPLETE": "TRUE",
        "RESUBMIT": "0",
        "CONTINUE_RUN": "FALSE",
    }
    for key, value in expected.items():
        if values.get(key) != value:
            raise ValueError(f"{case.name}: {key}={values.get(key)!r}, expected {value!r}")
    if setup.resolved(values["RUNDIR"], values) != str(plan["output_directory"] / "run"):
        raise ValueError(f"{case.name}: unexpected RUNDIR")
    if (case / "user_nl_cam").read_text() != setup.namelist(config, plan):
        raise ValueError(f"{case.name}: user_nl_cam differs from versioned configuration")
    if submitted_job_ids((case / "CaseStatus").read_text()):
        raise ValueError(f"{case.name}: already submitted")
    exe = setup.safe_path(Path(config["exeroot"]) / "cesm.exe")
    with exe.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != config["executable_sha256"]:
        raise ValueError("Pinned executable checksum changed")


def write_summary(path: Path, entries: list[dict], *, complete: bool) -> None:
    path.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "complete": complete,
        "submissions": entries,
    }, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=setup.DEFAULT_CONFIG)
    parser.add_argument("--month", action="append", help="Select YYYY-MM; repeat as needed")
    parser.add_argument("--submit", action="store_true", required=True,
                        help="Required acknowledgement that jobs will be queued")
    args = parser.parse_args()
    config = yaml.safe_load(setup.safe_path(args.config).read_text())
    plans = setup.plans(config)
    if args.month:
        plans = [p for p in plans if p["month"] in args.month]
        if {p["month"] for p in plans} != set(args.month):
            raise ValueError("Unknown month selection")
    for plan in plans:
        verify_ready(config, plan)

    log_root = setup.safe_path(config["log_root"], writable=True)
    summary = log_root / "submission-summary.json"
    if summary.exists():
        raise ValueError(f"Refusing existing submission summary: {summary}")
    entries: list[dict] = []
    write_summary(summary, entries, complete=False)
    for plan in plans:
        case = plan["case_directory"]
        before = set(submitted_job_ids((case / "CaseStatus").read_text()))
        submitted_at = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(
            ["./case.submit"], cwd=case, capture_output=True, text=True
        )
        log = log_root / f"{plan['case_name']}.submit.log"
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            write_summary(summary, entries, complete=False)
            raise RuntimeError(f"Submission failed for {case.name}; inspect {log}")
        after = submitted_job_ids((case / "CaseStatus").read_text())
        new = [job for job in after if job not in before]
        if len(new) != 1:
            write_summary(summary, entries, complete=False)
            raise RuntimeError(f"Could not resolve one new PBS job for {case.name}: {new}")
        entry = {
            "month": plan["month"], "case_name": plan["case_name"],
            "job_id": new[0], "submitted_at": submitted_at,
            "submit_log": str(log),
        }
        entries.append(entry)
        write_summary(summary, entries, complete=False)
        print(json.dumps(entry), flush=True)
    write_summary(summary, entries, complete=True)
    print(f"Recorded {len(entries)} submissions in {summary}", flush=True)


if __name__ == "__main__":
    main()
