#!/usr/bin/env bash
# Shared field/option IDs for the etymyriad GitHub Project (#4, van-riper).
# Sourced by the other scripts in this folder; not run directly.

PROJECT_NUM=4
OWNER=van-riper
PROJECT_ID=PVT_kwHOA9qC1c4BdaBy

STATUS_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhX7yZY
PRIORITY_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYBMOM
AREA_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYATPI
PHASE_FIELD=PVTSSF_lAHOA9qC1c4BdaByzhYAT4Y

declare -A STATUS=(
  [backlog]=4538b7fa [todo]=f75ad846
  [in-progress]=47fc9ee4 [done]=98236657
)
declare -A PRIORITY=( [high]=596255b5 [medium]=c7eff115 [low]=647e2fc9 )
declare -A AREA=( [etl]=ae60e295 [web]=c5c838f4 [db]=60184dbb [docs]=481a6113 )
declare -A PHASE=(
  [1]=b9b7a6b2 [2]=dc009842 [3]=3b57ef55
  [4]=4aaa199f [5]=96259b6e [6]=866b5bde [cross]=9c9ece2f
)
