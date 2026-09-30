# Catch-Up Transition Causal Representation Audit V4 Contract

Status: prospective and frozen before implementation.

Authoritative documents:

    docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V2.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V3.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V4.md

Authoritative V4 measurement SHA-256:

    f37833e46148b06f1a50fb7deefb59e4bca33b3fc4933f9e008982806164802a

Historical outcome-free checkpoints:

    V1 audit: ec871bd
    V2 audit: bc128fd
    V4 measurement spec: 7a56a25

This is NOT C31.

No predictive modeling or future-return analysis is authorized.

---

## 1. Purpose

Audit whether the V4 representation:

1. can be computed exactly and causally at E1;
2. replaces recurrent historical-onset search with coherent current-state
   persistence;
3. has complete or explainably incomplete measurement coverage;
4. contains expected versus problematic structural redundancy;
5. behaves coherently across year and symbol;
6. is technically suitable for later predictive-contract design.

The audit does NOT ask whether any V4 quantity predicts future return.

---

## 2. Frozen population

Use the exact frozen E1 population:

    2,199 entries

Entry rule:

    E1_H1_SMA24_CROSS_V1

Frozen entry hash:

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

Failure to reconcile exactly:

    REPRESENTATION_V4_AUDIT_INSUFFICIENT

and STOP.

---

## 3. Strict outcome firewall

Do NOT read or use:

- C29 GROSS40/GROSS50 labels;
- C29 endpoint returns;
- C30 labels;
- C30 probabilities;
- C30 scores;
- P0;
- T2;
- MFE;
- future returns;
- post-entry P&L;
- policy outcomes;
- strategy results.

No outcome-labelled artifact may be joined to V4 rows.

No model may be fitted.

---

## 4. 2026 prohibition

Do not access, enumerate, inspect, hash, count, validate, or use any 2026
market data or metadata.

Accepted inputs are restricted to the frozen pre-2026 research data and causal
warmup required by V4.

---

## 5. Authoritative V4 semantics

V4 is authoritative where it amends V1-V3.

Do not change:

- frozen five-symbol universe;
- leave-one-out equal-weight peer basket;
- 60-minute interval basis;
- catch-up state definition;
- market-expansion state definition;
- 12-boundary maximum run-length horizon;
- no historical-onset primary features;
- no magnitude thresholds;
- no alternate windows;
- no BTC primary feature.

If implementation cannot be uniquely derived from the specifications, STOP.

---

## 6. Frozen primary schema

Audit exactly these nine variables, in this exact order:

1. NEW_JOINER_FRACTION
2. BASKET_ACCELERATION
3. PRIOR_RELATIVE_DEFICIT
4. RELATIVE_IMPROVEMENT
5. DISPERSION_CHANGE
6. MARKET_EXPANSION_STATE_AT_E1
7. MARKET_EXPANSION_CURRENT_RUN_LENGTH
8. CATCHUP_STATE_AT_E1
9. CATCHUP_CURRENT_RUN_LENGTH

No additional primary feature.

---

## 7. Frozen interval semantics

At hourly boundary u:

    PREVIOUS_60(u)
        = [u-120m, u-60m)

    RECENT_60(u)
        = [u-60m, u)

Intervals are adjacent and non-overlapping.

Only completed accepted 1-minute bars may be used.

No bar beginning at u may enter RECENT_60(u).

---

## 8. Leave-one-out basket

For subject s:

    LOO_BASKET(s)

contains exactly the other four frozen symbols.

Equal arithmetic weighting only.

Verify:

- subject excluded;
- exactly four peers;
- no dynamic dropping;
- no capitalization weighting;
- no volatility weighting;
- no learned weighting.

---

## 9. Core return formulas

Verify:

    SUBJECT_PREV_RETURN
    SUBJECT_RECENT_RETURN
    BASKET_PREV_RETURN
    BASKET_RECENT_RETURN

according to prior frozen return semantics.

Verify:

    BASKET_ACCELERATION
        = BASKET_RECENT_RETURN
          - BASKET_PREV_RETURN

---

## 10. Relative formulas

Verify:

    SUBJECT_RELATIVE_PREVIOUS
        = SUBJECT_PREV_RETURN
          - BASKET_PREV_RETURN

    SUBJECT_RELATIVE_RECENT
        = SUBJECT_RECENT_RETURN
          - BASKET_RECENT_RETURN

    PRIOR_RELATIVE_DEFICIT
        = -SUBJECT_RELATIVE_PREVIOUS

    RELATIVE_IMPROVEMENT
        = SUBJECT_RELATIVE_RECENT
          - SUBJECT_RELATIVE_PREVIOUS

Use synthetic independent fixtures.

---

## 11. Participation formulas

Verify:

    BREADTH_PREVIOUS
    BREADTH_RECENT
    BREADTH_CHANGE
    NEW_JOINER_FRACTION
    PERSISTENT_PARTICIPANT_FRACTION

using all five frozen symbols.

NEW_JOINER_FRACTION is primary.

BREADTH_CHANGE remains support/state-definition only.

---

## 12. Dispersion

Verify:

    DISPERSION_PREVIOUS
    DISPERSION_RECENT

using population standard deviation:

    ddof = 0

and:

    DISPERSION_CHANGE
        = DISPERSION_RECENT
          - DISPERSION_PREVIOUS

---

## 13. Catch-up state

At boundary u:

    CATCHUP_STATE(u) = TRUE

iff:

    PRIOR_RELATIVE_DEFICIT(u) > 0

AND:

    RELATIVE_IMPROVEMENT(u) > 0

otherwise FALSE.

At E1:

    CATCHUP_STATE_AT_E1 = 1 if TRUE
                          0 if FALSE

No missing source data may be silently treated as FALSE.

---

## 14. Market-expansion state

At boundary u:

    MARKET_EXPANSION_STATE(u) = TRUE

iff:

    BREADTH_CHANGE(u) > 0

AND:

    BREADTH_RECENT(u) >= 0.6

otherwise FALSE.

At E1:

    MARKET_EXPANSION_STATE_AT_E1 = 1 if TRUE
                                   0 if FALSE

No missing source data may be silently treated as FALSE.

---

## 15. Catch-up current run length

Inspect at most the 12 hourly state boundaries ending at E1:

    t
    t-60m
    ...
    t-11h

Define:

    CATCHUP_CURRENT_RUN_LENGTH

as the count of consecutive TRUE CATCHUP_STATE values beginning at t and
walking backward until:

- first FALSE state;
- unavailable state;
- or 12 boundaries reached.

Frozen semantics:

    state(t) FALSE -> run length 0

    T at t only -> 1

    T,T ending at t -> 2

    ...

    12 consecutive TRUE states -> 12

Value 12 means:

    at least 12 consecutive observed TRUE states

not exact episode age.

---

## 16. Market-expansion current run length

Apply identical semantics to:

    MARKET_EXPANSION_STATE

Define:

    MARKET_EXPANSION_CURRENT_RUN_LENGTH

with range 0 through 12.

No historical total TRUE count.
No onset count.
No first-onset age.

---

## 17. Run-length missing-data semantics

If an unavailable historical state is encountered while computing a TRUE run:

the run length must be marked unavailable unless the current state is already
FALSE.

Example:

    state(t) = FALSE

then:

    run length = 0

and no earlier state is needed.

But if:

    state(t) = TRUE
    state(t-60m) = unavailable

then the true run length cannot be established and must be:

    null

Do not assume the missing state was FALSE.

Report these cases.

---

## 18. Run-length warmup

Each historical state requires its own causal PREVIOUS_60 and RECENT_60
intervals.

Computing the earliest of 12 state boundaries therefore requires causal source
warmup earlier than t-12h.

This is permitted.

No state boundary earlier than t-11h enters the run count itself.

---

## 19. State/run deterministic relationship

Verify exactly:

    MARKET_EXPANSION_STATE_AT_E1 == 0
        iff
    MARKET_EXPANSION_CURRENT_RUN_LENGTH == 0

for every valid row.

And:

    CATCHUP_STATE_AT_E1 == 0
        iff
    CATCHUP_CURRENT_RUN_LENGTH == 0

for every valid row.

Equivalently:

    STATE_AT_E1 = 1 iff RUN_LENGTH > 0

This deterministic relationship is expected.

Report it explicitly as:

    EXPECTED_STRUCTURAL_REDUNDANCY

not accidental duplicate information.

---

## 20. Technical availability

For each of nine primary variables report:

- valid count;
- null count;
- valid percentage;
- null reasons;
- by year;
- by symbol;
- by UTC entry month.

Also report:

    COMPLETE_V4_PRIMARY_COUNT
    COMPLETE_V4_PRIMARY_PERCENT

---

## 21. State-aware validity

Define:

    STATE_AWARE_VALID_ROW

iff every V4 primary value is valid under the frozen measurement semantics.

Unlike V3, absence of an event is not a reason for null state/run-length
values.

Therefore V4 should normally permit full representation wherever causal source
bars exist.

For PASS require:

    STATE_AWARE_VALID_PERCENT >= 99%

Any shortfall must be explained entirely by source integrity.

---

## 22. Current state frequencies

Report:

    CATCHUP_STATE_AT_E1

and:

    MARKET_EXPANSION_STATE_AT_E1

frequency:

- pooled;
- 2024;
- 2025;
- by symbol;
- by UTC month.

No outcome grouping.

---

## 23. Exact run-length distributions

For each run-length variable report exact counts for:

    0
    1
    2
    3
    4
    5
    6
    7
    8
    9
    10
    11
    12

Also report:

- mean;
- std;
- median;
- p75;
- p90;
- maximum.

Repeat by:

- year;
- symbol.

---

## 24. Persistence diagnostics

For each state report descriptive fractions:

    run == 0
    run == 1
    run == 2
    run == 3
    run >= 4

These are descriptive only.

No threshold becomes a feature or selection rule.

---

## 25. Joint state combinations

Report exact counts and percentages:

    market=0, catchup=0
    market=0, catchup=1
    market=1, catchup=0
    market=1, catchup=1

Repeat by:

- year;
- symbol.

No combination is declared favorable.

---

## 26. Joint run-length cross-tab

Produce outcome-free cross-tab:

    MARKET_EXPANSION_CURRENT_RUN_LENGTH
    x
    CATCHUP_CURRENT_RUN_LENGTH

using exact integer values 0-12.

Also provide a compact grouped view:

    0
    1
    2
    3
    4+

for each dimension.

No future outcome.

---

## 27. V3-vs-V4 mechanics comparison

Comparison to V3 is authorized only for outcome-free representation mechanics.

Report:

V3 historical diagnostics:

    catch-up mean onsets / 12h = 3.92
    catch-up median onsets = 4
    catch-up 4+ onset rows = 1,503 / 2,199
    catch-up same-boundary onset = 31.15%

    market mean onsets / 12h = 4.09
    market median onsets = 4
    market 4+ onset rows = 1,646 / 2,199
    market same-boundary onset = 50.25%

Compare with V4:

    current-state frequency
    current-run-length distribution

Do not claim predictive improvement.

---

## 28. Primary distribution audit

For every primary variable report:

- count;
- missing count;
- mean;
- std;
- min;
- p01;
- p05;
- p10;
- p25;
- median;
- p75;
- p90;
- p95;
- p99;
- max;
- unique count.

For binary/discrete quantities include exact frequency tables.

---

## 29. Structural redundancy audit

Required classifications:

### Expected structural relationship

    STATE_AT_E1
    versus
    CURRENT_RUN_LENGTH

must be identified as deterministic state/run coupling.

### Prohibited duplication

Check all other primary pairs for:

- exact equality;
- exact sign reversal;
- deterministic affine transform.

Tolerance:

    atol = 1e-12
    rtol = 1e-12

Do not remove variables.

---

## 30. Empirical redundancy audit

For all nine primary variables compute pairwise:

- Pearson;
- Spearman;
- pairwise valid observation count.

Flag:

    abs(Pearson) >= 0.95

or:

    abs(Spearman) >= 0.95

Distinguish expected state/run structural dependence from unexpected
near-redundancy.

Do not modify the schema.

---

## 31. Year stability

For every primary variable compare 2024 vs 2025:

- count;
- missing percentage;
- mean;
- median;
- std;
- standardized mean difference where defined;
- two-sample KS statistic.

No outcome data.
No p-value feature selection.

---

## 32. Symbol diagnostics

For every primary variable and symbol report:

- count;
- missing percentage;
- mean;
- median;
- p10;
- p90.

Do not normalize by symbol.

Do not modify formulas by symbol.

---

## 33. Future-mutation causality test

Required.

Compute full V4 representation at E1.

Mutate all post-E1 market data to extreme values.

Recompute.

Requirement:

    every primary/support value and every historical state used for run length
    remains unchanged.

---

## 34. Entry-fill independence test

Required.

Mutate:

- entry fill price;
- entry fill timestamp;
- first post-E1 execution price;
- execution cost/slippage information.

Requirement:

    V4 representation unchanged.

---

## 35. State synthetic tests

Required catch-up cases:

    current FALSE
        state=0, run=0

    ... F T
        state=1, run=1

    ... F T T
        state=1, run=2

    ... F T T T
        state=1, run=3

    T T F T
        final run=1

    twelve TRUE states
        run=12

Apply equivalent tests to market expansion.

---

## 36. Missing-state synthetic tests

Required:

    current state missing
        state/run unavailable

    current FALSE, prior missing
        state=0, run=0

    current TRUE, immediately prior missing
        run unavailable

    current TRUE, previous TRUE, next historical missing
        run unavailable because actual run may exceed known suffix

No silent FALSE substitution.

---

## 37. Formula boundary tests

Test:

- PRIOR_RELATIVE_DEFICIT == 0;
- RELATIVE_IMPROVEMENT == 0;
- BREADTH_CHANGE == 0;
- BREADTH_RECENT exactly 0.6;
- NEW_JOINER zero/non-zero;
- dispersion ddof=0;
- 12-state run cap.

Frozen strict inequalities must be preserved.

---

## 38. No historical-onset reconstruction

Do not compute new V4 primary values from:

- time since onset;
- most recent onset;
- first onset;
- onset count;
- onset interval magnitude.

Historical onset logic may only be referenced for V3 mechanics comparison.

---

## 39. No feature modification

Even if audit finds redundancy:

- do not remove state binaries;
- do not remove run lengths;
- do not merge them;
- do not add interactions;
- do not add presence flags;
- do not alter thresholds.

Any change requires prospective V5 or predictive-contract schema decision after
human review.

---

## 40. Required artifact namespace

Write only to:

    artifacts/catchup_transition_representation_audit_v4/

Do not overwrite prior audit artifacts.

---

## 41. Required artifacts

At minimum:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- source_boundary_audit.json
- representation_schema_v4.json
- formula_audit_v4.json
- interval_boundary_audit_v4.json
- loo_basket_audit.json
- state_definition_audit_v4.json
- run_length_semantics_audit.json
- feature_availability_v4.json
- state_aware_coverage.json
- catchup_state_frequency.json
- market_expansion_state_frequency.json
- catchup_run_length_distribution.json
- market_run_length_distribution.json
- joint_state_cross_tab.json
- joint_run_length_cross_tab.json
- persistence_diagnostics.json
- v3_v4_mechanics_comparison.json
- structural_redundancy_v4.json
- pearson_correlation_v4.json
- spearman_correlation_v4.json
- empirical_redundancy_flags_v4.json
- exact_duplicate_audit_v4.json
- feature_distributions_v4.json
- year_distribution_stability_v4.json
- symbol_distribution_diagnostics_v4.json
- future_mutation_test_v4.json
- entry_fill_independence_test_v4.json
- interpretation_predicates_v4.json
- final_summary_v4.json
- reproducibility_hashes_v4.json

Avoid unnecessary row-level dumps.

---

## 42. Frozen V4 classification

Return exactly one.

### REPRESENTATION_V4_AUDIT_PASS

Only if all hold:

1. exact 2,199 population reconciles;
2. exact nine-variable schema/order matches;
3. all formulas pass;
4. causal interval semantics pass;
5. catch-up state logic passes;
6. market-expansion state logic passes;
7. run-length semantics pass;
8. state/run deterministic relationships are correctly documented;
9. STATE_AWARE_VALID_PERCENT >= 99%;
10. future mutation changes nothing;
11. entry-fill mutation changes nothing;
12. no outcome-labelled artifact was read;
13. no 2026 data/metadata was accessed;
14. no unexpected exact/sign-reversed/affine primary duplicate exists;
15. no unresolved implementation ambiguity remains.

PASS means only:

    V4 is technically coherent enough for human review of whether a later
    predictive contract should be designed.

It does NOT mean predictive usefulness exists.

### REPRESENTATION_V4_NEEDS_REVISION

Use if implementation succeeds but representation remains materially flawed,
including:

- state-aware validity <99%;
- run-length semantics cannot be represented reliably;
- unexpected severe primary redundancy;
- severe year/symbol representation pathology;
- state/run representation fails to provide information beyond mechanically
  restating the same current quantities in a scientifically unusable way;
- material semantic ambiguity remains.

Expected deterministic state/run coupling alone does NOT force revision.

### REPRESENTATION_V4_AUDIT_INSUFFICIENT

Use only if:

- population reconciliation fails;
- source integrity fails;
- specification cannot be implemented uniquely;
- causal timing cannot be guaranteed;
- outcome firewall cannot be guaranteed;
- 2026 boundary cannot be guaranteed.

---

## 43. No distribution-shape pass criterion

Do not require:

- balanced TRUE/FALSE rates;
- rare states;
- long runs;
- short runs;
- any particular joint-state mix.

These are measurements, not targets.

---

## 44. Predictive-contract readiness question

The final audit may answer:

    predictive-contract DESIGN technically justified: YES / NO

based only on:

- causal validity;
- availability;
- semantic coherence;
- redundancy;
- distribution stability.

It must NOT use future returns to answer.

Even YES does not authorize executing C31.

---

## 45. No predictive work

Do NOT compute:

- GROSS40/GROSS50 association;
- endpoint returns;
- AUC;
- PR-AUC;
- Brier;
- log loss;
- probabilities;
- coefficients;
- P&L.

No model.

---

## 46. No C31

Do not create, implement, or run C31.

STOP after the V4 audit.

---

## 47. Required focused tests

At minimum:

- exact population/hash;
- year/symbol counts;
- exact nine-variable schema/order;
- leave-one-out peers;
- exact 60m intervals;
- all primary formulas;
- catch-up state boundaries;
- market state boundaries;
- state/run deterministic relationships;
- run lengths 0/1/2/3/12;
- reset after FALSE;
- missing-history semantics;
- causal warmup;
- no post-E1 dependence;
- no fill dependence;
- exact duplicate logic;
- deterministic correlations;
- deterministic hashes;
- no outcome artifact access;
- no 2026 access.

Run focused tests.

Run full suite once if scientific/runtime source code changes.

---

## 48. Reproducibility

Record:

- contract SHA-256;
- V4 spec SHA-256;
- all authoritative prior spec hashes;
- implementation hash;
- test hash;
- source hashes;
- population hash;
- ordered schema hash;
- semantic representation hash;
- Python version;
- environment;
- dependency versions;
- command;
- git HEAD;
- dirty/untracked status.

Core outputs must reproduce deterministically.

---

## 49. Governance

Do not modify:

- V1/V2/V3/V4 specifications;
- previous audit contracts;
- previous artifacts;
- C29/C30 behavior.

Do not:

- stage implementation/results;
- commit implementation/results;
- push;
- start C31.

The V4 audit contract itself may be committed prospectively.

---

## 50. Final report

Report:

1. contract SHA-256;
2. V4 measurement-spec SHA-256;
3. exact E1 reconciliation;
4. exact nine-variable schema;
5. source boundary audit;
6. formula audit;
7. interval audit;
8. leave-one-out basket audit;
9. catch-up state audit;
10. market-expansion state audit;
11. catch-up run-length audit;
12. market run-length audit;
13. complete-primary rate;
14. state-aware valid rate;
15. null/source failure reasons;
16. catch-up TRUE/FALSE frequency;
17. market TRUE/FALSE frequency;
18. catch-up exact run-length distribution;
19. market exact run-length distribution;
20. persistence diagnostics;
21. joint current-state table;
22. joint run-length table;
23. V3-vs-V4 mechanics comparison;
24. expected state/run structural redundancy;
25. unexpected structural redundancy;
26. Pearson/Spearman summary;
27. exact duplicate/affine audit;
28. year stability;
29. symbol diagnostics;
30. future-mutation result;
31. entry-fill-independence result;
32. exact frozen classification:
       REPRESENTATION_V4_AUDIT_PASS
       REPRESENTATION_V4_NEEDS_REVISION
       REPRESENTATION_V4_AUDIT_INSUFFICIENT
33. whether predictive-contract DESIGN is technically justified;
34. explicit statement that PASS does not imply predictive usefulness;
35. artifact hash verification;
36. focused-test result;
37. full-suite result if run;
38. git diff --check;
39. git status --short;
40. confirmation no outcome artifacts were read;
41. confirmation no model was fitted;
42. confirmation no feature was selected/removed;
43. confirmation no 2026 data/metadata was accessed;
44. confirmation implementation/results were not staged/committed/pushed;
45. confirmation C31 was not started.

STOP.
