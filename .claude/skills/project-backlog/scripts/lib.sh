#!/usr/bin/env bash
# Loads etymyriad's project-backlog config and exposes it to the other
# scripts in this folder. The actual project number/owner/field IDs live
# in project-backlog.conf.sh at the repo root, not here - this file is
# meant to be reusable if project-backlog is ever published as its own
# plugin, so it carries no consumer-specific values.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
source "$repo_root/project-backlog.conf.sh"
