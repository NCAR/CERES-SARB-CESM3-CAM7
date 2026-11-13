#!/usr/bin/env bash
# Collect raw evidence for one month of the RSES monthly technical progress report.
#
#   gather_activity.sh 2026-08 [--no-fetch]
#
# Scans every branch (local AND remote-tracking) of each project repo, because
# the month's work is routinely on a branch that is not checked out locally.
# Read-only: it fetches and reads history, and never writes to a repo.
#
# Repos are located relative to this repo's parent directory, so the script works
# unchanged on the laptop (~/EarthSystem/...) and on derecho (/glade/work/fillmore/...).
# Override with:  RSES_REPOS="/path/a /path/b" gather_activity.sh 2026-08

set -uo pipefail

MONTH="${1:-}"
FETCH=1
[ "${2:-}" = "--no-fetch" ] && FETCH=0

if ! printf '%s' "$MONTH" | grep -qE '^[0-9]{4}-(0[1-9]|1[0-2])$'; then
  echo "usage: $(basename "$0") YYYY-MM [--no-fetch]" >&2
  exit 2
fi

# Repo root via git, so this works whether the script is reached through
# skills/<name>/scripts/ or the .claude/skills/<name> symlink.
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null) || REPO_ROOT=$(cd -- "$SCRIPT_DIR/../../.." && pwd)
PARENT=$(dirname -- "$REPO_ROOT")
REPOS="${RSES_REPOS:-$REPO_ROOT $PARENT/CERES-MIP $PARENT/DAVINCI}"

# Window: [YYYY-MM-01, next month-01).  10# forces base-10 so 08/09 don't parse as octal.
Y=${MONTH%-*}; M=${MONTH#*-}
if [ "$((10#$M))" -eq 12 ]; then NEXT="$((Y + 1))-01-01"; else NEXT="$Y-$(printf '%02d' "$((10#$M + 1))")-01"; fi
SINCE="$MONTH-01"

echo "======================================================================"
echo "RSES ACTIVITY EVIDENCE   window: $SINCE 00:00 .. $NEXT 00:00 (exclusive)"
echo "generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "======================================================================"

for D in $REPOS; do
  NAME=$(basename "$D")
  echo
  echo "##################### $NAME"
  echo "# path: $D"

  if [ ! -d "$D" ]; then
    echo "# NOT FOUND on this machine - skipped (its work is invisible to this run; say so)"
    continue
  fi
  if [ ! -d "$D/.git" ]; then
    echo "# NOT A GIT REPOSITORY - skipped"
    continue
  fi

  if [ "$FETCH" -eq 1 ]; then
    if git -C "$D" fetch --all --tags --quiet 2>/dev/null; then
      echo "# fetch: ok (remote branches are current)"
    else
      echo "# fetch: FAILED or no remote - local refs may be stale; say so in the report step"
    fi
  else
    echo "# fetch: skipped (--no-fetch) - local refs may be stale"
  fi

  echo "# checked-out branch: $(git -C "$D" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  echo "# refs by recency:"
  git -C "$D" for-each-ref --sort=-committerdate \
      --format='#   %(committerdate:short)  %(refname:short)' refs/heads refs/remotes 2>/dev/null | head -12

  N=$(git -C "$D" log --all --since="$SINCE" --until="$NEXT" --oneline 2>/dev/null | wc -l | tr -d ' ')
  echo
  echo "--- commits in window across all refs: $N"
  if [ "$N" -gt 0 ]; then
    # Oldest first: the month then reads as a narrative.
    git -C "$D" log --all --reverse --since="$SINCE" --until="$NEXT" \
        --date=short --format='%ad  %h  %s%n            refs: %D' 2>/dev/null \
      | sed '/refs: *$/d'
  fi

  echo
  echo "--- merge commits in window (integration points)"
  git -C "$D" log --all --merges --reverse --since="$SINCE" --until="$NEXT" \
      --date=short --format='%ad  %h  %s' 2>/dev/null | sed 's/^/    /'

  echo
  echo "--- tags created in window (releases / citable artifacts)"
  git -C "$D" for-each-ref --sort=creatordate \
      --format='%(creatordate:short)  %(refname:short)  %(subject)' refs/tags 2>/dev/null \
    | awk -v s="$SINCE" -v e="$NEXT" '$1 >= s && $1 < e' | sed 's/^/    /'

  echo
  echo "--- areas touched (top-level dir / file, by number of commits)"
  git -C "$D" log --all --since="$SINCE" --until="$NEXT" --name-only --format='' 2>/dev/null \
    | sed '/^$/d' | awk -F/ 'NF>1{print $1"/"$2} NF==1{print $1}' \
    | sort | uniq -c | sort -rn | head -15 | sed 's/^/    /'

  echo
  echo "--- volume"
  git -C "$D" log --all --since="$SINCE" --until="$NEXT" --shortstat --format='' 2>/dev/null \
    | awk '{for(i=1;i<=NF;i++){if($(i+1)~/^file/)f+=$i; if($(i+1)~/^insert/)a+=$i; if($(i+1)~/^delet/)d+=$i}}
           END{printf "    %d files changed, %d insertions(+), %d deletions(-)\n", f, a, d}'
done

echo
echo "======================================================================"
echo "REMINDER: git shows only what was committed to these repos."
echo "Model runs on derecho, submitted abstracts, releases, reviews, meetings"
echo "and blockers leave no commit. Ask the user before drafting."
echo "======================================================================"
