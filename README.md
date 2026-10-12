# CERES-SARB-CESM3-CAM7

CAM7 source additions for constraining aerosol optical depth (AOD) with gridded
observations and writing aerosol optics in the 14 shortwave and 12 longwave
SARB/LFL spectral bands. Recipients supply their own CESM checkout, compset,
case configuration, emission inventories, and normal CESM input data.

The repository contains the 12 Fortran modules and all five CAM integration
patches, namelist definitions/defaults, and kernel tests copied from
`CERES-SARB-CAM7`. It does **not** contain the external optics tables or AOD
observation files. For the LUT method used in the original production runs,
the minimum runtime additions are one optics LUT and the observation files
covering the recipient's simulation dates, together with the namelist settings
below. The separate LW omega/g table is only needed for the remapping method
with prescribed LW scattering.

## Supported configuration

- **CAM7 physics**, with the original integration based on CESM
  `cesm3_0_beta08` and CAM tag `cam6_4_161`. That CAM tag contains both CAM6 and
  CAM7; select CAM7 through the recipient's compset. Other revisions may need
  the supplied patches merged into their corresponding routines.
- **FV f09 atmosphere/physics grid: 192 latitudes by 288 longitudes.** The AOD
  reader requires this grid and performs no spatial interpolation. Latitude
  centers run from -90 to +90 degrees, inclusive, with spacing `180/191`;
  longitude centers run from 0 to 358.75 degrees with spacing 1.25 degrees.
  The spectral writer also assumes this regular latitude/longitude layout.
- **MAM4 climate-list mode ordering `a1,a2,a3,a4`.** The supplied LUT reader
  checks that exact ordering and the model's mode count; the evaluator also
  checks each mode's geometric standard deviation against the table. The LUT
  supports black carbon, primary organic matter, secondary organic aerosol,
  sulfate, dust, sea salt, and water. Retain compatible MAM4 species and mode
  properties when using the table. The output scheme label is also MAM4.
- The recipient's emissions and other case choices can differ within those
  requirements. Changing aerosol optical properties or mode definitions needs
  a compatible LUT and renewed validation. The vertical level count comes
  from CAM; this extension does not impose the original cases' L32 choice.

The AOD constraint scales interstitial aerosol mass and number, with matching
aerosol-water/number buffers, by a column-wide observation/model ratio before
radiation. It runs on shortwave-radiation timesteps. The default ratio bounds
are 0.1 to 10, and model AOD below 0.01 is left unchanged. Keep
`aod_aci_on = .false.`: the cloud-borne scaling option is not implemented and
aborts if enabled.

The model-side AOD estimate uses CAM's visible-band diagnostic optical depth.
The observational target is nominally 550 nm; the CAM diagnostic and individual
LFL spectral bands are not identical monochromatic quantities.

## File inventory

There are 23 files under `src/cam/`. All 12 modules are needed by the supplied
build configuration, including when only one optics method is selected at
runtime.

### Fortran modules

Install these in `components/cam/src/physics/cam/` in the recipient's CESM tree.

| File | Purpose |
| --- | --- |
| [aod_nudging_kernel.F90](src/cam/aod_nudging_kernel.F90) | Ratio limits, missing-observation handling, and interpolation between observation times. |
| [aod_nudging_obs.F90](src/cam/aod_nudging_obs.F90) | Reads gridded AOD NetCDF files, checks f09 coordinates, and supplies time-interpolated targets to CAM chunks. |
| [aod_nudging_optics.F90](src/cam/aod_nudging_optics.F90) | Diagnoses model visible AOD through CAM optics and applies aerosol scaling to the model state. |
| [aod_nudging_intr.F90](src/cam/aod_nudging_intr.F90) | Nudging namelist, initialization, timestep driver, and `AODNDG_*` history diagnostics. |
| [aod_optics_kernel.F90](src/cam/aod_optics_kernel.F90) | Band-overlap remapping, LW scattering reconstruction, and optical-property bounds. |
| [aod_optics_bands.F90](src/cam/aod_optics_bands.F90) | Built-in SARB/LFL band edges, optional band override, remapping weights, and optional LW omega/g reader. |
| [aod_optics_tap.F90](src/cam/aod_optics_tap.F90) | Reads CAM's SW and per-mode LW optics for the `remap` method. |
| [aod_optics_lut_kernel.F90](src/cam/aod_optics_lut_kernel.F90) | Chebyshev coefficient evaluation, refractive-index interpolation/mixing, and LUT scattering calculations. |
| [aod_optics_lut_tables.F90](src/cam/aod_optics_lut_tables.F90) | Loads and validates the external LFL LUT, including band edges, dimensions, and MAM4 mode ordering. |
| [aod_optics_lut.F90](src/cam/aod_optics_lut.F90) | Evaluates LFL-band optics from CAM's current wet MAM4 aerosol state using the LUT. |
| [aod_optics_io.F90](src/cam/aod_optics_io.F90) | Gathers model chunks and writes per-band NetCDF files through CAM/PIO. |
| [aod_optics_diag_intr.F90](src/cam/aod_optics_diag_intr.F90) | Optics namelist, initialization, output timing, method selection, and output driver after the AOD constraint. |

### CAM integration patches

Patch targets below are relative to `components/cam/`. Merely copying the new
Fortran modules into a case's `SourceMods/src.cam` is insufficient; CAM must
also call them, compile them, and recognize their namelist settings.

| Patch | Target | Purpose |
| --- | --- | --- |
| [physics_cam_CMakeLists.txt.diff](src/cam/physics_cam_CMakeLists.txt.diff) | `src/physics/cam/CMakeLists.txt` | Adds all 12 modules to the CAM source list. |
| [runtime_opts.F90.diff](src/cam/runtime_opts.F90.diff) | `src/control/runtime_opts.F90` | Reads the two new namelist groups. |
| [physpkg.F90.diff](src/cam/physpkg.F90.diff) | `src/physics/cam7/physpkg.F90` | Initializes both features and invokes their timestep hooks before radiation. |
| [aerosol_optics_cam.F90.diff](src/cam/aerosol_optics_cam.F90.diff) | `src/physics/cam/aerosol_optics_cam.F90` | Allows diagnostic optics calls to suppress stock history writes and exposes per-mode LW absorption for remapping. |
| [build-namelist.diff](src/cam/build-namelist.diff) | `bld/build-namelist` | Adds defaults for the new namelist groups. |

### Namelist support and tests

| File | Purpose |
| --- | --- |
| [namelist/namelist_definition.xml](src/cam/namelist/namelist_definition.xml) | CAM definition snapshot containing the `aod_nudging_nl` and `aod_optics_nl` entries. Merge those entries into `bld/namelist_files/namelist_definition.xml`. |
| [namelist/namelist_defaults_cam.xml](src/cam/namelist/namelist_defaults_cam.xml) | CAM defaults snapshot containing the added `aod_*` defaults. Merge those defaults into `bld/namelist_files/namelist_defaults_cam.xml`. |
| [test/CMakeLists.txt](src/cam/test/CMakeLists.txt) | CAM/pFUnit test build integration. |
| [test/test_aod_nudging_kernel.pf](src/cam/test/test_aod_nudging_kernel.pf) | Tests nudging ratios and observation interpolation/masks. |
| [test/test_aod_optics_kernel.pf](src/cam/test/test_aod_optics_kernel.pf) | Tests remapping and optical-property calculations. |
| [test/test_aod_optics_lut_kernel.pf](src/cam/test/test_aod_optics_lut_kernel.pf) | Tests LUT numerical kernels. |

The XML files are full upstream snapshots, not minimal replacement files for
every CAM version. Merge only this extension's entries to preserve the
recipient's existing namelist definitions and defaults. The four test files
are optional for production builds; they can be installed together under
`components/cam/test/unit/aod_nudging/` for the CAM unit-test framework.

## External optics data on Derecho

Copy the required table from the following original-project location on
Derecho into the recipient's own input-data storage, and set the namelist to
that copied path. These NetCDF files are external to this Git repository.

**LFL-native MAM4 LUT — required for `aod_optics_method = 'lut'`:**

```text
/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4_camref_dense3_20260709.nc
```

This is the validated dense3 CAM-reference table identified in the original
project's run configuration. It contains SW/LW extinction, absorption, and
asymmetry coefficients, refractive-index axes and species data, MAM4 mode
widths, and LFL band edges. It supplies all 26 bands, including LW scattering
through extinction minus absorption. Set `aod_optics_lut_file` to this file.

**Prescribed CAM-LW omega/g table — used by `aod_optics_method = 'remap'`:**

```text
/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lw_omega_g.nc
```

This file supplies per-bin CAM-LW-band single-scattering albedo (`omega_lw`)
and asymmetry (`g_lw`) for reconstructing scattering in the remapping method.
Set `aod_optics_lw_table` to this file when using that method with the original
prescribed LW scattering. With an empty path, `remap` produces absorption-only
LW optics with zero scattering.

For the minimum **LUT** configuration, leave `aod_optics_lw_table = ''`.
The LUT calculation does not use omega/g from the separate table. Initialization
still opens that table if a non-empty path is supplied, so an unused stale path
can prevent a LUT run from starting.

No external band-definition file is needed: the 14 SW and 12 LW SARB/LFL band
edges are built into `aod_optics_bands.F90`. Leave `aod_optics_band_file = ''`.
The normal CAM aerosol/radiation input files remain part of the recipient's
CESM input-data requirements. The extra LUT does not replace them.

The table-generation Python code and its Mie/optical-property dependencies
remain in the original project; they are not needed to run CAM with the
precomputed table. Changing emission inventories alone does not require
regenerating the LUT when the aerosol species and mode properties remain
compatible.

## AOD observation inputs

The recipient must also supply CAM-readable target AOD files covering the
simulation dates, including the bracketing observation windows at the run
boundaries. Raw MODIS/VIIRS retrieval files cannot be read directly by these
Fortran modules. Observation acquisition and preprocessing are outside this
repository.

The default input series uses eight three-hour windows per day:

```text
MODIS_VIIRS_AOD_3hr_f09.YYYYMMDD.SSSSS.nc
```

`SSSSS` is the window-start second of day (`00000`, `10800`, ..., `75600`).
Each file has the exact f09 grid described above. The fields read by CAM are:

| Variable | Layout and meaning |
| --- | --- |
| `lat` | 192 latitude centers, in degrees north. |
| `lon` | 288 longitude centers, in degrees east. |
| `aod_weighted_mean` | `(lat,lon)` dimensionless target AOD at 550 nm; use `-999` for missing observations. |
| `time` | Scalar window-center time; the original contract uses `hours since 2000-01-01 00:00:00 UTC`, calendar `gregorian`. For three-hour windows, the center is 90 minutes after the filename's start time. |

The reader assumes time differences are in hours; it does not convert arbitrary
CF time units. Additional uncertainty, count, and source-specific fields in the
original observation products are not read by the nudging module.

Two valid bracketing observations are linearly interpolated; if only one is
valid, that one is used. If neither is valid, the column runs without an AOD
update. Missing files are logged and treated as unavailable observations rather
than stopping the run, so successful execution alone does not prove that
constraints were applied. `aod_obs_path` must include a trailing `/` because
the reader concatenates it directly with the filename.

## Installation in the recipient's CAM checkout

1. Use a CAM7/f09/MAM4 case satisfying the requirements above. Compare the
   recipient's CAM revision with the original `cam6_4_161` integration baseline.
2. Copy all 12 `src/cam/*.F90` files into
   `components/cam/src/physics/cam/`.
3. Check and apply the five patches from the `components/cam/` directory, or
   merge the same changes manually if the target version differs. For a
   compatible, unpatched checkout, the commands below check every patch before
   applying them together.
4. Merge the 19 definition entries whose group is `aod_nudging_nl` or
   `aod_optics_nl` from the supplied definition XML into the recipient's CAM
   definition XML. Merge the 18 `aod_*` defaults from the supplied defaults XML
   into the recipient's defaults XML. `aod_obs_path` is supplied by the user
   and has no XML default. Avoid duplicating existing entries.
5. Add the settings below to the recipient's `user_nl_cam`, run
   `./preview_namelists`, and check that `CaseDocs/atm_in` contains both new
   groups and the intended paths. Rebuild the case with its normal CIME build
   procedure so the modified CAM sources are compiled. Existing case
   `SourceMods/src.cam` overrides must agree with the patched sources.

Example patch commands; replace both paths before running:

```bash
extension_root=/path/to/CERES-SARB-CESM3-CAM7
cam_root=/path/to/CESM/components/cam
git -C "$cam_root" apply --check "$extension_root"/src/cam/*.diff &&
git -C "$cam_root" apply "$extension_root"/src/cam/*.diff
```

The original project's `scripts/sp2_deploy.sh` is not included: it hard-codes
the original account's source-tree paths and replaces full namelist XML files.
The installation above lets recipients retain their own case and input choices.

## Minimal runtime settings

Merge this block into the recipient's `user_nl_cam`, replacing the three paths.
Use assignments without enclosing namelist group delimiters; CAM's
`build-namelist` places them in the appropriate groups.

```fortran
! AOD observations on the exact f09 grid.
aod_nudge_on = .true.
aod_obs_path = '/path/to/AOD_f09_3hr/'
aod_obs_template = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
aod_times_per_day = 8
aod_aci_on = .false.
aod_diag_on = .true.

! LFL-native spectral optics using the copied Derecho LUT.
aod_optics_on = .true.
aod_optics_method = 'lut'
aod_optics_lut_file = '/path/to/optics/aod_lfl_lut_mam4_camref_dense3_20260709.nc'
aod_optics_outdir = '/path/to/output/band_optics'
aod_optics_interval_hours = 3
aod_optics_band_file = ''
aod_optics_lw_table = ''
```

Both features default to off. The code's default optics method remains
`remap`, so set `lut` explicitly to use the supplied LFL-native table. Optics
output can also be enabled with AOD nudging off for a free-running comparison.
Optionally set `aod_beg_ymd` and `aod_end_ymd` to restrict the inclusive nudging
date range; otherwise the default range includes all simulation dates.

Choose an output interval that the model timestep lands on exactly. AOD
updates follow the case's shortwave radiation schedule, while spectral output
follows `aod_optics_interval_hours`. Use accessible absolute data/output paths
on the runtime filesystem; keep the optics output path free of spaces because
the driver creates it with a shell command.

To save the nudging diagnostics, append these fields to the recipient's chosen
CAM history `fincl` list, preserving their existing selections and tape timing:

```text
AODNDG_OBS, AODNDG_MODEL_PRE, AODNDG_MODEL_POST, AODNDG_RATIO, AODNDG_MASK
```

`MODEL_PRE` is the cycling model first guess immediately before the update,
`MODEL_POST` is the analyzed AOD, and their difference is the analysis increment.
Inspect the ratio and mask together: a valid observation does not guarantee a
change when the low-model-AOD guard is active.

## Spectral output and verification

Each scheduled output time produces 26 separate NetCDF files, using the default
template `AER_MAM4_{band}.%y%m%d.%s.nc`, with band labels `SW01` through `SW14`
and `LW01` through `LW12`. These are instantaneous aerosol-optics files in
`aod_optics_outdir`, independent of CAM's history tapes. They contain:

- `Extinction_Layer_Optical_Depth`
- `Scattering_Layer_Optical_Depth`
- `Layer_Asymmetry_Parameter`
- `Extinction_Column_Optical_Depth`
- `DELP`, with `lon`, `lat`, and model-layer `lev` coordinates.

The output is diagnostic; it does not replace CAM's radiation solver or its
native spectral bands. Metadata record the method, LUT path/version, band,
representative wavelength, and nudging activation state.

After building, run a short case using the recipient's own configuration.
Check `AODNUDGE` log messages for observation reads, inspect the `AODNDG_*`
history fields, and confirm complete 26-band output groups with `method='lut'`
and the intended LUT metadata. Check finite optical properties,
`0 <= scattering <= extinction`, and asymmetry in `[-1,1]`.

The original project records validation for the dense3 LUT and f09/MAM4 runs,
including comparisons showing that enabling diagnostic optics leaves the
model history unchanged. That evidence does not establish build compatibility
with every later CAM revision. This repository is a source/data-interface
handoff; recipients still need to build and verify their selected case.

Source provenance: `CERES-SARB-CAM7` commit
`cd1b5d45dbf3ddfb737c3a7153b67cdf2adef254`. The Derecho optics paths above are
recorded in that repository's `config/cesm/monthly_2008_v1.yaml`; the validated
table is documented in
`docs/superpowers/specs/2026-07-08-sp3v2-lfl-lut-status.md`.
