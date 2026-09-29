# Version Lineage

```mermaid
graph TD
  W5["W5 (frozen baseline, e823e7be)"] --> C1["C1 survival retreat"]
  C1 -->|DROPPED| X1["DEV_REVERSED (timing noise)"]
  W5 --> ACE["ACE = allocator commitment expansion (7527253c)"]
  ACE -->|DEV_SUPPORTED / FRESH_UNCONFIRMED| ACEs["CER 0.373 -> 1.065, 6/6"]
  ACE --> C2["C2 lock-first approach (dda82730)"]
  C2 -->|INCONCLUSIVE| C2s["lock up, TTFL up, combat mixed"]
  ACE --> C3["C3 survival-aware prelock (9cae3045, DRAFT)"]
```

```
W5 (frozen)
├── C1 survival retreat ................ DROPPED
└── ACE allocator expansion ............ DEV_SUPPORTED / FRESH_UNCONFIRMED
    ├── C2 lock-first approach ......... INCONCLUSIVE
    └── C3 survival-aware prelock ...... DRAFT (diagnosis done, validation incomplete)
```
