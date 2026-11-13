# CERES DAVINCI Analysis Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the DAVINCI product, plotting, inspection, and CERES config path needed to regenerate the current five-day July 2008 AOD/optics diagnostics as full DAVINCI analyses.

**Architecture:** All executable code goes into `/glade/work/fillmore/DAVINCI`; `/glade/work/fillmore/CERES-SARB-CAM7` receives only YAML configs, docs, and config tests. DAVINCI gains a role/formula-based gridded analysis product layer, artifact writer, manifest writer, plot-suite expansion, and inspection stage/CLI. Plots consume persisted `analysis.nc` products rather than recomputing science fields from raw inputs.

**Tech Stack:** Python 3.11, xarray, numpy, netCDF4, pydantic v2, Typer, pytest, DAVINCI pipeline stages/renderers, CERES-SARB-CAM7 YAML configs and existing five-day July 2008 data.

---

## Scope Check

The approved spec covers multiple subsystems. This plan keeps them in one master plan because the final deliverable is one integrated regeneration workflow, but the tasks are ordered as independently verifiable slices:

1. gridded product engine,
2. artifact and manifest contract,
3. AOD plotting and inspection,
4. CERES AOD configs,
5. SARB-band optics support,
6. final five-day regeneration.

Do not start a later task until the full applicable test suites from the current task pass, or the task notes record the exact infrastructure blocker and narrower command that passed.

## Required Worktree And Commands

At execution time, create or use an isolated worktree for DAVINCI before editing it. The current `/glade/work/fillmore/DAVINCI` checkout has unrelated untracked files, so do not mix implementation commits with that dirty tree.

Use these shell variables in task notes:

```bash
export DV=/glade/work/fillmore/DAVINCI
export CERES=/glade/work/fillmore/CERES-SARB-CAM7
export PY=/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python
```

Full DAVINCI verification after every DAVINCI task:

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests -q
```

Full CERES verification after every CERES config/doc task, and after DAVINCI changes that affect CERES compatibility:

```bash
cd "$CERES"
PYTHONPATH="$CERES" "$PY" -m pytest tests sp1_aod_pipeline/tests sp3_tests -q
```

If a full-suite command cannot run because of queue, filesystem, or external-data limitations, record the command, the exact failure, and the narrower command that passed. The final five-day regeneration gate still requires full verification.

## File Structure

DAVINCI files to create:

- `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/formula.py` - safe expression parser/evaluator for role/formula fields.
- `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/gridded_reductions.py` - grouped xarray reductions and summary helpers.
- `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/gridded.py` - registered `gridded_analysis` derived analysis.
- `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/artifacts.py` - product NetCDF, summary JSON, and product re-read helpers.
- `/glade/work/fillmore/DAVINCI/davinci_monet/plots/suites.py` - plot-suite expansion for AOD and SARB optics.
- `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/core.py` - inspection models, preset registry, and run-directory inspection engine.
- `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/presets.py` - built-in AOD and SARB optics inspection presets.
- `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/__init__.py` - public inspection exports.
- `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/plot_suites.py` - pipeline stage that expands configured plot suites into concrete plots.
- `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/inspection.py` - optional inspection pipeline stage.
- `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/manifest.py` - final manifest writer.
- `/glade/work/fillmore/DAVINCI/davinci_monet/cli/commands/inspect.py` - `davinci-monet inspect <run-dir>` command.
- DAVINCI tests under:
  - `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/`
  - `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/plots/`
  - `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/inspection/`
  - `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/`
  - `/glade/work/fillmore/DAVINCI/davinci_monet/tests/integration/`

DAVINCI files to modify:

- `/glade/work/fillmore/DAVINCI/davinci_monet/config/schema.py` - config models for `gridded_analysis`, `plot_suites`, and `inspection`.
- `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/__init__.py` - import `gridded` for registration.
- `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/analyses.py` - write/re-read product artifacts for product analyses.
- `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/factory.py` - insert plot-suite, inspection, and manifest stages.
- `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/__init__.py` - re-export new stages.
- `/glade/work/fillmore/DAVINCI/davinci_monet/cli/app.py` and `/glade/work/fillmore/DAVINCI/davinci_monet/cli/commands/__init__.py` - register `inspect`.
- `/glade/work/fillmore/DAVINCI/pyproject.toml` - include inspection package data only if preset data files are introduced.

CERES files to create:

- `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/cam-aod-analysis-july-2008.yaml`
- `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/modis-viirs-aod-monthly-analysis-july-2008.yaml`
- `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/sarb-band-aerosol-optics-july-2008.yaml`
- `/glade/work/fillmore/CERES-SARB-CAM7/tests/test_davinci_analysis_configs.py`

CERES files to modify:

- `/glade/work/fillmore/CERES-SARB-CAM7/RUN.md` - add the new DAVINCI run-directory commands after the configs exist.
- `/glade/work/fillmore/CERES-SARB-CAM7/docs/HANDOFF.md` - add the migration status after the five-day regeneration completes.

---

### Task 1: DAVINCI Schema For Gridded Products, Plot Suites, And Inspection

**Files:**
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/config/schema.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_gridded_analysis_schema.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/config/test_product_config_schema.py`

- [ ] **Step 1: Write failing schema tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_gridded_analysis_schema.py`:

```python
from __future__ import annotations

import pytest

from davinci_monet.config.schema import MonetConfig


def _base_sources() -> dict:
    return {
        "cam": {
            "type": "generic",
            "files": "cam.nc",
            "variables": {
                "AODNDG_OBS": {},
                "AODNDG_MODEL_PRE": {},
                "AODNDG_MODEL_POST": {},
                "AODNDG_MASK": {},
            },
        }
    }


def test_gridded_analysis_spec_parses_roles_fields_and_groupby() -> None:
    cfg = MonetConfig(
        sources=_base_sources(),
        analyses={
            "daily_aod": {
                "type": "gridded_analysis",
                "source": "cam",
                "groupby": "day",
                "roles": {
                    "observation": "AODNDG_OBS",
                    "first_guess": "AODNDG_MODEL_PRE",
                    "analysis": "AODNDG_MODEL_POST",
                    "mask": "AODNDG_MASK",
                },
                "fields": {
                    "analyzed_aod": {"formula": 'mean(analysis, dim="time")'},
                    "nudge_fraction": {"formula": 'mean(mask, dim="time")'},
                },
            }
        },
    )
    spec = cfg.analyses["daily_aod"]
    assert spec.type == "gridded_analysis"
    assert spec.source == "cam"
    assert spec.groupby == "day"
    assert spec.roles["analysis"] == "AODNDG_MODEL_POST"
    assert spec.fields["analyzed_aod"].formula == 'mean(analysis, dim="time")'


def test_gridded_analysis_requires_at_least_one_role_and_field() -> None:
    with pytest.raises(ValueError, match="roles"):
        MonetConfig(
            sources=_base_sources(),
            analyses={
                "bad": {
                    "type": "gridded_analysis",
                    "source": "cam",
                    "groupby": "day",
                    "roles": {},
                    "fields": {"x": {"formula": "1"}},
                }
            },
        )
    with pytest.raises(ValueError, match="fields"):
        MonetConfig(
            sources=_base_sources(),
            analyses={
                "bad": {
                    "type": "gridded_analysis",
                    "source": "cam",
                    "groupby": "day",
                    "roles": {"analysis": "AODNDG_MODEL_POST"},
                    "fields": {},
                }
            },
        )
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/config/test_product_config_schema.py`:

```python
from __future__ import annotations

from davinci_monet.config.schema import MonetConfig


def test_plot_suites_and_inspection_config_parse() -> None:
    cfg = MonetConfig(
        sources={"product": {"type": "generic", "files": "analysis.nc"}},
        plots={},
        plot_suites={
            "daily_aod": {
                "preset": "gridded_aod_diagnostics",
                "source": "daily_aod",
                "group": "daily",
                "output_subdir": "plots/daily",
            }
        },
        inspection={
            "enabled": True,
            "required": True,
            "presets": ["gridded_aod_diagnostics"],
            "preview_format": "png",
        },
    )
    assert cfg.plot_suites["daily_aod"].preset == "gridded_aod_diagnostics"
    assert cfg.inspection.enabled is True
    assert cfg.inspection.required is True
```

- [ ] **Step 2: Run schema tests and verify they fail**

Run:

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_gridded_analysis_schema.py \
  davinci_monet/tests/unit/config/test_product_config_schema.py -q
```

Expected: failure because `gridded_analysis`, `plot_suites`, and `inspection` schemas do not exist.

- [ ] **Step 3: Add schema models**

Modify `/glade/work/fillmore/DAVINCI/davinci_monet/config/schema.py`:

```python
class FormulaFieldSpec(StrictSchema):
    """One named field produced by a gridded analysis formula."""

    formula: str
    units: str | None = None
    long_name: str | None = None
    display_name: str | None = None
    style_preset: str | None = None


class CustomWindowSpec(StrictSchema):
    """Named inclusive time window for grouped products."""

    name: str
    start: datetime | str
    end: datetime | str


class GriddedAnalysisSpec(StrictSchema):
    """Role/formula-driven gridded analysis product."""

    type: Literal["gridded_analysis"]
    source: str
    groupby: Literal["day", "month", "season", "all"] | list[CustomWindowSpec] = "all"
    roles: dict[str, str]
    fields: dict[str, FormulaFieldSpec]
    output_group: str | None = None

    @field_validator("roles")
    @classmethod
    def _roles_nonempty(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("gridded_analysis roles must not be empty")
        return value

    @field_validator("fields")
    @classmethod
    def _fields_nonempty(cls, value: dict[str, FormulaFieldSpec]) -> dict[str, FormulaFieldSpec]:
        if not value:
            raise ValueError("gridded_analysis fields must not be empty")
        return value


class PlotSuiteConfig(StrictSchema):
    """A named plot-suite expansion over one product source."""

    preset: str
    source: str
    group: str | None = None
    output_subdir: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    overrides: dict[str, Any] = Field(default_factory=dict)


class InspectionConfig(StrictSchema):
    """Optional visual-inspection configuration."""

    enabled: bool = False
    required: bool = False
    presets: list[str] = Field(default_factory=list)
    preview_format: Literal["png"] = "png"
```

Update `AnalysisSpec`, `build_analysis_spec`, and `MonetConfig`:

```python
AnalysisSpec = EOFSpec | WaveletSpec | GriddedAnalysisSpec


def build_analysis_spec(cfg: Any) -> AnalysisSpec:
    if isinstance(cfg, (EOFSpec, WaveletSpec, GriddedAnalysisSpec)):
        return cfg
    if not isinstance(cfg, dict):
        raise ValueError(f"analysis entry must be a mapping, got {type(cfg).__name__}")
    analysis_type = cfg.get("type")
    if analysis_type == "eof":
        return EOFSpec(**cfg)
    if analysis_type == "wavelet":
        return WaveletSpec(**cfg)
    if analysis_type == "gridded_analysis":
        return GriddedAnalysisSpec(**cfg)
    raise ValueError(
        "Unknown analysis type "
        f"{analysis_type!r}. Available analysis types: eof, wavelet, gridded_analysis"
    )
```

Add `plot_suites` and `inspection` fields plus validators to `MonetConfig`:

```python
plot_suites: dict[str, PlotSuiteConfig] = Field(default_factory=dict)
inspection: InspectionConfig | None = None

@field_validator("plot_suites", mode="before")
@classmethod
def parse_plot_suites(cls, value: Any) -> dict[str, PlotSuiteConfig]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {
            str(name): PlotSuiteConfig(**cfg) if isinstance(cfg, dict) else cfg
            for name, cfg in value.items()
        }
    return dict(value)

@field_validator("inspection", mode="before")
@classmethod
def parse_inspection(cls, value: Any) -> InspectionConfig | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return InspectionConfig(**value)
    return value
```

- [ ] **Step 4: Run schema tests and full DAVINCI suite**

Run:

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_gridded_analysis_schema.py \
  davinci_monet/tests/unit/config/test_product_config_schema.py -q
"$PY" -m pytest davinci_monet/tests -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
cd "$DV"
git add davinci_monet/config/schema.py \
  davinci_monet/tests/unit/analysis/test_gridded_analysis_schema.py \
  davinci_monet/tests/unit/config/test_product_config_schema.py
git commit -m "analysis: add gridded product config schema"
```

---

### Task 2: Safe Formula Evaluator

**Files:**
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/formula.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_formula.py`

- [ ] **Step 1: Write failing formula tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_formula.py`:

```python
from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from davinci_monet.analysis.formula import FormulaError, evaluate_formula


def _dataset() -> xr.Dataset:
    time = np.array(["2008-07-01T00:00", "2008-07-01T03:00"], dtype="datetime64[ns]")
    lat = np.array([-1.0, 1.0])
    lon = np.array([0.0, 90.0])
    shape = (2, 2, 2)
    return xr.Dataset(
        {
            "analysis": (("time", "lat", "lon"), np.arange(8, dtype=float).reshape(shape)),
            "observation": (("time", "lat", "lon"), np.ones(shape)),
            "mask": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[1.0, 0.0], [1.0, 0.0]],
                        [[0.0, 1.0], [1.0, 0.0]],
                    ]
                ),
            ),
            "count": (("time", "lat", "lon"), np.ones(shape) * 2.0),
        },
        coords={"time": time, "lat": lat, "lon": lon},
    )


def test_arithmetic_expression_uses_role_names() -> None:
    out = evaluate_formula("analysis - observation", _dataset())
    np.testing.assert_allclose(out.values, _dataset()["analysis"].values - 1.0)


def test_whitelisted_mean_and_active_mean() -> None:
    ds = _dataset()
    mean = evaluate_formula('mean(analysis, dim="time")', ds)
    active = evaluate_formula('active_mean(analysis - observation, mask > 0.5, dim="time")', ds)
    assert mean.dims == ("lat", "lon")
    assert active.dims == ("lat", "lon")
    np.testing.assert_allclose(mean.values, [[2.0, 3.0], [4.0, 5.0]])
    np.testing.assert_allclose(active.values[0, 0], -1.0)
    np.testing.assert_allclose(active.values[0, 1], 4.0)


def test_weighted_mean_and_where() -> None:
    ds = _dataset()
    out = evaluate_formula('weighted_mean(where(mask > 0.5, analysis, nan), count, dim="time")', ds)
    assert out.dims == ("lat", "lon")
    assert np.isfinite(out.values[0, 0])
    assert np.isnan(out.values[1, 1])


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('date')",
        "analysis.values",
        "open('x')",
        "lambda x: x",
        "[x for x in [1]]",
    ],
)
def test_unsafe_expressions_are_rejected(expr: str) -> None:
    with pytest.raises(FormulaError):
        evaluate_formula(expr, _dataset())
```

- [ ] **Step 2: Run formula tests and verify they fail**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_formula.py -q
```

Expected: failure because `davinci_monet.analysis.formula` does not exist.

- [ ] **Step 3: Implement evaluator**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/formula.py` with:

```python
from __future__ import annotations

import ast
from typing import Any

import numpy as np
import xarray as xr


class FormulaError(ValueError):
    """Raised when a formula is invalid or unsafe."""


_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)
_ALLOWED_UNARY = (ast.UAdd, ast.USub, ast.Not)
_ALLOWED_COMPARE = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_ALLOWED_BOOL = (ast.And, ast.Or)


def _mean(value: xr.DataArray, *, dim: str | list[str] | None = None) -> xr.DataArray:
    return value.mean(dim=dim, skipna=True)


def _sum(value: xr.DataArray, *, dim: str | list[str] | None = None) -> xr.DataArray:
    return value.sum(dim=dim, skipna=True)


def _count(value: xr.DataArray, *, dim: str | list[str] | None = None) -> xr.DataArray:
    return value.count(dim=dim)


def _where(condition: xr.DataArray, x: Any, y: Any) -> xr.DataArray:
    return xr.where(condition, x, y)


def _weighted_mean(
    value: xr.DataArray, weight: xr.DataArray, *, dim: str | list[str] | None = None
) -> xr.DataArray:
    valid = value.notnull() & weight.notnull() & (weight > 0)
    numer = value.where(valid).fillna(0.0) * weight.where(valid).fillna(0.0)
    denom = weight.where(valid).sum(dim=dim, skipna=True)
    return numer.sum(dim=dim, skipna=True) / denom.where(denom > 0)


def _active_mean(
    value: xr.DataArray, active: xr.DataArray, *, dim: str | list[str] | None = None
) -> xr.DataArray:
    masked = value.where(active)
    return masked.mean(dim=dim, skipna=True)


def _fraction(active: xr.DataArray, *, dim: str | list[str] | None = None) -> xr.DataArray:
    return active.astype(float).mean(dim=dim, skipna=True)


def _percentile(
    value: xr.DataArray, q: float, *, dim: str | list[str] | None = None
) -> xr.DataArray:
    return value.quantile(q / 100.0, dim=dim, skipna=True)


_FUNCTIONS = {
    "mean": _mean,
    "sum": _sum,
    "count": _count,
    "fraction": _fraction,
    "weighted_mean": _weighted_mean,
    "active_mean": _active_mean,
    "where": _where,
    "percentile": _percentile,
}


class _Evaluator(ast.NodeVisitor):
    def __init__(self, env: dict[str, Any]) -> None:
        self.env = env

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id == "nan":
            return np.nan
        if node.id not in self.env:
            raise FormulaError(f"unknown formula name: {node.id}")
        return self.env[node.id]

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (str, int, float, bool)) or node.value is None:
            return node.value
        raise FormulaError(f"unsupported constant: {node.value!r}")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        if not isinstance(node.op, _ALLOWED_BINOPS):
            raise FormulaError("unsupported arithmetic operator")
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
        return left % right

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        if not isinstance(node.op, _ALLOWED_UNARY):
            raise FormulaError("unsupported unary operator")
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        return ~operand

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if not isinstance(node.op, _ALLOWED_BOOL):
            raise FormulaError("unsupported boolean operator")
        values = [self.visit(value) for value in node.values]
        out = values[0]
        for value in values[1:]:
            out = (out & value) if isinstance(node.op, ast.And) else (out | value)
        return out

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        result = None
        for op, comp in zip(node.ops, node.comparators):
            if not isinstance(op, _ALLOWED_COMPARE):
                raise FormulaError("unsupported comparison operator")
            right = self.visit(comp)
            if isinstance(op, ast.Eq):
                current = left == right
            elif isinstance(op, ast.NotEq):
                current = left != right
            elif isinstance(op, ast.Lt):
                current = left < right
            elif isinstance(op, ast.LtE):
                current = left <= right
            elif isinstance(op, ast.Gt):
                current = left > right
            else:
                current = left >= right
            result = current if result is None else (result & current)
            left = right
        return result

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise FormulaError("formula calls are limited to whitelisted functions")
        args = [self.visit(arg) for arg in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords if kw.arg is not None}
        return _FUNCTIONS[node.func.id](*args, **kwargs)

    def generic_visit(self, node: ast.AST) -> Any:
        raise FormulaError(f"unsupported formula syntax: {type(node).__name__}")


def evaluate_formula(expression: str, env: xr.Dataset | dict[str, Any]) -> xr.DataArray:
    """Evaluate a constrained arithmetic formula against xarray variables."""

    names = dict(env.data_vars) if isinstance(env, xr.Dataset) else dict(env)
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(str(exc)) from exc
    try:
        result = _Evaluator(names).visit(tree)
    except FormulaError:
        raise
    except Exception as exc:
        raise FormulaError(str(exc)) from exc
    if not isinstance(result, xr.DataArray):
        raise FormulaError("formula did not produce an xarray DataArray")
    return result
```

- [ ] **Step 4: Run task and full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_formula.py -q
"$PY" -m pytest davinci_monet/tests -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
cd "$DV"
git add davinci_monet/analysis/formula.py davinci_monet/tests/unit/analysis/test_formula.py
git commit -m "analysis: add safe formula evaluator"
```

---

### Task 3: Grouped Gridded Reductions

**Files:**
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/gridded_reductions.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_gridded_reductions.py`

- [ ] **Step 1: Write failing grouped-reduction tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_gridded_reductions.py`:

```python
from __future__ import annotations

import numpy as np
import xarray as xr

from davinci_monet.analysis.gridded_reductions import (
    group_dataset,
    product_summary,
    robust_limits,
    symmetric_limits,
)


def _ds() -> xr.Dataset:
    time = np.array(
        [
            "2008-07-01T00:00",
            "2008-07-01T03:00",
            "2008-07-02T00:00",
            "2008-08-01T00:00",
        ],
        dtype="datetime64[ns]",
    )
    return xr.Dataset(
        {
            "aod": (("time", "lat", "lon"), np.arange(16, dtype=float).reshape(4, 2, 2)),
            "mask": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[1, 0], [1, 0]],
                        [[1, 1], [0, 0]],
                        [[0, 1], [1, 1]],
                        [[1, 1], [1, 1]],
                    ],
                    dtype=float,
                ),
            ),
        },
        coords={"time": time, "lat": [-1.0, 1.0], "lon": [0.0, 90.0]},
    )


def test_group_dataset_day_and_month() -> None:
    daily = group_dataset(_ds(), "day")
    monthly = group_dataset(_ds(), "month")
    assert list(daily) == ["2008-07-01", "2008-07-02", "2008-08-01"]
    assert list(monthly) == ["2008-07", "2008-08"]
    assert daily["2008-07-01"].sizes["time"] == 2
    assert monthly["2008-07"].sizes["time"] == 3


def test_group_dataset_custom_windows() -> None:
    groups = group_dataset(
        _ds(),
        [
            {"name": "first_two", "start": "2008-07-01T00:00", "end": "2008-07-01T23:59"},
            {"name": "all_july", "start": "2008-07-01", "end": "2008-07-31T23:59"},
        ],
    )
    assert list(groups) == ["first_two", "all_july"]
    assert groups["first_two"].sizes["time"] == 2
    assert groups["all_july"].sizes["time"] == 3


def test_product_summary_and_limits_ignore_nan_and_outlier() -> None:
    values = xr.DataArray(np.array([0.0, 0.1, 0.2, np.nan, 10.0]), dims=["x"])
    summary = product_summary({"field": values})
    assert summary["field"]["finite_count"] == 4
    assert summary["field"]["max"] == 10.0
    lo, hi = robust_limits(values)
    assert lo <= 0.1
    assert hi < 10.0
    slo, shi = symmetric_limits(xr.DataArray(np.array([-0.02, 0.0, 0.03, 5.0]), dims=["x"]))
    assert slo < 0.0 and shi > 0.0
    assert shi < 5.0
```

- [ ] **Step 2: Run grouped-reduction tests and verify they fail**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_gridded_reductions.py -q
```

Expected: failure because `gridded_reductions.py` does not exist.

- [ ] **Step 3: Implement grouping and summary helpers**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/gridded_reductions.py` with:

```python
from __future__ import annotations

from collections import OrderedDict
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr


def _label_time(value: Any, freq: str) -> str:
    stamp = pd.Timestamp(value)
    if freq == "day":
        return stamp.strftime("%Y-%m-%d")
    if freq == "month":
        return stamp.strftime("%Y-%m")
    if freq == "season":
        return f"{stamp.year}-{stamp.month:02d}-{stamp.day:02d}-{stamp.quarter}"
    return "all"


def group_dataset(
    ds: xr.Dataset,
    groupby: str | list[dict[str, Any]],
) -> "OrderedDict[str, xr.Dataset]":
    """Split a dataset into deterministic named groups."""

    groups: "OrderedDict[str, xr.Dataset]" = OrderedDict()
    if groupby == "all":
        groups["all"] = ds
        return groups
    if groupby in {"day", "month", "season"}:
        labels = [_label_time(value, str(groupby)) for value in ds["time"].values]
        for label in dict.fromkeys(labels):
            mask = np.asarray(labels) == label
            groups[label] = ds.isel(time=mask)
        return groups
    if isinstance(groupby, list):
        for window in groupby:
            name = str(window["name"])
            groups[name] = ds.sel(time=slice(window["start"], window["end"]))
        return groups
    raise ValueError(f"unsupported groupby value: {groupby!r}")


def _finite(values: xr.DataArray) -> np.ndarray:
    arr = np.asarray(values.values, dtype=float)
    return arr[np.isfinite(arr)]


def robust_limits(values: xr.DataArray, percentiles: tuple[float, float] = (2.0, 98.0)) -> tuple[float, float]:
    finite = _finite(values)
    if finite.size == 0:
        return 0.0, 1.0
    lo, hi = np.nanpercentile(finite, percentiles)
    if lo == hi:
        pad = max(abs(float(lo)) * 0.05, 0.05)
        return float(lo - pad), float(hi + pad)
    return float(lo), float(hi)


def symmetric_limits(values: xr.DataArray, fallback: float = 0.05) -> tuple[float, float]:
    finite = _finite(values)
    if finite.size == 0:
        return -fallback, fallback
    abs_values = np.abs(finite)
    q1, q3 = np.nanpercentile(abs_values, [25.0, 75.0])
    iqr = q3 - q1
    if iqr > 0.0:
        robust = abs_values[abs_values <= q3 + 1.5 * iqr]
        if robust.size:
            abs_values = robust
    limit = float(np.nanmax(abs_values))
    if limit == 0.0:
        limit = fallback
    return -limit, limit


def product_summary(fields: dict[str, xr.DataArray]) -> dict[str, dict[str, float | int | None]]:
    summary: dict[str, dict[str, float | int | None]] = {}
    for name, field in fields.items():
        finite = _finite(field)
        if finite.size == 0:
            summary[name] = {
                "finite_count": 0,
                "min": None,
                "mean": None,
                "max": None,
                "p02": None,
                "p50": None,
                "p98": None,
            }
            continue
        summary[name] = {
            "finite_count": int(finite.size),
            "min": float(np.nanmin(finite)),
            "mean": float(np.nanmean(finite)),
            "max": float(np.nanmax(finite)),
            "p02": float(np.nanpercentile(finite, 2.0)),
            "p50": float(np.nanpercentile(finite, 50.0)),
            "p98": float(np.nanpercentile(finite, 98.0)),
        }
    return summary
```

- [ ] **Step 4: Run task and full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_gridded_reductions.py -q
"$PY" -m pytest davinci_monet/tests -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
cd "$DV"
git add davinci_monet/analysis/gridded_reductions.py \
  davinci_monet/tests/unit/analysis/test_gridded_reductions.py
git commit -m "analysis: add grouped gridded reductions"
```

---

### Task 4: Registered Gridded Analysis Engine

**Files:**
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/gridded.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/__init__.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_gridded_analysis.py`

- [ ] **Step 1: Write failing gridded-analysis tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_gridded_analysis.py`:

```python
from __future__ import annotations

import numpy as np
import xarray as xr

from davinci_monet.analysis.gridded import GriddedAnalysis
from davinci_monet.config.schema import GriddedAnalysisSpec


def _cam_ds() -> xr.Dataset:
    time = np.array(["2008-07-01T00:00", "2008-07-01T03:00"], dtype="datetime64[ns]")
    lat = np.array([-1.0, 1.0])
    lon = np.array([0.0, 90.0])
    obs = np.array([[[0.2, -999.0], [0.3, -999.0]], [[0.4, 0.5], [0.6, -999.0]]])
    pre = np.array([[[0.1, 0.1], [0.2, 0.2]], [[0.2, 0.2], [0.3, 0.3]]])
    post = np.array([[[0.18, 0.1], [0.28, 0.2]], [[0.36, 0.46], [0.58, 0.3]]])
    mask = np.array([[[1, 0], [1, 0]], [[1, 1], [1, 0]]], dtype=float)
    return xr.Dataset(
        {
            "AODNDG_OBS": (("time", "lat", "lon"), obs),
            "AODNDG_MODEL_PRE": (("time", "lat", "lon"), pre),
            "AODNDG_MODEL_POST": (("time", "lat", "lon"), post),
            "AODNDG_MASK": (("time", "lat", "lon"), mask),
        },
        coords={"time": time, "lat": lat, "lon": lon},
        attrs={"geometry": "grid", "source_label": "cam"},
    )


def _spec() -> GriddedAnalysisSpec:
    return GriddedAnalysisSpec(
        type="gridded_analysis",
        source="cam",
        groupby="day",
        roles={
            "observation": "AODNDG_OBS",
            "first_guess": "AODNDG_MODEL_PRE",
            "analysis": "AODNDG_MODEL_POST",
            "mask": "AODNDG_MASK",
        },
        fields={
            "analyzed_aod": {"formula": 'mean(analysis, dim="time")'},
            "analysis_increment_aod": {
                "formula": 'active_mean(analysis - first_guess, mask > 0.5, dim="time")'
            },
            "nudge_fraction": {"formula": 'mean(mask, dim="time")'},
        },
    )


def test_gridded_analysis_builds_grouped_fields() -> None:
    out = GriddedAnalysis().analyze(_cam_ds(), _spec())
    assert out.attrs["geometry"] == "grid"
    assert out.attrs["analysis_type"] == "gridded_analysis"
    assert out.attrs["groupby"] == "day"
    assert "group" in out.dims
    assert "analyzed_aod" in out
    assert "analysis_increment_aod" in out
    assert "nudge_fraction" in out
    assert out["analyzed_aod"].dims == ("group", "lat", "lon")
    np.testing.assert_allclose(out["nudge_fraction"].values[0], [[1.0, 0.5], [1.0, 0.0]])


def test_gridded_analysis_names_formula_failures() -> None:
    spec = _spec()
    spec.fields["bad"] = type(spec.fields["analyzed_aod"])(formula="unknown + 1")
    try:
        GriddedAnalysis().analyze(_cam_ds(), spec)
    except ValueError as exc:
        assert "bad" in str(exc)
        assert "unknown" in str(exc)
    else:
        raise AssertionError("bad formula should fail")
```

- [ ] **Step 2: Run gridded-analysis tests and verify they fail**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_gridded_analysis.py -q
```

Expected: failure because `davinci_monet.analysis.gridded` does not exist.

- [ ] **Step 3: Implement `GriddedAnalysis` and register it**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/gridded.py` with:

```python
from __future__ import annotations

import numpy as np
import xarray as xr

from davinci_monet.analysis.base import DerivedAnalysis
from davinci_monet.analysis.formula import FormulaError, evaluate_formula
from davinci_monet.analysis.gridded_reductions import group_dataset
from davinci_monet.config.schema import GriddedAnalysisSpec
from davinci_monet.core.protocols import DataGeometry
from davinci_monet.core.registry import analysis_registry


def _role_dataset(data: xr.Dataset, roles: dict[str, str]) -> xr.Dataset:
    missing = [var for var in roles.values() if var not in data]
    if missing:
        raise ValueError(f"gridded_analysis source is missing variables: {missing}")
    return xr.Dataset(
        {role: data[var] for role, var in roles.items()},
        attrs=dict(data.attrs),
    )


@analysis_registry.register("gridded_analysis")
class GriddedAnalysis(DerivedAnalysis):
    """Role/formula-driven gridded analysis product."""

    name = "gridded_analysis"
    long_name = "Gridded Analysis Product"
    output_geometry = DataGeometry.GRID

    def analyze(self, data: xr.Dataset, spec: GriddedAnalysisSpec) -> xr.Dataset:
        role_ds = _role_dataset(data, spec.roles)
        groups = group_dataset(role_ds, spec.groupby)
        per_group: list[xr.Dataset] = []
        labels: list[str] = []
        for label, subset in groups.items():
            fields: dict[str, xr.DataArray] = {}
            env = subset.copy()
            for field_name, field_spec in spec.fields.items():
                try:
                    field = evaluate_formula(field_spec.formula, env)
                except FormulaError as exc:
                    raise ValueError(f"formula failed for field '{field_name}': {exc}") from exc
                field = field.rename(field_name)
                if field_spec.units:
                    field.attrs["units"] = field_spec.units
                if field_spec.long_name:
                    field.attrs["long_name"] = field_spec.long_name
                if field_spec.display_name:
                    field.attrs["display_name"] = field_spec.display_name
                if field_spec.style_preset:
                    field.attrs["style_preset"] = field_spec.style_preset
                fields[field_name] = field
                env[field_name] = field
            per_group.append(xr.Dataset(fields))
            labels.append(label)
        out = xr.concat(per_group, dim=xr.IndexVariable("group", np.asarray(labels, dtype=object)))
        out.attrs.update(
            {
                "geometry": "grid",
                "analysis_type": "gridded_analysis",
                "source": spec.source,
                "groupby": str(spec.groupby),
                "source_label": spec.output_group or "gridded_analysis",
            }
        )
        return out
```

Modify `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/__init__.py`:

```python
from davinci_monet.analysis import eof as _eof  # noqa: F401
from davinci_monet.analysis import gridded as _gridded  # noqa: F401
from davinci_monet.analysis import wavelet as _wavelet  # noqa: F401
```

- [ ] **Step 4: Run task and full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_gridded_analysis.py \
  davinci_monet/tests/unit/analysis/test_gridded_analysis_schema.py -q
"$PY" -m pytest davinci_monet/tests -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
cd "$DV"
git add davinci_monet/analysis/gridded.py davinci_monet/analysis/__init__.py \
  davinci_monet/tests/unit/analysis/test_gridded_analysis.py
git commit -m "analysis: add gridded analysis product"
```

---

### Task 5: Product Artifact Writer And Analysis-Stage Integration

**Files:**
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/artifacts.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/analyses.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_artifacts.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/test_gridded_artifact_stage.py`

- [ ] **Step 1: Write failing artifact tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/analysis/test_artifacts.py`:

```python
from __future__ import annotations

import json

import numpy as np
import xarray as xr

from davinci_monet.analysis.artifacts import write_product_artifacts


def test_write_product_artifacts_writes_netcdf_and_summary(tmp_path) -> None:
    ds = xr.Dataset(
        {"aod": (("group", "lat", "lon"), np.array([[[0.1, np.nan], [0.2, 0.3]]]))},
        coords={"group": ["2008-07-01"], "lat": [-1.0, 1.0], "lon": [0.0, 90.0]},
        attrs={"analysis_type": "gridded_analysis"},
    )
    result = write_product_artifacts(tmp_path, "daily_aod", ds)
    assert result.analysis_path == tmp_path / "products" / "daily_aod" / "analysis.nc"
    assert result.summary_path == tmp_path / "products" / "daily_aod" / "summary.json"
    assert result.analysis_path.exists()
    summary = json.loads(result.summary_path.read_text())
    assert summary["product"] == "daily_aod"
    assert summary["fields"]["aod"]["finite_count"] == 3
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/test_gridded_artifact_stage.py`:

```python
from __future__ import annotations

import json

import numpy as np
import xarray as xr

from davinci_monet.pipeline.runner import PipelineRunner


def test_gridded_analysis_pipeline_writes_and_uses_product_artifact(tmp_path) -> None:
    source = tmp_path / "cam.nc"
    ds = xr.Dataset(
        {
            "AOD": (("time", "lat", "lon"), np.ones((2, 1, 2))),
            "MASK": (("time", "lat", "lon"), np.ones((2, 1, 2))),
        },
        coords={
            "time": np.array(["2008-07-01T00:00", "2008-07-01T03:00"], dtype="datetime64[ns]"),
            "lat": [0.0],
            "lon": [0.0, 90.0],
        },
        attrs={"geometry": "grid"},
    )
    ds.to_netcdf(source)
    config = {
        "analysis": {"output_dir": str(tmp_path / "run")},
        "sources": {"cam": {"type": "generic", "files": str(source), "variables": {"AOD": {}, "MASK": {}}}},
        "analyses": {
            "daily_aod": {
                "type": "gridded_analysis",
                "source": "cam",
                "groupby": "day",
                "roles": {"analysis": "AOD", "mask": "MASK"},
                "fields": {"analyzed_aod": {"formula": 'mean(analysis, dim="time")'}},
            }
        },
    }
    result = PipelineRunner(show_progress=False).run_from_config(config)
    assert result.success
    analysis_nc = tmp_path / "run" / "products" / "daily_aod" / "analysis.nc"
    summary_json = tmp_path / "run" / "products" / "daily_aod" / "summary.json"
    assert analysis_nc.exists()
    assert summary_json.exists()
    summary = json.loads(summary_json.read_text())
    assert summary["fields"]["analyzed_aod"]["finite_count"] == 2
    assert result.context is not None
    assert result.context.sources["daily_aod"].config["artifact_path"] == str(analysis_nc)
```

- [ ] **Step 2: Run artifact tests and verify they fail**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_artifacts.py \
  davinci_monet/tests/unit/pipeline/test_gridded_artifact_stage.py -q
```

Expected: failure because artifact writer/stage integration does not exist.

- [ ] **Step 3: Implement artifacts and integrate in `AnalysesStage`**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/analysis/artifacts.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from davinci_monet.analysis.gridded_reductions import product_summary


@dataclass(frozen=True)
class ProductArtifactResult:
    product: str
    analysis_path: Path
    summary_path: Path


def _field_arrays(ds: xr.Dataset) -> dict[str, xr.DataArray]:
    return {name: ds[name] for name in ds.data_vars}


def write_product_artifacts(output_dir: str | Path, product: str, ds: xr.Dataset) -> ProductArtifactResult:
    root = Path(output_dir) / "products" / product
    root.mkdir(parents=True, exist_ok=True)
    analysis_path = root / "analysis.nc"
    summary_path = root / "summary.json"
    encoding: dict[str, dict[str, Any]] = {}
    for name, da in ds.data_vars.items():
        if np.issubdtype(da.dtype, np.floating):
            encoding[name] = {"dtype": "float32", "_FillValue": np.float32(np.nan)}
    ds.to_netcdf(analysis_path, engine="netcdf4", encoding=encoding)
    summary = {
        "product": product,
        "attrs": {str(k): str(v) for k, v in ds.attrs.items()},
        "groups": [str(v) for v in ds["group"].values] if "group" in ds.coords else [],
        "fields": product_summary(_field_arrays(ds)),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return ProductArtifactResult(product=product, analysis_path=analysis_path, summary_path=summary_path)


def load_product_dataset(path: str | Path) -> xr.Dataset:
    with xr.open_dataset(path) as ds:
        return ds.load()
```

Modify `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/analyses.py` inside the successful analysis block after `out_ds = analysis.analyze(in_ds, spec)`:

```python
artifact_config: dict[str, Any] = {}
if getattr(spec, "type", None) == "gridded_analysis":
    from davinci_monet.analysis.artifacts import load_product_dataset, write_product_artifacts

    artifact = write_product_artifacts(context.analysis_config().output_dir or ".", key, out_ds)
    out_ds = load_product_dataset(artifact.analysis_path)
    artifact_config = {
        "artifact_path": str(artifact.analysis_path),
        "summary_path": str(artifact.summary_path),
    }
    context.metadata.setdefault("product_artifacts", {})[key] = artifact_config
```

When constructing `SourceData`, merge `artifact_config` into `config`:

```python
config={**spec.model_dump(), **artifact_config},
```

- [ ] **Step 4: Run task and full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/analysis/test_artifacts.py \
  davinci_monet/tests/unit/pipeline/test_gridded_artifact_stage.py -q
"$PY" -m pytest davinci_monet/tests -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
cd "$DV"
git add davinci_monet/analysis/artifacts.py davinci_monet/pipeline/stages/analyses.py \
  davinci_monet/tests/unit/analysis/test_artifacts.py \
  davinci_monet/tests/unit/pipeline/test_gridded_artifact_stage.py
git commit -m "pipeline: persist gridded analysis artifacts"
```

---

### Task 6: Manifest Stage

**Files:**
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/manifest.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/factory.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/__init__.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/test_manifest_stage.py`

- [ ] **Step 1: Write failing manifest tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/test_manifest_stage.py`:

```python
from __future__ import annotations

import json

from davinci_monet.pipeline.stages import ManifestStage, PipelineContext, StageResult, StageStatus
from davinci_monet.pipeline.stages.factory import create_standard_pipeline


def test_manifest_stage_writes_run_manifest(tmp_path) -> None:
    ctx = PipelineContext(config={"analysis": {"output_dir": str(tmp_path)}})
    ctx.metadata["product_artifacts"] = {
        "daily_aod": {
            "artifact_path": str(tmp_path / "products" / "daily_aod" / "analysis.nc"),
            "summary_path": str(tmp_path / "products" / "daily_aod" / "summary.json"),
        }
    }
    ctx.results["plotting"] = StageResult(
        "plotting",
        StageStatus.COMPLETED,
        data={"plots_generated": [str(tmp_path / "plots" / "daily" / "aod.pdf")]},
    )
    result = ManifestStage().execute(ctx)
    assert result.status == StageStatus.COMPLETED
    manifest = tmp_path / "manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert data["status"] == "completed"
    assert "daily_aod" in data["products"]
    assert str(tmp_path / "plots" / "daily" / "aod.pdf") in data["plots"]


def test_manifest_is_last_standard_stage() -> None:
    names = [stage.name for stage in create_standard_pipeline()]
    assert names[-1] == "manifest"
```

- [ ] **Step 2: Run manifest tests and verify they fail**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/pipeline/test_manifest_stage.py -q
```

Expected: failure because `ManifestStage` does not exist.

- [ ] **Step 3: Implement manifest stage and factory registration**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/manifest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from davinci_monet.pipeline.stages.base import BaseStage, PipelineContext, StageResult, StageStatus


class ManifestStage(BaseStage):
    """Write the final self-contained run manifest."""

    def __init__(self) -> None:
        super().__init__("manifest")

    def execute(self, context: PipelineContext) -> StageResult:
        import time

        start = time.time()
        output_dir = Path(context.analysis_config().output_dir or ".")
        output_dir.mkdir(parents=True, exist_ok=True)
        plots: list[str] = []
        plotting = context.results.get("plotting")
        if plotting and isinstance(plotting.data, dict):
            plots = list(plotting.data.get("plots_generated", []))
        inspection = context.results.get("inspection")
        status = "completed"
        failed = [
            name for name, result in context.results.items() if result.status == StageStatus.FAILED
        ]
        if failed:
            status = "failed"
        manifest: dict[str, Any] = {
            "status": status,
            "failed_stages": failed,
            "products": context.metadata.get("product_artifacts", {}),
            "plots": plots,
            "inspection": inspection.data if inspection and isinstance(inspection.data, dict) else {},
            "stages": {name: result.status.name.lower() for name, result in context.results.items()},
        }
        path = output_dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return self._create_result(
            StageStatus.COMPLETED,
            data={"manifest": str(path)},
            duration=time.time() - start,
        )
```

Modify `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/factory.py`:

```python
from davinci_monet.pipeline.stages.manifest import ManifestStage
```

Append `ManifestStage()` after `SummaryStage()` in `create_standard_pipeline()` and `create_geometry_pipeline()`.

Modify `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/__init__.py`:

```python
from davinci_monet.pipeline.stages.manifest import ManifestStage
```

Add `"ManifestStage"` to `__all__`.

- [ ] **Step 4: Run task and full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/pipeline/test_manifest_stage.py -q
"$PY" -m pytest davinci_monet/tests -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
cd "$DV"
git add davinci_monet/pipeline/stages/manifest.py \
  davinci_monet/pipeline/stages/factory.py \
  davinci_monet/pipeline/stages/__init__.py \
  davinci_monet/tests/unit/pipeline/test_manifest_stage.py
git commit -m "pipeline: write run manifest"
```

---

### Task 7: Plot-Suite Expansion And AOD Preset

**Files:**
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/plots/suites.py`
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/plot_suites.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/factory.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/__init__.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/plots/test_plot_suites.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/test_plot_suite_stage.py`

- [ ] **Step 1: Write failing plot-suite tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/plots/test_plot_suites.py`:

```python
from __future__ import annotations

from davinci_monet.plots.suites import expand_plot_suite


def test_gridded_aod_suite_expands_absolute_and_difference_plots() -> None:
    plots = expand_plot_suite(
        "daily_aod",
        {
            "preset": "gridded_aod_diagnostics",
            "source": "daily_aod",
            "output_subdir": "plots/daily",
        },
        available_fields=[
            "observation_aod",
            "analyzed_aod",
            "first_guess_aod",
            "analysis_minus_observation_aod",
            "analysis_increment_aod",
            "nudge_fraction",
        ],
    )
    assert "daily_aod_analyzed_aod" in plots
    assert plots["daily_aod_analyzed_aod"]["type"] == "spatial"
    assert plots["daily_aod_analyzed_aod"]["style_preset"] == "geosit_aod"
    assert plots["daily_aod_analysis_increment_aod"]["cmap"] == "RdBu_r"
    assert plots["daily_aod_nudge_fraction"]["vmin"] == 0.0
    assert plots["daily_aod_nudge_fraction"]["vmax"] == 1.0
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/test_plot_suite_stage.py`:

```python
from __future__ import annotations

import numpy as np
import xarray as xr

from davinci_monet.pipeline.stages import PipelineContext, PlotSuiteStage, SourceData, StageStatus
from davinci_monet.core.protocols import DataGeometry


def test_plot_suite_stage_expands_into_context_plots(tmp_path) -> None:
    ds = xr.Dataset(
        {
            "analyzed_aod": (("group", "lat", "lon"), np.ones((1, 1, 2))),
            "nudge_fraction": (("group", "lat", "lon"), np.ones((1, 1, 2))),
        },
        coords={"group": ["2008-07-01"], "lat": [0.0], "lon": [0.0, 90.0]},
    )
    ctx = PipelineContext(
        config={
            "analysis": {"output_dir": str(tmp_path)},
            "plot_suites": {
                "daily": {
                    "preset": "gridded_aod_diagnostics",
                    "source": "daily_aod",
                    "output_subdir": "plots/daily",
                }
            },
        },
        sources={
            "daily_aod": SourceData(ds, "daily_aod", "gridded_analysis", DataGeometry.GRID)
        },
    )
    result = PlotSuiteStage().execute(ctx)
    assert result.status == StageStatus.COMPLETED
    assert "daily_analyzed_aod" in ctx.config["plots"]
    assert ctx.config["plots"]["daily_analyzed_aod"]["source"] == "daily_aod"
```

- [ ] **Step 2: Run plot-suite tests and verify they fail**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/plots/test_plot_suites.py \
  davinci_monet/tests/unit/pipeline/test_plot_suite_stage.py -q
```

Expected: failure because plot-suite code does not exist.

- [ ] **Step 3: Implement AOD suite expansion and stage**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/plots/suites.py`:

```python
from __future__ import annotations

from typing import Any


_AOD_TITLES = {
    "observation_aod": "Observation AOD",
    "analyzed_aod": "CAM Analyzed AOD",
    "first_guess_aod": "CAM First-Guess AOD",
    "analysis_minus_observation_aod": "Analysis Minus Observation AOD",
    "analysis_increment_aod": "Analysis Increment AOD",
    "nudge_fraction": "Nudge Fraction",
    "observation_fraction": "Observation Fraction",
    "analysis_minus_free_running_aod": "Analyzed Minus Free-Running AOD",
}


def _aod_plot_options(field: str) -> dict[str, Any]:
    if field.endswith("_aod") and "minus" not in field and "increment" not in field:
        return {"style_preset": "geosit_aod"}
    if "minus" in field or "increment" in field:
        return {"cmap": "RdBu_r", "robust": True}
    if "fraction" in field:
        return {"cmap": "gray_r", "vmin": 0.0, "vmax": 1.0}
    return {}


def expand_plot_suite(
    suite_name: str,
    suite: dict[str, Any],
    *,
    available_fields: list[str],
) -> dict[str, dict[str, Any]]:
    """Expand a named plot suite into concrete DAVINCI plot configs."""

    preset = suite["preset"]
    if preset != "gridded_aod_diagnostics":
        raise ValueError(f"unknown plot suite preset: {preset}")
    source = suite["source"]
    plots: dict[str, dict[str, Any]] = {}
    for field, title in _AOD_TITLES.items():
        if field not in available_fields:
            continue
        plots[f"{suite_name}_{field}"] = {
            "type": "spatial",
            "source": source,
            "variable": field,
            "title": title,
            "domain_type": ["all"],
            **_aod_plot_options(field),
        }
    return plots
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/plot_suites.py`:

```python
from __future__ import annotations

from davinci_monet.pipeline.stages.base import BaseStage, PipelineContext, StageResult, StageStatus


class PlotSuiteStage(BaseStage):
    """Expand configured plot suites into concrete plot specs."""

    def __init__(self) -> None:
        super().__init__("plot_suites")

    def validate(self, context: PipelineContext) -> bool:
        return bool(context.config_dict().get("plot_suites"))

    def execute(self, context: PipelineContext) -> StageResult:
        import time

        from davinci_monet.plots.suites import expand_plot_suite

        start = time.time()
        cfg = context.config_dict()
        plots = dict(cfg.get("plots", {}))
        generated: list[str] = []
        for suite_name, suite in cfg.get("plot_suites", {}).items():
            source = suite["source"]
            source_obj = context.sources[source]
            ds = source_obj.data if hasattr(source_obj, "data") else source_obj
            expanded = expand_plot_suite(
                suite_name,
                suite,
                available_fields=list(ds.data_vars),
            )
            plots.update(expanded)
            generated.extend(expanded)
        cfg["plots"] = plots
        context.config = cfg
        return self._create_result(
            StageStatus.COMPLETED,
            data={"expanded_plots": generated},
            duration=time.time() - start,
        )
```

Modify factory and stage exports:

```python
from davinci_monet.pipeline.stages.plot_suites import PlotSuiteStage
```

Insert `PlotSuiteStage()` after `AnalysesStage()` and before `PairingStage()`.

- [ ] **Step 4: Run task and full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/plots/test_plot_suites.py \
  davinci_monet/tests/unit/pipeline/test_plot_suite_stage.py -q
"$PY" -m pytest davinci_monet/tests -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
cd "$DV"
git add davinci_monet/plots/suites.py davinci_monet/pipeline/stages/plot_suites.py \
  davinci_monet/pipeline/stages/factory.py davinci_monet/pipeline/stages/__init__.py \
  davinci_monet/tests/unit/plots/test_plot_suites.py \
  davinci_monet/tests/unit/pipeline/test_plot_suite_stage.py
git commit -m "plots: add gridded AOD plot suite"
```

---

### Task 8: Inspection Engine, Stage, And CLI

**Files:**
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/core.py`
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/presets.py`
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/__init__.py`
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/inspection.py`
- Create: `/glade/work/fillmore/DAVINCI/davinci_monet/cli/commands/inspect.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/factory.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/__init__.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/cli/app.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/cli/commands/__init__.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/inspection/test_inspection_core.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/test_inspection_stage.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/cli/test_inspect_command.py`

- [ ] **Step 1: Write failing inspection tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/inspection/test_inspection_core.py`:

```python
from __future__ import annotations

import json

from davinci_monet.inspection.core import inspect_run_directory


def test_inspect_run_directory_writes_json_and_markdown(tmp_path) -> None:
    plots = tmp_path / "plots" / "daily"
    plots.mkdir(parents=True)
    (plots / "cam-analyzed-aod.pdf").write_bytes(b"%PDF-1.4\n")
    result = inspect_run_directory(tmp_path, presets=["gridded_aod_diagnostics"])
    assert result.passed is True
    assert (tmp_path / "inspection" / "inspection.json").exists()
    assert (tmp_path / "inspection" / "inspection.md").exists()
    data = json.loads((tmp_path / "inspection" / "inspection.json").read_text())
    assert data["passed"] is True
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/pipeline/test_inspection_stage.py`:

```python
from __future__ import annotations

from davinci_monet.pipeline.stages import InspectionStage, PipelineContext, StageStatus


def test_inspection_stage_skips_when_disabled(tmp_path) -> None:
    ctx = PipelineContext(config={"analysis": {"output_dir": str(tmp_path)}})
    result = InspectionStage().execute(ctx)
    assert result.status == StageStatus.SKIPPED


def test_required_inspection_failure_fails_stage(tmp_path) -> None:
    ctx = PipelineContext(
        config={
            "analysis": {"output_dir": str(tmp_path)},
            "inspection": {"enabled": True, "required": True, "presets": ["gridded_aod_diagnostics"]},
        }
    )
    result = InspectionStage().execute(ctx)
    assert result.status == StageStatus.FAILED
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/cli/test_inspect_command.py`:

```python
from __future__ import annotations

from typer.testing import CliRunner

from davinci_monet.cli.app import app


def test_inspect_command_exits_nonzero_for_missing_pdfs(tmp_path) -> None:
    result = CliRunner().invoke(app, ["inspect", str(tmp_path), "--preset", "gridded_aod_diagnostics"])
    assert result.exit_code == 1
    assert "Inspection failed" in result.output
```

- [ ] **Step 2: Run inspection tests and verify they fail**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/inspection/test_inspection_core.py \
  davinci_monet/tests/unit/pipeline/test_inspection_stage.py \
  davinci_monet/tests/unit/cli/test_inspect_command.py -q
```

Expected: failure because inspection package/stage/CLI do not exist.

- [ ] **Step 3: Implement deterministic inspection core first**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/core.py` with a deterministic file-based inspection. This establishes stage/CLI contracts before adding AI vision:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InspectionResult:
    passed: bool
    checks: list[dict[str, str | bool]]
    json_path: Path
    markdown_path: Path


def inspect_run_directory(run_dir: str | Path, *, presets: list[str]) -> InspectionResult:
    root = Path(run_dir)
    checks: list[dict[str, str | bool]] = []
    pdfs = sorted((root / "plots").rglob("*.pdf"))
    checks.append(
        {
            "name": "final_pdf_products_exist",
            "passed": bool(pdfs),
            "detail": f"{len(pdfs)} PDF plot(s) found",
        }
    )
    checks.append(
        {
            "name": "known_preset_selected",
            "passed": all(p in {"gridded_aod_diagnostics", "sarb_band_aerosol_optics"} for p in presets),
            "detail": ",".join(presets),
        }
    )
    passed = all(bool(check["passed"]) for check in checks)
    out_dir = root / "inspection"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "inspection.json"
    markdown_path = out_dir / "inspection.md"
    json_path.write_text(json.dumps({"passed": passed, "checks": checks}, indent=2) + "\n")
    lines = ["# DAVINCI Inspection", "", f"Passed: {passed}", ""]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: {check['name']} - {check['detail']}")
    markdown_path.write_text("\n".join(lines) + "\n")
    return InspectionResult(passed=passed, checks=checks, json_path=json_path, markdown_path=markdown_path)
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/presets.py`:

```python
BUILTIN_INSPECTION_PRESETS = {"gridded_aod_diagnostics", "sarb_band_aerosol_optics"}
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/__init__.py`:

```python
from davinci_monet.inspection.core import InspectionResult, inspect_run_directory

__all__ = ["InspectionResult", "inspect_run_directory"]
```

- [ ] **Step 4: Implement stage and CLI**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/pipeline/stages/inspection.py`:

```python
from __future__ import annotations

from davinci_monet.pipeline.stages.base import BaseStage, PipelineContext, StageResult, StageStatus


class InspectionStage(BaseStage):
    """Optional visual-inspection gate over final run directory products."""

    def __init__(self) -> None:
        super().__init__("inspection")

    def execute(self, context: PipelineContext) -> StageResult:
        import time

        from davinci_monet.config.schema import InspectionConfig
        from davinci_monet.inspection import inspect_run_directory

        start = time.time()
        cfg = context._typed_config().inspection if context._typed_config() else None
        if cfg is None:
            raw = context.config_dict().get("inspection")
            cfg = InspectionConfig(**raw) if raw else InspectionConfig()
        if not cfg.enabled:
            return self._create_result(
                StageStatus.SKIPPED,
                data={"skipped": "inspection disabled"},
                duration=time.time() - start,
            )
        result = inspect_run_directory(
            context.analysis_config().output_dir or ".",
            presets=cfg.presets,
        )
        status = StageStatus.COMPLETED if result.passed else StageStatus.FAILED if cfg.required else StageStatus.COMPLETED
        return self._create_result(
            status,
            data={
                "passed": result.passed,
                "inspection_json": str(result.json_path),
                "inspection_markdown": str(result.markdown_path),
            },
            error=None if result.passed or not cfg.required else "required inspection failed",
            duration=time.time() - start,
        )
```

Create `/glade/work/fillmore/DAVINCI/davinci_monet/cli/commands/inspect.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import List

import typer

from davinci_monet.cli.app import ERROR_COLOR, SUCCESS_COLOR
from davinci_monet.inspection import inspect_run_directory


def inspect_command(run_dir: Path, presets: List[str]) -> None:
    result = inspect_run_directory(run_dir, presets=presets)
    if result.passed:
        typer.secho(f"Inspection passed: {result.markdown_path}", fg=SUCCESS_COLOR)
        return
    typer.secho(f"Inspection failed: {result.markdown_path}", fg=ERROR_COLOR)
    raise typer.Exit(1)
```

Modify `/glade/work/fillmore/DAVINCI/davinci_monet/cli/app.py`:

```python
@app.command()
def inspect(
    run_dir: Path = typer.Argument(..., help="DAVINCI run directory to inspect."),
    preset: list[str] = typer.Option(
        ["gridded_aod_diagnostics"],
        "--preset",
        help="Inspection preset to apply; may be repeated.",
    ),
) -> None:
    """Inspect a completed DAVINCI run directory."""
    from davinci_monet.cli.commands.inspect import inspect_command

    inspect_command(run_dir, preset)
```

Add `InspectionStage` to factory before `ManifestStage`, and to `stages/__init__.py`.

- [ ] **Step 5: Run task and full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/inspection/test_inspection_core.py \
  davinci_monet/tests/unit/pipeline/test_inspection_stage.py \
  davinci_monet/tests/unit/cli/test_inspect_command.py -q
"$PY" -m pytest davinci_monet/tests -q
```

Expected: both commands pass.

- [ ] **Step 6: Commit**

```bash
cd "$DV"
git add davinci_monet/inspection davinci_monet/pipeline/stages/inspection.py \
  davinci_monet/pipeline/stages/factory.py davinci_monet/pipeline/stages/__init__.py \
  davinci_monet/cli/app.py davinci_monet/cli/commands/inspect.py \
  davinci_monet/cli/commands/__init__.py \
  davinci_monet/tests/unit/inspection/test_inspection_core.py \
  davinci_monet/tests/unit/pipeline/test_inspection_stage.py \
  davinci_monet/tests/unit/cli/test_inspect_command.py
git commit -m "inspection: add run-directory inspection gate"
```

---

### Task 9: CERES AOD DAVINCI Configs And Config Tests

**Files:**
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/cam-aod-analysis-july-2008.yaml`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/modis-viirs-aod-monthly-analysis-july-2008.yaml`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/tests/test_davinci_analysis_configs.py`

- [ ] **Step 1: Write failing CERES config tests**

Create `/glade/work/fillmore/CERES-SARB-CAM7/tests/test_davinci_analysis_configs.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "analyses" / "davinci"


@pytest.mark.parametrize(
    "name",
    [
        "cam-aod-analysis-july-2008.yaml",
        "modis-viirs-aod-monthly-analysis-july-2008.yaml",
    ],
)
def test_davinci_aod_configs_are_descriptive_and_parse(name: str) -> None:
    path = CONFIGS / name
    assert path.exists()
    cfg = yaml.safe_load(path.read_text())
    assert "SP1" not in name and "SP2" not in name and "SP3" not in name
    assert cfg["analysis"]["name"] == name.removesuffix(".yaml")
    assert "/runs/" in cfg["analysis"]["output_dir"]
    assert "analyses" in cfg
    assert "plot_suites" in cfg
    assert cfg["inspection"]["enabled"] is True


def test_cam_aod_config_uses_analysis_terms() -> None:
    cfg = yaml.safe_load((CONFIGS / "cam-aod-analysis-july-2008.yaml").read_text())
    fields = cfg["analyses"]["daily_aod"]["fields"]
    assert "analyzed_aod" in fields
    assert "first_guess_aod" in fields
    assert "analysis_increment_aod" in fields
    rendered = yaml.safe_dump(cfg)
    assert "post" not in rendered.lower()
    assert "pre" not in rendered.lower()
```

- [ ] **Step 2: Run CERES config tests and verify they fail**

```bash
cd "$CERES"
PYTHONPATH="$CERES" "$PY" -m pytest tests/test_davinci_analysis_configs.py -q
```

Expected: failure because configs do not exist.

- [ ] **Step 3: Add CAM AOD config**

Create `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/cam-aod-analysis-july-2008.yaml`:

```yaml
analysis:
  name: cam-aod-analysis-july-2008
  output_dir: /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/cam-aod-analysis-july-2008
  domain: global

sources:
  cam:
    type: cesm_fv
    files: /glade/derecho/scratch/fillmore/sp3_verify10_aodnudged_partial_disconnect_260629_091812/*.cam.h0*.nc
    variables:
      AODNDG_OBS: {}
      AODNDG_MODEL_PRE:
        rename: first_guess_source_aod
      AODNDG_MODEL_POST:
        rename: analysis_source_aod
      AODNDG_MASK: {}

analyses:
  daily_aod:
    type: gridded_analysis
    source: cam
    groupby: day
    roles:
      observation: AODNDG_OBS
      first_guess: first_guess_source_aod
      analysis: analysis_source_aod
      mask: AODNDG_MASK
    fields:
      observation_aod:
        formula: active_mean(observation, mask > 0.5, dim="time")
        display_name: Observation AOD
        style_preset: geosit_aod
      first_guess_aod:
        formula: mean(first_guess, dim="time")
        display_name: CAM First-Guess AOD
        style_preset: geosit_aod
      analyzed_aod:
        formula: mean(analysis, dim="time")
        display_name: CAM Analyzed AOD
        style_preset: geosit_aod
      analysis_minus_observation_aod:
        formula: active_mean(analysis - observation, mask > 0.5, dim="time")
        display_name: Analysis Minus Observation AOD
      analysis_increment_aod:
        formula: active_mean(analysis - first_guess, mask > 0.5, dim="time")
        display_name: Analysis Increment AOD
      nudge_fraction:
        formula: mean(mask, dim="time")
        display_name: Nudge Fraction

plot_suites:
  daily:
    preset: gridded_aod_diagnostics
    source: daily_aod
    group: daily
    output_subdir: plots/daily

inspection:
  enabled: true
  required: true
  presets:
    - gridded_aod_diagnostics
```

If the preserved five-day CAM h0 files are unavailable or have zero records, keep this config as the target schema and rely on the SARB-band config in Task 11 for the final five-day regenerated products.

- [ ] **Step 4: Add MODIS/VIIRS monthly config**

Create `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/modis-viirs-aod-monthly-analysis-july-2008.yaml`:

```yaml
analysis:
  name: modis-viirs-aod-monthly-analysis-july-2008
  output_dir: /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/modis-viirs-aod-monthly-analysis-july-2008
  domain: global

sources:
  observations:
    type: generic
    files: /glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/MODIS_VIIRS_AOD_3hr_f09.200807*.nc
    variables:
      aod_weighted_mean: {}
      aod_count: {}

analyses:
  monthly_aod:
    type: gridded_analysis
    source: observations
    groupby: month
    roles:
      observation: aod_weighted_mean
      count: aod_count
    fields:
      observation_aod:
        formula: weighted_mean(observation, count, dim="time")
        display_name: Observation AOD
        style_preset: geosit_aod
      observation_count:
        formula: sum(count, dim="time")
        display_name: Observation Count
      observation_fraction:
        formula: fraction(count > 0, dim="time")
        display_name: Observation Fraction

plot_suites:
  monthly:
    preset: gridded_aod_diagnostics
    source: monthly_aod
    group: monthly
    output_subdir: plots/monthly

inspection:
  enabled: true
  required: true
  presets:
    - gridded_aod_diagnostics
```

- [ ] **Step 5: Run CERES and DAVINCI validation**

```bash
cd "$CERES"
PYTHONPATH="$CERES" "$PY" -m pytest tests/test_davinci_analysis_configs.py -q
PYTHONPATH="$CERES" "$PY" -m pytest tests sp1_aod_pipeline/tests sp3_tests -q
cd "$DV"
"$PY" -m pytest davinci_monet/tests -q
```

Expected: all commands pass.

- [ ] **Step 6: Commit CERES configs**

```bash
cd "$CERES"
git add analyses/davinci/cam-aod-analysis-july-2008.yaml \
  analyses/davinci/modis-viirs-aod-monthly-analysis-july-2008.yaml \
  tests/test_davinci_analysis_configs.py
git commit -m "Add DAVINCI AOD analysis configs"
```

---

### Task 10: End-To-End Synthetic AOD Run

**Files:**
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/integration/test_gridded_aod_product_pipeline.py`

- [ ] **Step 1: Write failing end-to-end integration test**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/integration/test_gridded_aod_product_pipeline.py`:

```python
from __future__ import annotations

import json

import numpy as np
import xarray as xr

from davinci_monet.pipeline.runner import PipelineRunner


def test_gridded_aod_product_pipeline_creates_artifacts_plots_inspection_and_manifest(tmp_path) -> None:
    source = tmp_path / "cam.nc"
    ds = xr.Dataset(
        {
            "OBS": (("time", "lat", "lon"), np.ones((2, 2, 2)) * 0.2),
            "ANALYSIS": (("time", "lat", "lon"), np.ones((2, 2, 2)) * 0.3),
            "MASK": (("time", "lat", "lon"), np.ones((2, 2, 2))),
        },
        coords={
            "time": np.array(["2008-07-01T00:00", "2008-07-01T03:00"], dtype="datetime64[ns]"),
            "lat": [-1.0, 1.0],
            "lon": [0.0, 90.0],
        },
        attrs={"geometry": "grid"},
    )
    ds.to_netcdf(source)
    config = {
        "analysis": {"output_dir": str(tmp_path / "run"), "domain": "global"},
        "sources": {
            "cam": {
                "type": "generic",
                "files": str(source),
                "variables": {"OBS": {}, "ANALYSIS": {}, "MASK": {}},
            }
        },
        "analyses": {
            "daily_aod": {
                "type": "gridded_analysis",
                "source": "cam",
                "groupby": "day",
                "roles": {"observation": "OBS", "analysis": "ANALYSIS", "mask": "MASK"},
                "fields": {
                    "observation_aod": {"formula": 'mean(observation, dim="time")'},
                    "analyzed_aod": {"formula": 'mean(analysis, dim="time")'},
                    "analysis_minus_observation_aod": {
                        "formula": 'mean(analysis - observation, dim="time")'
                    },
                    "nudge_fraction": {"formula": 'mean(mask, dim="time")'},
                },
            }
        },
        "plot_suites": {
            "daily": {
                "preset": "gridded_aod_diagnostics",
                "source": "daily_aod",
                "output_subdir": "plots/daily",
            }
        },
        "inspection": {
            "enabled": True,
            "required": True,
            "presets": ["gridded_aod_diagnostics"],
        },
    }
    result = PipelineRunner(show_progress=False).run_from_config(config)
    assert result.success
    run = tmp_path / "run"
    assert (run / "products" / "daily_aod" / "analysis.nc").exists()
    assert (run / "products" / "daily_aod" / "summary.json").exists()
    assert (run / "manifest.json").exists()
    assert (run / "inspection" / "inspection.json").exists()
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["status"] == "completed"
    assert any(path.endswith(".pdf") for path in manifest["plots"])
```

- [ ] **Step 2: Run integration test**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/integration/test_gridded_aod_product_pipeline.py -q
```

Expected: if previous tasks are correct, this passes. If it fails because single-source plot output paths still go to the run root instead of `plots/daily`, update `PlotSuiteStage` and `PlottingStage` to honor `output_subdir` before continuing.

- [ ] **Step 3: Ensure PDFs are final outputs and preview PNGs stay inspection-local**

Add assertions to the same test:

```python
    product_pngs = [p for p in run.rglob("*.png") if "inspection/previews" not in str(p)]
    assert product_pngs == []
```

If current plotting always emits PNGs, update `PlottingStage` with a config-level `formats` option or suite-level final format so plot suites can request PDF-only final products.

- [ ] **Step 4: Run full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests -q
cd "$CERES"
PYTHONPATH="$CERES" "$PY" -m pytest tests sp1_aod_pipeline/tests sp3_tests -q
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
cd "$DV"
git add davinci_monet/tests/integration/test_gridded_aod_product_pipeline.py \
  davinci_monet/pipeline/stages/plot.py \
  davinci_monet/pipeline/stages/plot_suites.py
git commit -m "pipeline: verify gridded AOD product workflow"
```

---

### Task 11: SARB-Band Aerosol Optics Suite And CERES Config

**Files:**
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/plots/suites.py`
- Modify: `/glade/work/fillmore/DAVINCI/davinci_monet/inspection/presets.py`
- Test: `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/plots/test_sarb_optics_suite.py`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/sarb-band-aerosol-optics-july-2008.yaml`
- Modify: `/glade/work/fillmore/CERES-SARB-CAM7/tests/test_davinci_analysis_configs.py`

- [ ] **Step 1: Write failing SARB suite tests**

Create `/glade/work/fillmore/DAVINCI/davinci_monet/tests/unit/plots/test_sarb_optics_suite.py`:

```python
from __future__ import annotations

from davinci_monet.plots.suites import expand_plot_suite


def test_sarb_band_optics_suite_expands_expected_views() -> None:
    plots = expand_plot_suite(
        "optics",
        {"preset": "sarb_band_aerosol_optics", "source": "sarb_optics"},
        available_fields=[
            "visible_column_aod",
            "visible_single_scatter_albedo",
            "visible_asymmetry",
            "sw_spectral_profile",
            "dust_vertical_extinction",
            "lw_window_scattering",
            "lw_window_extinction",
        ],
    )
    assert "optics_visible_column_aod" in plots
    assert "optics_lw_window_scattering" in plots
    assert plots["optics_visible_column_aod"]["style_preset"] == "geosit_aod"
    assert plots["optics_lw_window_scattering"]["type"] == "spatial"
```

- [ ] **Step 2: Run SARB suite tests and verify they fail**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/plots/test_sarb_optics_suite.py -q
```

Expected: failure because the preset is not supported.

- [ ] **Step 3: Add SARB suite expansion**

Extend `/glade/work/fillmore/DAVINCI/davinci_monet/plots/suites.py`:

```python
_SARB_TITLES = {
    "visible_column_aod": "Visible Column AOD",
    "visible_single_scatter_albedo": "Visible Single-Scatter Albedo",
    "visible_asymmetry": "Visible Asymmetry",
    "sw_spectral_profile": "SW Spectral Profile",
    "dust_vertical_extinction": "Dust Vertical Extinction",
    "lw_window_scattering": "LW Window Scattering",
    "lw_window_extinction": "LW Window Extinction",
}


def _expand_sarb_suite(suite_name: str, suite: dict[str, Any], available_fields: list[str]) -> dict[str, dict[str, Any]]:
    source = suite["source"]
    plots: dict[str, dict[str, Any]] = {}
    for field, title in _SARB_TITLES.items():
        if field not in available_fields:
            continue
        plot_type = "vertical_profile" if "vertical" in field else "timeseries" if "spectral" in field else "spatial"
        opts: dict[str, Any] = {"type": plot_type, "source": source, "variable": field, "title": title}
        if field in {"visible_column_aod", "lw_window_extinction"}:
            opts["style_preset"] = "geosit_aod"
        plots[f"{suite_name}_{field}"] = opts
    return plots
```

Then dispatch in `expand_plot_suite`:

```python
if preset == "sarb_band_aerosol_optics":
    return _expand_sarb_suite(suite_name, suite, available_fields)
```

- [ ] **Step 4: Add CERES SARB config**

Create `/glade/work/fillmore/CERES-SARB-CAM7/analyses/davinci/sarb-band-aerosol-optics-july-2008.yaml`:

```yaml
analysis:
  name: sarb-band-aerosol-optics-july-2008
  output_dir: /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/sarb-band-aerosol-optics-july-2008
  domain: global

sources:
  sarb_optics_files:
    type: generic
    files: /glade/derecho/scratch/fillmore/sp3_verify10_aodnudged_partial_disconnect_260629_091812/AER_MAM4_*.200807*.nc
    variables:
      Extinction_Column_Optical_Depth: {}
      Extinction_Layer_Optical_Depth: {}
      Scattering_Layer_Optical_Depth: {}
      Layer_Asymmetry_Parameter: {}

analyses:
  sarb_optics:
    type: gridded_analysis
    source: sarb_optics_files
    groupby: all
    roles:
      column_extinction: Extinction_Column_Optical_Depth
      layer_extinction: Extinction_Layer_Optical_Depth
      layer_scattering: Scattering_Layer_Optical_Depth
      layer_asymmetry: Layer_Asymmetry_Parameter
    fields:
      visible_column_aod:
        formula: mean(column_extinction, dim="time")
        display_name: Visible Column AOD
        style_preset: geosit_aod
      lw_window_scattering:
        formula: sum(mean(layer_scattering, dim="time"), dim="lev")
        display_name: LW Window Scattering
      lw_window_extinction:
        formula: mean(column_extinction, dim="time")
        display_name: LW Window Extinction
        style_preset: geosit_aod

plot_suites:
  optics:
    preset: sarb_band_aerosol_optics
    source: sarb_optics
    output_subdir: plots/optics

inspection:
  enabled: true
  required: true
  presets:
    - sarb_band_aerosol_optics
```

This first config captures the suite contract. If the generic reader cannot combine per-band files without additional band-coordinate work, add a follow-up commit in DAVINCI to create a `sarb_band_optics` source reader or a `band_from_filename` option, covered by synthetic tests before using real files.

- [ ] **Step 5: Extend CERES config tests**

Append to `/glade/work/fillmore/CERES-SARB-CAM7/tests/test_davinci_analysis_configs.py`:

```python
def test_sarb_optics_config_uses_descriptive_names() -> None:
    path = CONFIGS / "sarb-band-aerosol-optics-july-2008.yaml"
    assert path.exists()
    cfg = yaml.safe_load(path.read_text())
    assert cfg["analysis"]["name"] == "sarb-band-aerosol-optics-july-2008"
    rendered = yaml.safe_dump(cfg)
    assert "SP3" not in rendered
    assert cfg["plot_suites"]["optics"]["preset"] == "sarb_band_aerosol_optics"
```

- [ ] **Step 6: Run full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests/unit/plots/test_sarb_optics_suite.py -q
"$PY" -m pytest davinci_monet/tests -q
cd "$CERES"
PYTHONPATH="$CERES" "$PY" -m pytest tests/test_davinci_analysis_configs.py -q
PYTHONPATH="$CERES" "$PY" -m pytest tests sp1_aod_pipeline/tests sp3_tests -q
```

Expected: all commands pass.

- [ ] **Step 7: Commit DAVINCI and CERES changes separately**

```bash
cd "$DV"
git add davinci_monet/plots/suites.py davinci_monet/inspection/presets.py \
  davinci_monet/tests/unit/plots/test_sarb_optics_suite.py
git commit -m "plots: add SARB aerosol optics suite"
cd "$CERES"
git add analyses/davinci/sarb-band-aerosol-optics-july-2008.yaml \
  tests/test_davinci_analysis_configs.py
git commit -m "Add DAVINCI SARB aerosol optics config"
```

---

### Task 12: Real Data Smoke Runs

**Files:**
- Modify: `/glade/work/fillmore/CERES-SARB-CAM7/RUN.md`

- [ ] **Step 1: Run monthly MODIS/VIIRS AOD analysis**

```bash
cd "$CERES"
davinci-monet run analyses/davinci/modis-viirs-aod-monthly-analysis-july-2008.yaml
davinci-monet inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/modis-viirs-aod-monthly-analysis-july-2008 \
  --preset gridded_aod_diagnostics
```

Expected: run directory contains `products/monthly_aod/analysis.nc`, `summary.json`, `manifest.json`, final PDFs, and passing inspection.

- [ ] **Step 2: Run CAM AOD analysis if CAM h0 records are usable**

```bash
cd "$CERES"
davinci-monet run analyses/davinci/cam-aod-analysis-july-2008.yaml
davinci-monet inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/cam-aod-analysis-july-2008 \
  --preset gridded_aod_diagnostics
```

Expected: pass when source files contain nonzero AODNDG time records. If the preserved disconnected CAM h0i has zero records, record that limitation and rely on the SARB-band five-day source for final regeneration.

- [ ] **Step 3: Run SARB-band optics analysis**

```bash
cd "$CERES"
davinci-monet run analyses/davinci/sarb-band-aerosol-optics-july-2008.yaml
davinci-monet inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/sarb-band-aerosol-optics-july-2008 \
  --preset sarb_band_aerosol_optics
```

Expected: run directory contains product NetCDF, summary JSON, manifest, final PDFs, and passing inspection. If per-band file ingestion needs a dedicated reader, stop and create a tested DAVINCI reader task before continuing.

- [ ] **Step 4: Compare summaries and plot inventory to legacy outputs**

Run:

```bash
cd "$CERES"
find /glade/work/fillmore/Data/CERES-SARB-CAM7/runs -path '*products*summary.json' -print
find /glade/work/fillmore/Data/CERES-SARB-CAM7/runs -path '*.pdf' -print
find /glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify5_aodnudged -name '*.pdf' -print
```

Expected: new run PDFs cover the legacy five-day VP products and expanded AOD diagnostics listed in `RUN.md`.

- [ ] **Step 5: Update RUN.md**

Add a short section to `/glade/work/fillmore/CERES-SARB-CAM7/RUN.md`:

~~~~markdown
## DAVINCI Analysis Run Directories

The full DAVINCI migration writes deterministic run directories under
`/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/`.

Run commands:

```bash
davinci-monet run analyses/davinci/modis-viirs-aod-monthly-analysis-july-2008.yaml
davinci-monet run analyses/davinci/cam-aod-analysis-july-2008.yaml
davinci-monet run analyses/davinci/sarb-band-aerosol-optics-july-2008.yaml
```

The final five-day regenerated deliverable is
`/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/sarb-band-aerosol-optics-july-2008/`.
Final plots are PDFs; inspection previews are under `inspection/previews/`.
~~~~

- [ ] **Step 6: Run full suites and commit docs**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests -q
cd "$CERES"
PYTHONPATH="$CERES" "$PY" -m pytest tests sp1_aod_pipeline/tests sp3_tests -q
git add RUN.md
git commit -m "Document DAVINCI analysis run directories"
```

Expected: both test suites pass and RUN.md records exact run locations.

---

### Task 13: Final Five-Day Regeneration Gate

**Files:**
- Modify: `/glade/work/fillmore/CERES-SARB-CAM7/docs/HANDOFF.md`

- [ ] **Step 1: Remove stale non-inspection PNGs from new run directories**

```bash
find /glade/work/fillmore/Data/CERES-SARB-CAM7/runs \
  -type f -name '*.png' ! -path '*/inspection/previews/*' -print -delete
```

Expected: no final plot PNGs remain outside `inspection/previews`.

- [ ] **Step 2: Verify required final artifacts**

```bash
RUN=/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/sarb-band-aerosol-optics-july-2008
test -f "$RUN/manifest.json"
test -f "$RUN/inspection/inspection.json"
find "$RUN/products" -name analysis.nc -print
find "$RUN/products" -name summary.json -print
find "$RUN/plots" -name '*.pdf' -print
find "$RUN" -name '*.png' ! -path '*/inspection/previews/*' -print | wc -l
```

Expected: manifest and inspection files exist; product NetCDF and summary JSON exist; final PDFs exist; PNG count outside inspection previews is `0`.

- [ ] **Step 3: Run final full suites**

```bash
cd "$DV"
"$PY" -m pytest davinci_monet/tests -q
cd "$CERES"
PYTHONPATH="$CERES" "$PY" -m pytest tests sp1_aod_pipeline/tests sp3_tests -q
```

Expected: both suites pass.

- [ ] **Step 4: Update handoff with final regenerated deliverable**

Append to `/glade/work/fillmore/CERES-SARB-CAM7/docs/HANDOFF.md`:

```markdown
- DAVINCI five-day regeneration complete: the new run directory
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/sarb-band-aerosol-optics-july-2008/`
  contains product NetCDFs, summary JSON, `manifest.json`, final PDF plots, inspection previews
  under `inspection/previews/`, and passing `inspection/inspection.json`. Full DAVINCI and
  CERES-SARB-CAM7 test suites passed after regeneration.
```

- [ ] **Step 5: Commit final CERES docs**

```bash
cd "$CERES"
git add docs/HANDOFF.md
git commit -m "Document DAVINCI five-day regeneration"
```

---

## Self-Review Checklist

Spec coverage:

- YAML interface and role/formula model -> Tasks 1, 2, 4, 9, 11.
- Grouped reductions -> Task 3.
- Persisted NetCDF, summary JSON, manifest -> Tasks 5, 6.
- AOD plot suite -> Task 7.
- Visual inspection stage and CLI -> Task 8.
- CERES configs under `analyses/davinci/` -> Tasks 9, 11.
- SARB-band optics migration -> Task 11.
- Full synthetic coverage and full-suite gate after each task -> every task verification step.
- Final five-day regeneration -> Tasks 12 and 13.

No task is complete without tests and full applicable suite verification. The final accepted deliverable is the regenerated five-day July 2008 run directory, not the existence of code alone.
