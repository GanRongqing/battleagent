# 01 — TARGET DEATH DATA FLOW
```
engine unit.kill()  ->  entity.pyx:33-35 sets _isactive=False
   |
radar._search(): foes = [e for e in engine.actives() if e.isdetectable and e.group!=self.group]   (radar.pyx:261,631)
   |               -> dead (isactive=False) units are NOT detectable
raw["white_observation"] (per tick, current tick only; no cache)
   |
_analyze_intel (main.py:680) -> intel["active"] = {name,position,velocity}
   |
/status 雷达捕获  ==  game-log active_enemies  (same intel, same raw)
   |
Obs.active (agent_hybrid_v5.py:225-227, verbatim)
   |
TrackManager.update:  if name in killed_names: continue   (agent_hybrid_v5.py:474-475)
   |
tracks  ->  controller actions
```
`kill_detect` (agent_hybrid_v5.py:537-560) populates `killed_names`.
Key: the observation is generated **per tick from `actives()`**, so a dead target cannot keep appearing
in `active` (except a possible <=1-tick same-tick ordering artifact).
