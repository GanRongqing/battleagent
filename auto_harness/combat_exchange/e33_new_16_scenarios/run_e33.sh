#!/usr/bin/env bash
cd /root/autodl-tmp/hsystem || exit 1
EPISODE_ID=e33_all AREA_TRACE=/tmp/opencode/e33_area_all.jsonl SAFETY_TRACE=/tmp/opencode/e33_safety_all.jsonl \
LIFECYCLE_HANDOFF_V1=0 OBS_TI_REVIVE=0 TARGET_LIFECYCLE_V2=0 \
/root/miniconda3/envs/hsystem_env/bin/python -u auto_harness/evaluation/parallel_runner/parallel_runner.py \
  --strategies N01,N02,N03,N04,N05,N06,N07,N08,N09,N10,N11,N12,N13,N14,N15,N16 \
  --seeds 43001 --policies C31 --workers 3 --epoch E33 --run-id e33_all --max-attempts 2
