# -*- coding: utf-8 -*-
"""scenario_10v10_rw —— 10v10 random-waypoint variant: 每方 5 USV + 5 UAV。

只改变黑方 USV 运动路径为随机航路（种子来自 RW_SEED_FILE，每局可复现）。
黑方 combat mechanics / lock logic / radar / UAV / 胜负条件 全部与 10v10 相同。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = _HERE if os.path.basename(_HERE) == "20250819TZB" \
    else os.path.join(os.path.dirname(_HERE), "sim_script", "20250819TZB")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scenario_builder import build_scenario  # noqa: E402


def sim(**kwargs):
    return build_scenario(white_usv_count=5, white_uav_count=5,
                          black_usv_count=5, black_uav_count=5,
                          black_movement="random_waypoint", **kwargs)
