# 01 — Non-Trigger Equivalence

Question: when the C1 survival condition does NOT trigger, does C1 produce the same policy
action as W5?

Method: offline code-level test (`equiv_test.py`). Generate representative controller states
(USV alive/dead/locked/locking, tracks in/out of lock range, alloc_result variants, 1-4 USVs),
run W5 `USVController.step()` and C1 `SurvivalUSVController.step()` on identical inputs, compare
(action list, targets table, state table).

Result:
- states generated: 225
- non-trigger states tested: 222
- exact match: 222
- mismatch: 0
- match rate: 100.0%
- survival-triggered states (correctly skipped): 3

## Conclusion
**Non-trigger implementation equivalent = YES.**

C1's `step()` is a thin wrapper: it computes a read-only retreat set, calls `super().step()`
(W5 logic), and only replaces actions for USVs in the retreat set. When the retreat set is empty
(survival not triggered), the returned actions are byte-identical to W5.

No CE-F1..F7 code-level differences found. C1 is a pure survival overlay, not a modified
allocator/controller/safety path.
