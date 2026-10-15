# 01 — BASELINE MANIFEST (frozen, C11 round)
| item | sha256 |
|---|---|
| ACE (official baseline) | 7527253c6d5a4bba198e478a990443354ecf5d8cf4e1c98ace66ce50dc809497 |
| C10 (development parent) | 886577b50125acf8d6c94cc267bc7b4c6640597e7e420e74f5a79f1361c60ba3 |
| C11 (candidate) | 07d1ffa9a56cb90aec6acfc138f55b1f18b9ddf5b261d8653ec421a21160fe33 |
| engine locker.py | 130f9c656dbdd56097f39bccb75c529f170954615378a905ceb2c6560cd873f6 |
- git HEAD at start: `abb1d06` (repo /root/autodl-tmp/githsysys).
- Epoch: E3 (C11) / baselines ACE & C10 from E2 epoch (same engine build; unchanged).
- Frozen: ACE, C10, C7, Black policies, scenarios, engine combat/sensor/lock/weapon semantics, metric defs.
- Do NOT mix epochs; C10 baseline from commit 7ca91e2 artifacts.
