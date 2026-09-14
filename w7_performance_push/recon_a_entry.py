#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""w7_performance_push/recon_a_entry.py — run the W7-recon-a harness (W5 + recon UAV)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from w7_performance_push.recon.w7_recon import W7ReconAAgent  # noqa: E402

if __name__ == "__main__":
    use_uavs = "--no-uav" not in sys.argv
    W7ReconAAgent(use_uavs=use_uavs).run()
