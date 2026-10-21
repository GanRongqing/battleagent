# 02 — UNIT TESTS
`test_passive_contract.py` — **5/5 PASS**
1 base TrackManager does NOT refresh bearing (BUG demonstrated: stale 90° despite a 45° alert);
2 PassiveAwareTrackManager refreshes bearing; 3 bearing-only never promoted to `has_position`;
4 detector memory retains `detected_by`; 5 episode isolation.
