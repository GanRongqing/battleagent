# 02 — SITUATION EXTRACTOR & ADAPTIVE COMPOSER
`adaptive_skills.extract(obs,tracks,now)` → `SituationFeatures`: active positioned tracks, passive count,
USV alive/locking/frozen, UAV alive/forward-of-front, min boundary margin, fleet spread, has_threat.
`adaptive_skills.Composer` (deterministic, hysteresis HOLD=3 on the USV axis):
- USV: POSITION_RECOVERY if margin<40 km else CONTACT_MAINTENANCE if threat else ACTIVE_SEARCH.
- UAV: BROAD_SEARCH if threat else FLEET_TETHERED_RECON.
- Engagement: unchanged C10.
Records `self.trace` (time, usv_mode, uav_mode); dumped to `SKILL_TRACE` when set. No scenario/seed input.
