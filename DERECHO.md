# Running CERES-SARB-CAM7 on Derecho

These instructions are the short operational path for building and running the
July 2008 MODIS AOD-nudged CAM7 cases on NCAR Derecho. The authoritative setup
entry point is [`scripts/setup_sp2_july2008_runs.sh`](scripts/setup_sp2_july2008_runs.sh).
It deploys the repository's CAM AOD-nudging and spectral band-optics source,
creates the nudged and free cases, configures them, builds CAM in a conda-free
environment, and optionally submits both cases.

Some executable filenames and case paths retain historical phase codes. They
are included only because they are the exact on-disk names; operators do not
need to know or use those codes as scientific or workflow terminology.

## 1. Start a clean Derecho session

Run case creation, builds, and submissions from a Derecho login node. Use the
project's `develop` branch unless directed otherwise.

```bash
ssh derecho.hpc.ucar.edu

export REPO=/glade/work/fillmore/CERES-SARB-CAM7
export DATA=/glade/work/fillmore/Data/CERES-SARB-CAM7
export CESM=/glade/work/fillmore/CESM3/cesm3_0_beta08
export CASE_ROOT=/glade/work/fillmore/CESM3/cases
export PROJECT=P19010000

cd "$REPO"
git switch develop
git pull --ff-only origin develop
```

The setup script accepts equivalent path overrides through `SP2_REPO`,
`SP2_CESM`, `SP2_CASE_ROOT`, and `SP2_OBS_DIR`.

## 2. Prepare the July 2008 MODIS data

### Configure Python

Use the `davinci` environment and put the DAVINCI checkout first on
`PYTHONPATH`:

```bash
export PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
export PYTHONPATH=/glade/work/fillmore/DAVINCI:"$REPO"
export MPLBACKEND=Agg
cd "$REPO"
```

### Configure Earthdata authentication

[`scripts/stage_obs.py`](scripts/stage_obs.py) downloads MODIS Terra and Aqua
Level-2 data through Earthdata. Store the credentials in `~/.netrc`:

```text
machine urs.earthdata.nasa.gov
  login <earthdata-username>
  password <earthdata-password>
```

Protect the credential file:

```bash
chmod 600 ~/.netrc
```

Run downloads on a Derecho login node or another node with outbound internet.

### Stage MODIS and AERONET inputs

First query Earthdata and report the expected inventory without downloading:

```bash
"$PY" scripts/stage_obs.py \
  --start 2008-07-01 --end 2008-07-31 --dry-run
```

Then stage the July 2008 MODIS and AERONET inputs. The command is idempotent and
resumes by skipping files already present:

```bash
"$PY" scripts/stage_obs.py \
  --start 2008-07-01 --end 2008-07-31
```

To stage only the MODIS inputs, add `--what modis`. The default `--what all`
also prepares the AERONET support data used for validation.

The raw files are written below:

```text
$DATA/MODIS_VIIRS_L2/MODIS_TERRA_AEROSOL/YYYYMMDD/*.hdf
$DATA/MODIS_VIIRS_L2/MODIS_AQUA_AEROSOL/YYYYMMDD/*.hdf
$DATA/AeroNet/AeroNet_YYYYMMDD.nc
```

Check the staged inventory:

```bash
find "$DATA/MODIS_VIIRS_L2/MODIS_TERRA_AEROSOL" -type f -name '*.hdf' | wc -l
find "$DATA/MODIS_VIIRS_L2/MODIS_AQUA_AEROSOL" -type f -name '*.hdf' | wc -l
find "$DATA/AeroNet" -maxdepth 1 -type f -name 'AeroNet_200807*.nc' | wc -l
```

### Create the CAM-readable f09 AOD files

Run the checked-in MODIS-to-CAM AOD processing configuration with the
repository's Python module:

```bash
"$PY" -m sp1_aod_pipeline run \
  --config sp1_aod_pipeline/config.example.yaml
```

This creates eight three-hourly files per day under `$DATA/AOD_f09_3hr`. The
production CAM setup requires exactly 248 July 2008 files:

```bash
find "$DATA/AOD_f09_3hr" -maxdepth 1 -type f \
  -name 'MODIS_VIIRS_AOD_3hr_f09.200807*.nc' | wc -l
# expected: 248
```

Validate the first and last files:

```bash
"$PY" -m sp1_aod_pipeline validate \
  "$DATA/AOD_f09_3hr/MODIS_VIIRS_AOD_3hr_f09.20080701.00000.nc"

"$PY" -m sp1_aod_pipeline validate \
  "$DATA/AOD_f09_3hr/MODIS_VIIRS_AOD_3hr_f09.20080731.75600.nc"
```

Do not run the CAM setup until the inventory and validation checks pass.

### Optional MODIS-on-ERA5 diagnostic files

[`scripts/prepare_modis_era5_grid.py`](scripts/prepare_modis_era5_grid.py)
creates the optional MODIS-only diagnostic product on the ERA5 f09 grid:

```bash
"$PY" scripts/prepare_modis_era5_grid.py \
  --start 2008-07-01 --end 2008-07-31

find "$DATA/MODIS_AOD_ERA5_GRID" -type f \
  -name 'MODIS_AOD_3hr_ERA5_f09.200807*.nc' | wc -l
# expected: 248
```

These files are useful for monthly MODIS diagnostics, but CAM does not read
them. CAM reads the three-hourly AOD contract files under
`$DATA/AOD_f09_3hr`.

## 3. Preview, build, and submit

Always preview the operation first:

```bash
./scripts/setup_sp2_july2008_runs.sh --dry-run
```

Create/configure/build the nudged and free cases without submitting:

```bash
./scripts/setup_sp2_july2008_runs.sh
```

Or build and submit both cases in one command:

```bash
./scripts/setup_sp2_july2008_runs.sh --submit
```

The script creates:

```text
/glade/work/fillmore/CESM3/cases/sp2_200807_mam4_modis
/glade/work/fillmore/CESM3/cases/sp2_200807_mam4_free
```

The nudged case is built first. The free case is a `--keepexe` clone and uses
the same executable. Existing cases are rejected by default; use
`--reuse-existing` only when intentionally reconfiguring a preserved case.

The setup script calls [`scripts/sp2_deploy.sh`](scripts/sp2_deploy.sh), which
deploys all checked-in AOD-nudging and band-optics CAM modules and applies the
required CAM/CMake/namelist patches. To refresh source in an existing case
before rebuilding:

```bash
./scripts/sp2_deploy.sh "$CASE_ROOT/<case-name>"
```

## 4. Executables

The repository tracks the executable setup/deploy scripts and the CAM source;
compiled `cesm.exe` binaries are generated build artifacts under Derecho
scratch and are not stored in Git.

For the standard July 2008 nudged/free pair, locate the shared executable with:

```bash
cd "$CASE_ROOT/sp2_200807_mam4_modis"
EXEROOT=$(./xmlquery --value EXEROOT)
test -x "$EXEROOT/cesm.exe"
printf '%s\n' "$EXEROOT/cesm.exe"
```

The completed production pair used:

```text
/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/bld/cesm.exe
```

The validated spectral band-optics runs, including the ten-day MODIS-nudged
run used by the current DAVINCI analysis, used:

```text
/glade/derecho/scratch/fillmore/sp3_lut_build/bld/cesm.exe
```

Submit through the CIME case rather than invoking `cesm.exe` directly; CIME
provides the MPI layout, environment, namelists, and input-data paths.

## 5. Submit and monitor an existing case

If setup was run without `--submit`:

```bash
cd "$CASE_ROOT/sp2_200807_mam4_modis"
./preview_run
./case.submit

cd "$CASE_ROOT/sp2_200807_mam4_free"
./preview_run
./case.submit
```

Monitor PBS and CIME:

```bash
qstat -u "$USER"
qstat -x -f <jobid>.desched1 | \
  egrep 'Job_Name|job_state|Exit_status|resources_used.mem|resources_used.walltime'

tail -n 40 "$CASE_ROOT/sp2_200807_mam4_modis/CaseStatus"
tail -n 40 "$CASE_ROOT/sp2_200807_mam4_free/CaseStatus"
```

A successful run records both `model execution success` and `case.run success`
in `CaseStatus`.

For a continuation from a valid restart:

```bash
cd "$CASE_ROOT/<case-name>"
./xmlchange CONTINUE_RUN=TRUE
./case.submit
```

## 6. Safety rules

- Do not rebuild a queued/running case or any `--keepexe` clone sharing its
  `EXEROOT`. PBS uses the executable currently present in that directory.
- Check `qstat -u "$USER"` and `./xmlquery --value EXEROOT` before rebuilding.
- Build on a login node in a conda-free environment. The production setup
  script performs the required PATH cleanup automatically.
- Preserve completed case and scratch directories as run records; use new case
  names and new `EXEROOT` directories for new experiments.
- Use account `P19010000` for `create_newcase`, `case.submit`, and interactive
  allocations.

See [`BUILD.md`](BUILD.md) for build troubleshooting and [`RUN.md`](RUN.md) for
the complete run inventory, spectral band-optics namelist details, validation
results, and current output locations.

## 7. Regenerate the accepted plots

Plotting is a separate DAVINCI analysis step in the `davinci` environment:

```bash
cd "$REPO"
export PYTHONPATH=/glade/work/fillmore/DAVINCI:"$REPO"
export MPLBACKEND=Agg

/glade/work/fillmore/miniforge3/envs/davinci/bin/python \
  -m davinci_monet.cli.app run \
  analyses/davinci/modis-aod-nudging-band-optics-july-2008.yaml
```

Do not render project plots directly with Matplotlib, Cartopy, or DAVINCI
plotter classes; final and verification plots must come from the complete
DAVINCI pipeline command above.
