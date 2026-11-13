#!/usr/bin/env python3
"""Submit a project DAVINCI analysis to Derecho PBS."""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

import yaml


DEFAULT_ACCOUNT = "P19010000"
DEFAULT_QUEUE = "develop"
DEFAULT_NCPUS = 4
DEFAULT_MEMORY = "32GB"
DEFAULT_WALLTIME = "04:00:00"
DEFAULT_PYTHON = Path("/glade/work/fillmore/miniforge3/envs/davinci/bin/python")
DEFAULT_DAVINCI_ROOT = Path("/glade/work/fillmore/DAVINCI")
DEFAULT_RUNS_ROOT = Path("/glade/work/fillmore/Data/CERES-SARB-CAM7/runs")
PBS_NAME_LIMIT = 64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a complete CERES DAVINCI YAML pipeline through PBS."
    )
    parser.add_argument("analysis", type=Path, help="Project YAML under analyses/davinci")
    parser.add_argument("--account", default=DEFAULT_ACCOUNT)
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument("--ncpus", type=int, default=DEFAULT_NCPUS)
    parser.add_argument("--memory", default=DEFAULT_MEMORY)
    parser.add_argument("--walltime", default=DEFAULT_WALLTIME)
    parser.add_argument("--job-name", help="PBS job name; defaults to a sanitized YAML stem")
    parser.add_argument("--log", type=Path, help="Combined stdout/stderr path")
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--davinci-root", type=Path, default=DEFAULT_DAVINCI_ROOT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the qsub command without creating directories or submitting",
    )
    return parser.parse_args()


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_mapping(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        fail(f"cannot read analysis YAML {path}: {exc}")
    if not isinstance(loaded, dict):
        fail(f"analysis YAML is not a mapping: {path}")
    return loaded


def sanitize_job_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    if not sanitized:
        fail("PBS job name is empty after sanitization")
    return sanitized[:PBS_NAME_LIMIT]


def main() -> int:
    args = parse_args()
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[3]
    analyses_root = (repo_root / "analyses" / "davinci").resolve()
    analysis = args.analysis.expanduser().resolve()

    if not analysis.is_file():
        fail(f"analysis YAML does not exist: {analysis}")
    try:
        analysis.relative_to(analyses_root)
    except ValueError:
        fail(f"analysis YAML must be below {analyses_root}: {analysis}")

    config = load_mapping(analysis)
    analysis_config = config.get("analysis")
    if not isinstance(analysis_config, dict):
        fail("analysis YAML lacks an 'analysis' mapping")
    raw_output_dir = analysis_config.get("output_dir")
    if not isinstance(raw_output_dir, str) or not raw_output_dir.strip():
        fail("analysis.output_dir must be a nonempty path string")

    output_dir = Path(raw_output_dir).expanduser()
    if not output_dir.is_absolute():
        fail(f"analysis.output_dir must be absolute: {output_dir}")
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(DEFAULT_RUNS_ROOT)
    except ValueError:
        fail(f"analysis.output_dir must be below {DEFAULT_RUNS_ROOT}: {output_dir}")

    python = args.python.expanduser().resolve()
    davinci_root = args.davinci_root.expanduser().resolve()
    if not python.is_file():
        fail(f"DAVINCI Python does not exist: {python}")
    if not davinci_root.is_dir():
        fail(f"DAVINCI checkout does not exist: {davinci_root}")
    if args.ncpus < 1:
        fail("--ncpus must be at least 1")

    log_path = (
        args.log.expanduser().resolve()
        if args.log is not None
        else output_dir / "davinci-pbs.log"
    )
    try:
        log_path.relative_to(output_dir)
    except ValueError:
        fail(f"PBS log must be below the analysis output directory {output_dir}: {log_path}")
    job_name = sanitize_job_name(args.job_name or f"davinci_{analysis.stem}")
    pythonpath = f"{davinci_root}:{repo_root}"
    command = [
        "qsub",
        "-A",
        args.account,
        "-q",
        args.queue,
        "-N",
        job_name,
        "-l",
        f"select=1:ncpus={args.ncpus}:mem={args.memory}",
        "-l",
        f"walltime={args.walltime}",
        "-o",
        str(log_path),
        "-j",
        "oe",
        "-v",
        f"PYTHONPATH={pythonpath}",
        "--",
        str(python),
        "-m",
        "davinci_monet.cli.app",
        "run",
        str(analysis),
    ]

    if args.dry_run:
        print(shlex.join(command))
        return 0

    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        fail("qsub is not available on this host")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        fail(f"qsub failed: {detail}")

    job_id = completed.stdout.strip()
    if not job_id:
        fail("qsub succeeded without returning a job ID")
    print(job_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
