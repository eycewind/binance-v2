# C29 Fixed-Horizon Opportunity Prevalence Audit

Status: prospectively specified before implementation or analysis.

## 1. Purpose

C28 established that frozen E1 entry timing materially outperformed a
prespecified matched non-signal reference at H24, but actual E1 H24 expectancy
did not survive realistic costs consistently across both years.

The subsequent strategy-design review froze the intended automated strategy as:

- Binance Spot
- USDT-quoted pairs
- long-only
- no leverage
- intended holding scale measured primarily in hours
- typical holding period several hours
- normal upper scale approximately 24 hours
- exceptional strong-trend extension may reach approximately 48 hours
- deployment-style round-trip friction approximately 19 bp with BNB fee
  deduction
- conservative round-trip friction approximately 24 bp
- strategy-level gross opportunity hurdle approximately 40-50 bp

C29 asks only:

    How much fixed-horizon executable opportunity actually exists after
    frozen E1 entries over the intended 3h/6h/12h/24h strategy scale?

C29 is descriptive/economic characterization only.

No new predictive model.
No entry modification.
No exit policy.
No threshold optimization.
No horizon selection.
No MFE-derived strategy.
No 2026 access.

## 2. Frozen entry population

Use the exact original E1 population:

    2,199 trades

Entry rule:

    E1_H1_SMA24_CROSS_V1

Frozen entry hash:

    6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3

Expected year counts:

- 2024: 1,093
- 2025: 1,106

Expected symbol counts:

- BNBUSDT: 442
- BTCUSDT: 451
- ETHUSDT: 434
- SOLUSDT: 431
- XRPUSDT: 441

Reconcile exactly before analysis.

If reconciliation fails materially:

    INSUFFICIENT_RECONCILIATION

and STOP.

## 3. Frozen horizons

Evaluate exactly:

    H3  = 3 hours
    H6  = 6 hours
    H12 = 12 hours
    H24 = 24 hours

These horizons represent the intended automated strategy scale.

All four are co-primary characterization horizons.

C29 MUST NOT:

- select a best horizon;
- rank horizons as strategy choices;
- construct an optimized holding period;
- interpolate an ideal horizon;
- inspect H48/H72/H168 as substitutes.

H24 remains useful continuity with C28, but C29 is explicitly a
multi-horizon characterization rather than a horizon-selection experiment.

## 4. Execution timing

Use the exact frozen C28 fixed-horizon execution convention wherever
applicable.

Entry:

    frozen E1 decision
        ->
    next valid executable 1-minute open

Fixed-horizon exit:

    first valid executable 1-minute open at or after the frozen horizon
    endpoint under the exact C28 timestamp convention.

The same convention must be used for H3/H6/H12/H24.

Before computing economics record the exact:

- entry-decision timestamp rule;
- entry-fill timestamp rule;
- horizon anchor;
- horizon-end timestamp rule;
- exit-fill rule.

No interpolation.
No synthetic fills.
No MFE exit.
No P0 exit.

## 5. Valid horizon population

For each horizon report:

- original trade count
- valid executable trade count
- unavailable trade count
- year counts
- symbol counts

A trade unavailable for one horizon remains eligible for shorter horizons if
its data are valid.

Do not fabricate future prices.

No 2026 market data may be used to complete a 2025 trade.

## 6. Cost scenarios

Evaluate exactly the existing frozen scenarios:

- C0
- C_BASE
- C_S5
- C_S10

C_BASE remains the conservative primary scenario for continuity.

Also calculate one DESIGN_BNB scenario solely for the strategy-design review:

    explicit fee = 7.5 bp per leg
    adverse execution allowance = 2 bp per leg

Indicative round-trip friction:

    approximately 19 bp

DESIGN_BNB is a prespecified economic scenario, not a fitted cost.

Do not alter fills or market prices between cost scenarios.

If the existing cost framework cannot represent DESIGN_BNB exactly without
changing prior scientific helpers, implement it locally in C29 without
modifying C7-C28 behavior.

## 7. Fixed-horizon return

For trade i and horizon H calculate the actual executable fixed-horizon return:

    R_i,H,cost

using the frozen entry and fixed-horizon exit accounting.

Report under every cost scenario:

- mean
- median
- p10
- p25
- p75
- p90
- positive-return fraction
- negative-return fraction
- exact-zero fraction
- total P&L

Report separately for:

- full population
- 2024
- 2025
- each symbol

## 8. Gross opportunity hurdles

The strategy-design review established two research hurdles:

    40 bp gross
    50 bp gross

These are economic viability/reference hurdles.

They are NOT:

- take-profit levels;
- exit rules;
- entry filters;
- thresholds to optimize.

Using C0 fixed-horizon executable return, define descriptive labels:

    GROSS40_H = 1 if R_H_C0 >= +0.40%
    GROSS50_H = 1 if R_H_C0 >= +0.50%

Exact boundary equality belongs to the positive class.

For every horizon report prevalence of both labels.

## 9. Opportunity prevalence

For each horizon and hurdle report:

- valid trade count
- opportunity count
- prevalence
- 2024 count/prevalence
- 2025 count/prevalence
- symbol count/prevalence
- calendar-month count/prevalence

Also report:

- intersection of GROSS40 and GROSS50 as implied by definitions
- number of trades satisfying the hurdle in both years combined

No minimum prevalence is prospectively declared sufficient for trading.

C29 characterizes prevalence; it does not authorize a model.

## 10. Gross opportunity magnitude

For GROSS40 and GROSS50 trades separately, report at each horizon:

- mean C0 return
- median C0 return
- p25/p75
- p90
- mean excess above hurdle
- median excess above hurdle
- total gross P&L contribution

Also report corresponding results for trades below each hurdle.

This is retrospective characterization only.

## 11. Cost survival of gross opportunities

For trades labeled from C0 only:

    GROSS40_H
    GROSS50_H

report their realized fixed-horizon return under:

- DESIGN_BNB
- C_BASE
- C_S5
- C_S10

For each scenario report:

- mean net return
- median net return
- positive-net-return fraction
- total net P&L

The class definition must remain frozen from C0.

Do NOT relabel opportunity trades separately under each cost scenario.

## 12. Whole-population cost economics

For every horizon report:

    C0 mean
    DESIGN_BNB mean
    C_BASE mean
    C_S5 mean
    C_S10 mean

Also calculate cost drag from C0.

This addresses whether increasing holding time within the intended strategy
scale materially improves gross opportunity relative to the fixed friction
floor.

Do not select a horizon from this result.

## 13. Forward-return threshold ladder

For descriptive scale only, report C0 prevalence at these fixed thresholds:

- >= +0.20%
- >= +0.40%
- >= +0.50%
- >= +0.75%
- >= +1.00%
- >= +1.50%
- >= +2.00%

These thresholds are fixed before execution.

Their purpose is to show the return distribution scale.

Do not create policies from them.

Do not search intermediate thresholds.

## 14. Negative-side distribution

Because opportunity prevalence alone can hide downside, also report C0
prevalence at:

- <= -0.20%
- <= -0.40%
- <= -0.50%
- <= -0.75%
- <= -1.00%
- <= -1.50%
- <= -2.00%

Report separately by horizon/year.

No stop-loss inference may be drawn from these thresholds.

## 15. Economic asymmetry

For each horizon report:

- mean positive C0 return
- mean negative C0 return
- total positive gross contribution
- total negative gross contribution
- positive/negative contribution ratio
- fraction of total positive contribution supplied by GROSS40 trades
- fraction supplied by GROSS50 trades

Repeat the contribution analysis under:

- DESIGN_BNB
- C_BASE

using the same C0-defined opportunity groups.

## 16. Opportunity concentration

For each horizon and hurdle, among hurdle-positive trades report:

- top 1 trade share of gross positive contribution
- top 5 trades share
- top 10 trades share
- top 1% share
- top 5% share
- top 10% share
- number of trades required to explain 50% of positive contribution

Also report entry-month concentration:

- number of months containing at least one hurdle-positive trade
- hurdle prevalence by month
- gross contribution by month

Do not remove influential trades or months.

## 17. Year stability

For every horizon and both hurdles compare 2024 versus 2025:

- prevalence
- mean gross opportunity return
- mean whole-population C0 return
- mean DESIGN_BNB return
- mean C_BASE return

Do not pool years as a substitute for year stability.

## 18. Symbol stability

For every symbol and horizon report:

- valid count
- mean C0 return
- DESIGN_BNB mean
- C_BASE mean
- GROSS40 prevalence
- GROSS50 prevalence
- GROSS40 net C_BASE mean
- GROSS50 net C_BASE mean

No symbol-specific strategy may be inferred or tested in C29.

## 19. Dependence-aware uncertainty

Use:

### Whole-trade bootstrap
- 2,000 replicates
- fixed PCG64 seed
- complete trades
- preserve all horizon outcomes together

### UTC entry-calendar-month bootstrap
- 2,000 replicates
- fixed PCG64 seed
- complete trades attached to entry month

For each horizon report 95% intervals for:

- mean C0 return
- mean DESIGN_BNB return
- mean C_BASE return
- GROSS40 prevalence
- GROSS50 prevalence

Report separately for:

- 2024
- 2025
- pooled population

No snapshot bootstrap.

## 20. MFE boundary

MFE may be reported only as continuity context from prior frozen artifacts.

Do NOT recompute an MFE-derived opportunity definition.

C29's economic opportunity is defined solely from executable fixed-horizon
returns.

Explicitly state:

    MFE is retrospective and is not used as a C29 target, policy, or
    opportunity label.

## 21. C29 interpretation

C29 must NOT choose a model or strategy.

It must answer these descriptive questions:

1. At 3h/6h/12h/24h, how often do actual E1 trades achieve at least 40 bp
   and 50 bp gross executable return?

2. Are those opportunities present in both 2024 and 2025?

3. Are they broadly distributed across trades/months/symbols or concentrated
   in a few episodes?

4. When those gross opportunities occur, do they remain economically
   meaningful after DESIGN_BNB and C_BASE costs?

5. Does the whole E1 population remain negative after realistic costs even
   though a meaningful opportunity subset exists?

6. Is there enough economic variation to justify a later prospective
   entry-state prediction study?

Question 6 remains a research recommendation, not a policy authorization.

## 22. Frozen final classification

Return exactly one diagnostic classification:

### OPPORTUNITY_VARIATION_PRESENT

Use if ALL are true:

1. GROSS40 opportunities occur in both 2024 and 2025 at at least two of the
   four frozen horizons;
2. GROSS50 opportunities occur in both years at at least one frozen horizon;
3. opportunity-positive trades remain positive on average under C_BASE at
   the corresponding horizons;
4. opportunity contribution is not confined to one entry month or one symbol;
5. at least one dependence-aware prevalence interval in each year has a
   positive lower bound above zero, confirming nonzero opportunity prevalence.

This classification means only:

    economically meaningful fixed-horizon opportunities exist often enough
    to justify asking whether entry-time state predicts them.

It does NOT mean the strategy is profitable.

### OPPORTUNITY_TOO_SPARSE_OR_FRAGILE

Use otherwise.

This means the current E1 population does not provide sufficiently stable
fixed-horizon opportunity mass to justify a new opportunity-selection model
without reconsidering the entry family or strategy design.

Do not alter these predicates after results.

## 23. No horizon winner

Regardless of classification, C29 must explicitly state:

    No preferred holding horizon was selected.

Even if one horizon has the highest return or prevalence, it remains a
descriptive result.

A later experiment would need a separate prospective rationale for any
specific prediction horizon.

## 24. Prohibited analyses

Do NOT:

- fit any predictive model
- construct entry-time features for classification
- choose a best horizon
- optimize threshold
- optimize holding time
- test H1/H2/H4/H8/H18/H36/H48
- use MFE as a label
- build an exit policy
- alter E1
- alter the 24h refractory rule
- select symbols
- select months
- lower costs to make results work
- optimize P&L or Sharpe
- access 2026
- start C30

## 25. Required artifacts

Write to:

artifacts/c29_opportunity_prevalence/

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- execution_timing.json
- cost_scenarios.json
- horizon_coverage.json
- fixed_horizon_returns.json
- full_population_economics.json
- opportunity_prevalence.json
- opportunity_magnitude.json
- opportunity_cost_survival.json
- threshold_ladder_positive.json
- threshold_ladder_negative.json
- contribution_asymmetry.json
- opportunity_concentration.json
- entry_month_results.json
- year_stability.json
- symbol_stability.json
- whole_trade_bootstrap.json
- calendar_month_bootstrap.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid raw 1-minute dumps.

## 26. Required tests

Add focused tests for:

- exact 2,199 entry reconciliation
- exact E1 hash
- exact 2024/2025 counts
- exact symbol counts
- H3/H6/H12/H24 only
- no other horizons
- exact fixed-horizon timing convention
- no synthetic fill
- no 2026 data
- exact C0/C_BASE/C_S5/C_S10
- exact DESIGN_BNB definition
- GROSS40 exact boundary
- GROSS50 exact boundary
- C0-only opportunity labels
- labels unchanged across cost scenarios
- positive threshold ladder
- negative threshold ladder
- year decomposition
- symbol decomposition
- concentration accounting
- whole-trade bootstrap determinism
- calendar-month bootstrap determinism
- no MFE-derived label
- no predictive model
- no policy simulation
- no best-horizon selection

Run focused tests.

Run the full repository suite once if scientific/runtime code changes.

## 27. Governance

Do NOT:

- modify C7-C28 scientific behavior
- modify STRATEGY_DESIGN_REVIEW.md
- modify this contract
- stage implementation/results
- commit implementation/results
- push
- access 2026
- start C30

The C29 contract itself may be committed before implementation.

## 28. Final report

Report:

1. contract SHA
2. population reconciliation
3. exact execution timing
4. cost scenarios including DESIGN_BNB
5. valid population by horizon
6. H3 whole-population economics
7. H6 whole-population economics
8. H12 whole-population economics
9. H24 whole-population economics
10. GROSS40 prevalence by horizon/year
11. GROSS50 prevalence by horizon/year
12. cost survival of GROSS40 opportunities
13. cost survival of GROSS50 opportunities
14. positive threshold ladder
15. negative threshold ladder
16. positive/negative contribution asymmetry
17. opportunity concentration
18. entry-month distribution
19. year stability
20. symbol stability
21. whole-trade uncertainty
22. calendar-month uncertainty
23. explicit MFE limitation
24. whether opportunity variation is economically meaningful
25. exact frozen classification:
       OPPORTUNITY_VARIATION_PRESENT
       or OPPORTUNITY_TOO_SPARSE_OR_FRAGILE
26. whether a later entry-state prediction study is justified
27. explicit statement that no horizon was selected
28. limitations
29. artifact hash verification
30. focused test result
31. full-suite result
32. git diff --check
33. git status --short
34. confirmation no model/threshold/horizon/policy search
35. confirmation no P&L optimization
36. confirmation no 2026 access
37. confirmation nothing implementation-related staged/committed/pushed
38. confirmation C30 not started

STOP after C29.
