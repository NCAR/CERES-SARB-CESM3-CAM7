# Running CESM3 / CAM7 cases — CERES-SARB-CAM7

Running log + reference for model runs on derecho. Build procedure is in [`BUILD.md`](BUILD.md).

## Run facts (derecho)
- **PBS project / account code: `P19010000`** (charge account; required by `create_newcase`, `case.submit`, and `qcmd`).
- Machine `derecho`, batch system **PBS**. Default queue `main` (dev/short work: `develop`).
- CESM checkout: `/glade/work/fillmore/CESM3/cesm3_0_beta08`. Cases: `/glade/work/fillmore/CESM3/cases/<case>`.
- Run/output dirs (scratch): `/glade/derecho/scratch/$USER/<case>/run`; short-term archive: `…/archive/<case>`.

## How to run a built case
```bash
cd /glade/work/fillmore/CESM3/cases/<case>
./xmlchange JOB_WALLCLOCK_TIME=01:00:00,JOB_QUEUE=main      # as needed
./xmlchange STOP_OPTION=ndays,STOP_N=1,REST_OPTION=ndays,REST_N=1
./case.submit                # charges P19010000
# monitor:
qstat -u $USER ; tail -f /glade/derecho/scratch/$USER/<case>/run/*.log.*
```
- Useful: `./preview_run` (shows PE layout + submit command), `./xmlquery NTASKS_ATM TOTALPES JOB_WALLCLOCK_TIME --value`, `./case.submit --dry-run`.
- Restarts/continue: `./xmlchange CONTINUE_RUN=TRUE` then `./case.submit`.

## Shared executable guard

Do not rebuild a queued/running case, and do not rebuild a case that another queued/running case uses via `--keepexe`. CIME launches the executable from the case's current `EXEROOT`; a submitted PBS job is not a private snapshot of `cesm.exe`.

The SP2 July 2008 pair submitted on 2026-06-28 used one shared executable:

- `sp2_200807_mam4_modis` / PBS `6581712.desched1`
- `sp2_200807_mam4_free` / PBS `6581729.desched1`

Both cases resolve `EXEROOT` to `/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/bld`, and the only executable for the pair is `/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/bld/cesm.exe`. For source development, keep using a new dev case such as `/glade/work/fillmore/CESM3/cases/sp2_dev_<topic>`, which will build under `/glade/derecho/scratch/$USER/sp2_dev_<topic>/bld`.

Checkpoint 2026-06-30: `qstat -u $USER` was empty. Both full-July jobs finished with PBS `Exit_status = 0` and `case.run success`: nudged at 2026-06-28 23:49:30 MDT, free at 2026-06-28 23:45:24 MDT. Each case wrote 248 3-hour records. VP5, VP6, and VP8 remain pending until their post-run sign-off commands below are run; VP7 is already signed off with the separate dev pair below.

Task 11 transport/advection proof passed on 2026-06-28 with separate development cases
`sp2_transport_pulse` / `sp2_transport_free` and a separate executable root
`/glade/derecho/scratch/fillmore/sp2_transport_pulse/bld/cesm.exe`. The July 2008
shared executable was not rebuilt or repointed. Final checker metrics:
`post_mask_max=0`, `inside_abs_sum=124.973`, `outside_abs_sum=401.311`,
`total_abs_sum=526.284`, `outside_frac=0.762537`, `outside_abs_max=0.855975`.
DAVINCI PDFs are under
`/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP2_AOD_nudging/transport_proof/sp2_transport_pulse/`.

## SP2 MAM4 sign-off workflow

The submitted July 2008 nudged/free pair has finished. Run numeric gates from the completed
h0 files, then run the applicable YAML analysis through the DAVINCI pipeline. Direct plotting
helpers were removed on 2026-07-13 and must not be recreated.

```bash
PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python

NUDGED_RUN=/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/run
FREE_RUN=/glade/derecho/scratch/fillmore/sp2_200807_mam4_free/run
NUDGED_H0I=$(ls -t "$NUDGED_RUN"/sp2_200807_mam4_modis.cam.h0i*.nc | head -1)
NUDGED_H0A=$(ls -t "$NUDGED_RUN"/sp2_200807_mam4_modis.cam.h0a*.nc | head -1)
FREE_H0A=$(ls -t "$FREE_RUN"/sp2_200807_mam4_free.cam.h0a*.nc | head -1)

"$PY" sp2_tests/check_integration.py --h0 "$NUDGED_H0I"
PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7 \
  "$PY" -m davinci_monet.cli.app run \
  analyses/davinci/cam-aod-monthly-analysis-july-2008.yaml
```

The full July 2008 pair did not request a 3-D aerosol field, so VP7 uses a separate short
dev/sign-off pair with its own build root. VP7 writes `dst_a1:I` because the profile gate
compares an instantaneous aerosol profile against instantaneous `AODNDG_RATIO`/`AODNDG_MASK`
diagnostics; a time-mean aerosol profile is not valid for this check. The default VP7 run is
six timesteps with one instantaneous history record at the first active AOD update.

```bash
bash scripts/setup_sp2_vp7_profile_runs.sh --dry-run
bash scripts/setup_sp2_vp7_profile_runs.sh --submit
```

The VP7 defaults create `sp2_vp7_200807_mam4_modis` and `sp2_vp7_200807_mam4_free`; the nudged
case builds its own `/glade/derecho/scratch/$USER/sp2_vp7_200807_mam4_modis/bld/cesm.exe`.
Do not point these cases at the full-July shared executable. The default VP7 layout uses
32 tasks on the `develop` queue because Derecho's CIME batch config only allows `develop`
for jobs with 1-63 tasks and a maximum one-hour walltime.

The former VP7 direct profile renderer has been removed. Any renewed profile verification
must be expressed as a DAVINCI YAML analysis before plots are generated.

## SP3 band-optics smoke workflow

SP3 source lives in this repo under `src/cam/aod_optics_*.F90`, with CAM patch files under
`src/cam/*.diff`. Deploy into the CAM checkout and a dev case with:

```bash
bash scripts/sp2_deploy.sh /glade/work/fillmore/CESM3/cases/sp3_smoke_mam4
```

Current dev/smoke case:

- Case: `/glade/work/fillmore/CESM3/cases/sp3_smoke_mam4`
- Run dir: `/glade/derecho/scratch/fillmore/sp3_smoke_mam4/run`
- Zero-LW output: `/glade/derecho/scratch/fillmore/sp3_smoke_mam4_zero`
- Physical-LW output: `/glade/derecho/scratch/fillmore/sp3_smoke_mam4_phys`
- LW zero table: `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lw_omega_g_zero.nc`
- LW physical table: `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lw_omega_g.nc`

The case-local `env_mach_specific.xml` is patched for foreground interactive runs with
`mpiexec -n 32`; `preview_run` should show `mpiexec  -n 32  --label  --line-buffer`.
The current `user_nl_cam` points at the physical LW table and writes instantaneous
`AODVIS,AODVISdn` history (`avgflag_pertape='I'`) for SP3 comparison.

Verification commands used on 2026-06-28:

```bash
PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python

"$PY" -m pytest sp3_tests/test_format_conformance.py -v

SP3_SAMPLE_FILE=/glade/derecho/scratch/fillmore/sp3_smoke_mam4_phys/AER_MAM4_LW06.20080701.10800.nc \
  "$PY" -m pytest sp3_tests/test_format_conformance.py -v

```

The smoke workflow is numeric only. Final maps are generated by the YAML analysis documented
under **DAVINCI Analysis Run Directories** below.

Known smoke note: SP3 `SW05` is the finite SARB/LFL visible band. It is closest to CAM
`AODVIS`, but not bit-identical to CAM's point diagnostic. In the 6-hour smoke,
`SW05` vs instantaneous `AODVISdn` at 2008-07-01 03:00 UTC had global-mean relative
absolute difference `4.7083e-02`. The SP3 field is finite, nonnegative, and in the
right visible magnitude; the residual is a diagnostic-convention difference, not the
earlier source-fraction remap bug.

## SP3 10-day verification workflow

Task 11 used ON/OFF 10-day twins at f09/MAM4:

- ON case: `/glade/work/fillmore/CESM3/cases/sp3_verify10_on`
- OFF case: `/glade/work/fillmore/CESM3/cases/sp3_verify10_off`
- Shared executable: `/glade/derecho/scratch/fillmore/sp3_smoke_mam4/bld/cesm.exe`
- ON output: `/glade/derecho/scratch/fillmore/sp3_verify10_on`
- OFF output: `/glade/derecho/scratch/fillmore/sp3_verify10_off`
- cprnc logs: `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3_verify10/cprnc_fixed_on_vs_off/`

Important build note: the first rebuilt ON attempt still differed in CAM `AODVIS`/`AODVISdn`
because the case executable compiled stale `sp3_smoke_mam4/SourceMods/src.cam` copies of
`aod_optics_tap.F90` and `aod_nudging_optics.F90`. The fix is to redeploy/patch the case
SourceMods so both calls pass `do_outfld=.false.`, rebuild, and rerun ON. The stale ON output
was moved aside to `/glade/derecho/scratch/fillmore/sp3_verify10_on_pre_sourcemods_fix_260629`.

Verification commands used on 2026-06-29:

```bash
PY=/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python
CPRNC=/glade/campaign/cesm/cesmdata/cprnc/cprnc

"$PY" -m pytest sp3_tests/test_check_sp3_outputs.py sp3_tests/test_silent_optics_contract.py -q

SP3_SAMPLE_FILE=/glade/derecho/scratch/fillmore/sp3_verify10_on/AER_MAM4_LW06.20080705.43200.nc \
  "$PY" -m pytest sp3_tests/test_format_conformance.py -v

"$PY" - <<'PY'
from pathlib import Path
from sp3_tests.check_sp3_outputs import summarize_directory, check_physical_invariants
root = Path('/glade/derecho/scratch/fillmore/sp3_verify10_on')
print(summarize_directory(root))
print(check_physical_invariants(root))
PY

for on in /glade/derecho/scratch/fillmore/sp3_verify10_on/run/sp3_verify10_on.cam.h0i.*.nc; do
  base=$(basename "$on")
  off=${base/sp3_verify10_on/sp3_verify10_off}
  stamp=${base#sp3_verify10_on.cam.h0i.}; stamp=${stamp%.nc}
  "$CPRNC" "$on" "/glade/derecho/scratch/fillmore/sp3_verify10_off/run/$off" \
    > "/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3_verify10/cprnc_fixed_on_vs_off/${stamp}.log"
done
```

Task 11 results:

- Fixed ON PBS job `6584612.desched1`, 32 MPI tasks, walltime used `01:14:23`, exit status 0.
- ON wrote 2,106 files = 81 complete 3-hour groups x 26 bands, from `20080701.00000` through `20080711.00000`; no missing bands or cadence gaps.
- OFF wrote zero `AER_MAM4_*.nc` files.
- All 10 daily ON/OFF instantaneous CAM history files were `cprnc` `IDENTICAL`, including `AODVIS` and `AODVISdn`.
- Full SP3 invariant scan passed over 2,106 files: `max_ext=2.4869134426116943`, `max_sca=2.2102725505828857`, `max_sca_minus_ext=0.0`, `max_abs_asm=0.9120195508003235`.
- Real-file format conformance passed on `AER_MAM4_LW06.20080705.43200.nc`.

Current replacement for the historical Task 12 direct plot commands:

```bash
DAVINCI_PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7 \
  "$DAVINCI_PY" -m davinci_monet.cli.app run \
  analyses/davinci/sarb-band-aerosol-optics-july-2008.yaml
```

Task 12 results:

- Retained final PDFs: VP1-VP7 in `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify10/`; zero-LW VP6 proof in `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify10_zero_lw/`.
- Final products are PDFs only; `find /glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics -maxdepth 2 -type f -name '*.png' | wc -l` returned `0`.
- The historical direct renderer was removed on 2026-07-13. Its retained results below are an
  audit record, not a current plotting workflow.
- Numeric summaries: VP1 visible AOD `min=0.00661516 mean=0.0896767 max=0.685782`; VP2 visible omega `min=0.777717 mean=0.964193 max=0.999535`; VP3 visible g `min=0.49808 mean=0.67495 max=0.814284`; VP4 dust spectral AOD `min=0.0914722 mean=0.167668 max=0.216824`; VP4 pollution spectral AOD `min=0.0232461 mean=0.143272 max=0.341774`; VP5 dust vertical extinction `min=1.19042e-05 mean=0.00677574 max=0.0328544`; physical-LW VP6 scattering `min=3.11835e-05 mean=0.059124 max=1.4929`; VP7 LW extinction `min=0.000591185 mean=0.0674055 max=1.66544`; zero-LW VP6 scattering `min=0 mean=0 max=0`.
- VP1: PASS — visible column AOD is finite/nonnegative and shows expected Sahara/Sahel, Arabian, Asian, biomass-burning, and pollution-region structure.
- VP2: PASS — visible single-scatter albedo is bounded in `[0.777717, 0.999535]`, with lower values over absorbing dust/smoke regions and high values over remote ocean/clean regions.
- VP3: PASS — visible asymmetry is bounded in `[0.49808, 0.814284]`, spatially coherent, and has no invalid out-of-range cells.
- VP4: PASS — pollution AOD falls steeply with wavelength, dust AOD is flatter, omega and g vary smoothly by band, and there are no band spikes.
- VP5: PASS — the selected Saharan dust column peaks in lower model levels and is small aloft.
- VP6: PASS — physical-LW table shows LW window scattering concentrated in dust regions; the zero-LW table renders flat zero everywhere, proving the table gate is active.
- VP7: PASS — LW window extinction follows the expected dust belt and related aerosol structure, with no blank or wrapped-map failure.

### SP3 AOD-nudged five-day diagnostic addendum

The first AOD-nudged 10-day rerun was interrupted by a session disconnect before completion.
It did not produce a usable day-6 restart: the case had `REST_OPTION=ndays,REST_N=10`,
so CESM would only write restart files at the 10-day endpoint. The partial output is preserved
and used only as a five-day AOD-nudged diagnostic source:

- AOD-nudged case: `/glade/work/fillmore/CESM3/cases/sp3_verify10_aodnudged`
- Preserved partial output: `/glade/derecho/scratch/fillmore/sp3_verify10_aodnudged_partial_disconnect_260629_091812`
- Free-running reference output: `/glade/derecho/scratch/fillmore/sp3_verify10_free_running_ref` -> `/glade/derecho/scratch/fillmore/sp3_verify10_on`
- Five-day SP3 VP PDFs: `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify5_aodnudged/`
- Five-day AOD diagnostic PDFs: `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify5_aodnudged/aod_diagnostics/`
- Free-running reference plot copy: `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify10_free_running/`

The preserved partial contains 1,040 SP3 files = 40 complete 3-hour groups x 26 bands,
from `20080701.00000` through `20080705.75600`. A sample SP3 file has `nudged=1`.
The interrupted CAM history file has the requested `AODNDG_*` and flux variables defined
(`FSNT`, `FSNTC`, `FLNT`, `FLNTC`, `FSNS`, `FSNSC`, `FLNS`, `FLNSC`), but the file has zero
time records after the disconnect. Therefore true CAM history diagnostics such as
`AODNDG_MODEL_POST - AODNDG_MODEL_PRE` and usable SW/LW flux time series require the deferred
clean 10-day rerun.

The five-day diagnostic command was a legacy direct renderer and was removed on 2026-07-13.
The following values remain as a historical numeric record. Any regenerated plots must be
declared in a YAML analysis under `analyses/davinci/` and run with `davinci-monet run`.

Five-day AOD diagnostic results:

- Retained final PDFs only: 10 AOD-diagnostic maps in the `aod_diagnostics/` directory.
- Mean observation AOD: `n=37868 min=0 mean=0.194496 max=4.927`; observation-derived means include only active observed cells.
- Mean CAM analyzed AOD from SP3 visible-column output: `n=55296 min=0.00655413 mean=0.139215 max=1.68475`.
- Analysis minus observation AOD: `n=37868 min=-3.49096 mean=-0.00423001 max=1.04903`; plotted with robust symmetric limits.
- Analysis/observation ratio: `n=37847 min=0.0371868 mean=1.12161 max=34.366`; plotted with robust percentile limits.
- Nudge fraction: `n=55296 min=0 mean=0.104165 max=0.95`.
- Nudged minus free-running AOD response: `n=55296 min=-0.93322 mean=0.0599933 max=1.62466`.
- Nudged minus free-running AOD response at observed cells: `n=37868 min=-1.42095 mean=0.0864683 max=4.74604`.

Plot naming note: these five-day products use SP3 visible-column output as the analyzed AOD.
The formal CAM analysis increment (`AODNDG_MODEL_POST - AODNDG_MODEL_PRE`) is not available
from the disconnected run, so the available response plots are labeled `nudged minus free-running`
rather than `analysis increment`.

## DAVINCI Analysis Run Directories

The self-contained DAVINCI migration writes deterministic run directories under
`/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/`. The executable code lives in
DAVINCI; this repo keeps the project analysis YAML under `analyses/davinci/`.

### 2008 MODIS monthly AOD acceptance (2026-09-08)

- The annual MODIS-only f09 contract at
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr_2008_v2/` contains exactly
  2,928 three-hour files (eight per day), with no missing or extra windows. The full-file audit
  found no schema failures, numeric failures, or all-fill products.
- `analyses/davinci/modis-aod-monthly-analysis-2008-v2.yaml` completed through the full DAVINCI
  pipeline. At explicit user direction this plotting run was executed directly rather than
  submitted to PBS. Its manifest is `completed`; it produced one monthly-analysis NetCDF,
  12 final PDFs, 12 inspection previews, and a passing `inspection/inspection.json` with no
  reported errors.
- The user visually accepted all 12 monthly maps on 2026-09-08. The maps show the expected
  seasonal dust, biomass-burning, and pollution structure, with monthly global means from
  0.127 to 0.172. Sparse cells near the high-latitude coverage edge remain a non-blocking QC
  follow-up.
- Accepted PDFs are under
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/modis-aod-monthly-analysis-2008-v2/`; the
  complete reproducible run is under
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/modis-aod-monthly-analysis-2008-v2/`.
- Annual generic multi-file ingestion was slower than expected. Cache or optimize the monthly
  aggregation before future full-year rerenders. This observation-only analysis has no owning
  CESM run-history record.

Run commands:

```bash
DAVINCI_PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
export PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7

"$DAVINCI_PY" -m davinci_monet.cli.app run analyses/davinci/modis-viirs-aod-monthly-analysis-july-2008.yaml
"$DAVINCI_PY" -m davinci_monet.cli.app run analyses/davinci/cam-aod-analysis-july-2008.yaml
"$DAVINCI_PY" -m davinci_monet.cli.app run analyses/davinci/cam-aod-monthly-analysis-july-2008.yaml
"$DAVINCI_PY" -m davinci_monet.cli.app run analyses/davinci/modis-aod-nudging-band-optics-july-2008.yaml
"$DAVINCI_PY" -m davinci_monet.cli.app run analyses/davinci/sarb-band-aerosol-optics-july-2008.yaml

"$DAVINCI_PY" -m davinci_monet.cli.app inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/modis-viirs-aod-monthly-analysis-july-2008 \
  --preset gridded_aod_diagnostics
"$DAVINCI_PY" -m davinci_monet.cli.app inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/cam-aod-analysis-july-2008 \
  --preset gridded_aod_diagnostics
"$DAVINCI_PY" -m davinci_monet.cli.app inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/cam-aod-monthly-analysis-july-2008 \
  --preset gridded_aod_diagnostics
"$DAVINCI_PY" -m davinci_monet.cli.app inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/modis-aod-nudging-band-optics-july-2008 \
  --preset sarb_band_aerosol_optics
"$DAVINCI_PY" -m davinci_monet.cli.app inspect /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/sarb-band-aerosol-optics-july-2008 \
  --preset sarb_band_aerosol_optics
```

Current regenerated run directories:

- MODIS/VIIRS monthly AOD:
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/modis-viirs-aod-monthly-analysis-july-2008/`.
  Completed with `products/monthly_aod/analysis.nc`, summary JSON, `manifest.json`, 2 final PDFs,
  2 inspection previews, and passing `inspection/inspection.json`.
- CAM AOD five-day analysis:
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/cam-aod-analysis-july-2008/`.
  This is the preserved five-day CAM AOD record. It completed with daily and five-day AOD products,
  summary JSON, `manifest.json`, 36 final PDFs, 36 inspection previews, and passing
  `inspection/inspection.json`.
- CAM AOD full-month July setup:
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/cam-aod-monthly-analysis-july-2008/`.
  This preserved MODIS AOD-nudging analysis is the AOD-only plot set. A clean 2026-07-13
  DAVINCI pipeline run
  completed in 224.1 seconds with 31 daily groups and one July aggregate: 192 final PDFs,
  192 inspection previews, a completed manifest, and all three inspection checks passing.
  The six promoted July aggregate PDFs use audience-facing analysis terminology, global maps,
  area-weighted `Mean:` subtitles, and tight layout. They are copied to
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/modis-aod-nudging-july-2008/`
  and `/glade/work/fillmore/Plots/CERES-SARB-CAM7/modis-aod-nudging-july-2008/`.
  The config stops at `2008-07-31T23:59:59` so the CAM boundary record at
  `2008-08-01T00:00:00` does not create an August daily/monthly group.
- MODIS AOD-nudged ten-day band optics:
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/modis-aod-nudging-band-optics-july-2008/`.
  This is the current requested SW/LW band-optics deliverable. It reads the complete
  AOD-nudged CAM7 band output in
  `/glade/derecho/scratch/fillmore/sp3v2_verify10_lut_aodnudged_camref_dense3_retry1_20260709/`
  and selects 80 three-hourly records per plotted band from July 1 through July 10. The
  `2008-07-11T00:00:00` boundary record is intentionally excluded. The clean 2026-07-13
  expanded DAVINCI pipeline run completed in 953.1 seconds with eight spectral product
  NetCDFs, summary JSON, a completed manifest, 20 final PDFs, 20 inspection previews, and all
  inspection checks passing. The shortwave selection represents ultraviolet (0.340 µm), visible
  (0.546 µm), near-infrared (0.842 µm), and shortwave-infrared (1.66 µm) regions. The named
  longwave selection covers the water vapor (6.51 µm), ozone (9.64 µm), atmospheric-window
  (11.35 µm), and carbon-dioxide (16.7 µm) regions. Accepted copies are under
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/modis-aod-nudging-band-optics-july-2008/`
  and `/glade/work/fillmore/Plots/CERES-SARB-CAM7/modis-aod-nudging-band-optics-july-2008/`.
  The earlier five-map set is preserved in the corresponding `-initial-five` run and plot
  directories.
- SARB ten-day aerosol optics:
  `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/sarb-band-aerosol-optics-july-2008/`.
  This is a valid band-optics analysis, but it is not the MODIS AOD-nudging plot deliverable.
  The clean 2026-07-13 run completed in 606.2 seconds with
  visible and longwave-window product NetCDFs, summary JSON, `manifest.json`, 5 final PDFs,
  5 inspection previews under `inspection/previews/`, and passing `inspection/inspection.json`.
  Its mistakenly promoted copies were removed when the requested MODIS-nudging plot set was
  regenerated.

The MODIS AOD-nudged run covers 20 DAVINCI optics maps: AOD, single-scatter albedo, and asymmetry
for four shortwave spectral regions, plus extinction and scattering optical depth for four named
longwave regions. Each map uses a global domain, a global area-weighted `Mean:` subtitle, solid
gridlines, coastlines, and tight layout. Optical-depth means use three decimal places; SSA and
asymmetry use robust, data-derived nice ranges bounded by their physical `[0, 1]` interval. Older
direct-render products are historical and are not accepted deliverables. Their
renderer scripts were removed on 2026-07-13; the YAML pipeline above is the sole regeneration path.

## Notes / conventions (fill in as we go)
- **Met nudging:** production nudges CAM meteorology toward **ERA5** (not MERRA-2). CAM-ready f09/L32 ERA5 already exists on glade — see [Met nudging — ERA5](#met-nudging--era5) below.
- AOD-nudging namelist group (`&nudging_AOD_nl`) — TBD once the module exists.
- Input data auto-staged to `/glade/derecho/scratch/$USER/inputdata` (or shared `/glade/campaign/cesm/cesmdata/inputdata`).

## Met nudging — ERA5

Production runs nudge CAM meteorology toward **ERA5** (replacing the prior attempt's MERRA-2 / GEOS-IT). CAM's met-nudging (`src/physics/cam/nudging.F90`, namelist group `&nudging_nl`, `Nudge_*` names) is data-agnostic — it relaxes the model toward a CAM-grid analysis dataset. **This is independent of SP1/SP2** and **coexists** with AOD nudging (met via `&nudging_nl`; aerosol via `&aod_nudging_nl`).

**CAM-ready ERA5 dataset (already on glade — no prep needed):**
- Path: `/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl/`
- Files: `ERA5_fv09.cam2.i.%y-%m-%d-%s.nc` — **f09, 32 levels (L32)**, **hourly** (`Nudge_Times_Per_Day=24`), **1979–~2024** (covers the v1 2020 window), ~8.6 TB. Source: W. Chapman (CGD/AMP).
- Provenance of the config below: a working ACOM f09 ERA5 `FCnudged` case, `/glade/campaign/acom/acom-da/Methane_simulations/f.e22.FCnudged.f09_f09_mg17.slh.2000.ERA5_cmip7.lght12_ct2025.001/.../user_nl_cam`.

> ⚠️ **Vertical-level match required.** This set is **L32**. It only works if the production CAM7 compset runs **32 levels** (same hybrid coefficients). If production is 58/70-level, this set won't match — use a matching-level ERA5 (ACOM has an L58 CONUS set; regrid tooling at `/glade/campaign/acom/acom-da/Gaubert/process_reanalysis_for_musica/`) or regrid ERA5 to the model levels. Confirm `nlev` for the chosen compset before the production run. (`Nudge_Vwin_Hindex=33` below corroborates 32 levels.)

**Reference `user_nl_cam` block** (set `Nudge_Beg_*`/`Nudge_End_*` to the actual run window; coefficients 0.25 on U/V/T/Q, PS off, full-domain windows):
```
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
Nudge_Beg_Year =2020
Nudge_Beg_Month=1
Nudge_Beg_Day  =1
Nudge_End_Year =2021
Nudge_End_Month=1
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
Notes: `Nudge_*` namelist names are the long-standing CAM met-nudging (`nudging.F90`) names and carry over to CAM7 (confirm against the CAM7 `nudging.F90` namelist). The dataset format (f09 analysis files) is CAM-version-independent; only the vertical-level match matters. For the SP2 smoke tests we use `F2000dev` (prescribed SSTs, **no** met-nudging), so ERA5 nudging is a **production-run** concern, not a build/smoke-test one.

## Run log
| Date | Case | Compset / Res | Chem/Aero | Purpose | Length | Status | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-24 | `sp3_200807_mam4_modis_era5_optics` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | Full-month combined ERA5 meteorological and MODIS AOD nudging with 3-D SW/LW LFL-band aerosol optics | 31 days | **queued** | PBS `6889504.desched1`, `main`/`cpu`, one exclusive Derecho CPU node / 128 MPI tasks / 235 GB, walltime `12:00:00`; queued at 15:47 MDT. Case `/glade/work/fillmore/CESM3/cases/sp3_200807_mam4_modis_era5_optics` uses the validated dense3 executable `/glade/derecho/scratch/fillmore/sp3_lut_build/bld/cesm.exe`, dense3 CAM-reference LUT, and physical LW omega/g table. `aod_optics_on=.true.` with a 3-hour interval for all 14 SW and 12 LW bands; expected output is 249 complete time groups x 26 bands = 6,474 files under `/glade/derecho/scratch/fillmore/sp3_200807_mam4_modis_era5_optics/optics`. |
| 2026-07-23 | `sp2_200807_mam4_modis_era5` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | Combined ERA5 meteorological and MODIS AOD nudging | 31 days | **passed** | PBS `6870141.desched1`, `main`/`cpu`, one node / 128 MPI tasks / 235 GB, exit 0, walltime `00:56:18`, peak memory `74.58 GB`. All 744 hourly July ERA5 files plus the August 1 boundary file and all 248 AOD files were present. Output `/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis_era5/run` contains 248 three-hourly AOD analysis records through `2008-08-01 00:00:00`; the 192-plot DAVINCI daily/monthly suite passed inspection. This run had `aod_optics_on=.false.` and therefore did not write 3-D band properties. |
| 2026-06-28 | `sp3_smoke_mam4` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3 zero-LW table smoke: per-band MAM-LFL files, writer, cadence, schema, zero-scattering LW check | 6 hours | **passed** | Interactive PBS `6583629.desched1`, 32 MPI tasks, foreground `mpiexec -n 32`. Rebuilt after destination-normalized remap and PIO writer broadcast fixes. Output `/glade/derecho/scratch/fillmore/sp3_smoke_mam4_zero`: 78 files = 26 bands at `00000`, `10800`, `21600`. Format conformance passed. `LW06` zero-table scattering max `0.0`, `sca <= ext`, finite fields. |
| 2026-06-28 | `sp3_smoke_mam4` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3 physical-LW table smoke and VP plot suite | 6 hours | **passed** | Same executable/case, physical table `aod_lw_omega_g.nc`, output `/glade/derecho/scratch/fillmore/sp3_smoke_mam4_phys`: 78 files. Format conformance passed on `LW06`. LW04-LW08 all had positive scattering and `sca <= ext`; `LW06` scattering column mean `5.75386608e-02`, extinction column mean `6.55411994e-02`. DAVINCI/PDF suite in `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/smoke_all/`; no retained PNGs. |
| 2026-06-29 | `sp3_verify10_on` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3 Task 11 fixed 10-day ON run with physical LW table | 10 days | **passed** | PBS `6584612.desched1`, queue `develop`/`cpudev`, 1 node / 32 MPI tasks, walltime `01:14:23`, exit 0. Shared executable rebuilt at 03:16 after patching stale case SourceMods to pass `do_outfld=.false.`. Output `/glade/derecho/scratch/fillmore/sp3_verify10_on`: 2,106 files = 81 complete 3-hour groups x 26 bands, `20080701.00000` through `20080711.00000`, no missing bands/gaps. Full invariant scan passed (`max_sca_minus_ext=0.0`, `max_abs_asm=0.9120195508003235`). |
| 2026-06-29 | `sp3_verify10_off` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3 Task 11 OFF twin / read-only proof | 10 days | **passed** | Foreground in interactive PBS `6583629.desched1`, 1 node / 32 MPI tasks, walltime about `00:58:35` for OFF segment, `aod_optics_on=.false.`. Output path `/glade/derecho/scratch/fillmore/sp3_verify10_off` contained zero `AER_MAM4_*.nc` files. All 10 daily `h0i` pairs compared against fixed ON with `cprnc` and were `IDENTICAL`, including `AODVIS`/`AODVISdn`; logs under `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3_verify10/cprnc_fixed_on_vs_off/`. |
| 2026-06-29 | `sp3_verify10_aodnudged` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | AOD-nudged SP3 rerun, five-day diagnostics from interrupted 10-day attempt | 5 days available; 10-day rerun deferred | **partial, plots passed** | Foreground run in interactive PBS `6587897.desched1` was interrupted by session disconnect before day 6. Partial preserved at `/glade/derecho/scratch/fillmore/sp3_verify10_aodnudged_partial_disconnect_260629_091812`: 1,040 files = 40 complete 3-hour groups x 26 bands, `20080701.00000` through `20080705.75600`, sample `nudged=1`. No usable restart because `REST_N=10`. VP1-VP7 PDFs in `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify5_aodnudged/`; 10 AOD-diagnostic PDFs in `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify5_aodnudged/aod_diagnostics/`. CAM h0i has requested AOD/flux variables defined but zero time records, so formal CAM analysis increment and flux checks await a clean rerun. |
| 2026-06-28 | `sp2_transport_pulse` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | Task 11 transport proof: initial high-AOD pulse followed by fill-only obs | 2 days | **passed** | Ran foreground in interactive PBS allocation `6582111.desched1`, queue `develop`, 1 node / 32 MPI tasks. CaseStatus: `model execution success` at 13:05 MDT. Separate executable `/glade/derecho/scratch/fillmore/sp2_transport_pulse/bld/cesm.exe`; did not touch the July shared executable. Outputs: `sp2_transport_pulse.cam.h0a.0001-01-01-03600.nc` (`AODVIS`) and `sp2_transport_pulse.cam.h0i.0001-01-01-03600.nc` (`AODNDG_*`). |
| 2026-06-28 | `sp2_transport_free` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | Task 11 fill-only free-control pair for transport proof | 2 days | **passed** | Cloned with `--keepexe` from `sp2_transport_pulse` and used the transport proof executable, not the July shared executable. CaseStatus: `model execution success` at 13:23 MDT. Checker passed with `post_mask_max=0`, `outside_frac=0.762537`, and `outside_abs_max=0.855975`; no stale PNGs in the DAVINCI plot directory. |
| 2026-06-28 | `sp2_vp7_200807_mam4_modis` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | VP7 aerosol vertical-profile sign-off with MODIS AOD nudging | 6 timesteps | **passed** | Final PBS `6582067.desched1`, queue `develop`, walltime `01:00:00`, 1 node / 32 MPI tasks, separate executable `/glade/derecho/scratch/fillmore/sp2_vp7_200807_mam4_modis/bld/cesm.exe`. Wrote instantaneous `dst_a1:I` and `AODNDG_*` to `h0i.2008-07-01-10800.nc`; `verify_profile.py` selected `(time,lat,lon)=(0,113,122)`, `max_rel_spread=0.0391554`, `median_rel_error=0.0547748`, `candidate_pass_count=2/10039`, plot `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP2_200807_mam4/vp7/sp2_vp7_dst_a1_profile_ratio.pdf`. |
| 2026-06-28 | `sp2_vp7_200807_mam4_free` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | VP7 free-running reference paired with profile sign-off | 6 timesteps | **passed** | Final PBS `6582068.desched1`, queue `develop`, walltime `01:00:00`, 1 node / 32 MPI tasks. Cloned with `--keepexe` from the VP7 nudged case and used the VP7 executable, not the July 2008 shared executable. Wrote instantaneous `dst_a1:I` to `h0i.2008-07-01-10800.nc`. |
| 2026-06-28 | `sp2_200807_mam4_modis` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | July 2008 SP2 real-observation run with MODIS AOD nudging | 31 days | **complete; gates pending** | PBS `6581712.desched1`, queue `main`, walltime `00:53:42`, exit 0, 1 node / 128 MPI tasks. CaseStatus: `model execution success` and `case.run success` at 2026-06-28 23:49:30 MDT. `aod_nudge_on=.true.`, obs path `/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/`. Run dir `/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/run`: `h0a` has 248 records from `20080701:5400` to `20080731:81000` with `AODVIS`/`FSNTC`; `h0i` has 248 records from `20080701:10800` to `20080801:0` with `AODNDG_MASK`, `AODNDG_MODEL_PRE`, `AODNDG_MODEL_POST`, and `AODNDG_OBS`. |
| 2026-06-28 | `sp2_200807_mam4_free` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | July 2008 free-running reference paired with MODIS AOD nudging run | 31 days | **complete; gates pending** | PBS `6581729.desched1`, queue `main`, walltime `00:49:18`, exit 0, 1 node / 128 MPI tasks. CaseStatus: `model execution success` at 2026-06-28 23:45:23 MDT and `case.run success` at 23:45:24 MDT. `aod_nudge_on=.false.`, 3-hourly `AODVIS` and `FSNTC` history. Cloned with `--keepexe` from the MODIS case and shares `/glade/derecho/scratch/fillmore/sp2_200807_mam4_modis/bld/cesm.exe`. Run dir `/glade/derecho/scratch/fillmore/sp2_200807_mam4_free/run`: `h0a` has 248 records from `20080701:5400` to `20080731:81000` with `AODVIS`/`FSNTC`; `h0i` has 248 time records from `20080701:10800` to `20080801:0` and no AODNDG fields, as expected for the free/no-nudging case. |
| 2026-07-08 | `sp3_lut_build` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3v2 LFL-native LUT implementation compile gate | build only | **passed** | Fresh dev case built from deployed CAM checkout on `develop`; executable `/glade/derecho/scratch/fillmore/sp3_lut_build/bld/cesm.exe`. Full CAM build completed successfully after adding all SP2/SP3 modules to `src/cam/physics_cam_CMakeLists.txt.diff`; deploy script is idempotent. |
| 2026-07-08 | offline | LFL bands | MAM-LFL | SP3v2 hard-coded LFL band identity check | offline | **passed** | Repo constants in `sp3_optics/lfl_bands.py` matched `/glade/work/fillmore/Data/Optics/SARB/LFL_bands.nc` and `/glade/work/fillmore/Data/Optics/SARB/mam4_mode1_larc_c000003.v2.nc` exactly for both `LFL_SW_bands` and `LFL_LW_bands` (`max_abs=0.0`). |
| 2026-07-08 | `sp3_lut_build` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3v2 remap-path smoke with hard-coded LFL bands and v2 LW omega/g table | 6 hours | **passed** | Foreground in interactive PBS `6670358.desched1`, 1 node / 32 MPI tasks, `mpiexec -n 32`. Output `/glade/derecho/scratch/fillmore/sp3_lut_build_remap`: 78 files = 26 bands at `00000`, `10800`, `21600`; sample `LW06` passed MAM-LFL format conformance. `SW05` and `LW06` fields finite with `sca <= ext`; `LW06` column extinction mean `1.089794e-02`, max `1.999928`; method attr `remap`. |
| 2026-07-08 | `sp3_lut_build` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3v2 LFL-native LUT smoke using reduced full-dimension LUT | 6 hours | **passed** | Same executable/case. LUT file `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4_smoke.nc` has 14 SW, 12 LW, 4 modes, 3x3 refractive-index axes, 5 Chebyshev coefficients. Output `/glade/derecho/scratch/fillmore/sp3_lut_build_lut`: 78 files; sample `LW06` passed MAM-LFL format conformance. `SW05` and `LW06` fields finite with `sca <= ext`; method attr `lut`, `lut_table_version=sp3v2_lfl_chebyshev_mie`. Reduced LUT `SW05` vs remap at `10800`: median ratio `0.663242`, mean absolute relative difference `0.389651` over 55,296 columns; this is a smoke LUT, not the production science table. |
| 2026-07-08 | offline + `sp3_lut_build` | LFL bands / `F2000dev` | MAM4 | SP3v2 production LFL LUT generation and smoke | 6 hours smoke | **passed** | Production table `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4.nc` generated with 14 SW, 12 LW, 4 modes, 7x10 refractive-index axes, 20 Chebyshev coefficients, 100 radius samples, and 700-point Mie grids. Production-LUT smoke output `/glade/derecho/scratch/fillmore/sp3_lut_build_lut_prod`: 78 files = 26 bands at `00000`, `10800`, `21600`; sample `LW06` passed MAM-LFL format conformance. `SW05` and `LW06` fields finite with `sca <= ext`; method attr `lut`, `lut_file=/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4.nc`, `lut_table_version=sp3v2_lfl_chebyshev_mie`. `SW05` at `10800` vs remap: median ratio `0.752293`, mean absolute relative difference `0.321382`; vs CAM `AODVISdn`: median ratio `0.879031`, mean absolute relative difference `0.180040`. |
| 2026-07-08 | offline + `sp3_lut_build` | LFL bands / `F2000dev` | MAM4 | SP3v2 CAM-refindex LUT smoke and visible-AOD check | 6 hours smoke | **passed smoke; raw SW05 caveat** | CAM-refindex table `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4_camref.nc` retargets only per-spectype refractive-index arrays to CAM physprop values; all coefficient arrays are unchanged from `aod_lfl_lut_mam4.nc`. Refindex comparison JSON: `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_refindex_mam_lfl_vs_cam.json`. Smoke output `/glade/derecho/scratch/fillmore/sp3_lut_build_lut_camref`: 78 SP3 files plus matching `sp3_lut_build.cam.h0i.0001-01-01-10800.nc`; sample `LW06` passed MAM-LFL format conformance. Raw LFL `SW05` vs `AODVISdn`: median ratio `0.891014`, mean absolute relative difference `0.126270`. Six-hour smoke like-for-like CAM visible overlap (`SW04/SW05/SW06` remapped to the CAM/RRTMGP visible diagnostic band): median ratio `0.934653`, mean absolute relative difference `0.095297`; the 10-day/global T10 gate remains to run. Method comparison/VP8 artifacts are under `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3v2_T10/smoke_method_comparison_camref*`. |
| 2026-07-08 | offline | CAM native bands | MAM4 | SP3v2 reduced CAM calibration report after RRTMG band-order and visible-gate fixes | offline | **passed reduced gate** | Updated artifacts `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_cam_lut_calibration_reduced_v2.{nc,json}`. All 4 modes and all CAM 14 SW + 16 LW bands with reduced 3x3 refractive-index axes, `ncoef=5`, `n_radius=25`, `n_quad=80`; report gates pass: SW extinction median relative error `0.014512`, visible-band extinction median relative error `0.014186`, SW absorption median relative error `0.026973`, SW asymmetry median absolute error `0.002644`, LW absorption median relative error `0.090766`. Full production T4 remains a required promotion gate before trusting the LFL table beyond reduced-gate status. |
| 2026-07-08 | offline | CAM native bands | MAM4 | SP3v2 full production CAM calibration gate | offline | **passed** | Full-dimension CAM calibration artifacts `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_cam_lut_calibration_full.{nc,json,log}`. Gates pass: SW extinction median relative error `0.0088569`, visible-band extinction median relative error `0.0120862`, SW absorption median relative error `0.0158296`, SW asymmetry median absolute error `0.0016187`, LW absorption median relative error `0.0817231`. |
| 2026-07-08 | `sp3_lut_build` + offline | LFL bands / `F2000dev` | MAM4 | SP3v2 offline CAM-LUT clone support check | one 3-hour snapshot | **passed support check** | Snapshot output `/glade/derecho/scratch/fillmore/sp3v2_t9_snapshot_lut_camref_wet` plus h0i `/glade/derecho/scratch/fillmore/sp3_lut_build/run/sp3_lut_build.cam.h0i.0001-01-01-10800.nc`. Offline verifier output `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3v2_T9/offline_lut_clone/sp3v2_offline_lut_comparison_summary.{csv,json}`. All 26 bands pass when replaying the same production CAM LUT tables offline: max median absolute extinction relative difference `0.0077863`, max strict SSA difference `0.0196882`, max strict asymmetry difference `0.0397976`; strict SSA/asymmetry gates use column scattering optical depth `>1.5e-3`. This is not the independent FABLE_PLAN T9 hard gate. |
| 2026-07-09 | `sp3_lut_build` + offline | LFL bands / `F2000dev` | MAM4 | SP3v2 T9 independent MAM-LFL fine-LUT cross-validation | one 3-hour snapshot | **failed hard gate** | Implemented `sp3_tests/compare_offline_lut.py --reference-method mam-lfl-fine-lut`, using MAM-LFL `mode_physics.lookup_mode_optics()` fine tables plus `num_a*` h0i number fields. Output `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3v2_T9/mam_lfl_fine_lut/sp3v2_offline_lut_comparison_summary.{csv,json}`. Current CAM-refindex production LUT fails the independent gate: examples include `SW01` median absolute extinction relative difference `0.192382`, `LW06` `0.196593`, `LW07` `0.418724`; `SW05` extinction is within 10% (`0.0796437`) but strict SSA/asymmetry outliers remain. Checks using median vs surface wet radius and h0 `num_a*` vs wet-volume-derived number indicate this is a production-LUT/fine-reference mismatch, not a verifier normalization typo. |
| 2026-07-09 | offline investigation | LFL bands | MAM4 | SP3v2 T9 fine-reference root-cause follow-up | targeted diagnostics | **blocker identified** | The MAM-LFL per-band "fine" tables are fine in refractive-index space but inherit a coarse linear radius grid: first two radii are `0.01` and `0.072475` um. `mode_physics.lookup_mode_optics()` lower-bins radius, so many `a2`/`a4` cells are evaluated at `0.01` um and are orders low versus direct MAM-LFL Mie. Direct sampled column checks using `mie_lognormal.mode_averaged_cross_sections_um2()` show `SW01` and `SW05` agree with SP3 LUT output at about 1% median extinction difference, supporting the CAM evaluator and production LUT for those bands. The same direct check still shows a real `LW12` far-IR mismatch (`~12%` median extinction difference and SSA/g outside current T9 thresholds at sampled high-tau columns), and the current CAM-refindex LUT artifact records an older `mie_source` attribute than the checked-in generator. A full single-core LUT regeneration was started and stopped after ~20 min because it was too slow for debugging; it left only zero-byte `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4_regen_current.log`. Do not promote `lut` until the T9 hard gate is redefined around a valid independent reference and the `LW12` discrepancy is resolved or explicitly scoped as far-IR/report-only. |
| 2026-07-09 | offline + `sp3_lut_build` | LFL bands / `F2000dev` | MAM4 | SP3v2 dense3 LUT and corrected direct-MIE T9 hard gate | one 3-hour snapshot | **passed** | Regenerated CAM-refindex dense table `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4_camref_dense3_20260709.nc` with `--refindex-subdivisions 3 --workers 32`; refindex report `/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4_camref_dense3_20260709_refindex_report.json`. Added direct sampled MAM-LFL Mie reference `--reference-method mam-lfl-direct-mie-sampled` with wet-volume normalization, dry-mass `PDELDRY` h0i requirement, X_CAP=200 handling, complete aerosol-species checks, and no silent sample loss. Fresh dry-mass snapshot output `/glade/derecho/scratch/fillmore/sp3v2_t9_snapshot_lut_camref_dense3_drymass_20260709`; h0i `/glade/derecho/scratch/fillmore/sp3_lut_build_t9_dense3_drymass_run/sp3_lut_build.cam.h0i.0001-01-01-10800.nc`. Corrected T9 artifacts `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3v2_T9/direct_mie_dense3_snapshot_wetvol_4col_drymass/sp3v2_offline_lut_comparison_summary.{csv,json}`: all 26 bands pass; deterministic 4-column sample per band; max median extinction relative difference `0.0210528` (`LW12`), max strict SSA difference `0.00801524`, max strict asymmetry difference `0.00826919`. An 8-column run was stopped after >33 min with no summaries; the 4-column dry-mass direct-MIE gate is the accepted T9 artifact. CAM LUT reader now rejects non-`a1,a2,a3,a4` `mode_order`; shared executable rebuilt successfully at `/glade/derecho/scratch/fillmore/sp3_lut_build/bld/cesm.exe`. |
| 2026-07-09 | `sp3_verify10_on/off/remap/aodnudged` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3v2 dense3 T10 current-executable rerun | 10 days each | **passed** | Fresh dense3/current-executable jobs used `/glade/derecho/scratch/fillmore/sp3_lut_build/bld/cesm.exe`. LUT ON `6682360.desched1` completed cleanly at 14:58:46 MDT with PBS `Exit_status=0`, walltime `01:17:43`, and 2,106 SP3 files in `/glade/derecho/scratch/fillmore/sp3v2_verify10_lut_on_camref_dense3_20260709`. LUT OFF `6682361.desched1` completed cleanly at 14:38:38 MDT with PBS `Exit_status=0`, walltime `00:57:34`, and zero SP3 files. First remap `6682362.desched1` and AOD-nudged `6682365.desched1` attempts ended early with partial outputs and no CAM/CESM fatal (`Exit_status=-32` with 1,040 files; `Exit_status=265` with 894 files); both used stale 55 GB resources, and AOD-nudged reported `resources_used.mem=56477068kb`. Retry jobs were moved from the CIME-generated 12-hour/235 GB exclusive request to 3-hour/128 GB scatter with `qalter`. Remap retry `6683100.desched1` completed with `Exit_status=0`, walltime `01:09:26`, peak `resources_used.mem=96451300kb`, and 2,106 files in `/glade/derecho/scratch/fillmore/sp3v2_verify10_remap_on_camref_dense3_retry1_20260709`. AOD-nudged retry `6683101.desched1` completed with `Exit_status=0`, walltime `01:23:07`, peak `resources_used.mem=88617900kb`, and 2,106 files in `/glade/derecho/scratch/fillmore/sp3v2_verify10_lut_aodnudged_camref_dense3_retry1_20260709`. Read-only T10 verifier output `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3v2_T10/verify10_lut_on_off_dense3_20260709/sp3v2_t10_readonly_summary.json`: LUT ON 2,106 files, LUT OFF 0 files, AOD-nudged 2,106 files, all 10 daily ON/OFF h0i pairs `cprnc` identical, `max_sca_minus_ext=0`. Method comparison artifacts are in `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3v2_T10/verify10_method_comparison_dense3_20260709/`: all 26 bands summarized; raw `SW05` vs remap median ratio `0.794502` and mean absolute relative difference `0.284064`; raw `SW05` vs `AODVISdn` median ratio `0.874314` and mean absolute relative difference `0.143199`; like-for-like `CAMVIS` vs `AODVISdn` median ratio `0.916612` and mean absolute relative difference `0.111177`; `LW06` LUT/remap median ratio `1.214117`. VP8 PDFs are under that directory's `vp8/`. VP1-VP7 DAVINCI PDFs passed visual contact-sheet inspection under `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify10_lut_dense3_20260709/` with no final PNGs. AOD-nudged diagnostics passed on the 80 h0-overlap stamps (`20080701.10800` through `20080711.00000`), output `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3v2_T10/verify10_aodnudged_camref_dense3_20260709/`, aggregate active nudge fraction `0.171237`, analysis increment mean `0.00065035`, SP3 SW05 nudged-minus-free mean `0.0409748`, coherence correlation `0.394106`. Plot commands require `PYTHONPATH=/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7` so `davinci_monet.plots` resolves to the real DAVINCI checkout rather than this repo's local namespace tests. |
| 2026-07-08 | `sp3_verify10_on/off/remap/aodnudged` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | SP3v2 T10 long verification jobs: LUT ON/OFF read-only proof, remap comparison, AOD-nudged LUT rerun | 10 days each | **queued** | Initial no-batch LUT ON attempt was stopped at 1,040 files because the 6-hour `cpudev` allocation could not safely reach the 2,106-file 10-day gate; partial preserved at `/glade/derecho/scratch/fillmore/sp3v2_verify10_lut_on_camref_partial_nobatch_20260708_1812`. Clean queued jobs use `/glade/derecho/scratch/fillmore/sp3_lut_build/bld/cesm.exe`: LUT ON `6675164.desched1`, LUT OFF `6675165.desched1`, remap ON `6675173.desched1`, AOD-nudged LUT `6675174.desched1`. Submitted with 12-hour `main`/`cpu`, then queued resources reduced with `qalter` to 3 hours, 32 cores, 55 GB, `place=scatter` on 2026-07-08 based on partial-run throughput and earlier 10-day SP3 runtimes. Submit logs are under `/glade/work/fillmore/Data/CERES-SARB-CAM7/SP3v2_T10/verify10_lut_on_off/`. |
| 2026-06-27 | `spike_f2000dev_cam7` | `F2000dev` / `f09_f09_mg17` | `ghg_mam4` (MAM4) | spike: confirm CAM7 builds on derecho | — | **built, not run** | `cesm.exe` OK (70 MB). Built login node, conda-free env, `-j16`, ~8.7 min. Not yet submitted. |

<!-- Append new runs above this line. Capture: case, compset/res, chem, walltime, # PEs, sim length, wallclock, throughput (sim-yr/day), output path, and outcome. -->
