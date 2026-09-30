# Catch-Up Transition Causal Representation Audit V3 Contract

Status: prospective and frozen before implementation.

Authoritative documents:

    docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V2.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V3.md

Historical outcome-free checkpoints:

    V1 audit: ec871bd
    V2 audit: bc128fd

This is NOT C31.

No predictive modeling or future-return analysis is authorized.

---

## 1. Purpose

Audit whether the V3 representation:

1. implements TRUE state transitions as distinct FALSE -> TRUE onset events;
2. produces causally valid catch-up and market-expansion episode timing;
3. distinguishes legitimate no-onset history from data/computation failure;
4. is sufficiently coherent for later predictive-contract design;
5. avoids the repetitive generic-momentum onset behavior found in V2;
6. remains non-redundant and stable enough for scientific use.

The audit does NOT ask whether any state predicts future return.

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

    REPRESENTATION_V3_AUDIT_INSUFFICIENT

and STOP.

---

## 3. Outcome firewall

Do NOT read or use:

- C29 GROSS40/GROSS50 labels;
- C29 endpoint returns;
- C30 labels;
- C30 predictions;
- C30 model scores;
- P0;
- T2;
- MFE;
- future returns;
- post-entry P&L;
- strategy results.

No future outcome may be joined to V3 representation rows.

No grouping by future outcome.

No model.

---

## 4. 2026 prohibition

Do not access, enumerate, inspect, hash, count, validate, or use any 2026
market data or metadata.

Accepted data are restricted to the frozen pre-2026 research inputs.

---

## 5. Authoritative V3 semantics

V3 supersedes earlier specifications only where explicitly amended.

Do not change:

- frozen five-symbol universe;
- leave-one-out equal-weight peer basket;
- 60-minute interval basis;
- 12-hour event search;
- sign-based catch-up state;
- market expansion state;
- FALSE -> TRUE onset semantics;
- most-recent onset selection;
- no magnitude thresholds;
- no alternate windows.

If the specification cannot be implemented uniquely, STOP rather than
improvise.

---

## 6. Frozen V3 primary schema

Audit exactly these eight variables in this exact order:

1. NEW_JOINER_FRACTION
2. BASKET_ACCELERATION
3. PRIOR_RELATIVE_DEFICIT
4. RELATIVE_IMPROVEMENT
5. DISPERSION_CHANGE
6. MINUTES_SINCE_MARKET_EXPANSION_ONSET
7. MINUTES_SINCE_CATCHUP_ONSET
8. CATCHUP_ONSET_RELATIVE_IMPROVEMENT

No additional primary feature.

No BTC primary feature.

No V2 subject absolute-onset feature.

No BREADTH_CHANGE primary feature.

---

## 7. Catch-up state

At hourly boundary u:

    CATCHUP_STATE(u) = TRUE

iff:

    PRIOR_RELATIVE_DEFICIT(u) > 0

AND:

    RELATIVE_IMPROVEMENT(u) > 0

otherwise FALSE.

Verify exact arithmetic from the frozen leave-one-out basket representation.

No future information.

---

## 8. Catch-up onset

A catch-up onset occurs at u iff:

    CATCHUP_STATE(u) == TRUE

AND:

    CATCHUP_STATE(u-60m) == FALSE

Verify explicitly:

    FALSE -> TRUE       onset
    TRUE  -> TRUE       no onset
    TRUE  -> FALSE      no onset
    FALSE -> FALSE      no onset

A TRUE state is not itself an onset.

---

## 9. Catch-up onset timestamps

For onset detected at u:

    CATCHUP_ONSET_INTERVAL_START_TS = u - 60m
    CATCHUP_ONSET_INTERVAL_END_TS   = u
    CATCHUP_ONSET_DETECTED_TS       = u

All source bars must lie in valid completed intervals.

No bar beginning at u may enter the interval ending at u.

---

## 10. Catch-up onset search

For E1 timestamp t:

Search event boundaries in:

    [t-12h, t]

Select:

    most recent FALSE -> TRUE catch-up onset

To evaluate the state transition at t-12h, causal warmup before t-12h is
permitted only as required to evaluate the prior state.

No onset earlier than t-12h may be selected.

---

## 11. Catch-up onset age

If onset exists:

    MINUTES_SINCE_CATCHUP_ONSET
        = E1_DECISION_TS - CATCHUP_ONSET_DETECTED_TS

If onset occurs at E1:

    0

If no onset:

    null

Zero is valid and distinct from missing.

---

## 12. Catch-up onset magnitude

If selected onset is u:

    CATCHUP_ONSET_RELATIVE_IMPROVEMENT
        = RELATIVE_IMPROVEMENT(u)

No future persistence or outcome enters the quantity.

If no onset:

    null

---

## 13. Catch-up onset count

Compute support diagnostic:

    CATCHUP_ONSET_COUNT_12H

equal to the number of FALSE -> TRUE catch-up transitions inside the frozen
12-hour event-search interval.

Do NOT count consecutive TRUE states as repeated onsets.

---

## 14. Market expansion state

At hourly boundary u:

    MARKET_EXPANSION_STATE(u) = TRUE

iff:

    BREADTH_CHANGE(u) > 0

AND:

    BREADTH_RECENT(u) >= 0.6

otherwise FALSE.

Use the frozen five-symbol universe.

---

## 15. Market expansion onset

A market-expansion onset occurs at u iff:

    MARKET_EXPANSION_STATE(u) == TRUE

AND:

    MARKET_EXPANSION_STATE(u-60m) == FALSE

Consecutive TRUE observations form one episode unless state becomes FALSE and
later TRUE again.

---

## 16. Market onset age

Search the same frozen 12-hour interval.

Use the most recent FALSE -> TRUE market-expansion onset.

If available:

    MINUTES_SINCE_MARKET_EXPANSION_ONSET
        = E1_DECISION_TS - MARKET_EXPANSION_ONSET_DETECTED_TS

Otherwise:

    null

---

## 17. Market onset count

Compute support diagnostic:

    MARKET_EXPANSION_ONSET_COUNT_12H

equal to the number of FALSE -> TRUE market-expansion transitions in the
12-hour window.

---

## 18. Core sequence audit

Using only causal timestamps, characterize the temporal relationship between:

    MARKET_EXPANSION_ONSET_DETECTED_TS
    CATCHUP_ONSET_DETECTED_TS
    E1_DECISION_TS

For rows with both onsets available, classify descriptively:

    MARKET_BEFORE_CATCHUP
    SAME_BOUNDARY
    CATCHUP_BEFORE_MARKET

Also report:

    market onset -> catch-up onset minutes
    catch-up onset -> E1 minutes
    market onset -> E1 minutes

No row is discarded based on ordering.

No sequence is declared favorable.

---

## 19. State-at-E1 diagnostics

Report:

    CATCHUP_STATE_AT_E1
    MARKET_EXPANSION_STATE_AT_E1

Counts and percentages:

- pooled;
- by year;
- by symbol;
- by UTC entry month.

Also report joint state table:

    MARKET_EXPANSION_STATE_AT_E1
    x
    CATCHUP_STATE_AT_E1

---

## 20. Same-boundary onset diagnostics

Report separately:

    CATCHUP_ONSET_DETECTED_TS == E1_DECISION_TS

and:

    MARKET_EXPANSION_ONSET_DETECTED_TS == E1_DECISION_TS

For each:

- count;
- percentage;
- by year;
- by symbol;
- by month.

Zero-age events are allowed.

The audit must determine descriptively whether V3 materially reduces the V2
pattern in which generic subject onset occurred at E1 for 81.95% of entries.

Do not impose a retrospective pass/fail percentage threshold solely for this.

---

## 21. Onset-count repetitiveness diagnostics

For:

    CATCHUP_ONSET_COUNT_12H
    MARKET_EXPANSION_ONSET_COUNT_12H

report:

- mean;
- std;
- min;
- p10;
- p25;
- median;
- p75;
- p90;
- max;
- exact frequency table.

Also report bands:

    0
    1
    2
    3
    4+
    
The purpose is to determine whether FALSE -> TRUE semantics create episode-like
events rather than frequently recurring conditions.

No outcome analysis.

---

## 22. Onset availability

Report presence/absence of:

    CATCHUP_ONSET_DETECTED_TS
    MARKET_EXPANSION_ONSET_DETECTED_TS

pooled and by:

- year;
- symbol;
- UTC month.

Also report joint availability:

    both available
    catch-up only
    market only
    neither

---

## 23. Legitimate absence vs data failure

Every null onset-derived value must be classified as either:

    NO_CAUSAL_ONSET_WITHIN_12H

or:

    SOURCE_OR_COMPUTATION_FAILURE

The first is valid state-history information.

The second is an implementation/data problem.

Report counts separately.

Do not collapse them into generic missingness.

---

## 24. Raw primary completeness

Report traditional complete-case availability for all eight primary variables:

    RAW_COMPLETE_PRIMARY_COUNT
    RAW_COMPLETE_PRIMARY_PERCENT

Because onset absence is legitimate in V3, this statistic is descriptive only.

Do NOT require raw completeness >=80% for PASS.

---

## 25. State-aware representation coverage

Define:

    STATE_AWARE_VALID_ROW = TRUE

iff:

- all non-onset primary variables are valid;
- any missing onset-age/magnitude variable is missing solely because the
  corresponding causal onset did not occur within 12h;
- no source/computation failure exists.

Report:

    STATE_AWARE_VALID_COUNT
    STATE_AWARE_VALID_PERCENT

For PASS require:

    STATE_AWARE_VALID_PERCENT >= 99%

unless frozen source limitations documented before implementation make this
mathematically impossible.

Do not count legitimate no-onset state as technical failure.

---

## 26. Missing-state encoding remains unresolved

Do NOT add onset-presence indicators to the V3 primary schema during this
audit.

Report whether a future predictive contract would require explicit indicators
or another prospectively frozen state encoding.

No encoding decision is authorized here.

---

## 27. Primary feature distributions

For each primary variable report, where defined:

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

Repeat pooled and by year.

For discrete features report exact frequency tables.

---

## 28. Catch-up onset magnitude diagnostics

For:

    CATCHUP_ONSET_RELATIVE_IMPROVEMENT

report:

- count;
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
- max.

Repeat by:

- year;
- symbol;
- catch-up onset age band.

No favorable interpretation.

---

## 29. Onset age diagnostics

For both:

    MINUTES_SINCE_CATCHUP_ONSET
    MINUTES_SINCE_MARKET_EXPANSION_ONSET

report:

- count;
- mean;
- std;
- min;
- p10;
- p25;
- median;
- p75;
- p90;
- max.

Fixed descriptive bands:

    0
    (0,60]
    (60,180]
    (180,360]
    (360,720]
    no onset

No outcome associations.

---

## 30. Structural redundancy audit

Verify V3 contains no prohibited aliases.

Confirm:

- NEW_JOINER_FRACTION primary;
- BREADTH_CHANGE support-only;
- no V2 SUBJECT_ONSET fields in primary matrix;
- no BTC primary field;
- no duplicate age aliases;
- no duplicate relative-return aliases.

Document exact algebraic relationships among support quantities.

---

## 31. Empirical redundancy audit

For the eight primary variables compute pairwise:

- Pearson;
- Spearman;
- pairwise valid count.

Diagnostic flags:

    abs(Pearson) >= 0.95
    abs(Spearman) >= 0.95

Do not remove or modify variables.

---

## 32. Exact duplicate audit

For every primary pair where jointly available test:

- exact equality;
- exact sign reversal;
- deterministic affine equivalence where identifiable.

Tolerance:

    atol = 1e-12
    rtol = 1e-12

Report all findings.

---

## 33. Year stability

For every primary variable report 2024 versus 2025:

- count;
- missing percentage;
- mean;
- median;
- std;
- standardized mean difference where defined;
- two-sample KS statistic.

No p-value-based feature selection.

---

## 34. Symbol diagnostics

For each primary variable and symbol:

- count;
- missing percentage;
- mean;
- median;
- p10;
- p90.

No symbol normalization.

No learned adjustment.

---

## 35. Sequence timing diagnostics

Where both onsets exist, report distribution of:

    CATCHUP_MINUS_MARKET_ONSET_MINUTES
        = CATCHUP_ONSET_DETECTED_TS
          - MARKET_EXPANSION_ONSET_DETECTED_TS

Interpretation:

    positive = market expansion detected first
    zero     = same boundary
    negative = catch-up detected first

Report pooled, by year, and by symbol.

Do not declare one ordering superior.

---

## 36. Future-mutation causality test

Required.

Compute V3 representation at E1.

Mutate all post-E1 market data to extreme values.

Recompute.

Requirement:

    every primary/support state, onset, count, timestamp, age, magnitude and
    sequence classification remains unchanged.

---

## 37. Entry-fill independence

Required.

Mutate:

- realized entry price;
- realized fill timestamp;
- first post-E1 execution price;
- slippage assumptions.

Requirement:

    full V3 representation unchanged.

---

## 38. State-transition synthetic tests

Required catch-up fixtures:

    FALSE -> FALSE
        no onset

    FALSE -> TRUE
        one onset

    FALSE -> TRUE -> TRUE
        one onset

    FALSE -> TRUE -> FALSE
        one onset

    FALSE -> TRUE -> FALSE -> TRUE
        two onsets

    TRUE -> TRUE
        no new onset at second TRUE

Equivalent tests required for MARKET_EXPANSION_STATE.

---

## 39. Search-boundary tests

Verify:

- onset exactly at E1;
- onset exactly 12h before E1;
- prior-state warmup required at 13h before E1;
- event earlier than 12h not selected;
- multiple onsets -> most recent selected;
- no onset -> legitimate null;
- source gap -> technical failure, not no-onset.

---

## 40. Formula tests

At minimum verify:

    NEW_JOINER_FRACTION

    BASKET_ACCELERATION
        = BASKET_RECENT_RETURN - BASKET_PREV_RETURN

    PRIOR_RELATIVE_DEFICIT
        = -(SUBJECT_PREV_RETURN - BASKET_PREV_RETURN)

    RELATIVE_IMPROVEMENT
        = SUBJECT_RELATIVE_RECENT
          - SUBJECT_RELATIVE_PREVIOUS

    DISPERSION_CHANGE
        = DISPERSION_RECENT - DISPERSION_PREVIOUS

    CATCHUP_ONSET_RELATIVE_IMPROVEMENT
        = RELATIVE_IMPROVEMENT at selected onset boundary

Use independent synthetic fixtures.

---

## 41. V2 comparison

Outcome-free comparison with V2 is authorized only for representation
mechanics.

Report:

    V2 subject same-boundary onset rate:
        historical 81.95%

    V2 mean subject qualifying conditions / 12h:
        historical 5.31

Compare against V3:

    catch-up same-boundary onset rate
    catch-up FALSE->TRUE onset count distribution

Do NOT compare future performance.

---

## 42. Required artifact namespace

Write only to:

    artifacts/catchup_transition_representation_audit_v3/

Do not modify V1 or V2 artifacts.

---

## 43. Required artifacts

At minimum:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- source_boundary_audit.json
- representation_schema_v3.json
- formula_audit_v3.json
- interval_boundary_audit_v3.json
- state_transition_audit_v3.json
- catchup_state_frequency.json
- market_expansion_state_frequency.json
- catchup_onset_availability.json
- market_expansion_onset_availability.json
- onset_joint_availability.json
- catchup_onset_count_distributions.json
- market_onset_count_distributions.json
- same_boundary_onset_audit_v3.json
- onset_age_distributions_v3.json
- catchup_onset_magnitude_distributions.json
- sequence_ordering.json
- sequence_timing_distributions.json
- raw_completeness.json
- state_aware_coverage.json
- null_reason_audit.json
- structural_redundancy_v3.json
- pearson_correlation_v3.json
- spearman_correlation_v3.json
- empirical_redundancy_flags_v3.json
- exact_duplicate_audit_v3.json
- feature_distributions_v3.json
- year_distribution_stability_v3.json
- symbol_distribution_diagnostics_v3.json
- future_mutation_test_v3.json
- entry_fill_independence_test_v3.json
- v2_v3_mechanics_comparison.json
- interpretation_predicates_v3.json
- final_summary_v3.json
- reproducibility_hashes_v3.json

Avoid unnecessary row-level dumps.

---

## 44. Frozen V3 classification

Return exactly one:

### REPRESENTATION_V3_AUDIT_PASS

Only if all hold:

1. exact 2,199 population reconciles;
2. exact eight-variable schema matches;
3. all formulas pass;
4. FALSE -> TRUE transition semantics pass;
5. state/onset timing is causal;
6. future-mutation invariance passes;
7. entry-fill independence passes;
8. no outcome artifact was read;
9. no 2026 data/metadata was accessed;
10. STATE_AWARE_VALID_PERCENT >= 99%;
11. no unresolved exact/sign-reversed/affine primary duplicate exists;
12. onset nulls are cleanly distinguishable from source failures;
13. no material implementation ambiguity remains.

PASS means only:

    V3 is technically coherent enough for human review of whether predictive
    experiment design is justified.

PASS does NOT mean:

- predictive signal exists;
- sequence is profitable;
- C31 is authorized.

### REPRESENTATION_V3_NEEDS_REVISION

Use when implementation is valid but representation design remains materially
problematic, including:

- state-aware coverage <99%;
- FALSE -> TRUE semantics still produce an event definition that is
  behaviorally indistinguishable from a generic recurring condition;
- state/onset distinction remains semantically unclear;
- severe primary redundancy remains;
- legitimate no-onset states cannot be represented cleanly for future use;
- severe year/symbol scale pathology creates a representation problem.

No outcome evidence may be used.

### REPRESENTATION_V3_AUDIT_INSUFFICIENT

Use only if:

- population reconciliation fails;
- source integrity fails;
- specification ambiguity prevents unique implementation;
- causal timing cannot be guaranteed;
- outcome firewall cannot be guaranteed;
- 2026 boundary cannot be guaranteed.

---

## 45. No automatic rarity threshold

Do NOT invent a minimum or maximum acceptable onset frequency.

Report exact frequencies.

Interpret distinctiveness using:

- onset counts;
- same-boundary rates;
- onset ages;
- state persistence patterns;
- sequence ordering.

Any future change requires a prospective V4 specification.

---

## 46. No feature modification

Do not:

- remove a primary variable;
- add onset-presence indicators;
- change signs;
- alter thresholds;
- change the 12h window;
- change the 60m base interval;
- add BTC;
- normalize by symbol.

Report problems only.

---

## 47. No predictive work

Do not compute:

- GROSS40/GROSS50 enrichment;
- endpoint-return association;
- future-return means;
- AUC;
- PR-AUC;
- Brier;
- log loss;
- coefficients;
- probabilities;
- trading P&L.

No model of any kind.

---

## 48. No C31

Do not:

- create C31;
- implement C31;
- fit a classifier;
- select a predictive schema using outcomes.

STOP at representation audit.

---

## 49. Required tests

Focused tests must cover at minimum:

- exact E1 population/hash;
- year/symbol reconciliation;
- exact eight-variable schema/order;
- leave-one-out peers;
- 60m non-overlapping intervals;
- catch-up state formula;
- market expansion state formula;
- all four state-transition cases;
- multiple episode recurrence;
- most-recent onset selection;
- exact 12h boundary;
- causal warmup;
- same-boundary E1 onset;
- onset magnitude;
- state-aware null classification;
- no entry-fill dependence;
- no post-E1 dependence;
- no outcome artifact access;
- no 2026 access;
- deterministic hashes.

Run focused tests.

Run full repository suite once if scientific/runtime source code changes.

---

## 50. Reproducibility

Record:

- V3 audit contract SHA-256;
- all four representation/measurement document hashes;
- implementation hash;
- test hash;
- source hashes;
- population hash;
- ordered schema hash;
- semantic representation hash;
- Python/environment/dependency versions;
- execution command;
- git HEAD;
- dirty/untracked status.

All core machine-readable outputs must reproduce deterministically.

---

## 51. Governance

Do NOT modify:

- V1/V2/V3 specifications;
- prior audit contracts;
- prior audit artifacts;
- C29/C30 behavior;
- sealed 2026 boundary.

Do NOT stage, commit, or push implementation/results.

The V3 audit contract itself may be committed prospectively.

---

## 52. Final report

Report:

1. contract SHA-256;
2. V3 measurement-spec SHA-256;
3. exact E1 reconciliation;
4. exact eight-variable schema;
5. formula audit;
6. interval/timing audit;
7. state-transition audit;
8. catch-up state-at-E1 frequency;
9. market-expansion state-at-E1 frequency;
10. catch-up onset availability;
11. market onset availability;
12. joint onset availability;
13. catch-up onset-count distribution;
14. market onset-count distribution;
15. catch-up same-boundary onset rate;
16. market same-boundary onset rate;
17. V2-vs-V3 mechanics comparison;
18. catch-up onset-age distribution;
19. market onset-age distribution;
20. catch-up onset magnitude distribution;
21. market-before-catch-up / same / catch-up-before-market counts;
22. sequence timing distribution;
23. raw complete-case rate;
24. state-aware valid rate;
25. legitimate no-onset counts;
26. source/computation failure counts;
27. structural redundancy;
28. Pearson/Spearman summary;
29. exact duplicate audit;
30. year stability;
31. symbol diagnostics;
32. future-mutation test;
33. entry-fill-independence test;
34. exact classification:
       REPRESENTATION_V3_AUDIT_PASS
       REPRESENTATION_V3_NEEDS_REVISION
       REPRESENTATION_V3_AUDIT_INSUFFICIENT
35. whether episode onsets appear materially more event-like than V2 generic
    qualifying conditions, using outcome-free evidence only;
36. whether missing-state encoding needs a prospective amendment before any
    predictive experiment;
37. whether predictive-contract DESIGN is technically justified;
38. explicit statement that PASS does not imply predictive usefulness;
39. artifact hash verification;
40. focused-test result;
41. full-suite result if run;
42. git diff --check;
43. git status --short;
44. confirmation no outcome artifacts were read;
45. confirmation no model was fit;
46. confirmation no feature was selected/removed;
47. confirmation no 2026 data/metadata was accessed;
48. confirmation nothing implementation-related was staged/committed/pushed;
49. confirmation C31 was not started.

STOP.
