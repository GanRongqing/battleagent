# 02 — TRACE NEUTRALITY (E31)
Same C31 (final buffer), seed 43001, TRACE ON (`e31_full_on`, AREA_TRACE+SAFETY_TRACE) vs OFF (`e31_neutral_off`):
| scenario | OFF traj hash | ON traj hash | OFF K/L | ON K/L | identical |
|---|---|---|---|---|---|
| W2-1 | 96ad3210633b896e | **96ad3210633b896e** | 16/5 | 16/5 | YES |
| S10 | 1a73034c3b1b64b7 | **1a73034c3b1b64b7** | 5/0 | 5/0 | YES |
=> TRACE ON/OFF is behavior-neutral (position+alive trajectory hash and K/L identical). VERIFIED.
