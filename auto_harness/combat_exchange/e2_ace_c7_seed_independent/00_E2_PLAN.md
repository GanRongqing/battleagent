# 00 — E2 PLAN (POST_SEED_PLUMBING_FIX)
Formal paired ACE vs C7 evaluation with the seed actually wired into the engine RNG.
Design: 4 strategies (W2-1, W2-6 hard; W2-2, W2-4 control) x 5 seeds (43001-43005) x {ACE, C7} = 40
episodes, paired by Strategy x Seed. No parameter tuning, no seed swapping, no new tactical candidate.
Run order: paired blocks (ACE then C7 per Strategy x Seed). Invalid episodes retried; failed logs kept.
Metric: 战损交换比 = Σ Black combat USV killed / Σ White combat USV lost (UAV excluded; pooled, not mean).
Also a same-priority W2-1 contact->lock localization funnel from the episode game logs.
