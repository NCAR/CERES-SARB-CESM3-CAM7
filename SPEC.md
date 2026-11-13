# SPEC — MODIS/VIIRS AOD Nudging in CESM3 / CAM7 (CERES-SARB)

*Design spec, 2026-06-27 (rev. 2026-06-28: MAM5 work deferred indefinitely by user direction). Status: **design finalized; ready for `writing-plans`.** This file is self-contained so a fresh session (possibly a different account) can resume from the repo alone. Companion docs, all tracked in this repo: `docs/HANDOFF.md` (project status), `docs/reference/SYNTHESIS.md` (prior-attempt analysis), `docs/spike/CAM7-integration-surface.md` (CAM7 API map), plus `BUILD.md`, `RUN.md`.*

## 1. Goal & context
Add **MODIS/VIIRS aerosol-optical-depth (AOD) nudging** to **CESM3 / CAM7** as a clean-slate, well-architected, tested replacement for a disorganized prior prototype (`/glade/work/tvmora`). Purpose: constrain modeled aerosol so the **direct radiative effect** is right for **CERES/SARB radiation-budget** studies. Platform: NCAR **derecho**. Custom code repo: `NCAR/CERES-SARB-CAM7` (this repo). Vanilla CESM checkout (build sandbox): `/glade/work/fillmore/CESM3/cesm3_0_beta08`.

**Base is verified to build** (see `BUILD.md`): CESM3 `cesm3_0_beta08`, CAM `cam6_4_161` (CAM7), RRTMGP radiation, and MAM4 aerosols at `f09_f09_mg17`. CAM7 also exposes MAM5 aerosol configurations, but all MAM5 work is deferred indefinitely. Project/account `P19010000`.

## 2. Scope & non-goals
**In scope (v1):** in-CAM hard-replacement AOD nudging on f09 with direct radiative feedback; an offline obs-data pipeline producing the f09 3-hourly AOD product; tests for both.
**Non-goals (v1):** aerosol–cloud interactions (ACI) — interface kept ACI-ready but off; non-f09 grids / runtime regridding; multi-band/spectral AOD; per-mode inversion; data assimilation (EnKF/4DVar). These are explicitly deferred.

## 3. Locked design decisions
| # | Decision | Value |
|---|---|---|
| D1 | Base model | CESM3 `cesm3_0_beta08` / CAM7 (`cam6_4_161`), MAM4 only for v1; code keeps a mode-agnostic adapter, but MAM5 validation/runs are deferred indefinitely |
| D2 | Grid | **f09 only** (192 lat × 288 lon); obs pre-gridded to f09 → no in-model interpolation |
| D3 | Method | **Hard replacement** — overwrite aerosol state each application |
| D4 | AOD→aerosol map | **Uniform column rescale**: `ratio = obs_AOD / model_AOD` (550 nm), applied to **all aerosol species mass AND number**, every mode & level → preserves speciation, size distribution, vertical shape; forces column total to obs |
| D5 | Radiative coupling | **Direct effect only** → nudged aerosol feeds **RRTMGP**; overwrite *before* radiation. ACI hook present but **off** by default |
| D6 | Cadence | Apply at the model's **radiation cadence**; **time-interpolate** the 3-hourly obs to the current time |
| D7 | Missing/invalid obs | **Leave model untouched** (overwrite only columns with a valid retrieval; night/cloud/fill → model runs free) |
| D8 | Obs source | **Rebuild + document** the data pipeline from L2 (do not depend on the unarchived prior pipeline) |
| D9 | Decomposition | Two subsystems (SP1 pipeline, SP2 module) joined by a fixed netCDF **contract**; build in parallel |
| D10 | Portability | A **CAM-version-abstraction boundary**: all CAM7-specific calls isolated in one adapter module so beta→release rebases / CAM6 fallback are a thin change |

## 4. Architecture overview
```
 MODIS L2 ┐                                   ┌── reads ──┐
 VIIRS L2 ┤─[SP1 pipeline]─> f09 3-hourly ────┤  CONTRACT ├──> [SP2 CAM7 module] ──> overwrite
          │  QC·merge·bias·regrid·aggregate    │ netCDF AOD │     aerosol state ──> RRTMGP (direct)
          └                                    └───────────┘
```
The **contract** (§5) is the only coupling. SP2 is developed/tested against contract-conforming **synthetic** sample files (SP2 plan Task 8's generator) while SP1's real pipeline is built independently. *(The legacy `/glade/work/tvmora` archive is NOT contract-conforming — per-sensor-only variable that flips `_modis`→`_viirs` across years, legacy ±89.53° grid, no CF `time` — so it is **seed material only**, never a test input or validation reference.)*

## 5. The obs-file CONTRACT (shared interface — pin first)
- **Format:** netCDF4, one file per 3-hour window (matches prior + keeps the model reader trivial).
- **Filename template:** `MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc` where `%s` = seconds-of-day of the window reference time (∈ {0, 10800, …, 75600}). *(Template is a namelist string in SP2; exact stem is free as long as both sides agree.)*
- **Grid:** f09, `lat(192)`, `lon(288)` with cell bounds (`lat_bnds`, `lon_bnds`); CF-compliant.
- **Primary variable:** `aod_weighted_mean(lat, lon)` — column AOD at **550 nm**, `units="1"`, `_FillValue=-999.` (**fill = "no valid obs here" → SP2 leaves the column untouched**).
- **Required companion vars:** `aod_count(lat,lon)` (# valid L2 pixels) and `aod_uncertainty(lat,lon)` (derived in SP1 — *absent from the legacy archive*; present so SP2 can later use obs-error weighting, v1 only needs it written). **Recommended:** per-sensor `aod_weighted_mean_modis`, `aod_weighted_mean_viirs` (present in legacy 2024 files) for diagnostics. *Legacy carried `aod_count` + per-sensor fields but NO uncertainty/QA and essentially no provenance — SP1 adds both.*
- **Time convention (RESOLVED):** each file aggregates a full **3-hour window**; its **valid time = window center**, stored as a CF-compliant scalar `time` coordinate (e.g. `units="hours since 2000-01-01 00:00:00 UTC"`). The filename `%s` stays keyed to the **window-start** seconds-of-day (∈ {0,10800,…,75600}) for tidy enumeration; **SP2 time-interpolates on the in-file CF `time` (center)**, not the filename stem. *(Legacy archive labeled by window start via ad-hoc int scalars and was not CF-compliant; we adopt CF center.)*
- **Provenance (required):** global attributes for source products/collections, QC thresholds, merge & bias-correction method + version, creation date, git commit of SP1.

## 6. SP1 — Observation data pipeline (offline, Python, **built on DAVINCI**)
**Architecture (RESOLVED, §9 R17):** SP1 is a small package `sp1_aod_pipeline/` in THIS repo that **imports `davinci_monet`** (the MONET-based DAVINCI toolkit at `../DAVINCI`, pinned as a dependency) and reuses its readers, EarthData downloads, swath→grid binning, and AERONET/stats. Two **general** capabilities SP1 needs but DAVINCI lacks — a **VIIRS `AERDB_L2` reader** and **uncertainty-aware binning** — are built **upstream in DAVINCI**; the SP1-specific glue (bias correction, inverse-variance merge, the §5 contract writer, the orchestration CLI) stays local. (DAVINCI is model-vs-obs *evaluation*; SP1 is obs *aggregation* — different scope, so SP1 stays its own package coupled only by the import.)

**Inputs (RESOLVED):** MODIS L2 (Terra+Aqua **MOD04_L2/MYD04_L2 C6.1, combined Dark Target + Deep Blue**, 550 nm) and VIIRS L2 (NOAA-20 `AERDB_L2`, 550 nm). Acquired from **LAADS DAAC via DAVINCI's `earthaccess` integration** (`stage_collection()`); credentials = EarthData login in **`~/.netrc`** (bearer-token flow). MODIS L2 is not on glade; local raw VIIRS covers only ~2023+. **v1 scope:** build + validate on a **one-month test period — July 2008**, designed to scale to 2000–2025 (deferred batch run). **July 2008 predates VIIRS (SNPP 2011, NOAA-20 2017) → MODIS-only (Terra MOD04_L2 + Aqua MYD04_L2, C6.1); the VIIRS reader/merge/bias paths stay unit-tested but are not exercised this month.** Single band 550 nm.

**Pipeline stages** (reuse = DAVINCI as-is · upstream = new DAVINCI capability · build = SP1-local):
1. **Acquire** — DAVINCI `stage_collection()` + a LAADS `CollectionSpec` for MOD04/MYD04/AERDB. *(reuse + thin SP1 spec)*
2. **Ingest + QC** — MODIS via `MODISL2AODReader` (**reuse**); **VIIRS `AERDB_L2` reader (upstream)**. QC defaults per §9 R8 (VIIRS `QA_Flag ≥ 2`, MODIS valid-retrieval, drop AOD∉[0,5]); carry per-pixel uncertainty.
3. **Grid to f09** — DAVINCI `bin_swath_to_grid`/`IntermediateGridStrategy` (**reuse**), **point-in-cell for v1** (§9 R18; area-weighting deferred); **uncertainty-aware binning (upstream)** → per-cell mean + count + σ, per sensor.
4. **Temporal aggregation** — 3-hourly windows (`time_resolution='3h'`) + a CF `time`-center/`time_bnds` adapter. *(build)*
5. **VIIRS→MODIS bias-correction** — AERONET-anchored, with **AERONET Ångström-interpolated to 550 nm** (§9 R19); coefficients + before/after RMSE-vs-AERONET in provenance. *(build)*
6. **Merge MODIS+VIIRS** — inverse-variance `w=1/σ²` → `aod_weighted_mean`. *(build)*
7. **Write** contract netCDF (§5) with full provenance — CF bounds, `_FillValue=-999`, filename template. *(build)*

**Tech:** Python; depends on **`davinci_monet`** (pinned) + numpy/xarray/netCDF4 + `earthaccess`; a conda env is fine (offline; unrelated to the conda-free CESM build). Deterministic, re-runnable, parameters logged.
**Validation:** DAVINCI **AERONET reader + `PointStrategy` co-location + stats metrics** (per §8); golden-file tests on small samples; **plot-based science verification** (`docs/science-verification.md`) after each pipeline run.

## 7. SP2 — In-CAM AOD nudging module (Fortran / CAM7)
**Module decomposition (small, single-purpose, testable):**
- `aod_nudging_kernel` — **pure, CAM-agnostic logic**: inputs `Target_AOD`, `Computed_AOD`, valid mask → `ratio` with guards/caps → returns scale factors. No CAM deps → unit-testable in isolation.
- `aod_nudging_optics` — **the CAM-abstraction boundary (D10)**: the *only* module that touches CAM7 internals. (a) compute model column AOD @ 550 nm from the aerosol state via `aerosol_optics_cam_sw` + `radconstants::idx_sw_diag`; (b) enumerate aerosol constituents generically via `rad_constituents::rad_cnst_get_info` / `rad_cnst_get_aer_mmr` / `rad_cnst_get_mode_num`; (c) write scaled mass+number back into `state%q`. Re-pointed for CAM6 / future CAM7.
- `aod_nudging_obs` — IO: open contract netCDF (`cam_pio_openfile`/`infld`), `scatter_field_to_chunk`, hold current+next snapshots, **time-interpolate** to model time, expose `Target_AOD` + valid mask per chunk.
- `aod_nudging_intr` — physics interface/driver mirroring CAM's `nudging.F90` lifecycle: `*_readnl` (in `phys_init`), `*_init`, `*_timestep_init` (in `phys_timestep_init`), `*_timestep_tend` (in `tphysac`). Orchestrates obs→optics→kernel→overwrite; emits diagnostics; calls `check_energy_chng`.

**Algorithm (per application, per column i where obs valid):**
```
Computed_AOD(i) = aod_nudging_optics::model_aod550(state, pbuf)        ! reuse CAM7 optics
ratio(i) = clamp( Target_AOD(i) / Computed_AOD(i), RATIO_MIN, RATIO_MAX )
if (Computed_AOD(i) < EPS_AOD  .or.  not valid(i))  ratio(i) = 1      ! skip/guard
do all aerosol constituents l (mass) and mode number n:               ! via rad_cnst_*
   state%q(i,:,idx) = ratio(i) * state%q(i,:,idx)                     ! overwrite mass + number, all levels
```
Then radiation runs → RRTMGP recomputes optics from the overwritten state (direct effect).
- **Hook point (CONFIRMED in checkout):** `src/physics/cam7/physpkg.F90::tphysac` (subroutine @ ~L1360) — insert the nudging call **after** aerosol wet processes (`t_stopf('aerosol_wet_processes')` ~L2015, i.e. after `modal_aero_wateruptake_dr` + `aero_model_wetdep`) and **before** `radiation_tend()` (~L2050). *(Implementation note — RESOLVED & ratified 2026-06-27: water uptake **is** re-evaluated after scaling — the `modal_aero_wateruptake_dr` refresh is the default in SP2 plan Task 9, because the SW optics reads stale pbuf `QAERWAT` for the climate list (`modal_aerosol_state_mod.F90:473`); the refresh keeps the aerosol state fed to RRTMGP internally consistent.)*
- **Guards/limits (RESOLVED, §9 R12):** `EPS_AOD=0.01` (skip near-zero model AOD), `RATIO_MIN`/`RATIO_MAX=0.1/10` clamp to avoid blow-ups; namelist-tunable, with per-step ratio hit-rate diagnostics.
- **Mode-agnostic:** no hard-coded species/mode counts. This is retained for portability and future aerosol packages, but v1 validation and runs are MAM4-only; MAM5 work is deferred indefinitely.
- **Diagnostics (`addfld`/`outfld`):** `AODNDG_OBS`, `AODNDG_MODEL_PRE`, `AODNDG_MODEL_POST`, `AODNDG_RATIO`, `AODNDG_MASK`.
- **Namelist `&aod_nudging_nl` (declared in CAM `namelist_definition.xml`):** `aod_nudge_on`, `aod_obs_path`, `aod_obs_template`, `aod_beg_*/end_*`, `aod_times_per_day` (=8), `aod_ratio_min/max`, `aod_eps`, `aod_aci_on` (=.false.), `aod_diag_on`.
- **Build delivery (RESOLVED):** **dev via `SourceMods/src.cam`** (fast iteration; standard CIME overlay, confirmed), **production via a CAM fork** of `ESCOMP/CAM` pinned at `cam6_4_161` by this repo's `git-fleximod` config (clean, version-controlled, upstream-ready). See `BUILD.md`.

## 8. Testing strategy
- **SP2 unit:** `aod_nudging_kernel` (ratio math, clamping, mask/guard, fill handling) — pure, tested with **pFUnit** (CONFIRMED integrated in `cesm3_0_beta08` via CIME `fortran_unit_testing`; CAM ships a live `.pf` suite under `components/cam/test/unit/`).
- **SP2 integration/regression:** short `F2000dev` MAM4-based case (verified spike build) + a synthetic contract obs file → assert post-overwrite model AOD == obs where valid (within optics round-trip tolerance) and **unchanged** where fill; conservation check via `check_energy_chng`. Do not add MAM5 smoke tests, plots, or CI gates unless the user explicitly reopens MAM5 work.
- **SP1 unit:** QC/grid/merge/bias functions (pytest), golden-file tests.
- **SP1 validation:** **our own DAVINCI-staged AERONET** at `/glade/work/fillmore/Data/CERES-SARB-CAM7/AeroNet` (monetio/DAVINCI netCDF, one file/day; **downloaded via DAVINCI's `AERONETReader` at Level 2.0** — staged for the July-2008 test month by `scripts/stage_obs.py`; any missing day fetched on demand) co-located **via DAVINCI's stats metrics + `PointStrategy`** → MAE/bias per season (Ångström-interpolated to 550 nm, R19). The AERONET comparison is **DAVINCI analysis, with scripts tracked in this repo** (`sp1_aod_pipeline/validation/`).
- **Science-verification gate (plot-based, `docs/science-verification.md`):** after each SP1/SP2 smoke run, DAVINCI renders a fixed set of views — global AOD map, AERONET scatter, uncertainty/count maps (SP1); OBS/PRE/POST/RATIO box maps, free-vs-nudged `AODVIS`, an aerosol **vertical-profile** D4 shape-invariance check, and an RRTMGP clear-sky **direct-effect** flux map (SP2) — each with explicit acceptance criteria; multimodal inspection of the PNGs is required before a task is "done".
- CI: at minimum scripted, repeatable test runners checked into the repo.

## 9. Resolved decisions (2026-06-27 — grounded via read-only filesystem investigations `wf_586f8b57-355` + `wf_84af0820-5ad`; **SP1 re-architected onto DAVINCI** 2026-06-27)
| # | Item | Resolution |
|---|---|---|
| R1 | Contract — time | Per-file valid time = **window center**, stored as a CF scalar `time` coord; filename `%s` stays window-start seconds; SP2 interpolates on the CF `time`. (§5) |
| R2 | Contract — companion vars | **Required:** `aod_count`, `aod_uncertainty` (derived in SP1). **Recommended:** per-sensor `aod_weighted_mean_modis/_viirs`. Add full provenance globals. (§5) |
| R3 | Contract — filename stem | `MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc` (free per contract; cleaner than legacy `terra_modis_npp_viirs_…`). |
| R4 | SP1 — products/sensors | MODIS Terra+Aqua MOD04/MYD04 **C6.1 (DT+DB)** + VIIRS NOAA-20 `AERDB_L2`; 550 nm. (§6) |
| R5 | SP1 — MODIS data | **Not on glade** → SP1 acquires MOD04/MYD04 from **LAADS DAAC via DAVINCI `earthaccess`/`stage_collection()`**; EarthData creds in **`~/.netrc`**. (§6) |
| R6 | SP1 — v1 scope | Build+validate on a **one-month test period — July 2008 (MODIS-only; predates VIIRS)**, staged under `/glade/work/fillmore/Data/CERES-SARB-CAM7/` via `scripts/stage_obs.py`; design to scale to 2000–2025. (§6) |
| R7 | SP1 — VIIRS bias | Prior unrecoverable → **define+document a new** correction, anchored to **AERONET**. (§6) |
| R8 | SP1 — QC/merge | Defaults: VIIRS `QA_Flag ≥ 2`, MODIS valid-retrieval QA, drop AOD∉[0,5]; **uncertainty-weighted** spatial/temporal/sensor merge (`w=1/σ²`). Tunable. (§6) |
| R9 | SP2 — delivery | **Dev `SourceMods/src.cam`; prod CAM fork** (ESCOMP/CAM @ `cam6_4_161`) via git-fleximod. (§7) |
| R10 | SP2 — test framework | **pFUnit** (confirmed integrated). (§8) |
| R11 | SP2 — hook point | `cam7/physpkg.F90::tphysac`, after `aerosol_wet_processes` (~L2015), before `radiation_tend` (~L2050). (§7) |
| R12 | SP2 — guards | `EPS_AOD=0.01`, `RATIO_MIN/MAX=0.1/10`, namelist-tunable + hit-rate diagnostics. (§7) |
| R13 | SP2 — namelist | `&aod_nudging_nl` via `namelist_definition.xml` (+ `namelist_defaults_cam.xml`); names per §7. |
| R14 | Number scales with mass | **Yes** (D4) — preserves modal size. |
| R15 | Run — aerosol scheme | **v1 targets MAM4 only**. All MAM5 work, including compatibility smoke tests and CI gates, is deferred indefinitely by user direction on 2026-06-28. |
| R16 | Run — met-nudging / spin-up | **ERA5** met-nudging (not MERRA-2) — CAM-ready f09/L32 at `/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl/` (`ERA5_fv09.cam2.i.*`), coexists with `&aod_nudging_nl`; **verify L32 matches production `nlev`**. Full `&nudging_nl` block + spin-up protocol in `RUN.md`. |
| R17 | SP1 — build-on | **Built on DAVINCI** (`davinci_monet`, MONET-based, `../DAVINCI`): SP1 = package `sp1_aod_pipeline/` in this repo *importing* it (pinned dep). **VIIRS `AERDB_L2` reader + uncertainty-aware binning contributed UPSTREAM to DAVINCI**; SP1 glue (bias, merge, contract writer, CLI) local. (§6) |
| R18 | SP1 — gridding | **Point-in-cell binning for v1** (reuse DAVINCI numba `bin_swath_to_grid`); true area-weighting deferred. (§6) |
| R19 | SP1 — AERONET λ | **Ångström-interpolate AERONET to 550 nm** for bias-anchoring + validation (AERONET native 500/675/870). (§6) |

**Grounded facts (from the investigation):** all CAM7 APIs the design depends on exist with matching signatures — `aerosol_optics_cam_sw` (`aerosol_optics_cam.F90:581`), `radconstants::idx_sw_diag`, generic `rad_cnst_get_info`/`_aer_mmr`/`_mode_num` (4 overloads → mode-agnostic), and `aerosol_state`/`aerosol_properties` polymorphic types. Those abstractions are **read-oriented**, so write-back of scaled mass+number uses direct `state%q` indexing via the `rad_cnst` index map. Legacy obs archive confirmed (`aod_weighted_mean[_modis/_viirs]`, `aod_count`, cell bounds, `_FillValue=-999`; no uncertainty/QA/provenance). Validation assets located (AERONET, CALIOP simulator).

## 10. Next steps
§9 is closed (see the R-table). Proceed:
1. Run `writing-plans` to produce **two** implementation plans — **SP1** (Python obs pipeline) and **SP2** (CAM7 module) — sharing the §5 contract; the contract is pinned first so both plans build against the same interface.
2. Implement with TDD (`test-driven-development`): SP2 against the verified CAM7 MAM4 build (pFUnit unit tests + MAM4 regression), SP1 in Python (pytest + golden-file tests + AERONET validation).

> Cross-account/new-session note: this repo (`NCAR/CERES-SARB-CAM7`) is the portable carrier and now tracks **everything** — `SPEC.md`, `BUILD.md`, `RUN.md`, the full `docs/` analysis tree (HANDOFF + reference + spike), and the `build-cesm-cam7` skill. Clone it and read `docs/HANDOFF.md` then this file. (Session memory under `~fillmore/.claude` does not travel across accounts; the repo is the source of truth.)
