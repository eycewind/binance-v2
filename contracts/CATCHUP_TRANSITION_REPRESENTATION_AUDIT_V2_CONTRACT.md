# Catch-Up Transition Causal Representation Audit V2 Contract

Status: prospective and frozen before implementation.

This audit evaluates the revised measurement definitions in:

    docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V2.md

V1 causal representation audit checkpoint:

    ec871bd

This is NOT C31.

This audit contains no predictive modeling and no future-return analysis.

---

## 1. Purpose

Determine whether the V2 catch-up transition representation:

1. preserves strict causal timing;
2. resolves the V1 completeness defect caused by same-boundary subject onset;
3. preserves the intended transition semantics;
4. remains sufficiently available across the frozen E1 population;
5. avoids exact or severe primary-feature redundancy;
6. behaves coherently across years and symbols;
7. is technically suitable for later, separately authorized predictive testing.

The audit does NOT ask whether the representation predicts profitable trades.

---

## 2. Frozen scientific question

The audit asks:

> Does the V2 nine-variable catch-up transition representation provide a
> causally valid, sufficiently complete, semantically coherent, and
> non-redundant description of participation expansion, peer-relative
> catch-up, price acceleration, dispersion, onset timing, and onset magnitude
> at E1?

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

Expected symbol counts:

    BNBUSDT = 442
    BTCUSDT = 451
    ETHUSDT = 434
    SOLUSDT = 431
    XRPUSDT = 441

Material reconciliation failure:

    REPRESENTATION_V2_AUDIT_INSUFFICIENT

and STOP.

---

## 4. Sealed future boundary

No 2026 market data or metadata may be accessed.

Do not:

- enumerate 2026 files;
- open 2026 files;
- count 2026 rows;
- inspect 2026 schemas;
- hash 2026 inputs;
- compute 2026 features;
- use 2026 to repair gaps.

All accepted input must be explicitly restricted to 2024-2025 and required
pre-2024 warmup only where already part of accepted frozen data handling.

---

## 5. Strict outcome firewall

This audit MUST NOT read or use:

- C29 GROSS40/GROSS50 labels;
- C29 fixed-endpoint returns;
- C30 labels;
- C30 probabilities;
- C30 proper scores;
- P0 outcomes;
- T2 outcomes;
- MFE;
- post-E1 profit/loss;
- trading-policy results;
- strategy P&L.

No outcome-labelled artifact may be joined to V2 representation rows.

Implementation should fail closed if an outcome-labelled source is supplied.

---

## 6. Authoritative semantics

The V2 measurement specification is authoritative where it explicitly amends
V1.

The V1 measurement specification remains authoritative for unchanged
definitions.

Do not alter:

- frozen five-symbol universe;
- leave-one-out equal-weight peer basket;
- 60-minute adjacent non-overlapping intervals;
- 12-hour onset search;
- most-recent onset selection;
- symbol-onset rule;
- market-onset rule;
- 0.6 breadth majority threshold;
- positive-return participation definition;
- dispersion ddof=0;
- catch-up sequence candidate semantics.

If a material ambiguity prevents unique implementation, STOP rather than
improvise.

---

## 7. Fundamental V2 timestamp semantics

For every qualifying onset detected at boundary u:

    ONSET_INTERVAL_START_TS = u - 60m
    ONSET_INTERVAL_END_TS   = u
    ONSET_DETECTED_TS       = u

The movement interval is:

    [u-60m, u)

The onset becomes causally knowable at:

    u

These concepts MUST remain distinct.

No implementation may treat:

    u-60m

as the causal detection time.

---

## 8. E1 information cutoff

For every primary V2 quantity:

    available_ts <= E1_DECISION_TS

No entry fill or post-E1 information may enter the representation.

Where an onset is detected exactly at E1:

    ONSET_DETECTED_TS == E1_DECISION_TS

is valid.

The associated onset interval:

    [E1-60m, E1)

contains only completed pre-E1 information.

---

## 9. Frozen V2 primary representation

Audit exactly these nine variables, in this exact order:

1. NEW_JOINER_FRACTION
2. BASKET_ACCELERATION
3. PRIOR_RELATIVE_DEFICIT
4. RELATIVE_IMPROVEMENT
5. DISPERSION_CHANGE
6. MINUTES_SINCE_MARKET_ONSET_DETECTION
7. MINUTES_SINCE_SUBJECT_ONSET_DETECTION
8. SUBJECT_ONSET_INTERVAL_RETURN
9. BTC_ONSET_LEAD_MINUTES

No tenth replacement feature.

No feature may be added.

No V1 BREADTH_CHANGE primary column.

No V1 SUBJECT_EXTENSION_SINCE_ONSET primary column.

---

## 10. Required support quantities

At minimum compute or retain for audit:

- SUBJECT_PREV_RETURN
- SUBJECT_RECENT_RETURN
- BASKET_PREV_RETURN
- BASKET_RECENT_RETURN
- BREADTH_PREVIOUS
- BREADTH_RECENT
- BREADTH_CHANGE
- NEW_JOINER_FRACTION
- PERSISTENT_PARTICIPANT_FRACTION
- SUBJECT_RELATIVE_PREVIOUS
- SUBJECT_RELATIVE_RECENT
- DISPERSION_PREVIOUS
- DISPERSION_RECENT
- MARKET_ONSET_INTERVAL_START_TS
- MARKET_ONSET_INTERVAL_END_TS
- MARKET_ONSET_DETECTED_TS
- SUBJECT_ONSET_INTERVAL_START_TS
- SUBJECT_ONSET_INTERVAL_END_TS
- SUBJECT_ONSET_DETECTED_TS
- BTC_ONSET_INTERVAL_START_TS
- BTC_ONSET_INTERVAL_END_TS
- BTC_ONSET_DETECTED_TS
- MINUTES_SINCE_BTC_ONSET_DETECTION
- SUBJECT_QUALIFYING_ONSET_COUNT_12H
- BTC_QUALIFYING_ONSET_COUNT_12H
- MARKET_QUALIFYING_ONSET_COUNT_12H
- BASKET_EXTENSION_SINCE_MARKET_ONSET
- CATCHUP_SEQUENCE_CANDIDATE

Support quantities are not future predictive inputs by authorization.

---

## 11. Formula verification

Verify exact implementation of all nine primary variables.

Required identities include:

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

    MINUTES_SINCE_MARKET_ONSET_DETECTION
        = E1_DECISION_TS - MARKET_ONSET_DETECTED_TS

    MINUTES_SINCE_SUBJECT_ONSET_DETECTION
        = E1_DECISION_TS - SUBJECT_ONSET_DETECTED_TS

    BTC_ONSET_LEAD_MINUTES
        = SUBJECT_ONSET_DETECTED_TS - BTC_ONSET_DETECTED_TS

Use independent synthetic fixtures.

---

## 12. Subject onset interval return verification

For subject onset detected at u:

    SUBJECT_ONSET_INTERVAL_RETURN
        = R(subject, u-60m, u)

Required checks:

- interval start exactly u-60m;
- interval end exactly u;
- no bar beginning at u is used;
- no entry fill is used;
- no post-E1 bar is used;
- same-boundary onset at E1 remains valid;
- no future persistence confirmation.

This is the core V2 repair.

---

## 13. Same-boundary onset audit

Explicitly identify rows where:

    SUBJECT_ONSET_DETECTED_TS == E1_DECISION_TS

Report:

- count;
- percentage;
- by year;
- by symbol;
- by UTC entry month.

For all such rows verify:

    MINUTES_SINCE_SUBJECT_ONSET_DETECTION == 0

and:

    SUBJECT_ONSET_INTERVAL_RETURN is available

provided the frozen source interval is valid.

Also report how many of these rows were incomplete under the V1 primary
representation solely because SUBJECT_EXTENSION_SINCE_ONSET was unavailable.

This V1 comparison uses only V1 representation availability metadata, not
future outcomes.

---

## 14. V1 vs V2 completeness comparison

Compare outcome-free representation completeness.

Report:

    V1 complete-primary count
    V1 complete-primary percentage

Expected V1 historical result:

    397 / 2,199
    18.05%

Report:

    V2 complete-primary count
    V2 complete-primary percentage

Also report:

    absolute count improvement
    percentage-point improvement

and null reasons for any remaining V2 incompleteness.

Do not alter V2 to force a target completeness rate.

---

## 15. V2 completeness requirement

For:

    REPRESENTATION_V2_AUDIT_PASS

require:

    COMPLETE_V2_PRIMARY_REPRESENTATION >= 80%

This is the same technical threshold used by V1.

Additionally:

The V2 audit should specifically confirm whether the same-boundary onset defect
is resolved.

If V2 remains below 80%, classify NEEDS_REVISION unless a more fundamental
audit failure requires INSUFFICIENT.

---

## 16. Leave-one-out basket audit

For every subject:

- exactly four peers;
- subject excluded;
- equal arithmetic weights;
- no dynamic dropping;
- no capitalization weighting;
- no volatility weighting.

Report peer membership for all five subjects.

---

## 17. Interval-boundary audit

For every E1 row verify:

    PREVIOUS_60 = [t-120m, t-60m)
    RECENT_60   = [t-60m, t)

No overlap.

No bar at or after t.

For onset return at u:

    ONSET_60 = [u-60m, u)

Report:

- expected bar counts;
- observed bar counts;
- earliest source timestamp;
- latest source timestamp;
- any invalid/gap reason.

No interpolation.

---

## 18. Symbol onset audit

Frozen rule:

At hourly boundary u:

    recent return > 0

AND:

    recent return > previous return

Search exactly 12 hours backward.

Choose most recent qualifying event.

For every E1 row report:

- selected subject onset;
- selected BTC onset;
- count of all qualifying subject onsets within 12h;
- count of all qualifying BTC onsets within 12h.

No persistence requirement.
No absolute-return threshold.
No outcome-based filtering.

---

## 19. Market onset audit

Frozen rule:

    BREADTH_CHANGE(u) > 0

AND:

    BREADTH_RECENT(u) >= 0.6

Search exactly 12 hours backward.

Choose most recent qualifying event.

Report:

- selected market onset;
- count of qualifying market onsets within 12h.

No threshold modification.

---

## 20. Onset availability

Report for:

- MARKET_ONSET_DETECTED_TS
- SUBJECT_ONSET_DETECTED_TS
- BTC_ONSET_DETECTED_TS

for each:

- present count;
- absent count;
- percentage present;
- by year;
- by symbol;
- by UTC entry month.

Also report joint availability:

- market + subject;
- market + BTC;
- subject + BTC;
- all three.

---

## 21. Onset-rule permissiveness diagnostics

Because V1 found all onset types available for all E1 entries, V2 must
characterize how repetitive the frozen onset rule is.

For:

    SUBJECT_QUALIFYING_ONSET_COUNT_12H
    BTC_QUALIFYING_ONSET_COUNT_12H
    MARKET_QUALIFYING_ONSET_COUNT_12H

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

Also report fraction of entries with:

    exactly 1 qualifying event
    2-3 events
    4-6 events
    7-9 events
    10-12 events

Do not define any of these bands as favorable.

---

## 22. Onset recency diagnostics

For:

    MINUTES_SINCE_MARKET_ONSET_DETECTION
    MINUTES_SINCE_SUBJECT_ONSET_DETECTION
    MINUTES_SINCE_BTC_ONSET_DETECTION

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

Repeat by:

- year;
- symbol.

Fixed descriptive age bands:

    0
    (0,60]
    (60,180]
    (180,360]
    (360,720]
    no onset

No outcome association.

---

## 23. Subject onset interval return diagnostics

For:

    SUBJECT_ONSET_INTERVAL_RETURN

report:

- available count;
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
- max.

Repeat by:

- year;
- symbol;
- onset-age band.

No favorable interpretation.

---

## 24. Catch-up sequence frequency

Use unchanged V2 descriptive flag:

    CATCHUP_SEQUENCE_CANDIDATE = 1

iff:

    MARKET_ONSET_DETECTED_TS is not null
    AND PRIOR_RELATIVE_DEFICIT > 0
    AND RELATIVE_IMPROVEMENT > 0

Report:

- pooled;
- 2024;
- 2025;
- each symbol;
- each UTC entry month.

No future outcomes.

---

## 25. Transition-state cross-tabs

At minimum report:

    MARKET_ONSET_PRESENT
    x PRIOR_RELATIVE_DEFICIT_SIGN
    x RELATIVE_IMPROVEMENT_SIGN

Also report sign/state counts for:

- NEW_JOINER_FRACTION zero / positive;
- BASKET_ACCELERATION negative / zero / positive;
- DISPERSION_CHANGE negative / zero / positive;
- subject onset age zero / positive;
- market onset age zero / positive.

No future labels.

---

## 26. Structural redundancy audit

Confirm:

- BREADTH_CHANGE is support-only;
- NEW_JOINER_FRACTION is primary;
- SUBJECT_EXTENSION_SINCE_ONSET is absent from V2 primary schema;
- SUBJECT_ONSET_INTERVAL_RETURN is present;
- no aliases appear in the nine-variable matrix.

Verify algebraic support relationships exactly.

---

## 27. Empirical redundancy audit

For the nine V2 primary variables compute pairwise:

- Pearson correlation;
- Spearman correlation;
- pairwise valid observation count.

Flag:

    NEAR_REDUNDANT_LINEAR

if:

    abs(Pearson) >= 0.95

Flag:

    NEAR_REDUNDANT_RANK

if:

    abs(Spearman) >= 0.95

Do not remove variables during the audit.

---

## 28. Exact duplicate / affine audit

For every pair of primary variables, on rows where both exist, detect:

- exact numerical duplicates;
- exact sign reversals;
- deterministic affine equivalence where identifiable.

Tolerance:

    atol = 1e-12
    rtol = 1e-12

Any such relationship must be reported.

---

## 29. Primary feature distributions

For each of the nine primary variables report:

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

For discrete variables also report exact frequency table.

Repeat pooled and by year.

---

## 30. Year distribution stability

Outcome-free 2024-vs-2025 comparison is authorized.

For every primary variable report:

- 2024 mean / median / std;
- 2025 mean / median / std;
- standardized mean difference where defined;
- two-sample KS statistic.

No p-value threshold may select/remove a variable.

Purpose:

    detect representation-scale or regime shifts.

---

## 31. Symbol-distribution diagnostics

For every primary variable and symbol report:

- count;
- missing percentage;
- mean;
- median;
- p10;
- p90.

Do not normalize by symbol.

Do not fit symbol-specific transformations.

---

## 32. Future-mutation causality test

Required.

Compute full V2 representation at E1.

Then mutate all post-E1 market data to extreme values.

Recompute.

Requirement:

    all primary and support values unchanged.

Must include:

- subject prices;
- peer prices;
- BTC;
- basket;
- breadth;
- dispersion;
- onset timestamps;
- onset counts;
- onset interval return;
- catch-up candidate.

---

## 33. Entry-fill independence test

Required.

Mutate:

- entry execution price;
- entry execution timestamp;
- future first-open information;

without changing valid pre-E1 state.

Requirement:

    full V2 representation unchanged.

---

## 34. Same-boundary causality test

Required synthetic fixture:

    SUBJECT_ONSET_DETECTED_TS == E1_DECISION_TS

Verify:

    SUBJECT_ONSET_INTERVAL_START_TS == E1-60m
    SUBJECT_ONSET_INTERVAL_END_TS   == E1
    MINUTES_SINCE_SUBJECT_ONSET_DETECTION == 0
    SUBJECT_ONSET_INTERVAL_RETURN is finite/valid
    no E1-open or later bar was used

This test is mandatory.

---

## 35. Onset-search tests

Synthetic tests must cover:

- onset at E1;
- onset 1h before;
- multiple qualifying onsets -> most recent;
- exact 12h boundary;
- outside 12h rejected;
- no onset -> null;
- positive but non-improving -> no onset;
- improving but non-positive -> no onset;
- equality recent == previous -> no onset;
- missing required interval -> no fabricated onset.

---

## 36. Market-onset tests

Synthetic tests must cover:

- breadth change positive + exactly 3/5 positive -> onset;
- positive breadth change + 2/5 positive -> no onset;
- breadth_recent == 0.6 accepted;
- breadth_change == 0 rejected;
- high breadth without increase -> no new onset;
- most recent qualifying event selected;
- qualifying-event count includes all events.

---

## 37. Reproducibility

Record:

- contract hash;
- V1 representation spec hash;
- V1 measurement spec hash;
- V2 measurement spec hash;
- implementation hash;
- test hash;
- source hashes;
- population hash;
- ordered V2 schema hash;
- semantic representation hash;
- environment;
- Python version;
- dependencies;
- command;
- git HEAD;
- dirty/untracked status.

Repeated execution from identical inputs must reproduce core results.

---

## 38. Required artifact namespace

Write only to:

    artifacts/catchup_transition_representation_audit_v2/

Do NOT overwrite:

    artifacts/catchup_transition_representation_audit/

---

## 39. Required artifacts

Required:

- run_manifest.json
- provenance.json
- population_reconciliation.json
- source_boundary_audit.json
- representation_schema_v2.json
- formula_audit_v2.json
- interval_boundary_audit_v2.json
- loo_basket_audit.json
- onset_semantics_audit_v2.json
- market_onset_audit.json
- onset_availability.json
- qualifying_onset_count_distributions.json
- same_boundary_onset_audit.json
- feature_availability_v2.json
- v1_v2_completeness_comparison.json
- catchup_sequence_frequency.json
- transition_state_cross_tabs.json
- onset_timing_distributions.json
- onset_age_bands.json
- onset_interval_return_distributions.json
- structural_redundancy_v2.json
- pearson_correlation_v2.json
- spearman_correlation_v2.json
- empirical_redundancy_flags_v2.json
- exact_duplicate_audit_v2.json
- feature_distributions_v2.json
- year_distribution_stability_v2.json
- symbol_distribution_diagnostics_v2.json
- future_mutation_test_v2.json
- entry_fill_independence_test_v2.json
- interpretation_predicates_v2.json
- final_summary_v2.json
- reproducibility_hashes_v2.json

Avoid unnecessary row-level dumps.

---

## 40. Frozen V2 audit classification

Return exactly one overall classification.

### REPRESENTATION_V2_AUDIT_PASS

Use only if ALL hold:

1. exact 2,199 E1 population reconciles;
2. exact nine-variable schema matches V2;
3. all formulas pass;
4. movement-interval and detection-time semantics pass;
5. same-boundary onset at E1 is causally computable;
6. V2 complete-primary rate >= 80%;
7. the V1 same-boundary completeness defect is materially resolved;
8. all primary values satisfy causal availability;
9. future mutation changes no representation value;
10. entry-fill mutation changes no representation value;
11. no outcome-labelled source was read;
12. no 2026 data/metadata was accessed;
13. no unresolved exact duplicate/sign-reversal/affine duplicate exists among
    primary variables;
14. no material implementation ambiguity remains.

This classification means only:

    V2 is technically coherent enough for human review of whether a later
    predictive experiment should be designed.

It does NOT mean:

- predictive signal exists;
- catch-up sequence is profitable;
- E1 is correctly timed;
- C31 is authorized.

### REPRESENTATION_V2_NEEDS_REVISION

Use if the audit executes validly but one or more occur:

- V2 completeness remains below 80%;
- same-boundary onset remains causally unresolved;
- severe primary redundancy remains;
- onset-rule behavior appears so repetitive that "onset" functions more like
  a generic recurring condition than a distinct transition event;
- severe year/symbol scale pathology exists;
- representation semantics remain materially ambiguous.

The "repetitive onset" point must be supported by descriptive onset-count and
recency distributions only.

Do NOT invent an outcome-based threshold.

### REPRESENTATION_V2_AUDIT_INSUFFICIENT

Use only if:

- population reconciliation fails;
- input/source integrity fails;
- causal timing cannot be established;
- specification ambiguity prevents unique implementation;
- outcome firewall cannot be guaranteed;
- 2026 boundary cannot be guaranteed.

---

## 41. No automatic pass from completeness

Even if V2 completeness rises above 80%:

    completeness alone does not imply PASS.

The audit must still evaluate:

- timestamp correctness;
- semantic consistency;
- onset repetitiveness;
- redundancy;
- distribution pathologies;
- causality invariance.

---

## 42. No automatic failure from onset universality

If all E1 rows again have detectable onsets:

    this alone does not force NEEDS_REVISION.

The executor must report:

- count of qualifying events per 12h;
- most-recent onset age;
- same-boundary detection frequency;
- distribution of onset interval returns.

Human review should assess whether the event definition remains behaviorally
meaningful.

Do not retrospectively change the onset rule.

---

## 43. No feature removal or revision

Even if a primary variable is redundant or pathological:

- do not remove it;
- do not replace it;
- do not redefine it;
- do not rerun V2 with another schema.

Report the issue and classify accordingly.

Any V3 requires a new prospective amendment.

---

## 44. No predictive work

The audit MUST NOT compute:

- endpoint-label prevalence by feature state;
- GROSS40/GROSS50 enrichment;
- future-return means;
- Brier;
- log loss;
- ROC AUC;
- PR-AUC;
- probabilities;
- model coefficients;
- strategy P&L;
- trading thresholds.

No model of any kind.

---

## 45. No C31

Do not:

- create a C31 contract;
- implement C31;
- fit any predictive model;
- select final predictive features from outcome evidence.

STOP at the V2 representation audit.

---

## 46. Required focused tests

Focused tests must include at minimum:

- exact E1 count/hash;
- year/symbol counts;
- exact nine-variable schema/order;
- exact five-symbol universe;
- leave-one-out peers;
- exact 60m non-overlap;
- exact onset movement interval;
- exact onset detection timestamp;
- same-boundary E1 onset behavior;
- no E1-open use;
- no fill dependence;
- no post-E1 dependence;
- onset interval return arithmetic;
- basket acceleration;
- relative deficit;
- relative improvement;
- dispersion ddof=0;
- 12h onset window;
- most-recent onset selection;
- qualifying-event counting;
- market onset 0.6 boundary;
- NEW_JOINER primary / BREADTH_CHANGE support-only;
- no SUBJECT_EXTENSION_SINCE_ONSET primary;
- exact redundancy checks;
- deterministic correlation output;
- deterministic semantic hashes;
- no outcome artifact access;
- no 2026 access.

Run focused tests.

Run full repository suite once if scientific/runtime source code changes.

---

## 47. Governance

Do NOT modify:

- C29 scientific behavior;
- C30 scientific behavior;
- V1 representation spec;
- V1 measurement spec;
- V2 measurement spec;
- V1 audit contract;
- V1 audit artifacts/results;
- this frozen V2 audit contract.

Do NOT:

- stage implementation/results;
- commit implementation/results;
- push;
- access 2026;
- start C31.

The V2 audit contract itself may be committed prospectively.

---

## 48. Final report

Report:

1. V2 audit contract SHA-256;
2. representation-spec hash;
3. V1 measurement-spec hash;
4. V2 measurement-spec hash;
5. exact E1 reconciliation;
6. source boundary verification;
7. outcome firewall verification;
8. exact nine-variable schema;
9. formula audit;
10. interval audit;
11. movement-interval vs detection-time audit;
12. leave-one-out basket audit;
13. same-boundary onset count and rate;
14. same-boundary causal validity;
15. V1 complete representation count/rate;
16. V2 complete representation count/rate;
17. V1->V2 completeness improvement;
18. remaining null reasons;
19. onset availability;
20. qualifying onset count distributions;
21. onset recency distributions;
22. subject onset interval-return distributions;
23. catch-up sequence frequency;
24. transition-state cross-tabs;
25. structural redundancy;
26. Pearson matrix summary;
27. Spearman matrix summary;
28. near-redundancy flags;
29. exact duplicate/affine audit;
30. pooled feature distributions;
31. 2024-vs-2025 distribution stability;
32. symbol distributions;
33. future-mutation test;
34. entry-fill-independence test;
35. exact frozen classification:
       REPRESENTATION_V2_AUDIT_PASS
       REPRESENTATION_V2_NEEDS_REVISION
       REPRESENTATION_V2_AUDIT_INSUFFICIENT
36. explicit statement that PASS does not imply predictive usefulness;
37. assessment of whether onset detection appears distinctive or highly
    repetitive, based only on outcome-free diagnostics;
38. whether later predictive-contract DESIGN is technically justified;
39. limitations;
40. artifact hash verification;
41. focused-test result;
42. full-suite result if run;
43. git diff --check;
44. git status --short;
45. confirmation no future outcomes/labels were read;
46. confirmation no model was fit;
47. confirmation no feature was selected/removed;
48. confirmation no 2026 data/metadata was accessed;
49. confirmation nothing implementation-related was staged/committed/pushed;
50. confirmation C31 was not started.

STOP.
