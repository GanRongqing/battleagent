# -*- coding: utf-8 -*-
"""scenario_20v20 —— 20v20: 每方 10 USV + 10 UAV（薄 wrapper，数量即配置）。"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = _HERE if os.path.basename(_HERE) == "20250819TZB" \
    else os.path.join(os.path.dirname(_HERE), "sim_script", "20250819TZB")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scenario_builder import build_scenario  # noqa: E402


def sim(**kwargs):
    return build_scenario(white_usv_count=10, white_uav_count=10,
                          black_usv_count=10, black_uav_count=10, **kwargs)
