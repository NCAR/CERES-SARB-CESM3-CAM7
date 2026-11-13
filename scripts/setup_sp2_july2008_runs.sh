#!/usr/bin/env bash
set -euo pipefail

REPO=${SP2_REPO:-/glade/work/fillmore/CERES-SARB-CAM7}
CESM=${SP2_CESM:-/glade/work/fillmore/CESM3/cesm3_0_beta08}
CASE_ROOT=${SP2_CASE_ROOT:-/glade/work/fillmore/CESM3/cases}
OBS_DIR=${SP2_OBS_DIR:-/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/}
PROJECT=${PROJECT:-P19010000}

FREE_CASE_NAME=sp2_200807_mam4_free
NUDGED_CASE_NAME=sp2_200807_mam4_modis
FREE_CASE="$CASE_ROOT/$FREE_CASE_NAME"
NUDGED_CASE="$CASE_ROOT/$NUDGED_CASE_NAME"

RUN_STARTDATE=2008-07-01
NTASKS=128
NTASKS=${SP2_NTASKS:-$NTASKS}
JOB_QUEUE=main
JOB_WALLCLOCK_TIME=12:00:00

DRY_RUN=false
REUSE_EXISTING=false
SUBMIT=false

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--reuse-existing] [--submit]

Prepare the paired SP2 July 2008 MAM4 cases:
  $NUDGED_CASE_NAME  MODIS AOD nudging on
  $FREE_CASE_NAME    free-running reference, AOD nudging off

Options:
  --dry-run         Print actions without creating cases, building, or submitting.
  --reuse-existing  Allow existing case directories to be reconfigured.
  --submit          Submit both cases with ./case.submit after setup.
  -h, --help        Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --reuse-existing) REUSE_EXISTING=true ;;
    --submit) SUBMIT=true ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

run() {
  if "$DRY_RUN"; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

run_in_case() {
  local case_dir=$1
  shift
  if "$DRY_RUN"; then
    printf '+ cd %q &&' "$case_dir"
    printf ' %q' "$@"
    printf '\n'
  else
    (cd "$case_dir" && "$@")
  fi
}

require_path() {
  local path=$1
  local label=$2
  if [[ ! -e "$path" ]]; then
    echo "Missing $label: $path" >&2
    exit 2
  fi
}

ensure_obs_files() {
  local count
  count=$(find "$OBS_DIR" -maxdepth 1 -type f -name 'MODIS_VIIRS_AOD_3hr_f09.200807*.nc' | wc -l)
  if [[ "$count" -ne 248 ]]; then
    echo "Expected 248 July 2008 3-hourly AOD files under $OBS_DIR; found $count" >&2
    exit 2
  fi
}

ensure_case_absent_or_reusable() {
  local case_dir=$1
  if [[ -d "$case_dir" && "$REUSE_EXISTING" != true ]]; then
    echo "Case already exists: $case_dir" >&2
    echo "Use --reuse-existing to reconfigure it intentionally." >&2
    exit 2
  fi
}

create_nudged_case() {
  if [[ -d "$NUDGED_CASE" ]]; then
    echo "Reusing existing nudged case: $NUDGED_CASE"
    return
  fi
  run "$CESM/cime/scripts/create_newcase" \
    --case "$NUDGED_CASE" \
    --compset F2000dev \
    --res f09_f09_mg17 \
    --machine derecho \
    --compiler intel \
    --project "$PROJECT" \
    --run-unsupported
}

create_free_case() {
  if [[ -d "$FREE_CASE" ]]; then
    echo "Reusing existing free case: $FREE_CASE"
    return
  fi
  run "$CESM/cime/scripts/create_clone" \
    --case "$FREE_CASE" \
    --clone "$NUDGED_CASE" \
    --keepexe \
    --project "$PROJECT"
}

strip_sp2_block() {
  local user_nl=$1
  local tmp
  tmp=$(mktemp)
  awk '
    /^! BEGIN SP2 July 2008 month-run block$/ {skip=1; next}
    /^! END SP2 July 2008 month-run block$/ {skip=0; next}
    !skip {print}
  ' "$user_nl" > "$tmp"
  cat "$tmp" > "$user_nl"
  rm -f "$tmp"
}

write_nudged_user_nl() {
  local user_nl="$NUDGED_CASE/user_nl_cam"
  if "$DRY_RUN"; then
    echo "Would write nudged SP2 user_nl_cam block to $user_nl"
    return
  fi
  strip_sp2_block "$user_nl"
  cat >> "$user_nl" <<EOF
! BEGIN SP2 July 2008 month-run block
aod_nudge_on = .true.
aod_obs_path = '${OBS_DIR}'
aod_obs_template = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
aod_times_per_day = 8
aod_diag_on = .true.
empty_htapes = .true.
fincl1 = 'AODVIS','FSNTC','AODNDG_OBS','AODNDG_MODEL_PRE','AODNDG_MODEL_POST','AODNDG_RATIO','AODNDG_MASK'
iradsw = -1
nhtfrq = -3
mfilt = 248
! END SP2 July 2008 month-run block
EOF
}

write_free_user_nl() {
  local user_nl="$FREE_CASE/user_nl_cam"
  if "$DRY_RUN"; then
    echo "Would write free SP2 user_nl_cam block to $user_nl"
    return
  fi
  strip_sp2_block "$user_nl"
  cat >> "$user_nl" <<EOF
! BEGIN SP2 July 2008 month-run block
aod_nudge_on = .false.
aod_diag_on = .false.
empty_htapes = .true.
fincl1 = 'AODVIS','FSNTC'
iradsw = -1
nhtfrq = -3
mfilt = 248
! END SP2 July 2008 month-run block
EOF
}

configure_case_xml() {
  local case_dir=$1

  run_in_case "$case_dir" ./xmlchange \
    RUN_STARTDATE=2008-07-01,STOP_OPTION=ndays,STOP_N=31,REST_OPTION=ndays,REST_N=31,DOUT_S=FALSE,CONTINUE_RUN=FALSE,RESUBMIT=0,JOB_QUEUE=main,JOB_WALLCLOCK_TIME=12:00:00
  run_in_case "$case_dir" ./xmlchange \
    NTASKS_ATM="$NTASKS",NTASKS_LND="$NTASKS",NTASKS_ICE="$NTASKS",NTASKS_OCN="$NTASKS"
  run_in_case "$case_dir" ./xmlchange \
    NTASKS_CPL="$NTASKS",NTASKS_ROF="$NTASKS",NTASKS_GLC="$NTASKS",NTASKS_WAV="$NTASKS",NTASKS_ESP=1
  run_in_case "$case_dir" ./xmlchange \
    ROOTPE_ATM=0,ROOTPE_LND=0,ROOTPE_ICE=0,ROOTPE_OCN=0,ROOTPE_CPL=0,ROOTPE_ROF=0,ROOTPE_GLC=0,ROOTPE_WAV=0,ROOTPE_ESP=0
  run_in_case "$case_dir" ./xmlchange \
    NTHRDS_ATM=1,NTHRDS_LND=1,NTHRDS_ICE=1,NTHRDS_OCN=1,NTHRDS_CPL=1,NTHRDS_ROF=1,NTHRDS_GLC=1,NTHRDS_WAV=1,NTHRDS_ESP=1
  run_in_case "$case_dir" ./xmlchange \
    MAX_MPITASKS_PER_NODE="$NTASKS",MAX_TASKS_PER_NODE="$NTASKS"

  if [[ -d "$case_dir/Buildconf" ]]; then
    run_in_case "$case_dir" ./case.setup --reset
  else
    run_in_case "$case_dir" ./case.setup
  fi
}

build_case_conda_free() {
  local case_dir=$1
  if "$DRY_RUN"; then
    echo "+ cd $(printf '%q' "$case_dir") && conda-free ./case.build"
    return
  fi

  (
    cd "$case_dir"
    shim=$(mktemp -d)
    trap 'rm -rf "$shim"' EXIT
    ln -s /glade/work/fillmore/miniforge3/bin/python3 "$shim/python3"
    export PATH="$shim:$(printf '%s' "$PATH" | tr : '\n' | awk '$0 !~ /miniforge3/' | paste -sd:)"
    unset CONDA_PREFIX
    ./case.build
  )
}

mark_free_clone_build_complete() {
  local exeroot

  if "$DRY_RUN"; then
    echo "+ cd $(printf '%q' "$FREE_CASE") && verify shared cesm.exe && ./xmlchange BUILD_COMPLETE=TRUE"
    return
  fi

  exeroot=$(cd "$FREE_CASE" && ./xmlquery --value EXEROOT)
  if [[ ! -x "$exeroot/cesm.exe" ]]; then
    echo "Free clone EXEROOT does not contain an executable: $exeroot/cesm.exe" >&2
    exit 2
  fi
  (cd "$FREE_CASE" && ./xmlchange BUILD_COMPLETE=TRUE)
}

submit_case() {
  local case_dir=$1
  if "$SUBMIT"; then
    run_in_case "$case_dir" ./case.submit
  else
    echo "Prepared $case_dir; submit with: cd $case_dir && ./case.submit"
  fi
}

require_path "$CESM/cime/scripts/create_newcase" "CESM create_newcase"
require_path "$CESM/cime/scripts/create_clone" "CESM create_clone"
require_path "$REPO/scripts/sp2_deploy.sh" "SP2 deploy script"
require_path "$OBS_DIR" "July 2008 AOD observation directory"
ensure_obs_files
ensure_case_absent_or_reusable "$NUDGED_CASE"
ensure_case_absent_or_reusable "$FREE_CASE"

run "$REPO/scripts/sp2_deploy.sh"

create_nudged_case
run "$REPO/scripts/sp2_deploy.sh" "$NUDGED_CASE"
configure_case_xml "$NUDGED_CASE"
write_nudged_user_nl
run_in_case "$NUDGED_CASE" ./check_input_data --download
build_case_conda_free "$NUDGED_CASE"
run_in_case "$NUDGED_CASE" ./preview_namelists --component atm

create_free_case
run "$REPO/scripts/sp2_deploy.sh" "$FREE_CASE"
configure_case_xml "$FREE_CASE"
write_free_user_nl
run_in_case "$FREE_CASE" ./check_input_data --download
mark_free_clone_build_complete
run_in_case "$FREE_CASE" ./preview_namelists --component atm

submit_case "$NUDGED_CASE"
submit_case "$FREE_CASE"
