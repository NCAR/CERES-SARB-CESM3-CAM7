module aod_nudging_obs
!-----------------------------------------------------------------------------
! Contract-file IO for AOD nudging.
!   - filename from template+date via interpret_filename_spec (%y%m%d.%s)
!   - read aod_weighted_mean(lat,lon) with infld (scatter to chunks)
!   - read each file's scalar CF time (window center) for interpolation
!   - require exact f09 grid identity; no in-model interpolation
!   - hold two bracketing snapshots and expose per-chunk target AOD + mask
!-----------------------------------------------------------------------------
  use shr_kind_mod,       only: r8 => shr_kind_r8, cl => shr_kind_cl, cs => shr_kind_cs
  use ppgrid,             only: pcols, begchunk, endchunk
  use cam_abortutils,     only: endrun
  use cam_logfile,        only: iulog
  use spmd_utils,         only: masterproc, mstrid=>masterprocid, mpicom, &
                                mpi_success, mpi_logical
  use time_manager,       only: get_curr_time, get_curr_date
  use filenames,          only: interpret_filename_spec
  use aod_nudging_kernel, only: interp_weight, combine_snapshots, AOD_FILL

  implicit none
  private

  public :: aod_obs_init
  public :: aod_obs_update
  public :: aod_obs_target

  integer,  parameter :: NLAT_F09 = 192
  integer,  parameter :: NLON_F09 = 288
  real(r8), parameter :: GRID_TOL = 1.e-3_r8
  real(r8), parameter :: TCEN_NONE = -1.e30_r8

  character(len=cl) :: obs_path = ''
  character(len=cs) :: obs_template = ''
  integer           :: times_per_day = 8
  real(r8)          :: win_sec  = 10800._r8
  real(r8)          :: half_sec = 5400._r8

  real(r8), allocatable :: obs_curr(:,:)
  real(r8), allocatable :: obs_next(:,:)
  logical,  allocatable :: vld_curr(:,:)
  logical,  allocatable :: vld_next(:,:)

  integer  :: k_curr = -huge(1)
  real(r8) :: cm_curr = 0._r8
  real(r8) :: tcen_curr = TCEN_NONE
  real(r8) :: tcen_next = TCEN_NONE
  real(r8) :: weight = 0._r8

contains

  subroutine aod_obs_init(path_in, template_in, times_per_day_in)
    character(len=*), intent(in) :: path_in
    character(len=*), intent(in) :: template_in
    integer,          intent(in) :: times_per_day_in
    integer :: istat

    obs_path      = trim(path_in)
    obs_template  = trim(template_in)
    times_per_day = times_per_day_in
    win_sec       = 86400._r8 / real(times_per_day, r8)
    half_sec      = 0.5_r8 * win_sec

    allocate(obs_curr(pcols, begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_obs_init: allocate obs_curr failed')
    allocate(obs_next(pcols, begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_obs_init: allocate obs_next failed')
    allocate(vld_curr(pcols, begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_obs_init: allocate vld_curr failed')
    allocate(vld_next(pcols, begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_obs_init: allocate vld_next failed')

    obs_curr  = AOD_FILL
    obs_next  = AOD_FILL
    vld_curr  = .false.
    vld_next  = .false.
    k_curr    = -huge(1)
    tcen_curr = TCEN_NONE
    tcen_next = TCEN_NONE
    weight    = 0._r8
  end subroutine aod_obs_init

  subroutine aod_obs_update()
    integer  :: days, secs, k
    real(r8) :: t_now

    call get_curr_time(days, secs)
    t_now = real(days, r8)*86400._r8 + real(secs, r8)

    k       = floor((t_now - half_sec) / win_sec)
    cm_curr = real(k, r8)*win_sec + half_sec

    if (k == k_curr) then
      call set_weight(t_now)
      return
    end if

    if (k == k_curr + 1) then
      obs_curr = obs_next
      vld_curr = vld_next
      tcen_curr = tcen_next
      call load_window(k+1, obs_next, vld_next, tcen_next)
    else
      call load_window(k,   obs_curr, vld_curr, tcen_curr)
      call load_window(k+1, obs_next, vld_next, tcen_next)
    end if
    k_curr = k
    call set_weight(t_now)
  end subroutine aod_obs_update

  subroutine set_weight(t_now)
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
    use cam_pio_utils,    only: cam_pio_openfile
    use pio,              only: file_desc_t, var_desc_t, pio_closefile,            &
                                pio_seterrorhandling, PIO_BCAST_ERROR, PIO_NOERR,  &
                                pio_inq_dimid, pio_inq_dimlen, pio_inq_varid,      &
                                pio_get_var, PIO_NOWRITE
    use ncdio_atm,        only: infld
    use cam_grid_support, only: cam_grid_id, cam_grid_get_dim_names,               &
                                cam_grid_dimensions, DLEN=>max_hcoordname_len

    integer,  intent(in)  :: k
    real(r8), intent(out) :: fld(:,:)
    logical,  intent(out) :: vld(:,:)
    real(r8), intent(out) :: center

    integer             :: ws_elapsed, days, secs, offset
    integer             :: yr, mon, day, tod
    character(len=cl)   :: fname
    logical             :: present_file, found
    type(file_desc_t)   :: fileID
    type(var_desc_t)    :: time_vid, latvid, lonvid
    integer             :: grid_id, err_handling, ierr, dimid
    integer             :: nlat_file, nlon_file, griddims(2)
    integer             :: jj
    character(len=DLEN) :: dim1name, dim2name
    real(r8)            :: tcen
    real(r8)            :: latf(NLAT_F09), lonf(NLON_F09)
    real(r8)            :: late, lone

    fld    = AOD_FILL
    vld    = .false.
    center = TCEN_NONE

    ws_elapsed = nint(real(k, r8)*win_sec)
    call get_curr_time(days, secs)
    offset = ws_elapsed - (days*86400 + secs)
    call get_curr_date(yr, mon, day, tod, offset=offset)

    fname = trim(obs_path)//trim(interpret_filename_spec(obs_template, &
            yr_spec=yr, mon_spec=mon, day_spec=day, sec_spec=tod))

    if (masterproc) inquire(file=trim(fname), exist=present_file)
    call MPI_bcast(present_file, 1, mpi_logical, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun('aod_obs::load_window: mpi_bcast present_file')

    if (.not. present_file) then
      if (masterproc) write(iulog,*) 'AODNUDGE: obs file absent, running free: ', trim(fname)
      return
    end if

    call cam_pio_openfile(fileID, trim(fname), PIO_NOWRITE)
    call pio_seterrorhandling(fileID, PIO_BCAST_ERROR, oldmethod=err_handling)
    if (masterproc) write(iulog,*) 'AODNUDGE: reading ', trim(fname)

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
      call endrun('aod_obs::load_window: obs grid /= CAM f09 grid')
    end if

    ierr = pio_inq_varid(fileID, 'lat', latvid)
    if (ierr == PIO_NOERR) ierr = pio_get_var(fileID, latvid, latf)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: cannot read lat coord in '//trim(fname))
    ierr = pio_inq_varid(fileID, 'lon', lonvid)
    if (ierr == PIO_NOERR) ierr = pio_get_var(fileID, lonvid, lonf)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: cannot read lon coord in '//trim(fname))

    do jj = 1, NLAT_F09
      late = -90._r8 + real(jj-1, r8)*180._r8/real(NLAT_F09-1, r8)
      if (abs(latf(jj) - late) > GRID_TOL) call endrun( &
           'aod_obs::load_window: obs lat centers /= CAM f09 grid')
    end do
    do jj = 1, NLON_F09
      lone = real(jj-1, r8)*360._r8/real(NLON_F09, r8)
      if (abs(lonf(jj) - lone) > GRID_TOL) call endrun( &
           'aod_obs::load_window: obs lon centers /= CAM f09 grid')
    end do

    grid_id = cam_grid_id('physgrid')
    call cam_grid_get_dim_names(grid_id, dim1name, dim2name)

    call infld('aod_weighted_mean', fileID, dim1name, dim2name, &
               1, pcols, begchunk, endchunk, fld, found, &
               gridname='physgrid', timelevel=1)
    if (.not. found) then
      call endrun('aod_obs::load_window: variable aod_weighted_mean missing in '//trim(fname))
    end if

    ierr = pio_inq_varid(fileID, 'time', time_vid)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: scalar time var missing in '//trim(fname))
    ierr = pio_get_var(fileID, time_vid, tcen)
    if (ierr /= PIO_NOERR) call endrun('aod_obs::load_window: cannot read scalar time in '//trim(fname))
    center = tcen

    vld = (fld > -900._r8)

    call pio_seterrorhandling(fileID, err_handling)
    call pio_closefile(fileID)
  end subroutine load_window

  subroutine aod_obs_target(lchnk, ncol, target_aod, valid)
    integer,  intent(in)  :: lchnk, ncol
    real(r8), intent(out) :: target_aod(:)
    logical,  intent(out) :: valid(:)

    target_aod = AOD_FILL
    valid      = .false.
    call combine_snapshots(obs_curr(:ncol,lchnk), obs_next(:ncol,lchnk), &
                           vld_curr(:ncol,lchnk), vld_next(:ncol,lchnk), &
                           weight, target_aod(:ncol), valid(:ncol))
  end subroutine aod_obs_target

end module aod_nudging_obs
