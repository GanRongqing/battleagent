# 06 — DISK USAGE AFTER
| mount | size | used | avail | use% |
|---|---|---|---|---|
| `/` (overlay) | 30G | 21G | 9.9G | 68% |
| `/root/autodl-tmp` (/dev/md127) | 60G | 17G | 44G | 28% |
Observed change: `/` freed **~7 GB** (28→21 used); `/dev/md127` freed **~37 GB** (54→17 used).
`hsystem` work tree: 39G → **1.6G**. `.git` sizes unchanged (59M deliverable, 82M engine) — no history rewrite.
Note: two sim_service processes were running during cleanup; they do not hold the deleted historical JSONs;
`df` deltas are attributable to this cleanup (no large concurrent writers observed).
