#!/usr/bin/env bash
# run_both.sh - capture BASE and the current checkout in isolation, then compare.
#
#   .claude/skills/regression-check/scripts/run_both.sh [BASE_REF] [OUT_DIR]
#
# BASE_REF defaults to origin/main (falls back to main). OUT_DIR defaults to a
# temp dir. BASE is checked out into a git worktree so the original code runs
# untouched; each capture uses its own fresh database (capture.py does that).
# The committed baseline in tests/baselines is NOT modified.
#
# Exit codes: 0 no differences; 1 differences; other = setup failure.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git rev-parse --show-toplevel)"
BASE_REF="${1:-}"
OUT="${2:-$(mktemp -d -t regression-check-XXXX)}"
CFG="$REPO/regression-check.yml"

if [[ -z "$BASE_REF" ]]; then
  if git -C "$REPO" rev-parse --verify -q origin/main >/dev/null; then BASE_REF=origin/main; else BASE_REF=main; fi
fi
[[ -f "$CFG" ]] || { echo "no regression-check.yml at repo root" >&2; exit 2; }

WT="$OUT/base-worktree"
echo "base      : $BASE_REF"
echo "candidate : $(git -C "$REPO" rev-parse --abbrev-ref HEAD) ($(git -C "$REPO" rev-parse --short HEAD))"
echo "output    : $OUT"
echo

git -C "$REPO" worktree add --detach -q "$WT" "$BASE_REF"
trap 'git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true' EXIT

# The base side must run with ITS OWN config and code; if base predates the
# config, fall back to the candidate's config against the base checkout.
BASE_CFG="$WT/regression-check.yml"; [[ -f "$BASE_CFG" ]] || BASE_CFG="$CFG"

python3 "$HERE/capture.py" --config "$BASE_CFG" --repo-root "$WT" --out "$OUT/base" --label "base:$BASE_REF"
python3 "$HERE/capture.py" --config "$CFG" --repo-root "$REPO" --out "$OUT/candidate" --label "candidate:$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
echo
set +e
python3 "$HERE/compare.py" --baseline "$OUT/base" --candidate "$OUT/candidate" --config "$CFG" --json "$OUT/report.json"
RC=$?
set -e
echo
echo "report: $OUT/report.json"
exit $RC
