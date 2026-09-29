# Catch-Up Transition Causal Representation Audit Contract

Status: prospective and frozen before implementation.

This audit implements and validates the measurements defined in:

    docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md

Authoritative design checkpoint:

    commit 5180f7f

This is NOT C31.

This audit contains no predictive modeling and no future-return analysis.

---

## 1. Purpose

Determine whether the frozen catch-up transition representation:

1. can be computed causally and reproducibly at E1;
2. is sufficiently available across the frozen E1 population;
3. produces the hypothesized temporal states often enough to be meaningful;
4. contains substantial structural or empirical redundancy;
5. is technically suitable for a later separately authorized predictive test.

The audit does NOT ask whether the representation predicts profitable trades.

---

## 2. Frozen scientific question

The audit asks:

> Can the prospectively defined catch-up transition measurements be computed
> faithfully from pre-E1 information, and do they form a coherent,
> sufficiently available, non-redundant representation of market
> participation expansion, relative catch-up, leadership timing, dispersion,
> and transition maturity around E1?

No future outcome participates in the answer.

---

## 3. Frozen population

Use the exact frozen E1 population:

    2,199 trades

Entry rule:

    E1_H1_SMA24_CROSS_V1

Frozen entry hash:

    6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3

Expected year counts:

    2024 = 1,093
    2025 = 1,106

Expected symbols:

    BNBUSDT = 442
    BTCUSDT = 451
    ETHUSDT = 434
    SOLUSDT = 431
    XRPUSDT = 441

Reconcile before measurement computation.

Material reconciliation failure:

    REPRESENTATION_AUDIT_INSUFFICIENT

and STOP.

---

## 4. Sealed future boundary

No 2026 market data or metadata may be accessed.

Do not:

- enumerate 2026 market files;
- open 2026 files;
- count 2026 rows;
- inspect 2026 schemas;
- compute 2026 features;
- use 2026 for missing-data completion.

All accepted market input must be explicitly restricted to pre-2026 data.

Synthetic tests may use artificial timestamps before 2026 only.

---

## 5. Strict outcome firewall

This audit MUST NOT read or use:

- C29 GROSS40/GROSS50 labels;
- C29 endpoint-return artifacts;
- C30 prediction labels;
- C30 model probabilities;
- C30 proper scores;
- P0 outcomes;
- T2 outcomes;
- MFE;
- future endpoint returns;
- post-entry profit/loss;
- strategy P&L.

No outcome column may be joined into the representation dataset.

No representation statistic may be grouped by future outcome.

Implementation should preferably fail closed if an outcome-labelled input is
accidentally supplied.

---

## 6. Authoritative measurement specification

Implement the definitions exactly as frozen in:

    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md

Do not change:

- five-symbol universe;
- leave-one-out equal-weight peer basket;
- 60-minute adjacent non-overlapping intervals;
- 12-hour onset search;
- majority breadth threshold 0.6;
- positive-return participation definition;
- directional onset semantics;
- most-recent qualifying onset rule;
- population-standard-deviation dispersion;
- catch-up sequence candidate definition;
- null semantics.

If a specification is internally impossible or ambiguous enough to prevent a
unique implementation, document the issue and STOP rather than improvise.

---

## 7. E1 information cutoff

Every primary representation value must satisfy:

    available_ts <= E1_decision_ts

No entry fill or post-E1 bar may enter a representation value.

For every row and feature retain enough provenance to verify:

    source_start_ts
    source_end_ts
    available_ts
    E1_decision_ts

The latest source value must be strictly pre-E1 where the measurement
specification requires completed data before t.

---

## 8. Frozen primary representation

Audit exactly these ten candidate variables:

1. BREADTH_CHANGE
2. NEW_JOINER_FRACTION
3. BASKET_ACCELERATION
4. PRIOR_RELATIVE_DEFICIT
5. RELATIVE_IMPROVEMENT
6. DISPERSION_CHANGE
7. MINUTES_SINCE_MARKET_ONSET
8. MINUTES_SINCE_SUBJECT_ONSET
9. SUBJECT_EXTENSION_SINCE_ONSET
10. BTC_ONSET_LEAD_MINUTES

No additional predictive feature may be introduced.

Support quantities may be computed only where required to audit formulas.

---

## 9. Required support quantities

At minimum retain or summarize:

- SUBJECT_PREV_RETURN
- SUBJECT_RECENT_RETURN
- BASKET_PREV_RETURN
- BASKET_RECENT_RETURN
- BREADTH_PREVIOUS
- BREADTH_RECENT
- PERSISTENT_PARTICIPANT_FRACTION
- SUBJECT_RELATIVE_PREVIOUS
- SUBJECT_RELATIVE_RECENT
- DISPERSION_PREVIOUS
- DISPERSION_RECENT
- MARKET_ONSET_TS
- SUBJECT_ONSET_TS
- BTC_ONSET_TS
- BASKET_EXTENSION_SINCE_MARKET_ONSET
- CATCHUP_SEQUENCE_CANDIDATE

These are audit/support values, not automatically future model inputs.

---

## 10. Formula verification

For every primary and support quantity verify exact implementation against the
measurement specification.

Required checks include:

    BREADTH_CHANGE
        = BREADTH_RECENT - BREADTH_PREVIOUS

    BASKET_ACCELERATION
        = BASKET_RECENT_RETURN - BASKET_PREV_RETURN

    PRIOR_RELATIVE_DEFICIT
        = -(SUBJECT_PREV_RETURN - BASKET_PREV_RETURN)

    RELATIVE_IMPROVEMENT
        = (SUBJECT_RECENT_RETURN - BASKET_RECENT_RETURN)
          -
          (SUBJECT_PREV_RETURN - BASKET_PREV_RETURN)

    DISPERSION_CHANGE
        = DISPERSION_RECENT - DISPERSION_PREVIOUS

Use independent hand-computable synthetic fixtures.

---

## 11. Leave-one-out basket audit

For every subject verify:

- exactly four peer symbols;
- subject excluded;
- equal arithmetic weight;
- no dynamic symbol dropping;
- no capitalization weighting;
- no volatility weighting.

Report peer membership for all five subject symbols.

---

## 12. Interval-boundary audit

For every E1 row verify:

    PREVIOUS_60 = [t-120m, t-60m)
    RECENT_60   = [t-60m, t)

No overlap.

No bar at or after t.

Report:

- earliest source timestamp;
- latest source timestamp;
- expected bar counts;
- observed bar counts;
- missing/gap reasons.

No interpolation or synthetic bars.

---

## 13. Onset-rule audit

Implement the frozen symbol onset condition:

At hourly boundary u:

    recent return > 0

AND:

    recent return > previous return

using adjacent completed non-overlapping 60-minute intervals.

Search exactly the preceding 12 hours.

Choose:

    most recent qualifying onset

not earliest.

Verify separately for:

- subject onset;
- BTC onset.

No persistence requirement may be added.

No absolute-return threshold may be added.

---

## 14. Market-onset audit

At hourly boundary u:

    BREADTH_CHANGE(u) > 0

AND:

    BREADTH_RECENT(u) >= 0.6

Search exactly 12 hours backward from E1.

Choose the most recent qualifying event.

No alternate breadth threshold.

No outcome-guided revision.

---

## 15. Onset availability

Report for each onset type:

- count present;
- count absent;
- percentage present;
- by year;
- by subject symbol;
- by UTC entry month.

Onset types:

- MARKET_ONSET_TS
- SUBJECT_ONSET_TS
- BTC_ONSET_TS

Also report joint availability:

- market + subject;
- market + BTC;
- subject + BTC;
- all three.

No future outcomes.

---

## 16. Primary-feature availability

For each of the ten primary variables report:

- available count;
- unavailable count;
- availability percentage;
- null reasons;
- by year;
- by symbol;
- by UTC entry month.

Also report:

    COMPLETE_PRIMARY_REPRESENTATION

count and percentage where all ten variables are available.

Do NOT impute missing onset-derived features.

---

## 17. Catch-up sequence frequency

Compute exactly the frozen descriptive flag:

    CATCHUP_SEQUENCE_CANDIDATE = 1

iff:

    MARKET_ONSET_TS is not null
    AND PRIOR_RELATIVE_DEFICIT > 0
    AND RELATIVE_IMPROVEMENT > 0

Report frequency:

- pooled;
- 2024;
- 2025;
- each symbol;
- each UTC entry month.

This is a representation-frequency statistic only.

Do not compare it to future returns.

---

## 18. Transition-state combinations

Descriptively report counts for the causal sign/state combinations at E1.

At minimum:

- market onset present / absent;
- prior relative deficit positive / non-positive;
- relative improvement positive / non-positive;
- breadth change positive / zero / negative;
- basket acceleration positive / zero / negative;
- dispersion change positive / zero / negative.

Report joint cross-tab for:

    MARKET_ONSET_PRESENT
    x PRIOR_RELATIVE_DEFICIT_SIGN
    x RELATIVE_IMPROVEMENT_SIGN

No future outcome columns.

---

## 19. Timing relative to E1

For onset-derived measurements report distributions of:

- MINUTES_SINCE_MARKET_ONSET
- MINUTES_SINCE_SUBJECT_ONSET
- BTC_ONSET_LEAD_MINUTES

Statistics:

- count;
- mean;
- standard deviation;
- minimum;
- p10;
- p25;
- median;
- p75;
- p90;
- maximum.

Repeat by year and symbol.

---

## 20. Important timing interpretation limitation

The frozen measurement system detects only causal onset events known by E1.

Therefore this audit may validly distinguish:

    NO_PRIOR_ONSET_WITHIN_12H

from:

    PRIOR_ONSET_PRESENT

and characterize:

    how long before E1 the onset occurred.

It MUST NOT claim that E1 occurred:

    "after the transition"

because no causal transition-END rule exists.

It also MUST NOT inspect post-E1 data merely to decide that a transition
started later.

The audit should state explicitly:

    onset-age can characterize E1 relative to detected onset,
    but cannot classify E1 as before/during/after a complete transition
    without an independently defined transition-end rule.

---

## 21. Age-band diagnostics

For descriptive readability only, report onset-age counts using fixed bands:

    0 minutes
    (0, 60] minutes
    (60, 180] minutes
    (180, 360] minutes
    (360, 720] minutes
    no onset

These bands are not features.

They are not thresholds for later selection.

Do not compare these bands to future outcomes.

---

## 22. Extension diagnostics

For:

    SUBJECT_EXTENSION_SINCE_ONSET
    BASKET_EXTENSION_SINCE_MARKET_ONSET

report:

- available count;
- mean;
- std;
- min;
- p10;
- p25;
- median;
- p75;
- p90;
- max;

pooled, year, and symbol.

No favorable interpretation of large/small extension.

---

## 23. Structural redundancy audit

Identify and verify all exact or algebraic relationships specified by the
measurement note.

At minimum:

    PRIOR_RELATIVE_DEFICIT
        = -SUBJECT_RELATIVE_PREVIOUS

    RELATIVE_IMPROVEMENT
        = SUBJECT_RELATIVE_RECENT
          - SUBJECT_RELATIVE_PREVIOUS

    SUBJECT_PEER_DISTANCE_RECENT
        = SUBJECT_RELATIVE_RECENT

    MARKET_TO_E1_MINUTES
        = MINUTES_SINCE_MARKET_ONSET

    SUBJECT_ONSET_TO_E1_MINUTES
        = MINUTES_SINCE_SUBJECT_ONSET

Do not duplicate aliases in the primary ten-variable matrix.

---

## 24. Empirical redundancy audit

Outcome-free empirical dependence analysis is authorized.

For the ten primary representation variables compute pairwise:

- Pearson correlation;
- Spearman correlation;
- pairwise complete observation count.

No outcome variable may enter these matrices.

Flag a pair as:

    NEAR_REDUNDANT_LINEAR

if:

    abs(Pearson) >= 0.95

Flag:

    NEAR_REDUNDANT_RANK

if:

    abs(Spearman) >= 0.95

These flags are diagnostics only.

Do not automatically remove variables during this audit.

---

## 25. Exact duplicate audit

For every pair of primary variables, on rows where both are present:

report whether they are:

- byte/numerically identical;
- exact sign reversals;
- exact affine transforms where deterministically identifiable.

Use tight numerical tolerance:

    absolute tolerance = 1e-12
    relative tolerance = 1e-12

Any exact relationship must be documented.

---

## 26. Distribution audit

For each primary variable report:

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
- number of unique values.

Repeat pooled and by year.

For coarse/discrete variables such as breadth quantities, also report exact
value frequencies.

No winsorization or clipping.

---

## 27. Temporal stability of representation distribution

Outcome-free comparison of 2024 versus 2025 feature distributions is
authorized.

For every primary variable report:

- 2024 mean / median / std;
- 2025 mean / median / std;
- standardized mean difference where defined;
- two-sample Kolmogorov-Smirnov statistic as descriptive evidence only.

Do NOT use p-values for feature selection.

Do NOT classify a variable as good/bad based on outcome-free distribution
shift alone.

Purpose:

    understand whether the representation itself occupies substantially
    different market states across years.

---

## 28. Symbol-distribution diagnostics

For every primary variable and symbol report:

- count;
- missing percentage;
- mean;
- median;
- p10;
- p90.

This is to reveal whether a measurement has strongly symbol-specific scale
despite the common formula.

Do not normalize by symbol during this audit.

---

## 29. Future-mutation causality test

Required.

Construct synthetic or isolated test fixtures and compute an E1 representation.

Then mutate all post-E1 price data to extreme values.

Recompute the representation.

Requirement:

    every pre-E1 primary/support quantity must remain exactly unchanged.

This must include:

- subject price;
- peer prices;
- BTC price;
- breadth;
- basket;
- dispersion;
- onset timestamps;
- extension-since-onset;
- catch-up-sequence flag.

Post-E1 mutation may not affect any representation value.

---

## 30. Entry-fill independence test

Required.

Change the realized future entry-fill price/timestamp without changing the E1
decision-state source data.

Requirement:

    representation unchanged.

The representation is anchored to E1 decision time, not executed fill.

---

## 31. Onset-search tests

Synthetic tests must verify:

- qualifying onset at E1 boundary;
- qualifying onset 1h before;
- multiple qualifying onsets -> most recent selected;
- onset 13h before -> unavailable;
- no qualifying onset -> null;
- recent return positive but not improving -> no onset;
- improving return but recent return <= 0 -> no onset;
- exact equality recent == previous -> no onset;
- missing interval -> no synthetic onset.

---

## 32. Market-onset tests

Synthetic tests must verify:

- breadth change positive and 3/5 positive -> onset;
- breadth change positive and 2/5 positive -> no onset;
- breadth recent exactly 0.6 -> onset if breadth change > 0;
- breadth change exactly zero -> no onset;
- 4/5 or 5/5 positive with no breadth increase -> no new onset;
- most recent qualifying onset selected.

---

## 33. Catch-up sequence tests

Verify:

CATCHUP_SEQUENCE_CANDIDATE = 1 only when:

- market onset exists;
- prior relative deficit > 0;
- relative improvement > 0.

Boundary tests:

- deficit exactly zero -> 0;
- improvement exactly zero -> 0;
- null market onset -> 0.

No future outcome involved.

---

## 34. Reproducibility

Use deterministic computation.

Record:

- source paths/hashes;
- specification hashes;
- implementation hash;
- ordered schema;
- population hash;
- representation matrix semantic hash;
- environment;
- Python version;
- dependency versions;
- command;
- timestamp;
- git HEAD;
- dirty/untracked status.

Repeated execution from identical inputs must reproduce the same core
machine-readable results and semantic hashes.

---

## 35. Required artifacts

Write to:

    artifacts/catchup_transition_representation_audit/

Required files:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- source_boundary_audit.json
- representation_schema.json
- formula_audit.json
- interval_boundary_audit.json
- loo_basket_audit.json
- onset_rule_audit.json
- market_onset_audit.json
- onset_availability.json
- feature_availability.json
- catchup_sequence_frequency.json
- transition_state_cross_tabs.json
- onset_timing_distributions.json
- onset_age_bands.json
- extension_distributions.json
- structural_redundancy.json
- pearson_correlation.json
- spearman_correlation.json
- empirical_redundancy_flags.json
- exact_duplicate_audit.json
- feature_distributions.json
- year_distribution_stability.json
- symbol_distribution_diagnostics.json
- future_mutation_test.json
- entry_fill_independence_test.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid large row-level dumps unless required for reproducibility.

---

## 36. Frozen audit classification

Return exactly one:

### REPRESENTATION_AUDIT_PASS

Only if ALL are true:

1. exact 2,199 E1 population reconciles;
2. all ten primary quantities match their frozen formulas;
3. all timing/availability checks pass;
4. post-E1 mutation cannot change any representation value;
5. entry-fill mutation cannot change any representation value;
6. no 2026 data is accessed;
7. no future outcome is read or joined;
8. catch-up sequence candidate is computable without future information;
9. no unresolved exact duplicate exists among the ten primary variables;
10. at least 80% of E1 rows have COMPLETE_PRIMARY_REPRESENTATION;
11. onset-derived missingness is fully explained by frozen causal rules rather
    than implementation failure;
12. no pair of primary variables is both structurally redundant and retained
    unknowingly as independent information.

This means only:

    the representation is technically coherent enough for a later scientific
    decision about predictive testing.

It does NOT mean the representation is predictive.

### REPRESENTATION_NEEDS_REVISION

Use if the audit executes correctly but one or more of the following occurs:

- complete primary availability < 80%;
- one or more primary quantities are exact/near duplicates in a way that
  materially undermines the compact representation;
- the hypothesized catch-up sequence is so rare that the representation does
  not meaningfully characterize the E1 population;
- onset timing is technically valid but clearly inconsistent with the
  intended representation semantics;
- strong year/symbol distribution pathologies reveal a representation-design
  problem;
- a design ambiguity becomes material during implementation.

No outcome evidence may be used for this classification.

### REPRESENTATION_AUDIT_INSUFFICIENT

Use only if:

- population reconciliation fails;
- accepted market inputs are unavailable/corrupt;
- causal timing cannot be established;
- specification ambiguity prevents unique implementation;
- 2026 boundary cannot be guaranteed;
- outcome firewall cannot be guaranteed.

---

## 37. Important rarity interpretation

There is deliberately NO frozen numeric minimum for:

    CATCHUP_SEQUENCE_CANDIDATE frequency

other than the 80% completeness requirement for the primary representation.

Therefore the executor may describe a sequence as uncommon, but MUST NOT
invent a retrospective rarity threshold to force PASS or NEEDS_REVISION.

If rarity appears scientifically important, report the exact frequency and
leave interpretation for human review.

---

## 38. No feature removal

Even if a primary pair is highly correlated:

- do not remove a variable;
- do not create a reduced schema;
- do not rerun the audit with a new subset.

Report the issue.

Any revised representation requires a new prospective design checkpoint.

---

## 39. No predictive work

The audit MUST NOT compute:

- Brier score;
- log loss;
- AUC;
- PR-AUC;
- endpoint-label prevalence by representation state;
- GROSS40/GROSS50 enrichment;
- future-return means by representation group;
- P&L;
- trading thresholds;
- probability scores.

No model of any kind.

---

## 40. No C31

Do not:

- create a C31 contract;
- implement C31;
- fit a C31 model;
- propose a final C31 feature matrix based on outcomes.

The audit terminates before predictive research.

---

## 41. Required tests

Focused tests must cover at minimum:

- exact 2,199 population/hash;
- year/symbol counts;
- exact five-symbol universe;
- leave-one-out peers;
- exact 60m non-overlapping intervals;
- pre-E1-only data;
- no entry-fill dependence;
- no post-E1 dependence;
- return arithmetic;
- breadth arithmetic;
- new-joiner arithmetic;
- basket acceleration;
- relative deficit;
- relative improvement;
- dispersion ddof=0;
- 12h onset window;
- most-recent onset selection;
- symbol onset boundaries;
- market onset boundaries;
- 0.6 breadth equality;
- null onset behavior;
- extension-since-onset timing;
- BTC lead sign convention;
- catch-up candidate boundaries;
- algebraic redundancy relationships;
- deterministic Pearson/Spearman matrices;
- exact duplicate detection;
- deterministic core hashes;
- no outcome artifact access;
- no 2026 access.

Run focused tests.

Run full repository suite once if scientific/runtime source code changes.

---

## 42. Governance

Do NOT modify:

- C29 scientific behavior;
- C30 scientific behavior;
- STRATEGY_DESIGN_REVIEW.md;
- CATCHUP_TRANSITION_REPRESENTATION_SPEC.md;
- CATCHUP_TRANSITION_MEASUREMENT_SPEC.md;
- this frozen audit contract.

Do NOT:

- stage implementation/results;
- commit implementation/results;
- push;
- access 2026;
- start C31.

The audit contract itself may be committed prospectively.

---

## 43. Final report

Report:

1. contract SHA-256;
2. representation-spec hash;
3. measurement-spec hash;
4. exact E1 reconciliation;
5. source boundary verification;
6. outcome-firewall verification;
7. ten-variable schema;
8. exact formula audit;
9. interval-boundary audit;
10. leave-one-out basket audit;
11. onset-rule audit;
12. market-onset audit;
13. onset availability;
14. complete-primary-representation rate;
15. catch-up-sequence frequency;
16. transition-state cross-tabs;
17. onset timing distributions;
18. fixed age-band distributions;
19. extension distributions;
20. structural redundancy;
21. Pearson matrix summary;
22. Spearman matrix summary;
23. near-redundancy flags;
24. exact duplicate/affine audit;
25. pooled feature distributions;
26. 2024-vs-2025 distribution stability;
27. symbol distribution diagnostics;
28. future-mutation test;
29. entry-fill-independence test;
30. exact frozen classification:
       REPRESENTATION_AUDIT_PASS
       REPRESENTATION_NEEDS_REVISION
       REPRESENTATION_AUDIT_INSUFFICIENT
31. explicit statement that PASS does not imply prediction;
32. whether later predictive-contract design is technically justified;
33. limitations, including inability to infer transition completion;
34. artifact hash verification;
35. focused-test result;
36. full-suite result if run;
37. git diff --check;
38. git status --short;
39. confirmation no outcome labels/returns were read;
40. confirmation no model was fit;
41. confirmation no feature was selected/removed;
42. confirmation no 2026 data/metadata was accessed;
43. confirmation nothing implementation-related was staged/committed/pushed;
44. confirmation C31 was not started.

STOP.
