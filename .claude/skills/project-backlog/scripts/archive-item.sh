#!/usr/bin/env bash
# Usage: archive-item.sh <item-id>
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

gh project item-archive "$PROJECT_NUM" --owner "$OWNER" --id "$1"
