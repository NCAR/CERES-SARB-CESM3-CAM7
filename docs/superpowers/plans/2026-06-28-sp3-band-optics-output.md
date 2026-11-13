# SP3 — Per-band 3D aerosol optics output (MAM-LFL format) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit CAM7's own per-band 3D aerosol optics (extinction OD, scattering OD, asymmetry) on the SARB/LFL bands, in the MAM-LFL NetCDF format, as a namelist-gated in-CAM diagnostic.

**Architecture:** A pure math kernel (band-overlap remap + prescribed LW scattering + mode mixing, pFUnit-tested) is driven by four thin CAM modules: a band/table reader, a CAM-internals optics tap (reusing `aerosol_optics_cam_sw` and a new per-mode LW routine), a PIO per-band writer, and a driver hooked into `physpkg` right after the SP2 nudge. SP3 never mutates model state.

**Tech Stack:** Fortran (CAM7 / `r8`), PIO, pFUnit, CIME/build-namelist XML; Python (xarray) for format-conformance + DAVINCI verification. Reference format: `../CERES-SARB-MAM-LFL/{mode_optics,external_mix}.py`.

## Global Constraints
- Base: CESM3 `cesm3_0_beta08` / CAM7 (`cam6_4_161`), RRTMGP, **MAM4**, **f09 only** (192 lat × 288 lon).
- Working precision `r8` everywhere; CAM mods delivered as SourceMods + tracked `.diff` files under `src/cam/` (mirror SP2).
- CAM native bands: **`nswbands=14`, `nlwbands=16`** (`radconstants`; SW edges ≈ 820–50000 cm⁻¹, LW edges ≈ 10–3250 cm⁻¹). SARB/LFL target bands: **14 SW + 12 LW**, edges read from `LFL_bands.nc` (`/glade/work/fillmore/Data/Optics/SARB/LFL_bands.nc`), vars `LFL_SW_bands`, `LFL_LW_bands`, units **µm**:
  - `LFL_SW_bands` (15 edges → 14 bands): `0.1754, 0.3225, 0.3575, 0.4375, 0.4975, 0.595, 0.6896, 0.794, 0.889, 1.042, 1.41, 1.9048, 2.5, 3.5088, 4`
  - `LFL_LW_bands` (13 edges → 12 bands): `4.54, 5.26, 5.88, 7.14, 8, 9.09, 10.2, 12.5, 14.9, 18.5, 25, 35.7, 100`
  - Remap is in **wavenumber** (`nu_cm⁻¹ = 1.e4 / λ_µm`). Weights are destination-normalized over the CAM-covered part of each SARB band, so output optical-depth fields remain band-representative values. Coverage edge case: LFL SW band 1 (0.1754–0.3225 µm = 31000–57000 cm⁻¹) extends past CAM's 50000 cm⁻¹ UV limit → partial coverage warning only; the covered part gets CAM's bluest band.
- Output variable names are EXACT (MAM-LFL): `DELP`, `Extinction_Layer_Optical_Depth`, `Scattering_Layer_Optical_Depth`, `Layer_Asymmetry_Parameter`, `Extinction_Column_Optical_Depth`.
- Invariants (enforced, as `external_mix.py`): finite; `ext ≥ 0`; `0 ≤ sca ≤ ext`; `−1 ≤ asym ≤ 1`. `τ_thresh = 1.e-5`. LW ω cap `ω ≤ 0.9`.
- Mode mixing: scattering OD adds; asymmetry is scattering-weighted (carry `scag = sca·g` extensive, divide at the end).
- SP3 is a **pure diagnostic**: read-only on `state`/`pbuf`; a fault aborts the diagnostic via `endrun`, never silently degrades.
- Plots via DAVINCI (`davinci_monet`), PDFs, global domain (AGENTS.md). Every diagnostic plot is **read back by the LLM and confirmed against explicit physical criteria** (Task 12) — a plot that doesn't show the expected physics is a FAIL, not a pass.

---

## File Structure

**Create (CAM, `src/cam/`):**
- `aod_optics_kernel.F90` — PURE, CAM-agnostic: overlap weights, extensive remap, LW scattering, asym-from-scaweighted, clamps. (pFUnit-tested.)
- `aod_optics_bands.F90` — read `LFL_bands.nc` + LW ω/g table; build CAM→SARB weight matrices at init via the kernel; getters.
- `aod_optics_tap.F90` — the ONLY module touching CAM optics internals: SW via `aerosol_optics_cam_sw`; LW via the new per-mode routine; returns CAM-band mixed `(ext, sca, scag)`.
- `aod_optics_io.F90` — gather physics chunks to global + write one MAM-LFL-format NetCDF per SARB band via PIO.
- `aod_optics_diag_intr.F90` — driver: `readnl`/`init`/`timestep_init`/`timestep_tend`; public `aod_optics_on`.
- `test/test_aod_optics_kernel.pf` — pFUnit tests for the kernel.

**Modify / diffs (CAM):**
- `aerosol_optics_cam.F90.diff` — add public `aerosol_optics_cam_lw_permode` (per-bin LW absorption; needs the module's private state).
- `physpkg.F90.diff` — add 3 SP3 hooks (compose with SP2's).
- `runtime_opts.F90.diff` — add `aod_optics_readnl`.
- `namelist/namelist_definition.xml`, `namelist/namelist_defaults_cam.xml`, `build-namelist.diff` — `&aod_optics_nl`.
- `test/CMakeLists.txt` — add the SP3 pFUnit target.

**Create (Python, `sp3_tests/`):**
- `test_format_conformance.py` — a written SP3 file is a legal MAM-LFL input (reuses `external_mix.py` validators).
- `make_omega_g_table.py` — generate the default per-mode/per-CAM-LW-band ω,g from MAM-LFL LW Mie; ω=0 fallback reproduces abs-only.
- `verify_sp3.py` — DAVINCI VP for a smoke-run band file.

**Dependencies:** T1 → T2; T3 → T4; T1,T2,T4,T5 → T6 → T7; T8 independent; T9 supports T6's default; T10 last.

---

## Task 1: Pure optics kernel + pFUnit tests

**Files:**
- Create: `src/cam/aod_optics_kernel.F90`
- Create: `src/cam/test/test_aod_optics_kernel.pf`
- Modify: `src/cam/test/CMakeLists.txt`

**Interfaces:**
- Produces:
  - `subroutine overlap_weights(nsrc, src_lo, src_hi, ndst, dst_lo, dst_hi, w, coverage)` — `w(ndst,nsrc)`, `w(i,j) = |overlap(j,i)| / Σ_j |overlap(j,i)|` for each covered destination band. Optional `coverage(i) = Σ_j |overlap(j,i)| / |dst_hi(i)-dst_lo(i)|`. Bands in any consistent monotone coordinate (wavenumber cm⁻¹).
  - `pure function remap_extensive(nsrc, ndst, w, src) result(dst)` — `dst(i)=Σ_j w(i,j)·src(j)`; `src(nsrc)`, `dst(ndst)`.
  - `elemental subroutine lw_scatter(abso, omega, g, omega_cap, ext, sca, scag)` — `ow=min(omega,omega_cap)`; `ext=abso/(1-ow)`; `sca=ow·ext`; `scag=sca·g`.
  - `elemental function asym_from_scaweighted(scag, sca, tau_thresh) result(asym)` — `merge(scag/sca, 0, sca>tau_thresh)`.
  - `elemental subroutine clamp_layer(ext, sca, asym)` — `sca=max(0,min(sca,ext))`; `asym=max(-1,min(1,asym))`.
  - `real(r8), parameter, public :: TAU_THRESH = 1.e-5_r8`, `OMEGA_CAP = 0.9_r8`.

- [ ] **Step 1: Write the failing test** — `src/cam/test/test_aod_optics_kernel.pf`

```fortran
module test_aod_optics_kernel
use funit
use shr_kind_mod, only: r8 => shr_kind_r8
use aod_optics_kernel, only: overlap_weights, remap_extensive, lw_scatter, &
                             asym_from_scaweighted, clamp_layer, TAU_THRESH, OMEGA_CAP
implicit none
contains

  @Test
  subroutine weights_tiling_average_sum_to_one()
    ! Two equal-width source bands tile one dst band: each weight = 0.5.
    real(r8) :: w(1,2)
    call overlap_weights(2, [0._r8,1._r8], [1._r8,2._r8], 1, [0._r8], [2._r8], w)
    @assertEqual(0.5_r8, w(1,1), tolerance=1.e-12_r8)
    @assertEqual(0.5_r8, w(1,2), tolerance=1.e-12_r8)
  end subroutine weights_tiling_average_sum_to_one

  @Test
  subroutine weights_subset_preserves_source_value()
    ! Source [0,2] fully covers dst [0,1]: weight = 1 and coverage = 1.
    real(r8) :: w(1,1)
    call overlap_weights(1, [0._r8], [2._r8], 1, [0._r8], [1._r8], w)
    @assertEqual(1._r8, w(1,1), tolerance=1.e-12_r8)
  end subroutine weights_subset_preserves_source_value

  @Test
  subroutine weights_no_overlap_zero()
    real(r8) :: w(1,1)
    call overlap_weights(1, [0._r8], [1._r8], 1, [2._r8], [3._r8], w)
    @assertEqual(0._r8, w(1,1), tolerance=1.e-12_r8)
  end subroutine weights_no_overlap_zero

  @Test
  subroutine remap_returns_band_representative_od()
    ! dst OD = width-weighted mean of the two source ODs when both tile dst.
    real(r8) :: w(1,2), dst(1)
    call overlap_weights(2, [0._r8,1._r8], [1._r8,2._r8], 1, [0._r8], [2._r8], w)
    dst = remap_extensive(2, 1, w, [0.3_r8, 0.5_r8])
    @assertEqual(0.4_r8, dst(1), tolerance=1.e-12_r8)
  end subroutine remap_returns_band_representative_od

  @Test
  subroutine lw_scatter_basic()
    real(r8) :: ext, sca, scag
    call lw_scatter(0.10_r8, 0.5_r8, 0.6_r8, OMEGA_CAP, ext, sca, scag)
    @assertEqual(0.20_r8, ext,  tolerance=1.e-12_r8)   ! 0.1/(1-0.5)
    @assertEqual(0.10_r8, sca,  tolerance=1.e-12_r8)   ! 0.5*0.2
    @assertEqual(0.06_r8, scag, tolerance=1.e-12_r8)   ! 0.1*0.6
  end subroutine lw_scatter_basic

  @Test
  subroutine lw_scatter_omega_zero_is_absorption_only()
    real(r8) :: ext, sca, scag
    call lw_scatter(0.10_r8, 0._r8, 0.6_r8, OMEGA_CAP, ext, sca, scag)
    @assertEqual(0.10_r8, ext,  tolerance=1.e-12_r8)
    @assertEqual(0._r8,   sca,  tolerance=1.e-12_r8)
    @assertEqual(0._r8,   scag, tolerance=1.e-12_r8)
  end subroutine lw_scatter_omega_zero_is_absorption_only

  @Test
  subroutine lw_scatter_caps_omega()
    real(r8) :: ext, sca, scag
    call lw_scatter(0.10_r8, 0.99_r8, 0.6_r8, OMEGA_CAP, ext, sca, scag)
    @assertEqual(1.0_r8, ext, tolerance=1.e-12_r8)     ! 0.1/(1-0.9)
  end subroutine lw_scatter_caps_omega

  @Test
  subroutine asym_weighted_and_threshold()
    @assertEqual(0.6_r8, asym_from_scaweighted(0.06_r8, 0.10_r8, TAU_THRESH), tolerance=1.e-12_r8)
    @assertEqual(0._r8,  asym_from_scaweighted(0.06_r8, 1.e-9_r8, TAU_THRESH), tolerance=1.e-12_r8)
  end subroutine asym_weighted_and_threshold

  @Test
  subroutine clamp_enforces_invariants()
    real(r8) :: ext, sca, asym
    ext = 0.2_r8; sca = 0.3_r8; asym = 1.5_r8
    call clamp_layer(ext, sca, asym)
    @assertEqual(0.2_r8, sca,  tolerance=1.e-12_r8)    ! sca capped to ext
    @assertEqual(1.0_r8, asym, tolerance=1.e-12_r8)    ! asym capped to 1
  end subroutine clamp_enforces_invariants

end module test_aod_optics_kernel
```

- [ ] **Step 2: Add the test to the build** — append to `src/cam/test/CMakeLists.txt`

```cmake
# --- SP3 optics kernel test ---
set(pf_sources_optics test_aod_optics_kernel.pf)
set(sources_needed_optics aod_optics_kernel.F90)
extract_sources("${sources_needed_optics}" "${cam_sources}" test_sources_optics)
create_pFUnit_test(aod_optics aod_optics_exe "${pf_sources_optics}" "${test_sources_optics}")
target_link_libraries(aod_optics_exe csm_share)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd src/cam/test && python /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/system/../../../cime/scripts/lib/... ` — use the project's pFUnit runner exactly as SP2 does (see SP2 plan Task for `run_tests.py --test-spec-dir`).
Expected: FAIL/`build error` — `aod_optics_kernel` module not found.

- [ ] **Step 4: Implement the kernel** — `src/cam/aod_optics_kernel.F90`

```fortran
module aod_optics_kernel
!-----------------------------------------------------------------------------
! PURE, CAM-agnostic optics math for SP3 (band-output diagnostic).
!   overlap_weights        : CAM-band -> SARB-band overlap weight matrix
!   remap_extensive        : apply the weight matrix to an extensive quantity
!   lw_scatter             : prescribed LW single-scatter from absorption OD
!   asym_from_scaweighted  : scattering-weighted asymmetry with threshold
!   clamp_layer            : enforce 0<=sca<=ext, |asym|<=1
! No CAM dependencies (only working precision). Unit-tested with pFUnit.
!-----------------------------------------------------------------------------
  use shr_kind_mod, only: r8 => shr_kind_r8
  implicit none
  private

  public :: overlap_weights, remap_extensive, lw_scatter
  public :: asym_from_scaweighted, clamp_layer
  real(r8), parameter, public :: TAU_THRESH = 1.e-5_r8
  real(r8), parameter, public :: OMEGA_CAP  = 0.9_r8

contains

  subroutine overlap_weights(nsrc, src_lo, src_hi, ndst, dst_lo, dst_hi, w)
    integer,  intent(in)  :: nsrc, ndst
    real(r8), intent(in)  :: src_lo(nsrc), src_hi(nsrc), dst_lo(ndst), dst_hi(ndst)
    real(r8), intent(out) :: w(ndst,nsrc)
    integer  :: i, j
    real(r8) :: slo, shi, dlo, dhi, ov, width
    w = 0._r8
    do j = 1, nsrc
      slo = min(src_lo(j), src_hi(j)); shi = max(src_lo(j), src_hi(j))
      width = shi - slo
      if (width <= 0._r8) cycle
      do i = 1, ndst
        dlo = min(dst_lo(i), dst_hi(i)); dhi = max(dst_lo(i), dst_hi(i))
        ov  = min(shi, dhi) - max(slo, dlo)
        if (ov > 0._r8) w(i,j) = ov / width
      end do
    end do
  end subroutine overlap_weights

  pure function remap_extensive(nsrc, ndst, w, src) result(dst)
    integer,  intent(in) :: nsrc, ndst
    real(r8), intent(in) :: w(ndst,nsrc), src(nsrc)
    real(r8)             :: dst(ndst)
    integer :: i
    do i = 1, ndst
      dst(i) = sum(w(i,:) * src(:))
    end do
  end function remap_extensive

  elemental subroutine lw_scatter(abso, omega, g, omega_cap, ext, sca, scag)
    real(r8), intent(in)  :: abso, omega, g, omega_cap
    real(r8), intent(out) :: ext, sca, scag
    real(r8) :: ow
    ow   = max(0._r8, min(omega, omega_cap))
    ext  = abso / (1._r8 - ow)
    sca  = ow * ext
    scag = sca * g
  end subroutine lw_scatter

  elemental function asym_from_scaweighted(scag, sca, tau_thresh) result(asym)
    real(r8), intent(in) :: scag, sca, tau_thresh
    real(r8)             :: asym
    if (sca > tau_thresh) then
      asym = scag / sca
    else
      asym = 0._r8
    end if
  end function asym_from_scaweighted

  elemental subroutine clamp_layer(ext, sca, asym)
    real(r8), intent(inout) :: ext, sca, asym
    if (ext  < 0._r8)  ext  = 0._r8
    if (sca  < 0._r8)  sca  = 0._r8
    if (sca  > ext )   sca  = ext
    if (asym < -1._r8) asym = -1._r8
    if (asym >  1._r8) asym =  1._r8
  end subroutine clamp_layer

end module aod_optics_kernel
```

- [ ] **Step 5: Run the test to verify it passes**

Run: the same pFUnit runner as Step 3.
Expected: PASS (9 tests).

- [ ] **Step 6: Commit**

```bash
git add src/cam/aod_optics_kernel.F90 src/cam/test/test_aod_optics_kernel.pf src/cam/test/CMakeLists.txt
git commit -m "SP3 Task 1: pure optics remap/scatter/mix kernel + pFUnit tests"
```

---

## Task 2: Band + ω/g table reader (`aod_optics_bands.F90`)

**Files:**
- Create: `src/cam/aod_optics_bands.F90`
- Reference: `radconstants.F90:73` (`get_sw_spectral_boundaries`), `:95` (`get_lw_spectral_boundaries`); `cam_pio_utils.F90` (`cam_pio_openfile`, `cam_pio_get_var`).

**Interfaces:**
- Consumes: `overlap_weights` (Task 1); `radconstants`: `nswbands`, `nlwbands`, `get_sw_spectral_boundaries`, `get_lw_spectral_boundaries`.
- Produces:
  - `subroutine aod_optics_bands_init(band_file, lw_table_file)` — reads SARB band edges + LW ω/g; sets `nsw_sarb`, `nlw_sarb`, builds `w_sw(nsw_sarb,nswbands)`, `w_lw(nlw_sarb,nlwbands)`.
  - `integer, public :: nsw_sarb, nlw_sarb`
  - `real(r8), allocatable, public :: w_sw(:,:), w_lw(:,:)`        ! CAM→SARB weights
  - `real(r8), allocatable, public :: sarb_sw_mid(:), sarb_lw_mid(:)` ! band-midpoint µm (for `wavelength_um` attr)
  - `real(r8), allocatable, public :: omega_lw(:,:), g_lw(:,:)`    ! (nlwbands, nbins) prescribed LW ω,g
  - `integer, public :: nbins_lw`                                  ! mode/bin count in the ω/g table
  - `character(len=*), parameter, public :: SW_LABEL_FMT='(\"sw\",i2.2)'`, `LW_LABEL_FMT='(\"lw\",i2.2)'`

**Implementation notes (no separate pFUnit — validated at init + smoke; the math is already unit-tested in Task 1):**
- Read `LFL_SW_bands` (n+1 edges → `nsw_sarb` bands) and `LFL_LW_bands` from `band_file` via `cam_pio_openfile`+`cam_pio_get_var`; convert wavelength edges (µm) to wavenumber (cm⁻¹: `nu = 1.e4/lambda_um`) so both grids share the coordinate `overlap_weights` expects.
- Get CAM band edges with `get_sw_spectral_boundaries(lo, hi, 'cm^-1')` / `get_lw_spectral_boundaries(...)`.
- Call `overlap_weights` once each for SW and LW → `w_sw`, `w_lw`.
- Read ω/g from `lw_table_file` (vars `omega_lw(nlwbands, nbins)`, `g_lw(...)`); validate first dim == `nlwbands`; set `nbins_lw`. If `lw_table_file==''` → allocate ω=0, g=0 with `nbins_lw=1` (reproduces stock absorption-only LW).
- Expect **15 SW edges → `nsw_sarb=14`** and **13 LW edges → `nlw_sarb=12`** (the Global Constraints values); log all edges at init. `endrun` with a clear message on: missing file, unexpected edge count. For a SARB band extending outside CAM coverage (LFL SW band 1 past 50000 cm⁻¹): **log a warning, do not abort** — `overlap_weights` already yields the partial weight.

- [ ] **Step 1: Implement `aod_optics_bands_init` and module state** (code per notes above; reuse the exact `cam_pio_*` calls SP2's obs reader uses — see `aod_nudging_obs.F90`).
- [ ] **Step 2: Build CAM** (login node, conda-free, per `BUILD.md`) to compile-check the module: `qcmd`-free `./case.build` of the smoke case from Task 10, or `gmake` the unit-test target. Expected: compiles.
- [ ] **Step 3: Commit**

```bash
git add src/cam/aod_optics_bands.F90
git commit -m "SP3 Task 2: SARB band + LW omega/g reader; build CAM->SARB weights"
```

---

## Task 3: Per-mode LW absorption routine (diff to `aerosol_optics_cam.F90`)

**Files:**
- Create: `src/cam/aerosol_optics_cam.F90.diff` (SourceMod: copy `components/cam/src/physics/cam/aerosol_optics_cam.F90` into the case `SourceMods/src.cam/`, add the new public routine, record the diff).

**Why a diff, not a new module:** the bin loop needs this module's PRIVATE state (`aero_props`, `aero_state` construction, `modal_active`/`carma_active`/`bulk_active`, `num_aero_models`, `crefwsw`, `crefwlw`, `rga`, `numrh`). Reuse it in place.

**Interfaces:**
- Produces (add to the module's `public` list and `contains`):
  - `subroutine aerosol_optics_cam_lw_permode(list_idx, state, pbuf, max_nbins, nbins_out, tauxar_bin)`
    - `integer, intent(in) :: list_idx, max_nbins`
    - `integer, intent(out) :: nbins_out`
    - `real(r8), intent(out) :: tauxar_bin(pcols,pver,nlwbands,max_nbins)` ! per-bin LW absorption OD

**Implementation:** copy the body of `aerosol_optics_cam_lw` (lines 1335–1514) and change ONLY:
- signature/declarations: add `max_nbins`, `nbins_out`, replace `tauxar(...)` out-arg with `tauxar_bin(...)`.
- before the loops: `tauxar_bin = 0._r8`; keep a running global bin counter `ig = 0`.
- inside `binloop`, accumulate into the per-bin slice: replace
  `tauxar(icol,ilev,iwav) = tauxar(icol,ilev,iwav) + dopaer(icol)`
  with `tauxar_bin(icol,ilev,iwav,ig) = tauxar_bin(icol,ilev,iwav,ig) + dopaer(icol)`,
  where `ig` is incremented once per `(iaermod,ibin)` at the top of `binloop` (`ig = ig + 1; if (ig>max_nbins) call endrun(prefix//'max_nbins too small')`).
- set `nbins_out = ig` after the loops.
- DELETE the `outfld('TOTABSLW'...)` / `outfld('AODABSLW'...)` calls (this routine is a pure tap; no history side effects).
- keep all `aero_state`/`aero_optics` construction and `deallocate` exactly as the stock routine.

- [ ] **Step 1: Copy stock file to SourceMods and add the routine** (per above).
- [ ] **Step 2: Compile-check** via the smoke-case build. Expected: compiles; existing `aerosol_optics_cam_lw` unchanged.
- [ ] **Step 3: Record the diff and commit**

```bash
cd <case>/SourceMods/src.cam && diff -u <stock>/aerosol_optics_cam.F90 aerosol_optics_cam.F90 > /glade/work/fillmore/CERES-SARB-CAM7/src/cam/aerosol_optics_cam.F90.diff
cd /glade/work/fillmore/CERES-SARB-CAM7
git add src/cam/aerosol_optics_cam.F90.diff
git commit -m "SP3 Task 3: add aerosol_optics_cam_lw_permode (per-bin LW absorption tap)"
```

---

## Task 4: CAM optics tap (`aod_optics_tap.F90`)

**Files:**
- Create: `src/cam/aod_optics_tap.F90`

**Interfaces:**
- Consumes: `aerosol_optics_cam_sw` (`aerosol_optics_cam`); `aerosol_optics_cam_lw_permode` (Task 3); `lw_scatter` (Task 1); `omega_lw`,`g_lw`,`nbins_lw` (Task 2); `radconstants`: `nswbands`,`nlwbands`; `ppgrid`: `pcols`,`pver`.
- Produces:
  - `subroutine sw_camband_optics(state, pbuf, ext, sca, scag)` — `ext/sca/scag(pcols,pver,nswbands)` mixed over modes; `ext=tauxar(:,1:pver,:)`, `sca=wa`, `scag=ga`.
  - `subroutine lw_camband_optics(state, pbuf, ext, sca, scag)` — calls the per-mode LW tap; applies `lw_scatter` with `omega_lw/g_lw` per bin/band; sums over bins → `ext/sca/scag(pcols,pver,nlwbands)`.

**Implementation:**
- SW: mirror `aod_nudging_optics.F90::model_aod550` setup (zero `tauxar/wa/ga/fa`, `idxnite=1`, `nnite=0`, `LIST_CLIMATE=0`), call `aerosol_optics_cam_sw(0, state, pbuf, 0, idxnite, tauxar, wa, ga, fa)`, then copy levels `1:pver` into `ext/sca/scag`.
- LW: allocate `tauxar_bin(pcols,pver,nlwbands,max_nbins)` with `max_nbins=nbins_lw` (or a safe upper bound, e.g. 8); call `aerosol_optics_cam_lw_permode(0, state, pbuf, max_nbins, nbins_out, tauxar_bin)`; loop `ib=1..nbins_out`, `iwav=1..nlwbands`: `call lw_scatter(tauxar_bin(:,:,iwav,ib), omega_lw(iwav,ib), g_lw(iwav,ib), OMEGA_CAP, e, s, sg)` and accumulate `ext+=e; sca+=s; scag+=sg`. Map bin index→ω/g row by position (modal bins are modes a1..a4, in `aero_props` order).

- [ ] **Step 1: Implement both subroutines** (per above).
- [ ] **Step 2: Compile-check** via smoke-case build. Expected: compiles.
- [ ] **Step 3: Commit**

```bash
git add src/cam/aod_optics_tap.F90
git commit -m "SP3 Task 4: CAM-band SW/LW optics tap (mode-summed ext/sca/scag)"
```

---

## Task 5: PIO per-band writer (`aod_optics_io.F90`)

**Files:**
- Create: `src/cam/aod_optics_io.F90`
- Reference: `phys_grid.F90:2532` (`gather_chunk_to_field`); `cam_pio_utils.F90` (`cam_pio_createfile`,`cam_pio_def_dim`,`cam_pio_def_var`); `pio` (`pio_put_var`,`pio_enddef`,`pio_closefile`,`pio_subsystem`).

**Interfaces:**
- Produces:
  - `subroutine write_band_file(fname, band_label, wavelength_um, scheme, ext, sca, asym, delp, col, lat, lon, lev)` where `ext/sca/asym/delp(pcols,pver,begchunk:endchunk)` (one SARB band), `col(pcols,begchunk:endchunk)`, and coord arrays. Writes one NetCDF in MAM-LFL format.

**Implementation (gather-to-root + PIO whole-array write; f09 is small):**
- For each layer field, `call gather_chunk_to_field(1, pver, 1, plon*plat, local, global3d)` (and the 2-D `col`) to assemble `global3d(plon,plat,pver)` on `pio_subsystem`'s io-root (== masterproc).
- Build the file on all tasks: `cam_pio_createfile(File, fname)`; `cam_pio_def_dim(File,'lon',plon,did_lon)`, `'lat'`,`plat`, `'lev'`,`pver`; define coord vars `lat,lon,lev` and the five MAM-LFL vars with dims `(lon,lat,lev)` (layer vars) / `(lon,lat)` (`Extinction_Column_Optical_Depth`); put global attrs `scheme`, `band=band_label`, `wavelength_um`, `source='CAM7'`, `nudged` (from a flag), creation date, git commit.
- `pio_enddef(File)`; `pio_put_var(File, vid_*, global*)` (the non-distributed put writes from the io-root buffer the gather filled); `pio_closefile(File)`.
- Transpose to MAM-LFL dim order `(lev,lat,lon)` on write (define dims in that order; PIO writes Fortran-fastest-first, so define `lon` fastest → file shows `(lev,lat,lon)`). Confirm against the conformance test (Task 8).

- [ ] **Step 1: Implement `write_band_file`** (per above).
- [ ] **Step 2: Compile-check** via smoke-case build. Expected: compiles.
- [ ] **Step 3: Commit**

```bash
git add src/cam/aod_optics_io.F90
git commit -m "SP3 Task 5: gather + PIO per-band MAM-LFL-format writer"
```

---

## Task 6: Driver / interface (`aod_optics_diag_intr.F90`)

**Files:**
- Create: `src/cam/aod_optics_diag_intr.F90`

**Interfaces:**
- Consumes: Tasks 1,2,4,5; `time_manager` (`get_curr_date`,`get_nstep`,`get_step_size`); `radiation` (`radiation_do`); `phys_grid`/`ppgrid`.
- Produces: `aod_optics_readnl(nlfile)`, `aod_optics_init()`, `aod_optics_timestep_init(phys_state)`, `aod_optics_timestep_tend(state,pbuf)`, `logical, public :: aod_optics_on`.

**Namelist `&aod_optics_nl`:** `aod_optics_on` (`.false.`), `aod_optics_interval_hours` (`3`), `aod_optics_outdir` (`''`), `aod_optics_template` (`'AER_MAM4_{band}.%y%m%d.%s.nc'`), `aod_optics_band_file` (`''` → LFL_bands.nc), `aod_optics_lw_table` (`''` → ω=0). Mirror `aod_nudging_readnl` exactly (read on masterproc, `MPI_bcast` each var).

**`aod_optics_init`:** `if (.not. aod_optics_on) return`; `call aod_optics_bands_init(aod_optics_band_file, aod_optics_lw_table)`; optional `addfld('AODSARB_<band>', ...)` diagnostics if a diag flag is set.

**`aod_optics_timestep_tend(state, pbuf)`** (one chunk):
1. gate: `if (.not. aod_optics_on) return`; `if (.not. on_output_step()) return` (output-step test from `aod_optics_interval_hours` vs current time, like SP2 cadence).
2. `call sw_camband_optics(state, pbuf, ext_cam, sca_cam, scag_cam)`.
3. SW remap per layer/column: `ext_sarb(:,k,s)=remap_extensive(nswbands,nsw_sarb,w_sw,ext_cam(:,k,:))` (loop columns/levels), same for sca/scag; `asym=asym_from_scaweighted(scag,sca,TAU_THRESH)`; `call clamp_layer(...)`; `col=sum(ext_sarb,dim=lev)`.
4. accumulate into the chunk's output buffers; on the LAST chunk of the step, hand the gathered fields to `write_band_file` for each of the `nsw_sarb` SW + `nlw_sarb` LW bands (filenames from the template with `{band}`,`%y%m%d`,`%s`).
5. repeat 2–4 for LW via `lw_camband_optics`.

**Placement note:** because SP3 recomputes optics from `state`, calling it right after the SP2 nudge (before `radiation_tend`) yields the exact optics radiation uses — no dependence on radiation having run.

- [ ] **Step 1: Implement the driver** (readnl + init + timestep_init cadence + timestep_tend pipeline).
- [ ] **Step 2: Compile-check** via smoke-case build. Expected: compiles.
- [ ] **Step 3: Commit**

```bash
git add src/cam/aod_optics_diag_intr.F90
git commit -m "SP3 Task 6: driver (readnl/init/tend); tap->remap->clamp->write pipeline"
```

---

## Task 7: Wire SP3 into CAM (diffs + namelist XML)

**Files:**
- Modify: `src/cam/physpkg.F90.diff`, `src/cam/runtime_opts.F90.diff`, `src/cam/build-namelist.diff`
- Modify: `src/cam/namelist/namelist_definition.xml`, `src/cam/namelist/namelist_defaults_cam.xml`

**Hooks (mirror SP2 exactly):**
- `runtime_opts.F90`: `use aod_optics_diag_intr, only: aod_optics_readnl` + `call aod_optics_readnl(nlfilename)` (next to `aod_nudging_readnl`).
- `physpkg.F90` `phys_init`: `use aod_optics_diag_intr, only: aod_optics_on, aod_optics_init` + `if (aod_optics_on) call aod_optics_init()`.
- `physpkg.F90` `phys_timestep_init`: `+ if (aod_optics_on) call aod_optics_timestep_init(phys_state)`.
- `physpkg.F90` `tphysac`: immediately AFTER the SP2 `aod_nudging` block (still before `radiation_tend`):
```fortran
    if (aod_optics_on) then
       call t_startf('aod_optics_diag')
       call aod_optics_timestep_tend(state, pbuf)
       call t_stopf('aod_optics_diag')
    end if
```
- `namelist_definition.xml`: add an `<entry>` per `&aod_optics_nl` var (copy the `aod_nudge_on` entry block format).
- `namelist_defaults_cam.xml`: add `<aod_optics_on>.false.</aod_optics_on>` … one per var.
- `build-namelist`: `add_default($nl, 'aod_optics_on');` … one per var.

- [ ] **Step 1: Apply all hook + XML edits.**
- [ ] **Step 2: Regenerate namelist** (`./preview_namelist` in the smoke case) → confirm `&aod_optics_nl` appears with defaults.
- [ ] **Step 3: Commit**

```bash
git add src/cam/physpkg.F90.diff src/cam/runtime_opts.F90.diff src/cam/build-namelist.diff src/cam/namelist/
git commit -m "SP3 Task 7: wire &aod_optics_nl + physpkg/runtime_opts hooks"
```

---

## Task 8: Python format-conformance test (`sp3_tests/`)

**Files:**
- Create: `sp3_tests/test_format_conformance.py`

**Interfaces:**
- Consumes: `../CERES-SARB-MAM-LFL/external_mix.py` (`REQUIRED_VARIABLES`, `LAYER_VARIABLES`, `SUPPORTED_LAYER_DIMS`, `_validate_optical_depths`, `mix_mode_datasets`).

- [ ] **Step 1: Write the failing test**

```python
import sys, numpy as np, xarray as xr, pytest
sys.path.insert(0, "/glade/work/fillmore/CERES-SARB-MAM-LFL")
import external_mix as em

REQ = ("DELP", "Extinction_Layer_Optical_Depth", "Scattering_Layer_Optical_Depth",
       "Layer_Asymmetry_Parameter", "Extinction_Column_Optical_Depth")

def _synthetic(path):
    nlev, nlat, nlon = 4, 3, 5
    ext = np.abs(np.random.rand(nlev, nlat, nlon)).astype("f4") * 0.1
    sca = (ext * 0.7).astype("f4")
    asm = np.full_like(ext, 0.6)
    delp = np.full_like(ext, 1000.0)
    ds = xr.Dataset(
        {"DELP": (("lev","lat","lon"), delp),
         "Extinction_Layer_Optical_Depth": (("lev","lat","lon"), ext),
         "Scattering_Layer_Optical_Depth": (("lev","lat","lon"), sca),
         "Layer_Asymmetry_Parameter": (("lev","lat","lon"), asm),
         "Extinction_Column_Optical_Depth": (("lat","lon"), ext.sum(0))},
        attrs={"scheme": "MAM4", "band": "sw01", "wavelength_um": 0.55, "source": "CAM7"})
    ds.to_netcdf(path)

def test_sp3_file_is_legal_mam_lfl_input(tmp_path):
    p = tmp_path / "AER_MAM4_SW01.20080701.0.nc"
    _synthetic(p)
    ds = xr.open_dataset(p)
    for v in REQ:
        assert v in ds, f"missing {v}"
    assert ds["Extinction_Layer_Optical_Depth"].dims in em.SUPPORTED_LAYER_DIMS
    # external_mix accepts the file as a mixable mode dataset (runs its validators)
    mixed = em.mix_mode_datasets([ds])
    assert "Extinction_Column_Optical_Depth" in mixed
```

- [ ] **Step 2: Run it.** `cd /glade/work/fillmore/CERES-SARB-CAM7 && python -m pytest sp3_tests/test_format_conformance.py -v`. Expected: PASS (this fixes the contract; the real SP3 file is checked against it in Task 10).
- [ ] **Step 3: Commit**

```bash
git add sp3_tests/test_format_conformance.py
git commit -m "SP3 Task 8: format-conformance test vs external_mix.py validators"
```

---

## Task 9: Default ω/g table generator (`sp3_tests/make_omega_g_table.py`)

**Files:**
- Create: `sp3_tests/make_omega_g_table.py`

**Goal:** produce `aod_lw_omega_g.nc` with `omega_lw(nlwbands=16, nbins=4)`, `g_lw(16,4)` — band-representative LW single-scatter albedo + asymmetry per MAM4 mode, derived from MAM-LFL's LW Mie (`mie_lognormal`/`refine_lut`), band-averaged onto the 16 CAM LW bands (`get_lw_spectral_boundaries`). Provide `--omega-zero` to emit an all-zero table (reproduces stock absorption-only LW) as the safe default.

- [ ] **Step 1:** implement the generator (import MAM-LFL `mie_lognormal`; for each mode's canonical `σ_g`,`r_dry`, integrate Mie ω,g over each CAM LW band; write NetCDF). Document the derivation in a header comment + a one-paragraph note in the spec's §11.
- [ ] **Step 2:** run `python sp3_tests/make_omega_g_table.py --omega-zero -o /glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lw_omega_g_zero.nc` and the physical version; sanity-check ω∈[0,0.9], g∈[-1,1].
- [ ] **Step 3: Commit**

```bash
git add sp3_tests/make_omega_g_table.py
git commit -m "SP3 Task 9: LW omega/g table generator (MAM-LFL Mie seed; omega=0 fallback)"
```

---

## Task 10: Smoke run + verification

**Files:**
- Create: `sp3_tests/verify_sp3.py` (DAVINCI VP suite; renders VP1–VP7 with `--plot {vpN|all}`; physical criteria + LLM gate in Task 12)
- Reference: `BUILD.md`, `RUN.md`, `docs/science-verification.md`

- [ ] **Step 1: Build + short run.** Reuse a July-2008 MAM4 f09 case (per `RUN.md`); add the SP3 SourceMods (Tasks 3–6) + the namelist:
```
&aod_optics_nl
  aod_optics_on = .true.
  aod_optics_interval_hours = 3
  aod_optics_outdir = '/glade/derecho/scratch/fillmore/sp3_smoke/'
  aod_optics_band_file = '<path>/LFL_bands.nc'
  aod_optics_lw_table  = '<path>/aod_lw_omega_g_zero.nc'
/
```
Run ~6 timesteps (login/interactive per BUILD.md). Expected: per-band files `AER_MAM4_SW01.20080701.*.nc` … `LW12` appear at the 3-h interval.

- [ ] **Step 2: Format conformance on the REAL file.** Point Task 8's validators at a written smoke file:
`python -m pytest sp3_tests/test_format_conformance.py -v` adapted to load the smoke path. Expected: PASS.

- [ ] **Step 3: Physical sanity.** Confirm the SW band nearest 550 nm reproduces CAM's own `AODVIS`: `Extinction_Column_Optical_Depth` (that band) vs `AODVIS` from the same run, global-mean rel. diff < 1e-3 (both come from `aerosol_optics_cam_sw`). LW ω=0 file → `Scattering_Layer_Optical_Depth==0`. Then swap the physical ω/g table → LW scattering > 0, `sca ≤ ext` holds.

- [ ] **Step 4: Render + LLM-read one sanity map.** `verify_sp3.py --plot vp1` renders the 550 nm SARB-band column-AOD map (PDF, global, GEOSIT style) under `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/smoke/`. **Read** the PDF and confirm the AOD field is finite, non-negative, and not blank/uniform (6 timesteps is too short for climatology — full physical gate is Task 11/12). The full VP suite is defined in Task 12.

- [ ] **Step 5: Commit + record**

```bash
git add sp3_tests/verify_sp3.py
git commit -m "SP3 Task 10: smoke run + format/physical/DAVINCI verification"
```
Update `docs/HANDOFF.md` with SP3 status and the smoke-run metrics.

---

## Task 11: 10-day interactive-node verification run

**Files:**
- Modify: `RUN.md` (append to the run log), `docs/HANDOFF.md` (SP3 status)
- Reference: `RUN.md` (interactive PBS pattern: SP2 transport proof ran foreground in a `qsub -I` allocation), `BUILD.md`.

**Goal:** exercise SP3 over a real 10-day f09 window on an interactive derecho compute node, and prove SP3 is a true read-only diagnostic (SP3-on ≡ SP3-off model state, bit-for-bit).

- [ ] **Step 1: Configure the 10-day case.** Reuse the Task 10 case (SP3 SourceMods built). Set the run length and SP3 output:
```bash
cd <case>
./xmlchange STOP_OPTION=ndays,STOP_N=10,REST_OPTION=ndays,REST_N=10
./xmlchange JOB_WALLCLOCK_TIME=04:00:00
# &aod_optics_nl: aod_optics_on=.true., interval=3h, physical LW table aod_lw_omega_g.nc (Task 9)
./preview_run     # confirm 1 node / 128 MPI tasks PE layout + throughput estimate
```

- [ ] **Step 2: Grab an interactive allocation and run foreground.** (No `case.submit` to batch — run inside the allocation, as the SP2 transport proof did.)
```bash
qsub -I -A P19010000 -q main -l select=1:ncpus=128:mpiprocs=128 -l walltime=04:00:00
# in the interactive shell:
cd <case> && ./case.submit --no-batch
```
Expected: `CaseStatus: model execution success`; per-band files `AER_MAM4_{SW01..LW12}.2008070[1-9..].*.nc` for all 10 days × 8 windows in `aod_optics_outdir` (≈ 80 times × 26 bands).

- [ ] **Step 3: Read-only proof (key verification).** Clone an SP3-OFF twin sharing the executable, run the same 10 days, and compare model history bit-for-bit:
```bash
cd <cases_dir>
<scripts>/create_clone --case sp3_verify10_off --clone <case> --keepexe
cd sp3_verify10_off && ./xmlchange ... # aod_optics_on=.false.; SP2 setting identical to the ON case
qsub -I ...; ./case.submit --no-batch
# compare a model field unaffected by diagnostics (cprnc returns IDENTICAL):
cprnc <on_run>/*.cam.h0.2008-07-10*.nc <off_run>/*.cam.h0.2008-07-10*.nc | grep -E "IDENTICAL|DIFF"
```
Expected: **IDENTICAL** for all model fields (AODVIS, T, Q, …) — SP3 perturbs nothing.

- [ ] **Step 4: Format + physical + spectral checks over the run.**
  - Format conformance on a mid-run file: `python -m pytest sp3_tests/test_format_conformance.py` pointed at `AER_MAM4_SW01.20080705.*.nc`. Expected PASS.
  - 550 nm SW band `Extinction_Column_Optical_Depth` vs `AODVIS` from the ON run, 10-day global-mean rel. diff < 1e-3.
  - Physical ω/g table → `Scattering_Layer_Optical_Depth` > 0 in LW window bands; `sca ≤ ext` and `|asym| ≤ 1` hold for every band/time (assert in `verify_sp3.py`).
  - Time continuity: 80 output times per band, no gaps; no NaNs.

- [ ] **Step 5: Diagnostic-plot suite + LLM physical-correctness gate.** Run **Task 12** against this 10-day output: render the full VP suite from the 10-day mean and have the LLM read each PDF and confirm physical correctness. This is the SP3 acceptance gate.

- [ ] **Step 6: Record + commit.** Append the run to `RUN.md` (case, compset/res, 10 days, # PEs, wallclock, throughput, output path, IDENTICAL result, outcome) and update `docs/HANDOFF.md`.
```bash
git add RUN.md docs/HANDOFF.md
git commit -m "SP3 Task 11: 10-day interactive verification run + read-only proof"
```

---

## Task 12: Diagnostic-plot suite + LLM physical-correctness gate

**Files:**
- Use: `sp3_tests/verify_sp3.py` (created in Task 10)
- Modify: `RUN.md` / `docs/HANDOFF.md` (record verdicts)
- Reference: `AGENTS.md` (DAVINCI, PDF, global, GEOSIT style), `docs/science-verification.md` (the project's plot-based gate + prior multimodal-inspection precedent).

**Goal:** turn the SP3 output into a fixed suite of DAVINCI diagnostic plots, then have the **LLM read each rendered PDF and confirm physical correctness** against explicit criteria. A plot that does not show the expected physics is a FAIL → `superpowers:systematic-debugging`, not a rationalized pass.

**The VP suite (`verify_sp3.py`, from the Task 11 10-day mean unless noted; PDF, global, GEOSIT AOD style where a map):**

| ID | Plot | Field | Physical pass criteria the LLM must confirm |
|----|------|-------|---------------------------------------------|
| VP1 | SW column-AOD map | `Extinction_Column_Optical_Depth`, 550 nm SARB band | High AOD over Saharan/Arabian/Asian **dust**, central-African + S-American + boreal **biomass burning**, E/S-Asian **pollution**; low over remote oceans/poles; finite, ≥0, not blank/uniform. |
| VP2 | SW single-scatter albedo map | ω = Σ`sca`/Σ`ext`, visible band | More **absorbing** (ω≈0.80–0.92) over biomass-burning + dust; near-conservative (ω≈0.95–1.0) over sulfate/sea-salt/remote ocean. ω∈[0,1] everywhere. |
| VP3 | SW asymmetry map | g (scattering-weighted column), visible band | g≈0.6–0.78; **larger** over coarse dust/sea-salt, **smaller** over fine smoke/pollution; g∈[−1,1]. |
| VP4 | SW spectral profile | ext, ω, g vs SARB SW band, at a dust column and a pollution column | **Pollution** AOD falls steeply with wavelength (Ångström); **dust** AOD ~flat/weakly increasing; g rises with wavelength; curves smooth, no band spikes. |
| VP5 | Vertical profile | `Extinction_Layer_Optical_Depth` vs level, dust column (e.g. Saharan Air Layer) | Extinction concentrated in lower/mid troposphere with the expected elevated dust layer; →0 in stratosphere; non-negative. |
| VP6 | LW window scattering map | `Scattering_Layer_Optical_Depth` column, 8–12 µm SARB LW band | With the **physical** ω/g table: LW scattering localized to coarse-**dust** regions, near-zero elsewhere, `sca ≤ ext`. With the **ω=0** table: identically zero (renders empty). Confirms D4b. |
| VP7 | LW absorption map | `Extinction_Layer_Optical_Depth` column, LW window band | Dust-dominated LW signal; magnitude smaller than the SW AOD; physical geographic pattern. |

- [ ] **Step 1: Implement the VP suite in `verify_sp3.py`.** One function per VP using DAVINCI `SpatialPlotter` (maps) / line plots (profiles); `--plot {vp1..vp7|all}`; `--indir`, `--outdir`. Maps use `style_preset="geosit_aod"`; titles in title case per AGENTS.md; output PDFs under `/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP3_band_optics/verify10/`. Also render a PNG copy of each to the session scratchpad for vision (temporary; not a tracked product).

- [ ] **Step 2: Render the suite.** `python sp3_tests/verify_sp3.py --plot all --indir <10day_outdir> --outdir <.../verify10/>`. Expected: VP1–VP7 PDFs (+ scratch PNGs).

- [ ] **Step 3: LLM physical-correctness gate.** For EACH VPn: **Read** the rendered PDF (or scratch PNG) and check it against the criteria above. Write a one-line verdict per plot: `VPn: PASS — <observed physical structure>` or `VPn: FAIL — <what is wrong>`. Do not pass a plot whose described physics is absent. Run VP6 twice (ω=0 table → must render empty; physical table → must show dust scattering) to prove the LW scheme is actually active and gated.

- [ ] **Step 4: On any FAIL** → invoke `superpowers:systematic-debugging` (trace remap weights / ω-g table / tap band index / write transpose); fix; re-render; re-read. Only proceed when all seven PASS.

- [ ] **Step 5: Record + commit.** Append the seven verdicts (with observed structure) to `RUN.md` and `docs/HANDOFF.md`.

```bash
git add sp3_tests/verify_sp3.py RUN.md docs/HANDOFF.md
git commit -m "SP3 Task 12: VP1-VP7 diagnostic-plot suite + LLM physical-correctness gate"
```

---

## Self-Review

**Spec coverage:** D1 tap → T3/T4; D2/D3 bands+remap → T1/T2; D4 total → T4/T6; D4b LW ω/g → T1/T3/T4/T9; D5 PIO writer → T5; D6 standalone post-nudge → T6/T7; D7 per-band files → T5/T6; D8 cadence → T6; D9 f09 → constraints. §5 tap, §6 remap, §7 contract, §8 placement, §9 errors, §10 testing all mapped (T10 fast smoke; T11 10-day interactive run + bit-for-bit read-only proof; T12 VP1–VP7 diagnostic-plot suite + LLM physical-correctness gate). Open items §11 → T3 (list_idx/side-effects via the `model_aod550` precedent), T2 (SARB band counts validated at init), T4/T10 (asphericity update is inside the SW routine we call, so we inherit it), T5 (decomp), T4/T5 (`0:pver` vs `1:pver` handled in T4/T5).

**Placeholder scan:** kernel + conformance steps carry full code; CAM-coupled tasks carry exact signatures, the precise stock-routine edits, and compile/smoke verification (they cannot be pFUnit'd without the full model — same split as SP2, whose optics/io are run-validated and only the kernel is unit-tested).

**Type consistency:** `(ext, sca, scag)` triple carried T4→T6; `asym` derived once via `asym_from_scaweighted`; `w_sw/w_lw(ndst,nsrc)` consumed by `remap_extensive(nsrc,ndst,...)`; `omega_lw/g_lw(nlwbands,nbins)` produced T2/T9, consumed T4; `aerosol_optics_cam_lw_permode` signature identical in T3 (produce) and T4 (consume).
