"""
加载和应用仿真情景的区域、蓝方航路和红方平台配置
"""

import argparse
import ast
import json
import math
import os
import socket
from functools import partial
from pathlib import Path

from .red_formation import red_formation


ENGINE_CONFIG = {
    "end_time": 600_000,
    "ratio": int(os.environ.get("HSYSTEM_RATIO", "100")),
}
RED_FORCE_CONFIG = {
    "ship": {
        "radar_distance": 20_000,
        "radar_sector": [0, 360],
        "speed": 0,
        "course": 90,
    },
    "uav": {
        "radar_distance": 60_000,
        "radar_sector": [-30, 30],
        "course": 90,
        "height": 100,
    },
}
BLUE_FORCE_CONFIG = {
    "radar_distance": 30_000,
    "radar_sector": [0, 360],
    "course": 0,
}


def _add_candidate(candidates, candidate):
    candidate = Path(candidate).expanduser()
    if candidate not in candidates:
        candidates.append(candidate)


def scenario_directory(anchor=None, core_file=None):
    """返回真实的 ``sim_script/scenario`` 目录
    """
    candidates = []

    configured_root = os.environ.get("HSYSTEM_ROOT")
    if configured_root:
        configured_root = Path(configured_root).expanduser().resolve()
        _add_candidate(candidates, configured_root)
        _add_candidate(candidates, configured_root / "sim_script" / "scenario")

    for path in (anchor, core_file, Path.cwd()):
        if not path:
            continue
        path = Path(path).expanduser().resolve()
        for parent in (path, *path.parents):
            _add_candidate(candidates, parent)

    for candidate in candidates:
        if candidate.name != "scenario":
            candidate = candidate / "sim_script" / "scenario"
        if (candidate / "area").is_dir() and (candidate / "route").is_dir():
            return candidate

    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "未找到场景数据目录 sim_script/scenario；已搜索: " + searched
    )


def scenario_files(area_filename, route_filename, anchor=None, core_file=None):
    """解析并校验任务区域和敌方路线 JSON 文件。"""
    directory = scenario_directory(anchor=anchor, core_file=core_file)
    area_file = directory / "area" / area_filename
    route_file = directory / "route" / route_filename

    missing = [str(path) for path in (area_file, route_file) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "场景 JSON 文件不存在: " + ", ".join(missing)
        )
    return area_file, route_file


def load_scenario(area_filename, route_filename, *, anchor=None, core_file=None):
    """加载并校验一个情景的区域和蓝方航路配置。"""
    area_file, route_file = scenario_files(
        area_filename, route_filename, anchor=anchor, core_file=core_file
    )
    with area_file.open("r", encoding="utf-8-sig") as stream:
        area = json.load(stream)
    with route_file.open("r", encoding="utf-8") as stream:
        blue_waypoints = json.load(stream)

    if not isinstance(area, dict):
        raise ValueError("任务区域必须是 JSON 对象")
    for name, point in area.items():
        if not _valid_point(point):
            raise ValueError(f"任务区域点 {name} 必须是两个有限数值")

    route_keys = [
        f"usv{i}" for i in range(1, blue_waypoints["usvNum"] + 1)
    ]
    for key in route_keys:
        if key not in blue_waypoints:
            raise ValueError(f"策略文件缺少 {key}")
        route = blue_waypoints[key]
        if not isinstance(route, list) or len(route) < 2:
            raise ValueError(f"{key} 必须至少包含两个航路点")
        for index, waypoint in enumerate(route):
            if not isinstance(waypoint, dict) or not _valid_point(
                waypoint.get("point")
            ):
                raise ValueError(f"{key} 的第 {index + 1} 个航路点缺少有效 point")
            speed = waypoint.get("speed")
            if (
                not isinstance(speed, (int, float))
                or not math.isfinite(speed)
                or speed <= 0
                or speed > 10
            ):
                raise ValueError(
                    f"{key} 的速度必须位于 (0, 10] m/s：{waypoint}"
                )
    return area, blue_waypoints, route_keys


def _valid_point(point):
    return (
        isinstance(point, (list, tuple))
        and len(point) == 2
        and all(
            isinstance(value, (int, float)) and math.isfinite(value)
            for value in point
        )
    )


def configure_matplotlib():
    """设置无界面运行所需的 Matplotlib 后端。"""
    import matplotlib as mpl

    mpl.use("Agg")
    mpl.rcParams["font.sans-serif"] = ["SimHei"]
    mpl.rcParams["axes.unicode_minus"] = False


def _seed_rng():
    """Adapter (behavior-neutral): seed process RNG from a seed FILE.

    只让仿真随机分量成为 seed 的确定函数，不改变任何航路/速度/阵型/策略行为。
    与 hsystem/sim_script/20250819TZB/scenario_builder.py 的播种方式一致。
    seed 通过文件跨进程传递（评估 runner 每局写入），缺失/非法 → 默认 0。
    """
    path = os.environ.get("RW_SEED_FILE", "/tmp/opencode/rw_seed.txt")
    seed = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            seed = int(f.read().strip())
    except Exception:
        seed = 0
    import random
    import numpy as np

    random.seed(seed + 1009)
    np.random.seed(seed + 7)


def _write_runtime_identity(strategy_filename, area_filename, area, blue_waypoints, formation_mode=None):
    """Read-only E9 instrumentation: record the scenario the simulator ACTUALLY loaded.
    Writes the canonical digest of the loaded blue-waypoints so the evaluation runner can verify
    Layer-3 runtime identity (independent of the requested label). Behaviour-neutral."""
    path = os.environ.get("RUNTIME_IDENTITY_FILE")
    if not path:
        return
    try:
        import hashlib as _h
        import json as _j
        def _d(o):
            return _h.sha256(_j.dumps(o, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        rec = {"strategy_filename": strategy_filename, "area_filename": area_filename,
               "formation_mode": formation_mode,
               "route_digest": _d(blue_waypoints), "area_digest": _d(area),
               "pid": os.getpid()}
        with open(path, "w", encoding="utf-8") as f:
            _j.dump(rec, f, ensure_ascii=False)
    except Exception:
        pass


def build_simulation(
    core_module,
    *,
    engine_name,
    area_filename,
    strategy_filename,
    anchor,
    simserver=None,
    web_ip=None,
    user_name="admin",
    render_config=None,
    checkbox_dict=None,
    logtag=None,
    uav_speed=0,
    formation_mode="diamond",
):
    """构建所有方案共用的仿真流程。"""
    _seed_rng()
    area, blue_waypoints, route_keys = load_scenario(
        area_filename,
        strategy_filename,
        anchor=anchor,
        core_file=core_module.__file__,
    )
    _write_runtime_identity(strategy_filename, area_filename, area, blue_waypoints, formation_mode)
    engine = create_engine(
        core_module,
        engine_name=engine_name,
        engine_config=ENGINE_CONFIG,
        web_ip=web_ip,
        user_name=user_name,
        render_config=render_config,
        checkbox_dict=checkbox_dict,
        logtag=logtag,
        simserver=simserver,
    )
    points_area = setup_area(engine, area)
    ships_xy, uav_swarm_xy = red_formation(formation_mode)
    red_uavs, reds = create_red_force(
        engine, ships_xy, uav_swarm_xy, uav_speed, RED_FORCE_CONFIG
    )
    blue_pairs, blues = create_blue_force(
        engine, blue_waypoints, route_keys, BLUE_FORCE_CONFIG
    )
    judge = engine.gen_judge_system("JudgeSystemTZB", reds + blues)
    judge.set_area(points_area + [points_area[0]])
    engine.set_starter(make_starter(judge, red_uavs))
    add_common_manipulators(
        engine,
        blues=blues,
        blue_pairs=blue_pairs,
        blue_waypoints=blue_waypoints,
    )
    return engine


def run_simulation(simulation, description):
    """提供所有方案共用的命令行入口。"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--para", help="参数列表，例如 [150]")
    parser.add_argument("--iter", help="仿真迭代标识")
    args = parser.parse_args()
    if args.para:
        [uav_speed] = ast.literal_eval(args.para)
        kwargs = {"logtag": socket.gethostname(), "uav_speed": uav_speed}
    else:
        kwargs = {"web_ip": "127.0.0.1", "user_name": "admin", "logtag": "test"}
    engine = simulation(**kwargs)
    engine.activate()
    engine.update()


def create_engine(
    core_module,
    *,
    engine_name,
    engine_config,
    web_ip,
    user_name,
    render_config,
    checkbox_dict,
    logtag,
    simserver,
):
    """创建并应用所有情景共用的仿真引擎配置。"""
    engine = core_module.tzb_engine.TzbEngine(
        engine_name,
        epoch=None,
        flag=core_module.log.DECISION,
        logpath=None,
        terminal=False,
        logtag=logtag,
        cache=True,
        render_config=render_config,
        checkbox_dict=checkbox_dict,
        web_ip=web_ip,
        user_name=user_name,
        simserver=simserver,
    )
    engine.render_config.update({
        "name": True,
        "lethality": False,
        "radar": True,
        "crosspoint": False,
        "network_link": False,
        "waypoints_units": "all",
        "target": {"rcs": 0.1, "speed": 255, "height": 20, "type_": "B-1B"},
    })
    engine.sim_config.update({"ignore_com": False, "earth_curvature": False})
    engine.set_end_time(engine_config["end_time"])
    engine.set_ratio(engine_config["ratio"])
    return engine


def setup_area(engine, area):
    """绘制区域边界并返回供裁判系统闭合使用的区域点列表。"""
    from simulation.core import special_effect

    points_area = list(area.values())
    special_effect.StaticPolygonEffect.gen(
        engine,
        "Area",
        points=points_area,
        color="green",
        alpha=0,
        fill_alpha=0,
        coordinate_system="Cartesian",
    )
    return points_area


def create_red_force(engine, ships_xy, uav_swarm_xy, uav_speed, config):
    """创建所有情景共用的红方水面艇、无人机和通信网络。"""
    ship_config = config["ship"]
    uav_config = config["uav"]
    engine.db["RadarWithGuider"]["distance"] = ship_config["radar_distance"]
    engine.db["RadarWithGuider"]["sector"] = ship_config["radar_sector"]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["Ship"]["comdev"] = "Comdev"
    engine.db["Ship"]["emitters"] = []
    engine.db["Ship"]["guiders"] = []
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]

    red_usvs = [
        engine.gen_platform(
            name,
            "Ship",
            "RED",
            ships_xy[name],
            ship_config["speed"],
            ship_config["course"],
            coordinate_system="Cartesian",
        )
        for name in ships_xy
    ]

    engine.db["RadarWithGuider"]["distance"] = uav_config["radar_distance"]
    engine.db["RadarWithGuider"]["sector"] = uav_config["radar_sector"]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"
    engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    engine.db["AEW"]["comdev"] = "Comdev"

    red_uavs = [
        engine.gen_platform(
            name,
            "AEW",
            "RED",
            point,
            uav_speed,
            uav_config["course"],
            uav_config["height"],
            coordinate_system="Cartesian",
        )
        for name, point in uav_swarm_xy.items()
    ]
    reds = red_usvs + red_uavs
    engine.gen_star_network(
        "StarNetwork4",
        red_usvs[0].name,
        [unit.name for unit in red_usvs[1:]]
        + [unit.name for unit in red_uavs],
    )
    return red_uavs, reds


def create_blue_force(engine, blue_waypoints, route_keys, config):
    """创建蓝方平台并按航路配置初始航行指令。"""
    engine.db["RadarWithGuider"]["distance"] = config["radar_distance"]
    engine.db["RadarWithGuider"]["sector"] = config["radar_sector"]
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]

    blue_pairs = []
    for route_key in route_keys:
        route = blue_waypoints[route_key]
        boat = engine.gen_platform(
            route_key,
            "Ship",
            "BLUE",
            route[0]["point"],
            route[0]["speed"],
            config["course"],
            coordinate_system="Cartesian",
        )
        blue_pairs.append((route_key, boat))
        engine.cmd_sail_area(
            boat,
            speed=route[1]["speed"],
            xy_points=[item["point"] for item in route],
        )
    return blue_pairs, [boat for _, boat in blue_pairs]


def make_starter(judge, red_uavs):
    """构造所有情景共用的仿真启动回调。"""
    def start(sim_engine):
        sim_engine.turn_on_radars()
        sim_engine.turn_on_lockers()
        for uav in red_uavs:
            uav.uavbattery.turn_on()
        judge.activate()

    return start


def add_common_manipulators(engine, *, blues, blue_pairs, blue_waypoints):
    """注册所有情景共用的蓝方策略和分段航速更新器。"""
    engine.add_manipulator(partial(blue_strategy, blues=blues), 1)
    engine.add_manipulator(
        partial(
            per_leg_speed,
            blue_pairs=blue_pairs,
            blue_waypoints=blue_waypoints,
        ),
        1,
    )


def per_leg_speed(sim_engine, *, blue_pairs, blue_waypoints, arrival_tolerance=50):
    """按航路 JSON 的下一航路点速度更新蓝方分段航速。

    ``blue_pairs`` 是 ``(route_key, boat)`` 元组序列，``blue_waypoints``
    是已加载的航路 JSON。进度保存在仿真引擎的 ``blue_leg_idx`` 缓存中，
    因此该函数可以直接作为 manipulator 使用。
    """
    leg_indexes = sim_engine.cache.setdefault("blue_leg_idx", {})
    for route_key, boat in blue_pairs:
        route = blue_waypoints[route_key]
        index = leg_indexes.get(route_key, 1)
        if index >= len(route):
            continue

        target_x, target_y = route[index]["point"]
        distance = math.hypot(
            boat.coords[0] - target_x, boat.coords[1] - target_y
        )
        if distance < arrival_tolerance:
            leg_indexes[route_key] = index + 1
            if index + 1 < len(route):
                sim_engine.cmd_sail_area(
                    boat,
                    speed=route[index + 1]["speed"],
                    xy_points=[item["point"] for item in route[index:]],
                )


def blue_strategy(sim_engine, *, blues):
    """将已发现红方无人艇均衡分配给蓝方平台锁定。"""
    targets = sorted(
        name for name in sim_engine.get_black_targets() if "usv" in name
    )
    if not targets:
        sim_engine.cache.pop("blue_target_assignments", None)
        return

    assignments = tuple(
        (boat.name, targets[index % len(targets)])
        for index, boat in enumerate(blues)
    )
    if sim_engine.cache.get("blue_target_assignments") == assignments:
        return

    for boat_name, target_name in assignments:
        sim_engine.black_cmd_lock(boat_name, target_name)
    sim_engine.cache["blue_target_assignments"] = assignments
