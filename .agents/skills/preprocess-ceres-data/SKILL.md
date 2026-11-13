---
name: preprocess-ceres-data
description: Stage, preprocess, and validate CERES-SARB-CAM7 run inputs with the project SP1 pipeline and DAVINCI data capabilities. Use when Codex must acquire version-pinned MODIS, VIIRS, or AERONET data; apply aerosol retrieval QC; grid and aggregate observations; fit or apply VIIRS-to-MODIS bias correction; write or audit the 3-hour f09 AOD contract consumed by CAM; prepare the optional MODIS-on-ERA5 diagnostic product; verify ERA5 nudging-input coverage; or establish that forcing data are ready before CIME case configuration.
---

# Preprocess CERES Data

Build reproducible, run-ready observation inputs while keeping raw data, intermediate diagnostics,
CAM forcing, model execution, and post-run analysis as distinct stages.

## Help Mode

When explicitly invoked as `$preprocess-ceres-data help`, `$preprocess-ceres-data --help`, or
`$preprocess-ceres-data -h`, enter help mode. Help takes precedence over the workflow. Do not use
tools, load bundled references, inspect inputs, submit jobs, or change state. Return only the
following brief bullets, then stop:

- Stage version-pinned MODIS, VIIRS, and AERONET inputs without replacing preserved caches.
- Build 3-hour f09 AOD files through SP1's DAVINCI readers, QC, gridding, and sensor merge.
- Validate coverage, CF time bounds, required fields, fill semantics, and provenance.
- Fit or verify AERONET-anchored VIIRS-to-MODIS bias correction.
- Prepare optional MODIS-on-ERA5 diagnostics without confusing them with CAM forcing.
- Hand case configuration and science plotting to the owning CERES skills.

## Workflow

1. Read the repository `AGENTS.md`, `SPEC.md` sections 5-6, and the data-preparation section of
   `README.md`. Read [references/data-products.md](references/data-products.md) and identify the
   requested product, period, grid, sensors, source versions, and consumer.
2. Resolve exact paths and inspect existing raw, intermediate, and final products. Treat a
   populated output directory as preserved by default. For a replacement, choose a new
   versioned output directory unless the user explicitly authorizes replacement.
3. Keep scientific choices in a checked-in YAML based on
   `sp1_aod_pipeline/config.example.yaml`. For a new period or product, create a descriptively
   named sibling config and change only the required paths, dates, products, collections, QC,
   uncertainty, and bias-coefficient settings.
4. Use the project DAVINCI environment and resolve the real DAVINCI checkout before this repo:

   ```bash
   REPO=/glade/work/fillmore/CERES-SARB-CAM7
   DAVINCI_PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
   export PYTHONPATH=/glade/work/fillmore/DAVINCI:$REPO
   "$DAVINCI_PY" -c 'import davinci_monet, sp1_aod_pipeline'
   ```

5. Preflight acquisition on a login node (cheap, search-only). Do not expose EarthData
   credentials or print `~/.netrc`:

   ```bash
   "$DAVINCI_PY" scripts/stage_obs.py --what modis --dry-run
   ```

   Confirm the CMR collection version, inclusive date range, expected sensors, destination,
   volume, and existing cache before downloading. July 2008 is correctly MODIS-only because it
   predates VIIRS. The package `download --dry-run` queries all package collections, including
   NOAA-20 VIIRS, so use it only for periods whose acquisition plan includes those collections.
6. Stage authorized raw data with `scripts/stage_obs.py` or the package `download` command.
   Downloads belong below `/glade/work/fillmore/Data/CERES-SARB-CAM7`; resume existing
   version-matched caches rather than mixing collection versions or the two staging layouts.
   Derecho compute nodes have outbound internet (DNS/HTTPS/ICMP verified live via `qsub` on
   2026-09-04 — an earlier "compute nodes have no internet" assumption in this repo's docs was
   wrong and has been corrected), so for a multi-day/production period prefer queuing staging
   through PBS rather than running it by hand on a login node. See step 8's
   `submit_stage_and_build_pbs.py`, which chains staging into the contract build as two PBS jobs
   with no login-node babysitting required.
7. Run the preprocessing tests before a production build:

   ```bash
   "$DAVINCI_PY" -m pytest -q \
     sp1_aod_pipeline/tests tests/test_prepare_modis_era5_grid.py
   ```

8. For a short smoke period, run `python -m sp1_aod_pipeline run --config <config>`. For
   multi-day production processing, queue staging chained into the contract build as two PBS
   jobs (preferred — no login node required for either step):

   ```bash
   "$DAVINCI_PY" .agents/skills/preprocess-ceres-data/scripts/submit_stage_and_build_pbs.py \
     sp1_aod_pipeline/<config>.yaml
   ```

   This submits a staging job for the config's start/end range; on success that job itself
   submits the contract build (`submit_sp1_preprocessing_pbs.py`) as a second, independent PBS
   job. If staging fails, the build is never submitted. Skip straight to
   `submit_sp1_preprocessing_pbs.py` only when raw data for the period is already staged.

   Use Derecho's shared `develop`→`cpudev` queue for lightly threaded staging and SP1 builds.
   The helpers default to that queue; the build requests 2 CPUs, 4 GB, and 2 hours, while staging
   requests 2 CPUs, 4 GB, and the shared queue's 6-hour maximum. Recent monthly MODIS builds used
   about one CPU and 1.2 GB, so an exclusive `main`→`cpu` node would waste most of a 128-core
   node and be charged as a full node. Override the queue or resources only when measured demand
   exceeds the shared profile; use `main` when a job cannot finish within the `develop` limits.

   Capture the job ID(s), then verify `qstat -xf <job-id>` reports exit 0 and inspect the PBS log.
   Do not infer data readiness from scheduler success alone.
9. Audit the output inventory. Require eight files per inclusive day, exact first/last
   filename stamps, no gaps or duplicates, and successful contract validation for every file:

   ```bash
   "$DAVINCI_PY" -m sp1_aod_pipeline validate \
     /path/to/MODIS_VIIRS_AOD_3hr_f09.YYYYMMDD.SSSSS.nc
   ```

   Inspect representative and boundary files numerically for finite active cells, AOD range,
   positive counts, finite uncertainty, fill consistency, CF window-center time, f09
   coordinates/bounds, source/QC/bias provenance, and the producing Git commit.
10. Use `scripts/prepare_modis_era5_grid.py` only when an ERA5-grid MODIS diagnostic is requested.
    It is not the CAM AOD-nudging input. For meteorological nudging, audit the existing ERA5
    hourly coverage, f09 horizontal grid, L32 vertical grid, boundary file, and case-compatible
    coefficients; do not silently regrid or rewrite the forcing. Native ERA5 model-level inputs
    are available from GDEX `d633006` under `/gdex/data/d633006/`. They are N320/L137 source
    files, not CAM-ready forcing. An inactive, non-executable ERA5-to-CAM seed copied from the
    authorized collaborator tree is preserved under `scripts/era5_cam_nudging_seed/`; read its
    `NOTES.md` and adapt it to the case's f09/L32 grid and filename contract before any run.
11. Put every verification plot in a versioned YAML under `analyses/davinci/` and hand its full
    DAVINCI execution, inspection, and PDF promotion to `$postprocess-ceres-davinci`. Numeric
    preprocessing scripts may write NetCDF and summaries but must not render plots.
12. Report source collections and versions, period, raw manifest, config, PBS job and exit,
    output path/count/endpoints, contract audit, numeric/science gates, and preserved or replaced
    products. Hand run-ready paths and filename templates to `$configure-cesm3-runs`.

## Guardrails

- Never use `/glade/work/tvmora` legacy products as contract-conforming forcing or validation
  truth; they are seed material only.
- Never overwrite raw downloads, bias coefficients, or populated contract directories without
  explicit replacement authority and a resolved destination.
- Choose either `scripts/stage_obs.py` or the package `download` layout for a versioned cache.
  Recursive ingestion can read both layouts, but that is not permission to mix provenance.
- Do not accept all-fill files merely because they satisfy the schema. Require raw coverage and
  nonzero active cells appropriate to the sensor sampling.
- For VIIRS periods, require an AERONET-anchored bias artifact and evidence that correction
  improves RMSE before merging it with MODIS.
- Keep the filename stamp as window-start seconds and the scalar CF time as the window center.
- Do not configure or submit CESM cases, and do not run post-model DAVINCI analysis, as part of
  this skill. Use the owning skills for those stages.
- Never execute `scripts/era5_cam_nudging_seed/` unchanged; it retains legacy L30, collaborator
  scratch, and filename defaults for provenance.
- Keep generated data under `/glade/work/fillmore/Data/CERES-SARB-CAM7`; do not commit raw or
  generated NetCDF data to the repository.

## Bundled Resources

- `scripts/submit_sp1_preprocessing_pbs.py`: safely submit a versioned SP1 YAML through Derecho
  PBS after checking raw daily coverage and refusing a populated contract destination. Defaults
  to a right-sized shared `develop` job (2 CPUs, 4 GB, 2 hours).
- `scripts/submit_stage_and_build_pbs.py`: queue raw staging for a versioned SP1 YAML's
  start/end range through PBS, self-chaining into `submit_sp1_preprocessing_pbs.py` on success.
  Preferred entry point for multi-day/production periods; defaults to shared `develop` with its
  6-hour maximum.
- `references/data-products.md`: identify raw, run-ready, diagnostic, validation, and ERA5
  products and apply the frozen CAM AOD input contract.
