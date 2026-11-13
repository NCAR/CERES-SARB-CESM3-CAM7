set(ORION_CONDA_PREFIX "/home/fillmore/miniforge3/envs/cesm3-build")

set(MPICC "${ORION_CONDA_PREFIX}/bin/mpicc")
set(MPICXX "${ORION_CONDA_PREFIX}/bin/mpicxx")
set(MPIFC "${ORION_CONDA_PREFIX}/bin/mpif90")
set(SCC "${ORION_CONDA_PREFIX}/bin/gcc")
set(SCXX "${ORION_CONDA_PREFIX}/bin/g++")
set(SFC "${ORION_CONDA_PREFIX}/bin/gfortran")

set(NETCDF_PATH "${ORION_CONDA_PREFIX}")
set(PNETCDF_PATH "${ORION_CONDA_PREFIX}")
set(LAPACK_LIBDIR "${ORION_CONDA_PREFIX}/lib")

execute_process(
  COMMAND "${NETCDF_PATH}/bin/nf-config" --flibs
  OUTPUT_VARIABLE ORION_NETCDF_FORTRAN_LIBS
  OUTPUT_STRIP_TRAILING_WHITESPACE
  COMMAND_ERROR_IS_FATAL ANY)

string(APPEND LDFLAGS " -Wl,-rpath,${ORION_CONDA_PREFIX}/lib")
string(APPEND SLIBS
       " ${ORION_NETCDF_FORTRAN_LIBS} -L${PNETCDF_PATH}/lib -lpnetcdf -llapack -lblas -ldl")
string(APPEND CXX_LIBS " -lstdc++")
set(SUPPORTS_CXX "TRUE")
