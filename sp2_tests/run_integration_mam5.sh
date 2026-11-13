#!/usr/bin/env bash
set -euo pipefail

CASE=${SP2_CASE:-/glade/work/fillmore/CESM3/cases/sp2_mam5}
CESM=${SP2_CESM:-/glade/work/fillmore/CESM3/cesm3_0_beta08}
OBSDIR=${SP2_OBSDIR:-/glade/derecho/scratch/fillmore/sp2_obs}
NTASKS=${SP2_NTASKS:-}
TARGET_CHEM="-chem trop_strat_mam5_t1s1"
TARGET_USE_CASE=2000_trop_strat_vbs_cam6

if [[ -z "$NTASKS" ]]; then
  if [[ ${PBS_SELECT:-} =~ ncpus=([0-9]+) ]]; then
    NTASKS=${BASH_REMATCH[1]}
  else
    NTASKS=32
  fi
fi

if [[ ! -d "$OBSDIR" ]] || ! find "$OBSDIR" -name 'MODIS_VIIRS_AOD_3hr_f09.*.nc' -print -quit | grep -q .; then
  echo "Missing synthetic obs files in $OBSDIR" >&2
  echo "Run sp2_tests/make_synthetic_obs.py first." >&2
  exit 2
fi

shim=$(mktemp -d)
trap 'rm -rf "$shim"' EXIT
ln -s /glade/work/fillmore/miniforge3/bin/python3 "$shim/python3"
export PATH="$shim:$(printf '%s' "$PATH" | tr : '\n' | awk '$0 !~ /miniforge3/' | paste -sd:)"
unset CONDA_PREFIX

if [[ ! -d "$CASE" ]]; then
  cd "$CESM/cime/scripts"
  ./create_newcase --case "$CASE" --compset F2000dev --res f09_f09_mg17 \
    --machine derecho --compiler intel --project P19010000 --run-unsupported
elif [[ ! -f "$CASE/env_case.xml" ]]; then
  echo "ERROR: $CASE exists but is not a CIME case" >&2
  exit 2
fi

cd "$CASE"

last_chem=$(./xmlquery -value CAM_CONFIG_OPTS | grep -o -- '-chem [a-z0-9_]*' | tail -1 || true)
if [[ "$last_chem" != "$TARGET_CHEM" ]]; then
  ./xmlchange --append CAM_CONFIG_OPTS=" $TARGET_CHEM"
fi
last_chem=$(./xmlquery -value CAM_CONFIG_OPTS | grep -o -- '-chem [a-z0-9_]*' | tail -1 || true)
echo "CAM_CONFIG_OPTS last chem = '${last_chem}'"
test "$last_chem" = "$TARGET_CHEM" || {
  echo "ERROR: MAM5 chem override not in effect" >&2
  exit 1
}

current_use_case=$(./xmlquery -value CAM_NML_USE_CASE)
if [[ "$current_use_case" != "$TARGET_USE_CASE" ]]; then
  ./xmlchange CAM_NML_USE_CASE="$TARGET_USE_CASE"
fi
current_use_case=$(./xmlquery -value CAM_NML_USE_CASE)
echo "CAM_NML_USE_CASE = '${current_use_case}'"
test "$current_use_case" = "$TARGET_USE_CASE" || {
  echo "ERROR: MAM5 VBS namelist use case not in effect" >&2
  exit 1
}

touch user_nl_cam
tmp=$(mktemp)
awk '
  /^! BEGIN SP2 AOD nudging integration block$/ {skip=1; next}
  /^! END SP2 AOD nudging integration block$/ {skip=0; next}
  !skip {print}
' user_nl_cam > "$tmp"
cat "$tmp" > user_nl_cam
rm -f "$tmp"

cat >> user_nl_cam <<EOF
! BEGIN SP2 AOD nudging integration block
aod_nudge_on = .true.
aod_obs_path = '${OBSDIR}/'
aod_obs_template = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
aod_times_per_day = 8
aod_diag_on = .true.
empty_htapes = .true.
fincl1 = 'AODNDG_OBS','AODNDG_MODEL_PRE','AODNDG_MODEL_POST','AODNDG_RATIO','AODNDG_MASK','AODVIS'
iradsw = -1
nhtfrq = -1
mfilt = 1
! END SP2 AOD nudging integration block
EOF

# Dormant historical helper: MAM5 SP2 work is deferred indefinitely.
# Do not run unless the user explicitly reopens MAM5 scope.
./xmlchange STOP_OPTION=nhours,STOP_N=3,REST_OPTION=never,DOUT_S=FALSE,CONTINUE_RUN=FALSE,RESUBMIT=0
./xmlchange NTASKS_ATM="$NTASKS",NTASKS_LND="$NTASKS",NTASKS_ICE="$NTASKS",NTASKS_OCN="$NTASKS"
./xmlchange NTASKS_CPL="$NTASKS",NTASKS_ROF="$NTASKS",NTASKS_GLC="$NTASKS",NTASKS_WAV="$NTASKS",NTASKS_ESP=1
./xmlchange ROOTPE_ATM=0,ROOTPE_LND=0,ROOTPE_ICE=0,ROOTPE_OCN=0,ROOTPE_CPL=0,ROOTPE_ROF=0,ROOTPE_GLC=0,ROOTPE_WAV=0,ROOTPE_ESP=0
./xmlchange NTHRDS_ATM=1,NTHRDS_LND=1,NTHRDS_ICE=1,NTHRDS_OCN=1,NTHRDS_CPL=1,NTHRDS_ROF=1,NTHRDS_GLC=1,NTHRDS_WAV=1,NTHRDS_ESP=1
./xmlchange MAX_MPITASKS_PER_NODE="$NTASKS",MAX_TASKS_PER_NODE="$NTASKS"
./case.setup --reset

RUNDIR=$(./xmlquery --value RUNDIR)
rm -f "$RUNDIR"/sp2_mam5.cam.h0*.nc

tmp=$(mktemp)
awk '
  /<mpirun mpilib="default">/ && !done {
    print "  <mpirun mpilib=\"default\">"
    print "    <executable>mpiexec</executable>"
    print "    <arguments>"
    print "      <arg name=\"num_tasks\"> -n $TOTALPES</arg>"
    print "      <arg name=\"label\"> --label</arg>"
    print "      <arg name=\"buffer\"> --line-buffer</arg>"
    print "    </arguments>"
    print "  </mpirun>"
    skip=1
    done=1
    next
  }
  skip && /<\/mpirun>/ {skip=0; next}
  !skip {print}
' env_mach_specific.xml > "$tmp"
cat "$tmp" > env_mach_specific.xml
rm -f "$tmp"

./preview_namelists --component atm
if grep -Eq "SOAE[[:space:]]*->" CaseDocs/atm_in; then
  echo "ERROR: generated MAM5 atm_in still contains SOAE surface emissions" >&2
  exit 1
fi
if ! grep -Eq "SVOC[[:space:]]*->" CaseDocs/atm_in; then
  echo "ERROR: generated MAM5 atm_in is missing VBS SVOC surface emissions" >&2
  exit 1
fi

./check_input_data --download
./case.build
./case.submit --no-batch
