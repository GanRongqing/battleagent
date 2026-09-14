# Persistence Final Diagnosis
STAGE1 4001-4003
P300 would_execute=55 post300=15 post600=17 post1200=3 rev300=28 med_life=222s
P600  would_execute=10 post300=8  post600=3  post1200=0 rev300=2  med_life=480s
P1200 would_execute=2  post300=0  post600=0  post1200=0 rev300=2  med_life=270s
STAGE2 4004-4006
P300 would_execute=38 post300=4 post600=1 rev300=33 med_life=160s
P600 would_execute=4  post300=2 post600=0 rev300=2  med_life=282s
P1200 would_execute=0
CROSS-SEED useful post600 signal: P300 2/6 seeds; P600 1/6 seeds; P1200 0/6.
SAFETY: near-lock/unique/coverage violations = 0 (base trigger). deterministic/neutral PASS.
CASE = C (persistence does not robustly solve transience across seeds)
RECOMMENDED HORIZON = NONE
PRIMARY FINDING = persistence filters raw volume (P300 93 -> P600 14 total) but post-trigger
stability does NOT generalize: post600 on 4004-4006 is ~0 for every horizon. The few stable
episodes in 4001-4003 do not reproduce.
ONE RECOMMENDED NEXT STEP = STOP hand-crafted SOFT rebalancing; no live SOFT trigger. Future
gains belong to an RL allocator / better sensing / strategic intent, not more hand-built
temporal gates.
