# CAM7 / CESM3 (`cesm3_0_beta08`) — AOD-Nudging Integration Surface

*Spike findings, 2026-06-27. Vanilla checkout: `/glade/work/fillmore/CESM3/cesm3_0_beta08` (CAM tag `cam6_4_161`). Maps where a clean AOD-nudging module hooks into CAM7, so the design's CAM-abstraction boundary is grounded in real APIs. Line numbers are approximate (read the files to confirm).*

## TL;DR for the design
- **CAM7 is a much better host than CAM6 for a clean rewrite.** It already provides **polymorphic aerosol abstractions** (`aerosol_state`, `aerosol_properties`) and a **generic constituent-enumeration API** (`rad_cnst_get_info` / `rad_cnst_get_aer_mmr`). Our nudging code can be **mode-agnostic** (MAM4 *and* MAM5) with no hard-coded 27-species lists — the single worst trait of the prior attempt disappears for free.
- **Reuse CAM7's own optics; do not reimplement.** `aerosol_optics_cam_sw` computes per-band aerosol optical depth from the aerosol state; column AOD at 550 nm is the `idx_sw_diag` band. This replaces the prior attempt's duplicated Köhler+Mie code.
- **The prior LARC Mie tables (`Mie_io/mam4_mode*_larc_*.nc`) do NOT transfer.** CAM7 uses Chebyshev-parameterized optics tables (`extpsw/abspsw/asmpsw`) in its physprop netCDFs. We don't need the old tables — we call CAM7's optics.
- **Radiation is RRTMGP** (`rte-rrtmgp v1.9.2`), confirmed. Aerosol optics reach it via `aer_rad_props` → `rrtmgp_inputs_cam`. This is the path to use if/when we want **radiative feedback** from nudged aerosol (likely required for CERES/SARB).
- **A met-nudging module already exists to emulate**: `src/physics/cam/nudging.F90` (Newtonian relaxation of U/V/T/Q toward reanalysis, `&nudging_nl`). Mirror its lifecycle for AOD.

## Build spike status
- Compset **`F2000dev`** = `2000_CAM70_CLM60%SP_CICE%PRES_DOCN%DOM_MOSART_SGLC_SWAV`, res `f09_f09_mg17`, machine `derecho`, compiler `intel`. Built on the **login node** (no batch account available; build needs none — `case.submit` will).
- `CAM_CONFIG_OPTS = -phys cam7`; resolved **`chem = ghg_mam4`** → **MAM4 active** (GHG chemistry + prognostic MAM4 aerosols). Confirmed via `Buildconf/camconf/config_cache.xml` and `CaseDocs/atm_in` (`mode_defs='mam4_mode1:accum...'`).
- `create_newcase` **requires a PROJECT** on derecho (`PROJECT_REQUIRED=true`); used a placeholder `NEEDACCT` for the build. **We need the real project/account code from the user for any run (and for compute-node builds via `qcmd`).**
- Build result: see `docs/HANDOFF.md` / the case at `/glade/work/fillmore/CESM3/cases/spike_f2000dev_cam7` (exe under `/glade/derecho/scratch/fillmore/spike_f2000dev_cam7/bld`).

### CAM7 chem/aerosol menu (from `config_cache.xml`) — relevant options
- **MAM4:** `trop_mam4`, `trop_strat_mam4_ts2`, **`trop_strat_mam4_vbs`** (← CAM7 analog of the reference's CCTS1), `trop_strat_mam4_vbsext`, `trop_strat_mam4_slh`, `ghg_mam4`, `geoschem_mam4`.
- **MAM5:** `trop_strat_mam5_slh`, `trop_strat_mam5_t1s1/_t1s2/_t2s1/_t4s2`, `trop_strat_mam5_vbsext`, `waccm_*_mam5`.
- MAM5 = MAM4 + a 5th **coarse stratospheric sulfate** mode — relevant if nudging stratospheric AOD.

---

## 1. Aerosol optics & AOD diagnosis (reuse these)

**Key files** (`components/cam/`):
| Path | Role |
|---|---|
| `src/physics/cam/aerosol_optics_cam.F90` | Top-level optics dispatcher; computes per-band aerosol τ for modal/CARMA/bulk; **outputs AODVIS (550nm), AODUV (350nm), AODNIR (1020nm)** |
| `src/physics/cam/aer_rad_props.F90` | Radiation interface; prepares τ, τ·w, τ·w·g, τ·w·f for the radiation driver |
| `src/chemistry/aerosol/refractive_aerosol_optics_mod.F90` | Modal Mie/Chebyshev optics: `sw_props(ncol,ilev,iwav,pext,pabs,palb,pasm)` — wet refractive index → Chebyshev-interpolated specific extinction |
| `src/chemistry/aerosol/aerosol_optics_mod.F90` | Abstract optics interface (`sw_props`/`lw_props` deferred procedures) |
| `src/physics/cam/phys_prop.F90` | Reads modal optics netCDFs (`extpsw/abspsw/asmpsw`, refr/refi tables; dims `ncoef/prefr/prefi`) |
| `src/physics/cam/aer_vis_diag_mod.F90` | Column-sum AOD diagnostic output (incl. stratospheric `AODVISst`) |
| `src/physics/rrtmgp/radiation.F90` | RRTMGP driver (confirms RRTMGP, not RRTMG) |
| `src/physics/rrtmgp/rrtmgp_inputs_cam.F90` | Loads aerosol optics into RRTMGP optical-property objects |
| `src/physics/rrtmgp/radconstants.F90` | Public band indices `idx_sw_diag` (550nm), `idx_uv_diag` (350nm), `idx_nir_diag` (1020nm) |
| `src/chemistry/utils/modal_aero_wateruptake.F90` | Köhler water uptake; stores `DGNUMWET`, `QAERWAT` in pbuf — reusable |

**How model AOD is computed:** for each SW band and level, `aerosol_optics_cam_sw` computes wet diameter + aerosol water (RH-dependent via `water_uptake`), forms the volume-weighted wet complex refractive index, Chebyshev-interpolates specific extinction `pext` (m²/kg), multiplies by layer mass (`dopaer = pext·mass`), and accumulates band τ; column AOD = vertical sum at `idx_sw_diag`.

**Adapter hook points (call, don't reimplement):**
```fortran
use aerosol_optics_cam, only: aerosol_optics_cam_sw
use radconstants,       only: idx_sw_diag
! compute current model column AOD at 550 nm from the (possibly nudged) state:
call aerosol_optics_cam_sw(0, state, pbuf, nnite, idxnite, tauxar, wa, ga, fa)
aod_550(:ncol) = sum(tauxar(:ncol,:,idx_sw_diag), dim=2)
```
**Caveat:** verify whether calling `aerosol_optics_cam_sw` standalone (outside the radiation step) has side effects / pbuf dependencies; may need water-uptake recomputed after we modify masses.

---

## 2. Aerosol state: MAM4/MAM5 & generic enumeration (the abstraction win)

**Modes & species** (`bld/build-namelist`, `src/chemistry/aerosol/modal_aero_data.F90`):
- **MAM4:** mode1 accum {so4,pom,soa,bc,dst,ncl}, mode2 aitken {so4,soa,ncl,dst}, mode3 coarse {dst,ncl,so4}, mode4 primary_carbon {pom,bc}. Constituents named `so4_a1`, `num_a1`, `dst_a3`, `pom_a4`, …
- **MAM5:** MAM4 + mode5 `coarse_strat` {so4}.

**Generic enumeration API** (`src/physics/cam/rad_constituents.F90`) — **use this instead of hard-coding**:
```fortran
call rad_cnst_get_info(0, nmodes=nmodes)
do m = 1, nmodes
   call rad_cnst_get_info(0, m, nspec=nspec, mode_type=mode_type)
   do l = 1, nspec
      call rad_cnst_get_info(0, m, l, spec_name=spec_name)
      call rad_cnst_get_aer_mmr(0, m, l, 'a', state, pbuf, mmr)   ! interstitial mass
   end do
   call rad_cnst_get_mode_num(0, m, state, pbuf, num)
end do
```
Index maps live in `modal_aero_data.F90` (`lmassptr_amode`, `numptr_amode`).

**Polymorphic abstractions** (let nudging code be representation-agnostic):
- `src/chemistry/aerosol/aerosol_state_mod.F90` (base) + `modal_aerosol_state_mod.F90` (impl): `get_ambient_mmr`, `get_ambient_num`, `water_uptake`, `wet_diameter`, …
- `src/chemistry/aerosol/aerosol_properties_mod.F90` (base) + `modal_aerosol_properties_mod.F90` (impl): `nbins`, `nspecies`, `optics_params`, `species_type`, `model_is`, …

**Default scheme per compset:** standard CAM7 base (`-phys cam7`) defaults to **`ghg_mam4` → MAM4** (confirmed by this spike). CAM-chem trop/strat compsets select MAM4 or MAM5 via the chem package (e.g. `trop_strat_mam4_vbs` vs `trop_strat_mam5_*`). WACCM variants use MAM5. *(Note: an earlier explorer claimed base CAM7 has "no aerosol model" — the build disproves that; base CAM7 = MAM4.)*

**Implication:** the adapter's "enumerate aerosol mass" and "write increment back" operations are written **once** against `rad_cnst_*` / the `aerosol_state` API and work for MAM4, MAM5, (and in principle other schemes) unchanged.

---

## 3. Physics integration, met-nudging template, build & namelist

**Physics driver / hook point:** `src/physics/cam7/physpkg.F90` (CAM7 has its own `cam7/` driver dir alongside shared `src/physics/cam/`). The clean hook is in **`tphysac`**, *after* modal aerosol water uptake / wet deposition and *before* radiation/diagnostics — so the nudge sees a fully-updated aerosol state and feeds the next radiation call. Lifecycle calls mirror the met-nudging wiring: `*_readnl` in `phys_init`, `*_timestep_init` in `phys_timestep_init`, `*_timestep_tend` in `tphysac` (followed by `physics_update` + `check_energy_chng`).

**Existing module to emulate** — `src/physics/cam/nudging.F90`:
- `nudging_readnl` (namelist `&nudging_nl`) → `nudging_init` (allocate Target/Model arrays per chunk, `addfld` diagnostics, read first analysis) → `nudging_timestep_init` (load analysis files, compute windows/timescales) → `nudging_timestep_tend` (fill `phys_tend`, `outfld`) → `nudging_final`.
- Reads analysis netCDF via `cam_pio_openfile` + `infld`; relaxation `F = α·(Target−Model)/τ`. **This is the architectural template** — and note our design will choose forcing vs. this relaxation deliberately (the prior attempt disabled the relaxation path).

**Adding our code to the build:**
- **SourceMods/src.cam/** — drop-in `.F90`, compiled automatically. Fast for dev; not version-controlled with CAM. (This is how the prior attempt did *everything* — a key cause of its mess.)
- **CAM fork via `git-fleximod`** — fork ESCOMP/CAM, point the `cam` submodule (`.gitmodules` `fxtag`/url) at our fork. Version-controlled, reproducible, shareable. **Recommended for the real implementation**, given our `NCAR/CERES-SARB-CAM7` repo. Design decision: fork CAM vs keep new modules in `CERES-SARB-CAM7` and inject via a thin SourceMods/symlink layer.

**Namelist mechanism:** declare a new `&nudging_AOD_nl` group + defaults in `bld/namelist_files/namelist_definition.xml` and `namelist_defaults_cam.xml`; `build-namelist` emits `atm_in`.

**Diagnostics:** `cam_history` (`addfld`/`outfld`) for nudged-AOD and increment fields; `physics_buffer` (`pbuf_add_field`/`pbuf_get_field`) for cross-step state (e.g. target AOD, wet diameter `DGNUMWET`, water `QAERWAT`).

---

## 4. Answers to the spike's original questions
1. **Does beta08 build CAM7 on derecho?** → see HANDOFF (build in progress/result). create_newcase needs a PROJECT.
2. **RRTMGP vs RRTMG?** → **RRTMGP** confirmed.
3. **MAM4 vs MAM5?** → both available; base CAM7 = MAM4; CAM-chem/WACCM select either. Our code should be mode-agnostic via `rad_cnst_*`.
4. **Where is column AOD diagnosed?** → `aerosol_optics_cam.F90` / `aer_vis_diag_mod.F90`, band `idx_sw_diag` (550 nm).
5. **Do the prior LARC Mie tables transfer?** → **No**; CAM7 uses Chebyshev optics tables in its physprop files. Reuse CAM7 optics instead.

## 5. Open items
- Confirm the F2000dev **build succeeds** (toolchain proof). If we want a fully representative build, also try a `trop_strat_mam4_vbs` / `mam5` CAM-chem compset (heavier; needs the real account for compute-node build).
- Get the **PROJECT/account code** from the user (blocks runs and `qcmd` builds).
- Decide **CAM fork vs SourceMods-injection** for `CERES-SARB-CAM7`.
- Verify side effects of calling `aerosol_optics_cam_sw` standalone, and whether water uptake must be recomputed after we modify masses.
