# Catch-Up Transition Representation Specification

Status: design note only.

This document defines a causal representation hypothesis for a possible
future Binance experiment.

It does NOT define:

- a trading strategy;
- a favorable trade;
- a predictive model;
- a probability threshold;
- a preferred holding horizon;
- a new E1 rule;
- C31.

No outcome analysis is authorized by this document.

---

## 1. Motivation

C29 established that economically meaningful fixed-endpoint opportunities
occur frequently enough to justify asking whether they can be predicted.

C30 tested whether a compact E1-time state representation could predict those
opportunities.

The C30 representation contained 34 causal features covering:

- local asset returns;
- local realized volatility;
- SMA24 geometry;
- BTC returns and volatility;
- relative-to-BTC returns;
- five-symbol breadth;
- five-symbol mean returns.

The representation was primarily a description of current/trailing market
state.

C30 did not establish stable predictive usefulness across the frozen
3h/6h/12h/24h endpoint tasks.

The next design question is therefore not:

    "Which new model should be tried?"

It is:

    "What market transition do we believe could causally distinguish
     continuation from exhaustion, and can that transition be represented
     using only information available before or at E1?"

---

## 2. Boundary between state definition and outcome

A critical distinction is frozen here.

A transition candidate is defined entirely from information available before
or at E1.

Future return MUST NOT participate in defining whether a transition existed.

Future fixed-endpoint outcomes may later be used only to evaluate whether the
causally defined transition was useful.

Therefore:

    causal transition state
        !=
    profitable trade

and:

    transition candidate
        !=
    future-confirmed winner

No representation in this document may use future price movement to decide
whether the transition occurred.

---

## 3. Primary behavioral hypothesis

The first coherent hypothesis is:

    An E1 transition is more likely to persist when market participation is
    expanding, the candidate asset initially lags that move, its relative
    movement begins improving, and E1 occurs before the asset becomes
    materially extended.

This is called:

    CATCH-UP TRANSITION HYPOTHESIS

Conceptual causal sequence:

    market participation begins expanding
        ->
    candidate asset remains behind the broader move
        ->
    candidate asset starts improving relative to the market
        ->
    E1 fires
        ->
    later fixed-endpoint return is observed

The final step is an outcome, not part of the transition definition.

---

## 4. Explicitly separate hypothesis: leader breakout

A different possible mechanism is:

    one asset leads a broad market move and continues after breaking first

That is a LEADER BREAKOUT hypothesis.

It is NOT part of the catch-up transition hypothesis.

Do not silently combine:

- leader continuation;
- laggard catch-up;
- broad momentum;
- reversal;
- breakout;

into one favorable feature bundle.

If leader-breakout behavior is researched later, it requires a separate
representation hypothesis.

---

## 5. Representation principles

Every proposed measurement must satisfy all of the following.

### 5.1 Causal observability

The measurement must use only data that would have been available before or
at the E1 decision timestamp.

No future-confirmed extrema.
No future-confirmed turning point.
No future leader designation.
No backward labeling from outcome.

### 5.2 Behavioral interpretation

Each quantity must correspond to a specific behavioral question.

A feature is not included merely because it is a common technical indicator.

### 5.3 Incremental meaning

Prefer measurements that describe a distinct aspect of the transition.

Avoid multiple algebraic or strongly redundant encodings of the same price
movement unless the distinction has an explicit behavioral rationale.

### 5.4 Transition rather than static level

Where possible, distinguish:

    current state

from:

    change in state

For example:

    breadth level

and:

    breadth expansion

are not the same concept.

### 5.5 No favorable sign assumptions

A large or positive measurement is not automatically favorable.

For example:

- high dispersion may mean leadership or fragmentation;
- increasing breadth may mean healthy participation or late-stage crowding;
- relative strength may mean catch-up or already-extended momentum.

The meaning must be tested later rather than embedded into the representation.

---

## 6. Concept 1: market participation expansion

### Expected mechanism

A move involving increasing participation across the frozen market universe
may be more persistent than an isolated asset move.

The hypothesis concerns EXPANSION of participation, not simply high breadth.

### Causal question

    Are more assets beginning to participate before E1?

### Candidate observables

Using only the frozen five-symbol universe:

    breadth_now

        fraction of symbols with positive return over a recent completed
        interval

    breadth_previous

        same quantity over the immediately preceding non-overlapping interval

    breadth_change

        breadth_now - breadth_previous

    new_joiner_fraction

        fraction of symbols negative/non-positive in the previous interval
        but positive in the recent interval

    persistent_participant_fraction

        fraction positive in both intervals

Possible intervals should be defined from completed bars only.

Initial representation candidate:

    previous 60m interval
    recent 60m interval

using adjacent NON-OVERLAPPING intervals.

Example at E1 time t:

    recent:
        [t-60m, t)

    previous:
        [t-120m, t-60m)

Exact bar-boundary semantics must be defined before implementation.

### Alternative interpretations

Increasing breadth may indicate:

- genuine market participation;
- synchronized reaction to a common event;
- late-stage crowding;
- temporary correlation spike.

Therefore breadth expansion is descriptive, not inherently bullish.

### Redundancy

Do not simultaneously include many overlapping:

    1h breadth
    3h breadth
    6h breadth
    mean return
    positive fraction

unless each has a distinct role.

The primary information sought here is CHANGE IN PARTICIPATION.

### Measurement limits

Five symbols are not "the crypto market."

Any such measurement must be described as:

    frozen-five-symbol participation

not market-wide participation.

---

## 7. Concept 2: leadership / initiation order

### Expected mechanism

The identity and timing of the earliest directional move may help distinguish
a broad transition from a simultaneous or asset-specific move.

Leadership here means PRICE LEADERSHIP only.

It does not establish information flow, order flow, causation, or informed
trading.

### Causal question

    Which asset began moving first before E1, and did that move persist?

### Candidate observable structure

A causal directional-onset rule must be defined.

The onset rule must be:

- deterministic;
- based only on completed historical data;
- identical across symbols;
- frozen before outcomes are inspected.

Possible representation dimensions include:

    time_since_btc_onset
    time_since_asset_onset
    asset_minus_btc_onset_delay
    number_of_symbols_with_prior_onset
    earliest_onset_symbol
    persistence_since_onset

However, the exact onset rule is NOT yet frozen by this document.

### Prohibited leadership definitions

Do not define the leader as:

- the asset with the highest subsequent return;
- the first asset later reaching +X%;
- the asset whose future move was largest;
- the asset later shown to have "caused" the move.

### Alternative interpretations

Earlier movement may reflect:

- genuine leadership;
- noise;
- a temporary idiosyncratic move;
- different asset volatility.

### Measurement limits

Price data can identify temporal ordering of price changes.

Price data alone cannot determine:

- who initiated trading pressure;
- information source;
- liquidity shock origin;
- causal transmission.

---

## 8. Concept 3: acceleration

### Expected mechanism

A transition may be more persistent when directional movement is strengthening
rather than merely remaining positive.

The concept is CHANGE IN MOMENTUM, not the absolute level of trailing return.

### Causal question

    Is recent directional movement strengthening relative to immediately
    preceding movement?

### Preferred representation

Use adjacent, non-overlapping intervals.

Example:

    R_recent_60
        return over [t-60m, t)

    R_previous_60
        return over [t-120m, t-60m)

    acceleration_60
        R_recent_60 - R_previous_60

The same principle can apply to market/basket return and asset-relative
return.

### Why non-overlapping windows

C30 included overlapping trailing windows such as:

    1h
    3h
    6h
    12h
    24h

Those mix current level, persistence and acceleration.

Adjacent non-overlapping intervals make the behavioral distinction clearer.

### Alternative interpretations

A high acceleration value may result from:

- sustained strengthening;
- one large bar;
- rebound after a weak prior interval.

Therefore later implementation should consider persistence/robustness without
using future bars.

### Measurement limits

Price acceleration is not equivalent to:

- order-flow acceleration;
- volume-pressure acceleration;
- liquidity demand.

---

## 9. Concept 4: relative catch-up

### Expected mechanism

The candidate asset may initially lag a broader move but become more attractive
when it begins closing that relative deficit before becoming extended.

This is the core mechanism of the catch-up hypothesis.

### Causal questions

    Was the asset behind the market before the recent transition?

and:

    Is its relative movement now improving?

### Candidate representation

Define a fixed reference:

    BTC
or
    equal-weight frozen-five-symbol basket excluding/including subject
    according to a prospectively fixed rule

No choice is made yet.

For reference return M and asset return A:

    prior_relative_return
        = A_previous - M_previous

    recent_relative_return
        = A_recent - M_recent

    relative_improvement
        = recent_relative_return - prior_relative_return

A catch-up candidate conceptually requires:

    prior relative deficit

followed by:

    improving relative movement

But no numerical threshold is frozen here.

### Important distinction

An asset with high relative strength is not necessarily catching up.

For example:

    already strong -> remains strong

is a momentum/leader state.

Whereas:

    previously weak -> improving

is a catch-up state.

These are behaviorally different.

### Alternative interpretations

Improving relative performance can mean:

- genuine catch-up;
- temporary bounce in a weak asset;
- broader market weakening while the asset falls less;
- rotation.

Therefore absolute and relative movement must be interpreted jointly.

### Measurement limits

Relative return alone cannot distinguish buying pressure from passive
outperformance caused by weaker movement elsewhere.

---

## 10. Concept 5: dispersion and convergence

### Expected mechanism

Cross-sectional dispersion may help characterize whether a broad move is:

- becoming coordinated;
- fragmenting;
- rotating between assets.

The hypothesis does not prescribe whether higher or lower dispersion is
favorable.

### Causal question

    Are asset returns becoming more similar or more separated before E1?

### Candidate representation

For the frozen five-symbol universe:

    dispersion_recent
        cross-sectional standard deviation or robust spread of recent returns

    dispersion_previous
        same measure over immediately preceding non-overlapping interval

    dispersion_change
        dispersion_recent - dispersion_previous

Potentially also:

    subject_distance_from_market_center

### Alternative interpretations

Increasing dispersion may mean:

- emerging leadership;
- fragmentation;
- rotation;
- one outlier asset.

Decreasing dispersion may mean:

- healthy broad confirmation;
- indiscriminate risk-on move;
- late synchronization.

No favorable direction is assumed.

### Measurement limits

Five assets provide only a coarse cross-sectional measure.

The statistic must not be described as whole-market dispersion.

---

## 11. Concept 6: trend maturity

### Expected mechanism

The same E1 cross may have different implications depending on whether it
occurs near the beginning of a transition or after a substantial move has
already occurred.

### Causal question

    How mature is the move when E1 fires?

### Candidate representation

Once a causal onset rule exists:

    elapsed_time_since_asset_onset
    elapsed_time_since_market_onset
    cumulative_asset_return_since_onset
    cumulative_market_return_since_onset
    relative_extension_since_onset

Potential complementary measures:

    number_of_completed_positive_intervals_since_onset
    number_of_completed_participation-expansion intervals

### Critical requirement

Onset must be detectable using only information available at each historical
time.

Do NOT use:

- hindsight local minima;
- future-confirmed pivot points;
- centered indicators;
- future reversal confirmation.

### Alternative interpretations

Large extension can mean:

- mature/exhausted move;
- strong persistent trend.

Small extension can mean:

- early opportunity;
- weak/nonexistent trend.

The representation measures maturity; it does not declare its effect.

---

## 12. Proposed causal sequence representation

The catch-up hypothesis requires ORDER, not merely a bag of simultaneous
features.

The conceptual sequence is:

    T0: broader participation begins expanding

    T1: candidate asset remains relatively behind

    T2: candidate relative movement begins improving

    T3: E1 fires

with:

    T0 <= T1/T2 <= T3

depending on exact semantics.

A future implementation should explicitly record event/timing quantities such
as:

    minutes from participation onset to E1
    minutes from relative-improvement onset to E1
    relative deficit before improvement
    amount recovered by E1
    asset extension by E1
    market extension by E1

The sequence itself may carry more information than any individual feature.

---

## 13. E1 timing adequacy

A central open question is:

    Is E1 early enough to observe and act on the proposed catch-up transition?

The design MUST allow the answer to be NO.

Possible situations include:

### E1 after transition

Participation expansion and catch-up may occur substantially before E1.

Then E1 may represent late confirmation rather than transition entry.

### E1 during transition

E1 may occur while the candidate asset is beginning to join the move.

This is the intended catch-up hypothesis.

### E1 before clear transition

E1 may occur before broad participation/catch-up evidence develops.

Then the transition representation may be more useful after E1 rather than at
entry.

No one of these cases is assumed in advance.

A later diagnostic may compare causal event timestamps relative to E1 without
constructing a trading rule.

---

## 14. Representation minimalism

The initial representation should be deliberately compact.

Prefer a small number of behaviorally distinct quantities.

Avoid reproducing C30 by creating:

    return_15m
    return_30m
    return_45m
    return_60m
    return_90m
    return_120m

unless each horizon has an explicit mechanistic role.

A candidate minimal structure might contain one or two measurements for each
of:

    participation expansion
    initiation order
    market acceleration
    prior relative deficit
    relative improvement
    dispersion change
    maturity at E1

This is a design target, not yet a frozen feature schema.

---

## 15. Redundancy rules

Before any future model is fitted, candidate quantities must be audited for:

### Exact duplication

Example:

    X == Y

### Algebraic dependence

Example:

    relative_return = asset_return - btc_return

If all three are included, document why.

### Derived-feature dependence

Example:

    current_geometry
    previous_geometry
    geometry_change = current - previous

Do not automatically include all three.

### Heavy conceptual overlap

Example:

    market mean return
    breadth fraction
    number positive
    BTC return

may all represent overlapping broad-direction information.

The representation review should identify the minimum set needed to express
the hypothesis.

---

## 16. Data availability

Current data can potentially support:

- 1-minute price paths;
- completed-hour context;
- temporal ordering of price moves;
- fixed-five-symbol participation;
- relative price movement;
- cross-sectional dispersion;
- price-based trend onset;
- price-based trend maturity.

Current price data alone cannot establish:

- order-flow imbalance;
- market depth;
- spread dynamics unless separately recorded;
- liquidation pressure;
- funding pressure for spot-only historical data;
- exchange-wide capital flows;
- identity of informed traders;
- causal transmission between assets;
- news/event cause.

Do not infer those mechanisms from price-only measurements.

---

## 17. Required representation review before experiment authorization

Before a future experiment may be contracted, produce a table for every
candidate quantity containing:

    concept
    variable name
    exact formula
    source timeframe
    observation window
    interval boundaries
    availability timestamp
    behavioral rationale
    alternative interpretation
    redundancy relationship
    missing-data behavior
    measurement limitation

No outcome statistics should be used to choose among candidate definitions at
this stage.

---

## 18. Open design decisions

The following remain intentionally unresolved:

### Directional onset rule

How should a causal market/asset transition onset be detected?

### Reference for catch-up

Should relative behavior use:

    BTC
or
    frozen five-symbol basket
or
    another prospectively defined reference?

### Base interval

Should transition change be measured using:

    adjacent 30-minute windows
    adjacent 60-minute windows
    another prospectively justified interval?

### Participation definition

Should participation mean:

    positive return
    return above a fixed noise floor
    above a causal trend state
    another deterministic rule?

### Persistence

How many completed intervals are required before movement is considered
persistent?

These decisions must be made conceptually and prospectively.

They must not be selected by testing which version best predicts historical
returns.

---

## 19. Governance

Until this representation design is completed:

- no C31;
- no new predictive model;
- no nonlinear-model test;
- no feature search;
- no threshold search;
- no new entry rule;
- no trading policy;
- no P&L optimization;
- no 2026 access.

This document is a design checkpoint only.

---

## 20. Next step

The next task is to turn the behavioral concepts above into a small set of
precise causal measurement definitions.

The priority is not predictive performance.

The priority is:

    Does the representation faithfully encode the hypothesized transition?

Only after those definitions are frozen should a new experiment be considered.
