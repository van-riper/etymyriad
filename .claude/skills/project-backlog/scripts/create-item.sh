#!/usr/bin/env bash
# Usage: create-item.sh <title> <body> [status] [priority] [area] [phase]
# status/priority/area/phase are keys into lib.sh's maps; each defaults to
# backlog/low/docs/cross if omitted. Prints the new item id.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

title="$1"
body="$2"
status="${3:-backlog}"
priority="${4:-low}"
area="${5:-docs}"
phase="${6:-cross}"

id=$(gh project item-create "$PROJECT_NUM" --owner "$OWNER" \
  --title "$title" --body "$body" --format json | jq -r '.id')

gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
  --field-id "$STATUS_FIELD" --single-select-option-id "${STATUS[$status]}"
gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
  --field-id "$PRIORITY_FIELD" --single-select-option-id "${PRIORITY[$priority]}"
gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
  --field-id "$AREA_FIELD" --single-select-option-id "${AREA[$area]}"
gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
  --field-id "$PHASE_FIELD" --single-select-option-id "${PHASE[$phase]}"

echo "$id"
