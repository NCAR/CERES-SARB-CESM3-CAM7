# Run History

The canonical structured run ledger lives under `run_history/records/`. Keep one YAML file per
run attempt and regenerate `run_history/index.md` after every change.

## Record identity

Use a stable `run_id` and matching filename:

```text
<case-name>--<execution-date>.yaml
```

Use `YYYYMMDD` for the execution date. If a case has multiple attempts on the same date, append
an attempt identifier such as `--retry1` or `--pbs-6889504`. Update an existing record when new
validation or post-processing evidence arrives; do not create a second record for the same
attempt.

## Evidence rules

- Record observed values from CIME, PBS, NetCDF inventories, validator outputs, DAVINCI
  manifests, and inspection records.
- Use `pending`, `blocked`, or `not-recorded` rather than inferring a result.
- Keep `status.stage` at the highest contiguous evidence-backed stage defined by
  `closeout-ceres-runs`.
- Store absolute paths for external case, run, optics, analysis, and accepted-plot locations.
- Store paths and summaries only. Do not commit model output, plots, logs, or other large
  artifacts into this repository.
- Record a failed or superseded attempt instead of deleting it.
- Treat the narrative table in `RUN.md` as legacy context. The structured ledger is the
  canonical source for new run-status facts.

## Validation categories

Every record carries separate `structural`, `numeric`, `davinci`, and `science` validation
objects. Each category has a controlled status:

```text
pending, passed, failed, blocked, not-applicable, not-recorded
```

Do not collapse automated DAVINCI inspection and visual scientific acceptance into one result.

## Commands

Use the DAVINCI environment because the registry is YAML:

```bash
PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
"$PY" scripts/run_history.py validate
"$PY" scripts/run_history.py render
"$PY" scripts/run_history.py render --check
```

`render` validates all records before rewriting the deterministic Markdown index. Commit record,
schema, generated-index, skill, and test changes together.
