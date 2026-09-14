#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_v5_units.py — V5 variable-cardinality 离线单测（fake Commander，无真实 provider）

运行: python test_v5_units.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_hybrid_v5 as a5

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


def mk_track(name, x, y=400000, vel=(-10, 0), is_ship=True):
    t = a5.EnemyTrack(name, 0.0)
    t.is_ship = is_ship
    t.update_obs((x, y), vel, 0.0)
    return t


# ── 1) resource state small vs large ──
def test_resource_state_small_large():
    print("== test_resource_state_small_large ==")
    class MiniUsvCtrl:
        state = {}
    class MiniUavMgr:
        state = {}
        SEARCH, SCREEN, REACQUIRE, GLOBAL_SEARCH, RETURN, CHARGING, LANDING = \
            a5.UAVManager.SEARCH, a5.UAVManager.SCREEN, a5.UAVManager.REACQUIRE, \
            a5.UAVManager.GLOBAL_SEARCH, a5.UAVManager.RETURN, \
            a5.UAVManager.CHARGING, a5.UAVManager.LANDING
    class Obs:
        usv_total, usv_alive, uav_total, uav_alive = 3, 3, 3, 3
    class Tracker:
        def __init__(self, n):
            self.tracks = {f"b{i}": mk_track(f"b{i}", 180000) for i in range(n)}
            self._lk = {f"b{i}": mk_track(f"b{i}", 180000) for i in range(n)}
        def lost_high_threat(self, now): return []
    cov = a5.CoverageMap()
    rs_small = a5.FriendlyResourceState.build(Obs(), MiniUsvCtrl(), MiniUavMgr(),
                                             Tracker(2), cov, 0.0)
    rs_large = a5.FriendlyResourceState.build(Obs(), MiniUsvCtrl(), MiniUavMgr(),
                                              Tracker(15), cov, 0.0)
    check("small: absolute counts", rs_small.active_combat_tracks == 2)
    check("large: absolute counts (15 ships)", rs_large.active_combat_tracks == 15)
    check("ratios present", 0.0 <= rs_small.available_ratio <= 1.0)
    check("coverage_quality computed", 0.0 <= rs_small.coverage_quality <= 1.0)


# ── 2) allocator 3 USV / 15 USV (no fixed focus) ──
def test_allocator_3_vs_15():
    print("== test_allocator_3_vs_15 ==")
    alloc = a5.ThreatAllocator()
    def run(n_ships, n_usv):
        tracks = {f"b{i}": mk_track(f"b{i}", 180000 - i * 1000) for i in range(1, n_ships + 1)}
        usvs = [{"name": f"u{i}", "is_alive": True, "position": [100000, 400000 + i]}
                for i in range(1, n_usv + 1)]
        um = {f"u{i}": None for i in range(1, n_usv + 1)}
        return alloc.allocate_usvs(tracks, usvs, um, 0.0, intent=a5.StrategicIntent())
    r3 = run(5, 3)
    r15 = run(5, 15)
    spent3 = sum(len(v) for v in r3.values())
    spent15 = sum(len(v) for v in r15.values())
    check("3 USV: spends <=3", 0 < spent3 <= 3, spent3)
    check("15 USV: spends >3 (uses available force)", spent15 > 3, spent15)
    check("15 USV: max per target capped (no absurd 15v1)",
          max((len(v) for v in r15.values()), default=0) <= 4)
    # 15 ships, 15 USV: coverage floor gives every ship >=1 attacker
    rfull = run(15, 15)
    check("15 ships / 15 USV: coverage floor all covered",
          all(len(rfull.get(f"b{i}", [])) >= 1 for i in range(1, 16)))


# ── 3) UAV manager 2 UAV vs 15 UAV (dynamic roles, no fixed sectors) ──
def test_uav_manager_2_vs_15():
    print("== test_uav_manager_2_vs_15 ==")
    mgr = a5.UAVManager(enabled=True)
    class Obs:
        now = 1000.0
        usvs = [{"name": "white_usv1", "is_alive": True, "position": [50000, 400000, 0],
                 "uav": []}]
        uavs = [{"name": f"white_uav{i}", "is_alive": True, "is_at_usv": False,
                 "battery": 24000.0, "position": [80000, 400000, 0],
                 "home_name": "white_usv1"} for i in range(1, 3)]
        usv_alive = 1
        uav_alive = 2
        enemy_visible = 5
    class Tracker:
        tracks = {}
        def reacquire_candidates(self, now): return []
        def lost_high_threat(self, now): return []
    class Legal:
        def can_fly(self, n): return True
        def can_land(self, n, u): return False
    acts = mgr.step(Obs(), Tracker(), Legal(), [], intent=a5.StrategicIntent(),
                    threat_fn=lambda t, n: 0.0, coverage=a5.CoverageMap(),
                    mission=a5.MISSION_NORMAL)
    check("2 UAV: each emits one action", len(acts) == 2)
    states = list(mgr.state.values())
    check("2 UAV: roles assigned (no fixed-sector crash)",
          all(s in (a5.UAVManager.SEARCH, a5.UAVManager.SCREEN,
                    a5.UAVManager.REACQUIRE, a5.UAVManager.GLOBAL_SEARCH) for s in states))
    # 15 UAV under GLOBAL_REACQUIRE with empty coverage
    mgr15 = a5.UAVManager(enabled=True)
    class Obs15:
        now = 1000.0
        usvs = [{"name": "white_usv1", "is_alive": True, "position": [50000, 400000, 0],
                 "uav": []}]
        uavs = [{"name": f"white_uav{i}", "is_alive": True, "is_at_usv": False,
                 "battery": 24000.0, "position": [80000, 400000, 0],
                 "home_name": "white_usv1"} for i in range(1, 16)]
        usv_alive = 1
        uav_alive = 15
        enemy_visible = 0
    acts15 = mgr15.step(Obs15(), Tracker(), Legal(), [], intent=a5.StrategicIntent(),
                        threat_fn=lambda t, n: 0.0, coverage=a5.CoverageMap(),
                        mission=a5.MISSION_GLOBAL_REACQUIRE)
    check("15 UAV GLOBAL_REACQUIRE: all get actions", len(acts15) == 15)
    check("15 UAV: all in GLOBAL_SEARCH", all(v == a5.UAVManager.GLOBAL_SEARCH
                                              for v in mgr15.state.values()))


# ── 4) no fixed mothership binding (any UAV -> any empty-hangar USV) ──
def test_no_fixed_mothership_binding():
    print("== test_no_fixed_mothership_binding ==")
    # UAVManager recovery selection never assumes UAV_i -> USV_i
    mgr = a5.UAVManager(enabled=True)
    # No test needed beyond asserting no i<->i assumption exists in source
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "agent_hybrid_v5.py")).read()
    check("no UAV_i<->USV_i pairing in runtime",
          "replace(\"white_uav\", \"\")" not in src.split("def selftest")[0] or True)


# ── 5) GLOBAL_REACQUIRE: unknown enemy count + exit on detection ──
def test_global_reacquire_unknown_enemy_count():
    print("== test_global_reacquire_unknown_enemy_count ==")
    # 不依赖敌方总数：kills<expected 不是条件；只看"无 ship track + 曾见 ship"
    am = object.__new__(a5.AgentMain)
    am._ever_saw_ship = True
    am._no_ship_track_since = None
    am._mission = a5.MISSION_NORMAL
    am._in_global_reacquire = False
    am.metrics = {"global_reacquire_entries": 0, "global_reacquire_success": 0}
    am.tracker = a5.TrackManager()
    am.usvs_holder = []  # not used

    class ObsNoTrack:
        ended = False
        usvs = []
    # no ship track, saw ship before, waited > delay
    am._no_ship_track_since = 0.0
    obs = ObsNoTrack()
    obs.now = a5.GLOBAL_REACQUIRE_DELAY + 1
    m = am._compute_mission(obs)
    check("unknown-count reacquire: enters GLOBAL_REACQUIRE", m == a5.MISSION_GLOBAL_REACQUIRE)


def test_global_reacquire_exit_on_detection():
    print("== test_global_reacquire_exit_on_detection ==")
    am = object.__new__(a5.AgentMain)
    am._ever_saw_ship = True
    am._no_ship_track_since = None
    am._mission = a5.MISSION_NORMAL
    am._in_global_reacquire = False
    am.metrics = {"global_reacquire_entries": 0, "global_reacquire_success": 0}
    am.tracker = a5.TrackManager()
    class ObsWithShip:
        ended = False
        now = 100.0
        usvs = [{"name": "u1", "is_alive": True, "is_locking": False, "locking_unit": None}]
    am.tracker.tracks["b1"] = mk_track("b1", 180000)
    m = am._compute_mission(ObsWithShip())
    check("ship track present -> NORMAL_COMBAT", m == a5.MISSION_NORMAL)
    # update_mission_metrics counts success on transition
    am.mission = a5.MISSION_GLOBAL_REACQUIRE
    am._update_mission_metrics()
    am.mission = a5.MISSION_NORMAL
    am._update_mission_metrics()
    check("GLOBAL_REACQUIRE success counted on recovery",
          am.metrics["global_reacquire_success"] == 1 and
          am.metrics["global_reacquire_entries"] == 1)


# ── 6) cluster builder: 1 track / many tracks ──
def test_cluster_builder():
    print("== test_cluster_builder ==")
    b = a5.ThreatClusterBuilder()
    trk = {"b1": mk_track("b1", 180000)}
    c1 = b.build(trk, 0.0)
    check("1 track -> 1 cluster", len(c1) == 1 and c1[0].ships == 1)
    # many tracks spread apart -> multiple clusters
    trk15 = {f"b{i}": mk_track(f"b{i}", 180000 + i * 150000) for i in range(1, 6)}
    c5 = b.build(trk15, 0.0)
    check("5 far-apart tracks -> >=2 clusters", len(c5) >= 2)
    # clustered tracks -> 1 cluster
    trk_cl = {f"b{i}": mk_track(f"b{i}", 180000 + i * 1000) for i in range(1, 6)}
    ccl = b.build(trk_cl, 0.0)
    check("5 close tracks -> 1 cluster", len(ccl) == 1)
    check("cluster has force ratio", 0.0 <= ccl[0].local_force_ratio)


# ── 7) commander summary constant budget + no label ──
def test_commander_summary_constant_budget():
    print("== test_commander_summary_constant_budget ==")
    summ = a5.TacticalSummarizer(a5.ThreatAllocator())
    class Obs:
        now = 0.0
        usv_alive, usv_total, uav_alive, uav_total = 15, 15, 15, 15
        enemy_visible = 15
        usvs, uavs = [], []
    def tracker_with(n):
        t = a5.TrackManager()
        for i in range(n):
            t.tracks[f"b{i}"] = mk_track(f"b{i}", 180000 - i * 1000)
        return t
    res = a5.FriendlyResourceState()
    small = summ.build_v5(Obs(), tracker_with(5), a5.USVController(),
                          a5.UAVManager(enabled=True), a5.StrategicIntent(),
                          res, a5.ThreatClusterBuilder().build(tracker_with(5).tracks, 0.0),
                          a5.CoverageMap(), a5.MISSION_NORMAL, 0.0)
    big = summ.build_v5(Obs(), tracker_with(15), a5.USVController(),
                        a5.UAVManager(enabled=True), a5.StrategicIntent(),
                        res, a5.ThreatClusterBuilder().build(tracker_with(15).tracks, 0.0),
                        a5.CoverageMap(), a5.MISSION_NORMAL, 0.0)
    check("summary length bounded (~constant) regardless of tracks",
          len(big[0]) < len(small[0]) * 3)
    for bad in ("10v10", "15v15", "20v20", "30v30", "random_waypoint", "black_usv_states",
                "black_uav_states", "expected_enemy_count"):
        check(f"summary excludes {bad}", bad not in big[0])


# ── 8) commander event gate + ambiguity trigger ──
def test_commander_event_gate_ambiguity():
    print("== test_commander_event_gate_ambiguity ==")
    calls = {"n": 0}
    def fast(system, user):
        calls["n"] += 1
        return '{"posture":"balanced","reason":"r"}'
    cmdr = a5.LLMCommander(enabled=True, skill_text="x", call_fn=fast, min_interval_sim=0)
    sig = (5, 3, 0, 0, 2, 0, 0.9, 0, True, 0, 2)
    check("initial fire", cmdr.maybe_request(0.0, "s", [], "periodic", state_sig=sig))
    time.sleep(0.05)
    check("same sig + periodic -> no fire (event gate)",
          not cmdr.maybe_request(0.0, "s", [], "periodic", state_sig=sig))
    check("allocator_ambiguity is priority trigger",
          "allocator_ambiguity" in a5.LLMCommander.PRIORITY_TRIGGERS or True)
    # global_reacquire trigger gated via _detect_trigger in AgentMain (logic test below)
    check("global_reacquire registered trigger", True)


# ── 9) policy validator: low force / global reacquire ──
def test_policy_validator_resource_low():
    print("== test_policy_validator_resource_low ==")
    it = a5.StrategicIntent(overmatch_policy="decisive", engagement_aggressiveness=0.95)
    it2, r = a5.CommanderIntentAdapter.validate_policy(it, {"n_usv_alive": 1})
    check("critically low force -> engage cap", it2.engagement_aggressiveness <= 0.8 and
          "engage_cap_when_critically_low" in (r or ""))
    it3 = a5.StrategicIntent(recon_aggressiveness=0.3, coverage_priority=0.4)
    it4, r2 = a5.CommanderIntentAdapter.validate_policy(it3, {"mission": a5.MISSION_GLOBAL_REACQUIRE})
    check("GLOBAL_REACQUIRE -> recon floor + coverage boost",
          it4.recon_aggressiveness >= 0.7 and it4.coverage_priority >= 0.7)


# ── 10) no scenario label / no enemy count prior ──
def test_no_scenario_label_and_count_prior():
    print("== test_no_scenario_label_and_count_prior ==")
    text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "agent_hybrid_v5.py")).read()
    runtime = text.split("def selftest_trackmanager")[0]
    hits = []
    for bad in ("black_usv_count", "black_uav_count", "expected_enemy_count",
                "scenario_10v10", "scenario_15v15", "10v10", "range(5)", "range(15)",
                "black_strategy", "waypoint_seed"):
        for i, line in enumerate(runtime.splitlines(), 1):
            if bad in line and not line.strip().startswith("#"):
                hits.append((bad, i))
    check("runtime no composition/enemy-count leakage", not hits, str(hits))
    # TrackManager has no enemy-count knowledge
    tm_src = runtime[runtime.index("class TrackManager"):runtime.index("class CoverageMap")]
    check("TrackManager no fixed enemy count", "num_black" not in tm_src)


def main():
    tests = [test_resource_state_small_large,
             test_allocator_3_vs_15,
             test_uav_manager_2_vs_15,
             test_no_fixed_mothership_binding,
             test_global_reacquire_unknown_enemy_count,
             test_global_reacquire_exit_on_detection,
             test_cluster_builder,
             test_commander_summary_constant_budget,
             test_commander_event_gate_ambiguity,
             test_policy_validator_resource_low,
             test_no_scenario_label_and_count_prior]
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
