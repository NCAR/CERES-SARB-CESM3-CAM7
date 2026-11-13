# CAM AOD Monthly Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full-month July 2008 CAM7 AOD nudging DAVINCI analysis while preserving the accepted five-day analysis.

**Architecture:** Keep the existing five-day YAML and run directory untouched. Add a separate full-month YAML that reuses the same CAM AOD roles and formulas, with daily July products and a monthly aggregate in a new deterministic run directory. CERES remains responsible only for YAML, docs, and config tests; DAVINCI remains the executable analysis engine.

**Tech Stack:** DAVINCI YAML configs, `davinci_monet.config.schema.MonetConfig`, pytest, xarray/netCDF source files from the completed CAM7 July 2008 nudged run.

---

### Task 1: Pin The Full-Month Config Contract

**Files:**
- Modify: `tests/test_davinci_analysis_configs.py`
- Create: `analyses/davinci/cam-aod-monthly-analysis-july-2008.yaml`

- [x] **Step 1: Write the failing config tests**

Add the new config name to the shared AOD config list and add a dedicated test requiring:

```python
def test_cam_aod_monthly_config_preserves_five_day_record() -> None:
    monthly = yaml.safe_load(
        (CONFIGS / "cam-aod-monthly-analysis-july-2008.yaml").read_text()
    )
    five_day = yaml.safe_load((CONFIGS / "cam-aod-analysis-july-2008.yaml").read_text())

    assert five_day["analysis"]["end_time"] == "2008-07-05T23:59:59"
    assert monthly["analysis"]["start_time"] == "2008-07-01T00:00:00"
    assert monthly["analysis"]["end_time"] == "2008-07-31T23:59:59"
    assert monthly["analysis"]["output_dir"] == (
        f"{DATA_ROOT}/runs/cam-aod-monthly-analysis-july-2008"
    )
    assert set(monthly["analyses"]) == {"daily_aod", "monthly_aod"}
    assert set(monthly["plot_suites"]) == {"daily_aod", "monthly_aod"}
    assert monthly["analyses"]["monthly_aod"]["groupby"] == "all"
    assert "five_day_aod" not in monthly["analyses"]
```

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```bash
PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7 \
  /glade/work/fillmore/miniforge3/envs/davinci/bin/python -m pytest \
  tests/test_davinci_analysis_configs.py::test_cam_aod_monthly_config_preserves_five_day_record -q
```

Expected: failure because `cam-aod-monthly-analysis-july-2008.yaml` does not exist yet.

- [x] **Step 3: Add the monthly YAML**

Create `analyses/davinci/cam-aod-monthly-analysis-july-2008.yaml` from the existing five-day CAM AOD config, changing only the run window, output directory, aggregate analysis name, aggregate long names, and aggregate plot subdirectory. Use `end_time: "2008-07-31T23:59:59"` and `monthly_aod.groupby: all` so DAVINCI does not create an August group from the CAM boundary record at `2008-08-01T00:00:00`.

- [x] **Step 4: Run the focused config tests**

Run:

```bash
PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7 \
  /glade/work/fillmore/miniforge3/envs/davinci/bin/python -m pytest \
  tests/test_davinci_analysis_configs.py -q
```

Expected: all config tests pass.

### Task 2: Document The Run Command

**Files:**
- Modify: `RUN.md`

- [x] **Step 1: Add the full-month command beside the existing DAVINCI commands**

Document:

```bash
davinci-monet run analyses/davinci/cam-aod-monthly-analysis-july-2008.yaml
davinci-monet inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/cam-aod-monthly-analysis-july-2008 \
  --preset gridded_aod_diagnostics
```

- [x] **Step 2: Run focused verification**

Run:

```bash
PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7 \
  /glade/work/fillmore/miniforge3/envs/davinci/bin/python -m pytest \
  tests/test_davinci_analysis_configs.py -q
PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7 \
  /glade/work/fillmore/miniforge3/envs/davinci/bin/python - <<'PY'
from davinci_monet.cli.commands.validate import validate_config_command

validate_config_command("analyses/davinci/cam-aod-monthly-analysis-july-2008.yaml")
PY
```

Expected: config tests pass and DAVINCI validation succeeds.
