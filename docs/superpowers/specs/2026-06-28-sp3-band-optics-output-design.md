# SPEC — SP3: Per-band 3D aerosol radiative-property output from CAM7 (MAM-LFL format)

*Design spec, 2026-06-28. Status: **design finalized; pending user review → `writing-plans`.** Self-contained so a fresh session can resume from the repo alone. Companions: `SPEC.md` (SP1/SP2 design), `docs/HANDOFF.md`, `docs/spike/CAM7-integration-surface.md`, reference repo `../CERES-SARB-MAM-LFL`.*

## 1. Goal & context
Add a third subsystem **SP3** to CERES-SARB-CAM7: emit the model's **3D aerosol radiative properties** — extinction, scattering, asymmetry — **per shortwave and longwave band**, in the **same NetCDF format produced by `../CERES-SARB-MAM-LFL`** (`mode_optics.py` / `external_mix.py`). Purpose: feed the CERES/SARB Langley Fu-Liou (LFL) radiative-transfer code with CAM7's *own* aerosol optics, so the optics SARB sees match the optics CAM's radiation used (including SP2's AOD nudging when active).

Platform: NCAR derecho. Base: CESM3 `cesm3_0_beta08` / CAM7 (`cam6_4_161`), RRTMGP, MAM4. Custom-code repo: `NCAR/CERES-SARB-CAM7`.

## 2. Scope & non-goals
**In scope (v1):** a namelist-gated in-CAM diagnostic that, at the radiation step, taps CAM's aerosol optics, remaps them onto the SARB/LFL bands, and writes per-band MAM-LFL-format NetCDF for the externally-mixed aerosol total.
**Non-goals (v1):** per-mode/per-species breakdown; reimplementing optics; non-f09 grids; ACI; changing radiation. SP3 is read-only w.r.t. the model state (pure diagnostic).

## 3. Locked design decisions
| # | Decision | Value |
|---|---|---|
| D1 | Optics source | **Extract CAM's own optics** — SW: tap `aerosol_optics_cam_sw`. LW: a local per-mode copy of `aerosol_optics_cam_lw`'s loop (stock routine returns only summed absorption); no reimplemented Köhler/Mie |
| D2 | Band set | **SARB/LFL bands** (14 SW + 12 LW), defined by `LFL_SW_bands`/`LFL_LW_bands` in the SARB optics-LUT template netCDF |
| D3 | Band remap | **Spectral-overlap weighting**: CAM RRTMGP bands (14 SW + 16 LW) → SARB bands; asm overlap-weighted by scattering |
| D4 | Granularity | **Externally-mixed total only** (sum over all MAM4 modes) — what RRTMGP uses |
| D4b | LW scattering | CAM LW LUT is absorption-only. Add a **simple prescribed scheme**: per-mode `ω_m`, `g_m` (namelist band-table) applied inside the per-mode loop → `ext_m=abs_m/(1−ω_m)`, `sca_m=ω_m·ext_m`, `asm=g_m`; summed across modes (sca adds, asm scattering-weighted). `ω_m=0` ⇒ stock abs-only; cap `ω_m≤0.9`. Upgradeable to per-column optics later |
| D5 | Output mechanism | **Direct Fortran writer** from CAM via **PIO** (no Python post-process) |
| D6 | Coupling | **Standalone diagnostic**, post-radiation tap — captures SP2 nudging when on, free model when off; usable in any CAM7 F-case |
| D7 | File layout | **Per-band files** (`sw01`…`lw12`), exactly like MAM-LFL |
| D8 | Cadence | **Namelist interval, default 3-hourly** (matches LFL/GEOS-IT cadence) |
| D9 | Grid | **f09 only** (consistent with SP1/SP2) |

## 4. Architecture
```
 radiation step (after SP2 nudge)
        │
        ▼
 [aod_optics_diag]  ── tap ──►  aerosol_optics_cam_sw  → tauxar, wa, ga   (14 SW RRTMGP bands)
        │                       aerosol_optics_cam_lw  → tauxar           (16 LW RRTMGP bands)
        │
        ├─ remap (spectral overlap) ──►  SARB bands (14 SW + 12 LW)
        │
        └─ PIO write ──► per-band MAM-LFL-format NetCDF  (one file per band per output time)
```
One new module **`aod_optics_diag.F90`** plus a hook in `physpkg.F90` (alongside the SP2 hook). No changes to optics or radiation; SP3 only *reads* state/pbuf and calls the existing optics routines.

## 5. The optics tap (D1)
- **SW:** `call aerosol_optics_cam_sw(list_idx, state, pbuf, nnite, idxnite, tauxar, wa, ga, fa)` returns, accumulated over modes (extensive, pre-RRTMGP-normalization):
  - `tauxar(pcols,0:pver,nswbands)` = Σ dopaer = **extinction OD**
  - `wa = Σ dopaer·palb` = τ·ssa = **scattering OD**
  - `ga = Σ dopaer·palb·pasm` = τ·ssa·g  (asymmetry numerator)
- **LW:** stock `aerosol_optics_cam_lw` returns only summed `tauxar` = absorption OD. SP3 uses a **local copy of its per-mode loop** so the mode index is in scope: for each mode get `pabs` (`lw_props`), form `abs_m`, then apply prescribed `ω_m, g_m` (D4b) → `ext_m=abs_m/(1−ω_m)`, `sca_m=ω_m·ext_m`; accumulate `Σ ext_m`, `Σ sca_m`, `Σ sca_m·g_m`. Final `asm = Σ(sca_m·g_m)/max(Σ sca_m, τ_thresh)`.
- **`list_idx`:** use the climate (radiation) optics list so the tap matches what RRTMGP used.
- **Caveat (carried from spike):** confirm calling these standalone has no side effects and that water uptake (`QAERWAT`/`DGNUMWET`) is current at the tap point (SP2 already refreshes water uptake before radiation; SP3 runs after, so state is consistent). Verify in the plan.

## 6. Band remap (D2, D3)
- **CAM native bands:** `nswbands`=14, `nlwbands`=16, edges from `radconstants` (`wavenum_low/high`, cm⁻¹).
- **SARB/LFL target bands** (read from `LFL_bands.nc` = `/glade/work/fillmore/Data/Optics/SARB/LFL_bands.nc`; units µm; path is a namelist input):
  - `LFL_SW_bands` — 15 edges → **14 SW bands**: `0.1754, 0.3225, 0.3575, 0.4375, 0.4975, 0.595, 0.6896, 0.794, 0.889, 1.042, 1.41, 1.9048, 2.5, 3.5088, 4`
  - `LFL_LW_bands` — 13 edges → **12 LW bands**: `4.54, 5.26, 5.88, 7.14, 8, 9.09, 10.2, 12.5, 14.9, 18.5, 25, 35.7, 100`
  - Coverage note: LFL SW band 1 (0.1754–0.3225 µm) extends past CAM's 50000 cm⁻¹ UV limit → partial overlap only (warn, don't abort).
- **Remap (per column, per layer):** for each SARB band *s*, weight contributing CAM bands *c* by the destination-normalized wavelength(or wavenumber)-overlap fraction `w_{sc}`. This treats optical-depth fields as band-representative values rather than spectral integrals:
  - extinction OD: `ext_s = Σ_c w_sc · tauxar_c`
  - scattering OD: `sca_s = Σ_c w_sc · wa_c`
  - asymmetry: `asm_s = (Σ_c w_sc · ga_c) / max(sca_s, τ_thresh)` (scattering-weighted; 0 below threshold)
- Overlap weights depend only on the two fixed band grids → precompute once at init. Define overlap in a single consistent coordinate (wavenumber); document the convention. Track destination coverage separately so partially covered SARB bands still warn without shrinking the covered band mean. `τ_thresh = 1e-5` (matches MAM-LFL).

## 7. Output contract (D5, D7) — match MAM-LFL exactly
- **One NetCDF per SARB band per output time.** Variables on `(lev, lat, lon)` (optionally leading `time` of size 1):
  - `DELP` — layer pressure thickness (from `state%pdel`), Pa
  - `Extinction_Layer_Optical_Depth` — ext OD (float32)
  - `Scattering_Layer_Optical_Depth` — sca OD (float32; LW from D4b prescribed scheme)
  - `Layer_Asymmetry_Parameter` — g (float32; LW from D4b prescribed scheme)
  - `Extinction_Column_Optical_Depth` — `Σ_lev` ext OD (float32)
- **Constraints (enforced, as MAM-LFL):** finite; ext ≥ 0; 0 ≤ sca ≤ ext; −1 ≤ asm ≤ 1.
- **Global attrs:** `scheme` (`MAM4`), `band` (`sw01`…`lw12`), `wavelength_um` (SARB band midpoint), `source` (`CAM7`), plus provenance: case name, git commit of SP3, creation date, `list_idx`, nudged flag (SP2 on/off).
- **Filename template:** namelist string, default mirrors MAM-LFL, e.g. `AER_MAM4_{band}.%y%m%d.%s.nc` (`%s` = seconds-of-day). Per-band token uppercase (`SW01`).
- **Grid/coords:** f09 `lat(192)`, `lon(288)`, hybrid `lev`; CF coordinates from CAM. Written via **PIO** (gathered global, consistent with CAM history I/O).

## 8. Placement & control (D6, D8)
- **Hook:** in `physpkg.F90`, at the radiation step, **after** the SP2 nudge/water-uptake refresh and the radiation call's optics are valid — so SP3 reflects the optics radiation used. Gate on `state%lchnk` chunk loop like other diagnostics.
- **Cadence:** namelist interval (default 3 h). Write only on output steps; cheap no-op otherwise.
- **Namelist `&aod_optics_diag_nl`:** `aod_optics_diag` (logical, default `.false.`), `aod_optics_diag_interval` (default 3 h), `aod_optics_diag_outdir`, `aod_optics_diag_filename`, `aod_optics_sarb_band_file` (LFL band-grid netCDF), `aod_optics_lw_omega_g_file` (per-mode `ω_m`, `g_m` LW table; D4b). Added via `namelist_definition.xml` + defaults, mirroring SP2.

## 9. Error handling
- Missing/invalid SARB band file → `endrun` at init with a clear message.
- Optics tap returns non-finite → clamp per §7 constraints and count; if any remain non-finite, `endrun`.
- I/O failure → `endrun` (do not silently drop output).
- SP3 never modifies model state; a fault aborts the diagnostic, not the science run's physics (init-time validation makes faults early).

## 10. Testing
- **pFUnit unit test** (mirrors SP2 `test/`): the **band-remap kernel** — given synthetic CAM-band optics + two band grids, assert overlap weights sum correctly, ext/sca/asm conservation, asm scattering-weighting, and the ext≥sca≥0 / |asm|≤1 invariants. LW D4b path: assert `ext=abs/(1−ω)`, `sca=ω·ext`, `ω=0 ⇒ sca=0`, and `ω` cap.
- **Format-conformance test (Python):** a written sample file validates against `external_mix.py`'s `REQUIRED_VARIABLES`, dims (`SUPPORTED_LAYER_DIMS`), and `_validate_optical_depths` — i.e. SP3 output is a legal MAM-LFL input.
- **Smoke run:** short CAM7 f09 run with `aod_optics_diag=.true.`; confirm per-band files appear at the interval, AODVIS-band column matches CAM's `AODVIS` to tolerance (sanity that the tap = what radiation used), and DAVINCI renders a SARB-band AOD map.
- **Diagnostic-plot suite (VP1–VP7) + LLM gate:** DAVINCI renders column-AOD / SSA / asymmetry maps, an SW/LW spectral profile, a vertical profile, and an LW-window scattering map; the **LLM reads each PDF and confirms physical correctness** against explicit criteria (dust/biomass/pollution structure, ω/g ranges, LW scattering gated by the ω/g table). A plot lacking the expected physics fails the gate.
- **10-day interactive verification run:** real July-2008 f09 run on an interactive derecho node with SP3 on; includes a **bit-for-bit read-only proof** (SP3-on model state ≡ SP3-off via `cprnc`), format/physical/spectral checks, and the LLM-gated VP suite on the 10-day mean.

## 11. Open items (resolve in plan, not blockers)
1. Exact `list_idx` / climate-list index and confirmation that the SW/LW tap has no pbuf side effects at the post-radiation point.
2. ~~SARB band edges + count~~ **RESOLVED**: confirmed 14 SW / 12 LW from `LFL_bands.nc` (edges listed in §6). SW/LW overlap at the 2.5–4 µm / 4.54 µm boundary handled by the overlap remap.
3. Whether RRTMGP applies the dust-asphericity `dopaer` update (lines ~908–925) — tap *after* it so SP3 matches radiation.
4. PIO decomposition reuse from CAM history vs a dedicated decomp.
5. Vertical index origin: SW `tauxar` is `0:pver`, LW is `1:pver` — align both to the LFL `lev` convention on write.
6. Default per-mode `ω_m`, `g_m` (D4b): defined per **CAM LW band** (applied before the §6 remap), seeded from MAM-LFL's LW Mie (`mie_lognormal`/`refine_lut`) band-averaged onto the 16 CAM LW bands per MAM4 mode; document derivation. `ω=0` table reproduces stock absorption-only LW.
