# Predictor Evolution (future)

LLM is NOT used for online coordinate prediction. It is reserved for OFFLINE evolution:

```
trajectory failures
   -> LLM discovers a new maneuver pattern (offline)
   -> LLM proposes a predictor candidate (interface: MotionPredictor)
   -> unit tests (synthetic + offline replay)
   -> replay benchmark (median / p90 error, best-model share, selector regret)
   -> accepted predictor added to the library
```

This round establishes only the interface + online scoring + shadow logging that such a
pipeline would feed into. Streaming residual learning (`physics_prediction + learned_residual`) and
CBR (`CaseRetriever`) are compatible future extensions; neither is implemented here.
