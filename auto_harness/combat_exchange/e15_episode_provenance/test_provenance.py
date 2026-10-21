# -*- coding: utf-8 -*-
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import provenance as P


def test_1_same_worker_diff_scenario_no_collision():
    a = P.agent_log_name("横向编队-中央汇聚箭头突防", "ACE", 43001, 0, P.make_episode_id("R", "W2-1", "ACE", 43001, 0))
    b = P.agent_log_name("菱形编队-南北两翼镜像夹击", "ACE", 43001, 0, P.make_episode_id("R", "W2-4", "ACE", 43001, 0))
    assert a != b


def test_2_different_worker_episode_ids_differ():
    assert P.make_episode_id("R", "W2-5", "C10", 43001, 0) != P.make_episode_id("R2", "W2-5", "C10", 43001, 0)


def test_3_retry_attempt_ids_differ():
    a = P.make_episode_id("R", "W2-5", "C10", 43001, 0)
    b = P.make_episode_id("R", "W2-5", "C10", 43001, 1)
    assert a != b
    assert P.agent_log_name("W2-5", "C10", 43001, 0, a) != P.agent_log_name("W2-5", "C10", 43001, 1, b)


def test_4_duplicate_game_logs_deduped():
    d = tempfile.mkdtemp()
    p1 = os.path.join(d, "g1.json"); p2 = os.path.join(d, "g2.json")
    open(p1, "w").write('{"a":1}'); open(p2, "w").write('{"a":1}')
    uniq, dup = P.dedupe_by_content([p1, p2])
    assert len(uniq) == 1 and len(dup) == 1


def test_5_manifest_has_required_fields():
    r = P.manifest_record("R", "E", 0, 0, "W2-5", "name", "digest", "C10", 43001, "43001",
                          "eng", 1, 8000, "t0", "t1")
    for k in ("run_id","episode_id","attempt_id","worker_id","scenario_id","scenario_name",
              "route_digest","policy_id","seed","actual_engine_seed","engine_hash","pid","api_port",
              "start_time","end_time"):
        assert k in r


def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)

if __name__=="__main__":
    sys.exit(0 if _all() else 1)
