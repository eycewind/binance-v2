# C2 — Asymmetric Slow-Entry / Fast-Exit Experiment

Status: research execution contract for review. Do not execute merely because this file exists.

Target repository: `/media/ata/Data/personal/binance-v2`

Future delivery destination: `contracts/C2_asymmetric_exit_experiment_DELIVERY.md`

Future artifact root: `artifacts/c2_asymmetric_exit_experiment/`

## Background

C1 established checksum-verified Binance spot 1-minute ingestion, corrected millisecond/microsecond timestamp handling, next-interval availability for close-derived features, simple causal features, and deterministic synthetic USDT accounting. C1 did not implement or accept a Binance strategy, pair-ranking system, model, replay engine, or real-data backtest. `C1_binance_empirical_experiment_PROPOSAL_CONTRACT.md` is historical and superseded; it is not an accepted specification.

The motivating PSX diagnostic reconstructed 70 completed FIFO lots from sparse approximately 90-second recorder data. Only two had complete excursion history plus actual broker entry and exit prices; both were observed profitable after entry and ultimately sold at a loss. This is suggestive only and is not proof of an architectural defect or of the proposed remedy.

Binance is the bounded experimental laboratory because complete 1-minute paths can support controlled comparisons. The hypothesis is:

> Slower-timeframe logic may identify opportunities while a separate, higher-resolution exit layer may retain more favorable excursion without destroying net expectancy through premature exits, turnover, fees, slippage, or noise.

The central question is:

> Given identical entry events, does higher-resolution exit logic retain materially more favorable excursion without destroying net expectancy through premature exits, turnover, fees, slippage, or noise?

This experiment is designed to falsify as well as support that hypothesis. It is not simply a contest for the largest backtest return.

## Objective

Implement a reproducible experiment with two strictly separated stages:

1. **C2-A, frozen-entry trade-path attribution (primary):** give every exit policy the identical immutable set of entry events and compare handling of the subsequent path without capital constraints changing later entries.
2. **C2-B, portfolio-level consequences (conditional/later):** after C2-A is reviewed, allow exits to change cash, overlap, feasible later entries, exposure, turnover, and equity. C2-B must be separately configured, run, and reported; C2-A results may not be relabeled as portfolio results.

The first execution milestone shall implement C2-A only unless a later accepted amendment explicitly authorizes C2-B.

## Scope

In scope for C2-A:

- Extend validated 1-minute spot history only for the fixed research fixtures `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, and `BNBUSDT` over the approved interval below.
- Causally resample 1-minute bars to 5-minute and 1-hour bars.
- Generate and freeze a simple 1-hour entry fixture.
- Replay four predefined deterministic exit policies against every frozen entry.
- Report trade-path, cost, dependence, sensitivity, and failure-mode diagnostics with full provenance.

Out of scope:

- Claims about a historical Binance trading universe or deployable strategy.
- Point-in-time exchange-universe reconstruction as a prerequisite.
- Machine learning, fitted predictors, broad parameter grids, symbol-specific rules, or threshold optimization on headline evaluation data.
- Futures, leverage, short selling, live/paper trading, credentials, production integration, or account-specific fee claims.
- Automatic implementation of C2-B, 1-minute decision policies, or volatility-aware trails.
- Treating software PASS as research success or profitability evidence.

## Architectural and Governance Constraints

- Read applicable `AGENTS.md`, repository workflow, C0/C1 contracts and deliveries, C1 correction evidence, and current source/tests before implementation. Preserve unrelated changes.
- Start future implementation from reviewed current `origin/main` as required by `docs/DEVELOPMENT_WORKFLOW.md`; use a short-lived branch. Do not merge automatically.
- Before Python or project commands record `CONDA_DEFAULT_ENV`, `python --version`, `which python`, and `sys.executable`. The required environment is `binance-v2-research`, Python 3.11.x, with its interpreter. Do not modify `base`, `binbot`, or `psx-ml-research`.
- Hash this contract before and after execution. Do not silently edit it to fit observed results. Any scientifically material deviation requires a reviewed amendment and a new fixture/policy version.
- Preserve C1 semantics: raw timestamp-unit provenance, next-boundary availability for close-derived information, symbol isolation, gaps breaking windows, unavailable values remaining unavailable, explicit quote-denominated fees, and deterministic reruns.
- Information derived from a bar cannot cause execution inside that bar. Evaluation-only future path information must never enter a decision.

## Experimental Units, Universe, and History

The five C1 symbols are a declared engineering/research subset, not a reconstructed or validated trading universe. Use all five unless archive coverage or quality makes a symbol unusable; exclusions must be decided from data availability/quality before performance inspection and reported, never silently substituted.

The four-day C1 interval `[2024-12-30 00:00:00, 2025-01-03 00:00:00)` is pipeline-validation data and is scientifically inadequate for this study. It may be used only for engineering smoke tests, never for headline evidence.

Target later acquisition: validated Binance public spot 1-minute archives for the five symbols over `[2024-01-01 00:00:00, 2026-01-01 00:00:00)` UTC, plus the minimum preceding 24 complete hours needed for warm-up. This is about 5.27 million rows and, using C1 measurements, approximately 240 MiB compressed and 1.2 GiB normalized CSV before derived outputs; implementation must set measured resource limits before download and may choose audited columnar normalized storage.

Minimum evidential dataset if the target cannot be obtained: 12 complete evaluation months spanning more than one visibly distinct market regime, plus a preceding three-month calibration/sanity interval and warm-up. Less is an engineering-only run and must yield `INSUFFICIENT EVIDENCE`. Calendar boundaries must be fixed before viewing exit-policy outcomes. For the target interval, use `[2024-01-01, 2024-04-01)` only for implementation sanity and any explicitly authorized calibration, and `[2024-04-01, 2026-01-01)` as the untouched headline evaluation. Fixed parameters below require no outcome-based calibration. The sanity interval must not contribute headline metrics.

Five correlated major assets do not constitute five independent replications. Primary uncertainty must use calendar-time blocks (weekly and monthly summaries, and a block bootstrap or equivalent dependence-aware interval) with all symbols in a time block kept together. Also report each symbol separately. Do not use naive per-trade standard errors or multiply apparent sample size through overlapping trades.

## Canonical Time and Resampling Semantics

All timestamps are UTC interval-start timestamps represented without floating-point conversion. A source 1-minute bar with open time `m` represents `[m, m+1 minute)`; its raw close timestamp may be inclusive, but its contents become available at exactly `m+1 minute`.

For duration `D` (5 minutes or 1 hour), an aggregate timestamp `T` is the UTC-aligned interval start and represents `[T, T+D)`:

- 5-minute boundaries are minutes divisible by five; the source opens are `T, T+1m, ..., T+4m`.
- 1-hour boundaries are the top of the UTC hour; the source opens are `T, T+1m, ..., T+59m`.
- `open` is the first source open, `high` the maximum high, `low` the minimum low, and `close` the final source close.
- Base volume, quote volume, and trade count are summed with no imputation.
- Any duplicate, invalid, off-grid, or missing required minute invalidates the entire aggregate. A zero-trade but otherwise valid minute is not missing. No forward fill is allowed.
- Partial leading, trailing, or gap-crossing aggregate bars are prohibited and must not drive signals or execution.
- The aggregate becomes available only at `T+D`. Close-derived decisions may be stamped at that boundary, never before it.
- Aggregation is independent by symbol. Changing source data at or after a future boundary must not change earlier aggregates or decisions.

The primary slow decision layer is 1 hour and the fast layer is 5 minutes. One-minute bars provide execution chronology and barrier-order resolution; they are not a general 1-minute signal layer. A later contract may study 1-minute decisions only if 5-minute findings justify their greater noise, turnover, and execution sensitivity.

## C2-A Frozen Entry Fixture

The entry fixture is experimental infrastructure, not a claim of alpha or profitability. Its purpose is to generate a modest number of causal slow-timeframe opportunities without fitting a model.

Fixture ID `E1_H1_SMA24_CROSS_V1`:

1. For each symbol independently, compute `SMA24(T)` as the arithmetic mean of the closes of the 24 completed, contiguous 1-hour bars ending with hour `T`. It is available only at the end boundary of hour `T`.
2. An entry signal occurs at that boundary when `close(T) > SMA24(T)` and, on the immediately preceding completed hour, `close(T-1) <= SMA24(T-1)`. Both moving averages must have complete contiguous inputs.
3. The entry decision timestamp equals the signal timestamp. Execute only at the open of the valid 1-minute bar whose interval starts exactly at that decision boundary. This bar was not part of the completed signal hour. If it is missing or invalid, do not jump across the gap: mark the event unexecutable and exclude it under a separately reported, pre-policy rule.
4. Freeze `trade_id`, symbol, signal/decision/execution timestamps, actual simulated entry open, and fixture version before running any exit. Sort deterministically by `(entry_execution_ts, symbol, trade_id)` and hash the table.
5. Apply a fixture-only 24-hour refractory period per symbol from one entry execution timestamp to the next. Signals inside it are suppressed whether or not any policy would have exited. This fixed clock, not policy state or capital, controls event generation.
6. Entry notional is a constant 1,000 USDT gross per replay for fee reporting. C2-A permits independent/overlapping notional lots and no cash constraint. Returns, not aggregate fictional capital, are primary.

This price/SMA crossing uses one fixed 1-hour scale, no ML, no symbol-specific optimization, and only capabilities straightforwardly supported by validated OHLC. It intentionally does not use C1's 1-minute feature artifact as though it were a strategy. The 24-hour lookback and refractory period are design choices, not empirically optimal claims; they must not be tuned on evaluation outcomes.

Frozen-entry invariance is absolute: every policy receives every executable entry exactly once. A policy's earlier exit cannot create a replacement or repeated re-entry in C2-A. This eliminates capital/re-entry feedback but does not eliminate selection bias from the fixture; findings are conditional on `E1` and must not be generalized to all slow alphas. A later robustness contract may pre-register one substantively different entry fixture; it may not retrofit one after seeing which makes fast exits look best.

## Common Opportunity Horizon and Terminal Handling

Each entry receives one immutable opportunity horizon `H` used for comparable evaluation:

- Run P0 first using only causal data.
- `H` ends at P0's execution timestamp.
- If P0 produces no executable exit within 7 calendar days after entry, compute the exact expected UTC 1-minute boundary at `entry_execution_ts + 7 calendar days`. `H` ends only at the open of the valid 1-minute bar starting exactly at that boundary, and P0's reason is `time_cap`.
- If that exact cap bar is absent or invalid, if the dataset ends, or if an earlier data gap makes the path incomplete, mark the entry right-censored. Do not advance to a later bar. Exclude it from paired headline return/excursion comparisons for all policies, but report it and the reason. No policy receives an informational advantage from asymmetric censoring.
- Every candidate is also forcibly closed at `H` if it has not exited, with reason `common_horizon_cap`. No candidate may use data after `H` in C2-A.

Thus each policy has both an actual held path (entry through its own exit) and the same opportunity path (entry through `H`). Policy exits do not redefine opportunity MFE/MAE.

## Predefined Exit Policies

All percentage thresholds are simple price returns from the gross simulated entry execution price. They are fixed globally, not by symbol. The initial experiment has exactly these configurations; do not add variants or select the best-looking threshold.

### P0 — `P0_H1_SMA24_CROSSDOWN_V1` (slow control)

At a completed 1-hour boundary, signal exit when `close(T) < SMA24(T)` using 24 complete contiguous hourly closes ending at `T`. Execute only at the open of the valid 1-minute bar starting exactly at the decision boundary. Equality does not exit. Apply the common 7-day cap above.

### P1 — `P1_BRACKET_TP2_SL1_V1` (fixed take-profit / stop-loss)

Immediately after entry execution, place a conceptual standing take-profit at `entry_price * 1.02` and stop-loss at `entry_price * 0.99`. Monitoring starts strictly after the entry fill, so the entry bar's pre-fill range cannot trigger either barrier. Use ordered 1-minute bars to find the first bar touching a barrier. A single-bar touch executes at the barrier price before fee/slippage; a gap beyond a barrier executes at that minute's open, never at the more favorable barrier. If both barriers are touched within the same 1-minute OHLC and ordering cannot be known, choose the stop-loss first and record `ambiguous_both_hit_conservative`. This standing-order policy is the sole initial exception to completed-5-minute decision execution; its 1-minute inputs resolve barrier chronology rather than create a learned 1-minute signal. Also report 5-minute-bucketed trigger timing for comparison.

P1 asks whether a simple standing risk/harvest mechanism already captures much of the suspected opportunity. It is not evidence that a 5-minute decision layer works. P2 and P3 are the initial direct tests of the proposed active 5-minute exit layer.

### P2 — `P2_M5_TRAIL1_AFTER_GAIN1_V1` (causal running-peak trail)

At each completed 5-minute boundary after entry, update the running peak using only 5-minute highs from complete post-entry intervals observed so far. The trail is inactive until the running peak is at least `entry_price * 1.01`; once activated it never deactivates. Signal when the just-completed 5-minute close is at or below `running_peak * 0.99`. Execute at the next eligible 1-minute open. The running peak is peak-to-date, never final MFE. No initial hard stop is added.

### P3 — `P3_M5_MOMENTUM_DERIORATION_V1` (5-minute deterioration)

For complete post-entry 5-minute bars, compute the close-to-close return. Signal after two consecutive negative 5-minute returns (`close[k] < close[k-1]` and `close[k-1] < close[k-2]`). Execute at the next eligible 1-minute open. The necessary pre-entry 5-minute close may initialize the first return but cannot itself count as a post-entry negative observation. Equality is not negative.

The numerical choices are deliberately simple diagnostic configurations, not optimized values. A volatility-aware trail and 1-minute decisions are deferred. If any calibration or additional sensitivity is later authorized, it must use the pre-evaluation sanity interval, freeze before evaluation, retain all attempted configurations in provenance, and report sensitivity rather than promote the ex-post winner.

## Execution, Missing Data, and Costs

- Completed-bar signals execute no earlier than the next source bar not contained in the signal bar. The default fill is that 1-minute bar's open.
- Slippage is adverse by side and applied to the pre-slippage execution price: buy `price * (1+s)` and sell `price * (1-s)`. Fees apply to the resulting quote notional. Reject nonfinite/nonpositive prices.
- A missing immediate next execution minute makes that signal non-executable; do not skip forward across an unknown interval. For candidates, record the failure and apply the common paired-censor rule. P1 barrier behavior also stops at gaps because chronology is unknown.
- A signal on the final available bar with no subsequent execution bar is unfilled and censored, never filled at the known close.
- P1 uses 1-minute chronology to resolve 5-minute OHLC ambiguity. Remaining within-minute TP/SL ambiguity uses the conservative stop-first rule above. Do not select favorable ordering.
- Gross return is based on adverse-slippage-adjusted fill prices but before fees; also retain raw-price return so slippage is separately attributable. Net return includes entry and exit fees and slippage. Use the C1-compatible USDT quote-fee ledger semantics and no borrowing.

Required cost scenarios, all reported gross and net separately:

1. `C0`: zero fee, zero slippage diagnostic.
2. `C_BASE`: 10 basis points fee per executed leg and 2 basis points adverse slippage per leg.
3. `C_S5`: 10 bp fee and 5 bp slippage per leg.
4. `C_S10`: 10 bp fee and 10 bp slippage per leg.

The 10 bp fee is an explicit research scenario inherited from C0, not a verified account-specific Binance rate. C2-A has exactly one entry and one exit leg per replay; report two executed legs unless an event is unfilled/censored. C2-B must count actual orders/legs and rejected orders. No maker rebates, spread model, partial fills, market impact, or quantity filters are claimed in C2-A; these limitations constrain deployment interpretation.

## Trade-Level Output and Definitions

Write one deterministic record per frozen executable entry × exit policy × cost scenario. At minimum include:

```text
run_id, trade_id, symbol, entry_fixture_id
entry_signal_ts, entry_decision_ts, entry_execution_ts, entry_price, entry_price_after_slippage
exit_policy, exit_policy_version
exit_signal_ts, exit_decision_ts, exit_execution_ts, exit_price, exit_price_after_slippage, exit_reason
entry_timeframe, signal_timeframe, exit_observation_timeframe, source_timeframe
execution_price_assumption, cost_scenario
gross_return, raw_price_return, net_return, fees_usdt, slippage_usdt_or_rate
held_mfe, held_mae, common_horizon_mfe, common_horizon_mae
time_to_held_mfe, time_to_common_horizon_mfe, holding_duration, common_horizon_duration
max_drawdown_from_post_entry_peak, held_peak_gain_surrendered, common_opportunity_capture_gap
held_peak_gain_retention, common_opportunity_capture_ratio
held_ever_green, held_ever_above_0_5pct, held_ever_above_1pct, held_ever_above_2pct, held_ever_above_3pct
common_opportunity_ever_green, common_opportunity_above_0_5pct, common_opportunity_above_1pct, common_opportunity_above_2pct, common_opportunity_above_3pct
held_green_then_red, common_opportunity_positive_exit_red
common_horizon_end_ts, censored, ambiguity_flag, data_quality_flag
```

Definitions use raw source prices relative to the actual raw entry execution price unless explicitly labeled cost-adjusted:

- `raw_price_return = exit_price / entry_price - 1`.
- `gross_return = exit_price_after_slippage / entry_price_after_slippage - 1` before fees.
- `net_return = (net exit proceeds - total entry outlay) / total entry outlay`, with both quote-denominated fees included. `fees_usdt` is their sum for the fixed 1,000 USDT gross entry notional; record the precise quantity convention.
- Post-entry path measurement starts after the entry fill. The entry price itself is included as a zero-return anchor. Pre-fill high/low from the entry minute is excluded because its ordering relative to the fill is unknown; subsequent complete source bars supply highs/lows. The exit fill is included as an endpoint, but post-exit range is not part of the held path.
- `held_mfe = max(path_high / entry_price - 1, 0)` and `held_mae = min(path_low / entry_price - 1, 0)` over entry through that policy's exit. These describe what the policy held and are not directly comparable opportunity sets when exit times differ.
- `common_horizon_mfe` and `common_horizon_mae` use the frozen entry through `H`, identically for every policy. These are the primary opportunity measures for paired exit attribution. Store them once in the frozen path table and verify they repeat identically across policies.
- `time_to_*_mfe` is elapsed UTC time from entry execution to the first timestamp at which the relevant maximum is observed. If MFE is zero only at the entry anchor, it is zero duration.
- `holding_duration = exit_execution_ts - entry_execution_ts`; it cannot be negative.
- `max_drawdown_from_post_entry_peak` is the maximum, over the actual held path, of `1 - current_low / running_peak_price`, where the running peak is initialized to entry price and uses only observations available up to that point.
- `held_peak_gain_surrendered = held_mfe - raw_price_return`. It measures favorable excursion actually observed while that policy held the position and subsequently given back by exit.
- `common_opportunity_capture_gap = common_horizon_mfe - raw_price_return`. It compares the realized exit with the best favorable excursion in the immutable comparison horizon. For an early exit, later appreciation is missed opportunity, not literal post-peak giveback.
- `held_peak_gain_retention = raw_price_return / held_mfe` only when `held_mfe >= 0.005`. Otherwise it is null with reason `held_mfe_below_retention_threshold`.
- `common_opportunity_capture_ratio = raw_price_return / common_horizon_mfe` only when `common_horizon_mfe >= 0.005`. Otherwise it is null with reason `common_mfe_below_retention_threshold`. For both ratios, 0.5% is the predeclared positive threshold, negative values are retained, values above one are investigated rather than clamped, and division by zero is forbidden. Never compare or aggregate the two ratios as though their denominators and horizons were interchangeable.
- `held_ever_green` means `held_mfe > 0`. The `held_ever_above_*` flags mean `held_mfe` is at least 0.5%, 1%, 2%, or 3% respectively and are policy-specific.
- `common_opportunity_ever_green` means `common_horizon_mfe > 0`. The `common_opportunity_above_*` flags mean common-horizon MFE is at least 0.5%, 1%, 2%, or 3% respectively and are identical across policies for a `trade_id`.
- `held_green_then_red` means that policy's `held_mfe > 0` and its `raw_price_return < 0`. This is the direct analogue of the motivating failure mode: the position was observed profitable while still held and later exited at a loss.
- `common_opportunity_positive_exit_red` means `common_horizon_mfe > 0` and that policy's `raw_price_return < 0`. It establishes favorable opportunity somewhere in the frozen comparison horizon but does not claim the policy held through that observation. Equality to zero is neither profitable nor losing and must be a separate count.

Because OHLC extremes do not reveal a unique continuous path, record whether MFE/MAE timing is exact to a minute or only localized to a minute. Never infer high-versus-low order inside a minute except for the stated conservative P1 rule.

## Required Analysis

All comparisons in C2-A are paired by `trade_id`. Report at least, overall, by symbol, by calendar block, by entry-year/month, by policy, and by cost scenario:

- trade count and censored/unexecutable count;
- policy-specific percentages `held_ever_green` and held above +0.5%, +1%, +2%, and +3%, alongside the corresponding common-opportunity percentages;
- profitable, zero, and losing exit percentages;
- `held_green_then_red` and `common_opportunity_positive_exit_red` percentages, never conflated;
- median plus quantiles/distributions of common and held MFE/MAE, realized raw/gross/net return, time to MFE, holding duration, drawdown, `held_peak_gain_surrendered`, `common_opportunity_capture_gap`, and both valid retention measures;
- arithmetic expectancy with dependence-aware uncertainty, downside quantiles, loss magnitude, and tail outcomes—not only mean or win rate;
- fixed replay notional diagnostics, executed/unfilled legs, fees, slippage sensitivity, holding-duration differences, and censor/unfilled differences; label the mechanical two-sided notional ratio as fixed replay turnover, not portfolio turnover;
- paired deltas versus P0 for net return, held surrender, common capture gap, holding duration, `held_green_then_red`, and `common_opportunity_positive_exit_red` status;
- premature-exit diagnostics: candidate exits before P0 followed by common-horizon appreciation above the candidate exit, candidate underperformance versus P0, and the distribution of foregone subsequent gain;
- rescue diagnostics: P0 nonpositive while a candidate is positive, with costs applied separately;
- policy trigger reasons, P1 ambiguity counts, gap/censor counts, and missing retention reasons.

Define the required baseline cohorts from the common path before inspecting candidate results:

```text
common_horizon_mfe >= +0.5% and P0 raw_price_return <= 0
common_horizon_mfe >= +1.0% and P0 raw_price_return <= 0
common_horizon_mfe >= +2.0% and P0 raw_price_return <= 0
common_horizon_mfe >= +3.0% and P0 raw_price_return <= 0
```

For each cohort report count, candidate profitability-rescue rate, paired held-surrender and common-capture-gap changes, exit-time change, net-return change at every cost scenario, and outcomes outside the cohort to expose premature exits. These nested cohorts are descriptive and dependent; do not treat them as four independent hypothesis tests.

Overlapping entries and clustered regimes invalidate naive aggregation. Report the number of simultaneously open frozen paths, effective calendar coverage, symbol correlations, and block-level dispersion. Equal-weight symbols and equal-weight entries answer different questions; report both and designate equal-weight-symbol aggregation as primary so a high-frequency symbol cannot dominate.

## C2-B Conditional Portfolio Stage

C2-B requires a reviewed follow-on section/amendment after C2-A evidence exists. It shall reuse the frozen entry signal generator but process events chronologically with a deterministic initial cash balance, position sizing, maximum concurrent exposure, tie-breaking, affordability, and C1-compatible USDT mark-to-market ledger. Policy exits may then change cash, overlaps, feasible entries, exposure, turnover, and later portfolio equity.

C2-B must not call skipped capital-constrained entries equivalent to C2-A entries, and must distinguish signal opportunities, submitted orders, rejected orders, and fills. It must include all open losing positions in equity and mark missing prices unresolved. Re-entry differences are a C2-B consequence, not an exit-quality benefit in C2-A. C2-A and C2-B get separate run IDs, tables, plots, and conclusions.

## Threats to Validity and Required Interpretation

- **Fixture selection:** frozen entries isolate exit attribution but condition results on one simplistic trend-crossing selector. The fixture may favor or oppose particular exits. Conclusions are limited to these selected paths; robustness across genuinely different pre-registered entries is future work.
- **Frozen-entry counterfactual:** suppressing policy-driven re-entry intentionally removes capital feedback. Every resolved C2-A replay has one entry and one exit, so policy-driven re-entry frequency, additional trade count, capital recycling, and meaningful portfolio-turnover differences are structurally suppressed. C2-A can measure fixed replay legs, costs, holding time, and censor/unfilled differences, but cannot determine whether fast exits cause excessive portfolio turnover or estimate portfolio return. C2-B is required for those claims.
- **Common horizon:** policy-specific held MFE identifies excursion actually experienced while held; the P0-derived common horizon identifies the immutable opportunity set. Report held giveback separately from common-horizon missed opportunity so early exits cannot improve a metric merely by truncating the future and later appreciation is not mislabeled as giveback.
- **OHLC ordering:** 5-minute OHLC alone can hide barrier order; 1-minute chronology reduces but does not eliminate ambiguity. Conservative within-minute resolution and ambiguity counts are mandatory.
- **Pseudo-replication:** five large-cap crypto assets are correlated, entries overlap, and regimes cluster. Calendar-block inference and symbol-level reporting are required; trade count is not independent sample size.
- **Survivorship/universe:** the fixed current-known symbols are research fixtures. Results say nothing about a historical Binance universe and may contain survivorship/selection bias.
- **History/regimes:** even two years may not represent future regimes. A short or single-regime sample is insufficient evidence, regardless of trade count.
- **Parameter mining:** the fixed entry and exit thresholds may be poor, but replacing them after outcome inspection would contaminate evidence. All attempted variants must be disclosed; no best-on-evaluation promotion is allowed.
- **Execution realism:** public OHLCV lacks spread, queue position, impact, and tick-by-tick paths. Slippage sensitivity bounds part, not all, of this risk.
- **Multiple outcomes:** no single metric or favorable subgroup establishes the hypothesis. Report the complete predefined panel and negative findings.

Within C2-A, evidence supporting further work would combine materially lower held peak-gain surrender, smaller common-opportunity capture gaps, fewer held-green-then-red outcomes, retained or improved net expectancy, cross-symbol/time robustness, and survival under baseline/modest cost sensitivity. Evidence against includes cosmetic peak capture with worse net expectancy, recurrent premature truncation of large trends, cost sensitivity, or concentration in one symbol/period. C2-A cannot demonstrate manageable portfolio turnover or rule out excessive policy-driven re-entry; those are C2-B questions. Mixed or underpowered results are `INSUFFICIENT EVIDENCE`.

Do not invent arbitrary ADVANCE/REJECT numerical cutoffs after seeing results. Engineering completion has objective PASS/FAIL criteria below; research interpretation must be `SUPPORTS FURTHER WORK`, `COUNTS AGAINST`, `MIXED`, or `INSUFFICIENT EVIDENCE`, with the full metric panel and uncertainty. No label claims profitability or deployment readiness.

## Future Implementation Tasks and Tests

### T1 — Provenance-bound data extension

Implement bounded, checksum-verified acquisition for only the five fixtures and approved dates. Preserve C1 timestamp transition handling, immutable raw inputs, validation manifests, hashes, exact grids, and failure-blocking publication. Record estimated versus measured rows/bytes. Do not reconstruct or claim a historical universe.

### T2 — Causal aggregation and frozen entries

Implement the canonical resampler, fixture, immutable entry/path tables, common horizon, and deterministic hashes. No exit-policy code may influence entry generation.

### T3 — Policy replay and costs

Implement P0–P3 exactly, shared execution/censor rules, cost scenarios, trade records, and independent calculation checks. Decision code must not receive final MFE or future rows.

### T4 — Analysis and evidence

Produce paired metrics, cohorts, distributions, dependence-aware uncertainty, limitations, and research interpretation without policy selection. Plotting is optional; machine-readable tables are mandatory.

Required automated tests include:

- exact 1m→5m and 1m→1h OHLC/volume/quote-volume/trade-count aggregation;
- UTC alignment, availability at interval end, and no same-bar execution;
- rejection of partial windows, gaps, duplicates, invalid bars, and cross-symbol contamination;
- symbol isolation and invariance of earlier aggregates/decisions under future append or mutation;
- identical frozen entry IDs/timestamps/prices and counts for every policy and cost scenario;
- exit never preceding entry; completed-bar execution strictly after its source interval; final-bar and missing-next-bar handling;
- running peak using past only and final MFE being unavailable to policy code;
- P1 TP/SL chronology, gap-through price, both-hit conservative ordering, and exclusion of pre-fill entry-bar range;
- P2 activation and trail behavior; P3 exact two-negative-return behavior;
- common-horizon MFE/MAE identical across policies and held-horizon measures correctly different;
- fee/slippage arithmetic, two executed legs, gross/net separation, and adverse direction;
- exact seven-day cap-bar enforcement and paired right-censoring when that minute is absent or invalid, with no gap skipping;
- correct held/common excursion flags and distinct `held_green_then_red` versus `common_opportunity_positive_exit_red` outcomes, including an early exit before later favorable movement;
- correct `held_peak_gain_surrendered` and `common_opportunity_capture_gap` on paths where their values differ;
- held and common retention null below their respective 0.5% MFE threshold, valid at exactly 0.5%, negative values retained, and no divide-by-zero/clamping or horizon mixing;
- deterministic row order, IDs, hashes, and byte-equivalent machine-readable outputs from identical inputs/configuration.

At least one hand-computable synthetic path must use entry 100, then rise materially, then fall below 100. For example, complete minute bars may establish a common-horizon high of 103 and P0 exit at 99, proving `common_horizon_mfe = 3%`, favorable opportunity existed, and baseline raw return is `-1%`. Run all candidate rules exactly as specified and assert their calculated outcomes; construct timestamps/bars naturally and do not alter the path to force any fast policy to win. Include a second path where an early fast exit misses a later large trend, so premature-exit diagnostics are positively tested.

## Reproducibility and Provenance

Every future run must record in a machine-readable manifest:

- source URLs/paths, raw and normalized hashes, validation/schema versions, and retrieval/cache-verification evidence;
- code revision plus hashes of dirty/untracked implementation/configuration files;
- contract hash, run ID, creation time, environment name, Python/interpreter and resolved dependencies;
- entry fixture ID/definition/version and frozen-entry-table hash;
- every exit policy ID/version and parameter value, including inactive/default values;
- date ranges, sanity/evaluation split, symbols, source resolution, resampling rules, timezone, and gap policy;
- fee/slippage scenarios, notional/quantity convention, execution and ambiguity assumptions;
- attempted configurations, deviations, censor/exclusion counts, and output hashes.

Identical validated inputs, code/configuration, and run identifier seed (if any resampling-based uncertainty is used) must produce identical core trade tables and metrics. Statistical resampling seeds and block definitions must be fixed and recorded.

## Completion Criteria

C2-A engineering PASS requires all of the following:

- approved history is validated or explicitly downgraded to an engineering-only run;
- all causal resampling, fixture, policy, execution, cost, retention, common-horizon, and deterministic tests pass;
- the frozen-entry hash and invariance evidence are recorded;
- every required field, aggregate, cohort, sensitivity, symbol/time breakdown, censor count, and threat-to-validity disclosure is delivered;
- no parameter was selected from headline evaluation outcomes and all attempted configurations are disclosed;
- a second identical-input run reproduces core hashes;
- `git diff --check` and the repository's relevant test command pass.

Research evidence is evaluated separately and may be supportive, adverse, mixed, or insufficient even when engineering passes. Failure to find fast-exit improvement is a valid completed result.

## Future Delivery Requirements

The later executor shall produce the flattened C2 delivery and artifacts under the stated root, including:

- initial/final branch, HEAD, remotes, status, environment evidence, contract hashes, command log, and exact diff;
- data inventory/quality/provenance and measured resource use;
- frozen entries and path table, policy/cost trade table, schema/data dictionary, configurations, and hashes;
- automated and hand-calculation test evidence plus deterministic rerun evidence;
- predefined aggregate/cohort/dependence tables and optional plots;
- deviations, censor/exclusion ledger, validity limitations, and research interpretation;
- an explicit statement that C2-B was not run unless separately authorized.

Do not begin C2-B, create a later contract, commit, push, or claim acceptance beyond the authority explicitly granted at execution time.

## Executor Notes

Prefer small, auditable components over a general trading framework. Keep policy decision inputs structurally separate from evaluation columns so final MFE cannot leak into decisions. Preserve intermediate frozen tables before policy replay. When an ambiguity cannot be removed, choose the predeclared conservative treatment and expose its count rather than hiding it in an aggregate.
