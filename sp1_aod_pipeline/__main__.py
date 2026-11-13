"""CLI for the SP1 AOD observation pipeline."""

import argparse
import sys

from .acquire import stage_sp1
from .bias import fit_bias, resolve_coeffs
from .config import RunConfig
from .contract import validate_contract_file
from .pipeline import run


def _cmd_run(args):
    cfg = RunConfig.from_yaml(args.config)
    coeffs = resolve_coeffs(cfg, args.bias)
    for path in run(cfg, coeffs):
        print("wrote", path)


def _cmd_validate(args):
    ok, errors = validate_contract_file(args.path)
    if ok:
        print("OK", args.path)
        return
    print("INVALID", args.path)
    for error in errors:
        print("  -", error)
    sys.exit(1)


def _cmd_download(args):
    cfg = RunConfig.from_yaml(args.config)
    start = cfg.start.isoformat()
    end = cfg.end.isoformat()
    for collection in ("mod04", "myd04", "aerdb_noaa20"):
        paths = stage_sp1(collection, start, end, cfg.stage_root, dry_run=args.dry_run)
        print(collection, "->", len(list(paths)), "granule(s)")


def _cmd_fit_bias(args):
    import numpy as np

    data = np.load(args.npz)
    coeffs = fit_bias(data["modis"], data["viirs"], data["aeronet"])
    coeffs.to_json(args.out)
    print(
        f"rmse_before={coeffs.rmse_before:.4f} "
        f"rmse_after={coeffs.rmse_after:.4f} n={coeffs.n} -> {args.out}"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sp1_aod_pipeline")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--bias", default=None)
    run_parser.set_defaults(func=_cmd_run)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.set_defaults(func=_cmd_validate)

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("--config", required=True)
    download_parser.add_argument("--dry-run", action="store_true")
    download_parser.set_defaults(func=_cmd_download)

    bias_parser = subparsers.add_parser("fit-bias")
    bias_parser.add_argument("--npz", required=True)
    bias_parser.add_argument("--out", required=True)
    bias_parser.set_defaults(func=_cmd_fit_bias)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
