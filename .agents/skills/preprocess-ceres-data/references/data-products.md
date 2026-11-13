# CERES Run-Data Products

Read this reference when choosing a preprocessing path or auditing whether data are ready for a
CAM run.

## Product routing

| Product | Default location | Consumer | Meaning |
| --- | --- | --- | --- |
| Native MODIS/VIIRS L2 | `$DATA/MODIS_VIIRS_L2/` | SP1 | Version-pinned raw retrieval granules |
| AERONET Level 2.0 | `$DATA/AeroNet/` | Bias fitting and validation | Independent station AOD |
| CAM AOD forcing | `$DATA/AOD_f09_3hr/` | `aod_nudging_obs` | Frozen 3-hour f09 contract |
| MODIS-on-ERA5 diagnostic | `$DATA/MODIS_AOD_ERA5_GRID/` | DAVINCI analysis | Intermediate diagnostic, not CAM forcing |
| ERA5 met nudging | `/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl/` | CAM `nudging_nl` | Existing hourly f09/L32 model forcing |

Here `$DATA` is `/glade/work/fillmore/Data/CERES-SARB-CAM7`.

`scripts/stage_obs.py` organizes MODIS by dataset label and date, while the package `download`
command uses collection subpaths such as `modis/terra`, `modis/aqua`, and `viirs/noaa20`. SP1
ingestion searches recursively, but a production cache should use one layout consistently and
record which staging route created it.

## SP1 and DAVINCI boundary

`sp1_aod_pipeline` owns project-specific observation aggregation. It imports DAVINCI capabilities
for EarthData acquisition, MODIS/VIIRS reading, swath-to-grid binning, AERONET reading, pairing,
and statistics. It owns the project-specific QC, uncertainty handling, bias application,
three-hour aggregation, sensor merge, and contract writer.

DAVINCI YAML owns all plots and visual science gates. Preprocessing code may write NetCDF and
numeric summaries, but it must not import DAVINCI plotters or render figures.

## Frozen CAM AOD contract

- One NetCDF4 file per three-hour window; eight files per inclusive day.
- Filename:
  `MODIS_VIIRS_AOD_3hr_f09.<YYYYMMDD>.<window-start-seconds>.nc`.
- Window-start seconds: `00000`, `10800`, `21600`, `32400`, `43200`, `54000`, `64800`,
  `75600`.
- Horizontal grid: f09 finite-volume, `lat=192`, `lon=288`, with exact bounds.
- Primary field: `aod_weighted_mean(lat,lon)`, 550 nm, units `1`, float fill `-999`.
- Required companions: `aod_uncertainty` and `aod_count`; sensor fields are recommended.
- Scalar CF `time` is the window center; `time_bnds` spans the full window. The filename retains
  the window start.
- Required provenance includes source products/collections, QC thresholds, merge/bias method and
  versions, grid, wavelength, creation time, and producing Git commit.

Expected file count is `8 * (end_date - start_date + 1)`. July 2008 therefore requires 248 files,
from `20080701.00000` through `20080731.75600`.

Schema conformance is necessary but not sufficient. Also require at least one native granule for
every configured sensor/day, nonzero active cells where sampling exists, finite uncertainty for
valid AOD, positive counts for valid AOD, and physically plausible values.

## Sensor and collection rules

- July 2008 uses Terra `MOD04_L2` and Aqua `MYD04_L2`, Collection 6.1, Dark Target plus Deep
  Blue. Absence of VIIRS is correct.
- For the preserved July 2008 cache, expect both sensors together: about 19,000 native granules
  and roughly 51 GB. Reconcile exact counts and sizes against its staged manifest.
- NOAA-20 `AERDB_L2` begins much later. Do not create synthetic VIIRS coverage for earlier
  periods.
- Use MODIS valid-retrieval QA, VIIRS `QA_Flag >= 2`, AOD in `[0,5]`, finite geolocation, and
  configured uncertainty limits unless a versioned config records a justified change.
- Merge sensors with inverse-variance weights. Before including VIIRS, preserve the
  AERONET-anchored bias coefficients and require `rmse_after < rmse_before`.
- EarthData credentials belong in `~/.netrc` with restrictive permissions. Never copy or log
  credential content.

## ERA5 distinctions

`scripts/prepare_modis_era5_grid.py` copies the ERA5 horizontal coordinates into a MODIS
diagnostic product. CAM does not read this directory for AOD nudging.

CAM meteorological nudging reads the external hourly ERA5 files. For a run period, verify every
hour plus the terminal boundary file, exact f09 coordinates, L32 levels and hybrid coefficients,
and compatibility with the case. Treat a missing or mismatched file as a blocker; do not
interpolate, regrid, or replace it without a separately reviewed preprocessing design.

## Stage handoffs

- After contract audit, give the AOD directory, filename template, date endpoints, and expected
  windows/day to `$configure-cesm3-runs`.
- After a CAM run, give history and optics outputs to `$closeout-ceres-runs`.
- Give versioned analysis YAML, input coverage, and numeric preprocessing evidence to
  `$postprocess-ceres-davinci` for DAVINCI execution and visual acceptance.
