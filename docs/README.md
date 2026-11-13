# CERES-SARB-CESM3-CAM7 documentation

The recipient installation and runtime guide is the repository
[README](../README.md). Supply your own CESM checkout, case configuration,
emissions and meteorological forcing, AOD observations and compatible optics
LUT. The source additions target CAM7 physics in `cesm3_0_beta08`,
CAM tag `cam6_4_161`, with the FV f09 grid and MAM4.

| Document | Purpose |
| --- | --- |
| [Installation and runtime settings](../README.md) | Fortran modules, CAM integration patches, namelist entries, observations and optics output. |
| [Tropospheric versus whole-column test](tropospheric-testing.md) | Matched on/off cases, tropopause diagnosis, diagnostic fields and vertical profiles of layer AOD. |
| [Tropospheric scaling method and original results](tropospheric-scaling.md) | The upstream method, protected-layer rules and July 2008 verification. |
| [Synchronization manifest](upstream-sync.json) | Exact source branch/commit and the mirrored file inventory. |
| [Original project workflow](../UPSTREAM-WORKFLOW.md) | The upstream preprocessing, Derecho setup and analysis workflow; adapt account paths for your installation. |
| [Scientific verification](science-verification.md) | Original numerical and plotted science checks. |
| [Run ledger](../run_history/index.md) | Original run records and links to the small validation summaries. |

## Branch and test setting

Use `feature/tropospheric-aod-nudging` for this option:

```bash
git fetch origin
git switch feature/tropospheric-aod-nudging
```

Keep `aod_nudge_on = .true.` in both test cases. Change only
`aod_tropo_only`: `.false.` retains whole-column scaling and `.true.` limits
the adjustment to levels strictly below the diagnosed tropopause. The
tropopause layer itself and all levels above it are excluded in the new mode.
Keep emissions and the other scientific inputs identical within the pair.

See the [paired test protocol](tropospheric-testing.md) for the layer-AOD
profiles to return and the before/after diagnostics that distinguish a
direct scaling increment from later changes along the model trajectory.

## Local validation

The existing focused tests can be run in the DAVINCI Python environment with
`gfortran` on `PATH`:

```bash
python -m pytest -q \
  tests/test_tropospheric_nudging.py \
  tests/test_sp2_deploy.py \
  tests/test_sp3_hardcoded_fortran_bands.py \
  tests/test_sp3_lut_table_reader_validation.py \
  tests/test_davinci_analysis_configs.py
```

This runs the compiled kernel/adapter test, the protected-layer numeric gate,
and the relevant deployment, optics and analysis-configuration checks.
The original full-model run evidence is preserved in the method note and
run ledger. These local tests do not build or execute a recipient's CESM case.
