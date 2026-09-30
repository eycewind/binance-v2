# Catch-Up Transition Measurement Specification V3

Status: prospective semantic amendment.

This document supersedes V2 only where explicitly stated.

Authoritative prior documents:

    docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V2.md

Outcome-free V2 audit checkpoint:

    bc128fd

No future-return outcomes, predictive labels, model scores, P0/T2/MFE,
profitability, or 2026 information were used to define V3.

This document does NOT authorize:

- C31;
- predictive modeling;
- outcome analysis;
- feature search;
- threshold search;
- trading-policy construction;
- P&L optimization;
- 2026 access.

---

## 1. Motivation

V2 corrected the causal completeness defect in V1.

V2 audit results included:

    complete primary representation:
        2,199 / 2,199 = 100%

    same-boundary subject onset:
        1,802 / 2,199 = 81.95%

    mean qualifying subject onset conditions per 12h:
        5.31

    entries with exactly one qualifying subject condition:
        0

    median subject onset detection age:
        0 minutes

This demonstrates that the frozen V2 subject-onset condition behaves as a
frequently recurring momentum condition rather than a distinctive onset event.

V3 changes the semantics of onset.

A condition being TRUE is not itself an onset.

An onset occurs only when a causal state transitions:

    FALSE -> TRUE

No future outcome evidence motivates this change.

---

## 2. Behavioral hypothesis remains unchanged

The primary hypothesis remains:

    An E1 transition is more likely to persist when market participation is
    expanding, the candidate asset initially lags that move, its relative
    movement begins improving, and E1 occurs before the asset becomes
    substantially mature.

V3 attempts to represent the beginning of the relevant price-state episodes
more faithfully.

Future return remains evaluation-only.

---

## 3. Frozen universe and time basis

No change.

Universe:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

Primary peer reference for subject s:

    equal-weight leave-one-out basket of the other four symbols

Primary transition interval:

    60 minutes

At boundary u:

    PREVIOUS_60(u)
        = [u-120m, u-60m)

    RECENT_60(u)
        = [u-60m, u)

All bars must be completed before u.

---

## 4. Relative quantities

No change to the underlying causal quantities.

For subject s:

    SUBJECT_PREV_RETURN(u)
    SUBJECT_RECENT_RETURN(u)

and leave-one-out basket:

    BASKET_PREV_RETURN(u)
    BASKET_RECENT_RETURN(u)

Define:

    SUBJECT_RELATIVE_PREVIOUS(u)
        = SUBJECT_PREV_RETURN(u)
          - BASKET_PREV_RETURN(u)

    SUBJECT_RELATIVE_RECENT(u)
        = SUBJECT_RECENT_RETURN(u)
          - BASKET_RECENT_RETURN(u)

    PRIOR_RELATIVE_DEFICIT(u)
        = -SUBJECT_RELATIVE_PREVIOUS(u)

    RELATIVE_IMPROVEMENT(u)
        = SUBJECT_RELATIVE_RECENT(u)
          - SUBJECT_RELATIVE_PREVIOUS(u)

No thresholds beyond sign are introduced.

---

## 5. Catch-up state

Define the causal Boolean state:

    CATCHUP_STATE(u) = TRUE

iff:

    PRIOR_RELATIVE_DEFICIT(u) > 0

AND:

    RELATIVE_IMPROVEMENT(u) > 0

Otherwise:

    FALSE

Interpretation:

    the subject was behind its leave-one-out peer basket over the preceding
    interval and its relative movement improved over the recent interval.

This is a descriptive price state.

It does not mean:

- profitable;
- successful;
- persistent;
- confirmed by the future.

---

## 6. Catch-up onset

A catch-up onset is detected at boundary u iff:

    CATCHUP_STATE(u) == TRUE

AND:

    CATCHUP_STATE(u-60m) == FALSE

This is a state transition:

    FALSE -> TRUE

It is NOT sufficient merely for CATCHUP_STATE(u) to be TRUE.

The state at u-60m must itself be computed causally from completed data
available at u-60m.

---

## 7. Catch-up onset timestamps

For a catch-up onset detected at u:

    CATCHUP_ONSET_INTERVAL_START_TS = u - 60m

    CATCHUP_ONSET_INTERVAL_END_TS = u

    CATCHUP_ONSET_DETECTED_TS = u

The state transition becomes knowable only at u.

No earlier timestamp is treated as known onset.

---

## 8. Catch-up onset search

At E1 decision timestamp t:

Search exactly:

    [t-12h, t]

over valid completed hourly boundaries.

Select:

    most recent qualifying FALSE -> TRUE catch-up onset

If none exists:

    CATCHUP_ONSET_DETECTED_TS = null

No fallback.

No alternative lookback.

No future confirmation.

---

## 9. Catch-up onset age

If a catch-up onset exists:

    MINUTES_SINCE_CATCHUP_ONSET
        = t - CATCHUP_ONSET_DETECTED_TS

If detected exactly at E1:

    MINUTES_SINCE_CATCHUP_ONSET = 0

Zero is valid.

If no onset exists:

    null

---

## 10. Catch-up onset interval magnitude

Define:

    CATCHUP_ONSET_RELATIVE_IMPROVEMENT

as:

    RELATIVE_IMPROVEMENT(u)

at the selected catch-up onset boundary u.

This measures the magnitude of relative improvement when the catch-up state
first transitioned from FALSE to TRUE.

It does not use future persistence or future return.

---

## 11. Catch-up episode diagnostics

For outcome-free audit purposes retain:

    CATCHUP_STATE_AT_E1

    CATCHUP_ONSET_COUNT_12H

where:

    CATCHUP_ONSET_COUNT_12H

is the count of FALSE -> TRUE catch-up state transitions within the frozen
12-hour search window.

This is an audit/support quantity only.

It is NOT automatically a predictive variable.

---

## 12. Market participation quantities

Continue to compute:

    BREADTH_PREVIOUS(u)
    BREADTH_RECENT(u)
    BREADTH_CHANGE(u)
    NEW_JOINER_FRACTION(u)
    PERSISTENT_PARTICIPANT_FRACTION(u)

using the frozen five-symbol universe.

No change to return or participation arithmetic.

---

## 13. Market expansion state

Define:

    MARKET_EXPANSION_STATE(u) = TRUE

iff:

    BREADTH_CHANGE(u) > 0

AND:

    BREADTH_RECENT(u) >= 0.6

Otherwise:

    FALSE

This is the same structural condition previously used for market onset.

V3 changes only the onset semantics.

---

## 14. Market expansion onset

A market expansion onset occurs at boundary u iff:

    MARKET_EXPANSION_STATE(u) == TRUE

AND:

    MARKET_EXPANSION_STATE(u-60m) == FALSE

Therefore onset is:

    FALSE -> TRUE

not every qualifying market-expansion hour.

---

## 15. Market expansion onset timestamps

For qualifying onset at u:

    MARKET_EXPANSION_ONSET_INTERVAL_START_TS = u - 60m

    MARKET_EXPANSION_ONSET_INTERVAL_END_TS = u

    MARKET_EXPANSION_ONSET_DETECTED_TS = u

The onset becomes causally knowable at u.

---

## 16. Market expansion onset search

At E1 timestamp t:

Search exactly:

    [t-12h, t]

Select:

    most recent FALSE -> TRUE market-expansion onset

If none exists:

    null

No fallback.

No threshold revision.

---

## 17. Market expansion onset age

If available:

    MINUTES_SINCE_MARKET_EXPANSION_ONSET
        = t - MARKET_EXPANSION_ONSET_DETECTED_TS

If onset occurs at E1:

    0

If absent:

    null

---

## 18. Market expansion episode diagnostics

For audit only retain:

    MARKET_EXPANSION_STATE_AT_E1
    MARKET_EXPANSION_ONSET_COUNT_12H

where the count refers only to FALSE -> TRUE transitions.

Do not count every TRUE hourly boundary as another onset.

---

## 19. Removal of V2 absolute subject onset

V3 removes the V2 generic absolute-price subject-onset machinery from the
primary representation.

Removed from primary semantics:

    SUBJECT_ONSET_DETECTED_TS
    MINUTES_SINCE_SUBJECT_ONSET_DETECTION
    SUBJECT_ONSET_INTERVAL_RETURN

Reason:

The V2 audit showed that the absolute subject momentum condition was strongly
coupled to E1 and repeatedly satisfied.

E1 already provides the primary absolute-trend transition anchor.

V3 instead uses the relative catch-up episode explicitly required by the
behavioral hypothesis.

V2 values remain historical audit evidence and must not be overwritten.

---

## 20. BTC leadership

BTC remains scientifically interesting but is no longer a primary V3 feature.

BTC leadership becomes SUPPORT/AUDIT context only.

Reason:

The core catch-up hypothesis can be represented without assuming BTC is always
the initiating leader.

For outcome-free diagnostics, BTC movement/onset timing may still be computed
using frozen causal data.

No BTC-derived variable enters the V3 primary representation unless a future
prospective amendment explicitly promotes it.

---

## 21. New-joiner fraction

Retain as primary:

    NEW_JOINER_FRACTION

BREADTH_CHANGE remains support/audit and is required for
MARKET_EXPANSION_STATE.

This preserves the V2 redundancy decision.

---

## 22. Basket acceleration

Retain unchanged:

    BASKET_ACCELERATION
        = BASKET_RECENT_RETURN
          - BASKET_PREV_RETURN

This represents strengthening/weakening of peer-basket movement.

No favorable sign is assumed.

---

## 23. Dispersion change

Retain unchanged:

    DISPERSION_CHANGE
        = DISPERSION_RECENT
          - DISPERSION_PREVIOUS

with population standard deviation:

    ddof = 0

No favorable sign is assumed.

---

## 24. Prior relative deficit

Retain unchanged:

    PRIOR_RELATIVE_DEFICIT

This measures how far the subject lagged its peer basket during the previous
interval.

Do not threshold by magnitude.

---

## 25. Relative improvement

Retain unchanged:

    RELATIVE_IMPROVEMENT

This measures change in subject relative movement from previous to recent
interval.

Do not threshold by magnitude beyond the state-sign semantics.

---

## 26. V3 primary representation

The V3 primary representation contains exactly eight variables:

1. NEW_JOINER_FRACTION
2. BASKET_ACCELERATION
3. PRIOR_RELATIVE_DEFICIT
4. RELATIVE_IMPROVEMENT
5. DISPERSION_CHANGE
6. MINUTES_SINCE_MARKET_EXPANSION_ONSET
7. MINUTES_SINCE_CATCHUP_ONSET
8. CATCHUP_ONSET_RELATIVE_IMPROVEMENT

No ninth variable is added merely to preserve dimensionality.

---

## 27. Exact primary schema order

Freeze this order:

    NEW_JOINER_FRACTION
    BASKET_ACCELERATION
    PRIOR_RELATIVE_DEFICIT
    RELATIVE_IMPROVEMENT
    DISPERSION_CHANGE
    MINUTES_SINCE_MARKET_EXPANSION_ONSET
    MINUTES_SINCE_CATCHUP_ONSET
    CATCHUP_ONSET_RELATIVE_IMPROVEMENT

Any future predictive contract must hash this ordered schema.

No predictive work is authorized here.

---

## 28. Support quantities

Permitted audit/support quantities include:

- SUBJECT_PREV_RETURN
- SUBJECT_RECENT_RETURN
- BASKET_PREV_RETURN
- BASKET_RECENT_RETURN
- SUBJECT_RELATIVE_PREVIOUS
- SUBJECT_RELATIVE_RECENT
- BREADTH_PREVIOUS
- BREADTH_RECENT
- BREADTH_CHANGE
- PERSISTENT_PARTICIPANT_FRACTION
- DISPERSION_PREVIOUS
- DISPERSION_RECENT
- CATCHUP_STATE_AT_E1
- CATCHUP_ONSET_COUNT_12H
- CATCHUP_ONSET_INTERVAL_START_TS
- CATCHUP_ONSET_INTERVAL_END_TS
- CATCHUP_ONSET_DETECTED_TS
- MARKET_EXPANSION_STATE_AT_E1
- MARKET_EXPANSION_ONSET_COUNT_12H
- MARKET_EXPANSION_ONSET_INTERVAL_START_TS
- MARKET_EXPANSION_ONSET_INTERVAL_END_TS
- MARKET_EXPANSION_ONSET_DETECTED_TS
- BTC support timing quantities if implemented causally

Support quantities are not automatically predictive inputs.

---

## 29. Relationship between current state and onset

The following are deliberately distinct:

    CATCHUP_STATE_AT_E1

and:

    MINUTES_SINCE_CATCHUP_ONSET

A state can remain TRUE for multiple intervals after a single onset.

Likewise:

    MARKET_EXPANSION_STATE_AT_E1

is distinct from:

    MINUTES_SINCE_MARKET_EXPANSION_ONSET

This is the central V3 semantic correction.

---

## 30. Episode recurrence

If a state evolves:

    FALSE
    TRUE
    TRUE
    FALSE
    TRUE

there are exactly two onsets.

The middle TRUE observation is NOT an onset.

This applies to:

- CATCHUP_STATE;
- MARKET_EXPANSION_STATE.

---

## 31. Search-boundary semantics

To determine whether boundary:

    u = t - 12h

is a FALSE -> TRUE onset, the state at:

    u - 60m

must be available.

Therefore the implementation may require source data earlier than the nominal
12-hour event-search interval solely to determine the immediately preceding
state.

This is permitted as causal warmup.

The event itself must still lie inside:

    [t-12h, t]

No earlier event may be selected.

---

## 32. Same-boundary onset at E1

A V3 onset at:

    u == E1_DECISION_TS

is valid if all required intervals are complete and pre-E1.

Then:

    MINUTES_SINCE_*_ONSET = 0

This is not considered a defect.

The audit question is whether FALSE -> TRUE events are structurally distinct,
not whether zero-age events exist.

---

## 33. Catch-up onset interval relative improvement

If catch-up onset occurs at u:

    CATCHUP_ONSET_RELATIVE_IMPROVEMENT
        = RELATIVE_IMPROVEMENT(u)

All source returns are from completed intervals ending no later than u.

If u == E1:

all source bars remain strictly pre-E1 under the frozen half-open interval
semantics.

---

## 34. No transition-end rule

V3 still defines no episode-end concept beyond the state becoming FALSE at a
later causal observation.

No future observation may be used at E1 to determine:

- total episode duration;
- future persistence;
- completed transition;
- exhaustion.

At E1 we know only current/past state history.

---

## 35. No magnitude thresholds

V3 deliberately does NOT introduce:

- return > X bp;
- relative deficit > X bp;
- relative improvement > X bp;
- onset strength > X;
- minimum duration;
- minimum persistence count.

The V2 defect was semantic repetition, not insufficient threshold tuning.

---

## 36. No alternate windows

Do not compare:

- 30m;
- 45m;
- 90m;
- 120m;

against the frozen 60m interval.

V3 uses the same 60-minute causal representation basis.

---

## 37. Completeness expectations

V3 may legitimately have lower completeness than V2 because a true FALSE ->
TRUE catch-up or market-expansion onset may not exist within the frozen
12-hour window.

That missingness is potentially meaningful.

Do not fabricate an onset merely to achieve completeness.

A future V3 audit must distinguish:

    legitimate no-onset state

from:

    implementation/data failure.

---

## 38. Missing-state handling

No imputation is authorized.

If:

    no CATCHUP onset exists within 12h

then:

    MINUTES_SINCE_CATCHUP_ONSET = null
    CATCHUP_ONSET_RELATIVE_IMPROVEMENT = null

If:

    no MARKET_EXPANSION onset exists within 12h

then:

    MINUTES_SINCE_MARKET_EXPANSION_ONSET = null

This is not automatically an invalid representation row.

The future audit must report both:

    raw primary completeness

and:

    state-aware availability

where absence of a causal onset is distinguished from missing source data.

No model handling decision is made here.

---

## 39. State-aware representation principle

V3 introduces an important distinction:

    "no onset exists"

is information about the causal state history.

It is NOT equivalent to:

    "feature computation failed."

Therefore a future experiment may eventually need explicit onset-presence
indicators or another prospective missing-state encoding.

V3 does NOT yet add those indicators to the primary schema.

The V3 audit must quantify this issue before any predictive contract.

---

## 40. Redundancy requirements

Future V3 audit must test:

- exact duplicates;
- sign reversals;
- affine relationships;
- Pearson correlation;
- Spearman correlation.

Threshold for diagnostic near redundancy:

    abs(correlation) >= 0.95

No variable may be automatically removed during the audit.

---

## 41. State-transition audit requirements

The V3 audit must verify synthetically that:

### Catch-up

FALSE -> TRUE:
    onset

TRUE -> TRUE:
    no onset

TRUE -> FALSE:
    no onset

FALSE -> FALSE:
    no onset

FALSE -> TRUE -> TRUE:
    exactly one onset

FALSE -> TRUE -> FALSE -> TRUE:
    exactly two onsets

### Market expansion

Apply the identical transition logic.

---

## 42. Causal mutation requirements

Mutating all post-E1 data must not change:

- CATCHUP_STATE history through E1;
- catch-up onset timestamps;
- catch-up onset counts;
- catch-up onset age;
- catch-up onset relative improvement;
- MARKET_EXPANSION_STATE history through E1;
- market expansion onset timestamps;
- market expansion onset counts;
- all other V3 primary/support values.

---

## 43. Entry-fill independence

No V3 variable may depend on:

- realized entry price;
- entry fill timestamp;
- post-E1 first open;
- execution slippage.

Mutating those values must leave V3 representation unchanged.

---

## 44. V2 artifacts remain immutable

Do not overwrite:

    artifacts/catchup_transition_representation_audit/
    artifacts/catchup_transition_representation_audit_v2/

V3 must use its own artifact namespace.

Suggested:

    artifacts/catchup_transition_representation_audit_v3/

---

## 45. Outcome firewall

Do not access:

- future endpoint returns;
- C29 labels;
- C29 outcome groups;
- C30 labels;
- C30 probabilities;
- P0;
- T2;
- MFE;
- P&L.

No future-return data may be used to evaluate whether the V3 event definition
"looks better."

---

## 46. 2026 prohibition

No 2026 market data or metadata may be:

- enumerated;
- opened;
- inspected;
- counted;
- hashed;
- used.

The sealed future remains intact.

---

## 47. Required V3 audit questions

Before predictive work, an outcome-free audit must answer:

1. Can all V3 states and transitions be computed causally?
2. How often does CATCHUP_STATE occur at E1?
3. How often does a catch-up FALSE -> TRUE onset occur within 12h?
4. How many catch-up onsets occur per 12h?
5. How often is the selected catch-up onset exactly at E1?
6. What is the catch-up onset-age distribution?
7. How often does MARKET_EXPANSION_STATE occur at E1?
8. How often does a market-expansion onset occur within 12h?
9. How repetitive are market-expansion onsets?
10. How often does market expansion onset precede catch-up onset?
11. How often does catch-up onset precede E1?
12. What fraction has no valid onset despite complete source data?
13. Are any V3 primary variables structurally or empirically redundant?
14. Are distributions materially unstable by year or symbol?
15. Does the representation preserve future-mutation invariance?
16. Does it preserve entry-fill independence?

No future outcome may enter these answers.

---

## 48. Interpretation boundary

A V3 audit may conclude that:

- episode onsets are distinctive;
- episode onsets remain repetitive;
- onsets are frequently absent;
- E1 often coincides with catch-up onset;
- market expansion usually precedes or follows catch-up onset.

It may NOT conclude that any of these states are:

- profitable;
- predictive;
- optimal;
- worth trading.

Those require a later predictive experiment.

---

## 49. No automatic requirement that market onset precede catch-up onset

The conceptual hypothesis suggests:

    market participation expansion
        ->
    subject catch-up
        ->
    E1

But V3 does NOT build that ordering into the state definition.

The audit must measure the ordering.

Do not discard rows because ordering differs.

The sequence itself remains a hypothesis to characterize.

---

## 50. No C31

Until V3 is audited and reviewed:

- no C31 contract;
- no predictive model;
- no classifier comparison;
- no probability scoring;
- no economic outcome comparison;
- no trading simulation.

---

## 51. Governance

V3 is an amendment to representation semantics only.

Do not modify:

- V1 specs;
- V2 spec;
- V1/V2 audit contracts;
- V1/V2 artifacts;
- historical experiment behavior.

A future V3 implementation must be separately contracted.

---

## 52. Next checkpoint

The next authorized step after freezing this document is:

    CATCH-UP TRANSITION REPRESENTATION AUDIT V3

The V3 audit remains outcome-free.

Only after human review of that audit may predictive-contract design be
considered.

STOP.
