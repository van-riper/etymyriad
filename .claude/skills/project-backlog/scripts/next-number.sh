#!/usr/bin/env bash
# Usage: next-number.sh
# Prints the next sequential ticket number for a new item's title prefix.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json \
  --limit 100 \
  | jq -r '.items[].title' | grep -oE '^[0-9]+' | sort -n | tail -1 \
  | awk '{print $1 + 1}'
