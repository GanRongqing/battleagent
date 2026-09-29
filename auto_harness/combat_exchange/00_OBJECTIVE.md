# 00 — Objective: W5 Kill-Oriented Combat Optimization

Primary KPI: **Combat Exchange Ratio (CER) = Black combat USV killed / White combat USV lost**.

- Mission Victory / Defeat and breakthrough are NOT the objective this phase.
- Objective: make White win the exchange in direct combat (local numerical advantage →
  stable lock → first hit → kill → preserve own force), even if some enemies leak.
- "Leak one enemy" is preferred over "lose two White USVs chasing it".

Formal metrics:
- `CER_episode = kills / losses` (INF if losses=0 and kills>0; 0 if both 0).
- `POOLED_CER = sum(kills) / sum(losses)` (NOT average of episode CER).
- `EXCHANGE_WIN = kills > losses`.

Gate discipline: breakthrough is recorded but is NOT a PASS/FAIL gate (except
EVALUATION_TRUNCATION if breakthrough ends the episode early and truncates combat).

Candidate must NOT:
- modify W5 (`agent_hybrid_v5.py` frozen, sha e823e7be…),
- modify physics / radar / weapon / black route / scenario / judge,
- read hidden truth (only White legal observation + own state + TrackManager belief + legal actions),
- hardcode any strategy name / route / y-lane / black ID / enemy count.

First generation = ONE mechanism only, chosen by root-cause coverage.
