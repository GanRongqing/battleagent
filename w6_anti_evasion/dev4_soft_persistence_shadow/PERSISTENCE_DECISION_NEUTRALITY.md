# Decision Neutrality
Replay operates purely on the previously logged shadow decision stream (frozen W5 policy).
The state machine writes no assignments/tasks; timers derive from logged legal shadow states.
Decision-neutral by construction; determinism PASS (pure sequential function); hidden-truth
PASS (no hidden fields read). Overhead: negligible offline.
