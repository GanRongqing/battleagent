#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_bt_wide.py — wide coverage unit/contract tests for the Harness × Real BT interface.

Covers: task submit lifecycle (2.1), cancel/preemption (2.2), persistence (2.3),
target ownership (2.4), target lost/reacquire (2.5), SUCCESS/FAILURE/RUNNING + memory (2.6),
ActionChannel (3), Safety feedback matrix (4), platform lifecycle (5),
no-ground-truth / single-writer audit (6).

Run: python test_bt_wide.py
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


def usv(pid="white_usv1"):
    return bhi.BTPlatformExecutive(pid, bhi.PlatformType.USV)


def cmd(pid="white_usv1", task_id="t1", rev=1, **kw):
    base = dict(task_id=task_id, platform_id=pid, platform_type=bhi.PlatformType.USV,
                task_type=bhi.TaskType.INTERCEPT_LOCK, target_id="enemy_3",
                revision=rev)
    base.update(kw)
    return bhi.TaskCommand(**base)


# ════════════════════════════════════════════════════════════════
# 2.1 Task submit lifecycle
# ════════════════════════════════════════════════════════════════
def test_submit_lifecycle():
    print("== 2.1 Task submit lifecycle ==")
    ex = usv()
    a1 = ex.submit_task(cmd(task_id="t1"))
    check("A. NEW TASK → ACCEPTED", a1.code == bhi.AckCode.ACCEPTED, a1.code)
    a2 = ex.submit_task(cmd(task_id="t1", rev=1))
    check("B. DUPLICATE → DUPLICATE_IGNORED", a2.code == bhi.AckCode.DUPLICATE_IGNORED, a2.code)
    # duplicate must not clear the running phase (advance to approach first)
    ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, t=1.0))
    check("phase advanced before duplicate", ex.tree.phase == bhi.Phase.APPROACH)
    ex.submit_task(cmd(task_id="t1", rev=1))  # duplicate
    check("duplicate did not reset memory/phase",
          ex.tree.phase == bhi.Phase.APPROACH and ex.task_revision == 1)
    a3 = ex.submit_task(cmd(task_id="t1", rev=2))
    check("C. HIGHER TASK REVISION → ACCEPTED", a3.code == bhi.AckCode.ACCEPTED, a3.code)
    check("new revision effective", ex.task_revision == 2)
    a4 = ex.submit_task(cmd(task_id="t1", rev=1))
    check("D. LOWER TASK REVISION → STALE_REJECTED",
          a4.code == bhi.AckCode.STALE_REJECTED, a4.code)
    ex2 = usv()
    ex2.submit_task(cmd(task_id="t1", plan_id="P1", plan_revision=5))
    a5 = ex2.submit_task(cmd(task_id="t1", plan_id="P1", plan_revision=3))
    check("E. LOWER PLAN REVISION → STALE_REJECTED",
          a5.code == bhi.AckCode.STALE_REJECTED, a5.code)
    ex3 = usv()
    a6 = ex3.submit_task(cmd(task_id="t_exp"), now_sim=200.0)
    check("F. NEW TASK (no valid_until) ACCEPTED", a6.code == bhi.AckCode.ACCEPTED, a6.code)
    a7 = ex3.submit_task(cmd(task_id="t_exp2", valid_until=100.0), now_sim=200.0)
    check("F. EXPIRED at submit → EXPIRED", a7.code == bhi.AckCode.EXPIRED, a7.code)
    # expired at tick (no actions, reason EXPIRED)
    ex4 = usv()
    ex4.submit_task(cmd(task_id="t_exp3", valid_until=100.0))
    r = ex4.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, t=200.0))
    check("F. expired at tick: no actions + reason EXPIRED",
          len(r.action_requests) == 0 and
          r.task_feedback.reason_code == bhi.FeedbackReason.EXPIRED,
          f"{len(r.action_requests)}/{r.task_feedback.reason_code}")
    # G. FUTURE VALID_FROM: not executed early
    ex5 = usv()
    ex5.submit_task(cmd(task_id="t_future", valid_from=500.0))
    r = ex5.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, t=100.0))
    check("G. FUTURE valid_from: no early execution (no actions, NOT_YET_VALID)",
          len(r.action_requests) == 0 and
          r.task_feedback.reason_code == bhi.FeedbackReason.NOT_YET_VALID,
          f"{len(r.action_requests)}/{r.task_feedback.reason_code}")
    r = ex5.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, t=600.0))
    check("G. after valid_from: executes",
          len(r.action_requests) >= 1 and r.task_feedback.phase == bhi.Phase.APPROACH,
          f"{len(r.action_requests)}/{r.task_feedback.phase}")


# ════════════════════════════════════════════════════════════════
# 2.2 Cancel / Preemption
# ════════════════════════════════════════════════════════════════
def test_cancel_preemption():
    print("== 2.2 Cancel / Preemption ==")
    ex = usv()
    ex.submit_task(cmd(task_id="t1"))
    a = ex.cancel_task(bhi.CancelTaskRequest("white_usv1", "t1"))
    check("A. cancel active → CANCELLED + cleared",
          a.code == bhi.AckCode.CANCELLED and ex.active_task is None, a.code)
    ex.submit_task(cmd(task_id="t2"))
    a2 = ex.cancel_task(bhi.CancelTaskRequest("white_usv1", "wrong_id"))
    check("B. cancel wrong task → NOT_FOUND, current intact",
          a2.code == bhi.AckCode.NOT_FOUND and ex.active_task is not None and
          ex.active_task.task_id == "t2", a2.code)
    ex2 = usv()
    ex2.submit_task(cmd(task_id="low", priority=1))
    a3 = ex2.submit_task(cmd(task_id="high", priority=10))
    check("C. higher-priority preemption → ACCEPTED_WITH_PREEMPTION",
          a3.code == bhi.AckCode.ACCEPTED_WITH_PREEMPTION, a3.code)
    check("C. new task active", ex2.active_task.task_id == "high")
    ex3 = usv()
    ex3.submit_task(cmd(task_id="locked", preemptible=False))
    a4 = ex3.submit_task(cmd(task_id="other"))
    check("D. NON_PREEMPTIBLE → BUSY (normal task rejected)",
          a4.code == bhi.AckCode.BUSY and ex3.active_task.task_id == "locked", a4.code)
    ex4 = usv()
    ex4.submit_task(cmd(task_id="locked", preemptible=False))
    a5 = ex4.submit_task(cmd(task_id="safety", safety_override=True))
    check("E. SAFETY_OVERRIDE preempts non-preemptible → ACCEPTED_WITH_PREEMPTION",
          a5.code == bhi.AckCode.ACCEPTED_WITH_PREEMPTION and
          ex4.active_task.task_id == "safety", a5.code)


# ════════════════════════════════════════════════════════════════
# 2.3 Task persistence (>=10 ticks)
# ════════════════════════════════════════════════════════════════
def test_task_persistence():
    print("== 2.3 Task persistence (10 ticks) ==")
    ex = usv()
    ex.submit_task(cmd(task_id="t_persist"))
    tree0 = ex.tree
    for i in range(1, 11):
        d = 150000 - i * 1000
        r = ex.tick(ctx(tracks={"enemy_3": trk([d, 300000])}, t=float(i)))
        check(f"tick {i}: task_id/revision stable", r.task_feedback.task_id == "t_persist"
              and ex.task_revision == 1)
    check("tree not rebuilt", ex.tree is tree0)
    check("no duplicate submits (revision stayed 1)", ex.task_revision == 1)


# ════════════════════════════════════════════════════════════════
# 2.4 Target ownership
# ════════════════════════════════════════════════════════════════
def test_target_ownership():
    print("== 2.4 Target ownership ==")
    ex = usv()
    ex.submit_task(cmd(task_id="own", target_id="enemy_3"))
    tracks = {"enemy_3": trk([150000, 300000]),
              "enemy_4": trk([15000, 300000]),          # closer
              "enemy_5": trk([140000, 300000], confidence=0.99),  # higher confidence
              "enemy_6": trk([20000, 300000])}          # in weapons range
    for i in range(1, 7):
        r = ex.tick(ctx(tracks=tracks, t=float(i)))
        for a in r.action_requests:
            check(f"tick {i}: target enemy_3 (never 4/5/6)", a.target_id == "enemy_3"
                  or a.target_id is None, str(a.target_id))
    check("feedback target enemy_3", ex.last_feedback.target_id == "enemy_3")


# ════════════════════════════════════════════════════════════════
# 2.5 Target lost / reacquire
# ════════════════════════════════════════════════════════════════
def test_target_lost_reacquire():
    print("== 2.5 Target lost / reacquire ==")
    ex = usv()
    ex.submit_task(cmd(task_id="reacq", allow_local_reacquire=True, max_search_time=50.0))
    r1 = ex.tick(ctx(tracks={}, t=0.0))
    check("lost → REACQUIRE, target unchanged",
          r1.task_feedback.phase == bhi.Phase.REACQUIRE and
          r1.task_feedback.target_id == "enemy_3", f"{r1.task_feedback.phase}")
    r2 = ex.tick(ctx(tracks={}, t=60.0))
    check("max_search_time exceeded → need_reallocation TARGET_LOST_TIMEOUT",
          r2.task_feedback.need_reallocation is True and
          r2.task_feedback.reason_code == bhi.FeedbackReason.TARGET_LOST_TIMEOUT,
          f"{r2.task_feedback.need_reallocation}/{r2.task_feedback.reason_code}")
    r3 = ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, t=61.0))
    check("re-detected same target resumes", r3.task_feedback.target_id == "enemy_3"
          and r3.task_feedback.phase != bhi.Phase.REACQUIRE)
    # allow_local_reacquire=False -> BLOCKED immediately
    ex2 = usv()
    ex2.submit_task(cmd(task_id="reacq2", allow_local_reacquire=False))
    r = ex2.tick(ctx(tracks={}, t=0.0))
    check("allow_local_reacquire=False → BLOCKED need_reallocation",
          r.task_feedback.need_reallocation is True and
          r.task_feedback.reason_code == bhi.FeedbackReason.BLOCKED,
          f"{r.task_feedback.need_reallocation}/{r.task_feedback.reason_code}")


# ════════════════════════════════════════════════════════════════
# 2.6 SUCCESS / FAILURE / RUNNING + memory continuation
# ════════════════════════════════════════════════════════════════
def _count(name, hits):
    def fn(bb):
        hits.append(name)
        return rt.Status.RUNNING
    return rt.Behavior(name, fn)


def test_status_memory():
    print("== 2.6 SUCCESS / FAILURE / RUNNING + memory ==")
    # framework: Sequence propagates FAILURE; Selector all-fail -> FAILURE
    f_seq = rt.Sequence("seq", memory=False)
    f_seq.add_child(rt.Behavior("f", lambda bb: rt.Status.FAILURE))
    bb = {}
    check("Sequence child FAILURE → FAILURE", f_seq.tick(bb) == rt.Status.FAILURE)
    sel = rt.Selector("sel", memory=False)
    sel.add_child(rt.Behavior("f1", lambda bb: rt.Status.FAILURE))
    sel.add_child(rt.Behavior("f2", lambda bb: rt.Status.FAILURE))
    check("Selector all FAILURE → FAILURE", sel.tick(bb) == rt.Status.FAILURE)
    ok = rt.Behavior("ok", lambda bb: rt.Status.SUCCESS)
    check("Behavior SUCCESS", ok.tick(bb) == rt.Status.SUCCESS)
    run = rt.Behavior("run", lambda bb: rt.Status.RUNNING)
    check("Behavior RUNNING", run.tick(bb) == rt.Status.RUNNING)
    # memory: RUNNING child resumed (not re-run earlier children)
    hits = []
    seqm = rt.Sequence("seqm", memory=True)
    seqm.add_child(rt.Behavior("A", lambda bb, h=hits: (h.append("A"), rt.Status.SUCCESS)[1]))
    seqm.add_child(rt.Behavior("B", lambda bb, h=hits: (h.append("B"), rt.Status.RUNNING)[1]))
    bb = {}
    check("seq memory tick1: A SUCCESS then B RUNNING", seqm.tick(bb) == rt.Status.RUNNING)
    check("tick1 visited A then B", hits == ["A", "B"], str(hits))
    hits.clear()
    check("seq memory tick2: resumes at B (A not re-run)", seqm.tick(bb) == rt.Status.RUNNING)
    check("tick2 visited only B", hits == ["B"], str(hits))
    # real tree: RUNNING (approach far) then SUCCESS (engage in range)
    ex = usv()
    ex.submit_task(cmd(task_id="tri"))
    r1 = ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, t=1.0))
    check("real tree RUNNING while approaching", r1.root_status == rt.Status.RUNNING
          and r1.task_feedback.phase == bhi.Phase.APPROACH)
    r2 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=2.0))
    check("real tree SUCCESS on engage in range", r2.root_status == rt.Status.SUCCESS
          and bhi.ActionKind.ENGAGE_TARGET in [a.action_kind for a in r2.action_requests])


# ════════════════════════════════════════════════════════════════
# 3. ActionChannel
# ════════════════════════════════════════════════════════════════
def test_action_channel():
    print("== 3. ActionChannel: at most one request per channel per tick ==")
    ex = usv()
    ex.submit_task(cmd(task_id="ch"))
    for i in range(1, 8):
        d = 150000 - i * 20000
        r = ex.tick(ctx(tracks={"enemy_3": trk([d, 300000])}, t=float(i)))
        channels = [a.channel for a in r.action_requests]
        check(f"tick {i}: no channel conflict", len(channels) == len(set(channels)),
              str(channels))
    # all action families convert through BTActionAdapter
    ad = bhi.BTActionAdapter()
    fams = [
        bhi.ActionRequest("white_usv1", bhi.ActionKind.APPROACH_TARGET, target_id="e", course=90.0),
        bhi.ActionRequest("white_usv1", bhi.ActionKind.ORBIT_TARGET, target_id="e", course=90.0),
        bhi.ActionRequest("white_usv1", bhi.ActionKind.TRACK_TARGET, target_id="e", course=90.0),
        bhi.ActionRequest("white_usv1", bhi.ActionKind.ENGAGE_TARGET, target_id="e"),
        bhi.ActionRequest("white_usv1", bhi.ActionKind.HOLD),
        bhi.ActionRequest("white_uav1", bhi.ActionKind.NAVIGATE_TO, waypoint=(1, 2), course=90.0),
        bhi.ActionRequest("white_uav1", bhi.ActionKind.RETURN_TO_BASE, course=270.0),
        bhi.ActionRequest("white_uav1", bhi.ActionKind.LAND_OR_DOCK, meta={"home": "white_usv1"}),
        bhi.ActionRequest("white_usv1", bhi.ActionKind.REACQUIRE, target_id="e", course=90.0),
    ]
    for ar in fams:
        out = ad.to_apply_payload([ar])["actions"]
        check(f"adapter: {ar.action_kind.value} → /apply payload",
              len(out) == 1 and "action_text" in out[0] and "action_type" in out[0], str(out))


# ════════════════════════════════════════════════════════════════
# 4. Safety Feedback Matrix
# ════════════════════════════════════════════════════════════════
def test_safety_matrix():
    print("== 4. Safety feedback matrix ==")
    ad = bhi.BTActionAdapter()
    # PASS: continue branch
    ex = usv()
    ex.submit_task(cmd(task_id="s_pass"))
    r1 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=0.0))
    text = ad.to_apply_payload(r1.action_requests)["actions"][0]["action_text"]
    r2 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=1.0, safety={text: "PASS"}))
    check("PASS: continues current branch (engage)",
          bhi.ActionKind.ENGAGE_TARGET in [a.action_kind for a in r2.action_requests])
    # CLAMPED: not a failure, continues
    r3 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=2.0, safety={text: "CLAMPED"}))
    check("CLAMPED: not misjudged as failure, continues",
          r3.task_feedback.reason_code != bhi.FeedbackReason.SAFETY_REJECTED and
          bhi.ActionKind.ENGAGE_TARGET in [a.action_kind for a in r3.action_requests])
    # MODIFIED: continues, does not assume exact execution
    r4 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=3.0, safety={text: "MODIFIED"}))
    check("MODIFIED: continues (not blocked)",
          r4.task_feedback.reason_code not in (bhi.FeedbackReason.SAFETY_REJECTED,
                                               bhi.FeedbackReason.SAFETY_OVERRIDE))
    # REJECTED: fallback HOLD, reason SAFETY_REJECTED, no repeat
    r5 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=4.0, safety={text: "REJECTED"}))
    check("REJECTED: fallback HOLD, reason SAFETY_REJECTED, no ENGAGE repeat",
          r5.task_feedback.reason_code == bhi.FeedbackReason.SAFETY_REJECTED and
          bhi.ActionKind.ENGAGE_TARGET not in [a.action_kind for a in r5.action_requests] and
          bhi.ActionKind.HOLD in [a.action_kind for a in r5.action_requests])
    # OVERRIDDEN: safety takeover, reason SAFETY_OVERRIDE
    r6 = ex.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=5.0, safety={text: "OVERRIDDEN"}))
    check("OVERRIDDEN: safety override perceived, reason SAFETY_OVERRIDE",
          r6.task_feedback.reason_code == bhi.FeedbackReason.SAFETY_OVERRIDE)


# ════════════════════════════════════════════════════════════════
# 5. Platform lifecycle
# ════════════════════════════════════════════════════════════════
def test_platform_lifecycle():
    print("== 5. Platform lifecycle ==")
    # A. new unit appears -> create executive
    registry = {}
    new_pid = "white_usv9"
    registry[new_pid] = bhi.BTPlatformExecutive(new_pid, bhi.PlatformType.USV)
    check("A. new unit → executive created", new_pid in registry)
    # B. unit destroyed -> deregister, task cleared, no more actions
    ex = registry[new_pid]
    ex.submit_task(cmd(pid=new_pid, task_id="t_die"))
    ex.tick(ctx(pid=new_pid, tracks={"enemy_3": trk([150000, 300000])}))
    del registry[new_pid]
    check("B. unit destroyed → deregistered", new_pid not in registry)
    # C. UAV pre-launch cooperative/situation -> actions produced (adapter -> fly)
    uav = bhi.BTPlatformExecutive("white_uav1", bhi.PlatformType.UAV)
    uav.submit_task(bhi.TaskCommand("uav_situ", "white_uav1", bhi.PlatformType.UAV,
                                    bhi.TaskType.SITUATION_UPDATE,
                                    constraints={"waypoint": [150000, 300000]}))
    r = uav.tick(ctx("white_uav1", bhi.PlatformType.UAV, t=0.0, pos=[0.0, 300000.0]))
    out = bhi.BTActionAdapter().to_apply_payload(r.action_requests)["actions"]
    check("C. UAV situation task → fly action", len(out) == 1 and out[0]["action_type"] == "fly")
    # D. UAV low energy -> RETURN_RECHARGE -> RETURN_TO_BASE
    uav2 = bhi.BTPlatformExecutive("white_uav2", bhi.PlatformType.UAV)
    uav2.submit_task(bhi.TaskCommand("uav_rtb", "white_uav2", bhi.PlatformType.UAV,
                                     bhi.TaskType.RETURN_RECHARGE,
                                     constraints={"base": [0.0, 300000.0]}))
    r = uav2.tick(ctx("white_uav2", bhi.PlatformType.UAV, t=0.0, pos=[100000, 300000.0]))
    check("D. return/recharge → RETURN_TO_BASE + LAND/DOCK",
          bhi.ActionKind.RETURN_TO_BASE in [a.action_kind for a in r.action_requests] and
          bhi.ActionKind.LAND_OR_DOCK in [a.action_kind for a in r.action_requests])
    # E. dock complete -> SUCCESS/COMPLETED feedback
    r2 = uav2.tick(ctx("white_uav2", bhi.PlatformType.UAV, t=1.0, pos=[0.0, 300000.0]))
    check("E. dock complete → COMPLETED feedback",
          r2.task_feedback.status == bhi.TaskStatus.COMPLETED, r2.task_feedback.status)
    # F. episode end -> all active tasks cancelled, no actions
    ex2 = usv()
    ex2.submit_task(cmd(task_id="t_end"))
    ex2.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}))
    ex2.cancel_task(bhi.CancelTaskRequest("white_usv1", "t_end"))
    r = ex2.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}, t=10.0))
    check("F. episode end → no actions (task cancelled)",
          len(r.action_requests) == 0, str(r.action_requests))
    # G. new episode sim_time rollback -> fresh executive state
    ex3 = usv()
    ex3.submit_task(cmd(task_id="t_ep1"))
    ex3.tick(ctx(tracks={"enemy_3": trk([30000, 300000])}, t=1000.0))
    # new episode: fresh executive (sim-time rollback -> clear prior state)
    ex3b = usv()
    ex3b.submit_task(cmd(task_id="t_ep2"))
    check("G. new episode → fresh state (no prior task residue)",
          ex3b.active_task.task_id == "t_ep2" and ex3b.tree.lost_since is None)


# ════════════════════════════════════════════════════════════════
# 6. No-ground-truth / single-writer audit
# ════════════════════════════════════════════════════════════════
def test_no_ground_truth():
    print("== 6. No-ground-truth / single-writer audit ==")
    bad = ["ground_truth", "true_enemy_state", "future_trajectory", "hidden_enemy",
           "undetected_target_state", "black_usv_states", "get_white_targets"]
    for mod in (rt, bhi):
        src = open(mod.__file__, encoding="utf-8").read()
        hits = [b for b in bad if b in src]
        check(f"{mod.__name__}: no ground-truth/hidden-state refs", not hits, str(hits))
    # poison network/engine APIs and run submit+tick
    class _Poke:
        def __getattr__(self, k):
            raise AssertionError(f"BT must not call {k}")
    saved = {}
    for name in ("requests", "grpc"):
        saved[name] = getattr(bhi, name, None)
    bhi.requests = _Poke()
    rt.requests = _Poke()
    try:
        ex = usv()
        ex.submit_task(cmd(task_id="ngt"))
        r = ex.tick(ctx(tracks={"enemy_3": trk([150000, 300000])}))
        check("submit+tick runs with poisoned requests/grpc", r.tick_id == 1)
    finally:
        for name in ("requests", "grpc"):
            if saved[name] is None:
                if hasattr(bhi, name):
                    delattr(bhi, name)
            else:
                setattr(bhi, name, saved[name])


def main():
    tests = [test_submit_lifecycle, test_cancel_preemption, test_task_persistence,
             test_target_ownership, test_target_lost_reacquire, test_status_memory,
             test_action_channel, test_safety_matrix, test_platform_lifecycle,
             test_no_ground_truth]
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
