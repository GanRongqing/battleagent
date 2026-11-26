"""红方单位的可复用初始编队。"""


def red_formation_horizontal():
    """20 个 USV 组成横队，10 个 UAV 位于右侧的成对 USV 之间。"""
    # 将横队放在任务区域内部，避免启动后被区域裁判清除。
    usv_x = 60_000
    uav_x = 90_000

    # 从上到下排列，关于 y=0 对称，相邻 USV 间隔 10000 米。
    usv_y = list(range(95_000, -95_001, -10_000))
    # USV1/USV2 之间放 UAV1，USV3/USV4 之间放 UAV2，依次类推。
    uav_y = [
        (usv_y[i] + usv_y[i + 1]) // 2
        for i in range(0, 20, 2)
    ]

    ships_xy = {
        f"white_usv{i + 1}": [usv_x, y]
        for i, y in enumerate(usv_y)
    }
    uav_swarm_xy = {
        f"white_uav{i + 1}": [uav_x, y]
        for i, y in enumerate(uav_y)
    }
    return ships_xy, uav_swarm_xy


def red_formation_diamond():
    """20 个 USV 组成菱形，10 个 UAV 在右侧组成箭头形。"""
    # 将编队整体放在任务区域内部，避免边界裁判和前端过滤掉红方单位。
    center_x, center_y = 120_000, 0
    corners = [
        (center_x, center_y + 180_000),
        (center_x + 60_000, center_y),
        (center_x, center_y - 180_000),
        (center_x - 60_000, center_y),
    ]

    ship_points = []
    for side in range(4):
        start = corners[side]
        end = corners[(side + 1) % 4]
        for index in range(5):
            ratio = index / 5
            ship_points.append([
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            ])

    uav_points = []
    for index in range(5):
        x = center_x + 75_000 + index * 10_000
        offset = 90_000 - index * 20_000
        uav_points.extend([
            [x, center_y + offset],
            [x, center_y - offset],
        ])

    return (
        {f"white_usv{i}": point for i, point in enumerate(ship_points, 1)},
        {f"white_uav{i}": point for i, point in enumerate(uav_points, 1)},
    )


def red_formation_echelon():
    """20 个 USV 分成 5 个台阶，10 个 UAV 位于各台阶右侧。"""
    ships_xy = {}
    uav_swarm_xy = {}

    # 每个台阶有 4 个纵向排列的 USV，台阶逐级向右下方移动。
    for step in range(5):
        usv_x = -175_200 + step * 30_000
        uav_x = usv_x + 20_000
        step_center_y = 90_000 - step * 45_000
        usv_y = [
            step_center_y + 15_000,
            step_center_y + 5_000,
            step_center_y - 5_000,
            step_center_y - 15_000,
        ]

        for offset, y in enumerate(usv_y):
            index = step * 4 + offset + 1
            ships_xy[f"white_usv{index}"] = [usv_x, y]

        # 每个台阶放 2 个 UAV，分别处于两对 USV 的中间。
        for offset, y in enumerate((step_center_y + 10_000,
                                    step_center_y - 10_000)):
            index = step * 2 + offset + 1
            uav_swarm_xy[f"white_uav{index}"] = [uav_x, y]

    return ships_xy, uav_swarm_xy


def red_formation_horizontal_n(usv_count):
    """E33: parameterized N-ship horizontal line (additive; used by the new 16-route scenarios).

    Matches the provided scenario spec: spacing 20 km for N<=20, 18 km for N=30, centered on y=0 at
    x=60 km. These scenarios define NO White UAVs, so uav_swarm_xy is empty."""
    spacing = min(20_000 if usv_count <= 20 else 18_000, 540_000 // max(1, usv_count - 1))
    start_y = (usv_count - 1) * spacing / 2
    ships_xy = {f"white_usv{i + 1}": [60_000, start_y - i * spacing] for i in range(usv_count)}
    return ships_xy, {}


def red_formation(mode="diamond"):
    """按名称选择红方初始编队；默认使用任务区域内的菱形编队。"""
    if mode == "horizontal":
        return red_formation_horizontal()
    if mode == "diamond":
        return red_formation_diamond()
    if mode == "echelon":
        return red_formation_echelon()
    import re as _re
    _m = _re.fullmatch(r"horizontal_(\d+)", mode or "")
    if _m:
        return red_formation_horizontal_n(int(_m.group(1)))
    raise ValueError(f"未知红方编队模式: {mode}")
