# C15 Economic-State Temporal Structure Contract

Status: prospectively specified before C15 analysis.

## 1. Purpose

C14 defined the post-T2 economic target:

DELTA_V(t) =
    HOLD_TO_P0_NET(t)
    -
    EXIT_NOW_NET(t)

where:

- DELTA_V > 0 means holding to frozen canonical P0 was economically superior
  to exiting at the next executable 1-minute open.
- DELTA_V < 0 means exiting immediately was economically superior.

C14 found that the existing causal C11 state representation did not
predict DELTA_V reliably.

C15 asks a prior structural question:

"Does DELTA_V behave like a persistent economic state, or does its sign/value
oscillate too rapidly for instantaneous HOLD_BETTER / EXIT_BETTER
classification to be a useful formulation?"

C15 is descriptive only.

It does not define or evaluate a trading policy.

## 2. Frozen dependencies

Reuse C14 target construction exactly.

Do not modify scientific behavior from C7 through C14.

Primary population:

- 845 first-T2 trades
- 843 binary continuation/deterioration source trades
- causal post-T2 snapshots as established in C14

Primary cost model:

C_BASE

Use the identical C14 DELTA_V construction and execution semantics.

No 2026 data or metadata may be accessed.

## 3. Leakage / future-information rule

DELTA_V is an evaluation-only future-derived quantity.

C15 may analyze the realized historical DELTA_V trajectory because C15 is
descriptive.

No DELTA_V-derived quantity is a live feature or trading signal.

C15 must not use future MFE, MAE, recovery, P0 return, or future path
information to construct new causal features or trading rules.

## 4. Primary economic states

At each eligible snapshot:

HOLD_BETTER:
    DELTA_V > 0

EXIT_BETTER:
    DELTA_V < 0

EXACT_ZERO:
    DELTA_V == 0

Do not introduce a deadband.

Do not optimize a threshold around zero.

## 5. Trade-level transition structure

For every eligible trade report:

- number of eligible snapshots
- number of HOLD_BETTER snapshots
- number of EXIT_BETTER snapshots
- fraction HOLD_BETTER
- fraction EXIT_BETTER
- number of sign transitions:
      HOLD -> EXIT
      EXIT -> HOLD
- total state transitions
- initial economic state
- final eligible economic state
- longest consecutive HOLD run
- longest consecutive EXIT run
- median HOLD dwell length
- median EXIT dwell length

Summarize distributions across trades.

## 6. Clean-transition versus oscillatory paths

Using fixed descriptive definitions:

MONOSTATE:
    no HOLD/EXIT sign transition

SINGLE_TRANSITION:
    exactly one HOLD/EXIT sign transition

LOW_OSCILLATION:
    2-3 transitions

HIGH_OSCILLATION:
    >=4 transitions

These categories are descriptive only.

Report:

- trade counts
- percentages
- snapshots
- DELTA_V distribution
- year split
- symbol split
- continuation-first / deterioration-first composition

Do not change these boundaries after seeing results.

## 7. State persistence

For snapshots with sufficient future eligible observations, estimate:

P(same economic-state sign after k minutes | current sign)

for fixed horizons:

- 1 minute
- 2 minutes
- 5 minutes
- 10 minutes
- 15 minutes
- 30 minutes
- 60 minutes

Report separately for:

HOLD_BETTER current state
EXIT_BETTER current state

Also report transition probability at each horizon.

Use whole-trade-aware weighting so long-duration trades do not dominate.

No horizon search is permitted.

## 8. DELTA_V magnitude around sign changes

For every HOLD -> EXIT and EXIT -> HOLD transition, report DELTA_V:

- 5 minutes before transition, if available
- 2 minutes before
- 1 minute before
- transition snapshot
- 1 minute after
- 2 minutes after
- 5 minutes after

Report:

- mean
- median
- p10
- p25
- p75
- p90

Purpose:

determine whether sign changes generally occur near economically negligible
zero crossings or represent large value reversals.

No threshold is derived from this analysis.

## 9. Near-zero characterization

Use fixed absolute DELTA_V bands:

- < 0.10%
- 0.10% to <0.25%
- 0.25% to <0.50%
- 0.50% to <1.00%
- >=1.00%

These are descriptive magnitude bins, not policy thresholds.

Report what fraction of sign transitions occur when absolute DELTA_V is in
each band.

This tests whether apparent state instability is largely small-value noise.

## 10. Right-tail concentration

C14 found:

- positive mean DELTA_V
- negative median DELTA_V
- minority HOLD_BETTER states

C15 must characterize concentration of positive economic value.

At trade level report contribution to total positive DELTA_V from:

- top 1% of trades
- top 5%
- top 10%
- top 20%

Also report:

- Lorenz-style cumulative contribution table
- Gini coefficient if straightforward and deterministic
- mean/median maximum positive DELTA_V per trade
- mean/median minimum DELTA_V per trade

Do not turn these into a trading rule.

## 11. Temporal location

Using the fixed C14 elapsed-since-T2 bands:

- 0-5m
- >5-15m
- >15-30m
- >30-60m
- >60m

report:

- transition rate
- HOLD persistence
- EXIT persistence
- mean DELTA_V
- median DELTA_V
- fraction HOLD_BETTER

Also characterize by remaining time to P0 using the same fixed bands where
applicable.

No timing threshold search.

## 12. Event-state relationship

Report transition/persistence structure separately for frozen C10 event
classes:

- CONTINUATION_FIRST
- DETERIORATION_FIRST

The key question is whether DETERIORATION_FIRST trades contain persistent
HOLD_BETTER periods or merely short-lived sign noise.

Do not fit separate models.

## 13. Year and symbol stability

Report all primary temporal metrics for:

- 2024
- 2025

and separately for:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

This is descriptive stability analysis.

No ranking or symbol-specific policy is permitted.

## 14. Interpretation rules

Freeze the following interpretation categories before results:

PERSISTENT_ECONOMIC_STATE

Use if:
- median trade has <=1 sign transition,
- at least 70% same-state persistence at 5 minutes for both HOLD and EXIT,
- and these findings are directionally consistent in both 2024 and 2025.

MIXED_TEMPORAL_STRUCTURE

Use if:
- economic state has meaningful persistence,
- but one or more persistence/transition criteria are inconsistent by
  state, year, or event class.

HIGHLY_UNSTABLE_ECONOMIC_STATE

Use if:
- median trade has >=4 transitions,
  OR
- 5-minute same-state persistence is <60% for either primary state in
  both years,
  OR
- most transitions are repeated oscillations rather than clean transitions.

INSUFFICIENT

Use if required causal/target reconstruction or temporal alignment cannot be
verified.

These labels describe target structure only.

They do not imply profitability.

## 15. Decision implication

C15 must end by selecting one research direction only:

A. If PERSISTENT_ECONOMIC_STATE:
   existing feature representation is likely insufficient.
   A future checkpoint may investigate richer causal information.

B. If HIGHLY_UNSTABLE_ECONOMIC_STATE:
   instantaneous HOLD_BETTER prediction is likely the wrong target.
   A future checkpoint should investigate persistent/sequential economic
   value rather than feature expansion.

C. If MIXED_TEMPORAL_STRUCTURE:
   identify which aspect is stable and which is unstable before choosing
   feature expansion or sequential-value modeling.

Do not implement the next checkpoint.

## 16. Artifacts

Write to:

artifacts/c15_economic_state_temporal_structure/

Required artifacts:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- trade_transition_summary.json
- transition_distribution.json
- persistence_by_horizon.json
- transition_magnitude_summary.json
- near_zero_transition_summary.json
- right_tail_concentration.json
- elapsed_time_summary.json
- event_class_summary.json
- year_summary.json
- symbol_summary.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid large redundant snapshot dumps.

## 17. Tests

Add focused tests for:

- DELTA_V trajectory reconstruction from frozen C14 semantics
- sign classification
- transition counting
- dwell/run calculations
- persistence horizon calculation
- whole-trade weighting
- near-zero magnitude bins
- concentration calculations
- year/symbol grouping
- deterministic outputs
- no 2026 access

Run focused tests.

Run the full repository test suite once.

## 18. Governance

Do not:

- modify C7-C14 scientific behavior
- introduce new model features
- train a predictive model
- define an exit policy
- optimize P&L
- search thresholds
- search horizons
- access 2026
- begin C16
- stage, commit, or push

## 19. Final report

Report:

1. contract SHA
2. population/snapshot reconciliation
3. DELTA_V transition distribution
4. median/mean transitions per trade
5. MONOSTATE / SINGLE_TRANSITION / LOW_OSCILLATION / HIGH_OSCILLATION counts
6. HOLD persistence by fixed horizon
7. EXIT persistence by fixed horizon
8. year stability
9. symbol stability
10. continuation-first temporal structure
11. deterioration-first temporal structure
12. DELTA_V magnitude around transitions
13. fraction of transitions near zero
14. right-tail concentration
15. elapsed-time structure
16. frozen interpretation classification
17. implication for C16 direction
18. limitations
19. artifact hashes
20. focused/full test results
21. git diff --check
22. git status --short
23. confirmation no model/policy/optimization
24. confirmation no 2026 access
25. confirmation nothing staged/committed/pushed

STOP after C15.
