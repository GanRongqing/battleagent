# -*- coding: utf-8 -*-
"""scenario_composition —— 通用 composition 场景（variable-cardinality）。

从配置文件读取每局参数：seed white_usv white_uav black_usv black_uav frontage_mode。
黑方 USV 运动 = 随机航路（seed 可复现）。只改变数量/路径，combat 机制不变。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = _HERE if os.path.basename(_HERE) == "20250819TZB" \
    else os.path.join(os.path.dirname(_HERE), "sim_script", "20250819TZB")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scenario_builder import build_scenario, validate_composition  # noqa: E402


def _read_cfg():
    path = os.environ.get("RW_CFG_FILE", "/tmp/opencode/rw_cfg.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            parts = f.read().strip().split()
        seed = int(parts[0])
        wu, wuv, bu, buv = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
        fmode = parts[5] if len(parts) > 5 else "fixed_frontage"
        oob = float(parts[6]) if len(parts) > 6 else 1.0
        profile = parts[7] if len(parts) > 7 else "B0_RANDOM"
        return seed, wu, wuv, bu, buv, fmode, oob, profile
    except Exception:
        return 1, 5, 5, 5, 5, "fixed_frontage", 1.0, "B0_RANDOM"


def sim(**kwargs):
    seed, wu, wuv, bu, buv, fmode, oob, profile = _read_cfg()
    validate_composition(wu, wuv, bu, buv)
    return build_scenario(white_usv_count=wu, white_uav_count=wuv,
                          black_usv_count=bu, black_uav_count=buv,
                          black_movement="random_waypoint", rw_seed=seed,
                          frontage_mode=fmode, enemy_oob_multiplier=oob,
                          opponent_profile=profile, **kwargs)
