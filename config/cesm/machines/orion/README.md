# CESM3 desktop machine configuration

This CIME machine definition targets the `Orion` Pop!_OS desktop. The
dedicated `cesm3-build` environment uses the GNU 15.2/OpenMPI 5.0 compiler
family already proven by MPAS, adding the MPI NetCDF, PnetCDF, ParallelIO, and
ESMF stack required by CESM's NUOPC driver. The existing MPAS environment is
not modified. A separate `cesm3-tools` environment supplies Perl 5.32 and
`XML::LibXML` for the CTSM namelist generator.

Environment definitions, compatibility-patch provenance, build commands, the
verified run record, and the desktop memory limit are documented in
[`docs/cesm3-desktop.md`](../../../../docs/cesm3-desktop.md).

Pass the directory to CIME without installing global user configuration:

```bash
/home/fillmore/EarthSystem/CESM3/cime/scripts/create_newcase \
  --case /home/fillmore/EarthSystem/CESM3/cases/example \
  --compset FHISTC_LTso \
  --res ne30pg3_ne30pg3_mt232 \
  --machine orion \
  --compiler gnu \
  --mpilib openmpi \
  --pecount 16 \
  --extra-machines-dir \
    /home/fillmore/EarthSystem/CERES-SARB-CAM7/config/cesm/machines/orion \
  --run-unsupported
```

The unsupported override is required by the beta08 CIME metadata and does not
constitute scientific validation. Building ne30 is verified, but running ne30
exhausts this desktop's 64 GiB memory; use the documented ne3 four-rank gate
locally. This configuration does not deploy the project's MODIS/VIIRS source
overlay.
