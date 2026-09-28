# C18 Pre-T2 Economic-Value Characterization Contract

Status: prospectively specified before C18 analysis.

## 1. Purpose

The research objective is:

slow entry,
then after entry switch to faster causal observation/execution,
and determine when an exit is economically justified.

The objective is NOT inherently to exit quickly.

C7-C17 showed:

- post-entry higher-resolution state information is measurable and useful;
- T2 is a meaningful favorable lifecycle state;
- direct post-T2 exit rules damaged the right tail;
- post-T2 HOLD_BETTER / EXIT_BETTER state is persistent;
- existing local, cross-asset, and entry-to-T2 features did not robustly predict
  that post-T2 economic state.

C9, however, showed that the pre-T2 model can predict:

    P(T2 before P0 | causal current state)

with materially useful discrimination.

C18 therefore asks:

"Does the frozen C9 pre-T2 probability also correspond to the economic value
of continuing the trade rather than exiting now?"

C18 is a descriptive economic-alignment study.

It is NOT a trading-policy experiment.

## 2. Frozen dependencies

Reuse without scientific modification:

- C7 frozen population and canonical P0 execution
- C8 frozen 60m/5m pre-T2 architecture
- C9 calibrated pre-T2 probability model
- C9 causal feature construction
- C_BASE cost semantics

No modification of C7-C17 scientific behavior.

No 2026 data or metadata access.

## 3. Population

Use the original frozen 2,199 E1 trades.

Pre-T2 state population consists only of eligible causal snapshots strictly
before:

- first T2 occurrence, if T2 occurs first; or
- canonical P0 termination, if P0 occurs first.

Expected frozen outcome structure:

- T2_FIRST: 845 trades
- P0_FIRST: 1,354 trades

Use the same pre-T2 snapshot eligibility and causal timing semantics as C9.

Preserve zero-row / unavailable-state accounting explicitly.

## 4. Primary economic target

At each eligible pre-T2 state snapshot t define:

EXIT_NOW_NET(t):
    net outcome if the position exits at the immediate next available 1-minute
    open after the completed state t.

HOLD_TO_P0_NET(t):
    net outcome if the trade remains unchanged until its original frozen
    canonical P0 exit.

Primary economic target:

DELTA_V_PRE(t) =
    HOLD_TO_P0_NET(t) - EXIT_NOW_NET(t)

Interpretation:

DELTA_V_PRE > 0:
    continuing to canonical P0 was economically better than exiting now.

DELTA_V_PRE < 0:
    exiting now was economically better than holding to canonical P0.

DELTA_V_PRE == 0:
    economically equivalent.

This is future-derived evaluation information only.

## 5. Leakage firewall

C9 probability and features remain strictly causal.

DELTA_V_PRE and all future-derived quantities are evaluation-only.

They must never enter:

- C9 feature generation
- C9 probability estimation
- preprocessing
- state construction
- alignment logic

Future MFE, future MAE, future T2 outcome, future P0 return, recovery, and
future path data are prohibited from predictors.

Add explicit leakage tests.

## 6. Execution semantics

For EXIT_NOW_NET:

- state must be based only on completed information;
- execute at the immediate next available 1-minute open;
- execution must be strictly before canonical P0;
- P0 wins ties;
- missing, duplicate, or discontinuous execution evidence fails closed and
  makes that snapshot ineligible.

Use exact frozen cost semantics.

Primary cost:
C_BASE.

Descriptive sensitivity:
C0, C_S5, C_S10.

No cost selection.

## 7. Primary C9 probability characterization

Use the frozen honest C9 calibrated probability:

    p_t2 = P(T2 before P0 | causal current state)

Do not refit or recalibrate it for C18.

Characterize DELTA_V_PRE by fixed probability bands:

- <0.20
- 0.20 to <0.40
- 0.40 to <0.60
- 0.60 to <0.80
- >=0.80

For each band report:

- snapshots
- unique trades
- mean DELTA_V_PRE
- median DELTA_V_PRE
- p10
- p25
- p75
- p90
- fraction DELTA_V_PRE > 0
- fraction DELTA_V_PRE < 0
- exact-zero fraction

Use whole-trade-aware weighting so long trades do not dominate.

## 8. Economic monotonicity

C18 must test whether increasing frozen C9 probability corresponds
directionally to increasing economic continuation value.

Report:

- probability-band mean DELTA_V_PRE
- probability-band median DELTA_V_PRE
- probability-band fraction HOLD_BETTER
- Spearman association between p_t2 and DELTA_V_PRE
- trade-weighted correlation between p_t2 and DELTA_V_PRE

These are characterization metrics.

Do not derive an action threshold.

## 9. Outcome-class decomposition

Report economic value separately for frozen outcome classes:

T2_FIRST
P0_FIRST

For each:

- mean/median DELTA_V_PRE
- fraction HOLD_BETTER
- probability-band breakdown
- elapsed-time breakdown

Purpose:

determine whether C9 probability alignment is merely reflecting T2 labels or
also separates economic continuation value.

## 10. Time structure

Using fixed elapsed-since-entry bands:

- 0-30m
- >30-60m
- >60-120m
- >120-240m
- >240m

report:

- p_t2 distribution
- DELTA_V_PRE mean/median
- HOLD_BETTER fraction
- p_t2 / DELTA_V_PRE association

Also report fixed remaining-to-P0 bands where applicable.

No timing threshold search.

## 11. Probability trajectory versus economic trajectory

For each trade, characterize:

- frozen C9 p_t2 trajectory
- realized evaluation-only DELTA_V_PRE trajectory

Report:

- whether rising p_t2 tends to coincide with improving DELTA_V_PRE
- whether falling p_t2 tends to coincide with deteriorating DELTA_V_PRE
- within-trade correlation where enough observations exist
- distribution of within-trade correlations

Use deterministic aggregation.

Do not select visually interesting trades manually.

## 12. Economic-state persistence

Define:

HOLD_BETTER:
    DELTA_V_PRE > 0

EXIT_BETTER:
    DELTA_V_PRE < 0

EXACT_ZERO:
    DELTA_V_PRE == 0

Report:

- transitions per trade
- fraction monostate
- 5m / 15m / 30m same-state persistence

This is descriptive only.

Do not define a policy.

## 13. Relation to C9 classification performance

Report C9 predictive performance exactly as frozen / reproduced:

- Brier
- log loss
- AUC
- calibration

Then report separately its economic-alignment metrics from C18.

Do not conflate:

"predicts T2 before P0"

with:

"predicts positive economic continuation value."

C18 exists specifically to test whether those two quantities align.

## 14. Right-tail concentration

Characterize positive DELTA_V_PRE concentration at trade level:

- top 1%
- top 5%
- top 10%
- top 20%

Report cumulative contribution to positive economic continuation value.

Also report:

- Gini coefficient if deterministic
- maximum positive DELTA_V_PRE per trade
- minimum DELTA_V_PRE per trade

Purpose:

determine whether a small minority of trades dominate the economic value of
continuing.

No policy may be derived from this.

## 15. Year stability

Report all primary economic-alignment findings separately for:

- 2024
- 2025

2025 is descriptive validation of the frozen C9 probability/economic
relationship.

No revision after seeing 2025.

2026 remains sealed.

## 16. Symbol stability

Report primary alignment metrics separately for:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

No symbol-specific rules.

No exclusions.

## 17. Frozen interpretation criteria

ECONOMIC_ALIGNMENT_SUPPORTED if:

- mean DELTA_V_PRE increases directionally across the frozen p_t2 bands in
  both 2024 and 2025;
- HOLD_BETTER fraction increases directionally across bands in both years;
- p_t2 / DELTA_V_PRE association is positive in both years;
- high-probability states have materially higher continuation value than
  low-probability states;
- relationship is not driven by one symbol only.

WEAK_ECONOMIC_ALIGNMENT if:

- relationship is directionally positive but materially non-monotonic,
  unstable by year/symbol, or weak in magnitude.

NO_USEFUL_ECONOMIC_ALIGNMENT if:

- frozen C9 probability does not meaningfully track economic continuation
  value.

INSUFFICIENT if:

- leakage-safe target construction, C9 reproduction, or required temporal
  alignment cannot be established.

Do not redefine these criteria after results.

## 18. Implication

If ECONOMIC_ALIGNMENT_SUPPORTED:

C18 supports moving toward a prospectively frozen early failure-recognition
policy experiment in a later checkpoint.

If WEAK_ECONOMIC_ALIGNMENT:

identify what part of the relationship is stable before any policy test.

If NO_USEFUL_ECONOMIC_ALIGNMENT:

do not use C9 probability directly as an economic exit signal; revisit the
pre-T2 economic target/state formulation.

Do not implement a policy in C18.

Do not start C19.

## 19. Artifacts

Write to:

artifacts/c18_pre_t2_economic_value/

Required:

- run_manifest.json
- provenance.json
- leakage_firewall.json
- population_reconciliation.json
- target_definition.json
- target_summary.json
- probability_band_summary.json
- economic_monotonicity.json
- outcome_class_summary.json
- elapsed_time_summary.json
- trajectory_alignment.json
- economic_state_persistence.json
- c9_reproduction.json
- right_tail_concentration.json
- year_summary.json
- symbol_summary.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid large redundant dumps.

## 20. Tests

Add focused tests for:

- C9 frozen probability reproduction
- DELTA_V_PRE construction
- next-1m-open semantics
- cost parity
- P0 tie precedence
- gap handling
- causal pre-T2 snapshot boundaries
- strict target/feature separation
- whole-trade weighting
- probability-band assignment
- trajectory alignment
- economic-state transition/persistence calculation
- year/symbol grouping
- deterministic results
- no 2026 access

Run focused tests.

Run full repository suite once.

## 21. Governance

Do not:

- modify C7-C17 scientific behavior
- train a new predictive model
- recalibrate C9
- define or test an exit policy
- optimize P&L
- search probability thresholds
- search horizons
- search symbols
- access 2026
- begin C19
- stage, commit, or push

## 22. Final report

Report:

1. contract SHA
2. population/snapshot reconciliation
3. leakage firewall result
4. C9 frozen reproduction
5. overall DELTA_V_PRE distribution
6. HOLD_BETTER / EXIT_BETTER proportions
7. DELTA_V_PRE by frozen C9 probability band
8. economic monotonicity metrics
9. T2_FIRST decomposition
10. P0_FIRST decomposition
11. elapsed-time structure
12. p_t2 versus DELTA_V_PRE trajectory alignment
13. economic-state persistence
14. right-tail concentration
15. 2024 alignment
16. 2025 alignment
17. symbol stability
18. frozen interpretation classification
19. implication for C19
20. limitations
21. artifact hashes
22. focused/full tests
23. git diff --check
24. git status --short
25. confirmation no new model/recalibration
26. confirmation no exit policy/P&L optimization
27. confirmation no threshold/horizon/symbol search
28. confirmation no 2026 access
29. confirmation nothing staged/committed/pushed

STOP after C18.
