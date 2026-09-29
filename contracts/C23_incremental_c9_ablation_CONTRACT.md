# C23 Incremental C9 Ablation Contract

Status: prospectively specified before C23 analysis.

## 1. Purpose

C21 showed that frozen C9 probability has positive between-trade covariance
with executable forward liquidation value, while within-trade covariance is
negative.

C22 showed that a richer causal state model improved proper binary scores over
current p_t2 alone, but generally did not improve AUC and showed mixed
continuous-value gains.

C23 asks one bounded question:

"Does current frozen C9 p_t2 add incremental predictive information beyond
the simplest causal decision state consisting only of elapsed time and
observable current return from entry?"

C23 compares exactly two candidate specifications:

S:
- elapsed_minutes_since_entry
- observable_current_return_from_entry

S+C9:
- elapsed_minutes_since_entry
- observable_current_return_from_entry
- current frozen p_t2

No other predictors are allowed.

C23 is an ablation/incremental-information study.

It is NOT:
- a policy experiment;
- a new architecture search;
- a model-family search;
- a horizon-selection exercise;
- a threshold search.

## 2. Frozen dependencies

Reuse without scientific modification:

- frozen C9 honest probabilities
- C20 executable liquidation targets
- C20 whole-trade weighting
- C22 decision timestamp semantics
- C22 observable-price definition
- C22 chronological evaluation structure

Targets:

- DELTA_LIQ_5
- DELTA_LIQ_15
- DELTA_LIQ_30
- DELTA_LIQ_60
- DELTA_LIQ_EVENT

No 2026 access.

## 3. Population

Use the exact C22 honestly scored target population.

Expected:

- 56,217 target-eligible honestly scored snapshots
- 1,610 honestly scored trades

Reconcile exactly before fitting.

No probabilities may be inferred for unscored states.

## 4. Decision-time causality

Prediction timestamp is after completion of the frozen 5-minute state bar at t.

All predictors must be observable at or before t.

Observable current price is exactly the C22 definition:

    OBS_PRICE(t)
      = frozen architecture-B fast.close[fast.at(t)]

This is the close of the completed 5-minute state bar ending at t.

Define:

    OBS_RETURN_FROM_ENTRY(t)
      = OBS_PRICE(t) / entry_price - 1

The next 1-minute open remains target/accounting-only information and MUST NOT
be used as a predictor.

## 5. Candidate feature sets

### S

Exactly:

- elapsed_minutes_since_entry
- observable_current_return_from_entry

### S+C9

Exactly:

- elapsed_minutes_since_entry
- observable_current_return_from_entry
- p_t2

where p_t2 is the frozen honest C9 probability available at t.

The only scientific difference between S and S+C9 is inclusion of p_t2.

## 6. Prohibited predictors

Do NOT use:

- first_honest_p_t2
- delta_p_from_first
- lagged p_t2 changes
- probability trajectory features
- next-open execution price
- EXIT_NOW_NET
- forward/event prices
- target values as predictors
- eventual T2/P0 outcome
- terminal proximity
- future MFE/MAE
- full-trajectory means
- future probabilities
- symbol-specific features not already implicit in frozen target construction

Do not add interactions or nonlinear transforms.

## 7. Exact target definitions

Continuous targets remain exactly C20:

    Y_H = DELTA_LIQ_H

for all five targets.

Before any model fitting, inspect the existing C22 implementation and record
the exact binary-label rule actually used in C22.

Specifically record treatment of:

    DELTA_LIQ_H > 0
    DELTA_LIQ_H < 0
    DELTA_LIQ_H == 0

Do NOT silently redefine the label.

C23 must reproduce the C22 binary convention exactly.

Write this to:

    binary_label_definition.json

If the C22 rule cannot be established unambiguously, STOP with
INSUFFICIENT_LABEL_DEFINITION before model fitting.

## 8. Models

Use fixed model families only.

Binary:

- S: fixed L2 logistic regression
- S+C9: fixed L2 logistic regression

with:

    C = 1.0

Continuous:

- S: fixed ridge regression
- S+C9: fixed ridge regression

with:

    alpha = 1.0

No hyperparameter search.

No alternative models.

## 9. Preprocessing

Use exactly the C22 preprocessing convention:

- training-only weighted median imputation;
- training-only weighted mean/sd standardization;
- apply frozen training preprocessing to validation data;
- equal total weight per trade.

The same preprocessing procedure must be applied to S and S+C9.

No information from validation/test data may enter preprocessing.

## 10. Chronological evaluation

Use exactly the honest C22 chronology.

### 2024 chronological validation

Reuse the only honestly available C22 fold:

fold_B:

- training strictly precedes validation;
- same train/validation date boundaries as C22;
- expected training population:
  - 7,970 rows
  - 256 trades
- expected validation population:
  - 8,631 rows
  - 267 trades

Do not fabricate fold_A.

State explicitly that 2024 is a single available chronological validation
block, not comprehensive multi-fold OOF coverage.

### 2025 untouched validation

Fit each frozen specification using the same full-2024 training procedure used
by C22.

Evaluate once on untouched 2025.

No revision after inspecting 2025 results.

## 11. Whole-trade weighting

Each eligible trade receives equal total weight.

If trade i has n_i scored snapshots:

    w_it = 1 / n_i

Normalize only as required by metric implementation.

Use identical weights for S and S+C9.

## 12. Primary binary metrics

For S and S+C9, for every target and year report:

- Brier score
- log loss
- AUC
- calibration intercept
- calibration slope
- ECE

Primary incremental comparisons:

    Delta_Brier
      = Brier(S) - Brier(S+C9)

    Delta_LogLoss
      = LogLoss(S) - LogLoss(S+C9)

Positive values mean adding C9 improves the proper score.

Secondary:

    Delta_AUC
      = AUC(S+C9) - AUC(S)

AUC is interpretive and is NOT required to improve for probability refinement
to be considered real.

## 13. Continuous companion analysis

For S and S+C9 report:

- MAE
- RMSE
- predicted-vs-realized correlation
- sign accuracy

Primary continuous differences:

    Delta_MAE
      = MAE(S) - MAE(S+C9)

    Delta_RMSE
      = RMSE(S) - RMSE(S+C9)

Positive values mean adding C9 improves error.

Correlation/sign accuracy are descriptive.

Do not require binary and continuous results to agree.

## 14. Paired dependence-aware uncertainty

This is required.

Use the already-generated honest out-of-time predictions from each frozen
candidate.

Do NOT tune or select models inside bootstrap replicates.

### Primary uncertainty

Paired calendar-month block bootstrap.

Requirements:

- resample calendar-month blocks;
- retain all symbols and all observations/trades belonging to sampled months;
- preserve pairing between S and S+C9;
- calculate paired score differences on the same replicate;
- fixed seed;
- fixed replication count prospectively in implementation metadata;
- percentile 95% intervals unless a pre-existing project convention requires
  another fixed method.

At minimum compute 95% intervals for:

- Delta_Brier
- Delta_LogLoss
- Delta_MAE
- Delta_RMSE

### Robustness uncertainty

Also perform paired whole-trade bootstrap:

- resample trades;
- include all snapshots from each sampled trade;
- preserve paired S versus S+C9 predictions;
- same metrics and 95% intervals.

Do NOT independently resample snapshots.

## 15. Interpretation of uncertainty

Uncertainty is about the frozen out-of-time score difference.

It does not prove:
- causality;
- policy profitability;
- economic action advantage.

Report point estimate and both uncertainty schemes side-by-side.

## 16. Symbol stability

For each symbol:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

report S versus S+C9 for:

- Brier
- log loss
- AUC
- RMSE
- MAE

No symbol-specific models.

No exclusions.

Do not treat five symbols as independent statistical replications.

## 17. Calibration interpretation

For both candidates report calibration intercept, slope, and ECE.

Explicitly distinguish:

- improved proper scoring through probability refinement/calibration;
- improved ranking/discrimination;
- improved continuous economic-value prediction.

Do not conflate them.

## 18. Frozen classification

Classify each target independently.

### INCREMENTAL_C9_SIGNAL_SUPPORTED

Require:

1. Delta_Brier > 0 in both 2024 and 2025;
2. Delta_LogLoss > 0 in both 2024 and 2025;
3. paired dependence-aware uncertainty is directionally supportive:
   - neither calendar-month nor whole-trade intervals show clear evidence that
     S+C9 is worse on both proper scores;
4. result is not obviously driven by one symbol.

AUC improvement is NOT required.

### WEAK_INCREMENTAL_C9_SIGNAL

Use if:

- proper-score point estimates are consistently favorable across years but
  intervals materially include zero;
- OR binary evidence is favorable while continuous-value evidence is mixed;
- OR symbol stability is incomplete.

### NO_USEFUL_INCREMENTAL_C9_SIGNAL

Use if:

- proper-score gains are absent or unstable;
- OR S+C9 is materially worse;
- OR apparent gains fail chronological/year robustness.

### INSUFFICIENT

Use if:

- population;
- label rule;
- timing;
- or frozen C9 alignment

cannot be reproduced exactly.

Do not change these predicates after seeing results.

## 19. No best-horizon selection

Evaluate all five targets.

Do NOT:

- rank horizons for strategy use;
- choose the strongest target;
- recommend a trading horizon;
- carry one target forward because it has the largest observed gain.

Each horizon is a separate characterization.

## 20. Scientific interpretation

Possible conclusions:

A. S+C9 consistently improves proper and continuous metrics

    Current C9 contains incremental predictive information beyond causal
    time/price progress.

B. S+C9 improves proper scores but not continuous value prediction

    C9 adds probability/sign refinement beyond S, but evidence for incremental
    economic-magnitude prediction remains weak.

C. S+C9 is approximately equivalent to S

    Simple causal time/price progress accounts for most usable information;
    C9 should not be retained solely because of C21 pooled/between-trade
    association.

D. S+C9 is worse than S

    Current C9 is not useful once simple causal state is known.

Even outcome A does NOT authorize an exit policy.

## 21. Artifacts

Write to:

artifacts/c23_incremental_c9_ablation/

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- binary_label_definition.json
- decision_timing_audit.json
- feature_schema.json
- leakage_firewall.json
- fold_reconciliation.json
- binary_metrics_2024.json
- continuous_metrics_2024.json
- calibration_2024.json
- paired_differences_2024.json
- binary_metrics_2025.json
- continuous_metrics_2025.json
- calibration_2025.json
- paired_differences_2025.json
- calendar_month_bootstrap.json
- whole_trade_bootstrap.json
- symbol_metrics.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid large redundant prediction dumps unless required for reproducibility.

## 22. Tests

Add focused tests for:

- exact C22 population reconciliation
- exact binary zero-boundary reproduction
- S feature set
- S+C9 feature set
- sole-feature difference is p_t2
- observable price timing
- next-open price prohibited
- frozen C9 alignment
- whole-trade weighting
- fold_B chronological boundaries
- no fabricated fold_A
- full-2024-to-2025 fitting
- training-only preprocessing
- paired calendar-month bootstrap
- paired whole-trade bootstrap
- deterministic bootstrap seed/results
- no future variables
- no 2026 access

Run focused tests.

Run full repository suite once if runtime/scientific code changes.

## 23. Governance

Do NOT:

- modify C7-C22 scientific behavior;
- add predictors beyond S and S+C9;
- use M3 trajectory/context features;
- search model families;
- search regularization;
- search thresholds;
- select horizons;
- define/evaluate an exit policy;
- optimize P&L;
- access 2026;
- begin C24;
- stage, commit, or push.

## 24. Final report

Report:

1. contract SHA
2. population reconciliation
3. exact binary label rule including zero handling
4. decision-timing verification
5. exact S schema
6. exact S+C9 schema
7. confirmation sole difference is current p_t2
8. 2024 fold reconciliation
9. 2024 absolute binary metrics
10. 2024 S+C9-minus-S proper-score differences
11. 2024 continuous metrics
12. 2024 continuous differences
13. 2024 calibration comparison
14. 2025 training/evaluation chronology
15. 2025 absolute binary metrics
16. 2025 proper-score differences
17. 2025 continuous metrics
18. 2025 continuous differences
19. 2025 calibration comparison
20. calendar-month paired uncertainty
21. whole-trade paired uncertainty
22. symbol stability
23. frozen classification for every target
24. whether C9 adds information beyond causal time/price state
25. distinction between probability refinement, ranking, and value prediction
26. limitations
27. implication for C24
28. artifact hashes
29. focused/full test results
30. git diff --check
31. git status --short
32. confirmation no new model family/horizon/threshold search
33. confirmation no policy/P&L optimization
34. confirmation no 2026 access
35. confirmation nothing staged/committed/pushed

STOP after C23.
