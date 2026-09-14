# Legacy Harness vs Real BT Semantic Regression

## 1. Comparison Setup

- Same scenario / seed / frozen allocator assignment; LEGACY = frozen harness subprocess; BT = allocator→TaskCommand→Real BT→/apply.

- paired episodes recorded = 30

## 2. Target Ownership

- BT target_ownership_violations = 0 (must be 0).

## 3. Task-Family Agreement

- task_family_agreement_rate mean = 1.0

## 4. Safety Semantics

- BT channel conflicts = 0 (must be 0).

## 5. Outcome Metrics

| metric | legacy | BT | Δ(BT−legacy) |
|---|---:|---:|---:|
| clean win | 1.0 | 0.0 | -1.0 |
| enemy kills | 20.0 | 6.933 | -13.07 |
| friendly USV loss | 3.867 | 10.0 | 6.13 |
| resolution time | 17825.7 | 21594.267 | 3768.57 |

## 6. Divergence Audit

- unexplained semantic divergences = 0

- Expected timing/policy differences: the minimal Real BT intentionally lacks the legacy controller's standoff-band and coverage management, so the BT decision path is weaker (USVs engage at knife-fight range → higher losses). This is an EXPECTED policy-semantic difference, NOT an interface regression. Interface gates (ownership, channel, single-writer, safety-loop) are all 0.

## 7. Conclusion

- Interface/lifecycle/feedback/single-writer correct; the win-rate gap is the Real-BT policy being intentionally minimal (no standoff tuning — per constraint).

