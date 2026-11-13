# SP2 MAM4 AOD Round-Trip and Aerosol State Consistency

Date: 2026-06-27

## Decision

The SP2 actuator scales every aerosol optical contributor in CAM's climate
radiation list:

- modal aerosol interstitial number and species mass
- modal pbuf `NAER` and `QAERWAT`
- bulk aerosol mass, when prescribed bulk aerosols are present
- bin aerosol number and species mass, when bin aerosols are present

The driver does not rerun modal size or water-uptake diagnostics after scaling.
For uniform column scaling, dry mass and number are multiplied by the same
ratio, so modal diameter and composition remain invariant. The pbuf fields that
represent extensive aerosol amount, `NAER` and `QAERWAT`, must scale by the same
ratio for the second optics call to see the same internally consistent aerosol
state.

## Bulk Aerosols Are Present in the MAM4 Run

This regression is a MAM4 configuration, but it is not modal-only for radiation.
The MAM4 `rad_climate` contains four modal MAM entries plus three prescribed
volcanic bulk aerosols:

- `M:mam4_mode1` through `M:mam4_mode4`
- `N:VOLC_MMR1`, `N:VOLC_MMR2`, `N:VOLC_MMR3`

Evidence from `/glade/work/fillmore/CESM3/cases/sp2_mam4/CaseDocs/atm_in`:

```text
rad_climate = ... 'M:mam4_mode1:...', 'M:mam4_mode2:...',
              'M:mam4_mode3:...', 'M:mam4_mode4:...',
              'N:VOLC_MMR1:...', 'N:VOLC_MMR2:...', 'N:VOLC_MMR3:...'
```

Evidence from the latest atm log:

```text
bulk aerosol list for climate calculations
   N:VOLC_MMR1 optics and phys props in ...
   N:VOLC_MMR2 optics and phys props in ...
   N:VOLC_MMR3 optics and phys props in ...
modal aerosol list for climate calculations
   mam4_mode1
   mam4_mode2
   mam4_mode3
   mam4_mode4
aerosol_optics_cam_init: nmodes,nbins,nbulk_aerosols: 4 0
           3
```

The final wrapped integer is `nbulk_aerosols=3`. Therefore a MAM regression
must still nudge prescribed background aerosol if it is radiatively active.

## Rejected Alternative

A trial refresh using CAM modal diagnostic recalculation after scaling
(`modal_aero_calcsize_diag` and water uptake) was rejected. It improved the
nudged-column round trip but changed free columns, because the diagnostic
recalculation did not reproduce the upstream prognostic pbuf state bit-for-bit.
SP2 only wants to overwrite valid-observation columns; free columns must remain
unchanged.

Directly scaling `NAER` and `QAERWAT` is the narrower consistency update. It
leaves invariant fields such as wet diameter unchanged and scales only the
amount-like pbuf fields that should scale with the aerosol ratio.

## Verification

Latest MAM4 case:

- Case root: `/glade/work/fillmore/CESM3/cases/sp2_mam4`
- Run directory: `/glade/derecho/scratch/fillmore/sp2_mam4/run`
- Latest atm log: `atm.log.6579690.desched1.260627-215322.gz`
- History file checked:
  `/glade/derecho/scratch/fillmore/sp2_mam4/run/sp2_mam4.cam.h0i.0001-01-01-03600.nc`

`CaseStatus` shows:

```text
2026-06-27 21:53:17 case.build success
2026-06-27 21:53:25 model execution starting
2026-06-27 22:00:14 model execution success
2026-06-27 22:00:14 case.run success
```

Numeric assertion:

```text
nudged cells=2730 max_rel_err=0.0000 bad=0
free cells=52566 max_abs_change=0.00e+00 bad=0
PASS
```

VP5 plot verifier after masking obs fill values:

```text
obs: n=2730 min=0.3 mean=0.3 max=0.3
bias: n=2730 min=0 mean=0 max=0
free_post_minus_pre: n=52566 min=0 mean=0 max=0
nudged_post_minus_obs: n=2730 min=0 mean=0 max=0
```

Hit-rate diagnostics in the latest log show the expected valid box fraction and
no sustained clamp hits:

```text
AODNUDGE hit-rate nstep=47 nudged_frac=0.0494 clamp_lo_frac=0.0000 clamp_hi_frac=0.0000 ncol_global=55296
```

The repo mirror and CAM checkout copies of `aod_nudging_optics.F90` and
`aod_nudging_intr.F90` were checked with `diff -u`; both pairs match.
