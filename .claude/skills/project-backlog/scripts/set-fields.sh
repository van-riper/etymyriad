#!/usr/bin/env bash
# Usage: set-fields.sh <item-id> [status] [priority] [target] [blocked] [decision] [active]
# status: open|done|-   priority: high|medium|low|-   target: now|next|later|someday|-
# blocked/decision/active: on|off|-  ("on" sets the flag, "off" clears
# it, "-" leaves it unchanged). Pass "-" for any positional arg to skip
# it; trailing args may be omitted entirely.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

id="$1"
status="${2:--}"
priority="${3:--}"
target="${4:--}"
blocked="${5:--}"
decision="${6:--}"
active="${7:--}"

if [ "$status" != "-" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$STATUS_FIELD" --single-select-option-id "${STATUS[$status]}"
fi
if [ "$priority" != "-" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$PRIORITY_FIELD" --single-select-option-id "${PRIORITY[$priority]}"
fi
if [ "$target" != "-" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$TARGET_FIELD" --single-select-option-id "${TARGET[$target]}"
fi
if [ "$blocked" = "on" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$BLOCKED_FIELD" --single-select-option-id "${BLOCKED[blocked]}"
elif [ "$blocked" = "off" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$BLOCKED_FIELD" --clear
fi
if [ "$decision" = "on" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$DECISION_FIELD" --single-select-option-id "${DECISION[decision]}"
elif [ "$decision" = "off" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$DECISION_FIELD" --clear
fi
if [ "$active" = "on" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$ACTIVE_FIELD" --single-select-option-id "${ACTIVE[active]}"
elif [ "$active" = "off" ]; then
  gh project item-edit --project-id "$PROJECT_ID" --id "$id" \
    --field-id "$ACTIVE_FIELD" --clear
fi
