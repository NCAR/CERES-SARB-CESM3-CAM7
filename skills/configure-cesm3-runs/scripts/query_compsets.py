#!/usr/bin/env python3
"""Filter compset metadata from an installed CESM/CIME checkout."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NoReturn


DEFAULT_CESM_ROOT = Path("/glade/work/fillmore/CESM3/cesm3_0_beta08")


@dataclass(frozen=True)
class Compset:
    alias: str
    long_name: str
    support: tuple[str, ...]

    @property
    def science_supported(self) -> bool:
        return any(item.startswith("science_support") for item in self.support)


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_args() -> argparse.Namespace:
    default_root = Path(os.environ.get("CESM_ROOT", DEFAULT_CESM_ROOT))
    parser = argparse.ArgumentParser(
        description="Query exact compset aliases, long names, and support from CIME."
    )
    parser.add_argument("--cesm-root", type=Path, default=default_root)
    parser.add_argument(
        "--component",
        default="cam",
        help="CIME active component passed to query_config --compsets (default: cam)",
    )
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        help="Exact alias to select; repeat for multiple aliases",
    )
    parser.add_argument(
        "--match",
        action="append",
        default=[],
        metavar="REGEX",
        help="Case-insensitive regex; repeated expressions must all match",
    )
    parser.add_argument(
        "--science-supported-only",
        action="store_true",
        help="Keep only entries with an explicit science_support declaration",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum entries to print; 0 means unlimited (default: 50)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def query_xml(cesm_root: Path, component: str) -> ET.Element:
    query_config = cesm_root / "cime" / "scripts" / "query_config"
    if not query_config.is_file():
        fail(f"CIME query_config does not exist: {query_config}")

    try:
        completed = subprocess.run(
            [str(query_config), "--compsets", component, "--xml"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        fail(f"query_config failed: {detail}")

    start = completed.stdout.find("<compsets")
    end_tag = "</compsets>"
    end = completed.stdout.rfind(end_tag)
    if start < 0 or end < 0:
        fail("query_config did not return a <compsets> XML document")

    try:
        return ET.fromstring(completed.stdout[start : end + len(end_tag)])
    except ET.ParseError as exc:
        fail(f"cannot parse query_config XML: {exc}")


def format_support(node: ET.Element) -> tuple[str, ...]:
    support: list[str] = []
    for child in node:
        tag = child.tag.rsplit("}", 1)[-1]
        if not tag.endswith("_support"):
            continue
        attributes = ", ".join(f"{key}={value}" for key, value in sorted(child.attrib.items()))
        support.append(f"{tag}({attributes})" if attributes else tag)
    return tuple(support)


def load_compsets(root: ET.Element) -> list[Compset]:
    entries: list[Compset] = []
    for node in root.findall("compset"):
        alias = (node.findtext("alias") or "").strip()
        long_name = (node.findtext("lname") or "").strip()
        if alias and long_name:
            entries.append(
                Compset(
                    alias=alias,
                    long_name=long_name,
                    support=format_support(node),
                )
            )
    return sorted(entries, key=lambda item: item.alias.casefold())


def compile_patterns(expressions: list[str]) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for expression in expressions:
        try:
            patterns.append(re.compile(expression, re.IGNORECASE))
        except re.error as exc:
            fail(f"invalid --match regular expression {expression!r}: {exc}")
    return patterns


def select_compsets(entries: list[Compset], args: argparse.Namespace) -> list[Compset]:
    aliases = {value.casefold() for value in args.alias}
    patterns = compile_patterns(args.match)
    selected: list[Compset] = []

    for entry in entries:
        if aliases and entry.alias.casefold() not in aliases:
            continue
        if args.science_supported_only and not entry.science_supported:
            continue
        searchable = " ".join((entry.alias, entry.long_name, *entry.support))
        if not all(pattern.search(searchable) for pattern in patterns):
            continue
        selected.append(entry)
    return selected


def print_text(cesm_root: Path, component: str, entries: list[Compset], total: int) -> None:
    print(f"CESM root: {cesm_root}")
    print(f"Component: {component}")
    print(f"Matches: {total}")
    for entry in entries:
        support = "; ".join(entry.support) if entry.support else "not declared"
        print()
        print(entry.alias)
        print(f"  long_name: {entry.long_name}")
        print(f"  support: {support}")


def main() -> int:
    args = parse_args()
    cesm_root = args.cesm_root.expanduser().resolve()
    if args.limit < 0:
        fail("--limit cannot be negative")

    root = query_xml(cesm_root, args.component)
    entries = select_compsets(load_compsets(root), args)
    if not entries:
        print("No compsets matched the requested filters.", file=sys.stderr)
        return 1

    total = len(entries)
    visible = entries if args.limit == 0 else entries[: args.limit]
    if args.json:
        payload = {
            "cesm_root": str(cesm_root),
            "component": args.component,
            "match_count": total,
            "compsets": [asdict(entry) for entry in visible],
        }
        print(json.dumps(payload, indent=2))
    else:
        print_text(cesm_root, args.component, visible, total)

    if len(visible) < total:
        print(
            f"Showing {len(visible)} of {total} matches; refine --match or use --limit 0.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
