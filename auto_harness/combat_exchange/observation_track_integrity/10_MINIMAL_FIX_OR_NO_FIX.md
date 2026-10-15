# 10 — MINIMAL FIX
Bug: live, radar-positioned contacts suppressed by `killed_names`.
Fix (single defect, minimal diff, `agent_hybrid_v5.py::TrackManager.update`, **env-gated**):
```python
if name in self.killed_names:
    if os.getenv("OBS_TI_REVIVE", "0") == "1" and e.get("position"):
        self.killed_names.discard(name)   # legal live contact -> not dead
    else:
        continue
```
- Default `OBS_TI_REVIVE=0` → **frozen ACE/C10/C11 behaviour unchanged** (reversible, disableable).
- Uses ONLY `obs.active` (legal radar capture) → no engine truth, no expanded observability.
- Does not fabricate positions (bearing-only passive branch is untouched).
- No sensor/weapon/rule change; no candidate logic change.
Status: implemented on the working branch, unit-tested. **No full evaluation re-run** (per instructions;
behaviour change to all agents requires a new epoch).
