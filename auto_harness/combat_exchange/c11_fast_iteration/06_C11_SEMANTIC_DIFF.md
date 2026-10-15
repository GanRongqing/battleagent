# 06 — C11 SEMANTIC DIFF (vs C10)
Only difference: in the support-candidate list, add `and not self._engaged(tracks, pos[support], now)`.
Everything else byte-equivalent to C10. When no package would form, or all candidate supports are spare,
the action stream is IDENTICAL to C10 (non-trigger equivalence, unit test test_3).
