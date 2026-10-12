module aod_optics_tap
!-----------------------------------------------------------------------------
! SP3 CAM optics abstraction boundary.
! This is the only SP3 module that calls CAM aerosol optics internals.
!-----------------------------------------------------------------------------
  use shr_kind_mod,       only: r8 => shr_kind_r8
  use ppgrid,             only: pcols, pver
  use physics_types,      only: physics_state
  use physics_buffer,     only: physics_buffer_desc
  use radconstants,       only: nswbands, nlwbands
  use aerosol_optics_cam, only: aerosol_optics_cam_sw, aerosol_optics_cam_lw_permode
  use cam_abortutils,     only: endrun
  use aod_optics_kernel,  only: lw_scatter, OMEGA_CAP
  use aod_optics_bands,   only: omega_lw, g_lw, nbins_lw

  implicit none
  private

  public :: sw_camband_optics
  public :: lw_camband_optics
  public :: LIST_CLIMATE

  integer, parameter :: LIST_CLIMATE = 0
  integer, parameter :: MAX_CAM_LW_BINS = 64

contains

  subroutine sw_camband_optics(state, pbuf, ext, sca, scag)
    type(physics_state),       intent(in), target :: state
    type(physics_buffer_desc), pointer            :: pbuf(:)
    real(r8),                  intent(out)        :: ext(pcols,pver,nswbands)
    real(r8),                  intent(out)        :: sca(pcols,pver,nswbands)
    real(r8),                  intent(out)        :: scag(pcols,pver,nswbands)

    real(r8) :: tauxar(pcols,0:pver,nswbands)
    real(r8) :: wa(pcols,0:pver,nswbands)
    real(r8) :: ga(pcols,0:pver,nswbands)
    real(r8) :: fa(pcols,0:pver,nswbands)
    integer  :: idxnite(1)
    integer  :: ncol

    ncol = state%ncol
    tauxar = 0._r8
    wa     = 0._r8
    ga     = 0._r8
    fa     = 0._r8
    idxnite = 1

    call aerosol_optics_cam_sw(LIST_CLIMATE, state, pbuf, 0, idxnite, tauxar, wa, ga, fa, do_outfld=.false.)

    ext  = 0._r8
    sca  = 0._r8
    scag = 0._r8
    ext(:ncol,:,:)  = tauxar(:ncol,1:pver,:)
    sca(:ncol,:,:)  = wa(:ncol,1:pver,:)
    scag(:ncol,:,:) = ga(:ncol,1:pver,:)
  end subroutine sw_camband_optics

  subroutine lw_camband_optics(state, pbuf, ext, sca, scag)
    type(physics_state),       intent(in), target :: state
    type(physics_buffer_desc), pointer            :: pbuf(:)
    real(r8),                  intent(out)        :: ext(pcols,pver,nlwbands)
    real(r8),                  intent(out)        :: sca(pcols,pver,nlwbands)
    real(r8),                  intent(out)        :: scag(pcols,pver,nlwbands)

    real(r8), allocatable :: tauxar_bin(:,:,:,:)
    real(r8) :: ext_bin(pcols,pver)
    real(r8) :: sca_bin(pcols,pver)
    real(r8) :: scag_bin(pcols,pver)
    integer  :: ibin, iwav, nbins_out, max_nbins

    if (nbins_lw <= 0) then
      call endrun('lw_camband_optics: aod_optics_bands_init has not initialized omega_lw/g_lw')
    end if

    max_nbins = max(nbins_lw, MAX_CAM_LW_BINS)
    allocate(tauxar_bin(pcols,pver,nlwbands,max_nbins))
    call aerosol_optics_cam_lw_permode(LIST_CLIMATE, state, pbuf, max_nbins, nbins_out, tauxar_bin)

    ext  = 0._r8
    sca  = 0._r8
    scag = 0._r8
    do ibin = 1, nbins_out
      do iwav = 1, nlwbands
        if (ibin <= nbins_lw) then
          call lw_scatter(tauxar_bin(:,:,iwav,ibin), omega_lw(iwav,ibin), &
                          g_lw(iwav,ibin), OMEGA_CAP, ext_bin, sca_bin, scag_bin)
        else
          call lw_scatter(tauxar_bin(:,:,iwav,ibin), 0._r8, &
                          0._r8, OMEGA_CAP, ext_bin, sca_bin, scag_bin)
        end if
        ext(:,:,iwav)  = ext(:,:,iwav)  + ext_bin
        sca(:,:,iwav)  = sca(:,:,iwav)  + sca_bin
        scag(:,:,iwav) = scag(:,:,iwav) + scag_bin
      end do
    end do

    deallocate(tauxar_bin)
  end subroutine lw_camband_optics

end module aod_optics_tap
