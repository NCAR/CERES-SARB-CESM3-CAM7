from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = (
    ROOT / "scripts",
    ROOT / "sp1_aod_pipeline",
    ROOT / "sp2_tests",
    ROOT / "sp3_tests",
)
FORBIDDEN_MODULES = ("davinci_monet.plots", "matplotlib", "cartopy")
REMOVED_RENDERERS = (
    "scripts/run_modis_monthly_davinci_analysis.py",
    "sp1_aod_pipeline/verify/plots.py",
    "sp2_tests/plot_transport_proof.py",
    "sp2_tests/verify_pair.py",
    "sp2_tests/verify_plots.py",
    "sp2_tests/verify_profile.py",
    "sp3_tests/plot_sp3v2_aod_nudged_diagnostics.py",
    "sp3_tests/plot_verify5_aod_diagnostics.py",
    "sp3_tests/verify_sp3.py",
)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_project_scripts_cannot_render_plots_directly() -> None:
    violations: list[str] = []
    for directory in CODE_DIRS:
        for path in directory.rglob("*.py"):
            if "tests" in path.relative_to(ROOT).parts:
                continue
            for module in _imports(path):
                if module.startswith(FORBIDDEN_MODULES):
                    violations.append(f"{path.relative_to(ROOT)}: {module}")
    assert violations == []


def test_legacy_plot_renderers_are_removed() -> None:
    assert [path for path in REMOVED_RENDERERS if (ROOT / path).exists()] == []
