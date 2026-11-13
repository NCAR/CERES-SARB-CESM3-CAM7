#!/usr/bin/env python3
"""Prepare (never build or submit) the versioned monthly 2008 CAM7 cases."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

import cftime
import netCDF4
import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "config/cesm/monthly_2008_v1.yaml"
AOD_TEMPLATE = "MODIS_VIIRS_AOD_3hr_f09.{date}.{seconds:05d}.nc"
ERA5_TEMPLATE = "ERA5_fv09.cam2.i.{date}-{seconds:05d}.nc"
ALLOWED = tuple(Path(p) for p in (
    "/glade/work/fillmore", "/glade/u/home/fillmore",
    "/glade/derecho/scratch/fillmore",
    "/glade/campaign/cesm/cesmdata",
    "/glade/campaign/collections/gdex/data",
    "/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl",
))


def safe_path(value: str | Path, *, writable: bool = False) -> Path:
    path = Path(os.path.abspath(value))
    roots = ALLOWED[:3] if writable else ALLOWED
    if not any(path.is_relative_to(root) for root in roots):
        raise ValueError(f"Path is outside authorized roots: {path}")
    # Inspect each link before traversing its target, including parent links.
    pending = path.parts[1:]
    current = Path(path.anchor)
    followed = 0
    while pending:
        current = current / pending[0]
        pending = pending[1:]
        if current.is_symlink():
            target = current.readlink()
            target = Path(
                os.path.abspath(
                    target if target.is_absolute() else current.parent / target
                )
            )
            if not any(target.is_relative_to(root) for root in roots):
                raise ValueError(f"Link leaves authorized roots: {current} -> {target}")
            followed += 1
            if followed > 40:
                raise ValueError(f"Symlink loop: {path}")
            pending = target.parts[1:] + pending
            current = Path(target.anchor)
    return path


def noleap(value: str) -> cftime.DatetimeNoLeap:
    dt = datetime.fromisoformat(value)
    return cftime.DatetimeNoLeap(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def plans(config: dict) -> list[dict]:
    if config["calendar"] != "NO_LEAP":
        raise ValueError("This F2000dev setup requires the approved NO_LEAP calendar")
    result = []
    for item in config["months"]:
        month = item["month"]
        analysis = noleap(f"{month}-01")
        next_month = cftime.DatetimeNoLeap(
            analysis.year + (analysis.month == 12), analysis.month % 12 + 1, 1
        )
        stop = noleap(item["stop"]) if "stop" in item else next_month
        start = analysis - timedelta(days=config["spinup_days"])
        hours = int((stop - start).total_seconds() // 3600)
        if not analysis < stop <= next_month or stop.minute or stop.second or stop.hour % 3:
            raise ValueError(f"Invalid three-hour analysis stop for {month}: {stop}")
        if month == "2008-03" and stop > noleap("2008-03-08T21:00:00"):
            raise ValueError("March stop would require missing March 9 ERA5 forcing")
        name = config["case_name_template"].format(month=month.replace("-", ""))
        result.append(dict(
            month=month, case_name=name, start=start, analysis_start=analysis, stop=stop,
            stop_hours=hours, history_records=hours // 3, optics_groups=hours // 3 + 1,
            analysis_records=int((stop - analysis).total_seconds() // 10800),
            case_directory=Path(config["case_root"]) / name,
            output_directory=Path(config["output_root"]) / name,
        ))
    if len({p["case_name"] for p in result}) != len(result):
        raise ValueError("Duplicate case names")
    return result


def entries(path: Path) -> dict[str, str]:
    safe_path(path)
    return {node.attrib["id"]: node.attrib["value"]
            for node in ET.parse(path).iter("entry") if "value" in node.attrib}


def case_values(case: Path) -> dict[str, str]:
    values = {}
    for path in case.glob("env_*.xml"):
        values.update(entries(path))
    return values


def resolved(value: str, values: dict[str, str]) -> str:
    for _ in range(20):
        new = re.sub(r"\$\{?(\w+)\}?", lambda m: values.get(m[1], m[0]), value)
        if new == value:
            return value
        value = new
    raise ValueError("Cyclic CIME variable expansion")


def stamped(template: str, t: cftime.DatetimeNoLeap, *, era5: bool = False) -> str:
    return template.format(date=t.strftime("%Y-%m-%d" if era5 else "%Y%m%d"),
                           seconds=t.hour * 3600)


def preflight(
    config: dict, cases: list[dict], *, existing_cases: bool = False
) -> tuple[dict, dict[str, Path]]:
    revision = subprocess.check_output(
        ["git", "-C", str(safe_path(config["cesm_root"])), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != config["cesm_commit"]:
        raise ValueError(f"CESM revision changed: {revision}")
    base = safe_path(config["base_case"])
    values = case_values(base)
    required = dict(CALENDAR=config["calendar"], COMPSET=config["compset"],
                    MACH=config["machine"], COMPILER=config["compiler"], MPILIB=config["mpilib"],
                    CAM_CONFIG_OPTS="-phys cam7", BUILD_COMPLETE="TRUE", BUILD_STATUS="0")
    for key, expected in required.items():
        if values.get(key) != expected:
            raise ValueError(f"Base {key}: {values.get(key)!r} != {expected!r}")
    if resolved(values["EXEROOT"], values) != config["exeroot"]:
        raise ValueError("Base executable directory has changed")
    exe = safe_path(Path(config["exeroot"]) / "cesm.exe")
    if not exe.is_file() or not os.access(exe, os.X_OK):
        raise ValueError(f"Missing executable: {exe}")
    for path in (base / "SourceMods").rglob("*.F90"):
        safe_path(path)
        if path.stat().st_mtime > exe.stat().st_mtime:
            raise ValueError(f"SourceMod is newer than the executable: {path}")
    for p in cases:
        case_target = safe_path(p["case_directory"], writable=True)
        output_target = safe_path(p["output_directory"], writable=True)
        if existing_cases:
            if not case_target.is_dir():
                raise ValueError(f"Case does not exist: {case_target}")
            if re.search(r"case\.submit success case\.run:",
                         (case_target / "CaseStatus").read_text()):
                raise ValueError(f"Case was already submitted: {case_target}")
        elif case_target.exists() or case_target.is_symlink():
            raise ValueError(f"Refusing existing target: {case_target}")
        if output_target.exists() or output_target.is_symlink():
            raise ValueError(f"Refusing existing target: {output_target}")
    sources = {}
    for raw in config["aod_sources"]:
        directory = safe_path(raw)
        for path in directory.glob("MODIS_VIIRS_AOD_3hr_f09.*.nc"):
            safe_path(path)
            if path.name in sources:
                raise ValueError(f"Duplicate AOD source filename: {path.name}")
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Missing/empty AOD source: {path}")
            sources[path.name] = path
    linkdir = safe_path(config["aod_directory"], writable=True)
    if linkdir.exists():
        for link in linkdir.iterdir():
            safe_path(link)
            if (
                link.name not in sources
                or not link.is_symlink()
                or link.resolve() != sources[link.name].resolve()
            ):
                raise ValueError(f"Existing input view has unrelated content: {link}")
    era5 = safe_path(config["era5_directory"])
    checked = set()
    for p in cases:
        last_hour = p["stop"] + timedelta(hours=bool(p["stop"].hour))
        t = p["start"]
        while t <= last_hour:
            name = stamped(ERA5_TEMPLATE, t, era5=True)
            if name not in checked:
                path = safe_path(era5 / name)
                if not path.is_file() or path.stat().st_size == 0 or not os.access(path, os.R_OK):
                    raise ValueError(f"Missing/empty/unreadable ERA5 file: {path}")
                checked.add(name)
            t += timedelta(hours=1)
        t = p["start"]
        while t < p["stop"]:
            name = stamped(AOD_TEMPLATE, t)
            if name not in sources:
                raise ValueError(f"Missing AOD forcing window: {name}")
            t += timedelta(hours=3)
    grid_names = ("lat", "lon", "hyam", "hybm", "hyai", "hybi")
    with netCDF4.Dataset(safe_path(config["cam_initial_file"])) as ds:
        grid = {key: np.asarray(ds[key][:]) for key in grid_names}
    for p in cases:
        for t in (p["start"], p["stop"]):
            path = safe_path(era5 / stamped(ERA5_TEMPLATE, t, era5=True))
            with netCDF4.Dataset(path) as ds:
                dimensions = {
                    key: len(ds.dimensions[key])
                    for key in ("lat", "lon", "lev", "ilev")
                }
                if dimensions != dict(lat=192, lon=288, lev=32, ilev=33):
                    raise ValueError(f"ERA5 grid dimensions mismatch: {path}")
                for key, reference in grid.items():
                    if not np.allclose(ds[key][:], reference, rtol=0, atol=1e-12):
                        raise ValueError(f"ERA5/CAM {key} mismatch: {path}")
                if not all(key in ds.variables for key in ("U", "V", "T", "Q", "PS")):
                    raise ValueError(f"ERA5 fields missing: {path}")
    for key in ("lut_file", "lw_table"):
        path = safe_path(config[key])
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing optics table: {path}")
    with netCDF4.Dataset(config["lut_file"]) as ds:
        if ds.getncattr("mode_order") != "a1,a2,a3,a4":
            raise ValueError("LUT mode order mismatch")
    with exe.open("rb") as handle:
        executable_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    if executable_hash != config["executable_sha256"]:
        raise ValueError("The pinned shared executable has changed")
    return dict(
        era5_files_checked=len(checked),
        aod_source_files=len(sources),
        executable_sha256=executable_hash,
        aod_outer_edges=(
            "Single-valid-snapshot handling before 2007-12-22 and after 2008-12-31"
        ),
        cases=cases,
    ), sources


def namelist(config: dict, p: dict) -> str:
    template = safe_path(REPO / config["namelist_template"]).read_text()
    # The met-nudging end setting has day precision; the CIME stop enforces March's hour.
    end = p["stop"]
    if end.hour:
        end = end.replace(hour=0) + timedelta(days=1)
    return template.format(**config, month=p["month"],
                           begin_year=p["start"].year, begin_month=p["start"].month,
                           begin_day=p["start"].day, end_year=end.year,
                           end_month=end.month, end_day=end.day,
                           aod_begin=p["start"].strftime("%Y%m%d"),
                           aod_end=p["stop"].strftime("%Y%m%d"),
                           optics_directory=p["output_directory"] / "optics")


def verify_build(config: dict, case: Path) -> None:
    base = Path(config["base_case"])
    original = entries(base / "env_build.xml")
    actual = entries(case / "env_build.xml")
    ignored = {"EXEROOT", "BUILD_COMPLETE", "BUILD_STATUS"}
    diffs = {key: (value, actual.get(key)) for key, value in original.items()
             if key not in ignored and value != actual.get(key)}
    if diffs:
        raise ValueError(f"Shared-executable build settings differ: {diffs}")
    if (case / "SourceMods").resolve() != (base / "SourceMods").resolve():
        raise ValueError("Clone SourceMods do not match the executable owner")
    values = case_values(case)
    if resolved(values["EXEROOT"], values) != config["exeroot"]:
        raise ValueError("Clone EXEROOT does not match the executable owner")


def prepare(config: dict, cases: list[dict], sources: dict[str, Path]) -> None:
    linkdir = safe_path(config["aod_directory"], writable=True)
    linkdir.mkdir(parents=True, exist_ok=True)
    for name, source in sorted(sources.items()):
        link = linkdir / name
        if not link.is_symlink():
            link.symlink_to(source)
    logs = safe_path(config["log_root"], writable=True)
    logs.mkdir(parents=True, exist_ok=True)
    for p in cases:
        case = p["case_directory"]
        logpath = logs / f"{p['case_name']}.log"
        print(f"PREPARING {p['case_name']}: {p['start']} -> {p['stop']}", flush=True)
        with logpath.open("x") as log:
            def run(args: list[str], cwd: Path = case) -> None:
                log.write("\nCOMMAND " + json.dumps(args) + "\n")
                log.flush()
                result = subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise RuntimeError(f"Command failed ({result.returncode}); inspect {logpath}")

            run([str(Path(config["cesm_root"]) / "cime/scripts/create_clone"),
                 "--case", str(case), "--clone", config["base_case"], "--keepexe",
                 "--project", config["project"]], cwd=logs)
            output = p["output_directory"]
            output.mkdir(parents=True)
            (output / "optics").mkdir()
            settings = dict(
                RUN_TYPE="startup",
                GET_REFCASE="FALSE",
                RUN_STARTDATE=p["start"].strftime("%Y-%m-%d"),
                START_TOD=0, STOP_OPTION="nhours", STOP_N=p["stop_hours"], STOP_DATE=-999,
                REST_OPTION="ndays", REST_N=1, DOUT_S="FALSE", CONTINUE_RUN="FALSE", RESUBMIT=0,
                RUNDIR=output / "run", DOUT_S_ROOT=output / "archive",
                NTASKS=config["tasks"], NTHRDS=config["threads"], ROOTPE=0,
                MAX_TASKS_PER_NODE=128, MAX_MPITASKS_PER_NODE=128,
                JOB_QUEUE=config["queue"],
                JOB_WALLCLOCK_TIME=config["walltime"],
                PROJECT=config["project"],
            )
            run(["./xmlchange", ",".join(f"{key}={value}" for key, value in settings.items())])
            (case / "user_nl_cam").write_text(namelist(config, p))
            run(["./case.setup", "--reset"])
            verify_build(config, case)
            run(["./xmlchange", "BUILD_COMPLETE=TRUE"])
            run(["./preview_namelists"])
            # Reject unauthorized input-list paths before CIME checks or reads them.
            for listing in (case / "Buildconf").glob("*.input_data_list"):
                for line in safe_path(listing).read_text().splitlines():
                    if "=" in line:
                        value = line.split("=", 1)[1].strip()
                        if value.startswith("/"):
                            safe_path(value)
            run(["./check_input_data"])
            run(["./preview_run"])
            run([
                "./xmlquery",
                (
                    "CASE,CALENDAR,RUN_STARTDATE,STOP_OPTION,STOP_N,REST_N,"
                    "BUILD_COMPLETE,EXEROOT,RUNDIR,NTASKS_ATM,NTHRDS_ATM,"
                    "JOB_QUEUE,JOB_WALLCLOCK_TIME"
                ),
            ])
            verify_build(config, case)
            values = case_values(case)
            expected = dict(
                CALENDAR="NO_LEAP",
                RUN_STARTDATE=p["start"].strftime("%Y-%m-%d"),
                STOP_N=str(p["stop_hours"]),
                STOP_OPTION="nhours",
                BUILD_COMPLETE="TRUE",
            )
            for key, value in expected.items():
                if values.get(key) != value:
                    raise ValueError(f"Generated {case.name} {key} != {value}")
            atm = (case / "CaseDocs/atm_in").read_text()
            for key in ("nudge_model", "aod_nudge_on", "aod_optics_on"):
                if not re.search(rf"\b{key}\s*=\s*\.true\.", atm, re.I):
                    raise ValueError(f"{case.name}: {key} not enabled")
            for path in (
                config["aod_directory"],
                config["era5_directory"],
                config["lut_file"],
                str(output / "optics"),
            ):
                if path not in atm:
                    raise ValueError(f"Generated CAM namelist does not contain {path}")
            batch = (case / ".case.run").read_text()
            if "select=1:ncpus=128:mpiprocs=128:ompthreads=1:mem=235GB" not in batch:
                raise ValueError(f"Unexpected PBS resource request in {case}")
            log.write("\nCONFIGURATION VALIDATED; NOT SUBMITTED\n")
        print(f"VALIDATED {case.name}; log={logpath}", flush=True)


def reconfigure(config: dict, cases: list[dict]) -> None:
    """Repoint prepared, unsubmitted cases to the config's runtime output root."""
    logs = safe_path(config["log_root"], writable=True)
    logs.mkdir(parents=True, exist_ok=True)
    for p in cases:
        case = safe_path(p["case_directory"], writable=True)
        output = safe_path(p["output_directory"], writable=True)
        logpath = logs / f"{p['case_name']}.storage-reconfigure.log"
        print(f"RECONFIGURING {p['case_name']} -> {output}", flush=True)
        output.mkdir(parents=True)
        (output / "optics").mkdir()
        with logpath.open("x") as log:
            def run(args: list[str]) -> None:
                log.write("\nCOMMAND " + json.dumps(args) + "\n")
                log.flush()
                result = subprocess.run(
                    args, cwd=case, stdout=log, stderr=subprocess.STDOUT
                )
                if result.returncode:
                    raise RuntimeError(
                        f"Command failed ({result.returncode}); inspect {logpath}"
                    )

            run(["./xmlchange", f"RUNDIR={output / 'run'},DOUT_S_ROOT={output / 'archive'}"])
            (case / "user_nl_cam").write_text(namelist(config, p))
            verify_build(config, case)
            run(["./preview_namelists"])
            for listing in (case / "Buildconf").glob("*.input_data_list"):
                for line in safe_path(listing).read_text().splitlines():
                    if "=" in line:
                        value = line.split("=", 1)[1].strip()
                        if value.startswith("/"):
                            safe_path(value)
            run(["./check_input_data"])
            run(["./preview_run"])
            values = case_values(case)
            if resolved(values["RUNDIR"], values) != str(output / "run"):
                raise ValueError(f"Unexpected RUNDIR for {case.name}")
            atm = (case / "CaseDocs/atm_in").read_text()
            if str(output / "optics") not in atm:
                raise ValueError(f"Unexpected optics directory for {case.name}")
            log.write("\nSTORAGE RECONFIGURATION VALIDATED; NOT SUBMITTED\n")
        print(f"VALIDATED {case.name}; log={logpath}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--reconfigure", action="store_true")
    parser.add_argument("--month", action="append", help="Select YYYY-MM; repeat as needed")
    args = parser.parse_args()
    config = yaml.safe_load(safe_path(args.config).read_text())
    cases = plans(config)
    if args.month:
        cases = [p for p in cases if p["month"] in args.month]
        if {p["month"] for p in cases} != set(args.month):
            raise ValueError("Unknown month selection")
    report, sources = preflight(config, cases, existing_cases=args.reconfigure)
    print(json.dumps(report, indent=2, default=str), flush=True)
    if args.prepare:
        prepare(config, cases, sources)
    elif args.reconfigure:
        reconfigure(config, cases)


if __name__ == "__main__":
    main()
