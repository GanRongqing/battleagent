# Persistence Shadow Design
Post-shadow-audit finding: static protected-SOFT trigger yields ~52 unique opportunities/run
but ~80% decay by 600s. This round tests whether an ONLINE persistence state machine (only act
after a protected priority inversion has persisted continuously for a horizon) produces a
post-trigger-stable, actionable subset. Horizons compared: P300/P600/P1200 (mechanism
sensitivity, NOT threshold optimization). No real reassignment; real policy frozen W5.
