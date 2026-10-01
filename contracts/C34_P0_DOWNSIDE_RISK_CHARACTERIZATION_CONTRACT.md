# C34 P0 Downside-Risk Characterization Contract

Status: prospective and frozen before execution.

C34 does NOT attempt to revive the retired E1/P0 strategy.

It studies one component independently:

    P0_H1_SMA24_CROSSDOWN_V1

Scientific question:

    Does an H1 close crossing below its causal SMA24 identify reproducibly
    elevated subsequent downside risk?

P0 is studied as a market-state/risk event, not as the exit of an E1 trade.

---

## 1. Universe

Frozen five-symbol Binance universe:

    BTCUSDT
    ETHUSDT
    SOLUSDT
    XRPUSDT
    BNBUSDT

Use accepted pre-2026 source data only.

Do not access, enumerate, inspect, hash, or validate 2026 data or metadata.

---

## 2. P0 event definition

Use the exact frozen canonical rule:

    P0_H1_SMA24_CROSSDOWN_V1

At completed hourly boundary t:

    previous completed H1 close >= previous causal SMA24
    current completed H1 close  <  current causal SMA24

Use the exact canonical H1 aggregation and SMA24 semantics already reconciled
by C32/C33.

Do not modify thresholds, bar phase, cadence, or SMA definition.

---

## 3. Event population

Generate every valid P0 cross-down event during the accepted 2024-2025
research period for all five symbols.

This population is independent of E1.

Do not require:

- an open E1 trade;
- a previous E1 signal;
- T2;
- positive MFE;
- any strategy position state.

Report:

- total P0 events;
- by year;
- by month;
- by symbol.

Also report inter-event spacing.

Do not apply a refractory period unless the frozen P0 definition itself
requires one.

---

## 4. Forward horizons

For every P0 event t, characterize forward price behavior at fixed horizons:

    1h
    3h
    6h
    12h
    24h
    48h

Use exact causal event time t and future data only for evaluation.

No future quantity may influence event definition.

---

## 5. Forward endpoint return

For horizon H:

    FORWARD_RETURN_H
        = price(t + H) / execution_reference(t) - 1

Use a clearly documented executable/reference price consistent across event
and control populations.

Prefer exact boundary 1-minute open at t if supported by canonical P0
semantics.

Report mean, median, percentiles and positive/negative fractions.

---

## 6. Forward adverse excursion

For each horizon H compute:

    FORWARD_MAE_H

as the worst percentage decline from the event reference price occurring
within (t, t+H].

Also compute:

    TIME_TO_MAE_H

Do not use MAE for decisions.

Evaluation only.

---

## 7. Forward favorable excursion

For each horizon H compute:

    FORWARD_MFE_H

and:

    TIME_TO_MFE_H

Purpose:

    determine whether P0 identifies asymmetric downside rather than merely
    high-volatility periods.

---

## 8. Downside threshold incidence

For each P0 event measure whether price reaches:

    -0.5%
    -1.0%
    -2.0%
    -3.0%

within:

    3h
    6h
    12h
    24h
    48h

Report:

- incidence;
- median time-to-threshold among hits.

Also measure corresponding upside thresholds:

    +0.5%
    +1.0%
    +2.0%
    +3.0%

for symmetry diagnostics.

---

## 9. Primary reference population

P0 event outcomes must not be interpreted in isolation.

Construct an eligible NON-P0 hourly reference population.

Eligible reference hour:

- same symbol universe;
- same accepted 2024-2025 period;
- full horizon available;
- not a P0 cross-down event at t.

Primary comparison:

    P0 events
    versus
    eligible non-P0 hours

Report separately by year and symbol.

---

## 10. Matched-state reference

Also construct a secondary matched reference to reduce the possibility that
P0 merely proxies generic high-volatility / negative-return hours.

For each P0 event, match non-P0 hours from the same:

    symbol
    calendar year
    UTC month

and nearest available state based on pre-event causal quantities:

    current 1h return
    trailing 24h realized volatility
    current close / SMA24 - 1

Use a frozen deterministic nearest-neighbor procedure.

No future outcome may enter matching.

Record exact matching algorithm and match distances.

Do not tune matching based on results.

---

## 11. Primary effect measures

For each horizon compare P0 versus both reference populations on:

    mean forward return
    median forward return
    mean forward MAE
    median forward MAE
    mean forward MFE
    median forward MFE
    probability of <= -0.5%
    probability of <= -1%
    probability of <= -2%
    probability of <= -3%

Primary downside statistic:

    DELTA_MAE_24H
        = mean MAE_24H(P0)
          - mean MAE_24H(reference)

More negative means greater downside after P0.

Primary endpoint statistic:

    DELTA_RETURN_24H
        = mean RETURN_24H(P0)
          - mean RETURN_24H(reference)

---

## 12. Downside asymmetry

For every horizon compute an excursion asymmetry diagnostic:

    DOWNSIDE_ASYMMETRY_H
        = abs(mean MAE_H) - mean MFE_H

and compare P0 versus reference.

Also report:

    P(abs(MAE_H) > MFE_H)

Purpose:

    distinguish genuine downside skew from generic movement/volatility.

---

## 13. Temporal reproducibility

All principal statistics must be reported separately for:

    2024
    2025

Do not pool years as the only evidence.

Also report by symbol.

No result is considered reproducible solely because pooled results are strong.

---

## 14. Month-level diagnostics

Report event counts and primary 24h downside effect by UTC month.

Purpose:

    identify whether the effect is broad or driven by isolated crash months.

Do not remove adverse months.

Do not optimize exclusions.

---

## 15. Bootstrap

Use:

    2,000 iterations
    numpy PCG64
    one frozen seed

Bootstrap separately by:

    event
    UTC month

For matched-control comparisons preserve matched pairs.

Estimate 95% intervals for at minimum:

    DELTA_RETURN_24H
    DELTA_MAE_24H
    delta probability <= -1% within 24h
    delta probability <= -2% within 24h
    downside asymmetry difference

Report 2024 and 2025 separately as well as pooled.

---

## 16. Interpretation

Return exactly one classification.

### REPRODUCIBLE_P0_DOWNSIDE_SIGNAL

Use only if all hold:

1. P0 has worse 24h forward MAE than matched reference in both 2024 and 2025;

2. P0 has lower 24h mean forward return than matched reference in both years;

3. probability of at least -1% within 24h is higher after P0 than matched
   reference in both years;

4. month-bootstrap direction is consistent and pooled 95% CI for at least
   DELTA_MAE_24H excludes zero;

5. effect is not explained by one symbol or one isolated month.

This means:

    P0 appears to contain reproducible information about elevated near-term
    downside risk.

It does NOT imply that P0 is by itself a profitable trading strategy.

### WEAK_P0_DOWNSIDE_SIGNAL

Use when direction is broadly consistent but:

- magnitude is modest;
- confidence intervals cross zero;
- one year is materially weaker;
- or dependence on symbols/months is substantial.

### NO_USEFUL_P0_DOWNSIDE_SIGNAL

Use when:

- matched reference removes the apparent effect;
- year-to-year direction is inconsistent;
- downside is not meaningfully worse than reference;
- or P0 mainly identifies volatility without downside asymmetry.

### C34_INSUFFICIENT

Use only for data/reconciliation/causality failures.

---

## 17. No strategy construction

C34 must NOT:

- create an entry model;
- create a short strategy;
- optimize a stop;
- optimize an exit;
- combine P0 with E1;
- select horizons;
- tune thresholds;
- choose symbols;
- create trading rules.

This is component characterization only.

---

## 18. Required artifacts

Write to:

    artifacts/c34_p0_downside_characterization/

At minimum:

- run_manifest.json
- provenance.json
- p0_definition_reconciliation.json
- event_population.json
- event_spacing.json
- reference_population.json
- matched_reference.json
- forward_return_profiles.json
- forward_mae_profiles.json
- forward_mfe_profiles.json
- downside_thresholds.json
- upside_thresholds.json
- downside_asymmetry.json
- yearly_results.json
- symbol_results.json
- month_results.json
- trade_bootstrap_intervals.json
- month_bootstrap_intervals.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid giant unnecessary row-level artifacts.

---

## 19. Tests

Focused tests must verify:

- exact canonical P0 rule;
- exact H1/SMA24 construction;
- causal event timing;
- no future leakage;
- P0 event population independent of E1;
- forward horizon construction;
- MAE/MFE correctness;
- threshold-hit timing;
- non-P0 reference exclusion;
- matched-reference causality;
- deterministic matching;
- deterministic PCG64 bootstrap;
- no strategy construction;
- no 2026 access.

Run focused tests.

Run full suite once if scientific/runtime source code changes.

---

## 20. Governance

Do NOT:

- modify E1;
- modify P0;
- modify prior experiment artifacts;
- access 2026;
- stage implementation/results;
- commit implementation/results;
- push;
- start a new strategy experiment.

The C34 contract itself may be committed prospectively.

---

## 21. Final report

Report:

1. contract SHA-256;
2. exact reconciled P0 definition;
3. total P0 event count;
4. counts by year/symbol/month;
5. inter-event spacing;
6. forward return profiles 1h-48h;
7. forward MAE profiles;
8. forward MFE profiles;
9. downside threshold incidence;
10. upside threshold incidence;
11. unmatched reference comparisons;
12. matched-state comparisons;
13. downside asymmetry;
14. 2024 vs 2025;
15. symbol consistency;
16. month consistency;
17. trade bootstrap;
18. month bootstrap;
19. exact classification;
20. explicit statement that no strategy was constructed;
21. artifact hash verification;
22. focused tests;
23. full-suite result if run;
24. git diff --check;
25. git status --short;
26. confirmation no 2026 access;
27. confirmation nothing staged/committed/pushed.

STOP.
