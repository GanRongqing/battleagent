# DEEP_SEARCH_REPORT — Reopened Wave1/Wave2 search

## Verdict: SEARCH_EXHAUSTED_NO_MATCH (for a labelled 5+6 external delivery)

The full checklist (§19) was executed. No artifact set labelled or shaped as "Wave1 = 5 Black
opponent strategies" + "Wave2 = 6" exists on this machine. The string "wave1/wave2/第一波/第二波"
appears ONLY in this phase's own instructions (opencode prompt-history), nowhere in any project file,
archive, git history, shell history, or Claude session.

## What was searched (all negative for a 5+6 set)
- Mounts: `/`, `/root/autodl-tmp`, `/home/coder`, `/tmp`, `/opt`, `/autodl-pub(+data 4TB)`.
- Archives: only relevant ones are `wang.rar` (2 strategies) and `六个策略.zip` (6 White-facing routes);
  all others are ML datasets / StarCraft / container images.
- Dir clusters: no directory holds exactly 5 or exactly 6 distinct Black-strategy sources.
- git (all repos): no stash/reflog/branch holds strategy files.
- Shell history (`/root`, `/home/coder`): no unzip/cp of a wave archive.
- Claude session logs + paste-cache + opencode history: no pasted wave artifacts.
- Static Black signatures: only the harness's own opponent_profiles/external_*/scenario_builder.

## Closest real candidates (for user confirmation, NOT auto-selected)
1. `六个策略.zip` — the ONLY real **6**-strategy Black-route delivery found (routes 1–6, plan scripts).
   Its own audit (SIX_STRATEGY_SOURCE_AUDIT.md) states BLUE = Black = "the strategy under test".
   This is the strongest candidate for **Wave2 = 6**.
2. `Demo/方案3/6/9/10/15` — 5 Black waypoint JSONs, BUT they are black-COUNT variants of one family
   (5/5/7/10/15 boats), i.e. NOT 5 distinct strategies. Weak candidate for **Wave1 = 5**.
3. xiaowang `dispersed` + `two-wave` (only 2 external strategies; no wave tag).
4. B0-B3 (4) + AUTO1 (1) = 5 registered Black policies (but B0-B3 is the OLD group, not Wave1).

## No auto-selection
Per instructions: no smoke run, no 75-episode eval, no substitution, no registry change.
Awaiting user confirmation of the intended Wave1(5)/Wave2(6) sources.
