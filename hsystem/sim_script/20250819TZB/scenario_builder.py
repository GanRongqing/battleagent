import os
import sys
import json
import socket
import argparse

import numpy as np
import pandas as pd
import collections
import matplotlib as mpl


mpl.use("Agg")
mpl.rcParams["font.sans-serif"] = ["SimHei"]
mpl.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

import simulation.algorithm as alg
import simulation.database as database
import simulation.core as core
import simulation.arsenal as asn
import simulation.utilities as utl

from simulation.core import CLASS, special_effect

# ════════════════════════════════════════════════════════════════
# scenario_builder —— 参数化场景构建器（SCALE IS CONTEXT, NOT POLICY）
#
# 兵力规模只作为输入参数进入 build_scenario()；战斗机制、黑方策略、
# 判定/API/单位命名全部与规模无关。4 个薄 wrapper（scenario_10v10.py
# / 15v15 / 20v20 / 30v30）只负责把具体数量传进来 —— 数量即"配置"。
#
# 部署: 恒定舰间距 + 居中 linspace，无硬编码 y 列表。30v30 的 15 舰墙
# (y=300k..510k @ 15km) 与原始 sim_20250819测试用例1.py 完全一致；
# 5/8/10/15 舰均不越界、无重叠。
# ════════════════════════════════════════════════════════════════

DEPLOY_Y_CENTER = 405000.0    # 原始 15 舰墙中线 (300000..510000)
DEPLOY_Y_SPACING = 15000.0    # 与原脚本一致的舰间距
DEPLOY_FRONTAGE = 60_000.0    # fixed-frontage 模式：恒定正面宽度（m）
ENEMY_X = 260000.0            # 敌方起始 x（黑方由西向东 patrol，机制不变）

_AREA_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "Demo", "任务区域.json")


def validate_composition(white_usv, white_uav, black_usv, black_uav):
    """composition 合法性检查：不 silently repair，非法即报原因。

    规则（引擎机制推导）：
      - 每艘 USV 机库最多 1 架 UAV（put_uav_in_ship 1:1）→ UAV ≤ USV（双方各自）
      - 至少 1 艘 USV
      - UAV 数量 ≥ 0
    """
    problems = []
    if white_usv < 1 or black_usv < 1:
        problems.append(f"USV count must be >= 1 (white={white_usv}, black={black_usv})")
    if white_uav < 0 or black_uav < 0:
        problems.append("UAV count must be >= 0")
    if white_uav > white_usv:
        problems.append(f"white_uav={white_uav} > white_usv={white_usv}: hangar capacity 1 UAV/USV")
    if black_uav > black_usv:
        problems.append(f"black_uav={black_uav} > black_usv={black_usv}: hangar capacity 1 UAV/USV")
    if problems:
        raise ValueError("Illegal composition: " + "; ".join(problems))
    return True


def _deploy_ys(count, frontage_mode="fixed_density"):
    """均匀纵线布阵: linspace(center-span/2, center+span/2, count)。

    - fixed_density : 恒定 15km 舰间距 → 数量增加时 frontage 变宽（secondary stress test）
    - fixed_frontage : 恒定正面宽度（DEPLOY_FRONTAGE=60km）→ 数量增加时密度增大（主实验）
    - 两种模式均无固定长度 y 列表，y ∈ [375000, 435000]（fixed_frontage）或由数量推导，
      都在任务多边形内。
    """
    if frontage_mode == "fixed_frontage":
        span = DEPLOY_FRONTAGE
    else:
        span = (count - 1) * DEPLOY_Y_SPACING
    return [float(y) for y in np.linspace(DEPLOY_Y_CENTER - span / 2.0,
                                          DEPLOY_Y_CENTER + span / 2.0,
                                          count)]


def _read_rw_seed():
    """从 seed 文件读取随机航路种子（评估 runner 每局写入）。

    - 文件路径可用环境变量 RW_SEED_FILE 覆盖，默认 /tmp/opencode/rw_seed.txt
    - 缺失/非法 → 默认 0（仍是确定性的）
    - 这只是 scenario 生成参数，白方 Agent 运行时不可见。
    """
    path = os.environ.get("RW_SEED_FILE", "/tmp/opencode/rw_seed.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _random_waypoint_paths(seed, ys):
    """为每艘黑 USV 生成带突破意图的随机航路（只改变黑方 USV 运动路径）。

    - 完全由 seed 可复现；不读取白方状态；不贴边界；不人为避开白方。
    - 总体仍是攻击型：从 x=260000 出发，经 2~5 个中间航路点（横向随机游走），
      最终冲向突破线 x=50000 方向。
    - 覆盖轻/中/明显横向机动与多次转向。
    """
    import random
    rng = random.Random(seed)
    break_line_x = 50000.0
    span = ENEMY_X - break_line_x
    y_min, y_max = 80000.0, 620000.0

    def _clamp_y(v):
        return max(y_min, min(y_max, v))

    paths = []
    for i, y0 in enumerate(ys):
        y0 = _clamp_y(y0)
        n_wp = rng.randint(2, 5)
        # 向西推进的比例（单调递增、带少量抖动），保证总体突破意图
        fracs = sorted(rng.uniform(0.15, 0.95) for _ in range(n_wp))
        path = [[ENEMY_X, y0]]
        prev_x = ENEMY_X
        y_off = 0.0
        for f in fracs:
            x_k = ENEMY_X - span * f + rng.uniform(-8000.0, 8000.0)
            x_k = max(break_line_x + 8000.0, min(prev_x - 5000.0, x_k))
            y_off += rng.uniform(-25000.0, 25000.0)
            y_k = _clamp_y(y0 + y_off)
            path.append([x_k, y_k])
            prev_x = x_k
        # 最终突破段（目标在突破线附近，途中必跨 x=50000；保证单调西进）
        x_final = max(break_line_x, min(prev_x - 8000.0,
                                        break_line_x + rng.uniform(0.0, 15000.0)))
        path.append([x_final, _clamp_y(y0 + y_off + rng.uniform(-15000.0, 15000.0))])
        paths.append(path)
    return paths


def build_scenario(white_usv_count=15, white_uav_count=15,
                   black_usv_count=15, black_uav_count=15,
                   black_movement="straight_west", rw_seed=None,
                   frontage_mode="fixed_density", enemy_oob_multiplier=1.0,
                   opponent_profile="B0_RANDOM",
                   simserver=None, engine_name='20250803水面所仿真2',
                   web_ip=None, gengtu_ip=None, user_name='admin',
                   render_config=None, checkbox_dict=None, logtag=None,
                   uav_speed=150):
    """参数化场景：任意 USV/UAV 数量。单位 ID 连续稳定（white_usv1..N）。

    frontage_mode: fixed_density（数量→frontage 变宽，secondary stress）
                 | fixed_frontage（恒定 60km 正面，数量→密度增大，主实验）。
    """
    # ── Reproducibility control (NOT a physics change) ──────────────────────
    # The engine's per-game draws (combat hit rolls in arsenal/locker.py, cosmetic
    # np.random ids, B3 perturbation noise) use the PROCESS-global RNG, which the
    # long-lived sim_server never reseeds. Without seeding, identical (seed,
    # composition) runs are NOT reproducible, invalidating any paired / same-seed
    # experiment design. We reseed here from rw_seed so every game is a deterministic
    # function of (seed, composition). No weapon/speed/sensor/damage value is touched.
    if rw_seed is not None:
        import random
        random.seed(int(rw_seed) + 1009)
        try:
            import numpy as np
            np.random.seed(int(rw_seed) + 7)
        except Exception:
            pass
    validate_composition(white_usv_count, white_uav_count,
                         black_usv_count, black_uav_count)
    flag = core.log.DECISION
    engine = core.tzb_engine.TzbEngine(engine_name, epoch=None, flag=flag,
                                       logpath=None, terminal=False,
                                       logtag=logtag, cache=True,
                                       render_config=render_config,
                                       checkbox_dict=checkbox_dict,
                                       web_ip=web_ip, user_name=user_name,
                                       simserver=simserver)

    # ========== 渲染配置 ==========
    engine.render_config.update({"name": True})
    engine.render_config.update({"lethality": False})
    engine.render_config.update({"radar": True})
    engine.render_config.update({"crosspoint": False})
    engine.render_config.update({"network_link": False})
    engine.render_config.update({"waypoints_units": "all"})

    engine.render_config.update({"target": {"rcs": 0.1, "speed": 255, "height": 20, "type_": "B-1B"}})
    engine.sim_config.update({"ignore_com": False})
    engine.sim_config.update({"earth_curvature": False})

    engine.set_end_time(600000)
    engine.set_ratio(100)  # 100x仿真（评估提速用；所有规模统一，机制一致）

    # 加载作战区域
    with open(_AREA_JSON, 'r', encoding='utf-8') as f1:
        area = json.load(f1)

    points_area = [item for i, item in area.items()]
    special_effect.StaticPolygonEffect.gen(engine, "Area", points=points_area,
                                           color='green', alpha=0, fill_alpha=0,
                                           coordinate_system="Cartesian")

    # ═══════ 我方兵力: 动态数量 ═══════
    white_ys = _deploy_ys(white_usv_count, frontage_mode)
    ships_xy = {f'white_usv{i}': [0.0, white_ys[i - 1]] for i in range(1, white_usv_count + 1)}
    uav_swarm_xy = {f'white_uav{i}': [0.0, white_ys[i - 1]] for i in range(1, white_uav_count + 1)}

    """配置白方USV参数"""
    engine.db["RadarWithGuider"]["distance"] = 35_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["Ship"]["comdev"] = "Comdev"
    engine.db["Ship"]["emitters"] = []
    engine.db["Ship"]["guiders"] = []
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]

    # 生成我方USV
    white_usvs = []
    for _i in range(1, white_usv_count + 1):
        _usv = engine.gen_platform(f'white_usv{_i}', 'Ship', 'RED',
                                   ships_xy[f'white_usv{_i}'], 10, 90,
                                   coordinate_system="Cartesian")
        white_usvs.append(_usv)

    """配置白方UAV参数"""
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["PlaneMotorTZB"]["max_speed"] = 150
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"
    engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    engine.db["AEW"]["comdev"] = "Comdev"

    # 生成我方UAV(每艘USV配1架，UAV数<=USV数)
    white_uavs = []
    for _i in range(1, white_uav_count + 1):
        _uav = engine.gen_platform(f'white_uav{_i}', 'AEW', 'RED',
                                   uav_swarm_xy[f'white_uav{_i}'], uav_speed,
                                   90, 100, coordinate_system="Cartesian")
        white_uavs.append(_uav)

    reds = white_usvs + white_uavs  # 所有红方单位

    # 星型网络(以white_usv1为中心)
    all_white_names = [f'white_usv{i}' for i in range(1, white_usv_count + 1)] \
        + [f'white_uav{i}' for i in range(1, white_uav_count + 1)]
    engine.gen_star_network("StarNetwork4", 'white_usv1', all_white_names)

    # ═══════ 敌方兵力: 动态数量 ═══════
    """配置黑方USV参数"""
    engine.db["RadarWithGuider"]["distance"] = 30_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["Ship"]["comdev"] = "Comdev"
    engine.db["Ship"]["emitters"] = []
    engine.db["Ship"]["guiders"] = []
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]

    engine.cache["num_black_usv"] = black_usv_count

    blues = []  # 所有蓝方单位
    black_usvs = []
    # 黑方使用独立 y 部署（不依赖白方数量）：支持 white≠black composition
    black_ys = _deploy_ys(black_usv_count, frontage_mode)
    # 随机航路：每局从 seed 文件读取种子，生成可复现的黑 USV 路径
    # opponent_profile: B0_RANDOM=标准随机（默认，行为不变）；B1/B2/B3/B4=opponent ladder
    _seed = None
    _auto_meta = None
    _black_speed = 10.0
    if black_movement == "random_waypoint":
        _seed = rw_seed if rw_seed is not None else _read_rw_seed()
        if opponent_profile in ("B0_RANDOM", None, ""):
            _rw_paths = _random_waypoint_paths(_seed, black_ys)
        elif opponent_profile == "B0_V2_VARIABLE_SPEED":
            import sys as _sys
            import os as _os
            import json as _json
            _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(
                _os.path.dirname(_os.path.abspath(__file__)))))
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            import opponent_b0_v2 as _b0v2
            # waypoint logic IDENTICAL to B0-v1 (same seed); only speed differs
            _rw_paths = _random_waypoint_paths(_seed, black_ys)
            _black_speed = _b0v2.sample_speed(_seed)
            print(f"[OPPONENT] profile={opponent_profile} effective=black-b0-v2 "
                  f"seed={_seed} episode_target_speed={_black_speed}", flush=True)
            try:
                with open("/tmp/opencode/b0v2_meta.json", "w", encoding="utf-8") as _f:
                    _json.dump({"requested_policy_id": "black-b0-v2",
                                "effective_policy_id": "black-b0-v2",
                                "seed": _seed, "episode_target_speed": _black_speed}, _f)
            except Exception:
                pass
        elif opponent_profile == "AUTO_FEINT_SWITCH":
            import sys as _sys
            import os as _os
            _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(
                _os.path.dirname(_os.path.abspath(__file__)))))
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            import opponent_auto_profiles as _auto
            _ngroups = max(1, (black_usv_count + 3) // 4)
            _rw_paths, _auto_meta = _auto.generate_initial_paths_auto(
                _seed, black_ys, n_groups=_ngroups)
            _auto_meta["names"] = [f"black_usv{i}" for i in range(1, black_usv_count + 1)]
        else:
            import sys as _sys
            import os as _os
            _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(
                _os.path.dirname(_os.path.abspath(__file__)))))
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            import opponent_profiles
            _opp = opponent_profiles.resolve_profile(opponent_profile, _seed)
            _rw_paths = opponent_profiles.generate_initial_paths(_opp, _seed, black_ys)
    for _i in range(1, black_usv_count + 1):
        _y = black_ys[_i - 1]
        # 敌方USV: 在x=260k, 向西巡逻
        _b = engine.gen_platform(f'black_usv{_i}', 'Ship', 'BLUE',
                                 [ENEMY_X, _y], 10, 0, coordinate_system="Cartesian")
        black_usvs.append(_b)
        blues.append(_b)
        if black_movement == "random_waypoint":
            engine.cmd_sail_area(_b, speed=_black_speed, xy_points=_rw_paths[_i - 1])
        else:
            # 向西巡逻航路点
            engine.cmd_sail_area(_b, speed=10,
                                 xy_points=[[ENEMY_X, _y], [ENEMY_X / 2.0, _y], [0.0, _y]])

    """配置黑方UAV参数(侦察)"""
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"
    engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    engine.db["AEW"]["comdev"] = "Comdev"

    # 生成敌方UAV(每艘USV配1架), 向西巡逻
    black_uavs = []
    for _i in range(1, black_uav_count + 1):
        _y = black_ys[_i - 1]
        _bu = engine.gen_platform(f'black_uav{_i}', 'AEW', 'BLUE',
                                  [ENEMY_X, _y], uav_speed, 0, 100,
                                  coordinate_system="Cartesian")
        black_uavs.append(_bu)
        blues.append(_bu)
        engine.cmd_sail_area(_bu, speed=30,
                             xy_points=[[ENEMY_X, _y], [ENEMY_X / 2.0, _y], [0.0, _y]])

    """设置裁判系统"""
    all_units = reds + blues
    judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
    judge_area = points_area + [points_area[0]]
    judge.set_area(judge_area)
    # 敌方 OOB 放宽（enemy_oob_multiplier 实验）：仅 BLUE 使用缩放后的区域
    if enemy_oob_multiplier and enemy_oob_multiplier != 1.0:
        _cx = sum(p[0] for p in points_area) / len(points_area)
        _cy = sum(p[1] for p in points_area) / len(points_area)
        _scaled = [[_cx + (p[0] - _cx) * enemy_oob_multiplier,
                    _cy + (p[1] - _cy) * enemy_oob_multiplier] for p in points_area]
        judge.set_enemy_area(_scaled + [_scaled[0]])

    def start(engine):
        """仿真启动时的初始化操作"""
        engine.turn_on_radars()
        engine.turn_on_lockers()
        for _uav in white_uavs:
            _uav.uavbattery.turn_on()
        for _bu in black_uavs:
            _bu.uavbattery.turn_on()
        judge.activate()
        for _i in range(1, white_uav_count + 1):
            engine.put_uav_in_ship(f'white_uav{_i}', f'white_usv{_i}')
    engine.set_starter(start)

    def black_strategy(engine):
        """黑方AI: USV锁定我方USV, UAV提供侦察"""
        detected = engine.get_black_targets()
        for _b_unit in black_usvs:
            for _w_unit_name in detected:
                if "usv" in _w_unit_name:
                    engine.black_cmd_lock(_b_unit.name, _w_unit_name)

    # 黑方AI每秒执行一次
    engine.add_manipulator(black_strategy, 1)

    # opponent ladder B3/B4→B3: legal adaptive waypoint replanning (Black's own radar intel)
    if black_movement == "random_waypoint" and _seed is not None \
            and opponent_profile == "AUTO_FEINT_SWITCH" and _auto_meta is not None:
        import sys as _sys
        import os as _os
        _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(
            _os.path.dirname(_os.path.abspath(__file__)))))
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        import opponent_auto_profiles as _auto
        print(f"[OPPONENT] profile={opponent_profile} resolved={_auto.AUTO} seed={_seed} "
              f"isFeintSwitch=True", flush=True)
        engine.add_manipulator(_auto.FeintSwitchController(seed=_seed, meta=_auto_meta),
                               interval=_auto.OBSERVE_INTERVAL)
        print("[OPPONENT] AUTO_FEINT_SWITCH controller registered", flush=True)
    elif black_movement == "random_waypoint" and _seed is not None \
            and opponent_profile not in ("B0_RANDOM", None, "", "B0_V2_VARIABLE_SPEED"):
        import sys as _sys
        import os as _os
        _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(
            _os.path.dirname(_os.path.abspath(__file__)))))  # project root (has opponent_profiles.py)
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        import opponent_profiles as _opp
        _resolved = _opp.resolve_profile(opponent_profile, _seed)
        print(f"[OPPONENT] profile={opponent_profile} resolved={_resolved} seed={_seed} "
              f"isB3={_resolved == _opp.B3}", flush=True)
        if _resolved == _opp.B3:
            engine.add_manipulator(_opp.B3AdaptiveController(seed=_seed),
                                   interval=_opp.B3_INTERVAL)
            print("[OPPONENT] B3 adaptive controller registered", flush=True)

    return engine


def _cli_sim(counts, uav_speed=150):
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    logtag = f'{hostname}'
    return build_scenario(*counts, logtag=logtag, uav_speed=uav_speed)
