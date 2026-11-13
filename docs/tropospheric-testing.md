# Testing tropospheric versus whole-column AOD scaling

Use branch `feature/tropospheric-aod-nudging`. This branch adds the same
tropospheric-scaling implementation as the private CERES-SARB-CAM7 project.
The recipient installation procedure is in the [README](../README.md).
For an installation that already has the main-branch extension, refresh the
Fortran modules, merge the new `aod_tropo_only` definition/default into CAM's
namelist XML and the corresponding `add_default` into `build-namelist`, then
regenerate the case namelists and rebuild. The existing CAM timestep hooks
are unchanged. Do not reapply already installed integration patches blindly.

## Matched comparison

Use the same branch and newly built executable for both cases, with identical
initial or restart state, dates, meteorological forcing, emissions, observation
files, physics, radiation cadence and output times. Keep AOD nudging enabled:

```fortran
! Common to both cases.
aod_nudge_on = .true.
aod_diag_on = .true.
aod_aci_on = .false.

! Whole-column reference case.
aod_tropo_only = .false.

! In the second case, replace the preceding setting with:
! aod_tropo_only = .true.
```

The false case retains whole-column scaling; it is not an unnudged control.
Check each generated `CaseDocs/atm_in` and the `AODNUDGE` startup log for the
intended setting. Resolve the separate emissions issue in an unnudged run
when diagnosing low background AOD; this switch changes where the AOD
constraint acts and does not correct emissions inputs.

## Tropopause and scaling

For each column and AOD update, CAM's native `tropopause_find_cam` routine
diagnoses the thermal tropopause using its TWMO lapse-rate method, with the
native climatological fallback. The WMO criterion looks for a sufficiently
weak temperature decrease with height (2 K/km) that persists on average
through the next 2 km. No fixed-pressure boundary is introduced.

CAM level indices increase downward. Only `k > tropopause_level` is scaled;
the tropopause layer and all levels above it are protected. The boundary is
held fixed for the before/after probes of each update. A failed diagnosis
gives an empty eligible mask and skips the tropospheric update.

The model AOD of the protected layers is subtracted from the observed
column target before calculating the tropospheric scaling ratio. The ratio
is bounded by `aod_ratio_min/max` (0.1 and 10 by default); `aod_eps` applies
to tropospheric AOD in the new mode. These guards mean that a target is not
always exactly attainable.

## Vertical profiles of layer AOD

Enable the same spectral optics output in both cases using the README's
`aod_optics_*` settings and compatible LUT. Plot
`Extinction_Layer_Optical_Depth` from the per-band output against model-level
pressure. This is dimensionless AOD contributed by each layer, rather than
column AOD or extinction per unit distance.

At matching times and locations, overlay the whole-column and tropospheric
profiles and plot their difference. Mark each run's diagnosed tropopause.
Include representative tropical, midlatitude and high-latitude columns.
Retain individual profiles around the first active updates as well as any
later time or regional averages, so the boundary treatment can be inspected.

Compare the same band between runs. SW05 is one possible visible LFL-band
choice, but it is not the same spectral quantity as CAM's visible-band
diagnostic or a monochromatic 550 nm AOD. Use `AODNDG_PMID` for pressure at
the update and `AODNDG_TROP_P/LEV` for the boundary, matching timestamps and
grid coordinates to the spectral files.

Append the relevant fields to the existing instantaneous history selection:

```text
AODNDG_OBS, AODNDG_MODEL_PRE, AODNDG_MODEL_POST, AODNDG_RATIO, AODNDG_MASK,
AODNDG_TROP_PRE, AODNDG_TROP_POST, AODNDG_FIXED_PRE, AODNDG_FIXED_POST,
AODNDG_TROP_P, AODNDG_TROP_LEV, AODNDG_TROP_MASK, AODNDG_PMID,
AODNDG_MMR_PRE, AODNDG_MMR_POST, AODNDG_NUM_PRE, AODNDG_NUM_POST
```

The mass and number fields are additional before/after state diagnostics;
they are not layer AOD. In tropospheric mode, check zero direct mass and
number increments in protected layers and unchanged `AODNDG_FIXED_PRE/POST`.
Do not infer that the two evolving runs must retain identical stratospheric
profiles: transport, subsequent physics and a changing tropopause can create
later differences. Request the layer-AOD profiles and the generated
namelists/log excerpts together when reviewing the comparison.

## Existing evidence

The mirrored [method note](tropospheric-scaling.md) and
[July 2008 CAM7 summary](../run_history/results/tropospheric-july2008-v1.json)
record the original Derecho comparison: 248 three-hourly July samples per
case, and exactly zero direct protected-layer mass/number increments in the
tropospheric run. Those results establish the original configuration's
behavior; a recipient must still test the rebuilt executable and its own
forcing and input data.
