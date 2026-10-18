# raw evidence sources
- E4 W2-6 OFF/ON, W2-4 ON: agent stdout [KILL]/[DETECT] + game logs under
  /tmp/opencode/parallel_runs/{e4_w26_off,e4_w26_on,e4_ctl_on}/w*/.
- W2-4 OFF baseline: hsystem/pomdp_api/api_logs/games/game_1_20261013_080710.json (E2).
- Engine semantics: hsystem/simulation/core/entity.pyx:33-35, radar.pyx:261/631, base_engine.pyx:788.
- No engine black-truth is logged; classification uses the proven active=>alive invariant.
