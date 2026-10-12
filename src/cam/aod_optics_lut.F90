module aod_optics_lut
!-----------------------------------------------------------------------------
! CAM boundary for SP3 LFL-native aerosol-optics diagnostics.
!-----------------------------------------------------------------------------
  use shr_kind_mod,   only: r8 => shr_kind_r8
  use ppgrid,         only: pcols, pver
  use physics_types,  only: physics_state
  use physics_buffer, only: physics_buffer_desc
  use physconst,      only: rga, rhoh2o
  use cam_abortutils, only: endrun
  use aerosol_properties_mod, only: aero_name_len
  use modal_aerosol_properties_mod, only: modal_aerosol_properties
  use modal_aerosol_state_mod,      only: modal_aerosol_state
  use aod_optics_bands, only: nsw_sarb, nlw_sarb, nbands_sarb
  use aod_optics_lut_kernel, only: cheb_basis, eval_coeff_table, mix_refindex, lut_scatter
  use aod_optics_lut_tables, only: lut_tables_ready, ncoef_lut, nmode_lut, nre_lut, nim_lut, &
                                   sigmag_lut, extpsw_lut, abspsw_lut, asmpsw_lut, &
                                   extplw_lut, absplw_lut, asmplw_lut, &
                                   refrtabsw_lut, refitabsw_lut, refrtablw_lut, refitablw_lut, &
                                   refre_spectype_sw_lut, refim_spectype_sw_lut, &
                                   refre_spectype_lw_lut, refim_spectype_lw_lut, spectype_index

  implicit none
  private

  public :: lfl_band_optics

  integer, parameter :: LIST_CLIMATE = 0
  integer, parameter :: MAX_SPECIES = 64

contains

  subroutine lfl_band_optics(state, pbuf, ext, sca, scag)
    type(physics_state),       intent(in), target :: state
    type(physics_buffer_desc), pointer            :: pbuf(:)
    real(r8),                  intent(out)        :: ext(pcols,pver,nbands_sarb)
    real(r8),                  intent(out)        :: sca(pcols,pver,nbands_sarb)
    real(r8),                  intent(out)        :: scag(pcols,pver,nbands_sarb)

    type(modal_aerosol_properties), pointer :: aero_props
    type(modal_aerosol_state),      pointer :: aero_state

    real(r8) :: dgnumwet(pcols,pver)
    real(r8) :: qaerwat(pcols,pver)
    real(r8) :: dryvol(pcols,pver)
    real(r8) :: watervol(pcols,pver)
    real(r8) :: wetvol(pcols,pver)
    real(r8) :: specvol(MAX_SPECIES)
    real(r8) :: specre(MAX_SPECIES)
    real(r8) :: specim(MAX_SPECIES)
    real(r8) :: mass(pcols,pver)
    real(r8) :: basis(ncoef_lut)
    real(r8) :: logsigma, sigmag, surface_radius
    real(r8) :: specdens, mix_re, mix_im, raw_ext, raw_abs, asym
    real(r8) :: layer_ext, layer_abs, layer_ext_out, layer_sca, layer_scag
    real(r8), pointer :: specmmr(:,:)

    character(len=aero_name_len) :: spectype
    integer :: ncol, nmodes, nspec, imode, ispec, iband, i, k, itype

    if (.not. lut_tables_ready) call endrun('lfl_band_optics: LUT tables are not initialized')

    ext = 0._r8
    sca = 0._r8
    scag = 0._r8

    ncol = state%ncol
    mass(:ncol,:) = state%pdeldry(:ncol,:) * rga

    aero_props => modal_aerosol_properties()
    if (.not. associated(aero_props)) call endrun('lfl_band_optics: modal_aerosol_properties allocation failed')
    aero_state => modal_aerosol_state(state, pbuf)
    if (.not. associated(aero_state)) call endrun('lfl_band_optics: modal_aerosol_state allocation failed')

    nmodes = aero_props%nbins(LIST_CLIMATE)
    if (nmodes > nmode_lut) call endrun('lfl_band_optics: LUT has too few modes')

    do imode = 1, nmodes
      logsigma = aero_props%alogsig(LIST_CLIMATE, imode)
      sigmag = exp(logsigma)
      if (abs(sigmag - sigmag_lut(imode)) > 1.e-5_r8) then
        call endrun('lfl_band_optics: LUT sigmag does not match CAM mode')
      end if

      call aero_state%water_uptake(aero_props, LIST_CLIMATE, imode, ncol, pver, dgnumwet(:ncol,:), qaerwat(:ncol,:))
      dryvol = 0._r8
      watervol = 0._r8
      wetvol = 0._r8
      nspec = aero_props%nspecies(LIST_CLIMATE, imode)
      if (nspec > MAX_SPECIES) call endrun('lfl_band_optics: too many species for local work arrays')

      do ispec = 1, nspec
        call aero_props%get(imode, ispec, list_ndx=LIST_CLIMATE, density=specdens, spectype=spectype)
        itype = spectype_index(trim(spectype))
        if (itype <= 0) call endrun('lfl_band_optics: unsupported aerosol spectype '//trim(spectype))
        call aero_state%get_ambient_mmr(LIST_CLIMATE, ispec, imode, specmmr)
        dryvol(:ncol,:) = dryvol(:ncol,:) + specmmr(:ncol,:) / specdens
      end do
      watervol(:ncol,:) = max(qaerwat(:ncol,:) / rhoh2o, 0._r8)
      wetvol(:ncol,:) = dryvol(:ncol,:) + watervol(:ncol,:)

      do k = 1, pver
        do i = 1, ncol
          if (wetvol(i,k) <= 0._r8 .or. mass(i,k) <= 0._r8) cycle
          surface_radius = 0.5_r8 * dgnumwet(i,k) * exp(2._r8 * logsigma**2)
          call cheb_basis(ncoef_lut, surface_radius, basis)

          do ispec = 1, nspec
            call aero_props%get(imode, ispec, list_ndx=LIST_CLIMATE, density=specdens, spectype=spectype)
            itype = spectype_index(trim(spectype))
            call aero_state%get_ambient_mmr(LIST_CLIMATE, ispec, imode, specmmr)
            specvol(ispec) = specmmr(i,k) / specdens
          end do

          do iband = 1, nsw_sarb
            call fill_spectype_refs_sw(nspec, imode, iband, aero_props, specre, specim)
            call mix_refindex(nspec, specvol(1:nspec), specre(1:nspec), specim(1:nspec), watervol(i,k), &
                              refre_spectype_sw_lut(iband,spectype_index('WAT')), &
                              refim_spectype_sw_lut(iband,spectype_index('WAT')), wetvol(i,k), mix_re, mix_im)
            call eval_coeff_table(ncoef_lut, nre_lut, nim_lut, refrtabsw_lut(:,iband,imode), &
                                  refitabsw_lut(:,iband,imode), extpsw_lut(:,:,:,iband,imode), &
                                  basis, mix_re, mix_im, .true., raw_ext)
            call eval_coeff_table(ncoef_lut, nre_lut, nim_lut, refrtabsw_lut(:,iband,imode), &
                                  refitabsw_lut(:,iband,imode), abspsw_lut(:,:,:,iband,imode), &
                                  basis, mix_re, mix_im, .false., raw_abs)
            call eval_coeff_table(ncoef_lut, nre_lut, nim_lut, refrtabsw_lut(:,iband,imode), &
                                  refitabsw_lut(:,iband,imode), asmpsw_lut(:,:,:,iband,imode), &
                                  basis, mix_re, mix_im, .false., asym)
            layer_ext = raw_ext * wetvol(i,k) * rhoh2o * mass(i,k)
            layer_abs = raw_abs * wetvol(i,k) * rhoh2o * mass(i,k)
            call lut_scatter(layer_ext, layer_abs, asym, layer_ext_out, layer_sca, layer_scag)
            ext(i,k,iband) = ext(i,k,iband) + layer_ext_out
            sca(i,k,iband) = sca(i,k,iband) + layer_sca
            scag(i,k,iband) = scag(i,k,iband) + layer_scag
          end do

          do iband = 1, nlw_sarb
            call fill_spectype_refs_lw(nspec, imode, iband, aero_props, specre, specim)
            call mix_refindex(nspec, specvol(1:nspec), specre(1:nspec), specim(1:nspec), watervol(i,k), &
                              refre_spectype_lw_lut(iband,spectype_index('WAT')), &
                              refim_spectype_lw_lut(iband,spectype_index('WAT')), wetvol(i,k), mix_re, mix_im)
            call eval_coeff_table(ncoef_lut, nre_lut, nim_lut, refrtablw_lut(:,iband,imode), &
                                  refitablw_lut(:,iband,imode), extplw_lut(:,:,:,iband,imode), &
                                  basis, mix_re, mix_im, .true., raw_ext)
            call eval_coeff_table(ncoef_lut, nre_lut, nim_lut, refrtablw_lut(:,iband,imode), &
                                  refitablw_lut(:,iband,imode), absplw_lut(:,:,:,iband,imode), &
                                  basis, mix_re, mix_im, .false., raw_abs)
            call eval_coeff_table(ncoef_lut, nre_lut, nim_lut, refrtablw_lut(:,iband,imode), &
                                  refitablw_lut(:,iband,imode), asmplw_lut(:,:,:,iband,imode), &
                                  basis, mix_re, mix_im, .false., asym)
            layer_ext = raw_ext * wetvol(i,k) * rhoh2o * mass(i,k)
            layer_abs = raw_abs * wetvol(i,k) * rhoh2o * mass(i,k)
            call lut_scatter(layer_ext, layer_abs, asym, layer_ext_out, layer_sca, layer_scag)
            ext(i,k,nsw_sarb+iband) = ext(i,k,nsw_sarb+iband) + layer_ext_out
            sca(i,k,nsw_sarb+iband) = sca(i,k,nsw_sarb+iband) + layer_sca
            scag(i,k,nsw_sarb+iband) = scag(i,k,nsw_sarb+iband) + layer_scag
          end do
        end do
      end do
    end do

    if (associated(aero_state)) deallocate(aero_state)
    if (associated(aero_props)) deallocate(aero_props)
  end subroutine lfl_band_optics

  subroutine fill_spectype_refs_sw(nspec, imode, iband, aero_props, specre, specim)
    integer, intent(in) :: nspec, imode, iband
    type(modal_aerosol_properties), pointer :: aero_props
    real(r8), intent(out) :: specre(MAX_SPECIES), specim(MAX_SPECIES)

    character(len=aero_name_len) :: spectype
    real(r8) :: specdens
    integer :: ispec, itype

    do ispec = 1, nspec
      call aero_props%get(imode, ispec, list_ndx=LIST_CLIMATE, density=specdens, spectype=spectype)
      itype = spectype_index(trim(spectype))
      specre(ispec) = refre_spectype_sw_lut(iband,itype)
      specim(ispec) = refim_spectype_sw_lut(iband,itype)
    end do
  end subroutine fill_spectype_refs_sw

  subroutine fill_spectype_refs_lw(nspec, imode, iband, aero_props, specre, specim)
    integer, intent(in) :: nspec, imode, iband
    type(modal_aerosol_properties), pointer :: aero_props
    real(r8), intent(out) :: specre(MAX_SPECIES), specim(MAX_SPECIES)

    character(len=aero_name_len) :: spectype
    real(r8) :: specdens
    integer :: ispec, itype

    do ispec = 1, nspec
      call aero_props%get(imode, ispec, list_ndx=LIST_CLIMATE, density=specdens, spectype=spectype)
      itype = spectype_index(trim(spectype))
      specre(ispec) = refre_spectype_lw_lut(iband,itype)
      specim(ispec) = refim_spectype_lw_lut(iband,itype)
    end do
  end subroutine fill_spectype_refs_lw

end module aod_optics_lut
