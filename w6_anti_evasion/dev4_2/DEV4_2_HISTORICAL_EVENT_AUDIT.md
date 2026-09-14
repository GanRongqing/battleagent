# Historical dev4 Event Audit vs dev4.2 rule

dev4 real events (5 GOOD / 2 BAD) were FREE additions to imminent corridors at sim 14k-21.7k
with FREE ETA ~4.4k-17.5k against corridor leads 6.4k-10.4k.

Under dev4.2:
- deadline feasibility requires ETA*(1+0.2) <= breakthrough_eta(C). Imminent corridors sit
  near the break line (small breakthrough_eta); FREE ETA values (thousands of seconds) far
  exceed it -> ALL 7 events (incl. 5 GOOD) would be REJECTED as DEADLINE_INFEASIBLE.
Explanation (not a rule bug per se): the historical GOOD adds were post-deadline "extra
attacker / endgame swarm" near resolution; they were harmless but tactically weak. dev4.2
deliberately does not replicate deadline-infeasible additions. Acceptance therefore relies on
genuinely deadline-feasible reinforcements, which the offline funnel found = 0 because FREE
platforms are geometrically far from near-breakline corridors.

BAD events (2 late transient): also rejected (deadline), i.e. not amplified. No GOOD event is
"captured" by dev4.2; the reason is documented: FREE-imminent reinforcement that is
deadline-feasible essentially never exists in these states.
