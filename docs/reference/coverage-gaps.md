# Coverage & Gaps (what wasn't read)

> Subsystem: **MODIS/VIIRS AOD Nudging Implementation for NCAR CESM2.2.2 (CAM6/MAM4)**  ·  source: prior attempt at `/glade/work/tvmora`

## Summary

This is a large, disorganized prior attempt to add satellite-derived aerosol optical depth (AOD) nudging to the NCAR Community Earth System Model version 2.2.2 (CESM2.2.2), specifically CAM6 atmospheric component with MAM4 modal aerosol scheme. The implementation involves reading MODIS and VIIRS L2 satellite AOD observations (2000-2025 archive in netCDF), performing bias correction and daily averaging, then nudging predicted aerosol mixing ratios (qaer) toward observed AOD via a forcing/relaxation mechanism. The system contains multiple experimental branches exploring different approaches: "Force_AODs" with 123 Fortran variants testing Kohler deliquescence, AOD visibility calculation, dust schemes, and parameter sensitivities; parallel "FHIST" and "aod_weighted_mean" variants; and over 200 test case directories in cesm2.2.2/cime/scripts with different configurations (GEOSIT/MODIS/VIIRS data, nudging coefficients, temporal update frequencies). The code modifies CAM's physpkg (physics package driver), modal_aer_opt (radiative optics), aer_rad_props (radiation interface), runtime_opts (namelist control), nudging (analysis relaxation), and tracer_data (external forcing) modules. Entry points show integration via SourceMods in cesm2.2.2 checkouts, with 80+ test/control scripts and 11 Jupyter analysis notebooks in CAM_scripts. The codebase reflects iterative exploration of parameter space rather than a clean production implementation.


## Key files

| Path | Role | ~Lines |
|---|---|---|
| `/glade/work/tvmora/CAM_modifications/nudging_AODs.F90` | Main AOD nudging driver module (central logic for forcing qaer toward observed AOD) | 4000 |
| `/glade/work/tvmora/CAM_modifications/Force_AODs/nudging_AODs_qaer_modis.F90` | MODIS-specific AOD nudging variant with qaer target calculation | 4000 |
| `/glade/work/tvmora/CAM_modifications/physpkg_AODs.F90` | Physics package driver modification to call nudging_AODs routines during CAM timestep | 3200 |
| `/glade/work/tvmora/CAM_modifications/Force_AODs/physpkg_AODs.F90` | Alternative physpkg variant for Force_AODs branch | 3200 |
| `/glade/work/tvmora/CAM_modifications/aer_rad_props_FL_interface_complete.F90` | Radiation interface layer computing aerosol optical properties at multiple wavelengths | 1200 |
| `/glade/work/tvmora/cesm2.2.2/components/cam/src/physics/cam/modal_aer_opt.F90` | Base CAM module for modal aerosol optics calculation | 2400 |
| `/glade/work/tvmora/cesm2.2.2/components/cam/src/control/runtime_opts.F90` | Base CAM runtime options/namelist registry | 1200 |
| `/glade/work/tvmora/CAM_modifications/namelist_definition_nudging_AODs.xml` | Namelist definition XML for AOD nudging parameters | 1500 |
| `/glade/work/tvmora/cesm2.2.2/cime/scripts/test_geosit_viirs_nds_2025_06_07/SourceMods/src.cam` | Example test case SourceMods showing deployed nudging configuration | 0 |
| `/glade/work/tvmora/MODIS_VIIRS_AOD` | Observation archive (2000-2025) containing daily gridded AOD files | 0 |


## Technical findings

- AOD nudging method: Daily-averaged satellite AOD observations are converted to mode-wise aerosol mass (qaer) via inversion of Mie optics, then model prognostic qaer is relaxed toward target via Newtonian damping (nudge_Qaer_coef * (qaer_target - qaer_prog) / delt)
- Modal aerosol architecture: CAM6 uses MAM4 (4 lognormal modes). Nudging occurs on visible-band AOD (~550nm), with inversion back to individual mode mixing ratios using mode-specific refractive indices and size distributions from Mie lookup tables
- Satellite data flow: MODIS L2 and VIIRS L2 files are time-averaged daily, bias-corrected, then used to drive nudging
- Integration points: (1) physpkg calls nudging_AODs%update_analyses during tracer tendency computation; (2) runtime_opts registers AOD namelist; (3) tracer_data handles external forcing; (4) aer_rad_props/modal_aer_opt compute AOD; (5) cam_history allows diagnostics
- Parameter exploration: Force_AODs/ contains 123 variants testing Kohler deliquescence, dust schemes, AOD formulations, nudging coefficients (0-2), and update frequencies (1-96 times/day)
- Test case proliferation: 200+ subdirectories following geosit_viirs_def_X, test_nudge_AOD_force_opt_Y, GEOSIT_MODIS_ZZZZ patterns with different AOD products and nudging parameters
- Observation bias correction: VIIRS_original/ vs VIIRS_corrected/ indicates VIIRS requires systematic adjustment relative to MODIS
- Modal optics calculation: aer_rad_props_FL_interface_complete.F90 computes AOD from mode-wise mixing ratios, providing forward model input for nudging target calculation
- Dust scheme variants: 13+ versions of modal_aer_opt in Dust_scheme/ directory suggesting iterative testing of dust optical properties
- Mie optics lookup tables: /glade/work/tvmora/Mie_io/ contains netCDF aerosol optical property databases defining size distributions and refractive indices


## Problems / why it's a mess

- Code fragmentation: 31 standalone nudging*.F90 files plus 123 in Force_AODs with manual ad-hoc naming instead of version control
- Parameter proliferation: Kohler (7 variants), dust schemes (13 variants), AOD types, nudging coefficients, and profile options without summary documentation
- Namelist inconsistency: Multiple separate namelist definition XML files rather than single evolving definition
- Test case explosion: 200+ directories with nested SourceMods make it impossible to determine correct configuration
- Integration gap: All modifications applied via SourceMods; no clear mechanism for merging back to CESM trunk
- Inversion algorithm unclear: AOD to qaer conversion mathematics not documented in code comments
- Bias correction undocumented: VIIRS_corrected/ exists but correction procedure and code invisible
- Observational metadata missing: MODIS_VIIRS_AOD/ files lack schema documentation
- Obsolete variants not cleaned: test files and dead-end experiments left in place
- Hard-coded parameters suspected: Magic numbers likely embedded in code rather than namelists
- FHIST redundancy: 8 variants that should have been unified with conditional logic
- No validation harness: 200+ cases with no visible postprocessing or metrics aggregation


## Open questions

- Which configuration (Force_AODs variant or test_geosit_viirs_nds_2025_06_07) is production-ready?
- What is the exact mathematical inversion from AOD to mode-wise qaer? Analytical or iterative?
- Why 7 Kohler variants? Did testing converge or are all equally valid?
- What is the VIIRS bias correction methodology and derived correction factors?
- How does code handle physically inconsistent AOD and aerosol mass combinations?
- Is nudge_Qaer_coef constant in time or season/region dependent?
- What does nudge_Qaer_prof parameter control (0=depth-integrated, 1=full-profile)?
- Are test case SourceMods cumulative or independent dependencies?
- Do Jupyter notebooks validate against independent AOD products (AERONET, OMI)?
- Why multiple CESM checkouts (cesm2.2.2, cesm_sarb, CESM2.2) and which is primary?


## Carry forward vs discard

- Nudging mechanism is sound: Newtonian relaxation toward satellite-derived targets is mathematically simple and proven in data assimilation
- Modal aerosol Mie optics inversion is tractable: Forward (qaer->AOD) is deterministic; inverse (AOD->qaer) with fixed distributions has unique solutions
- Multi-source satellite integration is validated: MODIS+VIIRS merge is standard in aerosol monitoring
- Test case infrastructure is comprehensive: 200+ cases enable sensitivity analysis despite poor organization
- Observation data archive (2000-2025) is valuable asset: 25 years of daily global AOD is substantive research infrastructure
- Namelist control paradigm works: nudging parameters properly exposed in CAM's native system
- SourceMods deployment is pragmatic: Allows incremental testing without rebuilding CESM trunk
- Radiative impact pathway is clear: Nudged qaer affects modal_aer_opt and aer_rad_props without modifying radiation driver
- Code reuse opportunity: Common logic can be unified into single 'aod_nudging' module with clean interface
- Testing regression suite: 200+ cases provide baselines for validating clean-rewrite against current code
- Use most recent case (test_geosit_viirs_nds_2025_06_07) as production template for new implementation
- Kohler, dust, and VIIRS bias variants are quantifiable differences suitable for sensitivity matrix
