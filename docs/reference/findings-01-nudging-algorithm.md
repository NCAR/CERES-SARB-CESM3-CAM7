# Nudging Algorithm (Science)

> Subsystem: **AOD Nudging/Forcing Algorithm for CESM2.2 CAM6-MAM4**  ·  source: prior attempt at `/glade/work/tvmora`

## Summary

The codebase implements an experimental AOD nudging/forcing system to assimilate MODIS-VIIRS observations into CESM2.2's CAM6 atmospheric chemistry model using the MAM4 (4-mode modal aerosol model). The system applies a multiplicative scaling approach: model aerosol mass mixing ratios for all 27 MAM4 species are scaled by AOD_ratio = (Observed_AOD / Computed_AOD) at each grid cell, then the target aerosols replace the model state directly (forced mode). Optionally, Newtonian relaxation can be applied instead. The observed AOD is matched at 550 nm by computing aerosol optical depth from model fields using Mie scattering parameterizations that account for relative-humidity-dependent growth and wet refractive indices. The system includes sophisticated windowing to apply nudging only in specified spatial regions and vertical layers using parameterized Heaviside functions. Time interpolation between observation snapshots is available, and the nudging strength is controlled per-species via a 27-element coefficient vector. Entry points are triggered from CAM's physics package, with state updates every model timestep but data file refreshes only when observation files are available (avoiding assimilation gaps).


## Key files

| Path | Role | ~Lines |
|---|---|---|
| `/glade/work/tvmora/CAM_modifications/nudging_AODs.F90` | Primary AOD nudging module. ~3300 lines. Core implementation with all subroutines: nudging_AOD_readnl (namelist), nudging_init_AOD, nudging_timestep_init_AOD (data updates & target computation), nudging_timestep_tend_AOD (state forcing/nudging), nudging_update_analyses_fv (file I/O), water_uptake_mam4 (hygroscopicity & wet radius), aerosol_sw_properties (AOD computation), qaer_target_mam4 (ratio calculation), relative_humidity (Magnus formula-based RH from q,T,p). | 3300 |
| `/glade/work/tvmora/CAM_modifications/nudging-forced-simplified.F90` | Alternate/predecessor implementation. Similar structure but with integrated U,V,T,Q,PS nudging + AOD forcing. Documents original control-flow design. | 3500 |
| `/glade/work/tvmora/CAM_modifications/nudging_AOD_2.F90` | Another variant iteration of the AOD-only nudging module. | 3000 |


## Technical findings

- Algorithm: Multiplicative scaling approach. Target_Qaer(i,k,l) = AOD_ratio(i) × Model_Qaer(i,k,l) for all 27 species l at cell i, level k. AOD_ratio = Target_AOD / Computed_AOD, clipped to 1.0 if Computed_AOD ≤ 0.01 or Target_AOD < 0. Line 3292 in nudging_AODs.F90.
- Forcing modes: Option 1 (default): direct replacement, phys_state%q(...,idxaer(kaer)) = Target_Qaer(...) at line 1907. Option 2 (commented): Newtonian relaxation via tendency: phys_tend%q = Nudge_Qaer_step = Tscale × Nudge_Qaer_tau × (Target - Model). Both options available via Nudge_AOD_Force_Opt parameter (0=NEXT-OBS, 1=LINEAR interpolation between obs times).
- AOD computation at 550 nm (visible): Uses aerosol_sw_properties subroutine (line 2983). Loops over isw=idx_sw_diag (fixed to visible). For each mode m and level k: calls binterp() to interpolate extinction coefficient cext(i,ncoef) from lookup tables parameterized by wet refractive index (real & imaginary parts). Computes pext (m²/kg) via Chebyshev polynomial expansion in log(radius). Multiplies by vmr_wet × ρ_water to get aerosol extinction. Sums dopaer(i,k,m) = pext × layer_mass over all modes and levels to get Computed_AOD.
- Wet radius growth: Computed via Köhler theory (Ghan & Zaveri 2007 Eq. 2). r_wet = r_dry × [1 - B/ln(RH)]^(1/3), where B = bulk hygroscopicity parameter (Eq. 5: B = Σ(B_i × V_i) / Σ(V_i)). B_i coefficients are species-specific (sulfate B≈2.4, sea-salt B≈4.8, organics B≈0.14, BC B≈0.01). RH capped at 0.99 to avoid ln(RH→1) singularity. Lines 2816-2860.
- Relative humidity: Magnus formula from D. Fillmore. RH = (p × q) / (ε × e_s0 × exp(17.67×(T-273.15)/(T-29.65))), where ε=0.622, e_s0=611.2 Pa. Clipped to ≤1. Line 2470-2471. Also stores ln(RH) for downstream use.
- Wavelength: Fixed to 550 nm (visible) via isw=idx_sw_diag. Refractive indices stored in tables for each component at 550 nm: water n=(1.333, 1.96e-9), sulfate (1.43, 1e-8), POM (1.53, 0.006), BC (1.75, 0.44), dust (1.22, 0.021), sea-salt (1.5, ~0). Line 2629-2637.
- Species distribution: Scaling applied uniformly across all 27 advected MAM4 species: SO4_a1/a2/a3, POM_a1/a4, SOA1-5_a1/a2, BC_a1/a4, DST_a1/a2/a3, NCL_a1/a2/a3, NUM_a1/a2/a3/a4. No selective tuning per-mode or per-species; all are scaled by same cell-level AOD_ratio. Array idxaer(27) maps to constituent indices at line 1508-1511.
- Vertical distribution: Scaling applied at every vertical level k independently (pver=72 or similar). No vertical-average scaling. Target_Qaer(i,k,l) computed for all k simultaneously.
- Timescales: Nudge_AOD_Step = 86400 / Nudge_Times_Per_Day_AOD (e.g., 4 obs/day → 21600 sec). Model update frequency Model_AOD_Step = 86400 / Model_Times_Per_Day_AOD (e.g., 48 updates/day → 1800 sec). Tscale conversion factor for Newtonian tendencies set via nudge_timescale_opt_AOD: 0→1/Tdlt_Anal, 1→Nudge_AOD_Step/DeltaT_current. Line 1756-1768.
- Spatial masking: Heaviside window function with 6 parameters: Nudge_AOD_Hwin_lat0/lon0 (center), latWidth/lonWidth (half-width), latDelta/lonDelta (transition sharpness). Vertical window: Nudge_AOD_Vwin_Lindex/Hindex (low/high level), Ldelta/Hdelta (transition length). Computed via tanh() smoothing, scales Nudge_Qaer_tau by window value ∈[0,1]. Lines 328-346, 1233-1243.
- Nudging coefficient: Array Nudge_Qaer_coef(27) provides per-species scaling of relaxation strength α ∈[0,1]. Default all=0 (off). Multiplies Nudge_Qaer_tau after profile windowing. Line 302, 503.
- Data input: Reads NetCDF file with 'aod_weighted_mean' variable (2D: lon × lat) at each time. File naming template allows %y,%m,%d,%s substitution. scatter_field_to_chunk() distributes file data to model chunks. Line 2113, 2157-2158.
- Clear-sky/masking limitations: No explicit clear-sky mask applied. Target AOD used directly if valid (≥0). No daytime-only restriction or quality-flag checks mentioned in code.
- Observation-model wavelength mismatch: Assumed none—both obs and model calculations use 550 nm. No spectral conversion or cross-wavelength corrections.
- Hygroscopic growth accounting: Fully incorporated. Wet radius explicitly computed, feeds into refractive index lookup, which affects extinction coefficient via Chebyshev expansion. RH-dependent pathway is end-to-end: RH(q,T,p) → B(RH) → r_wet(r_dry,B,RH) → n_wet(composition, r_wet) → σ_ext(n_wet) → AOD.


## Problems / why it's a mess

- Algorithm mismatch with traditional AOD assimilation: The multiplicative scaling (AOD_ratio × species) is a crude approximation. It assumes all aerosol size distributions and compositions scale uniformly with a single scalar. In reality, different modes (Aitken vs. accumulation) have different optical properties; scaling accumulation-mode sulfate ×2.5 may not be equivalent to scaling Aitken-mode BC ×2.5. No mode-selective or composition-selective adjustment.
- No vertical distribution inversion: Scaling is uniform in altitude. Observed column AOD tells you total load, but aerosol altitude profile is not constrained. Nudging masses at all levels equally may not match the actual vertical distribution of the discrepancy.
- RH formula robustness: Magnus approximation (line 2470-2471) is empirical and valid ~0–50°C. For polar regions or stratosphere, accuracy degrades. No saturation adjustment or phase change handling (ice vs. liquid); RH clipped to 1 but no explicit supersaturation treatment.
- Wet radius singularity risk: r_wet = r_dry × [1 - B/ln(RH)]^(1/3). As RH→1, ln(RH)→0, ratio B/ln(RH)→∞. Capping RH at 0.99 helps but is ad hoc. If model generates RH>0.99 in high-humidity regions, forced use of RH_cutoff=0.99 in Brd calculation (line 2837-2838) creates discontinuities.
- Lookup table interpolation: binterp() uses bilinear interpolation in (refr, refi) space to get Chebyshev coefficients. No error handling for out-of-bounds refractive indices. If model-computed wet n falls outside table domain, no fallback or warning (apart from geometric optics limit at line 3224).
- No uncertainty or observational error weighting: All observed AOD treated as equally valid. No per-pixel quality flags, cloud masking, or uncertainty estimates. Noisy / unreliable MODIS pixels forced identically to good ones.
- Accumulation of errors: Scaling factors applied every model timestep. If nudging strength is weak (α<0.5), error accumulation is slow; if α→1 (direct forcing), can create discontinuities in aerosol mass rates. No damping or relaxation to prevent overshoot.
- Spectral mismatch not handled: If MODIS uses band 1 (620-670 nm) or band 3 (459-479 nm) instead of 550 nm, no spectral conversion is applied. Observational wavelength must match assumed 550 nm or results are biased.
- File gap handling: If an observation file is missing, nudging is shut off (line 1628-1632). This can leave model free-running (no constraints) for hours, allowing drift. No gap-filling or background-error propagation.
- Namelist complexity: 20+ parameters for window functions, timescales, paths. Easy to misconfigure. No validation that Nudge_AOD_Hwin_latWidth >> Nudge_AOD_Hwin_latDelta; if not, window transitions are ill-defined.
- Hard-coded parameters: Hygroscopicity B-coefficients (lines 2647-2652), refractive indices (lines 2631-2637), density values (lines 2640-2645) are embedded constants. No ability to vary for different aerosol/climate regimes without recompiling.
- Limited vertical structure: Window function uses model-level indices directly, not physics-based scales (e.g., PBL height, tropopause). Difficult to target nudging to boundary layer or free troposphere adaptively.
- No feedback to radiation: While aerosol_sw_properties() computes extinction and AOD, the radiative transfer code (CAM's rrtmg) uses its own aerosol optics. Modified masses may not immediately affect shortwave fluxes if rrtmg uses cached fields or is called on a different cadence.
- Memory overhead: Allocates large arrays (Nobs_Qaer 5D: pcols×pver×27×nchunk×Nudge_NumObs; Computed_AOD; cext/cabs/casm/dopaer/...). For high-resolution runs, this balloons. No adaptive pruning of old observation files.
- Computational cost: Calls aerosol_sw_properties() inside nudging_timestep_init_AOD at every update (Model_Times_Per_Day_AOD times/day), which loops Mie scattering calculations. For 96 updates/day, significant overhead.
- Code organization chaos: Multiple versions (nudging.F90, nudging_AODs.F90, nudging-forced.F90, nudging-forced-simplified.F90, nudging_AOD_2.F90, etc.) in the same directory. Unclear which is 'canonical.' Many subroutines commented out or duplicated. Test versions mixed with production code (nudging_test_*.F90 files).
- No scientific validation: No comparison to standalone Mie calculations or published aerosol optics tables. Water uptake model is Ghan & Zaveri 2007, but which version? No cite to specific paper version or validation against observations.
- Partial implementation of Newtonian option: Code structure allows Nudge_AOD_Force_Opt & Nudge_TimeScale_Opt, but only FORCING (direct replacement) is active in nudging_timestep_tend_AOD (line 1907 uncommented, line 1906 commented out). Relaxation code is present but disabled.
- No ensemble/DA integration: Nudging is deterministic, offline. No EnKF, 4DVar, or OI framework. Single best-guess target; no error covariance structure or background constraint.


## Open questions

- Is the multiplicative scaling (AOD_ratio × Q_all_species) scientifically justified for MAM4? Does this approach preserve the relative contributions of accumulation vs. Aitken vs. coarse modes?
- How is Computed_AOD validated? Is there a pre-nudging comparison (model AOD vs. MODIS AOD) to demonstrate the magnitude of required adjustments?
- What is the intended deployment context—climate run initialization, process study, or real-time forecast? Does the system aim for short-term accuracy or long-term climate statistics?
- Why are multiple implementations (nudging_AODs.F90, nudging.F90, nudging_AOD_2.F90) present? Which is the 'official' version? Were they alternatives under testing?
- What is the observational source (MODIS, VIIRS, blend)? Is there QA/QC applied to aod_weighted_mean before it reaches the model, or is that done upstream?
- How are aerosol density ρ values (1.7e3 kg/m³ for sulfate, etc.) chosen? Are they tuned to MAM4 specifically or inherited from a reference?
- Is there interaction with other aerosol nudging schemes (e.g., prescribed emissions, AOD climatology) in the same run? Potential double-counting?
- What resolution do the MODIS/VIIRS files have (3×3 km, 10×10 km, regridded to model grid)? Does interpolation introduce artifacts?
- How sensitive is the result to the choice of Nudge_Qaer_coef values? Is there a tuning guideline or sensitivity study?
- Does the system account for aerosol-cloud interactions (ACIs)? i.e., does nudging aerosol mass also update cloud CCN/INP properties, or are clouds computed independently?
- Are there validation plots (scatter plots of model vs. obs AOD before/after nudging) in any publications or internal reports?
- What is the computational performance impact? e.g., % of CAM runtime spent in aerosol optics loops within nudging_timestep_init_AOD?
- How does the system behave when Computed_AOD = 0 (e.g., in polar winter)? Division by zero is guarded (line 3276) but what is the physical consequence of setting AOD_ratio=1?
- Is there a plan to upgrade to MAM7 or extend to other aerosol models?


## Carry forward vs discard

- **Reuse the water uptake (Köhler) logic**: The hygroscopicity parameterization (Eq. 5) and wet-radius formula (Eq. 2-3) are physically sound. Keep the B_mode aggregation, RH clipping, and r_wet computation. Consider parametrizing B_coefficients as namelist inputs instead of hard-coded.
- **Reuse the Mie/optical lookup infrastructure**: The binterp() bilinear interpolation in (refr, refi)→optical coefficients is efficient. Keep the Chebyshev polynomial acceleration for extinction, absorption, asymmetry. Just verify against rad_constituents tables.
- **Extract and simplify the windowing logic**: Heaviside window (tanh-based smooth step) with horizontal (lat/lon) and vertical (level) components is elegant. Separate from AOD-nudging specifics and make it a standalone module for reuse.
- **Validate/fix the RH Magnus formula**: Consider upgrading to Alduchov-Eskridge or August formulas for broader temperature range. Or integrate with CAM's internal saturation vapor pressure routines if they exist.
- **Decide on Newtonian vs. forcing**: The codebase supports both (structures in place, Nudge_TimeScale_Opt parameter). Complete the implementation of relaxation mode and benchmark both. Document the pros/cons.
- **Design obs quality control**: Add flags/masks for cloud contamination, granule edges, QA values. Either pre-filter in data-prep or add QC logic to nudging module.
- **Clarify vertical distribution**: Decide whether to enforce vertical profiles (e.g., scale each layer by mode-averaged AOD_ratio, or apply altitude weighting). Current uniform scaling may be too crude.
- **Consolidate versions**: Choose one canonical nudging_AODs.F90 (or nudging.F90 if including U,V,T,Q). Archive old variants as _backup. Clean up test code (nudging_test*.F90).
- **Document assumed observations**: Specify MODIS/VIIRS product version, wavelength, resolution, preprocessing steps (regridding, averaging, QC). Version-lock this to make science reproducible.
- **Benchmark against satellite climatology**: Compare nudged model AOD time series to independent satellite (e.g., AERONET, CALIOP) to assess skill.
- **Parameterize species/mode selectivity**: Instead of uniform scaling, allow per-mode or per-species weighting factors in Target_Qaer calculation. Requires inverse problem (solve for species adjustments given observed AOD), but more scientifically principled.
- **Performance: Consider lazy evaluation**: Only compute aerosol optics when observation data updates (not every model timestep). Store Computed_AOD & aodratio for reuse between nudging updates.
