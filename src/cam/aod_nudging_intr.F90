module aod_nudging_intr
!-----------------------------------------------------------------------------
! AOD-nudging physics interface/driver.
!-----------------------------------------------------------------------------
  use shr_kind_mod,   only: r8 => shr_kind_r8, cl => shr_kind_cl, cs => shr_kind_cs
  use cam_abortutils, only: endrun
  use cam_logfile,    only: iulog
  use spmd_utils,     only: masterproc, mstrid=>masterprocid, mpicom, mpi_success, &
                            mpi_integer, mpi_real8, mpi_logical, mpi_character, mpi_sum
  use ppgrid,         only: pcols, begchunk, endchunk
  use physics_types,  only: physics_state, physics_tend
  use physics_buffer, only: physics_buffer_desc
  use time_manager,   only: get_curr_date, get_nstep
  use cam_history,    only: addfld, outfld, horiz_only
  use radiation,      only: radiation_do
  use aod_nudging_kernel, only: compute_ratio
  use aod_nudging_optics,  only: model_aod550, apply_scaling, n_aero_modes
  use aod_nudging_obs,     only: aod_obs_init, aod_obs_update, aod_obs_target

  implicit none
  private

  public :: aod_nudging_readnl
  public :: aod_nudging_init
  public :: aod_nudging_timestep_init
  public :: aod_nudging_timestep_tend

  public :: aod_nudge_on
  public :: aod_nudge_active

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

  integer :: acc_nstep    = -1
  integer :: acc_ncol     = 0
  integer :: acc_nvalid   = 0
  integer :: acc_clamp_lo = 0
  integer :: acc_clamp_hi = 0

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

    call MPI_bcast(aod_nudge_on, 1, mpi_logical, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_nudge_on')
    call MPI_bcast(aod_obs_path, len(aod_obs_path), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_obs_path')
    call MPI_bcast(aod_obs_template, len(aod_obs_template), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_obs_template')
    call MPI_bcast(aod_beg_ymd, 1, mpi_integer, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_beg_ymd')
    call MPI_bcast(aod_end_ymd, 1, mpi_integer, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_end_ymd')
    call MPI_bcast(aod_times_per_day, 1, mpi_integer, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_times_per_day')
    call MPI_bcast(aod_ratio_min, 1, mpi_real8, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_ratio_min')
    call MPI_bcast(aod_ratio_max, 1, mpi_real8, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_ratio_max')
    call MPI_bcast(aod_eps, 1, mpi_real8, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_eps')
    call MPI_bcast(aod_aci_on, 1, mpi_logical, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_aci_on')
    call MPI_bcast(aod_diag_on, 1, mpi_logical, mstrid, mpicom, ierr)
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

  subroutine aod_nudging_init()
    if (.not. aod_nudge_on) return

    call aod_obs_init(aod_obs_path, aod_obs_template, aod_times_per_day)

    if (aod_diag_on) then
      call addfld('AODNDG_OBS',        horiz_only, 'I', '1', &
                  'AOD nudging: target (obs) AOD at 550nm')
      call addfld('AODNDG_MODEL_PRE',  horiz_only, 'I', '1', &
                  'AOD nudging: model AOD@550 before overwrite')
      call addfld('AODNDG_MODEL_POST', horiz_only, 'I', '1', &
                  'AOD nudging: model AOD@550 after overwrite')
      call addfld('AODNDG_RATIO',      horiz_only, 'I', '1', &
                  'AOD nudging: applied obs/model ratio')
      call addfld('AODNDG_MASK',       horiz_only, 'I', '1', &
                  'AOD nudging: obs valid mask (1=nudged,0=free)')
    end if

    if (masterproc) then
      write(iulog,*) 'AODNUDGE: init complete; aerosol modes = ', n_aero_modes()
    end if
  end subroutine aod_nudging_init

  subroutine flush_hitrate()
    integer :: loc(4), tot(4), ierr

    if (acc_ncol <= 0) return

    loc = (/ acc_ncol, acc_nvalid, acc_clamp_lo, acc_clamp_hi /)
    call MPI_reduce(loc, tot, 4, mpi_integer, mpi_sum, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun('aod_nudging: mpi_reduce hit-rate counters')

    if (masterproc .and. tot(1) > 0) then
      write(iulog,'(a,i9,a,f8.4,a,f8.4,a,f8.4,a,i10)') &
        'AODNUDGE hit-rate nstep=', acc_nstep,          &
        ' nudged_frac=',   real(tot(2), r8)/real(tot(1), r8), &
        ' clamp_lo_frac=', real(tot(3), r8)/real(tot(1), r8), &
        ' clamp_hi_frac=', real(tot(4), r8)/real(tot(1), r8), &
        ' ncol_global=',   tot(1)
    end if

    acc_ncol     = 0
    acc_nvalid   = 0
    acc_clamp_lo = 0
    acc_clamp_hi = 0
  end subroutine flush_hitrate

  subroutine aod_nudging_timestep_init(phys_state)
    type(physics_state), intent(in) :: phys_state(begchunk:endchunk)
    integer :: yr, mon, day, sec, ymd

    if (.not. aod_nudge_on) return

    call flush_hitrate()
    acc_nstep = get_nstep()

    call get_curr_date(yr, mon, day, sec)
    ymd = yr*10000 + mon*100 + day
    aod_nudge_active = (ymd >= aod_beg_ymd) .and. (ymd <= aod_end_ymd)

    if (aod_nudge_active) call aod_obs_update()
  end subroutine aod_nudging_timestep_init

  subroutine aod_nudging_timestep_tend(state, tend, pbuf, ztodt)
    use check_energy, only: check_energy_cam_chng

    type(physics_state),       intent(inout) :: state
    type(physics_tend),        intent(inout) :: tend
    type(physics_buffer_desc), pointer       :: pbuf(:)
    real(r8),                  intent(in)    :: ztodt

    integer  :: ncol, lchnk, nstep
    real(r8) :: aod_pre(pcols), aod_post(pcols)
    real(r8) :: target_aod(pcols), ratio(pcols)
    logical  :: valid(pcols)
    real(r8) :: maskr(pcols)
    real(r8) :: zero_flx(pcols)

    if (.not. (aod_nudge_on .and. aod_nudge_active)) return
    if (.not. radiation_do('sw')) return

    ncol     = state%ncol
    lchnk    = state%lchnk
    nstep    = get_nstep()
    zero_flx = 0._r8

    call model_aod550(state, pbuf, aod_pre)
    call aod_obs_target(lchnk, ncol, target_aod, valid)

    ratio = 1._r8
    ratio(:ncol) = compute_ratio(target_aod(:ncol), aod_pre(:ncol), valid(:ncol), &
                                 aod_eps, aod_ratio_min, aod_ratio_max)

    acc_ncol     = acc_ncol     + ncol
    acc_nvalid   = acc_nvalid   + count(valid(:ncol))
    acc_clamp_lo = acc_clamp_lo + count(valid(:ncol) .and. ratio(:ncol) == aod_ratio_min)
    acc_clamp_hi = acc_clamp_hi + count(valid(:ncol) .and. ratio(:ncol) == aod_ratio_max)

    call check_energy_cam_chng(state, tend, 'AODNUDGE_pre', nstep, ztodt, &
                               zero_flx, zero_flx, zero_flx, zero_flx)

    call apply_scaling(state, pbuf, ratio, aod_aci_on)
    call model_aod550(state, pbuf, aod_post)

    if (aod_diag_on) then
      maskr = 0._r8
      where (valid(:ncol)) maskr(:ncol) = 1._r8
      call outfld('AODNDG_OBS',        target_aod(:ncol), ncol, lchnk)
      call outfld('AODNDG_MODEL_PRE',  aod_pre(:ncol),    ncol, lchnk)
      call outfld('AODNDG_MODEL_POST', aod_post(:ncol),   ncol, lchnk)
      call outfld('AODNDG_RATIO',      ratio(:ncol),      ncol, lchnk)
      call outfld('AODNDG_MASK',       maskr(:ncol),      ncol, lchnk)
    end if

    call check_energy_cam_chng(state, tend, 'AODNUDGE', nstep, ztodt, &
                               zero_flx, zero_flx, zero_flx, zero_flx)
  end subroutine aod_nudging_timestep_tend

end module aod_nudging_intr
