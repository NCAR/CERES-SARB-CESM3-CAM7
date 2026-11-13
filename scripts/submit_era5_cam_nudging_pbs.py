#!/usr/bin/env python3
"""Preflight and submit an ERA5-to-CAM conversion through Derecho PBS."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import re
import shlex
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CONVERTER = REPO_ROOT / "scripts" / "generate_era5_cam_nudging.py"
DEFAULT_PYTHON = Path("/glade/work/fillmore/miniforge3/envs/davinci/bin/python")
DEFAULT_LOG_ROOT = Path(
    "/glade/work/fillmore/Data/CERES-SARB-CAM7/logs/preprocessing"
)


def _load_converter():
    spec = importlib.util.spec_from_file_location("generate_era5_cam_nudging", CONVERTER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load converter: {CONVERTER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--account", default="P19010000")
    parser.add_argument("--queue", default="develop")
    parser.add_argument("--ncpus", type=int, default=1)
    parser.add_argument("--memory", default="8GB")
    parser.add_argument("--walltime", default="06:00:00")
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--job-name")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _job_name(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:64]
    if not result:
        raise ValueError("PBS job name is empty after sanitization")
    return result


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.ncpus < 1:
        raise ValueError("--ncpus must be positive")
    config_path = args.config
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path
    config_path = config_path.resolve(strict=True)
    if not config_path.is_relative_to(REPO_ROOT):
        raise ValueError(f"Config must be versioned below {REPO_ROOT}: {config_path}")
    python = args.python.resolve(strict=True)

    converter = _load_converter()
    config = converter.load_config(config_path)
    report = converter.preflight(config, for_run=True, resume=args.resume)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = (
        args.log.resolve()
        if args.log is not None
        else DEFAULT_LOG_ROOT / f"{config_path.stem}.{stamp}.pbs.log"
    )
    log_absolute = Path(str(log_path.absolute()))
    if not log_absolute.is_relative_to(converter.PROJECT_DATA_ROOT):
        raise ValueError(
            f"PBS log must be below {converter.PROJECT_DATA_ROOT}: {log_absolute}"
        )
    existing_parent = log_absolute.parent
    while not existing_parent.exists():
        existing_parent = existing_parent.parent
    if not existing_parent.resolve().is_relative_to(converter.PROJECT_DATA_ROOT):
        raise ValueError(f"PBS log parent resolves outside the Data tree: {log_absolute}")

    run_arguments = [
        str(python),
        str(CONVERTER),
        "--config",
        str(config_path),
        "run",
    ]
    if args.resume:
        run_arguments.append("--resume")
    inner = f"cd {shlex.quote(str(REPO_ROOT))} && {shlex.join(run_arguments)}"
    command = [
        "qsub",
        "-A",
        args.account,
        "-q",
        args.queue,
        "-N",
        _job_name(args.job_name or f"era5_{config_path.stem}"),
        "-l",
        f"select=1:ncpus={args.ncpus}:mem={args.memory}",
        "-l",
        f"walltime={args.walltime}",
        "-o",
        str(log_absolute),
        "-j",
        "oe",
        "-v",
        f"PYTHONPATH=/glade/work/fillmore/DAVINCI:{REPO_ROOT}",
        "--",
        "/bin/bash",
        "-c",
        inner,
    ]
    print(
        f"preflight: {report['pending_outputs']} pending hour(s), "
        f"{report['unique_dynamic_source_files']} source bundle(s)",
        file=sys.stderr,
    )
    if args.dry_run:
        print(shlex.join(command))
        return 0

    log_absolute.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    job_id = completed.stdout.strip()
    if not job_id:
        raise RuntimeError("qsub succeeded without returning a job ID")
    print(job_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
