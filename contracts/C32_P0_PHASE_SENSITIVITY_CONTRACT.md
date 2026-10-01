# C32 P0 Daily-Window Phase Sensitivity Contract

Status: prospective and frozen before execution.

C32 tests a new hypothesis about the retired model.

It does NOT modify P0.

It asks whether the economics of the canonical slow P0 exit depend materially
on the arbitrary phase at which its 24-hour OHLCV state is sampled.

This is a phase/sampling diagnostic.

It is NOT:

- a new exit strategy;
- a faster exit model;
- a new entry rule;
- a feature search;
- a threshold search;
- a trading-policy optimization.

---

## 1. Scientific hypothesis

The working hypothesis is:

    The model may suffer from temporal phase/sampling error rather than from
    fundamentally incorrect P0 exit logic.

In particular:

    P0 may identify an appropriate exit state when evaluated on a 24-hour
    market window, but evaluating that state at only one fixed daily phase may
    cause favorable exit states to be missed until the next daily evaluation.

C32 tests phase only.

It does NOT yet test increased evaluation frequency.

---

## 2. Fundamental distinction

C32 must distinguish:

    INFORMATION HORIZON

from:

    EVALUATION PHASE

P0 remains a slow 24-hour-state exit.

For every C32 variant:

    P0 information horizon = unchanged
    P0 formula             = unchanged
    P0 model               = unchanged
    P0 threshold           = unchanged
    evaluation frequency   = once every 24 hours

Only the phase of the 24-hour aggregation/evaluation boundary changes.

Example:

    phase 00:
        bars end at 00:00 UTC each day

    phase 01:
        bars end at 01:00 UTC each day

    ...

    phase 23:
        bars end at 23:00 UTC each day

This is NOT equivalent to evaluating P0 hourly.

---

## 3. Frozen entry population

Use the exact frozen Binance E1 entry population:

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

Entries are frozen.

Do not regenerate, retime, filter, or alter entry decisions based on C32 phase.

---

## 4. Canonical P0 reconstruction

Before any phase experiment, reproduce the exact canonical P0 exit.

Use the committed/frozen P0 implementation and accepted historical artifacts
as authoritative.

Determine and record:

- exact P0 model/function;
- feature definitions;
- feature ordering;
- model parameters;
- exit threshold/decision semantics;
- canonical daily OHLCV construction;
- canonical daily boundary/phase;
- decision timestamp;
- execution timestamp;
- next-open semantics;
- terminal/right-censoring semantics;
- cost accounting.

Do NOT infer these from memory if repository artifacts/code provide them.

The canonical phase must be discovered from the accepted implementation.

Do not assume 00:00 UTC unless verified.

---

## 5. Canonical P0 reconciliation gate

Before phase shifting:

Recompute canonical P0 from the frozen entries and accepted pre-2026 market
data.

Reconcile exactly against accepted P0 outcomes at minimum for:

- trade count;
- exit timestamps;
- exit prices before costs;
- gross return;
- net return under C_BASE;
- year counts;
- symbol counts.

Use semantic hashes where existing accepted artifacts provide them.

If canonical P0 cannot be reproduced materially:

    C32_INSUFFICIENT

and STOP.

No phase experiment may proceed from an unreconciled P0.

---

## 6. Sealed future boundary

Do not access, enumerate, inspect, count, hash, validate, or use 2026 market
data or metadata.

C32 uses accepted pre-2026 data only.

Entries near the end of available history must follow the frozen P0
right-censoring / terminal semantics.

---

## 7. Phase grid

After canonical P0 reconciliation, construct exactly 24 phase variants.

Let:

    h ∈ {0,1,...,23}

represent UTC hour-of-day at which a 24-hour bar ends.

For phase h:

    each slow bar covers exactly 24 hours

and ends at:

    ... h:00 UTC
    ... next day h:00 UTC
    ... etc.

Use half-open causal intervals:

    [end_ts - 24h, end_ts)

No market data at or after end_ts enters the completed 24-hour bar.

---

## 8. Continuous Binance market assumption

Binance spot operates continuously for the purpose of this historical
experiment.

Therefore there is no privileged exchange close embedded into C32.

However, the experiment must not assume phase invariance.

Changing aggregation phase may change:

- open;
- high;
- low;
- close;
- volume;
- derived features;
- P0 model state.

That phase dependence is precisely what C32 measures.

---

## 9. P0 invariance

For all 24 variants keep exactly unchanged:

- P0 algorithm;
- P0 model parameters;
- P0 feature transformations;
- lookback expressed in number of 24-hour bars;
- thresholds;
- decision logic;
- entry population;
- entry timestamps;
- entry execution;
- cost model;
- terminal behavior.

Do NOT retrain P0 for each phase.

Do NOT recalibrate.

Do NOT normalize separately by phase unless the original frozen P0 itself does
so causally.

---

## 10. Evaluation cadence

For each phase:

    P0 may be evaluated only once per 24 hours.

For a trade entered after a phase boundary:

    the first eligible P0 evaluation is the next phase boundary at which all
    required P0 inputs are causally available.

No intra-day evaluation is permitted in C32.

That belongs to a later sampling-frequency experiment.

---

## 11. Exit execution

When P0 produces its frozen exit decision at phase boundary t:

    execute at the exact canonical P0 execution timing.

If canonical P0 uses:

    next valid 1-minute open

then every shifted phase must use the same rule.

No same-bar close fill unless canonical P0 already uses it.

No favorable fill substitution.

---

## 12. Transaction costs

Use the frozen cost cases:

    C0
    DESIGN_BNB
    C_BASE
    C_S5
    C_S10

C_BASE is primary.

Phase shifting does not create an additional exit/re-entry cycle.

Every completed trade remains:

    one entry
    one terminal exit

unless frozen P0 semantics explicitly say otherwise.

---

## 13. Primary paired comparison population

The primary phase comparison must use a COMMON-SUPPORT population.

A trade belongs to common support iff all 24 phase variants can be evaluated
under identical accepted-data and terminal rules without accessing 2026.

Report:

    common-support trade count
    excluded count
    exclusion reasons
    by year
    by symbol

Primary cross-phase inference uses this identical paired population.

Phase-specific full-population results may also be reported as secondary
diagnostics.

---

## 14. Primary economic outcome

For each trade i and phase h calculate:

    NET_RETURN_C_BASE(i,h)

using exact executed prices and C_BASE costs.

For every phase report:

- trade count;
- mean net return;
- median net return;
- total net P&L for frozen notional convention;
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

No phase is selected.

---

## 15. Gross-return diagnostics

Also report the same phase profile at:

    C0

This distinguishes:

    market/exit timing effect

from:

    cost accounting.

Because all variants ordinarily have the same number of entry/exit legs,
phase differences should primarily arise from execution timing rather than
turnover count.

---

## 16. MFE and surrender

For each phase-specific trade lifecycle:

    entry -> phase-specific P0 exit

compute causally/evaluation-only:

    MFE_RETURN
        maximum favorable price excursion before that phase's exit

    REALIZED_GROSS_RETURN

    SURRENDER_GAP
        = MFE_RETURN - REALIZED_GROSS_RETURN

MFE remains evaluation-only.

It may not influence P0 decisions.

For every phase report:

- mean MFE;
- median MFE;
- mean surrender gap;
- median surrender gap;
- fraction with realized return < 0 despite positive MFE;
- fraction retaining at least 25%, 50%, 75% of positive MFE where defined.

---

## 17. MFE timing diagnostic

For each phase-specific lifecycle record:

    MFE_TS

and:

    EXIT_MINUS_MFE_MINUTES
        = exit execution timestamp - MFE_TS

Report phase-level distributions:

- median;
- p25;
- p75;
- p90.

Purpose:

    determine whether certain aggregation phases cause P0 to observe and act
    closer to favorable excursion.

Do not use MFE_TS in the exit decision.

---

## 18. Exit timing diagnostics

For every phase report:

- median holding time;
- mean holding time;
- p10/p25/p75/p90 holding time;
- exit hour-of-day distribution;
- fraction exiting earlier than canonical P0;
- fraction exiting later than canonical P0;
- fraction exiting at identical timestamp to canonical P0.

All comparisons are paired on common-support trades.

---

## 19. Canonical-phase deltas

Let:

    h0 = verified canonical P0 phase.

For each phase h compute paired:

    DELTA_NET_RETURN(i,h)
        = NET_RETURN_C_BASE(i,h)
          - NET_RETURN_C_BASE(i,h0)

Report phase-level:

- mean;
- median;
- total P&L difference;
- wins / losses / ties versus canonical;
- trade-bootstrap 95% CI;
- month-bootstrap 95% CI.

These are descriptive comparisons.

Do NOT select the largest delta as a new policy.

---

## 20. Robust phase-profile statistics

Because max/min across 24 phases is selection-sensitive, primary phase
sensitivity must NOT rely on the best phase.

For each year and pooled common-support sample compute:

### Robust phase spread

    PHASE_P90_P10_SPREAD

equal to:

    90th percentile of the 24 phase mean net returns
    -
    10th percentile of the 24 phase mean net returns.

### Phase RMS variation

Let m_h be phase h mean net return and m_bar the mean across all 24 phases.

    PHASE_RMS
        = sqrt(mean_h((m_h - m_bar)^2))

### Adjacent-hour roughness

Circularly:

    ADJACENT_ABS_CHANGE
        = mean_h(abs(m_h - m_{h+1 mod 24}))

Report all three.

---

## 21. Cross-year phase-profile stability

Using the vector of 24 C_BASE phase mean net returns:

    profile_2024
    profile_2025

compute:

- Pearson correlation;
- Spearman correlation;
- centered-profile correlation after subtracting each year's phase mean.

Also report phase-profile correlation for:

- surrender gap;
- holding time.

Purpose:

    distinguish a reproducible phase pattern from year-specific noise.

---

## 22. Circular smoothness diagnostic

A genuine phase effect may vary smoothly across neighboring aggregation
boundaries.

Compare:

    mean absolute difference between adjacent phase means

versus:

    mean absolute difference across all non-identical phase pairs.

Define:

    ADJACENT_SMOOTHNESS_RATIO
        = adjacent mean absolute difference
          /
          all-pair mean absolute difference

Values below 1 indicate neighboring phases are more similar than arbitrary
phases.

This is descriptive only.

---

## 23. No "best phase" selection

C32 may report:

- highest observed phase mean;
- lowest observed phase mean;
- canonical phase rank among 24 phases;

only as clearly labelled descriptive diagnostics.

It MUST NOT:

- nominate a production phase;
- freeze the historically best phase;
- rerun P0 using the best phase;
- claim the best phase is predictive.

The scientific object is the entire 24-hour phase-response profile.

---

## 24. Bootstrap

Use:

    2,000 iterations
    numpy PCG64
    one frozen seed

Perform paired bootstrap over:

    trade

and separately:

    UTC entry month.

Preserve all 24 phase outcomes for a sampled trade/month together.

Bootstrap at minimum:

- PHASE_P90_P10_SPREAD;
- PHASE_RMS;
- each phase delta versus canonical;
- 2024-vs-2025 phase-profile correlation where feasible.

No bootstrap-based phase selection.

---

## 25. Phase sensitivity interpretation

Return exactly one classification.

### STABLE_P0_PHASE_SENSITIVITY

Use only if all hold on common support:

1. C_BASE PHASE_P90_P10_SPREAD >= 0.0010
   (10 basis points) in both 2024 and 2025;

2. 2024-vs-2025 centered phase-profile Spearman correlation >= 0.50;

3. pooled adjacent smoothness ratio < 1.0;

4. no canonical-P0 reconciliation failure;

5. no material phase-specific data-quality asymmetry explains the result.

This classification means:

    the arbitrary daily aggregation phase materially and reproducibly changes
    P0 economics.

It does NOT mean any particular phase should be traded.

### UNSTABLE_P0_PHASE_SENSITIVITY

Use if:

- phase spread is economically material in at least one year;
- but the phase profile does not reproduce sufficiently across years;

or:

- large differences exist but appear irregular/non-smooth.

This means phase matters historically, but not in a sufficiently stable way
to treat the phase profile as established structure.

### NO_MATERIAL_P0_PHASE_SENSITIVITY

Use if:

    PHASE_P90_P10_SPREAD < 10 bp in both years

or phase variation is otherwise economically negligible.

### C32_INSUFFICIENT

Use only if:

- canonical P0 cannot be reproduced;
- common-support comparison cannot be established;
- causal phase bars cannot be reconstructed;
- source integrity fails;
- 2026 boundary cannot be guaranteed.

---

## 26. Stage-B gating

C32 does NOT execute higher-cadence P0.

It may conclude:

    HIGHER_CADENCE_P0_TEST_JUSTIFIED = true

only if:

    STABLE_P0_PHASE_SENSITIVITY

or:

    UNSTABLE_P0_PHASE_SENSITIVITY
    with pooled robust phase spread >= 10 bp
    and clear MFE/surrender timing differences.

This is only authorization to DESIGN the next experiment.

Do not execute it in C32.

---

## 27. Important alternative outcome

A finding of:

    NO_MATERIAL_P0_PHASE_SENSITIVITY

would argue against the idea that the original P0 problem is mainly the
arbitrary location of the daily OHLCV boundary.

It would NOT yet directly test:

    evaluating the same 24-hour P0 state more frequently.

Phase and cadence are separate hypotheses.

---

## 28. No retraining

Do NOT retrain:

- P0;
- entry model;
- feature scalers;
- thresholds;
- any classifier.

If P0 cannot accept shifted 24-hour OHLCV without retraining, document that as
a limitation.

Do not silently retrain it.

---

## 29. No new exit logic

Do NOT add:

- MFE threshold;
- trailing stop;
- take profit;
- T2;
- C13;
- C25;
- V4 probability;
- new classifier;
- discretionary exit.

Only canonical P0 is allowed.

---

## 30. Required causality tests

Synthetic or isolated tests must verify:

- shifted 24h OHLCV uses [t-24h,t);
- no bar at t enters a bar ending at t;
- P0 decision at t uses no post-t information;
- execution follows canonical next-executable semantics;
- mutating all post-decision data cannot alter P0 decision at t;
- entry remains unchanged under phase shift;
- phase h remains exactly once-per-24h evaluation;
- no accidental rolling-hourly P0 evaluation occurs.

---

## 31. Required phase construction tests

Verify at minimum:

- phase 00 consecutive bars are exactly 24h and non-overlapping;
- phase 01 is a one-hour translation of boundaries, not a 23/25h bar;
- phase 23 behaves analogously;
- all 24 phases cover equal-duration windows;
- OHLCV aggregation is exact:
      open  = first 1m open
      high  = max 1m high
      low   = min 1m low
      close = last completed 1m close
      volume = sum accepted 1m volume
  subject to the frozen source semantics.

---

## 32. Required artifacts

Write to:

    artifacts/c32_p0_phase_sensitivity/

At minimum:

- run_manifest.json
- provenance.json
- canonical_p0_reconciliation.json
- phase_definition.json
- phase_bar_audit.json
- population_reconciliation.json
- common_support.json
- phase_trade_counts.json
- phase_net_return_profile.json
- phase_gross_return_profile.json
- phase_mfe_profile.json
- phase_surrender_profile.json
- phase_mfe_timing_profile.json
- phase_holding_time_profile.json
- canonical_phase_deltas.json
- robust_phase_statistics.json
- cross_year_phase_stability.json
- circular_smoothness.json
- trade_bootstrap_intervals.json
- month_bootstrap_intervals.json
- symbol_phase_profiles.json
- cost_robustness.json
- causality_tests.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid unnecessary giant row-level artifacts.

---

## 33. Reproducibility

Record:

- C32 contract SHA-256;
- canonical P0 implementation hash;
- canonical P0 reference artifact hashes;
- source file hashes;
- population hash;
- phase-construction implementation hash;
- result semantic hashes;
- Python version;
- environment;
- dependencies;
- RNG seed;
- git HEAD;
- dirty/untracked status;
- command.

Core results must reproduce deterministically.

---

## 34. Tests

Focused tests must cover at minimum:

- exact E1 population/hash;
- canonical P0 reconciliation;
- exact canonical phase discovery;
- all 24 phase boundaries;
- exact 24h duration;
- OHLCV aggregation;
- causal half-open intervals;
- one P0 evaluation per 24h;
- unchanged entry population;
- canonical execution timing;
- common-support construction;
- cost accounting;
- MFE evaluation-only behavior;
- paired phase deltas;
- robust phase spread;
- cross-year profile correlation;
- circular smoothness;
- deterministic PCG64 bootstrap;
- no retraining;
- no new exit logic;
- no 2026 access.

Run focused tests.

Run full suite once if scientific/runtime source changes.

---

## 35. Governance

Do NOT:

- modify canonical P0;
- modify E1;
- modify previous experiment artifacts;
- tune phase;
- select a production phase;
- increase evaluation cadence;
- start Stage B;
- stage implementation/results;
- commit implementation/results;
- push.

The C32 contract itself may be committed prospectively.

---

## 36. Final report

Report:

1. contract SHA-256;
2. canonical P0 implementation/reference hashes;
3. canonical P0 phase;
4. canonical P0 reconciliation;
5. exact E1 population reconciliation;
6. common-support population;
7. all 24 phase definitions;
8. C_BASE mean/median/P&L profile across 24 phases;
9. C0 profile;
10. MFE profile;
11. surrender-gap profile;
12. MFE-to-exit timing profile;
13. holding-time profile;
14. paired deltas versus canonical phase;
15. P90-P10 phase spread pooled/2024/2025;
16. phase RMS pooled/2024/2025;
17. circular adjacent smoothness;
18. 2024-vs-2025 phase-profile Pearson/Spearman;
19. symbol phase profiles;
20. cost robustness;
21. trade-bootstrap results;
22. month-bootstrap results;
23. canonical phase descriptive rank;
24. confirmation no phase was selected;
25. exact frozen classification:
       STABLE_P0_PHASE_SENSITIVITY
       UNSTABLE_P0_PHASE_SENSITIVITY
       NO_MATERIAL_P0_PHASE_SENSITIVITY
       C32_INSUFFICIENT
26. HIGHER_CADENCE_P0_TEST_JUSTIFIED true/false;
27. explicit statement that C32 does not test higher-frequency P0 evaluation;
28. artifact hash verification;
29. focused tests;
30. full-suite result if run;
31. git diff --check;
32. git status --short;
33. confirmation P0 was not retrained or modified;
34. confirmation no new exit logic was introduced;
35. confirmation no 2026 data/metadata was accessed;
36. confirmation implementation/results were not staged/committed/pushed.

STOP.
