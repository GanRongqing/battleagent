#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_v6_audit_units.py — V6 per-step A→F audit + stale-response protection unit tests.

Covers (offline, no server, no provider):
  1. explicit persistent audit_step_id + prev-step link
  2. audit manifest
  3. raw observation logging (A)
  4. fused state logging (B)
  5. exact LLM request logging (C)
  6. raw LLM response logging (D)
  7. action logging (E/F)
  8. replay utility (audit_step_replay.py) — reads exactly the step file, never reconstructs
  9. stale response rejection (STALE_REJECTED)
  10. current response acceptance
  11. T1 hidden-state counterfactual (same legal obs + different inaccessible hidden truth
      => same fused state hash, same Commander context hash, same deterministic decision)
  12. T2 HTTP-only truth-mask (one mocked decision cycle with only whitelisted HTTP responses,
      no simulator engine / black-truth object)

Run: python test_v6_audit_units.py
"""
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_hybrid_v5 as a5          # noqa: E402
import runtime_audit                  # noqa: E402
import audit_step_replay              # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


def sha(s):
    return hashlib.sha256(json.dumps(s, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def wait_idle(cmdr, timeout=4.0):
    deadline = time.time() + timeout
    while cmdr.in_flight and time.time() < deadline:
        time.sleep(0.02)


def make_status(usvs, active, uavs=(), now="00:05:00"):
    return {
        "局内时间": now,
        "已结束": False,
        "对局结果": None,
        "资源快照": {
            "统计": {"usv_total": len(usvs), "usv_alive": len(usvs),
                     "uav_total": len(uavs), "uav_alive": len(uavs),
                     "uav_flying": len(uavs), "enemy_visible": len(active)},
            "单位状态": {"white_usv_states": list(usvs), "white_uav_states": list(uavs)},
            "观察信息": {"white_observation": {"雷达捕获": list(active), "被动告警": []}},
        },
        "奖励信号": {"black_killed": 0, "black_hit": 0, "white_ship_killed": 0,
                     "white_uav_killed": 0, "black_breakthrough": 0},
    }


def make_usv(name, x, y=300000, locking=False):
    return {"name": name, "position": [x, y], "is_alive": True, "is_frozen": False,
            "is_locking": locking, "locking_unit": "black_usv1" if locking else None,
            "battery_pct": 100}


def make_active(name, x, vel=(-10, 0), y=300000):
    return {"name": name, "position": [x, y], "velocity": list(vel)}


# ════════════════════════════════════════════════════════════════
# 1-8. StepAudit persistence + C/D append + replay
# ════════════════════════════════════════════════════════════════
def test_stepaudit_persistence_and_manifest():
    print("== test_stepaudit_persistence_and_manifest ==")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "runtime_audit_test_tmp")
    os.makedirs(base, exist_ok=True)
    aud = runtime_audit.StepAudit(run_id="unit", base_dir=base, enabled=True)
    aud.set_run_id("unit")

    rec1 = aud.new_step(300.0, 1000.0)
    check("explicit audit_step_id assigned (1)", rec1 is not None and rec1.step_id == 1)
    check("first step prev_audit_step_id=0", rec1.prev_step_id == 0)
    rec1.set_A(make_status([make_usv("white_usv1", 100000)], [make_active("black_usv1", 150000)]),
               None, {"动作": {"[move]": ["white_usv1 移动"]}})
    rec1.set_B(tracks={"black_usv1": {"name": "black_usv1", "confidence": 1.0}},
               mission="NORMAL_COMBAT", state_signature=[[5], [1], [0]], trigger="first_detect")
    rec1.set_E(intent={"source": "default_intent", "describe": "posture=balanced"},
               allocator={"result": {"black_usv1": ["white_usv1"]}, "margin": 0.05,
                          "candidates": [{"target": "black_usv1", "value": 1.0}]},
               controller={"usv_actions": [["white_usv1 移动", "move"]], "uav_actions": []})
    rec1.set_F(requested_actions=[["white_usv1 移动", "move"]],
               filtered_actions=[{"action_text": "white_usv1 移动", "action_type": "move"}],
               apply_payload={"actions": [{"action_text": "white_usv1 移动"}]},
               apply_response={"成功": True},
               feedback_link={"requested_step_id": 1, "next_audit_step_id": 2})
    rec1.finalize()

    rec2 = aud.new_step(330.0, 1001.0)
    check("second audit_step_id=2", rec2 is not None and rec2.step_id == 2)
    check("second step prev_audit_step_id=1 (chain link)", rec2.prev_step_id == 1)
    rec2.set_A(make_status([make_usv("white_usv1", 100000)], []), None, {})
    rec2.finalize()

    d1 = json.load(open(os.path.join(base, "run_unit", "step_1.json"), encoding="utf-8"))
    check("step file persists audit_step_id", d1["audit_step_id"] == 1)
    check("A: raw /status observation persisted",
          d1["A_raw_observation"]["status"]["资源快照"]["统计"]["usv_alive"] == 1)
    check("A: raw /legal_actions persisted",
          d1["A_raw_observation"]["legal_actions"]["动作"]["[move]"][0] == "white_usv1 移动")
    check("B: fused mission persisted", d1["B_fused_state"]["mission"] == "NORMAL_COMBAT")
    check("B: state_signature persisted",
          d1["B_fused_state"]["state_signature"] == [[5], [1], [0]])
    check("B: trigger persisted", d1["B_fused_state"]["trigger"] == "first_detect")
    check("E: intent source", d1["E_intermediate"]["intent"]["source"] == "default_intent")
    check("E: allocator margin", d1["E_intermediate"]["allocator"]["margin"] == 0.05)
    check("E: allocator candidates",
          d1["E_intermediate"]["allocator"]["candidates"][0]["target"] == "black_usv1")
    check("F: exact /apply payload",
          d1["F_execution_feedback"]["apply_payload"]["actions"][0]["action_text"]
          == "white_usv1 移动")
    check("F: /apply response", d1["F_execution_feedback"]["apply_response"] == {"成功": True})
    check("F: next-step feedback link",
          d1["F_execution_feedback"]["feedback_link"]["next_audit_step_id"] == 2)
    check("meta prev link", d1["prev_audit_step_id"] == 0)

    man = json.load(open(os.path.join(base, "run_unit", "manifest.json"), encoding="utf-8"))
    check("audit manifest written",
          man.get("1") == "step_1.json" and man.get("2") == "step_2.json")


def test_stepaudit_async_c_d_append():
    print("== test_stepaudit_async_c_d_append ==")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "runtime_audit_test_tmp")
    aud = runtime_audit.StepAudit(run_id="unit2", base_dir=base, enabled=True)
    aud.set_run_id("unit2")
    rec = aud.new_step(600.0, 2000.0)
    rec.set_A(make_status([make_usv("white_usv1", 100000)], []), None, {})
    rec.finalize()

    # late async LLM C/D append (simulates commander background thread)
    aud.append(1, "C", {"request_id": 1, "generation": 1, "source_step_id": 1,
                        "source_state_signature": [[5], [1], [0]], "model": "deepseek-v4-flash",
                        "system": "ROLE", "user": "CURRENT TACTICAL STATE:\n\nsummary"})
    aud.append(1, "D", {"request_id": 1, "source_step_id": 1, "stale": False, "applied": True,
                        "raw_text": '{"posture":"aggressive"}', "parsed": "posture=aggressive",
                        "latency": 2.1, "error": None, "source": "deepseek"})
    d = json.load(open(os.path.join(base, "run_unit2", "step_1.json"), encoding="utf-8"))
    check("C: exact LLM request appended", d["C_llm_request"]["request_id"] == 1)
    check("C: exact system+user payload stored",
          d["C_llm_request"]["system"] == "ROLE" and d["C_llm_request"]["user"].startswith(
              "CURRENT TACTICAL STATE"))
    check("D: raw LLM response stored",
          d["D_llm_response"]["raw_text"] == '{"posture":"aggressive"}')
    check("D: parsed + latency stored",
          d["D_llm_response"]["applied"] is True and d["D_llm_response"]["latency"] == 2.1)


def test_replay_utility():
    print("== test_replay_utility ==")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "runtime_audit_test_tmp")
    replay = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_step_replay.py")
    r = subprocess.run([sys.executable, replay, "--run-id", "unit", "--step-id", "1",
                        "--dir", base], capture_output=True, text=True, timeout=20)
    check("replay exits 0 for existing step", r.returncode == 0)
    check("replay prints A-F sections, marks missing as NOT RECORDED",
          "A — RAW LEGAL HTTP OBSERVATION" in r.stdout and "NOT RECORDED" in r.stdout)
    r2 = subprocess.run([sys.executable, replay, "--run-id", "unit", "--step-id", "999",
                         "--dir", base], capture_output=True, text=True, timeout=20)
    check("replay exits 1 + 'Step not found' for missing step (no reconstruction)",
          r2.returncode == 1 and "Step not found" in r2.stdout)
    rec, path = audit_step_replay.load_step("unit", 2, base)
    check("replay load_step reads exact file", rec is not None and rec["audit_step_id"] == 2)


# ════════════════════════════════════════════════════════════════
# 9-10. stale-response protection
# ════════════════════════════════════════════════════════════════
def test_append_before_finalize_preserved():
    print("== test_append_before_finalize_preserved ==")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "runtime_audit_test_tmp")
    aud = runtime_audit.StepAudit(run_id="race", base_dir=base, enabled=True)
    aud.set_run_id("race")
    rec = aud.new_step(600.0, 2000.0)
    rec.set_A(make_status([make_usv("white_usv1", 100000)], []), None, {})
    # simulate the Commander worker appending C BEFORE the main thread finalizes
    aud.append(1, "C", {"request_id": 1, "source_step_id": 1,
                        "system": "ROLE", "user": "summary"})
    rec.set_B(tracks={}, mission="NORMAL_COMBAT", trigger="first_detect")
    rec.set_E(intent={"source": "default_intent", "describe": "posture=balanced"},
              allocator={"result": {}, "margin": None, "candidates": []},
              controller={"usv_actions": [], "uav_actions": []})
    rec.set_F(requested_actions=[], filtered_actions=[],
              apply_payload={"actions": []}, apply_response={}, feedback_link={})
    rec.finalize()  # must NOT destroy the appended C
    d = json.load(open(os.path.join(base, "run_race", "step_1.json"), encoding="utf-8"))
    check("C appended before finalize survives finalize", d["C_llm_request"] is not None
          and d["C_llm_request"]["system"] == "ROLE")
    check("A/B/E/F still present after merge", d["B_fused_state"]["trigger"] == "first_detect"
          and d["A_raw_observation"]["status"] is not None)


def test_stale_response_rejection():
    print("== test_stale_response_rejection ==")
    gate = threading.Event()

    def slow_call(system, user):
        gate.wait(timeout=5.0)
        return '{"posture":"aggressive","focus_level":3,"emergency_focus_level":4,"reason":"t"}'

    cmdr = a5.LLMCommander(enabled=True, skill_text="test", call_fn=slow_call)
    sig_a = (5, 1, 0, 1, 0, 0, 1.0, 0, True, 0, 2)
    started = cmdr.maybe_request(0.0, "summary", [], "first_detect", state_sig=sig_a)
    check("request spawned", started)
    # a NEWER observation advances the state signature while response is in flight
    sig_b = (6, 1, 0, 1, 0, 0, 1.0, 0, True, 0, 2)
    cmdr.maybe_request(10.0, "summary_new", [], "periodic", state_sig=sig_b)
    gate.set()
    wait_idle(cmdr)
    check("stale response rejected (stale_rejected=1)", cmdr.stats["stale_rejected"] == 1)
    check("last-valid intent preserved on stale reject", cmdr.get_intent() == a5.DEFAULT_INTENT)
    check("source unchanged on stale reject", cmdr.last_source == "default_intent")
    check("stale rejection recorded in commander audit",
          any(a.get("fallback_reason") == "stale_rejected" for a in cmdr.audit))


def test_current_response_acceptance():
    print("== test_current_response_acceptance ==")
    gate = threading.Event()

    def ok_call(system, user):
        gate.wait(timeout=5.0)
        return '{"posture":"cautious","focus_level":1,"reason":"ok"}'

    cmdr = a5.LLMCommander(enabled=True, skill_text="test", call_fn=ok_call)
    sig = (5, 1, 0, 1, 0, 0, 1.0, 0, True, 0, 2)
    cmdr.maybe_request(0.0, "summary", [], "first_detect", state_sig=sig)
    # same sig observed again (no material change) -> response stays current
    cmdr.maybe_request(10.0, "summary", [], "periodic", state_sig=sig)
    gate.set()
    wait_idle(cmdr)
    check("no stale rejection for current response", cmdr.stats["stale_rejected"] == 0)
    check("current response accepted and applied",
          cmdr.stats["responses"] == 1 and cmdr.get_intent().posture == "cautious")
    check("source=deepseek on accept", cmdr.last_source == "deepseek")


def test_stale_and_accept_with_audit_c_d():
    print("== test_stale_and_accept_with_audit_c_d ==")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "runtime_audit_test_tmp")
    aud = runtime_audit.StepAudit(run_id="unit3", base_dir=base, enabled=True)
    aud.set_run_id("unit3")
    rec = aud.new_step(900.0, 3000.0)
    rec.set_A(make_status([make_usv("white_usv1", 100000)], []), None, {})
    rec.finalize()

    gate = threading.Event()

    def ok_call(system, user):
        gate.wait(timeout=5.0)
        return '{"posture":"aggressive","focus_level":3,"reason":"t"}'

    cmdr = a5.LLMCommander(enabled=True, skill_text="test", call_fn=ok_call)
    sig = (5, 1, 0, 1, 0, 0, 1.0, 0, True, 0, 2)
    cmdr.maybe_request(0.0, "summary", [], "first_detect", state_sig=sig,
                       audit=aud, source_step_id=1)
    gate.set()
    wait_idle(cmdr)
    d = json.load(open(os.path.join(base, "run_unit3", "step_1.json"), encoding="utf-8"))
    check("C: source_step_id link", d["C_llm_request"]["source_step_id"] == 1)
    check("C: source_state_signature", d["C_llm_request"]["source_state_signature"] is not None)
    check("D: applied response recorded",
          d["D_llm_response"]["applied"] is True and d["D_llm_response"]["source"] == "deepseek")


# ════════════════════════════════════════════════════════════════
# 11. T1 — hidden-state counterfactual
# ════════════════════════════════════════════════════════════════
def test_t1_hidden_state_counterfactual():
    print("== test_t1_hidden_state_counterfactual ==")
    usv = [make_usv("white_usv1", 100000), make_usv("white_usv2", 105000)]
    active = [make_active("black_usv1", 150000), make_active("black_usv2", 165000)]

    # two legal observations that differ ONLY in inaccessible hidden truth (fictional
    # black-side states that the whitelisted HTTP layer must never expose)
    st_a = make_status(usv, active)
    st_b = make_status(usv, active)
    st_b["black_usv_states"] = [{"name": "black_usv1", "position": [999999, 999999],
                                 "velocity": [0, 0]}]  # hidden truth, agent cannot access

    now = a5.parse_sim_time(st_a["局内时间"])
    obs_a, obs_b = a5.Obs(st_a, now), a5.Obs(st_b, now)
    check("raw payloads differ (hidden truth differs)", sha(obs_a.status) != sha(obs_b.status))

    def fused(obs):
        trk = a5.TrackManager()
        trk.update(obs)
        usv_ctrl, uav_mgr = a5.USVController(), a5.UAVManager(enabled=False)
        cov = a5.CoverageMap()
        res = a5.FriendlyResourceState.build(obs, usv_ctrl, uav_mgr, trk, cov, now)
        return trk, res, cov

    ta, ra, ca = fused(obs_a)
    tb, rb, cb = fused(obs_b)
    fa = {n: runtime_audit.serialize_track(t, now) for n, t in ta.tracks.items()}
    fb = {n: runtime_audit.serialize_track(t, now) for n, t in tb.tracks.items()}
    check("T1: same fused-state hash under different hidden truth", sha(fa) == sha(fb))

    summ = a5.TacticalSummarizer(a5.ThreatAllocator())
    sa, _, _ = summ.build_v5(obs_a, ta, a5.USVController(), a5.UAVManager(enabled=False),
                             a5.DEFAULT_INTENT, ra, a5.ThreatClusterBuilder().build(ta.tracks, now),
                             ca, "NORMAL_COMBAT", now)
    sb, _, _ = summ.build_v5(obs_b, tb, a5.USVController(), a5.UAVManager(enabled=False),
                             a5.DEFAULT_INTENT, rb, a5.ThreatClusterBuilder().build(tb.tracks, now),
                             cb, "NORMAL_COMBAT", now)
    check("T1: same Commander request/context under different hidden truth", sa == sb)
    check("T1: hidden truth never reaches Commander context",
          "black_usv_states" not in sa and "999999" not in sa)

    alloc = a5.ThreatAllocator()
    res_a = alloc.allocate_usvs(dict(ta.tracks), obs_a.usvs, {u["name"]: None for u in obs_a.usvs},
                                now, intent=a5.DEFAULT_INTENT)
    res_b = alloc.allocate_usvs(dict(tb.tracks), obs_b.usvs, {u["name"]: None for u in obs_b.usvs},
                                now, intent=a5.DEFAULT_INTENT)
    check("T1: same deterministic decision under different hidden truth",
          sha(res_a) == sha(res_b))


# ════════════════════════════════════════════════════════════════
# 12. T2 — HTTP-only truth-mask (mocked decision cycle)
# ════════════════════════════════════════════════════════════════
class FakeWhitelistClient:
    """Emulates the POMDP API whitelist: NEVER exposes black-side truth."""

    FORBIDDEN = ("black_usv_states", "black_uav_states", "black_strategy",
                 "num_black", "black_total")

    def __init__(self, status_payload, legal_payload):
        self.status_payload = status_payload
        self.legal_payload = legal_payload
        self.applied = []

    def _assert_whitelist(self, d):
        s = json.dumps(d, ensure_ascii=False)
        assert not any(f in s for f in self.FORBIDDEN), "black truth leaked through whitelist!"

    def start(self):
        return {"成功": True, "对局编号": "mock"}

    def status(self):
        self._assert_whitelist(self.status_payload)
        return self.status_payload

    def obs(self):
        return None

    def legal_actions(self):
        return self.legal_payload

    def apply(self, actions):
        self.applied.extend(actions)
        return {"成功": True, "accepted": len(actions)}

    def stop(self):
        return {"成功": True}

    def result(self):
        return {"对局结果": None, "结果说明": "", "奖励信号": {}}


def test_t2_http_only_truth_mask():
    print("== test_t2_http_only_truth_mask ==")
    check("T2: agent module does not import simulator engine", "simulation" not in sys.modules)

    usv = [make_usv("white_usv1", 100000), make_usv("white_usv2", 105000)]
    active = [make_active("black_usv1", 150000), make_active("black_usv2", 165000)]
    status = make_status(usv, active)
    legal = {"动作": {
        "[move]": ["white_usv1 移动", "white_usv2 移动"],
        "[lock]": ["white_usv1 锁定 black_usv1", "white_usv2 锁定 black_usv1",
                   "white_usv1 锁定 black_usv2", "white_usv2 锁定 black_usv2"],
        "[launch_uav]": [], "[fly]": [], "[land_uav]": [],
    }}

    os.environ["LLM_ENABLED"] = "false"
    try:
        am = a5.AgentMain(use_uavs=False, max_steps=100)
        am.client = FakeWhitelistClient(status, legal)
        # enable audit for the mocked cycle so audit_step_id is persisted
        am._audit = runtime_audit.StepAudit(
            run_id="t2", base_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "runtime_audit_test_tmp"), enabled=True)
        am._audit.set_run_id("t2")
        ok = am.step_once()
        check("T2: one mocked decision cycle completed (whitelisted HTTP only)", ok is True)
        check("T2: actions applied through mocked /apply", len(am.client.applied) > 0)
        check("T2: applied actions are whitelist-derived (move/lock/noop)",
              all(a["action_type"] in ("move", "lock", "noop") for a in am.client.applied))
        check("T2: decision cycle assigned audit_step_id=1", am._audit.step_id == 1)
    finally:
        os.environ["LLM_ENABLED"] = "true"


def main():
    tests = [test_stepaudit_persistence_and_manifest,
             test_stepaudit_async_c_d_append,
             test_append_before_finalize_preserved,
             test_replay_utility,
             test_stale_response_rejection,
             test_current_response_acceptance,
             test_stale_and_accept_with_audit_c_d,
             test_t1_hidden_state_counterfactual,
             test_t2_http_only_truth_mask]
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
