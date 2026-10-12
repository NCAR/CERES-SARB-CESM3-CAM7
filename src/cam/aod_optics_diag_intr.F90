module aod_optics_diag_intr
!-----------------------------------------------------------------------------
! SP3 aerosol-optics diagnostic driver.
!-----------------------------------------------------------------------------
  use shr_kind_mod,   only: r8 => shr_kind_r8, cl => shr_kind_cl, cs => shr_kind_cs
  use cam_abortutils, only: endrun
  use cam_logfile,    only: iulog
  use spmd_utils,     only: masterproc, mstrid=>masterprocid, mpicom, &
                            mpi_success, mpi_integer, mpi_logical, mpi_character
  use ppgrid,         only: pcols, pver, begchunk, endchunk
  use physics_types,  only: physics_state
  use physics_buffer, only: physics_buffer_desc
  use time_manager,   only: get_curr_date, get_curr_time
  use filenames,      only: interpret_filename_spec
  use shr_sys_mod,    only: shr_sys_system
  use radconstants,   only: nswbands, nlwbands
  use aod_optics_kernel, only: remap_extensive, asym_from_scaweighted, &
                               clamp_layer, TAU_THRESH
  use aod_optics_bands,  only: aod_optics_bands_init, nsw_sarb, nlw_sarb, &
                               nbands_sarb, w_sw, w_lw, get_band_label, &
                               get_band_wavelength
  use aod_optics_tap,    only: sw_camband_optics, lw_camband_optics, LIST_CLIMATE
  use aod_optics_lut,    only: lfl_band_optics
  use aod_optics_lut_tables, only: aod_optics_lut_tables_init, lut_table_version
  use aod_optics_io,     only: write_band_file
  use aod_nudging_intr,  only: aod_nudge_active

  implicit none
  private

  public :: aod_optics_readnl
  public :: aod_optics_init
  public :: aod_optics_timestep_init
  public :: aod_optics_timestep_tend
  public :: aod_optics_on

  logical           :: aod_optics_on = .false.
  integer           :: aod_optics_interval_hours = 3
  character(len=cl) :: aod_optics_outdir = ''
  character(len=cl) :: aod_optics_template = 'AER_MAM4_{band}.%y%m%d.%s.nc'
  character(len=cl) :: aod_optics_band_file = ''
  character(len=cl) :: aod_optics_lw_table = ''
  character(len=cs) :: aod_optics_method = 'remap'
  character(len=cl) :: aod_optics_lut_file = ''

  logical :: initialized = .false.
  logical :: write_this_step = .false.
  integer :: output_count = 0

  real(r8), allocatable :: ext_buf(:,:,:,:)
  real(r8), allocatable :: sca_buf(:,:,:,:)
  real(r8), allocatable :: asym_buf(:,:,:,:)
  real(r8), allocatable :: col_buf(:,:,:)
  real(r8), allocatable :: delp_buf(:,:,:)

contains

  subroutine aod_optics_readnl(nlfile)
    use namelist_utils, only: find_group_name

    character(len=*), intent(in) :: nlfile

    integer :: unitn, ierr
    character(len=*), parameter :: prefix = 'aod_optics_readnl: '

    namelist /aod_optics_nl/ aod_optics_on, aod_optics_interval_hours, &
         aod_optics_outdir, aod_optics_template, aod_optics_band_file, aod_optics_lw_table, &
         aod_optics_method, aod_optics_lut_file

    if (masterproc) then
      open(newunit=unitn, file=trim(nlfile), status='old')
      call find_group_name(unitn, 'aod_optics_nl', status=ierr)
      if (ierr == 0) then
        read(unitn, aod_optics_nl, iostat=ierr)
        if (ierr /= 0) call endrun(prefix//'ERROR reading namelist')
      end if
      close(unitn)
    end if

    call MPI_bcast(aod_optics_on, 1, mpi_logical, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_optics_on')
    call MPI_bcast(aod_optics_interval_hours, 1, mpi_integer, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_optics_interval_hours')
    call MPI_bcast(aod_optics_outdir, len(aod_optics_outdir), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_optics_outdir')
    call MPI_bcast(aod_optics_template, len(aod_optics_template), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_optics_template')
    call MPI_bcast(aod_optics_band_file, len(aod_optics_band_file), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_optics_band_file')
    call MPI_bcast(aod_optics_lw_table, len(aod_optics_lw_table), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_optics_lw_table')
    call MPI_bcast(aod_optics_method, len(aod_optics_method), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_optics_method')
    call MPI_bcast(aod_optics_lut_file, len(aod_optics_lut_file), mpi_character, mstrid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun(prefix//'bcast aod_optics_lut_file')

    if (aod_optics_interval_hours <= 0) call endrun(prefix//'interval_hours must be positive')
    if (trim(aod_optics_method) /= 'remap' .and. trim(aod_optics_method) /= 'lut') then
      call endrun(prefix//'aod_optics_method must be remap or lut')
    end if

    if (masterproc .and. aod_optics_on) then
      write(iulog,*) 'AODOPTICS: ON outdir=', trim(aod_optics_outdir)
      write(iulog,*) 'AODOPTICS:    template=', trim(aod_optics_template), &
                     ' interval_hours=', aod_optics_interval_hours
      write(iulog,*) 'AODOPTICS:    band_file=', trim(aod_optics_band_file), &
                     ' lw_table=', trim(aod_optics_lw_table)
      write(iulog,*) 'AODOPTICS:    method=', trim(aod_optics_method), &
                     ' lut_file=', trim(aod_optics_lut_file)
    end if
  end subroutine aod_optics_readnl

  subroutine aod_optics_init()
    integer :: istat, ierr
    character(len=cl+16) :: cmd

    if (.not. aod_optics_on) return
    if (trim(aod_optics_outdir) == '') call endrun('aod_optics_init: aod_optics_outdir is required')

    if (masterproc) then
      cmd = 'mkdir -p '//trim(aod_optics_outdir)
      call shr_sys_system(trim(cmd), istat)
      if (istat /= 0) call endrun('aod_optics_init: mkdir failed for '//trim(aod_optics_outdir))
    end if
    call MPI_barrier(mpicom, ierr)
    if (ierr /= mpi_success) call endrun('aod_optics_init: MPI_barrier after mkdir')

    call aod_optics_bands_init(aod_optics_band_file, aod_optics_lw_table)
    if (trim(aod_optics_method) == 'lut') call aod_optics_lut_tables_init(aod_optics_lut_file)

    allocate(ext_buf(pcols,pver,begchunk:endchunk,nbands_sarb), stat=istat)
    if (istat /= 0) call endrun('aod_optics_init: allocate ext_buf failed')
    allocate(sca_buf(pcols,pver,begchunk:endchunk,nbands_sarb), stat=istat)
    if (istat /= 0) call endrun('aod_optics_init: allocate sca_buf failed')
    allocate(asym_buf(pcols,pver,begchunk:endchunk,nbands_sarb), stat=istat)
    if (istat /= 0) call endrun('aod_optics_init: allocate asym_buf failed')
    allocate(col_buf(pcols,begchunk:endchunk,nbands_sarb), stat=istat)
    if (istat /= 0) call endrun('aod_optics_init: allocate col_buf failed')
    allocate(delp_buf(pcols,pver,begchunk:endchunk), stat=istat)
    if (istat /= 0) call endrun('aod_optics_init: allocate delp_buf failed')

    ext_buf  = 0._r8
    sca_buf  = 0._r8
    asym_buf = 0._r8
    col_buf  = 0._r8
    delp_buf = 0._r8
    initialized = .true.
  end subroutine aod_optics_init

  subroutine aod_optics_timestep_init(phys_state)
    type(physics_state), intent(in) :: phys_state(begchunk:endchunk)

    integer :: days, seconds, interval

    if (.not. aod_optics_on) return
    if (.not. initialized) call endrun('aod_optics_timestep_init: diagnostic not initialized')

    call get_curr_time(days, seconds)
    interval = aod_optics_interval_hours * 3600
    write_this_step = (mod(days*86400 + seconds, interval) == 0)
    if (write_this_step) output_count = output_count + 1
  end subroutine aod_optics_timestep_init

  subroutine aod_optics_timestep_tend(state, pbuf)
    type(physics_state),       intent(in), target :: state
    type(physics_buffer_desc), pointer            :: pbuf(:)

    real(r8) :: ext_sw(pcols,pver,nswbands)
    real(r8) :: sca_sw(pcols,pver,nswbands)
    real(r8) :: scag_sw(pcols,pver,nswbands)
    real(r8) :: ext_lw(pcols,pver,nlwbands)
    real(r8) :: sca_lw(pcols,pver,nlwbands)
    real(r8) :: scag_lw(pcols,pver,nlwbands)
    real(r8) :: ext_lfl(pcols,pver,nbands_sarb)
    real(r8) :: sca_lfl(pcols,pver,nbands_sarb)
    real(r8) :: scag_lfl(pcols,pver,nbands_sarb)
    integer :: lchnk

    if (.not. aod_optics_on) return
    if (.not. write_this_step) return
    lchnk = state%lchnk
    if (trim(aod_optics_method) == 'lut') then
      call lfl_band_optics(state, pbuf, ext_lfl, sca_lfl, scag_lfl)
      call fill_lfl_chunk_buffers(state, ext_lfl, sca_lfl, scag_lfl)
    else
      call sw_camband_optics(state, pbuf, ext_sw, sca_sw, scag_sw)
      call lw_camband_optics(state, pbuf, ext_lw, sca_lw, scag_lw)
      call fill_chunk_buffers(state, ext_sw, sca_sw, scag_sw, ext_lw, sca_lw, scag_lw)
    end if

    if (lchnk == endchunk) call flush_outputs()
  end subroutine aod_optics_timestep_tend

  subroutine fill_chunk_buffers(state, ext_sw, sca_sw, scag_sw, ext_lw, sca_lw, scag_lw)
    type(physics_state), intent(in) :: state
    real(r8), intent(in) :: ext_sw(pcols,pver,nswbands), sca_sw(pcols,pver,nswbands), scag_sw(pcols,pver,nswbands)
    real(r8), intent(in) :: ext_lw(pcols,pver,nlwbands), sca_lw(pcols,pver,nlwbands), scag_lw(pcols,pver,nlwbands)

    integer :: i, k, s, lchnk, ncol, iband
    real(r8) :: ext_dst(nsw_sarb), sca_dst(nsw_sarb), scag_dst(nsw_sarb)
    real(r8) :: ext_ldst(nlw_sarb), sca_ldst(nlw_sarb), scag_ldst(nlw_sarb)

    lchnk = state%lchnk
    ncol  = state%ncol
    delp_buf(:,:,lchnk) = 0._r8
    delp_buf(:ncol,:,lchnk) = state%pdel(:ncol,:)

    do k = 1, pver
      do i = 1, ncol
        ext_dst  = remap_extensive(nswbands, nsw_sarb, w_sw, ext_sw(i,k,:))
        sca_dst  = remap_extensive(nswbands, nsw_sarb, w_sw, sca_sw(i,k,:))
        scag_dst = remap_extensive(nswbands, nsw_sarb, w_sw, scag_sw(i,k,:))
        do s = 1, nsw_sarb
          iband = s
          ext_buf(i,k,lchnk,iband)  = ext_dst(s)
          sca_buf(i,k,lchnk,iband)  = sca_dst(s)
          asym_buf(i,k,lchnk,iband) = asym_from_scaweighted(scag_dst(s), sca_dst(s), TAU_THRESH)
          call enforce_layer(ext_buf(i,k,lchnk,iband), sca_buf(i,k,lchnk,iband), asym_buf(i,k,lchnk,iband))
        end do

        ext_ldst  = remap_extensive(nlwbands, nlw_sarb, w_lw, ext_lw(i,k,:))
        sca_ldst  = remap_extensive(nlwbands, nlw_sarb, w_lw, sca_lw(i,k,:))
        scag_ldst = remap_extensive(nlwbands, nlw_sarb, w_lw, scag_lw(i,k,:))
        do s = 1, nlw_sarb
          iband = nsw_sarb + s
          ext_buf(i,k,lchnk,iband)  = ext_ldst(s)
          sca_buf(i,k,lchnk,iband)  = sca_ldst(s)
          asym_buf(i,k,lchnk,iband) = asym_from_scaweighted(scag_ldst(s), sca_ldst(s), TAU_THRESH)
          call enforce_layer(ext_buf(i,k,lchnk,iband), sca_buf(i,k,lchnk,iband), asym_buf(i,k,lchnk,iband))
        end do
      end do
    end do

    if (ncol < pcols) then
      ext_buf(ncol+1:pcols,:,lchnk,:)  = 0._r8
      sca_buf(ncol+1:pcols,:,lchnk,:)  = 0._r8
      asym_buf(ncol+1:pcols,:,lchnk,:) = 0._r8
      delp_buf(ncol+1:pcols,:,lchnk)   = 0._r8
    end if

    do iband = 1, nbands_sarb
      do i = 1, ncol
        col_buf(i,lchnk,iband) = sum(ext_buf(i,:,lchnk,iband))
      end do
      if (ncol < pcols) col_buf(ncol+1:pcols,lchnk,iband) = 0._r8
    end do
  end subroutine fill_chunk_buffers

  subroutine fill_lfl_chunk_buffers(state, ext_lfl, sca_lfl, scag_lfl)
    type(physics_state), intent(in) :: state
    real(r8), intent(in) :: ext_lfl(pcols,pver,nbands_sarb)
    real(r8), intent(in) :: sca_lfl(pcols,pver,nbands_sarb)
    real(r8), intent(in) :: scag_lfl(pcols,pver,nbands_sarb)

    integer :: i, k, lchnk, ncol, iband

    lchnk = state%lchnk
    ncol  = state%ncol
    delp_buf(:,:,lchnk) = 0._r8
    delp_buf(:ncol,:,lchnk) = state%pdel(:ncol,:)

    do iband = 1, nbands_sarb
      do k = 1, pver
        do i = 1, ncol
          ext_buf(i,k,lchnk,iband) = ext_lfl(i,k,iband)
          sca_buf(i,k,lchnk,iband) = sca_lfl(i,k,iband)
          asym_buf(i,k,lchnk,iband) = asym_from_scaweighted(scag_lfl(i,k,iband), sca_lfl(i,k,iband), TAU_THRESH)
          call enforce_layer(ext_buf(i,k,lchnk,iband), sca_buf(i,k,lchnk,iband), asym_buf(i,k,lchnk,iband))
        end do
      end do
      if (ncol < pcols) then
        ext_buf(ncol+1:pcols,:,lchnk,iband) = 0._r8
        sca_buf(ncol+1:pcols,:,lchnk,iband) = 0._r8
        asym_buf(ncol+1:pcols,:,lchnk,iband) = 0._r8
      end if
      do i = 1, ncol
        col_buf(i,lchnk,iband) = sum(ext_buf(i,:,lchnk,iband))
      end do
      if (ncol < pcols) col_buf(ncol+1:pcols,lchnk,iband) = 0._r8
    end do
    if (ncol < pcols) delp_buf(ncol+1:pcols,:,lchnk) = 0._r8
  end subroutine fill_lfl_chunk_buffers

  subroutine enforce_layer(ext, sca, asym)
    use, intrinsic :: ieee_arithmetic, only: ieee_is_finite

    real(r8), intent(inout) :: ext, sca, asym

    if (.not. ieee_is_finite(ext))  call endrun('aod_optics_diag: non-finite extinction')
    if (.not. ieee_is_finite(sca))  call endrun('aod_optics_diag: non-finite scattering')
    if (.not. ieee_is_finite(asym)) call endrun('aod_optics_diag: non-finite asymmetry')
    call clamp_layer(ext, sca, asym)
  end subroutine enforce_layer

  subroutine flush_outputs()
    integer :: iband, yr, mon, day, tod
    character(len=8)  :: label
    character(len=8)  :: upper_label
    character(len=cl) :: spec
    character(len=cl) :: fname

    call get_curr_date(yr, mon, day, tod)

    do iband = 1, nbands_sarb
      call get_band_label(iband, label)
      upper_label = label
      call uppercase(upper_label)
      spec = replace_band_token(aod_optics_template, trim(upper_label))
      fname = trim(aod_optics_outdir)//'/'//trim(interpret_filename_spec(trim(spec), &
              yr_spec=yr, mon_spec=mon, day_spec=day, sec_spec=tod))
      call write_band_file(trim(fname), trim(label), get_band_wavelength(iband), &
                           'MAM4', trim(aod_optics_method), trim(aod_optics_lut_file), &
                           trim(lut_table_version), aod_nudge_active, LIST_CLIMATE, ext_buf(:,:,:,iband), &
                           sca_buf(:,:,:,iband), asym_buf(:,:,:,iband), delp_buf, &
                           col_buf(:,:,iband))
    end do
  end subroutine flush_outputs

  function replace_band_token(template, band) result(out)
    character(len=*), intent(in) :: template
    character(len=*), intent(in) :: band
    character(len=cl) :: out

    integer :: p

    out = trim(template)
    p = index(out, '{band}')
    if (p > 0) then
      out = out(:p-1)//trim(band)//out(p+6:)
    end if
  end function replace_band_token

  subroutine uppercase(text)
    character(len=*), intent(inout) :: text

    integer :: i, code

    do i = 1, len_trim(text)
      code = iachar(text(i:i))
      if (code >= iachar('a') .and. code <= iachar('z')) then
        text(i:i) = achar(code - 32)
      end if
    end do
  end subroutine uppercase

end module aod_optics_diag_intr
