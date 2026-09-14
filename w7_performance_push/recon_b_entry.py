import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from w7_performance_push.recon_b.w7_recon_b import W7ReconB1Agent
if __name__ == "__main__":
    use = "--no-uav" not in sys.argv
    W7ReconB1Agent(use_uavs=use).run()
