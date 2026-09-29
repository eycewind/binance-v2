# C28 Strategy-Level Economic Review Contract

Status: prospectively specified before C28 implementation or analysis.

## 1. Purpose

C20-C27 established:

- economically informative post-entry state exists;
- first-Q1 DELTA_LIQ_5 states have negative short-horizon value;
- permanent Q1 liquidation produced only weak economic improvement;
- temporary sell/re-entry is infeasible under realistic frozen trading costs
  because the short-horizon edge is much smaller than incremental turnover
  friction.

Before further exit research, C28 reviews the strategy at a higher level.

C28 asks exactly three questions:

1. Is canonical P0 economically positive before costs but negative after costs?

2. Do frozen E1 entry times outperform comparable prespecified non-signal
   reference entry times at fixed executable horizons?

3. Does favorable post-entry movement survive realistic costs, and how much
   of that movement does canonical P0 retain?

C28 is a strategy-level diagnostic.

No new predictive model.
No exit policy.
No threshold search.
No entry-rule modification.
No horizon optimization.
No P&L optimization.
No 2026 access.

C28 ends with one strategy-research direction.

## 2. Frozen population

Use the exact original frozen E1 entry population:

    2,199 trades

Entry rule:

    E1_H1_SMA24_CROSS_V1

Frozen entry hash:

    6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3

Use exact frozen entry timestamps and execution conventions.

Reconcile all 2,199 entries before analysis.

If reconciliation fails materially:

    INSUFFICIENT_RECONCILIATION

and STOP.

## 3. Frozen canonical benchmark

Canonical lifecycle benchmark:

    P0

Use exact frozen P0 behavior and accounting from prior experiments.

Do not redefine P0.

Reproduce P0 under:

- C0
- C_BASE
- C_S5
- C_S10

C_BASE remains primary realistic-cost scenario.

## 4. Review structure

C28 contains three diagnostic layers:

### Layer 1
P0 gross versus net economics.

### Layer 2
Entry-timing advantage versus one frozen matched reference mechanism.

### Layer 3
Post-entry opportunity, realistic cost survival, and P0 retention.

No layer may modify another layer's specification.

## 5. Layer 1 — P0 gross versus net economics

For all 2,199 frozen entries, report canonical P0 under:

- C0
- C_BASE
- C_S5
- C_S10

For every scenario report:

- trade count
- total P&L
- mean return
- median return
- positive-return fraction
- negative-return fraction
- win/loss/tie count
- mean holding duration
- median holding duration

Report separately:

- full population
- 2024
- 2025
- each symbol

## 6. Layer 1 friction decomposition

Report:

    P0_COST_DRAG
      = P0_C0_NET - P0_C_BASE_NET

using both:

- mean return difference
- total P&L difference

Also report C_BASE, C_S5 and C_S10 degradation relative to C0.

Define descriptive flag:

    COST_FLIPS_P0 = TRUE

only if:

    P0 mean return under C0 > 0
    AND
    P0 mean return under C_BASE <= 0

Report this for:

- full population
- 2024
- 2025

Do not treat this flag alone as proof that costs are the only problem.

## 7. Layer 2 — entry timing question

Question:

    Does the frozen E1 entry timestamp provide forward-return advantage over
    comparable non-signal entry times?

Use exactly one reference-entry mechanism.

No alternate control may be tested.

## 8. Frozen reference-entry control

For each actual E1 trade i with:

- symbol s
- entry calendar month m
- entry UTC hour-of-day h

construct a deterministic reference pool of candidate completed hourly states
satisfying ALL:

1. same symbol s;
2. same calendar month m;
3. same UTC hour-of-day h;
4. E1 did NOT fire at that hourly state;
5. candidate timestamp is not within +/-24 hours of ANY frozen E1 entry for
   the same symbol;
6. candidate has valid executable 1-minute entry data;
7. candidate has sufficient future data for the horizon being evaluated;
8. candidate lies entirely inside the frozen 2024-2025 evaluation dataset;
9. no 2026 data.

Reference entry execution:

    next valid 1-minute open strictly after the candidate completed hourly
    state

using the same entry execution convention as actual E1 entries.

Do not match on future information.

Do not match on realized future volatility or return.

Do not use model outputs to choose controls.

## 9. Reference outcome per actual trade

For actual trade i and fixed horizon H:

1. compute the actual E1 fixed-horizon outcome;
2. compute the outcome for every eligible reference timestamp in i's frozen
   reference pool;
3. define i's reference outcome as the equal-weight mean of all eligible
   reference outcomes.

Thus every original E1 trade receives one deterministic matched-reference
outcome per horizon.

No random reference timestamp is selected.

An eligible reference timestamp may contribute to more than one actual trade's
reference pool.

Record this dependence explicitly.

## 10. Insufficient reference pool

For every actual trade/horizon report reference-pool size.

Do not fabricate controls.

If pool size is zero:

- mark that trade unavailable for that horizon's entry-timing comparison;
- retain it in Layer 1 and Layer 3 where applicable.

Do NOT:
- expand to another month;
- change hour matching;
- reduce the +/-24h exclusion;
- create a fallback control.

Report coverage by year/symbol/horizon.

## 11. Frozen fixed horizons

Evaluate exactly:

    H6   = 6 hours
    H24  = 24 hours
    H72  = 72 hours
    H168 = 168 hours / 7 days

H24 is PRIMARY.

Reason:

The frozen E1 entry mechanism has a 24-hour refractory period. H24 therefore
tests whether an entry signal adds economic value over the interval during
which the strategy cannot generate another entry.

H6, H72 and H168 are prespecified temporal diagnostics only.

Do not select another primary horizon after seeing results.

Do not interpolate an optimal horizon.

## 12. Fixed-horizon execution

For both actual and reference entries:

Entry:

    next valid 1-minute open after the completed hourly state.

Exit at horizon H:

    first valid 1-minute open at or after entry decision timestamp + H,
    using one frozen timestamp convention consistently for both actual and
    reference entries.

Record exact timing convention before computing results.

No MFE-based exit.
No P0-based exit.
No stop.
No take-profit.

Fixed horizon means fixed horizon.

## 13. Fixed-horizon cost accounting

For each H evaluate:

- C0
- C_BASE
- C_S5
- C_S10

Use actual executed notionals and exact frozen fee/slippage assumptions.

Actual E1 and reference entries use identical accounting.

For each trade i:

    ENTRY_ADVANTAGE_H_i
      = ACTUAL_E1_RETURN_H_i
        - MATCHED_REFERENCE_RETURN_H_i

Report both C0 and net cost scenarios.

## 14. Primary entry-timing estimand

Primary:

    mean ENTRY_ADVANTAGE_H24

under C_BASE.

Because actual/reference arms use the same fixed holding period and cost
convention, also report the C0 paired advantage.

Report:

- mean
- median
- positive/negative/tie fraction
- total normalized contribution
- 2024
- 2025
- full covered comparison population
- each symbol

H6/H72/H168 receive identical descriptive reporting.

## 15. Entry-timing uncertainty

Primary dependence-aware uncertainty:

### UTC entry-calendar-month block bootstrap

- 2,000 replicates
- fixed PCG64 seed
- resample actual E1 trades by UTC entry month
- retain each trade's deterministic matched-reference outcome
- preserve all horizons/cost scenarios together

Report 95% intervals for:

- mean H24 entry advantage C0
- mean H24 entry advantage C_BASE

separately for:

- 2024
- 2025
- pooled covered comparison population

Secondary robustness:

### Whole-entry bootstrap

- 2,000 PCG64 replicates
- fixed PCG64 seed

Explicitly note that matched reference pools may overlap, so this bootstrap
does not eliminate shared-control dependence.

No snapshot bootstrap.

## 16. Entry advantage definition

Define:

    ENTRY_ADVANTAGE_SUPPORTED = TRUE

only if ALL hold:

1. H24 actual-minus-reference mean > 0 in 2024;
2. H24 actual-minus-reference mean > 0 in 2025;
3. pooled H24 mean > 0;
4. calendar-month uncertainty is directionally supportive and does not show
   clear evidence of materially negative H24 advantage;
5. result is not obviously driven by one symbol.

The 95% CI is not required to exclude zero.

H6/H72/H168 may strengthen or weaken interpretation but may NOT replace H24
as the frozen primary test.

## 17. Layer 3 — favorable post-entry movement

MFE is descriptive only.

MFE must NOT be interpreted as a capturable exit because its time is known
only retrospectively.

Use the exact frozen MFE construction already established in C2 where
compatible.

At minimum report thresholds:

- MFE >= 0.5%
- MFE >= 1%
- MFE >= 2%
- MFE >= 3%

For each threshold report:

- count
- fraction of entries
- 2024/2025 split
- symbol split
- median time to first threshold crossing if already causally reconstructible
  from frozen minute data

No strategy may exit at MFE.

## 18. Executable opportunity evidence

Capturable/economic opportunity is assessed using the fixed horizons from
Layer 2, NOT MFE.

For actual E1 entries at H6/H24/H72/H168 report under every cost scenario:

- total P&L
- mean return
- median return
- positive-return fraction
- 2024
- 2025
- symbol results

Primary realistic opportunity statistic:

    ACTUAL_E1_H24_CBASE_MEAN

## 19. Cost-surviving entry opportunity

Define:

    ENTRY_OPPORTUNITY_SURVIVES_COSTS = TRUE

only if ALL hold:

1. ENTRY_ADVANTAGE_SUPPORTED = TRUE;
2. actual E1 H24 C_BASE mean return > 0 in 2024;
3. actual E1 H24 C_BASE mean return > 0 in 2025;
4. pooled actual E1 H24 C_BASE mean > 0;
5. month-block uncertainty does not show clear evidence of materially negative
   H24 actual-entry expectancy.

Again, H6/H72/H168 are diagnostics and cannot substitute for failed H24
criteria.

## 20. P0 retention diagnostics

For each original E1 trade, compare canonical P0 with the fixed-horizon actual
entry outcomes.

For H6/H24/H72/H168 report:

    P0_MINUS_H
      = P0_return - fixed_horizon_return_H

under:

- C0
- C_BASE

Report:

- mean
- median
- positive/negative fraction
- total P&L difference
- 2024/2025
- symbol

No "best horizon" may be formed by taking the maximum over horizons.

## 21. MFE retention diagnostics

MFE remains retrospective/descriptive.

For trades with MFE > 0 report:

    P0_GROSS_CAPTURE_RATIO
      = P0_C0_return / MFE

Do not clip the ratio.

Negative values are allowed and must remain visible.

Report:

- median
- p25/p75
- fraction capture ratio < 0
- fraction >= 0
- fraction >= 0.25
- fraction >= 0.50
- fraction >= 0.75
- fraction >= 1.00

Also report:

    MFE_SURRENDER_GAP
      = MFE - P0_C0_return

mean and median.

These metrics describe how much favorable excursion P0 retained.
They do NOT imply that MFE itself was executable or capturable.

## 22. Threshold-conditioned P0 retention

For frozen MFE cohorts:

- >=0.5%
- >=1%
- >=2%
- >=3%

report:

- trade count
- mean MFE
- mean/median P0 C0 return
- mean/median P0 C_BASE return
- P0 positive-return fraction
- P0 C_BASE positive-return fraction
- mean MFE surrender gap

Do not create exits from these thresholds.

## 23. Strategy-level decision

After all three layers, return exactly one research direction:

### INVESTIGATE_ENTRY_MODEL

Use if:

    ENTRY_ADVANTAGE_SUPPORTED = FALSE

Interpretation:

The frozen entry timing has not established sufficient predictive/economic
advantage over the prespecified reference entry mechanism.

Do not continue local exit-policy tuning.

### RECONSIDER_STRATEGY_ECONOMICS

Use if:

    ENTRY_ADVANTAGE_SUPPORTED = TRUE
    AND
    ENTRY_OPPORTUNITY_SURVIVES_COSTS = FALSE

Interpretation:

Entry timing has evidence of advantage, but the advantage does not survive the
frozen realistic-cost economics at the primary 24h scale.

Future work should address strategy economics such as turnover, natural
holding scale, and required gross edge before returning to exit design.

This does NOT authorize changing costs or selecting a favorable horizon.

### INVESTIGATE_PERMANENT_EXIT_TARGET

Use if:

    ENTRY_ADVANTAGE_SUPPORTED = TRUE
    AND
    ENTRY_OPPORTUNITY_SURVIVES_COSTS = TRUE
    AND
    canonical P0 C_BASE mean return <= 0

Interpretation:

The entry timing advantage survives realistic costs, but canonical P0 fails to
retain it economically.

Future exit research should target the economics of permanent liquidation
directly rather than repurposing the five-minute sign model.

### REVIEW_COMPLETE_P0_NOT_ECONOMICALLY_BROKEN

Use if:

    ENTRY_ADVANTAGE_SUPPORTED = TRUE
    AND
    ENTRY_OPPORTUNITY_SURVIVES_COSTS = TRUE
    AND
    canonical P0 C_BASE mean return > 0

Interpretation:

A cost-surviving entry advantage exists and P0 itself remains positive after
costs. C28 therefore does not establish that exit redesign is the primary
strategy problem.

No new policy is authorized.

## 24. Important interpretation rules

### MFE

MFE may establish that favorable movement occurred after entry.

MFE alone may NOT establish:

- a tradable opportunity;
- an achievable exit;
- an upper bound that a causal strategy could capture;
- evidence for a new threshold policy.

### Reference control

The matched non-signal control estimates whether frozen E1 timing adds value
relative to prespecified comparable market times.

It is not a fully identified causal counterfactual.

Report limitations from:

- shared reference pools;
- imperfect regime matching;
- month/hour matching granularity.

Do not overstate causality.

### Costs

If C0 is positive and C_BASE negative, report the cost flip clearly.

Do not infer that lowering assumed costs is a valid strategy improvement.

## 25. Prohibited analyses

Do NOT:

- retrain E1;
- change SMA period;
- change crossover definition;
- change 24h refractory;
- test alternate reference-control definitions;
- randomly search reference times;
- match on future outcomes;
- tune fixed horizons;
- declare H6/H72/H168 primary after results;
- take best return across horizons;
- create an MFE exit;
- create a take-profit;
- create a stop-loss;
- create a new exit model;
- reuse C9/S+C9 as an exit policy;
- alter P0;
- select symbols;
- select months;
- optimize costs;
- optimize P&L or Sharpe;
- access 2026;
- start C29.

## 26. Required artifacts

Write to:

artifacts/c28_strategy_economic_review/

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- p0_cost_economics.json
- p0_year_results.json
- p0_symbol_results.json
- p0_cost_drag.json
- reference_control_definition.json
- reference_pool_reconciliation.json
- reference_pool_coverage.json
- fixed_horizon_timing.json
- entry_advantage_h6.json
- entry_advantage_h24.json
- entry_advantage_h72.json
- entry_advantage_h168.json
- entry_advantage_year_results.json
- entry_advantage_symbol_results.json
- entry_advantage_calendar_month_bootstrap.json
- entry_advantage_whole_entry_bootstrap.json
- actual_entry_fixed_horizon_economics.json
- mfe_descriptive.json
- mfe_threshold_results.json
- p0_fixed_horizon_retention.json
- p0_mfe_retention.json
- strategy_decision_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid redundant raw-minute dumps.

## 27. Required tests

Add focused tests for:

- exact 2,199 E1 entry reproduction
- exact entry hash
- exact P0 reproduction
- exact cost scenarios
- deterministic reference pool construction
- same symbol matching
- same calendar month matching
- same UTC hour-of-day matching
- non-signal requirement
- +/-24h exclusion from every same-symbol E1 entry
- no future-feature matching
- valid horizon coverage
- no 2026 reference timestamps
- equal-weight reference averaging
- zero-pool handling
- H24 primary designation
- exact H6/H24/H72/H168 timing
- identical actual/reference execution convention
- fixed-horizon cost accounting
- calendar-month bootstrap determinism
- whole-entry bootstrap determinism
- MFE never used as an exit
- no best-horizon construction
- P0 retention arithmetic
- frozen strategy-decision predicates
- no model fitting
- no policy simulation
- no 2026 access

Run focused tests.

Run full repository suite once if scientific/runtime code changes.

## 28. Governance

Do NOT:

- modify C7-C27 scientific behavior;
- modify this contract;
- stage implementation/results;
- commit implementation/results;
- push;
- access 2026;
- start C29.

The contract itself may be committed before implementation.

## 29. Final report

Report:

1. contract SHA
2. population reconciliation
3. P0 C0 economics
4. P0 C_BASE economics
5. P0 C_S5/C_S10 economics
6. whether costs flip P0
7. exact reference-entry definition
8. reference coverage
9. H24 actual entry economics
10. H24 matched-reference economics
11. H24 actual-minus-reference advantage
12. 2024 H24 entry advantage
13. 2025 H24 entry advantage
14. H24 dependence-aware uncertainty
15. H6/H72/H168 diagnostic results
16. ENTRY_ADVANTAGE_SUPPORTED true/false
17. actual H24 C_BASE expectancy by year
18. ENTRY_OPPORTUNITY_SURVIVES_COSTS true/false
19. MFE threshold frequencies
20. explicit warning that MFE is retrospective
21. P0 versus each fixed horizon
22. P0 MFE capture/surrender diagnostics
23. whether evidence points primarily to entry, strategy economics, or exit
24. exact frozen strategy direction:
       INVESTIGATE_ENTRY_MODEL
       RECONSIDER_STRATEGY_ECONOMICS
       INVESTIGATE_PERMANENT_EXIT_TARGET
       REVIEW_COMPLETE_P0_NOT_ECONOMICALLY_BROKEN
25. limitations of matched reference control
26. implication for C29
27. artifact hash verification
28. focused test result
29. full-suite result
30. git diff --check
31. git status --short
32. confirmation no alternate control/horizon/model/policy search
33. confirmation no P&L optimization
34. confirmation no 2026 access
35. confirmation nothing implementation-related staged/committed/pushed
36. confirmation C29 not started

STOP after C28.
