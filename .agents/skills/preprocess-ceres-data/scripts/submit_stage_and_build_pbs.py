#!/usr/bin/env python3
"""Submit raw staging + SP1 contract build for one month as chained PBS jobs.

Verified 2026-09-04: derecho compute nodes have full outbound internet (DNS,
HTTPS, ICMP all confirmed via a live qsub test), and a
running PBS job can itself call qsub to submit a follow-on job (also verified
live). So staging no longer needs a login/interactive node: this script queues
one PBS job that runs `scripts/stage_obs.py` for the config's start/end range,
and on success has that same job invoke submit_sp1_preprocessing_pbs.py, which
queues the SP1 contract build as a second, independent PBS job (its own
walltime budget, unaffected by how long staging took). If staging fails, the
build is never submitted.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))

from submit_sp1_preprocessing_pbs import (  # noqa: E402
    DEFAULT_ACCOUNT,
    DEFAULT_DATA_ROOT,
    DEFAULT_DAVINCI_ROOT,
    DEFAULT_PYTHON,
    configured_date,
    existing_contract_files,
    fail,
    find_project_root,
    inside,
    load_mapping,
    sanitize_job_name,
)

DEFAULT_QUEUE = "develop"
DEFAULT_NCPUS = 2
DEFAULT_MEMORY = "4GB"
DEFAULT_WALLTIME = "06:00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_project_root = find_project_root(script_path.parent)
    parser = argparse.ArgumentParser(
        description="Queue SP1 raw staging, chained into the contract build, via PBS."
    )
    parser.add_argument(
        "config", type=Path, help="Versioned SP1 YAML in the project repo"
    )
    parser.add_argument("--account", default=DEFAULT_ACCOUNT)
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument("--ncpus", type=int, default=DEFAULT_NCPUS)
    parser.add_argument("--memory", default=DEFAULT_MEMORY)
    parser.add_argument("--walltime", default=DEFAULT_WALLTIME)
    parser.add_argument(
        "--job-name", help="PBS job name; defaults to stage_<config stem>"
    )
    parser.add_argument(
        "--log", type=Path, help="Combined stdout/stderr path for the staging job"
    )
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--davinci-root", type=Path, default=DEFAULT_DAVINCI_ROOT)
    parser.add_argument("--project-root", type=Path, default=default_project_root)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument(
        "--build-script",
        type=Path,
        default=script_path.parent / "submit_sp1_preprocessing_pbs.py",
        help="Script the staging job calls on success to queue the contract build",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the qsub command without submitting",
    )
    return parser.parse_args(argv)


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

    out_dir_value = loaded.get("out_dir")
    if isinstance(out_dir_value, str) and out_dir_value.strip():
        output_dir = Path(out_dir_value).expanduser().resolve()
        existing = (
            existing_contract_files(output_dir, start, end)
            if output_dir.is_dir()
            else []
        )
        if existing:
            fail(
                f"out_dir already contains {len(existing)} contract file(s) for "
                f"{start.isoformat()}..{end.isoformat()}; staging+build for this month "
                "looks already done"
            )

    python = args.python.expanduser().resolve()
    davinci_root = args.davinci_root.expanduser().resolve()
    build_script = args.build_script.expanduser().resolve()
    if not python.is_file():
        fail(f"DAVINCI Python does not exist: {python}")
    if not davinci_root.is_dir():
        fail(f"DAVINCI checkout does not exist: {davinci_root}")
    if not build_script.is_file():
        fail(f"build submission script does not exist: {build_script}")

    log_path = (
        args.log.expanduser().resolve()
        if args.log is not None
        else data_root / "logs" / "staging" / f"{config.stem}.pbs.log"
    )
    if not inside(log_path, data_root):
        fail(f"PBS log must be below {data_root}: {log_path}")

    job_name = sanitize_job_name(args.job_name or f"stage_{config.stem}")
    pythonpath = f"{davinci_root}:{project_root}"

    # qsub on this PBS Pro build has no -d/working-directory option (verified
    # 2026-09-04: "qsub: invalid option -- 'd'"), so cd into project_root as
    # part of the job command instead of relying on a qsub flag.
    inner_cmd = (
        f"cd {shlex.quote(str(project_root))} && "
        f"{shlex.quote(str(python))} scripts/stage_obs.py "
        f"--start {start.isoformat()} --end {end.isoformat()} "
        f"&& {shlex.quote(str(python))} {shlex.quote(str(build_script))} "
        f"{shlex.quote(str(config))}"
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
