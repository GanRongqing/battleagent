# W6 Baseline Audit

> Read-only audit. Goal: confirm which White execution path was used in the **formal
> B0 vs B3 opponent evaluation** (180 episodes), and that the later minimal Real-BT
> execution path was NOT the baseline for those results.
> Date: 2026-08

---

## 1. Frozen White identity

| item | hash |
|---|---|
| Agent (agent_hybrid_v5.py) | `a7842b29c81cc567ea63cae262cb6ab0b9d9bd9df90903c4115eaa6e6c6f0f66` |
| Skill (SKILL.md) | `155b02019dc92c6e6c0095949439a413cd86310ad1026cd394ad185c3d13552e` |

(Recomputed live from `sha256sum`; also recorded in `opponent_formal_eval/config_manifest.json`.)

## 2. Baseline runner

- **B0 column** (S1/S2/S3 × 30, seeds 1001–1030): `run_formal_eval.py`
- **B3 column** (S1/S2/S3 × 30, seeds 1001–1030, paired): `run_opponent_formal.py`

Both run White as an **external frozen subprocess**:
```python
p = subprocess.Popen([PY, "agent_hybrid_v5.py", "--uavs"],
                     env={**os.environ, "SCENARIO_SCRIPT": "scenario_composition",
                          "LLM_ENABLED": "false", ...})
```
No code-level hook into the agent; `LLM_ENABLED=false` ⇒ **deterministic Harness execution**
(ThreatAllocator + USVController + UAVManager + ActionSafety), i.e. the V5 harness, not the
LLM Commander and not the Behavior-Tree path.

## 3. Baseline execution path (inside agent_hybrid_v5.py)

```
AgentMain.run()
  step_once()
    ApiClient.status()            -> /status whitelist
    TrackManager.update(obs)      -> belief tracks
    ThreatAllocator.allocate_usvs -> marginal-value allocation
    USVController.step()          -> move/lock actions
    UAVManager.step()             -> launch/fly actions
    ActionSafety.filter()         -> legal check
    ApiClient.apply(safe)         -> POST /apply
```
- baseline allocator = `ThreatAllocator.allocate_usvs` (marginal value, coverage floor, reserve ratio)
- baseline USV controller = `USVController.step` (intercept/standoff state machine)
- baseline UAV manager = `UAVManager.step` (SEARCH/SCREEN/REACQUIRE)
- LLM Commander: present in code but `LLM_ENABLED=false` in the formal eval → `DEFAULT_INTENT` only.

## 4. BT involved in formal B3 evaluation?

**NO.**

- `run_opponent_formal.py` and `run_formal_eval.py` contain **0** references to
  `bt_harness_interface`, `BTPlatformExecutive`, `bt_real_trees`, `BTActionAdapter`.
- The Behavior-Tree execution path exists in separate, later files:
  - `bt_integration_run.py` — BT-driven execution, **seeds 1101–1103** (BT interface validation)
  - `bt_regression_run.py` — legacy-vs-BT paired regression, **seeds 1201–1205**
- These are distinct experiments with different seed sets; they did not contribute to the
  formal B0/B3 180-episode numbers.

## 5. Why the BT 0/30 regression is NOT the W6 baseline

The Real BT execution path (`bt_integration_run.py` / `bt_regression_run.py`) does not yet
carry the full legacy execution semantics (standoff-band management, coverage floor
orchestration). Its 0/30 clean-win on the 1201–1205 paired regression reflects the minimal
Real BT policy, **not** the frozen V5 harness. The W6 baseline must therefore be the
**frozen V5 harness** (agent_hybrid_v5.py) whose formal B0/B3 outcomes are:
  S1: 0.967→0.833 clean, S2: 0.933→0.800, S3: 0.933→0.833; exploration +24k–27k km²;
  resolution +8.8k–9.6k s; breakthrough failures up.

## 6. Conclusion

- baseline runner = `run_formal_eval.py` (B0) / `run_opponent_formal.py` (B3)
- baseline agent = `agent_hybrid_v5.py` (frozen, harness/LLM-off)
- baseline allocator = `ThreatAllocator.allocate_usvs`
- baseline USV controller = `USVController.step`
- baseline UAV manager = `UAVManager.step`
- BT involved in formal B3 evaluation = **NO**

W6 will be implemented as an additive, feature-gated layer on top of this frozen V5
harness (the deterministic control path), independent of the BT interface work.
