# 04 — UAVManager DECISION AUDIT
- In GLOBAL_REACQUIRE (mission after >90 s without ship tracks) the UAVs use `coverage.best_unobserved`;
  the coverage grid is x∈[0,300], y∈[80,620] km (E19), so the fleet's y≈0 line is **not even representable**
  and the grid bias sends UAVs **north-west** — exactly the observed 159–264 km, x 46–126 positions.
- `_search_fly` sweeps fixed east/west courses at the UAV's current y; it never references the fleet front.
- Consequence: at the decisive window the UAVs are 220–325 km from the fleet and cannot share positions.
- No evidence of a TrackManager drop: the issue is that no UAV was ever near the contact geometry.
=> A fleet-relative recon target (tether to the front) is the minimal, general fix. **VERIFIED by code + logs.**
