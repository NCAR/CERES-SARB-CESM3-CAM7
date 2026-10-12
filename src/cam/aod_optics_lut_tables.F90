module aod_optics_lut_tables
!-----------------------------------------------------------------------------
! SP3 LFL-native aerosol-optics LUT table storage and PIO reader.
!-----------------------------------------------------------------------------
  use shr_kind_mod,   only: r8 => shr_kind_r8, cl => shr_kind_cl
  use cam_abortutils, only: endrun
  use cam_logfile,    only: iulog
  use spmd_utils,     only: masterproc
  use rad_constituents, only: rad_cnst_get_info
  use aod_optics_bands, only: nsw_sarb, nlw_sarb, LFL_SW_EDGES_UM, LFL_LW_EDGES_UM

  implicit none
  private

  public :: aod_optics_lut_tables_init
  public :: lut_tables_ready
  public :: lut_table_file
  public :: lut_table_version
  public :: spectype_index
  public :: ncoef_lut
  public :: nmode_lut
  public :: nre_lut
  public :: nim_lut
  public :: sigmag_lut
  public :: extpsw_lut
  public :: abspsw_lut
  public :: asmpsw_lut
  public :: extplw_lut
  public :: absplw_lut
  public :: asmplw_lut
  public :: refrtabsw_lut
  public :: refitabsw_lut
  public :: refrtablw_lut
  public :: refitablw_lut
  public :: refre_spectype_sw_lut
  public :: refim_spectype_sw_lut
  public :: refre_spectype_lw_lut
  public :: refim_spectype_lw_lut

  integer, parameter :: NSPECTYPE_LUT = 7
  real(r8), parameter :: EDGE_TOL = 1.e-10_r8
  character(len=*), parameter :: EXPECTED_MODE_ORDER = 'a1,a2,a3,a4'
  character(len=8), parameter :: SPECTYPE_NAMES(NSPECTYPE_LUT) = &
       [ character(len=8) :: 'BC', 'POM', 'SOA', 'SU', 'DU', 'SS', 'WAT' ]

  logical :: lut_tables_ready = .false.
  character(len=cl) :: lut_table_file = ''
  character(len=cl) :: lut_table_version = 'unknown'

  integer :: ncoef_lut = 0
  integer :: nmode_lut = 0
  integer :: nre_lut = 0
  integer :: nim_lut = 0

  real(r8), allocatable :: sigmag_lut(:)
  real(r8), allocatable :: extpsw_lut(:,:,:,:,:)
  real(r8), allocatable :: abspsw_lut(:,:,:,:,:)
  real(r8), allocatable :: asmpsw_lut(:,:,:,:,:)
  real(r8), allocatable :: extplw_lut(:,:,:,:,:)
  real(r8), allocatable :: absplw_lut(:,:,:,:,:)
  real(r8), allocatable :: asmplw_lut(:,:,:,:,:)
  real(r8), allocatable :: refrtabsw_lut(:,:,:)
  real(r8), allocatable :: refitabsw_lut(:,:,:)
  real(r8), allocatable :: refrtablw_lut(:,:,:)
  real(r8), allocatable :: refitablw_lut(:,:,:)
  real(r8), allocatable :: refre_spectype_sw_lut(:,:)
  real(r8), allocatable :: refim_spectype_sw_lut(:,:)
  real(r8), allocatable :: refre_spectype_lw_lut(:,:)
  real(r8), allocatable :: refim_spectype_lw_lut(:,:)

contains

  subroutine aod_optics_lut_tables_init(fname)
    use cam_pio_utils, only: cam_pio_openfile, cam_pio_closefile
    use pio, only: file_desc_t, pio_nowrite

    character(len=*), intent(in) :: fname

    type(file_desc_t) :: fileid
    character(len=cl) :: mode_order

    if (trim(fname) == '') call endrun('aod_optics_lut_tables_init: aod_optics_lut_file is required')
    if (lut_tables_ready) return

    lut_table_file = trim(fname)
    call cam_pio_openfile(fileid, trim(fname), pio_nowrite)
    call read_dimensions(fileid, trim(fname))
    call allocate_tables()
    call read_table_vars(fileid, trim(fname))
    call validate_lfl_edges(fileid, trim(fname))
    call read_required_att(fileid, 'mode_order', mode_order)
    if (trim(mode_order) /= EXPECTED_MODE_ORDER) then
      call endrun('aod_optics_lut_tables: LUT mode_order must be '//EXPECTED_MODE_ORDER//' in '//trim(fname))
    end if
    call read_optional_att(fileid, 'table_version', lut_table_version)
    call cam_pio_closefile(fileid)

    lut_tables_ready = .true.
    if (masterproc) then
      write(iulog,*) 'AODOPTICS: LUT table=', trim(lut_table_file)
      write(iulog,*) 'AODOPTICS: LUT table_version=', trim(lut_table_version), &
                     ' ncoef=', ncoef_lut, ' nmode=', nmode_lut
    end if
  end subroutine aod_optics_lut_tables_init

  subroutine read_dimensions(fileid, fname)
    use pio, only: file_desc_t, pio_inq_dimid, pio_inq_dimlen

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: fname
    integer :: nsw_file, nlw_file, nspectype_file
    integer :: nsw_edge_file, nlw_edge_file, nmodes_cam

    call read_dim(fileid, 'sw_band', nsw_file, fname)
    call read_dim(fileid, 'lw_band', nlw_file, fname)
    call read_dim(fileid, 'lfl_sw_edge', nsw_edge_file, fname)
    call read_dim(fileid, 'lfl_lw_edge', nlw_edge_file, fname)
    call read_dim(fileid, 'mode', nmode_lut, fname)
    call read_dim(fileid, 'refindex_real', nre_lut, fname)
    call read_dim(fileid, 'refindex_im', nim_lut, fname)
    call read_dim(fileid, 'coef_number', ncoef_lut, fname)
    call read_dim(fileid, 'spectype', nspectype_file, fname)
    call rad_cnst_get_info(0, nmodes=nmodes_cam)
    if (nsw_file /= nsw_sarb) call endrun('aod_optics_lut_tables: sw_band count mismatch in '//trim(fname))
    if (nlw_file /= nlw_sarb) call endrun('aod_optics_lut_tables: lw_band count mismatch in '//trim(fname))
    if (nsw_edge_file /= nsw_sarb+1) call endrun('aod_optics_lut_tables: lfl_sw_edge count mismatch in '//trim(fname))
    if (nlw_edge_file /= nlw_sarb+1) call endrun('aod_optics_lut_tables: lfl_lw_edge count mismatch in '//trim(fname))
    if (nmode_lut /= nmodes_cam) call endrun('aod_optics_lut_tables: LUT mode count does not match CAM')
    if (nspectype_file /= NSPECTYPE_LUT) call endrun('aod_optics_lut_tables: spectype count mismatch')
  end subroutine read_dimensions

  subroutine read_dim(fileid, name, value, fname)
    use pio, only: file_desc_t, pio_inq_dimid, pio_inq_dimlen, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: name, fname
    integer, intent(out) :: value
    integer :: did, ierr

    ierr = pio_inq_dimid(fileid, trim(name), did)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: missing dimension '//trim(name)//' in '//trim(fname))
    ierr = pio_inq_dimlen(fileid, did, value)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: cannot read dimension '//trim(name))
  end subroutine read_dim

  subroutine allocate_tables()
    integer :: istat

    allocate(sigmag_lut(nmode_lut), stat=istat)
    if (istat /= 0) call endrun('aod_optics_lut_tables: allocate sigmag_lut failed')
    allocate(extpsw_lut(ncoef_lut,nre_lut,nim_lut,nsw_sarb,nmode_lut), &
             abspsw_lut(ncoef_lut,nre_lut,nim_lut,nsw_sarb,nmode_lut), &
             asmpsw_lut(ncoef_lut,nre_lut,nim_lut,nsw_sarb,nmode_lut), &
             extplw_lut(ncoef_lut,nre_lut,nim_lut,nlw_sarb,nmode_lut), &
             absplw_lut(ncoef_lut,nre_lut,nim_lut,nlw_sarb,nmode_lut), &
             asmplw_lut(ncoef_lut,nre_lut,nim_lut,nlw_sarb,nmode_lut), stat=istat)
    if (istat /= 0) call endrun('aod_optics_lut_tables: allocate coefficient tables failed')
    allocate(refrtabsw_lut(nre_lut,nsw_sarb,nmode_lut), &
             refitabsw_lut(nim_lut,nsw_sarb,nmode_lut), &
             refrtablw_lut(nre_lut,nlw_sarb,nmode_lut), &
             refitablw_lut(nim_lut,nlw_sarb,nmode_lut), stat=istat)
    if (istat /= 0) call endrun('aod_optics_lut_tables: allocate refindex axes failed')
    allocate(refre_spectype_sw_lut(nsw_sarb,NSPECTYPE_LUT), &
             refim_spectype_sw_lut(nsw_sarb,NSPECTYPE_LUT), &
             refre_spectype_lw_lut(nlw_sarb,NSPECTYPE_LUT), &
             refim_spectype_lw_lut(nlw_sarb,NSPECTYPE_LUT), stat=istat)
    if (istat /= 0) call endrun('aod_optics_lut_tables: allocate spectype refs failed')
  end subroutine allocate_tables

  subroutine read_table_vars(fileid, fname)
    use pio, only: file_desc_t, var_desc_t, pio_inq_varid, pio_get_var, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: fname

    call read_coeff_var(fileid, 'extpsw', extpsw_lut, nsw_sarb, fname)
    call read_coeff_var(fileid, 'abspsw', abspsw_lut, nsw_sarb, fname)
    call read_coeff_var(fileid, 'asmpsw', asmpsw_lut, nsw_sarb, fname)
    call read_coeff_var(fileid, 'extplw', extplw_lut, nlw_sarb, fname)
    call read_coeff_var(fileid, 'absplw', absplw_lut, nlw_sarb, fname)
    call read_coeff_var(fileid, 'asmplw', asmplw_lut, nlw_sarb, fname)
    call read_axis_real(fileid, 'refindex_real_sw', refrtabsw_lut, nre_lut, nsw_sarb, fname)
    call read_axis_real(fileid, 'refindex_im_sw', refitabsw_lut, nim_lut, nsw_sarb, fname)
    call read_axis_real(fileid, 'refindex_real_lw', refrtablw_lut, nre_lut, nlw_sarb, fname)
    call read_axis_real(fileid, 'refindex_im_lw', refitablw_lut, nim_lut, nlw_sarb, fname)
    call read_1d_real(fileid, 'sigmag', sigmag_lut, fname)
    call read_spectype_real(fileid, 'refindex_real_spectype_sw', refre_spectype_sw_lut, nsw_sarb, fname)
    call read_spectype_real(fileid, 'refindex_im_spectype_sw', refim_spectype_sw_lut, nsw_sarb, fname)
    call read_spectype_real(fileid, 'refindex_real_spectype_lw', refre_spectype_lw_lut, nlw_sarb, fname)
    call read_spectype_real(fileid, 'refindex_im_spectype_lw', refim_spectype_lw_lut, nlw_sarb, fname)
  end subroutine read_table_vars

  subroutine read_coeff_var(fileid, varname, target, nband, fname)
    use pio, only: file_desc_t, var_desc_t, pio_inq_varid, pio_get_var, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: varname, fname
    integer, intent(in) :: nband
    real(r8), intent(out) :: target(ncoef_lut,nre_lut,nim_lut,nband,nmode_lut)

    type(var_desc_t) :: vid
    real(r8), allocatable :: raw(:,:,:,:,:)
    integer :: ierr, iband, imode

    ierr = pio_inq_varid(fileid, trim(varname), vid)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: missing '//trim(varname)//' in '//trim(fname))
    allocate(raw(ncoef_lut,nre_lut,nim_lut,nmode_lut,nband))
    ierr = pio_get_var(fileid, vid, raw)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: cannot read '//trim(varname))
    do imode = 1, nmode_lut
      do iband = 1, nband
        target(:,:,:,iband,imode) = raw(:,:,:,imode,iband)
      end do
    end do
    deallocate(raw)
  end subroutine read_coeff_var

  subroutine read_axis_real(fileid, varname, target, naxis, nband, fname)
    use pio, only: file_desc_t, var_desc_t, pio_inq_varid, pio_get_var, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: varname, fname
    integer, intent(in) :: naxis, nband
    real(r8), intent(out) :: target(naxis,nband,nmode_lut)

    type(var_desc_t) :: vid
    real(r8), allocatable :: raw(:,:,:)
    integer :: ierr, iband, imode

    ierr = pio_inq_varid(fileid, trim(varname), vid)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: missing '//trim(varname)//' in '//trim(fname))
    allocate(raw(naxis,nmode_lut,nband))
    ierr = pio_get_var(fileid, vid, raw)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: cannot read '//trim(varname))
    do imode = 1, nmode_lut
      do iband = 1, nband
        target(:,iband,imode) = raw(:,imode,iband)
      end do
    end do
    deallocate(raw)
  end subroutine read_axis_real

  subroutine read_spectype_real(fileid, varname, target, nband, fname)
    use pio, only: file_desc_t, var_desc_t, pio_inq_varid, pio_get_var, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: varname, fname
    integer, intent(in) :: nband
    real(r8), intent(out) :: target(nband,NSPECTYPE_LUT)

    type(var_desc_t) :: vid
    integer :: ierr

    ierr = pio_inq_varid(fileid, trim(varname), vid)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: missing '//trim(varname)//' in '//trim(fname))
    ierr = pio_get_var(fileid, vid, target)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: cannot read '//trim(varname))
  end subroutine read_spectype_real

  subroutine read_1d_real(fileid, varname, target, fname)
    use pio, only: file_desc_t, var_desc_t, pio_inq_varid, pio_get_var, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: varname, fname
    real(r8), intent(out) :: target(:)
    type(var_desc_t) :: vid
    integer :: ierr

    ierr = pio_inq_varid(fileid, trim(varname), vid)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: missing '//trim(varname)//' in '//trim(fname))
    ierr = pio_get_var(fileid, vid, target)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: cannot read '//trim(varname))
  end subroutine read_1d_real

  subroutine validate_lfl_edges(fileid, fname)
    use pio, only: file_desc_t

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: fname

    real(r8) :: sw_edges(size(LFL_SW_EDGES_UM))
    real(r8) :: lw_edges(size(LFL_LW_EDGES_UM))

    call read_1d_real(fileid, 'lfl_sw_edges_um', sw_edges, fname)
    call read_1d_real(fileid, 'lfl_lw_edges_um', lw_edges, fname)
    if (maxval(abs(sw_edges - LFL_SW_EDGES_UM)) > EDGE_TOL) then
      call endrun('aod_optics_lut_tables: LUT SW edges do not match built-in SARB/LFL edges in '//trim(fname))
    end if
    if (maxval(abs(lw_edges - LFL_LW_EDGES_UM)) > EDGE_TOL) then
      call endrun('aod_optics_lut_tables: LUT LW edges do not match built-in SARB/LFL edges in '//trim(fname))
    end if
  end subroutine validate_lfl_edges

  subroutine read_required_att(fileid, name, value)
    use pio, only: file_desc_t, pio_get_att, pio_global, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: name
    character(len=*), intent(out) :: value
    integer :: ierr

    ierr = pio_get_att(fileid, pio_global, trim(name), value)
    if (ierr /= pio_noerr) call endrun('aod_optics_lut_tables: missing required global attribute '//trim(name))
  end subroutine read_required_att

  subroutine read_optional_att(fileid, name, value)
    use pio, only: file_desc_t, pio_get_att, pio_global, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: name
    character(len=*), intent(out) :: value
    integer :: ierr

    value = 'unknown'
    ierr = pio_get_att(fileid, pio_global, trim(name), value)
    if (ierr /= pio_noerr) value = 'unknown'
  end subroutine read_optional_att

  integer function spectype_index(spectype) result(index)
    character(len=*), intent(in) :: spectype
    character(len=32) :: key

    key = adjustl(spectype)
    call uppercase(key)
    select case (trim(key))
    case ('BC', 'BLACK-C')
      index = 1
    case ('POM', 'P-ORGANIC')
      index = 2
    case ('SOA', 'S-ORGANIC')
      index = 3
    case ('SU', 'SULFATE')
      index = 4
    case ('DU', 'DUST')
      index = 5
    case ('SS', 'SEASALT')
      index = 6
    case ('WAT', 'WATER')
      index = 7
    case default
      index = 0
    end select
  end function spectype_index

  subroutine uppercase(text)
    character(len=*), intent(inout) :: text
    integer :: i, code

    do i = 1, len_trim(text)
      code = iachar(text(i:i))
      if (code >= iachar('a') .and. code <= iachar('z')) text(i:i) = achar(code - 32)
    end do
  end subroutine uppercase

end module aod_optics_lut_tables
