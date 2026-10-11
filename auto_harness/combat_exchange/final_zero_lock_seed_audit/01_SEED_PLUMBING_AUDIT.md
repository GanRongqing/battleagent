# 01 — SEED PLUMBING AUDIT

## Seed source (engine)
`hsystem/sim_script/scenario/adaptation.py::_seed_rng()` (called at every `/start` via
`build_simulation`):
```
path = os.environ.get("RW_SEED_FILE", "/tmp/opencode/rw_seed.txt")
seed = int(read(path))            # missing/invalid -> 0
random.seed(seed + 1009)
np.random.seed(seed + 7)
```
`hsystem/sim_script/20250819TZB/scenario_builder.py:93,165,168` uses the same RW_SEED_FILE / +1009 / +7.

## RNG consumers (post-init)
- `simulation/arsenal/locker.py:106` `random.random()` — stochastic lock hit (now deterministic, see epoch).
- `simulation/arsenal/radar.pyx:127` `np.random.random()` — detection probability.
- `simulation/arsenal/motor.pyx:694/719/775/799` `np.random.random()` / `randint` — effects.
- `simulation/core/base_engine.pyx:466/478/2670` `np.random.randint` / `random.random` — log time-tag, cmd confidence.
- `simulation/core/special_effect.py`, `simulation/core/log.py` `np.random.randint` — cosmetic names.

## Plumbing chain (evaluation)
```
run_12strat.py / run_c5_eval.py / run_c6b_eval.py / run_c7_eval.py / run_c7_paired.py
   -> write  /tmp/opencode/seed_w0.txt                      (SEEDFILE)
engine (base_server) launched by /tmp/opencode/svc.sh with
   -> RW_SEED_FILE=/tmp/opencode/seed_det.txt               (DIFFERENT FILE)
adaptation._seed_rng() reads RW_SEED_FILE  ->  seed_det.txt
```

## Finding
The evaluation runners write the nominal seed to **`seed_w0.txt`**, but the engine reads
**`seed_det.txt`** (`/tmp/opencode/svc.sh:17`). The two are never reconciled. Therefore the nominal
seeds 43001..43005 **never reached the engine RNG**; every episode was seeded from the fixed
`seed_det.txt` content (value `11001` during the C7 run).

## Evidence
- `grep RW_SEED_FILE` → only `svc.sh` (seed_det) and the `adaptation`/`scenario_builder` readers.
- Runners: `run_c7_paired.py:106/118`, `run_c7_eval.py:104`, `run_12strat.py:59`, `run_c5_eval.py:18`,
  `run_c6b_eval.py:25` all write `seed_w0.txt`.
- `11_EVALUATION_INDEPENDENCE_AUDIT.csv`: W2-1/W2-2/W2-6 have **1** distinct trajectory and identical
  initial-state hash across the 5 nominal seeds → not independent realizations.
- Controlled test (`02_...`): the engine RNG *is* a correct function of the seed value (distinct draws
  for 43001/43002/43003; identical for repeated 43001) — so the mapping works; only the plumbing is broken.

## Verdict
SEED_INDEPENDENCE = **BROKEN** (nominal seed not wired to engine RNG).
