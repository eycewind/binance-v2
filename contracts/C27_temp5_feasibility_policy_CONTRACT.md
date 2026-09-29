# C27 Temporary Five-Minute Interruption Feasibility and Policy Contract

Status: prospectively specified before C27 implementation or evaluation.

## 1. Purpose

C26 established that first-Q1 states are genuinely adverse over the frozen
DELTA_LIQ_5 horizon in both 2024 and 2025, while a nontrivial subset later
recovers under the canonical lifecycle.

C25's permanent first-Q1 exit therefore may have mismatched the duration of
the action to the duration of the predictive target.

C27 tests one different hypothesis:

    A five-minute adverse-value signal may justify temporarily removing
    exposure for one matched decision interval, while allowing participation
    in later recovery.

C27 has two sequential stages:

    Stage A — cost-and-timing feasibility gate

    Stage B — one frozen temporary-exit-and-reentry policy

Stage B is allowed only if Stage A passes its prospectively frozen gate.

No threshold search.
No duration search.
No repeated-cycle search.
No re-entry-rule search.
No model search.
No horizon search.
No P&L optimization.

## 2. Frozen score and trigger

Use exactly the frozen C25 trigger:

- DELTA_LIQ_5 S+C9 score only
- exact C24/C25 training-derived Q1 boundary
- exact frozen tie convention
- first honest pre-T2 Q1 state only

No alternate target score may be inspected for policy design.

No alternate Q1 threshold.

No persistence requirement.

At most one temporary interruption per original trade.

## 3. Arms

C27 contains exactly three lifecycle arms:

### A. Canonical P0

Exact frozen canonical benchmark.

### B. Frozen C25 permanent exit

Exact frozen C25 policy outcome.

No recomputation or modification except exact reconciliation if required.

### C. TEMP5

One temporary interruption triggered by the first honest pre-T2 Q1 state,
subject to the frozen mechanics below.

No fourth arm.

## 4. Honest evaluation population

Preserve exact C25 honesty rules.

Original entry population:

    2,199 trades

Primary accounting includes all 2,199 trades.

Only honest policy-evaluable states may trigger TEMP5.

### 2024

Only C23/C24/C25 fold_B validation states may produce TEMP5 actions.

The 256 2024 training-only trades:
- receive no TEMP5 model action;
- remain canonical P0;
- remain in full-population accounting.

No fold_A reconstruction.

### 2025

Use the exact frozen C23/C24/C25 model and boundary derived from complete 2024
training.

Only untouched 2025 honest states may trigger TEMP5.

### Other trades

No honest trigger coverage:
- no TEMP5 action;
- canonical P0 fallback.

## 5. Trigger timestamp

Let t be the completed five-minute decision-state timestamp of the first honest
Q1 observation.

TEMP5 duration is anchored to t.

It is NOT anchored to the sell fill timestamp.

This is required because the underlying target is DELTA_LIQ_5 at state t.

## 6. Temporary interruption semantics

At first honest Q1 state t:

1. Create an irreversible temporary-exit decision.

2. Attempt to sell the full position at the next valid executable 1-minute
   open strictly after t, subject to frozen lifecycle precedence.

3. Define the interruption-end state as:

       t_reassess =
         first eligible completed five-minute decision-state timestamp
         satisfying timestamp >= t + 5 minutes

   using the same state timestamp semantics as the frozen architecture.

4. If the trade remains lifecycle-active and re-entry is permissible,
   attempt one full re-entry at the next valid executable 1-minute open
   strictly after t_reassess.

5. After successful re-entry:
   - no further TEMP5 model actions are allowed;
   - resume canonical lifecycle;
   - final exit remains canonical P0.

One interruption maximum per trade.

No repeated cycling.

## 7. Exit execution

The temporary sell:

    first valid 1-minute open strictly after t

subject to lifecycle precedence.

No same-bar fill.
No interpolation.
No synthetic fill.
No execution-price use in the signal.

If the sell fill is unavailable:

- TEMP5 action fails closed;
- record SELL_FILL_UNAVAILABLE;
- no later retry;
- remain under canonical P0.

Do NOT wait for another Q1.

## 8. Re-entry execution

If a valid temporary sell occurred and lifecycle remains active through the
re-entry decision:

    candidate re-entry =
      first valid 1-minute open strictly after t_reassess

One attempt only.

If re-entry fill is unavailable:

- record REENTRY_FILL_UNAVAILABLE;
- remain flat permanently;
- no retry;
- no synthetic fill.

This is part of the frozen candidate and may not be changed after results.

## 9. Lifecycle precedence while flat

Frozen lifecycle events retain precedence.

### P0 while flat

If canonical P0 terminal occurs before or at the candidate re-entry execution
boundary:

- do not re-enter;
- remain flat permanently;
- treat the temporary sell as the final economic exit.

### T2 while flat

If frozen T2 occurs before or at the candidate re-entry execution boundary:

- do not re-enter;
- remain flat permanently;
- no post-T2 TEMP5 policy is introduced.

The temporary interruption candidate ends in a permanent flat state.

### Same-boundary ties

If T2/P0 and candidate re-entry occur at the same execution boundary:

    lifecycle event wins

No re-entry.

## 10. Lifecycle after successful re-entry

Once successfully re-entered:

- no further Q1 decisions;
- no additional temporary exits;
- no persistence or recovery logic;
- follow canonical lifecycle to P0.

If T2 occurs later:
- follow the same canonical post-T2 lifecycle already frozen in P0.

C27 does not define a new post-T2 policy.

## 11. Position mechanics

TEMP5 uses:

- 100% sell
- 100% re-entry
- no partial exposure
- no scaling
- no rebalancing
- no discretionary override

After re-entry, position quantity must be determined using the frozen cash/value
resulting from the temporary sale and the exact cost convention.

Do not assume the original quantity can be restored for free.

## 12. Cost conventions

Evaluate exactly:

- C0
- C_BASE
- C_S5
- C_S10

C_BASE is primary.

Use the same fee/slippage conventions already frozen in the project.

TEMP5 must account for every actual transaction:

- original entry
- temporary sell
- temporary re-entry if executed
- final canonical exit if re-entered and lifecycle continues

The additional sell/re-entry turnover must not be canceled analytically.

Use actual executed notional for every leg.

## 13. Stage A — feasibility gate

Stage A occurs before TEMP5 policy P&L simulation.

Purpose:

Determine whether the frozen first-Q1 five-minute adverse-value signal is large
enough, under the existing execution/cost assumptions, to plausibly justify
one sell-and-reentry interruption.

No policy outcome optimization is allowed in Stage A.

## 14. Stage A population

Use exact honest FIRST_Q1 trigger states from C26:

Expected:

- 157 in 2024
- 541 in 2025
- 698 total

Reconcile exactly before evaluating feasibility.

## 15. Gross avoidable five-minute value

For each first-Q1 trigger t:

    V5(t) = frozen DELTA_LIQ_5(t)

Define gross avoidable adverse value:

    GROSS_AVOIDABLE_5(t) = max(0, -V5(t))

Also retain signed:

    SIGNED_AVOIDABLE_5(t) = -V5(t)

GROSS_AVOIDABLE_5 is diagnostic.

The primary feasibility margin uses SIGNED_AVOIDABLE_5 so favorable V5 states
correctly count against indiscriminate interruption economics.

## 16. Incremental temporary-interruption trading cost

For each first-Q1 trigger, estimate the exact incremental transaction friction
required by the proposed TEMP5 interruption using frozen execution timing and
cost assumptions:

    temporary sell leg
    +
    temporary re-entry leg

relative to remaining continuously invested over the same interval.

Under C0 this incremental friction is zero except for any price-path effect;
under nonzero cost scenarios include the actual frozen fee/slippage convention
on the additional sell and buy legs.

Do not use later P0 outcome in Stage A.

Do not include policy benefit from later lifecycle recovery.

Stage A is only a five-minute-horizon feasibility calculation.

## 17. Feasibility margin

For each first-Q1 trigger:

    FEASIBILITY_MARGIN_5
      = SIGNED_AVOIDABLE_5
        - INCREMENTAL_TEMP_ROUNDTRIP_FRICTION

Positive means the adverse five-minute value is large enough to cover the
extra transaction friction in expectation at that trigger.

For each year and cost scenario report:

- trigger count
- mean SIGNED_AVOIDABLE_5
- median SIGNED_AVOIDABLE_5
- mean GROSS_AVOIDABLE_5
- mean incremental friction
- median incremental friction
- mean FEASIBILITY_MARGIN_5
- median FEASIBILITY_MARGIN_5
- fraction FEASIBILITY_MARGIN_5 > 0
- fraction FEASIBILITY_MARGIN_5 == 0
- fraction FEASIBILITY_MARGIN_5 < 0

## 18. Stage A dependence-aware uncertainty

For C_BASE, separately for 2024 and 2025:

### Whole-trade bootstrap
- 2,000 replicates
- fixed PCG64 seed
- resample complete first-Q1 trades
- preserve all paired quantities

### UTC entry-calendar-month bootstrap
- 2,000 replicates
- fixed PCG64 seed
- whole trades attached to entry month

Report 95% intervals for:

- mean SIGNED_AVOIDABLE_5
- mean incremental friction
- mean FEASIBILITY_MARGIN_5
- fraction margin > 0

No snapshot bootstrap.

## 19. Stage A gate

Stage B may run only if ALL of the following hold under C_BASE:

1. mean FEASIBILITY_MARGIN_5 > 0 in 2024;
2. mean FEASIBILITY_MARGIN_5 > 0 in 2025;
3. whole-trade uncertainty does not show clear evidence of negative mean
   feasibility margin in either year;
4. calendar-month uncertainty does not show clear evidence of negative mean
   feasibility margin in either year.

The 95% interval is NOT required to exclude zero.

The gate asks whether the candidate remains economically plausible after costs,
not whether feasibility alone is statistically proven.

If any condition fails:

    classification = STOP_TEMPORARY_EXIT_CANDIDATE

Do NOT execute Stage B.

Do NOT alter:
- duration;
- threshold;
- costs;
- fill semantics;
- re-entry rule.

Stop C27 after producing all Stage A artifacts and validation.

## 20. Stage B authorization

If and only if Stage A passes:

    proceed to exact TEMP5 simulation

Record:

    FEASIBILITY_GATE = PASS

Otherwise:

    FEASIBILITY_GATE = FAIL

No discretionary override.

## 21. Stage B primary policy estimands

For every original trade i calculate:

    DELTA_TEMP_P0_i
      = TEMP5_NET_i - P0_NET_i

    DELTA_TEMP_C25_i
      = TEMP5_NET_i - C25_NET_i

Primary comparisons under C_BASE:

1. TEMP5 versus canonical P0
2. TEMP5 versus frozen C25 permanent exit

Full 2,199-trade population is primary.

Unchanged/fallback trades contribute exact zero against P0 where appropriate.

## 22. Stage B reporting

For P0, C25, and TEMP5 report:

- total P&L
- mean net return
- median net return

For TEMP5-P0 and TEMP5-C25 report:

- total P&L difference
- mean paired return difference
- median paired return difference
- wins/losses/ties
- changed-trade count

Report separately:

- full 2,199 population
- honest model-covered population
- 2024 honest validation
- 2025 untouched evaluation

## 23. TEMP5 path accounting

Every trade must receive a deterministic TEMP5 path category.

At minimum:

- TEMP_EXIT_AND_REENTRY_EXECUTED
- TEMP_EXIT_P0_TERMINAL_WHILE_FLAT
- TEMP_EXIT_T2_TERMINAL_WHILE_FLAT
- SELL_FILL_UNAVAILABLE
- REENTRY_FILL_UNAVAILABLE
- ELIGIBLE_NEVER_Q1
- 2024_TRAINING_ONLY_FALLBACK
- NO_HONEST_MODEL_COVERAGE
- OTHER_P0_FALLBACK if required

Also report:

- Q1 trigger count
- temporary sell count
- successful re-entry count
- terminal-while-flat count
- unavailable sell count
- unavailable re-entry count

## 24. Timing audit

For every triggered TEMP5 trade record:

- first-Q1 state timestamp t
- temporary sell candidate timestamp
- temporary sell actual timestamp
- t + 5 minutes
- t_reassess completed-state timestamp
- re-entry candidate timestamp
- re-entry actual timestamp if any
- interruption duration measured:
    - state-to-state
    - sell-fill-to-reentry-fill
- lifecycle event timestamp if precedence applies

Verify:

    t_reassess >= t + 5 minutes

and that no earlier eligible completed state satisfies the condition.

## 25. Recovery and tail diagnostics

Because C27 exists to test action-duration mismatch, compare TEMP5 with C25 on
the frozen C26 diagnostic groups.

At minimum report TEMP5-P0 and TEMP5-C25 outcomes for:

- SHORT_BAD_LIFECYCLE_BAD
- SHORT_BAD_LIFECYCLE_RECOVERS
- SHORT_OK_LIFECYCLE_BAD
- SHORT_OK_LIFECYCLE_GOOD

Also report C25 diagnostic labels:

- AVOIDED_LOSS
- PRESERVED_GAIN
- SURRENDERED_UPSIDE
- DEEPENED_LOSS
- TIE

Primary diagnostic question:

    Does TEMP5 recover meaningful value from C25 surrendered-upside trades
    without giving back most of C25's avoided-loss benefit?

No policy modification may follow inside C27.

## 26. Right-tail diagnostics

Report paired results for canonical P0 cohorts:

- P0 return >= +0.5%
- >= +1%
- >= +2%
- >= +3%
- >= +5%
- P0 return < 0

For each compare:

- P0
- C25
- TEMP5

Report:

- trade count
- TEMP5 action count
- P&L by arm
- TEMP5-P0 difference
- TEMP5-C25 difference

No cohort-specific policy.

## 27. Lifecycle-class decomposition

Report separately:

- T2_FIRST
- P0_FIRST

For each:

- trade count
- C25 exits
- TEMP5 sells
- TEMP5 successful re-entries
- P0 P&L
- C25 P&L
- TEMP5 P&L
- TEMP5-P0 difference
- TEMP5-C25 difference

Eventual class remains evaluation-only.

## 28. Cost robustness

If Stage B runs, repeat exact frozen TEMP5 simulation under:

- C0
- C_BASE
- C_S5
- C_S10

No policy parameter may vary by cost scenario.

Report both:

- TEMP5-P0
- TEMP5-C25

C_BASE remains primary.

## 29. Dependence-aware policy uncertainty

If Stage B runs:

### Whole-trade paired bootstrap
- 2,000 PCG64 replicates
- all 2,199 original trades
- preserve all three arm outcomes

### Entry-calendar-month bootstrap
- 2,000 PCG64 replicates
- whole entry-month blocks
- preserve all three arm outcomes

Report 95% intervals for:

- mean TEMP5-P0 paired return
- mean TEMP5-C25 paired return
- covered-population versions of both

No snapshot bootstrap.

## 30. Symbol stability

If Stage B runs, for each symbol report:

- trade count
- TEMP5 action count
- successful re-entry count
- P0 P&L
- C25 P&L
- TEMP5 P&L
- TEMP5-P0 difference
- TEMP5-C25 difference

No symbol-specific policy.

## 31. Stage B classification

If Stage A fails:

    STOP_TEMPORARY_EXIT_CANDIDATE

and Stage B does not exist.

If Stage A passes and Stage B runs, classify exactly one:

### TEMPORARY_ACTION_SIGNAL_SUPPORTED

Require under C_BASE:

1. full-population TEMP5-P0 mean paired return > 0;
2. full-population TEMP5-C25 mean paired return > 0;
3. 2024 honest TEMP5-P0 mean > 0;
4. 2025 untouched TEMP5-P0 mean > 0;
5. dependence-aware uncertainty is directionally supportive and does not show
   clear evidence of material worsening versus P0;
6. TEMP5 materially reduces C25 surrendered-upside harm without eliminating
   most of C25 avoided-loss benefit;
7. result is not obviously one-symbol or one-month dependent.

This does NOT authorize deployment.

### WEAK_TEMPORARY_ACTION_SIGNAL

Use if:

- TEMP5 improves on C25 but not consistently on P0;
- OR full-population TEMP5-P0 is positive but year stability/uncertainty is
  weak;
- OR recovery benefit exists but added turnover materially offsets it;
- OR right-tail recovery improves while avoided-loss benefit deteriorates
  substantially.

### NO_USEFUL_TEMPORARY_ACTION_SIGNAL

Use if:

- TEMP5-P0 is nonpositive;
- OR untouched 2025 TEMP5-P0 is negative;
- OR TEMP5 fails to improve meaningfully on C25;
- OR added transaction costs remove the advantage;
- OR temporary action simply shifts rather than resolves the C25 tradeoff.

Do not alter these predicates after results.

## 32. Interpretation boundary

Even TEMPORARY_ACTION_SIGNAL_SUPPORTED means only:

    this exact frozen one-interruption historical candidate improved the
    paired historical outcome under the tested assumptions.

It does NOT establish:

- deployment readiness
- live profitability
- optimal interruption duration
- optimal re-entry timing
- repeated-cycle value
- best threshold
- best horizon
- best model

No production conclusion.

## 33. Prohibited analyses

Do NOT:

- test 10m/15m/30m interruptions
- anchor duration to sell fill
- try earlier/later re-entry
- retry unavailable re-entry
- allow repeated temporary cycles
- use Q2 or other bands
- use raw probability thresholds
- add persistence
- add recovery confirmation
- use alternate score horizons
- add features
- retrain/recalibrate the model
- select symbols/months
- optimize P&L or Sharpe
- access 2026
- start C28

## 34. Required artifacts

Write to:

artifacts/c27_temp5_feasibility_policy/

Stage A required artifacts:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- trigger_reconciliation.json
- q1_score_boundary_reconciliation.json
- timing_contract.json
- feasibility_definition.json
- feasibility_2024.json
- feasibility_2025.json
- feasibility_cost_robustness.json
- feasibility_whole_trade_bootstrap.json
- feasibility_calendar_month_bootstrap.json
- feasibility_gate.json

If Stage A fails, also produce:

- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

and STOP.

If Stage A passes, additionally produce:

- temp5_trade_ledger.json
- temp5_path_counts.json
- execution_timing_audit.json
- full_population_results.json
- covered_population_results.json
- yearly_results.json
- temp5_vs_c25_results.json
- cost_robustness.json
- c26_quadrant_results.json
- c25_label_results.json
- right_tail_results.json
- lifecycle_class_results.json
- symbol_results.json
- entry_month_results.json
- whole_trade_bootstrap.json
- calendar_month_bootstrap.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

## 35. Required TEMP5 ledger fields

If Stage B runs, at minimum:

- trade_id
- symbol
- entry timestamp
- honest evaluation status
- first-Q1 state timestamp
- frozen S+C9 probability
- frozen Q1 boundary
- temporary sell candidate timestamp
- temporary sell actual timestamp
- temporary sell price
- t_plus_5m
- t_reassess
- re-entry candidate timestamp
- re-entry actual timestamp if any
- re-entry price if any
- lifecycle precedence status
- TEMP5 path category
- canonical P0 exit timestamp
- canonical P0 net
- C25 net
- TEMP5 net
- TEMP5-P0 paired difference
- TEMP5-C25 paired difference
- per-arm P&L

Clearly separate retrospective/evaluation fields from decision fields.

## 36. Tests

Add focused tests for:

- exact C25/C26 trigger reproduction
- exact first-Q1 count
- exact frozen DELTA_LIQ_5 score/boundary
- duration anchored to state t, not fill
- earliest completed state >= t+5m
- one interruption maximum
- no repeated Q1 actions
- sell next-valid-open timing
- re-entry next-valid-open timing
- no same-state fill
- T2 precedence while flat
- P0 precedence while flat
- lifecycle tie precedence
- unavailable sell fail-closed
- unavailable re-entry no-retry
- actual transaction-cost accounting
- full sell / full re-entry mechanics
- Stage A margin calculation
- Stage A gate deterministic behavior
- Stage B impossible when gate fails
- exact P0/C25 reconciliation
- all 2,199 trades accounted for
- 2024 training trades cannot receive TEMP5 actions
- right-tail diagnostics
- quadrant reconciliation
- paired whole-trade bootstrap
- paired calendar-month bootstrap
- fixed PCG64 determinism
- no alternate duration/threshold/horizon/model
- no 2026 access

Run focused tests.

Run full repository suite once if scientific/runtime code changes.

## 37. Governance

Do NOT:

- modify C7-C26 scientific behavior
- modify this contract
- stage implementation/results
- commit implementation/results
- push
- access 2026
- start C28

The contract itself may be committed before implementation.

## 38. Final report

Always report:

1. contract SHA
2. reconciliation status
3. exact first-Q1 population
4. exact TEMP5 timing semantics
5. exact transaction-cost definition
6. 2024 Stage A feasibility statistics
7. 2025 Stage A feasibility statistics
8. C0/C_BASE/C_S5/C_S10 feasibility
9. whole-trade Stage A uncertainty
10. calendar-month Stage A uncertainty
11. FEASIBILITY_GATE PASS/FAIL

If gate FAIL, additionally report:

12. STOP_TEMPORARY_EXIT_CANDIDATE
13. why the candidate failed
14. artifact hashes
15. focused/full tests
16. git diff --check
17. git status --short
18. confirmation Stage B not run
19. confirmation no tuning/search
20. confirmation no 2026 access
21. confirmation C28 not started

If gate PASS, additionally report:

12. TEMP5 action/path counts
13. sell/re-entry execution counts
14. terminal-while-flat counts
15. C_BASE P0 P&L
16. C_BASE C25 P&L
17. C_BASE TEMP5 P&L
18. TEMP5-P0 paired result
19. TEMP5-C25 paired result
20. 2024 honest TEMP5 result
21. 2025 untouched TEMP5 result
22. covered-population result
23. cost robustness
24. C26 quadrant decomposition
25. C25 avoided-loss/surrendered-upside decomposition
26. right-tail results
27. lifecycle-class results
28. symbol results
29. entry-month results
30. whole-trade policy uncertainty
31. calendar-month policy uncertainty
32. frozen Stage B classification
33. whether temporary action recovered surrendered upside
34. whether avoided-loss benefit survived
35. limitations
36. implication for C28
37. artifact hashes
38. focused/full test results
39. git diff --check
40. git status --short
41. confirmation no alternate duration/threshold/horizon/reentry/model search
42. confirmation no P&L optimization
43. confirmation no 2026 access
44. confirmation nothing staged/committed/pushed
45. confirmation C28 not started

STOP after C27.
