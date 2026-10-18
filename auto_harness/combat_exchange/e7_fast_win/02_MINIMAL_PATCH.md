# 02 — MINIMAL PATCH (LIFECYCLE_HANDOFF_V1)
Single mechanism: on an **inferred death revocation by a fresh legal positioned observation**, update
**both** death stores atomically, so the lifecycle handed to downstream consumers is consistent.

```python
# TrackManager.update, under the killed_names branch (agent_hybrid_v5.py)
if self._handoff and e.get("position"):
    self.killed_names.discard(name)
    _KILLED.discard(name)                 # keep the second store consistent
    self._lc_set(name, "OBSERVED_ACTIVE", "revive_via_legal_obs", "obs.active")
elif os.getenv("OBS_TI_REVIVE", "0") == "1" and e.get("position"):
    self.killed_names.discard(name)       # legacy: leaves _KILLED stale
else:
    continue
```
- Feature flag `LIFECYCLE_HANDOFF_V1` (default 0). `_handoff` read in `TrackManager.__init__`.
- Mutual exclusivity: when HANDOFF=1 it supersedes OBS_TI_REVIVE (which is the inconsistent path).
- No engine/Black/tactics/weapons; uses only `obs.active` positions; no truth.
- Behaviour-neutral when OFF (the branch is not taken).
- Lines changed: ~6 (flag + expiry; revive branch).
