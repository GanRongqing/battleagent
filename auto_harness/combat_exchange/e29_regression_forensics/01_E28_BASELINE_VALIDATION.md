# 01 — E28 BASELINE VALIDATION (reproduced)
Re-ran the paired episodes in the current environment (fresh workers, same seed 43001):
| scenario | C10 K/L | C30 K/L | E28 C10 | E28 C30 | reproduced |
|---|---|---|---|---|---|
| S10 | 5/1 | 0/5 | 5/1 | 0/5 | YES |
| S20 | 10/1 | 10/8 | 10/1 | 10/8 | YES |
| EXTT | 8/1 | 2/5 | 8/1 | 2/5 | YES |
- EngineHash `a509457250bc2799` on all; 14/14 E28 episodes valid; here 11/11 valid.
- `sim_script` symlink adapter is behaviour-neutral (same K/L as E28); it only fixes module import.
- INF CER handling: we report K/L and positive/negative exchange separately; no finite substitution for INF deltas.
