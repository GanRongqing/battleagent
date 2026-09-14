# Evidence-Driven Alternating Adversarial Co-Evolution

> This is the *System / Method* chapter draft for the thesis. It abstracts the concrete
> White/Black development in this project into a general, reproducible framework. The
> framework is deliberately **not** neural self-play: both sides are explicit policies that
> are alternately frozen and evolved, every change is evidence-driven, and every release is
> versioned and auditable.

## 1. Motivation

Training or evaluating a single agent against a **fixed opponent** has two well-known
limitations:

1. **Policy overfitting** — the agent can memorize opponent-specific patterns and fails to
   generalise when the opponent changes.
2. **Static benchmark limitation** — a fixed opponent gives a fixed difficulty ceiling;
   there is no way to *measure* how an agent's capability grows, because the test itself
   does not grow.

To study capability growth in an agentic system whose runtime policy is partly hand-designed
(controller / doctrine) and partly learned (offline skill evolution), we need a controlled
way to make the environment adversarially harder and then observe a bounded, mechanism-aware
adaptation. This motivates an **alternating adversarial co-evolution** loop in which the two
sides take turns: one side is frozen while the other is evolved from real failure evidence.

## 2. Problem Formulation

Let

- $W_t$ = White (defender) policy at round $t$,
- $B_t$ = Black (attacker / adversary) policy at round $t$,
- $P$ = the shared maritime simulation environment (physics, sensors, weapons),
- $O_W, O_B$ = the legal observations available to each side,
- $S$ = the White doctrine (Skill), and $Q$ = the prompt template (all evaluated offline).

Each episode is a draw from the environment under a scenario seed $s$:

$$\omega \sim \operatorname{Play}\big(P,\ W_t,\ B_t,\ s\big),$$

yielding outcome metrics $M(\omega) = (\text{clean\_win},\ \text{kills},\ \text{losses},\ \text{breakthrough},\ \text{explored},\ \text{resolution})$.

The **fair-play constraint** is that each side's policy is a function of only its own legal
observations:

$$a_W = W_t(O_W),\qquad a_B = B_t(O_B),$$

with $B_t$ never reading White belief/allocations/intent and $W_t$ never reading Black hidden
state. No side may receive a physics buff (speed / sensors / damage) as an "evolution".

## 3. Frozen-Checkpoint Alternation

At every round exactly **one** side may change:

- Round: freeze $(W_t, B_t, S, Q, P)$, record hashes/config/seeds; evolve only $B$; evaluate;
  then freeze $B_{t+1}$ and evolve only $W$; validate on holdout seeds; release $W_{t+1}$.
- Next round repeats with the roles' state carried forward: freeze $W_{t+1}$, evolve $B_{t+1}
  \to B_{t+2}$.

A **frozen checkpoint** means: byte-identified policy files (sha256), a recorded manifest of
hashes, feature gates and seeds, and a rule that no runtime file changes while the checkpoint
is being evaluated. This gives clean attribution of any outcome delta to the single changed
side.

## 4. Adversarial Opponent Evolution ($B_t \to B_{t+1}$)

The opponent is evolved one-sidedly while $W_t$ stays frozen. In this project the opponent
ladder is hand-specified but the framework only requires:

- the change is **legal-observation-driven** ($B$ uses only its own radar intel, e.g.
  `get_black_targets()` plus its own units);
- no physics buff and no hidden-state access;
- no seed / composition / count hard-coding;
- each tier is a minimal, documented capability increment
  (e.g. B0 random → B1 multi-axis grouping → B2 coordinated staggered lanes → B3 runtime
  legal replanning).

## 5. Evidence-Driven Failure Diagnosis

The framework forbids blind "make the agent stronger" iteration. Instead, after adversarial
evaluation the developer extracts **runtime evidence**:

- per-step traces and audits of the failing episodes,
- paired runs (same seed, both policies),
- failure-case lists,

and classifies a root cause. In this project the evidence chain was:

- Stage-1 regression trace → B0/B3 paired logs → root cause class
  `PREDICTION_GEOMETRY` (predictive aim placed interceptors inside the enemy weapon band);
- diagnostic ablation (7 mechanism variants × episodes) → mechanism attribution
  (predictive aim + pursuit-cost allocation degraded engagement; the screen was protective).

A rule that keeps the loop honest: runtime *code bugs* (tracking/allocator/simulator/logging,
stale LLM response) are **never** treated as policy problems; only a missing/ambiguous/over-
aggressive *doctrine or mechanism* may justify a change.

## 6. Controlled White Adaptation ($W_t \to W_{t+1}$)

With the new opponent frozen, White is adapted. The framework requires each change to declare
its **change layer**:

| Layer | Example in this project |
|---|---|
| Skill (doctrine) | offline Skill evolution pipeline (evidence → ANALYST → CRITIC → EDITOR → release) |
| Harness (control code) | W6 anti-evasion layer: predictive interception, pursuit-cost-aware allocation, target handoff, UAV track maintenance, adaptive screen, breakthrough-horizon risk |
| Controller / Perception | standoff geometry states, per-target committed-interceptor handoff reference |

Every mechanism is **feature-gated** so a variant can be turned on/off for ablation and so a
regression can be traced to a single mechanism.

## 7. Mechanism Validation

Before any release the candidate is validated with:

- **unit tests** (deterministic module-level checks, no simulator needed),
- **fair-play tests** (hidden-truth counterfactual: identical legal observation ⇒ identical
  action; internal-state mask on the opposite side; variable-cardinality stress),
- **paired traces** and **ablation** for mechanism attribution,
- **regression** suites that must stay green.

In this project the W6 candidate also received a per-game **mechanism fire-check** (counters
for prediction / intercept-plan changes / unsafe-close / handoff / screen reconfiguration /
high-risk transitions), so a feature cannot silently be a no-op.

## 8. Holdout Evaluation

DEV seeds are kept strictly separate from FINAL seeds. The adaptation is validated and then
finally measured on **unseen holdout seeds** with a **paired design**: for every holdout seed
$s$ we run all three checkpoints $(W_t,B_t), (W_t,B_{t+1}), (W_{t+1},B_{t+1})$, so outcome
deltas are seed-paired. $N=10$ per (scale × checkpoint). Statistical claims are limited to
paired mean/median deltas, offline bootstrap 95% CIs, and descriptive rates — never an
automatic sample-size increase "for significance".

## 9. Versioning and Auditability

Every released artifact is recorded in a version ledger with:

- `version`, `parent`, `change_summary`,
- `hash` (agent), `anti_evasion_dir_hash`, feature gates, and the frozen physics hash,
- DEV result and `approval_status` (`FROZEN` / `DEV_*_AUDIT` / `FINAL-CANDIDATE`),
- a rollback target hash.

A config manifest captured before the final run lists all versioned hashes and the 
reproducibility control (per-game RNG reseed — a determinism fix, not a balance change), so
the entire experiment is reproducible and auditable.

## 10. Current Instantiation

The framework is instantiated by the three-stage experiment in this project:

| Stage | Checkpoint | Meaning |
|---|---|---|
| Stage 0 | $W_5 \times B_0$ | initial baseline |
| Stage 1 | $W_5 \times B_3$ | black evolved only (W5 frozen) |
| Stage 2 | $W_6 \times B_3$ | white anti-evasion adaptation over frozen B3 |

From Stage 0 → Stage 1 we measure the **Black evolution effect**; from Stage 1 → Stage 2 we
measure the **White adaptation effect** (recovery). Mechanism counters collected only in
Stage 2 explain *why* White changed behaviour. The honest reading is descriptive: no claim of
self-play convergence, Nash equilibrium, or automatic strategy discovery is made.

---

*Scope note: this chapter describes the experimental framework and its instantiation; it does
not assert convergence or equilibrium results. Results and limitations are in the companion
experiment report.*
