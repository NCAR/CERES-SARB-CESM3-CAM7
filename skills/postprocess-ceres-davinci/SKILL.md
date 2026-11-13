---
name: postprocess-ceres-davinci
description: Post-process and record CERES-SARB-CAM7 observation, CAM AOD, and SARB-band aerosol-optics outputs through the complete DAVINCI YAML pipeline on Derecho PBS. Use when Codex must create or adapt an analysis under analyses/davinci, submit or resume a DAVINCI PBS job, regenerate plots, audit manifests and inspection, visually inspect previews, promote accepted PDFs, or update DAVINCI/science results in the versioned run_history registry.
---

# Post-process CERES with DAVINCI

Run the complete, reproducible CERES analysis path from source preflight through accepted PDF
products. Keep scientific choices in versioned project YAML. Submit the full DAVINCI pipeline
through PBS by default; keep login-node activity to lightweight validation, submission,
monitoring, and inspection.

## Help Mode

When explicitly invoked as `$postprocess-ceres-davinci help`,
`$postprocess-ceres-davinci --help`, or `$postprocess-ceres-davinci -h`, enter help mode. Help
takes precedence over the workflow. Do not use tools, load bundled references, inspect inputs or
PBS state, or change state. Return only the following brief bullets, then stop:

- Select or adapt a versioned DAVINCI analysis YAML for CERES inputs.
- Preflight source coverage and validate plotting-policy configuration.
- Submit, monitor, or resume complete DAVINCI pipelines through Derecho PBS.
- Audit manifests, products, PDFs, previews, and automated inspection results.
- Visually inspect science plots and promote accepted PDFs.
- Record DAVINCI and scientific evidence in the owning run-history record.

## Workflow

1. Resolve the CERES repository root and read its `AGENTS.md` completely. Treat its current
   plotting rules as authoritative.
2. Establish that the model or observation inputs are structurally complete. Use
   `$closeout-ceres-runs` for CESM cases when available.
3. Read [references/analysis-families.md](references/analysis-families.md). Select the closest
   existing YAML under `analyses/davinci/` and resolve the owning
   `run_history/records/<run_id>.yaml` when the source is a registered run.
4. For a new run, copy and minimally adapt that YAML. Change source paths, analysis window,
   output directory, audience-facing metadata, and only the scientifically required fields.
   Add or update focused assertions in `tests/test_davinci_analysis_configs.py`.
5. Run the read-only preflight:

   ```bash
   DAVINCI_PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
   "$DAVINCI_PY" skills/postprocess-ceres-davinci/scripts/preflight_analysis.py \
     analyses/davinci/<analysis>.yaml
   ```

   Pass `--allow-regional` only when the user explicitly requested a clipped domain.
6. Validate project policy and config parsing before the expensive run:

   ```bash
   "$DAVINCI_PY" -m pytest -q \
     tests/test_davinci_analysis_configs.py \
     tests/test_no_legacy_plot_renderers.py
   ```

7. Read [references/pbs-execution.md](references/pbs-execution.md), then submit DAVINCI's
   complete pipeline through PBS:

   ```bash
   "$DAVINCI_PY" skills/postprocess-ceres-davinci/scripts/submit_analysis_pbs.py \
     analyses/davinci/<analysis>.yaml
   ```

   Capture the returned PBS job ID. A queued or running job is not a completed pipeline. Do not
   replace PBS with `nohup`, a transient service, or a detached login-node process merely so a
   session can end.
8. Monitor PBS without holding the session open. On the same or a later session, confirm a zero
   PBS exit status and a clean DAVINCI log before auditing the completed run:

   ```bash
   qstat <job_id>
   qstat -xf <job_id>
   "$DAVINCI_PY" skills/postprocess-ceres-davinci/scripts/audit_analysis_output.py \
     /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/<analysis>
   ```

9. Inspect the generated previews visually against the applicable checklist in
   `docs/science-verification.md`. A passing machine inspection is necessary but not sufficient
   for scientific acceptance.
10. Promote the intended PDF subset only after numeric and visual checks pass. Keep accepted
    plots below `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/`. Remove stale final PNG
    replacements only after resolving their exact scope.
11. Update the owning run-history record unless the request is explicitly read-only:
    - Add the DAVINCI run and accepted-plot paths under `outputs`.
    - Record YAML, manifest status, product/PDF counts, automated inspection, and artifact paths
      under `validation.davinci`.
    - Record visual checklist evidence separately under `validation.science`.
    - Advance `status.stage` only when earlier applicable structural and numeric gates pass.
    - Validate and regenerate `run_history/index.md` with `scripts/run_history.py`.
12. Report the YAML, input coverage, output directory, product/PDF counts, manifest status,
    inspection result, visual result, and promoted paths. Distinguish pipeline completion from
    scientific acceptance and link the updated run-history record.

## Guardrails

- Preserve the August boundary record in source inventories but exclude it from July
  daily/monthly grouping by ending the analysis at July 31 23:59:59.
- Use daily means for daily CAM diagnostics. Compute observation means only over active cells
  and render masks as nudge fractions.
- Use CAM analysis terminology: POST is analyzed AOD, PRE is first-guess AOD, and POST-PRE is
  the analysis increment. Never label PRE as an unnudged control.
- Keep run identifiers, implementation labels, raw variable names, and dates out of main titles.
- Do not claim acceptance from file counts, `manifest.status`, or automated inspection alone.
- Submit complete DAVINCI `run` commands through PBS by default. Direct login-node execution is
  limited to an explicitly requested, demonstrably short smoke run; preflight, tests, audits,
  and metadata inspection may run on the login node.
- Do not submit CESM/model jobs as part of this skill. A DAVINCI post-processing PBS job is
  allowed and expected. Do not overwrite unrelated products.
- Do not create a second history record for post-processing the same run. Update the owning
  record and leave legacy `RUN.md` prose unchanged unless requested.
- Do not update the registry during a read-only DAVINCI inspection request.

## Bundled Resources

- `scripts/preflight_analysis.py`: validate YAML location, policy, source glob coverage, and
  output placement before a DAVINCI run.
- `scripts/submit_analysis_pbs.py`: submit the full YAML-driven DAVINCI run to Derecho PBS with
  project defaults and print its durable job ID.
- `scripts/audit_analysis_output.py`: summarize and validate manifest, products, PDFs, previews,
  and inspection state after a run.
- `references/analysis-families.md`: route requests to the closest project analysis family and
  define the post-processing acceptance boundary and run-history handoff.
- `references/pbs-execution.md`: define PBS defaults, submission, monitoring, resumption, and
  completion evidence for DAVINCI runs.
- Project `scripts/run_history.py`: validate records and regenerate the run-history index.
