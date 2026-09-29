# C26 Q1 Action-Semantics Diagnostic Contract

Status: prospectively specified before C26 analysis.

## 1. Purpose

C23 established that current frozen C9 p_t2 adds incremental predictive
information beyond elapsed time and observable return from entry.

C24 established that frozen DELTA_LIQ_5 S+C9 probabilities order realized
executable forward value.

C25 tested one frozen sequential policy:

    first honest pre-T2 Q1
        ->
    irreversible full exit at next valid 1-minute open
        ->
    otherwise reassess
        ->
    P0 fallback

C25 produced:

    WEAK_POLICY_ECONOMIC_SIGNAL

with positive full-population point estimate but:
- slightly negative 2024 honest validation result;
- positive 2025 result;
- uncertainty spanning zero;
- meaningful surrendered profitable tail.

C26 diagnoses why.

C26 asks:

1. Was Q1 actually economically unfavorable in absolute terms,
   or merely less favorable than higher probability bands?

2. Did first-Q1 policy triggers have materially different economics from
   the all-Q1 snapshot population characterized in C24?

3. Did C25 convert a short-horizon DELTA_LIQ_5 warning into an action whose
   economic horizon was too long, by permanently abandoning trades that
   later recovered before P0?

4. Was C25's small positive result broadly distributed or concentrated in
   a small number of trades/months?

C26 is diagnostic only.

No new model.
No threshold change.
No policy change.
No horizon search.
No P&L optimization.
No 2026 access.

## 2. Frozen scope

Use only the exact C25 policy/action population and exact frozen:

- DELTA_LIQ_5 S+C9 score
- C24 Q1 assignment
- C25 first-Q1 decisions
- C25 execution timing
- C25/P0 paired outcomes
- C20 DELTA_LIQ_5 target/accounting
- C_BASE as primary cost scenario

Do NOT inspect alternate:
- probability bands;
- raw thresholds;
- target horizons;
- model families;
- persistence rules.

No DELTA_LIQ_15/30/60/Event policy diagnosis.

## 3. Evaluation populations

Preserve exact C25 honesty separation.

Primary diagnostic populations:

### 2024
Only honest fold_B validation policy states/trades.

### 2025
Only untouched honest policy-evaluable states/trades.

### Full population
Use all 2,199 original trades only for C25-P0 contribution/concentration
diagnostics.

Do not create model diagnostics from 2024 training-only trades.

## 4. Frozen decision state

C25 policy state is the completed eligible pre-T2 five-minute state t.

At each first-Q1 trigger record:

- trade_id
- symbol
- entry timestamp
- trigger timestamp
- frozen S+C9 probability
- frozen Q1 boundary
- observable current return from entry
- elapsed minutes from entry
- executable EXIT_NOW reference
- corresponding DELTA_LIQ_5 target
- canonical P0 paired outcome

No future information may be used as a decision feature.

Future outcomes are evaluation-only diagnostics.

## 5. Check 1 — Absolute Q1 economics

Using the exact C24 DELTA_LIQ_5 Q1 assignment, report the absolute economics
of all honest Q1 snapshots separately for:

- 2024 fold_B validation
- 2025 untouched evaluation

For all-Q1 snapshots report:

- snapshot count
- trade count
- weighted positive rate:
      P(DELTA_LIQ_5 > 0)
- weighted exact-zero rate
- weighted negative rate
- weighted mean DELTA_LIQ_5
- weighted median DELTA_LIQ_5
- weighted p10/p25/p75/p90
- weighted mean positive value
- weighted mean negative value
- weighted positive contribution
- weighted negative contribution
- weighted net contribution

Use exact C23/C24 whole-trade weighting.

Primary question:

    Is mean DELTA_LIQ_5 in Q1 actually below zero?

Do not infer action usefulness merely from Q1 being worse than Q2-Q5.

## 6. Absolute-Q1 uncertainty

Use frozen observations only.

Compute paired/dependence-aware uncertainty for all-Q1 absolute mean
DELTA_LIQ_5 using:

### A. Calendar-month block bootstrap
- 2,000 replicates
- fixed PCG64 seed
- UTC entry month
- whole trades attached

### B. Whole-trade bootstrap
- 2,000 replicates
- fixed PCG64 seed
- all snapshots attached to sampled trades

Report 95% intervals for:

- mean DELTA_LIQ_5
- positive rate

No snapshot-level bootstrap.

## 7. Check 2 — All-Q1 versus first-Q1 trigger states

Construct two frozen groups for each evaluation year:

A. ALL_Q1
    every honest DELTA_LIQ_5 Q1 snapshot

B. FIRST_Q1
    exactly the first C25 Q1 trigger state per policy-triggered trade

Do not include later Q1 states in FIRST_Q1.

Compare:

- snapshot/trade count
- mean/median DELTA_LIQ_5
- positive rate
- mean S+C9 probability
- median S+C9 probability
- elapsed minutes since entry
- observable return from entry
- weighted positive contribution
- weighted negative contribution
- weighted net contribution

Primary first-trigger selection quantities:

    Delta_first_all_mean
      = mean_DELTA_LIQ_5(FIRST_Q1)
        - mean_DELTA_LIQ_5(ALL_Q1)

    Delta_first_all_positive_rate
      = positive_rate(FIRST_Q1)
        - positive_rate(ALL_Q1)

Negative values mean first-trigger states are economically worse than the
all-Q1 snapshot population.

## 8. First-trigger selection uncertainty

For the FIRST_Q1 versus ALL_Q1 comparison use dependence-aware resampling.

Primary:
- UTC entry-calendar-month blocks
- 2,000 PCG64 replicates

Robustness:
- whole-trade bootstrap
- 2,000 PCG64 replicates

Preserve group construction within every replicate.

Report 95% intervals for:

- Delta_first_all_mean
- Delta_first_all_positive_rate

Do not independently sample snapshots.

## 9. Check 3 — Short-horizon versus lifecycle value at first Q1

At each honest FIRST_Q1 trigger t define two retrospective evaluation values.

### A. Frozen selected-model endpoint value

    V5(t) = DELTA_LIQ_5(t)

This is the exact target whose sign/probability the frozen S+C9 model was
trained to characterize.

Interpretation:

    value of remaining invested to min(t+5m, frozen lifecycle terminal)
    versus executable exit now

### B. Canonical-lifecycle value

Define:

    VP0(t)
      = P0_FINAL_NET(t) - EXIT_NOW_NET(t)

where:

- EXIT_NOW_NET(t) uses the exact C20/C25 executable exit-now accounting at
  the same first-Q1 trigger;
- P0_FINAL_NET(t) is the same trade's frozen canonical P0 terminal net value.

Use the same cost convention, with C_BASE primary.

VP0 is evaluation-only.

Do NOT use VP0 as a predictor or policy feature.

## 10. First-Q1 horizon-mismatch quadrants

Assign every honest FIRST_Q1 trigger to exactly one diagnostic quadrant:

### Q_A
    V5 < 0 and VP0 < 0

Label:
    SHORT_BAD_LIFECYCLE_BAD

### Q_B
    V5 < 0 and VP0 >= 0

Label:
    SHORT_BAD_LIFECYCLE_RECOVERS

### Q_C
    V5 >= 0 and VP0 < 0

Label:
    SHORT_OK_LIFECYCLE_BAD

### Q_D
    V5 >= 0 and VP0 >= 0

Label:
    SHORT_OK_LIFECYCLE_GOOD

Exact zero belongs to the >= 0 side for these diagnostic quadrants.

For each quadrant report:

- trade count
- share of FIRST_Q1 triggers
- mean V5
- median V5
- mean VP0
- median VP0
- C25-P0 paired P&L contribution
- C25-P0 paired mean return difference
- number of C25 wins/losses/ties
- canonical P0 positive-return cohort composition

These are retrospective diagnostics only.

## 11. Horizon-mismatch primary quantities

For each year report:

- fraction with V5 < 0
- fraction with VP0 < 0
- fraction in SHORT_BAD_LIFECYCLE_RECOVERS
- fraction in SHORT_BAD_LIFECYCLE_BAD

Also report economic contribution of:

    SHORT_BAD_LIFECYCLE_RECOVERS

to:

- surrendered upside
- total C25-P0 loss contribution

Primary horizon-mismatch diagnostic:

A meaningful mismatch exists if:

- V5 identifies unfavorable short-horizon continuation;
- but a substantial subset of those states has VP0 >= 0;
- and that recovery quadrant materially explains C25 surrendered upside.

No threshold for "substantial" may be optimized after seeing results.
Report quantities directly and use the frozen interpretation rules below.

## 12. Link to C25 avoided-loss/surrendered-upside labels

For all MODEL_EXIT_EXECUTED C25 trades reconcile exactly to C25:

- AVOIDED_LOSS
- PRESERVED_GAIN
- SURRENDERED_UPSIDE
- DEEPENED_LOSS
- TIE

Cross-tab these labels against the four V5/VP0 quadrants.

Report:

- counts
- paired P&L contributions

This must reconcile to C25 totals.

## 13. Check 4 — Trade-level concentration

Using all 2,199 paired C25-P0 trade differences under C_BASE:

Separate positive and negative contribution distributions.

For positive paired contributions report:

- total positive contribution
- top 1 trade share
- top 5 trades share
- top 10 trades share
- top 20 trades share
- top 1% trade share
- top 5%
- top 10%
- top 20%

For negative paired contributions report the same using absolute negative
contribution.

Also report:

- Gini/concentration statistic if existing project utility is available
- number of trades required to explain 50% of total positive contribution
- number of trades required to explain 50% of total negative contribution

Do not remove influential trades.

## 14. Entry-month concentration

Group all original trades by UTC entry calendar month.

For each month report:

- original trade count
- covered trade count
- model exit count
- C25-P0 P&L difference
- mean paired return difference
- positive-contribution trade count
- negative-contribution trade count

No month selection.

## 15. Leave-one-entry-month-out sensitivity

For every unique UTC entry calendar month m:

- remove all trades whose entry month is m;
- recompute full-population C_BASE:
    - total C25-P0 P&L difference
    - mean paired return difference

Report:

- minimum leave-one-month-out result
- maximum result
- number of omitted months producing negative total difference
- number producing positive total difference
- identity of months associated with extrema for diagnosis only

Do NOT use this to select/exclude months.

## 16. Year-specific diagnosis

All core checks must be reported separately for:

- 2024 honest validation
- 2025 untouched evaluation

Do not use pooled results to override disagreement between years.

The full 2,199 population may be used only for policy contribution and
concentration accounting.

## 17. Symbol diagnostics

For each symbol, using honest FIRST_Q1 triggers, report:

- trigger count
- mean V5
- mean VP0
- SHORT_BAD_LIFECYCLE_RECOVERS fraction
- C25-P0 paired contribution

Symbols:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

Do not fit symbol-specific models.
Do not alter policy by symbol.
Do not treat symbols as independent replications.

## 18. No alternate target inspection

Do NOT repeat these diagnostics for:

- DELTA_LIQ_15
- DELTA_LIQ_30
- DELTA_LIQ_60
- DELTA_LIQ_EVENT

C26 diagnoses the exact DELTA_LIQ_5 decision semantics selected prospectively
for C25.

No retrospective horizon selection.

## 19. Frozen continue-or-stop decision

C26 MUST end with exactly one:

    CONTINUE_POLICY_RESEARCH

or:

    STOP_THIS_EXIT_LINE

No third ambiguous outcome.

### CONTINUE_POLICY_RESEARCH

Use only if C26 establishes at least one coherent explanation below and the
pattern is not solely a 2025 artifact.

#### Path A — Genuine first-Q1 short-horizon adversity

Require:

1. FIRST_Q1 mean V5 < 0 in both 2024 and 2025;
2. dependence-aware uncertainty is directionally supportive and does not show
   clear evidence of positive first-Q1 mean V5 in either year;
3. first-Q1 selection does not reverse the all-Q1 economic interpretation;
4. C25 benefit/harm is not dependent on only a tiny number of trades or one
   entry month.

Interpretation:

The warning state itself is economically adverse over the selected five-minute
decision horizon. C25 weakness then plausibly concerns action design rather
than absence of signal.

#### Path B — Coherent action-horizon mismatch

Require:

1. FIRST_Q1 V5 is materially worse than neutral/zero or clearly worse than
   the broader all-Q1 population in both years;
2. SHORT_BAD_LIFECYCLE_RECOVERS exists materially in both years;
3. that quadrant explains a meaningful share of C25 surrendered-upside loss;
4. the same qualitative pattern occurs in both years;
5. contribution/concentration diagnostics do not show the entire explanation
   depends on one or two isolated trades/months.

Interpretation:

The five-minute score may correctly identify short-horizon weakness, but
permanent liquidation mismatches the prediction horizon.

No new policy is authorized by this finding.

### STOP_THIS_EXIT_LINE

Use if neither Path A nor Path B is supported.

Examples include:

- all-Q1 and first-Q1 V5 are still positive on average;
- first-Q1 states lose the C24 economic ordering;
- V5/VP0 quadrant structure is unstable across years;
- surrendered upside is not explained by a coherent recovery quadrant;
- C25 apparent benefit depends heavily on a few trades/months;
- 2024 and 2025 mechanisms materially disagree.

STOP means:

Do not proceed to:
- Q1 persistence tuning;
- alternate Q1 thresholds;
- alternate horizon models;
- additional Q1 gating features;
- rescue-model fitting

within this exit line.

A future project may reconsider exit formulation from a different scientific
premise, but not by incremental tuning of C25.

## 20. Important interpretation boundary

CONTINUE_POLICY_RESEARCH does NOT mean:

- C25 is validated;
- Q1 exit should be deployed;
- a new policy is authorized;
- a threshold should be tuned;
- a new model should be fitted immediately.

It means only that the C25 weakness has a coherent, stable mechanism worth
researching further.

STOP_THIS_EXIT_LINE means the current Q1/S+C9 sequential-exit line has failed
to establish enough coherent actionable structure to justify further local
tuning.

## 21. Required artifacts

Write to:

artifacts/c26_q1_action_semantics/

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- first_q1_reconciliation.json
- all_q1_absolute_value_2024.json
- all_q1_absolute_value_2025.json
- all_q1_bootstrap.json
- first_vs_all_q1_2024.json
- first_vs_all_q1_2025.json
- first_vs_all_bootstrap.json
- first_q1_v5_vp0_2024.json
- first_q1_v5_vp0_2025.json
- horizon_mismatch_quadrants.json
- c25_label_quadrant_crosstab.json
- trade_concentration.json
- entry_month_results.json
- leave_one_month_out.json
- symbol_diagnostics.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid large redundant snapshot dumps.

## 22. Required reconciliation

Before interpretation verify:

- exact C25 2,199 trade population
- exact C25 honest covered trade count
- exact C25 first-Q1 trade/exit count
- exact Q1 boundaries and tie convention
- exact C25 paired P&L totals
- exact avoided-loss/surrendered-upside totals
- exact C25 yearly totals

If material reconciliation fails:

    STOP with INSUFFICIENT_RECONCILIATION

Do not continue diagnostic interpretation.

## 23. Tests

Add focused tests for:

- exact C25 population reproduction
- exact first-Q1 reconstruction
- first-Q1 means one trigger per trade
- all-Q1 includes all honest Q1 snapshots
- no 2024 training leakage
- V5 equals frozen DELTA_LIQ_5
- VP0 uses same trigger EXIT_NOW reference
- exact-zero quadrant handling
- quadrant exclusivity/exhaustiveness
- C25 label cross-tab reconciliation
- whole-trade weighting
- all-Q1 bootstrap
- first-vs-all bootstrap
- trade concentration accounting
- entry-month grouping
- leave-one-month-out deterministic results
- no alternate horizon use
- no new model fitting
- no threshold/policy changes
- no 2026 access

Run focused tests.

Run full repository suite once if scientific/runtime code changes.

## 24. Governance

Do NOT:

- modify C7-C25 scientific behavior
- alter C25 policy
- fit any new predictive model
- recalibrate probabilities
- search thresholds
- search probability bands
- add persistence
- use alternate horizons
- simulate alternate policies
- optimize P&L
- access 2026
- start C27
- stage, commit, or push implementation/results

The contract itself may be committed before implementation.

## 25. Final report

Report:

1. contract SHA
2. C25 reconciliation status
3. exact first-Q1 population
4. all-Q1 absolute mean/median V5 for 2024
5. all-Q1 absolute mean/median V5 for 2025
6. all-Q1 positive rates
7. absolute-Q1 uncertainty
8. first-Q1 mean/median V5 for 2024
9. first-Q1 mean/median V5 for 2025
10. FIRST_Q1 vs ALL_Q1 mean differences
11. FIRST_Q1 vs ALL_Q1 positive-rate differences
12. first-vs-all uncertainty
13. mean/median VP0 at first Q1
14. V5/VP0 quadrant counts and shares
15. SHORT_BAD_LIFECYCLE_RECOVERS share by year
16. quadrant C25-P0 contributions
17. C25 avoided-loss/surrendered-upside cross-tab
18. trade-level benefit concentration
19. trade-level harm concentration
20. entry-month contributions
21. leave-one-month-out sensitivity
22. symbol diagnostics
23. whether Q1 was absolutely negative or merely relatively weak
24. whether first-trigger selection changed C24's interpretation
25. whether action-horizon mismatch explains surrendered upside
26. whether C25 benefit was broad or episode-concentrated
27. exact frozen decision:
       CONTINUE_POLICY_RESEARCH
       or STOP_THIS_EXIT_LINE
28. which continuation path, if any, was satisfied
29. limitations
30. artifact hash verification
31. focused/full test results
32. git diff --check
33. git status --short
34. confirmation no new model/threshold/persistence/horizon/policy search
35. confirmation no P&L optimization
36. confirmation no 2026 access
37. confirmation nothing staged/committed/pushed
38. confirmation C27 not started

STOP after C26.
