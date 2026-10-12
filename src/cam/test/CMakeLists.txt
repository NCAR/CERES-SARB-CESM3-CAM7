# Allow this test directory to run either as part of the parent CAM unit-test
# CMake project or directly via run_tests.py --test-spec-dir aod_nudging.
if(NOT DEFINED cam_sources)
  cmake_minimum_required(VERSION 2.8)

  list(APPEND CMAKE_MODULE_PATH ${CIME_CMAKE_MODULE_DIRECTORY})
  include(CIME_initial_setup)

  project(CAM_aod_nudging_tests Fortran C)

  include(CIME_utils)

  function(create_pFUnit_test test_name exe_name pf_sources test_sources)
    add_pfunit_ctest(${exe_name}
      TEST_SOURCES "${pf_sources}"
      OTHER_SOURCES "${test_sources}"
      LABELS "${test_name}")
  endfunction()

  set(CAMROOT ../../..)
  set(CESMROOT ${CAMROOT}/../..)
  set(SHAREROOT ${CESMROOT}/share)

  include_directories(${SHAREROOT}/include ${SHAREROOT}/src)
  add_subdirectory(${SHAREROOT}/src csm_share_src)
  add_subdirectory(${SHAREROOT}/unit_test_stubs/util csm_share_stubs)

  add_subdirectory(${CAMROOT}/src/physics/cam physics_cam)

  add_library(csm_share ${share_sources})
  declare_generated_dependencies(csm_share "${share_genf90_sources}")
  get_target_property(includes csm_share INCLUDE_DIRECTORIES)
  if(NOT includes)
    unset(includes)
  endif()
  list(APPEND includes "${PFUNIT_INCLUDE_DIRS}")
  set_target_properties(csm_share PROPERTIES
    INCLUDE_DIRECTORIES "${includes}")
  include_directories(${CMAKE_CURRENT_BINARY_DIR})
endif()

# Local pFUnit files.
set(pf_sources
  test_aod_nudging_kernel.pf
  test_aod_optics_kernel.pf
  test_aod_optics_lut_kernel.pf)

# Sources to test (resolved out of the shared cam_sources list set by the parent).
set(sources_needed
  aod_nudging_kernel.F90
  aod_optics_kernel.F90
  aod_optics_lut_kernel.F90)
extract_sources("${sources_needed}" "${cam_sources}" test_sources)

# Do source preprocessing and add the executable.
create_pFUnit_test(aod_nudging aod_nudging_exe "${pf_sources}"
  "${test_sources}")

target_link_libraries(aod_nudging_exe csm_share)

# Standalone label/executable for the SP3 optics kernel.
set(pf_sources_optics test_aod_optics_kernel.pf test_aod_optics_lut_kernel.pf)
set(sources_needed_optics aod_optics_kernel.F90 aod_optics_lut_kernel.F90)
extract_sources("${sources_needed_optics}" "${cam_sources}" test_sources_optics)
create_pFUnit_test(aod_optics aod_optics_exe "${pf_sources_optics}"
  "${test_sources_optics}")
target_link_libraries(aod_optics_exe csm_share)
