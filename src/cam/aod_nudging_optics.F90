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

  use aod_nudging_kernel, only: below_tropopause, scale_profile
  use tropopause, only: find_tropopause => tropopause_find_cam

  implicit none
  private
  public :: get_troposphere, aerosol_profiles

  public :: model_aod550
  public :: apply_scaling
  public :: n_aero_modes

  ! Climate (prognostic) radiation-constituent list index (the one radiation uses).
  integer, parameter :: LIST_CLIMATE = 0

contains

  subroutine model_aod550(state, pbuf, aod, layer_mask, trop_aod)
    ! Column AOD at 550 nm = vertical sum of the visible-band layer optical depth,
    ! computed from the CURRENT aerosol state by CAM7's own optics. nnite=0 makes
    ! the routine diagnose every column (day and night); tauxar is filled for all
    ! columns regardless (night masking only affects the routine's own diagnostics).
    type(physics_state),       intent(in), target :: state
    type(physics_buffer_desc), pointer            :: pbuf(:)
    real(r8),                  intent(out)         :: aod(:)   ! (pcols)

    logical, optional, intent(in) :: layer_mask(:,:)
    real(r8), optional, intent(out) :: trop_aod(:)
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
    if (present(trop_aod)) then
      if (.not. present(layer_mask)) call endrun('AODNUDGE: eligible AOD requires a layer mask')
      trop_aod = 0._r8
      trop_aod(:state%ncol) = sum(tauxar(:state%ncol,1:pver,idx_sw_diag), dim=2, &
                                      mask=layer_mask(:state%ncol,:))
    end if
  end subroutine model_aod550

  subroutine apply_scaling(state, pbuf, ratio, aci_on, layer_mask)
    ! Restrict every enumerated mass/number field and optical cache to exactly
    ! the same eligible layers. Absent mask retains whole-column compatibility.
    type(physics_state),       intent(inout), target :: state
    type(physics_buffer_desc), pointer               :: pbuf(:)
    real(r8),                  intent(in)             :: ratio(:)   ! (pcols)
    logical,                   intent(in)             :: aci_on     ! cloud-borne/ACI hook

    logical, optional, intent(in) :: layer_mask(:,:)
    integer           :: nmodes, nbins, naero, nspec, m, l, ncol
    real(r8), pointer :: num(:,:)
    real(r8), pointer :: mmr(:,:)
    real(r8), pointer :: naer(:,:,:)
    real(r8), pointer :: qaerwat(:,:,:)

    if (aci_on) call endrun('AODNUDGE: cloud-borne aerosol scaling is not implemented')
    ncol = state%ncol
    call rad_cnst_get_info(LIST_CLIMATE, nmodes=nmodes, nbins=nbins, naero=naero)

    do m = 1, nmodes
      ! Interstitial mode number mixing ratio.
      call rad_cnst_get_mode_num(LIST_CLIMATE, m, 'a', state, pbuf, num)
      call scale_profile(num, ratio, ncol, layer_mask)

      ! Each interstitial species mass mixing ratio in this mode.
      call rad_cnst_get_info(LIST_CLIMATE, m, nspec=nspec)
      do l = 1, nspec
        call rad_cnst_get_aer_mmr(LIST_CLIMATE, m, l, 'a', state, pbuf, mmr)
        call scale_profile(mmr, ratio, ncol, layer_mask)
      end do
    end do

    if (nmodes > 0) then
      call pbuf_get_field(pbuf, pbuf_get_index('NAER'), naer)
      call pbuf_get_field(pbuf, pbuf_get_index('QAERWAT'), qaerwat)
      do m = 1, nmodes
        call scale_profile(naer(:,:,m), ratio, ncol, layer_mask)
        call scale_profile(qaerwat(:,:,m), ratio, ncol, layer_mask)
      end do
    end if

    ! CARMA/bin aerosols, when present, are a separate radiation-constituent path.
    do m = 1, nbins
      call rad_cnst_get_bin_num(LIST_CLIMATE, m, 'a', state, pbuf, num)
      call scale_profile(num, ratio, ncol, layer_mask)

      call rad_cnst_get_info_by_bin(LIST_CLIMATE, m, nspec=nspec)
      do l = 1, nspec
        call rad_cnst_get_bin_mmr_by_idx(LIST_CLIMATE, m, l, 'a', state, pbuf, mmr)
        call scale_profile(mmr, ratio, ncol, layer_mask)
      end do
    end do

    ! Bulk aerosols are also included by aerosol_optics_cam_sw when naero > 0.
    do m = 1, naero
      call rad_cnst_get_aer_mmr(LIST_CLIMATE, m, state, pbuf, mmr)
      call scale_profile(mmr, ratio, ncol, layer_mask)
    end do

  end subroutine apply_scaling

  subroutine get_troposphere(state, layer_mask, trop_p, trop_level)
    type(physics_state), intent(in) :: state
    logical, intent(out) :: layer_mask(:,:)
    real(r8), intent(out) :: trop_p(:)
    integer, intent(out) :: trop_level(:)
    integer :: i, k
    ! Use CAM's native TWMO diagnosis and its climatology fallback. Freeze this
    ! boundary for both optical probes and the entire current state update.
    trop_level = -1
    trop_p = 0._r8
    call find_tropopause(state, trop_level, tropP=trop_p)
    layer_mask = .false.
    do k = 1, pver
      do i = 1, state%ncol
        layer_mask(i,k) = below_tropopause(k, trop_level(i), pver)
      end do
    end do
  end subroutine get_troposphere

  subroutine aerosol_profiles(state, pbuf, mass, number)
    type(physics_state), intent(in), target :: state
    type(physics_buffer_desc), pointer :: pbuf(:)
    real(r8), intent(out) :: mass(:,:), number(:,:)
    real(r8), pointer :: field(:,:)
    integer :: nmodes, naero, nspec, m, l
    integer :: nbins
    mass = 0._r8
    number = 0._r8
    call rad_cnst_get_info(LIST_CLIMATE, nmodes=nmodes, naero=naero)
    do m = 1, nmodes
      call rad_cnst_get_mode_num(LIST_CLIMATE, m, 'a', state, pbuf, field)
      number(:state%ncol,:) = number(:state%ncol,:) + field(:state%ncol,:)
      call rad_cnst_get_info(LIST_CLIMATE, m, nspec=nspec)
      do l = 1, nspec
        call rad_cnst_get_aer_mmr(LIST_CLIMATE, m, l, 'a', state, pbuf, field)
        mass(:state%ncol,:) = mass(:state%ncol,:) + field(:state%ncol,:)
      end do
    end do
    call rad_cnst_get_info(LIST_CLIMATE, nbins=nbins)
    do m = 1, nbins
      call rad_cnst_get_bin_num(LIST_CLIMATE, m, 'a', state, pbuf, field)
      number(:state%ncol,:) = number(:state%ncol,:) + field(:state%ncol,:)
      call rad_cnst_get_info_by_bin(LIST_CLIMATE, m, nspec=nspec)
      do l = 1, nspec
        call rad_cnst_get_bin_mmr_by_idx(LIST_CLIMATE, m, l, 'a', state, pbuf, field)
        mass(:state%ncol,:) = mass(:state%ncol,:) + field(:state%ncol,:)
      end do
    end do
    do m = 1, naero
      call rad_cnst_get_aer_mmr(LIST_CLIMATE, m, state, pbuf, field)
      mass(:state%ncol,:) = mass(:state%ncol,:) + field(:state%ncol,:)
    end do
  end subroutine aerosol_profiles

  integer function n_aero_modes()
    ! Number of aerosol modes in the climate list (4 for MAM4, 5 for MAM5).
    integer :: nmodes
    call rad_cnst_get_info(LIST_CLIMATE, nmodes=nmodes)
    n_aero_modes = nmodes
  end function n_aero_modes

end module aod_nudging_optics
