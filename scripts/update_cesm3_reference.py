#!/usr/bin/env python3
"""Generate the versioned reference for the project's live CESM3 checkout."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CESM_ROOT = Path("/glade/work/fillmore/CESM3/cesm3_0_beta08")
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "cesm3-checkout.md"
DEFAULT_COMPSETS = ("F2000dev", "FCHIST", "FCnudged", "FCts2nudged")
DEFAULT_GRIDS = ("f09_f09_mg17",)
DEFAULT_MACHINE = "derecho"
PROJECT_ACCOUNT = "P19010000"

NESTED_COMPONENTS = (
    ("CAM atmosphere physics", "components/cam/src/atmos_phys"),
    (
        "RTE+RRTMGP",
        "components/cam/src/atmos_phys/schemes/rrtmgp/ext",
    ),
    ("RRTMGP data", "components/cam/src/physics/rrtmgp/data"),
    ("CICE6 core", "components/cice/src"),
    ("Icepack", "components/cice/src/icepack"),
    ("MOM6", "components/mom/MOM6"),
)

DOCUMENTATION_PATHS = (
    (".gitmodules", "Top-level component URLs, expected tags, and checkout policy"),
    ("doc/source/quickstart.rst", "CESM quick start"),
    ("doc/source/cesm_configurations.rst", "CESM configuration overview"),
    ("cime/AGENTS.md", "CIME-local agent instructions"),
    ("cime/doc/source/ccs/query-configuration.rst", "CIME metadata queries"),
    ("cime/doc/source/ccs/creating-a-case.rst", "Case creation"),
    ("cime/doc/source/ccs/cloning-a-case.rst", "Case cloning"),
    ("cime/doc/source/ccs/setting-up-a-case.rst", "Case setup"),
    ("cime/doc/source/ccs/building-a-case.rst", "Case build"),
    ("cime/doc/source/ccs/running-a-case.rst", "Case execution"),
    (
        "cime/doc/source/ccs/model-configuration/variables/compsets.rst",
        "Compset schema",
    ),
    (
        "cime/doc/source/ccs/model-configuration/variables/grids.rst",
        "Grid schema",
    ),
    (
        "cime/doc/source/ccs/model-configuration/variables/machine.rst",
        "Machine schema",
    ),
    (
        "cime/doc/source/ccs/model-configuration/variables/namelist-definition.rst",
        "Component namelist schema",
    ),
    (
        "cime/doc/source/ccs/model-configuration/variables/user-mods.rst",
        "User-mods behavior",
    ),
    (
        "ccs_config/machines/derecho/config_machines.xml",
        "Derecho compilers, MPI libraries, and resources",
    ),
    (
        "ccs_config/machines/derecho/config_batch.xml",
        "Derecho queues and batch policy",
    ),
    ("components/cam/README.md", "CAM source overview"),
    (
        "components/cam/bld/namelist_files/namelist_definition.xml",
        "Authoritative CAM namelist definitions",
    ),
    (
        "components/cam/bld/namelist_files/namelist_defaults_cam.xml",
        "Authoritative CAM namelist defaults",
    ),
    (
        "components/cam/bld/namelist_files/use_cases",
        "CAM use-case namelist fragments",
    ),
)


class SnapshotError(RuntimeError):
    """Raised when the live checkout cannot produce a trustworthy snapshot."""


@dataclass(frozen=True)
class GitState:
    head: str
    describe: str
    branch: str | None
    status_lines: tuple[str, ...]
    overlay_fingerprint: str | None

    @property
    def clean(self) -> bool:
        return not self.status_lines


@dataclass(frozen=True)
class ComponentState:
    name: str
    path: str
    expected_tag: str | None
    required: str | None
    git: GitState | None


@dataclass(frozen=True)
class CompsetState:
    alias: str
    long_name: str | None
    support: tuple[str, ...]


@dataclass(frozen=True)
class GridState:
    alias: str
    long_name: str | None
    constraints: str | None


@dataclass(frozen=True)
class MachineState:
    name: str
    description: str
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class NamelistEntry:
    name: str
    type_name: str
    group: str
    default: str
    description: str


@dataclass(frozen=True)
class CheckoutSnapshot:
    cesm_root: Path
    root_git: GitState
    components: tuple[ComponentState, ...]
    nested_components: tuple[ComponentState, ...]
    compsets: tuple[CompsetState, ...]
    grids: tuple[GridState, ...]
    machine: MachineState
    namelist_entries: tuple[NamelistEntry, ...]
    met_nudging_entry_count: int
    documentation_counts: tuple[tuple[str, int], ...]


def fail(message: str, exit_code: int = 2) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def command(
    args: list[str],
    *,
    cwd: Path | None = None,
    allow_failure: bool = False,
) -> str:
    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LANG": "C", "GIT_PAGER": "cat"})
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode and not allow_failure:
        detail = (completed.stderr or completed.stdout).strip()
        raise SnapshotError(f"{' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def command_bytes(args: list[str], *, cwd: Path | None = None) -> bytes:
    env = os.environ.copy()
    env.update({"LC_ALL": "C", "LANG": "C", "GIT_PAGER": "cat"})
    completed = subprocess.run(args, cwd=cwd, env=env, capture_output=True)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).decode(
            "utf-8", errors="replace"
        )
        raise SnapshotError(f"{' '.join(args)} failed: {detail.strip()}")
    return completed.stdout


def dirty_overlay_fingerprint(repo: Path) -> str:
    digest = hashlib.sha256()
    digest.update(command_bytes(["git", "-C", str(repo), "diff", "--binary", "HEAD", "--"]))
    untracked = command_bytes(
        [
            "git",
            "-C",
            str(repo),
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        ]
    )
    for raw_path in sorted(item for item in untracked.split(b"\0") if item):
        relative = os.fsdecode(raw_path)
        path = repo / relative
        digest.update(b"\0path\0")
        digest.update(raw_path)
        if path.is_symlink():
            digest.update(b"\0symlink\0")
            digest.update(os.fsencode(os.readlink(path)))
        elif path.is_file():
            digest.update(b"\0file\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def git_state(path: Path) -> GitState:
    head = command(["git", "-C", str(path), "rev-parse", "HEAD"])
    describe = command(
        ["git", "-C", str(path), "describe", "--tags", "--always"],
        allow_failure=True,
    )
    branch = command(
        ["git", "-C", str(path), "symbolic-ref", "--quiet", "--short", "HEAD"],
        allow_failure=True,
    )
    status = command(
        [
            "git",
            "-C",
            str(path),
            "status",
            "--short",
            "--untracked-files=all",
        ]
    )
    status_lines = tuple(line for line in status.splitlines() if line)
    fingerprint = dirty_overlay_fingerprint(path) if status_lines else None
    return GitState(
        head=head,
        describe=describe or head[:12],
        branch=branch or None,
        status_lines=status_lines,
        overlay_fingerprint=fingerprint,
    )


def is_git_root(path: Path) -> bool:
    if not path.exists():
        return False
    top_level = command(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        allow_failure=True,
    )
    return bool(top_level) and Path(top_level).resolve() == path.resolve()


def parse_gitmodules(cesm_root: Path) -> tuple[ComponentState, ...]:
    modules_path = cesm_root / ".gitmodules"
    if not modules_path.is_file():
        raise SnapshotError(f"missing git-fleximod metadata: {modules_path}")

    parser = configparser.ConfigParser(interpolation=None, strict=False)
    # git-config permits indentation that ConfigParser can mistake for a
    # multiline value (the CIME entry mixes a tab and spaces). Normalize only
    # option indentation before parsing the git-fleximod metadata.
    modules_text = modules_path.read_text(encoding="utf-8")
    normalized = re.sub(
        r"^[ \t]+(?=[A-Za-z][A-Za-z0-9._-]*\s*=)",
        "",
        modules_text,
        flags=re.MULTILINE,
    )
    parser.read_string(normalized)
    components: list[ComponentState] = []
    for section in parser.sections():
        match = re.fullmatch(r'submodule "(.+)"', section)
        if not match:
            continue
        relative = parser.get(section, "path", fallback="").strip()
        if not relative:
            continue
        component_path = cesm_root / relative
        state = None
        if is_git_root(component_path):
            state = git_state(component_path)
        components.append(
            ComponentState(
                name=match.group(1),
                path=relative,
                expected_tag=parser.get(section, "fxtag", fallback=None),
                required=parser.get(section, "fxrequired", fallback=None),
                git=state,
            )
        )
    return tuple(components)


def collect_nested_components(cesm_root: Path) -> tuple[ComponentState, ...]:
    components: list[ComponentState] = []
    for name, relative in NESTED_COMPONENTS:
        path = cesm_root / relative
        components.append(
            ComponentState(
                name=name,
                path=relative,
                expected_tag=None,
                required=None,
                git=git_state(path) if is_git_root(path) else None,
            )
        )
    return tuple(components)


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_compsets_xml(xml_text: str, aliases: tuple[str, ...]) -> tuple[CompsetState, ...]:
    start = xml_text.find("<compsets")
    end_tag = "</compsets>"
    end = xml_text.rfind(end_tag)
    if start < 0 or end < 0:
        raise SnapshotError("query_config did not return a <compsets> XML document")
    try:
        root = ET.fromstring(xml_text[start : end + len(end_tag)])
    except ET.ParseError as exc:
        raise SnapshotError(f"cannot parse compset XML: {exc}") from exc

    by_alias: dict[str, CompsetState] = {}
    for node in root.iter():
        if local_tag(node.tag) != "compset":
            continue
        alias = ""
        long_name = ""
        support: list[str] = []
        for child in node:
            tag = local_tag(child.tag)
            if tag == "alias":
                alias = (child.text or "").strip()
            elif tag == "lname":
                long_name = (child.text or "").strip()
            elif tag.endswith("_support"):
                attributes = ", ".join(
                    f"{key}={value}" for key, value in sorted(child.attrib.items())
                )
                support.append(f"{tag}({attributes})" if attributes else tag)
        if alias:
            by_alias[alias.casefold()] = CompsetState(
                alias=alias,
                long_name=long_name or None,
                support=tuple(support),
            )

    return tuple(
        by_alias.get(
            alias.casefold(),
            CompsetState(alias=alias, long_name=None, support=()),
        )
        for alias in aliases
    )


def parse_grids_text(text: str, aliases: tuple[str, ...]) -> tuple[GridState, ...]:
    found: dict[str, GridState] = {}
    current_alias: str | None = None
    current_constraints: str | None = None
    current_long_name: str | None = None

    def flush() -> None:
        if current_alias is not None:
            found[current_alias.casefold()] = GridState(
                alias=current_alias,
                long_name=current_long_name,
                constraints=current_constraints,
            )

    for line in text.splitlines():
        alias_match = re.match(r"\s*alias:\s+(\S+)(?:\s+\((.+)\))?\s*$", line)
        if alias_match:
            flush()
            current_alias = alias_match.group(1)
            current_constraints = alias_match.group(2)
            current_long_name = None
            continue
        long_name_match = re.match(r"\s*longname:\s+(\S+)\s*$", line)
        if long_name_match and current_alias is not None:
            current_long_name = long_name_match.group(1)
    flush()

    return tuple(
        found.get(
            alias.casefold(),
            GridState(alias=alias, long_name=None, constraints=None),
        )
        for alias in aliases
    )


def parse_machine_text(text: str, requested_name: str) -> MachineState:
    description = ""
    fields: list[tuple[str, str]] = []
    for line in text.splitlines():
        header = re.match(
            rf"\s*{re.escape(requested_name)}(?:\s+\([^)]*\))?\s*:\s*(.+)$",
            line,
        )
        if header:
            description = header.group(1).strip()
            continue
        stripped = line.strip()
        if not stripped or stripped == "Machine(s)":
            continue
        pieces = re.split(r"\s{2,}", stripped, maxsplit=1)
        if len(pieces) == 2:
            key, value = pieces
            if key in {"compilers", "mpilibs"}:
                value = ",".join(
                    sorted(item.strip() for item in value.split(",") if item.strip())
                )
            fields.append((key, value))
    if not description:
        raise SnapshotError(f"cannot parse machine {requested_name!r} from query_config")
    return MachineState(
        name=requested_name,
        description=description,
        fields=tuple(fields),
    )


def collect_compsets(
    cesm_root: Path, aliases: tuple[str, ...]
) -> tuple[CompsetState, ...]:
    query_config = cesm_root / "cime" / "scripts" / "query_config"
    xml_text = command(
        [str(query_config), "--compsets", "cam", "--xml"],
        cwd=cesm_root,
    )
    return parse_compsets_xml(xml_text, aliases)


def collect_grids(cesm_root: Path, aliases: tuple[str, ...]) -> tuple[GridState, ...]:
    query_config = cesm_root / "cime" / "scripts" / "query_config"
    text = command([str(query_config), "--grids"], cwd=cesm_root)
    return parse_grids_text(text, aliases)


def collect_machine(cesm_root: Path, name: str) -> MachineState:
    query_config = cesm_root / "cime" / "scripts" / "query_config"
    text = command(
        [str(query_config), "--machines", name, "--long"],
        cwd=cesm_root,
    )
    return parse_machine_text(text, name)


def collapsed_text(node: ET.Element) -> str:
    return " ".join("".join(node.itertext()).split())


def parse_checkout_xml(path: Path) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError:
        # CAM's locally deployed namelist XML contains human-readable comments
        # such as "(&aod_nudging_nl)". CIME's parser accepts them, but a strict
        # XML parser does not. Repair only bare ampersands in the in-memory copy.
        text = path.read_text(encoding="utf-8")
        repaired = re.sub(
            r"&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;|#x[0-9A-Fa-f]+;)",
            "&amp;",
            text,
        )
        return ET.fromstring(repaired)


def collect_namelists(
    cesm_root: Path,
) -> tuple[tuple[NamelistEntry, ...], int]:
    definition_path = (
        cesm_root
        / "components"
        / "cam"
        / "bld"
        / "namelist_files"
        / "namelist_definition.xml"
    )
    defaults_path = (
        cesm_root
        / "components"
        / "cam"
        / "bld"
        / "namelist_files"
        / "namelist_defaults_cam.xml"
    )
    try:
        definitions = parse_checkout_xml(definition_path)
        defaults_text = defaults_path.read_text(encoding="utf-8")
    except (ET.ParseError, OSError) as exc:
        raise SnapshotError(f"cannot parse CAM namelist metadata: {exc}") from exc

    entries: list[NamelistEntry] = []
    met_nudging_count = 0
    for entry in definitions.iter():
        if local_tag(entry.tag) != "entry":
            continue
        name = entry.attrib.get("id", "")
        category = entry.attrib.get("category", "")
        if category == "nudging":
            met_nudging_count += 1
        if category not in {"aod_nudging", "aod_optics"} and not name.startswith("aod_"):
            continue
        description = re.sub(
            r"\s*Default:.*$",
            "",
            collapsed_text(entry),
            flags=re.IGNORECASE,
        ).strip()
        # CAM's defaults file contains legacy element names with percent signs,
        # which are accepted by CAM's tooling but are not legal XML. Extract
        # only the selected, valid namelist tags rather than rewriting the
        # checkout or trying to parse unrelated malformed entries.
        default_pattern = re.compile(
            rf"<{re.escape(name)}(?:\s[^>]*)?>(.*?)</{re.escape(name)}>",
            flags=re.DOTALL,
        )
        values = [
            " ".join(match.group(1).split())
            for match in default_pattern.finditer(defaults_text)
        ]
        rendered_default = "; ".join(value if value else '""' for value in values)
        entries.append(
            NamelistEntry(
                name=name,
                type_name=entry.attrib.get("type", ""),
                group=entry.attrib.get("group", ""),
                default=rendered_default or "not set",
                description=description,
            )
        )
    return tuple(entries), met_nudging_count


def count_documentation(cesm_root: Path) -> tuple[tuple[str, int], ...]:
    counts = {".md": 0, ".rst": 0, ".txt": 0}
    for path in cesm_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in counts:
            counts[path.suffix.lower()] += 1
    return tuple((suffix, counts[suffix]) for suffix in (".md", ".rst", ".txt"))


def collect_snapshot(
    cesm_root: Path,
    *,
    compset_aliases: tuple[str, ...],
    grid_aliases: tuple[str, ...],
    machine_name: str,
) -> CheckoutSnapshot:
    cesm_root = cesm_root.expanduser().resolve()
    if not (cesm_root / "cime" / "scripts" / "query_config").is_file():
        raise SnapshotError(f"not a complete CESM/CIME checkout: {cesm_root}")
    namelist_entries, met_nudging_count = collect_namelists(cesm_root)
    return CheckoutSnapshot(
        cesm_root=cesm_root,
        root_git=git_state(cesm_root),
        components=parse_gitmodules(cesm_root),
        nested_components=collect_nested_components(cesm_root),
        compsets=collect_compsets(cesm_root, compset_aliases),
        grids=collect_grids(cesm_root, grid_aliases),
        machine=collect_machine(cesm_root, machine_name),
        namelist_entries=namelist_entries,
        met_nudging_entry_count=met_nudging_count,
        documentation_counts=count_documentation(cesm_root),
    )


def markdown_cell(value: object) -> str:
    text = str(value).replace("\n", " ").replace("|", r"\|")
    return " ".join(text.split())


def markdown_table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(markdown_cell(value) for value in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def git_state_summary(state: GitState | None) -> str:
    if state is None:
        return "not checked out"
    if state.clean:
        return "clean"
    untracked = sum(line.startswith("??") for line in state.status_lines)
    changed = len(state.status_lines) - untracked
    details: list[str] = []
    if changed:
        details.append(f"{changed} changed")
    if untracked:
        details.append(f"{untracked} untracked")
    return "dirty (" + ", ".join(details) + ")"


def atmosphere_token(long_name: str | None) -> str:
    if not long_name:
        return "not found"
    match = re.search(r"(?:^|_)(CAM[^_]+)", long_name)
    return match.group(1) if match else "not resolved"


def render_reference(snapshot: CheckoutSnapshot) -> str:
    root = snapshot.root_git
    branch = root.branch or "detached HEAD"
    lines = [
        "# CESM3 Checkout Reference",
        "",
        "> Generated by `scripts/update_cesm3_reference.py`; do not hand-edit factual sections.",
        "> The live checkout and CIME-generated case state remain authoritative.",
        "",
        "## Authority and refresh",
        "",
        "Use this file as a versioned index and drift detector, not as a replacement for live",
        "`query_config`, CAM namelist XML, generated `CaseDocs`, or source inspection. Regenerate",
        "after changing the CESM tag, component revisions, CIME metadata, machine configuration,",
        "or the local CAM overlay.",
        "",
        "```bash",
        f"python scripts/update_cesm3_reference.py --cesm-root {snapshot.cesm_root}",
        f"python scripts/update_cesm3_reference.py --cesm-root {snapshot.cesm_root} --check",
        "```",
        "",
        "## Project baseline",
        "",
        f"- CESM root: `{snapshot.cesm_root}`",
        f"- Root revision: `{root.head}` (`{root.describe}`)",
        f"- Root branch state: `{branch}`",
        f"- Root worktree: **{git_state_summary(root)}**",
        f"- Project/account: `{PROJECT_ACCOUNT}`",
        "- Canonical experiment-specific source: this CERES-SARB-CAM7 repository; the CESM",
        "  checkout is a deployed working tree.",
        "",
        "## Top-level git-fleximod components",
        "",
    ]

    component_rows: list[tuple[object, ...]] = []
    for component in snapshot.components:
        state = component.git
        component_rows.append(
            (
                f"`{component.name}`",
                f"`{component.path}`",
                f"`{component.expected_tag}`" if component.expected_tag else "not declared",
                f"`{state.head[:12]}`" if state else "not checked out",
                f"`{state.describe}`" if state else "—",
                git_state_summary(state),
                (
                    f"`{state.overlay_fingerprint[:16]}`"
                    if state and state.overlay_fingerprint
                    else "—"
                ),
            )
        )
    lines.extend(
        [
            markdown_table(
                (
                    "Component",
                    "Path",
                    "Expected tag",
                    "HEAD",
                    "Describe",
                    "State",
                    "Overlay SHA-256",
                ),
                component_rows,
            ),
            "",
            "The overlay fingerprint hashes tracked diffs and untracked file contents, so a",
            "content change in the deployed CAM overlay makes `--check` fail even when the set of",
            "dirty paths is unchanged.",
            "",
            "## Selected nested science components",
            "",
        ]
    )

    nested_rows: list[tuple[object, ...]] = []
    for component in snapshot.nested_components:
        state = component.git
        nested_rows.append(
            (
                component.name,
                f"`{component.path}`",
                f"`{state.head[:12]}`" if state else "not checked out",
                f"`{state.describe}`" if state else "—",
                git_state_summary(state),
                (
                    f"`{state.overlay_fingerprint[:16]}`"
                    if state and state.overlay_fingerprint
                    else "—"
                ),
            )
        )
    lines.extend(
        [
            markdown_table(
                ("Component", "Path", "HEAD", "Describe", "State", "Overlay SHA-256"),
                nested_rows,
            ),
            "",
            "## Local checkout overlay",
            "",
            "Root status:",
            "",
            "```text",
            *(root.status_lines or ("clean",)),
            "```",
            "",
        ]
    )
    dirty_components = [
        component
        for component in (*snapshot.components, *snapshot.nested_components)
        if component.git is not None and not component.git.clean
    ]
    if dirty_components:
        for component in dirty_components:
            assert component.git is not None
            lines.extend(
                [
                    f"### `{component.path}`",
                    "",
                    f"Overlay fingerprint: `{component.git.overlay_fingerprint}`",
                    "",
                    "```text",
                    *component.git.status_lines,
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(["All checked-out components are clean.", ""])

    compset_rows: list[tuple[object, ...]] = []
    for compset in snapshot.compsets:
        compset_rows.append(
            (
                f"`{compset.alias}`",
                f"`{compset.long_name}`" if compset.long_name else "**not found**",
                f"`{atmosphere_token(compset.long_name)}`",
                "; ".join(compset.support) if compset.support else "not declared",
            )
        )
    non_cam7 = [
        compset.alias
        for compset in snapshot.compsets
        if compset.long_name and not atmosphere_token(compset.long_name).startswith("CAM70")
    ]
    lines.extend(
        [
            "## Targeted live compsets",
            "",
            markdown_table(
                ("Alias", "Resolved long name", "Atmosphere token", "Support"),
                compset_rows,
            ),
            "",
        ]
    )
    if non_cam7:
        joined = ", ".join(f"`{alias}`" for alias in non_cam7)
        lines.extend(
            [
                f"**Current-checkout warning:** {joined} do not resolve to `CAM70`.",
                "Do not present those aliases as CAM7 choices without querying a different",
                "checkout or constructing and validating an explicit CAM7 configuration.",
                "",
            ]
        )

    grid_rows = [
        (
            f"`{grid.alias}`",
            f"`{grid.long_name}`" if grid.long_name else "**not found**",
            grid.constraints or "none declared",
        )
        for grid in snapshot.grids
    ]
    lines.extend(
        [
            "## Targeted live grids",
            "",
            markdown_table(("Alias", "Resolved long name", "Constraints"), grid_rows),
            "",
            f"## `{snapshot.machine.name}` machine metadata",
            "",
            snapshot.machine.description,
            "",
            markdown_table(
                ("Field", "Value"),
                [(f"`{key}`", value) for key, value in snapshot.machine.fields],
            ),
            "",
            "Always let `create_newcase` and `preview_run` perform the final compatibility and",
            "resource checks for the selected compset/grid pair.",
            "",
            "## Current CAM AOD namelist overlay",
            "",
            "These entries come from the live, locally modified CAM namelist definition and",
            "defaults. They are project overlay metadata, not pristine beta08 metadata.",
            "",
        ]
    )
    namelist_rows = [
        (
            f"`{entry.name}`",
            f"`{entry.group}`",
            f"`{entry.type_name}`",
            f"`{entry.default}`",
            entry.description,
        )
        for entry in snapshot.namelist_entries
    ]
    lines.extend(
        [
            markdown_table(
                ("Name", "Group", "Type", "Default", "Description"),
                namelist_rows,
            ),
            "",
            (
                "The same definition contains "
                f"{snapshot.met_nudging_entry_count} standard meteorological-nudging entries "
                "under category `nudging`; query those live rather than duplicating them here."
            ),
            "",
            "## Checkout documentation index",
            "",
        ]
    )
    count_text = ", ".join(
        f"`*{suffix}`: {count}" for suffix, count in snapshot.documentation_counts
    )
    lines.extend(
        [
            f"Documentation-like files currently present: {count_text}. Agents can query",
            "Markdown, RST, XML, text, and source directly; conversion to Markdown is not",
            "required.",
            "",
        ]
    )
    documentation_rows = [
        (
            f"`{relative}`",
            purpose,
            "present" if (snapshot.cesm_root / relative).exists() else "**missing**",
        )
        for relative, purpose in DOCUMENTATION_PATHS
    ]
    lines.extend(
        [
            markdown_table(("Checkout-relative path", "Purpose", "State"), documentation_rows),
            "",
            "## Recommended agent lookup order",
            "",
            "1. Confirm the CESM root, root revision, component revisions, and dirty overlay.",
            "2. Query live compsets, grids, and machines with CIME.",
            "3. Read the relevant CIME RST page for lifecycle semantics.",
            "4. Read CAM namelist definitions/defaults and applicable use-case fragments.",
            "5. Create or inspect the case, then verify resolved XML and generated `CaseDocs`.",
            "6. Record the requested alias, resolved long name, source/component revisions,",
            "   overlay fingerprint, and validation evidence in project provenance.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or verify the versioned CESM3 checkout reference."
    )
    parser.add_argument(
        "--cesm-root",
        type=Path,
        default=Path(os.environ.get("CESM_ROOT", DEFAULT_CESM_ROOT)),
        help=f"CESM checkout (default: $CESM_ROOT or {DEFAULT_CESM_ROOT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Markdown output (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed Markdown differs from the live checkout.",
    )
    parser.add_argument(
        "--compset",
        action="append",
        dest="compsets",
        help="Target compset alias; repeat to replace project defaults.",
    )
    parser.add_argument(
        "--grid",
        action="append",
        dest="grids",
        help="Target grid alias; repeat to replace project defaults.",
    )
    parser.add_argument(
        "--machine",
        default=DEFAULT_MACHINE,
        help=f"CIME machine to summarize (default: {DEFAULT_MACHINE})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        snapshot = collect_snapshot(
            args.cesm_root,
            compset_aliases=tuple(args.compsets or DEFAULT_COMPSETS),
            grid_aliases=tuple(args.grids or DEFAULT_GRIDS),
            machine_name=args.machine,
        )
        rendered = render_reference(snapshot).rstrip() + "\n"
    except SnapshotError as exc:
        fail(str(exc))

    output = args.output.expanduser().resolve()
    if args.check:
        if not output.is_file():
            fail(f"reference does not exist: {output}", exit_code=1)
        if output.read_text(encoding="utf-8") != rendered:
            fail(
                "CESM3 checkout reference is stale; regenerate it with "
                f"{Path(__file__).relative_to(REPO_ROOT)}",
                exit_code=1,
            )
        print(f"CESM3 checkout reference is current: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote CESM3 checkout reference: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
