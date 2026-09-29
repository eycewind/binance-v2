# C24 Frozen Probability-to-Economic-Value Ordering Contract

Status: prospectively specified before C24 analysis.

## 1. Purpose

C23 established that current frozen C9 p_t2 adds incremental predictive
information beyond the causal state:

- elapsed_minutes_since_entry
- observable_current_return_from_entry

The frozen S+C9 specification improved Brier and log loss over S in both
2024 and 2025 for all five targets, with dependence-aware uncertainty
supporting the proper-score improvements. AUC also improved for every
target/year.

However, better prediction of:

    P(DELTA_LIQ_H > 0)

does not automatically imply that higher predicted probabilities correspond
to higher economically meaningful executable forward value.

C24 asks one question:

"Do frozen S+C9 probabilities monotonically and stably order realized
executable forward liquidation value?"

C24 is a descriptive economic-ordering audit.

It does NOT:
- train or recalibrate a model;
- search thresholds;
- define an exit policy;
- optimize P&L;
- select a horizon;
- access 2026;
- begin C25.

## 2. Frozen dependencies

Reuse without scientific modification:

- C20 executable forward liquidation targets
- C22/C23 decision-time semantics
- C23 frozen S+C9 out-of-time probabilities
- C23 population
- C23 whole-trade weighting
- C23 chronological evaluation structure

Targets:

- DELTA_LIQ_5
- DELTA_LIQ_15
- DELTA_LIQ_30
- DELTA_LIQ_60
- DELTA_LIQ_EVENT

No model refitting except where strictly required to reproduce already-frozen
C23 predictions exactly.

Prefer reuse of stored/frozen C23 predictions if available.

## 3. Population

Reconcile exactly to C23.

Expected full eligible population:

- 56,217 honestly scored snapshots
- 1,610 trades

Evaluation populations must match C23 exactly for:

- 2024 chronological fold_B validation
- 2025 untouched validation

No inferred probabilities.

No added snapshots.

## 4. Frozen prediction source

Primary predictor:

    p_sc9(t)

defined as the frozen C23 S+C9 binary-model predicted probability:

    P(DELTA_LIQ_H > 0 | elapsed time,
                        observable return from entry,
                        frozen p_t2)

Use the target-specific frozen S+C9 probability for each target.

Do NOT:
- retrain after inspecting C24 outcomes;
- recalibrate probabilities;
- substitute raw C9 p_t2;
- use M3;
- use future information.

Record exact provenance and hashes.

## 5. Binary label and continuous value

Binary label remains exactly C23:

    Y_H = 1 if DELTA_LIQ_H > 0
    Y_H = 0 if DELTA_LIQ_H <= 0

Exact-zero target values remain retained as class 0.

Continuous economic value remains:

    V_H = DELTA_LIQ_H

using the frozen C20 executable accounting convention.

No target transformation.

## 6. Chronology

### 2024

Use only the frozen C23/C22 honest chronological validation block:

- fold_B only
- 7,970 training rows / 256 trades
- 8,631 validation rows / 267 trades

No fold_A reconstruction.

No broader claim of full 2024 OOF coverage.

### 2025

Use frozen S+C9 models fitted under C23 using the complete 2024 scored
training population.

Evaluate untouched 2025:

- 39,616 rows
- 1,087 trades

No model revision after 2025 outcomes.

## 7. Probability-bin construction

Probability bins MUST be learned from training predictions only.

For each target/year evaluation:

- derive bin boundaries from the corresponding training-set S+C9 predicted
  probabilities;
- then apply those fixed boundaries unchanged to validation probabilities.

Use five weighted quantile bins:

    Q1
    Q2
    Q3
    Q4
    Q5

Each training quantile is defined using whole-trade weights.

If duplicate probability values prevent exact equal-mass boundaries:
- use deterministic monotonic boundaries;
- do not split identical prediction values across bins;
- record actual weighted mass per bin.

Do NOT define bins using validation outcomes or validation probability
quantiles.

## 8. Whole-trade weighting

Each trade receives equal total weight.

For trade i with n_i eligible snapshots:

    w_it = 1 / n_i

Use the same C23 weighting convention for all summaries.

Do not let long-duration trades dominate.

## 9. Primary per-bin summaries

For every target, year, and probability bin report:

- probability boundary
- weighted mean predicted probability
- weighted median predicted probability
- weighted observed positive rate
- weighted mean DELTA_LIQ_H
- weighted median DELTA_LIQ_H
- weighted p10 DELTA_LIQ_H
- weighted p25 DELTA_LIQ_H
- weighted p75 DELTA_LIQ_H
- weighted p90 DELTA_LIQ_H
- weighted mean positive DELTA_LIQ_H among positive rows
- weighted mean negative DELTA_LIQ_H among negative rows
- positive contribution
- negative contribution
- net contribution
- snapshot count
- trade count
- effective whole-trade weight

These are descriptive summaries only.

## 10. Economic ordering tests

For each target/year report:

### A. Rank association

Between frozen predicted probability and realized DELTA_LIQ_H:

- weighted Spearman correlation
- weighted linear correlation

### B. Bin monotonicity

Across Q1-Q5 report whether:

- positive rate is nondecreasing;
- mean DELTA_LIQ_H is nondecreasing;
- median DELTA_LIQ_H is nondecreasing.

Do not force a monotonic label if ties/noise violate ordering.

### C. Top-minus-bottom economic spread

Define prospectively:

    Delta_mean_Q5_Q1
      = mean_DELTA_LIQ(Q5) - mean_DELTA_LIQ(Q1)

    Delta_positive_rate_Q5_Q1
      = positive_rate(Q5) - positive_rate(Q1)

    Delta_median_Q5_Q1
      = median_DELTA_LIQ(Q5) - median_DELTA_LIQ(Q1)

Positive values favor higher predicted probability.

These are characterization statistics, not action thresholds.

## 11. Tail asymmetry

For each bin report separately:

- average positive DELTA_LIQ magnitude
- average negative DELTA_LIQ magnitude
- total weighted positive contribution
- total weighted negative contribution
- ratio of positive to absolute negative contribution where defined

Purpose:

Determine whether higher predicted positive probability is associated with:

- genuinely improving net economic value;
or merely
- more frequent small positive outcomes while large negative outcomes remain.

Do not construct an expected-utility policy.

## 12. Concentration diagnostics

For each target/year report:

- share of total positive DELTA_LIQ contribution from top 1% of positive rows
- top 5%
- top 10%
- top 20%
- Gini/concentration statistic if already supported by project utilities

This is diagnostic only.

Do not use concentration to select a horizon.

## 13. Dependence-aware uncertainty

Required for the primary economic ordering quantities.

Use frozen validation predictions and outcomes only.

Do not refit or tune inside bootstrap replicates.

### Primary

Paired UTC entry-calendar-month block bootstrap:

- 2,000 replicates
- fixed PCG64 seed
- whole trades attached to their entry month
- all symbols retained within sampled months
- all snapshots of sampled trades retained

For each target/year estimate 95% intervals for:

- weighted Spearman
- weighted linear correlation
- Delta_mean_Q5_Q1
- Delta_positive_rate_Q5_Q1
- Delta_median_Q5_Q1

### Robustness

Paired whole-trade bootstrap:

- 2,000 replicates
- fixed PCG64 seed
- resample trades
- retain all snapshots of each sampled trade

Report the same intervals.

Do not bootstrap snapshots independently.

## 14. Year stability

Evaluate separately:

- 2024 fold_B validation
- 2025 untouched validation

Do not pool years for the primary conclusion.

A pooled descriptive panel may be reported only as secondary context.

## 15. Symbol stability

For each target/year/symbol report:

- positive rate by bin
- mean DELTA_LIQ by bin
- weighted Spearman
- Q5-Q1 mean spread

Symbols:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

No symbol-specific bins learned from validation outcomes.

No symbol-specific models.

Do not treat five symbols as independent statistical replications.

## 16. Frozen classification

Classify each target independently.

### ECONOMIC_ORDERING_SUPPORTED

Require:

1. weighted Spearman > 0 in both 2024 and 2025;
2. Delta_mean_Q5_Q1 > 0 in both years;
3. Delta_positive_rate_Q5_Q1 > 0 in both years;
4. dependence-aware uncertainty is directionally supportive:
   - neither primary uncertainty scheme shows clear evidence of reversed
     Q5-Q1 mean ordering in both years;
5. result is not obviously driven by one symbol;
6. mean economic ordering is not contradicted by severe tail asymmetry that
   makes Q5 net contribution worse than Q1.

Strict monotonicity across all five bins is NOT required for support, but must
be reported.

### WEAK_ECONOMIC_ORDERING

Use if:

- point estimates are directionally positive in both years but intervals are
  broad/materially include zero;
- OR probability ordering is strong but mean economic-value ordering is
  nonmonotonic/unstable;
- OR symbol stability is incomplete;
- OR tail asymmetry materially weakens the interpretation.

### NO_USEFUL_ECONOMIC_ORDERING

Use if:

- mean economic ordering is absent or reverses;
- OR year stability fails;
- OR higher probability does not correspond to higher realized executable
  value;
- OR apparent ordering is dominated by rare tail outcomes without stable
  cross-year support.

### INSUFFICIENT

Use if:

- frozen C23 predictions cannot be reproduced/aligned;
- population mismatch occurs;
- bin construction cannot be performed without leakage;
- timing/provenance cannot be verified.

Do not alter these predicates after seeing results.

## 17. Important interpretation boundary

Even ECONOMIC_ORDERING_SUPPORTED means only:

"Frozen S+C9 probabilities order realized executable forward value."

It does NOT establish:

- an optimal threshold;
- an exit trigger;
- policy profitability;
- transaction-frequency economics;
- sequential-policy value;
- a preferred horizon.

Those require a later prospective policy experiment.

## 18. No threshold search

Do NOT:

- search probability cutoffs;
- evaluate "best" bin boundary;
- merge bins based on outcomes;
- select top-N percent;
- optimize expected return;
- optimize Sharpe;
- optimize P&L;
- compare candidate trading rules.

Q1-Q5 are descriptive frozen quantile bins only.

## 19. No horizon selection

All five horizons are evaluated equally.

Do NOT:

- rank horizons for deployment;
- choose one horizon for C25;
- call any horizon best;
- tune future work around the strongest observed C24 result.

## 20. Artifacts

Write to:

artifacts/c24_probability_economic_ordering/

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- frozen_prediction_reconciliation.json
- binary_label_definition.json
- bin_definition.json
- bin_boundaries_2024.json
- bin_boundaries_2025.json
- bin_summaries_2024.json
- bin_summaries_2025.json
- economic_ordering_2024.json
- economic_ordering_2025.json
- tail_asymmetry_2024.json
- tail_asymmetry_2025.json
- concentration_2024.json
- concentration_2025.json
- calendar_month_bootstrap.json
- whole_trade_bootstrap.json
- symbol_stability.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid redundant prediction dumps unless necessary for reproducibility.

## 21. Tests

Add focused tests for:

- exact C23 population reproduction
- frozen S+C9 prediction provenance
- exact binary zero handling
- no probability recalibration
- training-only bin construction
- validation bins use frozen training boundaries
- duplicate probability boundary handling
- whole-trade weighting
- weighted quantiles
- per-bin economic summaries
- Q5-Q1 spread calculations
- tail contribution accounting
- weighted Spearman implementation
- paired calendar-month bootstrap
- paired whole-trade bootstrap
- deterministic PCG64 seed
- no threshold search
- no horizon selection
- no future predictors
- no 2026 access

Run focused tests.

Run full repository suite once if scientific/runtime code changes.

## 22. Governance

Do NOT:

- modify C7-C23 scientific behavior;
- train a new model;
- recalibrate S+C9;
- add predictors;
- search thresholds;
- search bins;
- search models;
- select horizons;
- define/evaluate a trading policy;
- optimize P&L;
- access 2026;
- begin C25;
- stage, commit, or push.

## 23. Final report

Report:

1. contract SHA
2. population reconciliation
3. frozen prediction provenance
4. exact label rule
5. exact training-only bin construction
6. 2024 bin boundaries
7. 2024 per-bin positive rates
8. 2024 per-bin mean/median DELTA_LIQ
9. 2024 tail asymmetry
10. 2024 Spearman/linear association
11. 2024 Q5-Q1 spreads
12. 2025 bin boundaries
13. 2025 per-bin positive rates
14. 2025 per-bin mean/median DELTA_LIQ
15. 2025 tail asymmetry
16. 2025 Spearman/linear association
17. 2025 Q5-Q1 spreads
18. calendar-month uncertainty
19. whole-trade uncertainty
20. concentration diagnostics
21. symbol stability
22. monotonicity diagnostics
23. frozen classification for each target
24. whether probability refinement corresponds to economic-value ordering
25. distinction between positive-rate ordering and value-magnitude ordering
26. limitations
27. implication for C25
28. artifact hashes
29. focused/full test results
30. git diff --check
31. git status --short
32. confirmation no model/recalibration
33. confirmation no threshold/bin search
34. confirmation no horizon selection
35. confirmation no policy/P&L optimization
36. confirmation no 2026 access
37. confirmation nothing staged/committed/pushed

STOP after C24.
