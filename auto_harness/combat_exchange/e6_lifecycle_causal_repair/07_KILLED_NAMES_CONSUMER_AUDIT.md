# 07 — `killed_names` / `kill_detect` / `_KILLED` CONSUMER AUDIT (agent_hybrid_v5.py)
| symbol | line | role |
|---|---|---|
| `self.killed_names` init | 463 | set of "sunk" enemy names |
| read (suppress track) | 474 | TrackManager.update skips killed names |
| read (no track create) | 533 | reconcile_assigned skips killed locking_unit |
| write (add) | 566 | kill_detect adds inferred dead |
| `_KILLED` init | 1971 | **module-global second death store** (never cleared) |
| read (allocator candidates) | 1837 | allocator excludes `_KILLED` |
| read (release target) | 2057 | controller releases targets in `_KILLED` |
| read (opportunistic lock) | 2143 | `_opportunistic_lock` excludes `_KILLED` |
| write | 2821 | `_KILLED.update(killed)` every step |

Findings:
- Death bookkeeping is **duplicated** in `TrackManager.killed_names` and the global `_KILLED`.
- Both are fed by `kill_detect`'s inferential heuristics; both gate engagement downstream
  (allocator candidate filter, opportunistic lock, target release).
- `_KILLED` is **never cleared** → latent cross-episode contamination (not triggered in our per-process
  eval runs, but violates Invariant 8). A patch must treat `killed_names` as the single source and
  derive/clear `_KILLED` consistently.
- Semantic overload: one set serves inference, filtering, cleanup, and kill statistics.
