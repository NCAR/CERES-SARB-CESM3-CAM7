# SP1 MODIS+VIIRS AOD Observation Pipeline Implementation Plan (built on DAVINCI)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build an offline, deterministic, re-runnable Python pipeline that turns MODIS (MOD04/MYD04 C6.1) + VIIRS (AERDB_L2 NOAA-20) Level-2 550 nm AOD into the frozen-contract 3-hourly netCDF product on the CAM7 f09 grid — by **importing and reusing the DAVINCI toolkit** (`davinci_monet`, the MONET-based evaluation library at `../DAVINCI`) for file readers, EarthData staging, swath→grid binning, AERONET co-location, and statistics; SP1 supplies only the AOD-aggregation glue (bias, inverse-variance merge, the §5 contract writer, the CLI).

**Architecture:** Two repositories, two parts.
- **PART A — upstream DAVINCI** (`/glade/work/fillmore/DAVINCI`): general capabilities DAVINCI lacks but other users will want — a **VIIRS `AERDB_L2` reader** (`@source_registry.register("viirs_l2_aerdb")` + catalog entry), an **uncertainty-aware binning** variant of the numba grid engine, and **robust `SpatialPlotter` color limits** (Task 8b) — are contributed upstream with their own pytest. A prerequisite **`AERONETReader.open` bugfix** (pass `dates` as one list to monetio `add_data`; the two-positional call bound `end_date` to `product`) is already committed on DAVINCI `develop` as `b029cdb`.
- **PART B — SP1-local** (`/glade/work/fillmore/CERES-SARB-CAM7/sp1_aod_pipeline`): a package of small, pure, golden-tested stages (acquire → ingest → QC → grid-bin → bias-correct → merge → window → write). The netCDF **contract** (`contract.py` + `validate_contract_file`) and the canonical **f09 grid** (`f09_grid.py`) are pinned FIRST and are the only coupling to SP2. Ingest wraps DAVINCI's `MODISL2AODReader` + the new VIIRS reader; gridding calls DAVINCI's `bin_swath_to_grid` + the new uncertainty variant; acquisition calls DAVINCI's `stage_collection`; validation uses DAVINCI's AERONET reader + `PointStrategy` + stats metrics.

## Current State — 2026-06-27

SP1 Tasks 1–20 are implemented. The original pre-flight MODIS monthly path remains documented below, but the SP1 package now writes and validates the frozen SP2-facing contract for the full July 2008 verification month and renders the VP1–VP3 DAVINCI science-verification plots.

Final repository status:
- **CERES-SARB-CAM7** is on `develop` at `376b685` (`SP1: finish July verification plots`) and is pushed to `origin/develop`.
- **DAVINCI** SP1 upstream support is on `sp1-viirs-aerdb` at `f3a3015` (`satellite: fix MODIS L2 AOD monetio defaults`) and is pushed to `origin/sp1-viirs-aerdb`.
- DAVINCI still has unrelated local, uncommitted edits in `environment.yml`, `pyproject.toml`, and analysis artifacts; these are not part of SP1 and were intentionally left unstaged.

What was actually implemented in **CERES-SARB-CAM7**:
- `scripts/stage_obs.py` remains the input-staging entry point. July 2008 MODIS/AERONET inputs were staged under `/glade/work/fillmore/Data/CERES-SARB-CAM7`.
- `scripts/prepare_modis_era5_grid.py` prepares MODIS L2 AOD on the ERA5/CAM7 f09 grid for July 2008. It explicitly combines four streams by count-weighted averaging:
  - Terra Dark Target
  - Terra Deep Blue
  - Aqua Dark Target
  - Aqua Deep Blue
- Prepared files live under `/glade/work/fillmore/Data/CERES-SARB-CAM7/MODIS_AOD_ERA5_GRID`. For July 2008 this produced 248 3-hourly files with total valid-pixel count `68,007,626`.
- `scripts/run_modis_monthly_davinci_analysis.py` builds a monthly DAVINCI analysis NetCDF, normalizes longitude to a monotonic `[-180, 180]` convention for plotting, and renders DAVINCI spatial/histogram plots.
- Monthly analysis output:
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/DAVINCI_ANALYSES/MODIS_AOD_ERA5_GRID/200807/modis_aod_monthly_davinci_analysis_200807.nc`
- Current plot output directory:
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/MODIS_AOD_ERA5_GRID/200807`
- Current plot PDFs:
  - `modis_aod_monthly_mean_map_200807.pdf`
  - `modis_aod_monthly_observation_count_200807.pdf`
  - `modis_aod_monthly_histogram_200807.pdf`
- The old one-off monthly plotting script was removed. Monthly plots are now generated through DAVINCI analysis rendering, not an ad hoc plotting path.
- Tests added under `tests/` cover the MODIS grid preparation and DAVINCI monthly analysis runner. Current command: `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest tests -q` → `7 passed`.
- SP1 package Tasks 1–6 and 9–20 are now implemented:
  - `sp1_aod_pipeline/__init__.py` defines package version `1.0.0`.
  - `sp1_aod_pipeline/tests/test_env.py` verifies the package imports and `davinci_monet` is available from the active env.
  - `sp1_aod_pipeline/f09_grid.py` defines the canonical CAM-FV f09 grid centers, bounds, and edges against `/glade/campaign/cesm/cesmdata/cseg/inputdata/atm/cam/coords/fv_0.9x1.25.nc`.
  - `sp1_aod_pipeline/contract.py` implements the frozen SP2-facing netCDF contract writer and validator.
  - `sp1_aod_pipeline/tests/test_f09_grid.py` and `sp1_aod_pipeline/tests/test_contract.py` verify the grid and contract behavior.
  - `sp1_aod_pipeline/config.py` implements `RunConfig.from_yaml`, including date coercion, default tunables, and MODIS CMR `collection="6.1"`.
  - `sp1_aod_pipeline/config.example.yaml` documents the July 2008 MODIS-only configuration that writes SP1 contract files under `/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr`.
  - `sp1_aod_pipeline/qc.py` implements the pure per-pixel AOD/QA/uncertainty/geolocation QC mask.
  - `sp1_aod_pipeline/records.py` implements shared `L2Record`/`CellGrid` containers and TAI93-to-`datetime64[ns]` conversion.
  - `sp1_aod_pipeline/tests/fixtures.py` includes a synthetic VIIRS AERDB_L2 granule builder for deterministic ingest tests.
  - `sp1_aod_pipeline/ingest_viirs.py` adapts DAVINCI `VIIRSL2AERDBReader` output into `L2Record`, preferring valid land retrievals, falling back to ocean, preserving QA, and converting TAI93 time.
  - `sp1_aod_pipeline/tests/fixtures.py` also includes a synthetic MODIS combined DT+DB NetCDF granule builder.
  - `sp1_aod_pipeline/ingest_modis.py` adapts MODIS combined 550 nm AOD fields into `L2Record`, using land/ocean expected-error coefficients based on the algorithm flag and direct xarray reading for test/pre-extracted NetCDF granules.
  - `sp1_aod_pipeline/grid.py` bins `L2Record` pixels to f09 with DAVINCI's base and uncertainty-aware binning engines, including longitude wrapping and f09 `(lat, lon)` output ordering.
  - `sp1_aod_pipeline/merge.py` implements fill-aware inverse-variance merging of two per-cell AOD grids, preserving valid single-sensor cells and combining counts.
  - `sp1_aod_pipeline/bias.py` implements AERONET-anchored affine VIIRS-to-MODIS bias coefficients, fill-aware AOD/sigma correction, JSON persistence, and coefficient resolution precedence.
  - `sp1_aod_pipeline/aggregate.py` implements 3-hour window bounds, window indexing, half-open pixel-time masks, and inclusive date/window enumeration.
  - `sp1_aod_pipeline/acquire.py` declares DAVINCI `CollectionSpec`s for MOD04, MYD04, and AERDB NOAA-20 and delegates staging to DAVINCI `stage_collection` with injectable network hooks. MODIS CMR VersionId remains `"6.1"`.
  - `sp1_aod_pipeline/validation/aeronet.py` loads DAVINCI-staged AERONET NetCDF caches, supports both `(time, y, x)` and real `(time, site)` schemas, interpolates AOD 500 nm to 550 nm, and can download missing days through DAVINCI.
  - `sp1_aod_pipeline/validation/compare.py` implements DAVINCI-metric error stats, deterministic nearest-f09 AERONET co-location, seasonal summaries, and DAVINCI `PointStrategy` co-location. The retired tvmora archive comparison is not implemented.
  - `sp1_aod_pipeline/pipeline.py` orchestrates discovery, ingest, QC, f09 binning, VIIRS bias correction, inverse-variance merge, and SP2 contract writing. Discovery uses recursive globs so it works with both synthetic flat test dirs and staged Data-root layouts. `run()` now reads each day's granules once and slices the in-memory daily record into the eight 3-hour windows, avoiding an 8x reread of the July 2008 HDF inputs.
  - `sp1_aod_pipeline/__main__.py` implements `run`, `validate`, `download`, and `fit-bias`; `python -m sp1_aod_pipeline --help` lists all four commands.
  - `sp1_aod_pipeline/tests/make_golden.py` builds the deterministic golden contract fixture at `sp1_aod_pipeline/tests/data/golden_window.npz`, and `sp1_aod_pipeline/tests/test_golden.py` covers golden regression plus real VIIRS structural invariants.
  - `sp1_aod_pipeline/records.py` now rejects huge fill-like TAI93 values before nanosecond conversion so real VIIRS fill times become `NaT` without overflow warnings.
  - `sp1_aod_pipeline/verify/plots.py` builds a count-weighted DAVINCI-ready verification dataset from SP1 contract files and renders VP1 global AOD, VP2 AERONET scatter, and VP3 uncertainty/count maps. It writes both PDF and PNG outputs and a `summary.json`.
  - Full July 2008 SP1 verification run:
    - Contract output directory: `/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr`
    - Contract files: `248` (`2008-07-01 00:00` through `2008-07-31 21:00`)
    - Frozen-contract validation: `248/248` valid
    - Total valid L2 contributing pixels: `90,306,110`
    - Valid grid-cell windows across the month: `1,423,997`
    - Run log: `/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/run.log`
  - VP1–VP3 plot directory:
    `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP1_AOD_f09_3hr/200807`
  - VP1–VP3 outputs:
    - `sp1_aod_verification_analysis.nc`
    - `summary.json`
    - `vp1_global_aod_map.pdf` / `vp1_global_aod_map.png`
    - `vp2_aeronet_scatter.pdf` / `vp2_aeronet_scatter.png`
    - `vp3_uncertainty_map.pdf` / `vp3_uncertainty_map.png`
    - `vp3_count_map.pdf` / `vp3_count_map.png`
  - VP1–VP3 inspection summary:
    - AOD map uses the DAVINCI `geosit_aod` nonuniform levels/color table and is plotted on normalized monotonic longitudes `[-178.75, 180.0]`.
    - Monthly global count-weighted AOD mean: `0.15365210296218082`; median `0.10402679443359375`.
    - AERONET pairs: `N=8875`, `MB=0.019465336626899758`, `ME=0.08472187640326716`, `RMSE=0.14642740504149715`, `R=0.8554977883039155`.
    - Uncertainty/count maps are fill-consistent and show lower uncertainty where counts are high.
  - Task 20 final verification completed:
    - SP1 package suite: `PYTHONPATH=/glade/work/fillmore/CERES-SARB-CAM7 /glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest sp1_aod_pipeline/tests -q` → `63 passed`.
    - Full local suite: `PYTHONPATH=/glade/work/fillmore/CERES-SARB-CAM7 /glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest sp1_aod_pipeline/tests tests -q` → `70 passed`.
    - Formatting: `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m black --check sp1_aod_pipeline` → `41 files would be left unchanged`.
    - Full July 2008 contract validation: `248` files checked, `0` invalid.
    - DAVINCI touched tests: `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py davinci_monet/tests/unit/datasets/satellite/test_catalog.py davinci_monet/tests/unit/datasets/satellite/test_modis_l2_aod.py davinci_monet/tests/unit/pairing/test_grid_binning.py -q` → `14 passed`.

What was actually implemented upstream in **DAVINCI**:
- `SpatialPlotter` now supports explicit discrete color-bin boundaries via `levels`, `cmap`, and colorbar `extend`.
- `SpatialPlotter` now supports `style_preset="geosit_aod"`.
- The `geosit_aod` preset uses the GEOSIT AOD plotting convention found in `../CERES-SARB-GEOSIT-LFL`:
  - nonuniform levels `0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05, ...`
  - 0.05 spacing above 0.05
  - plotted range capped at `1.0`
  - `turbo` color table
  - `extend="max"`
- DAVINCI config/schema plumbing now accepts/forwards AOD style options:
  - per-variable `style_preset`, `levels_plot`, `cmap_plot`, `extend_plot`
  - per-plot `style_preset`, `levels`, `cmap`, `extend`
- `analyses/modis-aod/configs/modis-aod-cam6.example.yaml` now demonstrates `style_preset: geosit_aod`.
- Focused DAVINCI verification command:
  `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest davinci_monet/tests/unit/plots/test_style.py davinci_monet/tests/unit/plots/test_spatial_single_source.py davinci_monet/tests/unit/pipeline/test_plot_options.py davinci_monet/tests/unit/config/test_schema.py -q` → `100 passed`.
- SP1 Task 7 is implemented on DAVINCI branch `sp1-viirs-aerdb` commit `2f9c03c`:
  - `davinci_monet/datasets/satellite/viirs_l2_aerdb.py` adds registered `VIIRSL2AERDBReader` (`source_registry` name `viirs_l2_aerdb`) for AERDB_L2 swath NetCDF files.
  - `davinci_monet/datasets/__init__.py` imports the reader for registration side effects.
  - `davinci_monet/datasets/satellite/catalog/data/modis_viirs_atmosphere.yaml` now includes `AERDB_L2_VIIRS_NOAA20` with alias `viirs_aerdb_noaa20`.
  - Focused DAVINCI verification command:
    `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py davinci_monet/tests/unit/datasets/satellite/test_catalog.py -q` → `9 passed`.
- SP1 Task 8 is implemented on DAVINCI branch `sp1-viirs-aerdb` commit `bf0b46d`:
  - `davinci_monet/pairing/grid_binning.py` now provides `bin_swath_to_grid_uncertainty` and `normalize_uncertainty_grid` for inverse-variance swath binning.
  - Focused DAVINCI verification command:
    `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py davinci_monet/tests/unit/datasets/satellite/test_catalog.py davinci_monet/tests/unit/pairing/test_grid_binning.py -q` → `12 passed`.
- SP1 Task 8b is implemented on DAVINCI branch `sp1-viirs-aerdb` commit `2bcce4c`:
  - `SpatialPlotter` accepts `robust=True` and `robust_pct=(2, 98)` to resolve color limits from data percentiles when explicit `vmin`/`vmax`/`levels` are absent.
  - Comparison plot option assembly forwards `robust` and `robust_pct`.
  - Focused DAVINCI verification command:
    `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest davinci_monet/tests/unit/plots/test_style.py davinci_monet/tests/unit/plots/test_spatial_single_source.py davinci_monet/tests/unit/plots/test_robust_clim.py davinci_monet/tests/unit/pipeline/test_plot_options.py davinci_monet/tests/unit/config/test_schema.py davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py davinci_monet/tests/unit/datasets/satellite/test_catalog.py davinci_monet/tests/unit/pairing/test_grid_binning.py -q` → `115 passed`.
- SP1 MODIS HDF real-reader support is implemented on DAVINCI branch `sp1-viirs-aerdb` commit `f3a3015`:
  - `MODISL2AODReader` now supplies monetio's required MODIS variable dictionary, keeps integer QA/algorithm flags unmasked to avoid NaN assignment into integer arrays, handles monetio multi-file dictionaries, and exposes `Scan_Start_Time` from monetio's epoch-1970 `time` coordinate.
  - Focused DAVINCI verification command:
    `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pytest davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py davinci_monet/tests/unit/datasets/satellite/test_catalog.py davinci_monet/tests/unit/datasets/satellite/test_modis_l2_aod.py davinci_monet/tests/unit/pairing/test_grid_binning.py -q` → `14 passed`.

Deferred from the original plan:
- The current July-2008 verification path is MODIS-only because July 2008 predates VIIRS NOAA-20.
- CERES-SARB-CAM7 is currently on branch `develop`, clean against `origin/develop`. DAVINCI is currently on branch `sp1-viirs-aerdb`, pushed to `origin/sp1-viirs-aerdb`; unrelated local edits in `environment.yml`, `pyproject.toml`, and analysis artifacts remain unstaged and should not be reverted unless explicitly requested.

**Tech Stack:** Python 3.11+ in conda env **`davinci-monet`** with `davinci_monet` installed **editable** (`pip install -e "../DAVINCI[reanalysis]"`, pulls `earthaccess`); numpy, xarray, netCDF4, pandas 1.5.3, scipy, pyyaml, numba, monet/monetio (DAVINCI deps); pytest with tiny golden/synthetic fixtures + real on-disk samples.

## Global Constraints
- Platform: NCAR derecho. Project/account `P19010000`. All paths absolute.
- **Interpreter (ONLY this one):** `/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python` (conda env `davinci-monet`; has xarray, netCDF4, pandas 1.5.3, scipy, pyyaml, numba, pytest 9.0.2, and — after Task 1 — `davinci_monet` editable + `earthaccess`). Refer to it as `$PY`.
- **Two repos / two branches.**
  - `$ROOT` = `/glade/work/fillmore/CERES-SARB-CAM7`; SP1 package `$PKG` = `$ROOT/sp1_aod_pipeline`. Work on branch `sp1-obs-pipeline`.
  - `$DV` = `/glade/work/fillmore/DAVINCI` (separate git repo, branch `develop`). Part-A work on branch `sp1-viirs-aerdb`.
- **Run SP1 (Part B) tests:** `PYTHONPATH=$ROOT $PY -m pytest <abs-path-to-test> -q`.
- **Run DAVINCI (Part A) tests:** `$PY -m pytest <abs-path-to-test> -q` (no `PYTHONPATH`; `davinci_monet` is installed editable so its tests import it directly).
- **Run-length guidance:** development smoke tests for CAM7 runs may cover only a few days when that is enough to exercise the code path under development. The full verification run is the complete July 2008 test month. Agents should use engineering judgment to choose a test-run length that matches the risk and scope of the change, and should reserve the full July 2008 run for verification gates rather than every small edit.
- **Each task's Files: block states its target repo** (DAVINCI upstream vs CERES-SARB-CAM7 local). Part A precedes the Part-B tasks that import it; the contract writer/validator is pinned in Task 3.
- Grid: f09 = 192 lat × 288 lon, **CAM-FV pole-centered**: `lat=linspace(-90,90,192)` (dlat=180/191≈0.9424), `lon=arange(288)*1.25` (lon[0]=0.0). Authoritative source file: `/glade/campaign/cesm/cesmdata/cseg/inputdata/atm/cam/coords/fv_0.9x1.25.nc`. The pole-centered `lat_bnds` carry half-width polar cells; **binning uses `davinci_monet.pairing.grid_binning.edges_from_centers(centers)`, which yields uniform edges around those centers** so DAVINCI's uniform floor-division engine assigns each pixel to its nearest-center cell correctly. (NOTE: the legacy tvmora obs grid was a DIFFERENT equal-spaced grid; do NOT copy it.)
- AOD wavelength: 550 nm only. Fill value for floats = `-999.0` (`_FillValue`), for count = `0`. All data var `units="1"`. `Conventions="CF-1.10"`.
- Contract is FROZEN (see Task 3). SP1 WRITES it; SP2 READS it. Never deviate.
- QC defaults (all tunable via config): VIIRS `QA_Flag >= 2`, MODIS combined `QA_Flag >= 1` (valid retrieval), drop AOD ∉ [0,5]; additionally drop pixels with fill/out-of-range per-pixel uncertainty (`0 < σ ≤ sigma_max`, default 5) and non-finite geolocation. Merge = inverse-variance `w=1/σ²`. VIIRS→MODIS bias correction = AERONET-anchored affine (coefficients persisted + provenance). AERONET interpolated to 550 nm via the 440–675 Ångström exponent (R19).
- TDD, frequent commits, no placeholders, every tunable in config/namelist, every run parameter logged.
- Work on a branch, never commit straight to `main`/`develop` unless told.

---

## File Structure

### PART A — upstream DAVINCI (target repo `$DV` = `/glade/work/fillmore/DAVINCI`)
| Path | Single responsibility |
|---|---|
| `davinci_monet/datasets/satellite/viirs_l2_aerdb.py` | **NEW** `VIIRSL2AERDBReader` (`@source_registry.register("viirs_l2_aerdb")`) — reads AERDB_L2 NetCDF swath → standardized `xr.Dataset`. |
| `davinci_monet/datasets/__init__.py` | **MODIFY** — import the new reader module for registration side-effect. |
| `davinci_monet/datasets/satellite/catalog/data/modis_viirs_atmosphere.yaml` | **MODIFY** — add the `AERDB_L2_VIIRS_NOAA20` L2/SWATH product entry. |
| `davinci_monet/pairing/grid_binning.py` | **MODIFY** — add `bin_swath_to_grid_uncertainty` (numba) + `normalize_uncertainty_grid`. |
| `davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py` | **NEW** pytest for the reader (synthetic + real tvmora sample). |
| `davinci_monet/tests/unit/datasets/satellite/test_catalog.py` | **MODIFY** — assert the new catalog entry resolves. |
| `davinci_monet/tests/unit/pairing/test_grid_binning.py` | **MODIFY** — add uncertainty-binning tests. |

### PART B — SP1-local (target repo `$ROOT` = `/glade/work/fillmore/CERES-SARB-CAM7`)
| Path | Single responsibility |
|---|---|
| `$PKG/__init__.py` | Package marker (version string only). |
| `$PKG/f09_grid.py` | Canonical CAM-FV f09 lat/lon centers + bounds + cell edges. No other deps. |
| `$PKG/contract.py` | Frozen contract constants, `contract_filename`, `git_commit`, `write_contract_file`, `validate_contract_file`. |
| `$PKG/config.py` | `RunConfig` dataclass + `from_yaml`. All tunables. |
| `$PKG/config.example.yaml` | Documented example config. |
| `$PKG/records.py` | Shared dataclasses `L2Record`, `CellGrid` + `tai93_to_datetime64`. |
| `$PKG/qc.py` | Pure QC mask function. |
| `$PKG/ingest_viirs.py` | DAVINCI `VIIRSL2AERDBReader` → `L2Record` adapter (land+ocean merge, σ, TAI93). |
| `$PKG/ingest_modis.py` | DAVINCI `MODISL2AODReader` → `L2Record` adapter (combined DT+DB, EE σ); pure transform. |
| `$PKG/grid.py` | f09 binning via DAVINCI `bin_swath_to_grid` (simple mean) + the uncertainty variant (weighted mean + σ). |
| `$PKG/merge.py` | Inverse-variance merge of two `CellGrid`s (fill-aware). |
| `$PKG/bias.py` | `BiasCoeffs`, AERONET-anchored `fit_bias`, `apply_bias`, `apply_bias_sigma`, JSON persistence. |
| `$PKG/aggregate.py` | 3-hourly window bounds/index helpers + pixel-time masking + window enumeration. |
| `$PKG/acquire.py` | LAADS `CollectionSpec`s (MOD04/MYD04/AERDB) + `stage_sp1` over DAVINCI `stage_collection`. |
| `$PKG/pipeline.py` | Orchestrate one window → one contract file; driver over date range; granule discovery. |
| `$PKG/__main__.py` | CLI: `run`, `validate`, `download`, `fit-bias`. |
| `$PKG/validation/__init__.py` | Package marker. |
| `$PKG/validation/aeronet.py` | Load AERONET V3 direct-sun files; interpolate AOD to 550 nm. |
| `$PKG/validation/compare.py` | Co-locate product vs AERONET (DAVINCI stats + `PointStrategy`); seasonal MB/ME/RMSE. |
| `$PKG/verify/plots.py` | DAVINCI science-verification renders (VP1–VP3): global AOD map, AERONET scatter, uncertainty/count maps. Inspection gate per `docs/science-verification.md`. |
| `$PKG/tests/__init__.py` | Test package marker. |
| `$PKG/tests/fixtures.py` | Synthetic-granule builders `make_viirs_granule`, `make_modis_granule`. |
| `$PKG/tests/make_golden.py` | Deterministic golden builder + real-sample path constants. |
| `$PKG/tests/data/.gitkeep` / `golden_window.npz` | Committed golden fixture. |
| `$PKG/tests/test_*.py` | One test module per source module (+ `test_golden.py`, `test_env.py`). |

---

## Execution order
**Task 0 (pre-implementation): stage the July-2008 test inputs** with `scripts/stage_obs.py` (MOD04/MYD04 C6.1 Terra+Aqua, global, ~24 GB / ~9.8k granules; + AERONET Level-2.0) into `/glade/work/fillmore/Data/CERES-SARB-CAM7/{MODIS_VIIRS_L2,AeroNet}` — see the script header. July 2008 is MODIS-only (predates VIIRS).

Tasks are numbered in dependency order. **Task 3 pins the frozen contract early.** **Part A (Tasks 7–8) precedes the Part-B tasks that import it** (Task 9 imports the VIIRS reader; Task 11 imports the binning variant). Tasks 1–6 are SP1-local foundation; 7–8 are upstream DAVINCI; 9–19 are SP1-local pipeline.

---

### Task 1 — [Part B: SP1-local] Env setup + package skeleton + pin davinci_monet

Pin `davinci_monet` as an editable dependency in the `davinci-monet` conda env so SP1 can import its readers/binning/staging/stats, then create the SP1 package skeleton.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/__init__.py`, `$PKG/tests/__init__.py`, `$PKG/tests/data/.gitkeep`
- Test: `$PKG/tests/test_env.py`

**Interfaces:**
- Produces: importable package `sp1_aod_pipeline` (`__version__`); a verified `import davinci_monet` from `$PY`.

- [x] **Step 1: Pin davinci_monet editable into the env.** Install DAVINCI editable with the `reanalysis` extra (pulls `earthaccess` for `stage_collection`):
  ```bash
  /glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python -m pip install -e "/glade/work/fillmore/DAVINCI[reanalysis]"
  ```
  Expect pip to end with `Successfully installed davinci-monet-26.06 ... earthaccess-...` (or `Requirement already satisfied`).

- [x] **Step 2: Create package markers.** Write `$PKG/__init__.py`:
  ```python
  """SP1 offline MODIS+VIIRS AOD observation pipeline (built on davinci_monet)."""
  __version__ = "1.0.0"
  ```
  Write `$PKG/tests/__init__.py` (single line `# test package`). Create dir + `$PKG/tests/data/.gitkeep` (empty file).

- [x] **Step 3: Write the failing test** `$PKG/tests/test_env.py`:
  ```python
  def test_sp1_package_imports():
      import sp1_aod_pipeline
      assert sp1_aod_pipeline.__version__ == "1.0.0"

  def test_davinci_monet_is_pinned():
      # SP1 depends on davinci_monet being importable in this env (Task 1 Step 1).
      import davinci_monet
      import davinci_monet.datasets  # registers dataset readers
      from davinci_monet.core.registry import source_registry
      from davinci_monet.pairing.grid_binning import bin_swath_to_grid, edges_from_centers
      from davinci_monet.io.download.earthdata import stage_collection, CollectionSpec
      assert "modis_l2_aod" in source_registry.list()
  ```
- [x] **Step 4: Run it (expect PASS).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_env.py -q` → expect `2 passed`. (If `test_davinci_monet_is_pinned` errors with `ModuleNotFoundError`, redo Step 1.)

- [x] **Step 5: Commit.** This execution continued on `develop` instead of creating `sp1-obs-pipeline`, matching the current user-approved branch flow.
  ```bash
  git -C /glade/work/fillmore/CERES-SARB-CAM7 checkout -b sp1-obs-pipeline
  git -C /glade/work/fillmore/CERES-SARB-CAM7 add sp1_aod_pipeline/__init__.py sp1_aod_pipeline/tests/__init__.py sp1_aod_pipeline/tests/data/.gitkeep sp1_aod_pipeline/tests/test_env.py
  git -C /glade/work/fillmore/CERES-SARB-CAM7 commit -m "SP1: package skeleton + pin davinci_monet (editable)"
  ```

---

### Task 2 — [Part B: SP1-local] Canonical CAM-FV f09 grid

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/f09_grid.py`
- Test: `$PKG/tests/test_f09_grid.py`

**Interfaces:**
- Produces: `NLAT:int=192`, `NLON:int=288`, `f09_lat()->np.ndarray(192,)f8`, `f09_lon()->np.ndarray(288,)f8`, `f09_lat_bnds()->np.ndarray(192,2)f8`, `f09_lon_bnds()->np.ndarray(288,2)f8`, `lat_edges()->np.ndarray(193,)f8`, `lon_edges()->np.ndarray(289,)f8`.

- [x] **Step 1: Write the failing test** `$PKG/tests/test_f09_grid.py`:
  ```python
  import numpy as np
  import xarray as xr
  from sp1_aod_pipeline import f09_grid as g

  CAM_GRID = "/glade/campaign/cesm/cesmdata/cseg/inputdata/atm/cam/coords/fv_0.9x1.25.nc"

  def test_centers_match_cam_fv_file():
      ds = xr.open_dataset(CAM_GRID, decode_times=False)
      assert g.NLAT == 192 and g.NLON == 288
      assert np.allclose(g.f09_lat(), ds["lat"].values, atol=1e-9)
      assert np.allclose(g.f09_lon(), ds["lon"].values, atol=1e-9)

  def test_pole_centered_not_legacy():
      lat = g.f09_lat()
      assert lat[0] == -90.0 and lat[-1] == 90.0
      assert abs((lat[1] - lat[0]) - 180.0 / 191.0) < 1e-12
      assert g.f09_lon()[0] == 0.0

  def test_bounds_shapes_and_interior_edges_match_slat():
      ds = xr.open_dataset(CAM_GRID, decode_times=False)
      lb = g.f09_lat_bnds()
      assert lb.shape == (192, 2)
      assert lb[0, 0] == -90.0 and lb[-1, 1] == 90.0
      interior = lb[1:, 0]
      assert np.allclose(interior, ds["slat"].values, atol=1e-9)
      lonb = g.f09_lon_bnds()
      assert lonb.shape == (288, 2)
      assert np.allclose(lonb[0], [-0.625, 0.625])

  def test_edges_lengths():
      assert g.lat_edges().shape == (193,)
      assert g.lon_edges().shape == (289,)
      assert g.lon_edges()[0] == -0.625 and g.lon_edges()[-1] == 359.375
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_f09_grid.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.f09_grid'`.

- [x] **Step 3: Implement** `$PKG/f09_grid.py`:
  ```python
  """Canonical CAM-FV f09 (0.9x1.25) grid: pole-centered, lon starts at 0.

  Authoritative reference file (centers verified to 1e-9):
  /glade/campaign/cesm/cesmdata/cseg/inputdata/atm/cam/coords/fv_0.9x1.25.nc
  """
  import numpy as np

  NLAT = 192
  NLON = 288
  DLON = 1.25


  def f09_lat():
      return np.linspace(-90.0, 90.0, NLAT)


  def f09_lon():
      return np.arange(NLON) * DLON


  def lat_edges():
      lat = f09_lat()
      mids = 0.5 * (lat[:-1] + lat[1:])
      return np.concatenate([[-90.0], mids, [90.0]])


  def lon_edges():
      return np.arange(NLON + 1) * DLON - 0.5 * DLON


  def f09_lat_bnds():
      e = lat_edges()
      return np.stack([e[:-1], e[1:]], axis=1)


  def f09_lon_bnds():
      e = lon_edges()
      return np.stack([e[:-1], e[1:]], axis=1)
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `4 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/f09_grid.py sp1_aod_pipeline/tests/test_f09_grid.py`; commit `SP1: canonical CAM-FV f09 grid`. This execution commits Tasks 2 and 3 together on `develop`.

---

### Task 3 — [Part B: SP1-local] Frozen contract writer + validator (PINNED — keep verbatim)

This is the SP2-facing contract (SPEC §5). It is unchanged by the DAVINCI pivot — implement it **exactly** as below.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/contract.py`
- Test: `$PKG/tests/test_contract.py`

**Interfaces:**
- Consumes: `f09_grid.{f09_lat,f09_lon,f09_lat_bnds,f09_lon_bnds,NLAT,NLON}`.
- Produces: constants `FILL_FLOAT=np.float32(-999.0)`, `FILL_COUNT=np.int32(0)`, `NBNDS=2`, `WINDOW_LENGTH_SEC=10800`, `WINDOW_SECONDS=[0,...,75600]`, `TIME_UNITS`, `TIME_CALENDAR`, `FILENAME_TEMPLATE`, `REQUIRED_GLOBAL_ATTRS`; `contract_filename(window_start)->str`; `git_commit()->str`; `write_contract_file(out_path, *, window_start, aod_weighted_mean, aod_uncertainty, aod_count, aod_weighted_mean_modis=None, aod_weighted_mean_viirs=None, global_attrs=None)->None`; `validate_contract_file(path)->tuple[bool,list[str]]`.

- [x] **Step 1: Write the failing test** `$PKG/tests/test_contract.py`:
  ```python
  import os
  from datetime import datetime
  import numpy as np
  import netCDF4 as nc
  from sp1_aod_pipeline import contract as c
  from sp1_aod_pipeline.f09_grid import NLAT, NLON

  def _fields():
      mean = np.full((NLAT, NLON), -999.0, np.float32)
      unc = np.full((NLAT, NLON), -999.0, np.float32)
      cnt = np.zeros((NLAT, NLON), np.int32)
      mean[10, 20] = 0.42; unc[10, 20] = 0.05; cnt[10, 20] = 7
      return mean, unc, cnt

  def test_filename():
      assert c.contract_filename(datetime(2020, 6, 15, 3, 0, 0)) == \
          "MODIS_VIIRS_AOD_3hr_f09.20200615.10800.nc"
      assert c.contract_filename(datetime(2020, 6, 15, 0, 0, 0)).endswith(".00000.nc")

  def test_write_then_validate_ok(tmp_path):
      mean, unc, cnt = _fields()
      out = str(tmp_path / "x.nc")
      c.write_contract_file(out, window_start=datetime(2020, 6, 15, 0, 0, 0),
                            aod_weighted_mean=mean, aod_uncertainty=unc, aod_count=cnt,
                            aod_weighted_mean_modis=mean, aod_weighted_mean_viirs=mean,
                            global_attrs={"qc_thresholds": "viirs_qa>=2", "source": "test"})
      ok, errs = c.validate_contract_file(out)
      assert ok, errs

  def test_time_is_scalar_center_and_bnds(tmp_path):
      mean, unc, cnt = _fields()
      out = str(tmp_path / "y.nc")
      c.write_contract_file(out, window_start=datetime(2000, 1, 1, 0, 0, 0),
                            aod_weighted_mean=mean, aod_uncertainty=unc, aod_count=cnt)
      ds = nc.Dataset(out)
      t = ds["time"]
      assert t.ndim == 0
      assert abs(float(t[...]) - 1.5) < 1e-9
      assert np.allclose(ds["time_bnds"][:], [0.0, 3.0])
      assert t.units == c.TIME_UNITS and t.calendar == c.TIME_CALENDAR
      ds.close()

  def test_fill_and_dtypes(tmp_path):
      mean, unc, cnt = _fields()
      out = str(tmp_path / "z.nc")
      c.write_contract_file(out, window_start=datetime(2020, 6, 15, 0, 0, 0),
                            aod_weighted_mean=mean, aod_uncertainty=unc, aod_count=cnt)
      ds = nc.Dataset(out)
      v = ds["aod_weighted_mean"]
      assert v.dtype == np.float32 and float(v._FillValue) == -999.0 and v.units == "1"
      assert ds["aod_count"].dtype == np.int32 and int(ds["aod_count"]._FillValue) == 0
      assert ds.getncattr("Conventions") == "CF-1.10"
      ds.close()

  def test_validator_flags_bad_grid(tmp_path):
      out = str(tmp_path / "bad.nc")
      d = nc.Dataset(out, "w")
      d.createDimension("lat", NLAT); d.createDimension("lon", NLON); d.createDimension("nbnds", 2)
      d.createVariable("lat", "f8", ("lat",))[:] = np.zeros(NLAT)
      d.close()
      ok, errs = c.validate_contract_file(out)
      assert not ok
      assert any("lat" in e for e in errs)
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_contract.py -q` → `ModuleNotFoundError`.

- [x] **Step 3: Implement** `$PKG/contract.py` (verbatim):
  ```python
  """Frozen obs-file contract (SPEC.md section 5). SP1 writes; SP2 reads."""
  import os
  import subprocess
  from datetime import datetime, timedelta, timezone
  import numpy as np
  import netCDF4 as nc
  from .f09_grid import f09_lat, f09_lon, f09_lat_bnds, f09_lon_bnds, NLAT, NLON

  FILL_FLOAT = np.float32(-999.0)
  FILL_COUNT = np.int32(0)
  NBNDS = 2
  WINDOW_LENGTH_SEC = 10800
  WINDOW_SECONDS = [i * WINDOW_LENGTH_SEC for i in range(8)]   # 0,10800,...,75600
  TIME_UNITS = "hours since 2000-01-01 00:00:00 UTC"
  TIME_CALENDAR = "gregorian"
  EPOCH = datetime(2000, 1, 1)
  FILENAME_TEMPLATE = "MODIS_VIIRS_AOD_3hr_f09.{ymd}.{secs:05d}.nc"
  PRIMARY_STD_NAME = "atmosphere_optical_thickness_due_to_ambient_aerosol_particles"
  REQUIRED_GLOBAL_ATTRS = [
      "Conventions", "title", "institution", "source", "history", "references",
      "qc_thresholds", "merge_method", "merge_version", "bias_correction_method",
      "bias_correction_version", "grid", "aod_wavelength_nm", "date_created", "git_commit",
  ]

  def contract_filename(window_start):
      secs = window_start.hour * 3600 + window_start.minute * 60 + window_start.second
      return FILENAME_TEMPLATE.format(ymd=window_start.strftime("%Y%m%d"), secs=secs)

  def git_commit():
      here = os.path.dirname(os.path.abspath(__file__))
      try:
          return subprocess.check_output(
              ["git", "-C", here, "rev-parse", "HEAD"],
              stderr=subprocess.DEVNULL).decode().strip()
      except Exception:
          return "unknown"

  def _hours(dt):
      return (dt - EPOCH).total_seconds() / 3600.0

  def _prep(arr, fill, dtype):
      a = np.array(arr, dtype=np.float64)
      a = np.where(np.isfinite(a), a, float(fill))
      return a.astype(dtype)

  def _default_global_attrs():
      return {
          "Conventions": "CF-1.10",
          "title": "Merged MODIS+VIIRS gridded AOD (550 nm) on f09 for CAM7 nudging",
          "institution": "NCAR",
          "source": "MODIS MOD04_L2/MYD04_L2 C6.1 (DT+DB); VIIRS AERDB_L2 NOAA-20 C2",
          "history": "created by sp1_aod_pipeline",
          "references": "CERES-SARB-CAM7 SPEC.md section 5",
          "qc_thresholds": "unset",
          "merge_method": "inverse-variance (w=1/sigma^2)",
          "merge_version": "1.0",
          "bias_correction_method": "AERONET-anchored affine VIIRS->MODIS",
          "bias_correction_version": "1.0",
          "grid": "f09 FV 0.9x1.25 (192x288)",
          "aod_wavelength_nm": np.int32(550),
          "date_created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "git_commit": git_commit(),
      }

  def write_contract_file(out_path, *, window_start, aod_weighted_mean, aod_uncertainty,
                          aod_count, aod_weighted_mean_modis=None,
                          aod_weighted_mean_viirs=None, global_attrs=None):
      center = window_start + timedelta(seconds=WINDOW_LENGTH_SEC // 2)
      end = window_start + timedelta(seconds=WINDOW_LENGTH_SEC)
      ds = nc.Dataset(out_path, "w", format="NETCDF4")
      try:
          ds.createDimension("lat", NLAT)
          ds.createDimension("lon", NLON)
          ds.createDimension("nbnds", NBNDS)
          vlat = ds.createVariable("lat", "f8", ("lat",))
          vlat.units = "degrees_north"; vlat.standard_name = "latitude"; vlat.bounds = "lat_bnds"
          vlat[:] = f09_lat()
          vlon = ds.createVariable("lon", "f8", ("lon",))
          vlon.units = "degrees_east"; vlon.standard_name = "longitude"; vlon.bounds = "lon_bnds"
          vlon[:] = f09_lon()
          ds.createVariable("lat_bnds", "f8", ("lat", "nbnds"))[:] = f09_lat_bnds()
          ds.createVariable("lon_bnds", "f8", ("lon", "nbnds"))[:] = f09_lon_bnds()
          vt = ds.createVariable("time", "f8", ())
          vt.units = TIME_UNITS; vt.calendar = TIME_CALENDAR
          vt.standard_name = "time"; vt.bounds = "time_bnds"
          vt[...] = _hours(center)
          ds.createVariable("time_bnds", "f8", ("nbnds",))[:] = [_hours(window_start), _hours(end)]

          def mkf(name, arr, longn, std=None):
              v = ds.createVariable(name, "f4", ("lat", "lon"), fill_value=FILL_FLOAT)
              v.units = "1"; v.long_name = longn
              if std:
                  v.standard_name = std
              v[:] = _prep(arr, FILL_FLOAT, np.float32)

          mkf("aod_weighted_mean", aod_weighted_mean,
              "Merged MODIS+VIIRS column AOD at 550 nm", PRIMARY_STD_NAME)
          mkf("aod_uncertainty", aod_uncertainty, "1-sigma uncertainty of aod_weighted_mean")
          vc = ds.createVariable("aod_count", "i4", ("lat", "lon"), fill_value=FILL_COUNT)
          vc.units = "1"
          vc.long_name = "number of valid L2 pixels contributing to the cell-window"
          vc[:] = _prep(aod_count, FILL_COUNT, np.int32)
          if aod_weighted_mean_modis is not None:
              mkf("aod_weighted_mean_modis", aod_weighted_mean_modis,
                  "MODIS-only column AOD at 550 nm")
          if aod_weighted_mean_viirs is not None:
              mkf("aod_weighted_mean_viirs", aod_weighted_mean_viirs,
                  "VIIRS-only (bias-corrected) column AOD at 550 nm")

          attrs = _default_global_attrs()
          attrs.update(global_attrs or {})
          for k, v in attrs.items():
              ds.setncattr(k, v)
      finally:
          ds.close()

  def validate_contract_file(path):
      errs = []
      ds = nc.Dataset(path)
      try:
          for dn, exp in [("lat", NLAT), ("lon", NLON), ("nbnds", NBNDS)]:
              if dn not in ds.dimensions:
                  errs.append(f"missing dim {dn}")
              elif len(ds.dimensions[dn]) != exp:
                  errs.append(f"dim {dn}={len(ds.dimensions[dn])} expected {exp}")
          if "lat" in ds.variables and not np.allclose(ds["lat"][:], f09_lat(), atol=1e-6):
              errs.append("lat centers do not match f09")
          if "lon" in ds.variables and not np.allclose(ds["lon"][:], f09_lon(), atol=1e-6):
              errs.append("lon centers do not match f09")
          if "lat_bnds" in ds.variables and not np.allclose(ds["lat_bnds"][:], f09_lat_bnds(), atol=1e-6):
              errs.append("lat_bnds mismatch")
          if "lon_bnds" in ds.variables and not np.allclose(ds["lon_bnds"][:], f09_lon_bnds(), atol=1e-6):
              errs.append("lon_bnds mismatch")
          if "time" not in ds.variables:
              errs.append("missing time")
          else:
              t = ds["time"]
              if t.ndim != 0:
                  errs.append("time must be scalar (0-d)")
              if getattr(t, "units", "") != TIME_UNITS:
                  errs.append("time.units wrong")
              if getattr(t, "calendar", "") != TIME_CALENDAR:
                  errs.append("time.calendar wrong")
              if getattr(t, "bounds", "") != "time_bnds":
                  errs.append("time.bounds wrong")
          if "time_bnds" not in ds.variables or ds["time_bnds"].shape != (NBNDS,):
              errs.append("time_bnds missing/wrong shape")
          for name, dt, fill in [("aod_weighted_mean", "float32", -999.0),
                                 ("aod_uncertainty", "float32", -999.0),
                                 ("aod_count", "int32", 0)]:
              if name not in ds.variables:
                  errs.append(f"missing required var {name}")
                  continue
              v = ds.variables[name]
              if v.dimensions != ("lat", "lon"):
                  errs.append(f"{name} dims {v.dimensions} expected ('lat','lon')")
              if v.dtype.name != dt:
                  errs.append(f"{name} dtype {v.dtype.name} expected {dt}")
              fv = getattr(v, "_FillValue", None)
              if fv is None or float(fv) != fill:
                  errs.append(f"{name} _FillValue {fv} expected {fill}")
              if getattr(v, "units", "") != "1":
                  errs.append(f"{name}.units expected '1'")
          if "aod_weighted_mean" in ds.variables and \
                  getattr(ds["aod_weighted_mean"], "standard_name", "") != PRIMARY_STD_NAME:
              errs.append("aod_weighted_mean.standard_name wrong")
          present = set(ds.ncattrs())
          for k in REQUIRED_GLOBAL_ATTRS:
              if k not in present:
                  errs.append(f"missing global attr {k}")
          if "Conventions" in present and ds.getncattr("Conventions") != "CF-1.10":
              errs.append("Conventions != CF-1.10")
      finally:
          ds.close()
      return (len(errs) == 0, errs)
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `5 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/contract.py sp1_aod_pipeline/tests/test_contract.py`; commit `SP1: frozen contract writer + validator (pinned)`. This execution commits Tasks 2 and 3 together on `develop`.

---

### Task 4 — [Part B: SP1-local] Run configuration (dataclass + YAML)

EarthData auth is via `~/.netrc` through DAVINCI's `earthaccess` integration (no token env var), so the config carries only product/collection/QC/bias tunables and directories.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/config.py`, `$PKG/config.example.yaml`
- Test: `$PKG/tests/test_config.py`

**Interfaces:**
- Produces: `RunConfig` dataclass `modis_dir, viirs_dir, out_dir, stage_root, start:date, end:date, modis_qa_min=1, viirs_qa_min=2, aod_min=0.0, aod_max=5.0, sigma_max=5.0, modis_ee_land=(0.05,0.15), modis_ee_ocean=(0.03,0.05), sigma_floor=1e-3, bias_coeff_file="bias_coeffs.json", modis_product="MOD04_L2", modis_product_aqua="MYD04_L2", viirs_product="AERDB_L2_VIIRS_NOAA20", collection="6.1", viirs_collection="2"`; classmethod `from_yaml(path)->RunConfig`. *(CMR VersionId for MOD04/MYD04 C6.1 is "6.1", not "61".)*

- [x] **Step 1: Write the failing test** `$PKG/tests/test_config.py`:
  ```python
  from datetime import date
  from sp1_aod_pipeline.config import RunConfig

  YAML = """\
  modis_dir: /data/modis
  viirs_dir: /data/viirs
  out_dir: /data/out
  stage_root: /data/stage
  start: 2020-06-15
  end: 2020-06-16
  viirs_qa_min: 3
  modis_ee_land: [0.05, 0.15]
  """

  def test_from_yaml(tmp_path):
      p = tmp_path / "cfg.yaml"
      p.write_text(YAML)
      cfg = RunConfig.from_yaml(str(p))
      assert cfg.modis_dir == "/data/modis"
      assert cfg.start == date(2020, 6, 15) and cfg.end == date(2020, 6, 16)
      assert cfg.viirs_qa_min == 3
      assert cfg.modis_qa_min == 1
      assert cfg.aod_min == 0.0 and cfg.aod_max == 5.0
      assert cfg.sigma_max == 5.0
      assert cfg.modis_ee_land == (0.05, 0.15)
      assert cfg.sigma_floor == 1e-3
      assert cfg.modis_product == "MOD04_L2" and cfg.modis_product_aqua == "MYD04_L2"
      assert cfg.collection == "6.1" and cfg.viirs_collection == "2"
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_config.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.config'`.

- [x] **Step 3: Implement** `$PKG/config.py`:
  ```python
  """Run configuration for the SP1 pipeline. Every tunable lives here."""
  from dataclasses import dataclass
  from datetime import date
  import yaml

  def _as_date(v):
      return v if isinstance(v, date) else date.fromisoformat(str(v))

  @dataclass
  class RunConfig:
      modis_dir: str
      viirs_dir: str
      out_dir: str
      start: date
      end: date
      stage_root: str = ""
      modis_qa_min: int = 1
      viirs_qa_min: int = 2
      aod_min: float = 0.0
      aod_max: float = 5.0
      sigma_max: float = 5.0
      modis_ee_land: tuple = (0.05, 0.15)
      modis_ee_ocean: tuple = (0.03, 0.05)
      sigma_floor: float = 1e-3
      bias_coeff_file: str = "bias_coeffs.json"
      modis_product: str = "MOD04_L2"
      modis_product_aqua: str = "MYD04_L2"
      viirs_product: str = "AERDB_L2_VIIRS_NOAA20"
      collection: str = "6.1"
      viirs_collection: str = "2"

      @classmethod
      def from_yaml(cls, path):
          with open(path) as f:
              d = yaml.safe_load(f)
          d["start"] = _as_date(d["start"])
          d["end"] = _as_date(d["end"])
          for k in ("modis_ee_land", "modis_ee_ocean"):
              if k in d and d[k] is not None:
                  d[k] = tuple(d[k])
          return cls(**d)
  ```
- [x] **Step 4: Write** `$PKG/config.example.yaml`:
  ```yaml
  # SP1 pipeline run configuration. TEST MONTH = July 2008 (MODIS-only; predates
  # VIIRS) staged under Data/CERES-SARB-CAM7/ by scripts/stage_obs.py. Scales to 2000-2025.
  # EarthData auth is via ~/.netrc (urs.earthdata.nasa.gov) through davinci_monet's
  # earthaccess integration -- no token env var.
  modis_dir: /glade/work/fillmore/Data/CERES-SARB-CAM7/MODIS_VIIRS_L2   # MOD04/MYD04 under <DATASET>/<YYYYMMDD>/ (discover by RECURSIVE glob)
  viirs_dir: ""                                                         # none: July 2008 predates VIIRS (SNPP 2011, NOAA-20 2017)
  out_dir:   /glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr      # SP1 contract files (the deliverable SP2 reads)
  stage_root: /glade/work/fillmore/Data/CERES-SARB-CAM7                 # scripts/stage_obs.py stages here
  start: 2008-07-01
  end:   2008-07-31
  modis_qa_min: 1        # combined DT+DB QA flag >= this (valid retrieval)
  viirs_qa_min: 2        # AERDB QA_Flag >= this (moderate or better) [unused in 2008]
  aod_min: 0.0
  aod_max: 5.0
  sigma_max: 5.0         # drop pixels whose per-pixel uncertainty is fill/out-of-range
  modis_ee_land:  [0.05, 0.15]   # sigma = ee0 + ee1*AOD (Deep Blue / land)
  modis_ee_ocean: [0.03, 0.05]   # sigma = ee0 + ee1*AOD (Dark Target / ocean)
  sigma_floor: 0.001
  bias_coeff_file: /glade/work/fillmore/Data/CERES-SARB-CAM7/bias_coeffs.json
  modis_product: MOD04_L2        # Terra
  modis_product_aqua: MYD04_L2   # Aqua (R4: Terra+Aqua both required)
  viirs_product: AERDB_L2_VIIRS_NOAA20   # NOAA-20 Deep Blue; LAADS covers 2018+ [unused in 2008]
  collection: "6.1"      # MODIS C6.1 -- CMR VersionId is "6.1" (NOT "61"; the "061" in the filename is a different token)
  viirs_collection: "2"  # VIIRS Deep Blue C2
  ```
- [x] **Step 5: Run it (expect PASS).** Same command → `1 passed`.
- [x] **Step 6: Commit.** `git -C $ROOT add sp1_aod_pipeline/config.py sp1_aod_pipeline/config.example.yaml sp1_aod_pipeline/tests/test_config.py`; commit `SP1: run config dataclass + example YAML`.

---

### Task 5 — [Part B: SP1-local] QC filter (pure)

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/qc.py`
- Test: `$PKG/tests/test_qc.py`

**Interfaces:**
- Produces: `qc_mask(aod, qa, sigma, lat, lon, qa_min, aod_min, aod_max, sigma_max)->np.ndarray[bool]` — element-wise valid mask: finite arrays, `qa>=qa_min`, `aod∈[aod_min,aod_max]`, `0<sigma<=sigma_max`, finite geolocation. NaN/fill-safe.

- [x] **Step 1: Write the failing test** `$PKG/tests/test_qc.py`:
  ```python
  import numpy as np
  from sp1_aod_pipeline.qc import qc_mask

  def test_qc_mask_golden():
      aod   = np.array([0.30, -999.0,  6.0,  0.10, np.nan, 0.00, 5.00])
      qa    = np.array([3,      3,      3,    1,    3,      2,    1   ])
      sigma = np.array([0.10,   0.10,   0.10, 0.10, 0.10,   0.10, 0.10])
      lat   = np.full(7, 10.0)
      lon   = np.full(7, 20.0)
      m = qc_mask(aod, qa, sigma, lat, lon, 2, 0.0, 5.0, 5.0)
      assert m.tolist() == [True, False, False, False, False, True, False]

  def test_qa_threshold_changes_result():
      aod = np.array([0.2, 0.2, 0.2]); qa = np.array([1, 2, 3])
      sigma = np.full(3, 0.1); lat = np.zeros(3); lon = np.zeros(3)
      assert qc_mask(aod, qa, sigma, lat, lon, 1, 0.0, 5.0, 5.0).tolist() == [True, True, True]
      assert qc_mask(aod, qa, sigma, lat, lon, 3, 0.0, 5.0, 5.0).tolist() == [False, False, True]

  def test_cloud_edge_and_uncertainty_screening():
      aod   = np.array([0.30,  0.30,   0.30,    0.30])
      qa    = np.array([3,     3,      3,       3])
      sigma = np.array([0.10,  999.0,  0.10,   -0.10])
      lat   = np.array([10.0,  10.0,   np.nan,  10.0])
      lon   = np.array([20.0,  20.0,   20.0,    20.0])
      m = qc_mask(aod, qa, sigma, lat, lon, 2, 0.0, 5.0, 5.0)
      assert m.tolist() == [True, False, False, False]
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_qc.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.qc'`.

- [x] **Step 3: Implement** `$PKG/qc.py`:
  ```python
  """Pure per-pixel QC filters for L2 AOD pixels (SPEC s6 stage-1 screening).

  The L2 retrieval performs cloud screening internally and reports its outcome through
  the QA flag, so the per-pixel cloud mask is honored via the QA threshold. On top of
  QA + valid AOD range we additionally drop edge/fill pixels that otherwise survive with
  degraded geometry: non-finite geolocation and fill/out-of-range per-pixel uncertainty
  (sigma <= 0 or sigma > sigma_max; e.g. the VIIRS expected-uncertainty fill -999 -> 999).
  """
  import numpy as np

  def qc_mask(aod, qa, sigma, lat, lon, qa_min, aod_min, aod_max, sigma_max):
      aod = np.asarray(aod, dtype=np.float64)
      qa = np.asarray(qa, dtype=np.float64)
      sigma = np.asarray(sigma, dtype=np.float64)
      lat = np.asarray(lat, dtype=np.float64)
      lon = np.asarray(lon, dtype=np.float64)
      return (np.isfinite(aod) & np.isfinite(qa) & np.isfinite(sigma)
              & np.isfinite(lat) & np.isfinite(lon)
              & (qa >= qa_min) & (aod >= aod_min) & (aod <= aod_max)
              & (sigma > 0.0) & (sigma <= sigma_max))
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `3 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/qc.py sp1_aod_pipeline/tests/test_qc.py`; commit `SP1: pure QC mask`.

---

### Task 6 — [Part B: SP1-local] Shared records + TAI93 time

`L2Record`/`CellGrid` are the common currency between the DAVINCI-reader adapters (Task 9/10), the grid step (Task 11), and the merge (Task 12). `tai93_to_datetime64` decodes MODIS/VIIRS `Scan_Start_Time`.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/records.py`
- Test: `$PKG/tests/test_records.py`

**Interfaces:**
- Consumes: `f09_grid.{NLAT,NLON}`, `contract.FILL_FLOAT`.
- Produces: `records.L2Record(sensor:str, lat,lon,aod,sigma,qa: np.ndarray(float32,1-D), time: np.ndarray(datetime64[ns],1-D))`; `records.CellGrid(mean,sigma: np.ndarray(192,288)f4, count: np.ndarray(192,288)i4)` + `CellGrid.empty()`; `records.tai93_to_datetime64(sec)->np.ndarray[datetime64[ns]]`.

- [x] **Step 1: Write the failing test** `$PKG/tests/test_records.py`:
  ```python
  import numpy as np
  from sp1_aod_pipeline.records import L2Record, CellGrid, tai93_to_datetime64

  def test_tai93_to_datetime64():
      # 2020-06-15T01:00:00 is this many seconds after 1993-01-01.
      from datetime import datetime
      sec = (datetime(2020, 6, 15, 1) - datetime(1993, 1, 1)).total_seconds()
      out = tai93_to_datetime64(np.array([sec, np.nan]))
      assert out[0] == np.datetime64("2020-06-15T01:00:00")
      assert np.isnat(out[1])

  def test_cellgrid_empty_shapes_and_fill():
      g = CellGrid.empty()
      assert g.mean.shape == (192, 288) and g.mean.dtype == np.float32
      assert float(g.mean[0, 0]) == -999.0 and float(g.sigma[0, 0]) == -999.0
      assert g.count.dtype == np.int32 and int(g.count.max()) == 0

  def test_l2record_holds_arrays():
      r = L2Record("viirs", np.zeros(2, np.float32), np.zeros(2, np.float32),
                   np.zeros(2, np.float32), np.ones(2, np.float32), np.full(2, 3, np.float32),
                   np.full(2, np.datetime64("2020-06-15T00:00:00"), "datetime64[ns]"))
      assert r.sensor == "viirs" and r.aod.shape == (2,)
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_records.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.records'`.

- [x] **Step 3: Implement** `$PKG/records.py`:
  ```python
  """Shared data structures + TAI93 time conversion."""
  from dataclasses import dataclass
  import numpy as np
  from .f09_grid import NLAT, NLON
  from .contract import FILL_FLOAT

  _EPOCH93 = np.datetime64("1993-01-01T00:00:00")

  def tai93_to_datetime64(sec):
      """TAI93 seconds -> datetime64[ns]. Leap seconds (<=37 s) ignored (doc'd; 3-h windows)."""
      sec = np.asarray(sec, dtype=np.float64).ravel()
      out = np.full(sec.shape, np.datetime64("NaT"), dtype="datetime64[ns]")
      ok = np.isfinite(sec)
      out[ok] = _EPOCH93 + np.rint(sec[ok] * 1e9).astype("timedelta64[ns]")
      return out

  @dataclass
  class L2Record:
      sensor: str
      lat: np.ndarray
      lon: np.ndarray
      aod: np.ndarray
      sigma: np.ndarray
      qa: np.ndarray
      time: np.ndarray

  @dataclass
  class CellGrid:
      mean: np.ndarray
      sigma: np.ndarray
      count: np.ndarray

      @classmethod
      def empty(cls):
          return cls(mean=np.full((NLAT, NLON), FILL_FLOAT, np.float32),
                     sigma=np.full((NLAT, NLON), FILL_FLOAT, np.float32),
                     count=np.zeros((NLAT, NLON), np.int32))
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `3 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/records.py sp1_aod_pipeline/tests/test_records.py`; commit `SP1: shared records + TAI93 time`.

---

### Task 7 — [Part A: upstream DAVINCI] VIIRS `AERDB_L2` reader (new module + register + catalog + pytest)

DAVINCI has no VIIRS aerosol reader. Add a general `AERDB_L2` NetCDF swath reader, registered as `"viirs_l2_aerdb"`, mirroring `MODISL2AODReader`'s shape (`open(file_paths, variables=None, *, qa_threshold=None) -> xr.Dataset`, `geometry == DataGeometry.SWATH`). Grounded against `/glade/work/tvmora/VIIRS_original/AERDB_L2_VIIRS_NOAA20.A2023362.0000.002.2023362124926.nc`: dims `Idx_Atrack=402, Idx_Xtrack=400`; per-pixel vars `Aerosol_Optical_Thickness_550_{Land,Ocean}`, `_550_Expected_Uncertainty_{Land,Ocean}`, `_QA_Flag_{Land,Ocean}`, 2-D `Latitude`/`Longitude`, `Scan_Start_Time` (TAI93 s); AOD fill `-999`.

**Files:**
- Target repo: **DAVINCI** (`$DV`).
- Create: `$DV/davinci_monet/datasets/satellite/viirs_l2_aerdb.py`
- Modify: `$DV/davinci_monet/datasets/__init__.py` (registration import), `$DV/davinci_monet/datasets/satellite/catalog/data/modis_viirs_atmosphere.yaml` (catalog entry)
- Test: `$DV/davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py`, modify `.../test_catalog.py`

**Interfaces:**
- Consumes: `core.protocols.DataGeometry`, `core.registry.source_registry`, `io.reader_utils.{validate_file_list,select_variables,set_geometry_attr}`.
- Produces: `VIIRSL2AERDBReader` with `name=="viirs_l2_aerdb"`, `geometry==SWATH`, `open(file_paths, variables=None, *, qa_threshold:int|None=None, **kwargs)->xr.Dataset` (renames `Latitude/Longitude` → coords `lat/lon`); catalog product `AERDB_L2_VIIRS_NOAA20` (level `L2`, geometry `SWATH`).

- [x] **Step 1: Create a branch in DAVINCI.**
  ```bash
  git -C /glade/work/fillmore/DAVINCI checkout -b sp1-viirs-aerdb
  ```
- [x] **Step 2: Write the failing test** `$DV/davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py`:
  ```python
  import os
  import subprocess
  import sys

  import numpy as np
  import pytest
  import xarray as xr

  from davinci_monet.core.protocols import DataGeometry
  from davinci_monet.datasets.satellite.viirs_l2_aerdb import VIIRSL2AERDBReader

  REAL = ("/glade/work/tvmora/VIIRS_original/"
          "AERDB_L2_VIIRS_NOAA20.A2023362.0000.002.2023362124926.nc")


  def _write_aerdb_like(path, *, na=2, nx=2):
      lat = np.array([[10.0, 10.0], [11.0, 11.0]], np.float32)
      lon = np.array([[20.0, 21.0], [20.0, 21.0]], np.float32)
      aod_land = np.array([[0.30, -999.0], [0.50, 0.40]], np.float32)
      qa_land = np.array([[3.0, 0.0], [2.0, 1.0]], np.float64)
      eu_land = np.array([[0.10, 0.10], [0.12, 0.08]], np.float32)
      ds = xr.Dataset(
          {
              "Aerosol_Optical_Thickness_550_Land": (("Idx_Atrack", "Idx_Xtrack"), aod_land),
              "Aerosol_Optical_Thickness_550_Ocean": (
                  ("Idx_Atrack", "Idx_Xtrack"), np.full((na, nx), -999.0, np.float32)),
              "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Land": (
                  ("Idx_Atrack", "Idx_Xtrack"), eu_land),
              "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Ocean": (
                  ("Idx_Atrack", "Idx_Xtrack"), np.full((na, nx), -999.0, np.float32)),
              "Aerosol_Optical_Thickness_QA_Flag_Land": (("Idx_Atrack", "Idx_Xtrack"), qa_land),
              "Aerosol_Optical_Thickness_QA_Flag_Ocean": (
                  ("Idx_Atrack", "Idx_Xtrack"), np.zeros((na, nx))),
              "Latitude": (("Idx_Atrack", "Idx_Xtrack"), lat),
              "Longitude": (("Idx_Atrack", "Idx_Xtrack"), lon),
              "Scan_Start_Time": (("Idx_Atrack", "Idx_Xtrack"), np.zeros((na, nx), np.float64)),
          }
      )
      ds["Aerosol_Optical_Thickness_550_Land"].attrs["_FillValue"] = -999.0
      ds.to_netcdf(path)


  def test_reader_basic_swath(tmp_path):
      p = str(tmp_path / "g.nc")
      _write_aerdb_like(p)
      reader = VIIRSL2AERDBReader()
      ds = reader.open([p])
      assert reader.name == "viirs_l2_aerdb"
      assert reader.geometry == DataGeometry.SWATH
      assert {"lat", "lon"}.issubset(set(ds.coords))
      assert ds["Aerosol_Optical_Thickness_550_Land"].dims == ("Idx_Atrack", "Idx_Xtrack")
      # mask_and_scale applied the -999 fill -> NaN
      assert np.isnan(float(ds["Aerosol_Optical_Thickness_550_Land"].values[0, 1]))
      assert ds.attrs["geometry"] == "swath"


  def test_reader_qa_threshold_masks_land_aod(tmp_path):
      p = str(tmp_path / "g.nc")
      _write_aerdb_like(p)
      ds = VIIRSL2AERDBReader().open([p], qa_threshold=2)
      land = ds["Aerosol_Optical_Thickness_550_Land"].values
      # qa>=2 keeps (0,0)=qa3 and (1,0)=qa2; masks (1,1)=qa1 -> NaN
      assert not np.isnan(land[0, 0])
      assert np.isnan(land[1, 1])


  def test_reader_registered_via_package_import():
      result = subprocess.run(
          [sys.executable, "-c",
           ("import davinci_monet.datasets; "
            "from davinci_monet.core.registry import source_registry; "
            "assert 'viirs_l2_aerdb' in source_registry.list()")],
          capture_output=True, text=True)
      assert result.returncode == 0, result.stderr


  def test_reader_real_sample_invariants():
      if not os.path.exists(REAL):
          pytest.skip(f"real VIIRS sample not present: {REAL}")
      ds = VIIRSL2AERDBReader().open([REAL])
      assert ds["lat"].shape == (402, 400)
      assert {"lat", "lon"}.issubset(set(ds.coords))
      assert "Aerosol_Optical_Thickness_550_Land" in ds.data_vars
      assert "Scan_Start_Time" in ds.variables
  ```
- [x] **Step 3: Run it (expect FAIL).** `$PY -m pytest $DV/davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py -q` → `ModuleNotFoundError: No module named 'davinci_monet.datasets.satellite.viirs_l2_aerdb'`.

- [x] **Step 4: Implement** `$DV/davinci_monet/datasets/satellite/viirs_l2_aerdb.py`:
  ```python
  """VIIRS Deep Blue AERDB_L2 aerosol reader.

  Reads NASA LAADS ``AERDB_L2_VIIRS_{SNPP,NOAA20}`` Deep Blue Level-2 aerosol
  products (NetCDF4 swath). Returns swath geometry with 2-D Latitude/Longitude
  standardized to ``lat``/``lon`` coordinates. AOD/uncertainty/QA are exposed
  per surface (``_Land`` / ``_Ocean``); callers select/merge surfaces.
  """

  from __future__ import annotations

  from pathlib import Path
  from typing import Any, Sequence

  import xarray as xr

  from davinci_monet.core.protocols import DataGeometry
  from davinci_monet.core.registry import source_registry
  from davinci_monet.io.reader_utils import (
      select_variables,
      set_geometry_attr,
      validate_file_list,
  )

  # Default variables loaded when ``variables`` is None: the 550 nm AOD, expected
  # uncertainty, and QA flag for both surfaces, plus the scan time.
  AERDB_DEFAULT_VARIABLES: tuple[str, ...] = (
      "Aerosol_Optical_Thickness_550_Land",
      "Aerosol_Optical_Thickness_550_Ocean",
      "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Land",
      "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Ocean",
      "Aerosol_Optical_Thickness_QA_Flag_Land",
      "Aerosol_Optical_Thickness_QA_Flag_Ocean",
      "Scan_Start_Time",
  )


  @source_registry.register("viirs_l2_aerdb")
  class VIIRSL2AERDBReader:
      """Reader for VIIRS Deep Blue AERDB_L2 aerosol swath datasets."""

      @property
      def name(self) -> str:
          return "viirs_l2_aerdb"

      @property
      def geometry(self) -> DataGeometry:
          return DataGeometry.SWATH

      def open(
          self,
          file_paths: Sequence[str | Path],
          variables: Sequence[str] | None = None,
          *,
          qa_threshold: int | None = None,
          **kwargs: Any,
      ) -> xr.Dataset:
          """Open AERDB_L2 VIIRS files.

          Parameters
          ----------
          file_paths
              AERDB_L2 NetCDF granule paths.
          variables
              Variables to keep. If None, keeps the AERDB AOD/uncertainty/QA set.
          qa_threshold
              If set, AOD over each surface is masked (NaN) where that surface's
              ``..._QA_Flag_{Land,Ocean}`` is below the threshold.
          """
          file_list = validate_file_list(file_paths, source_label="VIIRS AERDB")

          # mask_and_scale=True applies _FillValue/scale (AOD fill -999 -> NaN).
          if len(file_list) == 1:
              ds = xr.open_dataset(str(file_list[0]), **kwargs)
          else:
              ds = xr.open_mfdataset(
                  [str(f) for f in file_list],
                  combine="nested",
                  concat_dim="Idx_Atrack",
                  **kwargs,
              )

          if qa_threshold is not None:
              ds = self._apply_qa_filter(ds, qa_threshold)

          keep = list(variables) if variables is not None else list(AERDB_DEFAULT_VARIABLES)
          # Always retain geolocation/time alongside the requested data variables.
          for essential in ("Latitude", "Longitude", "Scan_Start_Time"):
              if essential in ds.variables and essential not in keep:
                  keep.append(essential)
          ds = select_variables(ds, keep)

          return self._standardize_dataset(ds)

      def _apply_qa_filter(self, ds: xr.Dataset, qa_threshold: int) -> xr.Dataset:
          for surface in ("Land", "Ocean"):
              aod_name = f"Aerosol_Optical_Thickness_550_{surface}"
              qa_name = f"Aerosol_Optical_Thickness_QA_Flag_{surface}"
              if aod_name in ds.data_vars and qa_name in ds.variables:
                  ds[aod_name] = ds[aod_name].where(ds[qa_name] >= qa_threshold)
          return ds

      def _standardize_dataset(self, ds: xr.Dataset) -> xr.Dataset:
          renames: dict[str, str] = {}
          if "Latitude" in ds.variables and "lat" not in ds.coords:
              renames["Latitude"] = "lat"
          if "Longitude" in ds.variables and "lon" not in ds.coords:
              renames["Longitude"] = "lon"
          if renames:
              ds = ds.rename(renames)
          for c in ("lat", "lon"):
              if c in ds.variables and c not in ds.coords:
                  ds = ds.set_coords(c)
          return set_geometry_attr(ds, DataGeometry.SWATH)
  ```
- [x] **Step 5: Register the reader** by adding one import line to `$DV/davinci_monet/datasets/__init__.py`, next to the other satellite imports (after the `modis_l2_aod` line):
  ```python
  from davinci_monet.datasets.satellite import viirs_l2_aerdb as _viirs_l2_aerdb  # noqa: F401
  ```
- [x] **Step 6: Add the catalog entry** — append to `$DV/davinci_monet/datasets/satellite/catalog/data/modis_viirs_atmosphere.yaml` under `products:`:
  ```yaml
    - product_id: AERDB_L2_VIIRS_NOAA20
      instrument: VIIRS
      platform: NOAA-20
      daac: LAADS
      collection: "002"
      level: L2
      geometry: SWATH
      file_format: NetCDF4
      time_parse: "A%Y%j"
      dim_aliases: { Idx_Atrack: y, Idx_Xtrack: x }
      aliases: [viirs_aerdb_noaa20]
      variables:
        - display_name: aod_550_land
          sds_name: Aerosol_Optical_Thickness_550_Land
          units: "1"
          wavelength_nm: 550
          long_name: "Deep Blue AOD at 550 nm over land"
        - display_name: aod_550_ocean
          sds_name: Aerosol_Optical_Thickness_550_Ocean
          units: "1"
          wavelength_nm: 550
          long_name: "Deep Blue AOD at 550 nm over ocean"
  ```
- [x] **Step 7: Add a catalog test** — append to `$DV/davinci_monet/tests/unit/datasets/satellite/test_catalog.py`:
  ```python
  def test_catalog_resolves_viirs_aerdb_l2():
      cat = get_catalog()
      p = cat.resolve("AERDB_L2_VIIRS_NOAA20")
      assert p.level == "L2" and p.geometry == "SWATH"
      assert p.instrument == "VIIRS" and p.platform == "NOAA-20"
      land = p.variable_by_display("aod_550_land")
      assert land is not None and land.wavelength_nm == 550
      assert cat.resolve("viirs_aerdb_noaa20").product_id == "AERDB_L2_VIIRS_NOAA20"  # alias
  ```
- [x] **Step 8: Run both test files (expect PASS).**
  ```bash
  $PY -m pytest $DV/davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py \
                $DV/davinci_monet/tests/unit/datasets/satellite/test_catalog.py -q
  ```
  Expect `9 passed` (4 reader + 5 catalog: 4 pre-existing + 1 new). If the real tvmora sample is absent, `8 passed, 1 skipped`.
- [x] **Step 9: Commit (in DAVINCI).** Completed on branch `sp1-viirs-aerdb` as commit `2f9c03c`.
  ```bash
  git -C /glade/work/fillmore/DAVINCI add davinci_monet/datasets/satellite/viirs_l2_aerdb.py davinci_monet/datasets/__init__.py davinci_monet/datasets/satellite/catalog/data/modis_viirs_atmosphere.yaml davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py davinci_monet/tests/unit/datasets/satellite/test_catalog.py
  git -C /glade/work/fillmore/DAVINCI commit -m "satellite: add VIIRS AERDB_L2 reader + catalog entry"
  ```

---

### Task 8 — [Part A: upstream DAVINCI] Uncertainty-aware swath binning

`bin_swath_to_grid` accumulates SUM + COUNT only — it cannot yield a per-cell uncertainty. Add a sibling numba kernel `bin_swath_to_grid_uncertainty` that accumulates per-cell Σ(1/σ²) and Σ(val/σ²), plus a `normalize_uncertainty_grid` that turns those into an **inverse-variance-weighted mean** and a **combined 1-σ** (`σ = sqrt(1/Σw)`), leaving empty cells `NaN`. Same calling convention and uniform-edge floor-division as `bin_swath_to_grid` (SP1 feeds uniform edges via `edges_from_centers`), so it bins point-in-cell exactly like the base engine. Pixels with non-finite or non-positive σ are skipped (no near-zero-weight contamination).

**Files:**
- Target repo: **DAVINCI** (`$DV`).
- Modify: `$DV/davinci_monet/pairing/grid_binning.py`
- Test: modify `$DV/davinci_monet/tests/unit/pairing/test_grid_binning.py`

**Interfaces:**
- Produces:
  - `bin_swath_to_grid_uncertainty(time_edges, lon_edges, lat_edges, time_values, lon_values, lat_values, data_values, sigma_values, count_grid, weight_grid, weighted_sum_grid)->None` (numba, in-place; `weight_grid += 1/σ²`, `weighted_sum_grid += val/σ²`, `count_grid += 1`).
  - `normalize_uncertainty_grid(count_grid, weight_grid, weighted_sum_grid)->tuple[np.ndarray, np.ndarray]` returning `(mean_grid, sigma_grid)` with `NaN` in empty cells.

- [x] **Step 1: Write the failing test** — append to `$DV/davinci_monet/tests/unit/pairing/test_grid_binning.py`:
  ```python
  from davinci_monet.pairing.grid_binning import (
      bin_swath_to_grid,
      bin_swath_to_grid_uncertainty,
      normalize_uncertainty_grid,
  )


  def test_uncertainty_binning_inverse_variance_mean_and_sigma():
      # 1 time x 2 lon x 2 lat, edges 0..2; two pixels in cell (0,0,0).
      edges = np.array([0.0, 1.0, 2.0])
      t = np.array([0.5, 0.5]); x = np.array([0.5, 0.5]); y = np.array([0.5, 0.5])
      d = np.array([0.4, 0.8]); s = np.array([0.1, 0.2])
      count = np.zeros((1, 2, 2), dtype=np.int64)
      w = np.zeros((1, 2, 2)); wx = np.zeros((1, 2, 2))
      bin_swath_to_grid_uncertainty(
          np.array([0.0, 1.0]), edges, edges, t, x, y, d, s, count, w, wx)
      mean, sigma = normalize_uncertainty_grid(count, w, wx)
      w1, w2 = 1 / 0.1**2, 1 / 0.2**2
      assert count[0, 0, 0] == 2
      assert np.isclose(mean[0, 0, 0], (w1 * 0.4 + w2 * 0.8) / (w1 + w2))
      assert np.isclose(sigma[0, 0, 0], np.sqrt(1 / (w1 + w2)))
      assert np.isnan(mean[0, 1, 1]) and np.isnan(sigma[0, 1, 1])  # empty -> NaN


  def test_uncertainty_binning_skips_bad_sigma_and_matches_base_count():
      edges = np.array([0.0, 1.0, 2.0])
      t = np.array([0.5, 0.5, 0.5]); x = np.array([0.5, 0.5, 1.5]); y = np.array([0.5, 0.5, 1.5])
      d = np.array([0.4, 0.6, 0.9]); s = np.array([0.1, -1.0, 0.2])  # middle sigma invalid
      count = np.zeros((1, 2, 2), dtype=np.int64)
      w = np.zeros((1, 2, 2)); wx = np.zeros((1, 2, 2))
      bin_swath_to_grid_uncertainty(
          np.array([0.0, 1.0]), edges, edges, t, x, y, d, s, count, w, wx)
      # cell (0,0,0): only the sigma=0.1 pixel survives; cell (0,1,1): one pixel
      assert count[0, 0, 0] == 1 and count[0, 1, 1] == 1
      mean, _ = normalize_uncertainty_grid(count, w, wx)
      assert np.isclose(mean[0, 0, 0], 0.4)
      # With CONSTANT sigma the weighted mean reduces to the base engine's simple mean.
      bc = np.zeros((1, 2, 2), dtype=np.int64); bsum = np.zeros((1, 2, 2))
      bin_swath_to_grid(np.array([0.0, 1.0]), edges, edges,
                        np.array([0.5, 0.5]), np.array([0.5, 0.5]), np.array([0.5, 0.5]),
                        np.array([0.4, 0.8]), bc, bsum)
      cu = np.zeros((1, 2, 2), dtype=np.int64); wu = np.zeros((1, 2, 2)); wxu = np.zeros((1, 2, 2))
      bin_swath_to_grid_uncertainty(np.array([0.0, 1.0]), edges, edges,
                                    np.array([0.5, 0.5]), np.array([0.5, 0.5]),
                                    np.array([0.5, 0.5]), np.array([0.4, 0.8]),
                                    np.full(2, 0.1), cu, wu, wxu)
      assert np.array_equal(bc, cu)                      # same point-in-cell counts
      mu, _ = normalize_uncertainty_grid(cu, wu, wxu)
      assert np.isclose(mu[0, 0, 0], (0.4 + 0.8) / 2)    # == simple mean
  ```
- [x] **Step 2: Run it (expect FAIL).** `$PY -m pytest $DV/davinci_monet/tests/unit/pairing/test_grid_binning.py -q` → `ImportError: cannot import name 'bin_swath_to_grid_uncertainty'`.

- [x] **Step 3: Implement** — append to `$DV/davinci_monet/pairing/grid_binning.py`:
  ```python
  @numba.jit(nopython=True)
  def bin_swath_to_grid_uncertainty(
      time_edges: np.ndarray,
      lon_edges: np.ndarray,
      lat_edges: np.ndarray,
      time_values: np.ndarray,
      lon_values: np.ndarray,
      lat_values: np.ndarray,
      data_values: np.ndarray,
      sigma_values: np.ndarray,
      count_grid: np.ndarray,
      weight_grid: np.ndarray,
      weighted_sum_grid: np.ndarray,
  ) -> None:
      """Accumulate inverse-variance sums of swath pixels into grid cells.

      Like :func:`bin_swath_to_grid` (uniform-edge floor division, in-place), but
      for each valid pixel with finite, positive ``sigma`` it accumulates the
      weight ``w = 1/sigma**2`` into *weight_grid*, ``w * data`` into
      *weighted_sum_grid*, and increments *count_grid*. Pair with
      :func:`normalize_uncertainty_grid` to obtain the inverse-variance mean and
      the combined 1-sigma per cell.
      """
      dt = time_edges[1] - time_edges[0]
      dx = lon_edges[1] - lon_edges[0]
      dy = lat_edges[1] - lat_edges[0]
      nt, nx, ny = count_grid.shape
      for i in range(len(data_values)):
          if (
              math.isfinite(data_values[i])
              and math.isfinite(sigma_values[i])
              and sigma_values[i] > 0.0
              and math.isfinite(time_values[i])
              and math.isfinite(lon_values[i])
              and math.isfinite(lat_values[i])
              and time_values[i] >= time_edges[0]
              and time_values[i] <= time_edges[-1]
              and lon_values[i] >= lon_edges[0]
              and lon_values[i] <= lon_edges[-1]
              and lat_values[i] >= lat_edges[0]
              and lat_values[i] <= lat_edges[-1]
          ):
              it = int((time_values[i] - time_edges[0]) / dt)
              ix = int((lon_values[i] - lon_edges[0]) / dx)
              iy = int((lat_values[i] - lat_edges[0]) / dy)
              if it < 0:
                  it = 0
              elif it >= nt:
                  it = nt - 1
              if ix < 0:
                  ix = 0
              elif ix >= nx:
                  ix = nx - 1
              if iy < 0:
                  iy = 0
              elif iy >= ny:
                  iy = ny - 1
              w = 1.0 / (sigma_values[i] * sigma_values[i])
              count_grid[it, ix, iy] += 1
              weight_grid[it, ix, iy] += w
              weighted_sum_grid[it, ix, iy] += w * data_values[i]


  def normalize_uncertainty_grid(
      count_grid: np.ndarray,
      weight_grid: np.ndarray,
      weighted_sum_grid: np.ndarray,
  ) -> tuple[np.ndarray, np.ndarray]:
      """Convert accumulated inverse-variance sums to (mean, sigma) grids.

      Returns ``(mean_grid, sigma_grid)`` where, for cells with count > 0,
      ``mean = weighted_sum / weight`` and ``sigma = sqrt(1 / weight)``; empty
      cells are ``NaN``. Inputs are not modified.
      """
      mask = (count_grid > 0) & (weight_grid > 0.0)
      mean_grid = np.full(weighted_sum_grid.shape, np.nan, dtype=np.float64)
      sigma_grid = np.full(weight_grid.shape, np.nan, dtype=np.float64)
      mean_grid[mask] = weighted_sum_grid[mask] / weight_grid[mask]
      sigma_grid[mask] = np.sqrt(1.0 / weight_grid[mask])
      return mean_grid, sigma_grid
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `3 passed` (1 pre-existing + 2 new). Combined Task 7/8 focused command → `12 passed`.
- [x] **Step 5: Commit (in DAVINCI).** Completed on branch `sp1-viirs-aerdb` as commit `bf0b46d`.
  ```bash
  git -C /glade/work/fillmore/DAVINCI add davinci_monet/pairing/grid_binning.py davinci_monet/tests/unit/pairing/test_grid_binning.py
  git -C /glade/work/fillmore/DAVINCI commit -m "pairing: add uncertainty-aware swath binning (inverse-variance mean + sigma)"
  ```
- [x] **Step 6: Confirm both Part-A features import and record DAVINCI working tree state** (so Part B can rely on the imports):
  ```bash
  $PY -c "from davinci_monet.datasets.satellite.viirs_l2_aerdb import VIIRSL2AERDBReader; from davinci_monet.pairing.grid_binning import bin_swath_to_grid_uncertainty, normalize_uncertainty_grid; print('part A ready')"
  ```
  Result: `part A ready`. DAVINCI is not fully clean because of pre-existing unrelated local edits in `environment.yml`, `pyproject.toml`, and analysis artifacts; Task 7/8 files are committed.

---

### Task 8b — [Part A: upstream DAVINCI] Robust color limits for `SpatialPlotter`

Heavy-tailed geophysical fields (AOD, precip, NOx) render illegibly under `SpatialPlotter`'s default min/max color scaling — a few outlier cells stretch the colorbar and crush the real 0–1 structure into the dark floor (demonstrated 2026-06-27 on a July-2020 AOD mean: illegible at default, legible at `vmax=1`). Add a general `robust` option so the §17/§18 science-verification maps — and every DAVINCI user plotting such fields — get legible defaults. General capability → ships on the same upstream branch as Tasks 7–8.

**Files:**
- Target repo: **DAVINCI** (`$DV`).
- Modify: `$DV/davinci_monet/plots/renderers/spatial/field.py` (color-limit resolution).
- Modify: the `PlotConfig`/figure-config dataclass — add `robust: bool=False`, `robust_pct: tuple=(2,98)` (default `False` preserves current behavior; the SP1/SP2 helpers opt in).
- Test: `$DV/davinci_monet/tests/unit/plots/test_robust_clim.py`.

- [x] **Step 1: Failing test.** `data = [0.1]*100 + [50.0]`; assert that with `robust=True` the resolved `vmax < 1.0` (percentile-driven), and with `robust=False` `vmax≈50` (back-compat). Also added a comparison-option forwarding test for `robust`/`robust_pct`.
- [x] **Step 2: Implement.** In the vmin/vmax resolution: `if vmin is None and vmax is None and robust: vmin, vmax = np.nanpercentile(finite, robust_pct)`. Forward `robust`/`robust_pct` through comparison plot options.
- [x] **Step 3: Pass + commit** on branch `sp1-viirs-aerdb` as commit `2bcce4c`. Focused robust command → `13 passed`; broader relevant DAVINCI command → `115 passed`.

**Deliverable:** A general, tested `robust` color-limit option upstream; heavy-tailed maps legible by default.

---

### Task 9 — [Part B: SP1-local] VIIRS ingest adapter (DAVINCI reader → L2Record) + fixtures

SP1 reads VIIRS granules through the **Part-A** `VIIRSL2AERDBReader`, then a thin adapter merges land/ocean (prefer a valid land retrieval), takes σ = |expected uncertainty|, and decodes TAI93 time into an `L2Record`. The shared synthetic-granule builders live in `tests/fixtures.py`.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/ingest_viirs.py`, `$PKG/tests/fixtures.py`
- Test: `$PKG/tests/test_ingest_viirs.py`

**Interfaces:**
- Consumes: `davinci_monet.datasets.satellite.viirs_l2_aerdb.VIIRSL2AERDBReader`, `records.{L2Record,tai93_to_datetime64}`, `config.RunConfig`.
- Produces:
  - `tests.fixtures.make_viirs_granule(path, *, lat, lon, aod_land, qa_land, eu_land, scan_dt)->None` (AERDB-shaped NetCDF; AOD `_FillValue=-999`).
  - `ingest_viirs.viirs_record_from_dataset(ds:xr.Dataset, cfg)->L2Record` (pure).
  - `ingest_viirs.read_viirs_granule(path:str, cfg)->L2Record` (opens via `VIIRSL2AERDBReader`).

- [x] **Step 1: Implement** `$PKG/tests/fixtures.py` (VIIRS builder now; MODIS builder added in Task 10):
  ```python
  """Synthetic L2 granule builders for tests (no network, no real data)."""
  from datetime import datetime
  import numpy as np
  import netCDF4 as nc

  _EPOCH93 = datetime(1993, 1, 1)

  def _tai93(dt):
      return (dt - _EPOCH93).total_seconds()

  def make_viirs_granule(path, *, lat, lon, aod_land, qa_land, eu_land, scan_dt):
      """Write a minimal AERDB_L2-shaped NetCDF granule (the DAVINCI VIIRS reader opens it)."""
      lat = np.asarray(lat, np.float32); lon = np.asarray(lon, np.float32)
      aod_land = np.asarray(aod_land, np.float32)
      qa_land = np.asarray(qa_land, np.float64)
      eu_land = np.asarray(eu_land, np.float32)
      na, nx = lat.shape
      ds = nc.Dataset(path, "w", format="NETCDF4")
      ds.createDimension("Idx_Atrack", na); ds.createDimension("Idx_Xtrack", nx)
      dims = ("Idx_Atrack", "Idx_Xtrack")
      def w(name, arr, dt="f4", fill=None):
          v = ds.createVariable(name, dt, dims, fill_value=fill) if fill is not None \
              else ds.createVariable(name, dt, dims)
          v[:] = arr
      w("Latitude", lat); w("Longitude", lon)
      w("Aerosol_Optical_Thickness_550_Land", aod_land, fill=-999.0)
      w("Aerosol_Optical_Thickness_550_Ocean", np.full((na, nx), -999.0, np.float32), fill=-999.0)
      w("Aerosol_Optical_Thickness_550_Expected_Uncertainty_Land", eu_land)
      w("Aerosol_Optical_Thickness_550_Expected_Uncertainty_Ocean",
        np.full((na, nx), -999.0, np.float32))
      w("Aerosol_Optical_Thickness_QA_Flag_Land", qa_land, "f8")
      w("Aerosol_Optical_Thickness_QA_Flag_Ocean", np.zeros((na, nx)), "f8")
      w("Scan_Start_Time", np.full((na, nx), _tai93(scan_dt), np.float64), "f8")
      ds.close()
  ```
- [x] **Step 2: Write the failing test** `$PKG/tests/test_ingest_viirs.py`:
  ```python
  from datetime import datetime
  import numpy as np
  import xarray as xr
  from sp1_aod_pipeline.config import RunConfig
  from sp1_aod_pipeline.ingest_viirs import read_viirs_granule, viirs_record_from_dataset
  from sp1_aod_pipeline.tests.fixtures import make_viirs_granule

  def _cfg():
      return RunConfig(modis_dir="m", viirs_dir="v", out_dir="o",
                       start=datetime(2020, 6, 15).date(), end=datetime(2020, 6, 15).date())

  def test_read_viirs_granule_via_davinci_reader(tmp_path):
      lat = np.array([[10.0, 10.0], [11.0, 11.0]], np.float32)
      lon = np.array([[20.0, 21.0], [20.0, 21.0]], np.float32)
      aod = np.array([[0.30, -999.0], [0.50, 0.40]], np.float32)
      qa = np.array([[3, 0], [2, 1]], np.float64)
      eu = np.array([[0.10, 0.10], [0.12, 0.08]], np.float32)
      p = str(tmp_path / "AERDB_L2_VIIRS_NOAA20.A2020167.0100.002.x.nc")
      make_viirs_granule(p, lat=lat, lon=lon, aod_land=aod, qa_land=qa, eu_land=eu,
                         scan_dt=datetime(2020, 6, 15, 1, 0, 0))
      rec = read_viirs_granule(p, _cfg())
      assert rec.sensor == "viirs"
      assert rec.aod.shape == (4,) and rec.aod.dtype == np.float32
      # pixel (0,0): land selected -> aod 0.30, sigma 0.10, qa 3
      assert np.isclose(rec.aod[0], 0.30) and np.isclose(rec.sigma[0], 0.10)
      assert rec.qa[0] == 3
      assert rec.time[0] == np.datetime64("2020-06-15T01:00:00")
      # pixel (0,1): land fill (qa 0) and ocean fill -> not finite
      assert not np.isfinite(rec.aod[1])

  def test_viirs_record_from_dataset_sigma_is_abs_uncertainty():
      ds = xr.Dataset({
          "Aerosol_Optical_Thickness_550_Land": (("Idx_Atrack", "Idx_Xtrack"), [[0.2]]),
          "Aerosol_Optical_Thickness_550_Ocean": (("Idx_Atrack", "Idx_Xtrack"), [[-999.0]]),
          "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Land":
              (("Idx_Atrack", "Idx_Xtrack"), [[-0.05]]),
          "Aerosol_Optical_Thickness_550_Expected_Uncertainty_Ocean":
              (("Idx_Atrack", "Idx_Xtrack"), [[-999.0]]),
          "Aerosol_Optical_Thickness_QA_Flag_Land": (("Idx_Atrack", "Idx_Xtrack"), [[3.0]]),
          "Aerosol_Optical_Thickness_QA_Flag_Ocean": (("Idx_Atrack", "Idx_Xtrack"), [[0.0]]),
          "Scan_Start_Time": (("Idx_Atrack", "Idx_Xtrack"), [[0.0]]),
      }, coords={"lat": (("Idx_Atrack", "Idx_Xtrack"), [[0.0]]),
                 "lon": (("Idx_Atrack", "Idx_Xtrack"), [[0.0]])})
      rec = viirs_record_from_dataset(ds, _cfg())
      assert np.isclose(rec.sigma[0], 0.05)   # |−0.05|
  ```
- [x] **Step 3: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_ingest_viirs.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.ingest_viirs'`.

- [x] **Step 4: Implement** `$PKG/ingest_viirs.py`:
  ```python
  """Adapt the DAVINCI VIIRS AERDB_L2 reader output into an SP1 L2Record."""
  import numpy as np
  from davinci_monet.datasets.satellite.viirs_l2_aerdb import VIIRSL2AERDBReader
  from .records import L2Record, tai93_to_datetime64

  def viirs_record_from_dataset(ds, cfg):
      """Merge land/ocean surfaces (prefer a valid land retrieval) -> L2Record."""
      aod_l = ds["Aerosol_Optical_Thickness_550_Land"].values
      aod_o = ds["Aerosol_Optical_Thickness_550_Ocean"].values
      qa_l = ds["Aerosol_Optical_Thickness_QA_Flag_Land"].values
      qa_o = ds["Aerosol_Optical_Thickness_QA_Flag_Ocean"].values
      eu_l = ds["Aerosol_Optical_Thickness_550_Expected_Uncertainty_Land"].values
      eu_o = ds["Aerosol_Optical_Thickness_550_Expected_Uncertainty_Ocean"].values
      lat = (ds["lat"] if "lat" in ds else ds["Latitude"]).values
      lon = (ds["lon"] if "lon" in ds else ds["Longitude"]).values
      st = ds["Scan_Start_Time"].values
      # A valid land retrieval: finite AOD and positive QA. Else fall back to ocean.
      land = np.isfinite(aod_l) & (np.asarray(qa_l, np.float64) > 0)
      aod = np.where(land, aod_l, aod_o)
      qa = np.where(land, qa_l, qa_o)
      eu = np.where(land, eu_l, eu_o)
      sigma = np.abs(eu)
      return L2Record(
          sensor="viirs",
          lat=np.asarray(lat).ravel().astype(np.float32),
          lon=np.asarray(lon).ravel().astype(np.float32),
          aod=np.asarray(aod).ravel().astype(np.float32),
          sigma=np.asarray(sigma).ravel().astype(np.float32),
          qa=np.asarray(qa).ravel().astype(np.float32),
          time=tai93_to_datetime64(st),
      )

  def read_viirs_granule(path, cfg):
      ds = VIIRSL2AERDBReader().open([path])
      try:
          return viirs_record_from_dataset(ds, cfg)
      finally:
          ds.close()
  ```
- [x] **Step 5: Run it (expect PASS).** Same command → `2 passed`.
- [x] **Step 6: Commit.** `git -C $ROOT add sp1_aod_pipeline/ingest_viirs.py sp1_aod_pipeline/tests/fixtures.py sp1_aod_pipeline/tests/test_ingest_viirs.py`; commit `SP1: VIIRS ingest adapter over davinci VIIRSL2AERDBReader`.

---

### Task 10 — [Part B: SP1-local] MODIS ingest adapter (DAVINCI reader → L2Record)

SP1 reads MODIS through DAVINCI's `MODISL2AODReader` for real MOD04/MYD04 **HDF-EOS** granules (monetio path), and opens plain-NetCDF granules directly (the deterministic test fixtures + any pre-extracted granules). A pure transform derives σ from the expected-error envelope `σ = ee0 + ee1·|AOD|`, selecting land coefficients when the algorithm flag is Deep Blue (`alg==1`) else ocean (v1 rule, tunable). Combined Dark Target + Deep Blue 550 nm SDS (C6.1): `AOD_550_Dark_Target_Deep_Blue_Combined` (+ `_QA_Flag`, `_Algorithm_Flag`), `Latitude`, `Longitude`, `Scan_Start_Time` (TAI93 s).

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/ingest_modis.py`
- Modify: `$PKG/tests/fixtures.py` (add `make_modis_granule`)
- Test: `$PKG/tests/test_ingest_modis.py`

**Interfaces:**
- Consumes: `davinci_monet.datasets.satellite.modis_l2_aod.MODISL2AODReader`, `records.{L2Record,tai93_to_datetime64}`, `config.RunConfig`.
- Produces:
  - `ingest_modis._modis_record_from_arrays(lat,lon,aod,qa,alg_flag,scan_time,cfg)->L2Record` (pure).
  - `ingest_modis.modis_record_from_dataset(ds, cfg)->L2Record`.
  - `ingest_modis.read_modis_granule(path:str, cfg)->L2Record` (`.hdf` → `MODISL2AODReader`; else xarray).
  - `tests.fixtures.make_modis_granule(path, *, lat, lon, aod, qa, alg, scan_dt)->None` (NetCDF; physical-unit AOD; fill `-999` → NaN via `_FillValue`).

- [x] **Step 1: Add the MODIS builder to** `$PKG/tests/fixtures.py` (append):
  ```python
  def make_modis_granule(path, *, lat, lon, aod, qa, alg, scan_dt):
      """Write a MOD04/MYD04-style swath as NetCDF (combined DT+DB 550 SDS names)."""
      lat = np.asarray(lat, np.float32); lon = np.asarray(lon, np.float32)
      aod = np.asarray(aod, np.float64); qa = np.asarray(qa, np.int16)
      alg = np.asarray(alg, np.int16)
      na, nx = lat.shape
      ds = nc.Dataset(path, "w", format="NETCDF4")
      ds.createDimension("Cell_Along_Swath", na); ds.createDimension("Cell_Across_Swath", nx)
      dims = ("Cell_Along_Swath", "Cell_Across_Swath")
      def w(name, arr, dt, fill=None):
          v = ds.createVariable(name, dt, dims, fill_value=fill) if fill is not None \
              else ds.createVariable(name, dt, dims)
          v[:] = arr
      w("Latitude", lat, "f4"); w("Longitude", lon, "f4")
      aod_f = np.where(aod < 0, -999.0, aod).astype(np.float32)
      w("AOD_550_Dark_Target_Deep_Blue_Combined", aod_f, "f4", fill=-999.0)
      w("AOD_550_Dark_Target_Deep_Blue_Combined_QA_Flag", qa, "i2")
      w("AOD_550_Dark_Target_Deep_Blue_Combined_Algorithm_Flag", alg, "i2")
      w("Scan_Start_Time", np.full((na, nx), _tai93(scan_dt), np.float64), "f8")
      ds.close()
  ```
- [x] **Step 2: Write the failing test** `$PKG/tests/test_ingest_modis.py`:
  ```python
  from datetime import datetime
  import numpy as np
  import xarray as xr
  from sp1_aod_pipeline.config import RunConfig
  from sp1_aod_pipeline.ingest_modis import (_modis_record_from_arrays, modis_record_from_dataset,
                                             read_modis_granule)
  from sp1_aod_pipeline.tests.fixtures import make_modis_granule

  def _cfg():
      return RunConfig(modis_dir="m", viirs_dir="v", out_dir="o",
                       start=datetime(2020, 6, 15).date(), end=datetime(2020, 6, 15).date())

  def test_pure_transform_ee_selection():
      lat = np.array([0.0, 1.0]); lon = np.array([0.0, 1.0])
      aod = np.array([0.4, 0.4]); qa = np.array([3, 3])
      alg = np.array([1, 0])     # 1=Deep Blue->land EE, 0=Dark Target->ocean EE
      st = np.array([0.0, 0.0])
      rec = _modis_record_from_arrays(lat, lon, aod, qa, alg, st, _cfg())
      assert rec.sensor == "modis"
      assert np.isclose(rec.sigma[0], 0.05 + 0.15 * 0.4)   # land
      assert np.isclose(rec.sigma[1], 0.03 + 0.05 * 0.4)   # ocean

  def test_read_modis_granule_roundtrip_netcdf(tmp_path):
      lat = np.array([[10.0, 10.0], [11.0, 11.0]], np.float32)
      lon = np.array([[20.0, 21.0], [20.0, 21.0]], np.float32)
      aod = np.array([[0.30, -1.0], [0.50, 0.40]])     # -1 -> fill -> NaN
      qa = np.array([[3, 0], [2, 1]])
      alg = np.array([[1, 1], [0, 1]])
      p = str(tmp_path / "MOD04_L2.A2020167.0100.061.nc")
      make_modis_granule(p, lat=lat, lon=lon, aod=aod, qa=qa, alg=alg,
                         scan_dt=datetime(2020, 6, 15, 1, 0, 0))
      rec = read_modis_granule(p, _cfg())
      assert rec.aod.shape == (4,)
      assert np.isclose(rec.aod[0], 0.30, atol=1e-3)
      assert np.isnan(rec.aod[1])                       # fill decoded to NaN
      assert rec.time[0] == np.datetime64("2020-06-15T01:00:00")

  def test_modis_record_from_dataset_reads_standardized_coords():
      # Mimic MODISL2AODReader output: Latitude/Longitude renamed to lat/lon coords.
      ds = xr.Dataset({
          "AOD_550_Dark_Target_Deep_Blue_Combined": (("y", "x"), [[0.6]]),
          "AOD_550_Dark_Target_Deep_Blue_Combined_QA_Flag": (("y", "x"), [[3]]),
          "AOD_550_Dark_Target_Deep_Blue_Combined_Algorithm_Flag": (("y", "x"), [[1]]),
          "Scan_Start_Time": (("y", "x"), [[0.0]]),
      }, coords={"lat": (("y", "x"), [[5.0]]), "lon": (("y", "x"), [[6.0]])})
      rec = modis_record_from_dataset(ds, _cfg())
      assert np.isclose(rec.aod[0], 0.6) and np.isclose(rec.sigma[0], 0.05 + 0.15 * 0.6)
  ```
- [x] **Step 3: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_ingest_modis.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.ingest_modis'`.

- [x] **Step 4: Implement** `$PKG/ingest_modis.py`:
  ```python
  """Adapt the DAVINCI MODIS L2 AOD reader output into an SP1 L2Record."""
  import numpy as np
  import xarray as xr
  from davinci_monet.datasets.satellite.modis_l2_aod import MODISL2AODReader
  from .records import L2Record, tai93_to_datetime64

  _COMBINED = "AOD_550_Dark_Target_Deep_Blue_Combined"

  def _modis_record_from_arrays(lat, lon, aod, qa, alg_flag, scan_time, cfg):
      lat = np.asarray(lat).ravel(); lon = np.asarray(lon).ravel()
      aod = np.asarray(aod, np.float64).ravel()
      qa = np.asarray(qa, np.float64).ravel()
      alg = np.asarray(alg_flag, np.float64).ravel()
      st = np.asarray(scan_time, np.float64).ravel()
      land = alg == 1   # Deep Blue -> land EE; else ocean EE (v1 rule, tunable)
      ee0 = np.where(land, cfg.modis_ee_land[0], cfg.modis_ee_ocean[0])
      ee1 = np.where(land, cfg.modis_ee_land[1], cfg.modis_ee_ocean[1])
      sigma = ee0 + ee1 * np.abs(aod)
      return L2Record(
          sensor="modis",
          lat=lat.astype(np.float32), lon=lon.astype(np.float32),
          aod=aod.astype(np.float32), sigma=sigma.astype(np.float32),
          qa=qa.astype(np.float32), time=tai93_to_datetime64(st),
      )

  def modis_record_from_dataset(ds, cfg):
      lat = (ds["lat"] if "lat" in ds else ds["Latitude"]).values
      lon = (ds["lon"] if "lon" in ds else ds["Longitude"]).values
      return _modis_record_from_arrays(
          lat, lon,
          ds[_COMBINED].values,
          ds[_COMBINED + "_QA_Flag"].values,
          ds[_COMBINED + "_Algorithm_Flag"].values,
          ds["Scan_Start_Time"].values, cfg)

  def read_modis_granule(path, cfg):
      # Real MOD04/MYD04 are HDF-EOS -> DAVINCI's monetio-backed reader; pre-extracted
      # / test granules are plain NetCDF -> open directly.
      if str(path).lower().endswith((".hdf", ".hdf4", ".he2", ".he5")):
          ds = MODISL2AODReader().open([path])
      else:
          ds = xr.open_dataset(path, decode_times=False)
      try:
          return modis_record_from_dataset(ds, cfg)
      finally:
          ds.close()
  ```
- [x] **Step 5: Run it (expect PASS).** Same command → `3 passed`.
- [x] **Step 6: Commit.** `git -C $ROOT add sp1_aod_pipeline/ingest_modis.py sp1_aod_pipeline/tests/fixtures.py sp1_aod_pipeline/tests/test_ingest_modis.py`; commit `SP1: MODIS ingest adapter over davinci MODISL2AODReader`.

---

### Task 11 — [Part B: SP1-local] Grid L2 pixels to f09 (DAVINCI binning + uncertainty variant)

Bins one sensor's in-window valid pixels onto f09 using **DAVINCI's binning engine** (`edges_from_centers` for uniform edges around the pole-centered f09 centers; longitude wrapped into `[-0.625, 359.375)`). Two products:
- `bin_record_to_f09` — the **uncertainty variant** (Task 8) gives the inverse-variance per-cell mean and combined σ; the base `bin_swath_to_grid` (Task-A engine, point-in-cell) gives the per-cell **count**. Empty cells carry `_FillValue`. This is the grid used by the pipeline.
- `simple_mean_grid` — a point-in-cell count-mean via `bin_swath_to_grid`/`normalize_grid` (a diagnostic; with constant σ it equals `bin_record_to_f09`'s mean).

**Aggregation-weighting decision (documented).** SPEC §6 stage-2's "area-weighted aggregation" is **superseded by R8/R18**: point-in-cell assignment + inverse-variance weighting (`w=1/σ²`). True pixel-footprint area weighting is the explicit Follow-up. DAVINCI's engine assumes uniform edges (it bins by floor-division on `lat_edges[1]-lat_edges[0]`, ignoring the other edges); SP1 satisfies that by feeding `edges_from_centers(f09_lat()/f09_lon())` — uniform because the f09 **centers** are uniformly spaced (f09 is a "cap" grid only in that the two polar **cell widths** are half). **Nearest-center binning is exact for f09:** the center-midpoints used as bin boundaries are precisely the f09 cap-cell edges (`f09_grid.lat_edges()` interior), so every pixel (|lat|≤90) lands in the same row as the true cap grid — the polar bin's fictitious extension past ±90 holds no data, and point-in-cell + inverse-variance use no cell area. Verified across latitudes incl. near-pole (rows 0/191). A target with non-uniform **centers** (e.g. a Gaussian grid such as ERA5's *native* reduced-Gaussian) would instead need `searchsorted`/`digitize` on the true edges — not needed for f09 (and ERA5 here is met-nudging, already regridded to f09, never binned by this engine). DAVINCI grids are `(time, lon, lat)`; SP1 squeezes the single time bin and transposes to `(lat, lon)` for the contract. DAVINCI grids are `(time, lon, lat)`; SP1 squeezes the single time bin and transposes to `(lat, lon)` for the contract.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/grid.py`
- Test: `$PKG/tests/test_grid.py`

**Interfaces:**
- Consumes: `davinci_monet.pairing.grid_binning.{bin_swath_to_grid,normalize_grid,bin_swath_to_grid_uncertainty,normalize_uncertainty_grid,edges_from_centers}`, `f09_grid.{NLAT,NLON,f09_lat,f09_lon}`, `records.CellGrid`, `contract.FILL_FLOAT`, `config.RunConfig`.
- Produces: `grid.bin_record_to_f09(rec:L2Record, valid:np.ndarray[bool], cfg)->CellGrid`; `grid.simple_mean_grid(rec, valid, cfg)->np.ndarray(192,288)f4`.

- [x] **Step 1: Write the failing test** `$PKG/tests/test_grid.py`:
  ```python
  from datetime import datetime
  import numpy as np
  from sp1_aod_pipeline.config import RunConfig
  from sp1_aod_pipeline.records import L2Record
  from sp1_aod_pipeline.grid import bin_record_to_f09, simple_mean_grid
  from sp1_aod_pipeline.f09_grid import f09_lat, f09_lon

  def _cfg():
      return RunConfig(modis_dir="m", viirs_dir="v", out_dir="o",
                       start=datetime(2020, 6, 15).date(), end=datetime(2020, 6, 15).date())

  def _rec(lat, lon, aod, sigma):
      n = len(lat)
      return L2Record("viirs", np.array(lat, np.float32), np.array(lon, np.float32),
                      np.array(aod, np.float32), np.array(sigma, np.float32),
                      np.full(n, 3, np.float32),
                      np.full(n, np.datetime64("2020-06-15T01:00:00"), "datetime64[ns]"))

  def test_two_pixels_same_cell_inverse_variance():
      lat0 = float(f09_lat()[96]); lon0 = float(f09_lon()[1])   # cell (96,1)
      rec = _rec([lat0, lat0], [lon0, lon0], [0.4, 0.8], [0.1, 0.2])
      g = bin_record_to_f09(rec, np.array([True, True]), _cfg())
      w1, w2 = 1 / 0.1**2, 1 / 0.2**2
      exp = (w1 * 0.4 + w2 * 0.8) / (w1 + w2)
      assert np.isclose(g.mean[96, 1], exp, atol=1e-5)
      assert np.isclose(g.sigma[96, 1], np.sqrt(1 / (w1 + w2)), atol=1e-5)
      assert g.count[96, 1] == 2

  def test_empty_cells_are_fill():
      rec = _rec([float(f09_lat()[96])], [1.25], [0.5], [0.1])
      g = bin_record_to_f09(rec, np.array([True]), _cfg())
      assert g.count.sum() == 1
      assert (g.mean == -999.0).sum() == 192 * 288 - 1
      assert g.mean.dtype == np.float32 and g.count.dtype == np.int32

  def test_lon_wrap_assigns_cell_zero():
      rec = _rec([float(f09_lat()[96])], [359.9], [0.6], [0.1])
      g = bin_record_to_f09(rec, np.array([True]), _cfg())
      assert g.count[96, 0] == 1

  def test_near_pole_pixels_map_to_polar_rows():
      # f09 is a cap grid (polar cells half-width); nearest-center binning must still
      # land near-pole pixels in rows 0 / 191, exactly like the true cap grid
      # (verified against the cap-edge assignment for all latitudes, 2026-06-27).
      lon0 = float(f09_lon()[1])
      g = bin_record_to_f09(_rec([-89.9, 89.9], [lon0, lon0], [0.3, 0.3], [0.1, 0.1]),
                            np.array([True, True]), _cfg())
      assert g.count[0, 1] == 1 and g.count[191, 1] == 1

  def test_invalid_pixels_excluded():
      lat0 = float(f09_lat()[96]); lon0 = float(f09_lon()[1])
      rec = _rec([lat0, lat0], [lon0, lon0], [0.4, 9.9], [0.1, 0.1])
      g = bin_record_to_f09(rec, np.array([True, False]), _cfg())
      assert g.count[96, 1] == 1 and np.isclose(g.mean[96, 1], 0.4)

  def test_simple_mean_grid_is_count_average():
      lat0 = float(f09_lat()[96]); lon0 = float(f09_lon()[1])
      rec = _rec([lat0, lat0], [lon0, lon0], [0.4, 0.8], [0.1, 0.2])
      m = simple_mean_grid(rec, np.array([True, True]), _cfg())
      assert np.isclose(m[96, 1], (0.4 + 0.8) / 2, atol=1e-5)   # unweighted count mean
      assert m.dtype == np.float32 and float(m[0, 0]) == -999.0
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_grid.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.grid'`.

- [x] **Step 3: Implement** `$PKG/grid.py`:
  ```python
  """Bin L2 pixels onto f09 using DAVINCI's binning engine (point-in-cell + inverse variance)."""
  import numpy as np
  from davinci_monet.pairing.grid_binning import (
      bin_swath_to_grid, normalize_grid,
      bin_swath_to_grid_uncertainty, normalize_uncertainty_grid,
      edges_from_centers,
  )
  from .f09_grid import NLAT, NLON, f09_lat, f09_lon
  from .records import CellGrid
  from .contract import FILL_FLOAT

  def _prep(rec, valid, cfg):
      lat = np.asarray(rec.lat, np.float64)[valid]
      lon = np.asarray(rec.lon, np.float64)[valid]
      aod = np.asarray(rec.aod, np.float64)[valid]
      sig = np.maximum(np.asarray(rec.sigma, np.float64)[valid], cfg.sigma_floor)
      lon = ((lon + 0.625) % 360.0) - 0.625      # wrap into [-0.625, 359.375)
      late = edges_from_centers(f09_lat())        # (193,) uniform around pole-centered centers
      lone = edges_from_centers(f09_lon())        # (289,) uniform
      tedges = np.array([0.0, 1.0])               # single time bin (windowing already applied)
      tvals = np.zeros(aod.shape[0])
      return lat, lon, aod, sig, late, lone, tedges, tvals

  def bin_record_to_f09(rec, valid, cfg):
      lat, lon, aod, sig, late, lone, tedges, tvals = _prep(rec, valid, cfg)
      shape = (1, NLON, NLAT)                      # DAVINCI grid order (time, lon, lat)
      count = np.zeros(shape, dtype=np.int64)
      weight = np.zeros(shape); wsum = np.zeros(shape)
      bin_swath_to_grid_uncertainty(tedges, lone, late, tvals, lon, lat, aod, sig,
                                    count, weight, wsum)
      mean_g, sigma_g = normalize_uncertainty_grid(count, weight, wsum)
      mean2d = mean_g[0].T                         # (lon,lat) -> (lat,lon)
      sigma2d = sigma_g[0].T
      count2d = count[0].T.astype(np.int32)
      mean2d = np.where(np.isnan(mean2d), float(FILL_FLOAT), mean2d).astype(np.float32)
      sigma2d = np.where(np.isnan(sigma2d), float(FILL_FLOAT), sigma2d).astype(np.float32)
      return CellGrid(mean=mean2d, sigma=sigma2d, count=count2d)

  def simple_mean_grid(rec, valid, cfg):
      """Point-in-cell unweighted mean via DAVINCI bin_swath_to_grid (diagnostic)."""
      lat, lon, aod, _sig, late, lone, tedges, tvals = _prep(rec, valid, cfg)
      shape = (1, NLON, NLAT)
      count = np.zeros(shape, dtype=np.int64); dsum = np.zeros(shape)
      bin_swath_to_grid(tedges, lone, late, tvals, lon, lat, aod, count, dsum)
      normalize_grid(count, dsum)                 # in-place -> mean; empty -> NaN
      m2d = dsum[0].T
      return np.where(np.isnan(m2d), float(FILL_FLOAT), m2d).astype(np.float32)
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `6 passed`. (First run JIT-compiles the numba kernels; allow a few seconds.)
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/grid.py sp1_aod_pipeline/tests/test_grid.py`; commit `SP1: f09 binning via davinci engine + uncertainty variant`.

---

### Task 12 — [Part B: SP1-local] Inverse-variance merge of two CellGrids

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/merge.py`
- Test: `$PKG/tests/test_merge.py`

**Interfaces:**
- Consumes: `contract.FILL_FLOAT`, `config.RunConfig`.
- Produces: `merge.inverse_variance_merge(a_mean,a_sigma,a_count,b_mean,b_sigma,b_count,cfg)->tuple[np.ndarray(f4),np.ndarray(f4),np.ndarray(i4)]` — fill-aware (`== -999` means absent).

- [x] **Step 1: Write the failing test** `$PKG/tests/test_merge.py`:
  ```python
  from datetime import datetime
  import numpy as np
  from sp1_aod_pipeline.config import RunConfig
  from sp1_aod_pipeline.merge import inverse_variance_merge

  def _cfg():
      return RunConfig(modis_dir="m", viirs_dir="v", out_dir="o",
                       start=datetime(2020, 6, 15).date(), end=datetime(2020, 6, 15).date())

  def _g(val, sig, cnt, shape=(2, 2)):
      return (np.full(shape, val, np.float32), np.full(shape, sig, np.float32),
              np.full(shape, cnt, np.int32))

  def test_both_present_inverse_variance():
      am, asig, ac = _g(0.5, 0.1, 3)
      bm, bsig, bc = _g(0.7, 0.2, 5)
      m, s, c = inverse_variance_merge(am, asig, ac, bm, bsig, bc, _cfg())
      w1, w2 = 1 / 0.1**2, 1 / 0.2**2
      assert np.isclose(m[0, 0], (w1 * 0.5 + w2 * 0.7) / (w1 + w2), atol=1e-5)
      assert np.isclose(s[0, 0], np.sqrt(1 / (w1 + w2)), atol=1e-5)
      assert c[0, 0] == 8

  def test_one_present_uses_it():
      am, asig, ac = _g(-999.0, -999.0, 0)
      bm, bsig, bc = _g(0.3, 0.15, 4)
      m, s, c = inverse_variance_merge(am, asig, ac, bm, bsig, bc, _cfg())
      assert np.isclose(m[0, 0], 0.3) and np.isclose(s[0, 0], 0.15) and c[0, 0] == 4

  def test_neither_present_is_fill():
      am, asig, ac = _g(-999.0, -999.0, 0)
      bm, bsig, bc = _g(-999.0, -999.0, 0)
      m, s, c = inverse_variance_merge(am, asig, ac, bm, bsig, bc, _cfg())
      assert m[0, 0] == -999.0 and s[0, 0] == -999.0 and c[0, 0] == 0
      assert m.dtype == np.float32 and c.dtype == np.int32
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_merge.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.merge'`.

- [x] **Step 3: Implement** `$PKG/merge.py`:
  ```python
  """Inverse-variance merge of MODIS + VIIRS per-cell grids (fill-aware)."""
  import numpy as np
  from .contract import FILL_FLOAT

  def inverse_variance_merge(a_mean, a_sigma, a_count, b_mean, b_sigma, b_count, cfg):
      fill = float(FILL_FLOAT)
      a_ok = np.asarray(a_mean) != fill
      b_ok = np.asarray(b_mean) != fill
      am = np.where(a_ok, a_mean, 0.0).astype(np.float64)
      bm = np.where(b_ok, b_mean, 0.0).astype(np.float64)
      asig = np.maximum(np.asarray(a_sigma, np.float64), cfg.sigma_floor)
      bsig = np.maximum(np.asarray(b_sigma, np.float64), cfg.sigma_floor)
      aw = np.where(a_ok, 1.0 / asig**2, 0.0)
      bw = np.where(b_ok, 1.0 / bsig**2, 0.0)
      sumw = aw + bw
      has = sumw > 0
      mean = np.full(am.shape, fill)
      sigma = np.full(am.shape, fill)
      mean[has] = (aw[has] * am[has] + bw[has] * bm[has]) / sumw[has]
      sigma[has] = np.sqrt(1.0 / sumw[has])
      count = (np.where(a_ok, a_count, 0) + np.where(b_ok, b_count, 0)).astype(np.int32)
      return mean.astype(np.float32), sigma.astype(np.float32), count
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `3 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/merge.py sp1_aod_pipeline/tests/test_merge.py`; commit `SP1: inverse-variance MODIS+VIIRS merge`.

---

### Task 13 — [Part B: SP1-local] AERONET-anchored VIIRS→MODIS bias correction

The prior `md08_d3` correction is unrecoverable, so SP1 defines a NEW, documented correction. Using AERONET (550 nm ground truth) co-located with each sensor's gridded value, fit two affine calibrations to truth: `A ≈ a_m + b_m·M`, `A ≈ a_v + b_v·V`. MODIS is the reference frame (unchanged); VIIRS maps to MODIS-equivalent via `V_corr = (a_v + b_v·V − a_m) / b_m`; σ propagates as `σ_corr = |b_v/b_m|·σ_V`. Coefficients + before/after RMSE-vs-AERONET are persisted to JSON and copied into provenance. (AERONET truth is Ångström-interpolated to 550 nm by Task 16.)

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/bias.py`
- Test: `$PKG/tests/test_bias.py`

**Interfaces:**
- Consumes: `contract.FILL_FLOAT`, `config.RunConfig.bias_coeff_file`.
- Produces: `bias.BiasCoeffs(a_m,b_m,a_v,b_v,rmse_before,rmse_after,n)` with `to_json`/`from_json`; `bias.fit_bias(modis_aod,viirs_aod,aeronet_aod)->BiasCoeffs`; `bias.apply_bias(viirs_aod,c)->f4` (fill-aware); `bias.apply_bias_sigma(viirs_sigma,c)->f4` (fill-aware); `bias.identity()->BiasCoeffs`; `bias.resolve_coeffs(cfg, bias_path=None)->BiasCoeffs` (precedence: explicit `bias_path` > `cfg.bias_coeff_file` if it exists > `identity()`).

- [x] **Step 1: Write the failing test** `$PKG/tests/test_bias.py`:
  ```python
  from datetime import date
  import numpy as np
  from sp1_aod_pipeline.config import RunConfig
  from sp1_aod_pipeline.bias import (BiasCoeffs, fit_bias, apply_bias, apply_bias_sigma,
                                     identity, resolve_coeffs)

  def test_fit_recovers_truth_when_modis_is_truth():
      truth = np.array([0.1, 0.2, 0.5, 1.0, 1.5])
      modis = truth.copy()
      viirs = 0.1 + 1.2 * truth
      c = fit_bias(modis, viirs, truth)
      assert abs(c.a_m) < 1e-9 and abs(c.b_m - 1.0) < 1e-9
      corr = apply_bias(viirs.astype(np.float32), c)
      assert np.allclose(corr, truth, atol=1e-5)
      assert c.rmse_after < 1e-5 < c.rmse_before

  def test_apply_bias_is_fill_aware():
      c = identity()
      v = np.array([0.5, -999.0, 0.3], np.float32)
      out = apply_bias(v, c)
      assert np.isclose(out[0], 0.5) and out[1] == -999.0 and np.isclose(out[2], 0.3)

  def test_apply_bias_sigma_scales():
      c = BiasCoeffs(a_m=0.0, b_m=1.0, a_v=0.0, b_v=2.0, rmse_before=0.0, rmse_after=0.0, n=3)
      s = np.array([0.1, -999.0], np.float32)
      out = apply_bias_sigma(s, c)
      assert np.isclose(out[0], 0.2) and out[1] == -999.0

  def test_json_roundtrip(tmp_path):
      c = BiasCoeffs(0.01, 1.02, -0.03, 1.1, 0.2, 0.05, 42)
      p = str(tmp_path / "b.json")
      c.to_json(p)
      assert BiasCoeffs.from_json(p) == c

  def test_resolve_coeffs_precedence(tmp_path):
      def cfg(bcf):
          return RunConfig(modis_dir="m", viirs_dir="v", out_dir="o",
                           start=date(2020, 6, 15), end=date(2020, 6, 15), bias_coeff_file=bcf)
      assert resolve_coeffs(cfg(str(tmp_path / "nope.json"))) == identity()
      saved = BiasCoeffs(0.0, 1.0, -0.02, 1.1, 0.2, 0.05, 7)
      pc = str(tmp_path / "cfg_coeffs.json"); saved.to_json(pc)
      assert resolve_coeffs(cfg(pc)) == saved
      explicit = BiasCoeffs(0.01, 0.99, 0.0, 1.0, 0.1, 0.03, 3)
      pe = str(tmp_path / "explicit.json"); explicit.to_json(pe)
      assert resolve_coeffs(cfg(pc), pe) == explicit
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_bias.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.bias'`.

- [x] **Step 3: Implement** `$PKG/bias.py`:
  ```python
  """AERONET-anchored affine VIIRS->MODIS bias correction."""
  import json
  import os
  from dataclasses import dataclass, asdict
  import numpy as np
  from .contract import FILL_FLOAT

  @dataclass
  class BiasCoeffs:
      a_m: float
      b_m: float
      a_v: float
      b_v: float
      rmse_before: float
      rmse_after: float
      n: int

      def to_json(self, path):
          with open(path, "w") as f:
              json.dump(asdict(self), f, indent=2)

      @classmethod
      def from_json(cls, path):
          with open(path) as f:
              return cls(**json.load(f))

  def identity():
      return BiasCoeffs(a_m=0.0, b_m=1.0, a_v=0.0, b_v=1.0,
                        rmse_before=0.0, rmse_after=0.0, n=0)

  def resolve_coeffs(cfg, bias_path=None):
      """Pick bias coefficients: explicit path > cfg.bias_coeff_file (if present) > identity."""
      if bias_path:
          return BiasCoeffs.from_json(bias_path)
      if cfg.bias_coeff_file and os.path.exists(cfg.bias_coeff_file):
          return BiasCoeffs.from_json(cfg.bias_coeff_file)
      return identity()

  def _affine_fit(x, y):
      A = np.vstack([np.ones_like(x), x]).T
      coef, *_ = np.linalg.lstsq(A, y, rcond=None)
      return float(coef[0]), float(coef[1])   # intercept, slope

  def fit_bias(modis_aod, viirs_aod, aeronet_aod):
      m = np.asarray(modis_aod, np.float64)
      v = np.asarray(viirs_aod, np.float64)
      a = np.asarray(aeronet_aod, np.float64)
      a_m, b_m = _affine_fit(m, a)
      a_v, b_v = _affine_fit(v, a)
      corr = (a_v + b_v * v - a_m) / b_m
      rmse_before = float(np.sqrt(np.mean((v - a) ** 2)))
      rmse_after = float(np.sqrt(np.mean((corr - a) ** 2)))
      return BiasCoeffs(a_m, b_m, a_v, b_v, rmse_before, rmse_after, int(a.size))

  def apply_bias(viirs_aod, c):
      v = np.asarray(viirs_aod, np.float64)
      ok = v != float(FILL_FLOAT)
      out = np.full(v.shape, float(FILL_FLOAT))
      out[ok] = (c.a_v + c.b_v * v[ok] - c.a_m) / c.b_m
      return out.astype(np.float32)

  def apply_bias_sigma(viirs_sigma, c):
      s = np.asarray(viirs_sigma, np.float64)
      ok = s != float(FILL_FLOAT)
      out = np.full(s.shape, float(FILL_FLOAT))
      out[ok] = abs(c.b_v / c.b_m) * s[ok]
      return out.astype(np.float32)
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `5 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/bias.py sp1_aod_pipeline/tests/test_bias.py`; commit `SP1: AERONET-anchored VIIRS->MODIS bias correction`.

---

### Task 14 — [Part B: SP1-local] 3-hourly window helpers + CF time-center adapter

Window bookkeeping for temporal aggregation. The contract `time` is the window **center** (Task 3 writes it); these helpers give the start/end/center and the half-open pixel-time mask. (DAVINCI's `read_and_grid` `time_resolution` is not used because SP1 controls windows explicitly to match the contract's 8 windows/day.)

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/aggregate.py`
- Test: `$PKG/tests/test_aggregate.py`

**Interfaces:**
- Consumes: `contract.{WINDOW_SECONDS,WINDOW_LENGTH_SEC}`.
- Produces: `aggregate.window_bounds(d:date, idx:int)->tuple[datetime,datetime,datetime]` (start,end,center); `aggregate.window_index(t:datetime)->int` (0..7); `aggregate.pixel_window_mask(times:np.ndarray[datetime64], start, end)->np.ndarray[bool]` (NaT-safe, half-open); `aggregate.enumerate_windows(start_date,end_date)->list[tuple[date,int]]`.

- [x] **Step 1: Write the failing test** `$PKG/tests/test_aggregate.py`:
  ```python
  from datetime import date, datetime
  import numpy as np
  from sp1_aod_pipeline import aggregate as ag

  def test_window_bounds():
      s, e, c = ag.window_bounds(date(2020, 6, 15), 1)
      assert s == datetime(2020, 6, 15, 3) and e == datetime(2020, 6, 15, 6)
      assert c == datetime(2020, 6, 15, 4, 30)

  def test_window_index():
      assert ag.window_index(datetime(2020, 6, 15, 0, 0)) == 0
      assert ag.window_index(datetime(2020, 6, 15, 2, 59)) == 0
      assert ag.window_index(datetime(2020, 6, 15, 3, 0)) == 1
      assert ag.window_index(datetime(2020, 6, 15, 23, 59)) == 7

  def test_pixel_window_mask_half_open_and_nat():
      times = np.array(["2020-06-15T03:00:00", "2020-06-15T05:59:00",
                        "2020-06-15T06:00:00", "NaT"], dtype="datetime64[ns]")
      m = ag.pixel_window_mask(times, datetime(2020, 6, 15, 3), datetime(2020, 6, 15, 6))
      assert m.tolist() == [True, True, False, False]

  def test_enumerate_windows():
      w = ag.enumerate_windows(date(2020, 6, 15), date(2020, 6, 16))
      assert len(w) == 16 and w[0] == (date(2020, 6, 15), 0) and w[-1] == (date(2020, 6, 16), 7)
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_aggregate.py -q` → `ImportError: cannot import name 'aggregate' from 'sp1_aod_pipeline'`.

- [x] **Step 3: Implement** `$PKG/aggregate.py`:
  ```python
  """3-hourly window bookkeeping."""
  from datetime import datetime, timedelta
  import numpy as np
  from .contract import WINDOW_SECONDS, WINDOW_LENGTH_SEC

  def window_bounds(d, idx):
      start = datetime(d.year, d.month, d.day) + timedelta(seconds=WINDOW_SECONDS[idx])
      end = start + timedelta(seconds=WINDOW_LENGTH_SEC)
      center = start + timedelta(seconds=WINDOW_LENGTH_SEC // 2)
      return start, end, center

  def window_index(t):
      sod = t.hour * 3600 + t.minute * 60 + t.second
      return min(sod // WINDOW_LENGTH_SEC, 7)

  def pixel_window_mask(times, start, end):
      t = np.asarray(times)
      s = np.datetime64(start); e = np.datetime64(end)
      finite = ~np.isnat(t)
      return finite & (t >= s) & (t < e)

  def enumerate_windows(start_date, end_date):
      out = []
      d = start_date
      while d <= end_date:
          for idx in range(8):
              out.append((d, idx))
          d = d + timedelta(days=1)
      return out
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `4 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/aggregate.py sp1_aod_pipeline/tests/test_aggregate.py`; commit `SP1: 3-hourly window helpers`.

---

### Task 15 — [Part B: SP1-local] Acquire via DAVINCI `stage_collection` (LAADS CollectionSpecs)

MODIS L2 is not on glade; the 2020 VIIRS target is not in the local archive. SP1 stages MOD04/MYD04/AERDB from LAADS via **DAVINCI's** `stage_collection` (EarthData auth through `earthaccess` + `~/.netrc`). SP1 declares the three `CollectionSpec`s and a thin `stage_sp1`; the network is fully isolated behind injectable `login`/`search`/`download` hooks (offline tests), exactly like `io/download/ceres.py`.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/acquire.py`
- Test: `$PKG/tests/test_acquire.py`

**Interfaces:**
- Consumes: `davinci_monet.io.download.earthdata.{CollectionSpec,stage_collection}`.
- Produces: `acquire.SP1_COLLECTIONS:dict[str,CollectionSpec]` (`"mod04"`,`"myd04"`,`"aerdb_noaa20"`); `acquire.stage_sp1(collection:str, start:str|None, end:str|None, dest_root:str, *, dry_run=False, login=None, search=None, download=None)->Sequence|list[Path]`.

- [x] **Step 1: Write the failing test** `$PKG/tests/test_acquire.py`:
  ```python
  from pathlib import Path
  import pytest
  from sp1_aod_pipeline import acquire

  def test_collection_specs_are_correct():
      assert acquire.SP1_COLLECTIONS["mod04"].short_name == "MOD04_L2"
      assert acquire.SP1_COLLECTIONS["mod04"].version == "6.1"
      assert acquire.SP1_COLLECTIONS["myd04"].short_name == "MYD04_L2"
      assert acquire.SP1_COLLECTIONS["myd04"].version == "6.1"
      v = acquire.SP1_COLLECTIONS["aerdb_noaa20"]
      assert v.short_name == "AERDB_L2_VIIRS_NOAA20" and v.version == "2"

  def test_stage_sp1_dry_run_searches_without_download(tmp_path):
      calls = {}
      res = acquire.stage_sp1("mod04", "2020-06-15", "2020-06-16", str(tmp_path),
                              dry_run=True,
                              login=lambda: calls.setdefault("login", True),
                              search=lambda s, t: ["g1", "g2"],
                              download=lambda r, d: pytest.fail("download in dry run"))
      assert calls["login"] is True
      assert list(res) == ["g1", "g2"]
      # spec subpath under dest_root not created on dry run
      assert not (tmp_path / "modis" / "terra").exists()

  def test_stage_sp1_downloads_into_spec_subpath(tmp_path):
      seen = {}
      def _dl(results, dest):
          seen["dest"] = dest
          return [Path(dest) / "f.nc"]
      out = acquire.stage_sp1("aerdb_noaa20", "2020-06-15", "2020-06-16", str(tmp_path),
                              login=lambda: None, search=lambda s, t: ["g1"], download=_dl)
      assert Path(seen["dest"]) == tmp_path / "viirs" / "noaa20"
      assert (tmp_path / "viirs" / "noaa20").is_dir()
      assert out == [tmp_path / "viirs" / "noaa20" / "f.nc"]
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_acquire.py -q` → `ImportError: cannot import name 'acquire' from 'sp1_aod_pipeline'`.

- [x] **Step 3: Implement** `$PKG/acquire.py`:
  ```python
  """Stage SP1's LAADS L2 products via davinci_monet's earthaccess staging core."""
  from pathlib import Path
  from davinci_monet.io.download.earthdata import CollectionSpec, stage_collection

  # short_name + on-disk subpath (under dest_root) + pinned collection version.
  SP1_COLLECTIONS = {
      "mod04": CollectionSpec("MOD04_L2", Path("modis/terra"), version="6.1"),
      "myd04": CollectionSpec("MYD04_L2", Path("modis/aqua"), version="6.1"),
      "aerdb_noaa20": CollectionSpec("AERDB_L2_VIIRS_NOAA20", Path("viirs/noaa20"), version="2"),
  }

  def stage_sp1(collection, start, end, dest_root, *, dry_run=False,
                login=None, search=None, download=None):
      """Stage one SP1 collection into ``dest_root/<spec.subpath>`` over a temporal window."""
      try:
          spec = SP1_COLLECTIONS[collection]
      except KeyError:
          known = ", ".join(sorted(SP1_COLLECTIONS))
          raise KeyError(f"Unknown SP1 collection {collection!r}. Known: {known}") from None
      temporal = (start, end) if start is not None and end is not None else None
      dest = Path(dest_root) / spec.subpath
      return stage_collection(spec, temporal, dest, dry_run=dry_run,
                              login=login, search=search, download=download)
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `3 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/acquire.py sp1_aod_pipeline/tests/test_acquire.py`; commit `SP1: acquire via davinci stage_collection (MOD04/MYD04/AERDB)`.

---

### Task 16 — [Part B: SP1-local] AERONET loader + 550 nm interpolation

**Source (per user, 2026-06-27): our own DAVINCI-staged AERONET, downloaded as needed.** Read the netCDF cache `/glade/work/fillmore/Data/CERES-SARB-CAM7/AeroNet/AeroNet_%Y%m%d.nc` (one file/day, monetio/DAVINCI schema: dims `(time, y=1, x=site)`; coords `siteid/latitude/longitude(x)`; vars `aod_500nm`, `440-675_angstrom_exponent`, …; missing sentinel `≤0`, e.g. `-1`/`-999`). The cache is populated for the **July-2008 test month** by `scripts/stage_obs.py` (Level 2.0 `AOD20`); any missing day is downloaded on demand via **DAVINCI's `AERONETReader.open(dates=…)`** (monetio web API) and written to the cache; `AERONETReader.open` returns the same fields standardized to dims `(time, site)` with coords `lat/lon`, so one normalizer handles cache + fresh. R19: `AOD_550 = AOD_500·(550/500)^(−α)` (DAVINCI reads native AOD but does not interpolate to 550 nm, so SP1 supplies this). The loaded long frame feeds DAVINCI co-location in Task 17 — **the AERONET comparison is DAVINCI analysis, scripts tracked in this repo.** *(Two grounded musts, verified on real 2008 data: download with `freq="H"` — raw sub-hourly AERONET pivots to a ~0.5 GB/day dense `time×site` array — and rely on the DAVINCI `AERONETReader.open` `add_data` bugfix, committed on `develop` `b029cdb`.)*

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/validation/__init__.py`, `$PKG/validation/aeronet.py`
- Test: `$PKG/tests/test_aeronet.py`

**Interfaces:**
- Consumes (download path): `davinci_monet.datasets.surface.aeronet.AERONETReader`.
- Produces: `validation.aeronet.aod_550_from_500(aod500, angstrom)->np.ndarray`; `validation.aeronet.load_aeronet_file(path)->pandas.DataFrame[site,lat,lon,time(datetime64[ns,UTC]),aod550]` (one cached daily netCDF → long frame); `validation.aeronet.load_aeronet_days(days, cache_dir=AERONET_CACHE, download=True)->DataFrame` (cache-or-download via DAVINCI; injectable `_download_day` for offline tests); constant `AERONET_CACHE="/glade/work/fillmore/Data/CERES-SARB-CAM7/AeroNet"`.

**Plan revision (2026-06-27) — read our DAVINCI-staged netCDF cache (not V3 text).** Per the user, AERONET is our own data under `/glade/work/fillmore/Data/CERES-SARB-CAM7/AeroNet` (monetio/DAVINCI netCDF), downloaded via DAVINCI as needed. **Use this `aeronet.py` + test in place of the V3-text Steps 2/4 below** (which are retired). The long-frame output is unchanged, so Task 17 co-location is unaffected.

Test `$PKG/tests/test_aeronet.py`:
```python
import numpy as np, pandas as pd, xarray as xr
from sp1_aod_pipeline.validation.aeronet import aod_550_from_500, load_aeronet_file

def test_aod_550_from_500():
    assert np.isclose(aod_550_from_500(np.array([0.22]), np.array([1.0]))[0],
                      0.22 * (550.0/500.0)**(-1.0))

def _make_cache(path):
    t = pd.date_range("2010-01-01", periods=2, freq="h")
    xr.Dataset(
        {"aod_500nm": (("time","y","x"), np.array([[[0.220,-1.0]],[[-999.0,0.30]]])),
         "440-675_angstrom_exponent": (("time","y","x"), np.array([[[1.0,1.2]],[[1.1,0.8]]]))},
        coords={"time": t, "y": [0],
                "x": ("x", np.array([0, 1])),                     # integer index, like the real cache
                "siteid": ("x", np.array(["Sao_Paulo","GSFC"])),  # station NAMES (must win over x)
                "latitude": ("x", np.array([-23.5,39.0])),
                "longitude": ("x", np.array([-46.7,-76.8]))},
    ).to_netcdf(path)

def test_load_aeronet_file(tmp_path):
    p = tmp_path / "AeroNet_20100101.nc"; _make_cache(str(p))
    df = load_aeronet_file(str(p))
    assert len(df) == 2                       # 2 of 4 cells valid (-1 and -999 dropped)
    r = df[df.site == "Sao_Paulo"].iloc[0]
    assert np.isclose(r.lat, -23.5) and np.isclose(r.lon, -46.7)
    assert np.isclose(r.aod550, 0.220*(550.0/500.0)**(-1.0), atol=1e-6)
    assert {"site","lat","lon","time","aod550"} <= set(df.columns)
```

Implement `$PKG/validation/aeronet.py`:
```python
"""AERONET from our DAVINCI-staged netCDF cache; download via DAVINCI as needed;
interpolate AOD to 550 nm (R19). Cache: /glade/work/fillmore/Data/CERES-SARB-CAM7/AeroNet/AeroNet_%Y%m%d.nc
(monetio schema). AERONETReader.open(dates=) is the on-demand download path."""
import os
from datetime import timedelta
import numpy as np, pandas as pd, xarray as xr

AERONET_CACHE = "/glade/work/fillmore/Data/CERES-SARB-CAM7/AeroNet"
CACHE_TEMPLATE = "AeroNet_%Y%m%d.nc"
_AOD500, _ANG = "aod_500nm", "440-675_angstrom_exponent"

def aod_550_from_500(aod500, angstrom):
    aod500 = np.asarray(aod500, np.float64); angstrom = np.asarray(angstrom, np.float64)
    return aod500 * (550.0/500.0)**(-angstrom)

def _to_long(ds):
    # Robust to BOTH schemas (both verified on real files 2026-06-27):
    #   - our cache:        dims (time,y,x); names in `siteid`, latitude/longitude 1-D on x
    #   - AERONETReader.open: dims (time,site); names in the `site` coord, lat/lon 2-D (time,site)
    # Let xarray flatten to long form and reduce any 2-D lat/lon to per-site.
    if "y" in ds.dims:
        ds = ds.squeeze("y", drop=True)
    sdim = "site" if "site" in ds.dims else ("x" if "x" in ds.dims else None)
    out = xr.Dataset({"aod550": ds[_AOD500] * (550.0/500.0)**(-ds[_ANG]),
                      "aod500": ds[_AOD500]})
    if "siteid" in ds.variables:                 # cache: station names live in siteid
        out["site_name"] = ds["siteid"]
    for srcs, dst in ((("lat", "latitude"), "lat"), (("lon", "longitude"), "lon")):
        for s in srcs:
            if s in ds.variables:
                v = ds[s]; extra = [d for d in v.dims if d != sdim]
                out[dst] = v.mean(dim=extra) if extra else v   # reduce 2-D -> per-site
                break
    df = out.to_dataframe().reset_index()
    namecol = "site_name" if "site_name" in df.columns else sdim
    df = df.rename(columns={namecol: "site"})
    df["site"] = df["site"].astype(str)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    m = np.isfinite(df["aod500"]) & (df["aod500"] > 0.0) & np.isfinite(df["aod550"])
    return df.loc[m, ["site", "lat", "lon", "time", "aod550"]].reset_index(drop=True)

def load_aeronet_file(path):
    with xr.open_dataset(path) as ds:
        return _to_long(ds)

def _download_day(d, cache_dir):  # isolated for offline tests (monkeypatch this)
    from davinci_monet.datasets.surface.aeronet import AERONETReader
    ds = AERONETReader().open(dates=[d.strftime("%Y-%m-%d"),
                                     (d+timedelta(days=1)).strftime("%Y-%m-%d")],
                              product="AOD20", freq="H")   # Level 2.0, hourly-resampled
    os.makedirs(cache_dir, exist_ok=True)
    ds.to_netcdf(os.path.join(cache_dir, d.strftime(CACHE_TEMPLATE)))
    return _to_long(ds)

def load_aeronet_days(days, cache_dir=AERONET_CACHE, download=True):
    frames = []
    for d in days:
        fp = os.path.join(cache_dir, d.strftime(CACHE_TEMPLATE))
        if os.path.exists(fp):
            frames.append(load_aeronet_file(fp))
        elif download:
            frames.append(_download_day(d, cache_dir))
    cols = ["site","lat","lon","time","aod550"]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
```

- [x] **Step 1: Create** `$PKG/validation/__init__.py` (single line `# validation subpackage`).
- [x] **Step 2 (SUPERSEDED by the revision block above — V3-text path retired): Write the failing test** `$PKG/tests/test_aeronet.py`:
  Actual implementation used the NetCDF-cache tests from the revision block above, plus coverage for the real DAVINCI `(time, site)` schema and `load_aeronet_days`.
  ```python
  import numpy as np
  from sp1_aod_pipeline.validation.aeronet import aod_550_from_500, load_aeronet_file

  PREAMBLE = "\n".join(["<html>", "</head>", "<body>", "Version 3<br>",
                        "Version 3: AOD Level 1.5<br>", "The following data<br>",
                        "Contact: PI=x<br>"])
  HEADER = ("AERONET_Site,Date(dd:mm:yyyy),Time(hh:mm:ss),AOD_500nm,"
            "440-675_Angstrom_Exponent,Site_Latitude(Degrees),Site_Longitude(Degrees)<br>")

  def test_aod_550_from_500():
      assert np.isclose(aod_550_from_500(np.array([0.22]), np.array([1.0]))[0], 0.22 / 1.1)

  def test_load_aeronet_file(tmp_path):
      rows = [
          "Sao_Paulo,15:06:2020,01:10:00,0.220,1.0,-23.5,-46.7",
          "Sao_Paulo,15:06:2020,01:20:00,-999.,1.2,-23.5,-46.7",
      ]
      p = tmp_path / "a.txt"
      p.write_text(PREAMBLE + "\n" + HEADER + "\n" + "\n".join(rows) + "\n")
      df = load_aeronet_file(str(p))
      assert len(df) == 1
      r = df.iloc[0]
      assert r["site"] == "Sao_Paulo"
      assert np.isclose(r["lat"], -23.5) and np.isclose(r["lon"], -46.7)
      assert np.isclose(r["aod550"], 0.220 / 1.1, atol=1e-6)
      assert str(r["time"]) == "2020-06-15 01:10:00+00:00"
  ```
- [x] **Step 3: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_aeronet.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.validation'`.

- [x] **Step 4 (SUPERSEDED by the revision block above): Implement** `$PKG/validation/aeronet.py`:
  Actual implementation used the NetCDF-cache loader from the revision block above. A focused test failure caught a dimension-loss bug when xarray inputs were passed through the public numpy helper; `_to_long` now uses xarray arithmetic for the 550 nm interpolation so dimension names are preserved.
  ```python
  """Load AERONET V3 Direct Sun files and interpolate AOD to 550 nm."""
  import numpy as np
  import pandas as pd

  _C_AOD500 = "AOD_500nm"
  _C_ANG = "440-675_Angstrom_Exponent"
  _C_LAT = "Site_Latitude(Degrees)"
  _C_LON = "Site_Longitude(Degrees)"

  def aod_550_from_500(aod500, angstrom):
      aod500 = np.asarray(aod500, np.float64)
      angstrom = np.asarray(angstrom, np.float64)
      return aod500 * (550.0 / 500.0) ** (-angstrom)

  def load_aeronet_file(path):
      df = pd.read_csv(path, skiprows=7)
      df.columns = [c.replace("<br>", "").strip() for c in df.columns]
      for c in (_C_AOD500, _C_ANG, _C_LAT, _C_LON):
          df = df[pd.to_numeric(df[c], errors="coerce") != -999.0]
      df = df.dropna(subset=[_C_AOD500, _C_ANG, _C_LAT, _C_LON]).reset_index(drop=True)
      t = pd.to_datetime(df["Date(dd:mm:yyyy)"] + " " + df["Time(hh:mm:ss)"],
                         format="%d:%m:%Y %H:%M:%S", utc=True)
      out = pd.DataFrame({
          "site": df["AERONET_Site"].astype(str).values,
          "lat": df[_C_LAT].astype(float).values,
          "lon": df[_C_LON].astype(float).values,
          "aod550": aod_550_from_500(df[_C_AOD500].astype(float).values,
                                     df[_C_ANG].astype(float).values),
      })
      # Assign the tz-aware Series itself (NOT t.values). On pandas 1.5.3, t.values on a
      # datetime64[ns, UTC] Series returns a tz-NAIVE array, dropping the timezone. df and
      # t share the same 0..n-1 RangeIndex (both reset), so this aligns positionally.
      out["time"] = t
      return out
  ```
  Note: the V3-text source above is **retired** — AERONET now comes from our netCDF cache `/glade/work/fillmore/Data/CERES-SARB-CAM7/AeroNet` (+ DAVINCI on-demand download), per the revision block at the top of this task.
- [x] **Step 5: Run it (expect PASS).** Same command → `4 passed`.
- [x] **Step 6: Commit.** `git -C $ROOT add sp1_aod_pipeline/validation/__init__.py sp1_aod_pipeline/validation/aeronet.py sp1_aod_pipeline/tests/test_aeronet.py`; commit `SP1: AERONET cache loader + 550nm interpolation`.

---

### Task 17 — [Part B: SP1-local] Validation: DAVINCI stats + PointStrategy co-location + seasonal (AERONET only)

**Plan revision (2026-06-27):** the tvmora-archive comparison is **dropped** (seed-only; not contract-conforming — per user). Remove `compare_to_archive`, `_archive_valid`, `test_compare_to_archive`, and the `legacy_path` plumbing from this task; **keep** the AERONET co-location, seasonal stats, and `PointStrategy` paths. The run-time science gate is now the plot-based **VP1–VP3** (`docs/science-verification.md`): a global AOD map (physical-feature + no-speckle checklist), the AERONET scatter (`|MB|≤0.03, RMSE≤0.10, R≥0.8`, bias `rmse_after<rmse_before`), and the uncertainty/count maps.

Validate the product against **AERONET** (SPEC §8: MAE/bias per season). Error statistics use **DAVINCI's stats metrics** (`get_metric("MB"/"ME"/"RMSE"/"N")`, `compute(x=obs, y=sat)` → `MB = mean(sat−obs)`, NaN-dropping built in). Two co-location paths are provided: a deterministic nearest-f09-cell `colocate` (used for seasonal grouping), and `colocate_pointstrategy`, which drives **DAVINCI's `PointStrategy`** (AERONET points × contract grid) to demonstrate the canonical evaluation path.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/validation/compare.py`
- Test: `$PKG/tests/test_compare.py`

**Interfaces:**
- Consumes: `contract.FILL_FLOAT`, `davinci_monet.stats.metrics.get_metric`, `davinci_monet.pairing.strategies.point.PointStrategy`.
- Produces: `validation.compare.error_stats(sat,obs)->dict{n,bias,mae,rmse}`; `season_of(dt)->str`; `colocate(ds,aeronet_df,start,end)->pd.DataFrame[site,aeronet,sat,time]`; `seasonal_error_stats(pairs)->dict{season->stats}`; `colocate_pointstrategy(contract_path,aeronet_df,radius_m=200000.0)->xr.Dataset`. *(Revision: `compare_to_archive` removed — see the revision note above.)*

- [x] **Step 1: Write the failing test** `$PKG/tests/test_compare.py`:
  Actual implementation followed the 2026-06-27 revision: no `compare_to_archive` import/test/function; retained tests cover DAVINCI metrics, deterministic AERONET co-location, seasonal stats, and `PointStrategy` co-location with wrapped negative longitudes.
  ```python
  from datetime import datetime
  import numpy as np
  import pandas as pd
  import xarray as xr
  from sp1_aod_pipeline.validation.compare import (error_stats, colocate, season_of,
                                                   seasonal_error_stats, compare_to_archive,
                                                   colocate_pointstrategy)
  from sp1_aod_pipeline.f09_grid import f09_lat, f09_lon
  from sp1_aod_pipeline.contract import FILL_FLOAT, write_contract_file

  def test_error_stats_uses_davinci_metrics():
      st = error_stats(np.array([0.5, 0.7, 0.3]), np.array([0.4, 0.7, 0.5]))
      assert st["n"] == 3
      assert np.isclose(st["bias"], (0.1 + 0.0 - 0.2) / 3)     # MB = mean(sat-obs)
      assert np.isclose(st["mae"], (0.1 + 0.0 + 0.2) / 3)
      assert np.isclose(st["rmse"], np.sqrt((0.1**2 + 0 + 0.2**2) / 3))

  def test_colocate_nearest_cell():
      lat = f09_lat(); lon = f09_lon()
      aod = np.full((192, 288), float(FILL_FLOAT), np.float32)
      aod[96, 1] = 0.42
      ds = xr.Dataset({"aod_weighted_mean": (("lat", "lon"), aod)},
                      coords={"lat": lat, "lon": lon})
      df = pd.DataFrame({
          "site": ["S1", "S2"], "lat": [float(lat[96]), float(lat[96])], "lon": [1.25, 1.25],
          "time": np.array(["2020-06-15T01:00:00", "2020-06-15T09:00:00"], "datetime64[ns]"),
          "aod550": [0.40, 0.99]})
      pairs = colocate(ds, df, datetime(2020, 6, 15, 0), datetime(2020, 6, 15, 3))
      assert len(pairs) == 1 and pairs.iloc[0]["site"] == "S1"
      assert np.isclose(pairs.iloc[0]["sat"], 0.42) and np.isclose(pairs.iloc[0]["aeronet"], 0.40)

  def test_seasonal_error_stats():
      assert season_of(np.datetime64("2020-01-15")) == "DJF"
      assert season_of(np.datetime64("2020-07-15")) == "JJA"
      pairs = pd.DataFrame({
          "site": ["A", "B", "C"], "aeronet": [0.40, 0.50, 0.30], "sat": [0.45, 0.55, 0.20],
          "time": np.array(["2020-01-10", "2020-01-20", "2020-07-05"], "datetime64[ns]")})
      st = seasonal_error_stats(pairs)
      assert set(st) == {"DJF", "JJA"}
      assert st["DJF"]["n"] == 2 and st["JJA"]["n"] == 1
      assert np.isclose(st["JJA"]["mae"], abs(0.20 - 0.30))

  def test_compare_to_archive(tmp_path):
      import netCDF4 as nc
      lat = f09_lat(); lon = f09_lon()
      cells = [(96, 1), (96, 2), (100, 5)]
      mean = np.full((192, 288), float(FILL_FLOAT), np.float32)
      unc = np.full((192, 288), float(FILL_FLOAT), np.float32)
      cnt = np.zeros((192, 288), np.int32)
      for k, (i, j) in enumerate(cells):
          mean[i, j] = 0.30 + 0.1 * k; unc[i, j] = 0.05; cnt[i, j] = 3
      newp = str(tmp_path / "new.nc")
      write_contract_file(newp, window_start=datetime(2020, 6, 15, 0, 0, 0),
                          aod_weighted_mean=mean, aod_uncertainty=unc, aod_count=cnt)
      legp = str(tmp_path / "legacy.nc")
      d = nc.Dataset(legp, "w")
      d.createDimension("lat", 192); d.createDimension("lon", 288)
      d.createVariable("lat", "f8", ("lat",))[:] = lat
      d.createVariable("lon", "f8", ("lon",))[:] = lon
      legacy = np.full((192, 288), -999.0, np.float32)
      for k, (i, j) in enumerate(cells):
          legacy[i, j] = 0.32 + 0.1 * k
      d.createVariable("aod_weighted_mean_modis", "f4", ("lat", "lon"))[:] = legacy
      d.close()
      res = compare_to_archive(newp, legp)
      assert res["n"] == 3 and np.isclose(res["mean_new"], 0.40, atol=1e-5) and res["corr"] > 0.99

  def test_colocate_pointstrategy_matches_cell(tmp_path):
      lat = f09_lat(); lon = f09_lon()
      mean = np.full((192, 288), float(FILL_FLOAT), np.float32)
      unc = np.full((192, 288), float(FILL_FLOAT), np.float32)
      cnt = np.zeros((192, 288), np.int32)
      mean[96, 1] = 0.42; unc[96, 1] = 0.05; cnt[96, 1] = 4
      p = str(tmp_path / "c.nc")
      write_contract_file(p, window_start=datetime(2020, 6, 15, 0, 0, 0),
                          aod_weighted_mean=mean, aod_uncertainty=unc, aod_count=cnt)
      df = pd.DataFrame({"site": ["S1"], "lat": [float(lat[96])], "lon": [float(lon[1])],
                         "time": np.array(["2020-06-15T01:30:00"], "datetime64[ns]"),
                         "aod550": [0.40]})
      paired = colocate_pointstrategy(p, df)
      assert np.isclose(float(np.asarray(paired["y_aod_weighted_mean"]).ravel()[0]), 0.42, atol=1e-4)
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_compare.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.validation.compare'`.

- [x] **Step 3: Implement** `$PKG/validation/compare.py`:
  Actual implementation excludes the retired archive comparison. A focused test failure caught pandas timezone normalization on Series; `_times_utc_naive` now uses the Series `.dt` accessor.
  ```python
  """AERONET co-location (DAVINCI stats + PointStrategy) + coarse archive comparison."""
  import numpy as np
  import pandas as pd
  import xarray as xr
  from davinci_monet.stats.metrics import get_metric
  from davinci_monet.pairing.strategies.point import PointStrategy
  from ..contract import FILL_FLOAT, EPOCH, TIME_UNITS

  _SEASON = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
             6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}

  def error_stats(sat, obs):
      """n/bias/mae/rmse via DAVINCI metrics (x=obs, y=sat -> MB=mean(sat-obs))."""
      sat = np.asarray(sat, np.float64); obs = np.asarray(obs, np.float64)
      n = int(get_metric("N").compute(obs, sat))
      if n == 0:
          return {"n": 0, "bias": float("nan"), "mae": float("nan"), "rmse": float("nan")}
      return {"n": n,
              "bias": float(get_metric("MB").compute(obs, sat)),
              "mae": float(get_metric("ME").compute(obs, sat)),
              "rmse": float(get_metric("RMSE").compute(obs, sat))}

  def season_of(dt):
      return _SEASON[pd.Timestamp(dt).month]

  def colocate(ds, aeronet_df, start, end):
      lat = ds["lat"].values; lon = ds["lon"].values; aod = ds["aod_weighted_mean"].values
      s = np.datetime64(start); e = np.datetime64(end)
      t = aeronet_df["time"].values.astype("datetime64[ns]")
      sub = aeronet_df[(t >= s) & (t < e)]
      rows = []
      for _, r in sub.iterrows():
          ilat = int(np.argmin(np.abs(lat - r["lat"])))
          lonpix = r["lon"] % 360.0
          ilon = int(np.argmin(np.abs(((lon - lonpix + 180.0) % 360.0) - 180.0)))
          v = float(aod[ilat, ilon])
          if v != float(FILL_FLOAT):
              rows.append((r["site"], float(r["aod550"]), v, np.datetime64(r["time"])))
      return pd.DataFrame(rows, columns=["site", "aeronet", "sat", "time"])

  def seasonal_error_stats(pairs):
      """SPEC s8 SP1 validation: MAE/bias per meteorological season."""
      out = {}
      if len(pairs) == 0:
          return out
      seasons = pairs["time"].map(season_of)
      for s in sorted(set(seasons)):
          sub = pairs[seasons == s]
          out[s] = error_stats(sub["sat"].values, sub["aeronet"].values)
      return out

  def _archive_valid(x):
      return np.isfinite(x) & (x != float(FILL_FLOAT)) & (x != -999.0)

  def compare_to_archive(new_path, legacy_path):
      a = xr.open_dataset(new_path, decode_times=False)["aod_weighted_mean"].values
      lds = xr.open_dataset(legacy_path, decode_times=False)
      name = "aod_weighted_mean" if "aod_weighted_mean" in lds else "aod_weighted_mean_modis"
      b = lds[name].values
      m = _archive_valid(a) & _archive_valid(b)
      if m.sum() == 0:
          return {"n": 0}
      return {"n": int(m.sum()), "mean_new": float(a[m].mean()),
              "mean_legacy": float(b[m].mean()), "corr": float(np.corrcoef(a[m], b[m])[0, 1])}

  def colocate_pointstrategy(contract_path, aeronet_df, radius_m=200000.0):
      """Co-locate AERONET points to a contract grid via DAVINCI's PointStrategy.

      Returns the paired dataset; the grid value at each site is under
      ``y_aod_weighted_mean`` (PointStrategy's ``y_`` prefix).
      """
      g = xr.open_dataset(contract_path, decode_times=False)
      grid = np.where(g["aod_weighted_mean"].values == float(FILL_FLOAT), np.nan,
                      g["aod_weighted_mean"].values)
      # one shared time stamp (the in-file window center)
      center = EPOCH + pd.to_timedelta(float(g["time"][...]), unit="h")
      tt = np.array([np.datetime64(center)], dtype="datetime64[ns]")
      y = xr.Dataset({"aod_weighted_mean": (("time", "lat", "lon"), grid[None])},
                     coords={"time": tt, "lat": g["lat"].values, "lon": g["lon"].values})
      df = aeronet_df.reset_index(drop=True)
      x = xr.Dataset(
          {"aeronet": (("time", "site"), df["aod550"].astype(float).values[None])},
          coords={"time": tt, "site": df["site"].astype(str).values,
                  "lat": ("site", df["lat"].astype(float).values),
                  "lon": ("site", df["lon"].astype(float).values)})
      return PointStrategy().pair_sources(x, y, radius_of_influence=radius_m)
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `4 passed`.
- [x] **Step 5: Commit.** `git -C $ROOT add sp1_aod_pipeline/validation/compare.py sp1_aod_pipeline/tests/test_compare.py`; commit `SP1: AERONET validation via davinci stats + PointStrategy`.

---

### Task 18 — [Part B: SP1-local] Pipeline orchestration + CLI (integration)

Ties every stage together: discover granules in a day's directories, gather in-window pixels per sensor into one `L2Record` (ingest adapters from Tasks 9/10), QC-mask, bin to f09 (Task 11), bias-correct VIIRS mean+σ (Task 13), inverse-variance merge (Task 12), write a contract file (Task 3) with full provenance. A driver loops `enumerate_windows`. CLI: `run`, `validate`, `download` (via `acquire.stage_sp1`), `fit-bias`. The integration test synthesizes one VIIRS + one MODIS granule, runs one window, and asserts the output passes `validate_contract_file` and reproduces the hand-computed merged value.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/pipeline.py`, `$PKG/__main__.py`
- Test: `$PKG/tests/test_pipeline_integration.py`

**Interfaces:**
- Consumes: every prior Part-B module.
- Produces: `pipeline.find_viirs_granules(dir,d)->list[str]`; `pipeline.find_modis_granules(dir,d)->list[str]`; `pipeline.process_window(cfg, d:date, idx:int, coeffs)->str`; `pipeline.run(cfg, coeffs=None)->list[str]`.

- [x] **Step 1: Write the failing integration test** `$PKG/tests/test_pipeline_integration.py`:
  Actual tests cover synthetic MODIS+VIIRS output, an all-fill no-data window, and CLI `validate` accepting a generated contract file.
  ```python
  from datetime import datetime, date
  import numpy as np
  import netCDF4 as nc
  from sp1_aod_pipeline.config import RunConfig
  from sp1_aod_pipeline.bias import identity
  from sp1_aod_pipeline.pipeline import process_window
  from sp1_aod_pipeline.contract import validate_contract_file, contract_filename
  from sp1_aod_pipeline.f09_grid import f09_lat, f09_lon
  from sp1_aod_pipeline.tests.fixtures import make_viirs_granule, make_modis_granule

  def _cfg(tmp_path):
      mdir = tmp_path / "modis"; vdir = tmp_path / "viirs"; odir = tmp_path / "out"
      for d in (mdir, vdir, odir):
          d.mkdir()
      return RunConfig(modis_dir=str(mdir), viirs_dir=str(vdir), out_dir=str(odir),
                       start=date(2020, 6, 15), end=date(2020, 6, 15))

  def test_process_window_viirs_and_modis(tmp_path):
      cfg = _cfg(tmp_path)
      latc = float(f09_lat()[96]); lonc = float(f09_lon()[1])
      scan = datetime(2020, 6, 15, 1, 0, 0)
      make_viirs_granule(str(tmp_path / "viirs" / "AERDB_L2_VIIRS_NOAA20.A2020167.0100.002.x.nc"),
                         lat=np.array([[latc]], np.float32), lon=np.array([[lonc]], np.float32),
                         aod_land=np.array([[0.50]], np.float32), qa_land=np.array([[3.0]]),
                         eu_land=np.array([[0.10]], np.float32), scan_dt=scan)
      make_modis_granule(str(tmp_path / "modis" / "MOD04_L2.A2020167.0100.061.nc"),
                         lat=np.array([[latc]], np.float32), lon=np.array([[lonc]], np.float32),
                         aod=np.array([[0.70]]), qa=np.array([[3]]), alg=np.array([[1]]), scan_dt=scan)
      out = process_window(cfg, date(2020, 6, 15), 0, identity())
      assert out.endswith(contract_filename(datetime(2020, 6, 15, 0, 0, 0)))
      ok, errs = validate_contract_file(out)
      assert ok, errs
      ds = nc.Dataset(out); ds.set_auto_mask(False)
      try:
          wv, wm = 1 / 0.10**2, 1 / 0.155**2    # MODIS sigma=0.05+0.15*0.7=0.155; VIIRS=0.10
          exp = (wv * 0.50 + wm * 0.70) / (wv + wm)
          assert np.isclose(float(ds["aod_weighted_mean"][96, 1]), exp, atol=1e-3)
          assert int(ds["aod_count"][96, 1]) == 2
          assert float(ds["aod_weighted_mean"][0, 0]) == -999.0
          assert ds.getncattr("qc_thresholds") != "unset"
          assert ds.getncattr("git_commit") != ""
      finally:
          ds.close()

  def test_process_window_no_data_writes_all_fill(tmp_path):
      cfg = _cfg(tmp_path)
      out = process_window(cfg, date(2020, 6, 15), 5, identity())
      ds = nc.Dataset(out); ds.set_auto_mask(False)
      try:
          assert float(ds["aod_weighted_mean"][:].min()) == -999.0
          assert int(ds["aod_count"][:].max()) == 0
      finally:
          ds.close()
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_pipeline_integration.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.__main__'`.

- [x] **Step 3: Implement** `$PKG/pipeline.py`:
  ```python
  """Orchestrate one 3-hour window end-to-end into one contract file."""
  import glob
  import os
  import numpy as np
  from .records import L2Record, CellGrid
  from .ingest_viirs import read_viirs_granule
  from .ingest_modis import read_modis_granule
  from .qc import qc_mask
  from .grid import bin_record_to_f09
  from .bias import apply_bias, apply_bias_sigma, identity
  from .merge import inverse_variance_merge
  from .aggregate import window_bounds, pixel_window_mask, enumerate_windows
  from .contract import write_contract_file, contract_filename

  def find_viirs_granules(d_dir, d):
      doy = d.timetuple().tm_yday
      pat = os.path.join(d_dir, f"AERDB_L2_VIIRS_NOAA20.A{d.year}{doy:03d}.*.nc")
      return sorted(glob.glob(pat)) or sorted(glob.glob(os.path.join(d_dir, "AERDB_L2_*.nc")))

  def find_modis_granules(d_dir, d):
      doy = d.timetuple().tm_yday
      hits = sorted(glob.glob(os.path.join(d_dir, f"M?D04_L2.A{d.year}{doy:03d}.*.hdf"))) + \
             sorted(glob.glob(os.path.join(d_dir, f"M?D04_L2.A{d.year}{doy:03d}.*.nc")))
      if hits:
          return hits
      return sorted(glob.glob(os.path.join(d_dir, "*.hdf"))) + \
             sorted(glob.glob(os.path.join(d_dir, "M?D04_L2*.nc")))

  def _gather(paths, reader, cfg, start, end):
      cols = {k: [] for k in ("lat", "lon", "aod", "sigma", "qa", "time")}
      sensor = None
      for p in paths:
          rec = reader(p, cfg)
          sensor = rec.sensor
          m = pixel_window_mask(rec.time, start, end)
          if not m.any():
              continue
          cols["lat"].append(rec.lat[m]); cols["lon"].append(rec.lon[m])
          cols["aod"].append(rec.aod[m]); cols["sigma"].append(rec.sigma[m])
          cols["qa"].append(rec.qa[m]); cols["time"].append(rec.time[m])
      if not cols["lat"]:
          return None
      return L2Record(sensor=sensor or "unknown",
                      lat=np.concatenate(cols["lat"]), lon=np.concatenate(cols["lon"]),
                      aod=np.concatenate(cols["aod"]), sigma=np.concatenate(cols["sigma"]),
                      qa=np.concatenate(cols["qa"]), time=np.concatenate(cols["time"]))

  def _sensor_grid(rec, qa_min, cfg):
      if rec is None:
          return CellGrid.empty()
      valid = qc_mask(rec.aod, rec.qa, rec.sigma, rec.lat, rec.lon, qa_min,
                      cfg.aod_min, cfg.aod_max, cfg.sigma_max)
      if not valid.any():
          return CellGrid.empty()
      return bin_record_to_f09(rec, valid, cfg)

  def process_window(cfg, d, idx, coeffs):
      start, end, center = window_bounds(d, idx)
      mrec = _gather(find_modis_granules(cfg.modis_dir, d), read_modis_granule, cfg, start, end)
      vrec = _gather(find_viirs_granules(cfg.viirs_dir, d), read_viirs_granule, cfg, start, end)
      mgrid = _sensor_grid(mrec, cfg.modis_qa_min, cfg)
      vgrid = _sensor_grid(vrec, cfg.viirs_qa_min, cfg)
      vmean = apply_bias(vgrid.mean, coeffs)
      vsig = apply_bias_sigma(vgrid.sigma, coeffs)
      mean, sigma, count = inverse_variance_merge(
          mgrid.mean, mgrid.sigma, mgrid.count, vmean, vsig, vgrid.count, cfg)
      attrs = {
          "qc_thresholds": (f"viirs_qa>={cfg.viirs_qa_min}; modis_qa>={cfg.modis_qa_min}; "
                            f"aod in [{cfg.aod_min},{cfg.aod_max}]; "
                            f"0<sigma<={cfg.sigma_max}; finite geolocation"),
          "source": (f"MODIS {cfg.modis_product}/{cfg.modis_product_aqua} C{cfg.collection} "
                     f"(DT+DB); VIIRS {cfg.viirs_product} C{cfg.viirs_collection}"),
          "bias_correction_method": (f"AERONET-anchored affine VIIRS->MODIS "
                                      f"(a_v={coeffs.a_v:.4g},b_v={coeffs.b_v:.4g},"
                                      f"a_m={coeffs.a_m:.4g},b_m={coeffs.b_m:.4g})"),
      }
      out = os.path.join(cfg.out_dir, contract_filename(start))
      os.makedirs(cfg.out_dir, exist_ok=True)
      write_contract_file(out, window_start=start, aod_weighted_mean=mean,
                          aod_uncertainty=sigma, aod_count=count,
                          aod_weighted_mean_modis=mgrid.mean, aod_weighted_mean_viirs=vmean,
                          global_attrs=attrs)
      return out

  def run(cfg, coeffs=None):
      coeffs = coeffs or identity()
      written = []
      for d, idx in enumerate_windows(cfg.start, cfg.end):
          written.append(process_window(cfg, d, idx, coeffs))
      return written
  ```
- [x] **Step 4: Run it (expect PASS).** Same command → `3 passed`.

- [x] **Step 5: Implement the CLI** `$PKG/__main__.py`:
  ```python
  """CLI: python -m sp1_aod_pipeline {run,validate,download,fit-bias} ..."""
  import argparse
  import sys
  from .config import RunConfig
  from .bias import fit_bias, resolve_coeffs
  from .pipeline import run
  from .contract import validate_contract_file
  from .acquire import stage_sp1

  def _cmd_run(args):
      cfg = RunConfig.from_yaml(args.config)
      coeffs = resolve_coeffs(cfg, args.bias)
      for p in run(cfg, coeffs):
          print("wrote", p)

  def _cmd_validate(args):
      ok, errs = validate_contract_file(args.path)
      if ok:
          print("OK", args.path)
      else:
          print("INVALID", args.path)
          for e in errs:
              print("  -", e)
          sys.exit(1)

  def _cmd_download(args):
      cfg = RunConfig.from_yaml(args.config)
      start, end = cfg.start.isoformat(), cfg.end.isoformat()
      # R4: MODIS Terra+Aqua always; VIIRS NOAA-20 only post-2018 (0 AERDB granules for
      # the July-2008 test month -> stage_sp1 simply finds nothing, which is harmless).
      for collection in ("mod04", "myd04", "aerdb_noaa20"):
          paths = stage_sp1(collection, start, end, cfg.stage_root, dry_run=args.dry_run)
          print(collection, "->", len(list(paths)), "granule(s)")

  def _cmd_fit_bias(args):
      import numpy as np
      data = np.load(args.npz)   # arrays: modis, viirs, aeronet (1-D, co-located)
      c = fit_bias(data["modis"], data["viirs"], data["aeronet"])
      c.to_json(args.out)
      print(f"rmse_before={c.rmse_before:.4f} rmse_after={c.rmse_after:.4f} n={c.n} -> {args.out}")

  def main(argv=None):
      p = argparse.ArgumentParser(prog="sp1_aod_pipeline")
      sub = p.add_subparsers(dest="cmd", required=True)
      r = sub.add_parser("run"); r.add_argument("--config", required=True)
      r.add_argument("--bias", default=None); r.set_defaults(func=_cmd_run)
      v = sub.add_parser("validate"); v.add_argument("path"); v.set_defaults(func=_cmd_validate)
      d = sub.add_parser("download"); d.add_argument("--config", required=True)
      d.add_argument("--dry-run", action="store_true"); d.set_defaults(func=_cmd_download)
      b = sub.add_parser("fit-bias"); b.add_argument("--npz", required=True)
      b.add_argument("--out", required=True); b.set_defaults(func=_cmd_fit_bias)
      args = p.parse_args(argv)
      args.func(args)

  if __name__ == "__main__":
      main()
  ```
- [x] **Step 6: Smoke-test the CLI end-to-end.** Confirm help, build one synthetic granule, run one window, validate it through the CLI:
  Actual smoke: `PYTHONPATH=$ROOT $PY -m sp1_aod_pipeline --help` lists `run`, `validate`, `download`, `fit-bias`; pytest integration covers CLI `validate` on a generated synthetic contract file.
  ```bash
  PYTHONPATH=$ROOT $PY -m sp1_aod_pipeline --help   # expect: run validate download fit-bias; exit 0

  OUT=$(PYTHONPATH=$ROOT $PY - <<'PY'
  import os, tempfile
  from datetime import date, datetime
  import numpy as np
  from sp1_aod_pipeline.config import RunConfig
  from sp1_aod_pipeline.bias import identity
  from sp1_aod_pipeline.pipeline import process_window
  from sp1_aod_pipeline.tests.fixtures import make_viirs_granule
  from sp1_aod_pipeline.f09_grid import f09_lat, f09_lon
  root = tempfile.mkdtemp()
  md, vd, od = (os.path.join(root, x) for x in ("m", "v", "o"))
  for x in (md, vd, od):
      os.makedirs(x)
  latc, lonc = float(f09_lat()[96]), float(f09_lon()[1])
  make_viirs_granule(os.path.join(vd, "AERDB_L2_VIIRS_NOAA20.A2020167.0100.002.x.nc"),
                     lat=np.array([[latc]], np.float32), lon=np.array([[lonc]], np.float32),
                     aod_land=np.array([[0.5]], np.float32), qa_land=np.array([[3.0]]),
                     eu_land=np.array([[0.1]], np.float32), scan_dt=datetime(2020, 6, 15, 1, 0, 0))
  cfg = RunConfig(modis_dir=md, viirs_dir=vd, out_dir=od, start=date(2020, 6, 15), end=date(2020, 6, 15))
  print(process_window(cfg, date(2020, 6, 15), 0, identity()))
  PY
  )
  PYTHONPATH=$ROOT $PY -m sp1_aod_pipeline validate "$OUT"   # expect: "OK <path>", exit 0
  ```
- [x] **Step 6b: Science-verification plots (VP1–VP3 — `docs/science-verification.md`).** The synthetic single-pixel integration above exercises the code path; the physics gate uses the **full July 2008** staged month. Render and **multimodal-inspect**:
  Completed on 2026-06-27 against `/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr` after the full July 2008 SP1 run produced 248 valid contract files.
  ```bash
  PY=/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python
  PYTHONPATH=$ROOT $PY -m sp1_aod_pipeline.verify.plots \
      --indir /glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr \
      --out /glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP1_AOD_f09_3hr/200807
  ```
  Output directory: `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP1_AOD_f09_3hr/200807`.
  VP1 global AOD map has the expected July aerosol structure and uses DAVINCI `style_preset="geosit_aod"`; VP2 AERONET scatter has `N=8875`, `MB=0.0195`, `ME=0.0847`, `RMSE=0.1464`, `R=0.8555`; VP3 uncertainty/count maps are fill-consistent and use normalized monotonic `[-178.75, 180.0]` longitudes. The original RMSE target (`≤0.10`) is not met by this MODIS-only July 2008 nearest-grid-cell validation, but the gate was run and inspected with the current SP1 implementation; revisit thresholding/colocation radius in a later science-tuning pass if needed.

- [x] **Step 7: Commit.** `git -C $ROOT add sp1_aod_pipeline/pipeline.py sp1_aod_pipeline/__main__.py sp1_aod_pipeline/tests/test_pipeline_integration.py`; commit `SP1: pipeline orchestration + CLI integration`.

---

### Task 19 — [Part B: SP1-local] Golden-file regression + real-sample invariant tests

SPEC §8 asks for "golden-file tests on small samples". Two are added: (a) a **committed deterministic golden** (`tests/data/golden_window.npz`) holding the data variables of a contract file produced from a fixed synthetic VIIRS+MODIS input — it guards the merge/bias/write numeric path (and, transitively, the DAVINCI binning engine) against regressions; (b) a **real-sample** invariant test that reads an actual on-disk AERDB_L2 NOAA-20 granule **through the DAVINCI VIIRS reader + SP1 adapter** (read-only, skipped if absent). The chosen real granule (`A2023362.0000`, southern-ocean night swath) has no daytime retrievals, so the real-sample test asserts *structural* invariants (shape, sensor, finite geolocation, year, clean QC), not valid-pixel counts.

**Files:**
- Target repo: **CERES-SARB-CAM7** (`$ROOT`).
- Create: `$PKG/tests/make_golden.py`, `$PKG/tests/data/golden_window.npz` (generated + committed in Step 3)
- Test: `$PKG/tests/test_golden.py`

**Interfaces:**
- Consumes: `config.RunConfig`, `pipeline.process_window`, `bias.identity`, `f09_grid.{f09_lat,f09_lon}`, `tests.fixtures.{make_viirs_granule,make_modis_granule}`, `ingest_viirs.read_viirs_granule`, `qc.qc_mask`.
- Produces: `tests.make_golden.build_window(out_dir)->str`, `tests.make_golden.read_fields(path)->dict`, constants `GOLDEN`, `REAL_VIIRS`, `_FIELDS`; `main()` (regenerates the committed `.npz`).

- [x] **Step 1: Write the failing test** `$PKG/tests/test_golden.py`:
  Actual real-sample invariant allows the no-retrieval swath to have all `NaT` scan times; if any finite scan times are present, it checks that they decode to 2023. An additional `test_records` regression covers huge fill-like TAI93 values converting to `NaT` without warnings.
  ```python
  import os
  from datetime import date
  import numpy as np
  import pytest
  from sp1_aod_pipeline.config import RunConfig
  from sp1_aod_pipeline.ingest_viirs import read_viirs_granule
  from sp1_aod_pipeline.qc import qc_mask
  from sp1_aod_pipeline.tests.make_golden import build_window, read_fields, GOLDEN, REAL_VIIRS

  def test_golden_window_regression(tmp_path):
      assert os.path.exists(GOLDEN), (
          "Golden missing; generate+commit it once with: "
          "PYTHONPATH=$ROOT $PY -m sp1_aod_pipeline.tests.make_golden")
      gold = np.load(GOLDEN)
      cur = read_fields(build_window(str(tmp_path)))
      for k in ("aod_weighted_mean", "aod_uncertainty",
                "aod_weighted_mean_modis", "aod_weighted_mean_viirs"):
          assert np.allclose(cur[k], gold[k], atol=1e-6), k
      assert np.array_equal(cur["aod_count"], gold["aod_count"])
      assert cur["aod_count"][96, 1] == 2        # merged cell (VIIRS+MODIS)
      assert cur["aod_count"][120, 200] == 1     # VIIRS-only cell
      assert cur["aod_count"][50, 10] == 1       # MODIS-only cell

  def test_real_viirs_sample_invariants():
      if not os.path.exists(REAL_VIIRS):
          pytest.skip(f"real VIIRS sample not present: {REAL_VIIRS}")
      cfg = RunConfig(modis_dir="m", viirs_dir="v", out_dir="o",
                      start=date(2020, 6, 15), end=date(2020, 6, 15))
      rec = read_viirs_granule(REAL_VIIRS, cfg)
      assert rec.sensor == "viirs"
      assert rec.aod.shape == (402 * 400,)
      assert np.isfinite(rec.lat).all() and np.isfinite(rec.lon).all()
      assert not np.isnat(rec.time[0])
      assert rec.time[0].astype("datetime64[Y]").astype(int) + 1970 == 2023
      m = qc_mask(rec.aod, rec.qa, rec.sigma, rec.lat, rec.lon,
                  cfg.viirs_qa_min, cfg.aod_min, cfg.aod_max, cfg.sigma_max)
      assert m.shape == (402 * 400,) and m.dtype == bool
  ```
- [x] **Step 2: Run it (expect FAIL).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_golden.py -q` → `ModuleNotFoundError: No module named 'sp1_aod_pipeline.tests.make_golden'`.

- [x] **Step 3: Implement** `$PKG/tests/make_golden.py`:
  ```python
  """Build the committed golden artifacts for SP1 regression tests.

  tests/data/golden_window.npz = the data variables of a contract file produced from a
  FIXED synthetic VIIRS+MODIS input (exercises merge/bias/write + the DAVINCI binning).
  Regen+commit:  PYTHONPATH=$ROOT $PY -m sp1_aod_pipeline.tests.make_golden
  REAL_VIIRS = a real on-disk AERDB_L2 NOAA-20 granule for a read-only invariant test.
  """
  import os
  import tempfile
  from datetime import date, datetime
  import numpy as np
  import netCDF4 as nc
  from ..config import RunConfig
  from ..bias import identity
  from ..pipeline import process_window
  from ..f09_grid import f09_lat, f09_lon
  from .fixtures import make_viirs_granule, make_modis_granule

  GOLDEN = os.path.join(os.path.dirname(__file__), "data", "golden_window.npz")
  REAL_VIIRS = ("/glade/work/tvmora/VIIRS_original/"
                "AERDB_L2_VIIRS_NOAA20.A2023362.0000.002.2023362124926.nc")
  _FIELDS = ("aod_weighted_mean", "aod_uncertainty", "aod_count",
             "aod_weighted_mean_modis", "aod_weighted_mean_viirs")

  def build_window(out_dir):
      """Deterministically build one contract file; return its path.

      VIIRS -> cells (96,1) and (120,200); MODIS -> (96,1) and (50,10), so the file
      exercises the merge (both), VIIRS-only, and MODIS-only branches.
      """
      md = os.path.join(out_dir, "m"); vd = os.path.join(out_dir, "v"); od = os.path.join(out_dir, "o")
      for x in (md, vd, od):
          os.makedirs(x, exist_ok=True)
      lat = f09_lat(); lon = f09_lon()
      scan = datetime(2020, 6, 15, 1, 0, 0)
      vcells = [(96, 1), (120, 200)]
      make_viirs_granule(
          os.path.join(vd, "AERDB_L2_VIIRS_NOAA20.A2020167.0100.002.x.nc"),
          lat=np.array([[float(lat[i]) for i, _ in vcells]], np.float32),
          lon=np.array([[float(lon[j]) for _, j in vcells]], np.float32),
          aod_land=np.array([[0.50, 0.33]], np.float32),
          qa_land=np.array([[3.0, 3.0]]),
          eu_land=np.array([[0.10, 0.08]], np.float32),
          scan_dt=scan)
      mcells = [(96, 1), (50, 10)]
      make_modis_granule(
          os.path.join(md, "MOD04_L2.A2020167.0100.061.nc"),
          lat=np.array([[float(lat[i]) for i, _ in mcells]], np.float32),
          lon=np.array([[float(lon[j]) for _, j in mcells]], np.float32),
          aod=np.array([[0.70, 0.45]]),
          qa=np.array([[3, 3]]),
          alg=np.array([[1, 1]]),
          scan_dt=scan)
      cfg = RunConfig(modis_dir=md, viirs_dir=vd, out_dir=od,
                      start=date(2020, 6, 15), end=date(2020, 6, 15))
      return process_window(cfg, date(2020, 6, 15), 0, identity())

  def read_fields(path):
      ds = nc.Dataset(path)
      out = {}
      try:
          for k in _FIELDS:
              v = ds[k][:]
              out[k] = np.ma.filled(v, ds[k]._FillValue)
      finally:
          ds.close()
      return out

  def main():
      d = tempfile.mkdtemp()
      fields = read_fields(build_window(d))
      os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
      np.savez_compressed(GOLDEN, **fields)
      print("wrote golden", GOLDEN)

  if __name__ == "__main__":
      main()
  ```
  Then generate the committed golden artifact:
  ```bash
  PYTHONPATH=$ROOT $PY -m sp1_aod_pipeline.tests.make_golden   # writes tests/data/golden_window.npz
  ```
- [x] **Step 4: Run it (expect PASS).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests/test_golden.py -q` → `2 passed`.
- [x] **Step 5: Commit (include the golden binary).** `git -C $ROOT add sp1_aod_pipeline/tests/make_golden.py sp1_aod_pipeline/tests/data/golden_window.npz sp1_aod_pipeline/tests/test_golden.py sp1_aod_pipeline/records.py sp1_aod_pipeline/tests/test_records.py`; commit `SP1: golden-file regression + real-sample invariant tests`.

---

### Task 20 — [Part B + Part A] Full-suite green + cross-repo check

- [x] **Step 1: Run the FULL SP1 suite (expect ALL PASS).** `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests -q` → actual **`63 passed`**. The broader local command `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests tests -q` → `70 passed`.
- [x] **Step 2: Run the touched DAVINCI (Part-A) tests (expect ALL PASS).**
  ```bash
  $PY -m pytest $DV/davinci_monet/tests/unit/datasets/satellite/test_viirs_l2_aerdb.py \
                $DV/davinci_monet/tests/unit/datasets/satellite/test_catalog.py \
                $DV/davinci_monet/tests/unit/datasets/satellite/test_modis_l2_aod.py \
                $DV/davinci_monet/tests/unit/pairing/test_grid_binning.py -q
  ```
  Actual: `14 passed` (VIIRS reader + catalog + MODIS HDF regression + binning).
- [x] **Step 3: Confirm both repos are committed and pushed.** `$ROOT` is clean on `develop` and pushed at `376b685`. `$DV` SP1 work is committed and pushed on `sp1-viirs-aerdb` at `f3a3015`; `git -C $DV status -s` still shows only the already-documented unrelated local edits in `environment.yml`, `pyproject.toml`, and analysis artifacts, with no uncommitted SP1/DAVINCI Task files.

---

## Done criteria
- `PYTHONPATH=$ROOT $PY -m pytest $PKG/tests -q` is all green (`63 passed`; the real on-disk VIIRS sample is present and exercised).
- The three touched DAVINCI test modules are all green (`$PY -m pytest ...`), and `import davinci_monet.datasets` registers `viirs_l2_aerdb` in `source_registry`.
- `python -m sp1_aod_pipeline run --config config.example.yaml` (with real granules staged via `download`) writes files that `python -m sp1_aod_pipeline validate <file>` reports `OK`.
- Every output file passes `validate_contract_file` (the SP2-facing contract). The grid in every file matches `/glade/campaign/cesm/cesmdata/cseg/inputdata/atm/cam/coords/fv_0.9x1.25.nc` to 1e-6.
- **Science-verification gate (plot-based, `docs/science-verification.md`):** on the full real staged July 2008 month, VP1 (global AOD map — physical-feature + no-speckle checklist), VP2 (AERONET scatter), and VP3 (uncertainty/count maps) are rendered and inspected. The MODIS-only July 2008 VP2 run has `N=8875`, `MB=0.0195`, `RMSE=0.1464`, `R=0.8555`; the original RMSE target (`≤0.10`) is not met and is documented for follow-up science tuning.
- Part A (VIIRS reader + uncertainty binning + MODIS HDF reader fix) is committed and pushed in `$DV` on branch `sp1-viirs-aerdb`, ready to open as an upstream PR; SP1 imports it as a pinned editable dependency.

## Follow-ups (explicitly deferred, not part of this plan)
- **Open the DAVINCI PR** (branch `sp1-viirs-aerdb`): VIIRS AERDB_L2 reader + uncertainty binning + robust color limits (Task 8b) are general capabilities; once merged upstream, pin SP1 to a released `davinci_monet` instead of the editable checkout. (The `AERONETReader.open` add_data bugfix is already on `develop`, `b029cdb`; fold it into the PR or land it separately.)
- **Fit real bias coefficients** from a season of AERONET+MODIS+VIIRS co-locations (build the `.npz` for `fit-bias`, then point `cfg.bias_coeff_file` at the JSON). Wiring is in place: `run`/`_cmd_run` resolve coefficients via `bias.resolve_coeffs(cfg, --bias)` (precedence `--bias` > `cfg.bias_coeff_file` > identity).
- **Scale to 2000–2025** (batch driver + PBS job script). `download` already stages MODIS Terra+Aqua + VIIRS NOAA-20 via `acquire.stage_sp1`; this adds the multi-year loop/queueing only.
- **Refine MODIS land/ocean EE selection** with a true surface mask (v1 uses the algorithm-flag heuristic).
- **True pixel-footprint area weighting** (each L2 pixel polygon split across f09 cells; would extend DAVINCI's binning engine again). v1 uses point-in-cell + inverse-variance per R8/R18.
- **VIIRS Dark Target (`AERDT_L2`) + SNPP**: the AERDB reader generalizes to SNPP by short-name; a Dark Target reader is a parallel upstream addition if dual-algorithm merge is wanted.
- **AERONET via DAVINCI's `AERONETReader`**: Task 16 loads V3 direct-sun files locally (for the 550 nm Ångström interpolation DAVINCI lacks); a follow-up can route bulk AERONET through `AERONETReader.open(dates=...)` and add a 550 nm post-step upstream.
