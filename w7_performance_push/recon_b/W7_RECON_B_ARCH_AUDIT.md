# W7 Recon-B Architecture Audit (read-only, W5 code)
CoverageMap: grid with per-cell last-covered time & coverage_quality; no exported frontier/
deficit API. ThreatClusterBuilder: spatial clusters of ship tracks. UAVManager: SEARCH/SCREEN/
REACQUIRE/GLOBAL_SEARCH roles, per-track reacquire_lock, screen_gate from intent.recon_mode,
battery-safe RETURN/SAFE_LOITER. UAV 60km±30 forward wedge is implicit (no footprint model);
no explicit anti-redundancy / overlap accounting. Lost-track uncertainty is on EnemyTrack
(uncertainty_radius + age) — usable for region demand. Existing variables sufficient to build
a coarse bin-level coverage_need without a new world model (lateral bins over seen ship lanes
x recent USV/UAV proximity).
