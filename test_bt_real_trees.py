#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_bt_real_trees.py — validation of the REAL USV/UAV trees wired through the interface.

Run: python test_bt_real_trees.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bt_harness_interface as bhi                       # noqa: E402
import bt_real_trees as rt                               # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


def ctx(pid="white_usv1", ptype=bhi.PlatformType.USV, t=0.0, tracks=None, safety=None,
        pos=None):
    return bhi.ExecutionContext(
        pid, ptype, t,
        platform_state={"name": pid, "position": pos or [0.0, 300000.0],
                        "speed": 20.0, "heading": 90.0, "is_alive": True},
        tracks=tracks or {}, safety_feedback=safety)


def trk(pos, visible=True, confidence=1.0):
    return {"position": list(pos), "visible": visible, "confidence": confidence}


def usv_exec(pid="white_usv1"):
    return bhi.BTPlatformExecutive(pid, bhi.PlatformType.USV)


def uav_exec(pid="white_uav1"):
    return bhi.BTPlatformExecutive(pid, bhi.PlatformType.UAV)


# ════════════════════════════════════════════════════════════════
# TEST A — REAL USV tree: INTERCEPT_LOCK, >=5 ticks, phase changes, real ActionRequests
# ════════════════════════════════════════════════════════════════
def test_A_real_usv_tree():
    print("== TEST A: REAL USV tree, INTERCEPT_LOCK, >=5 ticks ==")
    ex = usv_exec()
    check("production path uses REAL tree (not stub)",
          type(ex.tree).__name__ == "BehaviorTree" and ex.tree.platform_type == bhi.PlatformType.USV)
    ex.submit_task(bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                                   bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3"))
    phases = []
    for i in range(1, 6):
        d = 150000 - (i - 1) * 40000   # closes: 150k -> 30k (into lock range)
        r = ex.tick(ctx(tracks={"enemy_3": trk([d, 300000])}, t=float(i)))
        phases.append(r.task_feedback.phase.value)
        check(f"tick {i}: produces real ActionRequests, target=enemy_3",
              len(r.action_requests) >= 1 and
              all((a.target_id == "enemy_3" or a.target_id is None) for a in r.action_requests),
              f"{len(r.action_requests)}/{[a.target_id for a in r.action_requests]}")
    check("real tree phase transitions (approach -> engage)",
          "approach" in phases and "engage" in phases, str(phases))
    check("real TaskFeedback.status is RUNNING", ex.last_feedback.status == bhi.TaskStatus.RUNNING)


# ════════════════════════════════════════════════════════════════
# TEST B — REAL UAV tree: SITUATION_UPDATE + COOPERATIVE_LOCK, >=5 ticks
# ════════════════════════════════════════════════════════════════
def test_B_real_uav_tree():
    print("== TEST B: REAL UAV tree, SITUATION_UPDATE + COOPERATIVE_LOCK, >=5 ticks ==")
    # SITUATION_UPDATE
    su = uav_exec("white_uav1")
    check("UAV production path uses REAL UAV tree",
          type(su.tree).__name__ == "BehaviorTree" and su.tree.platform_type == bhi.PlatformType.UAV)
    su.submit_task(bhi.TaskCommand("uav1_situ", "white_uav1", bhi.PlatformType.UAV,
                                   bhi.TaskType.SITUATION_UPDATE,
                                   constraints={"waypoint": [150000, 300000]}))
    for i in range(1, 6):
        r = su.tick(ctx("white_uav1", bhi.PlatformType.UAV, t=float(i),
                        pos=[50000, 300000]))
        check(f"SITUATION tick {i}: NAVIGATE_TO action",
              any(a.action_kind == bhi.ActionKind.NAVIGATE_TO for a in r.action_requests) and
              r.task_feedback.phase == bhi.Phase.SEARCH,
              f"{[a.action_kind for a in r.action_requests]}")
    # COOPERATIVE_LOCK
    cl = uav_exec("white_uav2")
    cl.submit_task(bhi.TaskCommand("uav2_coop", "white_uav2", bhi.PlatformType.UAV,
                                   bhi.TaskType.COOPERATIVE_LOCK, target_id="enemy_3"))
    for i in range(1, 6):
        d = 90000 - (i - 1) * 20000     # far -> near
        r = cl.tick(ctx("white_uav2", bhi.PlatformType.UAV, t=float(i),
                        tracks={"enemy_3": trk([d, 300000])}, pos=[50000, 300000]))
        check(f"COOPERATIVE_LOCK tick {i}: real action, target=enemy_3",
              len(r.action_requests) >= 1 and
              all(a.target_id == "enemy_3" for a in r.action_requests),
              f"{[a.action_kind for a in r.action_requests]}")


# ════════════════════════════════════════════════════════════════
# TEST C — Safety: REJECTED primitive is not repeated next tick
# ════════════════════════════════════════════════════════════════
def test_C_safety_no_repeat():
    print("== TEST C: REJECTED primitive not repeated next tick ==")
    ex = usv_exec()
    ex.submit_task(bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                                   bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3"))
    r1 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=0.0))   # in range -> ENGAGE
    kinds1 = [a.action_kind for a in r1.action_requests]
    check("tick1 emits ENGAGE (lock) primitive", bhi.ActionKind.ENGAGE_TARGET in kinds1, str(kinds1))
    ad = bhi.BTActionAdapter()
    lock_text = next(a["action_text"] for a in ad.to_apply_payload(r1.action_requests)["actions"]
                     if a["action_type"] == "lock")
    r2 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=1.0,
                     safety={lock_text: "REJECTED"}))
    kinds2 = [a.action_kind for a in r2.action_requests]
    check("tick2 does NOT repeat the rejected ENGAGE primitive",
          bhi.ActionKind.ENGAGE_TARGET not in kinds2, str(kinds2))
    check("tick2 falls back to HOLD with SAFETY_REJECTED reason",
          r2.task_feedback.phase == bhi.Phase.HOLD and
          r2.task_feedback.reason_code == bhi.FeedbackReason.SAFETY_REJECTED,
          f"{r2.task_feedback.phase}/{r2.task_feedback.reason_code}")


# ════════════════════════════════════════════════════════════════
# TEST D — No internal allocation: enemy4 closer, still enemy3
# ════════════════════════════════════════════════════════════════
def test_D_no_internal_allocation():
    print("== TEST D: enemy4 closer, real tree always uses enemy3 ==")
    ex = usv_exec()
    ex.submit_task(bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                                   bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3"))
    tracks = {"enemy_3": trk([150000, 300000]), "enemy_4": trk([20000, 300000])}
    for i in range(1, 6):
        r = ex.tick(ctx(tracks=tracks, t=float(i)))
        for a in r.action_requests:
            check(f"tick {i}: target is enemy_3 (never enemy_4)",
                  a.target_id == "enemy_3" or a.target_id is None, str(a.target_id))
    check("feedback target_id is enemy_3", ex.last_feedback.target_id == "enemy_3")


# ════════════════════════════════════════════════════════════════
# TEST E — Single writer: HARNESS mode, zero BT-side simulator writes
# ════════════════════════════════════════════════════════════════
def test_E_single_writer():
    print("== TEST E: HARNESS mode — BT-side simulator writes = 0 ==")
    check("HARNESS_BT_MODE True", bhi.HARNESS_BT_MODE is True)
    tree = rt.build_usv_tree("white_usv1")
    bridge = rt.BTBridge()
    forbidden = ["apply", "status", "start", "stop", "result", "legal_actions",
                 "grpc", "requests", "engine", "cmd_sail", "unit_by_name", "get_state",
                 "gen_platform", "turn_on"]
    for attr in forbidden:
        check(f"real tree has no sim writer '{attr}'", not hasattr(tree, attr))
        check(f"real bridge has no sim writer '{attr}'", not hasattr(bridge, attr))
    # executing a full cycle must not touch network
    import bt_harness_interface as _m
    class _Poke:
        def __getattr__(self, k):
            raise AssertionError("BT must never touch network in harness mode")
    saved = getattr(_m, "requests", None)
    _m.requests = _Poke()
    try:
        ex = usv_exec()
        ex.submit_task(bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1",
                                       bhi.PlatformType.USV, bhi.TaskType.INTERCEPT_LOCK,
                                       target_id="enemy_3"))
        r = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}))
        check("real-tree submit+tick with no network access", r.tick_id == 1)
    finally:
        if saved is None:
            del _m.requests
        else:
            _m.requests = saved


# ════════════════════════════════════════════════════════════════
# Standalone BT mode regression: tree ticks standalone (no harness wrapper)
# ════════════════════════════════════════════════════════════════
def test_standalone_mode():
    print("== STANDALONE BT mode regression ==")
    tree = rt.build_usv_tree("white_usv1")
    tree.active_task = bhi.TaskCommand("standalone_task", "white_usv1", bhi.PlatformType.USV,
                                       bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3")
    bridge = rt.BTBridge()
    ctx1 = ctx(tracks={"enemy_3": trk([150000, 300000])}, t=0.0)
    bridge.pre_tick(tree, ctx1)
    status, actions, fb = tree.tick()
    check("standalone: real tree ticks and emits ActionRequest",
          status in ("RUNNING", "SUCCESS") and len(actions) >= 1,
          f"{status}/{len(actions)}")
    check("standalone: ActionRequests are intent-level (no gRPC writer involved)",
          all(isinstance(a, bhi.ActionRequest) for a in actions))


def main():
    tests = [test_A_real_usv_tree, test_B_real_uav_tree, test_C_safety_no_repeat,
             test_D_no_internal_allocation, test_E_single_writer, test_standalone_mode]
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
