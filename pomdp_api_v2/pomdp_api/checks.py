"""
动作执行前判定函数

每个 check_xxx 依据仿真系统 state 做判定：
- 返回 None → 通过，继续执行
- 返回 dict → 失败/跳过，直接返回给 Agent

所有阈值判定归仿真引擎，API 只检查可从 state 直接判断的条件。
"""

from typing import Optional


def check_move(unit: str, raw: Optional[dict]) -> Optional[dict]:
    """move 执行前判定：USV 存活"""
    if raw is None:
        return None
    for u in raw.get("white_usv_states", []):
        if u.get("name") == unit:
            if not u.get("is_alive"):
                return {"ok": False, "skipped": False,
                        "detail": f"{unit} 移动 失败: 已摧毁"}
            return None
    return {"ok": False, "skipped": False,
            "detail": f"{unit} 移动 失败: 单位不存在"}


def check_fly(unit: str, raw: Optional[dict]) -> Optional[dict]:
    """fly 执行前判定：UAV 存活且在飞行中"""
    if raw is None:
        return None
    for u in raw.get("white_uav_states", []):
        if u.get("name") == unit:
            if not u.get("is_alive"):
                return {"ok": False, "skipped": False,
                        "detail": f"{unit} 飞行 失败: 已摧毁"}
            if u.get("is_at_usv"):
                return {"ok": False, "skipped": False,
                        "detail": f"{unit} 飞行 失败: 已在甲板上，请先起飞"}
            return None
    return {"ok": False, "skipped": False,
            "detail": f"{unit} 飞行 失败: 单位不存在"}


def check_lock(unit: str, target: str, raw: Optional[dict],
               enemy_intel: Optional[dict] = None) -> Optional[dict]:
    """lock 执行前判定：USV 存活、目标存在、未重复锁定"""
    if raw is None:
        return None
    usv_found = False
    for u in raw.get("white_usv_states", []):
        if u.get("name") == unit:
            usv_found = True
            if not u.get("is_alive"):
                return {"ok": False, "skipped": False,
                        "detail": f"{unit} 锁定 {target} 失败: {unit} 已摧毁"}
            if u.get("locking_unit", "") == target:
                return {"ok": True, "skipped": True,
                        "detail": f"{unit} 已锁定 {target}，指令无效"}
            break
    if not usv_found:
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 锁定 {target} 失败: {unit} 不存在"}

    # 检查目标是否仍存在
    if enemy_intel:
        all_enemies = enemy_intel.get("active", []) + enemy_intel.get("passive", [])
        if not any(e.get("name") == target for e in all_enemies):
            return {"ok": False, "skipped": False,
                    "detail": f"{unit} 锁定 {target} 失败: 目标已不存在"}
    return None


def check_launch_uav(unit: str, home: str, raw: Optional[dict]) -> Optional[dict]:
    """launch_uav 执行前判定：UAV 存活在甲板、母船存活且匹配"""
    if raw is None:
        return None
    uav_state = None
    for u in raw.get("white_uav_states", []):
        if u.get("name") == unit:
            uav_state = u
            break
    home_state = None
    for s in raw.get("white_usv_states", []):
        if s.get("name") == home:
            home_state = s
            break

    if not uav_state or not uav_state.get("is_alive"):
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 起飞 失败: 已摧毁"}
    if not home_state or not home_state.get("is_alive"):
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 从 {home} 起飞 失败: 母船已摧毁"}
    if not uav_state.get("is_at_usv"):
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 起飞 失败: 已在空中"}
    if uav_state.get("home_name", "") != home:
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 起飞 失败: 不在 {home} 上"}
    return None


def check_land_uav(unit: str, target: str, raw: Optional[dict]) -> Optional[dict]:
    """land_uav 执行前判定：UAV 存活在飞行、USV 存活、甲板空"""
    if raw is None:
        return None

    uav_state = None
    for u in raw.get("white_uav_states", []):
        if u.get("name") == unit:
            uav_state = u
            break
    usv_state = None
    for s in raw.get("white_usv_states", []):
        if s.get("name") == target:
            usv_state = s
            break

    if not uav_state or not uav_state.get("is_alive"):
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 降落到 {target} 失败: {unit} 已摧毁"}
    if not usv_state or not usv_state.get("is_alive"):
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 降落到 {target} 失败: {target} 已摧毁"}
    if uav_state.get("is_at_usv"):
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 降落到 {target} 失败: {unit} 已在甲板上，无需降落"}

    # 甲板是否已被其他 UAV 占用
    deck_occupied = any(
        u2.get("is_at_usv") and u2.get("home_name") == target
        for u2 in raw.get("white_uav_states", [])
        if u2.get("name") != unit
    )
    if deck_occupied:
        return {"ok": False, "skipped": False,
                "detail": f"{unit} 降落到 {target} 失败: {target} 甲板已被占用"}

    return None
