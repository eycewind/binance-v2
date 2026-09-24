# C4 — Sequential Exit-State Transition Experiment

Status: research design contract for review. Creating this contract does not authorize implementation, data construction, model fitting, evaluation, Stage B, or access to 2026.

Target repository: `/media/ata/Data/personal/binance-v2`

Future delivery destination: `contracts/C4_sequential_exit_state_DELIVERY.md`

Future artifact root: `artifacts/c4_sequential_exit_state/`

## 1. Background

C2 evaluated frozen `E1_H1_SMA24_CROSS_V1` entries against P0 and several deterministic faster exits. The faster exits reduced some held-path giveback, but they did not improve common-horizon opportunity capture or robust net expectancy. P1, P2, and P3 were not advanced.

C3 asked whether state observed at two fixed favorable milestones predicted continuation before fallback. Models were developed on 2024 and evaluated once, locked, on 2025. M1 was `MIXED`; M2 `COUNTS AGAINST`. Some weak ranking structure, especially for M1, did not survive the required standard of proper scoring, calibration, temporal stability, and cross-asset incremental value. C3 must not be reopened or retuned.

Those results neither prove nor disprove that the path contains information between milestones. C4 asks a different question:

> Given a frozen E1 trade that is open at completed-bar boundary `t`, does its causal path state at `t` add stable information about near-term continuation, reversal, or surrender of earned unrealized gain beyond simple state and regime controls?

C4 replaces C3's single milestone-conditioned snapshot with repeated causal state observations. It does not reinterpret the C2/C3 failures as evidence that C4 should succeed.

All of 2024 and 2025 is development-era material. Although 2025 is chronologically out of time for C4, it was inspected in C3 and is not pristine or untouched. The period beginning `2026-01-01T00:00:00Z` remains completely sealed.

## 2. Objective

Stage A shall determine whether a compact, continuously evolving causal path representation improves probabilistic prediction of two pre-registered near-term transition questions beyond current return, barrier geometry, elapsed time, volatility, symbol, and broad market regime.

The key path-history comparison is `P1` versus `G1`, not raw AUC and not a comparison only with an unconditional event rate. `G1` versus `G0` measures the value of richer current-state geometry only and cannot support a historical-path claim. C4 must permit the conclusion that historical path features add nothing.

## 3. Scope / Non-Scope

### In scope for a later authorized Stage A

- Reuse the accepted frozen E1 trades and immutable P0-derived common horizons from C2 after verifying accepted provenance.
- Construct causal snapshots at completed UTC-aligned 5-minute boundaries while each trade remains open under its common horizon.
- Construct the two separate targets in Section 7.
- Fit only the pre-registered baselines and interpretable models in Section 17.
- Evaluate proper scores, calibration, temporal and cross-symbol stability, exclusions, and dependence-aware uncertainty.
- Produce deterministic schemas, manifests, attempt ledgers, and a scientific interpretation.

### Out of scope

- Any exit, hold, sell, trailing-stop, dynamic-stop, sizing, allocation, turnover, P&L, fee, slippage, portfolio, paper/live trading, or deployment rule.
- Reopening, modifying, or retuning C2 or C3; modifying E1, P0–P3, their cohorts, or accepted artifacts.
- Access of any kind to 2026 data or outcomes.
- New entry fixtures, symbols, historical-universe claims, or generalization beyond the fixed research fixture.
- AutoML, deep learning, trees, boosting, broad feature generation, broad hyperparameter sweeps, symbol-specific models, post-result feature additions, or causal-effect claims.
- Treating snapshots, trades, symbols, or calendar periods as independent replications when they are not.

## 4. Frozen Predecessor Assumptions

- E1 entry identifiers, symbols, timestamps, prices, and fixture version are immutable.
- Each trade's P0-derived common-horizon endpoint `H` is immutable. C4 does not recompute P0 or extend a path beyond `H`.
- Accepted C1/C2 timestamp availability, gap-breaking, symbol isolation, aggregate-bar, and deterministic-output semantics remain binding.
- C2/C3 artifacts are read-only inputs only if a later implementation contract explicitly authorizes their use and their accepted hashes reconcile.
- C3 targets, feature results, and 2025 findings may motivate this new pre-registered experiment but may not be retuned or silently imported as C4 labels.

## 5. Experimental Unit

The scientific source unit is a frozen E1 trade. The prediction row is a **trade-time landmark**: one eligible trade observed at one completed 5-minute boundary `t`. A trade may contribute many rows, so row count is not effective sample size.

The two targets create separate analytic tables and risk sets. A snapshot may be eligible for `T1` and not `T2`. The same row identifier may appear in both audit tables, but targets, fits, metrics, calibration, uncertainty, and interpretations remain separate.

Canonical row identity is `(dataset_version, target_id, trade_id, snapshot_ts)`. Deterministic order is `(snapshot_ts, symbol, trade_id, target_id)`.

## 6. Snapshot Cadence

Primary cadence is every completed, UTC-aligned 5-minute boundary:

- snapshot timestamps are exactly `t = k * 300000` UTC integer milliseconds for integer `k`;
- a 5-minute aggregate `[T,T+5m)` is available at `t = T+5m`;
- an eligible snapshot at `t` uses information with availability timestamp `<= t`;
- the latest included one-minute source interval is `[t-1m,t)`;
- the snapshot reference price is that valid interval's close, equivalently the close of `[T,T+5m)`;
- `t` must be strictly after entry execution and strictly before `H`;
- the complete aggregate ending at `t` must be wholly post-entry (`T >= entry_execution_ts`); and
- monitoring for the forward label begins at `t`, with the first eligible future source interval `[t,t+1m)`.

Five minutes is chosen because C2's fast layer and the causal path variables already have meaningful 5-minute semantics, while it limits serial duplication and noise relative to one-minute snapshots. One-minute source data remains necessary only to resolve forward barrier chronology and audit aggregate validity. An every-minute snapshot sensitivity is not authorized. A different cadence requires a reviewed amendment before outcomes are viewed.

## 7. Primary Target / Hazard Definitions

C4 V1 has exactly two separate targets. All percentage comparisons use raw simple-price levels and inclusive equality under the accepted numeric representation. The prediction horizon is exactly 60 minutes after `snapshot_ts`, truncated by `H` as described in Section 9. No alternate barrier or horizon grid is authorized.

### T1 — Near-term continuation versus adverse reversal

Target ID: `C4_T1_CONT_PLUS1_VS_REV_MINUS075_H60_V1`.

At snapshot `t`, let `C_t` be the snapshot reference close.

- favorable barrier `U1 = C_t * 1.0100`;
- adverse barrier `D1 = C_t * 0.9925`;
- administrative target end `E_t = t + 60 minutes`.

The first barrier touched after `t` is the event:

- `continuation` if `U1` is first;
- `adverse_reversal` if `D1` is first;
- `no_event_60m` if neither is touched and the complete path through `E_t` is observable before or at `H`;
- null if ambiguous or right-censored.

This asymmetric geometry asks whether enough additional favorable movement occurs before a smaller adverse move. It directly addresses C2's observed giveback-versus-premature-exit tension and avoids conditioning on C3's fixed entry-relative milestones. The barriers are fixed once here; they are diagnostic transition definitions, not proposed stops or profits.

### T2 — Gain-giveback versus renewed peak, conditional on positive earned gain

Target ID: `C4_T2_GIVEBACK50_VS_NEWPEAK050_H60_V1`.

Let `E` be entry price; let `P_t` be the maximum valid post-entry high observable by `t`, including the completed bar ending at `t`; define peak gain `G_t = P_t/E - 1` and current gain `R_t = C_t/E - 1`.

T2 eligibility requires `G_t >= 0.0100` and `R_t > 0`. The thresholds prevent unstable fractions of trivial gains and ensure the trade currently retains positive unrealized gain. Let:

- giveback barrier `D2 = E * (1 + 0.50 * G_t) = (E + P_t) / 2`, surrendering at least half of the running-peak gain;
- renewed-peak barrier `U2 = P_t * 1.0050`, making a further 0.50% move above the already observed peak;
- administrative target end `E_t = t + 60 minutes`.

Eligibility additionally requires `C_t > D2`; if half or more of peak gain has already been surrendered at the snapshot, the row is reported as `already_beyond_giveback_state` and excluded rather than pretending a future event remains at risk.

`P_t`, `G_t`, `R_t`, `D2`, and `U2` are frozen for this snapshot from information available at `t`. A future high, including a future high above `P_t`, cannot redefine any of them. Thus `C_t == D2` is ineligible under the strict `C_t > D2` rule, and every snapshot already at or below `D2` is an `already_beyond_giveback_state` exclusion.

The first barrier touched after `t` is the event:

- `substantial_giveback` if `D2` is first;
- `renewed_peak` if `U2` is first;
- `no_event_60m` if neither is touched and the complete path is observable;
- null if ambiguous or right-censored.

T2 directly tests the C2 failure mode in which earned excursion was later surrendered. Unlike C3, it conditions on a causal evolving gain state rather than first arrival at a fixed milestone. T2 is not an economic trailing-stop specification.

T1 and T2 must not be pooled, averaged into one label, or treated as interchangeable replications. No third target is authorized in V1.

## 8. Event Ordering and Ambiguity

Forward events are resolved using valid ordered 1-minute bars beginning with `[t,t+1m)`. For every monitored interval with open `O_i`, high `H_i`, and low `L_i`, T1 and T2 use the same inclusive precedence:

1. If `O_i >= U` and `O_i > D`, the upper event resolves at the open, even if the lower barrier is touched later in the interval.
2. If `O_i <= D` and `O_i < U`, the lower event resolves at the open, even if the upper barrier is touched later in the interval.
3. If a point observation were simultaneously at or beyond both distinct ordered barriers (`D < U`), the row is `invalid_conflicting_barriers`; this is logically impossible for a valid scalar price and is not a modeled class.
4. Otherwise, if `H_i >= U` and `L_i <= D`, the result is `ambiguous_same_minute`, with null outcome because high/low chronology is unknown.
5. Otherwise `H_i >= U` resolves the upper event, `L_i <= D` resolves the lower event, and neither touch advances the clock.

Once resolved, later values cannot alter the event. No favorable or conservative ordering is imposed between non-open extrema. A gap/open beyond a barrier is a touch at the open only when chronology through the preceding interval is complete; a data gap immediately before it censors the row instead because C4 may not infer what occurred inside the gap.

### Endpoint semantics

For each snapshot, define the observation endpoint `Q_t = min(t + 60 minutes, H)`. Snapshot timestamps `t` and nominal endpoints `t + 60 minutes` are UTC minute-aligned. The accepted C2 common horizon `H` and its execution point retain their accepted timestamp and price semantics and are not recomputed; `H` need not be assumed minute-aligned unless accepted C2 provenance says it is.

- Every complete ordinary interval `[m,m+1m)` whose close boundary `m+1m <= Q_t` is fully observable and may resolve an event using its complete OHLC. In particular, when `Q_t` is minute-aligned, `[Q_t-1m,Q_t)` is a normal fully observable interval and its OHLC may resolve the event.
- An event resolved by such an interval is recorded at its first knowable interval boundary, including a boundary equal to `Q_t`; it is not excluded by a “strictly before endpoint” rule.
- When `Q_t = H` and accepted C2 provenance supplies a distinct exact H execution-point price not already represented by the last fully observable interval, that exact point price may additionally resolve an otherwise unresolved event using inclusive equality. Only that point price is used; no range or post-H value is consumed.
- When `Q_t = t + 60 minutes < H`, there is no additional synthetic endpoint price beyond the fully observable interval ending at `Q_t`.
- If `Q_t = H` and the exact H execution-point price required by accepted C2 semantics is unavailable, the unresolved row is right-censored with reason `unavailable_exact_H_point`. No H-minute OHLC range extending beyond information available at H may be used.
- A logically impossible endpoint point satisfying both distinct ordered barriers is `invalid_conflicting_barriers`, not a class.

## 9. Censoring

The nominal label-observation endpoint is `Q_t = min(E_t, H)`.

- If a target event is resolved by an allowed interval ending at or before `Q_t`, or by the permitted exact H point, retain it.
- If `H >= E_t` and neither barrier is touched using every complete ordinary interval ending at or before `E_t`, assign `no_event_60m`; there is no extra synthetic `E_t` point.
- If `H < E_t` and no event is observed by the exact H execution point, mark `right_censored_at_common_horizon`; do not call it no-event.
- If `H == E_t`, additionally use the accepted exact H execution point when Section 8 requires it; if neither barrier resolves, assign `no_event_60m`.
- A missing/invalid interval, unavailable boundary point, dataset end, or broken chronology before resolution produces a null outcome and explicit censor reason.
- Same-minute dual touch is ambiguity, not censoring and not a class.

Primary modeling uses the three resolved classes only. Censored and ambiguous rows are never coerced into `no_event_60m`, favorable, or adverse classes. Counts and state distributions of excluded rows must be reported by target, symbol, month, and reason. Inverse-censoring weighting is not authorized in V1.

The primary Stage-A estimand is the conditional competing-event distribution among otherwise eligible snapshot states whose label is resolved under these observation and censoring rules. It is not an estimand for all open-trade states. Because later landmarks may be more likely to be censored by `H`, report censoring by target, reason, elapsed-time band, symbol, trade, entry cohort, snapshot week, snapshot month, and calendar quarter. For every target/split and every represented trade with `eligible_landmark_count > 0`, the per-trade eligible-landmark table must report `eligible_landmark_count`, `resolved_landmark_count`, `censored_landmark_count`, and `ambiguous_landmark_count`, together with the following explicitly denominated fractions:

- `resolved_fraction_of_eligible = resolved_landmark_count / eligible_landmark_count`;
- `censored_fraction_of_eligible = censored_landmark_count / eligible_landmark_count`; and
- `ambiguous_fraction_of_eligible = ambiguous_landmark_count / eligible_landmark_count`.

A trade with `eligible_landmark_count == 0` is not part of this per-trade eligible-landmark table. For each fraction, report aggregate `min`, `median`, `mean`, `p90`, and `max` by target, temporal split, and symbol. The denominator must never be implicit. Material differential censoring across these dimensions, assessed under criteria frozen at the independent data-adequacy review in Section 17, may force `INSUFFICIENT EVIDENCE` even when model metrics appear favorable.

## 10. Gap Handling

Every source minute required from entry through the snapshot for a path feature, and from snapshot through event or censoring for an outcome, must be valid, unique, UTC-grid aligned, and contiguous. No forward fill, nearest observation, interpolation, or skip across a gap is allowed.

A pre-snapshot gap makes cumulative path features unavailable and therefore the primary complete-case row feature-ineligible. A post-snapshot gap before resolution censors that target row. A gap after a resolved event does not undo it. Subject-local gaps do not silently borrow another symbol's values; context gaps make only the dependent context specification ineligible under its declared complete-case policy.

## 11. Causal Information Availability

All timestamps are UTC integer milliseconds. A source interval `[m,m+1m)` becomes available at `m+1m`; a 5-minute interval `[T,T+5m)` at `T+5m`; and an hour at its end boundary. Every feature records or inherits an availability timestamp no later than `snapshot_ts`.

Permitted running MFE/MAE are causal extrema only through `t`. Final common-horizon MFE/MAE, P0 outcome, target event, censoring, future path, C2 policy result, and C3 outcome are prohibited features. Future mutation or appending of data at or after `t` must not alter the row's features.

Maintain structurally separate ordered sets: `provenance_columns`, `feature_columns`, and `outcome_columns`. Model APIs receive only the frozen feature matrix and target vector. Grouping identifiers are passed separately and cannot enter a model unless explicitly listed as a control.

## 12. Feature Architecture

Version: `C4_CAUSAL_SEQUENTIAL_STATE_V1`. Raw values are stored. The asset-local primary specification contains the following compact families; exact formulas are fixed before scoring.

### A. Geometry and current state

- `elapsed_5m_bars` and `time_since_entry_minutes`.
- `current_unrealized_return = C_t/E - 1`.
- `running_mfe = P_t/E - 1`.
- `drawdown_from_running_peak = C_t/P_t - 1`.
- `peak_gain_retained_fraction = (C_t/E - 1)/(P_t/E - 1)` when peak gain is positive, otherwise null.
- target-specific upper and lower barrier distances.

These are current-state or target-geometry quantities, not genuine historical-path evidence. Several are algebraically related. Exact duplicate columns are excluded from fitted matrices. Where nonlinearly equivalent transforms are deliberately retained in `G1`, they exist to let the strongest geometry baseline absorb convenient parameterizations of target proximity; their predictive contribution cannot be called path-history signal. `running_mfe` is stored for audit but omitted from `G1` whenever it is exactly recoverable from included entry/current/peak-geometry columns.

For T1, normalized barrier distances are constants because `U1/C_t - 1 = 0.0100` and `1 - D1/C_t = 0.0075`. They may be stored only as provenance assertions and are prohibited from every fitted model matrix.

### B. Genuine causal path history

- `running_mae = L_t/E - 1`, where `L_t` is the minimum eligible post-entry low observable by `t`.
- `path_efficiency = (C_t/E - 1) / sum(abs(r_i))`, using consecutive completed post-entry 5-minute close returns through `t`; null for zero denominator.
- `recent_return_5m`, `recent_return_15m`, and `recent_return_30m` from completed contiguous 5-minute closes.
- `momentum_acceleration = recent_return_15m - prior_nonoverlapping_return_15m`.
- positive, negative, and zero 5-minute bar counts over the last six completed post-entry bars.

### C. Asset-local causal market history

- rolling local returns over 5, 15, 30, and 60 minutes ending at `t`.
- realized volatility of the last twelve 5-minute returns (`ddof=1`).
- volatility expansion ratio: latest six-return sample volatility divided by the preceding six; null for zero denominator.
- latest completed 5-minute range ratio relative to the median of the preceding twelve.
- latest completed 5-minute quote-volume and trade-count ratios to their preceding-twelve medians; null for zero denominators.
- distance of latest completed hourly close from causal H1 SMA24 and one-step H1 SMA24 slope.

Every aligned 5-minute post-entry path bar must lie wholly after entry. Local rolling windows require all constituent source minutes. No polynomial expansion, learned interactions, outcome-driven binning, winsorization, or feature selection is authorized.

## 13. Nested Control and Path Models

The required nested models are:

### G0 — basic controls

- training-fitted symbol indicators;
- `time_since_entry_minutes` transformed as `log1p(minutes/5)`;
- `current_unrealized_return`;
- realized volatility of the last twelve completed 5-minute returns;
- fixed calendar controls `sin(2*pi*month/12)` and `cos(2*pi*month/12)`; and
- the causal BTC 60-minute nuisance-regime control defined in Section 14.

### G1 — strong geometry/current-state control

`G1` contains `G0` plus the pre-registered non-duplicate geometry/current-state representation:

- `drawdown_from_running_peak`;
- `peak_gain_retained_fraction`; and
- for T2 only, normalized frozen distances `(U2-C_t)/C_t` and `(C_t-D2)/C_t`.

T1 constant barrier distances are provenance assertions only. `running_mfe` and running peak relative to entry are audited geometry fields but are not added as exact/reconstructible duplicates. The retained transforms intentionally make `G1` a strong nonlinear geometry baseline. `G1` versus `G0` may establish that richer current-state geometry matters, but it is not historical-path evidence.

### P1 — historical path model

`P1` contains `G1` plus only the genuine causal path-history and the remaining non-duplicate asset-local market-history features in Sections 12.B and 12.C. The realized-volatility column already present in `G0` is not duplicated. Only stable paired improvement of `P1` over `G1` may support a claim that historical path carries incremental information.

## 14. Cross-Asset Policy

The primary C4 specification is asset-local except for one BTC 60-minute return used solely as a coarse nuisance market-regime control in `G0`, `G1`, and `P1`. At snapshot `t`, let `B_t` be BTCUSDT's close of the completed one-minute interval `[t-1m,t)` and `B_{t-60m}` the close of `[t-61m,t-60m)`. The control is the simple return `B_t/B_{t-60m} - 1`, requiring every intervening completed source minute to be valid and contiguous. Its availability timestamp is `t`; it is aligned to the identical UTC snapshot timestamp for every subject.

The same universal value is used when BTCUSDT is itself the subject. It is never replaced with zero or a subject-specific sentinel. If the causal BTC window is unavailable, the dependent row is ineligible under the frozen complete-case policy.

C3 did not establish stable incremental value from a larger cross-asset family. No ETH leader, breadth, correlation, dominance, market-index, or other cross-asset feature or optional context model is authorized in V1. Such a model requires a separately reviewed contract version and cannot rescue a failed `P1`-versus-`G1` result.

## 15. Repeated-Measures / Dependence Treatment

- All rows from one `trade_id`, across both targets and all timestamps, belong to the same chronological partition.
- Split assignment is by entry timestamp as specified in Section 16; later snapshots from a trade can never enter another split.
- Metrics are paired on identical eligible snapshot rows when comparing models.
- Primary uncertainty uses the fully specified trade-entry-cohort moving-block bootstrap below. It clusters whole trades by entry-cohort time and is not claimed to be a literal resample of snapshot calendar time.
- Report trade-level mean loss first and snapshot-weighted loss second. Snapshot-weighted metrics are descriptive and cannot manufacture precision from long-lived trades.
- Report per-symbol, month, quarter, holding-age band, and market-episode diagnostics. Five symbols are not five independent replications.
- Define market episodes mechanically as UTC calendar months for primary concentration reporting; an outcome-derived episode segmentation is prohibited.

No row-level IID standard error, random snapshot split, or naive snapshot bootstrap is allowed. Effective counts must include trades, entry weeks, snapshot weeks, symbols, and events, not rows alone.

### Equal-trade weighting

For every target and training or evaluation partition, let trade `i` have `N_i` eligible modeling snapshots. Every snapshot `j` receives raw weight `w_ij = 1/N_i`. Thus every represented trade has total raw weight one. If an API requires normalized weights, all weights may be multiplied by one partition-wide constant only; relative trade weights must remain equal.

This weighting is mandatory for B0 class incidence, multinomial fitting, model-selection loss, validation loss, proper-score comparisons, calibration intercept/slope and incidence, reliability-bin construction and summaries, primary symbol/time aggregates, and bootstrap replicate metrics. Bins are formed using weighted training-prediction quantiles. Within each bin and primary subgroup, predicted and observed incidence use these weights. Every report includes both snapshot counts and unique-trade counts. Secondary explicitly labeled snapshot-weighted summaries may use unit row weights.

Preprocessing uses the same `w_ij`: weighted training-partition medians and weighted 25th/75th percentiles define centering and IQR scaling. Weighted quantiles use the deterministic left-continuous inverse weighted empirical CDF: sort by `(value,row_id)`, normalize positive weights to sum one, and select the first value whose cumulative weight is at least the requested probability. Validation data never influence these statistics.

### Primary four-entry-week moving-block bootstrap

For each target, split, paired model comparison, and evaluation partition:

1. Assign every trade to its UTC entry week `[Monday 00:00, next Monday 00:00)` and attach its complete analytic snapshot record to that week.
2. Let the ordered span from the earliest through latest represented entry week contain `W` consecutive calendar-week positions, including empty positions.
3. Construct every overlapping non-circular block of four consecutive positions whose start is within that span. A block contains every complete trade whose entry week is one of its four positions; empty blocks are retained as possible blocks only if all four positions are empty, then rejected and redrawn if sampled because they contribute no trade.
4. Draw `K = ceil(W/4)` blocks independently with replacement. Preserve every selected trade and all its snapshots; never split a trade.
5. Overlapping sampled blocks or repeated draws may select a trade multiple times. Preserve that integer multiplicity as distinct bootstrap copies; do not deduplicate.
6. Compute each selected trade-copy's mean paired loss difference over its snapshots, then average those trade-copy means. Equivalently, apply trade multiplicity after within-trade averaging. This preserves equal total weight per selected trade-copy.
7. Do not concatenate or reinterpret sampled block dates. The replicate is a clustered empirical resample and may contain approximately, not exactly, the original number of weeks or trades.

Beginning and end handling is non-circular: only block starts whose four positions lie within the observed `W`-week span are used. If `W < 4`, or if fewer than two nonempty four-week blocks exist, primary block uncertainty is unavailable and the target/split fails the adequacy gate. Every primary paired bootstrap comparison must use 2,000 replicates drawn with the NumPy-compatible `PCG64` generator initialized with seed `20240923`. This seed is frozen and must not be selected at implementation time; only a future separately reviewed contract version may change it. The primary 95% interval is the equal-tailed interval from the `2.5`th percentile to the `97.5`th percentile, computed with the exact NumPy-compatible linear interpolation rule `quantile(..., method="linear")`, corresponding to Hyndman-Fan Type 7. Specifically, for a sorted replicate vector `x` of length `n` and probability `p`, let `h = (n - 1)p`, `j = floor(h)`, and `g = h - j`; the quantile is `x[j] + g * (x[j + 1] - x[j])`, using zero-based indexing, with the natural endpoint convention when `j = n - 1`. Independent implementations must reproduce identical interval endpoints from the same replicate vector. A calendar-month whole-trade cluster bootstrap is a predeclared sensitivity only and may not replace the primary method based on results.

Descriptive reporting by target and split must include snapshot week, entry week, month, symbol, and market-episode concentration; snapshots per trade; the number of adjacent within-trade snapshot pairs with overlapping forward windows; and the fraction of within-trade snapshot pairs that share at least one forward minute. Snapshot count is never interpreted as independent sample size.

## 16. Chronological Split

All trade snapshots inherit the partition of `entry_execution_ts`, preventing one trade from crossing folds.

### 2024 development folds

- Fold A: train trades entered `[2024-01-01, 2024-07-01)`; validate trades entered `[2024-07-01, 2024-10-01)`.
- Fold B: train trades entered `[2024-01-01, 2024-10-01)`; validate trades entered `[2024-10-01, 2025-01-01)`.

A row is usable in a fold only if its snapshot and label resolution/censor determination occur strictly before that fold's end. Training rows must resolve strictly before the validation start. Boundary-crossing outcomes are purged and counted without consuming later-period values for model selection.

Model, preprocessing, regularization, and any interpretation choice use 2024 only. After freeze, refit on eligible 2024 trades whose outcomes are known strictly before `2025-01-01T00:00:00Z`.

### 2025 development-era out-of-time validation

Score trades entered in `[2025-01-01, 2026-01-01)`. Only snapshots and outcomes fully resolved from accepted pre-2026 values are eligible. A 2025 snapshot whose 60-minute window or common horizon reaches the sealed boundary is `unresolved_at_2025_boundary` without reading any on/after-boundary value.

The 2025 result is a locked, out-of-time internal validation for C4, not a pristine holdout, because 2025 was inspected in C3. Any change prompted by it creates a new contract/version and cannot reuse 2025 as unbiased evaluation.

Before any C4 2025 prediction is generated or scored, freeze and hash the snapshot cadence; targets and eligibility; endpoint and open-price precedence; censoring and complete-case policy; feature schema; `G0/G1/P1` column sets; cross-asset policy; trade and preprocessing weights; model family, regularization, and hyperparameters; calibration method; bootstrap construction; metrics; data-adequacy decision and criteria; interpretation rules; accepted source hashes; fitted preprocessing hashes; and fitted model hashes. No 2025 result may trigger retuning, reinterpretation of thresholds, or a replacement specification.

## 17. Model Family

### Pre-training data-adequacy gate

After causal landmarks and labels are constructed but before any model is trained, produce a deterministic data-adequacy report separately for T1 and T2 and for every development training/validation split. It must report:

- snapshots and unique trades;
- resolved event counts and unique trades by class;
- ambiguous, right-censored, and gap-censored rows;
- entry weeks, snapshot weeks, months, quarters, and symbols represented;
- minimum, median, and maximum snapshots per trade;
- for every target/split and every represented trade with at least one eligible landmark, `eligible_landmark_count`, `resolved_landmark_count`, `censored_landmark_count`, and `ambiguous_landmark_count`; the explicitly denominated resolved, censored, and ambiguous fractions required by Section 9; and each fraction's `min`, `median`, `mean`, `p90`, and `max` by target, temporal split, and symbol; and
- adjacent and all-pair within-trade forward-window overlap diagnostics required by Section 15.

Exact universal numeric cutoffs are not asserted without knowledge of the accepted fixture's trade frequency and event prevalence. Therefore C4 V1 requires a separate, predictive-performance-blind `DATA-ADEQUACY REVIEW` after the count report and before predictive scoring. That review may inspect only aggregate counts, coverage, overlap, censoring, and class incidence—not predictors, fitted models, predictions, coefficients, or model performance—and must pre-register conservative minimum resolved trades per class, total unique trades, represented entry weeks and months, minimum unique-trade support per eventual calibration bin, block-bootstrap feasibility, and maximum tolerable differential censoring. The count-based gate is decided before model fitting; the already-frozen calibration-bin and differential-censoring criteria are checked when those diagnostics become available and may only downgrade the result. The reviewed criteria and decision are hashed before any model runs and cannot be changed after predictive results are observed.

Failure of the reviewed criteria ends modeling for that target/split as `INSUFFICIENT EVENT COUNT` or `INSUFFICIENT EVIDENCE`, as applicable. Inadequate counts do not authorize changing a target, barrier, horizon, cadence, eligibility rule, or class. Any such redesign requires a separately reviewed contract version.

### Frozen model family

Each target is modeled separately as a three-class outcome using multinomial probabilities.

- `B0`: equal-trade-weighted training-partition class-incidence probabilities, constant for all validation rows.
- `G0`: basic-control multinomial logistic regression from Section 13.
- `G1`: `G0` plus the frozen geometry/current-state representation from Section 13.
- `P1`: `G1` plus only the frozen genuine path-history and asset-local market-history representation from Section 12.

Continuous variables are centered and scaled using the equal-trade-weighted training median and IQR rule in Section 15. A zero-IQR continuous column is excluded consistently from that fit and its validation matrix and recorded; unknown symbol categories are rejected because the fixture is frozen. No target encoding or post-hoc imputation is allowed; V1 uses identical complete-case rows for each paired nested comparison.

`G0` uses inverse regularization `C=1`. `G1` and `P1` use only `C in {0.1, 1.0, 10.0}`, chosen per target by mean equal-trade-weighted chronological-fold multinomial log loss, then Brier score, then smaller C. All multinomial fits use `w_ij` from Section 15. Retain every attempt. No nonlinear model is authorized; it requires a later reviewed amendment based only on permitted development evidence.

### Framework choice

Primary formulation is **fixed-horizon sequential landmark competing-event classification**, not conventional discrete-time survival.

A discrete-time competing-risk survival model is attractive because snapshots resemble person-period rows and can model cause-specific hazards. It is not primary here because T1 and T2 barriers are reset from evolving state at each landmark, rows have overlapping 60-minute futures, T2 eligibility can enter and leave, and events do not terminate the underlying E1 trade. Treating these as one irreversible survival clock would give an unclear risk set; implementing both frameworks would create an ex-post model contest.

The chosen landmark formulation estimates, at each causal state, the mutually exclusive 60-minute probabilities of favorable event, adverse event, and no event. Its overlap is handled explicitly through whole-trade entry-cohort clustering and equal-trade weighting. A true recurrent-event or multi-state survival model may be proposed only by amendment, not run as a sensitivity in V1.

## 18. Metrics

Primary metrics for each target are:

- equal-trade-weighted multinomial log loss;
- equal-trade-weighted multiclass Brier score;
- paired `P1-G1` loss differences with dependence-aware intervals, with `G1-G0` reported separately as geometry-only evidence;
- classwise calibration intercept/slope and observed-versus-predicted incidence;
- reliability tables using five bins defined from training predictions for each event class.

Secondary metrics are classwise one-versus-rest ROC AUC and PR AUC with class incidence, macro averages, ranked-probability score, top-class confusion counts, and snapshot-weighted versions of proper scores. Accuracy is descriptive only. Report metrics separately by fold/year, target, symbol, quarter, holding-age band, and where counts permit calendar month.

No metric may pool T1 with T2. Report paired coverage and enforce identical complete-case rows within every `G0/G1/P1` comparison so apparent improvement cannot be caused by evaluating different rows. Primary overall, symbol, time, calibration, and reliability aggregates use equal-trade weights; explicitly labeled row-weighted versions are secondary.

## 19. Calibration

Probabilities are evaluated directly from multinomial logistic models. No post-hoc calibrator is authorized in V1. Reliability bins are derived from the applicable training predictions and applied unchanged to validation. Duplicate cut points reduce bin count and are reported.

For each class, report equal-trade-weighted expected/observed incidence, calibration intercept and slope where estimable, maximum absolute bin gap, and snapshot/trade/calendar coverage per bin. Training reliability cut points use the weighted-quantile rule in Section 15 and are applied unchanged to validation. Calibration failure cannot be offset by AUC. Sparse class/bin estimates must be labeled unstable rather than pooled opportunistically.

## 20. Advancement Criteria

Each target receives `SUPPORTS SEQUENTIAL PATH-STATE SIGNAL`, `COUNTS AGAINST`, `MIXED`, `INSUFFICIENT EVIDENCE`, or `INSUFFICIENT EVENT COUNT`.

Support requires the evidence panel, taken together, to show:

- P1 improves equal-trade-weighted log loss and Brier score over the strongest G1 geometry/state control in both 2024 validation folds and does not reverse in locked 2025 validation;
- improvement is meaningful under paired four-week block intervals and is not explained by changed complete-case rows;
- class probabilities are reasonably calibrated with ordered incidence across risk bins;
- effects are not dominated by one symbol, month, market episode, holding-age band, or small number of trades;
- challenge tests do not reduce the result to current return, elapsed time, geometry/current state, volatility, symbol, BTC regime, or duplicated snapshots;
- conclusions are stable across the predeclared regularization values; and
- provenance, timing, leakage, censoring, and reproducibility checks pass.

Failure to improve proper scores, poor calibration, time reversal, concentration, equivalence to `G1`, or disappearance after equal-trade weighting counts against the historical-path hypothesis. Genuine but inconsistent evidence is mixed. Failure of pre-registered event-count requirements is `INSUFFICIENT EVENT COUNT`; materially inadequate non-count coverage, calibration support, censoring comparability, or engineering integrity is `INSUFFICIENT EVIDENCE`. `G1` improving over `G0` alone is geometry/current-state evidence and is never sufficient evidence for historical path information.

T1 success cannot rescue T2 failure or vice versa. Neither result authorizes Stage B.

## 21. Stage A / Stage B Separation

### Stage A — state-transition predictability

Only Stage A may be authorized under a later execution approval for this contract. It creates causal landmarks, labels, probability models, calibration evidence, uncertainty, and scientific interpretations.

### Stage B — economic exit decisions

Stage B is not authorized by this contract, even if Stage A succeeds. A separate reviewed contract must define and freeze any action mapping, threshold, execution delay, stop distance, costs, turnover, capital/re-entry effects, and evaluation period without reusing the same outcomes for choice and economic validation.

C4 V1 defines no exit threshold, hold/sell rule, trailing stop, dynamic stop, position sizing, P&L, or portfolio simulation. Barrier definitions are scientific labels only.

## 22. 2026 Sealing

During drafting, implementation, testing, and review under this contract:

- do not enumerate a 2026 directory or file;
- do not list, open, read, hash, count, inspect schema, validate coverage, or otherwise touch 2026 market data;
- do not construct a 2026 snapshot, feature, label, prediction, score, metric, or artifact;
- do not use 2026 for debugging, selection, calibration, interpretation, or sample-size planning;
- reject any timestamp `>= 2026-01-01T00:00:00Z` before associated market values are consumed; and
- discover inputs only through explicit accepted 2024–2025 path/hash allowlists, never broad globs.

Boundary tests use wholly synthetic fixtures and need not contain real 2026 values. The loader must inspect path metadata and requested timestamp bounds before opening a file, then enforce row timestamps before decoding market-value fields. Any eventual 2026 confirmation requires explicit later authorization after code, schemas, models, preprocessing, metrics, interpretations, and software revision are frozen.

## 23. Dataset Schema

Produce deterministic separate T1 and T2 landmark/outcome tables plus feature-only matrices.

### Provenance

```text
dataset_version, feature_schema_version, target_id, row_id
trade_id, symbol, entry_fixture_id, entry_execution_ts, entry_price
snapshot_ts, snapshot_interval_start_ts, snapshot_reference_price
common_horizon_end_ts, nominal_target_end_ts, observable_target_end_ts
source_resolution, snapshot_cadence, feature_cutoff_ts
feature_eligible, feature_ineligible_reason
split_id, split_eligibility, split_exclusion_reason
```

### Features

Exactly the ordered `G0`, `G1`, and `P1` columns defined in Sections 12–14, plus auditable family availability timestamps and immutable column-family membership. No broader context extension matrix is authorized in V1.

### Outcomes

```text
event_class, event_resolution_ts, event_resolution_price, event_timing
upper_barrier_price, lower_barrier_price
resolved, censored, censor_reason, ambiguous, ambiguity_reason
minutes_to_event, no_event_60m
```

T2 additionally stores causal eligibility fields `peak_gain_at_snapshot`, `current_gain_at_snapshot`, and `already_beyond_giveback_state` as provenance; model use is allowed only through the explicitly frozen feature/control columns. Null outcomes never become classes.

## 24. Required Tests

Future implementation must include independent synthetic tests for:

- exact completed 5-minute snapshot cadence, entry exclusion, and `t < H`;
- exclusion of a 5-minute bar partly before entry;
- exact snapshot close and feature cutoff availability;
- first future interval beginning at `t`, with no same-bar leakage;
- exact T1 and T2 barrier arithmetic and inclusive equality;
- T2 eligibility at `G_t=1%`, `R_t>0`, and `C_t>D2`, including boundary exclusions;
- upper-only, lower-only, neither, gap-open, and same-minute dual-touch outcomes;
- first-event permanence and exact 60-minute boundary handling;
- `H` before, equal to, and after the target end, including exact-point-only H resolution;
- right censoring, ambiguity, dataset end, and gap reasons without class coercion;
- gap rejection before snapshot and censoring after snapshot;
- causal running MFE/MAE, retained fraction, path efficiency, slopes, acceleration, volatility, range, activity, SMA, and counts against hand calculations;
- all rolling windows ending at `t`, exact cross-symbol alignment, and no forward fill;
- mutation/appending after `t` not changing features;
- outcome/provenance mutations not changing the feature matrix;
- structural rejection of outcome columns by model pipelines;
- every trade and all its snapshots remaining in one temporal partition;
- strict fold-boundary outcome purging without consuming later values;
- equal-trade aggregation differing correctly from snapshot weighting;
- exact `1/N_i` fitting weights and equal total raw weight per trade;
- equal-trade-weighted B0 incidence and multinomial training loss;
- weighted median/IQR preprocessing and deterministic weighted quantiles;
- whole-trade bootstrap attachment to entry week, overlapping-block multiplicity, and no trade splitting;
- equal-trade paired loss after bootstrap multiplicities are applied;
- exact persistence and use of the primary `PCG64` seed `20240923` for every primary paired bootstrap comparison;
- two runs from identical inputs producing an identical bootstrap replicate sequence, with identical sampled block indices, trade multiplicities per replicate, and paired loss-difference vectors;
- Type-7 / NumPy `method="linear"` `2.5`th- and `97.5`th-percentile endpoints matching independent numeric oracles, including the hand-computable sorted replicate vector `[0, 10, 20, 30, 40]`, whose endpoints are exactly `1` and `39`;
- changing only the RNG seed changing the bootstrap sequence in a synthetic test;
- the production/default bootstrap path refusing an unspecified seed;
- the bootstrap configuration hash including seed, generator, replication count, block length, block construction semantics, quantile method, and interval levels;
- endpoint ordinary-minute versus exact-H-point handling, including unavailable-H-point censoring;
- open-price upper precedence, open-price lower precedence, and ordinary both-hit ambiguity without open precedence;
- constant T1 barrier distances absent from every fitted matrix;
- T2 snapshot barriers unchanged by future peaks;
- exact `G0/G1/P1` feature-column separation;
- complete-case row identity held fixed for paired model comparisons;
- independently computed multinomial log loss, multiclass Brier, calibration, and B0;
- exact rejection at the sealed boundary before associated values are consumed;
- complete censoring diagnostics; all per-trade eligible, resolved, censored, and ambiguous landmark counts; the three explicitly denominated per-trade fractions; zero-eligible-trade exclusion; and the required per-target, temporal-split, and symbol fraction summaries;
- snapshot count never entering an IID variance or effective-sample-size calculation;
- complete 2025 specification/model hash freeze before scoring;
- input discovery restricted to explicit 2024–2025 allowlists;
- deterministic row order, semantic hashes, fixed seeds, and byte-equivalent core reruns.

All synthetic market timestamps used in tests must be before the sealed boundary. No test may discover or read real 2026 data.

## 25. Reproducibility

Every future run records a machine-readable manifest containing:

- contract hash, accepted predecessor revision, and all verified input/artifact hashes;
- explicit 2024–2025 input allowlist and schema/validation versions;
- snapshot, target, barrier, horizon, feature, control, and column-role versions/hashes;
- chronological partitions and all exclusion, censoring, ambiguity, resolution, trade, and row counts;
- data-adequacy report, independently reviewed thresholds, decision, and hashes before predictive scoring;
- every attempted model/configuration, including failures;
- library versions, full model/preprocessing specifications, fitted artifact hashes, and seeds, including the frozen primary bootstrap seed `20240923`;
- bootstrap generator (`PCG64`), seed (`20240923`), replication count (`2,000`), block length (`4` entry-week positions), full block construction semantics, quantile method (Hyndman-Fan Type 7 / NumPy `method="linear"`), interval levels (`0.025`, `0.975`), sampled block indices, trade multiplicities, paired loss-difference replicate vectors, configuration hash covering all of those configuration fields, and output hashes;
- environment name, Python version/path, resolved dependencies, code revision, and dirty/untracked implementation hashes;
- core dataset, feature, prediction, metric, calibration, coefficient, and summary hashes;
- deviations and failure ledgers;
- affirmative confirmation that no 2026 path was enumerated and no 2026 value was accessed.

Identical accepted inputs, code, and configuration must use `PCG64` seed `20240923` for every primary paired bootstrap comparison and reproduce the identical sampled block-index sequence, trade multiplicities, paired loss-difference replicate vector, Type-7 interval endpoints, byte-equivalent core tables, and machine-readable results. Regenerated manifest timestamps may differ, but semantic/core hashes must match. The contract may not be silently edited after results; scientifically material changes require reviewed versioning.

## 26. Future Implementation Tasks

1. **T1 — sealed loader and provenance:** verify accepted predecessors, implement explicit allowlists and pre-value boundary rejection, and freeze column roles.
2. **T2 — snapshots and outcomes:** build deterministic 5-minute landmarks and separate T1/T2 outcomes with full ambiguity/censoring ledgers.
3. **T3 — causal features:** implement and hash the V1 feature matrices before predictive scoring.
4. **T4 — adequacy and chronological models:** complete the independently reviewed data-adequacy gate, then run only B0/G0/G1/P1 with the fixed folds/grid, equal-trade weights, and attempt ledger when authorized by that gate.
5. **T5 — dependence-aware evaluation:** produce proper-score, calibration, stability, falsification, exclusion, and block-uncertainty evidence.
6. **T6 — interpretation and stop:** issue target-specific Stage A conclusions and stop without any economic action mapping.

## 27. Delivery Requirements

A later authorized executor must deliver:

- initial/final repository and environment state and exact command log;
- contract, input, code, schema, dataset, model, and output hashes;
- row/trade/event/exclusion/censor/ambiguity counts by target, split, symbol, trade, entry cohort, snapshot week, month, quarter, and holding-age band;
- snapshots-per-trade and within-trade forward-window overlap diagnostics, with snapshot counts never represented as independent sample size;
- feature-only, provenance, and outcome separation evidence;
- fold and locked-2025 proper scores, calibration, paired block uncertainty, coefficients, and stability reports;
- equal-trade primary and snapshot-weighted secondary metrics;
- all challenge-test results and attempted configurations;
- deterministic rebuild evidence and relevant test results;
- target-specific and overall scientific interpretations;
- explicit confirmation that Stage B and 2026 confirmation were not run.

Do not commit raw/normalized market caches, large generated tables, model caches, or credentials. Engineering PASS is not scientific support, economic usefulness, or deployment readiness.

## 28. Explicit Falsification / Challenge Tests

C4 must actively try to explain apparent signal without rich path state:

1. **Current-return sufficiency:** compare `G0`, `G1`, and `P1`. If `P1` improvement vanishes against `G1`, do not credit path history.
2. **Barrier-distance mechanics:** within training-weighted quintiles of nonconstant normalized upper/lower distance, compare `G1/P1` event incidence and paired loss. T1 distances are constant provenance assertions and never model columns; for T2, distance variation must be absorbed by `G1` rather than masquerade as historical path.
3. **Elapsed-time sufficiency:** report performance within fixed holding-age bands `0–6h`, `6–24h`, `24–72h`, and `>72h` and compare the predeclared elapsed-time-only diagnostic with `G0/G1/P1`.
4. **Geometry sufficiency:** compare `G1` with `G0` and `P1`. Peak, drawdown, retention, and barrier geometry may improve `G1` but cannot by themselves support historical-path evidence.
5. **Volatility sufficiency:** stratify by training-weighted volatility quintiles and require `P1` improvement over `G1` within more than one regime.
6. **Symbol identity:** report leave-one-symbol-out refits as a challenge diagnostic and per-symbol proper-score differences. A single-symbol result cannot support the shared-state claim.
7. **Broad crypto regime:** compare `P1` with the BTC-regime-controlled `G1` by quarter/month; improvement concentrated in one broad regime is not stable evidence.
8. **Duplicated snapshots:** repeat headline comparisons with exactly one deterministic snapshot per trade-day (the first eligible UTC snapshot) and with equal-trade loss. Disappearance under either challenge counts against added state information.
9. **Market-episode concentration:** remove each calendar month in turn from evaluation summaries without refitting and report whether sign/conclusion changes.
10. **Feature-family ablation:** `P1` versus `G1` is the primary nested historical-path comparison; secondary one-family-at-a-time removals from `P1` are descriptive and may not select a new model.
11. **Label overlap:** report how many adjacent snapshots share part of a forward 60-minute window and how much headline uncertainty widens under the declared block design. Overlap is not independent evidence.
12. **Censoring/eligibility selection:** compare state distributions for resolved, censored, ambiguous, already-beyond-giveback, and feature-ineligible rows. Material differential selection may force `INSUFFICIENT EVIDENCE`.
13. **Temporal falsification:** a 2024 pattern that reverses or loses calibration in locked 2025 counts against the hypothesis and cannot trigger retuning.
14. **Cross-asset restraint:** no broader cross-asset model is run. The universal BTC return remains a nuisance control, not evidence of incremental cross-asset value.

These are falsification diagnostics, not a menu for selecting the most favorable subset. All results, including failures, are retained.

## Unresolved Questions Reserved for Later Review

- Whether resolved event counts and calendar coverage will be sufficient for three-class calibration; this must be answered by a future authorized count, not by changing targets after inspection.
- Whether C4 Stage A evidence, if any, merits a separately contracted Stage B.
- Whether a genuine recurrent-event or multi-state survival formulation deserves a new pre-registered experiment.
- Whether nonlinear models, another cadence, alternate barriers/horizons, additional symbols, or another entry fixture deserve separate contracts.
- Whether and when sealed 2026 confirmation may be authorized.

## Executor Note

The purpose of C4 is to test whether causal path history adds stable probability information beyond simple state, geometry, time, symbol, volatility, and regime controls. Negative, unstable, uncalibrated, or insufficient results are valid completed outcomes. Stop after Stage A and await separate review.
