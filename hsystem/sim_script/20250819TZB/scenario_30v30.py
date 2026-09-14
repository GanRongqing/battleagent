# -*- coding: utf-8 -*-
"""scenario_30v30 —— 30v30: 每方 15 USV + 15 UAV（薄 wrapper，数量即配置）。

与原始 sim_20250819测试用例1.py 同一兵力规模；通过统一 builder 构建，
保证四种规模共享同一套机制与部署公式。
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
    return build_scenario(white_usv_count=15, white_uav_count=15,
                          black_usv_count=15, black_uav_count=15, **kwargs)
