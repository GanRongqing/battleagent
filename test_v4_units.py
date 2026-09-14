#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_v4_units.py — V4 Commander-layer 离线单测（fake Commander，无真实 provider 调用）

运行: python test_v4_units.py
"""
import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_hybrid_v4 as a4

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


def _wait_worker(cmdr, t=0.2):
    time.sleep(t)
    with cmdr.lock:
        return not cmdr.in_flight


# ── 1) source accounting ──
def test_source_accounting():
    print("== test_source_accounting ==")
    def ok(system, user):
        return '{"posture":"aggressive","focus_level":3,"reason":"t"}'
    def none(system, user):
        return None
    def bad(system, user):
        return "not json at all"
    cmdr = a4.LLMCommander(enabled=True, skill_text="x", call_fn=ok, min_interval_sim=0)
    cmdr.maybe_request(0.0, "s", [], "first_detect")
    _wait_worker(cmdr)
    check("deepseek source", cmdr.get_source() == "deepseek", cmdr.get_source())

    cmdr2 = a4.LLMCommander(enabled=True, skill_text="x", call_fn=none, min_interval_sim=0)
    cmdr2.maybe_request(0.0, "s", [], "first_detect")
    _wait_worker(cmdr2)
    check("provider_fallback source", cmdr2.get_source() == "provider_fallback")
    check("provider fallback stats", cmdr2.stats["api_failures"] == 1)

    cmdr3 = a4.LLMCommander(enabled=True, skill_text="x", call_fn=bad, min_interval_sim=0)
    cmdr3.maybe_request(0.0, "s", [], "first_detect")
    _wait_worker(cmdr3)
    check("parse_fallback source", cmdr3.get_source() == "parse_fallback")
    check("parse fallback stats", cmdr3.stats["parse_failures"] == 1)

    cmdr4 = a4.LLMCommander(enabled=False, skill_text="x")
    check("disabled -> default_intent source", cmdr4.get_source() == "default_intent")
    check("disabled -> DEFAULT_INTENT intent", cmdr4.get_intent() == a4.DEFAULT_INTENT)


# ── 2) policy validation ──
def test_policy_validation():
    print("== test_policy_validation ==")
    it = a4.StrategicIntent(recon_aggressiveness=0.2, reserve_ratio=0.4,
                            engagement_aggressiveness=0.3)
    it2, reason = a4.CommanderIntentAdapter.validate_policy(it, {"blind": True})
    check("blind -> recon floor", it2.recon_aggressiveness >= 0.5 and "recon_floor_when_blind" in (reason or ""))
    it3, reason3 = a4.CommanderIntentAdapter.validate_policy(
        a4.StrategicIntent(reserve_ratio=0.4, engagement_aggressiveness=0.3),
        {"breakthrough_imminent": True})
    check("breakthrough -> reserve cap", it3.reserve_ratio <= 0.10 and "reserve_cap_when_breakthrough" in (reason3 or ""))
    check("breakthrough -> engage floor", it3.engagement_aggressiveness >= 0.5)
    it4, r4 = a4.CommanderIntentAdapter.validate_policy(
        a4.StrategicIntent(overmatch_policy="decisive", focus_level=3),
        {"n_ships": 5, "n_usv_alive": 3})
    check("outnumbered -> focus cap", it4.focus_level <= 2 and "focus_cap_when_outnumbered" in (r4 or ""))
    it5, r5 = a4.CommanderIntentAdapter.validate_policy(
        a4.StrategicIntent(overmatch_policy="balanced", focus_level=2), {})
    check("no violation -> no reason", r5 is None)


# ── 3) last-valid fallback ──
def test_last_valid_fallback():
    print("== test_last_valid_fallback ==")
    responses = [('{"posture":"aggressive","focus_level":3,"reason":"first"}', None),
                 (None, None)]
    state = {"i": 0}
    def call(system, user):
        r, _ = responses[state["i"]]
        state["i"] += 1
        return r
    cmdr = a4.LLMCommander(enabled=True, skill_text="x", call_fn=call, min_interval_sim=0)
    cmdr.maybe_request(0.0, "s", [], "first_detect")
    _wait_worker(cmdr)
    check("first valid applied", cmdr.get_intent().posture == "aggressive")
    cmdr.maybe_request(0.0, "s", [], "periodic")
    _wait_worker(cmdr)
    check("provider fail keeps last valid", cmdr.get_intent().posture == "aggressive")
    check("source after fail = provider_fallback", cmdr.get_source() == "provider_fallback")


# ── 4) state-driven trigger (no per-tick spam) ──
def test_state_driven_trigger():
    print("== test_state_driven_trigger ==")
    calls = {"n": 0}
    def fast(system, user):
        calls["n"] += 1
        return '{"posture":"balanced","reason":"r"}'
    cmdr = a4.LLMCommander(enabled=True, skill_text="x", call_fn=fast, min_interval_sim=0)
    sig_a = (5, 3, 0, 0, 2, 0, 0.9, 0, True)
    # 首次触发
    check("initial fire", cmdr.maybe_request(0.0, "s", [], "periodic", state_sig=sig_a))
    _wait_worker(cmdr)
    # 同签名 + 非优先触发 → 不调用（防每 tick 空转）
    check("same sig + periodic -> no fire", not cmdr.maybe_request(0.0, "s", [], "periodic", state_sig=sig_a))
    # 不同签名 → 触发
    sig_b = (5, 3, 1, 0, 2, 0, 0.9, 0, True)
    check("changed sig -> fire", cmdr.maybe_request(0.0, "s", [], "periodic", state_sig=sig_b))
    _wait_worker(cmdr)
    # 同签名但优先事件 → 触发
    check("priority trigger fires regardless of sig",
          cmdr.maybe_request(0.0, "s", [], "friendly_loss", state_sig=sig_b))
    _wait_worker(cmdr)
    check("no spam total (3 fires)", calls["n"] >= 2 and calls["n"] <= 4, calls["n"])


# ── 5) hysteresis: no_change ──
def test_hysteresis_no_change():
    print("== test_hysteresis_no_change ==")
    def same(system, user):
        return '{"posture":"aggressive","focus_level":3,"reason":"diff text only"}'
    cmdr = a4.LLMCommander(enabled=True, skill_text="x", call_fn=same, min_interval_sim=0)
    cmdr.maybe_request(0.0, "s", [], "first_detect")
    _wait_worker(cmdr)
    check("first applied", cmdr.get_intent().posture == "aggressive")
    n0 = cmdr.stats["responses"]
    cmdr.maybe_request(0.0, "s", [], "periodic")
    _wait_worker(cmdr)
    check("identical strategic fields -> no_change counted", cmdr.stats["no_change"] >= 1)
    check("responses not incremented on no_change", cmdr.stats["responses"] == n0)


# ── 6) intent persistence (LLM disabled -> DEFAULT, then not reverted) ──
def test_intent_persistence():
    print("== test_intent_persistence ==")
    cmdr = a4.LLMCommander(enabled=False, skill_text="x")
    check("disabled -> DEFAULT_INTENT", cmdr.get_intent() == a4.DEFAULT_INTENT)
    check("disabled -> no fire", not cmdr.maybe_request(0.0, "s", [], "first_detect"))


# ── 7) allocator wiring: overmatch + uncertainty_tolerance ──
def test_allocator_wiring():
    print("== test_allocator_wiring ==")
    alloc = a4.ThreatAllocator()
    def make(tname, x, y=400000):
        t = a4.EnemyTrack(tname, 0.0)
        t.update_obs((x, y), (-10, 0), 0.0)
        return t
    tracks = {f"black_usv{i}": make(f"black_usv{i}", 180000) for i in range(1, 6)}
    usvs = [{"name": f"white_usv{i}", "is_alive": True, "position": [100000, 400000 + i]}
            for i in range(1, 6)]
    usv_map = {f"white_usv{i}": None for i in range(1, 6)}
    # decisive → 阈值更低 → 更多攻击者投入
    res_d = alloc.allocate_usvs(tracks, usvs, usv_map, 0.0,
                                intent=a4.StrategicIntent(overmatch_policy="decisive"))
    spent_d = sum(len(v) for v in res_d.values())
    # economical → 阈值更高 → 更早收手
    res_e = alloc.allocate_usvs(tracks, usvs, usv_map, 0.0,
                                intent=a4.StrategicIntent(overmatch_policy="economical"))
    spent_e = sum(len(v) for v in res_e.values())
    check("decisive commits >= economical", spent_d >= spent_e, f"d={spent_d} e={spent_e}")
    # 高不确定容忍 → guard 低 → 低置信丢失航迹可被 commit
    t_lost = make("black_usv9", 180000)
    t_lost.last_seen_time = -200.0
    t_lost.confidence = 0.5
    t_lost.point_confidence = 0.2   # 介于宽松 guard(0.15) 与严格 guard(0.50) 之间
    tracks2 = {"black_usv9": t_lost}
    usvs2 = [{"name": "white_usv1", "is_alive": True, "position": [100000, 400000]}]
    res_hi = alloc.allocate_usvs(tracks2, usvs2, {"white_usv1": None}, 0.0,
                                 intent=a4.StrategicIntent(uncertainty_tolerance=0.95))
    res_lo = alloc.allocate_usvs(tracks2, usvs2, {"white_usv1": None}, 0.0,
                                 intent=a4.StrategicIntent(uncertainty_tolerance=0.05))
    check("high unc tolerance -> low-conf committed", bool(res_hi))
    check("low unc tolerance -> low-conf blocked", not res_lo)


# ── 8) enemy UAV non-ship semantics + coverage floor ──
def test_enemy_uav_and_coverage_floor():
    print("== test_enemy_uav_and_coverage_floor ==")
    alloc = a4.ThreatAllocator()
    def make(tname, x, is_ship):
        t = a4.EnemyTrack(tname, 0.0)
        t.is_ship = is_ship
        t.update_obs((x, 400000), (-10, 0), 0.0)
        return t
    tracks = {"black_usv1": make("black_usv1", 180000, True),
              "black_uav1": make("black_uav1", 100000, False)}
    usvs = [{"name": "white_usv1", "is_alive": True, "position": [150000, 400000]}]
    res = alloc.allocate_usvs(tracks, usvs, {"white_usv1": None}, 0.0,
                              intent=a4.StrategicIntent())
    check("never assigns USV to enemy UAV", "black_uav1" not in res)
    # coverage floor: 4 ships, 5 USVs -> every ship covered before concentration
    tracks2 = {f"black_usv{i}": make(f"black_usv{i}", 170000 + i * 1000, True)
               for i in range(1, 5)}
    usvs2 = [{"name": f"white_usv{i}", "is_alive": True, "position": [100000, 400000 + i]}
             for i in range(1, 6)]
    usv_map2 = {f"white_usv{i}": None for i in range(1, 6)}
    res2 = alloc.allocate_usvs(tracks2, usvs2, usv_map2, 0.0, intent=a4.StrategicIntent())
    check("coverage floor: all 4 ships get >=1 attacker",
          all(len(res2.get(n, [])) >= 1 for n in tracks2.keys()))


# ── 9) SAFE_LOITER continuity (V4 unchanged) ──
def test_safe_loiter_continuity():
    print("== test_safe_loiter_continuity ==")
    mgr = a4.UAVManager(enabled=True)
    class Obs:
        now = 1000.0
        usvs = []
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
    mgr.step(Obs(), Tracker(), Legal(), [], intent=a4.DEFAULT_INTENT, threat_fn=lambda t, n: 0.0)
    check("no recovery -> not forced RETURN", mgr.state["white_uav1"] != mgr.RETURN)
    mgr.state["white_uav1"] = mgr.RETURN
    mgr.step(Obs(), Tracker(), Legal(), [], intent=a4.DEFAULT_INTENT, threat_fn=lambda t, n: 0.0)
    check("RETURN + no recovery -> SAFE_LOITER", mgr.state["white_uav1"] == mgr.SAFE_LOITER)


# ── 10) path-agnostic prompt + fair-play ──
def test_path_agnostic_and_fair_play():
    print("== test_path_agnostic_and_fair_play ==")
    prompt = a4.COMMANDER_ROLE + "\n" + a4.INTENT_SCHEMA_DOC
    for bad in ("10v10", "15v15", "random_waypoint", "seed ", "waypoint", "260000",
                "black_usv", "vx=-10"):
        check(f"prompt excludes {bad!r}", bad not in prompt)
    text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_hybrid_v4.py")).read()
    runtime = text.split("def selftest_trackmanager")[0]
    hits = []
    for bad in ("black_usv", "black_uav", "black_strategy", "BLACK_Y", "ENEMY_X",
                "260000", "vx=-10", "random_waypoint", "waypoint_seed"):
        for i, line in enumerate(runtime.splitlines(), 1):
            if bad in line and not line.strip().startswith("#"):
                hits.append((bad, i))
    check("runtime fair-play zero-hit", not hits, str(hits))


def main():
    tests = [test_source_accounting,
             test_policy_validation,
             test_last_valid_fallback,
             test_state_driven_trigger,
             test_hysteresis_no_change,
             test_intent_persistence,
             test_allocator_wiring,
             test_enemy_uav_and_coverage_floor,
             test_safe_loiter_continuity,
             test_path_agnostic_and_fair_play]
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
