# CESM3 Compset Selection

Use this reference while selecting a compset or grid. Treat the installed checkout as
authoritative because aliases, component versions, physics modifiers, and support declarations
change across CESM releases.

## Contents

- [Start from the experiment](#start-from-the-experiment)
- [Query the checkout](#query-the-checkout)
- [Read the long name](#read-the-long-name)
- [Interpret support accurately](#interpret-support-accurately)
- [Choose the grid separately](#choose-the-grid-separately)
- [CESM3 beta08 project baseline](#cesm3-beta08-project-baseline)

## Start from the experiment

Resolve these choices before recommending a compset:

1. Which components must be prognostic, data-driven, prescribed, stubbed, or inactive?
2. Is the experiment preindustrial, present-day climatological, historical transient, future
   scenario, idealized, or aquaplanet?
3. Which atmosphere generation, dynamics, chemistry, aerosol representation, and vertical grid
   are scientifically required?
4. Which land mode, ocean/ice boundary data or active ocean, runoff, glacier, and wave behavior
   are required?
5. Does the experiment need meteorological nudging, specified dynamics, data assimilation, or
   external forcings? These may be namelist/user-mod settings rather than compset identity.
6. Which horizontal grids have compatible initial conditions, boundary datasets, mapping files,
   and declared support?

Do not resolve missing scientific requirements by choosing the most familiar alias.

## Query the checkout

Use CIME's own metadata:

```bash
CESM_ROOT=/path/to/cesm

"$CESM_ROOT/cime/scripts/query_config" --compsets allactive
"$CESM_ROOT/cime/scripts/query_config" --compsets cam --long
"$CESM_ROOT/cime/scripts/query_config" --components cam --long
"$CESM_ROOT/cime/scripts/query_config" --grids
"$CESM_ROOT/cime/scripts/query_config" --machines <machine> --long
```

Filter the large compset catalog without copying it into project documentation:

```bash
python skills/configure-cesm3-runs/scripts/query_compsets.py \
  --cesm-root "$CESM_ROOT" --component cam --match 'CAM70' --match 'HIST|2000'

python skills/configure-cesm3-runs/scripts/query_compsets.py \
  --cesm-root "$CESM_ROOT" --component cam --alias F2000dev
```

Repeated `--match` expressions are conjunctive: every expression must match the alias, long name,
or support text. Query the full alias immediately before case creation even if a prior run used it.

## Read the long name

CIME long names enumerate the time/forcing mode and component stack, with component-specific
physics following `%`. The checkout's `<help>` text returned by `query_config --compsets ... --xml`
defines the exact token order.

Use the long name to answer:

- Does the atmosphere token name the intended CAM generation and physics?
- Is land active, prescribed, or a stub, and does its mode match the experiment?
- Are ice and ocean active or prescribed/data components?
- Are runoff, glacier, and wave components scientifically appropriate?
- Do suffix/options add an ensemble, coupling, or other mode?

Do not decode version-specific modifiers such as `%LT`, `%MT`, `%CT4S2`, `%NUDG`, or aerosol
choices from memory. Inspect the component configuration and generated namelist. A name containing
nudging may target a different CAM generation than requested; conversely, a suitable CAM7 compset
may require nudging through `user_nl_cam`.

## Interpret support accurately

`science_support` is an explicit tested scientific configuration, often restricted to a grid.
Other support tags may indicate test coverage rather than scientific endorsement. No declaration
does not prove a compset is invalid, but it is unsupported evidence and may require
`--run-unsupported`.

For every candidate report:

| Field | Evidence |
| --- | --- |
| Alias | Exact `query_config` result |
| Long name | Exact expanded component stack |
| Time/forcing | Long-name token plus component defaults |
| Atmosphere/chemistry | Atmosphere token and component configuration |
| Coupling | Active versus data/stub components |
| Supported grids | `science_support` attributes, if present |
| Required overrides | XML, `user_nl_*`, user-mods, SourceMods |
| Unresolved risks | Missing data, unsupported pairing, unclear initialization |

Prefer a declared science-supported combination when it meets the experiment. If an unsupported
configuration is scientifically necessary, make the status visible; do not present
`--run-unsupported` as validation.

## Choose the grid separately

A compset and grid are a compatible pair, not one decision. Inspect the grid alias expansion and
any `compset`/`not_compset` restrictions. Confirm:

- atmosphere and land resolution;
- ocean/ice grid or prescribed-data grid;
- mask and runoff/glacier/wave grids;
- mapping files and initial/boundary data;
- intended cost and PE layout;
- exact grid named by a compset's science-support declaration.

Let `create_newcase` perform the final compatibility check. Do not manufacture a custom long grid
name when an appropriate alias exists.

## CESM3 beta08 project baseline

For this repository, the currently installed checkout is normally
`/glade/work/fillmore/CESM3/cesm3_0_beta08` on Derecho, account `P19010000`. Existing project
scripts use `F2000dev` with `f09_f09_mg17` for CAM7 prescribed-ocean development cases, but that
precedent is not a universal recommendation. Requery the checkout and compare historical,
chemistry, nudged, coupled, and fixed-SST candidates against the new experiment.
