# Scenario Reproducibility

- Scenario builder: `hsystem/sim_script/20250819TZB/scenario_builder.py` +
  `scenario_composition.py`; region `hsystem/sim_script/20250819TZB/Demo/任务区域.json`.
- Script registry: `hsystem/simserver/config/sces.json` (incl. external_dispersed / external_twowave).
- API AVAILABLE_SCRIPTS: `hsystem/pomdp_api/main.py`.
- Black profiles: `opponent_profiles.py` (B0-B3), `opponent_auto_profiles.py` (auto),
  `opponent_b0_v2.py` (variable speed).
- Seeds: fixed per episode; runners record seed + scenario JSON + counts in config.
- Verified reproducible episode: S2 x B0_RANDOM seed 1001 (this round).
- Holdout discipline: seeds 5001-5010 reserved; auto corpus 6001-6100 read-only.
