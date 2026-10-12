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
  use physics_buffer,      only: physics_buffer_desc, pbuf_get_field, pbuf_get_index
  use radconstants,        only: nswbands, idx_sw_diag
  use aerosol_optics_cam,  only: aerosol_optics_cam_sw
  use rad_constituents,    only: rad_cnst_get_info, rad_cnst_get_info_by_bin, &
                                 rad_cnst_get_mode_num, rad_cnst_get_bin_num, &
                                 rad_cnst_get_aer_mmr, rad_cnst_get_bin_mmr_by_idx
  use cam_abortutils,      only: endrun

  implicit none
  private

  public :: model_aod550
  public :: apply_scaling
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

    call aerosol_optics_cam_sw(LIST_CLIMATE, state, pbuf, 0, idxnite, tauxar, wa, ga, fa, do_outfld=.false.)

    aod = 0._r8
    aod(:ncol) = sum(tauxar(:ncol, 0:pver, idx_sw_diag), dim=2)
  end subroutine model_aod550

  subroutine apply_scaling(state, pbuf, ratio, aci_on)
    ! Multiply every interstitial-phase ('a') aerosol species mass, every mode/bin
    ! number mixing ratio, and every bulk-aerosol mass by the per-column ratio.
    ! Enumeration is generic (rad_cnst_*) so this works unchanged for MAM4/MAM5 and
    ! remains aligned with the same climate-list aerosol state used by model_aod550.
    ! The mmr/num pointers alias state%q (or pbuf), so assigning through them
    ! overwrites the current aerosol state in place. ratio==1 columns are no-ops.
    ! aci_on (SPEC D5): direct effect (v1) touches ONLY the interstitial 'a' phase.
    ! When aci_on=.true. the routine routes to the reserved cloud-borne ('c') / ACI
    ! path, which is guarded (not validated in v1) but kept as a real, marked
    ! insertion point so the interface is ACI-ready.
    type(physics_state),       intent(inout), target :: state
    type(physics_buffer_desc), pointer               :: pbuf(:)
    real(r8),                  intent(in)             :: ratio(:)   ! (pcols)
    logical,                   intent(in)             :: aci_on     ! cloud-borne/ACI hook

    integer           :: nmodes, nbins, naero, nspec, m, l, icol, ncol
    real(r8), pointer :: num(:,:)
    real(r8), pointer :: mmr(:,:)
    real(r8), pointer :: naer(:,:,:)
    real(r8), pointer :: qaerwat(:,:,:)

    ncol = state%ncol
    call rad_cnst_get_info(LIST_CLIMATE, nmodes=nmodes, nbins=nbins, naero=naero)

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

    if (nmodes > 0) then
      call pbuf_get_field(pbuf, pbuf_get_index('NAER'), naer)
      call pbuf_get_field(pbuf, pbuf_get_index('QAERWAT'), qaerwat)
      do m = 1, nmodes
        do icol = 1, ncol
          naer(icol,:,m)    = ratio(icol) * naer(icol,:,m)
          qaerwat(icol,:,m) = ratio(icol) * qaerwat(icol,:,m)
        end do
      end do
    end if

    ! CARMA/bin aerosols, when present, are a separate radiation-constituent path.
    do m = 1, nbins
      call rad_cnst_get_bin_num(LIST_CLIMATE, m, 'a', state, pbuf, num)
      do icol = 1, ncol
        num(icol,:) = ratio(icol) * num(icol,:)
      end do

      call rad_cnst_get_info_by_bin(LIST_CLIMATE, m, nspec=nspec)
      do l = 1, nspec
        call rad_cnst_get_bin_mmr_by_idx(LIST_CLIMATE, m, l, 'a', state, pbuf, mmr)
        do icol = 1, ncol
          mmr(icol,:) = ratio(icol) * mmr(icol,:)
        end do
      end do
    end do

    ! Bulk aerosols are also included by aerosol_optics_cam_sw when naero > 0.
    do m = 1, naero
      call rad_cnst_get_aer_mmr(LIST_CLIMATE, m, state, pbuf, mmr)
      do icol = 1, ncol
        mmr(icol,:) = ratio(icol) * mmr(icol,:)
      end do
    end do

    ! ----------------------------------------------------------------------------
    ! ACI hook (SPEC D5 / section 2): present but OFF in v1. Direct-effect nudging must
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

  integer function n_aero_modes()
    ! Number of aerosol modes in the climate list (4 for MAM4, 5 for MAM5).
    integer :: nmodes
    call rad_cnst_get_info(LIST_CLIMATE, nmodes=nmodes)
    n_aero_modes = nmodes
  end function n_aero_modes

end module aod_nudging_optics
