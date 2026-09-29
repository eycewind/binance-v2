# C22 Causal Decision-State Prediction Contract

Status: prospectively specified before C22 analysis.

## 1. Purpose

C20 established executable forward liquidation targets.

C21 established that pooled positive probability-value covariance is
between-trade dominant, while within-trade covariance is negative.

C21 also showed that retrospective adjustment using elapsed time and current
execution-price progress substantially attenuates the within-trade
association.

However:

- next-open executable price is not available at the decision timestamp;
- therefore it is retrospective accounting information, not a legal live
  predictor;
- for the first-event target, strong attenuation after price adjustment is
  partly expected algebraically from the target equation.

C22 therefore asks:

"Can a strictly causal decision-state representation, available at the
completed snapshot timestamp, improve prediction of executable forward
liquidation value beyond current frozen C9 probability alone?"

C22 is a predictive characterization study.

It is NOT an exit-policy experiment.

## 2. Frozen dependencies

Reuse without scientific modification:

- C9 frozen probabilities
- C18 honest scored pre-T2 population
- C20 executable forward liquidation targets
- C21 between/within decomposition findings

Frozen targets:

- DELTA_LIQ_5
- DELTA_LIQ_15
- DELTA_LIQ_30
- DELTA_LIQ_60
- DELTA_LIQ_EVENT

No modification of C7-C21 scientific behavior.

No 2026 data or metadata access.

## 3. Decision timestamp

For each causal state completed at time t:

- all predictive features must be observable no later than t;
- decision is formed after completion of state t;
- actual liquidation, if later evaluated by a policy, would occur at the next
  valid 1-minute open after t.

Therefore:

NEXT-OPEN EXECUTION PRICE IS NOT A LIVE FEATURE.

It may appear only on the target/accounting side.

## 4. Observable current price

Define the causal current price used for live-state features as:

    OBS_PRICE(t)

where OBS_PRICE is the latest completed-bar/reference price already available
to the frozen causal state at timestamp t.

Use the exact price convention already present in frozen C9/C10 causal state
construction.

Do not introduce a later price.

Define:

    OBS_RETURN_FROM_ENTRY(t)
      = OBS_PRICE(t) / entry_price - 1

This is a legal causal feature.

Record the exact source field and timestamp semantics in an artifact.

## 5. Target-geometry audit

Before fitting any model, derive and document for each frozen C20 target:

    DELTA_LIQ_H(t)
      = FORWARD_NET_H(t) - EXIT_NOW_NET(t)

and:

    DELTA_LIQ_EVENT(t)
      = EVENT_NET(t) - EXIT_NOW_NET(t)

Identify algebraically which parts of target variation are mechanically driven
by:

- current executable liquidation price;
- fixed or event endpoint price;
- trade-specific quantity/cost scaling.

For the event target explicitly document the form:

    V_it = A_i - B_i P_exec,it

where applicable.

State clearly:

- target geometry can induce within-trade relationships;
- removing price-related variation retrospectively does not demonstrate a
  predictive mechanism;
- model evaluation must determine incremental predictive value.

No target may be changed.

## 6. Population

Use the exact honest frozen-C9 scored pre-T2 population from C20/C21.

Expected:

- 56,217 scored snapshots
- 1,610 trades

Reconcile exactly.

Do not infer probabilities for unscored states.

## 7. Frozen causal feature sets

### M0
Target-specific training mean / base-rate benchmark.

### M1: current frozen C9 state

Use:

- current frozen calibrated p_t2 only

For binary target interpretation:
predict DELTA_LIQ_H > 0.

For continuous target:
predict DELTA_LIQ_H.

### M2: causal progress state

M1 plus:

- elapsed_minutes_since_entry
- observable_current_return_from_entry

Both must be available at decision timestamp t.

### M3: causal trade-context + trajectory state

M2 plus:

- first_honest_p_t2
- delta_p_from_first
    = current_p_t2 - first_honest_p_t2

and fixed past-only probability changes:

- delta_p_5m
- delta_p_15m
- delta_p_30m

where each lag uses the latest honest probability available at or before the
required lag timestamp.

If lag history is unavailable:
- use explicit missing indicators;
- use deterministic training-only imputation.

No future probabilities.

No full-trade averages.

No eventual outcome labels.

## 8. Explicitly prohibited predictors

Do NOT use as features:

- next-open executable price
- EXIT_NOW_NET
- forward liquidation price
- future endpoint price
- DELTA_LIQ target values
- eventual T2/P0 outcome
- future terminal proximity
- future MFE/MAE
- full-trajectory p_t2 mean
- full-trajectory value mean
- future recovery/path information

Full-trajectory trade means remain diagnostic only.

## 9. Models

Use fixed, simple models only.

Binary target:
    Y_H = 1 if DELTA_LIQ_H > 0 else 0
    excluding exact-zero states from binary scoring if required by frozen
    implementation convention.

Models:
- M0 binary prevalence
- M1 fixed logistic
- M2 fixed logistic
- M3 fixed logistic

Continuous target:
- M0 training weighted mean
- M1 fixed ridge-style linear model
- M2 fixed ridge-style linear model
- M3 fixed ridge-style linear model

Use one fixed regularization setting inherited from prior project conventions
or frozen before evaluation.

No grid search.

No model-family search.

## 10. Development and validation

Use:

2024:
    chronological whole-trade out-of-fold development/evaluation

2025:
    untouched final validation

Requirements:

- whole trades remain intact;
- training strictly precedes validation;
- preprocessing fit only on training data;
- each trade receives equal total weight;
- no model revision after 2025 evaluation.

2026 remains sealed.

## 11. Primary comparison

Primary scientific question:

Does M3 improve over M1?

Secondary:

- M2 versus M1
- M3 versus M2

Do not choose a best model post hoc.

Report all fixed comparisons.

## 12. Binary metrics

For each target and M0/M1/M2/M3 report:

- Brier score
- log loss
- AUC
- calibration intercept
- calibration slope
- ECE

## 13. Continuous metrics

For each target and M0/M1/M2/M3 report:

- MAE
- RMSE
- correlation predicted vs realized DELTA_LIQ
- sign accuracy

Sign accuracy is descriptive only and does not establish strategy value.

## 14. Frozen evidence criteria

For each target classify predictive-state evidence.

CAUSAL_STATE_SIGNAL_SUPPORTED if:

- M3 improves over M1 on BOTH Brier and log loss in 2024;
- M3 improves over M1 on BOTH Brier and log loss in untouched 2025;
- M3 AUC > M1 AUC in both years;
- continuous M3 improves RMSE or MAE directionally in both years;
- M3 predicted-vs-realized continuous correlation is positive in both years;
- result is not dependent on one symbol only.

WEAK_CAUSAL_STATE_SIGNAL if:

- M3 improves at least one proper binary score in both years,
  OR
- continuous prediction improves directionally in both years,
but full support criteria fail.

NO_USEFUL_CAUSAL_STATE_SIGNAL if:
- improvements are unstable or absent.

INSUFFICIENT if:
- causal feature timing, target alignment, or validation cannot be established.

Do not redefine criteria after results.

## 15. No horizon selection

Run the exact same fixed comparison for:

- 5m
- 15m
- 30m
- 60m
- event

Do not rank horizons for strategy use.

Do not select a preferred horizon.

## 16. Feature contribution interpretation

Report standardized coefficients grouped into:

- current probability
- elapsed/current observable price progress
- initial trade context
- probability trajectory

Interpret only as predictive associations.

No causal claims.

## 17. Year stability

Report all primary results separately for:

- 2024
- 2025

No revision after seeing 2025.

## 18. Symbol robustness

Report M1/M2/M3 primary metrics separately for:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

No symbol-specific models.

No exclusions.

## 19. Trade-context diagnostic

For diagnostic interpretation only, report relationships between:

- first_honest_p_t2
- average realized forward value per trade

Full-trade average realized value is diagnostic only.

It must not become a live feature.

## 20. Trajectory diagnostic

Report descriptive associations of:

- delta_p_from_first
- delta_p_5m
- delta_p_15m
- delta_p_30m

with each forward target.

These are legal causal candidate features, but this section is descriptive.

Do not use diagnostic findings to alter the frozen feature set.

## 21. Implication

If CAUSAL_STATE_SIGNAL_SUPPORTED for one or more targets:

a later checkpoint may define a prospectively frozen sequential decision
policy using only supported causal state variables.

If WEAK_CAUSAL_STATE_SIGNAL:

do not define a policy yet; identify which component is stable.

If NO_USEFUL_CAUSAL_STATE_SIGNAL:

C21's decomposition is explanatory but does not translate into deployable
predictive structure; do not proceed directly to a C9-based policy.

Do not start C23.

## 22. Artifacts

Write to:

artifacts/c22_causal_decision_state/

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- target_geometry_audit.json
- decision_timing_audit.json
- observable_price_definition.json
- feature_schema.json
- leakage_firewall.json
- fold_definitions.json
- model_metrics_binary_2024.json
- model_metrics_continuous_2024.json
- calibration_2024.json
- model_metrics_binary_2025.json
- model_metrics_continuous_2025.json
- calibration_2025.json
- symbol_metrics.json
- feature_associations.json
- trade_context_diagnostic.json
- trajectory_diagnostic.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid redundant raw dumps.

## 23. Tests

Add focused tests for:

- decision timestamp semantics
- observable price available at t
- next-open price prohibited as feature
- first honest p_t2 construction
- causal lagged probability deltas
- missing lag handling
- no future probability access
- no full-trade mean feature
- target geometry audit
- chronological folds
- whole-trade weighting
- training-only preprocessing
- deterministic model fitting
- no 2026 access

Run focused tests.

Run full repository suite once.

## 24. Governance

Do not:

- modify C7-C21 scientific behavior
- use next-open execution price as a predictor
- use future information as predictors
- train models outside M0-M3
- search model families
- search regularization
- search horizons
- define/evaluate an exit policy
- optimize P&L
- access 2026
- begin C23
- stage, commit, or push

## 25. Final report

Report:

1. contract SHA
2. population reconciliation
3. target-geometry audit
4. decision-timing audit
5. exact observable-price definition
6. exact M0/M1/M2/M3 feature schemas
7. leakage-firewall result
8. 2024 binary metrics for all targets/models
9. 2024 continuous metrics
10. M2-vs-M1 and M3-vs-M1 comparisons
11. 2025 binary metrics
12. 2025 continuous metrics
13. 2025 comparisons
14. symbol robustness
15. feature-family associations
16. trade-context diagnostic
17. probability-trajectory diagnostic
18. frozen evidence classification by target
19. whether causal trade-context/progress separation adds predictive value
20. limitations
21. implication for C23
22. artifact hashes
23. focused/full tests
24. git diff --check
25. git status --short
26. confirmation next-open price was never a predictor
27. confirmation full-trajectory means were diagnostic only
28. confirmation no policy/P&L optimization
29. confirmation no horizon/model search
30. confirmation no 2026 access
31. confirmation nothing staged/committed/pushed

STOP after C22.
