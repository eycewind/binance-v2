# C30 Fixed-Endpoint Opportunity Prediction Contract

Status: prospectively specified before C30 implementation or evaluation.

## 1. Research question

Using only information available when E1 fires, can a prespecified model
predict whether executable gross return at each frozen 3h/6h/12h/24h endpoint
will be at least +40 bp or +50 bp, with consistent improvement over
training-prevalence baselines in chronological evaluation?

C30 asks whether the historical opportunities established by C29 are
predictable.

C30 does NOT ask whether trading those predictions is profitable.

No trading policy is authorized.

## 2. Scientific context

C29 established:

- economically meaningful fixed-endpoint opportunities exist;
- GROSS40/GROSS50 events occur frequently in both 2024 and 2025;
- opportunities occur across months and symbols;
- opportunity-positive trades remain profitable after realistic frozen costs;
- the whole E1 population remains negative after realistic costs.

Therefore the current problem is opportunity selection:

    Can causal information available when E1 fires distinguish entries that
    later produce sufficiently large fixed-endpoint returns?

## 3. Frozen entry population

Use exact frozen E1 population:

    2,199 trades

Entry rule:

    E1_H1_SMA24_CROSS_V1

Entry hash:

    6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3

Expected:

- 2024: 1,093 trades
- 2025: 1,106 trades

Symbols:

- BNBUSDT
- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT

Reconcile exactly before modeling.

If reconciliation fails materially:

    INSUFFICIENT_RECONCILIATION

and STOP.

## 4. Frozen eight prediction tasks

Evaluate exactly eight binary tasks:

- H3_GROSS40
- H3_GROSS50
- H6_GROSS40
- H6_GROSS50
- H12_GROSS40
- H12_GROSS50
- H24_GROSS40
- H24_GROSS50

These tasks are correlated.

They MUST NOT be interpreted as eight independent confirmations.

## 5. Frozen labels

For horizon H:

    GROSS40_H = 1
        iff executable C0 fixed-endpoint return at H >= +0.40%

    GROSS50_H = 1
        iff executable C0 fixed-endpoint return at H >= +0.50%

Exact equality belongs to class 1.

The label refers to return AT THE FIXED ENDPOINT.

It does NOT mean:

- threshold touched before endpoint;
- maximum favorable excursion;
- any-path threshold crossing;
- take-profit achievement.

Use exact C29 fixed-endpoint execution accounting.

## 6. Horizon availability

A trade may be unavailable for a longer horizon because its endpoint lies
outside the frozen dataset.

Preserve exact C29 availability:

Expected approximately:

- H3: 2,199 valid
- H6: 2,198 valid
- H12: 2,197 valid
- H24: 2,196 valid

Do not fabricate missing endpoints.

No 2026 market data.

## 7. Causal feature timing

Every predictor must be observable no later than the completed E1 decision
state.

Use completed data only.

No feature may depend on:

- entry fill future relative to decision state;
- future 1-minute bars;
- target horizon;
- future volatility;
- MFE;
- P0 outcome;
- T2 outcome;
- future cross-asset movement;
- validation labels.

All feature timestamps must be auditable.

## 8. Frozen compact feature set

Use one identical feature schema for all eight tasks.

No feature search.

No feature-family ablation in C30.

### A. E1 / local asset state

At E1 decision time include:

1. current hourly close relative to SMA24:
       close / SMA24 - 1

2. SMA24 one-hour slope:
       SMA24_t / SMA24_t-1 - 1

3. completed-return windows:
       1h return
       3h return
       6h return
       12h return
       24h return

4. realized volatility from completed hourly returns:
       6h
       12h
       24h

5. E1 cross geometry:
       previous close / previous SMA24 - 1
       current close / current SMA24 - 1
       change in close-minus-SMA24 geometry

### B. BTC market context

For every symbol, including BTCUSDT itself, use completed BTCUSDT data:

1. BTC 1h return
2. BTC 3h return
3. BTC 6h return
4. BTC 12h return
5. BTC 24h return
6. BTC 6h realized volatility
7. BTC 24h realized volatility
8. BTC close / BTC SMA24 - 1
9. BTC SMA24 one-hour slope

For BTCUSDT trades these features may overlap local features.
Do not remove them conditionally by symbol.

### C. Relative-to-BTC state

For the traded symbol:

1. asset 1h return - BTC 1h return
2. asset 3h return - BTC 3h return
3. asset 6h return - BTC 6h return
4. asset 12h return - BTC 12h return
5. asset 24h return - BTC 24h return

For BTCUSDT these values are exactly zero.

### D. Cross-asset confirmation

Using the frozen five-symbol universe and only completed data at E1 time:

1. fraction of the five symbols with positive 1h return
2. fraction with positive 3h return
3. fraction with positive 6h return
4. fraction currently above their causal SMA24
5. mean five-symbol 1h return
6. mean five-symbol 3h return
7. mean five-symbol 6h return

No additional features.

## 9. Missing feature handling

Feature computation must be causal and deterministic.

If a required historical feature cannot be computed:

- do not impute using future data;
- record missingness;
- exclude the row from model evaluation for all tasks requiring that feature.

Do not introduce learned imputation.

Report exclusions.

## 10. Feature transformations

No data-dependent feature selection.

Continuous features may be standardized using training-data mean/std only.

For every fold:

- fit scaler on training rows only;
- apply frozen scaler to validation rows.

No normalization using full-dataset statistics.

No nonlinear transforms unless already explicitly listed above.

## 11. Frozen model

Use one model specification for all eight tasks:

    LogisticRegression

with fixed:

    penalty = L2
    C = 1.0
    solver = lbfgs
    max_iter sufficiently high for convergence
    class_weight = None

Use the same implementation and settings for every task.

No hyperparameter search.

No alternate regularization.

No trees, boosting, neural networks, ensembles, calibration models, or model
selection.

## 12. Baseline

For each task and evaluation fold define:

    p_baseline
      = positive-label prevalence in the eligible training population

Every validation row receives this constant baseline probability.

Baseline must use training labels only.

Do not use validation prevalence.

## 13. Chronological evaluation

Evaluation must be strictly chronological.

Training labels must be FULLY RESOLVED before validation begins.

For each trade/task define:

    LABEL_RESOLUTION_TIME
      = executable fixed-endpoint timestamp used to determine its label

A row is eligible for training only if:

    LABEL_RESOLUTION_TIME < validation_start

An entry occurring before validation_start but whose endpoint resolves after
validation_start MUST NOT be used for training.

## 14. Frozen evaluation structure

Use two chronological evaluations.

### 2024 evaluation

Construct one honest 2024 validation block using the same broad chronology
principle as prior experiments:

- training consists only of earlier 2024 entries whose task-specific labels
  are fully resolved before validation start;
- validation consists of later 2024 entries;
- one common validation-start timestamp must be frozen before model fitting.

Choose the common 2024 validation start deterministically as:

    2024-07-01 00:00:00 UTC

For each task, training eligibility is still determined by that task's
LABEL_RESOLUTION_TIME.

Do not move the split after observing performance.

### 2025 evaluation

Fit once using all eligible 2024 rows whose task-specific labels are fully
resolved by:

    2025-01-01 00:00:00 UTC

Evaluate on untouched eligible 2025 rows.

No 2025 refitting.

No rolling retraining.

No 2026 data.

## 15. Fold reporting

For every task report:

### 2024

- training row count
- validation row count
- training positive prevalence
- validation positive prevalence
- earliest/latest training entry
- latest training label-resolution time
- earliest/latest validation entry

### 2025

- training row count
- validation row count
- training prevalence
- validation prevalence
- latest training label-resolution time

If either class is absent in a training set:

    INSUFFICIENT_TASK_TRAINING

for that task.

Do not alter the split.

## 16. Primary predictive metrics

For baseline and model report:

- Brier score
- log loss

Define improvements as:

    DELTA_BRIER
      = BRIER_BASELINE - BRIER_MODEL

    DELTA_LOGLOSS
      = LOGLOSS_BASELINE - LOGLOSS_MODEL

Positive means the model improves over training prevalence.

These are the PRIMARY metrics.

## 17. Complementary discrimination metrics

Report:

- ROC AUC
- PR AUC

AUC is complementary only.

Do not treat AUC improvement without proper-score improvement as sufficient
evidence.

## 18. Calibration diagnostics

For every task/year report:

- prediction mean
- actual prevalence
- calibration intercept if available without fitting a new model
- calibration slope if available as diagnostic only
- expected calibration error using fixed prespecified 10 equal-width
  probability bins

Do NOT recalibrate predictions.

Do not use validation data to alter model probabilities.

## 19. Dependence-aware predictive uncertainty

Required.

Predictions are frozen before bootstrapping.

No model refitting inside bootstrap replicates.

### A. Whole-trade bootstrap

- 2,000 replicates
- fixed PCG64 seed
- resample complete validation trades
- preserve all eight task predictions/outcomes together where available

For every task/year report 95% intervals for:

- DELTA_BRIER
- DELTA_LOGLOSS
- ROC AUC
- PR AUC

### B. UTC entry-calendar-month block bootstrap

- 2,000 replicates
- fixed PCG64 seed
- whole validation trades attached to UTC entry month
- preserve all eight tasks together

Report same quantities.

No row/snapshot-level bootstrap.

## 20. Prespecified probability groups

For each task/year create five probability groups:

    P1 ... P5

Boundaries must be learned from MODEL PREDICTIONS ON THE TRAINING POPULATION
ONLY.

Use weighted/equal-count quintile intent with deterministic tie handling:

- identical probability values must never be split across groups;
- record numeric boundaries;
- apply frozen boundaries to validation predictions.

Do not use validation quantiles.

Do not alter group count.

These groups are descriptive only.

## 21. Economic companion

For each task/year/probability group report the corresponding realized
fixed-endpoint return distribution.

### Gross C0 return

Report:

- trade count
- opportunity-positive count
- opportunity rate
- mean return
- median return
- p10
- p25
- p75
- p90
- positive-return fraction
- negative-return fraction
- mean positive return
- mean negative return
- total positive contribution
- total negative contribution
- net contribution

### DESIGN_BNB net return

Using the exact C29 DESIGN_BNB assumptions report:

- mean
- median
- p10
- positive fraction
- negative fraction
- mean loss among negative-return trades
- total positive contribution
- total negative contribution
- net contribution

### C_BASE net return

Report the same fields.

This economic companion must include EVERY validation trade in its assigned
probability group, including failed opportunities and their losses.

Do not report only successful opportunities.

## 22. Economic ordering diagnostics

For every task/year report descriptively:

- Spearman correlation between predicted probability and C0 endpoint return
- Spearman correlation between predicted probability and DESIGN_BNB return
- P5 - P1:
    - opportunity-rate difference
    - mean C0 return difference
    - mean DESIGN_BNB return difference
    - mean C_BASE return difference

Also report P1...P5 values individually.

Strict monotonicity is NOT required for predictive classification.

No group becomes a trading rule.

## 23. Economic uncertainty

For P5-P1 economic differences use:

### Whole-trade bootstrap
- 2,000 fixed-seed PCG64 replicates

### UTC entry-month bootstrap
- 2,000 fixed-seed PCG64 replicates

Report 95% intervals for:

- opportunity-rate spread
- mean C0 return spread
- mean DESIGN_BNB return spread
- mean C_BASE return spread

No threshold optimization.

## 24. Symbol diagnostics

For each task/year/symbol report:

- count
- prevalence
- mean predicted probability
- Brier model
- Brier baseline
- DELTA_BRIER
- log-loss model
- log-loss baseline
- DELTA_LOGLOSS
- AUC where defined

Also report P5-P1 opportunity-rate spread where both groups contain symbol
observations.

Do not fit symbol-specific models.

Do not remove a symbol.

## 25. Feature coefficient reporting

For each fitted task/year model report standardized coefficients.

Purpose:

- interpretation
- sanity checking
- cross-task consistency

Do not rank/select features for a later model inside C30.

Do not remove features based on coefficients.

## 26. Eight tasks are correlated

C30 must explicitly state:

- tasks share entries;
- GROSS40/GROSS50 labels are nested at a given horizon;
- horizons share overlapping future paths;
- features and market regimes are shared.

Therefore:

    8/8 positive results do NOT represent eight independent replications.

Do not perform naive binomial significance calculations across the eight
tasks.

## 27. Frozen classification

Return exactly one overall classification:

### OPPORTUNITY_PREDICTION_SUPPORTED

Use only if ALL hold:

1. at least 6 of 8 tasks have:
       DELTA_BRIER > 0
   in both 2024 and 2025;

2. at least 6 of 8 tasks have:
       DELTA_LOGLOSS > 0
   in both 2024 and 2025;

3. no more than 1 task has materially negative Brier/log-loss improvement in
   untouched 2025;

4. dependence-aware uncertainty is directionally supportive for the majority
   of tasks and does not show broad evidence of model worsening;

5. predicted probability groups show positive P5-P1 opportunity-rate
   enrichment for at least 6 of 8 tasks in both years;

6. economic companion results do not reveal that high predicted-probability
   groups obtain enrichment solely by accepting dramatically worse downside;

7. evidence is not obviously dependent on one symbol.

This means:

    fixed-endpoint economic opportunities contain prospectively useful
    information at E1 time.

It does NOT authorize trading.

### WEAK_OPPORTUNITY_PREDICTION_SIGNAL

Use if:

- proper-score improvements are generally positive but inconsistent across
  years/tasks;
- OR enrichment exists but uncertainty is broad;
- OR ranking improves while calibration remains weak;
- OR economic companion results are mixed.

### NO_USEFUL_OPPORTUNITY_PREDICTION_SIGNAL

Use if:

- proper-score improvement is absent or mostly negative;
- OR untouched 2025 broadly fails;
- OR probability groups do not economically enrich opportunities;
- OR high-score groups merely exchange higher opportunity frequency for
  materially worse downside.

### INSUFFICIENT

Use only for material reconciliation/training/timing failures preventing valid
evaluation.

Do not alter these predicates after seeing results.

## 28. No strategy selection

C30 MUST NOT:

- choose GROSS40 versus GROSS50;
- choose H3/H6/H12/H24;
- define a probability cutoff;
- recommend P4/P5;
- optimize trade count;
- calculate a strategy using filtered entries;
- optimize P&L;
- claim profitability;
- authorize deployment.

Probability groups are diagnostic only.

## 29. No alternative model/feature search

Do NOT:

- test another classifier;
- tune logistic C;
- remove/add features based on results;
- add interactions;
- add polynomial terms;
- use feature-selection methods;
- use trees/boosting;
- calibrate probabilities;
- select models by task;
- search folds.

If the frozen specification performs poorly, report that result.

## 30. 2026 prohibition

No 2026 market data may be accessed for:

- features
- labels
- fitting
- evaluation
- controls
- diagnostics

C30 ends with 2025.

## 31. Required artifacts

Write to:

artifacts/c30_opportunity_prediction/

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- label_reconciliation.json
- feature_schema.json
- feature_timing_audit.json
- feature_matrix_summary.json
- chronology_definition.json
- fold_reconciliation.json
- training_prevalence_baselines.json
- model_specification.json
- task_metrics_2024.json
- task_metrics_2025.json
- calibration_results.json
- probability_group_boundaries.json
- probability_group_results.json
- economic_companion_c0.json
- economic_companion_design_bnb.json
- economic_companion_cbase.json
- economic_ordering.json
- whole_trade_bootstrap.json
- calendar_month_bootstrap.json
- economic_whole_trade_bootstrap.json
- economic_calendar_month_bootstrap.json
- symbol_diagnostics.json
- coefficients.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid unnecessary row-level dumps.

## 32. Required tests

Add focused tests for:

- exact 2,199 E1 reconciliation
- exact entry hash
- exact C29 H3/H6/H12/H24 labels
- exact +40/+50 bp endpoint-label boundaries
- endpoint label is not path/touch label
- no MFE use
- feature availability at E1 time
- completed-data-only features
- BTC context timing
- relative-BTC feature arithmetic
- cross-asset confirmation timing
- no future leakage
- task-specific label-resolution time
- training label fully resolved before validation start
- frozen 2024-07-01 validation start
- frozen 2025 training/evaluation boundary
- same feature schema all eight tasks
- same model spec all eight tasks
- fixed C=1 logistic regression
- training-only scaling
- training-prevalence baseline
- DELTA_BRIER sign convention
- DELTA_LOGLOSS sign convention
- training-only probability-group boundaries
- no split probability ties
- economic groups include failed opportunities
- C0/DESIGN_BNB/C_BASE accounting
- whole-trade bootstrap determinism
- calendar-month bootstrap determinism
- no model refit in bootstrap
- no horizon/hurdle selection
- no trading cutoff
- no 2026 access

Run focused tests.

Run full repository suite once if scientific/runtime code changes.

## 33. Governance

Do NOT:

- modify C7-C29 scientific behavior;
- modify STRATEGY_DESIGN_REVIEW.md;
- modify this contract;
- stage implementation/results;
- commit implementation/results;
- push;
- access 2026;
- start C31.

The C30 contract itself may be committed before implementation.

## 34. Final report

Report:

1. contract SHA
2. population reconciliation
3. label reconciliation
4. exact eight tasks
5. exact endpoint-label semantics
6. feature schema
7. feature timing audit
8. chronology/fold definitions
9. training/validation counts per task
10. training prevalence per task
11. validation prevalence per task
12. 2024 Brier baseline/model/delta
13. 2024 log-loss baseline/model/delta
14. 2024 AUC/PR-AUC
15. 2025 Brier baseline/model/delta
16. 2025 log-loss baseline/model/delta
17. 2025 AUC/PR-AUC
18. calibration results
19. whole-trade uncertainty
20. calendar-month uncertainty
21. probability-group boundaries
22. P1-P5 opportunity rates
23. P1-P5 C0 return distributions
24. P1-P5 DESIGN_BNB return distributions
25. P1-P5 C_BASE return distributions
26. failed-opportunity loss magnitude by group
27. P5-P1 economic spreads
28. economic uncertainty
29. symbol stability
30. coefficient summary
31. explicit statement that eight tasks are correlated
32. frozen overall classification:
       OPPORTUNITY_PREDICTION_SUPPORTED
       WEAK_OPPORTUNITY_PREDICTION_SIGNAL
       NO_USEFUL_OPPORTUNITY_PREDICTION_SIGNAL
       INSUFFICIENT
33. whether later policy research is scientifically justified
34. explicit confirmation no horizon/hurdle/cutoff selected
35. explicit confirmation no profitability/deployment claim
36. limitations
37. artifact hash verification
38. focused tests
39. full-suite result
40. git diff --check
41. git status --short
42. confirmation no model/feature/regularization search
43. confirmation no P&L optimization
44. confirmation no 2026 access
45. confirmation nothing implementation-related staged/committed/pushed
46. confirmation C31 not started

STOP after C30.
