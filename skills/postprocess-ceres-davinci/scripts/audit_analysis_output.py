#!/usr/bin/env python3
"""Read-only audit of a completed CERES DAVINCI analysis directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit DAVINCI manifest, inspection, products, and plot artifacts."
    )
    parser.add_argument("run_dir", type=Path, help="DAVINCI analysis output directory")
    return parser


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"missing required JSON: {path}")
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {path}: {exc}")
        return {}
    if not isinstance(loaded, dict):
        errors.append(f"JSON root is not an object: {path}")
        return {}
    return loaded


def _artifact_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _artifact_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _artifact_strings(item)


def _resolve_artifact(value: str, run_dir: Path) -> Path | None:
    if not value.lower().endswith((".nc", ".pdf", ".json", ".csv")):
        return None
    path = Path(value)
    return path if path.is_absolute() else run_dir / path


def audit(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not run_dir.is_dir():
        errors.append(f"run directory does not exist: {run_dir}")
        return {
            "run_dir": str(run_dir),
            "passed": False,
            "errors": errors,
            "warnings": warnings,
        }

    manifest = _load_json(run_dir / "manifest.json", errors)
    inspection = _load_json(run_dir / "inspection" / "inspection.json", errors)

    pdfs = sorted((run_dir / "plots").rglob("*.pdf")) if (run_dir / "plots").is_dir() else []
    products = (
        sorted((run_dir / "products").rglob("*.nc"))
        if (run_dir / "products").is_dir()
        else []
    )
    previews = (
        sorted((run_dir / "inspection" / "previews").rglob("*.png"))
        if (run_dir / "inspection" / "previews").is_dir()
        else []
    )
    final_pngs = [
        path
        for path in run_dir.rglob("*.png")
        if "inspection" not in path.relative_to(run_dir).parts
    ]

    if not pdfs:
        errors.append("no final PDFs found below plots/")
    if not products:
        errors.append("no NetCDF products found below products/")
    if final_pngs:
        errors.append(
            f"{len(final_pngs)} PNG file(s) found outside inspection previews"
        )

    if manifest:
        if manifest.get("status") != "completed":
            errors.append(f"manifest status is {manifest.get('status')!r}, not 'completed'")
        failed_stages = manifest.get("failed_stages") or []
        if failed_stages:
            errors.append(f"manifest has failed stages: {failed_stages}")
        manifest_errors = manifest.get("errors") or {}
        if manifest_errors:
            errors.append("manifest contains errors")
        for stage, status in (manifest.get("stages") or {}).items():
            if status == "failed":
                errors.append(f"manifest stage failed: {stage}")

        missing_listed: list[str] = []
        for section in ("products", "plots", "analysis_artifacts"):
            for value in _artifact_strings(manifest.get(section)):
                artifact = _resolve_artifact(value, run_dir)
                if artifact is not None and not artifact.exists():
                    missing_listed.append(str(artifact))
        if missing_listed:
            errors.append(
                f"{len(missing_listed)} manifest-listed artifact(s) do not exist"
            )
            warnings.extend(f"missing artifact: {path}" for path in missing_listed[:10])

    inspection_checks: list[dict[str, Any]] = []
    if inspection:
        if inspection.get("passed") is not True:
            errors.append("inspection.passed is not true")
        checks = inspection.get("checks")
        if not isinstance(checks, list) or not checks:
            errors.append("inspection checks are missing")
        else:
            inspection_checks = [
                {
                    "name": check.get("name"),
                    "passed": check.get("passed"),
                    "detail": check.get("detail"),
                }
                for check in checks
                if isinstance(check, dict)
            ]
            failed_checks = [
                check.get("name")
                for check in checks
                if isinstance(check, dict) and check.get("passed") is not True
            ]
            if failed_checks:
                errors.append(f"inspection checks failed: {failed_checks}")

    if pdfs and len(previews) < len(pdfs):
        errors.append(
            f"only {len(previews)} inspection preview(s) exist for {len(pdfs)} PDF(s)"
        )

    return {
        "run_dir": str(run_dir),
        "passed": not errors,
        "manifest_status": manifest.get("status") if manifest else None,
        "inspection_passed": inspection.get("passed") if inspection else None,
        "counts": {
            "products_nc": len(products),
            "final_pdfs": len(pdfs),
            "inspection_previews_png": len(previews),
            "pngs_outside_inspection": len(final_pngs),
        },
        "inspection_checks": inspection_checks,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    args = _parser().parse_args()
    result = audit(args.run_dir)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
