# Observation Data Pipeline (MODIS/VIIRS)

> Subsystem: **MODIS/VIIRS AOD Observation Data and Its Preparation for CESM2.2.2 CAM6-MAM4**  ·  source: prior attempt at `/glade/work/tvmora`

## Summary

The tvmora codebase represents a prior attempt to add MODIS/VIIRS aerosol optical depth (AOD) nudging to NCAR CESM2.2.2 CAM6 with MAM4 modal aerosols. The core observation data pipeline consists of: (1) raw Level-2 swath VIIRS NOAA-20 AERDB files (product AERDB_L2_VIIRS_NOAA20; dimensions Idx_Atrack=402, Idx_Xtrack=400) and MODIS Terra/Aqua data (implied but not directly in the archive), (2) a bias-corrected intermediate VIIRS product (md08_d3 naming, 192x94 grid, hourly), and (3) final gridded 3-hourly AOD files at f09 resolution (192x288 grid; 0.9375°x1.25° lat-lon) spanning 2000-2025, stored as individual netCDF files with filename pattern MODIS_ta_VIIRS_noaa20_3hr_lat192xlon288.YYYYMMDD.SSSSS.nc where SSSSS is seconds-of-day. The gridded files contain a single variable aod_weighted_mean_modis (or aod_weighted_mean for certain years) representing column AOD at 550 nm with fill value -999, plus coordinate and weight metadata. The model reads these files via the nudging_AODs.F90 module, expecting a file template pattern with %y%m%d.%s placeholders and a path specifiable per year. A critical data-prep workflow exists but is not documented in the codebase: raw Level-2 VIIRS swaths must be (a) regridded to the f09 grid, (b) merged with MODIS (Terra & Aqua), (c) aggregated to 3-hourly means, and (d) corrected for sensor bias (evidenced by separate VIIRS_original and VIIRS_corrected directories with distinct grids and product names). The original/corrected distinction suggests inter-sensor harmonization or post-launch calibration adjustment, but the specific bias-correction algorithm is not archived.


## Key files

| Path | Role | ~Lines |
|---|---|---|
| `/glade/work/tvmora/MODIS_VIIRS_AOD` | Primary AOD data archive (2000-2025), final regridded and aggregated 3-hourly files at f09 (192x288) resolution. Files named MODIS_ta_VIIRS_noaa20_3hr_lat192xlon288.YYYYMMDD.SSSSS.nc or terra_modis_npp_viirs_3hr_lat192xlon288.YYYYMMDD.SSSSS.nc | 0 |
| `/glade/work/tvmora/VIIRS_original` | Raw Level-2 VIIRS NOAA-20 AERDB swath files (AERDB_L2_VIIRS_NOAA20.AYYYYDDD.HHMM.002.YYYYDDDHHMMSS.nc), dimensions Idx_Atrack=402 x Idx_Xtrack=400, containing raw retrieval data: Aerosol_Optical_Thickness_550_Land, Aerosol_Optical_Thickness_550_Ocean, Aerosol_Optical_Thickness_550_Land_Ocean variants with QA flags | 0 |
| `/glade/work/tvmora/VIIRS_corrected` | Intermediate bias-corrected VIIRS product (md08_d3.YYYYDDD.HH.nc format), 192x94 grid, hourly resolution, single variable tau_avg. Represents post-calibration or inter-sensor harmonization step prior to regridding | 0 |
| `/glade/work/tvmora/VIIRS/2022` | Organized by day-of-year subdirectories (002, 003, ..., 365) containing Level-2 swath VIIRS AERDB files per day, used for archive/staging | 0 |
| `/glade/work/tvmora/CAM_modifications/nudging_AODs.F90` | Core CAM nudging module that reads gridded AOD files and applies relaxation forcing. Subroutine nudging_update_analyses_fv() opens files, reads dimensions (nlon=288, nlat=192), and extracts aod_weighted_mean variable into Qtrans 2D array | 171000 |
| `/glade/work/tvmora/CAM_modifications/Force_AODs/nudging_AODs.F90` | Alternative/updated forcing module for AOD nudging with qaer-based target transformations | 150000 |
| `/glade/work/tvmora/CAM_scripts/Derecho_CESM_scripts/Forcing_AODs_NE.csh` | Example CESM setup script showing how AOD nudging is configured: sets nudge_path_Qaer, nudge_file_template_Qaer, nudge_times_per_day_AOD=8 (3-hourly), nudge_timescale_opt_AOD=1 | 1000 |
| `/glade/work/tvmora/Mie_io` | Aerosol optical properties (mam4_mode*.v2.nc files ~29MB each) used to convert model aerosol mass to AOD for comparison with observations | 0 |


## Technical findings

- Products and sources: VIIRS L2 swath AERDB product (NOAA-20 satellite; dimensions 402x400 native swath). MODIS data referenced in filenames but raw MODIS L2 files not found in archive; likely pre-processed externally and merged. Temporal coverage: Jan 2000 to Dec 2025 (26 years). Temporal cadence: 3-hourly (8 files/day) in final archive; raw VIIRS has ~14 swaths/day at ~6min intervals (0000, 0006, 0012, 0018, 0024, 0030, 0036, 0042, 0048, 0136, 0142, 0148, 0154, 0200, 0206, 0212, 0218, 0224, 0230 hours observed in 2022 data)
- Spatial grids: Raw VIIRS: native swath 402(along-track) x 400(cross-track) pixels. Intermediate VIIRS_corrected: 192x94 grid (possibly SRTM or intermediate regridding). Final AOD archive: f09 grid 192(lat) x 288(lon) = 0.9375° lat x 1.25° lon, global. Coordinates stored as 1D arrays lon(lon), lat(lat) with cell boundaries lon_min/max, lat_min/max and weights wght(lat) for area averaging
- Variables: Raw VIIRS has Aerosol_Optical_Thickness_550_Land (Deep Blue over land, -999 fill), Aerosol_Optical_Thickness_550_Ocean (SOAR over ocean), Land_Ocean merged product, plus QA_Flag (values 0=no retrieval, 1=poor, 2=moderate, 3=good), valid_range [0, 5]. Intermediate: tau_avg (fill=-999). Final: aod_weighted_mean_modis or aod_weighted_mean (float), fill=-999. No wavelength dimension in final files; 550nm implied by variable naming
- Wavelength: 550 nm (implicit; inferred from variable names Aerosol_Optical_Thickness_550_*)
- QA handling: VIIRS L2 includes QA_Flag_Land, QA_Flag_Ocean (0-3 scale). Final gridded product no explicit QA array; implies QA filtering applied during regridding/weighting
- File naming patterns: (1) Raw VIIRS: AERDB_L2_VIIRS_NOAA20.A{YYYYDDD}.{HHMM}.002.{YYYYDDDHHMMSS}.nc. (2) Intermediate: md08_d3.{YYYYDDD}.{HH}.nc. (3) Final: MODIS_ta_VIIRS_noaa20_3hr_lat192xlon288.{YYYYMMDD}.{SSSSS}.nc or terra_modis_npp_viirs_3hr_lat192xlon288.{YYYYMMDD}.{SSSSS}.nc, where SSSSS = seconds-of-day [0, 10800, 21600, 32400, 43200, 54000, 64800, 75600] (3-hourly 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 UTC)
- Time metadata in files: jdate (julian date), date (YYYYMMDD), syear (start year), sday (start day-of-year), shour, smin (start), ehour, emin (end); allows reconstruction of temporal bounds
- Data aggregation: aod_weighted_mean implies spatial average within 3-hourly window; aod_count variable present in some years (e.g., TA_only subdirectory) suggests number of valid observations per grid cell
- VIIRS bias-correction story: VIIRS_original contains raw L2 swaths; VIIRS_corrected contains md08_d3 product at different grid (192x94), suggesting post-launch bias adjustment or harmonization with MODIS. md08 likely refers to a specific VIIRS aerosol product variant (Deep Blue or DarkTarget). Exact algorithm not documented; likely external processing step (possibly LAADS DAAC or similar consolidation)
- Model interface: nudging_AODs.F90 module expects files indexed by (year, month, day, second). At each model timestep, code calls nudging_update_analyses_fv(aer_file) to open the file, read lon(288), lat(192), aod_weighted_mean(192,288), and scatter to chunks. Forcing formula: F_nudge = Alpha * (Target_AOD - Model_AOD) / timescale, where Alpha in [0,1], timescale from Nudge_Timescale_Opt_AOD, Target_AOD from aod_weighted_mean. Windowing: horizontal (lat/lon-based) and vertical (model-level indices) Heaviside window functions controllable via namelist
- File size pattern: ~248 KB per file in early years (2000-2020); ~1.1 MB per file in 2010 backup; ~465 KB in TA_only variant (2020). Suggests either different compression, data density, or variable count. Total archive ~2.7 MB for cesm_tree.txt index alone indicates multi-terabyte archive
- Year-specific variations: 2020 has TA_only subdirectory with terra_modis_npp_viirs naming (~465 KB files), suggesting data source or processing variant. 2010 has backup_old subdirectory with 1.1 MB files and all/terra/ subdirectory with matching filename format, implying versioning/QC history


## Problems / why it's a mess

- Data-prep pipeline not archived: Raw VIIRS L2 acquisition, MODIS L2 acquisition, regridding algorithm, aggregation/weighting scheme, and bias-correction method are external to this repo. Only input (VIIRS_original L2 swaths) and final output (MODIS_VIIRS_AOD gridded) exist; intermediate steps missing. Operator cannot reproduce the gridded product from scratch without external documentation
- VIIRS/MODIS merge logic unclear: Files named MODIS_ta_VIIRS but raw MODIS files not in archive. How are Terra, Aqua, NOAA-20 data merged? Precedence rules? Cloud screening? Ambiguity in aod_weighted_mean definition (simple mean? quality-weighted? gap-filled?)
- Bias-correction story fragmented: VIIRS_original (L2 swaths) and VIIRS_corrected (md08_d3 hourly product at 192x94 grid) are disconnected in the archive with no linking script or documentation. md08_d3 product naming and its relationship to standard VIIRS/LAADS products unknown. Grid mismatch (402x400 native → 192x94 intermediate → 192x288 final) with no transformation scripts
- Missing metadata: Final gridded files lack source dataset attribution, QA filter thresholds, weighting method, observation count, or uncertainty fields. aod_weighted_mean variable has no long_name, units, or description attributes beyond fill value. Historical vs. real-time data unclear (are 2023-2025 files final or provisional?)
- Multiple file name patterns and versions: MODIS_ta_VIIRS_noaa20 vs. terra_modis_npp_viirs naming variants in different years/subdirectories; TA_only variant in 2020; backup_old in 2010. No master registry or data lineage. Model namelists require year-specific path adjustments (nudge_path_Qaer with $sYYYY placeholder)
- Incomplete MODIS archive: No dedicated MODIS data directory despite MODIS being primary source 2000-2020. Unclear if MODIS L2 preprocessing happens externally (LAADS download?) or if MODIS is already merged into the gridded product without separation
- Kohler aerosol water uptake experiments: Force_AODs/Kohler/ contains 10+ variants of nudging_AODs_qaer_modis_kohler_*.F90, suggesting multiple attempts at water uptake parameterization without clear convergence. Latest/best version ambiguous
- Dust scheme proliferation: Force_AODs/Dust_scheme/cam/ contains 20+ variants of modal_aer_opt_*.F90 with date-stamped filenames (e.g., modal_aer_opt_AODVISdn_DF_032626.F90), indicating iterative debugging without version control clarity. DF/DF_2/DF_3 suffixes suggest incomplete deduplication
- Integration point undefined: Model reads aod_weighted_mean directly as columnar AOD. No explicit conversion to modal aerosol mass (qaer for MAM4 modes: aitken, accumulation, coarse, primary carbon). Forcing target distribution across 4 modes and 4 chemical constituents per mode (sulfate, sea salt, BC, OC, dust) not documented. nudging_AODs_qaer_modis*.F90 variants suggest multiple attempted approaches
- Temporal discontinuities: 2010 has /all/terra/ subdirectory structure; 2020 has /TA_only/ variant. Unclear if this indicates source data change (MODIS to VIIRS transition expected ~2012) or processing variants. 2023-2025 recent dates suggest ongoing data prep; finality unknown
- File count inconsistency: ~2928 files in 2000 (365 days × 8 3-hourly files = 2920 expected, but 2928 observed); ~2929 in 2020. Suggests gaps filled or leap day handling inconsistency
- CAM modifications version control chaos: Force_AOD, Force_AODs, Force_AODs_backup directories with similar contents. nudging_AODs.F90 appears in multiple locations (CAM_modifications/, CAM_modifications/aod_weighted_mean/, CAM_modifications/Force_AODs/) with different timestamps and no clear 'current' version. Multiple test/development branches (nudging_AODs_nt_*.F90, nudging_AODs_DF*.F90) without cleanup


## Open questions

- Where are the raw MODIS L2 files or intermediate MODIS-processed gridded data? The archive has VIIRS_original for VIIRS but no MODIS_original or equivalent. Were MODIS files deleted after merging? Are they on LAADS DAAC still, or permanently archived elsewhere?
- What is the md08_d3 product? Is it a LAADS DAAC standard product variant (e.g., VIIRS Level-3 binned), or custom preprocessing output? How does it differ from standard VIIRS DarkTarget/DeepBlue?
- What is the regridding and aggregation algorithm? Linear interpolation? Conservative flux? Inverse-distance weighting? How many swaths (Level-2 granules) are aggregated into a single 3-hourly file?
- What is the bias-correction between VIIRS_original and VIIRS_corrected? Offset? Slope correction? Aerosol-type-dependent? MODIS-VIIRS cross-calibration? References to literature or adjustment coefficients?
- How are Terra, Aqua, and NOAA-20 data merged when all three have observations at the same location and time? Precedence order? Simple average? QA-weighted average? Time-weighted interpolation?
- How is the aod_weighted_mean defined mathematically? Simple arithmetic mean over observations in 3-hourly window? Quality-filtered mean (QA >= threshold)? Uncertainty-weighted mean? What QA threshold (if any) is applied?
- How are missing values (fill=-999) handled in the model? Interpolation from adjacent times? Masking out? Replacement with climatology?
- Is the final gridded AOD product at 550 nm representative of the entire atmosphere (column AOD) or a specific layer (e.g., boundary layer, fine-mode only)? Are there separate files for VIIRS coarse-mode vs. fine-mode AOD, or is that distinction lost in the merge?
- Which forcing variant is 'final'? Force_AODs/nudging_AODs.F90 vs. Force_AODs/Kohler/nudging_AODs_qaer_modis_kohler.F90 vs. dozens of dated variants? Are Kohler experiments validated or exploratory?
- What is the time-axis format expected by the model? Are files indexed by start-of-period (SSSSS=00000 for 00:00-03:00 UTC window) or center-of-period?
- Why do 2010 and 2020 have variant subdirectories? Are the parent-directory files newer/better, or are variants intentional alternatives?
- Is the f09 (192x288) grid the intended CAM6 resolution for this work, or was regridding to other resolutions (ne30, ne120) also performed and archived elsewhere?


## Carry forward vs discard

- Preserve final AOD archive structure (MODIS_VIIRS_AOD/YYYY/ with 3-hourly files at f09 resolution). This is stable and working input to the model. File format netCDF with aod_weighted_mean(lat,lon) at 550nm, fill=-999, coordinates and weights is good template for new implementation
- Model interface (nudging_AODs.F90 pattern of reading files by YYYYMMDD.SSSSS, extracting 2D AOD, scattering to chunks) is sound. Reuse the basic I/O pattern and namelist structure (nudge_path_Qaer, nudge_file_template_Qaer, nudge_times_per_day_AOD=8)
- The windowing/masking infrastructure (Heaviside horizontal/vertical windows, inversion flags) for spatially-selective AOD nudging is sophisticated and useful; worth retaining or templating
- Consider retaining one well-tested variant of the qaer-to-AOD transformation (water uptake + modal optical properties calculation). The Kohler variants suggest this is a key integration point but also a source of uncertainty. Need to pick best-performing variant or simplify
- File size and compression appears reasonable (~250-500 KB per 3-hourly global field). No reason to change archive format or compression
- Discard: All the multiple test versions (nudging_AODs_nt_*.F90, *_DF*.F90, dated variants) and clean up to a single canonical nudging_AODs.F90. The proliferation makes maintenance impossible
- Document and separate the data-prep pipeline clearly: (1) raw VIIRS L2 swath acquisition, (2) MODIS L2 acquisition, (3) QA filtering & merging, (4) regridding to f09, (5) 3-hourly aggregation, (6) optional bias correction. Make each step reproducible with scripts/code in the archive
- For the bias-correction step, either archive the algorithm + coefficients or re-baseline to raw VIIRS L2 without 'corrected' variant, explaining the choice. The md08_d3 / VIIRS_original distinction is confusing without documentation
- Store metadata (source sensor, QA thresholds, number of observations, retrieval uncertainty, time-averaging method) in netCDF global attributes or in a companion CSV/JSON file per year, not just in code comments
