#!/usr/bin/env bash
# E34 fair-parity 16-scenario reproduction (C31, seed 43001, single worker, White USV radar=Black=30km)
cd /root/autodl-tmp/hsystem || exit 1
HSYSTEM_WHITE_USV_RADAR=30000 EPISODE_ID=e34_all AREA_TRACE=/tmp/opencode/e34_area.jsonl SAFETY_TRACE=/tmp/opencode/e34_safety.jsonl \
LIFECYCLE_HANDOFF_V1=0 OBS_TI_REVIVE=0 TARGET_LIFECYCLE_V2=0 \
/root/miniconda3/envs/hsystem_env/bin/python -u auto_harness/evaluation/parallel_runner/parallel_runner.py \
  --strategies F01,F02,F03,F04,F05,F06,F07,F08,F09,F10,F11,F12,F13,F14,F15,F16 \
  --seeds 43001 --policies C31 --workers 1 --epoch E34 --run-id e34_all --max-attempts 2
