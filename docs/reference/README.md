# Reference analysis — prior MODIS/VIIRS AOD-nudging attempt

Analysis of the disorganized prior attempt at `/glade/work/tvmora` (author `tvmora`),
produced 2026-06-27 by a parallel multi-agent exploration to inform a clean-slate rewrite.
All paths were verified against the live filesystem.

**Start with [`SYNTHESIS.md`](SYNTHESIS.md)** — the consolidated picture. The `findings-*`
files are the raw per-subsystem reports behind it.

| File | What it covers |
|---|---|
| [`SYNTHESIS.md`](SYNTHESIS.md) | Unified analysis: pipeline, algorithm, data, CAM integration, why-it's-a-mess, carry-forward vs discard, 12 open questions |
| [`findings-01-nudging-algorithm.md`](findings-01-nudging-algorithm.md) | The nudging/forcing science: AOD_ratio scaling, hard-replacement vs (disabled) relaxation, masking, optics coupling |
| [`findings-02-cam-integration.md`](findings-02-cam-integration.md) | CAM integration & the engineering mess: variant sprawl, physpkg hooks, SourceMods deployment |
| [`findings-03-optics-mie.md`](findings-03-optics-mie.md) | Aerosol optics: Mie/LARC tables, Köhler water uptake, Chebyshev/`binterp` |
| [`findings-04-observation-data.md`](findings-04-observation-data.md) | MODIS/VIIRS obs: products, levels, f09 3-hourly archive, VIIRS original→corrected bias step |
| [`findings-05-build-run-cases.md`](findings-05-build-run-cases.md) | Build/run on derecho: compset `HIST_CAM60%CCTS1%NUDG`, `f09_f09_mg17`, run scripts, checkouts |
| [`findings-06-emissions-context.md`](findings-06-emissions-context.md) | QFED/FINN fire emissions — out of scope for the rewrite |
| [`coverage-gaps.md`](coverage-gaps.md) | What wasn't read; most important still-unread files |

See [`../HANDOFF.md`](../HANDOFF.md) for project status, the base-version decision, and next steps.

### Key verified facts
- **Base:** CESM2.2.2 (`release-cesm2.2.2`), CAM6 + MAM4 (27 species / 4 modes), compset `HIST_CAM60%CCTS1%NUDG`, resolution `f09_f09_mg17`, with simultaneous MERRA2 met-nudging, on derecho.
- **Behavior:** "nudging" is actually **hard replacement** of aerosol mass (`nudging_AODs.F90:1907` active; relaxation at `:1906` commented out). The "inversion" is a single per-column scalar `AOD_ratio = Target/Computed` applied uniformly to all species/levels.
- **Durable assets:** obs archive `/glade/work/tvmora/MODIS_VIIRS_AOD/` (2000–2025, f09, 3-hourly, 550 nm); Mie tables `/glade/work/tvmora/Mie_io/mam4_mode[1-4]_larc_c000000.v2.nc`.
- **Mess metrics:** ~123 nudging `.F90` variants, 264 test cases, 5 namelist XMLs, multiple CESM checkouts, no git, no tests.
