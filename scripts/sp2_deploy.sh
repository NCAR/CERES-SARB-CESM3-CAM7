#!/usr/bin/env bash
# Deploy the SP2/SP3 CAM source from the repo mirror into a CAM checkout.
# Usage: sp2_deploy.sh [CASEROOT]
#   - Always copies the SP2/SP3 modules + the two namelist XMLs into the CAM src tree.
#   - Applies build-namelist.diff, runtime_opts.F90.diff, physpkg.F90.diff,
#     physics_cam_CMakeLists.txt.diff, and aerosol_optics_cam.F90.diff
#     (skips if already applied).
#   - If CASEROOT is given, also overlays the four modules into SourceMods/src.cam.
set -euo pipefail

REPO=/glade/work/fillmore/CERES-SARB-CAM7
CAM=/glade/work/fillmore/CESM3/cesm3_0_beta08/components/cam
SRC="$CAM/src/physics/cam"
TESTDIR="$CAM/test/unit/aod_nudging"
NLDIR="$CAM/bld/namelist_files"
CASEROOT="${1:-}"

MODULES="aod_nudging_kernel.F90 aod_nudging_optics.F90 aod_nudging_obs.F90 aod_nudging_intr.F90 aod_optics_kernel.F90 aod_optics_lut_kernel.F90 aod_optics_lut_tables.F90 aod_optics_lut.F90 aod_optics_bands.F90 aod_optics_tap.F90 aod_optics_io.F90 aod_optics_diag_intr.F90"

for m in $MODULES; do
  if [ -f "$REPO/src/cam/$m" ]; then
    cp -v "$REPO/src/cam/$m" "$SRC/$m"
  else
    echo "WARN: $REPO/src/cam/$m not present yet (skipping)"
  fi
done

if [ -f "$REPO/src/cam/test/CMakeLists.txt" ]; then
  cp -v "$REPO/src/cam/test/CMakeLists.txt" "$TESTDIR/CMakeLists.txt"
fi
if [ -f "$REPO/src/cam/test/test_aod_optics_kernel.pf" ]; then
  cp -v "$REPO/src/cam/test/test_aod_optics_kernel.pf" "$TESTDIR/test_aod_optics_kernel.pf"
fi
if [ -f "$REPO/src/cam/test/test_aod_optics_lut_kernel.pf" ]; then
  cp -v "$REPO/src/cam/test/test_aod_optics_lut_kernel.pf" "$TESTDIR/test_aod_optics_lut_kernel.pf"
fi

for x in namelist_definition.xml namelist_defaults_cam.xml; do
  if [ -f "$REPO/src/cam/namelist/$x" ]; then
    cp -v "$REPO/src/cam/namelist/$x" "$NLDIR/$x"
  fi
done

apply_diff() {  # $1 = diff file, $2 = target (rel to $CAM)
  local d="$1" t="$2"
  [ -f "$REPO/src/cam/$d" ] || { echo "WARN: $d not present yet (skipping)"; return 0; }
  if git -C "$CAM" apply --reverse --check "$REPO/src/cam/$d" 2>/dev/null; then
    echo "SKIP: $d already applied to $t"
  elif git -C "$CAM" apply --check "$REPO/src/cam/$d" 2>/dev/null; then
    git -C "$CAM" apply "$REPO/src/cam/$d" && echo "APPLIED: $d -> $t"
  elif patch_postimage_present "$d" "$t"; then
    echo "SKIP: $d changes already present in $t"
  else
    echo "ERROR: $d does not apply cleanly to $t (manual merge needed)"
    return 1
  fi
}

patch_postimage_present() {  # $1 = diff file, $2 = target (rel to $CAM)
  local d="$1" t="$2" line status=0 tmp_added tmp_removed
  [ -f "$CAM/$t" ] || return 1
  tmp_added=$(mktemp)
  tmp_removed=$(mktemp)
  awk '/^\+\+\+ / { next } /^\+/ { line=substr($0,2); if (line != "") print line }' \
    "$REPO/src/cam/$d" > "$tmp_added"
  awk '/^--- / { next } /^-/ { line=substr($0,2); if (line != "") print line }' \
    "$REPO/src/cam/$d" > "$tmp_removed"
  [ -s "$tmp_added" ] || { rm -f "$tmp_added" "$tmp_removed"; return 1; }

  while IFS= read -r line; do
    if grep -Fqx "$line" "$CAM/$t"; then
      rm -f "$tmp_added" "$tmp_removed"
      return 1
    fi
  done < "$tmp_removed"

  awk '
    NR == FNR { want[++n] = $0; next }
    i < n && $0 == want[i + 1] { i++ }
    END { exit !(n > 0 && i == n) }
  ' "$tmp_added" "$CAM/$t" || status=$?
  rm -f "$tmp_added" "$tmp_removed"
  return "$status"
}
apply_diff runtime_opts.F90.diff src/control/runtime_opts.F90
apply_diff physpkg.F90.diff       src/physics/cam7/physpkg.F90
apply_diff build-namelist.diff    bld/build-namelist
apply_diff physics_cam_CMakeLists.txt.diff src/physics/cam/CMakeLists.txt
apply_diff aerosol_optics_cam.F90.diff src/physics/cam/aerosol_optics_cam.F90

if [ -n "$CASEROOT" ]; then
  mkdir -p "$CASEROOT/SourceMods/src.cam"
  for m in $MODULES; do
    [ -f "$REPO/src/cam/$m" ] && cp -v "$REPO/src/cam/$m" "$CASEROOT/SourceMods/src.cam/$m"
  done
  echo "Overlaid modules into $CASEROOT/SourceMods/src.cam (note: build-namelist/physpkg/runtime_opts/namelist edits are NOT SourceMods-overlayable; use the CAM src tree for those)."
fi
echo "sp2_deploy: done."
