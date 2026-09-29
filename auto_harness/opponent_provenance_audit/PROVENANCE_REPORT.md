# PROVENANCE_REPORT.md — External Opponent Provenance Audit

## Verdict: MISSING_EXTERNAL_OPPONENT_ARTIFACTS

No source-backed Wave1(5) / Wave2(6) artifact set exists on this machine/repo. A bounded but thorough
filesystem + archive + registry search was completed. No evaluation was run; no registry modified.

## Q&A (required)
1. **What are B0-B3?** Four real registered Black opponent policies:
   `black-b0-v1` B0_RANDOM, `black-b1-v1` B1_MULTI_AXIS, `black-b2-v1` B2_COORDINATED_PRESSURE,
   `black-b3-v1` B3_ADAPTIVE. Defined in `opponent_profiles.py`, registered in
   `strategy_library/seed_policies.py` + DB and `policy_system/cards/black-b{0..3}-v1.json`.

2. **What is AUTO1? Is it Wave1/Wave2?** `black-auto-0001-v1` (in `opponent_auto_profiles.py`), an
   auto-generated Black profile. Its artifact contains **no** Wave1/Wave2 tag → NOT assigned to a wave.

3. **Why is B4_DOCTRINE_MIX not a distinct policy?** It is a seed-driven composition that randomly
   selects one of B1/B2/B3 per game (`opponent_profiles.py`, DOCTRINES=(B1,B2,B3)). It is a
   MIX/COMPOSITE GENERATOR, not an immutable independent opponent.

4. **What is in wang.rar?** Exactly 6 files: `测试2-黑方艇两波次前进.json`, `策略存放位置.txt`,
   `分散式.py`, `两波次.py`, `sces.json`, `测试1-黑方艇分散式前进.json` — i.e. **2** Black strategies
   (dispersed, two-wave). sha256 `4518380078c182c58de44560fb5e7474c674a17d30792fd6bc3a90eb645e8824`.

5. **dispersed / two-wave provenance + Black identity?** 师弟 (xiaowang) delivery in `wang.rar`;
   Black-side waypoint scripts (`分散式.py`/`两波次.py`) driving Black BLUE units to x=0, bound to
   scenario JSONs `测试1-黑方艇分散式前进.json`/`测试2-黑方艇两波次前进.json`; integrated copies
   `hsystem/sim_script/20250819TZB/external_{dispersed,twowave}.py`. Registered by
   `xiaowang_source/sces.json` as `地毯式前进`/`两波次前进`. **No wave tag** → do not assume Wave1.

6. **Any other xiaowang/wave archive?** No. Only `wang.rar`. `六个策略.zip` (sha256
   `3373a08acf7eee22c8d3708d5089ce39090c1e5a18626f51764be98929c4d9db`) and
   `sc2agent/six_strategies/` are the **White** 6-plan set. `dm8-tzb.tar` / `system-web-tzb.tar` are
   unrelated container images. No other rar/zip/7z/tar under /root or /tmp is a strategy delivery.

7. **Wave1 found: 0 / 5.**
8. **Wave2 found: 0 / 6.**

9. **Why are the 6 sces.json strategies not opponents?** They are White-facing
   `sim_script/scenario/plan/*` strategies (player/planner side), registered under White names and
   consumed by the White agent; they have no Black-side entrypoint. Class = WHITE_PLAN.

10. **Does a complete 4+5+6 evaluable set exist?** **No.** Confirmed Black opponent set on this
    machine = B0, B1, B2, B3 (OLD) + AUTO1 + dispersed + two-wave — with B4 as a mix. No Wave1(5)/
    Wave2(6).

## Confirmed Black opponent inventory (source-backed)
- OLD: black-b0-v1, black-b1-v1, black-b2-v1, black-b3-v1
- EXTRA: black-b0-v2 (B0 refinement), black-auto-0001-v1 (AUTO1)
- EXTERNAL (师弟): black-external-dispersed-v1, black-external-twowave-v1
- MIX (not counted): B4_DOCTRINE_MIX

## Next action
REQUEST_MISSING_WAVE_ARTIFACTS. Do NOT substitute B0/AUTO1/dispersed/twowave/White plans to reach 15.
