# C19 Target Definition and Decision-Timing Review Contract

Status: prospectively specified before C19 review.

## 1. Purpose

C19 is a methodology checkpoint.

It does NOT:
- train a model;
- define an exit policy;
- optimize P&L;
- search thresholds;
- search horizons;
- access 2026;
- begin C20.

Its purpose is to determine what economic quantity a future post-entry
decision system should actually predict or optimize.

The research objective remains:

slow entry,
then after entry switch to faster causal observation/execution,
and determine when an exit is economically justified.

This does NOT imply fast exit.

## 2. Background

C9 demonstrated strong causal prediction of:

    P(T2 before P0 | current pre-T2 state)

C18 then compared that probability against:

    DELTA_V_PRE(t)
      = HOLD_TO_P0_NET(t) - EXIT_NOW_NET(t)

and found no useful economic alignment.

However, C18 also found very strong negative within-trade association between
p_t2 and DELTA_V_PRE.

C19 must determine how much of that behavior follows mechanically from the
target definition and whether the target matches the actual intended decision.

## 3. Frozen dependencies

Do not modify scientific behavior from C7 through C18.

Use frozen artifacts/code from C7-C18 as authoritative evidence.

No 2026 data or metadata may be accessed.

## 4. Exact reconstruction of DELTA_V_PRE

Reconstruct and document the exact C18 definition.

For a causal state completed at time t:

EXIT_NOW_NET(t):
    net trade return/P&L if the position exits at the immediate next
    executable 1-minute open after t.

HOLD_TO_P0_NET(t):
    net trade return/P&L if the position remains unchanged until its frozen
    canonical P0 exit.

DELTA_V_PRE(t):
    HOLD_TO_P0_NET(t) - EXIT_NOW_NET(t)

Document explicitly:

- entry price and notional convention;
- state timestamp;
- next executable exit timestamp;
- canonical P0 timestamp and price;
- cost model;
- entry-side costs;
- exit-side costs;
- whether already-incurred entry costs cancel algebraically;
- slippage treatment;
- fee treatment;
- actual executed notional convention;
- P0 tie precedence;
- gap/missing-bar behavior.

Do not alter the equation.

## 5. Incremental-cost decomposition

Algebraically decompose DELTA_V_PRE into:

- terminal gross value difference;
- incremental exit-cost difference;
- any components common to both alternatives.

Identify which already-incurred costs cancel from the decision comparison.

Determine whether C18's implementation is economically equivalent to comparing
only incremental future cash flows from time t onward.

If not equivalent, document the discrepancy.

No repair is allowed in C19.

## 6. Mechanical relationships

Derive which relationships follow mechanically from:

    DELTA_V_PRE(t)
      = fixed eventual P0 value - current executable exit value

within a single trade.

In particular evaluate the statement:

"If the frozen P0 terminal value is fixed within a trade, increases in current
executable exit value mechanically reduce DELTA_V_PRE, all else equal."

Document implications for correlations between DELTA_V_PRE and variables that
rise as a trade progresses favorably, including p_t2.

Separate:

A. mathematical/mechanical relationships;

from:

B. empirical relationships that require data.

Do not infer economic uselessness from a mechanically induced correlation.

## 7. Decision problem A: terminal commitment

Define:

TERMINAL_COMMITMENT decision:

    EXIT NOW
    versus
    COMMIT TO HOLD UNTIL FROZEN P0

C18 evaluates this decision.

Document precisely what conclusions C18 can and cannot support under this
interpretation.

## 8. Decision problem B: sequential continuation

Define:

SEQUENTIAL_CONTINUATION decision:

    EXIT NOW
    versus
    CONTINUE FOR NOW, OBSERVE NEW CAUSAL INFORMATION, AND REASSESS LATER

This is closer to the intended strategy architecture.

Explicitly document that:

"continue now" does NOT imply commitment to P0.

Explain why the value of sequential continuation includes optionality from
future decisions.

## 9. Why sequential continuation value is policy-dependent

Define conceptually:

SEQUENTIAL_VALUE(t)
    = value of continuing now under a specified future causal decision rule
      - value of exiting now

State explicitly:

SEQUENTIAL_VALUE cannot be uniquely labeled from historical data without
specifying the downstream decision policy.

Therefore C19 must NOT construct a supposedly policy-free
"optimal continuation value" using future-best exits.

That would embed hindsight/optimization.

## 10. Candidate future evaluation targets

C19 may define, but not empirically select among, the following target classes.

### A. Terminal target

DELTA_V_P0(t):
    hold to frozen P0 minus exit now

This is the C18 target.

### B. Fixed-horizon forward opportunity targets

For prospectively chosen horizon H:

DELTA_V_H(t):
    executable value after continuing for H
    minus executable exit-now value

Candidate characterization horizons for a future checkpoint:

- 5m
- 15m
- 30m
- 60m

These horizons are NOT to be evaluated in C19.

### C. First-event target

DELTA_V_EVENT(t):
    value at the first frozen lifecycle event among T2/P0
    minus exit-now value

Document advantages and limitations.

### D. Sequential-policy target

DELTA_V_POLICY(t):
    value under a prospectively frozen future decision policy
    minus exit-now value

This can only be evaluated after that downstream policy is defined
prospectively.

## 11. Decision timing

Document the causal timing for any future exit/continue decision:

1. state is formed only from completed information;
2. decision occurs after state completion;
3. earliest executable action is the next valid 1-minute open;
4. no intrabar hindsight;
5. ties with frozen terminal execution must be handled prospectively;
6. missing/gapped execution evidence must fail closed.

Distinguish observation frequency from exit frequency:

higher-resolution observation does not imply frequent or immediate exits.

## 12. Accounting for benefits and harms of an exit policy

Any later policy evaluation must include BOTH:

A. avoided losses / preserved gains:
   cases where earlier exit improves outcome versus the comparator;

B. abandoned winners / foregone upside:
   cases where earlier exit produces a worse outcome than continuing.

Report policy effect as a paired difference over the complete frozen
population, not only triggered trades.

Non-triggered trades must retain exact comparator outcome.

## 13. Required future economic accounting

For a future policy P versus comparator C report at minimum:

- per-trade paired net-return difference;
- total P&L difference;
- mean paired difference;
- median paired difference;
- fraction improved;
- fraction worsened;
- positive contribution;
- negative contribution;
- winner/right-tail truncation;
- downside protection;
- holding/exposure changes;
- trigger and fallback counts.

Do not implement these calculations in C19 beyond verifying definitions.

## 14. Dependence and uncertainty

Future policy evaluation must treat trades as the primary dependence unit.

Use:

- trade-level paired analysis;
- whole-trade bootstrap/resampling where applicable.

Where trades may share market-regime/time dependence, use calendar-block
resampling as a robustness method.

The preferred established project convention is a fixed calendar-block
bootstrap when applicable.

Do not treat individual 1-minute snapshots as independent economic samples.

For symbol/year analyses:
- use them as robustness/decomposition;
- do not use them to select a policy post hoc.

## 15. Right-tail preservation

C7-C18 repeatedly showed strong right-tail concentration and winner truncation
risk.

C19 must state explicitly that future decision evaluation must measure both:

- downside avoided;
- right-tail upside destroyed.

A policy cannot be judged by:
- win rate alone;
- median outcome alone;
- avoided red trades alone;
- state-classification accuracy alone.

## 16. Interpretation of probability models

Document distinctions between:

P(event | state)

and:

E[incremental economic value | state]

and:

P(policy action is beneficial | state).

A probability model for a lifecycle event is not automatically an economic
decision model.

Conversely, failure to align with DELTA_V_P0 does not by itself prove that
the probability contains no economically relevant information for another
decision horizon.

## 17. C18 reinterpretation

Using only already-produced C18 results, state what C18 established:

- C9 predicts T2/P0 lifecycle outcome well;
- C9 does not align with the specific terminal-commitment target
  DELTA_V_PRE;
- DELTA_V_PRE has a mechanically declining component as current executable
  value rises toward/through a fixed terminal value;
- therefore C18 does not justify using C9 directly as an exit signal;
- C18 also does not settle the sequential continuation problem.

Do not recompute C18 or change its frozen classification.

## 18. C20 recommendation criteria

C19 should recommend ONE next methodological experiment.

If the review confirms that C18 answered TERMINAL_COMMITMENT while the actual
decision is SEQUENTIAL_CONTINUATION:

recommend a bounded forward-opportunity characterization before any policy.

The preferred candidate is to characterize fixed future horizons:

- 5m
- 15m
- 30m
- 60m

plus first-event value if methodologically justified.

No horizon may be selected as "best" based on outcome.

If the review instead finds a flaw in the C18 economic accounting itself:

stop and recommend a repair checkpoint before further analysis.

Do not execute C20.

## 19. Required artifacts

Write to:

artifacts/c19_target_definition_decision_timing_review/

Required artifacts:

- run_manifest.json
- provenance.json
- delta_v_pre_definition.json
- incremental_cost_decomposition.json
- mechanical_relationships.json
- terminal_commitment_definition.json
- sequential_continuation_definition.json
- sequential_value_policy_dependency.json
- candidate_target_taxonomy.json
- decision_timing.json
- future_policy_accounting_requirements.json
- dependence_uncertainty_requirements.json
- right_tail_requirements.json
- probability_vs_value_distinctions.json
- c18_reinterpretation.json
- c20_recommendation.json
- final_summary.json
- reproducibility_hashes.json

Keep artifacts concise.

## 20. Verification/tests

C19 should perform only focused verification necessary to confirm:

- exact C18 equation;
- exact C18 cost semantics;
- next-open execution timing;
- P0 comparator semantics;
- common-cost cancellation;
- no 2026 access;
- required frozen artifact hashes/provenance.

Add focused tests only if needed to verify these definitions.

Do NOT run a new model.

A full repository test suite is optional unless code is changed.

If no scientific/runtime code is changed, do not waste time/tokens rerunning
the full suite merely for C19.

## 21. Governance

Do not:

- modify C7-C18 scientific behavior;
- train/retrain/recalibrate a model;
- calculate new policy economics;
- evaluate candidate horizons;
- optimize P&L;
- choose an exit threshold;
- use hindsight-optimal exits;
- access 2026;
- begin C20;
- stage, commit, or push.

## 22. Final report

Report:

1. contract SHA
2. exact DELTA_V_PRE equation
3. exact timing semantics
4. incremental-cost decomposition
5. which costs cancel
6. mechanical relationships implied by the equation
7. empirical versus mechanical distinction
8. terminal-commitment decision definition
9. sequential-continuation decision definition
10. why sequential continuation value is policy-dependent
11. candidate future target taxonomy
12. required future policy accounting
13. dependence/uncertainty requirements
14. right-tail preservation requirements
15. probability/event/value distinction
16. precise reinterpretation of C18
17. whether C18 accounting itself is valid
18. recommended C20 direction
19. artifact hashes
20. focused verification/test results
21. git diff --check
22. git status --short
23. confirmation no model/policy/horizon evaluation
24. confirmation no 2026 access
25. confirmation nothing staged/committed/pushed

STOP after C19.
