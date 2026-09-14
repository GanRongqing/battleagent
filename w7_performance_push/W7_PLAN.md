# W7 Performance Push — Plan
Goal: raise White clean-win vs B3_ADAPTIVE (frozen physics/opponent, legal obs only, no RL).
Priority lexicographic: clean_win > breakthrough > friendly loss > kills/res/exploration.
USV execution base = frozen W5 (do NOT reintroduce W6 predictive-waypoint/geometry overrides).
Phases: Recon (sensing/screen/reacquire) -> Kill-chain completion -> Proactive pre-commit ->
Runtime fast-path -> combine positive modules -> 3-scale DEV -> FINAL holdout 5001-5010.
DEV seeds 4001-4010 only. Episode budget <=120.
