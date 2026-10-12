module aod_optics_kernel
!-----------------------------------------------------------------------------
! PURE, CAM-agnostic optics math for SP3 band-output diagnostics.
!-----------------------------------------------------------------------------
  use shr_kind_mod, only: r8 => shr_kind_r8

  implicit none
  private

  public :: overlap_weights
  public :: remap_extensive
  public :: lw_scatter
  public :: asym_from_scaweighted
  public :: clamp_layer

  real(r8), parameter, public :: TAU_THRESH = 1.e-5_r8
  real(r8), parameter, public :: OMEGA_CAP  = 0.9_r8

contains

  subroutine overlap_weights(nsrc, src_lo, src_hi, ndst, dst_lo, dst_hi, w, coverage)
    integer,  intent(in)  :: nsrc, ndst
    real(r8), intent(in)  :: src_lo(nsrc), src_hi(nsrc)
    real(r8), intent(in)  :: dst_lo(ndst), dst_hi(ndst)
    real(r8), intent(out) :: w(ndst, nsrc)
    real(r8), intent(out), optional :: coverage(ndst)

    integer  :: i, j
    real(r8) :: slo, shi, dlo, dhi, overlap, covered, width

    w = 0._r8
    if (present(coverage)) coverage = 0._r8
    do i = 1, ndst
      dlo = min(dst_lo(i), dst_hi(i))
      dhi = max(dst_lo(i), dst_hi(i))
      width = dhi - dlo
      if (width <= 0._r8) cycle

      covered = 0._r8
      do j = 1, nsrc
        slo = min(src_lo(j), src_hi(j))
        shi = max(src_lo(j), src_hi(j))
        if (shi <= slo) cycle

        dlo = min(dst_lo(i), dst_hi(i))
        dhi = max(dst_lo(i), dst_hi(i))
        overlap = min(shi, dhi) - max(slo, dlo)
        if (overlap > 0._r8) then
          w(i,j) = overlap
          covered = covered + overlap
        end if
      end do

      if (covered > 0._r8) w(i,:) = w(i,:) / covered
      if (present(coverage)) coverage(i) = covered / width
    end do
  end subroutine overlap_weights

  pure function remap_extensive(nsrc, ndst, w, src) result(dst)
    integer,  intent(in) :: nsrc, ndst
    real(r8), intent(in) :: w(ndst, nsrc)
    real(r8), intent(in) :: src(nsrc)
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
    ext  = max(0._r8, abso) / (1._r8 - ow)
    sca  = ow * ext
    scag = sca * max(-1._r8, min(1._r8, g))
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

    ext  = max(0._r8, ext)
    sca  = max(0._r8, min(sca, ext))
    asym = max(-1._r8, min(1._r8, asym))
  end subroutine clamp_layer

end module aod_optics_kernel
