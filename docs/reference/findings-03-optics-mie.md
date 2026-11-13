# Aerosol Optics (Mie_io)

> Subsystem: **Aerosol Optics (Mie Scattering and AOD Calculation)**  ·  source: prior attempt at `/glade/work/tvmora`

## Summary

The subsystem computes aerosol optical depth (AOD) by integrating Mie scattering coefficients across vertical layers for 14 shortwave (SW) spectral bands. Main workflow: (1) Pre-computed Mie coefficient tables (extpsw, abspsw, asmpsw) are read from NetCDF physprop files for 4 MAM4 modes; (2) Wet refractive indices are calculated from component mass fractions and hygroscopic growth via Kohler approximation with B-coefficients; (3) Chebyshev polynomial interpolation (5 coefficients) evaluates optical properties as function of wet radius and refractive index; (4) Layer extinction (pext, m2/kg_aerosol) is integrated over layer mass to get optical depth (dopaer = pext * mass); (5) Vertical integration yields column AOD. The system was designed for nudging aerosol constituents toward MODIS/VIIRS observations but underwent many iterations with 23 versions of modified modal_aer_opt code, indicating significant technical turbulence. Nudging computes model-AOD from constituent masses and scales profiles by target-AOD/model-AOD ratio. Visible (550 nm, idx_sw_diag), UV (350 nm), and NIR (880 nm) are primary diagnostic wavelengths.


## Key files

| Path | Role | ~Lines |
|---|---|---|
| `/glade/work/tvmora/cesm2.2.2/components/cam/src/physics/cam/modal_aer_opt.F90` | Primary optics engine: modal_aero_sw subroutine (lines 462-1185) computes tauxar (extinction optical depth), wa (single-scattering albedo), ga (asymmetry), fa (forward fraction) for all 14 SW bands. Implements Ghan & Zaveri 2007 Chebyshev parameterization with 5-coefficient tables. Also read_water_refindex (line 1449) loads water refractive indices from NetCDF. binterp (line 1552) performs bilinear interpolation in (refr, refi) space using Chebyshev basis. | 1100 |
| `/glade/work/tvmora/CAM_modifications/nudging_AOD_2.F90` | Nudging harness: water_uptake_mam4 (line 2570) calculates wet radii and hygroscopic growth for 4 MAM4 modes using B-coefficients. aerosol_sw_properties (line 2957) replicates modal_aero_sw logic but simplified: uses binterp to get cext/cabs/casm, applies Chebyshev basis, computes dopaer = pext * mass, accumulates Computed_AOD (only at idx_sw_diag visible band). qaer_target_mam4 (line 3238) scales Model_Qaer by AOD_ratio = Target_AOD / Computed_AOD. | 2750 |
| `/glade/work/tvmora/Mie_io/mam4_mode1_larc_c000000.v2.nc` | Precomputed Mie table NetCDF: contains ncoef=5 Chebyshev coefficients for extinction (extpsw), absorption (abspsw), asymmetry (asmpsw) across prefr=7 real-index and prefi=10 imaginary-index grid points, for all nswbands=14 SW bands and 4 modes. Files derived from LARC database. Accessed via rad_cnst_get_mode_props interface. | 0 |
| `/glade/work/tvmora/CAM_modifications/aer_rad_props_FL_interface_complete.F90` | Modified aer_rad_props module to output all 14 SW-band optical properties (tau_1 through tau_14, tau_w_1 through tau_w_14, tau_w_g_1 through tau_w_g_14) to history files for Fu-Liou RTM. Calls modal_aero_sw to compute base optics, then outputs band-by-band diagnostics. | 1009 |


## Technical findings

- AOD computed only at visible wavelength (idx_sw_diag, nominally 550 nm): binterp interpolates in (refr, refi) space using 5-coefficient Chebyshev basis. Single-band approach with line 3129 in nudging_AOD_2: do isw = idx_sw_diag,idx_sw_diag (fixed visible only).
- Mie coefficient lookup uses prefr=7 real-index and prefi=10 imaginary-index grid points from LARC tables (ncoef=5 Chebyshev coefficients). Size parameterization: radsurf = 0.5 * dgnumwet * exp(2*log(sigma)^2) where dgnumwet is wet number mode diameter and sigma_logr_aer is geometric std dev (1.6 or 1.2 per mode).
- Hygroscopic growth via Kohler: rwet_mode = rdry_mode * (1 - B / ln(RH))^(1/3) where B=B0 + B1*RH + B2*RH^2, RH truncated at 0.99 to avoid singularities (line 2812 in nudging_AOD_2). Parameters: B_su=[2.43, -3.85, 1.88], B_ss=[4.83, -6.92, 3.28], B_bc/pom/soa/du=[small/zero]. From Ghan and Zaveri 2007.
- Wet refractive index from volume mixing: crefin = sum(vmr_spec * n_spec) / wetvol, then crefin += watervol * crefwsw(isw) / wetvol (line 819 in modal_aer_opt.F90). Pure water refractive index (crefwsw) read from water_refindex_file (NetCDF) with real and imaginary parts for each SW band.
- Layer optical depth calculation: dopaer = pext * mass where pext is parameterized specific extinction in m2/kg (from Chebyshev + cext coefficients), mass = pdeldry * rga is layer air mass (kg/m2). Column AOD sums dopaer over vertical levels (line 901 in modal_aer_opt.F90: aodvis(i) = aodvis(i) + dopaer(i)).
- Mie_io directory contains 4 netCDF files (mam4_mode[1-4]_larc_c000000.v2.nc), each ~28 MB, with coefficients indexed by [refractive_index_real, refractive_index_imag, coefficient_index, sw_band]. Accessed via rad_constituents module interface (not directly by optics code).
- Nudging code computes AOD_ratio = Target_AOD / Computed_AOD (line 3254 in nudging_AOD_2) to scale constituent profiles. Target_AOD read from observation files; Computed_AOD computed in-model. Scaling applied to all 27 aerosol advected constituents per mode: Target_Qaer(i,:,l,lchnk) = AOD_ratio(i,lchnk) * Model_Qaer(i,:,l,lchnk) (line 3266).


## Problems / why it's a mess

- Multiple modal_aer_opt implementations (23 versions in Force_AODs directory alone, plus variants in aod_weighted_mean and forced_modules) indicate unresolved technical disagreements or incomplete convergence. No single canonical version maintained.
- Nudging code duplicates significant modal_aer_opt logic (water_uptake_mam4, aerosol_sw_properties) rather than calling the library function. This creates maintenance burden and risk of divergence between nudging-computed-AOD and radiation-computed-AOD.
- Refractive index hard-coded in nudging code (lines 2605-2611 at 550 nm only) rather than read from physics buffer. If radiation uses different values or applies wavelength-dependence, nudging optics will be inconsistent.
- Chebyshev parameter space (xrmin, xrmax) based on min/max wet radii (0.01 to 25 micrometers) is wide; normalization to [-1, 1] may lose precision in small-particle (Aitken) regime where AOD is sensitive.
- RH truncation at 0.99 (line 2632, RH_cutoff) is crude; avoids ln(RH) singularity but introduces discontinuity. Kohler equation valid only below cloud base; above cloud (RH > saturation) behavior undefined.
- Vertical integration of optical depth does not account for aerosol subgrid variability within layers or correlated spectral dependence; assumes independent band contributions and layer-mean properties.
- Nudging only operates on advected constituent masses (27 fields in MAM4), not directly on optical properties, so mismatches in mode size distribution assumptions between nudging and radiation modules are not corrected.
- No explicit test that model-computed-AOD and MODIS-AOD use identical wavelengths, viewing geometry (nadir vs. zenith-angle dependent), or aerosol-size assumptions. AOD_ratio scaling is empirical without physical justification.


## Open questions

- What is the canonical version of modal_aer_opt intended for final production? Which of the 23 versions in Force_AODs is actually used in simulations?
- Are the hard-coded refractive indices in nudging_AOD_2 (n_su, n_bc, etc. at 550 nm) consistent with those in LARC Mie tables or derived independently?
- Does the nudging code account for diurnal cycle effects in RH and hygroscopic growth, or does it use fixed daily-mean RH when computing wet radii?
- How sensitive is Computed_AOD to the Chebyshev parameter space normalization? Are Aitken-mode particles (0.01-0.1 micrometers) adequately resolved?
- What is the relationship between Target_AOD (from MODIS/VIIRS), model-native AOD (from radiation), and nudged-AOD? Is there feedback to radiation or only to advected constituents?
- Are the 4 Mie tables in /glade/work/tvmora/Mie_io consistent with the CESM2.2.2 modal_aer_opt defaults, or custom-generated? What is the source and citation?
- Does aerosol_sw_properties in nudging code apply the same top_lev truncation as modal_aero_sw to avoid using optical properties above a specified level?


## Carry forward vs discard

- The core Mie-table-based optics approach (Ghan & Zaveri 2007) is sound and well-documented in scientific literature. LARC tables are standard in CESM. Keep the Chebyshev parameterization and bilinear interpolation framework.
- Wet-radius calculation via Kohler approximation with B-coefficients is established and implementable; ensure RH inputs are consistent across modules and that saturation is handled properly.
- Separation of nudging logic (water_uptake_mam4, aerosol_sw_properties, qaer_target_mam4) into a standalone module is functional but should be refactored to call modal_aer_opt library functions directly rather than reimplementing. This reduces code duplication and maintenance risk.
- For a clean rewrite: (1) standardize on a single, well-tested modal_aer_opt version (use cesm2.2.2/components/cam/src/physics/cam/modal_aer_opt.F90 as baseline); (2) document refractive-index sources and wavelength assumptions; (3) ensure nudging optics match radiation optics by using shared library calls; (4) add diagnostics to track Computed_AOD vs. Target_AOD convergence; (5) validate against AERONET or collocated aircraft measurements.
