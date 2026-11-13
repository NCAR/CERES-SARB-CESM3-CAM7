# Emissions Context (QFED/FINN)

> Subsystem: **Fire emissions archives (QFED2.5+FINN, QFED2.6) in the tvmora AOD-nudging codebase**  ·  source: prior attempt at `/glade/work/tvmora`

## Summary

The two fire-emissions directories are SEPARATE from the AOD nudging system and represent legacy or parallel work on biomass-burning emissions preprocessing:

- **qfed2.5_finn_extended_2024** (57 GB, ~41 species): Contains concatenated monthly fire-emissions NetCDF files (Jan 2000 - Dec 2024) for chemical species (CO, SO2, NOx, BC, OC, SOA precursors, VOCs, etc.). The "extended" suggests an effort to combine QFED 2.5 fire data with FINN (Fire Inventory from NCAR) biomass-burning emissions. These are raw/intermediate data products, not actively linked to the AOD nudging code.

- **qfed_v2.6** (2.4 GB, ~51 species, dated Sept 2025): Contains finalized QFED 2.6 emission NetCDF files for 2025 on a 0.9×1.25° grid (CAM-standard resolution). Variable naming follows CESM conventions: `qfed.emis_<species>_0.9x1.25_mol_2025.nc`. This appears to be more recent and potentially prepared for CESM input, but no explicit link to nudging modules is evident.

**Connection to AOD nudging:** The nudging system (/glade/work/tvmora/CAM_modifications/nudging_AODs.F90, nudging_AODs.F90, etc.) reads MODIS-VIIRS AOD observations directly for nudging—it does NOT consume fire-emissions data from these directories. Fire emissions are independent, typically handled via CAM's standard emission-reading mechanisms (e.g., CAMS-GLOB-ANT, CMIP6 emissions as seen in the plotting notebooks).

**Assessment:** These fire-emissions directories are OUT OF SCOPE for AOD nudging rewrite. They represent parallel emissions-processing work, possibly abandoned or shelved. The AOD nudging system's core logic depends only on satellite AOD observations and model state, not on fire-emissions sources. Keep out of the clean rewrite.


## Key files

| Path | Role | ~Lines |
|---|---|---|
| `/glade/work/tvmora/qfed2.5_finn_extended_2024` | Raw fire-emissions archive: concatenated monthly QFED2.5+FINN biomass-burning NetCDF files (CO, SO2, NOx, BC, OC, VOCs, etc.) 2000-2024 | 0 |
| `/glade/work/tvmora/qfed_v2.6` | Finalized QFED 2.6 fire-emissions for 2025 on CAM 0.9x1.25 grid (51 species) | 0 |
| `/glade/work/tvmora/CAM_modifications/nudging_AODs.F90` | Core AOD nudging module: nudges CAM aerosol state toward MODIS-VIIRS observations, NOT using fire-emissions data | 3000 |
| `/glade/work/tvmora/CAM_scripts/Derecho_ipynb_scripts/emissions.ipynb` | Jupyter notebook comparing CAMS-GLOB-ANT vs CMIP6 emissions (includes SO4, aerosol number); separate from fire-emis work | 0 |
| `/glade/work/tvmora/cesm2.2.2/cime/scripts/geosit_modis_nds_qfed2_6_200801` | Test case directory using FCnudged compset; name references qfed2.6 but config files show standard CESM emission setup (not explicitly linked to fire data) | 0 |


## Technical findings

- qfed2.5_finn_extended_2024: 57 GB archive of concatenated monthly fire-emissions NetCDF files (Jan 2000-Dec 2024) covering ~41 chemical species
- qfed_v2.6: ~2.4 GB finalized QFED 2.6 2025 emissions at 0.9x1.25 CAM grid; 51 species, naming follows CESM conventions (qfed.emis_<species>_0.9x1.25_mol_<year>.nc)
- Nudging module nudging_AODs.F90 reads MODIS-VIIRS AOD observations and applies relaxation-based nudging to CAM's aerosol state; no reference to fire-emissions or qfed data
- Fire-emissions handled independently via standard CAM mechanisms (CAMS-GLOB-ANT, CMIP6 inventories, etc.), as evidenced by plotting notebooks (emissions.ipynb, plot_CMIP6_emissions_1750_2015.ipynb)
- Test cases (geosit_modis_nds_qfed2_6_*) use FCnudged compset but their env_run.xml configs do not explicitly reference QFED emissions
- 'Extended' in qfed2.5_finn_extended_2024 suggests an attempt to merge QFED 2.5 with FINN (Fire Inventory from NCAR) but is incomplete/shelved


## Problems / why it's a mess

- QFED directories appear to be raw/intermediate data products with no clear integration into the AOD nudging workflow—likely abandoned or parked mid-project
- No scripts, code, or documentation in the repository explain how/why these fire-emissions were created or intended for use
- Case naming (geosit_modis_nds_qfed2_6_*) references qfed2_6 but the actual case configuration does not activate QFED data—misleading naming convention
- Dual QFED versions (2.5+FINN extended vs. 2.6) without clear indication of which is active or preferred for current work
- Fire-emissions preprocessing work is disconnected from nudging design and adds clutter to the codebase


## Open questions

- Was the qfed2.5_finn_extended work intended to directly feed AOD nudging, or was it a separate emissions-bias-correction effort?
- Why does qfed_v2.6 exist (Sept 2025 date) when the primary AOD-nudging codebase appears frozen at late 2024?
- What emissions source is actually being used in current CAM-MAM4 runs (QFED 2.5/2.6 vs. CAMS-GLOB-ANT vs. CMIP6)?
- Should the case naming convention 'qfed2_6' be considered historical/legacy, or is there an active requirement to use QFED 2.6 for forced/nudged runs?


## Carry forward vs discard

- IGNORE both fire-emissions directories in the AOD-nudging rewrite; they represent separate emissions work with no active integration
- The nudging module is purely an AOD-state-constraint system driven by MODIS-VIIRS observations and model physics—emissions are decoupled
- Case naming mentioning 'qfed2_6' can be retained for historical traceability but should not influence AOD nudging design decisions
- If fire-emissions need revisiting in future, treat as a separate, independent effort (likely via CAMS or CMIP6 pipeline, not custom QFED/FINN)
