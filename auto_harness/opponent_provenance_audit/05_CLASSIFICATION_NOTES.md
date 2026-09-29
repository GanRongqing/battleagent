# 05 — Classification Notes

| artifact | class | why |
|----------|-------|-----|
| opponent_profiles.py | BLACK_OPPONENT_POLICY | pure Black policy ladder B0_RANDOM..B4_DOCTRINE_MIX; BLACK-only legal obs; no White internals |
| opponent_b0_v2.py | BLACK_OPPONENT_POLICY | single-strategy B0 refinement (not a wave) |
| opponent_auto_profiles.py | BLACK_OPPONENT_POLICY | auto-generated profile (AUTO1); no wave tag in artifact |
| strategy_library/seed_policies.py | REGISTRY | registers black-b0..b3 only |
| strategy_library.db | REGISTRY | strategies: white-w5/w6/w7 + black-b0..b3 |
| policy_system/cards/black-b{0,1,2,3}-v1.json | BLACK_OPPONENT_POLICY | policy cards |
| external_opponents/xiaowang_source/{分散式,两波次}.py | BLACK_OPPONENT_POLICY (external) | 师弟 delivery; Black-side waypoint scripts |
| hsystem/sim_script/20250819TZB/external_{dispersed,twowave}.py | BLACK_OPPONENT_POLICY (integrated) | runtime entrypoints of the 2 external scripts |
| 测试1-黑方艇分散式前进.json / 测试2-黑方艇两波次前进.json | BLACK_SCENARIO_STRATEGY | Black scenario JSONs bound to the 2 external scripts |
| hsystem/simserver/config/sces.json (6 编队 plans) | WHITE_PLAN / WHITE_SCENARIO | White-facing `sim_script/scenario/plan` strategies; NOT Black opponents |
| 六个策略.zip / sc2agent/six_strategies | WHITE_PLAN / WHITE_SCENARIO | same 6 White plans + 6 routes; misnamed "six strategies" |
| B4_DOCTRINE_MIX | MIX / COMPOSITE GENERATOR | seed-driven mixture of B1/B2/B3; not an immutable distinct policy |
| wang.rar | archive | contains the 2 external strategies only |

Rule applied: a name like "strategy" is NOT sufficient. An artifact counts only with a policy_id, or a
Black-side entrypoint invoked by a scenario/route runner, or a standalone Black-bound route/scenario
artifact — plus recoverable registered name + source + Black identity.

Wave classification result: **no artifact ties any policy to "Wave1"/"Wave2"**. The 2 externals
(dispersed, two-wave) are 师弟-delivered but carry no wave tag; do NOT assume they are Wave1.
