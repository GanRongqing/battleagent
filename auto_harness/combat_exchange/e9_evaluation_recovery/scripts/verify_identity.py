#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_identity.py — fail-closed Layer-3 scenario identity gate for one run.
Usage: python verify_identity.py <run_id> <sid> <policy>
"""
import glob, hashlib, json, os, sys

RUN, SID, POL = sys.argv[1], sys.argv[2], sys.argv[3]
HW = "/root/autodl-tmp/hsystem/hsystem"
ROOT = "/root/autodl-tmp/hsystem"
MAP = {
    "W2-1": ("横向编队-中央汇聚箭头突防", "路线1-中央汇聚箭头突防"),
    "W2-2": ("菱形编队-接近后扇形展开突防", "路线4-接近后扇形展开突防"),
    "W2-3": ("菱形编队-两翼包抄中央突进", "路线3-两翼包抄中央突进"),
    "W2-4": ("菱形编队-南北两翼镜像夹击", "路线2-南北两翼镜像夹击"),
    "W2-5": ("菱形编队-中央汇聚箭头突防", "路线1-中央汇聚箭头突防"),
    "W2-6": ("菱形编队-MUSV外侧绕行SUSV中央收缩", "路线5-MUSV外侧绕行SUSV中央收缩"),
}
# W2-5's plan uses which route? read the plan file.
def plan_route(sid):
    plan = MAP[sid][0]
    p = os.path.join(HW, "sim_script/scenario/plan", plan + ".py")
    txt = open(p, encoding="utf-8").read()
    import re
    m = re.search(r'strategy_filename="([^"]+)"', txt)
    return plan, (m.group(1) if m else None)

def digest(o): return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

plan, route = plan_route(SID)
route_path = os.path.join(HW, "sim_script/scenario/route", route)
expected = digest(json.load(open(route_path, encoding="utf-8"))) if route and os.path.exists(route_path) else None
rdir = f"/tmp/opencode/parallel_runs/{RUN}"
workers = sorted(glob.glob(os.path.join(rdir, "w*")))
# find this job's result first, then the worker that owns its game log
res0 = None; owner = None
for f in glob.glob(os.path.join(rdir, "results", "*.json")):
    j = json.load(open(f, encoding="utf-8"))
    if j["Strategy"] == SID and j["Policy"] == POL:
        res0 = j["Result"]; break
if res0 and res0.get("Game_Log"):
    for w in workers:
        if os.path.exists(os.path.join(w, "api_logs", "games", res0["Game_Log"])):
            owner = w; break
eff = []; ok_eff = owner is not None
check_workers = [owner] if owner else workers
for w in check_workers:
    p = os.path.join(w, "runtime_identity.json")
    rec = {"worker": os.path.basename(w), "exists": os.path.exists(p), "is_symlink": os.path.islink(p)}
    if os.path.exists(p):
        r = json.load(open(p, encoding="utf-8"))
        rec.update({"strategy_filename": r.get("strategy_filename"), "route_digest": r.get("route_digest"),
                    "formation_mode": r.get("formation_mode"), "pid": r.get("pid")})
        rec["match"] = (r.get("route_digest") == expected and r.get("strategy_filename") == route)
        ok_eff = ok_eff and rec["match"] and (not rec["is_symlink"])
    else:
        ok_eff = False
    eff.append(rec)
res = None
for f in glob.glob(os.path.join(rdir, "results", "*.json")):
    j = json.load(open(f, encoding="utf-8"))
    if j["Strategy"] == SID and j["Policy"] == POL:
        res = j["Result"]; break
glog = None; gscript = None
if res and res.get("Game_Log"):
    for w in workers:
        p = os.path.join(w, "api_logs", "games", res["Game_Log"])
        if os.path.exists(p):
            glog = p; gscript = json.load(open(p, encoding="utf-8")).get("script_name"); break
ok_log = (gscript == plan)
ok_res = bool(res) and str(res.get("Valid")) in ("True", "true", True)
out = {"run_id": RUN, "sid": SID, "policy": POL, "plan": plan, "route": route,
       "expected_route_digest": expected, "effective": eff,
       "gates": {"EFFECTIVE_IDENTITY_VALID": ok_eff, "LOG_ATTRIBUTION_VALID": ok_log, "RESULT_VALID": ok_res},
       "result": res, "game_log": {"path": glog, "script_name": gscript}
       }
out["SCENARIO_IDENTITY_VALID"] = ok_eff and ok_log and ok_res
os.makedirs(f"{ROOT}/auto_harness/combat_exchange/e9_evaluation_recovery/runtime_identity", exist_ok=True)
with open(f"{ROOT}/auto_harness/combat_exchange/e9_evaluation_recovery/runtime_identity/identity_{RUN}.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps({"run": RUN, "sid": SID, "policy": POL, "identity": out["SCENARIO_IDENTITY_VALID"],
                  "expected_digest": (expected or "")[:12], "effective": [(e.get("worker"), (e.get("route_digest") or "")[:12], e.get("match")) for e in eff],
                  "result": (f"{res['Black_Killed']}/{res['White_USV_Lost']}" if res else None)}, ensure_ascii=False))
sys.exit(0 if out["SCENARIO_IDENTITY_VALID"] else 1)
