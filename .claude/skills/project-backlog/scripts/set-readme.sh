#!/usr/bin/env bash
# Usage: set-readme.sh <readme-file>
# Sets the project README from a file's contents (no --readme-file flag
# exists upstream, so this reads the file and passes it as raw text).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source ./lib.sh

readme_file="$1"

gh project edit "$PROJECT_NUM" --owner "$OWNER" --readme "$(cat "$readme_file")"
