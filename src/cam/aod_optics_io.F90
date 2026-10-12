module aod_optics_io
!-----------------------------------------------------------------------------
! SP3 PIO writer for one SARB/LFL band file in MAM-LFL format.
!-----------------------------------------------------------------------------
  use shr_kind_mod,   only: r8 => shr_kind_r8, cl => shr_kind_cl
  use ppgrid,         only: pcols, pver, begchunk, endchunk
  use cam_abortutils, only: endrun
  use phys_grid,      only: gather_chunk_to_field, get_grid_dims
  use spmd_utils,     only: masterproc, masterprocid, mpicom, mpir8, mpi_success

  implicit none
  private

  public :: write_band_file

  interface put_att_checked
    module procedure put_att_checked_c
    module procedure put_att_checked_i
    module procedure put_att_checked_r
  end interface
  interface put_global_att
    module procedure put_global_att_c
    module procedure put_global_att_i
    module procedure put_global_att_r
  end interface

contains

  subroutine write_band_file(fname, band_label, wavelength_um, scheme, method, &
                             lut_file, lut_version, nudged, list_idx, ext, sca, asym, delp, col)
    use cam_pio_utils, only: cam_pio_createfile, cam_pio_closefile, &
                             cam_pio_def_dim, cam_pio_def_var
    use pio, only: file_desc_t, var_desc_t, pio_real, pio_double, pio_char, &
                   pio_enddef, pio_put_var, pio_put_att, pio_global, pio_noerr

    character(len=*), intent(in) :: fname
    character(len=*), intent(in) :: band_label
    real(r8),         intent(in) :: wavelength_um
    character(len=*), intent(in) :: scheme
    character(len=*), intent(in) :: method
    character(len=*), intent(in) :: lut_file
    character(len=*), intent(in) :: lut_version
    logical,          intent(in) :: nudged
    integer,          intent(in) :: list_idx
    real(r8), intent(in) :: ext(pcols,pver,begchunk:endchunk)
    real(r8), intent(in) :: sca(pcols,pver,begchunk:endchunk)
    real(r8), intent(in) :: asym(pcols,pver,begchunk:endchunk)
    real(r8), intent(in) :: delp(pcols,pver,begchunk:endchunk)
    real(r8), intent(in) :: col(pcols,begchunk:endchunk)

    type(file_desc_t) :: fileid
    type(var_desc_t)  :: vid_lon, vid_lat, vid_lev
    type(var_desc_t)  :: vid_delp, vid_ext, vid_sca, vid_asym, vid_col
    integer :: did_lon, did_lat, did_lev
    integer :: nlon, nlat, ierr, i, j, k
    integer :: dims3(3), dims2(2)
    real(r8), allocatable :: lon(:), lat(:), lev(:)
    real(r8), allocatable :: global5(:,:,:,:,:)
    real(r8), allocatable :: local5(:,:,:,:,:)
    real(r8), allocatable :: out3(:,:,:), out2(:,:)

    call get_grid_dims(nlon, nlat)
    allocate(lon(nlon), lat(nlat), lev(pver))
    allocate(global5(1,nlon,pver,nlat,1))
    allocate(local5(1,pcols,pver,begchunk:endchunk,1))
    allocate(out3(nlon,nlat,pver), out2(nlon,nlat))

    do i = 1, nlon
      lon(i) = real(i-1, r8) * 360._r8 / real(nlon, r8)
    end do
    do j = 1, nlat
      lat(j) = -90._r8 + real(j-1, r8) * 180._r8 / real(max(1, nlat-1), r8)
    end do
    do k = 1, pver
      lev(k) = real(k, r8)
    end do

    call cam_pio_createfile(fileid, trim(fname), 0)
    call cam_pio_def_dim(fileid, 'lon', nlon, did_lon)
    call cam_pio_def_dim(fileid, 'lat', nlat, did_lat)
    call cam_pio_def_dim(fileid, 'lev', pver, did_lev)

    call cam_pio_def_var(fileid, 'lon', pio_double, (/did_lon/), vid_lon)
    call cam_pio_def_var(fileid, 'lat', pio_double, (/did_lat/), vid_lat)
    call cam_pio_def_var(fileid, 'lev', pio_double, (/did_lev/), vid_lev)

    dims3 = (/did_lon, did_lat, did_lev/)
    dims2 = (/did_lon, did_lat/)
    call cam_pio_def_var(fileid, 'DELP', pio_real, dims3, vid_delp)
    call cam_pio_def_var(fileid, 'Extinction_Layer_Optical_Depth', pio_real, dims3, vid_ext)
    call cam_pio_def_var(fileid, 'Scattering_Layer_Optical_Depth', pio_real, dims3, vid_sca)
    call cam_pio_def_var(fileid, 'Layer_Asymmetry_Parameter', pio_real, dims3, vid_asym)
    call cam_pio_def_var(fileid, 'Extinction_Column_Optical_Depth', pio_real, dims2, vid_col)

    call put_global_att(fileid, pio_global, 'scheme', trim(scheme))
    call put_global_att(fileid, pio_global, 'method', trim(method))
    call put_global_att(fileid, pio_global, 'lut_file', trim(lut_file))
    call put_global_att(fileid, pio_global, 'lut_table_version', trim(lut_version))
    call put_global_att(fileid, pio_global, 'band', trim(band_label))
    call put_global_att(fileid, pio_global, 'source', 'CAM7')
    call put_global_att(fileid, pio_global, 'diagnostic', 'SP3 aerosol optics')
    call put_global_att(fileid, pio_global, 'list_idx', list_idx)
    call put_global_att(fileid, pio_global, 'wavelength_um', wavelength_um)
    call put_global_att(fileid, pio_global, 'nudged', merge(1, 0, nudged))

    call put_att_checked(fileid, vid_lon, 'units', 'degrees_east')
    call put_att_checked(fileid, vid_lat, 'units', 'degrees_north')
    call put_att_checked(fileid, vid_lev, 'long_name', 'model layer')
    call put_att_checked(fileid, vid_delp, 'units', 'Pa')
    call put_att_checked(fileid, vid_ext, 'units', '1')
    call put_att_checked(fileid, vid_sca, 'units', '1')
    call put_att_checked(fileid, vid_asym, 'units', '1')
    call put_att_checked(fileid, vid_col, 'units', '1')

    ierr = pio_enddef(fileid)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: pio_enddef failed for '//trim(fname))

    ierr = pio_put_var(fileid, vid_lon, lon)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing lon failed')
    ierr = pio_put_var(fileid, vid_lat, lat)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing lat failed')
    ierr = pio_put_var(fileid, vid_lev, lev)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing lev failed')

    call write_layer(fileid, vid_delp, delp, local5, global5, out3, 'DELP')
    call write_layer(fileid, vid_ext,  ext,  local5, global5, out3, 'Extinction_Layer_Optical_Depth')
    call write_layer(fileid, vid_sca,  sca,  local5, global5, out3, 'Scattering_Layer_Optical_Depth')
    call write_layer(fileid, vid_asym, asym, local5, global5, out3, 'Layer_Asymmetry_Parameter')
    call write_column(fileid, vid_col, col, out2, 'Extinction_Column_Optical_Depth')

    call cam_pio_closefile(fileid)

    deallocate(lon, lat, lev, global5, local5, out3, out2)
  end subroutine write_band_file

  subroutine write_layer(fileid, varid, local3, local5, global5, out3, varname)
    use pio, only: file_desc_t, var_desc_t, pio_put_var, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    type(var_desc_t),  intent(inout) :: varid
    real(r8), intent(in)    :: local3(pcols,pver,begchunk:endchunk)
    real(r8), intent(inout) :: local5(1,pcols,pver,begchunk:endchunk,1)
    real(r8), intent(inout) :: global5(:,:,:,:,:)
    real(r8), intent(inout) :: out3(:,:,:)
    character(len=*), intent(in) :: varname

    integer :: i, j, k, ierr

    local5(1,:,:,:,1) = local3
    call gather_chunk_to_field(1, pver, 1, size(out3,1), local5, global5)
    if (masterproc) then
      do k = 1, pver
        do j = 1, size(out3,2)
          do i = 1, size(out3,1)
            out3(i,j,k) = global5(1,i,k,j,1)
          end do
        end do
      end do
    end if
    call broadcast_3d(out3, varname)
    ierr = pio_put_var(fileid, varid, out3)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing '//trim(varname)//' failed')
  end subroutine write_layer

  subroutine write_column(fileid, varid, local2, out2, varname)
    use pio, only: file_desc_t, var_desc_t, pio_put_var, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    type(var_desc_t),  intent(inout) :: varid
    real(r8), intent(in)    :: local2(pcols,begchunk:endchunk)
    real(r8), intent(inout) :: out2(:,:)
    character(len=*), intent(in) :: varname

    real(r8), allocatable :: local5(:,:,:,:,:), global5(:,:,:,:,:)
    integer :: i, j, ierr

    allocate(local5(1,pcols,1,begchunk:endchunk,1))
    allocate(global5(1,size(out2,1),1,size(out2,2),1))
    local5(1,:,1,:,1) = local2
    call gather_chunk_to_field(1, 1, 1, size(out2,1), local5, global5)
    if (masterproc) then
      do j = 1, size(out2,2)
        do i = 1, size(out2,1)
          out2(i,j) = global5(1,i,1,j,1)
        end do
      end do
    end if
    call broadcast_2d(out2, varname)
    ierr = pio_put_var(fileid, varid, out2)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing '//trim(varname)//' failed')
    deallocate(local5, global5)
  end subroutine write_column

  subroutine broadcast_3d(field, varname)
    real(r8), intent(inout) :: field(:,:,:)
    character(len=*), intent(in) :: varname

    integer :: ierr

    call MPI_bcast(field, size(field), mpir8, masterprocid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun('aod_optics_io: bcast '//trim(varname)//' failed')
  end subroutine broadcast_3d

  subroutine broadcast_2d(field, varname)
    real(r8), intent(inout) :: field(:,:)
    character(len=*), intent(in) :: varname

    integer :: ierr

    call MPI_bcast(field, size(field), mpir8, masterprocid, mpicom, ierr)
    if (ierr /= mpi_success) call endrun('aod_optics_io: bcast '//trim(varname)//' failed')
  end subroutine broadcast_2d

  subroutine put_att_checked_c(fileid, varid, name, value)
    use pio, only: file_desc_t, var_desc_t, pio_put_att, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    type(var_desc_t),  intent(inout) :: varid
    character(len=*), intent(in) :: name
    character(len=*), intent(in) :: value

    integer :: ierr

    ierr = pio_put_att(fileid, varid, trim(name), trim(value))
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing attr '//trim(name)//' failed')
  end subroutine put_att_checked_c

  subroutine put_att_checked_i(fileid, varid, name, value)
    use pio, only: file_desc_t, var_desc_t, pio_put_att, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    type(var_desc_t),  intent(inout) :: varid
    character(len=*), intent(in) :: name
    integer, intent(in) :: value

    integer :: ierr

    ierr = pio_put_att(fileid, varid, trim(name), value)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing attr '//trim(name)//' failed')
  end subroutine put_att_checked_i

  subroutine put_att_checked_r(fileid, varid, name, value)
    use pio, only: file_desc_t, var_desc_t, pio_put_att, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    type(var_desc_t),  intent(inout) :: varid
    character(len=*), intent(in) :: name
    real(r8), intent(in) :: value

    integer :: ierr

    ierr = pio_put_att(fileid, varid, trim(name), value)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing attr '//trim(name)//' failed')
  end subroutine put_att_checked_r

  subroutine put_global_att_c(fileid, varid, name, value)
    use pio, only: file_desc_t, pio_put_att, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    integer, intent(in) :: varid
    character(len=*), intent(in) :: name
    character(len=*), intent(in) :: value

    integer :: ierr

    ierr = pio_put_att(fileid, varid, trim(name), trim(value))
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing attr '//trim(name)//' failed')
  end subroutine put_global_att_c

  subroutine put_global_att_i(fileid, varid, name, value)
    use pio, only: file_desc_t, pio_put_att, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    integer, intent(in) :: varid
    character(len=*), intent(in) :: name
    integer, intent(in) :: value

    integer :: ierr

    ierr = pio_put_att(fileid, varid, trim(name), value)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing attr '//trim(name)//' failed')
  end subroutine put_global_att_i

  subroutine put_global_att_r(fileid, varid, name, value)
    use pio, only: file_desc_t, pio_put_att, pio_noerr

    type(file_desc_t), intent(inout) :: fileid
    integer, intent(in) :: varid
    character(len=*), intent(in) :: name
    real(r8), intent(in) :: value

    integer :: ierr

    ierr = pio_put_att(fileid, varid, trim(name), value)
    if (ierr /= pio_noerr) call endrun('aod_optics_io: writing attr '//trim(name)//' failed')
  end subroutine put_global_att_r

end module aod_optics_io
