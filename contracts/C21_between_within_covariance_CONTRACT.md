# C21 Between-Trade / Within-Trade Covariance Decomposition Contract

Status: prospectively specified before C21 analysis.

## 1. Purpose

C20 found:

- positive pooled association between frozen C9 p_t2 and executable forward
  liquidation value for all five frozen targets;
- negative average within-trade correlations.

Those findings are not mathematically contradictory because they use different
aggregation and normalization.

C21 asks one primary question:

"Does positive between-trade variation outweigh negative within-trade
variation in C20's pooled probability-value association?"

C21 is a statistical decomposition / interpretation checkpoint.

It does NOT:
- train a model;
- define an exit policy;
- optimize P&L;
- select a horizon;
- access 2026;
- begin C22.

## 2. Frozen dependencies

Reuse without modification:

- C9 frozen probabilities
- C18/C20 frozen honest scored population
- C20 executable forward liquidation targets
- C20 whole-trade weighting
- C20 fixed targets:
  - DELTA_LIQ_5
  - DELTA_LIQ_15
  - DELTA_LIQ_30
  - DELTA_LIQ_60
  - DELTA_LIQ_EVENT

No C7-C20 scientific behavior may be changed.

## 3. Exact C20 reproduction first

Before decomposition, reproduce C20 for each target exactly.

Verify:

- same scored snapshot population;
- same trade population;
- same target values;
- same frozen p_t2 values;
- same whole-trade weighting;
- same pooled association metrics;
- same year/symbol membership.

Record zero-difference or numerical-tolerance differences.

Do not proceed to interpretation if reproduction fails.

## 4. Weighting convention

Each trade receives equal total weight.

If trade i has n_i eligible snapshots, each of its snapshots receives:

    w_it = 1 / n_i

Normalize globally only as required by the covariance implementation.

Use the identical trade-weighting convention as C20.

Do not let long-duration trades dominate.

## 5. Primary covariance decomposition

For each target V:

    V in {
      DELTA_LIQ_5,
      DELTA_LIQ_15,
      DELTA_LIQ_30,
      DELTA_LIQ_60,
      DELTA_LIQ_EVENT
    }

let:

    p_it = frozen C9 probability for trade i at snapshot t
    V_it = frozen executable forward liquidation value
    pbar_i = within-trade weighted mean p
    Vbar_i = within-trade weighted mean V

Decompose pooled covariance into:

    Cov_total(p,V)
      =
      Cov_between(pbar_i, Vbar_i)
      +
      E_i[ Cov_within_i(p_it, V_it) ]

under the exact whole-trade weighting convention.

The decomposition must reconstruct pooled covariance to strict numerical
tolerance.

Report:

- total covariance
- between-trade covariance
- within-trade covariance component
- reconstruction residual
- between share of total
- within share of total where mathematically meaningful

Do not force percentage shares when total covariance is near zero or signs
oppose; report raw components clearly.

## 6. Correlations are secondary interpretation

For each target also report:

- pooled correlation;
- correlation across trade means:
    Corr(pbar_i, Vbar_i)
- distribution of within-trade correlations;
- mean within-trade correlation;
- median within-trade correlation;
- p10 / p90;
- number of trades eligible for within-trade correlation.

State explicitly:

average per-trade correlation is NOT the within-trade covariance component and
cannot be averaged to reconstruct pooled correlation.

Do not conflate covariance decomposition with correlation decomposition.

## 7. Primary interpretation

For each target classify the decomposition descriptively:

BETWEEN_DOMINANT_POSITIVE if:
- total covariance > 0;
- between-trade covariance > 0;
- within-trade covariance < 0;
- and between-trade covariance magnitude exceeds the negative within component,
  thereby producing positive total covariance.

WITHIN_DOMINANT if:
- within-trade covariance determines the sign/magnitude of total covariance.

SAME_SIGN_COMPONENTS if:
- between and within components have the same sign.

MIXED_OR_NEAR_ZERO if:
- decomposition is numerically small, unstable, or does not fit the above.

These are explanatory labels only.

They do not imply policy value.

## 8. Year stability

Repeat the complete covariance decomposition separately for:

- 2024
- 2025

using the same weighting rules.

For each target report:

- total covariance
- between component
- within component
- pooled correlation
- trade-mean correlation
- within-trade correlation summary

No model revision or selection.

## 9. Symbol stability

Repeat for:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

Report raw components and signs.

Do not infer a symbol-specific rule.

Do not exclude symbols.

## 10. Dependence-aware uncertainty

Use trade as the primary resampling unit.

For pooled and year-level decomposition, estimate uncertainty using
whole-trade resampling.

Additionally use the established calendar-block resampling convention where
feasible to test sensitivity to temporal clustering.

For each covariance component report:

- point estimate
- 95% interval

At minimum for:
- total covariance
- between covariance
- within covariance

Do not resample individual snapshots independently.

For symbol-level cells with limited trades, report intervals but avoid strong
claims when support is weak.

## 11. Secondary causal adjustment

Perform one small prespecified descriptive adjustment to the within-trade
association.

Question:

"Does the within-trade p_t2 / forward-value association materially change
after accounting for causal elapsed time and current price progress?"

Use ONLY causal contemporaneous quantities:

A. elapsed time since entry

B. current price progress, defined prospectively as a causal current-state
   measure using information available at t.

Use a fixed simple definition:

    current_return_from_entry(t)
      = current executable/reference price at t relative to entry price

Do not use:
- future terminal distance
- future event proximity
- eventual T2/P0 class
- future MFE/MAE
- future P0 return
- full-trajectory means as predictors

## 12. Adjustment method

Use a fixed descriptive within-trade residualization / regression approach.

For each target, estimate the association between p_t2 and V after removing
linear effects of:

- elapsed time since entry
- current return from entry

using only causal quantities.

Keep trade grouping explicit.

Report:

- unadjusted within-trade covariance/association
- adjusted p_t2 coefficient or residual covariance
- sign change, if any
- magnitude change

This is descriptive adjustment only.

Do not interpret it as causal proof.

Do not use results to fit a live model in C21.

## 13. Diagnostic-only full-trajectory trade means

Trade means:

    pbar_i
    Vbar_i

are diagnostic quantities only.

They use full observed trade trajectories and therefore include later
snapshots relative to early states.

They MUST NOT be treated as live causal features.

They MUST NOT be proposed for a future production model.

C21 must state this explicitly in artifacts and final report.

## 14. Retrospective explainers

Future terminal proximity and eventual outcome class may be used only as
retrospective explanatory decompositions if helpful.

They cannot become live predictors.

If reported, label them:

EVALUATION_ONLY / RETROSPECTIVE.

Do not let them affect primary conclusions.

## 15. No horizon selection

C21 evaluates all five frozen C20 targets.

Do not:
- select a preferred horizon;
- rank horizons for strategy use;
- recommend the most profitable horizon.

The purpose is structural explanation only.

## 16. Interpretation implications

Possible outcomes:

### A. Positive between-trade covariance outweighs negative within-trade covariance

Implication:
the aggregation explanation is supported.

A future checkpoint may then distinguish:
- relatively persistent trade context/quality
from
- evolving within-trade decision state.

### B. Within-trade covariance differs materially from average per-trade
correlation implication

Implication:
variance and normalization explain part of the apparent pooled/within conflict.

### C. Signs/magnitudes unstable across years or symbols

Implication:
there is no stable decomposition on which to base a new architecture yet.

### D. Causal elapsed-time/current-price adjustment materially changes the
within-trade association

Implication:
those causal variables deserve consideration in a future state definition.

This does NOT establish predictive usefulness.

## 17. Critical limitation

Even a clean decomposition explains an observed association.

It does NOT demonstrate:
- an exit advantage;
- policy profitability;
- causal effect;
- deployable predictive value.

C21 must not over-interpret decomposition results.

## 18. Artifacts

Write to:

artifacts/c21_between_within_covariance/

Required:

- run_manifest.json
- provenance.json
- c20_reproduction.json
- weighting_definition.json
- covariance_definition.json
- covariance_decomposition.json
- correlation_interpretation.json
- year_decomposition.json
- symbol_decomposition.json
- uncertainty_trade_bootstrap.json
- uncertainty_calendar_block.json
- causal_adjustment_definition.json
- causal_adjustment_results.json
- diagnostic_only_trade_means.json
- interpretation_predicates.json
- c22_implication.json
- final_summary.json
- reproducibility_hashes.json

Keep artifacts bounded.

## 19. Tests

Add focused tests for:

- exact C20 population/target reproduction
- equal-total-weight-per-trade convention
- covariance decomposition identity
- numerical reconstruction tolerance
- distinction between covariance and correlation summaries
- year grouping
- symbol grouping
- whole-trade bootstrap
- calendar-block bootstrap if implemented
- causal elapsed-time calculation
- causal current-return calculation
- no future variables in adjustment
- diagnostic trade means prohibited from live feature schema
- deterministic results
- no 2026 access

Run focused tests.

Run full repository suite once if scientific/runtime code changes.

## 20. Governance

Do not:

- modify C7-C20 scientific behavior
- train/recalibrate a predictive model
- define/evaluate an exit policy
- optimize P&L
- select a horizon
- search thresholds
- promote full-trajectory means to predictors
- use future terminal information as live predictors
- access 2026
- begin C22
- stage, commit, or push

## 21. Final report

Report:

1. contract SHA
2. C20 reproduction status
3. exact weighting convention
4. covariance identity used
5. pooled decomposition for all five targets
6. reconstruction residuals
7. between vs within component interpretation
8. pooled correlations
9. trade-mean correlations
10. within-trade correlation distributions
11. why correlations do not reconstruct covariance
12. 2024 decomposition
13. 2025 decomposition
14. symbol decomposition
15. trade-bootstrap uncertainty
16. calendar-block uncertainty
17. causal adjustment definition
18. unadjusted vs adjusted within-trade association
19. whether elapsed time/current price materially changes the result
20. confirmation trade means are diagnostic only
21. frozen interpretation
22. implication for C22
23. limitations
24. artifact hashes
25. focused/full test results
26. git diff --check
27. git status --short
28. confirmation no model/policy/horizon selection
29. confirmation no future diagnostic promoted to predictor
30. confirmation no 2026 access
31. confirmation nothing staged/committed/pushed

STOP after C21.
