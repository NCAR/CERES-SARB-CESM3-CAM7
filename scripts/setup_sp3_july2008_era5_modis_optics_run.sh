#!/usr/bin/env bash
set -euo pipefail

CESM=${SP3_CESM:-/glade/work/fillmore/CESM3/cesm3_0_beta08}
CASE_ROOT=${SP3_CASE_ROOT:-/glade/work/fillmore/CESM3/cases}
BASE_CASE=${SP3_BASE_CASE:-$CASE_ROOT/sp3_verify10_aodnudged}
CASE_NAME=${SP3_CASE_NAME:-sp3_200807_mam4_modis_era5_optics}
CASE_DIR="$CASE_ROOT/$CASE_NAME"
RUN_ROOT=${SP3_RUN_ROOT:-/glade/derecho/scratch/fillmore/$CASE_NAME}
RUNDIR="$RUN_ROOT/run"
OPTICS_DIR="$RUN_ROOT/optics"
OBS_DIR=${SP3_OBS_DIR:-/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/}
ERA5_DIR=${SP3_ERA5_DIR:-/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl/}
LUT_FILE=${SP3_LUT_FILE:-/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lfl_lut_mam4_camref_dense3_20260709.nc}
LW_TABLE=${SP3_LW_TABLE:-/glade/work/fillmore/Data/CERES-SARB-CAM7/optics/aod_lw_omega_g.nc}
PROJECT=${PROJECT:-P19010000}

DRY_RUN=false
REUSE_EXISTING=false
SUBMIT=false

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--reuse-existing] [--submit]

Prepare a full July 2008 f09/L32 CAM7 case with:
  - ERA5 meteorological nudging of U, V, T, and Q
  - MODIS/VIIRS AOD nudging
  - 3-hourly 3-D aerosol optics for all 14 SW and 12 LW LFL bands
  - the validated dense3 CAM-reference LUT and physical LW omega/g table
  - one exclusive Derecho CPU node, 128 MPI ranks, and 235 GB RAM

The case is not submitted unless --submit is given.

Options:
  --dry-run         Print actions without creating or changing the case.
  --reuse-existing  Reconfigure an existing $CASE_NAME case.
  --submit          Submit with ./case.submit after validation.
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
  if "$DRY_RUN"; then
    printf '+ cd %q &&' "$CASE_DIR"
    printf ' %q' "$@"
    printf '\n'
  else
    (cd "$CASE_DIR" && "$@")
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

validate_inputs() {
  local aod_count
  local era5_count

  aod_count=$(find "$OBS_DIR" -maxdepth 1 -type f \
    -name 'MODIS_VIIRS_AOD_3hr_f09.200807*.nc' | wc -l)
  if [[ "$aod_count" -ne 248 ]]; then
    echo "Expected 248 July AOD files under $OBS_DIR; found $aod_count" >&2
    exit 2
  fi

  era5_count=$(find "$ERA5_DIR" -maxdepth 1 -type f \
    -name 'ERA5_fv09.cam2.i.2008-07-*.nc' | wc -l)
  if [[ "$era5_count" -ne 744 ]]; then
    echo "Expected 744 hourly July ERA5 files under $ERA5_DIR; found $era5_count" >&2
    exit 2
  fi

  require_path \
    "$ERA5_DIR/ERA5_fv09.cam2.i.2008-08-01-00000.nc" \
    "ERA5 interpolation boundary file"
}

create_case() {
  if [[ -d "$CASE_DIR" ]]; then
    if [[ "$REUSE_EXISTING" != true ]]; then
      echo "Case already exists: $CASE_DIR" >&2
      echo "Use --reuse-existing to reconfigure it intentionally." >&2
      exit 2
    fi
    echo "Reusing existing case: $CASE_DIR"
    return
  fi

  if [[ -e "$RUN_ROOT" ]]; then
    echo "Run root already exists: $RUN_ROOT" >&2
    exit 2
  fi

  run "$CESM/cime/scripts/create_clone" \
    --case "$CASE_DIR" \
    --clone "$BASE_CASE" \
    --keepexe \
    --project "$PROJECT"
}

configure_case_xml() {
  run_in_case ./xmlchange \
    RUN_TYPE=startup,GET_REFCASE=FALSE,RUN_STARTDATE=2008-07-01,STOP_OPTION=ndays,STOP_N=31,REST_OPTION=ndays,REST_N=31,DOUT_S=FALSE,CONTINUE_RUN=FALSE,RESUBMIT=0,RUNDIR="$RUNDIR"
  run_in_case ./xmlchange \
    NTASKS=128,NTHRDS=1,ROOTPE=0,MAX_TASKS_PER_NODE=128,MAX_MPITASKS_PER_NODE=128
  run_in_case ./xmlchange \
    JOB_QUEUE=main,JOB_WALLCLOCK_TIME=12:00:00,PROJECT="$PROJECT"

  if [[ -d "$CASE_DIR/Buildconf" ]]; then
    run_in_case ./case.setup --reset
  else
    run_in_case ./case.setup
  fi
}

write_user_nl() {
  local user_nl="$CASE_DIR/user_nl_cam"
  local tmp

  if "$DRY_RUN"; then
    echo "Would write combined ERA5, MODIS, and SP3 optics settings to $user_nl"
    return
  fi

  tmp=$(mktemp)
  awk '
    /^! BEGIN SP2 July 2008 ERA5 plus MODIS block$/ {skip=1; next}
    /^! END SP2 July 2008 ERA5 plus MODIS block$/ {skip=0; next}
    /^! BEGIN SP3 10-day AOD-nudged verification block$/ {skip=1; next}
    /^! END SP3 10-day AOD-nudged verification block$/ {skip=0; next}
    /^! BEGIN SP3 July 2008 ERA5 plus MODIS optics block$/ {skip=1; next}
    /^! END SP3 July 2008 ERA5 plus MODIS optics block$/ {skip=0; next}
    !skip {print}
  ' "$user_nl" > "$tmp"
  cp "$tmp" "$user_nl"
  rm -f "$tmp"

  cat >> "$user_nl" <<EOF
! BEGIN SP3 July 2008 ERA5 plus MODIS optics block
Nudge_Model = .true.
Nudge_Path = '${ERA5_DIR}'
Nudge_File_Template = 'ERA5_fv09.cam2.i.%y-%m-%d-%s.nc'
Nudge_Force_Opt = 0
Nudge_TimeScale_Opt = 0
Nudge_Times_Per_Day = 24
Model_Times_Per_Day = 48
Nudge_Uprof = 1
Nudge_Ucoef = 0.25
Nudge_Vprof = 1
Nudge_Vcoef = 0.25
Nudge_Tprof = 1
Nudge_Tcoef = 0.25
Nudge_Qprof = 1
Nudge_Qcoef = 0.25
Nudge_PSprof = 0
Nudge_PScoef = 0.00
Nudge_Beg_Year = 2008
Nudge_Beg_Month = 7
Nudge_Beg_Day = 1
Nudge_End_Year = 2008
Nudge_End_Month = 8
Nudge_End_Day = 1
Nudge_Hwin_lat0 = 0.0
Nudge_Hwin_latWidth = 9999.
Nudge_Hwin_latDelta = 1.
Nudge_Hwin_lon0 = 180.
Nudge_Hwin_lonWidth = 9999.
Nudge_Hwin_lonDelta = 1.
Nudge_Hwin_Invert = .false.
Nudge_Vwin_Hindex = 33.
Nudge_Vwin_Hdelta = 0.001
Nudge_Vwin_Lindex = 0.
Nudge_Vwin_Ldelta = 0.1
Nudge_Vwin_Invert = .false.

aod_nudge_on = .true.
aod_obs_path = '${OBS_DIR}'
aod_obs_template = 'MODIS_VIIRS_AOD_3hr_f09.%y%m%d.%s.nc'
aod_times_per_day = 8
aod_diag_on = .true.

aod_optics_on = .true.
aod_optics_interval_hours = 3
aod_optics_outdir = '${OPTICS_DIR}'
aod_optics_band_file = ''
aod_optics_lw_table = '${LW_TABLE}'
aod_optics_method = 'lut'
aod_optics_lut_file = '${LUT_FILE}'

empty_htapes = .true.
fincl1 = 'AODVIS','AODVISdn','AODNDG_OBS','AODNDG_MODEL_PRE','AODNDG_MODEL_POST','AODNDG_RATIO','AODNDG_MASK','FSNT','FSNTC','FLNT','FLNTC','FSNS','FSNSC','FLNS','FLNSC'
iradsw = -1
nhtfrq = -3
mfilt = 248
avgflag_pertape = 'I'
! END SP3 July 2008 ERA5 plus MODIS optics block
EOF
}

verify_configuration() {
  local atm_in="$CASE_DIR/CaseDocs/atm_in"
  local run_script="$CASE_DIR/.case.run"
  local exeroot

  if "$DRY_RUN"; then
    echo "Would validate generated CAM namelist and 235 GB batch request"
    return
  fi

  exeroot=$(cd "$CASE_DIR" && ./xmlquery EXEROOT --value)
  if [[ "$exeroot" != "/glade/derecho/scratch/fillmore/sp3_lut_build/bld" ]]; then
    echo "Unexpected EXEROOT: $exeroot" >&2
    exit 2
  fi
  require_path "$exeroot/cesm.exe" "validated SP3 executable"

  rg -qi 'nudge_model[[:space:]]*=[[:space:]]*\.true\.' "$atm_in"
  rg -qi 'aod_nudge_on[[:space:]]*=[[:space:]]*\.true\.' "$atm_in"
  rg -qi 'aod_optics_on[[:space:]]*=[[:space:]]*\.true\.' "$atm_in"
  rg -qi "aod_optics_method[[:space:]]*=[[:space:]]*'lut'" "$atm_in"
  rg -Fq "$LUT_FILE" "$atm_in"
  rg -Fq "$LW_TABLE" "$atm_in"
  rg -Fq "$OPTICS_DIR" "$atm_in"
  rg -q '^#PBS .*select=1:ncpus=128:mpiprocs=128:ompthreads=1:mem=235GB' "$run_script"
}

require_path "$CESM/cime/scripts/create_clone" "CESM create_clone"
require_path "$BASE_CASE" "validated SP3 AOD-nudged base case"
require_path "$OBS_DIR" "July 2008 AOD observation directory"
require_path "$ERA5_DIR" "ERA5 meteorological analyses directory"
require_path "$LUT_FILE" "validated dense3 optics LUT"
require_path "$LW_TABLE" "physical LW omega/g table"
validate_inputs

create_case
configure_case_xml
write_user_nl
run mkdir -p "$OPTICS_DIR"
run_in_case ./check_input_data
run_in_case ./xmlchange BUILD_COMPLETE=TRUE
run_in_case ./preview_namelists --component atm
run_in_case ./preview_run
verify_configuration

if "$SUBMIT"; then
  run_in_case ./case.submit
else
  echo "Prepared and validated $CASE_DIR"
  echo "Not submitted. Submit with: cd $CASE_DIR && ./case.submit"
fi
