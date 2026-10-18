# 06 — ERROR CASEBOOK (representative, from E4 raw logs)
Classification basis: `active⇒alive` (02). "FALSE_DEATH" = agent's [KILL] fired on a target that is
**still in active at the kill tick**.
- **FD-1 (W2-6 OFF, usv17, t=6570)** — agent emits `[KILL] usv17` while usv17 is still a live radar
  contact; `killed_names` then suppresses its track for the rest of the episode (892 steps). Consequence:
  the agent cannot lock a live, visible enemy.
- **FD-2 (W2-6 OFF, usv18, t=25170)** — usv18 killed-flagged; at the C11 FORM step (t=25290) usv18 is a
  live contact 34 km from white_usv16 but has no track → the C11 gate cannot see it.
- **FD-3 (W2-6 ON, 14 targets)** — with REVIVE=1 each of these live targets is re-tracked; windows
  16→26, kills 10→14.
- **W2-4 ON** — 10 false-death targets (usv11..usv20); reviving them changes the engagement; the first
  action divergence is at step 260 (02:10:30).
No evidence of FALSE_REVIVAL (reviving a genuinely-dead target) was found; it is structurally prevented
because revive requires a current positioned observation (active⇒alive).
