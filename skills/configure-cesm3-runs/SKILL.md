---
name: configure-cesm3-runs
description: Choose and validate CESM3 component sets and grids, audit a live CESM checkout and its component provenance, then create, clone, or configure CIME cases reproducibly. Use when Codex must translate an experiment into a compset, compare compset aliases and long names, determine support status, choose a model grid or machine/compiler/MPI combination, construct create_newcase or create_clone commands, apply XML and user_nl settings, configure run/restart/output behavior, inspect an existing case, refresh a versioned checkout reference, or validate a case before build and submission.
---

# Configure CESM3 Runs

Choose from the metadata in the installed CESM checkout, not from remembered aliases. Produce a
reproducible case configuration and verify its resolved CIME state. Treat build, submission, and
scientific validation as later, separately authorized stages.

## Help Mode

When explicitly invoked as `$configure-cesm3-runs help`, `$configure-cesm3-runs --help`, or
`$configure-cesm3-runs -h`, enter help mode. Help takes precedence over the workflow. Do not use
tools, load bundled references, inspect CESM cases, or change state. Return only the following
brief bullets, then stop:

- Translate an experiment into explicit CESM component and forcing requirements.
- Compare live compset aliases, long names, physics, and support declarations.
- Audit CESM and component revisions, local overlays, and checkout-reference drift.
- Choose compatible grids, machines, compilers, MPI libraries, and resource settings.
- Plan or configure reproducible `create_newcase` and `create_clone` workflows.
- Apply and validate CIME XML, `user_nl_*`, user-mods, SourceMods, and restart settings.
- Preserve configuration provenance while keeping build and submission separately authorized.

## Workflow

1. Read the active repository `AGENTS.md` and relevant project run/build documentation. Discover
   the intended CESM root, case root, machine, project/account, and existing run registry. Do not
   assume this repository's Derecho paths apply elsewhere. Read
   [references/checkout-provenance.md](references/checkout-provenance.md). If the repository
   provides a generated CESM checkout reference and updater, run its check mode before relying on
   the reference. Use live checkout queries when the reference is absent or stale.
2. Translate the experiment into explicit requirements:
   - coupled versus prescribed/data components;
   - forcing period and transient versus climatological behavior;
   - atmosphere, chemistry/aerosol, land, ocean/ice, runoff, and optional components;
   - grid, run start/type/length, restart cadence, output needs, and forcing datasets;
   - machine, compiler, MPI library, task layout, project, queue, and walltime;
   - source modifications, user mods, initialization/reference case, and branch/revision.
3. Read [references/compset-selection.md](references/compset-selection.md). Query the exact
   checkout:

   ```bash
   python skills/configure-cesm3-runs/scripts/query_compsets.py \
     --cesm-root /path/to/cesm --component cam --match 'CAM70'
   /path/to/cesm/cime/scripts/query_config --grids
   /path/to/cesm/cime/scripts/query_config --machines <machine> --long
   ```

4. Compare a short candidate set using exact alias, expanded long name, component/physics
   implications, forcing period, declared support grid, and unresolved assumptions. Recommend one
   candidate and explain the decisive tradeoff. If materially different candidates remain, obtain
   the user's scientific choice before creating a case.
5. Write a case plan before mutation. Include the CESM root and revision, case path/name, compset
   alias and long name, grid, machine/compiler/MPI/project, support status, `create_newcase` or
   `create_clone` command, XML changes, `user_nl_*` changes, user-mods/SourceMods, input data,
   validation commands, and whether build/submission are excluded.
6. For case creation or modification, read
   [references/case-configuration.md](references/case-configuration.md). Resolve exact existing
   paths and scheduler state first. Reject an existing case by default; reuse or reset one only
   when the user explicitly selected that case and the change is safe.
7. Create or clone the case only when the request includes configuration, not when it asks only
   for advice. Do not add `--run-unsupported` silently. Use it only after reporting the missing
   support declaration and receiving or already having authorization to create an unsupported
   case.
8. Apply settings in CIME lifecycle order:
   - creation-time options in `create_newcase`/`create_clone`;
   - case XML with `xmlchange`;
   - `case.setup`;
   - component namelists in `user_nl_*` and versioned SourceMods/user-mods;
   - `case.setup --reset` only when a setup-sensitive change requires it.
9. Validate the resolved case in proportion to the request:

   ```bash
   ./xmlquery <relevant-variable-list>
   ./check_input_data
   ./preview_namelists
   ./preview_run
   ./case.submit --dry-run
   ```

   Inspect generated `CaseDocs/*_in`, PE layout, executable/run/archive paths, input coverage,
   restart settings, queue/account, and walltime. A configured case is neither built nor runnable
   until the applicable later gates pass.
10. Preserve provenance in the repository's setup script, user-mods directory, or run-history
    record when one exists. Record the requested alias as well as CIME's resolved `COMPSET`, since
    an existing case may retain only the expanded long name.
11. Report the selection rationale, exact commands or changes, validation evidence, case path,
    support status, and the next unperformed stage. Hand actual run monitoring and closeout to the
    repository's run-history workflow when available.

## Guardrails

- Never infer component versions or physics from an alias prefix alone; inspect its long name.
- Never let a generated checkout reference override the live checkout, CIME metadata, or generated
  case state. Regenerate and review it after a CESM/component/overlay change when that maintenance
  is in scope.
- Never equate `HIST`, `2000`, or `1850` with a requested start date without checking forcing and
  initialization semantics.
- Treat chemistry, aerosol mode, dynamics, nudging, and prescribed-component behavior as separate
  decisions even when one compset encodes several of them.
- Do not overwrite an existing case, shared `EXEROOT`, restart, or output directory. Check active
  jobs before resetting, rebuilding, or modifying a case that shares an executable.
- Do not edit the upstream CESM source tree for an experiment-specific configuration. Prefer
  versioned user-mods, SourceMods, or project setup scripts.
- Do not run `case.build`, `case.submit`, or `cesm.exe` unless the user explicitly includes that
  stage. Submit model executions through CIME, never by invoking `cesm.exe` directly.

## Bundled Resources

- `scripts/query_compsets.py`: filter live CIME compset metadata and expose exact long names and
  declared science/test support.
- `references/compset-selection.md`: reason from experiment intent to candidate component sets and
  grids.
- `references/case-configuration.md`: apply and verify CIME settings in the correct lifecycle
  order.
- `references/checkout-provenance.md`: audit root/component revisions and local overlays, use a
  generated checkout reference safely, and refresh it after checkout changes.
