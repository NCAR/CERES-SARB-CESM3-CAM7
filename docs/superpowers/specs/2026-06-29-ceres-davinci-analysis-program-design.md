# SPEC - CERES-SARB-CAM7 / DAVINCI Analysis Program

*Design spec, 2026-06-29. Status: **design finalized; pending user review -> `writing-plans`.** This spec captures the joint CERES-SARB-CAM7 and DAVINCI development program to replace project-specific diagnostic plot scripts with full DAVINCI analyses.*

## 1. Goal

Turn the current CERES-SARB-CAM7 diagnostic plotting workflow into full DAVINCI analyses. A "full DAVINCI analysis" means a YAML-driven DAVINCI run that:

1. loads source files,
2. maps configured variables into semantic roles,
3. evaluates configured derived-field formulas,
4. performs grouped reductions,
5. writes standardized analysis artifacts,
6. renders final PDF plots from those artifacts,
7. runs or supports visual inspection, and
8. records all outputs in a run manifest.

The user-facing interface is DAVINCI YAML. All executable analysis code lives in DAVINCI. CERES-SARB-CAM7 contains runnable analysis configs, project docs, and legacy scripts during migration.

## 2. Scope

In scope:

- A generic DAVINCI gridded analysis product layer that supports CAM AOD, MODIS/VIIRS AOD, and later SARB-band aerosol optics products.
- YAML-declared roles and formulas rather than hard-coded CERES analysis types.
- Grouped daily, monthly, seasonal, and custom-window reductions in one run.
- Standard self-contained run directories with NetCDF products, summary JSON, plot PDFs, manifest JSON, and inspection outputs.
- Built-in DAVINCI plot and visual-inspection presets for gridded AOD and SARB-band aerosol optics diagnostics.
- CERES-SARB-CAM7 configs under `analyses/davinci/`.
- A migration path that leaves existing project plot scripts and legacy plot directories in place until the DAVINCI analyses pass.
- Complete unit-test coverage for each new DAVINCI capability using synthetic data fixtures, so core behavior is testable without relying on derecho project files.
- A verification discipline where every implementation task ends by running the full applicable test suite and recording the result.

Out of scope for this design:

- Removing current CERES plot scripts immediately.
- Moving CAM/SP2/SP3 model-development code.
- Encoding CERES-specific variable names directly into DAVINCI analysis code.
- Allowing arbitrary Python execution in formulas.

## 3. Repository Boundary

DAVINCI owns:

- product/analysis execution code,
- constrained expression evaluation,
- grouped reductions,
- artifact writers,
- plot-suite presets,
- inspection engine and CLI,
- all tests for these code paths.

CERES-SARB-CAM7 owns:

- YAML analysis configs in `analyses/davinci/`,
- project documentation and run notes,
- data-path provenance,
- legacy scripts during transition.

New viewer-facing names should avoid `SP1`, `SP2`, and `SP3`. Those labels may remain only in lower-level data directories or provenance paths. Run directories, plot titles, manifests, and public docs should use descriptive names such as `cam-aod-analysis-july-2008`, `modis-viirs-aod-monthly-analysis-july-2008`, and `sarb-band-aerosol-optics-july-2008`.

## 4. Target Architecture

DAVINCI gains a product layer between source loading and plotting:

```text
source files
  -> role mapping
  -> formula fields
  -> grouped reductions
  -> persisted analysis products
  -> plots
  -> visual inspection
  -> manifest
```

The first implementation target is a generic `gridded_analysis` derived-analysis type. It consumes one source dataset, resolves role aliases from YAML, evaluates configured formulas, groups/reduces over time or other dimensions, and writes DAVINCI-ready products.

The existing DAVINCI `analyses:` block should be used if it can naturally express these products. A separate root key such as `products:` is acceptable only if the existing schema becomes unclear. The important contract is that product declarations are role/formula driven and produce persisted artifacts before plotting.

## 5. Run Directory Contract

Each analysis run writes a deterministic, self-contained run directory. The directory is the review and rerun unit.

Example:

```text
runs/cam-aod-analysis-july-2008/
  config.yaml
  products/
    daily/
      analysis.nc
      summary.json
    monthly/
      analysis.nc
      summary.json
  plots/
    daily/
      cam-analyzed-aod.pdf
      analysis-minus-observation-aod.pdf
      nudge-fraction.pdf
    monthly/
      ...
  inspection/
    previews/
      daily-cam-analyzed-aod.png
    inspection.json
    inspection.md
  manifest.json
```

Rules:

- `analysis.nc` is the canonical plot input. Plotting should not recompute derived fields from raw source files unless the product is being rebuilt.
- `summary.json` records finite counts, min/mean/max, percentiles, grouping windows, active masks, and product-specific notes.
- `manifest.json` records source inputs, config hash, DAVINCI version, product outputs, plot outputs, inspection outputs, and run status.
- Final plots are PDFs.
- PNGs are allowed only under `inspection/previews/` as temporary review aids. They are not final plot products.
- The run directory name is deterministic and descriptive, not timestamped.

## 6. YAML Analysis Model

CERES configs declare source variables, semantic roles, formulas, grouped products, plots, and inspection presets. DAVINCI supplies the execution engine.

Representative config shape:

```yaml
analysis:
  name: cam-aod-analysis-july-2008
  output_dir: /glade/work/fillmore/Data/CERES-SARB-CAM7/runs/cam-aod-analysis-july-2008
  domain: global

sources:
  cam:
    type: cesm_fv
    files: /path/to/*.cam.h0*.nc
    variables:
      AODNDG_OBS: {}
      AODNDG_MODEL_PRE: {}
      AODNDG_MODEL_POST: {}
      AODNDG_MASK: {}

analyses:
  daily_aod:
    type: gridded_analysis
    source: cam
    groupby: day
    roles:
      observation: AODNDG_OBS
      first_guess: AODNDG_MODEL_PRE
      analysis: AODNDG_MODEL_POST
      mask: AODNDG_MASK
    fields:
      observation_aod:
        formula: active_mean(observation, mask > 0.5, dim="time")
      first_guess_aod:
        formula: mean(first_guess, dim="time")
      analyzed_aod:
        formula: mean(analysis, dim="time")
      analysis_minus_observation_aod:
        formula: active_mean(analysis - observation, mask > 0.5, dim="time")
      analysis_increment_aod:
        formula: active_mean(analysis - first_guess, mask > 0.5, dim="time")
      nudge_fraction:
        formula: mean(mask, dim="time")
```

The exact schema may evolve during implementation, but these concepts are locked:

- roles are YAML-declared,
- derived fields are YAML formulas,
- one run can produce multiple grouped products,
- plots consume persisted product artifacts.

## 7. Formula Language

DAVINCI should implement a constrained expression language for formulas.

Allowed:

- role aliases and previously defined field aliases,
- numeric constants,
- arithmetic operators,
- comparisons,
- boolean mask expressions,
- whitelisted functions:
  - `mean`
  - `sum`
  - `count`
  - `fraction`
  - `weighted_mean`
  - `active_mean`
  - `where`
  - `percentile`
  - `robust_limits`
  - `symmetric_limits`

Not allowed:

- imports,
- file access,
- arbitrary Python calls,
- attribute access,
- mutation,
- access to globals outside the evaluator environment.

Formulas operate on xarray objects and must preserve metadata where possible. Errors must name the product, field, and formula that failed.

## 8. Grouping And Reductions

The first milestone must support full grouped reductions, not a special-case daily or monthly shortcut.

Required grouping modes:

- day,
- month,
- season,
- all,
- explicit custom windows.

Required reduction behavior:

- unweighted mean,
- count-weighted mean,
- active-cell masked mean,
- fraction/count reductions,
- percentiles for summaries and plotting limits,
- robust asymmetric and robust symmetric limits for plot metadata.

One product run may emit multiple groups, such as daily and monthly products, into separate product subdirectories.

## 9. AOD Plot Preset

DAVINCI should ship a built-in plot-suite preset for gridded AOD diagnostics. CERES configs select the preset and optionally override field selections or names.

Default AOD suite:

- observation AOD,
- CAM analyzed AOD,
- CAM first-guess AOD,
- analysis minus observation AOD,
- analysis increment AOD,
- nudge fraction or observation fraction,
- optional analysis minus free-running AOD when a `free_running` role exists,
- optional histograms/distribution plots.

Plot rules:

- absolute AOD maps use `style_preset: geosit_aod`,
- global domain by default,
- coastlines and solid latitude/longitude gridlines,
- no political borders unless explicitly configured,
- human-readable title case,
- no raw variable names in titles,
- no date appended to main titles.

## 10. SARB-Band Aerosol Optics Preset

After the AOD product layer is working, DAVINCI should add a SARB-band aerosol optics plot and inspection preset. This migrates the current VP-style SP3 diagnostics into full DAVINCI analyses without using `SP3` in viewer-facing names.

Default optics suite:

- visible-band column AOD map,
- visible single-scatter albedo map,
- visible asymmetry map,
- SW spectral profile at configured representative columns,
- vertical extinction profile,
- LW window scattering map,
- LW window extinction map,
- optional zero-LW-scattering comparison proof.

The product layer must support band-indexed products and representative-column extraction. The existing VP1-VP7 scripts and PDFs remain validation references during migration.

## 11. Visual Inspection

Visual inspection is part of the acceptance workflow.

DAVINCI should provide one inspection engine with two entry points:

- optional pipeline stage enabled in YAML,
- standalone CLI, for example `davinci inspect runs/cam-aod-analysis-july-2008`.

Inspection uses built-in DAVINCI presets selected by plot suite. CERES configs should not need to write full inspection prompts from scratch.

Inspection outputs:

- `inspection/inspection.json` for machine-readable results,
- `inspection/inspection.md` for human-readable review,
- `inspection/previews/*.png` for temporary visual-review images.

Pipeline behavior:

- when configured as required, inspection failure fails the run,
- when optional, failure is recorded but does not fail the run.

CLI behavior:

- exits zero on pass,
- exits nonzero on failure.

The existing DAVINCI AI image/summary provider and PNG encoding layer should be reused where possible, but inspection differs from summaries: it produces explicit pass/fail verdicts against built-in criteria.

## 12. Migration Waves

### Wave 1: Generic Gridded AOD Analysis

- Add DAVINCI product/artifact contract.
- Add constrained formula evaluator.
- Add grouped reductions and product writer.
- Add AOD plot suite and inspection preset.
- Add complete synthetic unit coverage for formula parsing, role resolution, grouping, reductions, product writing, plot manifest generation, and AOD plot-suite expansion before using real CERES data.
- Add CERES configs under `analyses/davinci/` for:
  - `modis-viirs-aod-monthly-analysis-july-2008`,
  - `cam-aod-analysis-july-2008`.
- Validate against current MODIS/monthly and CAM AOD scripts.
- After each implementation task, run the full DAVINCI test suite and the CERES config/unit tests that exercise the new config path. Record the exact command and result in the task notes before moving on.

### Wave 2: Run Directories And Inspection

- Add `manifest.json` with source/product/plot/inspection status.
- Add `davinci inspect <run-dir>`.
- Add required/optional inspection behavior in pipeline config.
- Add cleanup/retention behavior so non-final PNGs stay only under `inspection/previews/`.
- Update CERES documentation to point at run directories instead of the legacy plot tree.
- Add complete synthetic unit coverage for manifest updates, required vs optional inspection behavior, CLI exit codes, preview generation, and final-PDF retention rules.
- After each implementation task, rerun the full applicable DAVINCI and CERES test suites and verify the run directory contract remains intact.

### Wave 3: SARB-Band Aerosol Optics

- Extend product logic for band-indexed products.
- Add representative-column extraction.
- Add SARB optics plot-suite preset.
- Add optics-specific inspection preset.
- Add CERES config `sarb-band-aerosol-optics-july-2008`.
- Add complete synthetic unit coverage for band-indexed product assembly, band selection, representative-column extraction, spectral/profile plot inputs, and optics inspection preset expansion.
- Validate against the current VP1-VP7 scripts and PDFs.
- Keep legacy `SP3` labels only in data paths/provenance.
- After each implementation task, rerun the full applicable DAVINCI and CERES test suites and verify no existing AOD analysis behavior regresses.

## 13. Testing And Verification

DAVINCI tests:

- formula parser/evaluator unit tests for allowed and rejected expressions,
- grouped reduction tests for daily, monthly, seasonal, and custom windows,
- artifact writer tests for NetCDF, summary JSON, and manifest JSON,
- AOD plot-preset tests that verify the expected PDFs are generated from a synthetic product,
- inspection engine tests with stubbed AI/provider responses,
- CLI tests for `davinci inspect`,
- integration tests for one end-to-end gridded AOD run.
- complete synthetic fixture coverage for every new code path before the feature is validated on real CERES data.

CERES-SARB-CAM7 verification:

- run the new AOD configs against existing July 2008 data,
- compare product summaries against current script summaries,
- compare plot set completeness against current PDFs,
- run visual inspection and record verdicts,
- keep legacy scripts until the DAVINCI path passes artifact, plot, and inspection gates.
- after each development task, run the full applicable test suite, verify the outputs, and record the command/result before beginning the next task.
- final delivery is not complete until the existing five-day July 2008 verification products are regenerated through the new DAVINCI analysis path.

The five-day regeneration gate covers the current preserved AOD-nudged July 2008 diagnostic set: the five-day SARB-band aerosol-optics VP products and the expanded five-day AOD diagnostics. The regenerated deliverable must produce deterministic run directories, NetCDF products, summary JSON, manifests, final PDF plots, inspection previews under `inspection/previews/`, and passing inspection results. The old scripts remain as references, but the final accepted products must come from the new DAVINCI configs.

## 14. Development Task Gate

Every implementation plan derived from this spec must make each development task independently verifiable. A task is not complete until all of the following are true:

1. New behavior has synthetic unit tests that cover success, edge cases, and expected failures.
2. The task-specific tests pass.
3. The full applicable DAVINCI test suite passes.
4. The full applicable CERES-SARB-CAM7 test/config suite passes when the task touches CERES configs or compatibility.
5. Verification commands and results are recorded in the task notes or commit message.

If a full-suite run is impossible because of queue limits, missing external data, or infrastructure failure, the task notes must say exactly what could not run, why, and what narrower command was run instead. That exception does not satisfy the final deliverable gate; the full suite and five-day regeneration must still pass before the program is accepted.

## 15. Open Implementation Decisions

These are intentionally left for the implementation plan:

1. Whether the schema names the product block `analyses:` only or adds a clearer alias such as `products:`.
2. Exact manifest schema fields and versioning.
3. Exact expression-parser implementation: Python AST subset, custom parser, or existing safe-expression library.
4. Whether plot-suite presets are first implemented as pipeline expansions, renderer wrappers, or a dedicated plotting stage helper.
5. How inspection previews are generated from PDFs on derecho in a reliable noninteractive environment.

None of these change the approved architecture: generic DAVINCI code, CERES YAML configs, persisted artifacts, descriptive run directories, built-in plot/inspection presets, and a phased migration from existing scripts.
