# -*- coding: utf-8 -*-
"""scenario_15v15 —— 15v15: 每方 8 USV + 7 UAV（薄 wrapper，数量即配置）。"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = _HERE if os.path.basename(_HERE) == "20250819TZB" \
    else os.path.join(os.path.dirname(_HERE), "sim_script", "20250819TZB")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scenario_builder import build_scenario  # noqa: E402


def sim(**kwargs):
    return build_scenario(white_usv_count=8, white_uav_count=7,
                          black_usv_count=8, black_uav_count=7, **kwargs)
