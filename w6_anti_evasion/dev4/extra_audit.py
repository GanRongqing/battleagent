import sys, os
sys.path.insert(0, os.getcwd())
import dev4_live
for seed in (4001, 4002):
    print("EXTRA seed", seed, flush=True)
    dev4_live.run_one(seed)
print("extra done; events:", sum(1 for _ in open("dev4_events.jsonl")), flush=True)
