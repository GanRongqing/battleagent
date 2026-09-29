# Unit Test Report — white-combat-0002-v1

`test_allocator_expand.py` — 7/7 PASS:
- TEST A: zero-owner visible target + free USV -> free USV assigned to it.
- TEST B: multiple zero-owner + free -> filled until exhausted.
- TEST C: stable-lock owner not stolen to cover a zero-owner target.
- TEST D: free USV goes to zero-owner (0->1) before giving a 2-owner target its 3rd attacker.
- TEST F: reserve released under under-commitment.
- TEST G: no under-commitment -> reserve preserved (ExpandingAllocator == base ThreatAllocator).
- TEST H: variable cardinality 3/5/10/15/20 friendly USVs.
