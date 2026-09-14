#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_bt_harness_interface.py — 8 minimal interface tests for the Harness×BT adapter.

Run: python test_bt_harness_interface.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bt_harness_interface as bhi                       # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


def ctx(platform_id="white_usv1", ptype=bhi.PlatformType.USV, sim_time=0.0,
        tracks=None, platform_state=None, safety=None):
    return bhi.ExecutionContext(
        platform_id=platform_id, platform_type=ptype, sim_time=sim_time,
        platform_state=platform_state or {"name": platform_id, "position": [0.0, 300000.0],
                                          "speed": 20.0, "heading": 90.0, "is_alive": True},
        tracks=tracks or {},
        safety_feedback=safety)


def trk(pos, visible=True, confidence=1.0):
    return {"position": list(pos), "visible": visible, "confidence": confidence}


# ── TEST 1: submit once → tick 5 times, task persists (no re-init) ──
def test_1_task_persists_across_ticks():
    print("== TEST 1: submit once → tick 5 times, no re-initialization ==")
    ex = bhi.BTPlatformExecutive("white_usv1", bhi.PlatformType.USV)
    cmd = bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                          bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3")
    ack = ex.submit_task(cmd)
    check("submit accepted", ack.code == bhi.AckCode.ACCEPTED, ack.code)
    for i in range(1, 6):
        r = ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, sim_time=float(i)))
        check(f"tick {i}: task_id persists + tick_id increments",
              r.task_feedback.task_id == "usv1_enemy3_intercept" and r.tick_id == i,
              f"{r.task_feedback.task_id}/{r.tick_id}")
    check("tree.active_task not re-initialized",
          ex.tree.active_task is cmd and ex.tree.active_task.target_id == "enemy_3")


# ── TEST 2: duplicate submit → DUPLICATE_IGNORED ──
def test_2_duplicate_submit():
    print("== TEST 2: duplicate submit → DUPLICATE_IGNORED ==")
    ex = bhi.BTPlatformExecutive("white_usv1", bhi.PlatformType.USV)
    cmd = bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                          bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3")
    ex.submit_task(cmd)
    ack2 = ex.submit_task(bhi.TaskCommand(
        "usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
        bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3", revision=1))
    check("duplicate submit → DUPLICATE_IGNORED", ack2.code == bhi.AckCode.DUPLICATE_IGNORED,
          ack2.code)


# ── TEST 3: old revision → STALE_REJECTED ──
def test_3_stale_revision():
    print("== TEST 3: old revision → STALE_REJECTED ==")
    ex = bhi.BTPlatformExecutive("white_usv1", bhi.PlatformType.USV)
    ex.submit_task(bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                                   bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3", revision=2))
    stale = ex.submit_task(bhi.TaskCommand(
        "usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
        bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3", revision=1))
    check("old revision → STALE_REJECTED", stale.code == bhi.AckCode.STALE_REJECTED, stale.code)
    upd = ex.submit_task(bhi.TaskCommand(
        "usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
        bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3", revision=3))
    check("newer revision accepted (update)", upd.code in (bhi.AckCode.ACCEPTED,), upd.code)


# ── TEST 4: target immutable (enemy_3 stays even if enemy_4 closer) ──
def test_4_target_immutable():
    print("== TEST 4: assigned target=enemy_3 stays even if enemy_4 closer ==")
    ex = bhi.BTPlatformExecutive("white_usv1", bhi.PlatformType.USV)
    cmd = bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                          bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3")
    ex.submit_task(cmd)
    # enemy_4 is much closer; enemy_3 far. Tree must NOT switch.
    tracks = {"enemy_3": trk([150000, 300000]), "enemy_4": trk([10000, 300000])}
    for i in range(3):
        r = ex.tick(ctx(tracks=tracks, sim_time=float(i)))
        for ar in r.action_requests:
            check(f"tick {i+1}: target_id is enemy_3 (never enemy_4)",
                  ar.target_id == "enemy_3" or ar.target_id is None,
                  f"got {ar.target_id}")
    check("feedback target is enemy_3", ex.last_feedback.target_id == "enemy_3")


# ── TEST 5: target lost → local reacquire → timeout → need_reallocation ──
def test_5_target_lost_reacquire():
    print("== TEST 5: lost → reacquire → timeout → need_reallocation ==")
    ex = bhi.BTPlatformExecutive("white_usv1", bhi.PlatformType.USV)
    ex.submit_task(bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                                   bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3"))
    r1 = ex.tick(ctx(tracks={}, sim_time=0.0))  # enemy_3 not in tracks → lost
    check("lost → REACQUIRE phase, target still enemy_3, no realloc yet",
          r1.task_feedback.phase == bhi.Phase.REACQUIRE and
          r1.task_feedback.target_id == "enemy_3" and
          r1.task_feedback.need_reallocation is False,
          f"{r1.task_feedback.phase}/{r1.task_feedback.need_reallocation}")
    r2 = ex.tick(ctx(tracks={}, sim_time=bhi.REACQUIRE_TIMEOUT_S + 1))
    check("reacquire timeout → need_reallocation=True, reason=TARGET_LOST_TIMEOUT",
          r2.task_feedback.need_reallocation is True and
          r2.task_feedback.reason_code == bhi.FeedbackReason.TARGET_LOST_TIMEOUT,
          f"{r2.task_feedback.need_reallocation}/{r2.task_feedback.reason_code}")
    # visible again → resumes on the SAME target
    r3 = ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, sim_time=bhi.REACQUIRE_TIMEOUT_S + 2))
    check("re-detected → reacquire cleared, same target",
          r3.task_feedback.target_id == "enemy_3" and r3.task_feedback.phase != bhi.Phase.REACQUIRE)


# ── TEST 6: BT ActionRequest → POST /apply payload ──
def test_6_action_adapter():
    print("== TEST 6: BT ActionRequest → /apply payload ==")
    ad = bhi.BTActionAdapter()
    reqs = [
        bhi.ActionRequest("white_usv1", bhi.ActionKind.APPROACH_TARGET, target_id="enemy_3",
                          waypoint=(150000, 300000), course=90.0),
        bhi.ActionRequest("white_usv1", bhi.ActionKind.ENGAGE_TARGET, target_id="enemy_3",
                          waypoint=(150000, 300000)),
        bhi.ActionRequest("white_uav1", bhi.ActionKind.RETURN_TO_BASE,
                          waypoint=(0.0, 300000.0), course=270.0),
        bhi.ActionRequest("white_uav1", bhi.ActionKind.LAND_OR_DOCK,
                          waypoint=(0.0, 300000.0), meta={"home": "white_usv1"}),
        bhi.ActionRequest("white_usv2", bhi.ActionKind.HOLD, target_id=None),
    ]
    payload = ad.to_apply_payload(reqs)
    texts = [a["action_text"] for a in payload["actions"]]
    types = [a["action_type"] for a in payload["actions"]]
    check("approach → move action", texts[0].startswith("white_usv1 移动 target_speed=") and types[0] == "move", texts[0])
    check("engage → lock enemy_3", texts[1] == "white_usv1 锁定 enemy_3" and types[1] == "lock", texts[1])
    check("return → fly", texts[2].startswith("white_uav1 飞行 ") and types[2] == "fly", texts[2])
    check("land → land_uav", texts[3].startswith("white_uav1 降落 ") and types[3] == "land_uav", texts[3])
    check("hold → move hold", types[4] == "move", texts[4])
    check("payload has 'actions' key (POST /apply body)", "actions" in payload)


# ── TEST 7: HARNESS_BT_MODE → no BT-side simulator write ──
def test_7_no_bt_sim_writes():
    print("== TEST 7: HARNESS_BT_MODE — no BT-side gRPC/HTTP writes ==")
    check("HARNESS_BT_MODE is True", bhi.HARNESS_BT_MODE is True)
    # the stub tree/bridge expose NO simulator/network surface
    tree = bhi.StubBehaviorTree("white_usv1", bhi.PlatformType.USV)
    bridge = bhi.StubBTBridge()
    forbidden = ["apply", "status", "start", "stop", "result", "legal_actions", "grpc",
                 "requests", "engine", "cmd_", "sail", "unit_by_name", "get_state"]
    for attr in forbidden:
        check(f"tree has no sim writer attribute '{attr}'",
              not hasattr(tree, attr))
        check(f"bridge has no sim writer attribute '{attr}'",
              not hasattr(bridge, attr))
    # executing submit+tick performs no network call (patch requests to raise)
    import bt_harness_interface as _m
    class _Poke:
        def __getattr__(self, k):
            raise AssertionError("BT must never touch network in harness mode")
    saved = getattr(_m, "requests", None)
    _m.requests = _Poke()
    try:
        ex = bhi.BTPlatformExecutive("white_usv1", bhi.PlatformType.USV)
        ex.submit_task(bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                                       bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3"))
        r = ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}))
        check("submit+tick completes with no network access", r.tick_id == 1)
    finally:
        if saved is None:
            del _m.requests
        else:
            _m.requests = saved


# ── TEST 8: ActionSafety REJECTED visible to BT next tick ──
def test_8_safety_feedback_visible():
    print("== TEST 8: REJECTED action visible in ExecutionContext next tick ==")
    ex = bhi.BTPlatformExecutive("white_usv1", bhi.PlatformType.USV)
    ex.submit_task(bhi.TaskCommand("usv1_enemy3_intercept", "white_usv1", bhi.PlatformType.USV,
                                   bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3"))
    r1 = ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, sim_time=0.0))
    check("tick1 emits an action request", len(r1.action_requests) >= 1)
    # next tick carries ActionSafety rejection for the emitted action
    adv = bhi.BTActionAdapter()
    text = adv.to_apply_payload(r1.action_requests)["actions"][0]["action_text"]
    r2 = ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, sim_time=1.0,
                     safety={text: "REJECTED"}))
    check("tick2 sees rejection → HOLD fallback + SAFETY_REJECTED reason",
          r2.task_feedback.reason_code == bhi.FeedbackReason.SAFETY_REJECTED and
          r2.task_feedback.phase == bhi.Phase.HOLD,
          f"{r2.task_feedback.reason_code}/{r2.task_feedback.phase}")


def main():
    tests = [test_1_task_persists_across_ticks,
             test_2_duplicate_submit,
             test_3_stale_revision,
             test_4_target_immutable,
             test_5_target_lost_reacquire,
             test_6_action_adapter,
             test_7_no_bt_sim_writes,
             test_8_safety_feedback_visible]
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
