# 04 — COMPATIBILITY CHECK (pre-run, all 16)
- `/start`,`/status`,`/legal_actions`,`/apply`,`/result` all functional for all 16 (16/16 valid episodes).
- Public area polygon loads; Safety `available=True` in all 16 (SAFETY_TRACE).
- White UAV count = 0 handled (UAVManager over empty lists; no crash). USV names white_usv1..N parse fine;
  allocator/screen (`%3`) and target allocation work for N=10/15/20/30; no fixed-count assumption triggered.
- Deployment: horizontal_N within area (N=30 at 18km → y±261km < 277.8). No illegal overlap.
- **0 White USV/UAV AREA_OUT** across all 16 (engine AREA_TRACE produced no events).
- No hidden enemy truth used; no scenario-name branching; engine/rules unchanged.
