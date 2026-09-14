#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_v3_units.py — V3 新模块离线单元测试（无需服务器）

运行: python test_v3_units.py
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_hybrid_v3 as a3

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


def mk_track(name, pos, vel, now):
    t = a3.EnemyTrack(name, now)
    t.update_obs(pos, vel, now)
    return t


def _extract_course(text):
    import re
    m = re.search(r"target_course=([\d.]+)", text)
    return float(m.group(1)) if m else None


# ── 1) maneuver turn detection ──
def test_maneuver_track_turn_detection():
    print("== test_maneuver_track_turn_detection ==")
    t = a3.EnemyTrack("black_usv1", 0.0)
    t.update_obs((200000, 400000), (-10, 0), 0.0)   # 朝西
    t.update_obs((199900, 400000), (-10, 0), 10.0)  # 继续西
    check("straight: no turn yet", t.turn_events == 0 and t.maneuver_score < 0.3)
    t.update_obs((199850, 400100), (-5, 8), 20.0)   # 转向（heading 变化明显）
    check("turn detected: turn_events>=1", t.turn_events >= 1)
    t.update_obs((199800, 400300), (-2, 10), 30.0)  # 继续机动
    check("maneuver_score rises", t.maneuver_score >= 0.4)
    check("point_confidence penalized", t.point_confidence < 0.95)


# ── 2) uncertainty growth ──
def test_uncertainty_growth():
    print("== test_uncertainty_growth ==")
    t = mk_track("black_usv1", (200000, 400000), (-10, 0), 0.0)
    r0 = t.uncertainty(0.0)
    r30 = t.uncertainty(30.0)
    r180 = t.uncertainty(180.0)
    check("uncertainty grows with time", r0 < r30 < r180)
    check("maneuver increases uncertainty", True)
    t2 = mk_track("black_usv2", (200000, 400000), (-10, 0), 0.0)
    t2.update_obs((199500, 401000), (-3, 12), 30.0)  # 机动目标
    check("maneuver target uncertainty > stable",
          t2.uncertainty(60.0) > t.uncertainty(60.0))


# ── 3) uncertainty decay on reacquire ──
def test_uncertainty_decay_on_reacquire():
    print("== test_uncertainty_decay_on_reacquire ==")
    t = mk_track("black_usv1", (200000, 400000), (-10, 0), 0.0)
    r_lost = t.uncertainty(120.0)
    t.update_obs((197000, 400000), (-10, 0), 120.0)  # 重新探测
    r_re = t.uncertainty(120.0)
    check("reacquire shrinks uncertainty", r_re < r_lost)


# ── 4) UAV safe loiter when no recovery platform ──
def test_uav_safe_loiter_no_recovery_platform():
    print("== test_uav_safe_loiter_no_recovery_platform ==")
    mgr = a3.UAVManager(enabled=True)
    class Obs:
        now = 1000.0
        usvs = []               # 无存活 USV（无回收平台）
        uavs = [{"name": "white_uav1", "is_alive": True, "is_at_usv": False,
                 "battery": 15000.0, "position": [180000, 400000, 0],
                 "home_name": "white_usv1"}]
        usv_alive = 0
        uav_alive = 1
        enemy_visible = 0
    class Tracker:
        tracks = {}
        def reacquire_candidates(self, now): return []
    class Legal:
        def can_fly(self, n): return True
        def can_land(self, n, u): return False
    events = []
    acts = mgr.step(Obs(), Tracker(), Legal(), events, intent=a3.DEFAULT_INTENT,
                    threat_fn=lambda t, n: 0.0)
    # 关键：无回收舰时绝不能强制 RTB（旧 bug: est_ret=inf → RTB → 西飞出界）
    check("no recovery -> no RTB forced (state not RETURN)", mgr.state["white_uav1"] != mgr.RETURN)
    check("no recovery -> keeps sensing role (SEARCH/SCREEN)", mgr.state["white_uav1"] in
          (mgr.SEARCH, mgr.SCREEN))
    check("loiter emits a fly action", len(acts) >= 1 and acts[0][1] == "fly")
    # RETURN 中回收舰消失 → SAFE_LOITER（显式安全盘旋）
    mgr.state["white_uav1"] = mgr.RETURN
    acts2 = mgr.step(Obs(), Tracker(), Legal(), [], intent=a3.DEFAULT_INTENT,
                     threat_fn=lambda t, n: 0.0)
    check("RETURN with lost recovery -> SAFE_LOITER", mgr.state["white_uav1"] == mgr.SAFE_LOITER)


# ── 5) UAV region reacquire (not single point) ──
def test_uav_region_reacquire():
    print("== test_uav_region_reacquire ==")
    mgr = a3.UAVManager(enabled=True)
    t = mk_track("black_usv1", (180000, 400000), (-10, 0), 100.0)
    # 距 center 很近 → 应进入 sweep（不是直接飞向 center 的单一 point）
    pos = (181000, 400000)
    f1 = mgr._region_reacquire_fly("white_uav1", pos, t, 120.0, 0)
    f2 = mgr._region_reacquire_fly("white_uav1", pos, t, 120.0, 1)
    check("reacquire emits fly", f1[1] == "fly" and f2[1] == "fly")
    c1 = _extract_course(f1[0])
    c2 = _extract_course(f2[0])
    check("sweep changes course (region scan, not fixed point)", abs(c1 - c2) > 1.0)
    # 远距 → 先接近 center
    pos_far = (250000, 400000)
    f3 = mgr._region_reacquire_fly("white_uav1", pos_far, t, 120.0, 0)
    c3 = _extract_course(f3[0])
    check("far -> approach center", abs(c3 - a3.bearing_to(pos_far, (179000, 400000))) < 5.0)


# ── 6) enemy UAV not a breakthrough/combat target ──
def test_enemy_uav_not_breakthrough_target():
    print("== test_enemy_uav_not_breakthrough_target ==")
    alloc = a3.ThreatAllocator()
    usv_t = mk_track("black_usv1", (180000, 400000), (-10, 0), 0.0)
    uav_t = mk_track("black_uav1", (100000, 400000), (-30, 0), 0.0)
    check("ship is_ship", usv_t.is_ship)
    check("uav is not ship", not uav_t.is_ship)
    s_ship = alloc.threat_score(usv_t, 0.0)
    s_uav = alloc.threat_score(uav_t, 0.0)
    check("uav threat capped low", s_uav <= 0.35 and s_uav < s_ship,
          f"ship={s_ship:.2f} uav={s_uav:.2f}")
    # 分配只给 ship
    tracks = {"black_usv1": usv_t, "black_uav1": uav_t}
    usvs = [{"name": "white_usv1", "is_alive": True, "position": [150000, 400000]}]
    res = alloc.allocate_usvs(tracks, usvs, {"white_usv1": None}, 0.0,
                              intent=a3.StrategicIntent())
    check("allocator never assigns USV to enemy UAV",
          all(k != "black_uav1" for k in res.keys()))


# ── 7) low-confidence commitment guard ──
def test_low_confidence_commitment_guard():
    print("== test_low_confidence_commitment_guard ==")
    alloc = a3.ThreatAllocator()
    # 丢失 + 低点置信 + 离突破线不近 → 阻止 commit
    t = mk_track("black_usv1", (180000, 400000), (-10, 0), 0.0)
    t.last_seen_time = -200.0   # 已丢失
    t.confidence = 0.5
    t.point_confidence = 0.2
    tracks = {"black_usv1": t}
    usvs = [{"name": "white_usv1", "is_alive": True, "position": [150000, 400000]}]
    res = alloc.allocate_usvs(tracks, usvs, {"white_usv1": None}, 0.0,
                              intent=a3.StrategicIntent())
    check("low-conf lost track not committed (guard)", not res,
          f"res={res}")
    # 但极近突破线 → 必须拦截
    t2 = mk_track("black_usv2", (70000, 400000), (-10, 0), 0.0)
    t2.last_seen_time = -200.0
    t2.confidence = 0.5
    t2.point_confidence = 0.2
    tracks2 = {"black_usv2": t2}
    res2 = alloc.allocate_usvs(tracks2, usvs, {"white_usv1": None}, 0.0,
                               intent=a3.StrategicIntent())
    check("urgent low-conf near-break -> intercept allowed", res2)


# ── 8) standoff lock band ──
def test_standoff_lock_band():
    print("== test_standoff_lock_band ==")
    ctrl = a3.USVController()
    # 在 band 内（34km）→ 应收敛到 band（course 大致指向 band_mid 方向 = 远离？）
    pos = (100000, 400000)
    tpos = (133000, 400000)  # 33km
    m = ctrl._standoff_move("white_usv1", pos, tpos, 37000, 32000, 39000)
    crs = _extract_course(m[0])
    # 33km < band_mid 37km → 向外（back toward band）→ course 应远离目标方向
    away = a3.bearing_to(pos, (100000 - 5000, 400000))
    check("standoff backs off when too close", crs is not None and m[1] == "move")
    # 超过 band_outer（41km）→ 收拢（朝目标）
    tpos2 = (141000, 400000)
    m2 = ctrl._standoff_move("white_usv1", pos, tpos2, 37000, 32000, 39000)
    crs2 = _extract_course(m2[0])
    toward = a3.bearing_to(pos, tpos2)
    check("standoff closes when near break", abs(crs2 - toward) < 5.0)


# ── 9) marginal allocator small force ──
def test_marginal_allocator_small_force():
    print("== test_marginal_allocator_small_force ==")
    alloc = a3.ThreatAllocator()
    tracks = {f"black_usv{i}": mk_track(f"black_usv{i}", (180000, 400000), (-10, 0), 0.0)
              for i in range(1, 6)}
    usvs = [{"name": f"white_usv{i}", "is_alive": True,
             "position": [100000, 400000 + i]} for i in range(1, 6)]
    usv_map = {f"white_usv{i}": None for i in range(1, 6)}
    res = alloc.allocate_usvs(tracks, usvs, usv_map, 0.0, intent=a3.StrategicIntent())
    spent = sum(len(v) for v in res.values())
    check("small force: assigns within available", 0 < spent <= 5)
    check("small force: focus cap respected (<=2 per target in non-emergency)",
          all(len(v) <= 2 for v in res.values()) or spent <= 5)
    check("marginal gain 1->2 > 2->3", a3.ThreatAllocator.marginal_gain(1) >
          a3.ThreatAllocator.marginal_gain(2))
    check("marginal gain decreasing", a3.ThreatAllocator.marginal_gain(2) >
          a3.ThreatAllocator.marginal_gain(3))


# ── 10) marginal allocator large force ──
def test_marginal_allocator_large_force():
    print("== test_marginal_allocator_large_force ==")
    alloc = a3.ThreatAllocator()
    tracks = {f"black_usv{i}": mk_track(f"black_usv{i}", (180000, 400000), (-10, 0), 0.0)
              for i in range(1, 16)}
    usvs = [{"name": f"white_usv{i}", "is_alive": True,
             "position": [100000, 400000 + i]} for i in range(1, 16)]
    usv_map = {f"white_usv{i}": None for i in range(1, 16)}
    res = alloc.allocate_usvs(tracks, usvs, usv_map, 0.0, intent=a3.StrategicIntent())
    spent = sum(len(v) for v in res.values())
    check("large force: not everything committed to one target",
          max((len(v) for v in res.values()), default=0) <= 4)
    check("large force: spreads reasonably", spent > 0 and len(res) >= 2)


# ── 11) commander schema fallback ──
def test_commander_schema_fallback():
    print("== test_commander_schema_fallback ==")
    intent, err = a3.CommanderIntentAdapter.parse("not json", [])
    check("malformed -> fallback", intent is None and err == "malformed_json")
    intent, _ = a3.CommanderIntentAdapter.parse(
        '{"overmatch_policy":"decisive","recon_mode":"screen_priority",'
        '"standoff_preference":"high","uncertainty_tolerance":0.9}', ["E1"])
    check("new fields parsed", intent is not None)
    check("overmatch whitelist", intent.overmatch_policy == "decisive")
    check("recon_mode whitelist", intent.recon_mode == "screen_priority")
    check("standoff whitelist", intent.standoff_preference == "high")
    check("uncertainty clamp", abs(intent.uncertainty_tolerance - 0.9) < 1e-9)
    intent, _ = a3.CommanderIntentAdapter.parse(
        '{"overmatch_policy":"bogus","recon_mode":"x","standoff_preference":"extreme",'
        '"uncertainty_tolerance":5}', [])
    check("bad new fields fall back to defaults",
          intent.overmatch_policy == "balanced" and intent.recon_mode == "balanced"
          and intent.standoff_preference == "medium" and abs(intent.uncertainty_tolerance - 1.0) < 1e-9)


# ── 12) no scenario label in summary ──
def test_no_scenario_label_in_summary():
    print("== test_no_scenario_label_in_summary ==")
    alloc = a3.ThreatAllocator()
    summ = a3.TacticalSummarizer(alloc)
    class MiniObs:
        now = 1000.0
        usv_alive = 5
        uav_alive = 5
        enemy_visible = 5
        usvs = []
        uavs = []
    tracker = a3.TrackManager()
    for i in range(1, 6):
        tracker.tracks[f"black_usv{i}"] = mk_track(f"black_usv{i}", (180000, 400000), (-10, 0), 0.0)
    s, tids = summ.build(MiniObs(), tracker, a3.USVController(),
                         a3.UAVManager(enabled=True), a3.StrategicIntent())
    for bad in ("10v10", "15v15", "20v20", "30v30", "random_waypoint",
                "black_usv_states", "black_uav_states", "black_strategy",
                "vx=-10", "260000", "BLACK_Y"):
        check(f"summary excludes {bad}", bad not in s)
    check("summary contains maneuver aggregate", "MANEUVER" in s and "high_uncertainty_tracks" in s)
    check("summary contains force aggregate", "FORCE" in s and "available_ratio" in s)


def main():
    tests = [test_maneuver_track_turn_detection,
             test_uncertainty_growth,
             test_uncertainty_decay_on_reacquire,
             test_uav_safe_loiter_no_recovery_platform,
             test_uav_region_reacquire,
             test_enemy_uav_not_breakthrough_target,
             test_low_confidence_commitment_guard,
             test_standoff_lock_band,
             test_marginal_allocator_small_force,
             test_marginal_allocator_large_force,
             test_commander_schema_fallback,
             test_no_scenario_label_in_summary]
    for t in tests:
        try:
            t()
        except Exception as e:
            FAIL.append(t.__name__)
            print(f"  [ERROR] {t.__name__}: {e}")
    print("=" * 60)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
