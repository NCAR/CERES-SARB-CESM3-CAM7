# MODIS/VIIRS AOD Nudging in CESM2.2.2 / CAM6-MAM4 — Unified Analysis of the Prior Attempt

*Synthesis prepared 2026-06-27 to drive a clean-slate rewrite. All paths verified against the live filesystem under `/glade/work/tvmora/`.*

---

## 0. Executive summary

The prior attempt (author: `tvmora`) is a **working but deeply disorganized research prototype** that constrains CAM6's MAM4 aerosol state toward satellite-observed column AOD. It is scientifically coherent in its core idea but suffers from severe engineering debt: **66 nudging-module variants in one directory (123 `.F90` files recursively), 5 namelist-definition XMLs, 264 test-case directories, and zero version control or tests.**

One critical fact that the explorers disagreed on, now resolved by direct inspection of the canonical `nudging_AODs.F90`:

> **The system does NOT actually run Newtonian relaxation. It runs hard replacement.** At line 1907, `phys_state%q(...) = Target_Qaer(...)` is active; the relaxation tendency at line 1906 (`phys_tend%q = Nudge_Qaer_step`) is **commented out**. So despite the name "nudging" and the presence of `Alpha*(Target-Model)/TimeScale` machinery throughout, the deployed behavior overwrites aerosol mass every timestep. This is a *forcing* scheme, not a nudging scheme. The relaxation path exists but is disabled.

This distinction matters enormously for the rewrite and should be an early design decision.

---

## 1. What the prior attempt does (end-to-end)

The pipeline, from satellite to model state:

1. **Satellite ingest (offline, external to repo).** MODIS (Terra/Aqua) and VIIRS (NOAA-20) Level-2 AOD swaths at 550 nm are acquired. Raw VIIRS L2 lives in `/glade/work/tvmora/VIIRS_original/` (`AERDB_L2_VIIRS_NOAA20`, native swath 402×400).

2. **Bias correction + intermediate gridding (offline).** VIIRS is bias-corrected against MODIS, producing `/glade/work/tvmora/VIIRS_corrected/` (`md08_d3.YYYYDDD.HH.nc`, 192×94 hourly, variable `tau_avg`). **The correction algorithm itself is not in the repo** — only inputs and outputs survive.

3. **Merge + regrid + temporal aggregation (offline).** MODIS + VIIRS are merged, quality-weighted, and regridded to the **f09 grid (192 lat × 288 lon, 0.9375°×1.25°)**, aggregated to **3-hourly** (8 files/day). Final archive: `/glade/work/tvmora/MODIS_VIIRS_AOD/{YYYY}/...`, files `terra_modis_npp_viirs_3hr_lat192xlon288.YYYYMMDD.SSSSS.nc` (also a `MODIS_ta_VIIRS_noaa20_...` naming variant), single variable `aod_weighted_mean` (or `aod_weighted_mean_modis` / `_viirs`), fill `-999`, 2000–2025. **This archive is the durable, valuable asset.**

4. **In-model read.** Each model update step, `nudging_update_analyses_fv()` (in `nudging_AODs.F90`) opens the file matching the current `%y%m%d.%s`, reads `lon(288)`, `lat(192)`, and the 2D AOD field, and `scatter_field_to_chunk()`s it across MPI chunks → `Target_AOD`.

5. **Forward optics: model AOD from model aerosol.** For each column, the code computes `Computed_AOD` at 550 nm from the model's own 27 MAM4 mass mixing ratios: relative humidity → Köhler water uptake → wet radius → wet refractive index → Chebyshev/Mie lookup extinction → vertical integration. This logic is **re-implemented inside the nudging module** (subroutines `relative_humidity`, `water_uptake_mam4`, `aerosol_sw_properties`), duplicating CAM's `modal_aer_opt.F90` + `modal_aero_wateruptake.F90`.

6. **Inversion: target aerosol from observed AOD.** A single scalar ratio per column, `AOD_ratio = Target_AOD / Computed_AOD`, scales **every** species at **every** level (`qaer_target_mam4`).

7. **Apply.** The model state is **overwritten** with the target (line 1907), every model AOD-update step, inside the CAM physics loop.

Throughout, **MERRA2 meteorological nudging runs simultaneously** so dynamics stay realistic while aerosol is constrained.

---

## 2. The nudging algorithm

### 2.1 Governing operation (as actually deployed)

Per column `i`, level `k`, species `l` (verified at `nudging_AODs.F90:3277-3292`, `:1907`):

```
AOD_ratio(i) = Target_AOD(i) / Computed_AOD(i)         [line 3280]
   ... with AOD_ratio(i) = 1  if guarded (Computed_AOD too small / Target invalid)  [line 3277]
Target_Qaer(i,k,l) = AOD_ratio(i) * Model_Qaer(i,k,l)  [line 3292]   ← uniform over all k and all 27 l
phys_state%q(i,k, idxaer(l)) = Target_Qaer(i,k,l)      [line 1907]   ← HARD REPLACEMENT (active)
```

The relaxation form is present but disabled (line 1906, commented):
```
! phys_tend%q(...) = Nudge_Qaer_step = Nudge_Qaer_coef(l) * (Target - Model) / TimeScale
```
So the often-quoted equation `F = α·(Target − Model)/τ` describes **dormant code**, not runtime behavior. The two `Nudge_AOD_Force_Opt` modes (0 = next-obs, 1 = linear interpolation in time between obs snapshots) still apply to how `Target_Qaer` is built (see line 1721 for the time-interp blend).

### 2.2 What is adjusted

- All **27 advected MAM4 constituents** across 4 modes: `SO4_a1/a2/a3`, `POM_a1/a4`, `SOA(1–5)_a1/a2`, `BC_a1/a4`, `DST_a1/a2/a3`, `NCL_a1/a2/a3`, `NUM_a1/a2/a3/a4`, mapped via `cnst_get_ind` into `idxaer(27)`.
- **Uniformly** — one scalar per column scales every species and every level identically.

### 2.3 Timescale & masking

- `Nudge_AOD_Step = 86400 / Nudge_Times_Per_Day_AOD` (8/day → 10800 s, matching 3-hourly obs). `Model_AOD_Step = 86400 / Model_Times_Per_Day_AOD` (e.g. 48/day for 30-min steps). These govern *update cadence*; under hard replacement they do not damp.
- **Heaviside/tanh windows**: horizontal (`Hwin_lat0/lon0`, `latWidth/lonWidth`, `latDelta/lonDelta`, `Invert`) and vertical (`Vwin_Lindex/Hindex`, `Ldelta/Hdelta`, `Invert`). Comment in source: configured for **only one window per simulation**. Per-species `Nudge_Qaer_coef(27)` and `Nudge_Qaer_prof(27)` profiles exist but bite only in the (disabled) relaxation path.

### 2.4 Model-AOD / optics coupling (the scientifically substantive part)

- **RH**: local Magnus formula (D. Fillmore), `RH = p·q/(ε·e_s0·exp(17.67(T−273.15)/(T−29.65)))`, ε=0.622, e_s0=611.2 Pa, clipped ≤ 1; `ln(RH)` cached.
- **Water uptake (Köhler, Ghan & Zaveri 2007)**: `r_wet = r_dry·(1 − B/ln(RH))^(1/3)`, bulk `B = Σ(B_i·V_i)/ΣV_i`; RH capped at **0.99** to dodge the `ln(RH)→0` singularity. B-coefficients are species-specific (sulfate ≈ 2.43, sea-salt ≈ 4.83, organics small, BC ≈ 0).
- **Optics**: wet refractive index from volume mixing → `binterp()` bilinear interpolation in `(refr, refi)` over LARC Mie tables (`prefr=7`, `prefi=10`, `ncoef=5` Chebyshev coeffs) in `/glade/work/tvmora/Mie_io/mam4_mode[1-4]_larc_c000000.v2.nc` → specific extinction `pext` (m²/kg) → `dopaer = pext·mass` → column sum.
- **Only the visible diagnostic band is used** (`do isw = idx_sw_diag, idx_sw_diag`, ~550 nm). Both obs and model assume 550 nm; no spectral conversion.

### 2.5 Where explorers disagreed / were unsure (flagged)

- **"Nudging vs forcing"** — *resolved*: forcing (hard replacement) is active; relaxation is dead code.
- **Inversion sophistication** — coverage-check described an "inversion of Mie optics to mode-wise qaer" and called the math "tractable with unique solutions." The actual code is **not an inversion** — it is a single-scalar multiplicative rescale of the existing model mass profile. There is no per-mode or per-species solve. This is a much cruder operation than the coverage summary implies.
- **Whether nudged qaer feeds radiation** — unresolved. The state is overwritten before radiation in the physics order, but whether RRTMG re-derives optics from the modified mass on the same step (vs. cached fields) was not confirmed by any explorer.
- **RH source** — code computes RH locally rather than using CAM's saturation routines; explorers agree this is a duplication risk.

---

## 3. Observation data pipeline

| Stage | Location | Grid / cadence | Key variables | Status |
|---|---|---|---|---|
| Raw VIIRS L2 | `/glade/work/tvmora/VIIRS_original/`, `/glade/work/tvmora/VIIRS/{year}/{doy}/` | swath 402×400, ~14/day | `Aerosol_Optical_Thickness_550_{Land,Ocean,Land_Ocean}`, `QA_Flag` (0–3) | present |
| Bias-corrected VIIRS | `/glade/work/tvmora/VIIRS_corrected/` | 192×94, hourly | `tau_avg` (fill −999), `md08_d3.YYYYDDD.HH.nc` | present, **algorithm absent** |
| Final merged/gridded | `/glade/work/tvmora/MODIS_VIIRS_AOD/{YYYY}/...` | **f09 192×288**, 3-hourly (8/day, SSSSS ∈ {0,10800,…,75600}) | `aod_weighted_mean[_modis/_viirs]`, fill −999, + `lon/lat`, cell bounds, `wght(lat)`, `aod_count` (some years) | **present, durable asset, 2000–2025** |

- **Wavelength**: 550 nm throughout (implicit in variable names; no wavelength dim in final files).
- **MODIS raw L2 is NOT archived** — only the merged product names it. Reproducing the gridded product from scratch is not currently possible from this repo.
- **Original-vs-corrected VIIRS**: the existence of both directories evidences inter-sensor harmonization / post-launch calibration, but the offset/slope/aerosol-type dependence and any literature reference are **undocumented**.
- **QA**: present in L2 (0–3); no QA array survives into final files, implying QA filtering happened during regridding/weighting (method unrecorded).
- **Metadata gaps**: final files lack `long_name`, `units`, source attribution, QA thresholds, observation counts, uncertainty. File-count anomalies (e.g., 2928 vs expected 2920 in 2000) and per-year layout variants (`TA_only` in 2020, `backup_old` in 2010) are unexplained.
- **Grid match**: 192×288 matches f09 exactly, so the in-model read does **no interpolation** — and aborts on any dimension mismatch.

---

## 4. CAM integration & build

- **Base version**: `/glade/work/tvmora/cesm2.2.2`, git tag **`release-cesm2.2.2`**, working tree clean (all mods live in SourceMods, *not* committed to the tree). Secondary checkouts `cesm_sarb` (cesm2.2.0, superseded) and `CESM2.2` (non-git) add confusion.
- **Compset / resolution**: `HIST_CAM60%CCTS1%NUDG...` (CAM-Chem trop/strat MAM4-VBS, `CCTS1`), aliased `FCnudged` / `FCts2nudged` in a custom `config_compsets.xml`. Resolution **`f09_f09_mg17`** (0.9°×1.25°). Created with `--run-unsupported`.
- **Code injection**: pure **SourceMods** copy-in. A case build copies ~6–7 files into `SourceMods/src.cam/`: `nudging_AODs.F90`, modified `physpkg.F90` (= `physpkg_AODs.F90`, 2794 lines), `modal_aer_opt.F90` (with `binterp` made public via `modal_aer_opt_binterpublic.F90`), `aer_rad_props.F90`, `runtime_opts.F90`, `tracer_data.F90`, and a `namelist_definition*.xml`. Example deployed set: `/glade/work/tvmora/cesm2.2.2/cime/scripts/test_geosit_viirs_nds_2025_06_07/SourceMods/src.cam/`.
- **Physics hooks** (`physpkg_AODs.F90`): `nudging_init_AOD` in `phys_init`; `nudging_timestep_init_AOD` in `phys_run2_init` (builds Target/Computed AOD); `nudging_timestep_tend_AOD` in `phys_run2` after aerosol microphysics + `check_energy_chng`. Gated by `Nudge_Model_AOD` / `Nudge_AOD_ON`.
- **Namelist** (`&nudging_AOD_nl`, defined in `namelist_definition_nudging_AODs.xml`): `nudge_model_AOD`, `nudge_path_Qaer`, `nudge_file_template_Qaer` (e.g. `terra_modis_npp_viirs_3hr_lat192xlon288.%y%m%d.%s.nc`), `nudge_beg/end_{year,month,day}_AOD`, `nudge_AOD_force_opt` (0/1), `nudge_timescale_opt_AOD`, `nudge_times_per_day_AOD=8`, `model_times_per_day_AOD=48`, `nudge_Qaer_coef(27)`, `nudge_Qaer_prof(27)`, plus all window params. MERRA2 met-nudging via the standard `&nudging_nl` (`MERRA2_fv09_32L`, coefs 0.25, 8/day).
- **Run workflow on Derecho**: shell scripts in `/glade/work/tvmora/CAM_scripts/Derecho_CESM_scripts/` (e.g. `derecho_FCnudged_control.csh`) do `create_newcase → case.setup → cp SourceMods → xmlchange dates/STOP → append user_nl_cam → case.build [--clean-all] → case.submit`. ~80+ scripts; 11 analysis notebooks in `Derecho_ipynb_scripts/`.
- **Maturity**: some short cases succeed (e.g. `test_nudge_AOD_force_opt_0` ran 2010-01-01→02); several recent 2025 cases **build but fail at runtime** (cause unconfirmed — candidates: namelist mismatch, missing/malformed obs files, or NaN from `AOD_ratio` blow-up). A 2.8 GB spin-up restart (`spin-up_23.cam.i.2024-01-01-00000.nc`) exists with no documented spin-up protocol.

---

## 5. Why it's a mess (evidenced)

| Problem | Evidence (verified) |
|---|---|
| **Variant sprawl** | 66 `.F90` directly in `Force_AODs/`; **123** recursively; 19 in `Force_AODs/Kohler/`; **38** in `Force_AODs/Dust_scheme/`; 19 top-level `nudging*.F90`; 49 in `modules_control_test/`. |
| **Multiple "canonical" candidates** | Top-level `nudging_AODs.F90` (3302 lines) vs `Force_AODs/nudging_AODs_qaer_modis.F90` (3546 lines) — different sizes, no marker of which is production. |
| **Namelist proliferation** | 5 XMLs: `namelist_definition.xml`, `..._nudge_FV.xml`, `..._nudge_FV_2.xml`, `..._nudging_AOD.xml` (singular), `..._nudging_AODs.xml` (plural). |
| **Test-case explosion** | **264** directories under `cesm2.2.2/cime/scripts/`, each freezing its own SourceMods snapshot. |
| **No version control of the science** | All iteration encoded in filenames (`_nt_005`, `_DF`, `_DF_2`, `_AODVISdn`, `_kohler_rhdeliques`, `_print_all`, `_toplev`, dated `_032626`), timestamps Aug 2023 → Dec 2025. No git, no branches, no commit messages, no README. |
| **Monolith + global state** | One ~3.3k-line module mixes I/O, optics, RH, windowing, time mgmt; ~40 module-scope `save` allocatables (`Target_*`, `Model_*`, `Nobs_*`, `cext/cabs/casm`, etc.), never deallocated. |
| **Duplicated physics** | RH, Köhler water uptake, and Mie extinction re-implemented inside the nudging module instead of calling CAM's `modal_aero_wateruptake` / `modal_aer_opt` → divergence risk between nudging-AOD and radiation-AOD. |
| **Hard-coding** | 27-species indices, mode indices `pnmde(4)`, `ncoef=5/prefr=7/prefi=10`, B-coefficients, refractive indices, densities, default paths/grid all embedded; obs variable names hard-coded with `endrun` on mismatch. |
| **Dead / debug code** | Active relaxation path commented out (line 1906); abundant `print*` in hot paths; commented `calc_MidpointPressure`, `nudging_update_analyses_se/eul`. |
| **No tests / no validation harness** | `modules_control_test/` is 49 ad-hoc debug snapshots, not a suite. No unit/regression/CI. 264 cases with no metrics aggregation. |
| **Out-of-scope clutter** | Two fire-emissions archives (`qfed2.5_finn_extended_2024` 57 GB, `qfed_v2.6` 2.4 GB) are unrelated to AOD nudging; some case names misleadingly say `qfed2_6` without activating it. |

---

## 6. Carry forward vs. discard

### Carry forward (scientific content / data / proven patterns)
- **The observation archive** `/glade/work/tvmora/MODIS_VIIRS_AOD/` (2000–2025, f09, 3-hourly) — durable asset; keep format, keep `aod_weighted_mean` convention.
- **The Mie/LARC optics infrastructure** — `/glade/work/tvmora/Mie_io/mam4_mode[1-4]_larc_c000000.v2.nc` + Chebyshev/`binterp` parameterization (Ghan & Zaveri 2007) is standard and sound. **Reuse CAM's `modal_aer_opt`/`modal_aero_wateruptake` directly** rather than the duplicated copies.
- **Köhler water-uptake logic** — physically correct; keep the B-mode aggregation and `r_wet` formula. Promote hard-coded coefficients to namelist; fix the RH=0.99 discontinuity properly.
- **The Heaviside/tanh windowing module** — elegant; extract as a standalone, reusable spatial-mask utility (and lift the "one window only" restriction).
- **CAM-native integration patterns** — SourceMods deployment, `&nudging_AOD_nl` namelist control, `scatter_field_to_chunk`, `cnst_get_ind` for indexing, the time-interp (curr/next + linear blend) machinery, simultaneous MERRA2 met-nudging, and the `FCnudged` compset concept all work — keep the *patterns*, rebuild the *implementation*.
- **The forcing-vs-relaxation switch** as a real, tested, documented namelist option (it already exists structurally — finish and benchmark both).

### Discard
- **All 122 non-canonical nudging variants**, the Kohler/Dust_scheme exploratory trees, and the 49 `modules_control_test/` snapshots — archive to a research branch, then delete from the working path.
- **4 of the 5 namelist XMLs**; consolidate to one schema-validated definition.
- **The duplicated RH / water-uptake / extinction code** inside the nudging module.
- **Secondary CESM checkouts** (`cesm_sarb`, `CESM2.2`); standardize on `cesm2.2.2` (or move up — see §7).
- **Dead/debug code**, hard-coded paths/variable names, and the fire-emissions directories (out of scope).
- **Almost all 264 test cases**; keep one as a regression baseline, regenerate the rest from a reproducible script.

---

## 7. Open questions for the user (decide before designing the rewrite)

**Scientific method**
1. **Forcing vs. nudging — what do we actually want?** The deployed code hard-overwrites aerosol mass (line 1907). Is that the intended physics, or should the rewrite use the true relaxation `α·(Target−Model)/τ`? This is the single biggest design fork.
2. **Is single-scalar multiplicative rescale acceptable?** `AOD_ratio × Q_all_species` applies one number to all 27 species and all levels. It preserves the model's *relative* speciation and vertical shape but constrains only the column total. Do we want per-mode/per-species adjustment or a vertical redistribution — i.e., a genuine inversion — or is the column-scaling deliberate and adequate?
3. **Should nudged aerosol feed radiation?** Confirm whether the intent is radiative feedback (and whether RRTMG re-derives optics from the overwritten mass on the same step) or constraint of aerosol fields only.
4. **RH=0.99 cap and the Magnus formula** — acceptable, or replace with CAM's native saturation routines / a higher-RH-robust water-uptake treatment?

**Observations**
5. **Which product is canonical** — MODIS-only, VIIRS-only, or the merged `aod_weighted_mean`? And single-band 550 nm only?
6. **VIIRS bias correction**: do we re-baseline to raw L2 and document a new correction, or recover/specify the existing `md08_d3` algorithm? The current method is unarchived.
7. **QC / observation error**: should we add per-pixel QA filtering, cloud masking, and uncertainty weighting (none exist today)?
8. **Obs-gap handling**: today a missing file aborts (or disables nudging). What is the desired behavior (skip, persist last, climatology fill)?

**Platform & scope**
9. **CAM6/CESM2.2.2 vs. CAM7/CESM3?** The prior work is pinned to `release-cesm2.2.2`. A rewrite is the moment to decide whether to move to CAM7/CESM3 (different aerosol-optics interfaces; the `modal_aer_opt`/MAM4 coupling would change). MAM4-only, or design for portability to other aerosol schemes?
10. **Grid scope**: f09 only (matching the obs archive and avoiding in-model interpolation), or support arbitrary grids with conservative regridding?
11. **Integration target**: stay with SourceMods overlays, or aim for a clean modular set (`nudging_io` / `nudging_optics` / `nudging_kernel` / `nudging_phys_interface`) with unit + regression tests intended for eventual upstream/branch merge?
12. **Spin-up & MERRA2 coupling**: keep simultaneous MERRA2 met-nudging as a hard requirement? What spin-up protocol should the rewrite assume/document?

---

### Key file reference (verified paths)
- Canonical nudging module: `/glade/work/tvmora/CAM_modifications/nudging_AODs.F90` (3302 lines; active forcing at line 1907, dead relaxation at 1906, ratio logic 3277–3292)
- Largest MODIS variant: `/glade/work/tvmora/CAM_modifications/Force_AODs/nudging_AODs_qaer_modis.F90` (3546 lines)
- Physics driver mod: `/glade/work/tvmora/CAM_modifications/physpkg_AODs.F90` (2794 lines)
- Namelist (keep, consolidate): `/glade/work/tvmora/CAM_modifications/namelist_definition_nudging_AODs.xml`
- Base CAM optics (reuse): `/glade/work/tvmora/cesm2.2.2/components/cam/src/physics/cam/modal_aer_opt.F90`
- Mie tables: `/glade/work/tvmora/Mie_io/mam4_mode[1-4]_larc_c000000.v2.nc`
- Obs archive: `/glade/work/tvmora/MODIS_VIIRS_AOD/{YYYY}/`; VIIRS raw `/glade/work/tvmora/VIIRS_original/`; corrected `/glade/work/tvmora/VIIRS_corrected/`
- CESM checkout: `/glade/work/tvmora/cesm2.2.2` (tag `release-cesm2.2.2`); 264 cases under `cesm2.2.2/cime/scripts/`
- Variant sprawl: `Force_AODs/` (66 direct / 123 recursive), `Force_AODs/Kohler/` (19), `Force_AODs/Dust_scheme/` (38), `modules_control_test/` (49); 19 top-level `nudging*.F90`; 5 namelist XMLs
- Out of scope: `/glade/work/tvmora/qfed2.5_finn_extended_2024`, `/glade/work/tvmora/qfed_v2.6`