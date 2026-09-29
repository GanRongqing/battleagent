# CBR (Case-Based Reasoning) — EXTENSION POINT ONLY

NOT implemented this round. The interface is reserved for future work:

```
recent trajectory -> feature embedding / handcrafted features
                  -> retrieve similar historical maneuvers (top_k)
                  -> provide a prior to PredictorManager
```

No database, no retrieval implemented. See `base.py` for the (interface-only) contract.
