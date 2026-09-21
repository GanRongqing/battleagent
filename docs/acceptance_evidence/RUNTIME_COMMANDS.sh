#!/usr/bin/env bash
set -e
# Real provenance (verified run): repo root was /root/autodl-tmp/hsystem.
# Override with REPO_ROOT / PYTHON for portability.
REPO="${REPO_ROOT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
PY="${PYTHON:-python}"

# C) start backend (base_server spawns sim_servers)
cd "$REPO/hsystem/simserver"
PYTHONPATH=".:..:../simulation" setsid "$PY" -u base_server.py --simserver_num 3 < /dev/null > /tmp/opencode/simlogs/base_server.log 2>&1 &
# D) start POMDP API (:8000)
cd "$REPO/hsystem/pomdp_api"
SIM_HOST=127.0.0.1 setsid "$PY" -u main.py < /dev/null > /tmp/opencode/simlogs/pomdp_api.log 2>&1 &
sleep 18
# E) health
curl -s http://127.0.0.1:8000/health
# F) scripts
curl -s http://127.0.0.1:8000/scripts
# G) run ONE canonical W5 episode (LLM off)
cd "$REPO"
"$PY" scripts/acceptance/run_single_w5.py
# I) stop
curl -s http://127.0.0.1:8000/stop
