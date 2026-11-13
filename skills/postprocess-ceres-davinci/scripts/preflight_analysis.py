#!/usr/bin/env python3
"""Read-only preflight checks for CERES DAVINCI project YAML files."""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by the CLI environment
    raise SystemExit(
        "PyYAML is required; run this script with the CERES davinci environment."
    ) from exc


DEFAULT_DATA_ROOT = Path("/glade/work/fillmore/Data/CERES-SARB-CAM7")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a CERES DAVINCI YAML and inventory its source globs."
    )
    parser.add_argument("config", type=Path, help="Project YAML under analyses/davinci")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="CERES repository root (default: current directory)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Required root for generated artifacts",
    )
    parser.add_argument(
        "--allow-regional",
        action="store_true",
        help="Allow a non-global domain when explicitly requested",
    )
    parser.add_argument(
        "--skip-source-check",
        action="store_true",
        help="Validate policy without expanding source file globs",
    )
    return parser


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _parse_time(value: Any, label: str, errors: list[str]) -> datetime | None:
    if value is None:
        errors.append(f"analysis.{label} is required")
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"analysis.{label} is not ISO-8601: {value!r}")
        return None


def _patterns(files: Any) -> list[str]:
    if isinstance(files, str):
        return [files]
    if isinstance(files, list) and all(isinstance(item, str) for item in files):
        return list(files)
    return []


def _resolve_pattern(pattern: str, project_root: Path) -> str:
    expanded = os.path.expanduser(os.path.expandvars(pattern))
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return str(candidate)


def _aod_style_warnings(config: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    skip_terms = ("minus", "difference", "increment", "ratio", "fraction", "mask")
    containers: list[tuple[str, dict[str, Any]]] = []

    for source_name, source in (config.get("sources") or {}).items():
        if isinstance(source, dict):
            containers.append(
                (f"sources.{source_name}.variables", source.get("variables") or {})
            )
    for analysis_name, analysis in (config.get("analyses") or {}).items():
        if isinstance(analysis, dict):
            containers.append(
                (f"analyses.{analysis_name}.fields", analysis.get("fields") or {})
            )

    for prefix, specs in containers:
        if not isinstance(specs, dict):
            continue
        for name, spec in specs.items():
            if not isinstance(spec, dict):
                continue
            text = " ".join(
                str(spec.get(key, ""))
                for key in ("source_name", "display_name", "long_name")
            )
            lowered = f"{name} {text}".lower()
            if "aod" not in lowered or any(term in lowered for term in skip_terms):
                continue
            if spec.get("style_preset") != "geosit_aod":
                warnings.append(
                    f"{prefix}.{name} looks like an AOD magnitude but does not declare "
                    "style_preset: geosit_aod"
                )
    return warnings


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    project_root = args.project_root.resolve()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = project_root / config_path
    config_path = config_path.resolve()
    data_root = args.data_root.resolve()

    errors: list[str] = []
    warnings: list[str] = []
    source_inventory: dict[str, Any] = {}

    if not config_path.is_file():
        errors.append(f"config does not exist: {config_path}")
        return {
            "config": str(config_path),
            "passed": False,
            "errors": errors,
            "warnings": warnings,
            "sources": source_inventory,
        }

    required_config_root = project_root / "analyses" / "davinci"
    if not _inside(config_path, required_config_root):
        errors.append(f"config must be under {required_config_root}")

    with config_path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        errors.append("config root must be a mapping")
        loaded = {}

    analysis = loaded.get("analysis")
    if not isinstance(analysis, dict):
        errors.append("analysis mapping is required")
        analysis = {}

    start = _parse_time(analysis.get("start_time"), "start_time", errors)
    end = _parse_time(analysis.get("end_time"), "end_time", errors)
    if start is not None and end is not None and start > end:
        errors.append("analysis.start_time must not be after analysis.end_time")

    domain = analysis.get("domain")
    if domain != "global" and not args.allow_regional:
        errors.append(
            f"analysis.domain is {domain!r}; use global or pass --allow-regional for an "
            "explicitly requested clipped view"
        )

    output_dir_value = analysis.get("output_dir")
    if not output_dir_value:
        errors.append("analysis.output_dir is required")
        output_dir = None
    else:
        output_dir = Path(os.path.expandvars(str(output_dir_value))).expanduser()
        if not output_dir.is_absolute():
            errors.append("analysis.output_dir must be absolute")
        elif not _inside(output_dir, data_root):
            errors.append(f"analysis.output_dir must be under {data_root}")

    inspection = loaded.get("inspection")
    if not isinstance(inspection, dict):
        errors.append("inspection mapping is required")
    else:
        if inspection.get("enabled") is not True:
            errors.append("inspection.enabled must be true")
        if inspection.get("required") is not True:
            errors.append("inspection.required must be true")

    plot_suites = loaded.get("plot_suites")
    plots = loaded.get("plots")
    if not plot_suites and not plots:
        errors.append("at least one plot_suites or plots declaration is required")

    sources = loaded.get("sources")
    if not isinstance(sources, dict) or not sources:
        errors.append("at least one source is required")
        sources = {}

    for source_name, source in sources.items():
        if not isinstance(source, dict):
            errors.append(f"sources.{source_name} must be a mapping")
            continue
        source_patterns = _patterns(source.get("files"))
        if not source_patterns:
            errors.append(f"sources.{source_name}.files must be a path or list of paths")
            continue
        pattern_records: list[dict[str, Any]] = []
        total_matches = 0
        for pattern in source_patterns:
            resolved = _resolve_pattern(pattern, project_root)
            matches = [] if args.skip_source_check else sorted(glob.glob(resolved))
            if not args.skip_source_check and not matches:
                errors.append(f"sources.{source_name} matched no files: {resolved}")
            total_matches += len(matches)
            pattern_records.append(
                {
                    "pattern": resolved,
                    "count": len(matches),
                    "first": matches[0] if matches else None,
                    "last": matches[-1] if matches else None,
                }
            )
        source_inventory[source_name] = {
            "match_count": total_matches,
            "patterns": pattern_records,
        }

    warnings.extend(_aod_style_warnings(loaded))

    return {
        "config": str(config_path),
        "analysis_window": {
            "start": str(analysis.get("start_time")) if analysis else None,
            "end": str(analysis.get("end_time")) if analysis else None,
        },
        "domain": domain,
        "output_dir": str(output_dir) if output_dir is not None else None,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "sources": source_inventory,
    }


def main() -> int:
    args = _parser().parse_args()
    result = preflight(args)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
