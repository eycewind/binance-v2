# Catch-Up Transition Measurement Specification V4

Status: prospective semantic amendment.

Authoritative prior documents:

    docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V2.md
    docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC_V3.md

V3 outcome-free audit established that FALSE -> TRUE onset semantics reduced
same-boundary coupling but still produced highly recurrent historical events.

V4 therefore removes historical onset-search features from the primary
representation.

No future outcomes, predictive labels, P0/T2/MFE, model results, P&L, or 2026
data were used to define V4.

This document does NOT authorize:

- C31;
- predictive modeling;
- future-return analysis;
- feature search;
- threshold search;
- trading-policy construction;
- P&L optimization;
- 2026 access.

---

## 1. V4 design principle

V4 represents:

    CURRENT CAUSAL STATE

and:

    CURRENT CONSECUTIVE STATE DURATION

rather than searching backward for repeated historical onset events.

The core questions become:

    Is the hypothesized behavior present now?

and:

    How long has the current state persisted continuously?

This avoids choosing among multiple historical FALSE -> TRUE events.

---

## 2. Behavioral hypothesis

The behavioral hypothesis remains:

    An E1 transition may be more persistent when broader participation is
    expanding, the subject asset has lagged its peer basket, its relative
    movement is improving, and the transition is not already mature.

V4 does not encode profitability or future persistence.

---

## 3. Frozen universe

No change.

Use exactly:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

For subject s:

    LOO_BASKET(s)

is the equal-weight basket of the other four symbols.

No learned weights.
No capitalization weighting.
No volatility weighting.

---

## 4. Frozen time basis

No change.

At hourly boundary u:

    PREVIOUS_60(u)
        = [u-120m, u-60m)

    RECENT_60(u)
        = [u-60m, u)

Only completed accepted 1-minute bars may be used.

At E1 decision timestamp t:

    all primary measurements must be available no later than t.

---

## 5. Frozen return quantities

Retain:

    SUBJECT_PREV_RETURN
    SUBJECT_RECENT_RETURN
    BASKET_PREV_RETURN
    BASKET_RECENT_RETURN

with the same return convention frozen in prior specifications.

Define:

    BASKET_ACCELERATION
        = BASKET_RECENT_RETURN
          - BASKET_PREV_RETURN

---

## 6. Relative quantities

Retain:

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

No magnitude thresholds are introduced.

---

## 7. Participation quantities

Retain:

    BREADTH_PREVIOUS
    BREADTH_RECENT
    BREADTH_CHANGE
    NEW_JOINER_FRACTION
    PERSISTENT_PARTICIPANT_FRACTION

using the frozen five-symbol universe.

As in V2/V3:

    NEW_JOINER_FRACTION

is primary.

    BREADTH_CHANGE

remains support/state-definition information.

---

## 8. Dispersion

Retain:

    DISPERSION_PREVIOUS
    DISPERSION_RECENT

using population standard deviation:

    ddof = 0

Primary quantity:

    DISPERSION_CHANGE
        = DISPERSION_RECENT
          - DISPERSION_PREVIOUS

---

## 9. Catch-up state

At each hourly boundary u:

    CATCHUP_STATE(u) = TRUE

iff:

    PRIOR_RELATIVE_DEFICIT(u) > 0

AND:

    RELATIVE_IMPROVEMENT(u) > 0

otherwise:

    FALSE

No future persistence is required.

No historical onset search is required.

---

## 10. Catch-up state at E1

Primary binary variable:

    CATCHUP_STATE_AT_E1

equal to:

    1 if CATCHUP_STATE(t) is TRUE
    0 otherwise

This directly represents whether the catch-up condition is present at E1.

---

## 11. Catch-up current run length

Define:

    CATCHUP_CURRENT_RUN_LENGTH

as the number of consecutive hourly boundaries ending at E1 for which:

    CATCHUP_STATE == TRUE

Examples:

    F F F
        -> run length 0

    F F T
        -> run length 1

    F T T
        -> run length 2

    T T T
        -> run length at least 3 according to available causal lookback

    T T F T
        -> run length 1

Only the currently active consecutive run matters.

Earlier historical episodes are ignored.

---

## 12. Catch-up run-length search limit

To keep the representation finite and causally bounded, inspect at most:

    12 hourly state boundaries ending at E1

Therefore:

    CATCHUP_CURRENT_RUN_LENGTH

has range:

    0 through 12

If all 12 inspected states are TRUE:

    value = 12

This means:

    at least 12 consecutive observed hourly states are TRUE

not necessarily that the episode began exactly 12 hours ago.

No earlier data are required to distinguish 12 from >12.

---

## 13. Market expansion state

At boundary u:

    MARKET_EXPANSION_STATE(u) = TRUE

iff:

    BREADTH_CHANGE(u) > 0

AND:

    BREADTH_RECENT(u) >= 0.6

otherwise:

    FALSE

This is unchanged from V3.

---

## 14. Market expansion state at E1

Primary binary variable:

    MARKET_EXPANSION_STATE_AT_E1

equal to:

    1 if MARKET_EXPANSION_STATE(t) is TRUE
    0 otherwise

---

## 15. Market expansion current run length

Define:

    MARKET_EXPANSION_CURRENT_RUN_LENGTH

as the number of consecutive hourly boundaries ending at E1 for which:

    MARKET_EXPANSION_STATE == TRUE

Examples follow the same semantics as catch-up run length.

Range:

    0 through 12

If the current state is FALSE:

    run length = 0

If all 12 inspected states are TRUE:

    run length = 12

meaning at least 12 observed consecutive TRUE states.

---

## 16. Removal of historical onset features

V4 removes all historical onset-derived primary variables.

Removed from primary representation:

    MINUTES_SINCE_MARKET_EXPANSION_ONSET
    MINUTES_SINCE_CATCHUP_ONSET
    CATCHUP_ONSET_RELATIVE_IMPROVEMENT

Historical onset timestamps/counts may be retained only when required to
reproduce prior V3 artifacts.

They are not part of V4.

---

## 17. Why onset search is removed

The V3 audit found:

    mean catch-up FALSE -> TRUE onsets / 12h:
        3.92

    median:
        4

    entries with 4+ catch-up onsets:
        1,503 / 2,199

    mean market-expansion onsets / 12h:
        4.09

    median:
        4

    entries with 4+ market-expansion onsets:
        1,646 / 2,199

The event definition remained highly recurrent.

V4 therefore stops treating historical state flips as the primary concept.

This change is based exclusively on outcome-free representation mechanics.

---

## 18. V4 primary representation

The V4 primary representation contains exactly nine variables:

1. NEW_JOINER_FRACTION
2. BASKET_ACCELERATION
3. PRIOR_RELATIVE_DEFICIT
4. RELATIVE_IMPROVEMENT
5. DISPERSION_CHANGE
6. MARKET_EXPANSION_STATE_AT_E1
7. MARKET_EXPANSION_CURRENT_RUN_LENGTH
8. CATCHUP_STATE_AT_E1
9. CATCHUP_CURRENT_RUN_LENGTH

No tenth variable is added.

---

## 19. Exact primary schema order

Freeze this order:

    NEW_JOINER_FRACTION
    BASKET_ACCELERATION
    PRIOR_RELATIVE_DEFICIT
    RELATIVE_IMPROVEMENT
    DISPERSION_CHANGE
    MARKET_EXPANSION_STATE_AT_E1
    MARKET_EXPANSION_CURRENT_RUN_LENGTH
    CATCHUP_STATE_AT_E1
    CATCHUP_CURRENT_RUN_LENGTH

Any future predictive experiment must use this exact frozen order unless a new
prospective amendment is created.

No predictive experiment is authorized here.

---

## 20. Important structural relationship

For either state:

    STATE_AT_E1 == 0

implies:

    CURRENT_RUN_LENGTH == 0

and:

    CURRENT_RUN_LENGTH > 0

implies:

    STATE_AT_E1 == 1

Therefore each state/run-length pair is structurally related.

This relationship is intentional.

The binary state answers:

    is the condition present?

The run length answers:

    how long has it persisted?

The future audit must report this dependence explicitly.

It must NOT automatically remove either variable.

---

## 21. Current-state persistence semantics

Run length measures only uninterrupted persistence.

Example:

    T T F T T

At final boundary:

    current run length = 2

The earlier TRUE episode contributes nothing.

This is intentional.

V4 does not summarize total TRUE count over 12h.

---

## 22. No accumulated-history feature

Do NOT add:

- number of TRUE states over 12h;
- number of state flips;
- historical onset count;
- time since first TRUE;
- time since most recent prior onset;
- fraction TRUE over 12h.

Those may be interesting later but are not part of V4.

The purpose is to keep the representation compact.

---

## 23. Run-length causality

For E1 at time t:

    state(t)

must use only completed data strictly available by t.

Earlier states:

    state(t-60m)
    state(t-120m)
    ...

must each be computed using only data available by their own boundary.

No future confirmation.

---

## 24. Warmup requirement

Computing up to 12 consecutive states may require price data earlier than:

    t-12h

because each state uses:

    PREVIOUS_60
    RECENT_60

This earlier source data are causal warmup only.

The run-length state boundaries remain bounded to the last 12 hourly
boundaries ending at E1.

---

## 25. Expected availability

Unlike V3 historical onset ages, all V4 state/run-length variables should be
defined whenever the required source bars exist.

No causal event is required to occur.

Therefore:

    state FALSE -> binary 0, run length 0

is valid information.

No onset-null encoding problem remains.

---

## 26. Missingness

If required source data are absent:

    corresponding state/run-length measurement = null

Do not fabricate a FALSE state from missing data.

Distinguish:

    valid FALSE state

from:

    unavailable state

No imputation.

---

## 27. Relationship to original sequence hypothesis

V4 does NOT force the sequence:

    market expansion
        ->
    catch-up
        ->
    E1

The V3 audit found mixed temporal ordering.

V4 instead measures both states independently at E1.

A later predictive experiment may determine whether their combination matters.

No ordering is built into the representation.

---

## 28. Interaction not encoded

Do NOT add a combined variable such as:

    MARKET_AND_CATCHUP

or:

    MARKET_RUN_X_CATCHUP_RUN

to the V4 primary schema.

The representation should preserve the separate concepts.

Any interaction can be handled only by a later prospectively specified model.

---

## 29. BTC leadership

BTC remains excluded from the V4 primary representation.

Reason:

The current catch-up hypothesis is defined relative to the leave-one-out peer
basket.

BTC-specific timing remains a separate possible hypothesis.

Do not reintroduce BTC in V4.

---

## 30. Measurement interpretation

The nine V4 quantities represent:

    NEW_JOINER_FRACTION
        immediate participation joining

    BASKET_ACCELERATION
        strengthening/weakening of peer movement

    PRIOR_RELATIVE_DEFICIT
        subject's prior lag

    RELATIVE_IMPROVEMENT
        subject's current catch-up movement

    DISPERSION_CHANGE
        cross-sectional convergence/divergence change

    MARKET_EXPANSION_STATE_AT_E1
        whether broad participation expansion is present now

    MARKET_EXPANSION_CURRENT_RUN_LENGTH
        current uninterrupted persistence of that state

    CATCHUP_STATE_AT_E1
        whether lag-plus-relative-improvement condition is present now

    CATCHUP_CURRENT_RUN_LENGTH
        current uninterrupted persistence of that state

No favorable direction is asserted beyond the descriptive Boolean definitions.

---

## 31. No trend-maturity claim beyond state persistence

V4 current run length is a persistence measure.

It must NOT automatically be described as:

- trend maturity;
- exhaustion;
- remaining upside;
- age of the entire market move.

A run can reset after one FALSE observation even if a broader trend continues.

The measurement claim is narrower:

    consecutive persistence of the frozen state condition.

---

## 32. No future confirmation

A state is TRUE or FALSE at each historical boundary using only information
available at that boundary.

Run length uses only these causal historical states.

No future observation may revise an earlier state.

---

## 33. No magnitude thresholds

Do not add:

- minimum relative deficit;
- minimum relative improvement;
- minimum basket acceleration;
- minimum new-joiner fraction;
- minimum run length.

Run length itself remains continuous/discrete 0-12.

No cutoff is selected.

---

## 34. No alternative state definitions

Do not compare alternative Boolean conditions.

Frozen:

    CATCHUP_STATE
        PRIOR_RELATIVE_DEFICIT > 0
        AND RELATIVE_IMPROVEMENT > 0

Frozen:

    MARKET_EXPANSION_STATE
        BREADTH_CHANGE > 0
        AND BREADTH_RECENT >= 0.6

Any alternative requires V5.

---

## 35. No alternate base intervals

Do not compare:

- 15m;
- 30m;
- 45m;
- 90m;
- 120m.

V4 remains based on completed 60-minute intervals.

---

## 36. No alternate persistence horizon

Do not compare 6h, 12h, 24h run-length caps.

V4 uses:

    maximum 12 observed hourly states

This is inherited from the prior 12-hour representation horizon.

No outcome-guided search.

---

## 37. Structural redundancy audit requirement

A V4 audit must explicitly examine the deterministic relationship between:

    MARKET_EXPANSION_STATE_AT_E1
    MARKET_EXPANSION_CURRENT_RUN_LENGTH

and:

    CATCHUP_STATE_AT_E1
    CATCHUP_CURRENT_RUN_LENGTH

This expected relationship must not be mistaken for accidental duplication.

However, if a binary state is exactly reconstructible from run length:

    STATE = 1 iff RUN_LENGTH > 0

the audit must document this exact deterministic relationship.

Human review must then decide prospectively whether both should remain in any
future predictive matrix.

Do NOT remove either during the audit.

---

## 38. Empirical redundancy

Future audit must compute pairwise:

- Pearson;
- Spearman;
- valid-pair count.

Flag:

    abs(correlation) >= 0.95

but do not automatically remove anything.

---

## 39. State/run-length distribution audit

Future audit must report for both states:

- TRUE frequency at E1;
- FALSE frequency;
- run-length exact distribution 0-12;
- mean;
- median;
- p75;
- p90;
- maximum;
- by year;
- by symbol.

This is outcome-free.

---

## 40. Combination-state audit

For descriptive purposes only, report the four current-state combinations:

    market=0, catchup=0
    market=0, catchup=1
    market=1, catchup=0
    market=1, catchup=1

Also report joint run-length cross-tabs.

No future return association.

---

## 41. Future-mutation requirement

Changing all post-E1 market data must leave unchanged:

- every primary variable;
- every historical state used for run length;
- all support variables.

Required test.

---

## 42. Entry-fill independence

Changing:

- realized entry fill price;
- fill timestamp;
- first post-E1 open;
- execution costs;

must leave V4 unchanged.

---

## 43. V3 historical artifacts remain immutable

Do not overwrite:

    artifacts/catchup_transition_representation_audit/
    artifacts/catchup_transition_representation_audit_v2/
    artifacts/catchup_transition_representation_audit_v3/

V4 must receive its own audit namespace.

Suggested:

    artifacts/catchup_transition_representation_audit_v4/

---

## 44. Outcome firewall

Do not access:

- C29 labels;
- C29 endpoint returns;
- C30 labels;
- C30 predictions;
- P0;
- T2;
- MFE;
- P&L;
- future endpoint returns.

No representation choice may be evaluated using future outcome.

---

## 45. 2026 prohibition

No 2026 market data or metadata may be:

- enumerated;
- opened;
- inspected;
- counted;
- hashed;
- validated;
- used.

---

## 46. Required V4 audit questions

Before any predictive experiment, answer:

1. Can all nine V4 quantities be computed causally?
2. Are source-data failures zero or fully explained?
3. What fraction of E1 entries have catch-up state TRUE?
4. What is the catch-up current-run distribution?
5. What fraction have market-expansion state TRUE?
6. What is the market current-run distribution?
7. How often are both states TRUE simultaneously?
8. Are run lengths dominated by 0/1 or meaningfully distributed?
9. Are state/run-length pairs deterministically redundant?
10. Are any other primary pairs near redundant?
11. Are feature distributions stable by year?
12. Are feature scales strongly symbol-specific?
13. Does post-E1 mutation leave everything unchanged?
14. Does fill mutation leave everything unchanged?
15. Is the representation technically coherent enough for predictive-contract
    design?

No outcome analysis.

---

## 47. V4 technical success concept

V4 is intended to be simpler than V3.

A good technical representation does NOT require:

- rare states;
- long run lengths;
- balanced binary states;
- a particular market/catch-up combination frequency.

The audit should judge:

- causal correctness;
- semantic clarity;
- availability;
- redundancy;
- stability.

Do not optimize descriptive distributions.

---

## 48. No predictive work

Until V4 audit is completed and reviewed:

- no model;
- no probabilities;
- no Brier/log loss/AUC;
- no GROSS40/GROSS50 comparison;
- no endpoint-return comparison;
- no strategy P&L;
- no C31.

---

## 49. Governance

Do not modify historical V1/V2/V3 documents or artifacts.

V4 is a new prospective semantic checkpoint.

Any further semantic change requires a V5 amendment.

---

## 50. Next step

After freezing V4:

    create and execute an outcome-free
    CATCHUP_TRANSITION_REPRESENTATION_AUDIT_V4 contract.

Only after human review of that audit may predictive C31 design be considered.

STOP.
