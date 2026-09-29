# 00 — Parent Evidence (C2)

## Lineage
Frozen W5 -> ACE (ALLOCATOR_COMMITMENT_EXPANSION) -> C2 (this phase)

## Hashes
- W5: e823e7bed219f4693aa778a838df1400c161f8e7e44001502e5bceb0ae804252
- ACE: 7527253c6d5a4bba198e478a990443354ecf5d8cf4e1c98ace66ce50dc809497

## ACE status
- DEV outcome supported (pooled CER 0.373 -> 1.065, 6/6 strategies).
- FRESH_UNCONFIRMED (previous Fresh run INVALID: infra killed the APIs; 54/60 connection refused).

## Evidence reused (0 new episodes)
- W5 baseline agent logs + reliable baseline game logs (11001/11002, 12 episodes).
- ACE DEV agent logs (12101/12102, 11 episodes).
- Key constraint: ACE shares the SAME USVController as W5 (ACE only changed the allocator),
  so the W5 baseline game logs (reliable) are representative for the assigned->lock geometry.

## Key correction
Earlier aggregate "lock fraction 16%" was a STEP-LEVEL occupancy (locks are brief). The PER-ASSIGNMENT
lock rate (recovered from game-log lock commands `white_usvN 锁定 usvN`) is **71.6%**.
