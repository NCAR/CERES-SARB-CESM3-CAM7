#!/usr/bin/env bash
# Build the CESM3/CAM7 aerosol nudging deck with Tectonic and gate on
# layout errors.
#
# Usage:
#   ./build.sh                 # build, check, open in Preview
#   BUILD_NO_OPEN=1 ./build.sh # build and check only
#
# An "Overfull \vbox" means a frame overran its page and content is silently
# cropped off the bottom of the slide.
set -euo pipefail

cd "$(dirname "$0")"

TECTONIC="${TECTONIC:-$HOME/miniforge3/envs/tex/bin/tectonic}"
command -v tectonic >/dev/null 2>&1 && TECTONIC=tectonic

"$TECTONIC" -X compile main.tex --keep-logs --outdir . 2>&1 | tail -20

if grep -n "Overfull \\\\vbox" main.log; then
  echo "error: overfull vbox — a frame overruns its page" >&2
  exit 1
fi

echo "built main.pdf"

if [[ -z "${BUILD_NO_OPEN:-}" ]]; then
  open main.pdf
fi
