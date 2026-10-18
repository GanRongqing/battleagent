#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""identity_gate.py — fail-closed scenario identity gate for one E8.1 run.

Independent evidence = the worker's REAL `simserver/temp.py` (the scenario script the simulator actually
loaded), NOT the job label. Also checks the game-log script_name and validity.
Usage: python identity_gate.py <run_id> <sid> <policy>
"""
import glob, json, os, re, sys

RUN = sys.argv[1]; SID = sys.argv[2]; POL = sys.argv[3]
ROOT = "/root/autodl-tmp/hsystem"
EXPECT = {
    "W2-1": ("横向编队-中央汇聚箭头突防", "路线1-中央汇聚箭头突防.json"),
    "W2-2": ("菱形编队-接近后扇形展开突防", "路线4-接近后扇形展开突防.json"),
    "W2-4": ("菱形编队-南北两翼镜像夹击", "路线2-南北两翼镜像夹击.json"),
    "W2-6": ("菱形编队-MUSV外侧绕行SUSV中央收缩", "路线5-MUSV外侧绕行SUSV中央收缩.json"),
}
plan, route = EXPECT[SID]
rdir = f"/tmp/opencode/parallel_runs/{RUN}"
workers = sorted(glob.glob(os.path.join(rdir, "w*")))
out = {"run_id": RUN, "sid": SID, "policy": POL, "requested_plan": plan, "expected_route": route}
# 1) effective scenario from the simulator's loaded temp.py (per-worker real file)
eff = []
for w in workers:
    tp = os.path.join(w, "simserver", "temp.py")
    rec = {"worker": os.path.basename(w), "temp_exists": os.path.exists(tp),
           "is_symlink": os.path.islink(tp)}
    if os.path.exists(tp):
        txt = open(tp, encoding="utf-8", errors="replace").read()
        m = re.search(r'strategy_filename="([^"]+)"', txt)
        rec["effective_route"] = m.group(1) if m else None
        rec["has_plan"] = plan in txt
    eff.append(rec)
out["effective"] = eff
# 2) result + game log
res = None
for f in glob.glob(os.path.join(rdir, "results", "*.json")):
    j = json.load(open(f, encoding="utf-8"))
    if j["Strategy"] == SID and j["Policy"] == POL:
        res = j["Result"]; break
out["result"] = res
gl_script = None; gl_path = None
if res and res.get("Game_Log"):
    for w in workers:
        p = os.path.join(w, "api_logs", "games", res["Game_Log"])
        if os.path.exists(p):
            gl_path = p; gl_script = json.load(open(p, encoding="utf-8")).get("script_name"); break
out["game_log"] = {"path": gl_path, "script_name": gl_script}
# gates
ok_worker = bool(eff) and all((not e["is_symlink"]) and e.get("effective_route") == route and e.get("has_plan") for e in eff)
ok_log = (gl_script == plan)
ok_result = bool(res) and str(res.get("Valid")) in ("True", "true", True)
out["gates"] = {"EFFECTIVE_IDENTITY_VALID": ok_worker, "LOG_ATTRIBUTION_VALID": ok_log,
                "RESULT_VALID": ok_result}
out["SCENARIO_IDENTITY_VALID"] = ok_worker and ok_log and ok_result
print(json.dumps(out, ensure_ascii=False, indent=1))
with open(f"{ROOT}/auto_harness/combat_exchange/e8_1_scenario_revalidation/raw_logs/identity_{RUN}.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
sys.exit(0 if out["SCENARIO_IDENTITY_VALID"] else 1)
