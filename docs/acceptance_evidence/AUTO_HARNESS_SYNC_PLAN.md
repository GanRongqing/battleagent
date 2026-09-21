# Auto Harness Sync Plan

Goal: bring the LATEST local Auto Harness evidence into the public repo WITHOUT pushing
large raw rollout logs. This plan is NOT auto-executed in Stage 1.

## Current state

- Public repo (`githsysys`, mirror) already contains: `auto_harness/evolution_memory/`,
  `auto_harness/phase0/`, `auto_harness/phase1/`.
- Local-only (not yet in public repo): `phase1_5`, `phase2a_lateral_coverage`,
  `phase2b_forward_sweep`, `phase3_assignment_engagement`, `phase4_track_freshness`,
  `phase5_lock_transition_audit`, `phase6_oracle_decomposition`, `phase7_oracle_guided`,
  `detection_quality_audit`.
- Total local `auto_harness/` size: ~18 MB (phase0 4 MB, phase1 11 MB).
- Raw trace volume: 95 `*.jsonl` (~5.2 MB) + 248 `*.log`.

## A. SHOULD commit (small, core, human-readable)

Patterns:
- `*_REPORT.md`, `*_DESIGN.md`, `*_SUMMARY.md`, `*_ANALYSIS.md`, `README*`
- canonical small CSVs (e.g. `ASSIGNMENT_EVENTS.csv`, `AUTO_HARNESS_DERIVED.csv`, `*_RESULTS.csv`)
- policy cards / manifests: `*.json` that are cards/manifests/summaries
- `evolution_memory/**`
- phase `*.py` (design/analysis code)
- `WHITE_INTERCEPTION_EVOLUTION.csv`

Suggested per-phase minimal set:
| phase | commit | rationale |
|---|---|---|
| phase1_5 | reports + csv | small |
| phase2a_lateral_coverage | *_REPORT.md, *_ANALYSIS.md, *.csv, *.py | small (~56 KB) |
| phase2b_forward_sweep | reports + csv + py | small (~236 KB, but drop jsonl/log) |
| phase3_assignment_engagement | reports + ASSIGNMENT_EVENTS.csv + py | small (~116 KB) |
| phase4_track_freshness | reports + py | drop w5log_*/ traces (~524 KB) |
| phase5_lock_transition_audit | reports + py | drop w5log_*/ traces (~680 KB) |
| phase6_oracle_decomposition | reports + py | drop traces (~672 KB) |
| phase7_oracle_guided | reports | tiny (~8 KB) |
| detection_quality_audit | reports + csv | small (~52 KB) |

## B. SHOULD NOT commit (large / raw / regenerable)

- `*.jsonl` raw rollout / audit / translog / tracklog traces
- `*.jsonl.ctrl` control traces
- `*.log` agent stdout
- `__pycache__/`, `*.pyc`
- large per-seed dumps under `*/w5log_*/`, `*/dev_cand/`, `*/fresh_cand/`

## Proposed command (to run in a LATER stage, after approval)

```bash
# sync only reports/design/csv/json/py, exclude raw traces
rsync -av --prune-empty-dirs \
  --include='*/' \
  --include='*.md' --include='*.csv' --include='*.json' --include='*.py' \
  --exclude='*.jsonl' --exclude='*.log' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='w5log_*/' --exclude='dev_cand/' --exclude='fresh_cand/' \
  /root/autodl-tmp/hsystem/auto_harness/ /root/autodl-tmp/githsysys/auto_harness/
```

## Decision for Stage 1
- **Deferred.** Stage 1 does NOT sync auto_harness. It is documented here for the next stage.
