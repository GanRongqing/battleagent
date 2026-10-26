# 05 — C25 FLEET_TETHERED_RECON (white-combat-0025-v1, parent C19)
ONE mechanism: while a UAV is in SEARCH/SCREEN/GLOBAL_SEARCH, replace its recon target with a tether point
**30 km ahead of the fleet's forward-most USV**, spread across the fleet's y (±30 km). RETURN/LANDING/
CHARGING/battery safety untouched; C19 USV behaviour unchanged. Uses only own USV/UAV positions; no
scenario/route ID, no truth. Unit tests `test_fleet_recon.py` 3/3.
