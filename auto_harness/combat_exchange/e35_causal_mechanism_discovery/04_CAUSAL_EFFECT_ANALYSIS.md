# 04 — CAUSAL EFFECT ANALYSIS (E33→E34, 2×2)
Four conditions (same Black routes, seed 43001, C31 frozen; only White count & radar vary):
| condition | White count | White radar | pooled K/L | CER |
|---|---|---|---|---:|
| A (E33) | E33 (10–30) | 20 km | 95/146 | **0.651** |
| B | E33 (10–30) | 30 km | 190/143 | **1.329** |
| C | parity (30/20/24/45) | 20 km | 248/217 | **1.143** |
| D (E34) | parity | 30 km | 343/274 | **1.251** |

### Effects
- **Radar effect**: A→B (E33 counts): **+0.678** (0.651→1.329). C→D (parity): **+0.108** (1.143→1.251).
- **Count/deployment effect**: A→C (20 km): **+0.492** (0.651→1.143). B→D (30 km): **−0.078** (1.329→1.251).
- **Interaction (negative)**: radar helps much more when White is small (A→B) than at parity (C→D); count helps
  more at low radar (A→C) than at high radar (B→D). The two factors **substitute** for each other.

### Answers (Goal A)
1. **Radar alone**: +0.678 at E33 counts — the single biggest lever. VERIFIED.
2. **Count/deployment alone**: +0.492 at 20 km, but −0.078 at 30 km — at full radar, adding White ships adds as many
   losses as kills. VERIFIED.
3. **Interaction**: negative (substitutive); B (E33 counts + 30 km) is the **highest** pooled CER (1.329), above D.
4. **Radar matters most for**: small-force scenarios (N01 0→5, N04 0→2, N05 0→4, N07 1→11, N11 0→10, N13 0→4) —
   where detection/lock range was the binding constraint.
5. **Count/deployment matters most for**: F04 (C 1/14 vs A 0/10), F13 (C 45/4), F05 (C 29/3) — where force mass
   changes local engagement geometry (with high route-to-route variance).

### Confounds (honest)
- Count change is confounded with formation spacing (horizontal_N spacing depends on N) — the "count" effect
  includes a deployment-geometry change; a pure-count estimate needs deployment held fixed (not fully separable).
- Per-scenario variance is large (e.g., C swings F05 29/3 up but F06 6/30 down) — single-seed deterministic
  results; no statistical significance claimed.
