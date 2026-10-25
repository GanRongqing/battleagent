# 05 — C17 UAV_AREA_BOUNDED_FLIGHT
`agent_hybrid_uav_bounds.py` (white-combat-0017-v1, parent C10). ONE mechanism: bound every UAV flight
waypoint's y to the fleet's **own initial y extent + 10 km** (recorded at first observation; legal
own-history) so UAVs never reach the operational-area edge. No scenario/route/strategy ID, no truth; x uses
existing world bounds; lock/fire/radar unchanged.
Tests `test_uav_bounds.py` **3/3**: target y clamped, inside value unchanged, y_limit derived from fleet extents.
