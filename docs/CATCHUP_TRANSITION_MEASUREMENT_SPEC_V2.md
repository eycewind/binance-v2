# Catch-Up Transition Measurement Specification V2

Status: prospective design amendment.

This document supersedes the measurement semantics in:

    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md

only where explicitly stated below.

The original representation hypothesis remains unchanged:

    docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md

This V2 amendment is motivated exclusively by the outcome-free causal
representation audit completed at repository checkpoint:

    ec871bd

No future-return outcomes, predictive labels, model scores, P0/T2/MFE,
profitability, or 2026 information were used to define these amendments.

This document does NOT authorize:

- C31;
- predictive model fitting;
- outcome analysis;
- threshold search;
- feature search;
- trading-policy construction;
- P&L optimization;
- 2026 access.

---

## 1. Motivation for V2

The frozen V1 representation audit established:

- exact 2,199-entry E1 population reconciliation;
- all causal timing and formula checks passed;
- all three onset types were detectable for all 2,199 entries;
- catch-up sequence candidate frequency was 878 / 2,199 = 39.93%;
- complete ten-variable representation was only 397 / 2,199 = 18.05%;
- the dominant completeness failure arose when subject onset was detected
  exactly at E1;
- V1 SUBJECT_EXTENSION_SINCE_ONSET required the open at the onset detection
  timestamp, which is not strictly pre-E1 when onset detection equals E1;
- BREADTH_CHANGE and NEW_JOINER_FRACTION were highly rank-redundant:
      Spearman = 0.95917;
- no exact/sign-reversed/affine duplicate existed among the ten primary
  variables.

V2 addresses these representation issues only.

---

## 2. Frozen behavioral hypothesis

The underlying hypothesis remains:

    An E1 transition is more likely to persist when market participation is
    expanding, the candidate asset initially lags that move, its relative
    movement begins improving, and E1 occurs before the asset becomes
    materially extended.

Future outcomes remain evaluation-only.

V2 does not redefine a successful transition.

---

## 3. Fundamental timestamp distinction

V2 explicitly separates:

    MOVEMENT_INTERVAL

from:

    DETECTION_TIME

For a qualifying onset evaluated at boundary u:

    ONSET_INTERVAL_START_TS = u - 60 minutes

    ONSET_INTERVAL_END_TS   = u

    ONSET_DETECTED_TS       = u

The directional movement used to recognize the onset occurred over:

    [u - 60m, u)

The onset becomes causally knowable only at:

    u

This distinction is mandatory.

Do not describe u-60m as the time at which the onset was known.

---

## 4. Frozen base intervals

No change from V1.

At any evaluation boundary u:

    PREVIOUS_60(u)
        = [u - 120m, u - 60m)

    RECENT_60(u)
        = [u - 60m, u)

Intervals are adjacent and non-overlapping.

Only completed accepted 1-minute bars are used.

---

## 5. Symbol onset rule

No change from V1.

For symbol s, a qualifying directional onset is detected at hourly boundary u
iff:

    R(s, RECENT_60(u)) > 0

AND:

    R(s, RECENT_60(u)) > R(s, PREVIOUS_60(u))

Search exactly 12 hours backward from E1.

Use the most recent qualifying event.

For every detected symbol onset retain:

    SYMBOL_ONSET_INTERVAL_START_TS
    SYMBOL_ONSET_INTERVAL_END_TS
    SYMBOL_ONSET_DETECTED_TS

where:

    INTERVAL_END_TS == DETECTED_TS

No future confirmation.

---

## 6. Market-participation onset rule

No change from V1.

At hourly boundary u:

    BREADTH_CHANGE(u) > 0

AND:

    BREADTH_RECENT(u) >= 0.6

defines a qualifying market-participation onset.

Search exactly 12 hours backward.

Use the most recent qualifying event.

Retain:

    MARKET_ONSET_INTERVAL_START_TS
    MARKET_ONSET_INTERVAL_END_TS
    MARKET_ONSET_DETECTED_TS

Again:

    onset interval
        !=
    causal detection time

---

## 7. BTC onset

BTC uses the identical symbol-onset semantics.

Retain:

    BTC_ONSET_INTERVAL_START_TS
    BTC_ONSET_INTERVAL_END_TS
    BTC_ONSET_DETECTED_TS

BTC remains a price-leadership reference only.

No causal transmission claim is made.

---

## 8. V1 feature removed

The following V1 primary variable is removed:

    SUBJECT_EXTENSION_SINCE_ONSET

Reason:

When:

    SUBJECT_ONSET_DETECTED_TS == E1_DECISION_TS

the V1 extension definition required a reference open at the detection
timestamp.

That value is not strictly pre-E1 and therefore cannot be used as a causal
E1-time measurement.

This is a representation-definition defect, not an implementation defect.

Do NOT patch it by:

- allowing the E1 open;
- using entry fill;
- shifting the onset timestamp backward;
- inventing another price;
- dropping all same-boundary onset rows.

V2 replaces the variable entirely.

---

## 9. New primary variable: subject onset interval return

Define:

    SUBJECT_ONSET_INTERVAL_RETURN

as the subject return over the completed interval that triggered the most
recent qualifying subject onset:

    R(
      subject,
      SUBJECT_ONSET_INTERVAL_START_TS,
      SUBJECT_ONSET_INTERVAL_END_TS
    )

Equivalently, if onset was detected at u:

    SUBJECT_ONSET_INTERVAL_RETURN
        = R(subject, u-60m, u)

This value is fully known at u.

If:

    u == E1_DECISION_TS

the complete onset interval still lies strictly before E1:

    [E1-60m, E1)

and is therefore causally valid.

If no subject onset exists within the frozen 12-hour search:

    SUBJECT_ONSET_INTERVAL_RETURN = null

No imputation.

---

## 10. Interpretation of onset interval return

SUBJECT_ONSET_INTERVAL_RETURN answers:

    How large was the completed directional move that caused the subject onset
    to become detectable?

It does NOT answer:

- how far price has moved since some unknowable turning point;
- how much remaining upside exists;
- whether the move is exhausted;
- future continuation.

Large values may indicate:

- strong emerging movement;
- already substantial extension;
- one unusually large interval.

No favorable sign beyond the qualifying onset semantics is assumed.

---

## 11. Detection-age semantics

Rename onset-age concepts explicitly around DETECTION.

### Subject

    MINUTES_SINCE_SUBJECT_ONSET_DETECTION
        = E1_DECISION_TS - SUBJECT_ONSET_DETECTED_TS

### Market

    MINUTES_SINCE_MARKET_ONSET_DETECTION
        = E1_DECISION_TS - MARKET_ONSET_DETECTED_TS

### BTC

Where useful as a support quantity:

    MINUTES_SINCE_BTC_ONSET_DETECTION
        = E1_DECISION_TS - BTC_ONSET_DETECTED_TS

If onset is detected exactly at E1:

    age = 0

This is valid and expected.

Do not interpret zero as missing.

---

## 12. BTC lead timing V2

Define:

    BTC_ONSET_LEAD_MINUTES

using detection timestamps:

    SUBJECT_ONSET_DETECTED_TS - BTC_ONSET_DETECTED_TS

Therefore:

    positive
        BTC was detected earlier than the subject

    zero
        both detected at the same hourly boundary

    negative
        subject was detected earlier than BTC

No movement-interval-start timestamp is used for this feature.

---

## 13. Breadth redundancy amendment

V1 included both:

    BREADTH_CHANGE
    NEW_JOINER_FRACTION

as primary variables.

The outcome-free V1 audit found:

    Spearman(BREADTH_CHANGE, NEW_JOINER_FRACTION)
        = 0.95917

V2 retains:

    NEW_JOINER_FRACTION

as the primary participation-expansion quantity.

V2 demotes:

    BREADTH_CHANGE

to SUPPORT/AUDIT status.

Reason:

NEW_JOINER_FRACTION maps directly to the behavioral mechanism:

    additional assets are beginning to participate

whereas BREADTH_CHANGE is a net quantity combining joining and leaving.

No future-return evidence was used for this choice.

---

## 14. Breadth support quantities retained

Continue computing for audit purposes:

    BREADTH_PREVIOUS
    BREADTH_RECENT
    BREADTH_CHANGE
    PERSISTENT_PARTICIPANT_FRACTION
    NEW_JOINER_FRACTION

BREADTH_CHANGE remains necessary for the frozen market-onset rule.

Its demotion from the primary representation does NOT change market-onset
semantics.

---

## 15. V2 compact primary representation

The V2 primary representation contains exactly nine variables:

1. NEW_JOINER_FRACTION
2. BASKET_ACCELERATION
3. PRIOR_RELATIVE_DEFICIT
4. RELATIVE_IMPROVEMENT
5. DISPERSION_CHANGE
6. MINUTES_SINCE_MARKET_ONSET_DETECTION
7. MINUTES_SINCE_SUBJECT_ONSET_DETECTION
8. SUBJECT_ONSET_INTERVAL_RETURN
9. BTC_ONSET_LEAD_MINUTES

No tenth replacement variable is added.

The purpose of V2 is to improve semantic clarity and causal completeness, not
to preserve feature count.

---

## 16. Support variables

The following remain permitted as support/audit quantities:

- SUBJECT_PREV_RETURN
- SUBJECT_RECENT_RETURN
- BASKET_PREV_RETURN
- BASKET_RECENT_RETURN
- BREADTH_PREVIOUS
- BREADTH_RECENT
- BREADTH_CHANGE
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
- BASKET_EXTENSION_SINCE_MARKET_ONSET
- CATCHUP_SEQUENCE_CANDIDATE

Support status does not authorize predictive use.

---

## 17. Catch-up sequence candidate

No change in conceptual definition.

For descriptive auditing:

    CATCHUP_SEQUENCE_CANDIDATE = 1

iff:

    MARKET_ONSET_DETECTED_TS is not null

AND:

    PRIOR_RELATIVE_DEFICIT > 0

AND:

    RELATIVE_IMPROVEMENT > 0

Otherwise:

    0

Detection-time naming replaces ambiguous V1 onset naming.

No future confirmation.

---

## 18. Catch-up sequence ordering

V2 distinguishes causal detection order from movement interval.

A conceptual sequence may therefore be described using:

    MARKET_ONSET_DETECTED_TS
    SUBJECT_ONSET_DETECTED_TS
    E1_DECISION_TS

but this alone does not prove a full market-transition sequence.

PRIOR_RELATIVE_DEFICIT and RELATIVE_IMPROVEMENT remain contemporaneous
E1-state measurements.

Do not infer an unobserved exact catch-up start timestamp.

---

## 19. No transition-end semantics

V2 still defines no transition-end rule.

Therefore the representation may characterize:

- no prior detected onset;
- onset detected at E1;
- onset detected N minutes before E1.

It may NOT classify E1 as:

- before the whole transition;
- during the whole transition;
- after the whole transition;

because completion/end has not been prospectively defined.

---

## 20. Onset universality remains an open representation question

The V1 audit found all onset types available for all 2,199 E1 entries.

V2 does NOT modify the onset rule in response to that observation.

Reason:

Changing the rule simply to produce a more selective distribution would be
representation tuning.

Instead, a V2 outcome-free audit should report:

- detection ages;
- repeated qualifying-onset frequency within the 12-hour window;
- time since most recent detection;
- onset interval return distributions;
- market-onset frequency;
- subject-onset frequency;
- BTC-onset frequency.

Human review may later decide whether the rule is behaviorally too permissive.

No future outcomes may inform that decision.

---

## 21. Repeated qualifying onset count

V2 adds one SUPPORT diagnostic:

    SUBJECT_QUALIFYING_ONSET_COUNT_12H

equal to the number of hourly boundaries in the 12-hour search window that
satisfy the frozen subject-onset condition.

Likewise:

    BTC_QUALIFYING_ONSET_COUNT_12H

and:

    MARKET_QUALIFYING_ONSET_COUNT_12H

These are audit diagnostics only.

They are NOT part of the nine-variable primary representation.

Purpose:

    determine whether "most recent onset" is usually one distinctive event or
    one of many repeatedly qualifying intervals.

No outcome association may be computed.

---

## 22. Primary causal availability

For every V2 primary variable:

    available_ts <= E1_DECISION_TS

SUBJECT_ONSET_INTERVAL_RETURN uses data ending exactly at:

    SUBJECT_ONSET_DETECTED_TS

and when detection is at E1:

    source interval ends at E1 but contains no bar at or after E1.

Exact bar semantics must remain:

    [u-60m, u)

not inclusive of the bar beginning at u.

---

## 23. Entry-fill independence

No V2 variable may use:

- entry fill price;
- future entry execution;
- subsequent 1-minute open;
- slippage-adjusted fill.

Mutating future fill information must leave the complete V2 representation
unchanged.

---

## 24. Future-mutation invariance

Mutating all market values after E1 must not change:

- any nine primary variables;
- onset intervals;
- onset detection timestamps;
- onset counts;
- support variables;
- CATCHUP_SEQUENCE_CANDIDATE.

This must be tested.

---

## 25. Redundancy rules V2

The V2 audit must again test:

### Exact duplicates

No two primary variables may be exact duplicates.

### Sign reversals

No two primary variables may be exact sign reversals.

### Affine equivalence

No deterministic affine duplicate may be silently retained.

### Empirical dependence

Report pairwise Pearson and Spearman correlations.

Flag:

    abs(Pearson) >= 0.95

or:

    abs(Spearman) >= 0.95

as near redundancy.

Do not remove another variable during the audit.

---

## 26. Expected V2 completeness effect

V2 is specifically designed so that:

    SUBJECT_ONSET_DETECTED_TS == E1_DECISION_TS

does NOT make the primary representation incomplete.

In that case:

    MINUTES_SINCE_SUBJECT_ONSET_DETECTION = 0

and:

    SUBJECT_ONSET_INTERVAL_RETURN

is computed from:

    [E1-60m, E1)

Therefore the V1 artificial completeness loss should disappear.

This is a design expectation, not a guaranteed audit result.

Do not fabricate completeness if other legitimate null conditions occur.

---

## 27. Frozen measurement units

Use:

    returns                  decimal fraction
    breadth/fractions        [0,1]
    dispersion               decimal-return units
    time                     integer or exact numeric minutes
    timestamps               UTC

No basis-point conversion inside the stored primary representation.

Reporting may additionally show human-readable basis points.

---

## 28. Missingness

No imputation.

If a required historical interval is unavailable:

    corresponding measurement = null

If an onset genuinely does not exist within the 12-hour window:

    onset-derived measurements = null

Zero detection age is NOT missing.

Zero return where mathematically valid is NOT missing.

---

## 29. V2 representation schema

Exact primary order:

    NEW_JOINER_FRACTION
    BASKET_ACCELERATION
    PRIOR_RELATIVE_DEFICIT
    RELATIVE_IMPROVEMENT
    DISPERSION_CHANGE
    MINUTES_SINCE_MARKET_ONSET_DETECTION
    MINUTES_SINCE_SUBJECT_ONSET_DETECTION
    SUBJECT_ONSET_INTERVAL_RETURN
    BTC_ONSET_LEAD_MINUTES

This order should be hash-frozen before any future predictive experiment.

No predictive experiment is authorized here.

---

## 30. Outcome firewall

Same as V1.

Do not access:

- C29 opportunity labels;
- endpoint returns;
- C30 predictions;
- C30 labels;
- P0;
- T2;
- MFE;
- P&L.

No future-return outcome may be joined to V2 representation rows.

---

## 31. 2026 prohibition

No 2026 data or metadata may be:

- enumerated;
- opened;
- counted;
- hashed;
- validated;
- used for gap completion;
- used for any audit.

V2 remains 2024-2025 only.

---

## 32. Required V2 audit before predictive work

A separate outcome-free V2 audit must verify:

1. exact E1 population reconciliation;
2. exact V2 formulas;
3. movement-interval vs detection-time semantics;
4. nine-variable schema;
5. primary completeness;
6. same-boundary onset behavior;
7. onset interval return correctness;
8. onset qualifying-event counts;
9. causal availability;
10. future-mutation invariance;
11. entry-fill independence;
12. structural redundancy;
13. empirical redundancy;
14. year/symbol distributions;
15. no outcome access;
16. no 2026 access.

Do not proceed directly to prediction.

---

## 33. Required V2 synthetic tests

At minimum:

### Detection semantics

- onset movement interval [u-60m,u);
- detection time exactly u;
- no bar at u enters onset interval return;
- E1 == u yields valid onset interval return;
- E1 == u yields onset detection age zero.

### Most-recent onset

- multiple qualifying events;
- most recent selected;
- qualifying-event count records all valid events in 12h.

### Boundary

- event exactly 12h before E1 is handled according to frozen inclusive search
  boundary semantics;
- event outside 12h rejected.

### Breadth

- BREADTH_CHANGE remains market-onset support;
- NEW_JOINER_FRACTION remains primary;
- no BREADTH_CHANGE primary column.

### Causality

- mutate E1 open/fill -> unchanged representation;
- mutate all post-E1 bars -> unchanged representation.

### Redundancy

- exact primary order;
- nine variables only;
- no V1 SUBJECT_EXTENSION_SINCE_ONSET primary field.

---

## 34. Relationship to V1 audit

V1 audit results remain historical evidence about V1.

Do not overwrite:

    artifacts/catchup_transition_representation_audit/

V2 must write to a separate artifact namespace.

Suggested:

    artifacts/catchup_transition_representation_audit_v2/

Do not mutate the V1 implementation/results to make V1 appear to have passed.

---

## 35. Governance

Until the V2 audit is completed and reviewed:

- no C31;
- no model;
- no predictive score;
- no outcome comparison;
- no horizon/hurdle selection;
- no strategy;
- no P&L optimization;
- no 2026.

V2 is a representation amendment only.

---

## 36. Expected decision after V2 audit

The human review after the V2 audit should decide only:

    Is this representation technically coherent enough to freeze for a
    later predictive experiment?

Possible reasons to stop/revise again include:

- low legitimate availability;
- unresolved timestamp ambiguity;
- primary near-duplication;
- onset rule clearly functioning as an almost continuous generic momentum
  condition rather than a meaningful event;
- severe symbol/year scale pathology.

No future outcome evidence is required for that decision.

---

## 37. Scope termination

This specification ends after the V2 measurement definitions are frozen.

Do not implement predictive C31 under this document.

STOP.
