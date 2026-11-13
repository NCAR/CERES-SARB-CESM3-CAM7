program test_tropospheric_nudging
  use shr_kind_mod, only: r8=>shr_kind_r8
  use ppgrid
  use aod_nudging_kernel
  use aod_nudging_optics
  use physics_types
  use physics_buffer
  use tropopause, only: test_trop_level
  implicit none
  type(physics_state), target :: state
  type(physics_buffer_desc), pointer :: pbuf(:)
  real(r8) :: ratio(pcols), aod0(pcols), aod1(pcols), trop0(pcols), trop1(pcols), tp(pcols)
  real(r8) :: mass0(pcols,pver), mass1(pcols,pver), num0(pcols,pver), num1(pcols,pver)
  real(r8) :: q0(pcols,pver,15), cache0(pcols,pver,4)
  integer :: tl(pcols), i, k
  logical :: mask(pcols,pver)
  allocate(pbuf(2))
  ! Nonuniform values expose vertical-index mistakes; padding must stay untouched.
  do k=1,pver
    state%q(:,k,:)=real(k,r8)
    pbuf(1)%value(:,k,:)=real(2*k,r8)
    pbuf(2)%value(:,k,:)=real(3*k,r8)
  end do
  call equal(compute_tropospheric_ratio(.5_r8,.3_r8,.2_r8,.true.,.01_r8,.1_r8,10._r8),2._r8)
  call equal(compute_tropospheric_ratio(.05_r8,.3_r8,.2_r8,.true.,.01_r8,.1_r8,10._r8),.1_r8)
  call equal(compute_tropospheric_ratio(99._r8,.3_r8,.2_r8,.true.,.01_r8,.1_r8,10._r8),10._r8)
  call equal(compute_tropospheric_ratio(.5_r8,.3_r8,.001_r8,.true.,.01_r8,.1_r8,10._r8),1._r8)
  call equal(compute_tropospheric_ratio(-999._r8,.3_r8,.2_r8,.true.,.01_r8,.1_r8,10._r8),1._r8)
  call equal(compute_tropospheric_ratio(.5_r8,.3_r8,.2_r8,.false.,.01_r8,.1_r8,10._r8),1._r8)
  if(below_tropopause(3,-1,pver) .or. below_tropopause(3,pver+1,pver)) stop 21
  call get_troposphere(state,mask,tp,tl)
  do k=1,pver
    if(mask(1,k) .neqv. (k>2)) stop 22
    if(mask(2,k) .neqv. (k>3)) stop 23
  end do
  if(any(mask(3,:))) stop 24
  q0=state%q
  cache0=pbuf(1)%value
  call aerosol_profiles(state,pbuf,mass0,num0)
  call model_aod550(state,pbuf,aod0,mask,trop0)
  ratio=[2._r8,.5_r8,9._r8]
  call apply_scaling(state,pbuf,ratio,.false.,mask)
  call aerosol_profiles(state,pbuf,mass1,num1)
  call model_aod550(state,pbuf,aod1,mask,trop1)
  do i=1,state%ncol
    call equal(aod1(i),aod0(i)-trop0(i)+ratio(i)*trop0(i))
    call equal(trop1(i),ratio(i)*trop0(i))
    do k=1,pver
      if(mask(i,k)) then
        call equal(mass1(i,k),ratio(i)*mass0(i,k))
        call equal(num1(i,k),ratio(i)*num0(i,k))
        if(any(pbuf(1)%value(i,k,:)/=ratio(i)*cache0(i,k,:))) stop 25
      else
        if(any(state%q(i,k,:)/=q0(i,k,:))) stop 26
        if(any(pbuf(1)%value(i,k,:)/=cache0(i,k,:))) stop 27
        call equal(pbuf(2)%value(i,k,1),real(3*k,r8))
      end if
    end do
  end do
  if(any(state%q(:,:,10:13)/=q0(:,:,10:13))) stop 28
  if(any(state%q(3,:,:)/=q0(3,:,:))) stop 29
  if(any(pbuf(1)%value(3,:,:)/=cache0(3,:,:))) stop 30
  test_trop_level=-1
  call get_troposphere(state,mask,tp,tl)
  if(any(mask)) stop 31
  q0=state%q
  call apply_scaling(state,pbuf,ratio,.false.,mask)
  if(any(state%q/=q0)) stop 32
  ! A disabled restriction reproduces whole-column scaling.
  call aerosol_profiles(state,pbuf,mass0,num0)
  call apply_scaling(state,pbuf,ratio,.false.)
  call aerosol_profiles(state,pbuf,mass1,num1)
  do i=1,state%ncol
    do k=1,pver
      call equal(mass1(i,k),ratio(i)*mass0(i,k))
      call equal(num1(i,k),ratio(i)*num0(i,k))
    end do
  end do
  print *, 'PASS: native boundary, fixed AOD, mass/number/cache protection, legacy mode'
contains
  subroutine equal(actual,expected)
    real(r8), intent(in) :: actual, expected
    if(abs(actual-expected)>1.e-12_r8*max(1._r8,abs(expected))) then
      print *, actual, expected
      stop 33
    end if
  end subroutine
end program
