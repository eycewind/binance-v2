# Binance Strategy Design Review

Status: strategy-design pause after C28.

This document records the intended economic design of the automated Binance
strategy before further model or policy research.

## 1. Evidence established so far

The completed research supports several distinct conclusions.

### Entry timing

Frozen E1 entry timing showed material advantage over the prespecified matched
non-signal reference at the primary H24 horizon.

This supports the existence of entry-timing information.

It does NOT by itself establish profitable trading.

### Canonical lifecycle

Canonical P0 was approximately flat before costs but materially negative after
the frozen realistic cost assumption.

C28:

- P0 C0 mean: approximately +0.0166%
- P0 C_BASE mean: approximately -0.2231%
- C_BASE cost drag versus C0: approximately 0.2398 percentage points

Thus trading friction is a first-order strategy constraint.

### Short-horizon exit information

The frozen S+C9 / Q1 state contained genuine information about adverse
five-minute continuation value.

However:

- permanent first-Q1 liquidation produced only weak economic improvement;
- temporary five-minute exit/re-entry was economically infeasible because
  the short-horizon adverse value was much smaller than the extra trading
  friction.

Therefore further local tuning of Q1 exits is not currently justified.

## 2. Intended implementation

### Venue

Binance.

### Product

Spot.

### Primary quote currency

USDT.

USDT-quoted pairs remain the primary automated-strategy universe because
strategy economics and account performance are evaluated primarily in
stablecoin / USD-equivalent terms.

BTC-quoted and BNB-quoted pairs may be investigated later as separate strategy
families.

They must not be mixed into the current USDT strategy simply to improve
historical results.

### Direction

Long-only.

### Leverage

None.

### Funding

None for the current spot strategy.

### Borrowing

None.

### Initial capital scale

Small enough that market impact is assumed negligible for initial deployment.

This assumption should be revisited if deployment capital increases
materially.

## 3. Trading fees and execution friction

### Intended deployment

Use BNB fee deduction where available.

The operational requirement is to maintain a small BNB balance and monitor it
so fee deduction remains active.

### Research cost assumptions

Maintain two useful cost references:

#### Expected deployment-style cost

Approximately:

- 7.5 bp explicit trading fee per leg with BNB fee deduction
- approximately 2 bp adverse execution allowance per leg

Indicative round trip:

    approximately 19 bp

#### Conservative cost

Approximately:

- 10 bp explicit trading fee per leg
- approximately 2 bp adverse execution allowance per leg

Indicative round trip:

    approximately 24 bp

The existing C_BASE assumption therefore remains a useful conservative
baseline.

Do not reduce assumed costs simply to make a strategy profitable.

Future live/paper execution should measure actual realized fee, spread and
slippage and replace assumptions with observed distributions.

## 4. Intended automated holding scale

The automated strategy is intended to capture relatively short crypto
transitions.

### Primary intent

Hold positions for hours.

### Typical lifecycle

Several hours.

### Normal upper scale

Approximately 24 hours.

### Exceptional extension

Up to approximately 48 hours only when a strong trend remains active.

This is not intended to be the normal lifecycle.

### Not the objective

The automated strategy is not intended to routinely hold positions for
several days in order to capture broad swing trends.

H72/H168 historical results therefore must not redefine the automated strategy
simply because they appear economically attractive.

## 5. Separate slower strategy

A slower multi-day crypto strategy may be researched separately.

Its intended workflow could resemble the PSX process:

- lower trade frequency;
- longer holding period;
- greater human review;
- potentially manual execution.

It must be treated as a separate strategy family with separate hypotheses,
cost assumptions, lifecycle and evaluation.

## 6. Economic viability hurdle

A statistically positive signal is not sufficient.

The automated strategy should have gross economic opportunity comfortably
above expected trading friction.

Indicative research hurdle:

### BNB-discounted deployment assumption

Expected round-trip friction:

    approximately 19 bp

Minimum gross opportunity worth serious research:

    approximately 40 bp or greater

### Conservative execution assumption

Expected round-trip friction:

    approximately 24 bp

Minimum gross opportunity worth serious research:

    approximately 50 bp or greater

These are strategy-viability hurdles, not entry or exit thresholds.

They must NOT be converted directly into take-profit rules.

The purpose is to avoid investing research effort in effects whose magnitude
is too close to the execution floor.

## 7. Required safety margin

The target opportunity must cover more than nominal fees.

Conceptually:

    required gross opportunity
        >
    expected trading friction
        + execution uncertainty
        + statistical/model uncertainty
        + worthwhile economic margin

A result that is only marginally above zero after costs is not sufficient
evidence for deployment.

## 8. Current strategic diagnosis

Current evidence is most consistent with:

    a real entry-timing signal
        +
    insufficiently large short-horizon absolute opportunity
        +
    substantial sensitivity to trading friction

The principal open question is no longer:

    "Can we find a better Q1 exit?"

The principal research question is:

    "Under what causal pre-entry or entry-time conditions does the strategy
     encounter opportunities whose expected magnitude is large enough to
     clear the economic hurdle?"

## 9. Next research direction

The next research phase should study opportunity magnitude.

Candidate explanatory families may include:

- entry-signal strength;
- broader BTC / market regime;
- relative strength versus BTC;
- cross-asset confirmation;
- volatility expansion;
- trend persistence;
- market-wide versus idiosyncratic movement.

These are candidate explanatory dimensions only.

No feature, regime, threshold or model is authorized yet.

The next experiment must be prospectively specified and must avoid selecting
conditions merely because they produced the largest historical return.

## 10. Research objective for the next phase

Determine whether there exist causally observable entry-time states for which
the expected executable opportunity over the intended several-hour to
approximately 24-hour lifecycle is materially larger than:

    40-50 bp gross

and remains economically meaningful after realistic costs and uncertainty.

If such states cannot be identified robustly, further optimization of the
current automated E1 strategy should be reconsidered.

If such states can be identified prospectively and robustly, later work may
test whether they can support an economically viable automated trading policy.

## 11. Governance

Until a new contract is explicitly authorized:

- no C29;
- no new model;
- no threshold search;
- no exit-policy tuning;
- no alternate holding-period selection;
- no BTC/BNB quote-pair mixing;
- no cost reduction to rescue historical P&L;
- no 2026 evaluation population.

The strategy-design pause remains in force.
