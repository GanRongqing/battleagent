# 02 — `active_enemies` SEMANTICS
- Source: `hsystem/pomdp_api/main.py::_analyze_intel` (l.680-707), fed by `raw["white_observation"]`.
- Classification: **LEGAL_OBSERVATION** (radar capture of the White fleet), NOT `ENGINE_TRUTH`.
- Contains positions + velocity of radar-captured enemies; `passive_enemies` is bearing-only.
- It is the SAME list the agent receives as `观察信息.white_observation.雷达捕获` (`main.py:1687`).
- Therefore using `active_enemies` offline is using legal data, not truth. (Shadow did NOT contaminate
  with truth; the earlier `w2_6_engagement_forensics` note calling the discrepancy an "observation gap"
  is refined here: the observation WAS present; the **TrackManager dropped it**.)
- Mixed with truth? No — game log does not record black truth; only White radar/observation.
