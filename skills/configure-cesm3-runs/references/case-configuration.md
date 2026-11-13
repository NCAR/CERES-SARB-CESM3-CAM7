# CIME Case Configuration

Use this reference when creating, cloning, modifying, or validating a CESM3 CIME case. Keep case
creation/configuration separate from build and model execution.

## Contents

- [Plan the lifecycle](#plan-the-lifecycle)
- [Inspect before modifying](#inspect-before-modifying)
- [Validate configuration](#validate-configuration)
- [Preserve a reproducible record](#preserve-a-reproducible-record)

## Plan the lifecycle

### Creation-time choices

Set structural choices in `create_newcase`:

```bash
"$CESM_ROOT/cime/scripts/create_newcase" \
  --case /absolute/path/to/case \
  --compset <verified-alias-or-long-name> \
  --res <verified-grid> \
  --machine <machine> \
  --compiler <compiler> \
  --mpilib <mpilib> \
  --project <account>
```

Add `--pecount`, `--user-mods-dirs`, `--output-root`, queue, or walltime only when the experiment
requires them. Add `--run-unsupported` only after disclosing and accepting unsupported status.
Use absolute case paths and abort on pre-existing directories.

Use `create_clone` for a scientifically compatible base case when preserving its configuration or
reusing its executable is intentional. Before `--keepexe`, prove that the source executable
matches the new SourceMods, component build settings, compiler/MPI, and grid. Never rebuild a
shared executable while a source or clone is queued or running.

### XML before setup

Use `xmlchange` for CIME-controlled settings. Typical groups include:

```bash
./xmlchange RUN_TYPE=startup,RUN_STARTDATE=YYYY-MM-DD
./xmlchange STOP_OPTION=ndays,STOP_N=N
./xmlchange REST_OPTION=ndays,REST_N=N
./xmlchange CONTINUE_RUN=FALSE,RESUBMIT=0
./xmlchange JOB_QUEUE=<queue>,JOB_WALLCLOCK_TIME=HH:MM:SS
```

Set initialization and reference-case fields consistently when using branch or hybrid starts.
Treat short-term archiving, history cadence, restart cadence, resubmission, and continuation as
independent choices. Do not copy dates or restart paths from a base case without verifying the
new run window.

Run `case.setup` after creation-time and setup-sensitive XML is resolved. Use
`case.setup --reset` only when required and only after inspecting what it will regenerate.

### Namelists and source changes

Put component runtime settings in `user_nl_<component>`. Inspect the component's namelist
definition and a generated `CaseDocs/*_in`; do not assume option names from another CESM/CAM
version. Use clearly delimited, idempotent blocks in automation so reconfiguration replaces a
block instead of appending duplicates.

Prefer a versioned `--user-mods-dirs` directory or repository setup script for reproducibility.
Keep experiment-specific code in versioned SourceMods or a project-maintained component fork, not
as unrecorded edits to the CESM checkout.

Changing build-time settings or SourceMods invalidates an old executable. Changing only runtime
namelist fields may not, but verify with CIME rather than assuming `--keepexe` is safe.

## Inspect before modifying

For an existing case:

```bash
cd /absolute/path/to/case
./xmlquery CASE,COMPSET,GRID,MACH,COMPILER,MPILIB,PROJECT,CHARGE_ACCOUNT
./xmlquery RUN_TYPE,RUN_STARTDATE,STOP_OPTION,STOP_N,REST_OPTION,REST_N
./xmlquery CONTINUE_RUN,RESUBMIT,JOB_QUEUE,JOB_WALLCLOCK_TIME
./xmlquery EXEROOT,RUNDIR,DOUT_S_ROOT,DIN_LOC_ROOT
./xmlquery --value CAM_CONFIG_OPTS
```

Some variables are component-specific or absent; query them separately if one missing variable
would abort a grouped query. Also inspect:

- `CaseStatus` and recent scheduler history;
- `README.case` and creation command/provenance;
- `user_nl_*`, SourceMods, and user-mods inputs;
- `env_case.xml`, `env_run.xml`, `env_build.xml`, and `env_mach_pes.xml` diffs;
- whether another case shares `EXEROOT`.

Do not mutate a case with an active job until the exact change and safety impact are resolved.

## Validate configuration

Run the applicable checks after setup:

```bash
./check_input_data
./preview_namelists
./preview_run
./case.submit --dry-run
```

Inspect rather than merely counting successful commands:

- `CaseDocs/*_in` contains intended forcing, physics, history, and restart settings;
- required input files cover the entire run window, including interpolation boundaries;
- component grids, vertical levels, coordinates, and calendars match external forcing;
- `preview_run` has the intended PE layout, queue, account, walltime, and executable;
- `EXEROOT`, `RUNDIR`, archive root, and case name are unique or intentionally shared;
- start type, reference case/date, restart cadence, continuation, and resubmission are coherent.

`case.setup`, `preview_namelists`, or `case.submit --dry-run` success does not establish that the
case is built, that input science is correct, or that a production run will complete.

## Preserve a reproducible record

Record:

- CESM source path, version/commit, and any component fork commits;
- requested compset alias plus resolved `COMPSET`;
- grid, machine, compiler, MPI, project/account, PE layout, queue, and walltime;
- case, executable, run, archive, input, and reference-case paths;
- run type/date/length, restart/archive/output settings, XML changes, and component namelists;
- user-mods/SourceMods provenance and configuration validation results.

When the repository has a run-history registry, store or link this evidence there. Do not call a
configuration a completed run; later scheduler, model-output, numeric, and scientific gates remain.
