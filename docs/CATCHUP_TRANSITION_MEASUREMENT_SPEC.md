# Catch-Up Transition Measurement Specification

Status: prospective representation-definition note.

This document turns the behavioral concepts in:

    docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md

into exact causal measurements.

It does NOT authorize:

- C31;
- model fitting;
- outcome analysis;
- feature search;
- threshold search;
- horizon selection;
- trading-policy construction;
- P&L optimization;
- 2026 access.

The objective is only:

    define a compact, auditable representation of the catch-up transition
    hypothesis using information available no later than E1.

---

## 1. Primary hypothesis

The frozen behavioral hypothesis is:

    An E1 transition is more likely to persist when market participation is
    expanding, the candidate asset initially lags that move, its relative
    movement begins improving, and E1 occurs before the asset becomes
    materially extended.

This document defines how those concepts are measured.

Future endpoint return is NOT part of any feature definition.

---

## 2. Frozen universe

Use exactly:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

No additional symbols.

When the subject asset is one of these five, its broad-market reference is the
equal-weight basket of the OTHER FOUR symbols.

This is called:

    LOO_BASKET

where LOO means leave-one-out.

For BTCUSDT as subject, the basket therefore contains:

    ETHUSDT
    SOLUSDT
    XRPUSDT
    BNBUSDT

For ETHUSDT as subject, the basket contains:

    BTCUSDT
    SOLUSDT
    XRPUSDT
    BNBUSDT

and analogously for the remaining subjects.

No capitalization weighting.
No volatility weighting.
No learned weights.

---

## 3. Frozen time basis

Primary transition measurements use adjacent non-overlapping 60-minute
intervals.

For an E1 decision time t:

    RECENT_60:
        [t - 60 minutes, t)

    PREVIOUS_60:
        [t - 120 minutes, t - 60 minutes)

All measurements use only completed 1-minute bars whose timestamps lie fully
inside the applicable interval.

No bar at or after t may enter a feature.

No centered windows.
No forward filling across missing bars.
No interpolation.

---

## 4. Return convention

For symbol s and interval [a,b):

    R(s,a,b)
        = CLOSE_LAST_COMPLETED_BEFORE_b
          / OPEN_FIRST_VALID_AT_OR_AFTER_a
          - 1

Implementation must use the existing accepted 1-minute source semantics.

The exact bar timestamps used for each interval must be auditable.

If an interval lacks valid contiguous data required by the accepted source
rules, the corresponding feature is unavailable.

No synthetic price may be inserted.

---

## 5. Subject return

For subject asset s:

    SUBJECT_PREV_RETURN
        = R(s, t-120m, t-60m)

    SUBJECT_RECENT_RETURN
        = R(s, t-60m, t)

These are support quantities.

They are not automatically both included as model features.

---

## 6. Leave-one-out basket return

For subject s, let O_s be the other four frozen symbols.

For interval I:

    LOO_BASKET_RETURN(s,I)
        = arithmetic mean of R(j,I)
          for j in O_s

All four component returns must be valid.

No symbol may be dropped dynamically.

Define:

    BASKET_PREV_RETURN
        = LOO_BASKET_RETURN(s, PREVIOUS_60)

    BASKET_RECENT_RETURN
        = LOO_BASKET_RETURN(s, RECENT_60)

---

## 7. Market participation

Participation is defined using the frozen five-symbol universe, not the
leave-one-out basket.

For interval I:

    PARTICIPANT(s,I) = 1
        iff R(s,I) > 0

    otherwise 0

Exact zero is non-positive.

Define:

    BREADTH_PREVIOUS
        = mean PARTICIPANT(s, PREVIOUS_60)
          across all five symbols

    BREADTH_RECENT
        = mean PARTICIPANT(s, RECENT_60)
          across all five symbols

Primary transition measurement:

    BREADTH_CHANGE
        = BREADTH_RECENT - BREADTH_PREVIOUS

Range:

    [-1, +1]

with increments determined by five-symbol participation.

This is explicitly:

    frozen-five-symbol breadth

not whole-crypto-market breadth.

---

## 8. New joiner fraction

For each frozen symbol j:

    NEW_JOINER_j = 1

iff:

    R(j, PREVIOUS_60) <= 0

and:

    R(j, RECENT_60) > 0

otherwise 0.

Define:

    NEW_JOINER_FRACTION
        = mean NEW_JOINER_j across all five symbols

This measures expansion in directional participation.

It does not imply that new participation is favorable.

---

## 9. Persistent participant fraction

For each frozen symbol j:

    PERSISTENT_PARTICIPANT_j = 1

iff:

    R(j, PREVIOUS_60) > 0

and:

    R(j, RECENT_60) > 0

otherwise 0.

Define:

    PERSISTENT_PARTICIPANT_FRACTION
        = mean across all five symbols

This distinguishes newly expanding participation from already-existing broad
positive participation.

This quantity is initially diagnostic/supporting and is not automatically
part of the compact final representation.

---

## 10. Basket acceleration

Define:

    BASKET_ACCELERATION
        = BASKET_RECENT_RETURN - BASKET_PREV_RETURN

Interpretation:

    positive -> broad price movement strengthened relative to the immediately
                preceding interval

    negative -> broad price movement weakened relative to the immediately
                preceding interval

No favorable sign is assumed.

---

## 11. Subject relative return

For subject s:

    SUBJECT_RELATIVE_PREVIOUS
        = SUBJECT_PREV_RETURN - BASKET_PREV_RETURN

    SUBJECT_RELATIVE_RECENT
        = SUBJECT_RECENT_RETURN - BASKET_RECENT_RETURN

Interpretation:

    negative SUBJECT_RELATIVE_PREVIOUS
        means the subject lagged its peer basket in the previous interval

    positive SUBJECT_RELATIVE_PREVIOUS
        means the subject led its peer basket

This is a price-relative measurement only.

---

## 12. Prior relative deficit

Define:

    PRIOR_RELATIVE_DEFICIT
        = -SUBJECT_RELATIVE_PREVIOUS

This sign convention is chosen so:

    larger positive values
        = greater prior lag versus peers

    negative values
        = subject previously led peers

Do NOT clip negative values.

Do NOT convert this into a binary lag/no-lag threshold at this stage.

---

## 13. Relative improvement

Define:

    RELATIVE_IMPROVEMENT
        = SUBJECT_RELATIVE_RECENT
          - SUBJECT_RELATIVE_PREVIOUS

Interpretation:

    positive
        = subject's relative performance improved

    negative
        = subject's relative performance deteriorated

This is the principal catch-up dynamic measurement.

No minimum improvement threshold is frozen.

---

## 14. Catch-up geometry support variables

For auditability retain:

    SUBJECT_RELATIVE_PREVIOUS
    SUBJECT_RELATIVE_RECENT
    PRIOR_RELATIVE_DEFICIT
    RELATIVE_IMPROVEMENT

However, because these are algebraically related, a future predictive
representation should not automatically include all four.

The compact candidate pair is:

    PRIOR_RELATIVE_DEFICIT
    RELATIVE_IMPROVEMENT

because those map directly to:

    was the asset behind?
    is it catching up?

---

## 15. Cross-sectional dispersion

For interval I, calculate the five frozen symbol returns:

    R_1 ... R_5

Define:

    DISPERSION(I)
        = population standard deviation of those five returns

Use population standard deviation:

    ddof = 0

Then:

    DISPERSION_PREVIOUS
        = DISPERSION(PREVIOUS_60)

    DISPERSION_RECENT
        = DISPERSION(RECENT_60)

Primary transition quantity:

    DISPERSION_CHANGE
        = DISPERSION_RECENT - DISPERSION_PREVIOUS

No sign is declared favorable.

---

## 16. Subject distance from peer center

For subject s:

    SUBJECT_PEER_DISTANCE_RECENT
        = SUBJECT_RECENT_RETURN - BASKET_RECENT_RETURN

This is equal to:

    SUBJECT_RELATIVE_RECENT

Therefore it is NOT a separate feature.

Record this equivalence explicitly in the redundancy audit.

---

## 17. BTC price leadership context

BTC is retained as a descriptive leadership reference even though the primary
catch-up comparison uses a leave-one-out basket.

Define BTC directional onset using the same causal onset algorithm specified
below.

Possible timing quantity:

    BTC_ONSET_LEAD_MINUTES
        = SUBJECT_ONSET_TS - BTC_ONSET_TS

Interpretation:

    positive
        = BTC onset preceded subject onset

    zero
        = same detected onset time

    negative
        = subject onset preceded BTC onset

This variable must remain price-leadership timing only.

It must not be interpreted as causal information transmission.

---

## 18. Causal directional onset rule

A simple deterministic onset rule is frozen for design purposes.

Use completed adjacent 60-minute intervals.

For each candidate evaluation boundary u, define:

    PREV(u):
        [u-120m, u-60m)

    RECENT(u):
        [u-60m, u)

For a symbol s, directional onset occurs at the earliest boundary u such that:

    R(s, RECENT(u)) > 0

and:

    R(s, RECENT(u)) > R(s, PREV(u))

That is:

    recent return is positive
    AND
    recent return improved versus the preceding non-overlapping interval.

No absolute-return threshold is used.

No future persistence confirmation is used.

No subsequent return participates.

---

## 19. Onset search window

At E1 decision time t, search backward over exactly:

    12 hours

for the most recent causal onset satisfying Section 18.

Candidate boundaries must occur on completed hourly boundaries.

Search interval:

    [t-12h, t]

Only information available by each candidate boundary u may be used to decide
whether onset occurred at u.

If multiple onset events occur, use the MOST RECENT qualifying onset before or
at t.

Rationale:

The representation asks about current transition maturity, not the first
positive episode arbitrarily far in the past.

The 12-hour search window is a representation-design choice and is NOT chosen
from outcome performance.

No alternative onset lookback is tested in this specification.

---

## 20. Subject onset

For subject s:

    SUBJECT_ONSET_TS

is the most recent qualifying onset under Sections 18-19.

If no qualifying event exists in the 12-hour lookback:

    SUBJECT_ONSET_TS = null

No fallback timestamp is fabricated.

---

## 21. BTC onset

Define:

    BTC_ONSET_TS

using the identical onset rule and lookback.

BTC onset is defined whether or not BTC is the traded subject.

---

## 22. Market-participation onset

At each hourly boundary u define:

    BREADTH_CHANGE(u)

using the two adjacent 60-minute intervals ending at u.

A market-participation onset occurs when:

    BREADTH_CHANGE(u) > 0

and:

    BREADTH_RECENT(u) >= 0.6

Because there are five symbols:

    BREADTH_RECENT >= 0.6

means at least 3 of 5 symbols have positive recent return.

The threshold 0.6 is structural:

    majority of frozen universe

not optimized from historical outcomes.

Define:

    MARKET_ONSET_TS

as the most recent qualifying market-participation onset during the same
12-hour lookback.

If none exists:

    MARKET_ONSET_TS = null

---

## 23. Market-onset age

If MARKET_ONSET_TS exists:

    MINUTES_SINCE_MARKET_ONSET
        = (t - MARKET_ONSET_TS) in minutes

Otherwise:

    null

No imputation.

This is a maturity measurement.

---

## 24. Subject-onset age

If SUBJECT_ONSET_TS exists:

    MINUTES_SINCE_SUBJECT_ONSET
        = (t - SUBJECT_ONSET_TS) in minutes

Otherwise:

    null

---

## 25. BTC onset lead

If both SUBJECT_ONSET_TS and BTC_ONSET_TS exist:

    BTC_ONSET_LEAD_MINUTES
        = SUBJECT_ONSET_TS - BTC_ONSET_TS

measured in minutes.

Examples:

    +120
        BTC onset occurred two hours before subject onset

    -60
        subject onset occurred one hour before BTC onset

Otherwise:

    null

---

## 26. Subject extension since onset

If SUBJECT_ONSET_TS exists:

    SUBJECT_EXTENSION_SINCE_ONSET
        = close_at_E1_cutoff
          / onset_reference_price
          - 1

where:

    onset_reference_price
        = first valid 1-minute open at SUBJECT_ONSET_TS

and:

    close_at_E1_cutoff
        = last completed 1-minute close before E1 decision timestamp t

No bar at or after t is used.

This measures price extension after the causally detected onset.

It does not declare whether greater extension is favorable or exhausted.

---

## 27. Market extension since onset

If MARKET_ONSET_TS exists, define subject-specific peer-market extension:

    BASKET_EXTENSION_SINCE_MARKET_ONSET

using the equal-weight leave-one-out basket return from MARKET_ONSET_TS to t.

All four peer symbols must have valid data over the interval.

No dynamic dropping.

---

## 28. Sequence timing

The hypothesized catch-up sequence is:

    MARKET_ONSET
        ->
    subject remains behind peers
        ->
    relative improvement
        ->
    E1

A later diagnostic may characterize whether this ordering actually occurs.

For now define support variables:

    MARKET_ONSET_TS
    SUBJECT_ONSET_TS
    BTC_ONSET_TS
    MINUTES_SINCE_MARKET_ONSET
    MINUTES_SINCE_SUBJECT_ONSET
    BTC_ONSET_LEAD_MINUTES

No future outcome is used.

---

## 29. Catch-up sequence candidate flag

For descriptive representation auditing only, define:

    CATCHUP_SEQUENCE_CANDIDATE = 1

iff all are true at E1:

    MARKET_ONSET_TS is not null

    PRIOR_RELATIVE_DEFICIT > 0

    RELATIVE_IMPROVEMENT > 0

Otherwise:

    0

This is NOT:

- a trading rule;
- a favorable label;
- an entry filter;
- a predictive target.

It simply records whether the qualitative causal sequence is present.

Do NOT add any return threshold beyond sign.

Do NOT require future confirmation.

---

## 30. Why no stronger candidate threshold

The following tempting definitions are deliberately NOT frozen:

    PRIOR_RELATIVE_DEFICIT > X bp
    RELATIVE_IMPROVEMENT > Y bp
    breadth_change >= Z
    onset_age < N hours

because choosing X/Y/Z/N from historical endpoint performance would introduce
outcome-guided tuning.

The first representation therefore uses structural sign/majority semantics
only where a binary descriptive state is needed.

Continuous quantities remain continuous.

---

## 31. E1 timing adequacy variables

A future diagnostic should be able to determine whether E1 is:

    before
    during
    after

the hypothesized transition.

Define, where available:

    MARKET_TO_E1_MINUTES
        = t - MARKET_ONSET_TS

    SUBJECT_ONSET_TO_E1_MINUTES
        = t - SUBJECT_ONSET_TS

    BTC_ONSET_TO_E1_MINUTES
        = t - BTC_ONSET_TS

These are identical in information to the onset-age variables and should not
be separately included in a model.

They may be exposed under one canonical naming convention only.

---

## 32. Compact candidate representation

The initial compact representation candidate is:

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

Support/audit quantities may also be computed, but they are not automatically
predictive inputs.

This list is a representation candidate only.

It does not authorize model fitting.

---

## 33. Redundancy audit

Before any future experiment, explicitly verify:

### Exact/algebraic relationships

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

Do not include both aliases.

### Conceptual overlap

Review whether:

    BREADTH_CHANGE
    NEW_JOINER_FRACTION

provide sufficiently distinct information.

Review whether:

    BASKET_ACCELERATION
    DISPERSION_CHANGE

capture different dimensions.

No decision may be made using future outcome performance.

---

## 34. Missingness semantics

Never impute an onset or interval measurement from future information.

If required interval data are missing:

    feature = null

If onset is absent within 12 hours:

    onset-derived feature = null

A future experiment must decide prospectively whether:

- rows with missing required representation are excluded;
- explicit causal missingness indicators are used.

That decision is NOT made here.

---

## 35. Timestamp availability

Every future implementation must record, for every feature:

    observation_end_ts
    available_ts

Requirement:

    available_ts <= E1_decision_ts

For onset-derived features:

    onset determination must itself use only data available at onset boundary

and the final derived feature must remain reproducible if all data after E1
are mutated.

---

## 36. No entry-fill leakage

The representation is anchored to:

    E1 decision time

not the later realized entry execution price.

Future entry fill information may not appear in these features.

If a value requires knowledge of the fill, it is not eligible.

---

## 37. No outcome-guided onset revision

Once implemented, do not revise the onset definition because:

- successful trades appear to start earlier;
- failed trades appear to start later;
- another lookback produces stronger separation;
- another participation threshold improves endpoint prediction.

Any materially different onset rule becomes a new prospectively specified
representation version.

---

## 38. What this representation can measure

It can describe:

- recent directional strengthening;
- expansion of participation across the frozen five-symbol universe;
- relative lag;
- relative improvement;
- cross-sectional convergence/divergence;
- temporal ordering of price-based onset;
- extension/maturity at E1;
- price leadership timing relative to BTC.

---

## 39. What it cannot establish

It cannot establish:

- causal leadership;
- order-flow pressure;
- exchange-wide liquidity conditions;
- hidden institutional activity;
- liquidation cascades;
- futures positioning;
- funding pressure;
- news causation;
- why one asset moved first.

All such interpretations remain outside the measurement claim.

---

## 40. Required pre-experiment audit

Before C31 or any later numbered experiment, produce a measurement audit
containing for every candidate variable:

- exact formula;
- source bars;
- interval boundaries;
- earliest/latest source timestamp;
- availability timestamp;
- null rule;
- range;
- units;
- exact/algebraic redundancy relationships;
- example calculation on synthetic data;
- future-mutation causality test.

Also report:

- frequency of missing onset states;
- frequency of CATCHUP_SEQUENCE_CANDIDATE;
- timing distribution of market/subject/BTC onset relative to E1.

Those last quantities are REPRESENTATION diagnostics only.

Do not pair them with future-return outcomes until separately authorized.

---

## 41. Prohibited work

This specification does NOT authorize:

- GROSS40/GROSS50 association analysis;
- endpoint-return comparison;
- model fitting;
- probability scoring;
- feature selection;
- threshold selection;
- alternative onset lookbacks;
- 30m versus 60m search;
- alternate basket weighting;
- alternate participation threshold search;
- trading simulation;
- profitability analysis;
- 2026 access;
- C31 implementation.

---

## 42. Next checkpoint

After implementation-independent review of these definitions, the next
authorized task should be a CAUSAL REPRESENTATION AUDIT only.

That audit should answer:

1. Can every quantity be computed exactly and causally?
2. How often are the quantities available?
3. Does the proposed temporal sequence actually occur around E1?
4. Does E1 usually happen before, during, or after the detected transition?
5. Are any proposed quantities structurally redundant?
6. Is the representation compact enough to justify a later predictive test?

Only after that audit should C31 be considered.
