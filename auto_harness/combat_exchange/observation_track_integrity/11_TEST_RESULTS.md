# 11 — TEST RESULTS
`test_observation_integrity.py` — **6/6 PASS**
1 live positioned contact tracked; 2 bearing-only has no position; 3 killed suppressed by default;
4 revive on legal active+position (flag ON); 5 revive NOT triggered by bearing-only (no fabricated
position, stays in killed_names); 6 no truth-leakage fields in the new branch.
Regression: `import agent_hybrid_v5` OK; flag OFF keeps frozen behaviour (test 3).
