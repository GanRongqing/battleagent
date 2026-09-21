# Runtime Path Status (source-verified)

1. LLM Commander role: OPTIONAL strategic-intent layer (`LLMCommander`), not required by the stable W5 physical loop.
2. If `LLM_ENABLED=false`: `CommanderIntentAdapter` falls back to a deterministic default intent; episode completes (verified: S2 x B0 seed1001 Victory, LLM off).
3. Skill direct action influence: NO. `skills/maritime_commander/SKILL.md` is strategic doctrine text consumed by the LLM commander; it does not emit physical actions. With LLM off it is inert.
4. BT in default W5 path: NO. W5 uses `USVController`/`UAVManager`, not BT.
5. `test_bt_harness_interface.py`: interface contract between BT harness and the platform (experimental).
6. `test_bt_real_trees.py`: real BT tree behavior tests (experimental).
7. MARL/RL integration: at decision output (platform/task/target), NOT raw low-level control (see MARL_INTEGRATION_REFERENCE.md).
8. Current execution layer: `USVController.step` (agent_hybrid_v5.py:2002).
9. Skill evolution: OFFLINE (`skill_evolution.py` + `history/versions.jsonl`).
10. Auto Harness: OFFLINE evolution pipeline (candidate mining), not in runtime.
