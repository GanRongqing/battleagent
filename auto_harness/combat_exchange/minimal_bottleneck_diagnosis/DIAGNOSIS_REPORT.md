# Minimal-Episode Bottleneck Diagnosis

## 1. How many new episodes were used?
**0.** All conclusions reuse existing logs.

## 2. Existing evidence reused
- W5: 23 episodes (baseline 11001/11002 = 12, W5 DEV 12101/12102 = 11 present).
- ACE: 11 episodes (ACE DEV 12101/12102).
- Baseline game logs (reliable): 12 (W5) for white-death context.
- NOT reusable: ACE game logs (corrupted by parallel shared log dir); ACE Fresh (invalid, 6/60).

## 3. Combat funnel (killed is the reliable signal; assigned uses [ASSIGN] proxy)

| policy | n | detected | killed | losses | kill_rate | CER |
|---|---|---|---|---|---|---|
| W5 | 23 | 535 | 202 | 352 | 37.8% | 0.574 |
| ACE | 11 | 249 | 139 | 135 | 55.8% | 1.030 |

## 4. Transition conversion (aggregate USV occupancy)

| policy | int_frac (chasing) | lock_frac | lock / (int+lock) |
|---|---|---|---|
| W5 | 6.9% | 0.9% | **11.9%** |
| ACE | 9.2% | 1.8% | **16.1%** |

**KEY**: even after ACE expands commitment (more USVs assigned, int_frac 6.9%→9.2%), only **16.1%** of the
engaged USVs are actually LOCKING; ~84% are merely INTERCEPTING/approaching. This ratio barely moved from
W5. => the engaged USVs spend the vast majority of engagement time approaching without a lock.

## 5. White death analysis (W5 baseline, 180 deaths)
- 100% die while exposed (locked by Black).
- 81% die WITHOUT an own lock.
- 75% were assigned/committed before death.
- 39% isolated.
=> White USVs die while chasing targets they have not locked.

## 6. W5 → ACE bottleneck migration
- Allocator under-commitment (W5's dominant F1=86%) is substantially reduced by ACE
  (assignment coverage 43.5%→75.7%; kill_rate 37.8%→55.8%; losses 15.3→12.3 per episode).
- After that improvement, the **lock-of-engaged ratio stays ~16%** and the exchange is ~1:1.
- => the exposed next bottleneck is the **engagement: approach → lock**, not the allocator.

## 7. Primary bottleneck
**LOCK_ACQUISITION** (the engaged USVs spend ~84% of engagement time approaching without a lock;
the kills come only from brief locks; 81% of deaths occur without an own lock).
Confidence: MEDIUM.

## 8. Why it is NOT the other layers
- **NOT initial detection**: ~22.6/30 Black detected per episode (75%); and 30/30 was detected on the
  stress scenarios in earlier audits — the issue is downstream of detection.
- **NOT allocator (anymore)**: ACE raised coverage to 75.7% and cut never-assigned sharply; the
  allocator is no longer the dominant limiter for ACE.
- **NOT pure kill-closure**: locks DO convert (kill_rate 55.8%); the problem is getting the lock at all /
  holding it long enough, while exposed.
- **NOT pure capacity**: no per-step simultaneous-threat vs conversion data (NOT_MEASURED).
- **NOT pure local-overmatch**: no per-target attacker-count in ACE logs (NOT_MEASURED); historical
  53% vs 28% is observational only.

## 9. Recommended next candidate (do NOT implement this round)
**LOCK_GEOMETRY / APPROACH** candidate (reduce the approach-to-lock time; get into lock range faster /
with less exposure), possibly combined with a survival-aware approach. Primary maps to
`LOCK_ACQUISITION`, secondary to `SURVIVAL_GEOMETRY`.

## 10. Evidence limitations
- Per-target lock target (`locking_unit`) is absent from game logs -> target-level
  Assigned→Lock→Hit→Kill funnel is NOT_MEASURED; only aggregate USV occupancy.
- ACE game logs corrupted (parallel shared dir) -> ACE white-death context unavailable (count only).
- [ASSIGN] proxy over-counts, so exact never-assigned splits are approximate.
- `runtime_audit/run_ep4` is the only run with canonical allocator/controller state (1 run).
