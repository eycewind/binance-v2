# C31 V4 Transition Representation Prediction Contract

Status: prospective and frozen before outcome access for C31.

C31 is the first predictive test of the completed V4 catch-up transition
representation.

It answers a representation question, not a strategy-selection question.

---

## 1. Scientific question

Primary question:

> Does the prospectively developed V4 transition representation contain
> reproducible information about fixed-endpoint economic opportunity that is
> not captured by the previously frozen C30 representation?

Secondary question:

> Does V4 improve proper probabilistic prediction relative to a simple
> training-prevalence baseline?

C31 does NOT ask:

- which horizon should be traded;
- which probability threshold should be used;
- whether a trade should be entered or exited;
- whether a nonlinear model can improve results;
- which V4 feature should be selected;
- how to optimize P&L.

---

## 2. Scientific motivation

C30 tested a 34-feature E1-time representation dominated by overlapping:

- local returns;
- BTC returns;
- realized volatility;
- SMA geometry;
- relative returns;
- breadth;
- mean cross-asset returns.

C30 produced:

    WEAK_OPPORTUNITY_PREDICTION_SIGNAL

with weak discrimination and generally over-dispersed probabilities.

Subsequent outcome-free representation work produced V1-V4.

V4 passed its frozen causal representation audit with:

- exact population reconciliation;
- 100% primary availability;
- causal future-mutation invariance;
- fill independence;
- no unexpected exact structural duplicates;
- stable year/symbol representation distributions.

C31 now tests whether that representation work improved prediction.

---

## 3. Frozen population

Use the exact frozen E1 population:

    2,199 entries

Entry rule:

    E1_H1_SMA24_CROSS_V1

Entry hash:

    6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3

Expected:

    2024 = 1,093
    2025 = 1,106

Symbols:

    BNBUSDT = 442
    BTCUSDT = 451
    ETHUSDT = 434
    SOLUSDT = 431
    XRPUSDT = 441

Exact reconciliation is mandatory.

---

## 4. Sealed future boundary

No 2026 market data or metadata may be accessed.

Do not:

- enumerate;
- inspect;
- hash;
- count;
- validate;
- open;
- use

any 2026 market input.

C31 remains entirely within the existing 2024-2025 research population.

---

## 5. Frozen outcome definitions

Use exactly the C29/C30 fixed-endpoint opportunity labels.

Tasks:

    H3_GROSS40
    H3_GROSS50

    H6_GROSS40
    H6_GROSS50

    H12_GROSS40
    H12_GROSS50

    H24_GROSS40
    H24_GROSS50

For each horizon H:

    GROSS40 = 1 iff fixed-endpoint executable gross return >= 40 bp

    GROSS50 = 1 iff fixed-endpoint executable gross return >= 50 bp

Use the exact C29/C30 endpoint timing and executable-price semantics.

Do NOT substitute:

- touch return;
- MFE;
- maximum return;
- P0;
- T2;
- path-dependent return.

Reconcile C31 labels exactly against C29/C30 before fitting.

---

## 6. Horizon coverage

Use exactly the same valid endpoint population as C30 for each task.

Expected C29 coverage:

    H3  = 2,199
    H6  = 2,198
    H12 = 2,197
    H24 = 2,196

No new endpoint fallback.

No dynamic horizon substitution.

---

## 7. Frozen V4 predictive representation

Use exactly the V4 nine-variable representation in this exact order:

1. NEW_JOINER_FRACTION
2. BASKET_ACCELERATION
3. PRIOR_RELATIVE_DEFICIT
4. RELATIVE_IMPROVEMENT
5. DISPERSION_CHANGE
6. MARKET_EXPANSION_STATE_AT_E1
7. MARKET_EXPANSION_CURRENT_RUN_LENGTH
8. CATCHUP_STATE_AT_E1
9. CATCHUP_CURRENT_RUN_LENGTH

Authoritative V4 specification:

    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V4.md

Frozen V4 spec SHA-256:

    f37833e46148b06f1a50fb7deefb59e4bca33b3fc4933f9e008982806164802a

The V4 audit must be reproduced or hash-verified before C31 fitting.

---

## 8. Expected state/run structural dependence

The two state/run pairs are intentionally retained:

    MARKET_EXPANSION_STATE_AT_E1
    MARKET_EXPANSION_CURRENT_RUN_LENGTH

and:

    CATCHUP_STATE_AT_E1
    CATCHUP_CURRENT_RUN_LENGTH

Although:

    STATE == 1 iff RUN_LENGTH > 0

the two terms have distinct model roles:

    binary state
        permits a level shift between absent/present state

    run length
        permits an additional linear persistence effect once state exists

This is a prospectively accepted hurdle-like linear parameterization.

Do NOT remove either term during C31.

Do NOT rerun C31 with a reduced representation after seeing results.

---

## 9. No additional features

Do NOT add:

- symbol one-hot encoding;
- BTC-specific variables;
- C30 features;
- interactions;
- polynomial terms;
- nonlinear transforms;
- alternative run-length encodings;
- missing indicators;
- volume;
- future information.

C31 V4 means exactly the nine frozen columns.

---

## 10. Comparator 1: training-prevalence baseline

For every task/fold, define:

    B0

as the positive-label prevalence in the training population.

Every validation row receives the same probability:

    p = training prevalence

This is the same conceptual baseline used by C30.

---

## 11. Comparator 2: locked C30 representation

C30 is the primary scientific comparator.

Use the exact frozen C30 34-feature representation, model specification,
chronology, labels, and folds.

Do NOT:

- alter C30 features;
- remove C30 duplicates;
- recalibrate C30;
- retrain with V4 information;
- retune C30;
- change C30 regularization.

Preferred implementation:

    reproduce exact locked C30 predictions deterministically from the frozen
    C30 implementation/specification.

If exact C30 prediction artifacts already exist and have reproducible hashes,
they may be used after verification.

C31 must verify reproduced C30 metrics against the accepted C30 results.

Material mismatch => STOP.

---

## 12. C30 accepted reference metrics

The reproduced C30 metrics should match the accepted C30 results within
machine/reproducibility tolerance.

Accepted proper-score deltas vs training-prevalence baseline:

H3_GROSS40:
    2024:
        delta_brier = -0.01274
        delta_logloss = -0.02978
    2025:
        delta_brier = +0.00204
        delta_logloss = +0.00286

H3_GROSS50:
    2024:
        -0.01197
        -0.03061
    2025:
        +0.00353
        +0.00658

H6_GROSS40:
    2024:
        -0.01034
        -0.02588
    2025:
        -0.00493
        -0.01162

H6_GROSS50:
    2024:
        -0.00890
        -0.02417
    2025:
        -0.00431
        -0.01115

H12_GROSS40:
    2024:
        -0.01243
        -0.02578
    2025:
        -0.00083
        -0.00198

H12_GROSS50:
    2024:
        -0.01438
        -0.02997
    2025:
        -0.00027
        -0.00063

H24_GROSS40:
    2024:
        -0.00917
        -0.01946
    2025:
        -0.00401
        -0.00831

H24_GROSS50:
    2024:
        -0.01046
        -0.02322
    2025:
        -0.00375
        -0.00776

These rounded values are reconciliation references only.

Use full-precision reproduced values for C31 comparisons.

---

## 13. Frozen chronological evaluation

Use the exact C30 chronological fold semantics.

### 2024 evaluation

Validation begins:

    2024-07-01 UTC

Training uses only earlier entries whose fixed-endpoint labels are fully
resolved before the validation boundary according to C30 timing rules.

No validation outcome may enter training.

The accepted C30 implementation is authoritative for exact eligibility.

### 2025 evaluation

Fit on eligible 2024 entries only.

Evaluate on 2025 entries.

Do not refit during 2025.

Do not call 2025 a pristine external holdout.

It is:

    locked C31 2025 evaluation

because 2025 has been used extensively in prior research.

---

## 14. Same rows for comparator evaluation

For a given task/year:

    B0
    C30
    V4

must be evaluated on exactly the same validation rows.

Any row-set mismatch must be reported and resolved before comparison.

No model-specific dropping is allowed because V4 has 100% representation
coverage on the frozen E1 population.

---

## 15. Frozen model

V4 uses exactly:

    sklearn.linear_model.LogisticRegression

Parameters:

    penalty = "l2"
    C = 1.0
    solver = "lbfgs"
    max_iter = 10000
    tol = 1e-6
    class_weight = None

No hyperparameter search.

No class weighting.

No alternate solver unless execution literally fails; if it fails, STOP
rather than change model.

---

## 16. Scaling

Use:

    sklearn.preprocessing.StandardScaler

Fit scaler on training rows only.

Apply frozen training mean/scale to validation.

No full-sample scaling.

For binary state features, apply the same StandardScaler as all other inputs.

Do not special-case them.

---

## 17. Model naming

Use:

    M_V4

for the nine-feature V4 logistic model.

Comparators:

    B0
    M_C30_LOCKED

No additional model ladder.

No nonlinear comparator.

---

## 18. Convergence audit

For every one of the 16 V4 fits:

    8 tasks x 2 evaluation years

record:

- n_iter_;
- convergence status;
- warnings;
- coefficient norm;
- intercept;
- scaler mean;
- scaler scale.

If max_iter is reached:

    mark fit non-converged.

Do NOT increase max_iter after seeing that result.

Report it as a scientific limitation.

---

## 19. Primary proper scores

For every task/year/model compute:

    Brier score
    log loss

Primary V4-vs-C30 differences:

    DELTA_BRIER_V4_C30
        = Brier(C30) - Brier(V4)

    DELTA_LOGLOSS_V4_C30
        = LogLoss(C30) - LogLoss(V4)

Positive values mean V4 is better.

Secondary V4-vs-baseline:

    DELTA_BRIER_V4_B0
        = Brier(B0) - Brier(V4)

    DELTA_LOGLOSS_V4_B0
        = LogLoss(B0) - LogLoss(V4)

Positive values mean V4 beats prevalence baseline.

---

## 20. Discrimination diagnostics

For each task/year/model report:

    ROC AUC
    PR AUC

These are secondary diagnostics.

Do not classify C31 solely from AUC.

Proper probability scores remain primary.

---

## 21. Calibration diagnostics

For V4 and locked C30 report:

- calibration intercept;
- calibration slope;
- 10-bin expected calibration error;
- predicted-probability min;
- p01;
- p05;
- p10;
- p25;
- median;
- p75;
- p90;
- p95;
- p99;
- max.

Do NOT recalibrate.

Calibration diagnostics are explanatory only.

---

## 22. Training and validation reconciliation

For every task/year report:

- training rows;
- training trades;
- validation rows;
- validation trades;
- positive counts;
- negative counts;
- prevalence;
- excluded rows and exact reason.

Reconcile exactly to C30 fold semantics.

---

## 23. Coefficient diagnostics

Record standardized V4 coefficients for every task/year.

This is descriptive.

Do NOT:

- select features from coefficient magnitude;
- remove sign-unstable features;
- refit reduced models.

Also report sign agreement between 2024 and 2025 fits for each V4 feature.

Interpret cautiously because state/run pairs are structurally dependent.

---

## 24. Joint representation-level comparison

The main C31 representation comparison aggregates all eight correlated tasks
without pretending they are independent.

For each evaluation year compute:

    mean DELTA_BRIER_V4_C30 across eight tasks

    mean DELTA_LOGLOSS_V4_C30 across eight tasks

and likewise V4 versus B0.

These are equal-weight task summaries.

Do not weight tasks by whichever performs best.

---

## 25. Task-level sign summary

For each year report count of tasks where V4:

    improves both Brier and log loss vs C30;
    improves one but not the other;
    worsens both.

Also report tasks where V4 improves both proper scores versus B0.

---

## 26. Dependence-aware uncertainty

Use paired bootstrap on frozen predictions.

Bootstrap unit:

    trade

and separately:

    UTC entry month

Iterations:

    2,000

RNG:

    numpy PCG64

Use one prospectively fixed seed.

Preserve the eight tasks jointly within each replicate.

For each year estimate 95% intervals for:

    mean DELTA_BRIER_V4_C30 across tasks
    mean DELTA_LOGLOSS_V4_C30 across tasks

and:

    mean DELTA_BRIER_V4_B0
    mean DELTA_LOGLOSS_V4_B0

Also report task-level paired intervals as diagnostics.

No resampling-based tuning.

---

## 27. Probability ordering diagnostic

For each task/year:

Use TRAINING predictions to define probability quintile boundaries for V4.

Apply those frozen boundaries to validation probabilities.

Report validation:

- row count;
- positive-label rate;
- mean predicted probability

for Q1-Q5.

This is calibration/ordering diagnosis only.

Do NOT compute future-return means or P&L by quintile.

Do NOT derive thresholds.

---

## 28. Symbol breadth diagnostic

For each task/year/symbol report:

- validation count;
- Brier V4;
- Brier C30;
- delta;
- log loss V4;
- log loss C30;
- delta;
- AUC where both classes exist.

Do not fit symbol-specific models.

---

## 29. Frozen overall classification

Return exactly one:

### V4_REPRESENTATION_IMPROVEMENT_SUPPORTED

Only if ALL hold:

1. V4 joint mean DELTA_BRIER_V4_C30 > 0 in both 2024 and 2025;
2. V4 joint mean DELTA_LOGLOSS_V4_C30 > 0 in both 2024 and 2025;
3. at least 4 of 8 tasks improve BOTH proper scores versus C30 in BOTH years;
4. in 2025, V4 joint mean proper-score differences versus B0 are both > 0;
5. the 2025 month-block 95% interval has lower bound > 0 for BOTH:
       mean DELTA_BRIER_V4_C30
       mean DELTA_LOGLOSS_V4_C30
6. no task worsens BOTH proper scores versus C30 in BOTH years;
7. all required V4 fits converge.

This means:

    the V4 representation provides reproducible incremental predictive
    information over the locked C30 representation under the frozen linear
    model.

It does NOT mean a trading strategy is profitable.

### V4_REPRESENTATION_IMPROVEMENT_WEAK

Use if SUPPORTED fails but:

1. 2025 joint mean DELTA_BRIER_V4_C30 > 0;
2. 2025 joint mean DELTA_LOGLOSS_V4_C30 > 0;
3. at least 4/8 2025 tasks improve both proper scores versus C30;
4. no catastrophic implementation/calibration failure occurs;
5. all required fits converge.

Typical cases include:

- 2025 improvement but mixed 2024;
- positive point estimates with uncertainty intervals crossing zero;
- task heterogeneity preventing SUPPORTED classification.

### NO_USEFUL_V4_REPRESENTATION_IMPROVEMENT

Use if any of the following:

- 2025 joint mean Brier improvement vs C30 <= 0;
- 2025 joint mean log-loss improvement vs C30 <= 0;
- fewer than 4/8 2025 tasks improve both proper scores vs C30;
- V4 does not improve both joint proper scores relative to B0 in 2025;
- systematic calibration deterioration offsets discrimination;
- required model convergence materially fails.

### C31_INSUFFICIENT

Use only if:

- population/label reconciliation fails;
- locked C30 comparator cannot be reproduced;
- V4 features cannot be reproduced;
- chronology cannot be guaranteed;
- source integrity fails;
- sealed-2026 boundary cannot be guaranteed.

---

## 30. Important interpretation

C31 is deliberately a hard comparison.

A NO_USEFUL result would mean:

    replacing C30's broad state representation with the prospectively designed
    V4 transition representation did not produce useful incremental
    prediction under the same fixed linear model and evaluation framework.

It would NOT prove:

    opportunity is intrinsically unpredictable.

Likewise, a SUPPORTED result would establish representation improvement, not a
deployment-ready strategy.

---

## 31. No adaptive rerun

After seeing C31 results, do NOT in the same experiment:

- remove state variables;
- remove run variables;
- add interactions;
- change regularization;
- add symbol identity;
- try random forest;
- try boosting;
- try neural networks;
- change horizons;
- change GROSS40/GROSS50;
- change V4 formulas.

Any subsequent experiment requires separate prospective design.

---

## 32. No economic policy test

C31 must NOT:

- choose a probability threshold;
- skip E1 entries;
- simulate selective entry;
- construct a position-sizing rule;
- calculate strategy P&L from predictions;
- optimize capital allocation.

Prediction first.

Policy later, only if justified.

---

## 33. Required artifacts

Write to:

    artifacts/c31_v4_transition_prediction/

Required at minimum:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- label_reconciliation.json
- representation_reconciliation.json
- c30_comparator_reconciliation.json
- fold_reconciliation.json
- model_specification.json
- training_prevalence_baselines.json
- proper_scores.json
- discrimination_metrics.json
- calibration_results.json
- probability_distribution_diagnostics.json
- coefficients.json
- coefficient_stability.json
- task_sign_summary.json
- joint_representation_comparison.json
- trade_bootstrap_intervals.json
- month_bootstrap_intervals.json
- probability_quintile_diagnostics.json
- symbol_breadth_diagnostics.json
- convergence_audit.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid unnecessary row-level dumps.

---

## 34. Required tests

Focused tests must cover:

- exact 2,199 entry reconciliation;
- year/symbol counts;
- endpoint-label reconciliation;
- H3/H6/H12/H24 coverage;
- exact nine-column V4 schema/order;
- V4 feature hash/reproduction;
- exact C30 comparator reproduction;
- exact fold chronology;
- no validation-to-training leakage;
- train-only scaler fitting;
- fixed logistic parameters;
- proper-score sign convention;
- identical comparator row sets;
- calibration computation;
- joint eight-task aggregation;
- paired trade bootstrap;
- paired month bootstrap;
- deterministic PCG64 result;
- no policy/P&L calculation;
- no 2026 access.

Run focused tests.

Run full repository suite once if scientific/runtime source code changes.

---

## 35. Reproducibility

Record:

- C31 contract SHA-256;
- V4 specification SHA-256;
- V4 audit final-summary hash;
- C29/C30 authoritative hashes;
- source hashes;
- label hashes;
- population hash;
- V4 matrix semantic hash;
- C30 comparator prediction hash;
- model/scaler specification;
- Python version;
- package versions;
- git HEAD;
- dirty/untracked status;
- command;
- RNG seed.

Core machine-readable outputs must reproduce exactly or within explicitly
documented floating-point tolerance.

---

## 36. Governance

Do not modify frozen C29/C30 behavior.

Do not modify V1-V4 representation specifications or audit results.

Do not:

- access 2026;
- tune;
- select;
- stage implementation/results;
- commit implementation/results;
- push;
- start a post-C31 policy experiment.

The C31 contract itself may be committed prospectively.

---

## 37. Final report

Report:

1. contract SHA-256;
2. V4 spec/audit hashes;
3. exact E1 reconciliation;
4. exact label reconciliation;
5. horizon coverage;
6. exact V4 schema;
7. C30 comparator reconciliation;
8. fold train/validation counts and prevalence;
9. convergence for all 16 V4 fits;
10. absolute Brier/log loss for B0, C30, V4;
11. V4-C30 proper-score deltas;
12. V4-B0 proper-score deltas;
13. ROC AUC / PR AUC;
14. calibration intercept/slope/ECE;
15. probability-distribution diagnostics;
16. coefficient/sign-stability summary;
17. tasks improving both scores by year;
18. joint eight-task mean deltas;
19. trade-bootstrap intervals;
20. month-bootstrap intervals;
21. V4 probability-quintile ordering;
22. symbol-breadth diagnostics;
23. exact frozen classification:
       V4_REPRESENTATION_IMPROVEMENT_SUPPORTED
       V4_REPRESENTATION_IMPROVEMENT_WEAK
       NO_USEFUL_V4_REPRESENTATION_IMPROVEMENT
       C31_INSUFFICIENT
24. explicit statement that representation improvement does not establish
    trading profitability;
25. whether later policy research is scientifically justified;
26. artifact hash verification;
27. focused-test result;
28. full-suite result if run;
29. git diff --check;
30. git status --short;
31. confirmation no 2026 data/metadata was accessed;
32. confirmation no model/hyperparameter/feature search occurred;
33. confirmation no policy or P&L optimization occurred;
34. confirmation implementation/results were not staged/committed/pushed.

STOP.
