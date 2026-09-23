# C3 — Milestone-State Continuation Experiment

Status: research design contract for review. Creating this contract does not authorize implementation or execution.

Target repository: `/media/ata/Data/personal/binance-v2`

Future delivery destination: `contracts/C3_milestone_state_continuation_DELIVERY.md`

Future artifact root: `artifacts/c3_milestone_state_continuation/`

Accepted predecessor: C2 checkpoint `ab08b62` (`Complete C2 asymmetric exit experiment`).

## Background

C1 established checksum-verified Binance spot data, integer timestamp provenance, next-boundary availability for close-derived information, gap-breaking causal windows, and deterministic artifacts. C2 then froze 2,199 entries from `E1_H1_SMA24_CROSS_V1` and compared `P0_H1_SMA24_CROSSDOWN_V1`, `P1_BRACKET_TP2_SL1_V1`, `P2_M5_TRAIL1_AFTER_GAIN1_V1`, and `P3_M5_MOMENTUM_DETERIORATION_V1` on common P0-derived horizons.

C2 found that the tested deterministic fast exits reduced some held-path giveback but did not demonstrate improved common-horizon opportunity capture or robust net expectancy versus P0. The existing P1/P2/P3 policies were not advanced, and C2-B was not advanced. C3 does not reopen those decisions and does not reinterpret C2 as a model-selection exercise.

The accepted descriptive temporal checkpoint found the following first competing events after favorable milestones:

| Milestone | Continuation | Fallback | Censored | Ambiguous | Eligible |
|---|---:|---:|---:|---:|---:|
| First +1% touch | +2%: 432 | Entry: 385 | 34 | 1 | 852 |
| First +2% touch | +3%: 279 | +1%: 264 | 8 | 1 | 552 |

After excluding censored and ambiguous rows, the accepted descriptive resolved counts are 817 for M1 and 543 for M2. These counts motivate non-degenerate conditional probability questions; they do not establish predictability. The temporal findings were retrospective and outcome-conditioned. They may motivate causal feature families but may not themselves become inputs, rules, labels beyond the two predeclared targets, or evidence that a signal exists.

All of 2024–2025 has now served as discovery/development data for this hypothesis. The period beginning `2026-01-01T00:00:00Z` remains completely untouched and sealed.

## Objective

C3 asks a narrow conditional question:

> Given that a frozen E1 trade has first reached a favorable milestone, does market state causally observable at that milestone contain stable information about continuation before fallback?

C3 has two separate scientific targets:

1. **M1:** after the first +1% touch, distinguish +2% before entry from entry before +2%.
2. **M2:** after the first +2% touch, distinguish +3% before +1% from +1% before +3%.

M1 and M2 shall have separate datasets, schemas, baselines, fitted models, calibration, validation results, uncertainty, and interpretations. They may share implementation utilities and feature definitions where semantically identical. They must not be pooled into one target during the initial C3 milestone because their conditioning events, fallback barriers, sample sizes, and post-milestone processes differ. A later amendment would need to justify any pooled or multitask model before outcomes are inspected.

The experiment must be capable of concluding any of:

- `SUPPORTS CONTINUATION-STATE SIGNAL`
- `COUNTS AGAINST`
- `MIXED`
- `INSUFFICIENT EVIDENCE`

Engineering PASS is separate from scientific interpretation. C3 is not structured to require a successful model.

## Scope and Non-Scope

### In scope for the first C3 milestone

- Reuse the accepted five-symbol 2024–2025 C2 history, frozen entries, and immutable P0-derived horizon `H` after verifying accepted hashes.
- Construct deterministic M1 and M2 milestone-state tables.
- Freeze a compact causal feature schema before predictive evaluation.
- Compare unconditional, simple stratification, and interpretable logistic baselines using chronological development.
- Evaluate probability quality, calibration, stability, and dependence-aware uncertainty.
- Produce machine-readable provenance, dataset definitions, attempted-configuration logs, and a research interpretation.

### Out of scope

- Reading, validating, hashing, listing, computing, scoring, or otherwise inspecting 2026 market data or outcomes.
- C2-B, portfolio simulation, capital allocation, position sizing, or re-entry consequences.
- A new exit rule, probability-to-action mapping, trading threshold, economic backtest, live/paper trading, or deployment recommendation.
- Modification of E1, P0–P3, their thresholds, C2 costs, C2 cohorts, or accepted C2 artifacts.
- Historical exchange-universe reconstruction; the fixed five symbols remain research fixtures.
- Deep learning, broad AutoML, unrestricted feature generation, broad hyperparameter search, symbol-specific models or thresholds, and post-result feature additions.
- Claiming that feature importance or association is causal evidence.

## Governance and Repository Controls

- Read applicable `AGENTS.md`, `docs/DEVELOPMENT_WORKFLOW.md`, C1/C2 contracts and deliveries, C2 temporal governance, and current source/tests before implementation.
- Start implementation only after this contract is reviewed and explicit execution is authorized. Use the required `binance-v2-research` environment with Python 3.11.x.
- Hash this contract before and after execution. A scientifically material change requires a reviewed amendment and new dataset/model version; do not silently edit the contract to match results.
- Preserve accepted C1 timing, validation, gap, symbol-isolation, and deterministic-output semantics.
- Preserve the accepted C2 frozen-entry, common-horizon, paired-table, and temporal hashes before using any local input.
- Policy/model code must receive a feature-only matrix. Provenance and label/outcome tables remain structurally separate.
- No result from 2025 or any eventual confirmation period may cause an in-place feature, model, threshold, metric, or interpretation change. Such a change creates a new pre-registered version and invalidates the prior locked evaluation for selection purposes.

## Experimental Units and Fixed Universe

The source units remain the 2,199 accepted frozen E1 trades for `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, and `BNBUSDT`. A trade contributes to M1 only if it reaches M1 within its immutable C2 common horizon, and to M2 only if it reaches M2. The same trade may contribute one row to each separate dataset; it contributes at most one row per milestone because only the first valid touch qualifies.

These rows are not IID. Entries overlap, M1 and M2 rows may share a trade, the five symbols are correlated, and events cluster in market episodes. Trade count must never be presented as independent sample size.

No additional entry fixture, symbol, date, milestone, barrier, or horizon may be added after viewing predictive performance.

## Canonical Time and Information Availability

- All timestamps are UTC integer milliseconds. A 1-minute source row with open `m` represents `[m, m+60s)` and its OHLCV/trade-count contents become available at `m+60s`.
- A 5-minute bar `[T,T+5m)` becomes available at `T+5m`; a 1-hour bar becomes available at `T+1h`.
- A feature with availability timestamp `a` may enter a milestone row only when `a <= feature_cutoff_ts`.
- Missing, duplicate, invalid, partial, off-grid, or gap-crossing windows are unavailable. No forward fill is permitted.
- Cross-asset observations must have the same canonical availability boundary as the subject observation. Nearest-neighbor, last-known-value, or future alignment is prohibited.

Because 1-minute OHLC does not identify an intraminute threshold-crossing instant, C3 must not invent one. Each milestone records:

- `milestone_interval_start_ts = m`, the open timestamp of the first qualifying 1-minute interval;
- `milestone_available_ts = m + 60s`, when that interval's high is known historically;
- `milestone_ts = m`, retained as the source-resolution event timestamp with `milestone_timing = localized_to_1m_interval`;
- `feature_cutoff_ts = m`.

The complete touch-minute OHLCV/trade-count row is excluded from all primary features. Features must use only observations whose contents were available by `m`. This conservative snapshot represents the state already computed when a hypothetical standing milestone observer encounters the threshold and prevents post-touch portions of the same minute from leaking into predictors. The milestone fact and fixed threshold price are provenance/conditioning fields, not learned feature values. A secondary feature set using the completed touch minute is prohibited in the first milestone because it could contain the target or fallback after the unknown intraminute touch.

## Milestone and Label Semantics

All thresholds are raw simple-price levels relative to the accepted raw E1 entry price. Comparisons include equality and use no tolerance beyond the accepted numeric representation.

### Entry-minute exclusion

Monitoring begins strictly after the entry fill. The entry execution minute's high/low is excluded because its pre-fill ordering is unknown. The first eligible touch interval has `open_time_ms >= entry_execution_ms + 60,000`.

### M1

- Milestone ID: `M1_FIRST_PLUS_1PCT_V1`.
- Milestone price: `entry_price * 1.01`.
- Milestone interval: the first valid eligible post-entry 1-minute row whose high is at least the milestone price, or the exact H execution point when H price is at least the milestone price.
- Target upper barrier: `entry_price * 1.02`.
- Target fallback barrier: `entry_price`.
- `Y1 = 1` when the upper barrier is first resolved before the fallback barrier.
- `Y1 = 0` when the fallback barrier is first resolved before the upper barrier.

### M2

- Milestone ID: `M2_FIRST_PLUS_2PCT_V1`.
- Milestone price: `entry_price * 1.02`.
- Milestone interval: the first valid eligible post-entry 1-minute row whose high is at least the milestone price, or the exact H execution point when H price is at least the milestone price.
- Target upper barrier: `entry_price * 1.03`.
- Target fallback barrier: `entry_price * 1.01`.
- `Y2 = 1` when the upper barrier is first resolved before the fallback barrier.
- `Y2 = 0` when the fallback barrier is first resolved before the upper barrier.

M2 is explicitly conditional on the selected population of trades that already reached +2%. M1 and M2 therefore have different conditioned populations. Their AUC, loss, calibration, separation, or other performance metrics may not be compared as though they came from the same population, and a higher metric for M2 may not be described as evidence that prediction is easier or better at +2%. M1 and M2 remain separately fitted, evaluated, and interpreted.

### Touch-minute and competing-event ordering

For the milestone-touch minute:

- If its high also reaches the target upper barrier and its low does not reach the fallback barrier, continuation is resolved in that interval. Price continuity requires the milestone to be crossed before the higher barrier.
- If it reaches both the upper and fallback barriers, ordering is unknowable: mark `ambiguous_same_minute`, leave `label` null, and exclude it from primary supervised fitting/evaluation.
- A fallback touch without an upper touch in the milestone minute does not resolve fallback because the low may have occurred before the milestone. Competition then begins with the next minute.

For every later valid minute before H:

- Upper only resolves label 1.
- Fallback only resolves label 0.
- Both in the same minute are `ambiguous_same_minute`, with a null label.
- Neither advances the clock.
- Once resolved, later events cannot alter the label.

Only the exact H execution price, not an H-minute range, may resolve a milestone or competing event at H. If H price reaches both logically impossible distinct point barriers, reject the row as invalid rather than impose an ordering. If no event resolves by H, mark `right_censored_at_H`, leave the label null, and exclude the row from primary supervised fitting/evaluation.

A missing or invalid minute anywhere from entry through milestone or during the competing-event clock breaks chronology. Mark the affected milestone/event row censored with an explicit gap reason; never skip across the gap. Rows without a milestone before H do not enter that milestone dataset and are counted separately.

Primary supervised class counts must reproduce the accepted descriptive reference counts unless a documented implementation correction is reviewed:

- M1: 432 continuation, 385 fallback; 34 censored and 1 ambiguous reported separately.
- M2: 279 continuation, 264 fallback; 8 censored and 1 ambiguous reported separately.

No oversampling, synthetic minority generation, downsampling, or time-order-destroying balancing is permitted. Primary models are unweighted because the classes are already approximately balanced. A class-weighted sensitivity is allowed only if predeclared in the attempted-configuration ledger and must not replace the unweighted primary result.

## Critical Leakage Prohibitions

Milestone features must never use, directly or through preprocessing:

- final common-horizon MFE or MAE;
- any future MAE, drawdown, realized volatility, return, volume, trade count, or price extreme;
- P0's eventual exit, return, reason, or final outcome;
- a later P1/P2/P3 signal or exit;
- `rescued`, `damaged`, candidate-superiority, premature-truncation, foregone-gain, held/common green-red, or other retrospective C2 labels;
- the C3 label, resolution timestamp, censor reason, ambiguity flag, time-to-resolution, later milestone transition, or any proxy derived from them;
- any future-fitted scaling, imputation, bin, encoding, feature selection, or calibration parameter;
- the touch-minute OHLCV/trade-count contents in the primary feature matrix;
- any retrospective temporal diagnostic requiring post-milestone prices.

Temporal observations may justify including a predeclared causal family such as time-to-milestone, but observed outcome associations may not determine transformations, cut points, signs, interactions, or trading actions.

The implementation must maintain three explicit column sets:

1. `provenance_columns` — identifiers, timestamps, versions, availability and quality metadata;
2. `feature_columns` — only frozen causal predictors;
3. `outcome_columns` — label, resolution, censoring, ambiguity and future-event fields.

Model pipeline APIs must accept only `feature_columns` plus the separately passed target vector. Runtime assertions must reject any outcome/provenance column not explicitly allowed for grouping from the design matrix.

## Frozen First-Pass Feature Architecture

The initial feature schema shall be compact, interpretable, shared in definition across M1/M2, and versioned `C3_CAUSAL_MILESTONE_FEATURES_V1`. Raw feature values are stored; any standardization is fitted on training data only. No interaction expansion or polynomial library is allowed.

All trailing bars below must be complete, contiguous, and available at or before `feature_cutoff_ts`. Returns are simple close-to-close returns unless explicitly labeled otherwise. Counts and fractions use only the stated completed windows.

The named 5m/15m/30m/60m local and cross-asset returns are rolling minute-window returns, not returns from aligned 5-minute, 15-minute, 30-minute, or hourly aggregate bars. Let `m = feature_cutoff_ts` and let `C_s(t)` be the close of symbol `s`'s one-minute source interval `[t-60s,t)`, which becomes available at `t`. For `W in {5m,15m,30m,60m}`:

```text
return_s_W(m) = C_s(m) / C_s(m-W) - 1
```

Both endpoint observations and every one-minute source interval between them must exist, be valid, unique, contiguous on the UTC minute grid, and have availability at or before `m`; otherwise the entire return and any dependent feature are unavailable. Thus the last included source interval is `[m-60s,m)`, and the milestone-touch interval `[m,m+60s)` is never included. Because milestone cutoffs are on the one-minute grid, no 5-minute-boundary rounding is performed: for a cutoff such as `12:07`, the 5-minute return uses closes available at `12:07` and `12:02`. Cross-asset endpoints and every intervening source minute use those same exact UTC timestamps. No aligned-bar substitution, partial window, nearest observation, or forward fill is permitted.

In contrast, every feature explicitly described as using a "5-minute bar" or "5-minute return" uses non-overlapping UTC-aligned aggregates `[T,T+5m)` with `T mod 5m = 0`, available at `T+5m`; only bars with `T+5m <= m` qualify. A post-entry 5-minute bar additionally requires `T >= entry_execution_ts`, so its entire interval is at or after the execution boundary; an aligned bar with `T < entry_execution_ts < T+5m` is partially pre-entry and cannot count or contribute to a post-entry path feature. Any missing or invalid constituent minute makes the aggregate bar and every dependent window unavailable.

### A. Path-to-milestone

1. `time_from_entry_seconds`.
2. `pre_milestone_mae`: minimum low/entry return using eligible minutes strictly after entry and strictly before the touch minute.
3. `complete_5m_bars_since_entry`.
4. `path_efficiency_5m`: fixed milestone return (0.01 for M1, 0.02 for M2) divided by the sum of absolute close-to-close returns across complete post-entry 5-minute bars through the cutoff; null when the denominator is zero.
5. `positive_5m_fraction_last6` and `negative_5m_fraction_last6`.
6. `recent_drawdown_last6_5m`: latest available 5-minute close relative to the causal running maximum of the last six completed 5-minute highs.

### B. Local momentum

7. Subject returns over the last 5, 15, 30 and 60 completed minutes: `local_return_5m`, `local_return_15m`, `local_return_30m`, `local_return_60m`.
8. `local_momentum_acceleration`: the rolling recent return `C_subject(m)/C_subject(m-15m)-1` minus the immediately preceding non-overlapping return `C_subject(m-15m)/C_subject(m-30m)-1`. Both legs require the complete contiguous minute source from the anchor ending at `m-30m` through `[m-60s,m)` and are unavailable together if any constituent is missing or invalid.
9. `consecutive_positive_5m` and `consecutive_negative_5m`, capped at 6 only after the exact uncapped counts are recorded for audit.

### C. Volatility/range

10. `absolute_return_5m`.
11. `realized_volatility_last6_5m`: sample standard deviation (`ddof=1`) of the last six 5-minute returns.
12. `volatility_expansion_ratio`: volatility of the most recent six 5-minute returns divided by the preceding six; null when the prior value is zero.
13. `latest_5m_range_ratio`: latest completed 5-minute `(high-low)/close` divided by the median of that measure over the preceding 12 completed 5-minute bars; null when the median is zero.

### D. Trend/context

14. `distance_from_h1_sma24`: latest completed 1-hour close divided by its causal contiguous SMA24 minus one.
15. `h1_sma24_slope`: current causal SMA24 divided by the preceding available causal SMA24 minus one.
16. `distance_from_6h_high` and `distance_from_6h_low`, using the latest available close and completed bars only.
17. `trend_persistence_last12_5m`: fraction of positive returns in the last 12 completed 5-minute returns.

### E. Volume/activity

18. Latest completed 5-minute base-volume, quote-volume, and trade-count ratios to their respective medians over the preceding 12 completed 5-minute bars.
19. `quote_volume_acceleration`: mean quote volume in the latest three completed 5-minute bars divided by the preceding three; null when the prior mean is zero.

These activity fields advance only if the accepted C2 source schema and validation continue to support them without imputation. If a field is structurally unavailable, implementation must stop and request a contract amendment rather than silently substitute another feature.

### F. Cross-asset/leader context

20. `btc_minus_subject_return_5m`, `btc_minus_subject_return_15m`, and `btc_minus_subject_return_60m`: the aligned BTC rolling return minus the subject-local rolling return for the identical window.
21. `eth_minus_subject_return_5m`, `eth_minus_subject_return_15m`, and `eth_minus_subject_return_60m`: the aligned ETH rolling return minus the subject-local rolling return for the identical window.
22. `other_four_breadth_15m`: fraction of the four fixed-universe symbols other than the subject whose aligned 15-minute rolling return is positive.
23. `btc_eth_agreement_15m`: `1` when BTC and ETH 15-minute rolling-return signs agree, `0` otherwise, with zero as its own sign.

Cross-asset features use the same fixed five fixtures, not a reconstructed universe, and use the exact rolling-minute alignment defined above. The ordered family-F columns are identical for every subject symbol; values are computed by the same formulas rather than adding, removing, or renaming columns by subject. For a BTC subject, each BTC-minus-subject value is the defined constant zero and the ETH-relative values remain contextual; for an ETH subject the converse holds. Neither relative-return column equals the corresponding subject-local return column, and the raw BTC/ETH return is not also supplied to L2. The leave-subject-out breadth is a fixed column whose formula always uses the other four fixtures. This representation makes L2's added columns relative/context quantities rather than exact copies of L1 predictors, preventing duplicate columns from changing an L2-regularized fit merely through altered regularization geometry.

### Missingness and eligibility

The primary complete-case dataset requires every V1 feature to be available. A missing/gap-crossing subject or cross-asset window makes the row feature-ineligible, with a reason recorded before model fitting. No mean/zero/forward imputation is allowed in V1. Report feature-ineligible counts by milestone, symbol, month and reason, and compare their label/censor availability descriptively to expose selection effects. Do not alter the feature list to recover favorable sample size after viewing performance.

## Feature Freeze and Attempt Ledger

- Hash the ordered feature schema, exact formulas, column roles, and source availability rules before producing predictive metrics.
- Record every attempted feature/model configuration, including failures and abandoned runs, in an append-only machine-readable ledger.
- No feature may be added, removed, transformed, clipped, interacted, or discretized after the first locked 2025 score is inspected.
- Exploratory screening is confined to the 2024 development folds below. It may compare only the predeclared nested specifications and single-feature diagnostics in this contract.
- Bins for single-feature stratification are quintiles estimated from the applicable training fold only and then applied unchanged to its validation fold. Duplicate cut points reduce the number of bins and must be reported.
- Symbol-specific features, coefficients, thresholds or models are prohibited in V1. A shared model may include training-fitted symbol indicators as a control.

## Chronological Development and Evaluation Split

Random train/test splitting is prohibited as the primary design.

### 2024 model-selection folds

- Fold A: train `[2024-01-01, 2024-07-01)`, validate `[2024-07-01, 2024-10-01)`.
- Fold B: train `[2024-01-01, 2024-10-01)`, validate `[2024-10-01, 2025-01-01)`.

Rows are assigned to candidate split populations by `milestone_interval_start_ts`, not entry time or label-resolution time. A row may contribute to supervised fitting or metrics only when its non-null label is fully resolved strictly before the applicable boundary:

- Fold-A training rows must have `label_resolution_ts < 2024-07-01T00:00:00Z`.
- Fold-A validation rows have milestones in `[2024-07-01, 2024-10-01)` and must have `label_resolution_ts < 2024-10-01T00:00:00Z`. A Fold-A milestone resolving in Q4 or later is purged from Fold-A supervised validation and reported as `unresolved_at_validation_boundary`.
- Fold-B training rows must have `label_resolution_ts < 2024-10-01T00:00:00Z`.
- Fold-B validation rows have milestones in `[2024-10-01, 2025-01-01)` and must have `label_resolution_ts < 2025-01-01T00:00:00Z`. A row resolving on or after that boundary is purged from Fold-B supervised validation and reported as `unresolved_at_validation_boundary` without consuming that later outcome for model selection.

Training candidates without a resolution strictly before their cutoff are reported as `unresolved_at_training_boundary`. Censoring or ambiguity already known before the boundary remains reportable but does not become a supervised class. No 2025 outcome may enter 2024 feature selection, preprocessing, hyperparameter selection, calibration, model selection, or interpretation.

Model/preprocessing selection uses the two chronological 2024 folds only. Fold results are reported separately and aggregated by calendar duration, not by pretending rows are IID.

### Locked 2025 development evaluation

After separately freezing the complete M1 and M2 specifications, fit each selected pipeline only on eligible rows with milestones in 2024 whose labels resolved at `label_resolution_ts < 2025-01-01T00:00:00Z`. A 2024 milestone resolving in 2025 is excluded as `unresolved_at_training_boundary`; its 2025 outcome is not consumed before the locked evaluation is opened. Preprocessing and calibration fit on this boundary-clean 2024 set only.

Score milestone rows in `[2025-01-01, 2026-01-01)` only when their labels resolve at `label_resolution_ts < 2026-01-01T00:00:00Z`. Rows not resolved by that boundary are excluded from supervised 2025 metrics and reported as `unresolved_at_2025_evaluation_boundary`. The implementation must determine this from accepted pre-2026 data and stop at the boundary; it must not read an on/after-boundary event to decide exclusion. The 2025 evaluation is opened once and receives no retuning.

The 2025 period is not a pristine confirmation holdout: its aggregate temporal outcomes helped motivate C3. It is a locked internal development evaluation used to challenge stability. Results must be labeled accordingly. Any change prompted by 2025 produces a new future contract/version and may not reuse 2025 as unbiased evaluation.

### Sealed 2026 confirmation

No 2026 row participates in initial C3 development. An eventual 2026 confirmation requires a separately authorized checkpoint after dataset schema, feature code/hash, model family and hyperparameters, preprocessing, calibration, any probability/action threshold, metrics, interpretation rules, and software version are frozen.

## Baselines and Model Family

Every target is evaluated separately against the following predeclared sequence.

### B0 — Unconditional probability

Predict the training-fold continuation fraction for every validation row. This is the primary probabilistic baseline for paired log-loss and Brier comparisons.

### B1 — Constant-action diagnostics

Report always-continuation and always-fallback accuracy/confusion counts only as intuitive decision-equivalent diagnostics. They are not probabilistic baselines and cannot establish usefulness.

### B2 — Single-feature stratifications

Report training-defined quintile continuation rates for exactly five representatives:

- `time_from_entry_seconds`;
- `local_return_15m`;
- `realized_volatility_last6_5m`;
- `distance_from_h1_sma24`;
- `btc_minus_subject_return_15m`.

These are diagnostics, not five independent hypothesis tests and not sources for new cut points.

### L0 — Regime/control logistic model

Unweighted logistic regression using symbol indicators, `realized_volatility_last6_5m`, `distance_from_h1_sma24`, and the fixed transforms `sin(2*pi*month/12)` and `cos(2*pi*month/12)`. The calendar transforms are controls for coarse seasonality, remain defined when a validation month was absent from training, and are not a license to memorize individual months.

### L1 — Asset-local milestone-state logistic model

Unweighted L2-regularized logistic regression using the frozen A–E feature families plus symbol and the same fixed calendar controls.

### L2 — Asset-local plus cross-asset logistic model

The L1 inputs plus the frozen family F. L2 versus L1 is the predeclared test of incremental leader/context information.

Continuous features are median-centered and scaled by interquartile range using training data only; zero-IQR features remain centered but unscaled and are reported. Categorical encodings are fit on training only. No target encoding is allowed.

The only hyperparameter grid is inverse regularization strength `C in {0.1, 1.0, 10.0}` for L1/L2. L0 uses `C=1.0`. Select independently for M1 and M2 by mean chronological-fold log loss, using Brier score as the predeclared tie-breaker and then smaller `C` as the final tie-breaker. All six regularized L1/L2 configurations per target (three values for each of two specifications), plus fixed L0 and every baseline, must be retained; do not report only the selected specification.

No nonlinear predictive model is authorized in the first C3 milestone. A shallow tree/boosted model may be proposed only in a later amendment if interpretable models show a reproducible deficiency or nonlinear pattern on 2024 without using 2025 or 2026 to choose complexity. Deep learning and AutoML are prohibited.

## Calibration and Predictive Evaluation

Primary scientific outcomes are probability quality and stable conditional separation, not accuracy.

For every baseline/model, milestone, fold, 2025 evaluation, symbol, month and quarter, report where mathematically defined:

- sample, positive, negative, censored, ambiguous, feature-ineligible, `unresolved_at_training_boundary`, `unresolved_at_validation_boundary`, and `unresolved_at_2025_evaluation_boundary` counts;
- ROC AUC;
- PR AUC, alongside the continuation base rate;
- log loss;
- Brier score and Brier skill relative to B0;
- calibration intercept and slope;
- reliability table and plot using five probability bins whose boundaries are learned from training predictions only;
- observed continuation rates and lift over B0 by probability bin;
- confusion/accuracy only as secondary diagnostics at threshold 0.5, without calling 0.5 an economic action threshold.

Do not fit a separate post-hoc calibrator in V1. Logistic probabilities are evaluated directly. Calibration correction, if later justified, requires a pre-registered nested scheme and cannot be fit on locked evaluation outcomes.

Primary model comparisons use paired row-level differences in log loss and Brier score, summarized with calendar-month block bootstrap intervals. All symbols and simultaneous events in a sampled month remain together. Fix and record bootstrap seed, replication count, block definition, and quantile method before scoring. Also report quarterly dispersion and per-symbol metrics without treating five symbols as independent replications.

Duplicate/simultaneous milestone timestamps must be counted. Report maximum events per timestamp, event clusters by day/week, and effective calendar coverage. No naive per-row confidence interval or standard error is permitted.

## Challenge Tests and Falsification Controls

C3 must actively test explanations that do not require useful milestone-state signal.

1. **Barrier geometry:** near-50/50 labels may be a mechanical consequence of the fixed adjacent barriers. Balanced classes are not evidence of predictability. V1 conclusions are limited to the exact M1/M2 geometries; no general continuation claim and no alternate-barrier tuning is allowed. Report base rates by symbol, month, volatility quintile and time-to-resolution to show geometry/regime sensitivity.
2. **Time as volatility proxy:** compare the single-feature time diagnostic with volatility, L0, and L1. Report correlation and conditional performance of time-to-milestone after controlling for realized volatility and symbol. Do not interpret a time coefficient as independent state information unless it is stable in nested comparisons.
3. **Cross-asset incremental value:** compare L2 directly with L1 using paired loss differences and block uncertainty. Cross-asset features add useful information only if improvement is stable beyond asset-local state, not merely because BTC/ETH encode the same broad volatility regime.
4. **Pseudo-replication:** preserve calendar blocks, keep simultaneous/correlated symbols together, report cluster counts, and inspect whether performance is dominated by a few high-event months or market episodes.
5. **Barrier sensitivity:** do not change barriers in V1. Explicitly limit inference to +1→(+2 vs entry) and +2→(+3 vs +1). Any alternative distances are a new target requiring pre-registration, not a robustness knob selected from these results.
6. **Increment beyond symbol/regime:** L0 is the required control. L1 must improve on L0, not merely B0, with calibration and cross-time/symbol stability before path state is credited.
7. **Out-of-sample disappearance:** 2025 is a locked adversarial development evaluation. A 2024-only pattern that disappears or reverses in 2025 counts against the hypothesis and must not trigger retuning.
8. **M1/M2 inconsistency:** agreement across M1/M2 is supportive only where concepts and effect directions are comparable. A result in one target cannot be transferred to the other; disagreement must be reported rather than pooled away.
9. **Selection and censoring:** compare eligible, feature-ineligible, censored and ambiguous counts across symbols/time. Strongly differential exclusion may make the result insufficient even if metrics appear favorable.

## Explainability

For L0–L2, report standardized coefficients, signs, bootstrap or block-fold variability, and partial probability changes over robust training-data quantiles. Report whether effects are stable across folds, symbols and years and whether one feature family, symbol, or period dominates.

Feature attribution describes model association at the milestone snapshot. It is not causal evidence, a structural market mechanism, or permission to convert a coefficient into a trading rule. Unsupported sign stories are prohibited.

## Stage Separation and Economic Translation

### Stage A — Predictive validity (authorized by a future C3 execution)

The first C3 milestone stops after causal dataset construction and predictive evaluation. It produces probabilities and scientific evidence only.

### Stage B — Decision usefulness (not authorized here)

Only if Stage A supports a stable, calibrated signal may a later reviewed contract define mappings such as hold, tighten, or exit. That contract must:

- choose any probability threshold using development/validation data only;
- freeze the threshold and mapping before a new evaluation/confirmation period;
- retain continuous probabilities even if a binary decision is used;
- include costs, execution delay, ambiguity, censoring and common-horizon comparisons;
- prevent the same rows from selecting a threshold and estimating its economic value;
- avoid relabeling frozen-path results as portfolio results.

No probability threshold, action mapping, exit policy, cost simulation, or economic performance result is part of initial C3.

## Advancement and Interpretation

Do not invent a single arbitrary cutoff after seeing results. `SUPPORTS CONTINUATION-STATE SIGNAL` requires the evidence panel, taken together, to show:

- improvement over B0 and L0 in proper scoring rules, not merely accuracy;
- reasonable calibration and useful probability-bin separation;
- directionally consistent performance across chronological folds and the locked 2025 evaluation;
- no dependence on one symbol, month, quarter, or correlated event cluster;
- incremental path-state information beyond symbol and volatility regime;
- for cross-asset claims, stable L2 improvement over L1;
- persistence under the three predeclared regularization values without cherry-picking;
- sufficient probability separation to justify, but not execute, a later decision-usefulness experiment;
- no leakage, invalid timing, unexplained exclusion, or provenance failure.

`COUNTS AGAINST` is appropriate when models fail to improve proper scores, are poorly calibrated, reverse out of time, reduce to symbol/volatility controls, or show concentration/instability. `MIXED` is appropriate for genuine but inconsistent improvement. `INSUFFICIENT EVIDENCE` is required when sample size, class resolution, missingness, dependence, validation coverage, leakage risk or engineering failure prevents a credible assessment.

M1 and M2 each receive an interpretation. An overall C3 interpretation must preserve disagreement and may not average one successful and one unsuccessful target into a success claim.

## Explicit 2026 Holdout Governance

During initial C3 implementation and review:

- no 2026 market file may be opened or read;
- no 2026 file listing, row count, checksum, schema validation or coverage inspection may be performed;
- no 2026 feature may be computed;
- no 2026 milestone or label may be generated;
- no 2026 model score, prediction, metric, diagnostic or artifact may be produced or inspected;
- no debugging, model choice, hyperparameter choice, threshold choice, feature design, calibration or interpretation tuning may use 2026;
- every input/event/feature/label timestamp at or after `2026-01-01T00:00:00Z` must be rejected before any associated market outcome value is consumed.

Input discovery must use an explicit allowlist of accepted 2024–2025 paths/hashes rather than broad globbing that could enumerate 2026 files. Synthetic fixtures must test the boundary without reading real 2026 data. Any eventual confirmation requires a separately authorized checkpoint; this contract alone does not authorize it.

## Milestone-State Dataset Schema

Produce separate deterministic M1 and M2 tables, ordered by `(milestone_interval_start_ts, symbol, trade_id, milestone_id)`. At minimum include:

### Provenance columns

```text
dataset_version, feature_schema_version, trade_id, symbol, entry_fixture_id
entry_execution_ts, entry_execution_ms, entry_price
milestone_id, milestone_ts, milestone_interval_start_ts, milestone_available_ts
feature_cutoff_ts, milestone_timing, milestone_price
common_horizon_end_ts, source_resolution, data_quality_flag
feature_eligible, feature_ineligible_reason
split_eligibility, split_exclusion_reason, applicable_label_resolution_boundary_ts
```

### Frozen feature columns

Exactly the ordered `C3_CAUSAL_MILESTONE_FEATURES_V1` columns defined above, plus explicit availability timestamps for each source timeframe/family where needed to audit the cutoff.

### Outcome columns

```text
label, label_name, label_resolution_ts, label_resolution_timing
censored, censor_reason, ambiguous, ambiguity_reason
upper_barrier_price, fallback_barrier_price
time_to_resolution_seconds
```

Outcome columns may coexist in a joined audit table but must be stored separately from the feature-only model matrix. Null labels are never coerced to a class.

## Required Future Tests

Implementation must include independent, hand-computable synthetic tests for:

- exact first +1% and +2% touch and rejection of later duplicate touches;
- entry-minute pre-fill exclusion;
- exact equality at milestones, upper barriers and fallback barriers;
- milestone-touch-minute upper-only resolution;
- milestone-touch-minute fallback-only non-resolution;
- same-minute upper/fallback ambiguity at the milestone and later;
- first resolved event remaining first when the opposite occurs later;
- complete censoring at H and H execution-price-only resolution;
- missing/invalid minute and gap handling without skipping;
- milestone and label timestamps strictly below the 2026 boundary;
- exact rejection at `2026-01-01T00:00:00Z` before market values are consumed;
- touch-minute exclusion from every primary feature;
- feature availability `<= feature_cutoff_ts` and truncation of every window at the milestone;
- future append/mutation after the cutoff not changing an earlier milestone feature row;
- mutation of label/outcome rows not changing features;
- completed 5-minute and 1-hour availability with no same-bar leakage;
- exact rolling-minute 5m/15m/30m/60m return calculations at a milestone cutoff that is not a 5-minute boundary, including exact endpoints, alignment and gap rejection;
- exact non-overlapping recent/prior 15-minute acceleration windows at a non-5-minute cutoff;
- exclusion of an aligned 5-minute bar that partly precedes entry from every post-entry path feature;
- cross-symbol timestamp alignment and rejection of nearest/forward-filled context;
- BTC/ETH context causality, including BTC/ETH as the subject, and an assertion that family F contains no exact duplicate of a corresponding L1 subject-local predictor for either subject;
- path efficiency, MAE, momentum, volatility, SMA, range, volume and breadth against independent numerical oracles;
- warm-up and missing-feature exclusion reasons;
- deterministic row order, semantic hash and byte-equivalent core output;
- exact 2024 fold and 2025 boundary assignment by milestone timestamp;
- a Fold-A validation milestone whose label resolves in Q4 being purged and counted as `unresolved_at_validation_boundary`;
- a Fold-B milestone resolving on or after `2025-01-01T00:00:00Z` being purged before any 2025 outcome value participates in model selection;
- a 2024 final-fit milestone resolving in 2025 being excluded as `unresolved_at_training_boundary`;
- a 2025 evaluation milestone unresolved at `2026-01-01T00:00:00Z` being excluded as `unresolved_at_2025_evaluation_boundary` without reading or consuming any 2026 outcome value;
- purge of every training label unresolved at its fold cutoff, with strict equality-at-boundary rejection;
- no row, path, feature, label or score at or after the 2026 boundary;
- feature/provenance/outcome structural separation;
- model pipeline rejection of outcome columns and future-fitted preprocessing;
- independently calculated B0, log loss, Brier, AUC and calibration examples;
- block-bootstrap grouping that keeps all symbols/simultaneous events in a month together;
- deterministic model/evaluation rerun with fixed seeds.

Tests use synthetic pre-2026 timestamps only. No 2026 market data may be accessed to test boundary enforcement.

## Reproducibility and Provenance

Every future C3 run must record in a machine-readable manifest:

- C3 contract hash and accepted predecessor revision `ab08b62`;
- accepted C2 source/normalized/aggregate hashes, frozen-entry hash, common-horizon hash, paired-table hash and temporal artifact hashes;
- exact allowlisted input paths and validation/schema versions;
- milestone and label definition versions;
- ordered feature schema, formulas, column roles and schema hash;
- M1 and M2 dataset semantic/file hashes and row/exclusion counts;
- chronological split boundaries and separate `unresolved_at_training_boundary`, `unresolved_at_validation_boundary`, and `unresolved_at_2025_evaluation_boundary` counts by milestone, fold, symbol and month;
- all attempted configurations and their status;
- model library/version, complete model specification and fitted-artifact hashes;
- preprocessing and encoding specification/hashes;
- random seeds, bootstrap block definition, replication count and quantile method;
- environment name, Python/interpreter and resolved dependencies;
- code revision plus hashes of dirty/untracked implementation, tests and configuration;
- core metric, prediction, calibration, coefficient and summary hashes;
- confirmation that no 2026 path was enumerated and no 2026 market outcome was accessed;
- deviations, failures and exclusion/censor/ambiguity ledgers.

Identical accepted inputs, code, configuration and seeds must reproduce byte-equivalent core milestone tables, feature matrices, predictions and machine-readable metric outputs. Manifests containing regenerated creation timestamps need not be byte-identical; core hashes must be.

## Future Implementation Tasks

### T1 — Provenance and sealed-boundary loader

Verify accepted C2 hashes, implement explicit 2024–2025 input allowlisting, enforce the 2026 boundary before values are consumed, and publish input/column-role manifests.

### T2 — Milestones, labels and causal features

Build separate deterministic M1/M2 tables, feature-only matrices and outcome tables under the exact semantics above. Freeze and hash the schema before predictive scoring.

### T3 — Chronological baselines and models

Run only B0–B2 and L0–L2 with the fixed folds/grid. Preserve all attempts and fitted preprocessing/model provenance.

### T4 — Dependence-aware evaluation and interpretation

Produce complete proper-score, calibration, stability, challenge-control, exclusion and block-uncertainty evidence. Stop before economic mapping.

## Engineering Completion Criteria

C3 Stage A engineering PASS requires:

- accepted C2 hashes verified and no accepted artifact mutated;
- exact M1/M2 milestone, ambiguity, censor and label counts reconciled;
- all causal availability and leakage tests passing;
- ordered feature schema frozen before predictive results;
- separate M1/M2 outputs and interpretations;
- chronological folds, label purging and locked 2025 evaluation implemented exactly;
- no 2026 file enumerated, opened or consumed;
- complete attempt, exclusion and provenance ledgers;
- dependence-aware metrics and challenge controls delivered;
- identical-input rerun reproducing core hashes;
- full relevant tests and `git diff --check` passing.

Engineering PASS does not imply signal, economic usefulness, profitability, deployment readiness, or authorization for Stage B or 2026 confirmation.

## Future Delivery Requirements

A later authorized executor shall deliver:

- initial/final repository and environment evidence;
- contract/input/code/schema/model hashes and explicit command log;
- M1/M2 schema dictionaries, counts, exclusion/censor/ambiguity ledgers and compact machine-readable summaries;
- separate feature-only and outcome artifacts, with large generated tables ignored but hash-addressed;
- fold, 2025, symbol, month and quarter metrics;
- calibration/reliability evidence, block-bootstrap uncertainty and coefficient stability;
- challenge-control findings and all attempted configurations;
- independent deterministic rebuild evidence;
- target-specific and overall scientific interpretations;
- explicit statements that Stage B, C2-B and 2026 confirmation were not run.

Do not commit raw/normalized market caches, large generated tables, model caches or credentials. Prefer compact source-controlled provenance and reproducible generated outputs.

## Unresolved Questions Reserved for Later Authorization

The following are intentionally not answered by initial C3 and must not be resolved opportunistically from 2025 or 2026 outcomes:

- Whether a supported probability signal has enough economic separation to warrant Stage B.
- How probabilities would map to hold/tighten/exit actions or thresholds.
- Whether a nonlinear model deserves a separately pre-registered experiment.
- Whether alternate milestone/barrier geometries merit a new target.
- Whether evidence generalizes beyond E1 or the fixed five-symbol fixture.
- Whether and when the sealed 2026 confirmation may be authorized.

## Executor Notes

The purpose of C3 is not to prove milestone-state prediction works. It is to determine whether a compact, causal state snapshot at a favorable milestone contains robust conditional information beyond base rate, symbol and volatility regime. Negative, unstable, poorly calibrated or insufficient results are valid completed outcomes. Stop after Stage A and await review.
