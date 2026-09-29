# Semantic Diff — W5 -> ACE (white-combat-0002-v1)

## What changed
- **Before (W5)**: the ThreatAllocator protected a static reserve (`reserve_ratio=0.20`) on every step,
  even when there existed visible, actionable, zero-owner hostile targets AND free combat USVs. Those
  free USVs stayed idle; the zero-owner targets were never committed.
- **After (ACE)**: the reserve is **temporarily released** (reserve_usvs -> 0) exactly while a visible
  actionable zero-owner ship coexists with a free combat USV. In all other states the W5 reserve
  semantics are preserved unchanged.

## Why changed
Root cause: ALLOCATOR_UNDER_COMMITMENT (F1-A = 86% of kill-chain failures). The conservative default
intent (focus_level=2 + reserve_ratio=0.20) was throttling commitment breadth.

## Trigger condition
`ExpandingAllocator._under_commitment()`: exists a free combat USV (usv_map owner None, alive, positioned)
AND exists a visible ship with `len(assigned_usvs)==0`.

## What was intentionally NOT changed
- target scoring / threat model, coverage floor (PASS1), marginal concentration (PASS2)
- USVController, TrackManager, detection, radar, lock range, weapon, Black, scenario, judge
- no interface/signature changes

## Expected mechanism
More zero-owner targets get committed -> assignment coverage up -> more kills, without touching the
engagement/controller layer.

## Interface changed?
NO. (`interface_changes: []`)
