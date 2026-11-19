#!/usr/bin/env bash
# E32 reproduction (5 primary L1..L5 + 2 seed re-checks), C31, AREA_TRACE on
cd /root/autodl-tmp/hsystem || exit 1
PYBIN=/root/miniconda3/envs/hsystem_env/bin/python
for spec in "L1 43001" "L2 43001" "L3 43001" "L4 43001" "L5 43001" "L2 73121" "L5 73121"; do
  set -- $spec; S=$1; SEED=$2; RID=e32_${S}_${SEED}
  EPISODE_ID=$RID AREA_TRACE=/tmp/opencode/area_${RID}.jsonl SAFETY_TRACE=/tmp/opencode/safety_${RID}.jsonl \
  LIFECYCLE_HANDOFF_V1=0 OBS_TI_REVIVE=0 TARGET_LIFECYCLE_V2=0 \
  $PYBIN -u auto_harness/evaluation/parallel_runner/parallel_runner.py \
    --strategies $S --seeds $SEED --policies C31 --workers 1 --epoch E32 --run-id $RID --max-attempts 2
done
