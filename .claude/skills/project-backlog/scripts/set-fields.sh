#!/usr/bin/env bash
# Usage: set-fields.sh <item-id> [status] [priority] [area] [phase]
# Pass "-" (or omit trailing args) to leave a field unchanged. Item id is
# the PVTI_... item id, not the DI_... content id.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

id="$1"
status="${2:--}"
priority="${3:--}"
area="${4:--}"
phase="${5:--}"

if [ "$status" != "-" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$STATUS_FIELD" --single-select-option-id "${STATUS[$status]}"
fi
if [ "$priority" != "-" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$PRIORITY_FIELD" \
    --single-select-option-id "${PRIORITY[$priority]}"
fi
if [ "$area" != "-" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$AREA_FIELD" --single-select-option-id "${AREA[$area]}"
fi
if [ "$phase" != "-" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$PHASE_FIELD" --single-select-option-id "${PHASE[$phase]}"
fi
