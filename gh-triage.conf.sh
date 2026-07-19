#!/usr/bin/env bash
# Consumer-specific config for the gh-triage skill. Copy this file
# to your repo root as gh-triage.conf.sh and fill in the values
# below for your GitHub Project (v2). Nothing here is secret - these are
# project/field/option IDs, not credentials - so it's safe to commit.
#
# Bootstrapping the values:
#   1. Pick a short PROJECT_KEY (your ticket prefix, e.g. ABC) and set
#      PROJECT_NUM/OWNER/PROJECT_ID from your project's URL and
#      `gh project view <num> --owner <owner> --format json`.
#   2. Run scripts/refresh-ids.sh (needs PROJECT_NUM/OWNER set) to print
#      every field and its option IDs, then fill in the *_FIELD variables
#      and the option maps below from that output.

PROJECT_KEY=ETYM
PROJECT_NUM=4
OWNER=van-riper
PROJECT_ID=PVT_kwHOA9qC1c4BdaBy

STATUS_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhX7yZY
TYPE_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYUwZM
EFFORT_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYUwbs
EPIC_FIELD=PVTF_lAHOA9qC1c4BdaByzhYVMa0

declare -A STATUS=(
  [backlog]=4440993c [ready]=a9b4fcea [blocked]=32d65a5c
  [in_progress]=9d932a43 [done]=98236657
)
declare -A TYPE=(
  [story]=776fdcca [bug]=ec8f70a1 [task]=cc2236e3
  [spike]=285edc9e [epic]=77dac0a4
)
declare -A EFFORT=(
  [xs]=8775bdad [s]=4c8efbef [m]=e2d6e0e3
  [l]=23006dce [xl]=9d1b561e [xxl]=96596e72
)
