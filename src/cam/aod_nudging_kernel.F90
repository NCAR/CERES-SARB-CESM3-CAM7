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
