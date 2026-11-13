# DAVINCI PBS Execution

Use this reference for every complete `davinci ... run` pipeline on Derecho. Preflight, focused
tests, output audits, and metadata inspection are lightweight login-node work; rendering and
other complete pipeline execution go through PBS by default.

## Project defaults

- Account: `P19010000`
- Submission queue: `develop` (routes to the shared `cpudev` execution queue)
- Resources: one chunk, 4 CPUs, 32 GB memory
- Walltime: 4 hours
- DAVINCI Python: `/glade/work/fillmore/miniforge3/envs/davinci/bin/python`
- Import order:
  `/glade/work/fillmore/DAVINCI:/glade/work/fillmore/CERES-SARB-CAM7`
- Combined PBS/DAVINCI log: `<analysis.output_dir>/davinci-pbs.log`

These are conservative post-processing defaults, not scientific settings. The shared `develop`
queue avoids allocating and charging an exclusive 128-core Derecho node for a serial or lightly
parallel DAVINCI YAML. Override CPUs, memory, or walltime when evidence from a comparable
analysis requires it. Use `--queue main` only when the workflow genuinely needs an exclusive
node, and then size the CPU request according to current Derecho guidance.

## Submit

Run the preflight and project tests first. Then submit from the repository root:

```bash
DAVINCI_PY=/glade/work/fillmore/miniforge3/envs/davinci/bin/python
"$DAVINCI_PY" skills/postprocess-ceres-davinci/scripts/submit_analysis_pbs.py \
  analyses/davinci/<analysis>.yaml
```

The helper validates that the YAML is a project analysis, reads `analysis.output_dir`, creates
the log directory, and submits this exact executable shape:

```bash
/glade/work/fillmore/miniforge3/envs/davinci/bin/python \
  -m davinci_monet.cli.app run /absolute/path/to/analysis.yaml
```

It prints the durable PBS job ID to standard output. Record that ID in the working notes or
run-history validation details when it is relevant to the audit trail. Use `--dry-run` to inspect
the fully quoted `qsub` command without creating directories or submitting a job. Use
`--walltime`, `--ncpus`, or `--memory` only when the default is inappropriate. Use `--queue main`
only for an explicitly justified exclusive-node run.

Submitting successfully proves only that PBS accepted the request. It does not prove that
DAVINCI ran or produced valid results.

## Monitor and resume

The PBS job survives logout and session termination. Do not keep an agent session open merely
to poll it. Check status in the current or a later session:

```bash
qstat <job_id>
qstat -f <job_id>
```

After the job leaves the active queue, query PBS history:

```bash
qstat -xf <job_id>
```

If PBS on the current host rejects the server-qualified form, retry with the numeric portion
before the first dot. Inspect `job_state`, `Exit_status`, resources used, and the combined
`davinci-pbs.log`. A zero PBS exit status is required but not sufficient: continue with the
skill's manifest, artifact, automated-inspection, and visual gates.

If the job is queued or running when the user wants to end the session, report the job ID, YAML,
output directory, and log path, then end the session safely. On resume, inspect PBS history and
the existing output directory before deciding whether to resubmit. Never create a duplicate job
solely because the original is no longer visible in the active `qstat` listing.

## Failure and cancellation

- Do not silently rerun after a nonzero exit. Read PBS history and the DAVINCI log, preserve the
  failed evidence, and diagnose whether the failure is configuration, data, resource, or code
  related.
- Do not treat a missing log while a job is queued as a failure; PBS may not create it until
  execution begins.
- Cancel with `qdel` only when the user requests cancellation or continued execution is clearly
  unsafe or destructive. Report the exact cancelled job ID.
- Do not move a complete pipeline to `nohup`, `systemd-run`, `screen`, `tmux`, or another
  login-node background mechanism as a substitute for PBS.
