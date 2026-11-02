#!/usr/bin/env bash
# E31 final acceptance reproduction (13 scenarios, C31, seed 43001)
cd /root/autodl-tmp/hsystem || exit 1
EPISODE_ID=e31_full_on AREA_TRACE=/tmp/opencode/e31_area_on.jsonl SAFETY_TRACE=/tmp/opencode/e31_safety_on.jsonl \
LIFECYCLE_HANDOFF_V1=0 OBS_TI_REVIVE=0 TARGET_LIFECYCLE_V2=0 \
/root/miniconda3/envs/hsystem_env/bin/python -u auto_harness/evaluation/parallel_runner/parallel_runner.py \
  --strategies W2-1,W2-2,W2-3,W2-4,W2-5,W2-6,S10,S15,S20,S30,S10RW,EXTD,EXTT \
  --seeds 43001 --policies C31 --workers 3 --epoch E31 --run-id e31_full_on --max-attempts 2
