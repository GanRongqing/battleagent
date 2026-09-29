# ACE Cross-Strategy Generalization — STOP REPORT

## Decision: STOPPED before evaluation (registry != 15)

### Triggered STOP conditions
1. **Actual registry != 15 enemy strategies.**
2. **Cannot confirm B0-B3 / Wave1 / Wave2 strategy identity** (no Wave1(5)/Wave2(6) set exists).

### ACE policy (unchanged, frozen)
- path: `agent_hybrid_allocator_expand.py`
- sha256: `7527253c6d5a4bba198e478a990443354ecf5d8cf4e1c98ace66ce50dc809497`
- git commit: `d9d4f51` (no modification made this phase)

### Deterministic mode
- engine-level step mode available (opt-in) + Stage-A ordering fix (`judge_system.set_units`
  sorted) are present (commit `3a96b75`). Not exercised: no evaluation was run.

### What was found (summary)
- OLD B0-B3: confirmed as 4 profiles in `opponent_profiles.py` + `strategy_library` DB
  (black-b0..b3).
- Wave1/Wave2: **not found.** The only 师弟 (xiaowang) external delivery (`wang.rar`, sha256
  4518380078c182c58de44560fb5e7474c674a17d30792fd6bc3a90eb645e8824) contains exactly **2**
  strategies: `分散式` (dispersed) and `两波次` (two-wave). No registry defines 5 or 6 more.
- See `00_STRATEGY_REGISTRY.md` for the full enumeration.

### Episodes run
0 (none). No CSV produced. ACE and enemy strategies untouched.

### Required to proceed
Provide/point to the actual Wave1 (5) and Wave2 (6) strategy registry (files + registered names +
scenario/route ids). If the intended set is instead "B0-B4 + dispersed + twowave + plan strategies",
confirm the exact desired set and I will run the 5-seed × N evaluation.
