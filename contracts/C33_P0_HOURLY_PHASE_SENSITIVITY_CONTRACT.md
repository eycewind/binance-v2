# C33 P0 Hourly Phase Sensitivity Contract

Status: prospective and frozen before execution.

C33 is the final planned rescue diagnostic for the retired Binance model
family.

It tests whether the canonical hourly P0 exit is materially sensitive to the
sub-hour phase alignment of its 60-minute OHLCV bars.

This experiment does NOT alter:

- P0 logic;
- P0 model parameters;
- P0 feature definitions;
- 60-minute bar duration;
- 24-bar SMA lookback;
- hourly evaluation cadence;
- entry population;
- execution rule;
- transaction-cost assumptions.

Only the minute offset of the hourly bar/evaluation boundary changes.

---

## 1. Background

C32 established that the canonical P0 is:

    P0_H1_SMA24_CROSSDOWN_V1

with:

    bar duration:
        1 hour

    lookback:
        24 hourly closes

    evaluation cadence:
        every hour

    canonical boundaries:
        UTC hh:00

    execution:
        exact boundary 1-minute open

Therefore the relevant phase question is NOT daily-window phase.

It is:

    Does shifting the 60-minute bar boundary within the hour materially change
    P0 exit timing and economics?

---

## 2. Scientific hypothesis

Working hypothesis:

    P0 may be economically limited partly by temporal sampling phase.

The underlying slow decision rule may remain valid, while arbitrary alignment
of hourly bars at minute :00 may delay or alter detection of the cross-down
state.

C33 tests this without changing model resolution or evaluation frequency.

---

## 3. Frozen entry population

Use the exact frozen E1 population:

    2,199 entries

Entry rule:

    E1_H1_SMA24_CROSS_V1

Entry hash:

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

Entries remain completely frozen.

Do not phase-shift or regenerate E1.

---

## 4. Canonical P0

Canonical exit:

    P0_H1_SMA24_CROSSDOWN_V1

Canonical semantics from C32 are authoritative.

At each canonical hourly boundary:

    completed hourly close crosses below causal SMA24

with execution using the frozen canonical execution rule.

Before phase testing:

    reproduce canonical phase-00 P0 exactly.

Required reconciliation:

- exit timestamps;
- exit prices;
- exit reasons;
- gross returns;
- C_BASE net returns;
- trade hash;
- horizon hash.

Any material failure:

    C33_INSUFFICIENT

and STOP.

---

## 5. Sealed 2026 boundary

No 2026 market data or metadata may be:

- enumerated;
- inspected;
- opened;
- hashed;
- counted;
- validated;
- used.

Use accepted pre-2026 data only.

---

## 6. Phase grid

Construct exactly 60 phase variants:

    p = 0 ... 59

where p is the minute offset of each hourly boundary.

Examples:

    phase 00:
        00:00, 01:00, 02:00, ...

    phase 01:
        00:01, 01:01, 02:01, ...

    phase 15:
        00:15, 01:15, 02:15, ...

    phase 30:
        00:30, 01:30, 02:30, ...

    phase 59:
        00:59, 01:59, 02:59, ...

For every phase:

    bar duration = exactly 60 minutes
    evaluation cadence = exactly 60 minutes

No phase may use shorter/faster bars.

---

## 7. Hourly bar construction

For boundary t in phase p:

    H1 bar = [t-60m, t)

OHLCV:

    open   = first valid 1m open in interval
    high   = maximum 1m high
    low    = minimum 1m low
    close  = last completed 1m close before t
    volume = sum accepted 1m volume

No bar at or after t enters the completed H1 bar.

All 60 phases use identical aggregation semantics.

---

## 8. P0 invariance

For every phase preserve exactly:

- SMA lookback = 24 completed H1 bars;
- P0 cross-down formula;
- threshold semantics;
- model parameters;
- any frozen feature transforms;
- evaluation frequency = once per hour;
- execution rule;
- terminal/right-censoring semantics;
- costs.

Do NOT retrain.

Do NOT recalibrate.

Do NOT alter lookback to preserve clock-time labels.

Twenty-four shifted H1 bars still represent 24 hours.

---

## 9. Entry invariance

Entries remain the canonical frozen E1 trades.

Do NOT rebuild entry H1 bars using the shifted phase.

C33 changes EXIT observation phase only.

This is essential.

The experiment asks:

    given exactly the same entry,
    how does P0 behave if its hourly observation lattice is shifted?

---

## 10. First eligible exit evaluation

For a trade entered at time e and phase p:

The first P0 exit evaluation may occur only at the first phase-p hourly
boundary after entry for which the full frozen P0 state is causally available.

No evaluation before entry.

No evaluation exactly at an entry timestamp if the decision would have
required information unavailable before the entry.

Document boundary precedence explicitly.

---

## 11. Exit execution

Use exact canonical P0 execution semantics.

C32 established canonical execution at the exact boundary 1-minute open.

Therefore for shifted phase p:

    if P0 exit fires at t,
    execute using the valid 1-minute open at t

subject to frozen source validity.

Do not use:

- previous close;
- future close;
- best intraminute price;
- high/low;
- interpolation.

---

## 12. Costs

Use frozen cases:

    C0
    DESIGN_BNB
    C_BASE
    C_S5
    C_S10

Primary:

    C_BASE

Each trade remains one entry plus one terminal exit.

No re-entry.
No additional turnover cycle.

---

## 13. Common-support population

Primary inference must use identical paired trades across all 60 phases.

Define:

    COMMON_SUPPORT

as trades for which every phase can produce a valid outcome under frozen
source and terminal rules without accessing 2026.

Report:

- common-support count;
- excluded count;
- exact exclusion reasons;
- year counts;
- symbol counts.

All primary phase comparisons use common support.

Phase-specific full-population statistics may be secondary only.

---

## 14. Primary economic profile

For every phase p calculate:

    NET_RETURN_C_BASE(i,p)

Report phase-level:

- trade count;
- mean;
- median;
- total P&L under frozen notional convention;
- positive-return fraction;
- p10;
- p25;
- p75;
- p90.

Repeat:

- pooled;
- 2024;
- 2025;
- each symbol.

Do not select a phase.

---

## 15. Canonical paired deltas

Canonical phase:

    p0 = 00

For every trade and phase:

    DELTA_NET_RETURN(i,p)
        = NET_RETURN_C_BASE(i,p)
          - NET_RETURN_C_BASE(i,00)

Report for every p:

- mean paired delta;
- median delta;
- total P&L delta;
- wins;
- losses;
- ties;
- trade-bootstrap CI;
- month-bootstrap CI.

This is descriptive.

No historically best phase becomes policy.

---

## 16. Exit-time displacement

For every trade and phase:

    DELTA_EXIT_MINUTES(i,p)
        = EXIT_TS(i,p)
          - EXIT_TS(i,00)

Report:

- mean;
- median;
- p10;
- p25;
- p75;
- p90;
- fraction earlier;
- fraction later;
- fraction identical.

This is a primary diagnostic.

---

## 17. MFE evaluation

For each phase-specific lifecycle:

    entry -> phase-specific P0 exit

compute:

    MFE_RETURN
    MFE_TS

MFE is evaluation-only and may never affect P0.

Also compute:

    SURRENDER_GAP
        = MFE_RETURN - REALIZED_GROSS_RETURN

and:

    EXIT_MINUS_MFE_MINUTES
        = EXIT_TS - MFE_TS

---

## 18. MFE capture diagnostics

For every phase report:

- mean MFE;
- median MFE;
- mean surrender gap;
- median surrender gap;
- fraction realized negative despite positive MFE;
- fraction retaining >=25% of positive MFE;
- fraction retaining >=50%;
- fraction retaining >=75%;
- median EXIT_MINUS_MFE_MINUTES;
- p25/p75/p90 EXIT_MINUS_MFE_MINUTES.

The hypothesis predicts that some phases may detect P0 deterioration closer to
the favorable excursion.

No MFE-based exit is allowed.

---

## 19. Holding time

For every phase report:

- mean holding minutes;
- median;
- p10;
- p25;
- p75;
- p90.

Also report paired holding-time difference versus phase 00.

---

## 20. Full 60-phase response

The scientific object is the complete circular phase-response profile.

For each year and pooled report vectors for:

    mean C_BASE net return
    mean gross return
    median surrender gap
    median exit displacement
    median MFE-to-exit delay
    median holding time

Do not focus only on maxima.

---

## 21. Robust phase sensitivity statistics

For phase mean C_BASE net returns m_p:

### P90-P10 spread

    PHASE_P90_P10_SPREAD
        = percentile90(m_p)
          - percentile10(m_p)

### RMS phase variation

    m_bar = mean_p(m_p)

    PHASE_RMS
        = sqrt(mean_p((m_p - m_bar)^2))

### Full range

    PHASE_RANGE
        = max(m_p) - min(m_p)

Full range is descriptive only and not primary because it is max/min sensitive.

Report pooled, 2024, and 2025.

---

## 22. Circular smoothness

For p=0..59 with wraparound:

    adjacent_difference(p)
        = abs(m_p - m_(p+1 mod 60))

Compute:

    ADJACENT_MEAN_ABS_CHANGE

and:

    ALL_PAIR_MEAN_ABS_CHANGE

Define:

    ADJACENT_SMOOTHNESS_RATIO
        = adjacent mean
          / all-pair mean

A coherent phase response should generally vary more smoothly between nearby
phases than between arbitrary phases.

No hard profitability claim follows from smoothness.

---

## 23. Cross-year stability

Using the 60-dimensional phase profiles for 2024 and 2025 compute:

- Pearson correlation;
- Spearman correlation;
- centered Pearson correlation;
- centered Spearman correlation.

Center each year's vector by subtracting its own 60-phase mean.

Primary stability measure:

    centered Spearman correlation

Also calculate corresponding cross-year correlations for:

- surrender gap;
- exit displacement;
- MFE-to-exit delay.

---

## 24. Circular-shift robustness

Because phase is circular, compute whether the 2024 and 2025 profiles align
only after an arbitrary shift.

This is diagnostic only.

Report:

    maximum circular cross-correlation
    shift at maximum

BUT primary classification must use zero-shift correlation.

Do NOT realign years to claim stability.

A stable clock-phase effect should reproduce at the same minute phase.

---

## 25. Local-neighborhood consistency

For every phase p compute local 5-minute neighborhood mean:

    phases p-2 ... p+2
    circularly wrapped

Report the 60 neighborhood means.

Purpose:

    determine whether high/low phase regions are supported by neighboring
    minute offsets rather than isolated one-minute spikes.

Do NOT select the highest neighborhood.

---

## 26. Best/worst descriptive reporting

May report:

    maximum observed phase
    minimum observed phase
    canonical phase rank

but these are explicitly post-hoc descriptive statistics.

Do NOT:

- freeze a winner;
- recommend a production phase;
- rerun using the best phase;
- call the highest phase optimal.

---

## 27. Paired bootstrap

Use:

    2,000 iterations
    numpy PCG64
    one frozen seed

Bootstrap units separately:

    trade
    UTC entry month

Preserve all 60 phase outcomes jointly.

At minimum estimate intervals for:

- PHASE_P90_P10_SPREAD;
- PHASE_RMS;
- every phase delta vs phase 00;
- centered 2024-vs-2025 phase-profile Spearman where feasible.

No bootstrap-driven selection.

---

## 28. Cost robustness

Report full phase profile under:

    C0
    DESIGN_BNB
    C_BASE
    C_S5
    C_S10

Primary classification remains C_BASE.

Because phase does not change number of trade legs, broad phase structure
should not depend heavily on proportional fees, though executed prices may
change.

Report whether phase-profile rank correlations remain similar across cost
cases.

---

## 29. Symbol diagnostics

For each symbol report:

- 60-phase mean net-return profile;
- P90-P10 spread;
- phase RMS;
- centered 2024-vs-2025 correlation where sample size permits;
- correlation with pooled phase profile.

Do not require all symbols to have identical phase behavior.

Do not select symbol-specific phases.

---

## 30. Frozen classification

Return exactly one:

### STABLE_HOURLY_PHASE_SENSITIVITY

Only if all hold:

1. C_BASE P90-P10 phase spread >= 0.0010
   (10 bp) in both 2024 and 2025;

2. zero-shift centered 2024-vs-2025 Spearman phase-profile correlation >= 0.50;

3. pooled ADJACENT_SMOOTHNESS_RATIO < 1.0;

4. phase-00 canonical P0 reconciles exactly;

5. no material phase-specific source asymmetry explains the pattern;

6. common support remains sufficiently broad:
       >= 90% of the frozen 2,199 entries.

This means:

    P0 economics are materially and reproducibly sensitive to the arbitrary
    sub-hour alignment of otherwise identical H1 bars.

It does NOT establish a deployable phase.

### UNSTABLE_HOURLY_PHASE_SENSITIVITY

Use if:

- >=10 bp robust spread appears in at least one year or pooled;
- but zero-shift cross-year profile stability fails;
- or the profile is irregular/non-smooth.

This means:

    historical phase sensitivity exists but is not stable enough to treat as
    established exploitable structure.

### NO_MATERIAL_HOURLY_PHASE_SENSITIVITY

Use if:

- P90-P10 spread <10 bp in both years;

or:

- phase-dependent exit timing exists but produces economically negligible
  return/surrender differences.

### C33_INSUFFICIENT

Use only if:

- canonical P0 reconciliation fails;
- shifted H1 bars cannot be reconstructed causally;
- common support <90%;
- source integrity fails;
- 2026 boundary cannot be guaranteed.

---

## 31. Final stopping rule

C33 is the final planned rescue diagnostic for this Binance model family.

If classification is:

    NO_MATERIAL_HOURLY_PHASE_SENSITIVITY

then:

    RETIRE_MODEL_FAMILY = true

and no further rescue experiment is justified from the current research line.

If classification is:

    UNSTABLE_HOURLY_PHASE_SENSITIVITY

then:

    RETIRE_MODEL_FAMILY = true

unless human review identifies a concrete non-adaptive causal explanation for
the instability.

Do NOT automatically create another experiment.

If classification is:

    STABLE_HOURLY_PHASE_SENSITIVITY

then:

    RETIRE_MODEL_FAMILY = false_pending_review

and only a separately designed experiment may investigate whether phase
sampling can be exploited without post-hoc phase selection.

C33 itself does not un-retire the model.

---

## 32. No cadence increase

C33 evaluates exactly once every hour.

Do NOT evaluate:

- every 30m;
- every 15m;
- every 5m;
- every 1m.

That would change cadence and belongs to a separate hypothesis.

The only variable in C33 is sub-hour phase.

---

## 33. No retraining

Do not retrain or recalibrate P0.

No phase-specific model.

No phase-specific scaler.

No threshold adjustment.

---

## 34. No new exit logic

Do not add:

- trailing stops;
- take profit;
- MFE logic;
- T2;
- probability exits;
- V4 prediction;
- discretionary rules.

Only frozen P0.

---

## 35. Causality tests

Required:

- phase p H1 bar is exactly [t-60m,t);
- no bar at t enters completed state;
- 24-bar SMA uses exactly 24 completed shifted H1 closes;
- shifted P0 decision uses no post-t data;
- execution uses frozen boundary-open semantics;
- post-t mutation does not alter decision at t;
- entry is identical across all phases;
- evaluation cadence remains exactly 60m;
- phase changes boundary only.

---

## 36. Phase-construction tests

Verify:

- all 60 minute offsets;
- phase 00 reproduces canonical H1 bars/P0;
- phase 01 is exact +1 minute lattice shift;
- phase 59 is exact +59 minute lattice shift;
- all bars exactly 60 minutes;
- no gaps/overlaps inside a phase;
- OHLCV aggregation exact;
- 24-bar SMA uses phase-consistent bars.

---

## 37. Required artifacts

Write to:

    artifacts/c33_p0_hourly_phase_sensitivity/

At minimum:

- run_manifest.json
- provenance.json
- canonical_p0_reconciliation.json
- population_reconciliation.json
- phase_definitions.json
- phase_bar_audit.json
- common_support.json
- phase_net_return_profile.json
- phase_gross_return_profile.json
- canonical_phase_deltas.json
- exit_time_displacement.json
- phase_mfe_profile.json
- phase_surrender_profile.json
- phase_mfe_timing_profile.json
- phase_holding_time_profile.json
- robust_phase_statistics.json
- circular_smoothness.json
- cross_year_phase_stability.json
- circular_shift_diagnostic.json
- local_neighborhood_consistency.json
- trade_bootstrap_intervals.json
- month_bootstrap_intervals.json
- cost_robustness.json
- symbol_phase_profiles.json
- causality_tests.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid unnecessary row-level dumps.

---

## 38. Reproducibility

Record:

- C33 contract SHA-256;
- canonical P0 implementation hash;
- C32 canonical reconciliation hash;
- source hashes;
- population hash;
- phase implementation hash;
- semantic result hashes;
- environment;
- Python version;
- dependencies;
- RNG seed;
- git HEAD;
- dirty/untracked status;
- command.

---

## 39. Tests

Focused tests must cover:

- exact E1 population/hash;
- canonical P0 reconciliation;
- phase-00 identity;
- all 60 phase offsets;
- exact 60m duration;
- exact 24-bar SMA;
- exact hourly cadence;
- shifted OHLCV aggregation;
- entry invariance;
- exit boundary execution;
- common support;
- paired return deltas;
- exit displacement;
- MFE evaluation-only calculation;
- circular smoothness;
- cross-year profile correlation;
- local neighborhood calculations;
- PCG64 paired bootstrap;
- no retraining;
- no cadence increase;
- no new exit logic;
- no 2026 access.

Run focused tests.

Run full repository suite once if scientific/runtime source changes.

---

## 40. Governance

Do NOT:

- modify P0;
- modify E1;
- modify prior artifacts;
- select a production phase;
- increase P0 cadence;
- stage implementation/results;
- commit implementation/results;
- push;
- start another rescue experiment.

The C33 contract itself may be committed prospectively.

---

## 41. Final report

Report:

1. contract SHA-256;
2. canonical P0 hashes/reconciliation;
3. exact E1 reconciliation;
4. common-support count/rate;
5. phase-00 identity;
6. all 60 phase definitions;
7. C_BASE 60-phase mean/median/P&L profile;
8. C0 profile;
9. paired phase deltas vs phase 00;
10. exit-time displacement profile;
11. MFE profile;
12. surrender profile;
13. MFE-to-exit delay profile;
14. holding-time profile;
15. P90-P10 spread pooled/2024/2025;
16. RMS phase variation pooled/2024/2025;
17. full range descriptive values;
18. adjacent smoothness ratio;
19. 2024-vs-2025 zero-shift Pearson/Spearman;
20. centered Pearson/Spearman;
21. circular-shift diagnostic;
22. local-neighborhood consistency;
23. symbol diagnostics;
24. cost robustness;
25. trade-bootstrap results;
26. month-bootstrap results;
27. canonical phase rank, descriptive only;
28. confirmation no best phase was selected;
29. exact classification:
       STABLE_HOURLY_PHASE_SENSITIVITY
       UNSTABLE_HOURLY_PHASE_SENSITIVITY
       NO_MATERIAL_HOURLY_PHASE_SENSITIVITY
       C33_INSUFFICIENT
30. RETIRE_MODEL_FAMILY value;
31. explicit statement that C33 does not test increased cadence;
32. artifact hash verification;
33. focused tests;
34. full-suite result if run;
35. git diff --check;
36. git status --short;
37. confirmation P0 was unchanged;
38. confirmation E1 was unchanged;
39. confirmation no retraining occurred;
40. confirmation no new exit logic was introduced;
41. confirmation no 2026 data/metadata was accessed;
42. confirmation implementation/results were not staged/committed/pushed.

STOP.
