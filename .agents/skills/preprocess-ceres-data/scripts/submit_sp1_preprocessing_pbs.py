#!/usr/bin/env python3
"""Submit a versioned SP1 AOD preprocessing configuration through Derecho PBS."""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, NoReturn

import yaml

DEFAULT_ACCOUNT = "P19010000"
DEFAULT_QUEUE = "develop"
DEFAULT_NCPUS = 2
DEFAULT_MEMORY = "4GB"
DEFAULT_WALLTIME = "02:00:00"
DEFAULT_PYTHON = Path("/glade/work/fillmore/miniforge3/envs/davinci/bin/python")
DEFAULT_DAVINCI_ROOT = Path("/glade/work/fillmore/DAVINCI")
DEFAULT_DATA_ROOT = Path("/glade/work/fillmore/Data/CERES-SARB-CAM7")
PBS_NAME_LIMIT = 64
CONTRACT_DAY_GLOB_TEMPLATE = "MODIS_VIIRS_AOD_3hr_f09.{stamp}.*.nc"


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() and (candidate / "sp1_aod_pipeline").is_dir():
            return candidate
    fail(f"cannot locate CERES repository root above {start}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_project_root = find_project_root(script_path.parent)
    parser = argparse.ArgumentParser(
        description="Submit the CERES SP1 observation preprocessing pipeline through PBS."
    )
    parser.add_argument(
        "config", type=Path, help="Versioned SP1 YAML in the project repo"
    )
    parser.add_argument("--account", default=DEFAULT_ACCOUNT)
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument("--ncpus", type=int, default=DEFAULT_NCPUS)
    parser.add_argument("--memory", default=DEFAULT_MEMORY)
    parser.add_argument("--walltime", default=DEFAULT_WALLTIME)
    parser.add_argument("--job-name", help="PBS job name; defaults to the config stem")
    parser.add_argument("--log", type=Path, help="Combined stdout/stderr path")
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--davinci-root", type=Path, default=DEFAULT_DAVINCI_ROOT)
    parser.add_argument("--project-root", type=Path, default=default_project_root)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the qsub command without creating directories or submitting",
    )
    return parser.parse_args(argv)


def load_mapping(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        fail(f"cannot read preprocessing YAML {path}: {exc}")
    if not isinstance(loaded, dict):
        fail(f"preprocessing YAML is not a mapping: {path}")
    return loaded


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def configured_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be a nonempty absolute path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        fail(f"{label} must be absolute: {path}")
    return path.resolve()


def configured_date(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        fail(f"{label} must be an ISO date: {value!r}")


def days(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def missing_modis_days(root: Path, start: date, end: date) -> list[str]:
    missing: list[str] = []
    for day in days(start, end):
        doy = day.timetuple().tm_yday
        patterns = (
            f"M?D04_L2.A{day.year}{doy:03d}.*.hdf",
            f"M?D04_L2.A{day.year}{doy:03d}.*.nc",
        )
        if not any(any(root.rglob(pattern)) for pattern in patterns):
            missing.append(day.isoformat())
    return missing


def missing_viirs_days(root: Path, start: date, end: date) -> list[str]:
    missing: list[str] = []
    for day in days(start, end):
        doy = day.timetuple().tm_yday
        pattern = f"AERDB_L2_VIIRS_NOAA20.A{day.year}{doy:03d}.*.nc"
        if not any(root.rglob(pattern)):
            missing.append(day.isoformat())
    return missing


def existing_contract_files(root: Path, start: date, end: date) -> list[Path]:
    """Contract files already covering any day in [start, end] (shared out_dir, other
    months' files must not trip this)."""
    found: list[Path] = []
    for day in days(start, end):
        stamp = f"{day.year}{day.month:02d}{day.day:02d}"
        pattern = CONTRACT_DAY_GLOB_TEMPLATE.format(stamp=stamp)
        found.extend(sorted(root.glob(pattern)))
    return found


def sanitize_job_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    if not sanitized:
        fail("PBS job name is empty after sanitization")
    return sanitized[:PBS_NAME_LIMIT]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.expanduser().resolve()
    data_root = args.data_root.expanduser().resolve()
    config = args.config.expanduser()
    if not config.is_absolute():
        config = project_root / config
    config = config.resolve()

    if not config.is_file():
        fail(f"preprocessing YAML does not exist: {config}")
    if not inside(config, project_root):
        fail(f"preprocessing YAML must be versioned below {project_root}: {config}")
    if args.ncpus < 1:
        fail("--ncpus must be at least 1")

    loaded = load_mapping(config)
    start = configured_date(loaded.get("start"), "start")
    end = configured_date(loaded.get("end"), "end")
    if start > end:
        fail("start must not be after end")

    modis_dir = configured_path(loaded.get("modis_dir"), "modis_dir")
    if not modis_dir.is_dir():
        fail(f"MODIS directory does not exist: {modis_dir}")
    missing_modis = missing_modis_days(modis_dir, start, end)
    if missing_modis:
        sample = ", ".join(missing_modis[:5])
        suffix = " ..." if len(missing_modis) > 5 else ""
        fail(
            f"MODIS has no native granules for {len(missing_modis)} day(s): {sample}{suffix}"
        )

    raw_viirs = loaded.get("viirs_dir")
    if isinstance(raw_viirs, str) and raw_viirs.strip():
        viirs_dir = configured_path(raw_viirs, "viirs_dir")
        if not viirs_dir.is_dir():
            fail(f"VIIRS directory does not exist: {viirs_dir}")
        missing_viirs = missing_viirs_days(viirs_dir, start, end)
        if missing_viirs:
            sample = ", ".join(missing_viirs[:5])
            suffix = " ..." if len(missing_viirs) > 5 else ""
            fail(
                f"VIIRS has no native granules for {len(missing_viirs)} day(s): "
                f"{sample}{suffix}"
            )
        bias_value = loaded.get("bias_coeff_file")
        bias_path = configured_path(bias_value, "bias_coeff_file")
        if not bias_path.is_file():
            fail("VIIRS preprocessing requires an existing bias_coeff_file")

    output_dir = configured_path(loaded.get("out_dir"), "out_dir")
    if not inside(output_dir, data_root):
        fail(f"out_dir must be below {data_root}: {output_dir}")
    existing = (
        existing_contract_files(output_dir, start, end) if output_dir.is_dir() else []
    )
    if existing:
        fail(
            f"out_dir already contains {len(existing)} contract file(s) for "
            f"{start.isoformat()}..{end.isoformat()}; select a new versioned "
            "destination rather than overwriting"
        )

    python = args.python.expanduser().resolve()
    davinci_root = args.davinci_root.expanduser().resolve()
    if not python.is_file():
        fail(f"DAVINCI Python does not exist: {python}")
    if not davinci_root.is_dir():
        fail(f"DAVINCI checkout does not exist: {davinci_root}")

    log_path = (
        args.log.expanduser().resolve()
        if args.log is not None
        else data_root / "logs" / "preprocessing" / f"{config.stem}.pbs.log"
    )
    if not inside(log_path, data_root):
        fail(f"PBS log must be below {data_root}: {log_path}")

    job_name = sanitize_job_name(args.job_name or f"sp1_{config.stem}")
    pythonpath = f"{davinci_root}:{project_root}"
    # qsub on this PBS Pro build has no -d/working-directory option (verified
    # 2026-09-04: "qsub: invalid option -- 'd'"), so cd into project_root as
    # part of the job command instead of relying on a qsub flag.
    inner_cmd = (
        f"cd {shlex.quote(str(project_root))} && "
        f"{shlex.quote(str(python))} -m sp1_aod_pipeline run --config {shlex.quote(str(config))}"
    )
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
        "/bin/bash",
        "-c",
        inner_cmd,
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
