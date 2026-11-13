# CERES-SARB-CAM7

This repository contains the CERES-SARB CAM7 aerosol work for NCAR derecho,
including MODIS-derived AOD observation preparation, CAM7 AOD nudging, and
diagnostic/verification scripts.

A stock CESM3/CAM7 baseline has also been built and run on the Orion Linux
desktop for the CERES-MIP setup phase. See
[`docs/cesm3-desktop.md`](docs/cesm3-desktop.md) for the no-MODIS toolchain,
directory layout, exact build/run evidence, and remaining production-input
gates.

The operational MODIS AOD nudging path is:

1. Stage MODIS Terra/Aqua Level-2 aerosol inputs and AERONET support data.
2. Convert the staged observations into 3-hourly f09 AOD contract files.
3. Deploy the CAM7 AOD nudging code into a CESM3/CAM7 checkout.
4. Build and submit a nudged CAM case and a free-running reference case.
5. Verify CAM history diagnostics and render DAVINCI PDF diagnostics.

The current tested month is July 2008. July 2008 predates VIIRS, so the run is
MODIS-only even though the SP1/SP2 file contract keeps the generic
`MODIS_VIIRS_AOD_3hr_f09` name.

## Tropospheric Scaling Option

Set `aod_tropo_only = .true.` in `aod_nudging_nl` to restrict scaling to levels
strictly below CAM's native tropopause level. The diagnosed level and everything
above it stay unchanged. The default `.false.` retains whole-column scaling.
The same option and numerical contract are implemented in CAM6. See
[the method and matched July profile tests](docs/tropospheric-scaling.md).

## Run History

The canonical run ledger is [`run_history/index.md`](run_history/index.md), generated from one
versioned YAML record per attempt under `run_history/records/`. Records capture configuration,
PBS/CIME outcome, output locations, and separate structural, numeric, DAVINCI, and science
validation states. See [`docs/run-history.md`](docs/run-history.md) for the contract and
maintenance commands.

## Derecho Layout

Default paths used by the scripts:

```bash
export REPO=/glade/work/fillmore/CERES-SARB-CAM7
export DATA=/glade/work/fillmore/Data/CERES-SARB-CAM7
export CESM=/glade/work/fillmore/CESM3/cesm3_0_beta08
export CASE_ROOT=/glade/work/fillmore/CESM3/cases
export PROJECT=P19010000
```

Important directories:

```text
$DATA/MODIS_VIIRS_L2/          Raw staged MODIS L2 granules
$DATA/AeroNet/                 Daily AERONET cache files
$DATA/AOD_f09_3hr/             CAM-readable AOD contract files
$CASE_ROOT/sp2_200807_mam4_modis
$CASE_ROOT/sp2_200807_mam4_free
/glade/derecho/scratch/$USER/<case>/{bld,run}
```

Use branch `develop` unless explicitly directed otherwise.

## Python Environment

Most Python commands need this environment and import path:

```bash
cd /glade/work/fillmore/CERES-SARB-CAM7
export PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
export PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7
export MPLBACKEND=Agg
```

The `PYTHONPATH` order matters. `/glade/work/fillmore/DAVINCI` must come before
this repository so the `davinci-monet` pipeline resolves to the real DAVINCI checkout.

For CESM `case.build`, remove miniforge from `PATH` and unset `CONDA_PREFIX`.
The setup script below does that automatically for the production July 2008
pair.

## EarthData Credentials

MODIS staging uses LAADS/CMR through `earthaccess` and expects EarthData
credentials in `~/.netrc`.

The file should contain an entry like:

```text
machine urs.earthdata.nasa.gov
  login <your-earthdata-username>
  password <your-earthdata-password>
```

Protect it:

```bash
chmod 600 ~/.netrc
```

Run a quick `--dry-run` preflight on a derecho login node. Derecho compute nodes also have
outbound internet (verified live via `qsub` on 2026-09-04), so multi-day staging can be queued
through PBS instead. Use the shared `develop`→`cpudev` queue for these lightly threaded jobs;
reserve the exclusive `main`→`cpu` queue for work that cannot fit the shared queue limits. See
`.agents/skills/preprocess-ceres-data/scripts/submit_stage_and_build_pbs.py`.

## Step 1: Stage MODIS and AERONET Inputs

Dry-run first. This searches CMR and reports expected files/sizes without
downloading:

```bash
cd "$REPO"
"$PY" scripts/stage_obs.py --dry-run
```

Stage the July 2008 default month:

```bash
"$PY" scripts/stage_obs.py
```

Useful variants:

```bash
# MODIS only
"$PY" scripts/stage_obs.py --what modis

# AERONET only
"$PY" scripts/stage_obs.py --what aeronet

# Different date range
"$PY" scripts/stage_obs.py --start 2008-07-01 --end 2008-07-31
```

Expected July 2008 raw layout:

```text
$DATA/MODIS_VIIRS_L2/MODIS_TERRA_AEROSOL/YYYYMMDD/*.hdf
$DATA/MODIS_VIIRS_L2/MODIS_AQUA_AEROSOL/YYYYMMDD/*.hdf
$DATA/AeroNet/AeroNet_YYYYMMDD.nc
```

Check inventory:

```bash
find "$DATA/MODIS_VIIRS_L2/MODIS_TERRA_AEROSOL" -name '*.hdf' | wc -l
find "$DATA/MODIS_VIIRS_L2/MODIS_AQUA_AEROSOL"  -name '*.hdf' | wc -l
find "$DATA/AeroNet" -name 'AeroNet_200807*.nc' | wc -l
```

The July 2008 MODIS download is global and large, roughly 24 GB / 9.8k granules.
The staging script is idempotent and skips existing files.

## Step 2: Create CAM AOD Contract Files

CAM reads one file per 3-hour window from `$DATA/AOD_f09_3hr`, with filenames:

```text
MODIS_VIIRS_AOD_3hr_f09.YYYYMMDD.SSSSS.nc
```

where `SSSSS` is the window-start second of day:
`00000, 10800, ..., 75600`.

Run the SP1 pipeline with the checked-in July 2008 config:

```bash
cd "$REPO"
"$PY" -m sp1_aod_pipeline run --config sp1_aod_pipeline/config.example.yaml
```

Expected July 2008 output count:

```bash
find "$DATA/AOD_f09_3hr" -maxdepth 1 \
  -name 'MODIS_VIIRS_AOD_3hr_f09.200807*.nc' | wc -l
# expected: 248
```

Validate representative files:

```bash
"$PY" -m sp1_aod_pipeline validate \
  "$DATA/AOD_f09_3hr/MODIS_VIIRS_AOD_3hr_f09.20080701.00000.nc"

"$PY" -m sp1_aod_pipeline validate \
  "$DATA/AOD_f09_3hr/MODIS_VIIRS_AOD_3hr_f09.20080731.75600.nc"
```

The primary fields in each contract file are:

```text
aod_weighted_mean(lat,lon)       550 nm target AOD, fill = -999
aod_uncertainty(lat,lon)         1-sigma uncertainty, fill = -999
aod_count(lat,lon)               valid L2 pixel count, fill = 0
aod_weighted_mean_modis(lat,lon) MODIS-only AOD
```

The scalar `time` coordinate is the 3-hour window center; the filename second is
the window start. SP2 reads the file `time` values for interpolation.

### Optional MODIS ERA5-grid diagnostic product

`scripts/prepare_modis_era5_grid.py` writes an intermediate diagnostic product
under `$DATA/MODIS_AOD_ERA5_GRID`. It is useful for MODIS monthly analysis, but
it is not the directory read by the CAM nudging case.

Use `$DATA/AOD_f09_3hr` for CAM runs.

## Step 3: Deploy CAM AOD Nudging Code

The deploy script patches the CESM/CAM checkout and, when given a case path,
also overlays modules into that case's `SourceMods/src.cam`.

Patch the shared CAM source tree:

```bash
cd "$REPO"
bash scripts/sp2_deploy.sh
```

For an individual case:

```bash
bash scripts/sp2_deploy.sh /glade/work/fillmore/CESM3/cases/<case>
```

The deploy script is idempotent. Re-run it after changing files under
`src/cam/` or the CAM patch fragments.

## Step 4: Build and Configure the July 2008 MAM4 Cases

The production helper prepares a nudged case and a paired free case:

```text
sp2_200807_mam4_modis  AOD nudging enabled
sp2_200807_mam4_free   AOD nudging disabled, same executable via clone
```

Dry-run first:

```bash
cd "$REPO"
bash scripts/setup_sp2_july2008_runs.sh --dry-run
```

Create/configure/build the cases without submitting:

```bash
bash scripts/setup_sp2_july2008_runs.sh
```

Create/configure/build and submit both cases:

```bash
bash scripts/setup_sp2_july2008_runs.sh --submit
```

If the case directories already exist, the script stops unless you explicitly
allow reuse:

```bash
bash scripts/setup_sp2_july2008_runs.sh --reuse-existing
```

Use `--reuse-existing` only when you intend to reconfigure the existing cases.
For a new experiment, use a copied/edited setup script or move the old cases
aside so the preserved run record remains unambiguous.

The script checks that `$DATA/AOD_f09_3hr` contains exactly 248 July 2008
contract files before it builds.

### Case XML and namelist settings

The setup script configures both cases for:

```text
RUN_STARTDATE = 2008-07-01
STOP_OPTION   = ndays
STOP_N        = 31
REST_OPTION   = ndays
REST_N        = 31
DOUT_S        = FALSE
RESUBMIT      = 0
NTASKS_*      = 128 for active components, ESP = 1
JOB_QUEUE     = main
JOB_WALLCLOCK_TIME = 12:00:00
```

The nudged case appends this block to `user_nl_cam`:

```fortran
aod_nudge_on = .true.
aod_obs_path = '/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/'
aod_obs_template = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
aod_times_per_day = 8
aod_diag_on = .true.
empty_htapes = .true.
fincl1 = 'AODVIS','FSNTC','AODNDG_OBS','AODNDG_MODEL_PRE','AODNDG_MODEL_POST','AODNDG_RATIO','AODNDG_MASK'
iradsw = -1
nhtfrq = -3
mfilt = 248
```

The free case sets:

```fortran
aod_nudge_on = .false.
aod_diag_on = .false.
empty_htapes = .true.
fincl1 = 'AODVIS','FSNTC'
iradsw = -1
nhtfrq = -3
mfilt = 248
```

Check generated namelists:

```bash
cd "$CASE_ROOT/sp2_200807_mam4_modis"
./preview_namelists --component atm
grep -n "aod_nudging_nl" CaseDocs/atm_in
grep -n "aod_nudge_on\\|aod_obs_path\\|fincl1" CaseDocs/atm_in
```

## Step 5: Submit and Monitor

If you did not use `--submit`:

```bash
cd "$CASE_ROOT/sp2_200807_mam4_modis"
./case.submit

cd "$CASE_ROOT/sp2_200807_mam4_free"
./case.submit
```

Monitor queue state:

```bash
qstat -u "$USER"
qstat -x -f <jobid>.desched1 | egrep 'Job_Name|job_state|Exit_status|resources_used.mem|resources_used.walltime'
```

Monitor CIME status:

```bash
tail -n 40 "$CASE_ROOT/sp2_200807_mam4_modis/CaseStatus"
tail -n 40 "$CASE_ROOT/sp2_200807_mam4_free/CaseStatus"
```

Expected success lines:

```text
model execution success <jobid>
case.run success <jobid>
```

## Step 6: Locate Run Outputs

Get run directories from the cases:

```bash
NUDGED_CASE="$CASE_ROOT/sp2_200807_mam4_modis"
FREE_CASE="$CASE_ROOT/sp2_200807_mam4_free"

NUDGED_RUN=$(cd "$NUDGED_CASE" && ./xmlquery --value RUNDIR)
FREE_RUN=$(cd "$FREE_CASE" && ./xmlquery --value RUNDIR)

echo "$NUDGED_RUN"
echo "$FREE_RUN"
```

For the preserved July 2008 run these are:

```text
/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/run
/glade/derecho/scratch/fillmore/sp2_200807_mam4_free/run
```

Expected files:

```bash
ls "$NUDGED_RUN"/sp2_200807_mam4_modis.cam.h0a.*.nc
ls "$NUDGED_RUN"/sp2_200807_mam4_modis.cam.h0i.*.nc
ls "$FREE_RUN"/sp2_200807_mam4_free.cam.h0a.*.nc
ls "$FREE_RUN"/sp2_200807_mam4_free.cam.h0i.*.nc
```

For the July 2008 setup, each `h0a`/`h0i` file should contain 248 3-hourly
records. The nudged `h0i` contains:

```text
AODNDG_MASK
AODNDG_OBS
AODNDG_MODEL_PRE
AODNDG_MODEL_POST
AODNDG_RATIO
```

The free `h0i` should not contain AODNDG fields.

## Step 7: Verify Nudging Behavior

Basic last-record check:

```bash
"$PY" sp2_tests/check_integration.py \
  --h0 "$NUDGED_RUN/sp2_200807_mam4_modis.cam.h0i.2008-07-01-10800.nc"
```

Generate verification plots only through a declared DAVINCI analysis:

```bash
DAVINCI_PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7 \
  "$DAVINCI_PY" -m davinci_monet.cli.app run \
  analyses/davinci/cam-aod-monthly-analysis-july-2008.yaml
```

Project scripts do not render plots directly. Final plots should be PDFs. Keep generated
artifacts under:

```text
/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/
```

Do not keep ad hoc PNG replacements as final plot products.

## Optional: ERA5 Meteorological Nudging

The MODIS AOD nudging namelist is `&aod_nudging_nl`. It is independent of CAM's
standard meteorological nudging namelist, `&nudging_nl`.

The July 2008 SP2 smoke/full-month cases used `F2000dev` without met nudging.
Production runs can also nudge meteorology toward ERA5 if the chosen compset has
the same vertical levels as the ERA5 forcing files.

CAM-ready ERA5 f09/L32 files are available here:

```text
/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl/
```

The Python translation of the ERA5 N320/L137 to CAM f09/L32 converter is
`scripts/generate_era5_cam_nudging.py`. Its March 9--10, 2008 gap config is
`config/era5/march_2008_gap_v1.yaml`. Check the complete source inventory
without writing data, then submit the conversion through the shared PBS queue:

```bash
DAVINCI_PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
"$DAVINCI_PY" scripts/generate_era5_cam_nudging.py \
  --config config/era5/march_2008_gap_v1.yaml preflight
"$DAVINCI_PY" scripts/submit_era5_cam_nudging_pbs.py \
  config/era5/march_2008_gap_v1.yaml --dry-run
"$DAVINCI_PY" scripts/submit_era5_cam_nudging_pbs.py \
  config/era5/march_2008_gap_v1.yaml
```

The converter refuses overwrites and writes a checksummed `manifest.json`.
Use `--resume` only after auditing a partial directory; every existing hourly
file must pass the full validator before it is skipped.

The checked-in `config/era5/smoke_20080308_23_v1.yaml` regenerates an hour that
already exists in the canonical series. Use the converter's `compare` command
to report field-wise maximum, RMSE, bias, and nonpolar differences before a
production submission.

For continuity with the canonical 2008 series, the versioned configs retain
its zero-valued source-geopotential pole rows during the ECMWF surface-pressure
adjustment. This does not alter the CAM target `PHIS` field copied into each
output file. The converter likewise preserves the surrounding files' legacy
ESMF `VS` behavior at the two degenerate pole rows.

Template block:

```fortran
Nudge_Model        =.true.
Nudge_Path         ='/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl/'
Nudge_File_Template='ERA5_fv09.cam2.i.%y-%m-%d-%s.nc'
Nudge_Force_Opt    = 0
Nudge_TimeScale_Opt= 0
Nudge_Times_Per_Day= 24
Model_Times_Per_Day= 48
Nudge_Uprof  =1
Nudge_Ucoef  =0.25
Nudge_Vprof  =1
Nudge_Vcoef  =0.25
Nudge_Tprof  =1
Nudge_Tcoef  =0.25
Nudge_Qprof  =1
Nudge_Qcoef  =0.25
Nudge_PSprof =0
Nudge_PScoef =0.00
Nudge_Beg_Year =2008
Nudge_Beg_Month=7
Nudge_Beg_Day  =1
Nudge_End_Year =2008
Nudge_End_Month=8
Nudge_End_Day  =1
Nudge_Hwin_lat0    =0.0
Nudge_Hwin_latWidth=9999.
Nudge_Hwin_latDelta=1.
Nudge_Hwin_lon0    =180.
Nudge_Hwin_lonWidth=9999.
Nudge_Hwin_lonDelta=1.
Nudge_Hwin_Invert  =.false.
Nudge_Vwin_Hindex  =33.
Nudge_Vwin_Hdelta  =0.001
Nudge_Vwin_Lindex  =0.
Nudge_Vwin_Ldelta  =0.1
Nudge_Vwin_Invert  =.false.
```

Do not enable this blindly for a non-L32 CAM configuration. Confirm the model
vertical grid first.

Prepare the combined July 2008 ERA5-met-nudged and MODIS-AOD-nudged case with:

```bash
scripts/setup_sp2_july2008_era5_modis_run.sh
```

The setup validates the forcing coverage and f09/L32 grid, clones the existing
built MODIS case as `sp2_200807_mam4_modis_era5`, and verifies the generated CAM
namelist. It does not submit unless passed `--submit`.

## Current Preserved July 2008 Reference Run

The following already completed successfully and should be treated as a preserved
run record unless intentionally replacing it:

```text
Nudged case: sp2_200807_mam4_modis
PBS job:     6581712.desched1
Run dir:     /glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/run
Walltime:    00:53:42
Exit:        0

Free case:   sp2_200807_mam4_free
PBS job:     6581729.desched1
Run dir:     /glade/derecho/scratch/fillmore/sp2_200807_mam4_free/run
Walltime:    00:49:18
Exit:        0
```

The nudged run wrote 248 records with `AODVIS`, `FSNTC`, and `AODNDG_*`
diagnostics. The free run wrote matching `AODVIS` and `FSNTC` records and no
AODNDG fields.

See `RUN.md` for the detailed run log.

## Common Failure Modes

| Symptom | Likely cause / fix |
| --- | --- |
| `earthaccess` cannot authenticate | Check `~/.netrc` and `chmod 600 ~/.netrc`. |
| MODIS staging finds zero granules | Collection must be CMR VersionId `6.1`, not `61`; use `scripts/stage_obs.py`. |
| `setup_sp2_july2008_runs.sh` says expected 248 obs files | Run the SP1 pipeline and confirm `$DATA/AOD_f09_3hr/MODIS_VIIRS_AOD_3hr_f09.200807*.nc`. |
| `davinci-monet` imports the wrong checkout | Put `/glade/work/fillmore/DAVINCI` first in `PYTHONPATH`. |
| CAM build fails in TUV-x/yaml-cpp | Build on a login node with miniforge removed from `PATH` and `CONDA_PREFIX` unset. |
| Case already exists | Use `--reuse-existing` only intentionally, or create a new case name by copying/editing the setup script. |
| A submitted free clone runs a changed executable | Do not rebuild a case while its job, or a `--keepexe` clone using the same `EXEROOT`, is queued/running. |
| Free run contains AODNDG fields | Its `user_nl_cam` was not reset; rerun setup and inspect `CaseDocs/atm_in`. |
| Nudged run has no active cells | Check obs file dates/path/template and inspect `AODNDG_MASK` in h0i. |

## Quick Command Summary

```bash
cd /glade/work/fillmore/CERES-SARB-CAM7
export PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
export PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7
export MPLBACKEND=Agg

# Raw observations
"$PY" scripts/stage_obs.py --dry-run
"$PY" scripts/stage_obs.py

# CAM-readable 3-hourly contract files
"$PY" -m sp1_aod_pipeline run --config sp1_aod_pipeline/config.example.yaml
find /glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr -maxdepth 1 \
  -name 'MODIS_VIIRS_AOD_3hr_f09.200807*.nc' | wc -l

# Cases
bash scripts/setup_sp2_july2008_runs.sh --dry-run
bash scripts/setup_sp2_july2008_runs.sh --submit

# Monitor
qstat -u "$USER"
tail -n 40 /glade/work/fillmore/CESM3/cases/sp2_200807_mam4_modis/CaseStatus
tail -n 40 /glade/work/fillmore/CESM3/cases/sp2_200807_mam4_free/CaseStatus
```
