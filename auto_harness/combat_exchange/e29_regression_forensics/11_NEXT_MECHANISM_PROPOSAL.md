# 11 — NEXT MECHANISM PROPOSAL (not implemented)
**Fix the boundary model, not the tactics.** Replace the hardcoded W2 rectangle with a *scenario-grounded*
safe region derived from legal information, e.g.:
1. Expose the public operational-area polygon in a legal observation (it is public map geometry, not enemy
   truth) and use it; or
2. Derive the safe box dynamically from the fleet's own initial/deployed positions and legal motion history
   (e.g., keep within the convex hull of own positions expanded by a margin), so the layer never assumes a
   coordinate frame it cannot see.
Then: safety only intervenes near the *actual* boundary, and is inactive in the interior (no constant rewrite).
Validation plan: re-run W2 six (must keep AREA_OUT=0 and pooled CER ≈1.922) AND non-W2 seven (must recover to
C10-like CER) with the same seed; prove the safety rewrite no longer fires in the interior (count==0 for
interior steps) and that a genuine boundary still triggers it.
