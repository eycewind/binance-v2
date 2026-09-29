# C25 Frozen Q1 Sequential Exit Policy Contract

Status: prospectively specified before C25 implementation or policy evaluation.

## 1. Purpose

C23 established that current frozen C9 p_t2 adds incremental predictive
information beyond elapsed time and observable return from entry.

C24 established that frozen S+C9 probabilities order realized executable
forward liquidation value across all five targets.

C25 performs the first prospective sequential policy experiment.

Question:

"Does a single frozen low-probability sequential exit rule improve full-
population lifecycle economics relative to canonical P0?"

C25 tests exactly one model-driven policy.

No threshold search.
No horizon search.
No model search.
No policy-family search.

## 2. Frozen decision score

Use only the frozen C23/C24 S+C9 model for:

    DELTA_LIQ_5

Reason:

C25 reassesses approximately every five minutes. DELTA_LIQ_5 therefore
matches the one-step continuation decision:

    exit now
    versus
    remain invested until the next eligible reassessment interval

The 5-minute score is selected by decision semantics, NOT because of observed
C24 performance.

Do NOT use:

- DELTA_LIQ_15
- DELTA_LIQ_30
- DELTA_LIQ_60
- DELTA_LIQ_EVENT

for policy decisions.

They may not be used as policy alternatives or controls.

## 3. Frozen policy

At each honestly eligible completed pre-T2 five-minute state t:

1. Compute/reproduce the frozen DELTA_LIQ_5 S+C9 probability using the exact
   C23 procedure.

2. Apply the exact corresponding C24 training-derived Q1 assignment rule.

3. If the state is in Q1:
   - create an irreversible full-position exit decision;
   - execute only at the next valid executable 1-minute open strictly after
     the completed decision state, subject to lifecycle precedence.

4. If the state is not in Q1:
   - take no action;
   - reassess at the next honestly eligible five-minute state.

5. If the position reaches frozen T2 before any model exit executes:
   - permanently stop C25 model-driven exit decisions for that trade;
   - thereafter follow canonical P0.

6. If no C25 exit executes:
   - canonical P0 remains the fallback exit.

One successfully executed C25 exit closes 100% of the position.

No re-entry.
No partial exits.
No scale-out.
No cancellation because later probability changes.
No discretionary override.

## 4. Frozen Q1 boundary

Use the exact C24 DELTA_LIQ_5 S+C9 Q1 assignment convention.

For 2024 fold_B policy evaluation:

- use the Q1 boundary derived only from the corresponding C23/C24 fold_B
  training predictions.

For 2025 policy evaluation:

- use the Q1 boundary derived only from the complete 2024 training
  predictions used for the frozen 2025 S+C9 model.

Do NOT derive boundaries from policy evaluation outcomes.

Do NOT derive boundaries from validation probability quantiles.

Do NOT retune Q1.

Do NOT convert Q1 into an independently chosen numeric threshold.

Preserve C24 behavior that identical probability values are never split
across bins.

Before policy simulation, record:

- numeric boundary/boundaries;
- exact comparison/tie convention;
- source artifact hashes;
- reproduced Q1 membership counts.

If C24 Q1 membership cannot be reproduced exactly, STOP with:

    INSUFFICIENT_Q1_REPRODUCTION

## 5. Decision timing

Decision state t occurs only after completion of the frozen five-minute state
bar.

All model information must be available at or before t.

Signal:

    completed five-minute state
        ->
    frozen S+C9 probability
        ->
    frozen Q1 assignment
        ->
    irreversible EXIT decision if Q1
        ->
    next valid one-minute open strictly after t

The execution price must never be used to form the decision.

No same-bar execution.

No interpolation.

No synthetic fill.

## 6. Execution convention

Use the frozen repository execution convention/helper already used for
next-open executable accounting wherever scientifically compatible.

A model exit may execute only at a valid next 1-minute open that exists in the
frozen market data.

Record:

- decision timestamp;
- candidate execution timestamp;
- actual execution timestamp;
- execution price;
- execution status.

If required execution data are missing or invalid:

- do not assume a fill;
- record the failed/unavailable execution opportunity;
- leave the position open;
- allow reassessment at a later honestly eligible state only if still pre-T2.

## 7. Lifecycle precedence

Frozen lifecycle events have precedence over a not-yet-executed model exit.

The model exit is valid only if the trade remains eligible and pre-T2 at the
candidate fill.

If frozen T2 or P0 occurs before the candidate model fill:

    lifecycle event wins.

If a frozen lifecycle event and candidate model fill coincide at the same
execution boundary:

    lifecycle event wins.

If P0 wins:

    execute canonical P0.

If T2 wins:

    cancel C25 model exit eligibility permanently;
    continue under canonical P0 thereafter.

Record every precedence case.

## 8. Eligible policy states

C25 model actions are allowed only for honestly scored pre-T2 states that
would have been available live.

Unscored states:

- cause no model-driven action;
- do not receive inferred probabilities;
- do not receive imputed policy scores;
- remain open under the existing lifecycle;
- may be reassessed later if a genuinely eligible honest state becomes
  available.

## 9. Honest evaluation populations

The original frozen entry population is:

    2,199 trades

Every original entry MUST appear in full-population accounting.

### 2024

Only the honest C23/C24 fold_B validation population may receive model-driven
C25 actions.

Expected fold_B:

Training:
- 7,970 scored rows
- 256 trades

Validation:
- 8,631 scored rows
- 267 trades

The 256 fold_B training trades are NOT policy-evaluable.

For those training trades:

    C25 outcome = canonical P0

They remain in full-population accounting.

Do NOT generate in-sample policy actions for them.

Do NOT fabricate fold_A.

### 2025

Use the frozen S+C9 procedure fitted once on the complete 2024 scored training
population.

Expected untouched 2025 evaluation population:

- 39,616 scored rows
- 1,087 trades

Only honestly eligible 2025 states may generate model actions.

### Other original trades

Any original trade without honest policy-eligible model coverage receives no
C25 model action and follows canonical P0.

## 10. Population reporting

Report at least two views.

### A. Full population — PRIMARY

All 2,199 original frozen entries.

Every trade paired with its canonical P0 outcome.

### B. Honest model-covered evaluation population

Only trades with at least one honestly policy-eligible C25 state in:

- 2024 fold_B validation;
- untouched 2025 evaluation.

This is secondary diagnostic reporting.

Do not replace the full-population result with covered-only results.

## 11. Canonical baseline

Baseline:

    P0

Use the exact frozen canonical P0 lifecycle and execution accounting already
established in prior experiments.

Do not redefine P0.

Every C25 trade must be paired with the same trade's canonical P0 outcome.

## 12. Costs

Evaluate the same frozen cost scenarios:

- C0
- C_BASE
- C_S5
- C_S10

C_BASE is primary.

Use actual executed notional under the existing cost convention.

Do not introduce new cost assumptions.

## 13. Primary economic estimand

For each trade i:

    DELTA_POLICY_i
      = C25_Q1_EXIT_NET_i - P0_NET_i

Primary full-population statistic:

    mean_i(DELTA_POLICY_i)

under C_BASE.

Also report:

- median paired difference;
- total P&L difference;
- win/loss/tie count versus P0;
- fraction of trades changed by C25.

Every unchanged/fallback trade contributes exactly zero paired difference.

## 14. Secondary cost robustness

Repeat the exact paired comparison under:

- C0
- C_S5
- C_S10

No cost scenario may be selected as preferred.

C_BASE remains primary.

## 15. Policy event accounting

Every original trade must fall into an auditable policy path category.

At minimum report:

- MODEL_EXIT_EXECUTED
- ELIGIBLE_NEVER_Q1
- Q1_SIGNAL_TERMINAL_PRECEDENCE
- Q1_SIGNAL_FILL_UNAVAILABLE
- REACHED_T2_BEFORE_MODEL_EXIT
- 2024_TRAINING_ONLY_FALLBACK
- NO_HONEST_MODEL_COVERAGE
- OTHER_P0_FALLBACK if needed, with exact definition

Categories must be deterministic and mutually interpretable.

Also report:

- number of Q1 decisions;
- number of unique trades with Q1;
- number of executed exits;
- time from entry to first Q1;
- time from Q1 signal to actual fill;
- number of repeated reassessments before first Q1;
- number of failed execution opportunities.

## 16. No persistence requirement

A single honestly observed Q1 state is sufficient.

Do NOT require:

- two consecutive Q1 states;
- three consecutive Q1 states;
- minimum Q1 duration;
- probability hysteresis;
- recovery confirmation.

These would introduce new policy parameters.

## 17. Irreversibility

Once a valid Q1 decision has been made:

- later model probabilities cannot cancel it;
- later state improvement cannot override it.

The decision remains pending until:

A. valid next-open execution occurs; or
B. frozen lifecycle precedence invalidates it.

If execution is unavailable because of missing/invalid market data and no
lifecycle event has occurred, the failed action does NOT remain indefinitely
pending. Record failure and permit later honest reassessment.

## 18. Right-tail protection diagnostics

C13 showed that plausible early exits can destroy profitable right-tail
trades.

C25 MUST therefore decompose paired policy impact by canonical P0 outcome
cohorts.

At minimum report:

- P0 return >= +0.5%
- P0 return >= +1%
- P0 return >= +2%
- P0 return >= +3%
- P0 return >= +5%
- P0 return < 0

For every cohort report:

- trade count;
- C25 exit count;
- P0 P&L;
- C25 P&L;
- paired P&L difference;
- mean paired return difference.

These are diagnostics only.

Do not redesign the policy after observing them.

## 19. Lifecycle decomposition

Report separately for original frozen lifecycle classes:

- T2_FIRST
- P0_FIRST

For each report:

- count;
- C25 exits;
- unchanged trades;
- P0 P&L;
- C25 P&L;
- paired difference.

Do not condition the policy on eventual class.

Eventual class is evaluation-only.

## 20. Avoided-loss versus surrendered-upside decomposition

For trades with MODEL_EXIT_EXECUTED classify the realized paired outcome
descriptively as:

- AVOIDED_LOSS:
    C25 beats P0 and canonical P0 return is negative

- PRESERVED_GAIN:
    C25 beats P0 and canonical P0 return is nonnegative

- SURRENDERED_UPSIDE:
    C25 underperforms P0 and canonical P0 return is positive

- DEEPENED_LOSS:
    C25 underperforms P0 and canonical P0 return is nonpositive

- TIE

Report counts and P&L contributions.

These labels are retrospective diagnostics only and may never be policy
features.

## 21. Time decomposition

Report paired policy results by:

- 2024 policy-evaluable validation
- 2025 untouched evaluation
- full 2,199-trade population

Do not pool years as a substitute for year stability.

Also report calendar-month paired contributions without choosing favorable
months.

## 22. Symbol decomposition

For:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

report:

- original trade count;
- policy-covered trade count;
- model exit count;
- P0 P&L;
- C25 P&L;
- paired difference;
- mean paired return difference.

Do not create symbol-specific policies.

Do not treat five symbols as independent statistical replications.

## 23. Dependence-aware uncertainty

Required.

Primary uncertainty:

### Whole-trade paired bootstrap

- 2,000 replicates
- fixed PCG64 seed
- resample complete original trades
- preserve C25/P0 pairing
- all snapshots/events for a trade remain attached

Report 95% intervals for:

- mean paired return difference;
- total normalized paired return difference if used;
- model-covered mean paired difference.

### Calendar-month robustness

- 2,000 replicates
- fixed PCG64 seed
- group trades by UTC entry calendar month
- resample whole calendar-month blocks
- keep all symbols and trades in sampled months together
- preserve C25/P0 pairing

Report the same quantities.

No snapshot-level bootstrap.

## 24. Primary decision rule

Under C_BASE, classify the experiment as follows.

### POLICY_ECONOMIC_SIGNAL_SUPPORTED

Require:

1. full-population mean paired C25-P0 difference > 0;
2. 2024 honest policy-evaluable paired mean > 0;
3. 2025 untouched paired mean > 0;
4. whole-trade and calendar-month uncertainty are directionally supportive,
   with neither showing clear evidence of negative full-population effect;
5. result is not obviously driven by one symbol;
6. right-tail diagnostics do not show that gains arise only by sacrificing a
   disproportionately large profitable tail.

This does NOT authorize deployment.

### WEAK_POLICY_ECONOMIC_SIGNAL

Use if:

- full-population point estimate is positive but uncertainty materially
  includes zero;
- OR years disagree materially;
- OR model-covered results are positive but full-population effect is diluted
  or unstable;
- OR avoided-loss benefit is offset substantially by surrendered upside.

### NO_USEFUL_POLICY_ECONOMIC_SIGNAL

Use if:

- full-population paired result is nonpositive;
- OR untouched 2025 result is negative;
- OR uncertainty materially supports no improvement/worsening;
- OR right-tail surrender offsets the proposed benefit.

### INSUFFICIENT

Use if:

- frozen S+C9 score cannot be reproduced;
- Q1 boundary cannot be reproduced;
- execution timing cannot be established;
- population/P0 pairing fails;
- honest evaluation separation fails.

Do not alter these predicates after seeing results.

## 25. Important interpretation boundary

Even POLICY_ECONOMIC_SIGNAL_SUPPORTED means only that this exact frozen
historical policy produced a stable paired historical improvement.

It does NOT establish:

- live profitability;
- future profitability;
- optimality;
- best threshold;
- best horizon;
- best holding period;
- production readiness.

A later stage would be required for any deployment decision.

## 26. Prohibited analyses

Do NOT:

- evaluate Q2 exits;
- evaluate Q1+Q2 exits;
- try alternate percentile thresholds;
- try raw probability thresholds;
- require persistence;
- try event/15m/30m/60m scores;
- optimize exit delay;
- optimize fill convention;
- optimize P&L;
- optimize Sharpe;
- select symbols;
- select years/months;
- train another model;
- recalibrate probabilities;
- modify P0;
- access 2026;
- begin C26.

## 27. Required artifacts

Write to:

artifacts/c25_q1_sequential_exit/

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- honest_policy_population.json
- score_reproduction.json
- q1_boundary_reproduction.json
- decision_timing_audit.json
- execution_contract.json
- lifecycle_precedence_audit.json
- policy_path_counts.json
- policy_trade_ledger.json
- full_population_results.json
- covered_population_results.json
- yearly_results.json
- symbol_results.json
- lifecycle_class_results.json
- right_tail_results.json
- avoided_loss_surrendered_upside.json
- cost_robustness.json
- calendar_month_results.json
- whole_trade_bootstrap.json
- calendar_month_bootstrap.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

policy_trade_ledger.json must contain sufficient per-trade information to
reproduce the paired result, but avoid unnecessary large snapshot dumps.

## 28. Required per-trade ledger fields

At minimum:

- trade_id
- symbol
- entry timestamp
- evaluation status
- honest policy coverage status
- first eligible score timestamp if any
- first Q1 timestamp if any
- Q1 probability
- Q1 boundary provenance
- candidate fill timestamp
- actual model fill timestamp if executed
- execution price if executed
- precedence outcome
- policy path category
- frozen lifecycle class
- canonical P0 exit timestamp
- canonical P0 net return
- C25 exit timestamp
- C25 net return
- paired return difference
- P0 P&L
- C25 P&L
- paired P&L difference

Future/evaluation-only fields must remain clearly separated from decision
features.

## 29. Tests

Add focused tests for:

- exact 2,199 entry population
- exact C23/C24 DELTA_LIQ_5 S+C9 score reproduction
- exact C24 Q1 boundary reproduction
- exact tie handling
- sole policy score is DELTA_LIQ_5 S+C9
- no alternate target scores used
- 2024 training trades cannot receive policy actions
- fold_B validation honesty
- 2025 untouched honesty
- unscored state no-action behavior
- no inferred probabilities
- first Q1 triggers irrevocable exit decision
- no persistence requirement
- next valid 1m open strictly after decision state
- no same-bar fill
- terminal precedence
- tie precedence
- missing fill fail-closed behavior
- T2 disables later model exits
- P0 fallback
- one full irreversible exit
- no re-entry
- full-population inclusion
- paired P0 accounting
- cost accounting
- right-tail cohort accounting
- whole-trade bootstrap
- calendar-month bootstrap
- deterministic PCG64 output
- no 2026 access

Run focused tests.

Run full repository suite once if scientific/runtime code changes.

## 30. Governance

Do NOT:

- modify C7-C24 scientific behavior;
- modify this contract;
- stage implementation/results;
- commit implementation/results;
- push;
- access 2026;
- start C26.

The contract itself may be committed before implementation.

## 31. Final report

Report:

1. contract SHA
2. population reconciliation
3. honest model-action population
4. excluded/in-sample/fallback population counts
5. exact DELTA_LIQ_5 S+C9 score provenance
6. exact Q1 boundary and tie convention
7. score/boundary reproduction status
8. execution timing convention
9. lifecycle precedence convention
10. policy path counts
11. number of trades with Q1
12. number of executed exits
13. number of fallback P0 trades
14. C_BASE full-population P0 result
15. C_BASE full-population C25 result
16. C_BASE paired mean return difference
17. C_BASE total P&L difference
18. 2024 honest policy-evaluable result
19. 2025 untouched result
20. model-covered population result
21. C0/C_S5/C_S10 robustness
22. T2_FIRST/P0_FIRST decomposition
23. right-tail cohort results
24. avoided-loss/surrendered-upside decomposition
25. symbol results
26. calendar-month results
27. whole-trade bootstrap interval
28. calendar-month bootstrap interval
29. frozen classification
30. whether gains come from avoided losses, preserved gains, or tail surrender
31. limitations
32. implication for C26
33. artifact hash verification
34. focused test result
35. full-suite result
36. git diff --check
37. git status --short
38. confirmation no alternate threshold/persistence/horizon/model search
39. confirmation no P&L optimization
40. confirmation no 2026 access
41. confirmation nothing implementation-related staged/committed/pushed
42. confirmation C26 not started

STOP after C25.
