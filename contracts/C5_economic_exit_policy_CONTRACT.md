# C5 — Economic Exit-Policy Stage B Contract

Status: design contract only. This file does not authorize implementation, policy replay, P&L calculation, model fitting, prediction regeneration, or access to sealed data.

Reviewed pre-execution addendum: `contracts/C5_economic_exit_policy_ADDENDUM.md`. The addendum is bound to this contract's pre-addendum SHA-256 `e836c3ac834b6beb49a87b1efa5dd0fb4f157725810ac68efb57bbea509de0de` and controls where it freezes or narrows Sections 14–18 and 22. Neither document authorizes execution by itself.

Target repository: `/media/ata/Data/personal/binance-v2`

Future artifact root: `artifacts/c5_economic_exit_policy/`

## 1. Scientific basis and objective

C2 found substantial favorable excursion followed by large surrender under the immutable held exit, while its simple deterministic fast exits reduced some giveback without robustly improving expectancy. C3 fixed-milestone continuation classifiers did not generalize strongly enough. C4 therefore tested sequential post-entry state.

The accepted C4 conclusion is frozen:

- T1: `MIXED`.
- T2: `SUPPORTS SEQUENTIAL PATH-STATE SIGNAL`.
- Locked 2025 T2 G1: log loss `0.6837583397803341`; Brier score `0.3983540377871161`.
- Locked 2025 T2 P1: log loss `0.6749034432670686`; Brier score `0.3943488387769584`.
- The decisive P1-minus-G1 comparison improved both proper scores with dependence-aware intervals below zero. Improvement appeared in all five symbols and all four quarters, but not every month.
- Calibration supports ranking but is imperfect as an absolute-probability interpretation.

C5 asks:

> Can a causal state-dependent exit policy use the frozen C4 T2 signal to capture more already-observed favorable excursion than immutable P0, net of realistic costs, while preserving net expectancy and avoiding unacceptable truncation of large winners?

The primary scientific attribution question is whether a P1-driven policy improves trade economics over the economically identical G1-driven policy. P1 versus P0 is the primary practical comparison. G1 versus P0 is a required control. A favorable P1-versus-P0 result without a favorable P1-versus-G1 result cannot be attributed to historical path information.

This is a frozen-entry, fixed-opportunity replay design, not a causal claim about live deployment, a portfolio backtest, or authorization to trade.

## 2. Scope and non-scope

The only later work this contract can govern is staged mechanical implementation, verification, development-era replay, and possible policy freeze as specified in Section 19.

It does not authorize:

- any work merely because this file exists;
- any model refit, feature selection, hyperparameter change, probability recalibration, target change, horizon change, or regeneration or alteration of locked predictions;
- broad threshold optimization or selection of the best realized P&L;
- entry changes, sizing optimization, capital recycling, replacement entries, re-entry, leverage, shorting, live/paper trading, or deployment;
- treating faster exits as automatically freeing capital for another trade;
- access to the sealed confirmation period; or
- modification of C2, C3, or C4 artifacts.

## 3. Governance and temporal roles

The 2024 and 2025 periods are consumed research/development evidence. Both may be used for C5 Stage-B development only after this contract, its reviewed pre-execution addendum, and its complete provenance manifest have been reviewed and frozen. Neither period is pristine confirmation for C5 economics. Results must be labeled development-era evidence.

The period beginning at the sealed boundary remains inaccessible. No file, directory, row, partition, manifest entry, hash, metadata listing, or outcome from that period may be enumerated, opened, inspected, hashed, or consumed. Only synthetic unit tests containing a date-boundary literal may reference that calendar year; they must contain no market observations or derived outcomes.

Any eventual confirmation requires all of the following: completion of T3, a frozen single C5 policy and code/configuration hashes, a new reviewed confirmation contract, and explicit authorization. Development and confirmation must not be combined.

## 4. Immutable upstream inputs and hash gate

C5 treats these as read-only and immutable:

- `E1_H1_SMA24_CROSS_V1` entry IDs, symbols, signal/decision/execution timestamps, execution prices, and fixture order;
- immutable P0 exits and P0-derived common horizons `H`;
- C4 T2 snapshot cadence, row identity, reference prices, eligibility, barrier/event definitions, censoring semantics, and endpoint rules;
- C4 T2 feature schema and exact G1/P1 model matrices;
- frozen 2024 preprocessing objects and statistics;
- frozen G1 and P1 coefficients, class order, intercepts, transforms, and prediction conventions;
- locked 2025 G1 and P1 prediction rows and values;
- accepted 2024 G1 and P1 prediction rows needed only to establish rank cutoffs;
- C4 trade weights and all accepted source, configuration, code, model, preprocessing, prediction, and output hashes.

Known accepted C2 provenance recorded in its delivery includes:

- frozen-entry hash: `6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3`;
- common-horizon hash: `81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f`.

These values are documentary references, not permission to open upstream data. Before T1 implementation, a provenance-only gate must copy every required accepted hash from the authoritative accepted manifests into a C5 input manifest and reconcile it byte-for-byte. The contract intentionally does not invent C4 hashes that are not stated in the reviewed materials available at contract drafting. Missing, conflicting, or unaccepted hashes block T1 and are reported; they may not be repaired by refitting or regenerating an artifact.

No hash reconciliation may touch sealed-period artifacts or recursively enumerate paths that could expose them.

## 5. Experimental unit and common opportunity set

The primary experimental unit is one frozen E1 trade. Repeated five-minute policy decisions within a trade are dependent state observations, not independent samples.

Every policy receives the same entry and immutable common horizon. Earlier exit cannot create a replacement trade. Evaluation-only path metrics use the accepted path no later than `H`; policy-held metrics stop at that policy's exit. Common-horizon MFE must be identical across policies for a trade. Policy-specific held MFE must not be substituted for common-horizon MFE to make an early exit appear to capture more opportunity.

Primary aggregation is equal weight per trade. Equal-weight-symbol aggregation is a required co-primary robustness view so the most frequent symbol cannot dominate. Trade-weighted and fixed-notional totals must both be labeled. Five symbols are not five independent replications.

C5 answers two distinct questions: whether the common policy has economic value across the pooled five-symbol research universe, and for which individual symbols that unchanged policy appears economically suitable. Pooled evidence cannot substitute for symbol-level evidence. The first replay must apply the identical global policy definitions, global Q75/Q90 construction, eligibility, execution, and costs to `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, and `BNBUSDT`. No symbol receives a bespoke cutoff, recalibration, refit, feature change, score, or policy choice.

## 6. Eligible T2 activation state

A C5 policy may decide to exit only at a completed five-minute snapshot that is eligible for the frozen C4 T2 risk set. All of the following are mandatory:

- causal running peak gain `G_t = P_t / E - 1 >= 0.0100`;
- current gain `R_t = C_t / E - 1 > 0`;
- `C_t > D2`, where `D2 = E * (1 + 0.50 * G_t) = (E + P_t) / 2`;
- the trade is open under that C5 policy and `t < H`;
- the completed snapshot and frozen prediction satisfy every accepted C4 T2 availability, feature-eligibility, gap, and identity rule.

Thus the policy cannot first activate after the trade has already reached or crossed the frozen 50%-giveback state. Equality at `C_t == D2` is ineligible. No decision is allowed from T1, an ineligible T2 row, a future label, or a future path value.

The policy is evaluated at each eligible snapshot while the trade remains open. An eligible row that lacks an accepted frozen model prediction is `prediction_unavailable`; it cannot be imputed, recomputed, or skipped silently. Section 22 requires a provenance-only coverage decision before replay.

P0 is not subject to the T2 risk set because it is the immutable baseline, not an active C5 action.

## 7. Frozen policy state score

For model `M` in `{G1, P1}` and an eligible snapshot `t`, define exactly:

```text
S_M(t) = p_M(substantial_giveback | t) - p_M(renewed_peak | t)
```

The class probabilities are the frozen C4 T2 outputs in the accepted class order. `p_M(no_event_60m)` is retained and audited but has coefficient zero in this score. Larger `S_M(t)` means greater relative giveback risk and is the exit direction. No logit transform, odds ratio, renormalization excluding no-event, smoothing, recalibration, symbol adjustment, elapsed-time adjustment, or outcome-dependent transformation is allowed.

This contrast is chosen because it directly ranks the two economically opposed resolved transitions without treating a probability such as 0.70 as literally calibrated. It also applies the same semantic mapping to G1 and P1. The score is a ranking device, not an estimate of expected return.

## 8. Exact policy family: five variants

C5 V1 contains exactly five policy variants:

1. `P0_HELD_V1`: immutable original P0 exit.
2. `G1_Q75_EXIT_V1`: exit at the first eligible G1 snapshot with `S_G1(t) >= q_G1(0.75)`.
3. `P1_Q75_EXIT_V1`: exit at the first eligible P1 snapshot with `S_P1(t) >= q_P1(0.75)`.
4. `G1_Q90_EXIT_V1`: exit at the first eligible G1 snapshot with `S_G1(t) >= q_G1(0.90)`.
5. `P1_Q90_EXIT_V1`: exit at the first eligible P1 snapshot with `S_P1(t) >= q_P1(0.90)`.

For each model separately, `q_M(a)` is the deterministic unweighted empirical Type-7 quantile of that model's accepted frozen 2024 score vector over unique frozen T2 feature-eligible prediction rows, before any economic path or outcome is joined. Use NumPy-compatible `quantile(..., method="linear")`; sort ties by canonical C4 row identity for audit, although the numeric quantile is order invariant. Quantiles are global, not symbol-, month-, quarter-, elapsed-time-, or trade-specific. The exact numeric cutoffs, source-row count, row-set hash, score-vector hash, method, and resulting cutoff hash must be frozen before economic replay.

The two intensities represent one moderate and one sparse intervention. They are not a grid and neither may be designated primary based on replay results. `Q75` is the predeclared primary intensity because it offers enough intervention opportunities to test the capture hypothesis; `Q90` is the sole predeclared sparse sensitivity for winner preservation. Ties trigger under inclusive `>=` semantics and may make the realized trigger fraction exceed the nominal tail fraction.

The G1 and P1 policies have identical eligibility, score formula, rank level, decision cadence, execution, costs, and fallback. Model-specific quantiles deliberately compare equivalent within-model risk ranks rather than uncalibrated probability levels. Raw-score cutoff comparisons are descriptive only.

Each model's Q75 and Q90 cutoffs are global across the full accepted cutoff-source population and are applied unchanged to every symbol. A symbol's own prediction distribution, trigger rate, or economic result cannot redefine a cutoff.

No ensemble, persistence rule, hysteresis, stop, take-profit, partial exit, size change, combined G1/P1 rule, third quantile, or alternate score is authorized.

## 9. Decision and execution semantics

Snapshots occur only at the existing completed, UTC-aligned five-minute cadence. At boundary `t`, the latest input is the completed interval ending at `t`; only information with availability timestamp `<= t` is available.

When an eligible score first meets its cutoff:

- `exit_decision_ts = t`;
- execution is at the raw open of the immediate one-minute interval `[t, t+1m)`;
- no value from that execution minute may influence the decision;
- the execution is a full liquidation of the fixed replay position; and
- no later snapshot can reverse or replace the exit.

If the immediate execution minute is missing, invalid, duplicated, non-grid-aligned, or has a nonfinite/nonpositive open, the policy exit is unexecutable. The implementation must not skip to a later price or fill at the snapshot close. The affected policy-trade is unresolved and excluded only under a predeclared paired-comparison rule: for each contrast, both sides are excluded if either side is unresolved. Counts and reasons remain reported. A common complete-case panel across all five policies is a required sensitivity.

If no trigger executes before `H`, the policy exits at exactly the immutable P0 execution point, price, and reason. A decision at `t >= H`, or whose next-minute execution is not strictly before the P0 execution point, cannot replace P0. When the next-minute open timestamp equals the P0 execution timestamp, P0 prevails, preventing a synthetic timing advantage at the common endpoint.

No barrier is assumed between snapshots. This policy is a completed-state market-exit instruction, not a standing stop. Gaps execute at the next permitted open under the same adverse-slippage convention as any other exit.

## 10. Costs and return accounting

C5 inherits the accepted C2 fixed-replay conventions. Entry fills and entry costs are identical across policies. Slippage is adverse by side and multiplicative: buy `price * (1+s)`, sell `price * (1-s)`. Fees apply separately to each resulting executed quote notional.

The primary Binance spot research fee assumption is 10 basis points (`0.0010`, or 0.10%) on entry executed notional and 10 basis points on exit executed notional. Thus a normal one-entry/one-exit trade has approximately 20 bp (0.20%) fee-only round-trip friction before slippage. Because exit notional varies with price and slippage and percentage costs compound, basis-point round-trip totals are approximations; the ledger must calculate exact cash amounts from actual executed notionals.

For every trade-policy-cost record, preserve and report separately:

- `raw_price_return`, before modeled slippage or fees;
- `gross_return`, retaining the accepted C2 meaning of return after adverse slippage but before fees;
- `entry_fee_quote`, charged to actual slippage-adjusted entry executed quote notional;
- `exit_fee_quote`, charged to actual slippage-adjusted exit executed quote notional/proceeds;
- `entry_slippage_quote` and `exit_slippage_quote`, plus their sum `slippage_cost_quote`, relative to the raw execution prices under the accepted fixed-quantity ledger;
- `total_transaction_cost_quote = entry_fee_quote + exit_fee_quote + slippage_cost_quote`; and
- `net_return`, after every fee and modeled slippage cash flow.

Also report `entry_fee_rate`, `exit_fee_rate`, and the entry/exit slippage rates so the cash ledger is auditable. Total transaction cost must never be approximated by multiplying a headline round-trip basis-point number by initial notional when exact executed notionals are available.

Exactly four cost scenarios apply to every policy; a policy is never optimized separately by cost case:

| ID | Entry fee | Exit fee | Adverse entry slippage | Adverse exit slippage | Approx. normal round trip | Role |
|---|---:|---:|---:|---:|---:|---|
| `C0` | 0 bp | 0 bp | 0 bp | 0 bp | 0 bp | frictionless diagnostic |
| `C_BASE` | 10 bp | 10 bp | 2 bp | 2 bp | 24 bp (0.24%) | primary economic case |
| `C_S5` | 10 bp | 10 bp | 5 bp | 5 bp | 30 bp (0.30%) | slippage sensitivity |
| `C_S10` | 10 bp | 10 bp | 10 bp | 10 bp | 40 bp (0.40%) | slippage stress sensitivity |

Fee remains fixed at 10 bp per executed leg in `C_BASE`, `C_S5`, and `C_S10`; only adverse slippage changes. In `C_BASE`, the approximately 20 bp fee-only round trip plus approximately 4 bp round-trip slippage gives approximately 24 bp total friction for the normal two-leg trade. The 10 bp fee is the contract's Binance spot research assumption, not a verified account-tier, BNB-discount, maker/taker, promotion, or symbol-specific rate. No maker rebate, spread beyond the slippage scenarios, impact, queue position, partial fill, minimum quantity, or latency beyond the explicit next-minute rule is modeled. These omissions limit deployment interpretation.

Use the accepted C2 fixed gross entry notional of 1,000 USDT solely for quote-denominated fee and aggregate fixed-notional diagnostics. Fees and slippage must be computed on the actual executed notional of each transaction, not charged as a flat amount. Every current C5 variant performs one entry and one full exit; earlier timing does not create extra trades. If a future, separately contracted policy ever permits partial or multiple exits, every exit transaction must incur its own fee and slippage and must be listed separately; netting several transactions into one fee is prohibited. This clause does not authorize such a policy in C5 V1.

Report raw, gross, cost-component, total-cost, and net results for all four scenarios. `C_BASE` governs advancement, and conclusions must disclose if they fail either adverse-slippage sensitivity. No advancement or suitability conclusion may be based on raw or gross economics alone.

## 11. Trade-level output and audit fields

The canonical policy-trade table is ordered by `(entry_execution_ts, symbol, trade_id, policy_id, cost_scenario)`. At minimum retain:

```text
trade_id, symbol, entry_fixture_id, common_horizon_id
entry_execution_ts, raw_entry_price, entry_price_after_slippage
policy_id, model_id, rank_level, score_cutoff, cutoff_hash
trigger_row_id, trigger_snapshot_ts, trigger_score, trigger_rank
exit_decision_ts, exit_execution_ts, raw_exit_price, exit_price_after_slippage
exit_reason, executable, censor_reason, cost_scenario
raw_price_return, gross_return, net_return
entry_executed_notional, exit_executed_notional
entry_fee_rate, exit_fee_rate, entry_fee_quote, exit_fee_quote
entry_slippage_rate, exit_slippage_rate
entry_slippage_quote, exit_slippage_quote, slippage_cost_quote
total_transaction_cost_quote
holding_duration, fixed_replay_legs, fixed_replay_notional
```

Evaluation-only fields must live in a structurally separate table unavailable to policy code. Policy functions receive only frozen causal row identity, eligibility, score, cutoff, and execution-price access after a decision.

## 12. MFE, giveback, and capture metrics

All price-path quantities use raw prices relative to the raw entry execution price unless explicitly labeled net. Let:

- `common_mfe = max(0, max_valid_high_entry_to_H / entry_price - 1)`;
- `held_mfe_policy = max(0, max_valid_high_entry_to_policy_exit / entry_price - 1)`;
- `realized_raw_return = raw_exit_price / entry_price - 1`;
- `common_capture_gap = common_mfe - realized_raw_return`;
- `held_peak_surrender = held_mfe_policy - realized_raw_return`.

Required metrics, overall and by policy/comparison, symbol, month, quarter, year, trigger status, and cost case where applicable, are:

- realized gross and net return;
- common and held MFE;
- `common_capture_fraction = realized_raw_return / common_mfe` only when `common_mfe >= 0.0050`;
- `held_capture_fraction = realized_raw_return / held_mfe_policy` only when `held_mfe_policy >= 0.0050`;
- common capture gap and held peak surrender, retaining negative values and never clamping;
- `fraction_positive_mfe_surrendered = (common_mfe - realized_raw_return) / common_mfe` only when `common_mfe >= 0.0050`;
- `green_to_red = held_mfe_policy > 0 and realized_raw_return < 0`;
- `common_green_to_red = common_mfe > 0 and realized_raw_return < 0`;
- `preserved_at_least_half_peak = realized_raw_return >= 0.5 * common_mfe` only when `common_mfe >= 0.0050`;
- time to common MFE, time in trade, trigger/exit frequency, and trigger-to-execution delay.

For nonpositive or `0 < MFE < 0.0050`, ratio metrics are null with an explicit denominator reason; counts remain reported. Zero MFE is not assigned a zero or perfect capture ratio. Price-difference metrics remain valid. Report the distribution, mean, median, and relevant quantiles, not only a rate.

## 13. Winner-truncation accounting

For every executed exit earlier than P0, compute only in the evaluation layer:

- realized raw and net exit return;
- `future_max_price_after_exit_to_H`, using observations strictly after the exit point through `H`;
- `remaining_future_mfe_from_entry = future_max_price_after_exit_to_H / entry_price - 1`;
- `opportunity_foregone_vs_exit = future_max_price_after_exit_to_H / raw_exit_price - 1`;
- `net_return_delta_vs_P0` at every cost case;
- whether the accepted post-exit path through `H` subsequently reached entry-relative `+2%`, `+3%`, and `+5%`; and
- whether the early exit missed a subsequently higher raw price by at least `0.5%`, `1%`, `2%`, `3%`, or `5%` relative to its exit price.

If no valid observation exists strictly after exit and no distinct H point is available, future-opportunity fields are null, not zero. Equality reaches a milestone. The entry-relative and exit-relative milestone families must not be conflated.

Report early-exit count, milestone-truncation rates, mean/median/tail opportunity foregone, P0 underperformance rate, and the share and magnitude of baseline large winners reduced by each policy. In particular report policies' outcomes within immutable P0 winner cohorts defined before C5 replay by P0 raw returns of at least `+2%`, `+3%`, and `+5%`. These cohorts are descriptive diagnostics, not optimization strata.

No future-opportunity field, P0 outcome, final MFE, or milestone flag may enter eligibility, scoring, triggering, cutoff formation, or execution.

## 14. Economic metrics

The primary outcome is paired per-trade `C_BASE` net-return difference. Required economic reporting includes:

- arithmetic mean and median net trade return;
- arithmetic expectancy, defined as mean net trade return, with win/loss decomposition reported separately rather than counted as another independent endpoint;
- aggregate fixed-notional net P&L and gross P&L, explicitly not a portfolio equity curve;
- win, zero, and loss rates;
- loss magnitude, downside deviation, 5th and 10th percentiles, worst trade, and expected shortfall below the 10th percentile;
- holding duration and exposure time, defined as the sum of policy holding durations and also as the union of wall-clock intervals with at least one open frozen replay;
- exit/trigger frequency and fixed replay executed legs/notional;
- unresolved/unexecutable counts; and
- symbol, month, quarter, and year dispersion.

Every pooled economic table must include raw-price return, gross return, entry fee, exit fee, entry and exit slippage, total transaction cost, and net return. Required pooled views include trade-weighted five-symbol results, equal-weight-symbol results, and fixed-notional totals. Costs must reconcile from transaction rows to pooled totals exactly, apart from explicitly specified numeric rounding.

Median, win rate, capture, surrender, or faster release of notional cannot override deterioration in mean net expectancy. Aggregate P&L uses the same 1,000 USDT replay notional for every frozen trade and must not imply feasible simultaneous capital. No compounding, overlapping-capital constraint, replacement entry, or reinvestment is permitted. A capital-recycling study requires a separate portfolio allocation contract with chronological cash, concurrency, sizing, affordability, rejected entries, and mark-to-market rules.

### 14.1 Required symbol-specific economic fitness report

In addition to pooled results, produce a separate complete report for each of `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, and `BNBUSDT`, using the unchanged global policy family. For every symbol and policy/intensity, report at minimum:

- total frozen trades, unique trades entering the T2 eligible risk set, policy-triggered exits, unresolved exits, and paired comparison count;
- gross mean trade return and `C_BASE` net mean trade return;
- gross and net expectancy with win/loss decomposition;
- fixed-notional gross and net P&L;
- separately reconciled entry fees, exit fees, slippage, and total transaction costs;
- paired `P1_Qx - P0`, `P1_Qx - G1_Qx`, and `G1_Qx - P0` net-return differences;
- win rate, zero rate, loss rate, downside deviation, 5th/10th percentiles, worst trade, and 10% expected shortfall;
- common and held MFE capture fractions, with valid denominator counts;
- common MFE minus realized exit return, held peak surrender, and positive-MFE surrender fraction;
- at-least-50%-of-common-peak preservation and green-to-red incidence;
- winner-truncation counts, rates, and opportunity-foregone magnitude;
- subsequent entry-relative `+2%`, `+3%`, and `+5%` opportunities foregone after an early exit;
- average and median holding time, trigger/exit frequency, and exposure diagnostics; and
- paired block-bootstrap intervals where the frozen support rule permits them, otherwise point estimates labeled descriptive with the exact insufficiency reason.

Per-symbol suitability is an interpretation of an unchanged common policy, not permission to select or tune a symbol-specific policy. It must be reported independently of the overall strategy classification using the addendum's frozen materiality, safety, and support rules. Assign exactly one addendum-defined label: `SUITABLE FOR FURTHER VALIDATION`, `MIXED / HOLD`, `NOT SUPPORTED`, or `INSUFFICIENT SUPPORT`.

### 14.2 Concentration and universality diagnostics

For Q75 and Q90, and especially the primary `C_BASE` Q75 comparisons, report:

- each symbol's signed contribution in quote currency and percentage contribution to pooled net P&L improvement;
- each symbol's signed contribution to pooled `P1_Qx - P0` improvement;
- each symbol's signed contribution to pooled `P1_Qx - G1_Qx` improvement;
- the largest single-symbol share of each positive total improvement;
- the number and identity of symbols with favorable, zero, and unfavorable point estimates for each primary comparison; and
- trade-weighted and equal-weight-symbol versions so trade-count imbalance is visible.

Signed contribution is the sum of paired fixed-notional net-P&L differences for that symbol on the applicable paired panel. Percentage contribution is defined only when the pooled improvement denominator is strictly positive; otherwise report signed contributions and mark percentage shares and largest-share statistics null with reason `nonpositive_pooled_improvement`. Negative symbol contributions remain negative and may cause favorable symbols' shares to exceed 100%; do not take absolute values or renormalize away opposition.

Overall interpretation must distinguish `BROAD / MULTI-SYMBOL ECONOMIC VALUE` from `CONCENTRATED ECONOMIC VALUE`. A favorable pooled result dominated by one or two symbols cannot be described as universally suitable across the five-symbol universe. The exact breadth/concentration criterion is not justified by the predictive experiment and remains a blocking pre-replay choice in Section 22.

## 15. Primary comparisons and multiplicity

For each rank level, report in this order:

1. `P1_Qx - G1_Qx`: primary attribution comparison;
2. `P1_Qx - P0`: primary practical comparison;
3. `G1_Qx - P0`: required geometry control.

`Q75` is primary; `Q90` is sensitivity. The primary endpoint is paired mean `C_BASE` net-return difference. Co-primary safety evidence is winner truncation and downside-tail behavior. Capture/giveback metrics are mechanistic supporting evidence. Other cost cases and subgroup views are sensitivity/robustness evidence.

No family-wise significance claim is made from the six related contrasts. All are reported; no favorable contrast may be isolated. The two rank levels cannot be pooled, averaged, or selected after results. Symbol/month/quarter results are heterogeneity diagnostics, not separate chances to pass. Per-symbol reporting may support a suitability conclusion about the unchanged common policy, but cannot select different rank levels or create separate policy specifications by symbol.

## 16. Dependence-aware uncertainty

All contrasts are paired by `trade_id`. Repeated snapshots never enter uncertainty as separate observations. A trade is attached to the UTC week containing its immutable entry execution timestamp; the whole trade, all symbols' trades in sampled calendar blocks, and all policy outcomes for a trade remain together.

Primary uncertainty inherits C4's four-entry-week moving-block construction:

1. Build the contiguous UTC entry-week span from minimum to maximum represented week, retaining empty positions.
2. Candidate non-circular blocks are every four-consecutive-week position sequence wholly inside that span.
3. Sample candidate blocks with replacement until at least the observed span length in week positions is accumulated, then truncate excess positions at the end.
4. Select all trades attached to sampled nonempty week positions and preserve integer multiplicity when blocks overlap or repeat; never deduplicate.
5. Compute the paired statistic after applying multiplicity. A trade's policy pair is never split.

Use exactly 2,000 replicates, NumPy-compatible `PCG64`, seed `20240923`, and equal-tailed 95% intervals at `0.025` and `0.975` using Type-7 / NumPy `quantile(..., method="linear")`. If the span is shorter than four weeks or fewer than two nonempty candidate blocks exist, primary uncertainty is unavailable and the comparison is `INSUFFICIENT EVIDENCE`.

Required intervals cover paired mean net return, mean capture gap, mean held surrender, green-to-red indicator difference, preservation indicator difference, early-exit milestone-truncation indicators, holding duration, and selected downside statistics where bootstrap support is adequate. Rates use paired per-trade indicators with explicit eligible denominators.

The same four-entry-week block construction is used within each symbol by restricting each sampled block to that symbol's whole trades; it is not replaced with trade-IID resampling. A per-symbol interval is emitted only when the frozen minimum trade/event/calendar-block support rule is satisfied. When support is inadequate, report the point estimate, denominator, represented weeks/blocks, and `interval_unavailable_low_symbol_support`; do not substitute a naive interval or treat absence of an interval as favorable evidence.

A whole-calendar-month trade-cluster bootstrap with the same seed, replicates, generator, and interval method is the sole predeclared uncertainty sensitivity. It may not replace the primary method based on results. No row-IID, snapshot-IID, ordinary trade-IID, symbol-IID, or naive standard-error interval is allowed.

## 17. Evidence hierarchy and advancement logic

Engineering validity precedes scientific interpretation. Any provenance mismatch, causal leakage, policy divergence from this contract, material paired missingness, unreproducible output, or unavailable primary bootstrap makes the affected result `INSUFFICIENT EVIDENCE` and blocks T3.

Before T2 economic replay, the classification, support, concentration, safety, and Q75/Q90 rules must be frozen without examining C5 economic outcomes. The reviewed pre-execution addendum now supplies those rules, including:

- strict positive `C_BASE` net-return direction with no invented numeric minimum-return hurdle;
- exact P1-versus-P0 and P1-versus-G1 directional and interval categories;
- interval-direction rules for unacceptable truncation, opportunity-foregone, green-to-red, and downside-tail evidence;
- the four-of-five breadth and greater-than-50% concentration rules;
- the 50-distinct-eligible-trade threshold and unavailable-bootstrap behavior; and
- exact common-policy symbol suitability and overall C5 labels.

The addendum deliberately uses direction and paired-interval safety rules rather than inventing an unsupported minimum-return hurdle. None may be inferred from or changed after replay results.

Assign exactly one addendum-defined overall label: `SUPPORTS BROAD ECONOMIC EXIT VALUE`, `SUPPORTS BUT CONCENTRATED`, `MIXED`, `COUNTS AGAINST`, or `INSUFFICIENT EVIDENCE`. The addendum exclusively defines their gates, including `C_S5` survival and the safety-breach rules.

Only an addendum-defined support label may justify T3 consideration. A favorable pooled result alone is insufficient. A concentrated result may support research continuation but cannot authorize or imply universal five-symbol deployment. Per-symbol suitability labels remain separate from the overall label. No overall label itself claims profitability, deployment readiness, or confirmation.

No advancement is allowed merely because MFE capture improves, surrender falls, win rate rises, holding time falls, Q90 is favorable, or one policy has the highest P&L among the five variants. None of the overall outcomes authorizes symbol-specific tuning on the same development data.

## 18. Anti-overfitting controls

The following are prohibited:

- any threshold beyond Q75 and Q90 or any broad/fine cutoff grid;
- choosing between Q75 and Q90 by realized P&L;
- optimizing by symbol, month, quarter, year, entry cohort, cost case, volatility regime, or winner cohort;
- selecting Q75 for one symbol and Q90 for another after seeing economic results;
- using per-symbol diagnostics to tune cutoffs, recalibrate probabilities, refit models, alter features, or silently exclude an unfavorable symbol;
- post-hoc recalibration, probability transformation, score reweighting, persistence, or model blending;
- target, risk-set, label, class-order, feature, cadence, or horizon changes;
- alternative exit families or execution rules added after any economic result is visible;
- cherry-picking gross results, favorable costs, resolved trades, symbols, or periods;
- using future MFE, P0 result, target event, or winner flag in a policy decision;
- treating snapshot rows as independent evidence;
- changing any frozen addendum threshold, direction, category, denominator, or safety rule after replay begins; or
- presenting the best policy among many attempts without a complete immutable attempt ledger.

Every attempted run, including failed and invalid runs, must be recorded with configuration hash, code hash, input-manifest hash, start/end timestamp, purpose, status, and output hashes. A scientifically material amendment creates a new contract version and policy IDs; it cannot overwrite C5 V1.

It is scientifically permissible to conclude after the common-policy experiment that the unchanged policy appears suitable for some symbols and unsuitable for others. That conclusion is deployment-fitness diagnosis, not optimization. Any future symbol-specific threshold, calibration, model, feature set, or policy family is a separate experiment requiring separate temporal governance, a new contract, and evidence not reused for both tuning and confirmation.

## 19. Staged execution

### T1 — policy definition and mechanical implementation only

After separate authorization, reconcile upstream hashes, freeze numeric rank cutoffs without joining economic outcomes, implement the five policies, schemas, causal guards, cost arithmetic, synthetic tests, and deterministic fixtures. Only synthetic hand-computable paths may be replayed. T1 must not calculate historical returns, P&L, MFE, or economic metrics.

### T2 — development-era economic replay

Only after T1 acceptance, addendum review/hash, upstream provenance reconciliation, and complete frozen-prediction coverage, replay the frozen five-policy family on the authorized 2024/2025 development material. Produce the complete metric panel, paired uncertainty, attempt ledger, and one addendum-defined evidence label. No policy is selected by best result.

### T3 — final policy freeze

Only if T2 is `SUPPORTS BROAD ECONOMIC EXIT VALUE` or `SUPPORTS BUT CONCENTRATED`, a separately reviewed freeze may nominate `P1_Q75_EXIT_V1`. Q90 is sensitivity only and cannot replace Q75 in C5 V1. A concentrated result cannot support universal five-symbol use. Freeze policy/code/configuration/input hashes and all execution/cost semantics. No refit or threshold change is allowed.

### T4 — possible sealed confirmation

Not authorized here. It requires a separate contract and explicit approval after T3. No development-era choice may occur during T4.

## 20. Reproducibility requirements

Future C5 artifacts must include:

- contract and approved-addendum SHA-256 hashes;
- authoritative upstream artifact paths, semantic versions, byte hashes, and reconciliation results;
- exact five-policy registry and machine-readable configuration;
- score class order, formula, source-row IDs/count/hash, score-vector hashes, quantile method, numeric cutoffs, and cutoff hashes;
- source/code/environment/library hashes and versions;
- canonical tables, schemas, row order, cost parameters, exclusion reasons, and output hashes;
- bootstrap generator, seed, replicate count, block length/construction, sampled block indices, multiplicities, replicate vectors, interval method, and configuration/output hashes;
- complete attempt ledger and command log; and
- confirmation that sealed data was neither enumerated nor accessed.

Two clean runs from identical accepted inputs, code, and configuration must reproduce byte-equivalent core policy-trade/evaluation tables and identical bootstrap replicate sequences and metric values. Timestamp-bearing manifests may differ only in declared nonsemantic fields. Earlier decisions must be invariant to mutation/appending of later synthetic data.

## 21. Required tests before historical replay

T1 must pass automated tests for:

- exact T2 eligibility at `G_t == 1%`, `R_t == 0`, and `C_t == D2`, including correct inclusive/strict boundaries;
- no action outside the T2 risk set and no action after a policy exit or at/after `H`;
- score formula, class order, direction, no-event coefficient zero, and G1/P1 mapping identity;
- Type-7 Q75/Q90 quantiles, inclusive ties, global rather than subgroup cutoffs, and stable cutoff hashes;
- completed five-minute availability, future-append invariance, and absence of same-bar execution;
- exact next-minute-open execution, P0 precedence at an equal endpoint, gap/missing-next-minute rejection, and no gap skipping;
- first-trigger-only behavior and exact fallback to immutable P0;
- G1 and P1 policy code differing only by frozen prediction source and model-specific cutoff;
- prevention of policy access to targets, future paths, P0 outcomes, final MFE, or evaluation tables;
- adverse buy/sell slippage, two fee legs, raw/gross/net separation, and all four cost cases;
- exact 10 bp entry and exit fees on their respective executed notionals, separate fee/slippage cash fields, total-cost reconciliation, and approximate 20/24/30/40 bp normal-round-trip scenario labels;
- every transaction being charged independently in a synthetic multi-transaction ledger test, without authorizing a multi-exit C5 policy;
- paired exclusion and common-panel sensitivity logic;
- common MFE identical across policies and held MFE correctly policy-specific;
- capture/giveback formulas, null denominators below 0.5%, exact validity at 0.5%, negative values retained, and no clamping;
- green-to-red and half-peak-preservation semantics;
- future opportunity beginning strictly after early exit and exact +2%/+3%/+5% inclusive milestone flags;
- one synthetic rise-then-fall path where an early exit preserves gain and one path where it truncates a later large winner;
- fixed-entry invariance and no re-entry/capital recycling;
- whole-trade four-entry-week bootstrap attachment, all-symbol block preservation, multiplicity, seed, replicate count, and Type-7 endpoints;
- per-symbol reporting with unchanged global cutoffs, symbol-restricted whole-trade blocks, and explicit low-support interval suppression;
- signed symbol contribution reconciliation to pooled P&L differences, including negative contributions and null shares for nonpositive pooled improvement;
- deterministic ordering, IDs, hashes, attempt ledger, and byte-equivalent reruns; and
- a synthetic sealed-boundary guard that rejects equality and later timestamps without reading any external data.

Historical replay is forbidden until an independent test report and configuration hash are reviewed.

## 22. Pre-execution resolutions and remaining input gates

The reviewed pre-execution addendum resolves former items 3–9: economic direction/materiality treatment, winner/downside safety, concentration and breadth, Q75/Q90 governance, minimum symbol support, symbol-level comparison criteria, and low-support bootstrap interpretation. Those frozen addendum rules replace post-replay discretion.

The following non-economic input/provenance gates remain to be satisfied mechanically before their stated stage:

1. **Authoritative C4 hashes and prediction coverage.** The accepted manifest locations and hashes for frozen preprocessing, G1/P1 models, 2024 cutoff-source predictions, and locked 2025 predictions must be supplied and reconciled. A prediction-row coverage audit must establish whether accepted predictions exist for every causally eligible policy snapshot, including rows whose future T2 label was censored or otherwise unavailable. The audit may inspect identities/counts/hashes only, not economic paths or outcomes.
2. **Frozen prediction coverage.** The addendum requires complete accepted coverage of causally eligible policy snapshots. Unexplained absence blocks replay; predictions cannot be regenerated, imputed, or converted post hoc into no-action states.

The classification design is now frozen and ready for T1 under separate authorization. Items 1 and 2 are mandatory T1 acceptance gates and block T2 historical replay if unsatisfied. They are provenance checks, not open economic-classification choices. The addendum may not be altered to add policies, change the score or quantiles, change execution, tune by symbol, or respond to economic results.

## 23. Required end report for any future authorized execution

The future delivery must report the exact contract/addendum hashes; all upstream hashes; the five variants; matched G1/P1 controls; activation and execution semantics; itemized transaction costs; complete pooled and five separate symbol economic, MFE/giveback, and winner-truncation panels; paired bootstrap results; symbol contributions and concentration classification; independent per-symbol suitability labels; heterogeneity; exclusions; attempt ledger; advancement label and criteria; development-era limitation; sealed-period compliance; and reproducibility evidence.

Creation of this contract itself ends after documentation validation. It performs no C5 implementation, exit simulation, economic replay, or P&L calculation.
