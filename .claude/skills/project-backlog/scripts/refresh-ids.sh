#!/usr/bin/env bash
# Usage: refresh-ids.sh
# Prints current field/option IDs - run when an item-edit call fails with
# a "not found" error, meaning a field was deleted/recreated. Update
# project-backlog.conf.sh and SKILL.md's ID table by hand from the result.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json
