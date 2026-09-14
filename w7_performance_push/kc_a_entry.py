import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from w7_performance_push.killchain.w7_kc import W7KcAAgent
if __name__ == "__main__":
    use = "--no-uav" not in sys.argv
    W7KcAAgent(use_uavs=use).run()
