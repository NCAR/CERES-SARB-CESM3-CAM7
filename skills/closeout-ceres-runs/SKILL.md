---
name: closeout-ceres-runs
description: Audit, close out, and record CERES-SARB-CAM7 CESM/CAM runs on Derecho using the versioned run_history registry, scheduler history, CIME CaseStatus, model logs, NetCDF records, SP2 AOD diagnostics, SP3 completeness, numeric verifiers, DAVINCI results, and scientific gates. Use for run-status questions, monitoring completed or failed jobs, validating outputs, maintaining run-history records, distinguishing attempts, or deciding the highest evidence-backed completion stage.
---

# Close Out CERES Runs

Determine what happened to a run and how far it has progressed through operational, structural,
numeric, and scientific gates. Default to read-only investigation.

## Help Mode

When explicitly invoked as `$closeout-ceres-runs help`, `$closeout-ceres-runs --help`, or
`$closeout-ceres-runs -h`, enter help mode. Help takes precedence over the workflow. Do not use
tools, load bundled references, inspect repository or scheduler state, or change state. Return
only the following brief bullets, then stop:

- Check whether a CESM/CAM run is prepared, queued, running, completed, or failed.
- Reconcile PBS history, CIME status, logs, output records, and preserved attempts.
- Validate history coverage, required variables, SP2 AOD diagnostics, and SP3 completeness.
- Run or interpret existing numeric verifiers and scientific completion gates.
- Create or update canonical run-history records and regenerate their index.
- Report the highest evidence-backed stage, remaining gates, and stale documentation.

## Workflow

1. Resolve the CERES repository root, confirm the active branch, and read `AGENTS.md`.
2. Identify the intended case before inspecting it:
   - Search `run_history/index.md` and `run_history/records/*.yaml` first.
   - Search the newest entries and uncommitted changes in `RUN.md` for legacy or not-yet-recorded
     attempts.
   - Query `qstat -u "$USER"` for live jobs.
   - Compare case names, purposes, and dates; do not substitute an older preserved run merely
     because it has better documentation.
3. Read [references/status-gates.md](references/status-gates.md) and select the applicable case
   family and expectations.
4. Run the bundled read-only summary with explicit expectations. Example:

   ```bash
   DAVINCI_PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
   "$DAVINCI_PY" skills/closeout-ceres-runs/scripts/summarize_ceres_case.py \
     /glade/work/fillmore/CESM3/cases/<case> \
     --inspect-netcdf \
     --expected-h0i-records 248 \
     --require-h0i-variable AODNDG_MASK \
     --require-h0i-variable AODNDG_MODEL_PRE \
     --require-h0i-variable AODNDG_MODEL_POST \
     --require-h0i-variable AODNDG_OBS \
     --expected-optics-groups 249 \
     --expected-first-stamp 20080701.00000 \
     --expected-last-stamp 20080801.00000
   ```

   Omit optics expectations for cases with `aod_optics_on=.false.`. Supply expectations for the
   requested period rather than assuming July 2008.
5. Inspect failures at their owning layer:
   - PBS: `qstat -xf <job-id>`.
   - CIME: `CaseStatus`, case stdout/stderr, and timing files.
   - Model: compressed component and CESM logs in the run directory.
   - Structure: history dimensions/variables and SP3 timestamp-band groups.
6. Run the existing case-specific numeric verifier from the reference. Do not replace a
   full-field invariant scan or paired comparison with the summary script.
7. If plots or scientific sign-off are in scope, use `$postprocess-ceres-davinci`; inspect its
   manifest, previews, and the relevant physical checklist.
8. Assign only the highest stage whose evidence is complete:

   ```text
   prepared -> queued -> running -> model-complete -> structurally-complete
   -> numeric-gates-passed -> davinci-inspection-passed -> scientifically-accepted
   ```

9. Report exact evidence: case and job IDs, scheduler state/exit, completion time, walltime and
   memory when available, history coverage, variables, optics groups, validator outcomes,
   DAVINCI outcome, remaining gates, and stale ledger entries.
10. When the user asks to record, organize, or close out the run, create or update its canonical
    YAML under `run_history/records/` using `docs/run-history.md`:
    - Keep one record per attempt and preserve failed/superseded attempts.
    - Record evidence sources and use `pending`, `blocked`, or `not-recorded` rather than guessing.
    - Update operational, structural, and numeric fields. Leave DAVINCI/science fields for
      `$postprocess-ceres-davinci` unless their evidence already exists.
    - Validate and regenerate the index:

      ```bash
      "$DAVINCI_PY" scripts/run_history.py validate
      "$DAVINCI_PY" scripts/run_history.py render
      "$DAVINCI_PY" scripts/run_history.py render --check
      ```

    - Include the record and generated index in the same change.

## Guardrails

- Treat `qstat -u` being empty as “no live jobs,” not proof that no historical job ran.
- Treat PBS exit 0 and `case.run success` as model completion, not scientific acceptance.
- Require expected record/group counts and endpoints before calling outputs structurally complete.
- Distinguish a free reference from the cycling first guess; PRE is not an unnudged control.
- Do not submit, resubmit, cancel, rebuild, delete, promote plots, or edit run ledgers while
  answering a status or diagnostic request. Update the structured ledger only when the user asks
  to record/organize history or when run closeout is part of an authorized change workflow.
- Do not create duplicate records for later validation of the same attempt. Update the existing
  `run_id` file.
- Preserve unrelated dirty-worktree changes. Report stale documentation rather than silently
  rewriting it unless the user asks for documentation updates.

## Bundled Resources

- `scripts/summarize_ceres_case.py`: gather PBS, CIME, history-file, and SP3 inventory evidence
  into a machine-readable summary.
- `references/status-gates.md`: define completion stages, case-family expectations, and existing
  project verifiers, including their run-history mapping.
- Project `scripts/run_history.py`: validate records and render the checked-in index.
