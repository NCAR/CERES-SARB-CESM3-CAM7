#!/usr/bin/env bash
set -euo pipefail

REPO=${SP2_REPO:-/glade/work/fillmore/CERES-SARB-CAM7}
CESM=${SP2_CESM:-/glade/work/fillmore/CESM3/cesm3_0_beta08}
CASE_ROOT=${SP2_CASE_ROOT:-/glade/work/fillmore/CESM3/cases}
BASE_CASE=${SP2_BASE_CASE:-$CASE_ROOT/sp2_200807_mam4_modis}
CASE_NAME=${SP2_CASE_NAME:-sp2_200807_mam4_modis_era5}
CASE_DIR="$CASE_ROOT/$CASE_NAME"
OBS_DIR=${SP2_OBS_DIR:-/glade/work/fillmore/Data/CERES-SARB-CAM7/AOD_f09_3hr/}
ERA5_DIR=${SP2_ERA5_DIR:-/glade/campaign/cgd/amp/wchapman/Nudging_ERA5/fv_L32_ncl/}
CAM_INIT_FILE=${SP2_CAM_INIT_FILE:-/glade/campaign/cesm/cesmdata/inputdata/atm/cam/inic/fv/cami-mam3_0000-01-01_0.9x1.25_L32_c141031.nc}
GRID_CHECK_PYTHON=${SP2_GRID_CHECK_PYTHON:-/glade/work/fillmore/miniforge3/envs/davinci/bin/python}
PROJECT=${PROJECT:-P19010000}

DRY_RUN=false
REUSE_EXISTING=false
SUBMIT=false

usage() {
  cat <<EOF
Usage: $0 [--dry-run] [--reuse-existing] [--submit]

Prepare a July 2008 f09/L32 CAM7 case with both:
  - ERA5 meteorological nudging of U, V, T, and Q
  - MODIS/VIIRS AOD nudging

The new case clones the built SP2 MODIS case with --keepexe. It is not submitted
unless --submit is given.

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

validate_forcing_files() {
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

validate_era5_grid() {
  "$GRID_CHECK_PYTHON" - "$ERA5_DIR/ERA5_fv09.cam2.i.2008-07-01-00000.nc" "$CAM_INIT_FILE" <<'PY'
from __future__ import annotations

import sys

import numpy as np
from netCDF4 import Dataset


era5_path, cam_init_path = sys.argv[1:]
with Dataset(era5_path) as era5, Dataset(cam_init_path) as cam:
    expected_dimensions = {"lat": 192, "lon": 288, "lev": 32, "ilev": 33}
    actual_dimensions = {
        name: len(era5.dimensions[name]) for name in expected_dimensions
    }
    if actual_dimensions != expected_dimensions:
        raise SystemExit(
            f"ERA5 grid mismatch: expected {expected_dimensions}, got {actual_dimensions}"
        )

    missing = [name for name in ("U", "V", "T", "Q", "PS") if name not in era5.variables]
    if missing:
        raise SystemExit(f"ERA5 sample is missing required fields: {missing}")

    for name in ("lat", "lon", "hyam", "hybm", "hyai", "hybi"):
        era5_values = np.asarray(era5.variables[name][:])
        cam_values = np.asarray(cam.variables[name][:])
        if era5_values.shape != cam_values.shape:
            raise SystemExit(
                f"{name} shape mismatch: ERA5 {era5_values.shape}, CAM {cam_values.shape}"
            )
        max_abs_difference = float(np.max(np.abs(era5_values - cam_values)))
        if max_abs_difference > 1.0e-12:
            raise SystemExit(
                f"{name} mismatch: maximum absolute difference {max_abs_difference}"
            )

print("Validated ERA5 f09/L32 grid against the CAM initial-condition grid")
PY
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

  run "$CESM/cime/scripts/create_clone" \
    --case "$CASE_DIR" \
    --clone "$BASE_CASE" \
    --keepexe \
    --project "$PROJECT"
}

configure_case_xml() {
  run_in_case ./xmlchange \
    RUN_TYPE=startup,GET_REFCASE=FALSE,RUN_STARTDATE=2008-07-01,STOP_OPTION=ndays,STOP_N=31,REST_OPTION=ndays,REST_N=31,DOUT_S=FALSE,CONTINUE_RUN=FALSE,RESUBMIT=0,JOB_QUEUE=main,JOB_WALLCLOCK_TIME=12:00:00

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
    echo "Would write ERA5+MODIS settings to $user_nl"
    return
  fi

  tmp=$(mktemp)
  awk '
    /^! BEGIN SP2 July 2008 month-run block$/ {skip=1; next}
    /^! END SP2 July 2008 month-run block$/ {skip=0; next}
    /^! BEGIN SP2 July 2008 ERA5 plus MODIS block$/ {skip=1; next}
    /^! END SP2 July 2008 ERA5 plus MODIS block$/ {skip=0; next}
    !skip {print}
  ' "$user_nl" > "$tmp"
  cp "$tmp" "$user_nl"
  rm -f "$tmp"

  cat >> "$user_nl" <<EOF
! BEGIN SP2 July 2008 ERA5 plus MODIS block
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
empty_htapes = .true.
fincl1 = 'AODVIS','FSNTC','AODNDG_OBS','AODNDG_MODEL_PRE','AODNDG_MODEL_POST','AODNDG_RATIO','AODNDG_MASK'
iradsw = -1
nhtfrq = -3
mfilt = 248
! END SP2 July 2008 ERA5 plus MODIS block
EOF
}

mark_build_complete() {
  local exeroot

  if "$DRY_RUN"; then
    echo "+ verify shared cesm.exe and set BUILD_COMPLETE=TRUE"
    return
  fi

  exeroot=$(cd "$CASE_DIR" && ./xmlquery --value EXEROOT)
  if [[ ! -x "$exeroot/cesm.exe" ]]; then
    echo "Shared EXEROOT does not contain an executable: $exeroot/cesm.exe" >&2
    exit 2
  fi
  run_in_case ./xmlchange BUILD_COMPLETE=TRUE
}

verify_atm_in() {
  local atm_in="$CASE_DIR/CaseDocs/atm_in"

  if "$DRY_RUN"; then
    echo "Would verify ERA5 met nudging and MODIS AOD nudging in $atm_in"
    return
  fi

  rg -qi 'nudge_model[[:space:]]*=[[:space:]]*\.true\.' "$atm_in"
  rg -qi "nudge_path[[:space:]]*=[[:space:]]*'${ERA5_DIR}'" "$atm_in"
  rg -qi "nudge_file_template[[:space:]]*=[[:space:]]*'ERA5_fv09\.cam2\.i\.%y-%m-%d-%s\.nc'" "$atm_in"
  rg -qi 'model_times_per_day[[:space:]]*=[[:space:]]*48' "$atm_in"
  rg -qi 'aod_nudge_on[[:space:]]*=[[:space:]]*\.true\.' "$atm_in"
  rg -qi "aod_obs_path[[:space:]]*=[[:space:]]*'${OBS_DIR}'" "$atm_in"
}

require_path "$CESM/cime/scripts/create_clone" "CESM create_clone"
require_path "$BASE_CASE" "built SP2 MODIS base case"
require_path "$OBS_DIR" "July 2008 AOD observation directory"
require_path "$ERA5_DIR" "ERA5 meteorological analyses directory"
require_path "$CAM_INIT_FILE" "CAM f09/L32 initial-condition file"
require_path "$GRID_CHECK_PYTHON" "Python for ERA5 grid validation"
validate_forcing_files
validate_era5_grid

create_case
configure_case_xml
write_user_nl
run_in_case ./check_input_data
mark_build_complete
run_in_case ./preview_namelists --component atm
verify_atm_in

if "$SUBMIT"; then
  run_in_case ./case.submit
else
  echo "Prepared and validated $CASE_DIR"
  echo "Not submitted. Submit with: cd $CASE_DIR && ./case.submit"
fi
