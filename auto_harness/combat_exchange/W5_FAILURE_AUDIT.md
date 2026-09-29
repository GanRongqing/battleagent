# W5 Combat Failure-Mode Audit

Scope: 24 W5 episodes (seeds 11001/11002 baseline + 12101/12102 DEV), LLM off.
Primary KPI: CER = Black kills / White USV losses.

## 1. Kill-chain funnel (aggregated over 4 seeds, proxy-based)

| strategy | detected | assigned | killed | kill_rate | assign_rate |
|---|---|---|---|---|---|
| S1 横向中央汇聚 | 92 | 129 | 55 | 59.8% | 140% (overcount) |
| S2 扇形展开 | 120 | 143 | 86 | **71.7%** | 119% |
| S3 两翼包抄 | 94 | 85 | 45 | 47.9% | 90% |
| S4 南北镜像 | 61 | 56 | 28 | 45.9% | 92% |
| S5 菱形中央汇聚 | 118 | 50 | 24 | **20.3%** | 42% |
| S6 MUSV绕行 | 85 | 89 | 37 | 43.5% | 105% |

`[ASSIGN]`/`[DETECT]` are step-level proxies (over/under-count); `killed` and losses are reliable.

## 2. Kill-chain failure classification (non-killed detected targets, N=295)

| class | count | % |
|---|---|---|
| KC-F1 DETECTED_NOT_COMMITTED | 250 | **84.7%** |
| KC-F5/9 ATTACKER_DIED_OR_GEOMETRY | 45 | 15.3% |

Dominant failure: **W5 detects a target but never commits a White USV to it.** This is a ThreatAllocator
under-commitment, worst on S5 (assign_rate 42%, kill_rate 20%).

## 3. White-death context (baseline 12 episodes, 180 deaths)

| signal | count | % |
|---|---|---|
| committed (assigned) before death | 135 | 75% |
| died WITHOUT a valid lock | 146 | **81%** |
| died while exposed (enemy locking it) | 180 | 100% |
| died isolated (<2 friendly in 50 km) | 70 | 39% |

Every White USV death happens while it is being locked by the numerically superior Black (30 vs 20).
81% of deaths happen while the White USV itself is NOT holding a lock — i.e. it is chasing/pressing a
target it cannot lock, exposed, and gets destroyed.

## 4. Seed variance (CER per episode across 4 seeds)

| strategy | seed11001 | 11002 | 12101 | 12102 | variance |
|---|---|---|---|---|---|
| S1 | 5.75 | 1.46 | 0.00 | 1.18 | HUGE |
| S2 | 0.00 | 1.93 | 1.81 | 2.00 | HUGE (one 0 outlier) |
| S3 | 0.62 | 0.80 | 0.75 | 0.65 | small (~0.7) |
| S4 | 1.22 | 0.25 | 2.00 | 0.19 | HUGE |
| S5 | 0.10 | 0.11 | 0.00 | 1.11 | small (~0.1, one outlier) |
| S6 | 0.81 | 0.30 | 0.37 | 1.00 | large |

W5's combat outcome is dominated by **single-seed trajectory variance** on S1/S2/S4/S6. Only S3
(stably ~0.7) and S5 (stably ~0.1) are low-variance.

## 5. Synthesized systematic failure modes

1. **Under-commitment (dominant, 84.7%)** — W5's ThreatAllocator commits a White USV to only a
   subset of detected targets. Worst on S5 (42% assign, 20% kill). Targets that are never committed
   simply transit to the breakthrough line unengaged.

2. **Over-exposure of committed USVs** — the few USVs that ARE committed die chasing targets they
   cannot lock (81% died without lock, 100% exposed). The Black's 30-vs-20 numerical edge wins every
   unfocused 1v1.

3. **S5 (diamond + central convergence) is a hard geometric mismatch** — kill_rate 20%, CER ~0.1
   across seeds. The Black converges through the diamond's gaps while White cannot mass fire.

4. **High timing sensitivity** — because the simulator advances continuously (not lockstep), the same
   policy yields 5-10x CER swings across seeds. Any candidate must be judged on PAIRED fresh seeds.

## 6. Interpretation for the next candidate

The failure is NOT primarily "first-hit → kill closure" (the committed USVs rarely even reach a lock).
It is a combination of:
- (a) too FEW commitments (under-commitment), and
- (b) committed USVs fighting unfocused 1v1 and losing (over-exposure).

Both are consistent with the **LOCAL_OVERMATCH** mechanism (form 2v1/3v1 to win a local exchange fast,
then release and move on), which is the natural next single-mechanism candidate — NOT survival-retreat
(already disproven) and NOT sensing/coverage changes.

Do not stack onto C1 (dropped). Next candidate parent = W5.
