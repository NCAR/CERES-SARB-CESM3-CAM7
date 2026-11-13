! Small test doubles for the CAM6 interfaces used by the optics adapter.
! These verify state mutation and calls; they do not validate CAM radiation.
module shr_kind_mod
  implicit none
  integer, parameter :: shr_kind_r8 = kind(1.d0)
end module
module ppgrid
  integer, parameter :: pcols=3, pver=4
end module
module physics_types
  use shr_kind_mod, only: r8=>shr_kind_r8
  use ppgrid
  type physics_state
    integer :: ncol=2
    real(r8) :: q(pcols,pver,15)=1._r8
  end type
end module
module physics_buffer
  use shr_kind_mod, only: r8=>shr_kind_r8
  use ppgrid
  type physics_buffer_desc
    real(r8) :: value(pcols,pver,4)=1._r8
  end type
contains
  integer function pbuf_get_index(name)
    character(len=*), intent(in) :: name
    select case(name)
    case('NAER')
      pbuf_get_index=1
    case('QAERWAT')
      pbuf_get_index=2
    case default
      stop 99
    end select
  end function
  subroutine pbuf_get_field(pbuf, index, field)
    type(physics_buffer_desc), pointer :: pbuf(:)
    integer, intent(in) :: index
    real(r8), pointer :: field(:,:,:)
    field=>pbuf(index)%value
  end subroutine
end module
module radconstants
  integer, parameter :: nswbands=14, idx_sw_diag=10
end module
module rad_constituents
  use shr_kind_mod, only: r8=>shr_kind_r8
  use physics_types
  use physics_buffer
  interface rad_cnst_get_aer_mmr
    module procedure mode_mmr, bulk_mmr
  end interface
contains
  subroutine rad_cnst_get_info_by_bin(list_idx, m, nspec)
    integer, intent(in) :: list_idx, m
    integer, intent(out) :: nspec
    nspec=1
  end subroutine
  subroutine rad_cnst_get_bin_num(list_idx, m, phase, state, pbuf, num)
    integer, intent(in) :: list_idx, m
    character(len=*), intent(in) :: phase
    type(physics_state), intent(in), target :: state
    type(physics_buffer_desc), pointer :: pbuf(:)
    real(r8), pointer :: num(:,:)
    num=>state%q(:,:,14)
  end subroutine
  subroutine rad_cnst_get_bin_mmr_by_idx(list_idx, m, l, phase, state, pbuf, mmr)
    integer, intent(in) :: list_idx, m, l
    character(len=*), intent(in) :: phase
    type(physics_state), intent(in), target :: state
    type(physics_buffer_desc), pointer :: pbuf(:)
    real(r8), pointer :: mmr(:,:)
    mmr=>state%q(:,:,15)
  end subroutine
  subroutine rad_cnst_get_info(list_idx, m, nmodes, naero, nspec, nbins)
    integer, intent(in) :: list_idx
    integer, intent(in), optional :: m
    integer, intent(out), optional :: nmodes, naero, nspec, nbins
    if(present(nbins)) nbins=1
    if(present(nmodes)) nmodes=4
    if(present(naero)) naero=1
    if(present(nspec)) nspec=1
  end subroutine
  subroutine rad_cnst_get_mode_num(list_idx, m, phase, state, pbuf, num)
    integer, intent(in) :: list_idx, m
    character(len=*), intent(in) :: phase
    type(physics_state), intent(in), target :: state
    type(physics_buffer_desc), pointer :: pbuf(:)
    real(r8), pointer :: num(:,:)
    if(phase/='a') stop 98
    num=>state%q(:,:,m)
  end subroutine
  subroutine mode_mmr(list_idx, m, l, phase, state, pbuf, mmr)
    integer, intent(in) :: list_idx, m, l
    character(len=*), intent(in) :: phase
    type(physics_state), intent(in), target :: state
    type(physics_buffer_desc), pointer :: pbuf(:)
    real(r8), pointer :: mmr(:,:)
    if(phase/='a') stop 97
    mmr=>state%q(:,:,m+4)
  end subroutine
  subroutine bulk_mmr(list_idx, m, state, pbuf, mmr)
    integer, intent(in) :: list_idx, m
    type(physics_state), intent(in), target :: state
    type(physics_buffer_desc), pointer :: pbuf(:)
    real(r8), pointer :: mmr(:,:)
    mmr=>state%q(:,:,9)
  end subroutine
end module
module phys_control
  logical :: prognostic=.true.
contains
  subroutine phys_getopts(prog_modal_aero_out)
    logical, intent(out) :: prog_modal_aero_out
    prog_modal_aero_out=prognostic
  end subroutine
end module
module cam_abortutils
contains
  subroutine endrun(message)
    character(len=*), intent(in) :: message
    print *, message
    stop 1
  end subroutine
end module
module aer_rad_props
  use shr_kind_mod, only: r8=>shr_kind_r8
  use ppgrid
  use radconstants
  use physics_types
  use physics_buffer
contains
  subroutine aer_rad_props_sw(list_idx, state, pbuf, nnite, idxnite, tau, tau_w, tau_w_g, tau_w_f, do_outfld)
    integer, intent(in) :: list_idx, nnite, idxnite(:)
    type(physics_state), intent(in), target :: state
    type(physics_buffer_desc), pointer :: pbuf(:)
    real(r8), intent(out) :: tau(pcols,0:pver,nswbands), tau_w(pcols,0:pver,nswbands)
    real(r8), intent(out) :: tau_w_g(pcols,0:pver,nswbands), tau_w_f(pcols,0:pver,nswbands)
    logical, intent(in), optional :: do_outfld
    integer :: k
    if(.not.present(do_outfld)) stop 96
    if(do_outfld .or. nnite/=0 .or. list_idx/=0) stop 95
    tau=0._r8
    tau_w=0._r8
    tau_w_g=0._r8
    tau_w_f=0._r8
    do k=1,pver
      tau(:,k,idx_sw_diag)=sum(state%q(:,k,5:9),dim=2)+state%q(:,k,15)
    end do
  end subroutine
end module

module tropopause
  use physics_types
  integer :: test_trop_level(pcols)=[2,3,-1]
contains
  subroutine tropopause_find(state, trop_level, tropP)
    type(physics_state), intent(in) :: state
    integer, intent(out) :: trop_level(:)
    real(r8), intent(out), optional :: tropP(:)
    trop_level=test_trop_level
    if(present(tropP)) tropP=20000._r8
  end subroutine
  subroutine tropopause_find_cam(state, trop_level, tropP)
    type(physics_state), intent(in) :: state
    integer, intent(out) :: trop_level(:)
    real(r8), intent(out), optional :: tropP(:)
    call tropopause_find(state,trop_level,tropP)
  end subroutine
end module

module aerosol_optics_cam
  use aer_rad_props, only: aerosol_optics_cam_sw=>aer_rad_props_sw
end module
