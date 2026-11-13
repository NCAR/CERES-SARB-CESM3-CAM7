#!/usr/bin/env python3
"""Post-run checks for SP3v2 T10 verification artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import xarray as xr

from sp3_tests.check_sp3_outputs import DEFAULT_BANDS
from sp3_tests.check_sp3_outputs import Sp3DirectorySummary
from sp3_tests.check_sp3_outputs import check_physical_invariants
from sp3_tests.check_sp3_outputs import summarize_directory


@dataclass(frozen=True)
class CprncResult:
    on_file: str
    off_file: str
    log_file: str
    returncode: int
    identical: bool


def assert_sp3_directory_complete(
    indir: Path,
    *,
    expected_groups: int = 81,
    expected_bands: Iterable[str] = DEFAULT_BANDS,
    expected_first_stamp: str | None = None,
    expected_last_stamp: str | None = None,
) -> Sp3DirectorySummary:
    if not indir.is_dir():
        raise AssertionError(f"{indir}: not a directory")
    summary = summarize_directory(indir, expected_bands=expected_bands)
    expected_file_count = expected_groups * len(tuple(expected_bands))
    if summary.file_count != expected_file_count:
        raise AssertionError(f"{indir}: expected {expected_file_count} files, found {summary.file_count}")
    if summary.group_count != expected_groups:
        raise AssertionError(f"{indir}: expected {expected_groups} groups, found {summary.group_count}")
    if summary.incomplete_groups:
        raise AssertionError(f"{indir}: incomplete SP3 groups: {summary.incomplete_groups}")
    if summary.interval_errors:
        raise AssertionError(f"{indir}: interval errors: {summary.interval_errors}")
    if expected_first_stamp is not None and summary.first_stamp != expected_first_stamp:
        raise AssertionError(f"{indir}: expected first stamp {expected_first_stamp}, found {summary.first_stamp}")
    if expected_last_stamp is not None and summary.last_stamp != expected_last_stamp:
        raise AssertionError(f"{indir}: expected last stamp {expected_last_stamp}, found {summary.last_stamp}")
    return summary


def assert_no_sp3_files(indir: Path) -> int:
    if not indir.is_dir():
        return 0
    files = sorted(indir.glob("AER_MAM4_*.nc"))
    if files:
        raise AssertionError(f"{indir}: expected no SP3 files, found {len(files)}")
    return 0


def assert_sp3_attrs(
    indir: Path,
    *,
    expected_method: str | None = None,
    expected_lut_file: str | None = None,
    expected_nudged: int | None = None,
) -> int:
    if not indir.is_dir():
        raise AssertionError(f"{indir}: not a directory")
    files = sorted(indir.glob("AER_MAM4_*.nc"))
    if not files:
        raise AssertionError(f"{indir}: no SP3 files found")
    for path in files:
        with xr.open_dataset(path) as ds:
            if expected_method is not None and ds.attrs.get("method") != expected_method:
                raise AssertionError(f"{path.name}: method attr {ds.attrs.get('method')!r} != {expected_method!r}")
            if expected_lut_file is not None and ds.attrs.get("lut_file") != expected_lut_file:
                raise AssertionError(f"{path.name}: lut_file attr {ds.attrs.get('lut_file')!r} != {expected_lut_file!r}")
            if expected_nudged is not None:
                actual = ds.attrs.get("nudged")
                if actual is None or int(actual) != int(expected_nudged):
                    raise AssertionError(f"{path.name}: nudged attr {actual!r} != {expected_nudged!r}")
    return len(files)


def h0i_pairs(
    on_run: Path,
    off_run: Path,
    *,
    on_case: str = "sp3_verify10_on",
    off_case: str = "sp3_verify10_off",
    expected_count: int | None = None,
    expected_first_stamp: str | None = None,
    expected_last_stamp: str | None = None,
) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for on_file in sorted(on_run.glob(f"{on_case}.cam.h0i.*.nc")):
        off_name = on_file.name.replace(on_case, off_case, 1)
        off_file = off_run / off_name
        if not off_file.exists():
            raise AssertionError(f"missing OFF h0i pair for {on_file.name}: {off_file}")
        pairs.append((on_file, off_file))
    if not pairs:
        raise AssertionError(f"{on_run}: no {on_case}.cam.h0i.*.nc files found")
    if expected_count is not None and len(pairs) != expected_count:
        raise AssertionError(f"expected {expected_count} h0i pairs, found {len(pairs)}")
    stamps = [path.name.split(".cam.h0i.", 1)[1].removesuffix(".nc") for path, _ in pairs]
    if expected_first_stamp is not None and stamps[0] != expected_first_stamp:
        raise AssertionError(f"expected first h0i stamp {expected_first_stamp}, found {stamps[0]}")
    if expected_last_stamp is not None and stamps[-1] != expected_last_stamp:
        raise AssertionError(f"expected last h0i stamp {expected_last_stamp}, found {stamps[-1]}")
    return pairs


def cprnc_log_is_identical(text: str) -> bool:
    upper = text.upper()
    if "NOT IDENTICAL" in upper:
        return False
    return "IDENTICAL" in upper


def run_cprnc_pairs(pairs: Iterable[tuple[Path, Path]], *, cprnc: Path, outdir: Path) -> list[CprncResult]:
    outdir.mkdir(parents=True, exist_ok=True)
    results: list[CprncResult] = []
    for on_file, off_file in pairs:
        stamp = on_file.name.split(".cam.h0i.", 1)[1].removesuffix(".nc")
        log_file = outdir / f"{stamp}.log"
        completed = subprocess.run(
            [str(cprnc), str(on_file), str(off_file)],
            text=True,
            capture_output=True,
            check=False,
        )
        log_text = completed.stdout + completed.stderr
        log_file.write_text(log_text, encoding="utf-8")
        results.append(
            CprncResult(
                on_file=str(on_file),
                off_file=str(off_file),
                log_file=str(log_file),
                returncode=int(completed.returncode),
                identical=completed.returncode == 0 and cprnc_log_is_identical(log_text),
            )
        )
    return results


def assert_cprnc_identical(log_files: Iterable[Path]) -> None:
    failures = [path.name for path in log_files if not cprnc_log_is_identical(path.read_text(encoding="utf-8"))]
    if failures:
        raise AssertionError(f"cprnc logs missing IDENTICAL: {', '.join(failures)}")


def assert_cprnc_results_identical(results: Iterable[CprncResult]) -> None:
    failures = [
        f"{Path(result.log_file).name} returncode={result.returncode} identical={result.identical}"
        for result in results
        if result.returncode != 0 or not result.identical
    ]
    if failures:
        raise AssertionError(f"cprnc comparisons failed: {', '.join(failures)}")


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lut-on-dir", required=True, type=Path)
    parser.add_argument("--lut-off-dir", required=True, type=Path)
    parser.add_argument("--on-run", required=True, type=Path)
    parser.add_argument("--off-run", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--cprnc", default="/glade/campaign/cesm/cesmdata/cprnc/cprnc", type=Path)
    parser.add_argument("--expected-groups", default=81, type=int)
    parser.add_argument("--expected-first-stamp", default="20080701.00000")
    parser.add_argument("--expected-last-stamp", default="20080711.00000")
    parser.add_argument("--expected-h0i-pairs", default=10, type=int)
    parser.add_argument("--expected-h0i-first-stamp")
    parser.add_argument("--expected-h0i-last-stamp")
    parser.add_argument("--expected-lut-file")
    parser.add_argument("--aodnudged-dir", type=Path)
    parser.add_argument("--skip-cprnc", action="store_true")
    args = parser.parse_args(argv)

    summary = assert_sp3_directory_complete(
        args.lut_on_dir,
        expected_groups=args.expected_groups,
        expected_first_stamp=args.expected_first_stamp,
        expected_last_stamp=args.expected_last_stamp,
    )
    invariants = check_physical_invariants(args.lut_on_dir)
    lut_attr_count = assert_sp3_attrs(
        args.lut_on_dir,
        expected_method="lut",
        expected_lut_file=args.expected_lut_file,
        expected_nudged=0,
    )
    off_count = assert_no_sp3_files(args.lut_off_dir)
    aodnudged_attr_count = None
    aodnudged_summary = None
    if args.aodnudged_dir is not None:
        aodnudged_summary = assert_sp3_directory_complete(
            args.aodnudged_dir,
            expected_groups=args.expected_groups,
            expected_first_stamp=args.expected_first_stamp,
            expected_last_stamp=args.expected_last_stamp,
        )
        aodnudged_attr_count = assert_sp3_attrs(
            args.aodnudged_dir,
            expected_method="lut",
            expected_lut_file=args.expected_lut_file,
            expected_nudged=1,
        )
    pairs = h0i_pairs(
        args.on_run,
        args.off_run,
        expected_count=args.expected_h0i_pairs,
        expected_first_stamp=args.expected_h0i_first_stamp,
        expected_last_stamp=args.expected_h0i_last_stamp,
    )
    cprnc_results: list[CprncResult] = []
    if not args.skip_cprnc:
        cprnc_results = run_cprnc_pairs(pairs, cprnc=args.cprnc, outdir=args.outdir / "cprnc_lut_on_vs_off")
        assert_cprnc_results_identical(cprnc_results)

    report = {
        "lut_on_summary": asdict(summary),
        "lut_on_invariants": invariants,
        "lut_on_attr_count": lut_attr_count,
        "lut_off_file_count": off_count,
        "aodnudged_attr_count": aodnudged_attr_count,
        "aodnudged_summary": asdict(aodnudged_summary) if aodnudged_summary is not None else None,
        "h0i_pair_count": len(pairs),
        "cprnc_results": [asdict(result) for result in cprnc_results],
    }
    path = write_json(args.outdir / "sp3v2_t10_readonly_summary.json", report)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
