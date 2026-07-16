#!/usr/bin/env bash
# Usage: create-item.sh <title> <body> [priority] [target]
# Always creates the item as Status: Open. priority/target default to
# low/later if omitted.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

title="$1"
body="$2"
priority="${3:-low}"
target="${4:-later}"

id=$(gh project item-create "$PROJECT_NUM" --owner "$OWNER" \
  --title "$title" --body "$body" --format json | jq -r '.id')

gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
  --field-id "$STATUS_FIELD" --single-select-option-id "${STATUS[open]}"
gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
  --field-id "$PRIORITY_FIELD" --single-select-option-id "${PRIORITY[$priority]}"
gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
  --field-id "$TARGET_FIELD" --single-select-option-id "${TARGET[$target]}"

echo "$id"
