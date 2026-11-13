# CERES DAVINCI Analysis Families

Use this reference only while selecting or adapting an analysis, running DAVINCI, or deciding
whether its products are acceptable. Read the repository `AGENTS.md` for current plotting policy.

## Environment and execution boundary

- Repository: `/glade/work/fillmore/CERES-SARB-CAM7`
- DAVINCI checkout: `/glade/work/fillmore/DAVINCI`
- Python: `/glade/work/fillmore/miniforge3/envs/davinci/bin/python`
- Project YAML: `analyses/davinci/*.yaml`
- Generated runs: `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/`
- Accepted plots: `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/`

Set `PYTHONPATH` with the DAVINCI checkout before the project repository so imports resolve to
the real DAVINCI package. Render only with `python -m davinci_monet.cli.app run <yaml>`, submitted
through PBS as described in [pbs-execution.md](pbs-execution.md).

## Choosing a starting YAML

| Need | Start from |
| --- | --- |
| Monthly gridded observation AOD | `modis-viirs-aod-monthly-analysis-july-2008.yaml` |
| CAM AOD daily diagnostics | `cam-aod-analysis-july-2008.yaml` |
| CAM AOD daily plus monthly diagnostics | `cam-aod-monthly-analysis-july-2008.yaml` |
| ERA5-constrained CAM AOD daily plus monthly diagnostics | `cam-aod-era5-modis-monthly-analysis-july-2008.yaml` |
| AOD-nudged multi-band aerosol optics | `modis-aod-nudging-band-optics-july-2008.yaml` |
| SARB aerosol-optics method verification | `sarb-band-aerosol-optics-july-2008.yaml` |
| One-day sampled dense-band maps | `sp3-dense3-aodnudged-retry1-daily-band-maps-20080701.yaml` |

Derive a new YAML when the source case, time extent, product meaning, or accepted output
directory changes. Do not silently repoint a preserved analysis record.

## Analysis semantics

- Treat `AODNDG_MODEL_POST` as analyzed AOD and the primary CAM AOD.
- Treat `AODNDG_MODEL_PRE` as the cycling first guess immediately before the current update.
  Prior increments persist in it; it is not an unnudged control.
- Treat POST-PRE as the analysis increment.
- Compute observation-derived means only where the nudge mask is active.
- Compute mask products as the fraction of active records.
- For July monthly products, end at `2008-07-31T23:59:59`; retain but do not group the
  `2008-08-01T00:00:00` boundary record.
- Apply `geosit_aod` only to AOD magnitudes. Use robust symmetric limits for signed differences.
- Keep implementation provenance in filenames, manifests, or meaningful subtitles rather than
  audience-facing main titles.

## Acceptance boundary

The analysis pipeline is complete only when:

1. Source coverage and variables pass preflight.
2. The committed YAML parses and focused project tests pass.
3. DAVINCI exits successfully.
4. `manifest.json` reports `completed`, with no failed stages or errors.
5. Product NetCDFs, summary artifacts, and final PDFs exist.
6. `inspection/inspection.json` passes and preview coverage matches final PDF coverage.
7. Preview images pass visual inspection against `docs/science-verification.md`.
8. The intended accepted PDF subset is present under the project data tree.

Do not call the result scientifically accepted at step 3, 4, or 6 alone. Record numeric,
automated-inspection, and visual outcomes separately.

## Run-history handoff

For a registered CESM source, update its existing `run_history/records/<run_id>.yaml` after
post-processing:

- `outputs.davinci_run_dir`: deterministic DAVINCI output directory
- `outputs.accepted_plots`: promoted PDF directory, when promotion occurred
- `validation.davinci.status`: `passed`, `failed`, `blocked`, or `pending`
- `validation.davinci.config`: project YAML path
- `validation.davinci.checked_at`: inspection date
- `validation.davinci`: product/PDF counts, manifest status, inspection result, and relevant
  artifact paths
- `validation.science`: separate visual checklist result and evidence

Do not advance `status.stage` past a failed or blocked earlier gate. Run
`scripts/run_history.py validate`, `render`, and `render --check` after the edit.
