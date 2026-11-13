#!/usr/bin/env bash
set -euo pipefail

REPO=${SP2_REPO:-/glade/work/fillmore/CERES-SARB-CAM7}
CESM=${SP2_CESM:-/glade/work/fillmore/CESM3/cesm3_0_beta08}
CASE_ROOT=${SP2_CASE_ROOT:-/glade/work/fillmore/CESM3/cases}
OBSDIR=${SP2_TRANSPORT_OBSDIR:-/glade/derecho/scratch/fillmore/sp2_transport_obs}
PULSE_OBS_DIR=${SP2_TRANSPORT_PULSE_OBS_DIR:-$OBSDIR/pulse}
FILL_OBS_DIR=${SP2_TRANSPORT_FILL_OBS_DIR:-$OBSDIR/fill}
PROJECT=${PROJECT:-P19010000}

NUDGED_CASE_NAME=${SP2_TRANSPORT_PULSE_CASE_NAME:-sp2_transport_pulse}
FREE_CASE_NAME=${SP2_TRANSPORT_FREE_CASE_NAME:-sp2_transport_free}
NUDGED_CASE="$CASE_ROOT/$NUDGED_CASE_NAME"
FREE_CASE="$CASE_ROOT/$FREE_CASE_NAME"

RUN_STARTDATE=0001-01-01
STOP_OPTION=${SP2_TRANSPORT_STOP_OPTION:-ndays}
STOP_N=${SP2_TRANSPORT_STOP_N:-2}
REST_OPTION=${SP2_TRANSPORT_REST_OPTION:-$STOP_OPTION}
REST_N=${SP2_TRANSPORT_REST_N:-$STOP_N}
NTASKS=${SP2_TRANSPORT_NTASKS:-32}
JOB_QUEUE=${SP2_TRANSPORT_JOB_QUEUE:-develop}
JOB_WALLCLOCK_TIME=${SP2_TRANSPORT_JOB_WALLCLOCK_TIME:-02:00:00}
HISTORY_NHTFRQ=${SP2_TRANSPORT_NHTFRQ:--1}
MFILT=${SP2_TRANSPORT_MFILT:-48}
EXPECTED_OBS_FILES=${SP2_TRANSPORT_EXPECTED_OBS_FILES:-16}

DRY_RUN=false
REUSE_EXISTING=false
RUN_NO_BATCH=true
SUBMIT=false

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--reuse-existing] [--setup-only] [--submit]

Prepare and run the paired SP2 transport-proof MAM4 cases:
  $NUDGED_CASE_NAME  AOD nudging on, initial pulse obs then fill-only windows
  $FREE_CASE_NAME    AOD nudging on, fill-only obs for all windows

Both cases use a separate transport-proof build root. They must not reuse the
queued July 2008 executable.

Options:
  --dry-run         Print actions without creating cases, building, or running.
  --reuse-existing  Allow existing transport case directories to be reconfigured.
  --setup-only      Prepare and build cases, but do not launch them.
  --submit          Submit both cases to PBS instead of running foreground no-batch.
  -h, --help        Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --reuse-existing) REUSE_EXISTING=true ;;
    --setup-only) RUN_NO_BATCH=false ;;
    --submit)
      RUN_NO_BATCH=false
      SUBMIT=true
      ;;
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

guard_case_names() {
  case "$NUDGED_CASE_NAME $FREE_CASE_NAME" in
    *sp2_200807*)
      echo "Transport case names must be separate development names, not submitted month-run names." >&2
      exit 2
      ;;
  esac
}

ensure_obs_files() {
  local dir=$1
  local label=$2
  local count
  count=$(find "$dir" -maxdepth 1 -type f -name 'MODIS_VIIRS_AOD_3hr_f09.*.nc' | wc -l)
  if [[ "$count" -lt "$EXPECTED_OBS_FILES" ]]; then
    echo "Expected at least $EXPECTED_OBS_FILES $label obs files under $dir; found $count" >&2
    echo "Run sp2_tests/make_transport_pulse_obs.py for both pulse and fill directories first." >&2
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
    echo "Reusing existing transport pulse case: $NUDGED_CASE"
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
    echo "Reusing existing transport free case: $FREE_CASE"
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
    /^! BEGIN SP2 transport proof block$/ {skip=1; next}
    /^! END SP2 transport proof block$/ {skip=0; next}
    !skip {print}
  ' "$user_nl" > "$tmp"
  cat "$tmp" > "$user_nl"
  rm -f "$tmp"
}

write_transport_user_nl() {
  local case_dir=$1
  local obs_dir=$2
  local user_nl="$case_dir/user_nl_cam"
  if "$DRY_RUN"; then
    echo "Would write SP2 transport user_nl_cam block to $user_nl"
    return
  fi
  strip_sp2_block "$user_nl"
  cat >> "$user_nl" <<EOF
! BEGIN SP2 transport proof block
aod_nudge_on = .true.
aod_obs_path = '${obs_dir}/'
aod_obs_template = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
aod_times_per_day = 8
aod_diag_on = .true.
empty_htapes = .true.
fincl1 = 'AODNDG_OBS','AODNDG_MODEL_PRE','AODNDG_MODEL_POST','AODNDG_RATIO','AODNDG_MASK','AODVIS'
iradsw = -1
nhtfrq = ${HISTORY_NHTFRQ}
mfilt = ${MFILT}
! END SP2 transport proof block
EOF
}

configure_case_xml() {
  local case_dir=$1

  run_in_case "$case_dir" ./xmlchange \
    RUN_STARTDATE="$RUN_STARTDATE",STOP_OPTION="$STOP_OPTION",STOP_N="$STOP_N",REST_OPTION="$REST_OPTION",REST_N="$REST_N",DOUT_S=FALSE,CONTINUE_RUN=FALSE,RESUBMIT=0,JOB_QUEUE="$JOB_QUEUE",JOB_WALLCLOCK_TIME="$JOB_WALLCLOCK_TIME"
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

patch_no_batch_mpirun() {
  local case_dir=$1
  if "$DRY_RUN"; then
    echo "+ cd $(printf '%q' "$case_dir") && patch env_mach_specific.xml for no-batch mpiexec"
    return
  fi
  local tmp
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
  ' "$case_dir/env_mach_specific.xml" > "$tmp"
  cat "$tmp" > "$case_dir/env_mach_specific.xml"
  rm -f "$tmp"
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
    echo "+ cd $(printf '%q' "$FREE_CASE") && verify shared transport cesm.exe && ./xmlchange BUILD_COMPLETE=TRUE"
    return
  fi

  exeroot=$(cd "$FREE_CASE" && ./xmlquery --value EXEROOT)
  if [[ ! -x "$exeroot/cesm.exe" ]]; then
    echo "Transport free clone EXEROOT does not contain an executable: $exeroot/cesm.exe" >&2
    exit 2
  fi
  (cd "$FREE_CASE" && ./xmlchange BUILD_COMPLETE=TRUE)
}

clean_history() {
  local case_dir=$1
  local case_name=$2
  if "$DRY_RUN"; then
    echo "+ remove stale history from $case_dir run directory"
    return
  fi
  local rundir
  rundir=$(cd "$case_dir" && ./xmlquery --value RUNDIR)
  rm -f "$rundir"/"$case_name".cam.h0*.nc
}

launch_case() {
  local case_dir=$1
  if "$RUN_NO_BATCH"; then
    run_in_case "$case_dir" ./case.submit --no-batch
  elif "$SUBMIT"; then
    run_in_case "$case_dir" ./case.submit
  else
    echo "Prepared $case_dir; launch with: cd $case_dir && ./case.submit --no-batch"
  fi
}

guard_case_names
require_path "$CESM/cime/scripts/create_newcase" "CESM create_newcase"
require_path "$CESM/cime/scripts/create_clone" "CESM create_clone"
require_path "$REPO/scripts/sp2_deploy.sh" "SP2 deploy script"
require_path "$PULSE_OBS_DIR" "transport pulse observation directory"
require_path "$FILL_OBS_DIR" "transport fill observation directory"
ensure_obs_files "$PULSE_OBS_DIR" "pulse"
ensure_obs_files "$FILL_OBS_DIR" "fill"
ensure_case_absent_or_reusable "$NUDGED_CASE"
ensure_case_absent_or_reusable "$FREE_CASE"

run "$REPO/scripts/sp2_deploy.sh"

create_nudged_case
run "$REPO/scripts/sp2_deploy.sh" "$NUDGED_CASE"
configure_case_xml "$NUDGED_CASE"
write_transport_user_nl "$NUDGED_CASE" "$PULSE_OBS_DIR"
if "$RUN_NO_BATCH"; then
  patch_no_batch_mpirun "$NUDGED_CASE"
fi
run_in_case "$NUDGED_CASE" ./check_input_data --download
build_case_conda_free "$NUDGED_CASE"
run_in_case "$NUDGED_CASE" ./preview_namelists --component atm
clean_history "$NUDGED_CASE" "$NUDGED_CASE_NAME"

create_free_case
run "$REPO/scripts/sp2_deploy.sh" "$FREE_CASE"
configure_case_xml "$FREE_CASE"
write_transport_user_nl "$FREE_CASE" "$FILL_OBS_DIR"
if "$RUN_NO_BATCH"; then
  patch_no_batch_mpirun "$FREE_CASE"
fi
run_in_case "$FREE_CASE" ./check_input_data --download
mark_free_clone_build_complete
run_in_case "$FREE_CASE" ./preview_namelists --component atm
clean_history "$FREE_CASE" "$FREE_CASE_NAME"

launch_case "$NUDGED_CASE"
launch_case "$FREE_CASE"
