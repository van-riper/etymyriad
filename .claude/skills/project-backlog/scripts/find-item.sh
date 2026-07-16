#!/usr/bin/env bash
# Usage: find-item.sh <title-keyword-regex>
# Prints matching items as JSON, including .id (PVTI_...) and
# .content.id (DI_..., needed to edit title/body).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

gh project item-list "$PROJECT_NUM" --owner "$OWNER" --format json \
  --limit 100 \
  | jq --arg kw "$1" '.items[] | select(.title | test($kw; "i"))'
