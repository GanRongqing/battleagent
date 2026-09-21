# Runtime A->F Example (real runtime_audit artifact)

Source: `runtime_audit/run_ep4_1787234142/step_19.json` (per-step audit, one file per step; `manifest.json` per run).

Present keys: `A_raw_observation`, `B_fused_state`, `E_intermediate`, `F_execution_feedback`.
Common keys: `run_id`, `audit_step_id`, `prev_audit_step_id`, `sim_time`, `wall_time`.

Example (step_19, sim_time=323s):
- A_raw_observation.status: 对局编号=4, usv_total=5, usv_alive=5, enemy_visible=0, white_usv1 speed=20.0 course=90.
- B_fused_state / E_intermediate / F_execution_feedback: present (see file).

Note: this run used a 5-USV scenario (ep4). C/D stages are not separate top-level keys in this
artifact version (folded into E). See LOGGING_REFERENCE.md.
