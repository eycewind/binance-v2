# C17 Entry-to-T2 Path Economic-Class Contract

Status: prospectively specified before C17 analysis.

## 1. Purpose

C14 defined economic value:

DELTA_V(t) =
    HOLD_TO_P0_NET(t) - EXIT_NOW_NET(t)

C15 showed that this economic state is highly persistent within trades.

C16 showed that contemporaneous cross-asset context does not robustly improve
prediction of this economic state.

C17 asks:

"Is the eventual post-T2 economic class already distinguishable from the
causal path by which the trade reached T2?"

C17 is a predictive characterization study.

It is NOT a trading-policy experiment.

## 2. Frozen dependencies

Reuse without scientific modification:

- C7 population and canonical P0
- C10/C11 causal post-T2 architecture
- C14 DELTA_V semantics
- C15 trade economic-class definitions
- C16 findings

No 2026 data or metadata may be accessed.

## 3. Unit of analysis

Use ONE observation per eligible trade.

For each trade:

features are calculated using information available through the first eligible
post-T2 snapshot only.

No later post-T2 information may enter the predictors.

Primary labels come from C15 trade-level economic class.

## 4. Primary target

Use C15 definitions exactly:

PREDOMINANTLY_HOLD:
    >80% eligible post-T2 snapshots are HOLD_BETTER

PREDOMINANTLY_EXIT:
    >80% eligible post-T2 snapshots are EXIT_BETTER

MIXED:
    otherwise

Primary binary modeling population:

PREDOMINANTLY_HOLD versus PREDOMINANTLY_EXIT.

MIXED trades are excluded from primary binary fitting and reported
descriptively.

Do not alter the 80% threshold.

## 5. Leakage firewall

The economic-class target is future-derived target information only.

Predictors may use only information causally available through the first
eligible post-T2 snapshot.

Prohibited predictors include:

- DELTA_V
- future P0 return
- future MFE/MAE
- future recovery
- future continuation/deterioration outcome
- post-first-snapshot future bars
- C15 economic class
- any statistic calculated from future post-T2 observations

Add explicit leakage tests.

## 6. Frozen feature groups

### M1: frozen local first-snapshot state

Use the existing frozen C11 local causal feature representation evaluated at
the first eligible post-T2 snapshot.

Do not change or search this feature set.

### M2: M1 plus entry-to-T2 path descriptors

Add ONLY the following prospectively frozen causal path descriptors.

A. Timing
- entry_to_t2_minutes
- entry_to_first_0p5pct_minutes
- entry_to_first_1pct_minutes

If a milestone was not reached before T2, record a fixed missing indicator
and deterministic neutral/imputed value using training-only preprocessing.

B. Pre-T2 excursion
- pre_t2_mfe
- pre_t2_mae
- pre_t2_range

All computed strictly from completed bars between entry and T2.

C. Path efficiency
- absolute net entry-to-T2 return divided by cumulative absolute 1m returns

Use one fixed deterministic definition.

D. Peak / drawdown structure
- number of causal new running highs before T2
- maximum drawdown from running peak before T2
- time from last pre-T2 peak to T2

E. Time-above-entry structure
- fraction of completed pre-T2 minutes with close > entry price
- fraction of completed pre-T2 minutes within 0.5% of running peak

F. Pre-T2 volatility
- standard deviation of completed 1m returns over entry-to-T2 path

G. Late-path momentum
Using completed bars only:

- return over final 5m before T2
- return over final 15m before T2
- return over final 30m before T2

If insufficient history exists, use deterministic missing indicators and
training-only imputation.

H. Acceleration
- final 5m return minus preceding 5m return
- final 15m return minus preceding 15m return

No additional path features may be added after results.

## 7. Explicit exclusions

Do NOT add:

- cross-asset C16 features
- volume indicators unless already part of frozen M1
- order-book data
- derivatives/funding data
- sentiment
- additional technical indicators
- new time horizons
- nonlinear transforms chosen after inspection
- interaction searches

## 8. Models

M0:
    training class prevalence

M1:
    fixed logistic model using frozen first-snapshot local state

M2:
    same fixed logistic procedure using M1 plus frozen entry-to-T2 path
    descriptors

No model-family search.

No regularization search.

No feature-selection search.

## 9. Development and validation

2024:
    chronological whole-trade out-of-fold development/evaluation

2025:
    untouched final validation

Requirements:

- one row per trade
- training strictly before validation
- preprocessing fit on training only
- no future target leakage
- no revision after 2025 evaluation

2026 remains sealed.

## 10. Primary metrics

Report M0/M1/M2:

- Brier score
- log loss
- AUC
- calibration intercept
- calibration slope
- ECE

Primary comparison:

M2 versus M1.

## 11. Frozen interpretation criteria

PATH_SIGNAL_SUPPORTED if:

- M2 improves over M1 on BOTH Brier and log loss in 2024 OOF;
- M2 improves over M1 on BOTH Brier and log loss in untouched 2025;
- M2 AUC > M1 AUC in both years;
- M2 calibration slope is positive in both years;
- direction of improvement is not dependent on one symbol alone.

WEAK_PATH_SIGNAL if:

- M2 improves at least one proper score over M1 in both years,
  OR
- both proper scores improve clearly in one year and directionally in the
  other,
but full support criteria fail.

NO_USEFUL_PATH_SIGNAL if:

- M2 does not show stable improvement over M1.

INSUFFICIENT if:

- causal path reconstruction, target provenance, or validation cannot be
  established.

Do not redefine criteria after results.

## 12. Deterioration-first descriptive subgroup

Using the frozen C10 event label, evaluate the SAME M1 and M2 models among
DETERIORATION_FIRST trades.

Do not fit subgroup-specific models.

Report:

- prevalence
- Brier
- log loss
- AUC
- calibration

Purpose:

determine whether entry-to-T2 path helps distinguish economically recoverable
versus economically harmful deterioration.

## 13. MIXED trade characterization

Do not train on MIXED trades.

Report their fixed M1 and M2 predicted probabilities descriptively.

Compare their path-feature distributions with predominantly HOLD and EXIT
classes.

Do not redesign the model based on MIXED trades.

## 14. Path-feature family ablation

One fixed 2024-only descriptive ablation is allowed.

Starting from M2, remove one entire family at a time:

- timing
- excursion
- efficiency
- peak/drawdown
- time-above-entry
- volatility
- late momentum
- acceleration

Do not evaluate ablations on 2025.

Do not redesign M2 based on ablations.

## 15. Feature associations

Report standardized M2 coefficients grouped by:

- frozen local state
- timing
- excursion
- efficiency
- peak/drawdown
- time-above-entry
- volatility
- late momentum
- acceleration

Interpret as predictive associations only.

## 16. Symbol robustness

Report M1 and M2 metrics separately for:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

No symbol-specific models.

No exclusions.

## 17. Artifacts

Write to:

artifacts/c17_entry_to_t2_path_class/

Required:

- run_manifest.json
- provenance.json
- leakage_firewall.json
- population_reconciliation.json
- trade_class_definition.json
- path_feature_schema.json
- path_reconstruction_audit.json
- fold_definitions.json
- model_metrics_2024.json
- calibration_2024.json
- deterioration_subset_2024.json
- family_ablation_2024.json
- frozen_model_procedure.json
- model_metrics_2025.json
- calibration_2025.json
- deterioration_subset_2025.json
- mixed_trade_summary.json
- symbol_metrics.json
- feature_associations.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid redundant raw dumps.

## 18. Tests

Add focused tests for:

- one-row-per-trade construction
- entry/T2 timestamp boundaries
- no post-first-snapshot predictor access
- milestone timing
- pre-T2 MFE/MAE
- path efficiency
- peak/drawdown logic
- time-above-entry fractions
- volatility
- late momentum
- acceleration
- missing-history handling
- leakage firewall
- chronological folds
- training-only preprocessing
- deterministic model results
- no 2026 access

Run focused tests.

Run the full repository suite once.

## 19. Governance

Do not:

- modify C7-C16 scientific behavior
- define an exit policy
- optimize P&L
- search thresholds
- search horizons
- search models
- add features after results
- access 2026
- begin C18
- stage, commit, or push

## 20. Final report

Report:

1. contract SHA
2. population reconciliation
3. HOLD / EXIT / MIXED trade counts
4. leakage/path-reconstruction audit
5. exact path feature schema
6. 2024 M0/M1/M2 metrics
7. 2024 M2-vs-M1 comparison
8. 2024 deterioration-first comparison
9. 2024 fixed family ablation
10. 2025 M0/M1/M2 metrics
11. 2025 M2-vs-M1 comparison
12. 2025 deterioration-first comparison
13. MIXED trade characterization
14. symbol robustness
15. strongest path-feature associations
16. frozen interpretation classification
17. whether entry-to-T2 path contains useful economic-class information
18. limitations
19. implication for C18
20. artifact hashes
21. focused/full test results
22. git diff --check
23. git status --short
24. confirmation one row per trade
25. confirmation no policy/P&L optimization
26. confirmation no feature/model/horizon search
27. confirmation no 2026 access
28. confirmation nothing staged/committed/pushed

STOP after C17.
