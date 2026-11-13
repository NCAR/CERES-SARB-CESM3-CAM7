# CERES Run Status Gates

Use this reference while choosing expectations, running numeric verifiers, or assigning a
completion stage. Do not use a later stage unless every earlier relevant stage has evidence.

## Completion stages

| Stage | Minimum evidence |
| --- | --- |
| `prepared` | Case exists and configuration/setup evidence is present. |
| `queued` | PBS job ID exists and the job is queued/held, or submission succeeded without later evidence. |
| `running` | PBS or `CaseStatus` shows active model execution. |
| `model-complete` | PBS exit is zero when history is available, plus `model execution success` and `case.run success`. |
| `structurally-complete` | Model-complete plus expected history records, variables, timestamps, SP3 bands, and boundary coverage. |
| `numeric-gates-passed` | Applicable project verifier(s) pass on the completed outputs. |
| `davinci-inspection-passed` | The complete DAVINCI YAML run, manifest, PDFs, and automated inspection pass. |
| `scientifically-accepted` | Numeric gates and DAVINCI inspection pass, and visual physics checks are accepted. |

PBS exit zero alone is `model-complete` at most. A DAVINCI manifest marked `completed` is
`davinci-inspection-passed` only when its inspection record and artifacts also pass.

## Case families and structural expectations

### SP2 or ERA5+MODIS AOD-nudged CAM

- Require CAM `h0i` coverage at the requested cadence.
- Require `AODNDG_MASK`, `AODNDG_OBS`, `AODNDG_MODEL_PRE`, and
  `AODNDG_MODEL_POST`.
- Treat `AODNDG_MODEL_POST` as analyzed AOD, `AODNDG_MODEL_PRE` as cycling first guess, and
  POST-PRE as the analysis increment.
- Check `AODVIS` and requested radiative fields on their configured history streams.

For the established 31-day July 2008 cases, expect 248 three-hourly `h0i` records ending at
`2008-08-01 00:00:00`. Derive expectations from configuration for other periods.

Run the SP2 last-record numeric check:

```bash
/glade/work/fillmore/miniforge3/envs/davinci/bin/python \
  sp2_tests/check_integration.py --h0 <nudged-h0i-file>
```

### Free-running CAM reference

- Require the matching requested `AODVIS` and radiation history.
- Require no `AODNDG_*` variables when AOD nudging is disabled.
- Do not use the free run interchangeably with PRE; compare it as a separate model trajectory.

### SP3 per-band aerosol optics

- Require all 14 SW and 12 LW bands at every configured timestamp.
- Require continuous three-hourly timestamps unless the case configured another interval.
- For the full July 2008 run including initial and boundary states, expect 249 groups from
  `20080701.00000` through `20080801.00000`: 6,474 files total.
- Require per-file schema and physical invariants: finite fields, nonnegative extinction and
  scattering, scattering no greater than extinction, asymmetry within [-1, 1], and column
  extinction equal to the layer sum.

Use `sp3_tests.check_sp3_outputs.summarize_directory` for completeness and
`check_physical_invariants` for the full invariant scan. The invariant scan reads every field
and may be expensive for a full month; report whether it was actually run.

For paired ten-day LUT verification, use:

```bash
/glade/work/fillmore/miniforge3/envs/davinci/bin/python \
  sp3_tests/verify_sp3_t10.py \
  --lut-on-dir <on-optics> \
  --lut-off-dir <off-optics> \
  --on-run <on-run> \
  --off-run <off-run> \
  --outdir <numeric-output>
```

For AOD-nudged versus free SP3 diagnostics, use
`sp3_tests/verify_sp3v2_aod_nudged.py` with explicit nudged/free directories, h0 inputs,
expected method, timestamps, and an output directory under the project data tree.

## DAVINCI and visual gates

Use `$postprocess-ceres-davinci` for all project plots. Read `docs/science-verification.md` for
the applicable physical checklist. Keep these outcomes separate:

1. DAVINCI execution completed.
2. Manifest and automated inspection passed.
3. Preview plots passed visual inspection.
4. Requested PDFs were promoted to the accepted project plots directory.

## Status investigation order

1. Inspect `git status`, recent `RUN.md` entries, and live `qstat`.
2. Resolve the exact case and latest job ID from `CaseStatus`.
3. Query historical PBS state with `qstat -xf`.
4. Check model/component logs and restart endpoints.
5. Inventory history and optics outputs with explicit expectations.
6. Run the applicable numeric verifier.
7. Audit DAVINCI outputs and visual acceptance.
8. Compare the evidence with `RUN.md` and report stale records.

Status and diagnosis requests are read-only. Do not repair, resubmit, delete, or update
documentation unless the user separately asks for those changes.

## Run-history mapping

Read `docs/run-history.md` before creating or updating a record. Map closeout evidence as follows:

- CIME case identity and scientific intent -> `case_name`, `purpose`, `simulation`
- compset, grid, chemistry/aerosol, executable, enabled features -> `configuration`
- PBS job ID, queue, requested/used resources, timestamps, exit -> `scheduler`
- highest contiguous gate and model result -> `status`
- case/run/optics/history locations -> `outputs`
- inventory/timestamp/variable checks -> `validation.structural`
- full-field and paired verifier results -> `validation.numeric`
- concise scientific or operational findings -> `results`
- `CaseStatus`, `qstat`, logs, manifests, and verifier artifacts -> `provenance.sources`

Use one file per attempt at `run_history/records/<run_id>.yaml`. For later evidence on the same
attempt, update that file rather than creating a second record. Advance `status.stage` only when
all earlier applicable stages have evidence. A passing DAVINCI result does not skip a blocked
numeric stage.
