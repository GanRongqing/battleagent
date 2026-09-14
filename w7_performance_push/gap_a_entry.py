import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from w7_performance_push.gap.w7_gap import W7GapAAgent
if __name__ == "__main__":
    use = "--no-uav" not in sys.argv
    W7GapAAgent(use_uavs=use).run()
