# Near-Miss Cases (offline, representative)

Offline scan of the 2035 saved states: 895 states contain an imminent (risk>=HIGH or
deficit<0) corridor and 777 contain a FREE platform whose best-ETA target is one of those
imminent corridors (~38%, consistent with the soft/elastic counterfactual). These are the
"potentially beneficial but not realised live" states.

Live dev4 realises only the subset where (a) a FREE platform exists while the imminent target
is treated as uncovered/deficit, and (b) the reallocation cadence allows it. Most imminent
corridors already carry a comparable lead, so the unrealised opportunity is *additional*
(FREE) interceptors on imminent corridors rather than owner swaps; per-event quality of the
realised subset is GOOD (5) vs BAD (2, very late transient).

Representative gate picture: candidate is FREE (always eligible class), so the binding live
gate is the TRIGGER narrowness (uncovered-only), not commitment/cooldown/hysteresis.
Instrumentation for per-state machine-readable gate attribution was not available for the
stored states; recorded here as offline proxy only.
