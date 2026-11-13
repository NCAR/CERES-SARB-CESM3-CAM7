# Build / Run / Cases on Derecho

> Subsystem: **MODIS/VIIRS AOD nudging for NCAR CESM2.2.2 (CAM6 with MAM4 modal aerosols)**  ·  source: prior attempt at `/glade/work/tvmora`

## Summary

This is a prior attempt to add MODIS/VIIRS aerosol optical depth (AOD) forcing/nudging capability to CESM2.2.2, which runs CAM6 atmosphere with MAM4 modal aerosols (trop_strat_mam4_vbs chemistry). The implementation uses a relaxation-based nudging approach to nudge model aerosol mass mixing ratios (Qaer constituents for 27 modal aerosol species) toward MODIS/VIIRS satellite-derived AOD observations. The model is built via CESM's standard create_newcase/case.setup/case.build workflow, with custom nudging modules injected into SourceMods/src.cam. The compset is HIST (historical forcing) with CAM-Chem troposphere/stratosphere (CCTS1 option) and nudging enabled (%NUDG). The runs use f09_f09_mg17 resolution (0.9x1.25 degree atmosphere/land grid) on Derecho supercomputer, with MERRA2 meteorological nudging simultaneously applied for consistent atmospheric dynamics.


## Key files

| Path | Role | ~Lines |
|---|---|---|
| `/glade/work/tvmora/cesm2.2.2` | Primary CESM2.2.2 checkout (release-cesm2.2.2 tag) with custom FCnudged compset definition in config_compsets.xml allowing simultaneous met+AOD nudging | 0 |
| `/glade/work/tvmora/cesm_sarb` | Secondary CESM checkout (cesm2.2.0 tag) - used early in development but appears superseded by cesm2.2.2 | 0 |
| `/glade/work/tvmora/CAM_modifications` | Repository of CAM source mods: nudging modules (nudging_AODs variants), modal_aer_opt_binterpublic.F90 (makes binterp public), namelist_definition XMLs, physpkg mods | 0 |
| `/glade/work/tvmora/CAM_modifications/Force_AODs` | Latest nudging_AODs implementation variants (qaer_modis, kohler, dust schemes, ratio-limiting logic), ~80 versions tracking algorithm iterations | 0 |
| `/glade/work/tvmora/CAM_modifications/Force_AODs/nudging_AODs_qaer_modis.F90` | Main AOD nudging module: reads MODIS/VIIRS 3-hourly AOD files, computes relaxation forcing F_nudge = Alpha*(Target-Model)/TimeScale, applies horizontal/vertical windowing, maps AOD to 27 MAM4 aerosol constituents via computed optical properties | 3546 |
| `/glade/work/tvmora/CAM_modifications/Force_AODs/physpkg_AODs.F90` | Modified physics package driver: calls nudging_AODs initialization and tendencies at each timestep, manages AOD forcing integration into CAM physics loop | 116 |
| `/glade/work/tvmora/CAM_scripts/Derecho_CESM_scripts` | Shell scripts automating case creation, config, and submission; examples: derecho_FHIST_control_NE.csh (FHIST no AOD), derecho_FCnudged_control.csh (FCnudged with AOD), show full workflow | 0 |
| `/glade/work/tvmora/CAM_scripts/Derecho_CESM_scripts/derecho_FCnudged_control.csh` | Example run script using FCnudged compset; shows: create_newcase FHIST, copy SourceMods (nudging_AODs, modal_aer_opt, physpkg), configure user_nl_cam with nudging_nl + nudging_AOD_nl namelist entries, execute case.build/case.submit | 169 |
| `/glade/work/tvmora/MODIS_VIIRS_AOD` | Observation archive structure: /yyyy/mm directories, files named terra_modis_npp_viirs_3hr_lat192xlon288.%y%m%d.%s.nc with 8 timesteps/day (3-hourly), coverage 2000-2025 | 0 |
| `/glade/work/tvmora/cesm2.2.2/cime/scripts/test_nudge_AOD_force_opt_0` | Example successful case: HIST_CAM60%CCTS1%NUDG compset, SourceMods with nudging_AODs_qaer_modis.F90, user_nl_cam with nudging_AOD_nl parameters, ran 2010-01-01 to 01-02 successfully | 0 |


## Technical findings

- Compset: HIST (historical forcing) with CAM-Chem troposphere/stratosphere (CCTS1 = MAM4_VBS), resolution f09_f09_mg17 (0.9x1.25 deg), CAM6 physics. FCnudged compset alias maps to HIST_CAM60%CCTS1%NUDG_CLM50%SP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV.
- AOD forcing injected via SourceMods/src.cam: copies 6-7 files into case before build: nudging_AODs.F90 (3-5 variants tested), modal_aer_opt.F90 (binterp made public to allow external AOD-from-Qaer computation), physpkg.F90 (calls nudging init/tendencies), namelist_definition.xml (adds nudging_AOD_nl), runtime_opts.F90.
- Nudging algorithm: relaxation forcing F = alpha*((Target_AOD - Model_Computed_AOD)/TimeScale). Target AOD from MODIS/VIIRS files at 3-hourly intervals. Model AOD computed from predicted Qaer (27 MAM4 species) using modal_aer_opt radiative module, requiring RH, pressure, wet/dry refractive indices, wet radii via Kohler theory.
- Namelist controls via user_nl_cam &nudging_AOD_nl: nudge_model_AOD (bool), nudge_path_Qaer (e.g., /glade/work/tvmora/MODIS_VIIRS_AOD/), nudge_file_template_Qaer (terra_modis_npp_viirs_3hr_lat192xlon288.%y%m%d.%s.nc), nudge_beg/end_year/month/day_AOD, nudge_AOD_force_opt (0=next-obs, 1=linear-interp), nudge_timescale_opt_AOD, nudge_times_per_day_AOD (8 for 3-hr), model_times_per_day_AOD (48 for 30min timesteps), nudge_Qaer_coef (27-element array, ~1.0 each), nudge_Qaer_prof (27-element array, =1 for all).
- Simultaneous MERRA2 met-nudging enabled via: nudge_model=.true., nudge_path=/glade/p/cesmdata/cseg/inputdata/atm/cam/met/nudging/MERRA2_fv09_32L/, nudge_file_template=%y/MERRA2_fv09.cam2.i.%y-%m-%d-%s.nc, nudge_qcoef/nudge_tcoef/nudge_ucoef/nudge_vcoef=0.25, nudge_times_per_day=8.
- Build workflow: ./create_newcase --case NAME --compset HIST --res f09_f09_mg17 --project P19010000 --run-unsupported; ./case.setup; cp SourceMods into SourceMods/src.cam/; ./xmlchange RUN_STARTDATE/STOP_OPTION/STOP_N; append user_nl_cam; ./case.build --clean-all; ./case.build; ./case.submit.
- cesm2.2.2 checkout: git tag release-cesm2.2.2 (CESM v2.2.2 final), no local modifications (git status clean), contains custom config_compsets.xml with FCnudged and FCts2nudged aliases pointing to %NUDG compset variants.
- cesm_sarb checkout: git tag cesm2.2.0 (earlier CESM2.2 release), no local modifications, not actively used (appears superseded by cesm2.2.2).
- CESM2.2 directory: non-git checkout, likely partial copy or test setup.
- AOD data structure: /glade/work/tvmora/MODIS_VIIRS_AOD/{year}/{month}/, files at 3-hourly intervals (seconds=00000, 10800, 21600, 32400, 43200, 54000, 64800, 75600), 192x288 lat/lon grid matching f09 resolution.
- 80+ nudging_AODs variants in Force_AODs track iterative algorithm changes: qaer_modis (maps Qaer to MODIS AOD), qaer_viirs, modal_aero_kohler (uses Kohler deliquescence), DF variations (damp-factor ratio-limiting), max_ratio (bounds AOD ratio), upper/lower_ratio_range. Suggests active debugging/tuning of AOD-to-Qaer inversion.
- physpkg_AODs.F90 mods: adds Nudge_AOD_ON logical flag, calls nudging_timestep_init_AOD (prepare target/computed AOD), nudging_timestep_tend_AOD (apply forcing tendency), check_energy_chng for nudging_AODs tendency tracking.
- Recent runs (test_nudge_AOD_force_opt_0 Jun2025, AODVIS_2020 Feb2025) show builds complete but many fail at runtime. Example error: model execution error after 2min run, mpiexec failure on 1024 PEs.
- History output: fincl1/fincl2 include AODVISdn, AODNIRdn, Target_AOD, Nudge_Qaer for validation.
- Multiple script variants show increasing complexity: CESM_derecho_FHIST.csh (basic met nudging only), CESM_derecho_FCnudged.csh (adds AOD), derecho_FCnudged_control_NE.csh (144 lines, extensive comments, NE grid test), derecho_FCnudged_forced_* variants (met/AOD forcing combinations).


## Problems / why it's a mess

- Extreme code duplication in Force_AODs: ~80 nudging_AODs variants (most differ by <1%) suggests ad-hoc trial-and-error development without version control of algorithm branches. No clear tracking of which version solves which problem.
- AOD-to-Qaer inversion appears mathematically fragile: requires inverting 27 modal aerosol species + water uptake + 4 optical property coefficients from single (or 2) spectral AOD observations. Multiple Kohler, ratio-limiting, and damping-factor variants suggest nonconvergence or instability.
- Namelist_definition_nudging_AODs.xml (328 KB) and multiple versions (namelist_definition_nudging_AOD.xml, namelist_definition.xml) indicate evolving parameter definitions, but no schema documentation or parameter validation rules visible.
- Modal_aer_opt.F90 modification only makes binterp public; the actual AOD computation appears embedded in nudging_AODs, mixing optical radiative transfer logic with nudging dynamics. No separation of concerns.
- Runtime failures in recent test cases (e.g., AODVIS_2020, AODVISdn_DF_d) after successful builds suggest: (1) namelist compatibility issues, (2) nudging file I/O errors (missing/malformed MODIS data), or (3) Qaer inversion NaN/divergence.
- Simultaneous MERRA2 met nudging + AOD nudging creates coupled forcing problem: nudging aerosol constituents modifies optical properties, which modifies radiation, which should feed back to dynamics, but met nudging overrides predicted winds. Risk of thermodynamic inconsistency.
- No documentation of spin-up requirement: single large restart file (spin-up_23.cam.i.2024-01-01-00000.nc, 2.8 GB) in archive_spin-ups suggests multi-month spin-up needed but no log/script explains spin-up procedure or convergence criteria.
- Grid resolution mismatch: MODIS_VIIRS_AOD files on lat192xlon288 (192 latitudes x 288 longitudes = explicit 192x288 grid), but f09 is native 96x144 (some files with regridding suffix). Interpolation method and conservative mass conservation not documented.
- Multiple CESM checkouts (cesm2.2.2, cesm_sarb, CESM2.2) create maintenance burden; unclear which is canonical. cesm_sarb is CESM2.2.0 (earlier tag), cesm2.2.2 is final release, but no documented rationale for dual-checkout approach.
- No integration into CESM main tree: all AOD changes in SourceMods, relying on file copying via shell scripts. Fragile to CESM rebuilds; no automated testing; no git tracking of when which modules went into which cases.
- Emission specifiers in user_nl_cam reference /glade/campaign/acom/MUSICA/emis/qfed/qfed2.5_finn/f09/ and /glade/campaign/cesm/cesmdata/inputdata/atm/cam/chem/, suggesting external fire emissions (QFED) merged into workflow, but integration with AOD nudging not clear.
- Chem_inparm namelist entries show ext_frc_type='SERIAL' and srf_emis_specifier paths for anthropogenic + volcanic emissions; AOD nudging target is total AOD but forcing only modifies advected Qaer, not forcings. Target discrepancy risk.


## Open questions

- What is the exact algorithm for inverting single (or dual-band) AOD observations to 27 MAM4 aerosol species? The ratio limiting, damping factors, and Kohler logic in multiple variants suggest multiple attempts; which converges and under what RH/composition ranges?
- Why do multiple recent runs (test_nudge_AOD_force_opt_0, AODVIS_2020, etc.) build successfully but fail at runtime? Are nudging files missing, netCDF corrupt, or is the Qaer inversion algorithm diverging?
- What is the spin-up protocol? The spin-up_23.cam.i file is 2.8 GB for a single date (2024-01-01); was it generated by a multi-year nudged run? How long? With or without AOD nudging enabled?
- How are MODIS/VIIRS observations preprocessed before being stored in /glade/work/tvmora/MODIS_VIIRS_AOD/? Are they regridded to f09? How is topographic correction applied?
- Is AOD nudging compatible with CAM-Chem chemistry (CCTS1 with VBS-SOA)? The nudging overwrites Qaer, bypassing emission sources and chemistry; is there feedback from chemistry to nudging targets?
- What is the intent of the 27-element nudge_Qaer_coef array being uniformly ~1.0? Does this mean full nudging strength to all species equally, or are there tuned values being planned?
- Why does the script say '--run-unsupported' in create_newcase? Is FCnudged an unsupported CESM compset, or is there a CESM release issue?
- What observational error/uncertainty is assumed for MODIS/VIIRS AOD? Is there a bias-correction applied between MODIS (Terra/Aqua) and VIIRS (NOAA-20)?
- How do aerosol emission files (QFED, CAMS-GLOB-ANT) interact with AOD nudging? Are emissions turned off during AOD nudging, or do both contribute?
- Is the modal_aer_opt.F90 modification (public binterp) sufficient, or are other modules needed for accurate AOD computation from Qaer?


## Carry forward vs discard

- Keep the FCnudged compset definition concept (HIST_CAM60%CCTS1%NUDG allowing met+AOD nudging together). The CESM compset framework is well-integrated.
- Retain the relaxation-nudging physics: F_nudge = alpha*(Target-Model)/TimeScale is standard and interpretable (equivalent Newtonian cooling timescale). Document equation clearly in rewrite.
- Reuse observation data structure: /glade/work/tvmora/MODIS_VIIRS_AOD/{year}/{month}/ with 3-hourly files is well-organized. No need to move it.
- Keep namelist control strategy (nudging_AOD_nl in user_nl_cam) but rationalize parameter set: remove redundant coefficients, add uncertainty bounds, clarify forcing options. Use XML schema for validation.
- Retain MERRA2 met-nudging alongside AOD nudging (it works and is documented). Just ensure thermodynamic consistency in radiative feedback.
- Use modal_aer_opt optical property module as-is; just ensure binterp can be called to compute AOD from predicted Qaer. No need to rewrite radiative transfer.
- Document the AOD inversion algorithm clearly: given observed AOD(lambda), compute Qaer for 27 MAM4 species to match AOD, subject to:  (1) mass conservation, (2) RH-dependent water uptake, (3) refractive indices, (4) optical closure. Show equations and cite references (e.g., Fast et al. 2006 for MAM, Köhler theory, optical property tables).
- Adopt version control (git) for all source mods, branching by algorithm variant (e.g., feature/qaer-inversion-v1, feature/kohler-deliquescence) rather than file proliferation. One canonical nudging_AODs.F90 per release.
- Create unit tests for: (1) AOD inversion (input Qaer, compute AOD, check spectral consistency), (2) namelist parsing, (3) file I/O (read MODIS netCDF), (4) windowing functions.
- Discard: the 80 variants of nudging_AODs (keep only the final/best one), the multiple CESM checkouts (consolidate to cesm2.2.2 + git), the ad-hoc shell scripts (replace with reproducible Python/Bash workflow with logged parameters).
