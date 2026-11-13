# Monthly 2008 CAM7 case configuration

Prepare twelve independent ERA5- and MODIS-nudged CAM7/MAM4 cases with
three-hourly aerosol optics in all 14 SW and 12 LW bands. Each case starts ten
model days before its analysis month. Both nudging systems operate during
spinup; analysis must exclude spinup. March is truncated at
**2008-03-08 21:00 UTC**, because March 9-10 ERA5 files are missing and CAM reads
the next hourly analysis ahead. March 8 is therefore a partial analysis day.

The user selected **NO_LEAP** on 2026-09-08. February has 28 model days; March
spinup starts February 19. February 29 observation/ERA5 files remain preserved
but are not requested by the model. The original Gregorian CF observation
times remain unchanged, including their 27-hour separation across the skipped
leap day; the existing CAM reader interpolates using those stored times.

## Baseline and provenance

- YAML: `config/cesm/monthly_2008_v1.yaml`.
- CESM: `/glade/work/fillmore/CESM3/cesm3_0_beta08`,
  commit `8ce857e8ba55bf7aeca11d93562e36abd635e5a0`.
- `scripts/update_cesm3_reference.py --check` passed on 2026-09-08. The
  generated checkout reference records the deployed CAM overlay.
- Requested alias: `F2000dev`; resolved case compset:
  `2000_CAM70_CLM60%SP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV_SESP`.
- f09/L32, `f09_f09_mg17`, `ghg_mam4`, CAM7 physics, prescribed ocean/ice and
  year-2000 climatological background forcing retained from the established
  experiment. The dates select 2008 meteorology/AOD; they do not turn this
  into a historical-emissions experiment.
- This development compset has no declared science-support pairing in the
  installed checkout. Clone the already selected experiment; do not silently
  select a different atmosphere or forcing compset.
- Clone **`sp3_lut_build`** with `--keepexe`, using its canonical SourceMods
  and `/glade/derecho/scratch/fillmore/sp3_lut_build/bld/cesm.exe`. The older
  July case points at older SourceMods missing the LUT mode-order guard;
  cloning the build owner preserves correspondence with the actual executable.
- Derecho, Intel/MPICH, `P19010000`, 128 MPI ranks, one thread, one exclusive
  235-GB CPU node, `main`, 12-hour walltime. Do not rebuild the shared executable.
- Executable SHA-256:
  `e232b73691f4c80b9715a5f8cf31f6014352048cebb13d9618cc3466e0cdd7fd`.

## Lifecycle and paths

The setup script refuses existing target cases or output roots. It validates
the base case, executable, grid and all requested hourly ERA5/three-hour AOD
windows before creating cases. A new input directory links the preserved
December 2007 spinup and corrected 2008 v2 AOD files without changing them.
CAM's existing single-valid-snapshot behavior covers the unstaged window before
December 22 and after December 31, 2008; these edge conditions are reported.

Case names are `sp3_YYYYMM_mam4_modis_era5_optics_spinup10_v1`, under
`/glade/work/fillmore/CESM3/cases`. Each has separate `run`, `optics`, and
`archive` paths below
`/glade/derecho/scratch/fillmore/CERES-SARB-CAM7/monthly_2008_v1/`.
This transient runtime location has enough capacity for the expected roughly
2.6-TiB output. The project work allocation had only about 1.1 TiB free at
submission preflight. Configuration logs and eventual accepted/preserved
products remain organized below the project data tree.

For each case the command sequence is:

1. `create_clone --case <case> --clone <base> --keepexe --project P19010000`.
2. `xmlchange`: startup at the spinup start, stop after the calculated number
   of model hours, restart every 24 hours, no continuation/resubmission/short-term
   archive, unique output paths, and the configured task/queue settings.
3. Install the rendered `user_nl_cam`; run `case.setup --reset` to regenerate
   copied setup-sensitive files and the PBS resource request.
4. Verify build-setting compatibility with the build owner; restore
   `BUILD_COMPLETE=TRUE` only if settings and executable still match.
5. `preview_namelists`, `check_input_data`, and `preview_run`; inspect generated
   XML, component namelists, and PBS resources. `preview_run` provides this CIME
   version's dry-run submission command; `case.submit --dry-run` is not supported.
6. Record prepared cases and validation evidence. Build remains excluded; use
   the separate submission helper to queue the validated cases and capture IDs.

History contains eight instantaneous three-hour records per file (daily files).
Spinup history and optics are retained. Daily/monthly postprocessing must average
the appropriate records and exclude the documented spinup interval. The final
restart is retained to support later work on the March gap.

| Analysis month | Spinup start | Stop (UTC) | Total model hours | Analysis records |
| --- | --- | --- | ---: | ---: |
| January | 2007-12-22 | 2008-02-01 00:00 | 984 | 248 |
| February | 2008-01-22 | 2008-03-01 00:00 | 912 | 224 |
| March | 2008-02-19 | 2008-03-08 21:00 | 429 | 63 |
| April | 2008-03-22 | 2008-05-01 00:00 | 960 | 240 |
| May | 2008-04-21 | 2008-06-01 00:00 | 984 | 248 |
| June | 2008-05-22 | 2008-07-01 00:00 | 960 | 240 |
| July | 2008-06-21 | 2008-08-01 00:00 | 984 | 248 |
| August | 2008-07-22 | 2008-09-01 00:00 | 984 | 248 |
| September | 2008-08-22 | 2008-10-01 00:00 | 960 | 240 |
| October | 2008-09-21 | 2008-11-01 00:00 | 984 | 248 |
| November | 2008-10-22 | 2008-12-01 00:00 | 960 | 240 |
| December | 2008-11-21 | 2009-01-01 00:00 | 984 | 248 |

Analysis record counts use the established history convention `(month start,
stop]`. The month-start optics state is additionally available; select optics
and history consistently during postprocessing. There are 80 additional history
records from spinup and one additional initial optics time per case.

## Queued cases and verification

All twelve cases were configured and submitted on September 8, 2026 (MDT),
without rebuilding the shared executable. The
[run-history index](../run_history/index.md) links their individual `queued`
records. Generated XML and CAM namelists match the YAML; all cases passed
`preview_namelists`, `check_input_data`, `preview_run`, and
SourceMods/build-setting compatibility checks against the existing executable.

| Analysis month | PBS case.run job |
| --- | --- |
| January | `7355506.desched1` |
| February | `7355507.desched1` |
| March | `7355509.desched1` |
| April | `7355510.desched1` |
| May | `7355512.desched1` |
| June | `7355514.desched1` |
| July | `7355520.desched1` |
| August | `7355522.desched1` |
| September | `7355523.desched1` |
| October | `7355525.desched1` |
| November | `7355526.desched1` |
| December | `7355527.desched1` |

Preflight checked 8,688 distinct required hourly ERA5 files across the selected
NO_LEAP run windows and their boundaries, plus the start/stop f09/L32 coordinates
and hybrid coefficients for each case. The new AOD input view has 3,008 symlinks
to the preserved December spinup and corrected annual products. No missing
March 9-10 ERA5 files are requested. The focused schedule, submission, and
registry tests pass, all 16 registry records validate, and the generated index
is current.

Configuration, storage-reconfiguration, and submission logs plus
`configuration-summary.json` and `submission-summary.json` are under
`/glade/work/fillmore/Data/CERES-SARB-CAM7/logs/case_configuration/monthly_2008_v1/`.
The summary records January's separately completed input and batch checks after
the path validator was extended to recognize the institutional GDEX collection
root. Immediately after submission, `qstat -u fillmore` confirmed all twelve
case-run jobs in Derecho PBS state `Q`; no short-term archive jobs were enabled.

Run the reproducible setup with the project DAVINCI Python:

```bash
/glade/work/fillmore/miniforge3/envs/davinci/bin/python \
  scripts/setup_monthly_2008_cases.py --preflight
/glade/work/fillmore/miniforge3/envs/davinci/bin/python \
  scripts/setup_monthly_2008_cases.py --prepare
/glade/work/fillmore/miniforge3/envs/davinci/bin/python \
  scripts/submit_monthly_2008_cases.py --submit
```
