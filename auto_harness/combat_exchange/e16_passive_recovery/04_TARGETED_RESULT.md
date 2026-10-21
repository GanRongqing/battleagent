# 04 — W2-5 TARGETED RESULT (seed 43001, identity VERIFIED)
| version | kills | losses | breakers | breach count | usv4 positioned steps | total positioned Black |
|---|---|---|---|---|---|---|
| C10 (baseline) | 27 | 14 | usv4 (north y=+115) | 1 | **0** | 26 |
| C15 | **19** | 14 | **usv23 (south y=−75)** | 1 | **1019** | **21** |
- **Mechanism works**: usv4, previously passive-only (0 radar steps), became a **positioned track for 1019
  steps** under C15. VERIFIED.
- **But net negative**: the single scout's diversion reduced total positioned contacts (26→21) and kills
  (27→19); the breach still occurs (now on a different southern lane, usv23). No Clean Victory.
- Interaction/observability: `UAV_TRACE` kinds recorded (uav_step 1304, global_search 1113); the scout path is
  the one added action. No silent no-op (behaviour and result both changed).
