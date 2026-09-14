# -*- coding: utf-8 -*-
"""scenario_10v10 —— 10v10: 每方 5 USV + 5 UAV（薄 wrapper，数量即配置）。"""
import os
import sys

# temp.py 被写到 simserver/ 目录，通过 __file__ 定位真实的 20250819TZB 源目录
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = _HERE if os.path.basename(_HERE) == "20250819TZB" \
    else os.path.join(os.path.dirname(_HERE), "sim_script", "20250819TZB")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scenario_builder import build_scenario  # noqa: E402


def sim(**kwargs):
    return build_scenario(white_usv_count=5, white_uav_count=5,
                          black_usv_count=5, black_uav_count=5, **kwargs)
