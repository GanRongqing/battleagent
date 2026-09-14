# Behavior Space Gap Audit (B0-B3 fp-v2, S2 x W5 x 7001-7010)

## Existing empirical regions (from fp-v2 behavioral means)
| region | policy | replan | dispersion_event | y_spread_km | groups | arrival_std_s | lane_entropy |
|---|---|---|---|---|---|---|---|
| E0 random / uncoordinated | B0 | 0 | 0 | 86.7 | 4.94 | 7.4 | 0.64 |
| E1 structured multi-axis pressure | B1 | 0 | 0 | 181.4 | 3.86 | 1557 | 1.18 |
| E1 structured multi-axis pressure | B2 | 0 | 0 | 178.0 | 3.97 | 1020 | 1.23 |
| E2 adaptive replanning pressure | B3 | 619.7 | 196.0 | 152.3 | 4.87 | 68.5 | 1.16 |

Pairwise: B0/B1/B2/B3 mostly DISTINCT except **B1 vs B2 INCONCLUSIVE**
(behavior distance 0.371; top effect group-spacing d=1.147 but seed consistency only 0.70).

## Covered dimensions
- E0: no coordination, low lane entropy, compressed arrival front.
- E1: wide lateral dispersion, high lane entropy, structured groups, moderate/large arrival spread.
- E2: continuous high-frequency legal adaptive replanning (replan 620/10ep, dispersion events 196), tight arrival front.

## Missing dimensions (no B0-B3 policy occupies them)
1. **Force-role asymmetry / reserve usage** — every B0-B3 policy commits (roughly) the whole
   force on one coordinated plan; none holds a reserve or a small decoy while the majority waits.
2. **Discrete phased switching** — B3 switches continuously (every 15 s); B0/B1/B2 never switch.
   A policy with a FEW discrete phase transitions (feint -> switch -> main push) is absent.
3. **Early-vs-late concentration shift** — no policy has low early commitment then high late
   concentration (feint/main push signature).
4. **Dominant-axis shift** — no policy deliberately moves its main effort between lateral axes
   in response to the opponent's visible reaction.
5. **Low-replan + high-phase structure** — the (low continuous replanning, high phase structure)
   quadrant is empty: B3 has high/high-frequency, B0-B2 have none.

## Selected missing region
**PHASED ROLE-ASYMMETRIC FEINT-SWITCH**: small feint group on axis A + held main force +
bounded legal response observation -> few discrete switch(es) -> concentrated main push on
axis B. This is low continuous-replanning but high phase-structure.

## Why Feint-and-Switch (not saturation/reserve only)
- Legally implementable: Black already has `get_black_targets()` (own radar intel) and own unit
  states; a feint axis and a main axis are both legal geometry choices, and the switch can be
  driven purely by whether White units become visible near the feint axis (legal observation).
- Orthogonal to B0-B3: expected low replan (like B0-B2), moderate dispersion, plus NEW generic
  features (phase_switch_count>0, reserve_fraction>0, early/late concentration delta, axis shift).
- Not a B3 parameter tweak and not a B1/B2 perturbation: it changes role allocation and adds
  a phase state machine, not lane geometry/rates.

## Expected contrast per existing policy
- vs B0: structured phase timing + role asymmetry (B0 random, no phases).
- vs B1/B2: small feint + held reserve + discrete axis switch vs whole-force static multi-axis.
- vs B3: few discrete switches (phase_switch_count small) vs continuous replanning (replan ~620).

## Expected weakness
- If White does not over-commit to the feint axis, the feint wastes time and delays main push.
- Discrete switch may raise resolution time; delayed main commitment can lower early pressure.
