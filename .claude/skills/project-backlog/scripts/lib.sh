#!/usr/bin/env bash
# Shared field/option IDs for the etymyriad GitHub Project (#4, van-riper).
# Sourced by the other scripts in this folder; not run directly.

PROJECT_NUM=4
OWNER=van-riper
PROJECT_ID=PVT_kwHOA9qC1c4BdaBy

STATUS_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhX7yZY
PRIORITY_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYBMOM
TARGET_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYEVOc
BLOCKED_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYEVOg
DECISION_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYEVOk
ACTIVE_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYEVOo

declare -A STATUS=( [open]=4538b7fa [done]=98236657 )
declare -A PRIORITY=( [high]=596255b5 [medium]=c7eff115 [low]=647e2fc9 )
declare -A TARGET=(
  [now]=b610a379 [next]=694f47a5
  [later]=211578d0 [someday]=3925d590
)
declare -A BLOCKED=( [blocked]=2c1b1285 )
declare -A DECISION=( [decision]=07c3cda8 )
declare -A ACTIVE=( [active]=e0ea67d8 )
