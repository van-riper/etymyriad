#!/usr/bin/env bash
# Usage: board-summary.sh
# Prints Status counts, then every item flagged Active, Blocked, or
# Decision - a one-call orientation dump for the start of a session.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

items=$(gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json --limit 100)

echo "== Status counts =="
echo "$items" | jq -r '.items | group_by(.status) | map({status: .[0].status, count: length}) | .[] | "\(.status): \(.count)"'

echo
echo "== Active =="
echo "$items" | jq -r '.items[] | select(.active=="Active") | "\(.title)"'

echo
echo "== Blocked =="
echo "$items" | jq -r '.items[] | select(.blocked=="Blocked") | "\(.title)"'

echo
echo "== Decision needed =="
echo "$items" | jq -r '.items[] | select(.decision=="Decision") | "\(.title)"'
