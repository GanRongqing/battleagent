# -*- coding: utf-8 -*-
"""scenario_L1 — E32 large-scale stress (White 15USV+15UAV vs Black 15USV+15UAV).
random_waypoint + fixed_frontage + enemy_oob=1.0; seed from RW_SEED_FILE. Scenario config only."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = _HERE if os.path.basename(_HERE) == "20250819TZB" \
    else os.path.join(os.path.dirname(_HERE), "sim_script", "20250819TZB")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scenario_builder import build_scenario  # noqa: E402


def _seed():
    try:
        with open(os.environ.get("RW_SEED_FILE", ""), "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 43001


def sim(**kwargs):
    return build_scenario(white_usv_count=15, white_uav_count=15,
                          black_usv_count=15, black_uav_count=15,
                          black_movement="random_waypoint", rw_seed=_seed(),
                          frontage_mode="fixed_frontage", enemy_oob_multiplier=1.0,
                          opponent_profile="B0_RANDOM", **kwargs)
