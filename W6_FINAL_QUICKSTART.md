# W6 Final Quick Start
Environment: Python /root/miniconda3/envs/hsystem_env/bin/python; sim services via
`bash /tmp/opencode/start_services.sh` (HTTP 127.0.0.1:8000).
Run W6 (deliverable = dev3, decoupled, legacy execution):
```
cd /root/autodl-tmp/hsystem
printf "4001 5 5 10 0 fixed_frontage 1.0 B3_ADAPTIVE" > /tmp/opencode/rw_cfg.txt
SCENARIO_SCRIPT=scenario_composition LLM_ENABLED=false \
W6_ANTI_EVASION=1 W6_MODE=dev3 \
/root/miniconda3/envs/hsystem_env/bin/python agent_hybrid_w6.py --uavs
```
Return to W5: omit W6_ANTI_EVASION (or run agent_hybrid_v5.py directly).
Smoke/units: python test_w6_units.py && python test_w6_dev3_units.py
Manifest: W6_FINAL_MANIFEST.json
