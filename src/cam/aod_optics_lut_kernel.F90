module aod_optics_lut_kernel
!-----------------------------------------------------------------------------
! PURE LUT math for SP3 LFL-native aerosol-optics diagnostics.
!-----------------------------------------------------------------------------
  use shr_kind_mod, only: r8 => shr_kind_r8

  implicit none
  private

  public :: cheb_basis
  public :: eval_coeff_table
  public :: mix_refindex
  public :: lut_scatter

  real(r8), parameter :: RADMIN = 0.01e-6_r8
  real(r8), parameter :: RADMAX = 25.e-6_r8
  real(r8), parameter :: XRMIN = log(RADMIN)
  real(r8), parameter :: XRMAX = log(RADMAX)

contains

  pure subroutine cheb_basis(ncoef, surface_radius_m, basis)
    integer,  intent(in)  :: ncoef
    real(r8), intent(in)  :: surface_radius_m
    real(r8), intent(out) :: basis(ncoef)

    integer :: icoef
    real(r8) :: xrad

    if (ncoef <= 0) return
    xrad = max(log(max(surface_radius_m, RADMIN)), XRMIN)
    xrad = min(xrad, XRMAX)
    xrad = (2._r8*xrad - XRMAX - XRMIN) / (XRMAX - XRMIN)

    basis(1) = 1._r8
    if (ncoef == 1) return
    basis(2) = xrad
    do icoef = 3, ncoef
      basis(icoef) = 2._r8*xrad*basis(icoef-1) - basis(icoef-2)
    end do
  end subroutine cheb_basis

  pure subroutine eval_coeff_table(ncoef, nre, nim, re_axis, im_axis, table, basis, &
                                   ref_re, ref_im, log_ext, value)
    integer,  intent(in)  :: ncoef, nre, nim
    real(r8), intent(in)  :: re_axis(nre), im_axis(nim)
    real(r8), intent(in)  :: table(ncoef,nre,nim)
    real(r8), intent(in)  :: basis(ncoef)
    real(r8), intent(in)  :: ref_re, ref_im
    logical,  intent(in)  :: log_ext
    real(r8), intent(out) :: value

    integer :: ire0, ire1, iim0, iim1, icoef
    real(r8) :: wre, wim, c00, c10, c01, c11, coeff

    call bracket_axis(nre, re_axis, ref_re, ire0, ire1, wre)
    call bracket_axis(nim, im_axis, abs(ref_im), iim0, iim1, wim)

    value = 0._r8
    do icoef = 1, ncoef
      c00 = table(icoef,ire0,iim0)
      c10 = table(icoef,ire1,iim0)
      c01 = table(icoef,ire0,iim1)
      c11 = table(icoef,ire1,iim1)
      coeff = (1._r8 - wim) * ((1._r8 - wre)*c00 + wre*c10) + &
              wim * ((1._r8 - wre)*c01 + wre*c11)
      if (icoef == 1) coeff = 0.5_r8 * coeff
      value = value + basis(icoef) * coeff
    end do
    if (log_ext) value = exp(value)
  end subroutine eval_coeff_table

  pure subroutine mix_refindex(nspec, dry_vol, ref_re, ref_im, water_vol, &
                               water_re, water_im, wet_vol, mix_re, mix_im)
    integer,  intent(in)  :: nspec
    real(r8), intent(in)  :: dry_vol(nspec), ref_re(nspec), ref_im(nspec)
    real(r8), intent(in)  :: water_vol, water_re, water_im, wet_vol
    real(r8), intent(out) :: mix_re, mix_im

    integer :: ispec
    real(r8) :: denom

    mix_re = water_vol * water_re
    mix_im = water_vol * water_im
    do ispec = 1, nspec
      mix_re = mix_re + dry_vol(ispec) * ref_re(ispec)
      mix_im = mix_im + dry_vol(ispec) * abs(ref_im(ispec))
    end do
    denom = max(wet_vol, 1.e-60_r8)
    mix_re = mix_re / denom
    mix_im = abs(mix_im / denom)
  end subroutine mix_refindex

  pure subroutine lut_scatter(ext_in, abs_in, asym_in, ext, sca, scag)
    real(r8), intent(in)  :: ext_in, abs_in, asym_in
    real(r8), intent(out) :: ext, sca, scag

    real(r8) :: abso, asym

    ext = max(0._r8, ext_in)
    abso = max(0._r8, min(abs_in, ext))
    sca = max(0._r8, ext - abso)
    asym = max(-1._r8, min(1._r8, asym_in))
    scag = sca * asym
  end subroutine lut_scatter

  pure subroutine bracket_axis(naxis, axis, target, i0, i1, weight)
    integer,  intent(in)  :: naxis
    real(r8), intent(in)  :: axis(naxis), target
    integer,  intent(out) :: i0, i1
    real(r8), intent(out) :: weight

    integer :: i

    if (naxis <= 1) then
      i0 = 1
      i1 = 1
      weight = 0._r8
      return
    end if
    if (target <= axis(1)) then
      i0 = 1
      i1 = 1
      weight = 0._r8
      return
    end if
    if (target >= axis(naxis)) then
      i0 = naxis
      i1 = naxis
      weight = 0._r8
      return
    end if
    do i = 1, naxis - 1
      if (target >= axis(i) .and. target <= axis(i+1)) then
        i0 = i
        i1 = i + 1
        weight = (target - axis(i)) / max(axis(i+1) - axis(i), 1.e-60_r8)
        return
      end if
    end do
    i0 = naxis
    i1 = naxis
    weight = 0._r8
  end subroutine bracket_axis

end module aod_optics_lut_kernel
