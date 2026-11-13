# SP2 — In-CAM7 AOD-Nudging Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add a clean, mode-agnostic, tested CAM7 module that reads the frozen contract obs file, diagnoses model column AOD@550nm by reusing CAM7's own optics, forms a clamped obs/model ratio, and hard-overwrites every aerosol species mass and mode number mixing ratio before radiation so RRTMGP sees the nudged aerosol (direct effect).

**Architecture:** Four small Fortran modules with strict separation: a PURE CAM-agnostic kernel (`aod_nudging_kernel`), a single CAM-abstraction adapter that is the ONLY code touching CAM7 internals (`aod_nudging_optics`), an IO reader (`aod_nudging_obs`), and a driver mirroring CAM's `nudging.F90` lifecycle (`aod_nudging_intr`). The driver is wired into `cam7/physpkg.F90::tphysac` after aerosol wet processes and before `radiation_tend`. Mode-agnosticism comes from enumerating constituents with `rad_constituents::rad_cnst_*` (no hard-coded species/mode counts), but active SP2 work is MAM4-only; all MAM5 validation/runs are deferred indefinitely by user direction on 2026-06-28.

**Tech Stack:** Fortran 2008 (CAM7 / CESM3 `cesm3_0_beta08`, CAM `cam6_4_161`), RRTMGP radiation, PIO/`infld` IO, pFUnit unit tests via CIME `fortran_unit_testing`, Python 3 (numpy/netCDF4) for the synthetic contract-file generator, CIME case scripting on NCAR derecho.

## Global Constraints  (every task implicitly includes these)
- Platform: NCAR derecho; project/account `P19010000` (`create_newcase` needs `--project P19010000`).
- Base checkout (build sandbox + CAM-fork working tree): `/glade/work/fillmore/CESM3/cesm3_0_beta08`; CAM src root: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam`.
- Custom repo (version control + portability): `/glade/work/fillmore/CERES-SARB-CAM7`.
- Primary model for SP2 development, science runs, and routine verification: `F2000dev` (CAM7, MAM4) at res `f09_f09_mg17`, machine `derecho`, compiler `intel`. Build verified per `BUILD.md`. MAM5 work is deferred indefinitely: do not run MAM5 smoke tests, create MAM5 plots, add MAM5 CI gates, rebuild MAM5 cases for SP2, or treat MAM5 as a current science configuration unless the user explicitly reopens that scope.
- Grid: f09 = lat(192) x lon(288), FV 0.9x1.25 deg. AOD wavelength: 550 nm only (`radconstants::idx_sw_diag`).
- Obs-file contract (frozen) is the ONLY coupling to SP1: netCDF4, one file per 3-hour window; primary var `aod_weighted_mean(lat,lon)`, `units="1"`, `_FillValue=-999.`; filename template `MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc` with `%s` = window-start seconds-of-day zero-padded to 5 digits (`interpret_filename_spec` uses `(i5.5)`); the **filename** stem is keyed to window-START seconds, but the in-file scalar CF `time` coordinate carries the window-CENTER valid time (contract §5). SP2 builds candidate filenames from the model date + the 8 window-start seconds, then **reads each bracketing file's scalar `time` (center) and time-interpolates on those file values** (contract: "SP2 time-interpolates between the two bracketing files using their scalar `time` (center) values").
- Grid identity (contract): the obs file grid MUST equal CAM's f09 grid exactly (no in-model interpolation). SP2 **aborts on dimension mismatch** (explicit `lat==192`/`lon==288` and CAM-grid-size check in `aod_nudging_obs::load_window`).
- Cadence (SPEC D6): apply the overwrite at the model's **radiation cadence** (gate on `radiation::radiation_do('sw')`), AND time-interpolate the 3-hourly obs to the current time. Both halves of D6 are required.
- Fill value `-999.` means "no valid obs here" -> leave that column untouched (ratio = 1).
- Guards (namelist-tunable): `aod_eps=0.01` (skip near-zero model AOD), `aod_ratio_min=0.1`, `aod_ratio_max=10.0`. Emit **per-step ratio hit-rate + clamp-hit diagnostics** (SPEC R12 / §7): fraction of columns nudged and how often the ratio hit `rmin`/`rmax`, logged once per radiation step (MPI-reduced to masterproc).
- MUST avoid hard-coded species names, mode counts, or `pcnst`-sized aerosol arrays; enumerate via `rad_cnst_get_info`/`rad_cnst_get_aer_mmr`/`rad_cnst_get_mode_num` only. This keeps the adapter portable, but MAM4 is the only active validation/run target.
- ACI hook present but OFF by default (`aod_aci_on=.false.`): scale interstitial-phase ('a') mass + number only; do NOT touch cloud-borne ('c'). The flag is LIVE — it is read in `readnl`, broadcast, logged, and passed to `apply_scaling(...,aci_on)`, which routes to a guarded cloud-borne ('c') path (a clean `endrun` + a marked future-implementation insertion point) so the interface is ACI-ready without silently doing unvalidated work in v1.
- TDD where unit-testable (the kernel); frequent commits; NO placeholders (every code/test/command shown in full).
- Delivery: primary dev edits the checkout's CAM source tree directly (it is the future fork working tree, and the pFUnit harness compiles from it); the same `.F90` files are also valid as a `caseroot/SourceMods/src.cam` copy-in overlay for single-case fast iteration. Canonical copies are mirrored into the repo `src/cam/` for version control.
- Build rule (BUILD.md): build / run unit tests on a LOGIN node in a CONDA-FREE env (scrub miniforge from `PATH`, `unset CONDA_PREFIX`), giving CIME a `python3` shim.
- Interactive-node option: a derecho **interactive** compute node with internet (verified: github + EarthData reachable) can do the whole MAM4 loop — build (conda-free, as above) AND run the smoke tests (Tasks 8/9) within wallclock, **no batch queue**. For the run, use **`./case.submit --no-batch`** (foreground) after setting a PE layout that fits the node (`./xmlchange NTASKS=<≤ allocated cores>` → `./case.setup --reset` → rebuild; the default f09 batch layout exceeds one dev node). Batch `./case.submit` stays the default for larger/longer production runs.

---

## File Structure

| File | Single responsibility |
|---|---|
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_kernel.F90` | PURE, CAM-agnostic math: `compute_ratio` (clamped obs/model ratio with guards), `interp_weight`, `combine_snapshots` (time-interp + valid-mask logic). Only dependency: `shr_kind_mod`. Unit-tested with pFUnit. |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_optics.F90` | CAM-abstraction boundary (D10): `model_aod550(state,pbuf,aod)` (reuse `aerosol_optics_cam_sw` + `idx_sw_diag`); `apply_scaling(state,pbuf,ratio,aci_on)` (write scaled mass+number back via `rad_cnst_*` pointers; `aci_on` gates the reserved cloud-borne/ACI path); `n_aero_modes()` (diagnostic). ONLY module touching CAM internals. |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_obs.F90` | IO: build filename from template+date, open via `cam_pio_openfile`, read `aod_weighted_mean` via `infld` (auto-scatter to chunks), hold curr+next snapshots, schedule/rotate on the model clock, expose per-chunk interpolated `target_aod` + valid mask. |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_intr.F90` | Driver mirroring `nudging.F90` lifecycle: `aod_nudging_readnl`, `_init`, `_timestep_init`, `_timestep_tend`. Orchestrates obs->optics->kernel->overwrite; `addfld`/`outfld` diagnostics; `check_energy_cam_chng`. Owns `&aod_nudging_nl`. |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam7/physpkg.F90` | MODIFY: insert lifecycle calls (readnl wiring is in runtime_opts; init in `phys_init`; timestep_init in `phys_timestep_init`; tend in `tphysac`). |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/control/runtime_opts.F90` | MODIFY: call `aod_nudging_readnl(nlfilename)`. |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/bld/namelist_files/namelist_definition.xml` | MODIFY: declare `&aod_nudging_nl` entries (group="aod_nudging_nl"). |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/bld/namelist_files/namelist_defaults_cam.xml` | MODIFY: defaults for `&aod_nudging_nl`. |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/aod_nudging/test_aod_nudging_kernel.pf` | pFUnit tests for `aod_nudging_kernel`. |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/aod_nudging/CMakeLists.txt` | CMake wiring for the kernel unit test. |
| `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/CMakeLists.txt` | MODIFY: `add_subdirectory(aod_nudging)`. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/make_synthetic_obs.py` | Generate a contract-conforming f09 obs file set (synthetic). |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/run_integration_mam4.sh` | Scripted F2000dev (MAM4) regression case build+run on derecho. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/run_integration_mam5.sh` | Dormant historical helper. Do not run or extend; all MAM5 work is deferred indefinitely. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/check_integration.py` | Assert post-overwrite AOD == obs where valid, unchanged where fill. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/make_transport_pulse_obs.py` | Completed Task 11: generate a two-day SP2 contract obs set with an initial valid AOD pulse followed by fill-only windows, so any later aerosol anomaly cannot come from new observations. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/run_transport_proof.sh` | Completed Task 11: scripted paired MAM4 transport-proof experiment with a nudged pulse run and free-control run from identical setup. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/check_transport_proof.py` | Completed Task 11: assert that, after observations are fill-only, no new nudging is applied while the nudged-minus-free AOD anomaly persists and moves outside the original pulse mask. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/plot_transport_proof.py` | Completed Task 11: DAVINCI-only PDF renders of daily-mean nudged-minus-free AODVIS anomaly and nudge-mask diagnostics for the transport-proof case. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/verify_plots.py` | DAVINCI science-verification renders for VP5: OBS / first-guess / analyzed AOD / ratio / mask maps from the nudged h0 file. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/verify_pair.py` | MAM4 VP6/VP8 paired free-vs-nudged DAVINCI PDF maps and numeric summaries from nudged/free h0 outputs. |
| `/glade/work/fillmore/CERES-SARB-CAM7/scripts/setup_sp2_vp7_profile_runs.sh` | Separate short MAM4 VP7 dev/sign-off pair with instantaneous `dst_a1:I` 3-D aerosol output on `h0i` and its own dev build root; never reuse the queued July 2008 executable. |
| `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/verify_profile.py` | MAM4 VP7 DAVINCI vertical-profile PDF and numeric check that a selected nudged/free `dst_a1` ratio is vertically constant and equals `AODNDG_RATIO`. |
| `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/` | Version-controlled mirror of the four `.F90` modules + the two modified-`.F90` diffs (`runtime_opts.F90.diff` captured in Task 5, `physpkg.F90.diff` captured in Task 7); the two modified namelist XMLs are mirrored as full-file copies under `src/cam/namelist/` (XML diffs are noisy/auto-formatted, so full copies are the carrier). Together these are the production CAM-fork carrier. |
| `/glade/work/fillmore/CERES-SARB-CAM7/scripts/sp2_deploy.sh` | Copy the four modules + the two namelist XMLs from the repo mirror into the checkout CAM src tree (and optionally a case `SourceMods/src.cam`), and apply the two `.F90` diffs. **Authored in Task 1, Step 9.** |

---

### Task 1: PURE kernel `aod_nudging_kernel` + pFUnit tests (TDD)

**Files:**
- Create: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_kernel.F90`
- Create (test): `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/aod_nudging/test_aod_nudging_kernel.pf`
- Create (test wiring): `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/aod_nudging/CMakeLists.txt`
- Modify: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/CMakeLists.txt` (add `add_subdirectory(aod_nudging)`)
- Create (mirror): `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_kernel.F90`

**Interfaces:**
- Produces (relied on by Tasks 3, 5, 7):
  - `real(r8) elemental function compute_ratio(target_aod, computed_aod, valid, eps, rmin, rmax)` — args `real(r8) target_aod, computed_aod`; `logical valid`; `real(r8) eps, rmin, rmax`; returns `real(r8)` (1.0 when skipped/guarded).
  - `real(r8) elemental function interp_weight(t_model, t_curr, t_next)` — returns weight in [0,1] for the NEXT snapshot.
  - `elemental subroutine combine_snapshots(curr, next, curr_valid, next_valid, w, target_aod, valid)` — `real(r8) curr,next`; `logical curr_valid,next_valid`; `real(r8) w`; `real(r8), intent(out) target_aod`; `logical, intent(out) valid`.
  - `real(r8), parameter, public :: AOD_FILL = -999._r8`.

- [ ] **Step 1: Create the test directory.**
```bash
mkdir -p /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/aod_nudging
mkdir -p /glade/work/fillmore/CERES-SARB-CAM7/src/cam
mkdir -p /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests
mkdir -p /glade/work/fillmore/CERES-SARB-CAM7/scripts
```

- [ ] **Step 2: Write the FAILING pFUnit test** at `components/cam/test/unit/aod_nudging/test_aod_nudging_kernel.pf` (the module under test does not exist yet, so the build will fail):
```fortran
module test_aod_nudging_kernel

use pfunit_mod
use shr_kind_mod, only: r8 => shr_kind_r8
use aod_nudging_kernel, only: compute_ratio, interp_weight, combine_snapshots, AOD_FILL

implicit none

contains

  @Test
  subroutine ratio_basic()
    ! obs 0.4 / model 0.2 = 2.0, inside [0.1,10]
    real(r8) :: r
    r = compute_ratio(0.4_r8, 0.2_r8, .true., 0.01_r8, 0.1_r8, 10._r8)
    @assertEqual(2.0_r8, r, tolerance=1.e-12_r8)
  end subroutine ratio_basic

  @Test
  subroutine ratio_clamps_high()
    ! 5.0/0.01 = 500 -> clamp to rmax=10
    real(r8) :: r
    r = compute_ratio(5.0_r8, 0.01_r8, .true., 0.001_r8, 0.1_r8, 10._r8)
    @assertEqual(10._r8, r, tolerance=1.e-12_r8)
  end subroutine ratio_clamps_high

  @Test
  subroutine ratio_clamps_low()
    ! 0.001/1.0 = 0.001 -> clamp to rmin=0.1
    real(r8) :: r
    r = compute_ratio(0.001_r8, 1.0_r8, .true., 0.01_r8, 0.1_r8, 10._r8)
    @assertEqual(0.1_r8, r, tolerance=1.e-12_r8)
  end subroutine ratio_clamps_low

  @Test
  subroutine ratio_skips_when_model_near_zero()
    ! computed < eps -> ratio = 1 (no change)
    real(r8) :: r
    r = compute_ratio(0.4_r8, 0.005_r8, .true., 0.01_r8, 0.1_r8, 10._r8)
    @assertEqual(1.0_r8, r, tolerance=1.e-12_r8)
  end subroutine ratio_skips_when_model_near_zero

  @Test
  subroutine ratio_skips_when_invalid()
    real(r8) :: r
    r = compute_ratio(0.4_r8, 0.2_r8, .false., 0.01_r8, 0.1_r8, 10._r8)
    @assertEqual(1.0_r8, r, tolerance=1.e-12_r8)
  end subroutine ratio_skips_when_invalid

  @Test
  subroutine ratio_skips_on_fill()
    ! fill (-999) target -> no change even if mask were true
    real(r8) :: r
    r = compute_ratio(AOD_FILL, 0.2_r8, .true., 0.01_r8, 0.1_r8, 10._r8)
    @assertEqual(1.0_r8, r, tolerance=1.e-12_r8)
  end subroutine ratio_skips_on_fill

  @Test
  subroutine weight_midpoint()
    @assertEqual(0.5_r8, interp_weight(150._r8, 100._r8, 200._r8), tolerance=1.e-12_r8)
  end subroutine weight_midpoint

  @Test
  subroutine weight_clamped_and_degenerate()
    @assertEqual(0._r8, interp_weight(50._r8,  100._r8, 200._r8), tolerance=1.e-12_r8) ! before curr
    @assertEqual(1._r8, interp_weight(250._r8, 100._r8, 200._r8), tolerance=1.e-12_r8) ! after next
    @assertEqual(0._r8, interp_weight(150._r8, 100._r8, 100._r8), tolerance=1.e-12_r8) ! denom<=0
  end subroutine weight_clamped_and_degenerate

  @Test
  subroutine combine_both_valid()
    real(r8) :: t
    logical  :: v
    call combine_snapshots(0.2_r8, 0.4_r8, .true., .true., 0.5_r8, t, v)
    @assertTrue(v)
    @assertEqual(0.3_r8, t, tolerance=1.e-12_r8)
  end subroutine combine_both_valid

  @Test
  subroutine combine_one_valid()
    real(r8) :: t
    logical  :: v
    call combine_snapshots(0.2_r8, AOD_FILL, .true., .false., 0.5_r8, t, v)
    @assertTrue(v)
    @assertEqual(0.2_r8, t, tolerance=1.e-12_r8)   ! uses curr, ignores weight
  end subroutine combine_one_valid

  @Test
  subroutine combine_none_valid()
    real(r8) :: t
    logical  :: v
    call combine_snapshots(AOD_FILL, AOD_FILL, .false., .false., 0.5_r8, t, v)
    @assertFalse(v)
    @assertEqual(AOD_FILL, t, tolerance=1.e-12_r8)
  end subroutine combine_none_valid

end module test_aod_nudging_kernel
```

- [ ] **Step 3: Write the test CMakeLists** at `components/cam/test/unit/aod_nudging/CMakeLists.txt` (mirrors `vdiff_lu_solver/CMakeLists.txt`):
```cmake
# Local pFUnit files.
set(pf_sources
  test_aod_nudging_kernel.pf)

# Sources to test (resolved out of the shared cam_sources list set by the parent).
set(sources_needed
  aod_nudging_kernel.F90)
extract_sources("${sources_needed}" "${cam_sources}" test_sources)

# Do source preprocessing and add the executable.
create_pFUnit_test(aod_nudging aod_nudging_exe "${pf_sources}"
  "${test_sources}")

target_link_libraries(aod_nudging_exe csm_share)
```

- [ ] **Step 4: Register the test subdir.** In `components/cam/test/unit/CMakeLists.txt`, after the line `add_subdirectory(vdiff_lu_solver)` add:
```cmake
add_subdirectory(aod_nudging)
```

- [ ] **Step 5: Run the test and confirm it FAILS to build** (module missing). On a login node, conda-free:
```bash
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
cd /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit
../../../../cime/scripts/fortran_unit_testing/run_tests.py \
  --build-dir $(mktemp -d --tmpdir=. ut.XXXXXXXX) \
  --machine derecho --compiler intel \
  --cmake-args ' -DCPPDEFS=-DUSE_CONTIGUOUS=contiguous,'
```
Expected: build error, e.g. `Cannot open module file 'aod_nudging_kernel.mod'` / `Fatal Error: Cannot open module file` — i.e. compilation of `test_aod_nudging_kernel.pf` fails because `aod_nudging_kernel` does not exist.

- [ ] **Step 6: Implement the kernel** at `components/cam/src/physics/cam/aod_nudging_kernel.F90`:
```fortran
module aod_nudging_kernel
!-----------------------------------------------------------------------------
! PURE, CAM-agnostic AOD-nudging math.
!   compute_ratio       : clamped obs/model ratio with skip/guard logic
!   interp_weight       : linear time-interpolation weight for the NEXT snapshot
!   combine_snapshots   : combine two snapshots + valid masks into a target+mask
! No CAM dependencies (only the working-precision kind). Unit-tested with pFUnit.
!-----------------------------------------------------------------------------
  use shr_kind_mod, only: r8 => shr_kind_r8

  implicit none
  private

  public :: compute_ratio
  public :: interp_weight
  public :: combine_snapshots

  ! Contract fill value: "no valid obs here" -> leave model untouched.
  real(r8), parameter, public :: AOD_FILL = -999._r8

contains

  elemental function compute_ratio(target_aod, computed_aod, valid, eps, rmin, rmax) result(ratio)
    ! Return obs/model ratio clamped to [rmin,rmax]; return 1.0 (no change) when
    ! the obs is invalid/fill or the model AOD is below eps (avoids blow-ups).
    real(r8), intent(in) :: target_aod    ! obs AOD@550 (AOD_FILL where invalid)
    real(r8), intent(in) :: computed_aod  ! model AOD@550
    logical,  intent(in) :: valid         ! obs valid mask for this column
    real(r8), intent(in) :: eps           ! skip threshold on model AOD
    real(r8), intent(in) :: rmin, rmax    ! clamp bounds
    real(r8)             :: ratio

    ratio = 1._r8
    if (.not. valid)            return     ! D7: only overwrite valid retrievals
    if (target_aod < 0._r8)     return     ! catches AOD_FILL even if mask wrong
    if (computed_aod < eps)     return     ! near-zero model AOD -> skip
    ratio = target_aod / computed_aod
    if (ratio < rmin) ratio = rmin
    if (ratio > rmax) ratio = rmax
  end function compute_ratio

  elemental function interp_weight(t_model, t_curr, t_next) result(w)
    ! Weight for the NEXT snapshot so target = (1-w)*curr + w*next.
    ! All times in consistent units (seconds). Degenerate spacing -> use curr.
    real(r8), intent(in) :: t_model, t_curr, t_next
    real(r8)             :: w, denom

    denom = t_next - t_curr
    if (denom <= 0._r8) then
      w = 0._r8
      return
    end if
    w = (t_model - t_curr) / denom
    if (w < 0._r8) w = 0._r8
    if (w > 1._r8) w = 1._r8
  end function interp_weight

  elemental subroutine combine_snapshots(curr, next, curr_valid, next_valid, w, target_aod, valid)
    ! Combine two bracketing snapshots into a single target + valid mask.
    !   both valid -> linear interp; one valid -> that one; neither -> fill/invalid.
    real(r8), intent(in)  :: curr, next
    logical,  intent(in)  :: curr_valid, next_valid
    real(r8), intent(in)  :: w
    real(r8), intent(out) :: target_aod
    logical,  intent(out) :: valid

    if (curr_valid .and. next_valid) then
      target_aod = (1._r8 - w)*curr + w*next
      valid = .true.
    else if (curr_valid) then
      target_aod = curr
      valid = .true.
    else if (next_valid) then
      target_aod = next
      valid = .true.
    else
      target_aod = AOD_FILL
      valid = .false.
    end if
  end subroutine combine_snapshots

end module aod_nudging_kernel
```

- [ ] **Step 7: Re-run the unit test and confirm PASS** (reuse the same shell env from Step 5):
```bash
cd /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit
../../../../cime/scripts/fortran_unit_testing/run_tests.py \
  --build-dir $(mktemp -d --tmpdir=. ut.XXXXXXXX) \
  --machine derecho --compiler intel \
  --cmake-args ' -DCPPDEFS=-DUSE_CONTIGUOUS=contiguous,'
```
Expected: CTest summary `100% tests passed, 0 tests failed out of N`, and in the pFUnit output for the `aod_nudging` executable: `... OK` with `11` tests run, `0` failures, `0` errors (e.g. a line like `Ran 11 tests` / `OK`).

- [ ] **Step 8: Mirror to the repo and commit.**
```bash
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_kernel.F90 \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_kernel.F90
mkdir -p /glade/work/fillmore/CERES-SARB-CAM7/src/cam/test
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/aod_nudging/test_aod_nudging_kernel.pf \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/test/test_aod_nudging_kernel.pf
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/test/unit/aod_nudging/CMakeLists.txt \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/test/CMakeLists.txt
cd /glade/work/fillmore/CERES-SARB-CAM7
git checkout -b sp2-aod-nudging
git add src/cam/aod_nudging_kernel.F90 src/cam/test/
git commit -m "SP2 Task 1: pure aod_nudging_kernel + pFUnit tests (compute_ratio, interp_weight, combine_snapshots)"
```

- [ ] **Step 9: Author the deploy script** `scripts/sp2_deploy.sh` (the File-Structure deliverable). It copies the repo-mirrored modules + namelist XMLs into the checkout CAM src tree, applies the two `.F90` diffs (idempotently — skips a diff already applied), and optionally overlays a case `SourceMods/src.cam`. (The diffs and namelist mirrors do not all exist until Tasks 5/7; the script is path-driven and only copies what is present, so it is authored now and used after Task 7.)
```bash
cat > /glade/work/fillmore/CERES-SARB-CAM7/scripts/sp2_deploy.sh <<'EOF'
#!/usr/bin/env bash
# Deploy the SP2 AOD-nudging source from the repo mirror into a CAM checkout.
# Usage: sp2_deploy.sh [CASEROOT]
#   - Always copies the four modules + the two namelist XMLs into the CAM src tree.
#   - Applies runtime_opts.F90.diff and physpkg.F90.diff (skips if already applied).
#   - If CASEROOT is given, also overlays the four modules into SourceMods/src.cam.
set -euo pipefail

REPO=/glade/work/fillmore/CERES-SARB-CAM7
CAM=/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam
SRC="$CAM/src/physics/cam"
NLDIR="$CAM/bld/namelist_files"
CASEROOT="${1:-}"

MODULES="aod_nudging_kernel.F90 aod_nudging_optics.F90 aod_nudging_obs.F90 aod_nudging_intr.F90"

for m in $MODULES; do
  if [ -f "$REPO/src/cam/$m" ]; then
    cp -v "$REPO/src/cam/$m" "$SRC/$m"
  else
    echo "WARN: $REPO/src/cam/$m not present yet (skipping)"
  fi
done

for x in namelist_definition.xml namelist_defaults_cam.xml; do
  if [ -f "$REPO/src/cam/namelist/$x" ]; then
    cp -v "$REPO/src/cam/namelist/$x" "$NLDIR/$x"
  fi
done

apply_diff() {  # $1 = diff file, $2 = target (rel to $CAM)
  local d="$1" t="$2"
  [ -f "$REPO/src/cam/$d" ] || { echo "WARN: $d not present yet (skipping)"; return 0; }
  if git -C "$CAM" apply --reverse --check "$REPO/src/cam/$d" 2>/dev/null; then
    echo "SKIP: $d already applied to $t"
  elif git -C "$CAM" apply --check "$REPO/src/cam/$d" 2>/dev/null; then
    git -C "$CAM" apply "$REPO/src/cam/$d" && echo "APPLIED: $d -> $t"
  else
    echo "ERROR: $d does not apply cleanly to $t (manual merge needed)"; return 1
  fi
}
apply_diff runtime_opts.F90.diff src/control/runtime_opts.F90
apply_diff physpkg.F90.diff       src/physics/cam7/physpkg.F90

if [ -n "$CASEROOT" ]; then
  mkdir -p "$CASEROOT/SourceMods/src.cam"
  for m in $MODULES; do
    [ -f "$REPO/src/cam/$m" ] && cp -v "$REPO/src/cam/$m" "$CASEROOT/SourceMods/src.cam/$m"
  done
  echo "Overlaid modules into $CASEROOT/SourceMods/src.cam (note: physpkg/runtime_opts/namelist edits are NOT SourceMods-overlayable; use the CAM src tree for those)."
fi
echo "sp2_deploy: done."
EOF
chmod +x /glade/work/fillmore/CERES-SARB-CAM7/scripts/sp2_deploy.sh
cd /glade/work/fillmore/CERES-SARB-CAM7
git add scripts/sp2_deploy.sh
git commit -m "SP2 Task 1: scripts/sp2_deploy.sh (repo-mirror -> CAM checkout deploy)"
```
Expected: the script is committed and `bash scripts/sp2_deploy.sh` is runnable (it no-ops with WARNs until the later modules/diffs exist).

**Deliverable:** A pure, fully unit-tested kernel (11 passing pFUnit assertions) plus the test wiring, and the `sp2_deploy.sh` deploy carrier; independently verifiable with `run_tests.py`.

---

### Task 2: Optics adapter — read path `model_aod550`

**Files:**
- Create: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_optics.F90`
- Create (mirror): `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_optics.F90`

**Interfaces:**
- Consumes (verified in checkout):
  - `aerosol_optics_cam::aerosol_optics_cam_sw(list_idx, state, pbuf, nnite, idxnite, tauxar, wa, ga, fa)` where `tauxar(pcols,0:pver,nswbands)` is layer extinction optical depth (`aerosol_optics_cam.F90:581`).
  - `radconstants::nswbands`, `radconstants::idx_sw_diag` (550 nm band index).
  - `ppgrid::pcols, pver`; `physics_types::physics_state`; `physics_buffer::physics_buffer_desc`.
- Produces (relied on by Tasks 7, 9):
  - `subroutine model_aod550(state, pbuf, aod)` — `type(physics_state), intent(in), target :: state`; `type(physics_buffer_desc), pointer :: pbuf(:)`; `real(r8), intent(out) :: aod(:)` (pcols, column AOD@550 for ALL columns).

- [ ] **Step 1: Create the module skeleton with `model_aod550`** at `components/cam/src/physics/cam/aod_nudging_optics.F90`:
```fortran
module aod_nudging_optics
!-----------------------------------------------------------------------------
! CAM-abstraction boundary (D10): the ONLY module that touches CAM7 internals.
!   model_aod550  : diagnose column AOD@550nm by reusing CAM7's own optics.
!   apply_scaling : overwrite aerosol mass+number (added in Task 3).
!   n_aero_modes  : number of aerosol modes in the climate list (diagnostic).
! All aerosol enumeration is generic (rad_cnst_*) -> mode-agnostic (MAM4/MAM5).
!-----------------------------------------------------------------------------
  use shr_kind_mod,        only: r8 => shr_kind_r8
  use ppgrid,              only: pcols, pver
  use physics_types,       only: physics_state
  use physics_buffer,      only: physics_buffer_desc
  use radconstants,        only: nswbands, idx_sw_diag
  use aerosol_optics_cam,  only: aerosol_optics_cam_sw

  implicit none
  private

  public :: model_aod550
  public :: n_aero_modes

  ! Climate (prognostic) radiation-constituent list index (the one radiation uses).
  integer, parameter :: LIST_CLIMATE = 0

contains

  subroutine model_aod550(state, pbuf, aod)
    ! Column AOD at 550 nm = vertical sum of the visible-band layer optical depth,
    ! computed from the CURRENT aerosol state by CAM7's own optics. nnite=0 makes
    ! the routine diagnose every column (day and night); tauxar is filled for all
    ! columns regardless (night masking only affects the routine's own diagnostics).
    type(physics_state),       intent(in), target :: state
    type(physics_buffer_desc), pointer            :: pbuf(:)
    real(r8),                  intent(out)         :: aod(:)   ! (pcols)

    real(r8) :: tauxar(pcols,0:pver,nswbands)
    real(r8) :: wa(pcols,0:pver,nswbands)
    real(r8) :: ga(pcols,0:pver,nswbands)
    real(r8) :: fa(pcols,0:pver,nswbands)
    integer  :: idxnite(1)   ! placeholder; nnite=0 means it is not indexed
    integer  :: ncol

    ncol = state%ncol
    tauxar = 0._r8
    wa     = 0._r8
    ga     = 0._r8
    fa     = 0._r8
    idxnite = 1

    call aerosol_optics_cam_sw(LIST_CLIMATE, state, pbuf, 0, idxnite, tauxar, wa, ga, fa)

    aod = 0._r8
    aod(:ncol) = sum(tauxar(:ncol, 0:pver, idx_sw_diag), dim=2)
  end subroutine model_aod550

  integer function n_aero_modes()
    ! Number of aerosol modes in the climate list (4 for MAM4, 5 for MAM5).
    use rad_constituents, only: rad_cnst_get_info
    integer :: nmodes
    call rad_cnst_get_info(LIST_CLIMATE, nmodes=nmodes)
    n_aero_modes = nmodes
  end function n_aero_modes

end module aod_nudging_optics
```

- [ ] **Step 2: Compile-verify by an incremental case build.** (This module needs the full CAM build; there is no isolated unit test for CAM-internal calls.) Create the integration case once and reuse it:
```bash
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
cd /glade/work/fillmore/CESM3/cesm3_0_beta08/cime/scripts
./create_newcase --case /glade/work/fillmore/CESM3/cases/sp2_mam4 \
  --compset F2000dev --res f09_f09_mg17 --machine derecho --compiler intel \
  --project P19010000 --run-unsupported
cd /glade/work/fillmore/CESM3/cases/sp2_mam4
./case.setup
./case.build
```
Expected (baseline, before our module is referenced by physpkg): `MODEL BUILD HAS FINISHED SUCCESSFULLY`. At this point the new `.F90` is in the CAM src tree and compiled into the CAM library; a successful build proves it compiles. (The module is not yet called; that wiring is Task 7.)

- [ ] **Step 3: Mirror + commit.**
```bash
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_optics.F90 \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_optics.F90
cd /glade/work/fillmore/CERES-SARB-CAM7
git add src/cam/aod_nudging_optics.F90
git commit -m "SP2 Task 2: aod_nudging_optics::model_aod550 (reuse aerosol_optics_cam_sw, idx_sw_diag)"
```

**Deliverable:** `model_aod550` compiling into CAM; AOD diagnosis reuses CAM7 optics (no duplicated Mie/Köhler code).

---

### Task 3: Optics adapter — write path `apply_scaling` (mode-agnostic)

**Files:**
- Modify: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_optics.F90`
- Update (mirror): `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_optics.F90`

**Interfaces:**
- Consumes (verified in `rad_constituents.F90`):
  - `rad_cnst_get_info(list_idx, nmodes=)` and `rad_cnst_get_info(list_idx, m_idx, nspec=)` (overloaded).
  - `rad_cnst_get_mode_num(list_idx, mode_idx, phase, state, pbuf, num)` -> `num(:,:)` pointer into `state%q` (source 'A') or pbuf ('N').
  - `rad_cnst_get_aer_mmr(list_idx, mode_idx, spec_idx, phase, state, pbuf, mmr)` (the `rad_cnst_get_mam_mmr_by_idx` overload) -> `mmr(:,:)` pointer into `state%q` ('A') or pbuf ('N').
- Produces (relied on by Tasks 6, 9):
  - `subroutine apply_scaling(state, pbuf, ratio, aci_on)` — `type(physics_state), intent(inout), target :: state`; `type(physics_buffer_desc), pointer :: pbuf(:)`; `real(r8), intent(in) :: ratio(:)` (pcols; 1.0 = no change); `logical, intent(in) :: aci_on` (when `.false.` scale interstitial 'a' only; when `.true.` route to the guarded cloud-borne/ACI path).

- [ ] **Step 1: Add the `use` for the write-back routines + abort util, and DELETE the now-redundant function-local `use` in `n_aero_modes`.** In `aod_nudging_optics.F90` module header, after `use aerosol_optics_cam, only: aerosol_optics_cam_sw` add:
```fortran
  use rad_constituents,    only: rad_cnst_get_info, rad_cnst_get_mode_num, &
                                 rad_cnst_get_aer_mmr
  use cam_abortutils,      only: endrun
```
Then **remove** the now-duplicate function-local import from `n_aero_modes` (it is use-associated at module scope after the line above). Delete this line from inside `n_aero_modes`:
```fortran
    use rad_constituents, only: rad_cnst_get_info   ! DELETE: now module-level
```
so `n_aero_modes` becomes:
```fortran
  integer function n_aero_modes()
    ! Number of aerosol modes in the climate list (4 for MAM4, 5 for MAM5).
    integer :: nmodes
    call rad_cnst_get_info(LIST_CLIMATE, nmodes=nmodes)
    n_aero_modes = nmodes
  end function n_aero_modes
```

- [ ] **Step 2: Make `apply_scaling` public.** In the public list add:
```fortran
  public :: apply_scaling
```

- [ ] **Step 3: Implement `apply_scaling`.** Add this subroutine to the `contains` section (before `n_aero_modes`):
```fortran
  subroutine apply_scaling(state, pbuf, ratio, aci_on)
    ! Multiply every interstitial-phase ('a') aerosol species mass AND every mode
    ! number mixing ratio, at all levels, by the per-column ratio. Enumeration is
    ! generic (rad_cnst_*) so this works unchanged for MAM4 and MAM5. The mmr/num
    ! pointers alias state%q (or pbuf), so assigning through them overwrites the
    ! prognostic aerosol state in place. ratio==1 columns are untouched (no-op).
    ! aci_on (SPEC D5): direct effect (v1) touches ONLY the interstitial 'a' phase.
    ! When aci_on=.true. the routine routes to the reserved cloud-borne ('c') / ACI
    ! path, which is guarded (not validated in v1) but kept as a real, marked
    ! insertion point so the interface is ACI-ready.
    type(physics_state),       intent(inout), target :: state
    type(physics_buffer_desc), pointer               :: pbuf(:)
    real(r8),                  intent(in)             :: ratio(:)   ! (pcols)
    logical,                   intent(in)             :: aci_on     ! cloud-borne/ACI hook

    integer           :: nmodes, nspec, m, l, icol, ncol
    real(r8), pointer :: num(:,:)
    real(r8), pointer :: mmr(:,:)

    ncol = state%ncol
    call rad_cnst_get_info(LIST_CLIMATE, nmodes=nmodes)

    do m = 1, nmodes
      ! Interstitial mode number mixing ratio.
      call rad_cnst_get_mode_num(LIST_CLIMATE, m, 'a', state, pbuf, num)
      do icol = 1, ncol
        num(icol,:) = ratio(icol) * num(icol,:)
      end do

      ! Each interstitial species mass mixing ratio in this mode.
      call rad_cnst_get_info(LIST_CLIMATE, m, nspec=nspec)
      do l = 1, nspec
        call rad_cnst_get_aer_mmr(LIST_CLIMATE, m, l, 'a', state, pbuf, mmr)
        do icol = 1, ncol
          mmr(icol,:) = ratio(icol) * mmr(icol,:)
        end do
      end do
    end do

    ! ----------------------------------------------------------------------------
    ! ACI hook (SPEC D5 / §2): present but OFF in v1. Direct-effect nudging must
    ! NOT touch the cloud-borne ('c') phase, so the default path above is complete.
    ! Turning on aod_aci_on selects the cloud-borne pathway, which is not validated
    ! in v1 -> abort cleanly rather than silently scale an unverified phase.
    ! ----------------------------------------------------------------------------
    if (aci_on) then
      call endrun('apply_scaling: aod_aci_on=.true. selects the cloud-borne/ACI path, '// &
                  'which is not implemented/validated in v1 (direct effect only)')
      ! FUTURE ACI IMPLEMENTATION (mirror the 'a' loop with phase 'c'):
      !   do m = 1, nmodes
      !     call rad_cnst_get_mode_num(LIST_CLIMATE, m, 'c', state, pbuf, num)
      !     do icol = 1, ncol ; num(icol,:) = ratio(icol)*num(icol,:) ; end do
      !     call rad_cnst_get_info(LIST_CLIMATE, m, nspec=nspec)
      !     do l = 1, nspec
      !       call rad_cnst_get_aer_mmr(LIST_CLIMATE, m, l, 'c', state, pbuf, mmr)
      !       do icol = 1, ncol ; mmr(icol,:) = ratio(icol)*mmr(icol,:) ; end do
      !     end do
      !   end do
    end if
  end subroutine apply_scaling
```

- [ ] **Step 4: Compile-verify (incremental build).**
```bash
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
cd /glade/work/fillmore/CESM3/cases/sp2_mam4
./case.build
```
Expected: `MODEL BUILD HAS FINISHED SUCCESSFULLY`.

- [ ] **Step 5: Mirror + commit.**
```bash
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_optics.F90 \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_optics.F90
cd /glade/work/fillmore/CERES-SARB-CAM7
git add src/cam/aod_nudging_optics.F90
git commit -m "SP2 Task 3: aod_nudging_optics::apply_scaling (mode-agnostic mass+number write-back via rad_cnst_*)"
```

**Deliverable:** Mode-agnostic write-back that scales mass + number through `rad_cnst_*` pointers; compiles into CAM under MAM4.

---

### Task 4: Obs reader `aod_nudging_obs`

**Files:**
- Create: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_obs.F90`
- Create (mirror): `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_obs.F90`

**Interfaces:**
- Consumes:
  - kernel: `interp_weight`, `combine_snapshots`, `AOD_FILL` (Task 1).
  - `filenames::interpret_filename_spec(filename_spec, yr_spec, mon_spec, day_spec, sec_spec)` (`%y`=i4.4, `%m`/`%d`=i2.2, `%s`=i5.5). VERIFIED signature: `interpret_filename_spec(filename_spec, number, prev, case, yr_spec, mon_spec, day_spec, sec_spec, flag_spec)` (all but the first optional).
  - `time_manager::get_curr_time(days, seconds)`, `get_curr_date(yr,mon,day,tod,offset)`.
  - `cam_pio_utils::cam_pio_openfile`; `pio::{file_desc_t, var_desc_t, pio_closefile, pio_seterrorhandling, PIO_BCAST_ERROR, PIO_NOERR, pio_inq_dimid, pio_inq_dimlen, pio_inq_varid, pio_get_var}` (read pattern verified in `sat_hist.F90`); `ncdio_atm::infld`; `cam_grid_support::{cam_grid_id, cam_grid_get_dim_names, cam_grid_dimensions, max_hcoordname_len}`.
  - `ppgrid::{pcols,begchunk,endchunk}`; `spmd_utils::{masterproc, mstrid=>masterprocid, mpicom, mpi_success, mpi_logical}` (`mpi_bcast` itself is the MPI external — not a `spmd_utils` public entity — resolved at link time, mirroring `nudging.F90`).
- Produces (relied on by Tasks 6, 7):
  - `subroutine aod_obs_init(path_in, template_in, times_per_day_in)` — `character(len=*) path_in,template_in`; `integer times_per_day_in` (dummy names match the implementation; module vars `obs_path/obs_template/times_per_day` are distinct to avoid shadowing).
  - `subroutine aod_obs_update()` — loads/rotates curr+next snapshots for the current model time, reads each bracket file's scalar CF `time` (center), and sets the time-interp weight on those file values (GLOBAL IO; call once per timestep from `phys_timestep_init`).
  - `subroutine aod_obs_target(lchnk, ncol, target_aod, valid)` — `integer lchnk,ncol`; `real(r8), intent(out) :: target_aod(:)` (pcols); `logical, intent(out) :: valid(:)` (pcols).

- [ ] **Step 1: Implement the module** at `components/cam/src/physics/cam/aod_nudging_obs.F90`:
```fortran
module aod_nudging_obs
!-----------------------------------------------------------------------------
! Contract-file IO for AOD nudging.
!   - filename from template+date via interpret_filename_spec (%y%m%d.%s),
!     keyed to window-START seconds-of-day (contract §5)
!   - read aod_weighted_mean(lat,lon) with infld (auto-scatter to chunks)
!   - read each file's SCALAR CF `time` (window CENTER) and interpolate on those
!     file values (contract: "SP2 time-interpolates ... using their scalar time")
!   - explicit f09 grid-identity check; abort on dimension mismatch (contract)
!   - hold two bracketing 3-hourly snapshots (curr,next), rotate on the model clock
!   - expose per-chunk time-interpolated target AOD + valid mask
!-----------------------------------------------------------------------------
  use shr_kind_mod,    only: r8 => shr_kind_r8, cl => shr_kind_cl, cs => shr_kind_cs
  use ppgrid,          only: pcols, begchunk, endchunk
  use cam_abortutils,  only: endrun
  use cam_logfile,     only: iulog
  use spmd_utils,      only: masterproc, mstrid=>masterprocid, mpicom, mpi_success, mpi_logical
  use time_manager,    only: get_curr_time, get_curr_date
  use filenames,       only: interpret_filename_spec
  use aod_nudging_kernel, only: interp_weight, combine_snapshots, AOD_FILL

  implicit none
  private

  public :: aod_obs_init
  public :: aod_obs_update
  public :: aod_obs_target

  ! Frozen contract f09 grid (D2): lat=192, lon=288. Must equal CAM's grid exactly.
  integer, parameter :: NLAT_F09 = 192
  integer, parameter :: NLON_F09 = 288

  ! Sentinel for an unread/absent file-center time.
  real(r8), parameter :: TCEN_NONE = -1.e30_r8

  ! Configuration (set in aod_obs_init). NOTE: module vars are intentionally named
  ! differently from the aod_obs_init dummies (path_in/template_in/...) to avoid
  ! host-association shadowing.
  character(len=cl) :: obs_path = ''
  character(len=cs) :: obs_template = ''
  integer           :: times_per_day = 8
  real(r8)          :: win_sec  = 10800._r8   ! window length (s) = 86400/times_per_day
  real(r8)          :: half_sec = 5400._r8    ! half window (s)

  ! Two snapshots, per chunk: value (AOD) + valid mask.
  real(r8), allocatable :: obs_curr(:,:)      ! (pcols, begchunk:endchunk)
  real(r8), allocatable :: obs_next(:,:)
  logical,  allocatable :: vld_curr(:,:)
  logical,  allocatable :: vld_next(:,:)

  ! Bracket bookkeeping.
  integer  :: k_curr  = -huge(1)             ! window index of the current bracket
  real(r8) :: cm_curr = 0._r8                ! curr window CENTER in MODEL elapsed seconds (anchor)
  real(r8) :: tcen_curr = TCEN_NONE          ! curr file scalar CF time (center), file units
  real(r8) :: tcen_next = TCEN_NONE          ! next file scalar CF time (center), file units
  real(r8) :: weight  = 0._r8                ! interp weight for next (0..1)

contains

  subroutine aod_obs_init(path_in, template_in, times_per_day_in)
    character(len=*), intent(in) :: path_in, template_in
    integer,          intent(in) :: times_per_day_in
    integer :: istat

    obs_path      = trim(path_in)
    obs_template  = trim(template_in)
    times_per_day = times_per_day_in
    win_sec  = 86400._r8 / real(times_per_day, r8)
    half_sec = 0.5_r8 * win_sec

    allocate(obs_curr(pcols, begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_obs_init: allocate obs_curr failed')
    allocate(obs_next(pcols, begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_obs_init: allocate obs_next failed')
    allocate(vld_curr(pcols, begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_obs_init: allocate vld_curr failed')
    allocate(vld_next(pcols, begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_obs_init: allocate vld_next failed')

    obs_curr = AOD_FILL ; obs_next = AOD_FILL
    vld_curr = .false.  ; vld_next = .false.
    k_curr   = -huge(1)
    tcen_curr = TCEN_NONE ; tcen_next = TCEN_NONE
  end subroutine aod_obs_init

  subroutine aod_obs_update()
    ! Determine the bracketing windows for the current model time, load the two
    ! contract files (rotating the curr snapshot when only advancing one), read
    ! each file's scalar CF time (center), and set the interp weight on those.
    integer  :: days, secs, k
    real(r8) :: t_now

    call get_curr_time(days, secs)
    t_now = real(days, r8)*86400._r8 + real(secs, r8)

    ! Bracket: window centers occur at k*win + half for integer k.
    k       = floor((t_now - half_sec) / win_sec)
    cm_curr = real(k, r8)*win_sec + half_sec   ! curr center in MODEL elapsed seconds

    if (k == k_curr) then
      call set_weight(t_now)                   ! same bracket: only the weight moves
      return
    end if

    if (k == k_curr + 1) then
      ! Advanced by exactly one window: reuse next as the new curr.
      obs_curr = obs_next ; vld_curr = vld_next ; tcen_curr = tcen_next
      call load_window(k+1, obs_next, vld_next, tcen_next)
    else
      ! First call or a jump: load both.
      call load_window(k,   obs_curr, vld_curr, tcen_curr)
      call load_window(k+1, obs_next, vld_next, tcen_next)
    end if
    k_curr = k
    call set_weight(t_now)
  end subroutine aod_obs_update

  subroutine set_weight(t_now)
    ! Interpolate on the FILE scalar `time` (center) values per the contract. To
    ! avoid coupling the model calendar (noleap) to the file calendar (gregorian),
    ! place the model time on the file time axis by anchoring at the curr center
    ! read from the file and adding the model's calendar-free elapsed offset past
    ! that center (seconds -> the file `time` hour units). When a bracket file is
    ! absent its center is unknown; the weight is then irrelevant because
    ! combine_snapshots selects the present bracket via its valid mask.
    real(r8), intent(in) :: t_now
    real(r8) :: t_model_axis

    if (tcen_curr <= TCEN_NONE*0.5_r8 .or. tcen_next <= TCEN_NONE*0.5_r8) then
      weight = 0._r8
      return
    end if
    t_model_axis = tcen_curr + (t_now - cm_curr)/3600._r8
    weight = interp_weight(t_model_axis, tcen_curr, tcen_next)
  end subroutine set_weight

  subroutine load_window(k, fld, vld, center)
    ! Load the contract file whose window-start = k*win into fld(:,chunk) + mask,
    ! and return its scalar CF `time` (window center) in `center`.
    ! Missing file -> all-invalid (model runs free; SPEC D7 / gap handling).
    use cam_pio_utils,    only: cam_pio_openfile
    use pio,              only: file_desc_t, var_desc_t, pio_closefile,            &
                                pio_seterrorhandling, PIO_BCAST_ERROR, PIO_NOERR,  &
                                pio_inq_dimid, pio_inq_dimlen, pio_inq_varid, pio_get_var
    use ncdio_atm,        only: infld
    use cam_grid_support, only: cam_grid_id, cam_grid_get_dim_names, cam_grid_dimensions, &
                                DLEN=>max_hcoordname_len

    integer,  intent(in)  :: k
    real(r8), intent(out) :: fld(:,:)          ! (pcols, begchunk:endchunk)
    logical,  intent(out) :: vld(:,:)
    real(r8), intent(out) :: center            ! file scalar CF time (window center)

    integer            :: ws_elapsed, days, secs, offset
    integer            :: yr, mon, day, tod
    character(len=cl)  :: fname
    logical            :: present_file, found
    type(file_desc_t)  :: fileID
    type(var_desc_t)   :: time_vid
    integer            :: grid_id, err_handling, ierr, dimid
    integer            :: nlat_file, nlon_file, griddims(2)
    character(len=DLEN):: dim1name, dim2name
    real(r8)           :: tcen

    fld    = AOD_FILL
    vld    = .false.
    center = TCEN_NONE

    ! Calendar date/sec-of-day of this window's START (= k*win elapsed seconds).
    ws_elapsed = nint(real(k, r8)*win_sec)
    call get_curr_time(days, secs)
    offset = ws_elapsed - (days*86400 + secs)
    call get_curr_date(yr, mon, day, tod, offset=offset)

    fname = trim(obs_path)//trim(interpret_filename_spec(obs_template, &
            yr_spec=yr, mon_spec=mon, day_spec=day, sec_spec=tod))

    if (masterproc) inquire(file=trim(fname), exist=present_file)
    call mpi_bcast(present_file, 1, mpi_logical, mstrid, mpicom, ierr)  ! mpi_bcast: MPI external
    if (ierr /= mpi_success) call endrun('aod_obs::load_window: mpi_bcast present_file')

    if (.not. present_file) then
      if (masterproc) write(iulog,*) 'AODNUDGE: obs file absent, running free: ', trim(fname)
      return
    end if

    call cam_pio_openfile(fileID, trim(fname), 0)
    call pio_seterrorhandling(fileID, PIO_BCAST_ERROR, oldmethod=err_handling)
    if (masterproc) write(iulog,*) 'AODNUDGE: reading ', trim(fname)

    ! --- Contract grid-identity check: abort on dimension mismatch (no in-model
    !     interpolation). Compare the file's lat/lon to f09 AND to CAM's own grid. ---
    ierr = pio_inq_dimid(fileID, 'lat', dimid)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: missing lat dim in '//trim(fname))
    ierr = pio_inq_dimlen(fileID, dimid, nlat_file)
    ierr = pio_inq_dimid(fileID, 'lon', dimid)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: missing lon dim in '//trim(fname))
    ierr = pio_inq_dimlen(fileID, dimid, nlon_file)
    call cam_grid_dimensions('physgrid', griddims)
    if (nlat_file /= NLAT_F09 .or. nlon_file /= NLON_F09 .or. &
        griddims(1)*griddims(2) /= NLAT_F09*NLON_F09) then
      if (masterproc) write(iulog,*) 'AODNUDGE: grid mismatch obs(lat,lon)=', &
           nlat_file, nlon_file, ' expected f09=', NLAT_F09, NLON_F09, &
           ' model physgrid dims=', griddims
      call endrun('aod_obs::load_window: obs grid /= CAM f09 grid (no in-model interpolation)')
    end if

    grid_id = cam_grid_id('physgrid')
    call cam_grid_get_dim_names(grid_id, dim1name, dim2name)

    call infld('aod_weighted_mean', fileID, dim1name, dim2name, &
               1, pcols, begchunk, endchunk, fld, found, &
               gridname='physgrid', timelevel=1)
    if (.not. found) then
      call endrun('aod_obs::load_window: variable aod_weighted_mean missing in '//trim(fname))
    end if

    ! --- Read the scalar CF `time` (window center) and interpolate on it (contract). ---
    ierr = pio_inq_varid(fileID, 'time', time_vid)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: scalar time var missing in '//trim(fname))
    ierr = pio_get_var(fileID, time_vid, tcen)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: cannot read scalar time in '//trim(fname))
    center = tcen

    ! Valid where not fill (fill = -999; tolerate float noise).
    vld = (fld > -900._r8)

    call pio_seterrorhandling(fileID, err_handling)
    call pio_closefile(fileID)
  end subroutine load_window

  subroutine aod_obs_target(lchnk, ncol, target_aod, valid)
    ! Per-chunk time-interpolated target + valid mask (elemental over columns).
    integer,  intent(in)  :: lchnk, ncol
    real(r8), intent(out) :: target_aod(:)      ! (pcols)
    logical,  intent(out) :: valid(:)           ! (pcols)

    target_aod = AOD_FILL
    valid      = .false.
    call combine_snapshots(obs_curr(:ncol,lchnk), obs_next(:ncol,lchnk),  &
                           vld_curr(:ncol,lchnk), vld_next(:ncol,lchnk),  &
                           weight, target_aod(:ncol), valid(:ncol))
  end subroutine aod_obs_target

end module aod_nudging_obs
```

- [ ] **Step 2: Compile-verify (incremental build).**
```bash
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
cd /glade/work/fillmore/CESM3/cases/sp2_mam4
./case.build
```
Expected: `MODEL BUILD HAS FINISHED SUCCESSFULLY`. (The pure time-interp/combine logic this module relies on is already proven by Task 1's pFUnit tests; correct file reading is asserted end-to-end in Task 8.)

- [ ] **Step 3: Mirror + commit.**
```bash
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_obs.F90 \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_obs.F90
cd /glade/work/fillmore/CERES-SARB-CAM7
git add src/cam/aod_nudging_obs.F90
git commit -m "SP2 Task 4: aod_nudging_obs (infld reader, two snapshots, clock-driven schedule, time-interp)"
```

**Plan revision (2026-06-27) — harden the grid check to coordinate VALUES, not just sizes.**
`infld` reads the obs field **by index** (no coordinate interpolation), so a 192×288 file on the
*wrong* centers (the legacy ±89.53° grid, or a 0.625°-offset lon) passes the size-only check above
and silently misregisters obs by up to ~0.47° in latitude. SP1 provably emits the exact CAM f09
grid (verified to ~1e-14 vs `atm/cam/coords/fv_0.9x1.25.nc`), so this is defense-in-depth — but it
is cheap. In `load_window`, after the dimension check, also read the file's `lat`/`lon` coordinate
variables and compare to the analytic f09 centers. Add to the declarations:
```fortran
    real(r8) :: latf(NLAT_F09), lonf(NLON_F09)
    real(r8) :: late, lone
    type(var_desc_t) :: latvid, lonvid
    integer  :: jj
    real(r8), parameter :: GRID_TOL = 1.e-3_r8   ! deg
```
and after the size-check `end if`, before `grid_id = cam_grid_id('physgrid')`:
```fortran
    ! Coordinate-VALUE identity (index-based infld -> centers must match exactly).
    ierr = pio_inq_varid(fileID, 'lat', latvid)
    if (ierr == PIO_NOERR) ierr = pio_get_var(fileID, latvid, latf)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: cannot read lat coord in '//trim(fname))
    ierr = pio_inq_varid(fileID, 'lon', lonvid)
    if (ierr == PIO_NOERR) ierr = pio_get_var(fileID, lonvid, lonf)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: cannot read lon coord in '//trim(fname))
    do jj = 1, NLAT_F09
      late = -90._r8 + real(jj-1,r8)*180._r8/real(NLAT_F09-1,r8)   ! pole-centered f09
      if (abs(latf(jj) - late) > GRID_TOL) call endrun( &
        'aod_obs::load_window: obs lat centers /= CAM f09 (no in-model interpolation)')
    end do
    do jj = 1, NLON_F09
      lone = real(jj-1,r8)*360._r8/real(NLON_F09,r8)               ! lon[0]=0, d=1.25
      if (abs(lonf(jj) - lone) > GRID_TOL) call endrun( &
        'aod_obs::load_window: obs lon centers /= CAM f09 (no in-model interpolation)')
    end do
```
(`var_desc_t` and `pio_get_var` are already imported in `load_window`.)

**Deliverable:** Obs reader that loads contract files, scatters to chunks, and exposes per-chunk interpolated target+mask; compiles into CAM.

---

### Task 5: Namelist `&aod_nudging_nl` (XML defs + defaults + readnl wiring)

**Files:**
- Modify: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/bld/namelist_files/namelist_definition.xml`
- Modify: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/bld/namelist_files/namelist_defaults_cam.xml`
- Create (skeleton driver with readnl only): `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_intr.F90`
- Modify: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/control/runtime_opts.F90`
- Create (mirror): `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_intr.F90`

**Interfaces:**
- Produces (relied on by Tasks 6, 7):
  - module `aod_nudging_intr` with public module vars `logical :: aod_nudge_on`, `logical :: aod_nudge_active`, and configuration accessible to later steps; public `subroutine aod_nudging_readnl(nlfile)` — `character(len=*) nlfile`.

- [ ] **Step 1: Declare the namelist group** in `bld/namelist_files/namelist_definition.xml`. Immediately after the closing `</entry>` of the last `nudging_nl` entry, insert:
```xml
<!-- AOD Nudging Parameters (&aod_nudging_nl) -->

<entry id="aod_nudge_on" type="logical" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Toggle AOD nudging ON/OFF. When TRUE, model aerosol mass and number are
       hard-overwritten before radiation so column AOD@550nm matches the obs file.
       Default: FALSE
</entry>
<entry id="aod_obs_path" type="char*256" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Directory containing the contract obs files (trailing slash recommended).
       NOTE: deliberately NOT input_pathname="abs": this is a run-supplied directory
       (typically under /glade/derecho/scratch), not a DIN_LOC_ROOT input file, so
       build-namelist must not subject it to input-data path validation.
       Default: none
</entry>
<entry id="aod_obs_template" type="char*256" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Obs filename template with %y,%m,%d,%s substitutions
       (e.g. MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc).
       Default: MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc
</entry>
<entry id="aod_beg_ymd" type="integer" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Start date (YYYYMMDD) of the nudging window. Default: 101 (year 0000-01-01).
</entry>
<entry id="aod_end_ymd" type="integer" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       End date (YYYYMMDD) of the nudging window. Default: 99991231.
</entry>
<entry id="aod_times_per_day" type="integer" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Number of obs windows per day (3-hourly = 8). Default: 8.
</entry>
<entry id="aod_ratio_min" type="real" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Lower clamp on the obs/model ratio. Default: 0.1
</entry>
<entry id="aod_ratio_max" type="real" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Upper clamp on the obs/model ratio. Default: 10.0
</entry>
<entry id="aod_eps" type="real" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Skip nudging where model AOD < aod_eps (avoids blow-ups). Default: 0.01
</entry>
<entry id="aod_aci_on" type="logical" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Reserved aerosol-cloud-interaction hook. Default: FALSE (direct effect only).
</entry>
<entry id="aod_diag_on" type="logical" category="aod_nudging"
       group="aod_nudging_nl" valid_values="" >
       Emit AODNDG_* history diagnostics. Default: TRUE.
</entry>
```

- [ ] **Step 2: Add build-namelist defaults** in `bld/namelist_files/namelist_defaults_cam.xml`. Inside the top-level `<namelist_defaults>` element (e.g. before its closing tag), insert:
```xml
<!-- AOD nudging defaults -->
<aod_nudge_on>.false.</aod_nudge_on>
<aod_obs_template>MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc</aod_obs_template>
<aod_beg_ymd>101</aod_beg_ymd>
<aod_end_ymd>99991231</aod_end_ymd>
<aod_times_per_day>8</aod_times_per_day>
<aod_ratio_min>0.1</aod_ratio_min>
<aod_ratio_max>10.0</aod_ratio_max>
<aod_eps>0.01</aod_eps>
<aod_aci_on>.false.</aod_aci_on>
<aod_diag_on>.true.</aod_diag_on>
```

- [ ] **Step 3: Create the driver module with module vars + `aod_nudging_readnl` only** at `components/cam/src/physics/cam/aod_nudging_intr.F90` (the rest of the lifecycle is Task 6):
```fortran
module aod_nudging_intr
!-----------------------------------------------------------------------------
! AOD-nudging physics interface/driver. Mirrors nudging.F90 lifecycle:
!   aod_nudging_readnl       (called from runtime_opts)
!   aod_nudging_init         (called from phys_init)            [Task 6]
!   aod_nudging_timestep_init(called from phys_timestep_init)   [Task 6]
!   aod_nudging_timestep_tend(called from tphysac)              [Task 6]
!-----------------------------------------------------------------------------
  use shr_kind_mod,   only: r8 => shr_kind_r8, cl => shr_kind_cl, cs => shr_kind_cs
  use cam_abortutils, only: endrun
  use cam_logfile,    only: iulog
  use spmd_utils,     only: masterproc, mstrid=>masterprocid, mpicom, mpi_success, &
                            mpi_integer, mpi_real8, mpi_logical, mpi_character

  implicit none
  private

  ! Lifecycle (public).
  public :: aod_nudging_readnl

  ! Hook flags consumed by physpkg.
  public :: aod_nudge_on            ! master on/off (namelist)
  public :: aod_nudge_active        ! true only within [beg,end] window (set in timestep_init)

  ! Namelist state (module-scope, broadcast in readnl).
  logical           :: aod_nudge_on      = .false.
  logical           :: aod_nudge_active  = .false.
  character(len=cl) :: aod_obs_path      = ''
  character(len=cs) :: aod_obs_template  = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
  integer           :: aod_beg_ymd       = 101
  integer           :: aod_end_ymd       = 99991231
  integer           :: aod_times_per_day = 8
  real(r8)          :: aod_ratio_min     = 0.1_r8
  real(r8)          :: aod_ratio_max     = 10.0_r8
  real(r8)          :: aod_eps           = 0.01_r8
  logical           :: aod_aci_on        = .false.
  logical           :: aod_diag_on       = .true.

contains

  subroutine aod_nudging_readnl(nlfile)
    use namelist_utils, only: find_group_name
    character(len=*), intent(in) :: nlfile
    integer :: unitn, ierr
    character(len=*), parameter :: prefix = 'aod_nudging_readnl: '

    namelist /aod_nudging_nl/ aod_nudge_on, aod_obs_path, aod_obs_template, &
         aod_beg_ymd, aod_end_ymd, aod_times_per_day,                       &
         aod_ratio_min, aod_ratio_max, aod_eps, aod_aci_on, aod_diag_on

    if (masterproc) then
      open(newunit=unitn, file=trim(nlfile), status='old')
      call find_group_name(unitn, 'aod_nudging_nl', status=ierr)
      if (ierr == 0) then
        read(unitn, aod_nudging_nl, iostat=ierr)
        if (ierr /= 0) call endrun(prefix//'ERROR reading namelist')
      end if
      close(unitn)
    end if

    call mpi_bcast(aod_nudge_on,      1,                  mpi_logical,   mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_nudge_on')
    call mpi_bcast(aod_obs_path,      len(aod_obs_path),  mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_obs_path')
    call mpi_bcast(aod_obs_template,  len(aod_obs_template), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_obs_template')
    call mpi_bcast(aod_beg_ymd,       1,                  mpi_integer,   mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_beg_ymd')
    call mpi_bcast(aod_end_ymd,       1,                  mpi_integer,   mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_end_ymd')
    call mpi_bcast(aod_times_per_day, 1,                  mpi_integer,   mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_times_per_day')
    call mpi_bcast(aod_ratio_min,     1,                  mpi_real8,     mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_ratio_min')
    call mpi_bcast(aod_ratio_max,     1,                  mpi_real8,     mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_ratio_max')
    call mpi_bcast(aod_eps,           1,                  mpi_real8,     mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_eps')
    call mpi_bcast(aod_aci_on,        1,                  mpi_logical,   mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_aci_on')
    call mpi_bcast(aod_diag_on,       1,                  mpi_logical,   mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_diag_on')

    if (masterproc .and. aod_nudge_on) then
      write(iulog,*) 'AODNUDGE: ON  path=', trim(aod_obs_path)
      write(iulog,*) 'AODNUDGE:     template=', trim(aod_obs_template)
      write(iulog,*) 'AODNUDGE:     beg/end_ymd=', aod_beg_ymd, aod_end_ymd, &
                     ' times/day=', aod_times_per_day
      write(iulog,*) 'AODNUDGE:     ratio=[', aod_ratio_min, ',', aod_ratio_max, &
                     '] eps=', aod_eps, ' aci=', aod_aci_on
    end if
  end subroutine aod_nudging_readnl

end module aod_nudging_intr
```

- [ ] **Step 4: Wire readnl into runtime_opts.** In `components/cam/src/control/runtime_opts.F90`, add the `use` near the other physics readnl `use` lines (after `use nudging, only: nudging_readnl` at L90):
```fortran
   use aod_nudging_intr,    only: aod_nudging_readnl
```
and add the call immediately after `call nudging_readnl(nlfilename)` (L199):
```fortran
   call aod_nudging_readnl(nlfilename)
```

- [ ] **Step 5: Verify build-namelist emits the group.** Run `case.setup`/`preview_namelists` on the existing case and confirm `&aod_nudging_nl` appears in `atm_in`:
```bash
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
cd /glade/work/fillmore/CESM3/cases/sp2_mam4
./preview_namelists
grep -n "aod_nudging_nl" CaseDocs/atm_in
grep -n "aod_nudge_on\|aod_times_per_day\|aod_ratio_max" CaseDocs/atm_in
```
Expected: a line `&aod_nudging_nl` and entries like `aod_nudge_on = .false.`, `aod_times_per_day = 8`, `aod_ratio_max = 10.0`.

- [ ] **Step 6: Compile-verify (incremental build).**
```bash
cd /glade/work/fillmore/CESM3/cases/sp2_mam4
./case.build
```
Expected: `MODEL BUILD HAS FINISHED SUCCESSFULLY`.

- [ ] **Step 7: Mirror + commit** (the driver skeleton, the two namelist XMLs as full-file copies, and the `runtime_opts.F90` change as a diff — the first of the "two `.F90` diffs" carrier; `physpkg.F90.diff` is captured in Task 7).
```bash
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_intr.F90 \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_intr.F90
mkdir -p /glade/work/fillmore/CERES-SARB-CAM7/src/cam/namelist
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/bld/namelist_files/namelist_definition.xml \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/namelist/namelist_definition.xml
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/bld/namelist_files/namelist_defaults_cam.xml \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/namelist/namelist_defaults_cam.xml
# Capture ONLY the runtime_opts.F90 modification as a diff (its own deliverable).
git -C /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam diff -- src/control/runtime_opts.F90 \
   > /glade/work/fillmore/CERES-SARB-CAM7/src/cam/runtime_opts.F90.diff
cd /glade/work/fillmore/CERES-SARB-CAM7
git add src/cam/aod_nudging_intr.F90 src/cam/namelist/ src/cam/runtime_opts.F90.diff
git commit -m "SP2 Task 5: &aod_nudging_nl namelist (xml defs+defaults), readnl + runtime_opts wiring (+runtime_opts.F90.diff)"
```

**Deliverable:** Namelist group declared, defaulted, broadcast, and emitted into `atm_in`; `runtime_opts.F90.diff` mirrored; build succeeds.

---

### Task 6: Driver lifecycle — `init` / `timestep_init` / `timestep_tend` + diagnostics + energy check

**Files:**
- Modify: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_intr.F90`
- Update (mirror): `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_intr.F90`

**Interfaces:**
- Consumes: `aod_nudging_optics::{model_aod550, apply_scaling, n_aero_modes}` (Tasks 2,3); `aod_nudging_obs::{aod_obs_init, aod_obs_update, aod_obs_target}` (Task 4); `aod_nudging_kernel::compute_ratio` (Task 1); `check_energy::check_energy_cam_chng`; `cam_history::{addfld, outfld, horiz_only}`; `time_manager::{get_curr_date, get_nstep}`; `radiation::radiation_do` (D6 cadence gate); `spmd_utils::mpi_sum` (+ `mpi_reduce` MPI external) for the per-step hit-rate reduction.
- Produces (relied on by Task 7):
  - `subroutine aod_nudging_init()`
  - `subroutine aod_nudging_timestep_init(phys_state)` — `type(physics_state), intent(in) :: phys_state(begchunk:endchunk)`
  - `subroutine aod_nudging_timestep_tend(state, tend, pbuf, ztodt)` — `type(physics_state), intent(inout) :: state`; `type(physics_tend), intent(inout) :: tend`; `type(physics_buffer_desc), pointer :: pbuf(:)`; `real(r8), intent(in) :: ztodt`.

- [ ] **Step 1: Extend the module `use`/public lists and add the hit-rate counters.** In `aod_nudging_intr.F90`, after the existing `use` lines add:
```fortran
  use ppgrid,         only: pcols, begchunk, endchunk
  use physics_types,  only: physics_state, physics_tend
  use physics_buffer, only: physics_buffer_desc
  use time_manager,   only: get_curr_date, get_nstep
  use cam_history,    only: addfld, outfld, horiz_only
  use spmd_utils,     only: mpi_sum                 ! for per-step hit-rate reduction
  use radiation,      only: radiation_do            ! D6: radiation-cadence gate
  use aod_nudging_kernel, only: compute_ratio
  use aod_nudging_optics,  only: model_aod550, apply_scaling, n_aero_modes
  use aod_nudging_obs,     only: aod_obs_init, aod_obs_update, aod_obs_target
```
and extend the public list:
```fortran
  public :: aod_nudging_init
  public :: aod_nudging_timestep_init
  public :: aod_nudging_timestep_tend
```
and add these module-scope diagnostic counters (SPEC R12 per-step hit-rate; accumulated across chunks within a radiation step on this rank, MPI-reduced + logged once per step):
```fortran
  ! Per-step ratio hit-rate / clamp-hit counters (this rank; reduced in timestep_init).
  integer :: acc_nstep    = -1   ! model step whose counts are being accumulated
  integer :: acc_ncol     = 0    ! columns processed (radiation steps only)
  integer :: acc_nvalid   = 0    ! columns with a valid obs -> nudged
  integer :: acc_clamp_lo = 0    ! valid columns whose ratio hit aod_ratio_min
  integer :: acc_clamp_hi = 0    ! valid columns whose ratio hit aod_ratio_max
```

- [ ] **Step 2: Implement `aod_nudging_init`.** Add to the `contains` section:
```fortran
  subroutine aod_nudging_init()
    if (.not. aod_nudge_on) return

    call aod_obs_init(aod_obs_path, aod_obs_template, aod_times_per_day)

    if (aod_diag_on) then
      ! 'I' (instantaneous): the nudge runs at the radiation cadence and the
      ! round-trip assertion (Task 8) compares post vs obs at a single step, so
      ! instantaneous output matches the test intent (a time-average would smear
      ! nudged cells). Output cadence is set to the radiation cadence (Task 8/10).
      call addfld('AODNDG_OBS',        horiz_only, 'I', '1', 'AOD nudging: target (obs) AOD at 550nm')
      call addfld('AODNDG_MODEL_PRE',  horiz_only, 'I', '1', 'AOD nudging: model AOD@550 before overwrite')
      call addfld('AODNDG_MODEL_POST', horiz_only, 'I', '1', 'AOD nudging: model AOD@550 after overwrite')
      call addfld('AODNDG_RATIO',      horiz_only, 'I', '1', 'AOD nudging: applied obs/model ratio')
      call addfld('AODNDG_MASK',       horiz_only, 'I', '1', 'AOD nudging: obs valid mask (1=nudged,0=free)')
    end if

    if (masterproc) then
      write(iulog,*) 'AODNUDGE: init complete; aerosol modes (mode-agnostic) = ', n_aero_modes()
    end if
  end subroutine aod_nudging_init

  subroutine flush_hitrate()
    ! Reduce + log the per-step ratio hit-rate / clamp-hit counts accumulated over
    ! the PREVIOUS radiation step's chunk loop, then reset (SPEC R12 / §7). Called
    ! once per step at the top of aod_nudging_timestep_init, so the log lags the
    ! accumulating step by one model step; the run's final step is not flushed
    ! (acceptable for a diagnostic). No-op on steps with no accumulation (e.g.
    ! non-radiation steps, where the gate in timestep_tend skips accumulation).
    integer :: loc(4), tot(4), ierr
    if (acc_ncol <= 0) return
    loc = (/ acc_ncol, acc_nvalid, acc_clamp_lo, acc_clamp_hi /)
    call mpi_reduce(loc, tot, 4, mpi_integer, mpi_sum, mstrid, mpicom, ierr)  ! mpi_reduce: MPI external
    if (ierr /= mpi_success) call endrun('aod_nudging: mpi_reduce hit-rate counters')
    if (masterproc .and. tot(1) > 0) then
      write(iulog,'(a,i9,a,f8.4,a,f8.4,a,f8.4,a,i10)')                 &
        'AODNUDGE hit-rate nstep=', acc_nstep,                          &
        ' nudged_frac=',   real(tot(2),r8)/real(tot(1),r8),            &
        ' clamp_lo_frac=', real(tot(3),r8)/real(tot(1),r8),           &
        ' clamp_hi_frac=', real(tot(4),r8)/real(tot(1),r8),           &
        ' ncol_global=',   tot(1)
    end if
    acc_ncol = 0 ; acc_nvalid = 0 ; acc_clamp_lo = 0 ; acc_clamp_hi = 0
  end subroutine flush_hitrate
```

- [ ] **Step 3: Implement `aod_nudging_timestep_init`** (GLOBAL: sets the window flag and performs the once-per-step obs IO):
```fortran
  subroutine aod_nudging_timestep_init(phys_state)
    type(physics_state), intent(in) :: phys_state(begchunk:endchunk)
    integer :: yr, mon, day, sec, ymd

    if (.not. aod_nudge_on) return

    ! Flush the PREVIOUS step's hit-rate counters (reduce + log), then tag this step.
    call flush_hitrate()
    acc_nstep = get_nstep()

    call get_curr_date(yr, mon, day, sec)
    ymd = yr*10000 + mon*100 + day
    aod_nudge_active = (ymd >= aod_beg_ymd) .and. (ymd <= aod_end_ymd)

    if (aod_nudge_active) call aod_obs_update()
  end subroutine aod_nudging_timestep_init
```

- [ ] **Step 4: Implement `aod_nudging_timestep_tend`** (PER-CHUNK: orchestrate diagnose -> ratio -> overwrite -> diagnose -> diagnostics -> energy check):
```fortran
  subroutine aod_nudging_timestep_tend(state, tend, pbuf, ztodt)
    use check_energy, only: check_energy_cam_chng
    type(physics_state),       intent(inout) :: state
    type(physics_tend),        intent(inout) :: tend
    type(physics_buffer_desc), pointer       :: pbuf(:)
    real(r8),                  intent(in)     :: ztodt

    integer  :: ncol, lchnk, nstep
    real(r8) :: aod_pre(pcols), aod_post(pcols)
    real(r8) :: target_aod(pcols), ratio(pcols)
    logical  :: valid(pcols)
    real(r8) :: maskr(pcols)
    real(r8) :: zero_flx(pcols)

    if (.not. (aod_nudge_on .and. aod_nudge_active)) return

    ! D6: apply the overwrite ONLY at the model's radiation (shortwave) cadence, so
    ! the nudged aerosol is what RRTMGP sees and the overwrite does not run on
    ! non-radiation physics substeps (which would persist into aerosol evolution).
    if (.not. radiation_do('sw')) return

    ncol  = state%ncol
    lchnk = state%lchnk
    nstep = get_nstep()
    zero_flx = 0._r8

    ! 1) model AOD before overwrite
    call model_aod550(state, pbuf, aod_pre)

    ! 2) interpolated obs target + valid mask for this chunk
    call aod_obs_target(lchnk, ncol, target_aod, valid)

    ! 3) clamped ratio (1.0 where invalid/guarded), elemental over columns
    ratio = 1._r8
    ratio(:ncol) = compute_ratio(target_aod(:ncol), aod_pre(:ncol), valid(:ncol), &
                                 aod_eps, aod_ratio_min, aod_ratio_max)

    ! 3a) accumulate per-step hit-rate / clamp-hit counters (reduced+logged next step)
    acc_ncol     = acc_ncol     + ncol
    acc_nvalid   = acc_nvalid   + count(valid(:ncol))
    acc_clamp_lo = acc_clamp_lo + count(valid(:ncol) .and. ratio(:ncol) == aod_ratio_min)
    acc_clamp_hi = acc_clamp_hi + count(valid(:ncol) .and. ratio(:ncol) == aod_ratio_max)

    ! 3b) pre-nudge energy baseline: set state%te_cur/tw_cur to the PRE-overwrite
    !     value so the post-overwrite check below measures ONLY the nudge interval
    !     (not the preceding aerosol_wet_processes block). Trace aerosols are not in
    !     the te/tw integrals, so this baseline call reports ~0 itself.
    call check_energy_cam_chng(state, tend, 'AODNUDGE_pre', nstep, ztodt, &
                               zero_flx, zero_flx, zero_flx, zero_flx)

    ! 4) hard-overwrite aerosol mass + number ('a' phase; aci_on routes 'c'/ACI)
    call apply_scaling(state, pbuf, ratio, aod_aci_on)

    ! 5) model AOD after overwrite (for diagnostics / round-trip check)
    call model_aod550(state, pbuf, aod_post)

    ! 6) diagnostics
    if (aod_diag_on) then
      maskr = 0._r8
      where (valid(:ncol)) maskr(:ncol) = 1._r8
      call outfld('AODNDG_OBS',        target_aod(:ncol), ncol, lchnk)
      call outfld('AODNDG_MODEL_PRE',  aod_pre(:ncol),    ncol, lchnk)
      call outfld('AODNDG_MODEL_POST', aod_post(:ncol),   ncol, lchnk)
      call outfld('AODNDG_RATIO',      ratio(:ncol),      ncol, lchnk)
      call outfld('AODNDG_MASK',       maskr(:ncol),      ncol, lchnk)
    end if

    ! 7) conservation gate: relative to the pre-nudge baseline (3b), scaling trace
    !    aerosols changes no energy/water -> this must report ~0 with zero fluxes.
    call check_energy_cam_chng(state, tend, 'AODNUDGE', nstep, ztodt, &
                               zero_flx, zero_flx, zero_flx, zero_flx)
  end subroutine aod_nudging_timestep_tend
```

- [ ] **Step 5: Compile-verify (incremental build).**
```bash
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
cd /glade/work/fillmore/CESM3/cases/sp2_mam4
./case.build
```
Expected: `MODEL BUILD HAS FINISHED SUCCESSFULLY`. (All new imports are verified public: `check_energy_cam_chng` in `check_energy.F90:52`; `radiation_do` in `rrtmgp/radiation.F90:66,390` (single arg `op`); `mpi_sum`/`mpi_integer` re-exported by `spmd_utils:58-64`; `mpi_reduce` is the MPI external, mirroring the `mpi_bcast` usage in `nudging.F90`.)

- [ ] **Step 6: Mirror + commit.**
```bash
cp /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_intr.F90 \
   /glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_intr.F90
cd /glade/work/fillmore/CERES-SARB-CAM7
git add src/cam/aod_nudging_intr.F90
git commit -m "SP2 Task 6: driver lifecycle (init/timestep_init/timestep_tend), AODNDG_* diagnostics, energy check"
```

**Deliverable:** Complete driver that orchestrates obs->optics->kernel->overwrite **at the radiation cadence** (D6), emits the five gridded AODNDG_* diagnostics PLUS a per-step MPI-reduced ratio hit-rate / clamp-hit log line (SPEC R12), passes `aod_aci_on` to the ACI hook, and brackets the overwrite with pre/post energy checks so the conservation gate measures only the nudge; compiles into CAM.

---

### Task 7: Wire the driver into `cam7/physpkg.F90`

**Files:**
- Modify: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam7/physpkg.F90`
- Create (mirror diff): `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/physpkg.F90.diff`

**Interfaces:**
- Consumes: `aod_nudging_intr::{aod_nudge_on, aod_nudge_active, aod_nudging_init, aod_nudging_timestep_init, aod_nudging_timestep_tend}` (Tasks 5,6).

- [ ] **Step 1: Init hook in `phys_init`.** In `physpkg.F90`, the subroutine that contains `if(Nudge_Model) call nudging_init` (around L956). Add the `use` inside that subroutine near `use nudging, only: Nudge_Model, nudging_init` (L770):
```fortran
    use aod_nudging_intr,   only: aod_nudge_on, aod_nudging_init
```
and after the existing `if(Nudge_Model) call nudging_init` (L956) add:
```fortran
    ! Initialize AOD nudging
    if (aod_nudge_on) call aod_nudging_init()
```

- [ ] **Step 2: Timestep-init hook in `phys_timestep_init`.** Near `use nudging, only: Nudge_Model, nudging_timestep_init` (L3046) add:
```fortran
  use aod_nudging_intr,    only: aod_nudge_on, aod_nudging_timestep_init
```
and after `if(Nudge_Model) call nudging_timestep_init(phys_state)` (L3118) add:
```fortran
  ! Update AOD-nudging obs snapshots (global IO; once per timestep)
  if (aod_nudge_on) call aod_nudging_timestep_init(phys_state)
```

- [ ] **Step 3: Tend hook in `tphysac`.** Add the `use` inside `tphysac` near `use nudging, only: Nudge_Model,Nudge_ON,nudging_timestep_tend` (L1414):
```fortran
    use aod_nudging_intr,   only: aod_nudge_on, aod_nudge_active, aod_nudging_timestep_tend
```
Then insert the overwrite call AFTER `call t_stopf('aerosol_wet_processes')` and its closing `endif` (L2015-2017) and BEFORE `call t_startf('bc_history_write')` (L2024). Exact insertion (immediately after the `endif` that closes the `aerosol_wet_processes` block at ~L2017):
```fortran
    !===================================================
    ! AOD nudging: overwrite aerosol mass+number before radiation
    ! (after wet processes / water uptake, so optics see a settled state;
    !  before radiation_tend, so RRTMGP sees the nudged aerosol -> direct effect).
    ! The D6 RADIATION-CADENCE gate lives INSIDE aod_nudging_timestep_tend
    ! (it early-returns on non-radiation steps via radiation_do('sw')), so the
    ! call here fires every physics step but only overwrites on radiation steps.
    !===================================================
    if (aod_nudge_on .and. aod_nudge_active) then
       call t_startf('aod_nudging')
       call aod_nudging_timestep_tend(state, tend, pbuf, ztodt)
       call t_stopf('aod_nudging')
    end if
```

- [ ] **Step 4: Full build with the hook active.**
```bash
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
cd /glade/work/fillmore/CESM3/cases/sp2_mam4
./case.build
```
Expected: `MODEL BUILD HAS FINISHED SUCCESSFULLY`. Confirm the four modules are in the build's object list:
```bash
ls $(./xmlquery -value EXEROOT)/atm/obj | grep -i aod_nudging
```
Expected: `aod_nudging_kernel.o aod_nudging_obs.o aod_nudging_optics.o aod_nudging_intr.o` (order may vary).

- [ ] **Step 5: Capture the diff, mirror, commit** (capture ONLY `physpkg.F90` here — the second of the "two `.F90` diffs"; `runtime_opts.F90.diff` was captured in Task 5 Step 7).
```bash
cd /glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam
git -C . diff -- src/physics/cam7/physpkg.F90 \
  > /glade/work/fillmore/CERES-SARB-CAM7/src/cam/physpkg.F90.diff
cd /glade/work/fillmore/CERES-SARB-CAM7
git add src/cam/physpkg.F90.diff
git commit -m "SP2 Task 7: hook driver into cam7/physpkg.F90 (init, timestep_init, tphysac before radiation)"
```

**Deliverable:** A complete CAM7 executable that includes all four modules and the lifecycle hooks; the nudge runs between wet processes and radiation, at the radiation cadence. The repo carries two `.F90` diffs (`runtime_opts.F90.diff`, `physpkg.F90.diff`) plus the namelist XML full copies.

---

### Task 8: Synthetic contract obs + first end-to-end MAM4 regression

**Files:**
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/make_synthetic_obs.py`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/run_integration_mam4.sh`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/check_integration.py`

**Interfaces:**
- Consumes: the built case `sp2_mam4` (Task 7); contract file (Global Constraints).
- Produces: the assertion that post-overwrite AOD == obs where valid (within optics round-trip tolerance) and unchanged where fill; energy-conservation confirmation.

- [ ] **Step 1: Write the synthetic obs generator** at `sp2_tests/make_synthetic_obs.py`. It writes one contract file per 3-hour window for a given date, on the f09 grid, with a constant valid AOD over a test box (lat 0..40N, lon 200..280E) and fill elsewhere:
```python
#!/usr/bin/env python3
"""Generate CONTRACT-CONFORMING synthetic obs files (f09, 3-hourly) for SP2 tests.

Strictly matches the frozen obs-file contract (SPEC.md section 5):
  - netCDF4/CF-1.10; dims lat=192, lon=288, nbnds=2.
  - lat/lon float64 with standard_name + bounds; lat_bnds/lon_bnds float64.
  - SCALAR CF `time` (window CENTER) float64, units "hours since 2000-01-01 ...",
    calendar="gregorian", standard_name="time", bounds="time_bnds";
    time_bnds(nbnds) = [window_start, window_end].
  - aod_weighted_mean(lat,lon) float32 _FillValue=-999.f (primary), with the
    contract long_name + standard_name; aod_uncertainty float32 _FillValue=-999.f;
    aod_count int32 _FillValue=0; recommended per-sensor float32 fields.
  - Full provenance global attributes.
Filename: MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc, %s = window-START sec-of-day (i5.5).
SP2 reads the scalar `time` and interpolates on it; it only reads aod_weighted_mean
for the nudge, but this writer conforms to the WHOLE contract so SP1 parity holds.
"""
import argparse, datetime, os
import numpy as np
from netCDF4 import Dataset

FILL_F = np.float32(-999.0)   # float _FillValue (contract -999.f)
FILL_I = np.int32(0)          # int32 _FillValue for aod_count (contract 0)
EPOCH  = datetime.datetime(2000, 1, 1, 0, 0, 0)

def hours_since_2000(dt):
    # Gregorian (proleptic) hours since 2000-01-01 00:00:00 UTC. Negative pre-2000
    # is fine: SP2 anchors the model time on the file center, so only the 3-h
    # center spacing matters for the test, not the absolute epoch value.
    return (dt - EPOCH).total_seconds() / 3600.0

def f09_grid():
    # FV 0.9x1.25: lat 192 pts -90..90 inclusive; lon 288 pts 0..358.75 step 1.25.
    lat = np.linspace(-90.0, 90.0, 192)
    lon = np.arange(0.0, 360.0, 1.25)
    # Cell bounds (computed once). lat: midpoints, capped at the poles.
    lat_b = np.zeros((192, 2))
    mid = (lat[:-1] + lat[1:]) / 2.0
    lat_b[1:, 0] = mid
    lat_b[:-1, 1] = mid
    lat_b[0, 0] = -90.0
    lat_b[-1, 1] = 90.0
    lon_b = np.zeros((288, 2))
    lon_b[:, 0] = lon - 0.625
    lon_b[:, 1] = lon + 0.625
    return lat, lon, lat_b, lon_b

def write_file(path, lat, lon, lat_b, lon_b, value, start_hours, center_hours, end_hours):
    nlat, nlon = lat.size, lon.size
    aod = np.full((nlat, nlon), FILL_F, dtype="f4")
    # Valid test box: 0..40N, 200..280E (fill elsewhere -> SP2 leaves those free).
    jlat = np.where((lat >= 0.0) & (lat <= 40.0))[0]
    ilon = np.where((lon >= 200.0) & (lon <= 280.0))[0]
    box = np.ix_(jlat, ilon)
    aod[box] = np.float32(value)
    valid = aod > -900.0

    ds = Dataset(path, "w", format="NETCDF4")
    ds.createDimension("lat", nlat)
    ds.createDimension("lon", nlon)
    ds.createDimension("nbnds", 2)   # contract bounds dim name is 'nbnds'

    vlat = ds.createVariable("lat", "f8", ("lat",))
    vlat[:] = lat; vlat.units = "degrees_north"
    vlat.standard_name = "latitude"; vlat.bounds = "lat_bnds"
    vlon = ds.createVariable("lon", "f8", ("lon",))
    vlon[:] = lon; vlon.units = "degrees_east"
    vlon.standard_name = "longitude"; vlon.bounds = "lon_bnds"
    ds.createVariable("lat_bnds", "f8", ("lat", "nbnds"))[:] = lat_b
    ds.createVariable("lon_bnds", "f8", ("lon", "nbnds"))[:] = lon_b

    vt = ds.createVariable("time", "f8", ())            # SCALAR (0-d) coordinate
    vt[...] = center_hours
    vt.units = "hours since 2000-01-01 00:00:00 UTC"
    vt.calendar = "gregorian"; vt.standard_name = "time"; vt.bounds = "time_bnds"
    ds.createVariable("time_bnds", "f8", ("nbnds",))[:] = np.array(
        [start_hours, end_hours], dtype="f8")

    va = ds.createVariable("aod_weighted_mean", "f4", ("lat", "lon"), fill_value=FILL_F)
    va[:] = aod; va.units = "1"
    va.long_name = "Merged MODIS+VIIRS column AOD at 550 nm"
    va.standard_name = "atmosphere_optical_thickness_due_to_ambient_aerosol_particles"
    vu = ds.createVariable("aod_uncertainty", "f4", ("lat", "lon"), fill_value=FILL_F)
    unc = np.where(valid, np.float32(0.05), FILL_F).astype("f4")
    vu[:] = unc; vu.units = "1"
    vu.long_name = "1-sigma uncertainty of aod_weighted_mean"
    vc = ds.createVariable("aod_count", "i4", ("lat", "lon"), fill_value=FILL_I)
    cnt = np.where(valid, np.int32(10), FILL_I).astype("i4")
    vc[:] = cnt; vc.units = "1"
    vc.long_name = "number of valid L2 pixels contributing to the cell-window"
    # Recommended per-sensor diagnostics (mirror the merged field where valid).
    for nm, ln in (("aod_weighted_mean_modis", "MODIS column AOD at 550 nm"),
                   ("aod_weighted_mean_viirs", "VIIRS column AOD at 550 nm")):
        vs = ds.createVariable(nm, "f4", ("lat", "lon"), fill_value=FILL_F)
        vs[:] = aod; vs.units = "1"; vs.long_name = ln

    # Required provenance globals (contract).
    ds.Conventions = "CF-1.10"
    ds.title = "SP2 synthetic contract obs (TEST ONLY)"
    ds.institution = "NCAR"
    ds.source = "synthetic (no real MODIS/VIIRS L2 input)"
    ds.history = "created by make_synthetic_obs.py"
    ds.references = "CERES-SARB-CAM7 SPEC.md section 5"
    ds.qc_thresholds = "synthetic: none"
    ds.merge_method = "synthetic constant box"
    ds.merge_version = "test-0"
    ds.bias_correction_method = "none (synthetic)"
    ds.bias_correction_version = "test-0"
    ds.grid = "f09 FV 0.9x1.25 (192x288)"
    ds.aod_wavelength_nm = 550
    ds.date_created = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    ds.git_commit = "synthetic-test"
    ds.close()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", required=True)
    p.add_argument("--date", required=True, help="YYYYMMDD of the first window-start day")
    p.add_argument("--ndays", type=int, default=1)
    p.add_argument("--times-per-day", type=int, default=8)
    p.add_argument("--value", type=float, default=0.30)
    a = p.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    lat, lon, lat_b, lon_b = f09_grid()
    win = 86400 // a.times_per_day
    day0 = datetime.datetime(int(a.date[:4]), int(a.date[4:6]), int(a.date[6:8]))
    for d in range(a.ndays):                # timedelta rolls month/day boundaries
        for k in range(a.times_per_day):
            start = k * win
            ws_dt = day0 + datetime.timedelta(days=d, seconds=start)  # window start
            start_hours  = hours_since_2000(ws_dt)
            center_hours = hours_since_2000(ws_dt + datetime.timedelta(seconds=win // 2))
            end_hours    = hours_since_2000(ws_dt + datetime.timedelta(seconds=win))
            fname = "MODIS_VIIRS_AOD_3hr_f09.%04d%02d%02d.%05d.nc" % (
                ws_dt.year, ws_dt.month, ws_dt.day, start)
            write_file(os.path.join(a.outdir, fname), lat, lon, lat_b, lon_b,
                       a.value, start_hours, center_hours, end_hours)
            print("wrote", fname)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the obs for the run window.**
```bash
export PATH=/glade/work/fillmore/miniforge3/bin:$PATH   # python with netCDF4 for the generator
mkdir -p /glade/derecho/scratch/fillmore/sp2_obs
python3 /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/make_synthetic_obs.py \
  --outdir /glade/derecho/scratch/fillmore/sp2_obs \
  --date 00010101 --ndays 2 --times-per-day 8 --value 0.30
ls /glade/derecho/scratch/fillmore/sp2_obs | head
```
Expected: 16 files named `MODIS_VIIRS_AOD_3hr_f09.00010101.00000.nc` ... `.00010102.75600.nc`. (F2000dev default run start is year 0001; confirm with `./xmlquery RUN_STARTDATE` and regenerate with the matching date if different.)

Early-run note (OI6): at the very start (model time 0), the *curr* bracket is window `k=-1`, whose file is the previous day (`0000-12-31.75600`), which is NOT generated. SP2 then has `vld_curr=.false.` but `vld_next=.true.` (the `k=0` file `00010101.00000.nc`), so `combine_snapshots` falls back to the nearest valid bracket — nudging is active from step 1 (not free). The assertion in Step 5 reads the LAST h0 record, where both brackets exist, so this boundary case does not affect the test. (To exercise an exactly-bracketed start instead, also generate the prior day with `--date 00001231 --ndays 1`.)

- [ ] **Step 3: Write the run script** at `sp2_tests/run_integration_mam4.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
CASE=/glade/work/fillmore/CESM3/cases/sp2_mam4
OBSDIR=/glade/derecho/scratch/fillmore/sp2_obs
cd "$CASE"
# Enable AOD nudging via user_nl_cam.
cat >> user_nl_cam <<EOF
aod_nudge_on = .true.
aod_obs_path = '${OBSDIR}/'
aod_obs_template = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
aod_times_per_day = 8
aod_diag_on = .true.
! ensure AODNDG_* and AODVIS are written hourly to h0
fincl1 = 'AODNDG_OBS','AODNDG_MODEL_PRE','AODNDG_MODEL_POST','AODNDG_RATIO','AODNDG_MASK','AODVIS'
! Hourly SW radiation (iradsw=-1) so the radiation-cadence overwrite (D6) coincides
! with the hourly history write; the AODNDG_* fields are 'I' (instantaneous), so the
! written record captures the post-nudge state at a radiation step.
iradsw = -1
nhtfrq = -1
mfilt  = 48
EOF
./xmlchange STOP_OPTION=ndays,STOP_N=1,DOUT_S=FALSE
./xmlchange JOB_WALLCLOCK_TIME=01:00:00
./case.submit
echo "submitted; monitor with: ./xmlquery RUNDIR ; tail -f \$(./xmlquery -value RUNDIR)/atm.log.*"
```
Run it:
```bash
bash /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/run_integration_mam4.sh
```
Expected: job submits; on completion `CaseStatus` shows `case.run success`. (`case.submit` uses the real account `P19010000`; this is the first compute-node use, unlike the login-node builds.)

- [ ] **Step 4: Write the assertion script** at `sp2_tests/check_integration.py`:
```python
#!/usr/bin/env python3
"""Assert SP2 nudging behavior from a CAM h0 file.

Where obs valid (AODNDG_MASK==1): AODNDG_MODEL_POST ~= AODNDG_OBS (round-trip tol).
Where fill         (AODNDG_MASK==0): AODNDG_MODEL_POST ~= AODNDG_MODEL_PRE (unchanged).
"""
import argparse, sys
import numpy as np
from netCDF4 import Dataset

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--h0", required=True)
    p.add_argument("--rtol", type=float, default=0.05)  # 5% optics round-trip tol
    p.add_argument("--atol", type=float, default=1e-3)
    a = p.parse_args()
    ds = Dataset(a.h0)
    def last(v): return ds.variables[v][-1, ...].filled(np.nan)
    obs  = last("AODNDG_OBS")
    pre  = last("AODNDG_MODEL_PRE")
    post = last("AODNDG_MODEL_POST")
    mask = last("AODNDG_MASK")
    nud = mask > 0.5
    free = ~nud
    ok = True
    if nud.any():
        err = np.abs(post[nud] - obs[nud]) / np.maximum(obs[nud], a.atol)
        bad = np.sum(err > a.rtol)
        print(f"nudged cells={np.sum(nud)} max_rel_err={np.nanmax(err):.4f} bad={bad}")
        if bad > 0: ok = False
    else:
        print("WARNING: no nudged cells found"); ok = False
    if free.any():
        d = np.abs(post[free] - pre[free])
        bad = np.sum(d > a.atol)
        print(f"free cells={np.sum(free)} max_abs_change={np.nanmax(d):.2e} bad={bad}")
        if bad > 0: ok = False
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the assertion.**
```bash
export PATH=/glade/work/fillmore/miniforge3/bin:$PATH
RUNDIR=$(cd /glade/work/fillmore/CESM3/cases/sp2_mam4 && ./xmlquery -value RUNDIR)
H0=$(ls -t $RUNDIR/sp2_mam4.cam.h0.*.nc | head -1)
python3 /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/check_integration.py --h0 "$H0"
```
Expected: a `nudged cells=...` line with `bad=0`, a `free cells=...` line with `bad=0` (`max_abs_change` ~ 0), and a final `PASS`. NOTE: if `bad > 0` on the nudged cells, the round-trip is not self-consistent -> proceed to Task 9 (water-uptake refresh) to fix it.

- [ ] **Step 6: Verify conservation AND the per-step hit-rate diagnostic in the log.**
```bash
RUNDIR=$(cd /glade/work/fillmore/CESM3/cases/sp2_mam4 && ./xmlquery -value RUNDIR)
# (a) conservation: the 'AODNUDGE' check is bracketed by a pre-nudge baseline, so it
#     measures only the nudge -> no energy-imbalance lines tagged AODNUDGE expected.
grep -iE "AODNUDGE[_ ]" $RUNDIR/atm.log.* | grep -i "energy" || echo "no AODNUDGE energy-error messages (expected)"
# (b) hit-rate diagnostic (SPEC R12): a per-radiation-step line with the nudged
#     fraction and clamp fractions.
grep "AODNUDGE hit-rate" $RUNDIR/atm.log.* | tail -5
```
Expected: (a) no energy-imbalance error lines tagged `AODNUDGE`/`AODNUDGE_pre` (scaling trace aerosols conserves energy/water); (b) one or more `AODNUDGE hit-rate nstep=... nudged_frac=... clamp_lo_frac=... clamp_hi_frac=... ncol_global=...` lines (nudged_frac > 0 over the valid test box).

- [ ] **Step 6b: Science-verification plots (VP5 — `docs/science-verification.md`).** The numeric round-trip (Step 5) proves the column matches; this proves it *spatially*. Render the OBS/PRE/POST/RATIO/MASK box maps from the h0 file with DAVINCI (`SpatialPlotter` + `SpatialBiasPlotter`) via the committed helper `sp2_tests/verify_plots.py`, then **multimodal-inspect**:
```bash
PY=/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python
RUNDIR=$(cd /glade/work/fillmore/CESM3/cases/sp2_mam4 && ./xmlquery -value RUNDIR)
H0=$(ls -t $RUNDIR/sp2_mam4.cam.h0.*.nc | head -1)
$PY /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/verify_plots.py --h0 "$H0" --out "$RUNDIR/verify" --views obs,pre,post,ratio,bias
```
Inspection gate (VP5): `POST≈OBS` inside the valid box (the `POST−OBS` bias map is ~0), `POST≈PRE` outside (no halo at box edges), `RATIO` smooth and ∈ [0.1,10]. Do not mark Task 8 done until the PDFs pass the checklist. *(`verify_plots.py` is the SP2 helper from `docs/science-verification.md` §1; commit it in Step 7.)*

- [ ] **Step 7: Commit the test assets.**
```bash
cd /glade/work/fillmore/CERES-SARB-CAM7
chmod +x sp2_tests/run_integration_mam4.sh
git add sp2_tests/make_synthetic_obs.py sp2_tests/run_integration_mam4.sh sp2_tests/check_integration.py
git commit -m "SP2 Task 8: synthetic contract obs generator + MAM4 integration run + assertion harness"
```

**Deliverable:** End-to-end MAM4 proof that post-overwrite model AOD matches obs where valid, is unchanged where fill, and conserves energy.

---

### Task 9: Water-uptake refresh after scaling — RATIFIED default (2026-06-27) + round-trip confirmation

**Files:**
- Possibly modify: `/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam/src/physics/cam/aod_nudging_intr.F90`
- Update (mirror): `/glade/work/fillmore/CERES-SARB-CAM7/src/cam/aod_nudging_intr.F90`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/docs/spike/water-uptake-roundtrip.md` (record the empirical finding)

**Background (GROUNDED 2026-06-27 against the checkout).** A source check confirmed that for the climate list (`list_idx=0`) the optics **reads `DGNUMWET`/`QAERWAT` from pbuf** (`modal_aerosol_state_mod.F90:473–476`) — it does NOT recompute water uptake. Under uniform mass+number scaling each particle's dry (hence wet) diameter is invariant, so the stale **`DGNUMWET`** stays correct; but grid-box aerosol water **`QAERWAT` scales with particle number** and, left unrefreshed, becomes inconsistent with the scaled mass. Whether the AOD round-trip is nonetheless exact hinges on an internal optics detail — does the wet refractive index key off per-particle `DGNUMWET` (then exact) or off `QAERWAT`/dry-volume (then off by ~1/ratio)? Rather than gamble on that, **and** because the aerosol state handed to RRTMGP must be internally consistent regardless, **the `modal_aero_wateruptake_dr` refresh is the DEFAULT** — one extra call per radiation step, which the model already does once per step at `tphysac` L1968 (cheap relative to radiation). This task **confirms** the round-trip is exact *with* the refresh and **quantifies** the error *without* it (the `QAERWAT`-staleness sensitivity) for the record.

**Interfaces:**
- Consumes: Task 8's `AODNDG_MODEL_POST` vs `AODNDG_OBS` (and vs `ratio*AODNDG_MODEL_PRE`).
- Produces: a documented decision and, if needed, a `modal_aero_wateruptake_dr` re-call in `aod_nudging_timestep_tend`.

- [ ] **Step 1: Quantify the round-trip from the Task 8 output.**
```bash
export PATH=/glade/work/fillmore/miniforge3/bin:$PATH
RUNDIR=$(cd /glade/work/fillmore/CESM3/cases/sp2_mam4 && ./xmlquery -value RUNDIR)
H0=$(ls -t $RUNDIR/sp2_mam4.cam.h0.*.nc | head -1)
python3 - "$H0" <<'PY'
import sys, numpy as np
from netCDF4 import Dataset
ds=Dataset(sys.argv[1])
def last(v): return ds.variables[v][-1,...].filled(np.nan)
obs,pre,post,mask=last("AODNDG_OBS"),last("AODNDG_MODEL_PRE"),last("AODNDG_MODEL_POST"),last("AODNDG_MASK")
m=mask>0.5
# Expected post if round-trip exact = obs (clamped ratio*pre). Compare post vs obs.
rel=np.abs(post[m]-obs[m])/np.maximum(obs[m],1e-3)
print("nudged cells:",int(m.sum()))
print("max rel |post-obs|/obs:",float(np.nanmax(rel)))
print("median rel:",float(np.nanmedian(rel)))
PY
```
Decision rule (RATIFIED 2026-06-27 by the user): the refresh **ships by default** — Steps 2-4 are NOT optional. Use this Step-1 measurement to (a) record the **without-refresh** `max rel |post-obs|/obs` (the `QAERWAT`-staleness sensitivity), then (b) after adding the refresh, confirm the **with-refresh** error is `<= 0.05` (clamping aside; verify ratios ∈ (0.1,10)). If the with-refresh round-trip still exceeds 0.05, STOP — the residual is not water uptake; investigate before proceeding. (If the without-refresh error is itself already `<= 0.05`, that is useful evidence the optics keys off `DGNUMWET`, but ship the refresh anyway for state consistency feeding RRTMGP.)

- [ ] **Step 2 (REQUIRED — ratified default): Add the refresh call.** In `aod_nudging_intr.F90` add the import inside `aod_nudging_timestep_tend`:
```fortran
    use modal_aero_wateruptake, only: modal_aero_wateruptake_dr
```
and insert, between `call apply_scaling(state, pbuf, ratio, aod_aci_on)` (step 4) and the second `call model_aod550(...)` (step 5):
```fortran
    ! Refresh wet diameter / aerosol water from the rescaled state so the optics
    ! round-trip is self-consistent (empirically required for this configuration).
    call modal_aero_wateruptake_dr(state, pbuf)
```

- [ ] **Step 3 (REQUIRED — ratified default): Rebuild.**
```bash
SHIM=$(mktemp -d); ln -s /glade/work/fillmore/miniforge3/bin/python3 $SHIM/python3
export PATH="$SHIM:$(echo $PATH|tr : '\n'|grep -v miniforge3|paste -sd:)"; unset CONDA_PREFIX
cd /glade/work/fillmore/CESM3/cases/sp2_mam4
./case.build
```
Expected: `MODEL BUILD HAS FINISHED SUCCESSFULLY`.

- [ ] **Step 4 (REQUIRED — ratified default): Re-run and re-assert.**
```bash
cd /glade/work/fillmore/CESM3/cases/sp2_mam4 && ./case.submit
# after completion:
export PATH=/glade/work/fillmore/miniforge3/bin:$PATH
RUNDIR=$(cd /glade/work/fillmore/CESM3/cases/sp2_mam4 && ./xmlquery -value RUNDIR)
H0=$(ls -t $RUNDIR/sp2_mam4.cam.h0.*.nc | head -1)
python3 /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/check_integration.py --h0 "$H0"
```
Expected: `PASS` with `bad=0` on nudged cells.

- [ ] **Step 5: Record the finding** in `docs/spike/water-uptake-roundtrip.md` (state the measured max rel error, the decision taken, and the rationale — the dry/wet-diameter invariance argument), then commit:
```bash
cd /glade/work/fillmore/CERES-SARB-CAM7
git add docs/spike/water-uptake-roundtrip.md src/cam/aod_nudging_intr.F90
git commit -m "SP2 Task 9: resolve water-uptake round-trip (empirical); refresh only if needed"
```

**Deliverable:** A documented, empirically grounded decision on water-uptake re-evaluation, with the model AOD round-trip verified self-consistent.

---

### Deferred Indefinitely: MAM5 compatibility work

**Status:** Deferred indefinitely by user direction on 2026-06-28. Do not run, debug, extend, plot, or gate SP2 on MAM5. MAM4 is the only active SP2 model for development, routine regression, real-observation experiments, and science verification.

**Retained context only:** A prior MAM5 attempt with `CAM_NML_USE_CASE=2000_trop_strat_vbs_cam6` generated an `atm_in` with VBS/SVOC emissions and no legacy `SOAE`, initialized AOD nudging with `aerosol modes = 5`, and advanced through the one-day final timestep before failing during restart writing (`write_restart_fie` / `cam_write_restart`) without a valid h0 record. That evidence remains historical context, not a current task.

**Do not do until explicitly reopened:**
- Do not rerun `sp2_tests/run_integration_mam5.sh`.
- Do not create new MAM5 cases or rebuild existing MAM5 cases for SP2.
- Do not add MAM5 plots, DAVINCI verification, CI gates, or acceptance criteria.
- Do not block MAM4 SP2 completion on MAM5 behavior.

The dormant helper `sp2_tests/run_integration_mam5.sh` and its lightweight script tests may remain in the repo as historical scaffolding, but they are not part of the active plan.

### Task 10: One-time MAM4 physics sign-off (`docs/science-verification.md`)

One-time deeper checks (run once, on the MAM4 case) need a paired **free** run (`aod_nudge_on=.false.`, same window, plus instantaneous 3-D aerosol output `fincl1 += 'dst_a1:I','AODVIS','FSNTC'`):
- **VP6** — free-vs-nudged global `AODVIS`: Δ is non-zero **only where obs are valid** and moves model AOD **toward** obs (sign correct).
- **VP7** — aerosol **vertical-profile** D4 shape-invariance: in the shortest active paired run (six timesteps here), at a selected nudged column, the nudged/free instantaneous 3-D aerosol-mmr ratio is **vertically constant** and equals the column `AODNDG_RATIO` (uniform rescale preserved the profile shape). This is the direct test of D4 that no column-integrated assert can make; do not compare a time-mean aerosol profile against point diagnostics.
- **VP8** — RRTMGP **direct effect**: Δ`FSNTC` (clear-sky SW TOA) `< 0` where Δ`AOD` `> 0`, ~0 elsewhere — confirms the nudged aerosol actually changed the radiation budget (the CERES/SARB payoff).
Multimodal-inspect each against the §4 acceptance table. Record pass/fail in the run log.

Operational split (2026-06-28): the submitted July 2008 nudged/free pair has `AODVIS`,
`FSNTC`, and `AODNDG_*`, so run `sp2_tests/verify_pair.py` on those h0 files for VP6/VP8
after completion. That pair does **not** include `dst_a1`, so run
`scripts/setup_sp2_vp7_profile_runs.sh` for a separate short MAM4 VP7 dev/sign-off pair with
its own build root, then run `sp2_tests/verify_profile.py` on the VP7 instantaneous `h0i` pair.
The verifier scans active nudged cells and reports the selected passing column plus candidate
counts. Do not rebuild or repoint the queued July 2008 executable.

---

### Task 11: Transport proof — aerosol increments persist after observations stop

**Status:** Completed and passed on 2026-06-28. The proof used separate development case names and its own build root; it did not rebuild or repoint the queued July 2008 executable shared by `sp2_200807_mam4_modis` and `sp2_200807_mam4_free`. Checker metrics: `post_mask_max=0`, `inside_abs_sum=124.973`, `outside_abs_sum=401.311`, `total_abs_sum=526.284`, `outside_frac=0.762537`, `outside_abs_max=0.855975`.

**Files:**
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/make_transport_pulse_obs.py`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/run_transport_proof.sh`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/check_transport_proof.py`
- Create: `/glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/plot_transport_proof.py`

**Purpose:** Code inspection already shows `apply_scaling` writes through `rad_cnst_*` pointers that alias `state%q`, and `state%q` is the prognostic tracer state. This task adds the model-run proof: create one aerosol increment pulse, turn observations off, and show the resulting AOD anomaly persists and leaves the original pulse mask in a paired free-control comparison.

**Experiment design:**
- Pulse run: first two 3-hour SP2 obs windows have a valid high-AOD box; every later obs window is fill-only.
- Free-control run: same case setup and initial conditions, but all obs windows are fill-only.
- Both runs keep `aod_nudge_on=.true.` so the proof checks that the observation mask, not a different namelist path, controls whether new increments are applied.
- After hour 12, `AODNDG_MASK` must be zero everywhere in the pulse run. Any later nudged-minus-free `AODVIS` anomaly is therefore a persisted aerosol-state perturbation, not a new observation overwrite.
- The transport gate requires the final-time nudged-minus-free `AODVIS` anomaly to remain nonzero outside the original valid-observation mask.

- [x] **Step 1: Create the pulse-observation generator.**

Write `sp2_tests/make_transport_pulse_obs.py` with the same f09 grid, CF metadata, filename template, fill value, and variables as `sp2_tests/make_synthetic_obs.py`, plus these CLI arguments:
```bash
--outdir PATH
--date YYYYMMDD
--ndays INT
--times-per-day INT
--pulse-windows INT
--pulse-value FLOAT
--pulse-lat-min FLOAT
--pulse-lat-max FLOAT
--pulse-lon-min FLOAT
--pulse-lon-max FLOAT
```
Implementation rule: for `global_window_index < pulse_windows`, write `pulse_value` inside the configured lat/lon box and fill outside; for every later window, write fill everywhere. With `--pulse-windows 0`, the script creates the free-control all-fill obs set.

- [x] **Step 2: Generate paired obs sets.**
```bash
export PY=/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python
export OBSDIR=/glade/derecho/scratch/fillmore/sp2_transport_obs
rm -rf "$OBSDIR"
$PY /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/make_transport_pulse_obs.py \
  --outdir "$OBSDIR/pulse" \
  --date 00010101 \
  --ndays 2 \
  --times-per-day 8 \
  --pulse-windows 2 \
  --pulse-value 1.0 \
  --pulse-lat-min 25 \
  --pulse-lat-max 45 \
  --pulse-lon-min 160 \
  --pulse-lon-max 220
$PY /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/make_transport_pulse_obs.py \
  --outdir "$OBSDIR/fill" \
  --date 00010101 \
  --ndays 2 \
  --times-per-day 8 \
  --pulse-windows 0 \
  --pulse-value 1.0 \
  --pulse-lat-min 25 \
  --pulse-lat-max 45 \
  --pulse-lon-min 160 \
  --pulse-lon-max 220
```
Expected: each directory contains 16 files named `MODIS_VIIRS_AOD_3hr_f09.00010101.*.nc` and `MODIS_VIIRS_AOD_3hr_f09.00010102.*.nc`; the pulse directory has valid AOD only in the first two windows; the fill directory has no valid AOD cells.

- [x] **Step 3: Create the paired-run script.**

Write `sp2_tests/run_transport_proof.sh`. It creates two MAM4 `F2000dev` cases on derecho:
- `/glade/work/fillmore/CESM3/cases/sp2_transport_pulse`
- `/glade/work/fillmore/CESM3/cases/sp2_transport_free`

Use the same PE/layout pattern as `sp2_tests/run_integration_mam4.sh`. Both cases run for 2 days with:
```fortran
aod_nudge_on = .true.
aod_obs_template = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
aod_times_per_day = 8
aod_diag_on = .true.
fincl1 = 'AODNDG_OBS','AODNDG_MODEL_PRE','AODNDG_MODEL_POST','AODNDG_RATIO','AODNDG_MASK','AODVIS'
iradsw = -1
nhtfrq = -1
mfilt  = 48
```
Set `aod_obs_path` to `"$OBSDIR/pulse/"` for `sp2_transport_pulse` and `"$OBSDIR/fill/"` for `sp2_transport_free`.

- [x] **Step 4: Run the paired transport experiment.**
```bash
bash /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/run_transport_proof.sh
```
Actual: both cases finished with `case.run success` in interactive PBS allocation `6582111.desched1`. CAM wrote split 48-record history files: `h0a` contains `AODVIS`, while `h0i` contains instantaneous `AODNDG_MASK`, `AODNDG_MODEL_PRE`, and `AODNDG_MODEL_POST`.

- [x] **Step 5: Create and run the transport checker.**

Write `sp2_tests/check_transport_proof.py` with this CLI:
```bash
--nudged-h0 PATH
--free-h0 PATH
--nudged-diag-h0 PATH  # optional; use when AODNDG_* diagnostics are in a split h0i file
--pulse-obs PATH
--post-start-index INT
--outside-frac-min FLOAT
--outside-max-min FLOAT
```
The checker must:
1. Read the original pulse mask from the first pulse obs file (`aod_weighted_mean > -900`).
2. Assert `max(AODNDG_MASK[post_start_index:, :, :]) == 0` in the nudged h0 file.
3. Compute `delta = AODVIS_nudged - AODVIS_free`.
4. At the final record, compute absolute anomaly mass inside and outside the original pulse mask.
5. Pass only when `outside_abs_sum / total_abs_sum >= outside_frac_min` and `outside_abs_max >= outside_max_min`.

Run:
```bash
export PY=/glade/work/fillmore/miniforge3/envs/davinci-monet/bin/python
export PULSE_RUN=/glade/derecho/scratch/fillmore/sp2_transport_pulse/run
export FREE_RUN=/glade/derecho/scratch/fillmore/sp2_transport_free/run
export NUDGED_H0A=$(ls -t "$PULSE_RUN"/sp2_transport_pulse.cam.h0a*.nc | head -1)
export NUDGED_H0I=$(ls -t "$PULSE_RUN"/sp2_transport_pulse.cam.h0i*.nc | head -1)
export FREE_H0A=$(ls -t "$FREE_RUN"/sp2_transport_free.cam.h0a*.nc | head -1)
$PY /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/check_transport_proof.py \
  --nudged-h0 "$NUDGED_H0A" \
  --free-h0 "$FREE_H0A" \
  --nudged-diag-h0 "$NUDGED_H0I" \
  --pulse-obs /glade/derecho/scratch/fillmore/sp2_transport_obs/pulse/MODIS_VIIRS_AOD_3hr_f09.00010101.00000.nc \
  --post-start-index 12 \
  --outside-frac-min 0.02 \
  --outside-max-min 1.0e-4
```
Actual: `PASS` with `post_mask_max=0`, `inside_abs_sum=124.973`, `outside_abs_sum=401.311`, `total_abs_sum=526.284`, `outside_frac=0.762537`, and `outside_abs_max=0.855975`.

- [x] **Step 6: Render DAVINCI-only transport-proof PDFs.**

Write `sp2_tests/plot_transport_proof.py`. It must use DAVINCI `SpatialPlotter`, `MapConfig`, `PlotConfig`, and `build_series`; it must not call raw Matplotlib plotting APIs except to save the DAVINCI-rendered figure. Render PDFs only, under:
```bash
/glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP2_AOD_nudging/transport_proof/sp2_transport_pulse/
```
Required plots:
- `sp2_transport_daily_mean_aodvis_anomaly_day2.pdf` — day-2 daily mean `AODVIS_nudged - AODVIS_free`, global, continents only, solid gridlines, robust symmetric difference limits.
- `sp2_transport_final_aodvis_anomaly.pdf` — final-record `AODVIS_nudged - AODVIS_free`, global, continents only, solid gridlines, robust symmetric difference limits.
- `sp2_transport_nudge_mask_daily_mean_day2.pdf` — day-2 daily mean `AODNDG_MASK`, global, continents only, solid gridlines, scale `[0, 1]`; this should be zero everywhere.

Run:
```bash
$PY /glade/work/fillmore/CERES-SARB-CAM7/sp2_tests/plot_transport_proof.py \
  --nudged-h0 "$NUDGED_H0A" \
  --free-h0 "$FREE_H0A" \
  --nudged-diag-h0 "$NUDGED_H0I" \
  --out /glade/work/fillmore/Data/CERES-SARB-CAM7/plots/SP2_AOD_nudging/transport_proof/sp2_transport_pulse
```
Actual: exactly the three PDFs above; no PNG files; all titles follow DAVINCI title case and omit dates from titles.

- [ ] **Step 7: Commit the transport-proof task.**
Not performed in this session; keep the changes uncommitted unless the user requests a commit/push.
```bash
cd /glade/work/fillmore/CERES-SARB-CAM7
git add \
  docs/superpowers/plans/2026-06-27-sp2-cam7-nudging-module.md \
  sp2_tests/make_transport_pulse_obs.py \
  sp2_tests/run_transport_proof.sh \
  sp2_tests/check_transport_proof.py \
  sp2_tests/plot_transport_proof.py
git commit -m "SP2 Task 11: add transport proof for persisted aerosol increments"
git push
```

**Deliverable:** Completed. A paired-run proof showed that, after observations are fill-only and `AODNDG_MASK` is zero, the nudged-minus-free `AODVIS` anomaly persists outside the original pulse mask. This is the run-time transport evidence; code inspection alone is not sufficient for closing Task 11.

---

## Notes for the implementer
- The kernel is the only piece with isolated unit tests (pFUnit); CAM-internal modules are gated by `case.build` success plus the end-to-end assertions in Tasks 8-10. Do not skip the incremental builds — they localize compile errors to one module. Task 11 transport/advection proof is complete; the remaining MAM4 SP2 gates are VP5, VP6, and VP8 after the queued July 2008 pair finishes.
- `model_aod550` passes `nnite=0`: `aerosol_optics_cam_sw` fills `tauxar` for all columns regardless; the night-column args only mask its own internal diagnostics. This gives AOD for day AND night columns (obs validity, not solar zenith, decides whether a column is nudged).
- The write-back aliases `state%q` through the `rad_cnst_*` `mmr`/`num` pointers (source 'A'); assigning through them overwrites the prognostic state in place. Columns with `ratio==1` are no-ops, so no masking is needed in `apply_scaling`.
- **Cadence (D6, both halves).** The overwrite runs ONLY on radiation steps — `aod_nudging_timestep_tend` early-returns unless `radiation_do('sw')` is true — and within a window it time-interpolates the obs. The `tphysac` hook fires every physics step but the driver gates internally, so nothing is overwritten on non-radiation substeps. Set `iradsw` and `nhtfrq` together in the regression so the instantaneous (`'I'`) AODNDG_* output lands on a radiation step.
- **Time interpolation reads the file `time` (contract).** `load_window` reads each bracket file's SCALAR CF `time` (window center) via `pio_inq_varid`/`pio_get_var`; `set_weight` interpolates on those file values. To avoid coupling the model calendar (noleap) to the file calendar (gregorian), the model time is placed on the file axis by anchoring at the curr center read from the file and adding the model's calendar-free elapsed offset (`tcen_curr + (t_now - cm_curr)/3600`). This satisfies the contract ("interpolate on their scalar `time`") and is robust if SP1's centers are not exactly 3 h apart, with no leap-day arithmetic. For production, the obs `time` axis and the model clock should share a calendar/epoch convention (document in `RUN.md`).
- **Grid identity (contract).** `load_window` reads the file's `lat`/`lon` dim lengths and compares them to f09 (192×288) AND to CAM's own `physgrid` size (`cam_grid_dimensions`), calling `endrun` on any mismatch — no in-model interpolation, abort on dimension mismatch.
- **Energy check is bracketed.** A pre-nudge `check_energy_cam_chng('AODNUDGE_pre',...)` sets `state%te_cur`/`tw_cur` to the pre-overwrite values, so the post-nudge `'AODNUDGE'` check measures ONLY the nudge interval (not the preceding `aerosol_wet_processes` block). Both report ~0 because trace aerosols are not in the te/tw integrals; the bracketing just makes the `'AODNUDGE'` label accurate.
- **Per-step hit-rate (R12).** Counters accumulate across the chunk loop and are MPI-reduced + logged once per step (`AODNUDGE hit-rate ...`) at the top of the next `timestep_init` (a one-step lag; the run's final step is not flushed). This is in addition to the gridded `AODNDG_RATIO`/`AODNDG_MASK` fields.
- **ACI hook is live but guarded.** `aod_aci_on` is read/broadcast/logged and passed to `apply_scaling(...,aci_on)`. v1 scales only the interstitial 'a' phase (direct effect); `aci_on=.true.` routes to the cloud-borne ('c') path, which is a clean `endrun` plus a marked future-implementation block — ACI-ready without silently doing unvalidated work.
- **550 nm is band-approximate.** `idx_sw_diag` is a broad visible band that "contains 500-nm wave" (radconstants), SPEC-sanctioned as the 550 nm proxy; the AOD@550 round-trip and the contract's "550 nm" matching are therefore band-approximate (inherited, not a defect of this module).
