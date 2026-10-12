module aod_optics_bands
!-----------------------------------------------------------------------------
! SP3 spectral-band inputs.
!   - Use built-in SARB/LFL SW and LW wavelength edges, or read a NetCDF override.
!   - Build CAM RRTMGP band -> SARB/LFL band overlap weights in wavenumber.
!   - Read prescribed CAM-LW-band omega/g values, or default to omega=0.
!-----------------------------------------------------------------------------
  use shr_kind_mod,   only: r8 => shr_kind_r8
  use cam_abortutils, only: endrun
  use cam_logfile,    only: iulog
  use spmd_utils,     only: masterproc
  use radconstants,   only: nswbands, nlwbands, get_sw_spectral_boundaries, &
                            get_lw_spectral_boundaries
  use aod_optics_kernel, only: overlap_weights, OMEGA_CAP

  implicit none
  private

  public :: aod_optics_bands_init
  public :: get_band_label
  public :: get_band_wavelength
  public :: is_sw_band
  public :: nsw_sarb
  public :: nlw_sarb
  public :: nbands_sarb
  public :: nbins_lw
  public :: w_sw
  public :: w_lw
  public :: sarb_sw_mid
  public :: sarb_lw_mid
  public :: omega_lw
  public :: g_lw
  public :: LFL_SW_EDGES_UM
  public :: LFL_LW_EDGES_UM

  real(r8), parameter :: LFL_SW_EDGES_UM(15) = (/ &
       0.1754_r8, 0.3225_r8, 0.3575_r8, 0.4375_r8, 0.4975_r8, &
       0.5950_r8, 0.6896_r8, 0.7940_r8, 0.8890_r8, 1.0420_r8, &
       1.4100_r8, 1.9048_r8, 2.5000_r8, 3.5088_r8, 4.0000_r8 /)
  real(r8), parameter :: LFL_LW_EDGES_UM(13) = (/ &
       4.5400_r8, 5.2600_r8, 5.8800_r8, 7.1400_r8, 8.0000_r8, &
       9.0900_r8, 10.2000_r8, 12.5000_r8, 14.9000_r8, 18.5000_r8, &
       25.0000_r8, 35.7000_r8, 100.0000_r8 /)

  integer :: nsw_sarb = 0
  integer :: nlw_sarb = 0
  integer :: nbands_sarb = 0
  integer :: nbins_lw = 0

  real(r8), allocatable :: w_sw(:,:)       ! (nsw_sarb, nswbands)
  real(r8), allocatable :: w_lw(:,:)       ! (nlw_sarb, nlwbands)
  real(r8), allocatable :: sarb_sw_mid(:)  ! microns
  real(r8), allocatable :: sarb_lw_mid(:)  ! microns
  real(r8), allocatable :: omega_lw(:,:)   ! (nlwbands, nbins_lw)
  real(r8), allocatable :: g_lw(:,:)       ! (nlwbands, nbins_lw)

contains

  subroutine aod_optics_bands_init(band_file_in, lw_table_file)
    character(len=*), intent(in) :: band_file_in
    character(len=*), intent(in) :: lw_table_file

    real(r8), allocatable :: sw_edges(:), lw_edges(:)
    real(r8), allocatable :: sw_dst_lo(:), sw_dst_hi(:)
    real(r8), allocatable :: lw_dst_lo(:), lw_dst_hi(:)
    real(r8), allocatable :: sw_coverage(:), lw_coverage(:)
    real(r8) :: sw_cam_lo(nswbands), sw_cam_hi(nswbands)
    real(r8) :: lw_cam_lo(nlwbands), lw_cam_hi(nlwbands)

    if (trim(band_file_in) == '') then
      allocate(sw_edges(size(LFL_SW_EDGES_UM)), lw_edges(size(LFL_LW_EDGES_UM)))
      sw_edges = LFL_SW_EDGES_UM
      lw_edges = LFL_LW_EDGES_UM
    else
      call read_band_edges(trim(band_file_in), sw_edges, lw_edges)
    end if

    nsw_sarb = size(sw_edges) - 1
    nlw_sarb = size(lw_edges) - 1
    nbands_sarb = nsw_sarb + nlw_sarb
    if (nsw_sarb /= 14) call endrun('aod_optics_bands_init: expected 14 LFL SW bands')
    if (nlw_sarb /= 12) call endrun('aod_optics_bands_init: expected 12 LFL LW bands')

    allocate(sarb_sw_mid(nsw_sarb), sarb_lw_mid(nlw_sarb))
    allocate(sw_dst_lo(nsw_sarb), sw_dst_hi(nsw_sarb))
    allocate(lw_dst_lo(nlw_sarb), lw_dst_hi(nlw_sarb))
    allocate(w_sw(nsw_sarb, nswbands), w_lw(nlw_sarb, nlwbands))
    allocate(sw_coverage(nsw_sarb), lw_coverage(nlw_sarb))

    call lambda_edges_to_band_nu(sw_edges, sw_dst_lo, sw_dst_hi, sarb_sw_mid)
    call lambda_edges_to_band_nu(lw_edges, lw_dst_lo, lw_dst_hi, sarb_lw_mid)

    call get_sw_spectral_boundaries(sw_cam_lo, sw_cam_hi, 'cm^-1')
    call get_lw_spectral_boundaries(lw_cam_lo, lw_cam_hi, 'cm^-1')

    call overlap_weights(nswbands, sw_cam_lo, sw_cam_hi, nsw_sarb, sw_dst_lo, sw_dst_hi, w_sw, sw_coverage)
    call overlap_weights(nlwbands, lw_cam_lo, lw_cam_hi, nlw_sarb, lw_dst_lo, lw_dst_hi, w_lw, lw_coverage)

    call warn_partial_coverage('SW', sw_coverage)
    call warn_partial_coverage('LW', lw_coverage)
    call read_lw_table(trim(lw_table_file))

    if (masterproc) then
      if (trim(band_file_in) == '') then
        write(iulog,*) 'AODOPTICS: SARB bands initialized from built-in hard-coded SARB/LFL edges'
      else
        write(iulog,*) 'AODOPTICS: SARB bands initialized from external NetCDF file ', trim(band_file_in)
      end if
      write(iulog,*) 'AODOPTICS: SARB SW edges (um)=', sw_edges
      write(iulog,*) 'AODOPTICS: SARB LW edges (um)=', lw_edges
      write(iulog,*) 'AODOPTICS: nsw_sarb=', nsw_sarb, ' nlw_sarb=', nlw_sarb, &
                     ' nbins_lw=', nbins_lw
      if (trim(lw_table_file) == '') then
        write(iulog,*) 'AODOPTICS: LW omega/g table absent; using omega=0 absorption-only LW'
      else
        write(iulog,*) 'AODOPTICS: LW omega/g table=', trim(lw_table_file)
      end if
    end if
  end subroutine aod_optics_bands_init

  subroutine read_band_edges(fname, sw_edges, lw_edges)
    use cam_pio_utils, only: cam_pio_openfile, cam_pio_closefile
    use pio, only: file_desc_t, pio_nowrite

    character(len=*), intent(in) :: fname
    real(r8), allocatable, intent(out) :: sw_edges(:), lw_edges(:)

    type(file_desc_t) :: fileid

    call cam_pio_openfile(fileid, trim(fname), pio_nowrite)
    call read_1d_real(fileid, 'LFL_SW_bands', sw_edges, trim(fname))
    call read_1d_real(fileid, 'LFL_LW_bands', lw_edges, trim(fname))
    call cam_pio_closefile(fileid)
  end subroutine read_band_edges

  subroutine read_lw_table(fname)
    use cam_pio_utils, only: cam_pio_openfile, cam_pio_closefile
    use pio, only: file_desc_t, pio_nowrite

    character(len=*), intent(in) :: fname

    type(file_desc_t) :: fileid

    if (allocated(omega_lw)) deallocate(omega_lw)
    if (allocated(g_lw)) deallocate(g_lw)

    if (trim(fname) == '') then
      nbins_lw = 1
      allocate(omega_lw(nlwbands, nbins_lw), g_lw(nlwbands, nbins_lw))
      omega_lw = 0._r8
      g_lw     = 0._r8
      return
    end if

    call cam_pio_openfile(fileid, trim(fname), pio_nowrite)
    call read_2d_lw(fileid, 'omega_lw', omega_lw, trim(fname))
    call read_2d_lw(fileid, 'g_lw', g_lw, trim(fname))
    call cam_pio_closefile(fileid)

    if (size(omega_lw, 1) /= nlwbands) then
      call endrun('aod_optics_bands: omega_lw first dimension must equal CAM nlwbands')
    end if
    if (any(shape(omega_lw) /= shape(g_lw))) then
      call endrun('aod_optics_bands: omega_lw and g_lw shapes differ')
    end if
    nbins_lw = size(omega_lw, 2)
    omega_lw = max(0._r8, min(OMEGA_CAP, omega_lw))
    g_lw     = max(-1._r8, min(1._r8, g_lw))
  end subroutine read_lw_table

  subroutine read_1d_real(fileid, varname, values, fname)
    use pio, only: file_desc_t, var_desc_t, pio_inq_varid, pio_inquire_variable, &
                   pio_inquire_dimension, pio_get_var, pio_noerr, PIO_MAX_VAR_DIMS

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: varname, fname
    real(r8), allocatable, intent(out) :: values(:)

    type(var_desc_t) :: varid
    integer :: ierr, ndims, dimids(PIO_MAX_VAR_DIMS), n

    ierr = pio_inq_varid(fileid, trim(varname), varid)
    if (ierr /= pio_noerr) call endrun('aod_optics_bands: missing '//trim(varname)//' in '//trim(fname))
    ierr = pio_inquire_variable(fileid, varid, ndims=ndims)
    if (ierr /= pio_noerr .or. ndims /= 1) call endrun('aod_optics_bands: '//trim(varname)//' must be rank 1')
    ierr = pio_inquire_variable(fileid, varid, dimids=dimids(:ndims))
    ierr = pio_inquire_dimension(fileid, dimids(1), len=n)
    if (ierr /= pio_noerr) call endrun('aod_optics_bands: cannot inspect '//trim(varname))
    allocate(values(n))
    ierr = pio_get_var(fileid, varid, values)
    if (ierr /= pio_noerr) call endrun('aod_optics_bands: cannot read '//trim(varname))
  end subroutine read_1d_real

  subroutine read_2d_lw(fileid, varname, values, fname)
    use pio, only: file_desc_t, var_desc_t, pio_inq_varid, pio_inquire_variable, &
                   pio_inquire_dimension, pio_get_var, pio_noerr, PIO_MAX_VAR_DIMS

    type(file_desc_t), intent(inout) :: fileid
    character(len=*), intent(in) :: varname, fname
    real(r8), allocatable, intent(out) :: values(:,:)

    type(var_desc_t) :: varid
    integer :: ierr, ndims, dimids(PIO_MAX_VAR_DIMS), n1, n2
    real(r8), allocatable :: raw(:,:)

    ierr = pio_inq_varid(fileid, trim(varname), varid)
    if (ierr /= pio_noerr) call endrun('aod_optics_bands: missing '//trim(varname)//' in '//trim(fname))
    ierr = pio_inquire_variable(fileid, varid, ndims=ndims)
    if (ierr /= pio_noerr .or. ndims /= 2) call endrun('aod_optics_bands: '//trim(varname)//' must be rank 2')
    ierr = pio_inquire_variable(fileid, varid, dimids=dimids(:ndims))
    ierr = pio_inquire_dimension(fileid, dimids(1), len=n1)
    if (ierr == pio_noerr) ierr = pio_inquire_dimension(fileid, dimids(2), len=n2)
    if (ierr /= pio_noerr) call endrun('aod_optics_bands: cannot inspect '//trim(varname))
    allocate(raw(n1, n2))
    ierr = pio_get_var(fileid, varid, raw)
    if (ierr /= pio_noerr) call endrun('aod_optics_bands: cannot read '//trim(varname))
    if (n1 == nlwbands) then
      allocate(values(n1, n2))
      values = raw
    else if (n2 == nlwbands) then
      allocate(values(n2, n1))
      values = transpose(raw)
    else
      call endrun('aod_optics_bands: one dimension of '//trim(varname)//' must equal CAM nlwbands')
    end if
  end subroutine read_2d_lw

  subroutine lambda_edges_to_band_nu(edges_um, dst_lo, dst_hi, mid_um)
    real(r8), intent(in)  :: edges_um(:)
    real(r8), intent(out) :: dst_lo(:), dst_hi(:), mid_um(:)

    integer :: i

    do i = 1, size(edges_um) - 1
      if (edges_um(i) <= 0._r8 .or. edges_um(i+1) <= 0._r8) then
        call endrun('aod_optics_bands: LFL wavelength edges must be positive')
      end if
      dst_lo(i) = 1.e4_r8 / edges_um(i)
      dst_hi(i) = 1.e4_r8 / edges_um(i+1)
      mid_um(i) = 0.5_r8 * (edges_um(i) + edges_um(i+1))
    end do
  end subroutine lambda_edges_to_band_nu

  subroutine warn_partial_coverage(name, coverage)
    character(len=*), intent(in) :: name
    real(r8), intent(in) :: coverage(:)

    integer :: i

    if (.not. masterproc) return
    do i = 1, size(coverage)
      if (coverage(i) <= 0._r8) then
        write(iulog,*) 'AODOPTICS WARNING: ', trim(name), ' SARB band ', i, &
                       ' has no CAM spectral overlap'
      else if (coverage(i) < 0.999_r8) then
        write(iulog,*) 'AODOPTICS WARNING: ', trim(name), ' SARB band ', i, &
                       ' has partial CAM spectral overlap; covered destination fraction=', coverage(i)
      end if
    end do
  end subroutine warn_partial_coverage

  logical function is_sw_band(iband)
    integer, intent(in) :: iband
    is_sw_band = iband <= nsw_sarb
  end function is_sw_band

  subroutine get_band_label(iband, label)
    integer, intent(in) :: iband
    character(len=*), intent(out) :: label

    if (iband <= nsw_sarb) then
      write(label, '("sw", i2.2)') iband
    else
      write(label, '("lw", i2.2)') iband - nsw_sarb
    end if
  end subroutine get_band_label

  real(r8) function get_band_wavelength(iband)
    integer, intent(in) :: iband

    if (iband <= nsw_sarb) then
      get_band_wavelength = sarb_sw_mid(iband)
    else
      get_band_wavelength = sarb_lw_mid(iband - nsw_sarb)
    end if
  end function get_band_wavelength

end module aod_optics_bands
