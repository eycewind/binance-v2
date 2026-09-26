# C6 — Simple T2 Exit Controls Economic Experiment Contract

Status: **DESIGN FROZEN; NOT AUTHORIZED FOR IMPLEMENTATION OR EXECUTION**.

This document preregisters a future C6 development-era economic experiment. Creating and hashing this document does not authorize policy implementation, historical replay, return or P&L calculation, MFE or winner-truncation calculation, prediction generation, threshold or delay search, or access to sealed confirmation data.

Target repository: `/media/ata/Data/personal/binance-v2`

## 1. Scientific question and hypotheses

C5 found a large economic improvement for `G1_Q75_EXIT_V1` and `P1_Q75_EXIT_V1` relative to `P0_HELD_V1` on the accepted replay-authorized development population, while P1 did not show robust economic improvement over G1. C6 does not recalculate or re-adjudicate that result. It asks:

> How much of the accepted C5 improvement is explained by reaching T2 and exiting generally early, and how much requires model-dependent selection or timing?

The descriptive trigger diagnostics supplied before this contract—439 trades, 38,745 eligible snapshots, predominantly ordinal-one/two triggers, short elapsed time to trigger, G1/P1 agreement, path lengths, and year differences—motivate only the two fixed simple controls below. They are not economic evidence.

The frozen hypotheses, all stated for paired mean `C_BASE` net return, are:

- **H1 — simple early-T2 value (primary gate):** `EXIT_FIRST_T2 - P0_HELD_V1 > 0`. This tests whether entering the T2 state and exiting at its first causal opportunity has economic value relative to holding to P0.
- **H2 — model value beyond the primary simple clock (second gate):** `G1_Q75_EXIT_V1 - EXIT_FIRST_T2 > 0`. This tests whether G1-dependent selection/timing adds value beyond an immediate T2 exit.
- **H3 — selection value beyond timing-matched randomness (third gate):** `G1_Q75_EXIT_V1 - RANDOM_TIMING_CONTROL > 0`. This tests whether the association between G1 state and the trade receiving a particular timing/fallback label adds value beyond the same broad G1 timing propensity assigned without G1 state.
- **H4 — second-snapshot diagnostic:** report `EXIT_SECOND_T2 - P0_HELD_V1` and `G1_Q75_EXIT_V1 - EXIT_SECOND_T2`. H4 is a prespecified diagnostic motivated by the accepted ordinal distribution. It is not a co-primary alternative and cannot rescue a failed H1, H2, or H3 gate.
- **H5 — coin-flip negative control:** if validly implemented, report `COIN_FLIP_CONTROL - P0_HELD_V1` and `G1_Q75_EXIT_V1 - COIN_FLIP_CONTROL` descriptively. It is not in the confirmatory hierarchy and cannot rescue it.

Positive means the first-named policy has higher paired mean net return. The null at every formal gate is a difference less than or equal to zero. No new numeric materiality margin is introduced: direction, the frozen interval rules, cost survival, safety, and consistency are reported separately.

## 2. Immutable upstream policies and inputs

C6 includes exactly these accepted C5 outputs without rerunning, redefining, rescoring, or reconstructing them:

- `P0_HELD_V1`;
- `G1_Q75_EXIT_V1`;
- `P1_Q75_EXIT_V1`.

Their policy-trade rows, exits, costs, and evaluation fields must be copied or joined from the accepted canonical C5 trade table by exact trade, policy, and cost-case identity. The authoritative C5 contract, addendum, prediction-population amendment, accepted manifests, and canonical-table hashes govern their meanings. A future C6 readiness review must record those exact accepted hashes; this design document does not inspect data to supply them.

The accepted C4/C5 T2 eligibility, completed five-minute cadence, row identity/order, availability, causal features, immutable entry, P0 common horizon `H`, execution-price convention, missing-minute rules, and complete-path authorization remain unchanged. No score is computed for a simple or randomized control. C6 must not alter any accepted C5 row.

## 3. Population and experimental unit

The population is exactly the accepted C5 `replay_authorized_complete_path` population of **439 frozen trades and 38,745 T2-eligible snapshots** from 2024 and 2025. There is no population expansion, exclusion based on outcomes, or return to raw/incomplete T2 paths.

The experimental unit is one whole frozen trade. All snapshots, the entry, every policy outcome, symbol, entry year, entry week, and common horizon remain attached to that trade. Earlier exit never creates a replacement entry, frees capital for a simulated new position, changes size, or changes the opportunity set.

Mandatory views are pooled, calendar-entry-year 2024, calendar-entry-year 2025, and each of `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, and `BNBUSDT`. Policies and controls are identical across years and symbols.

## 4. Common decision and execution semantics

For a trade, let its accepted replay-authorized T2 path be the strictly ordered sequence `(r_1, ..., r_L)`, where `L >= 1` and ordinal one is the first replay-authorized completed five-minute T2-eligible snapshot. The snapshot timestamp is the accepted completed-boundary timestamp.

When a control is assigned ordinal `k <= L`, its decision is at `r_k` and it exits at the raw open of the immediate next one-minute interval, using exactly the accepted C5 execution, P0-precedence, missing/invalid-open, paired-unresolved, and cost rules. A next-minute execution not strictly before the immutable P0 execution point cannot replace P0. No snapshot close or later substitute fill is allowed.

When a control receives the P0 fallback label, or its frozen rule below requires fallback, it uses exactly the accepted canonical `P0_HELD_V1` exit row. A control never examines economic outcomes, future prices, MFE, labels, accepted P0 return, or winner status to decide.

## 5. Exact prospective controls

### 5.1 `S1_EXIT_FIRST_T2_V1`

At `r_1`, exit at the immediate next one-minute open under Section 4. It uses no model, score, prediction, threshold, or random number. Every population trade has at least one authorized T2 snapshot by construction.

### 5.2 `S2_EXIT_SECOND_T2_V1`

If `L >= 2`, decide at `r_2` and exit at the immediate next one-minute open under Section 4. If `L = 1`, deterministically fall back to the immutable canonical P0 exit. This fail-safe avoids inventing an unavailable snapshot or a new delay and is consistent with the common P0 horizon. It uses no model, score, prediction, threshold, or random number.

### 5.3 `S3_G1_TIMING_PERMUTATION_V1`

This is an ensemble of fixed timing-label randomizations, not one selected seed. Its purpose is to retain G1's observed timing propensity while breaking which same-year, same-symbol trade receives each G1 timing label.

For every trade, derive from the **accepted canonical C5 policy output only** a label:

```text
g1_timing_label = accepted G1 trigger ordinal k, if G1 executed before P0;
                  P0_FALLBACK, otherwise.
```

This derivation reads policy identity/timing fields, not returns or future evaluation fields. Partition trades into the ten fixed strata `(entry calendar year, symbol)`. Within each stratum, permute the complete multiset of G1 timing labels among whole recipient trades, subject to the compatibility rule that an ordinal `k` may be assigned only when recipient path length `L >= k`; `P0_FALLBACK` is compatible with every recipient. This preserves exactly, within every year-symbol stratum and every randomization, the count of each G1 trigger ordinal and the P0-fallback count. It therefore preserves broad timing, intervention frequency, year, and symbol structure without using economics.

The constrained permutation algorithm is frozen as follows:

1. Order donor labels by descending ordinal, with `P0_FALLBACK` after all numeric labels; break donor ties by canonical `trade_id`. Order recipients by canonical `trade_id`.
2. For each randomization, draw one independent `uint64` priority for every compatible donor-recipient edge using NumPy-compatible `PCG64`, consuming draws in assignment order, then the fixed stratum order below, donor order, and recipient order. Incompatible edges consume no draw.
3. Find a complete minimum-cost bipartite assignment within each stratum, where edge cost is its drawn priority interpreted as an unsigned integer and total costs are summed without integer overflow. Resolve any exact total-cost tie by the lexicographically smallest recipient-ordered vector of donor `trade_id` values.
4. If no complete compatible assignment exists, the randomization and C6 readiness fail closed; do not clip, resample an ordinal, convert it to fallback, move it across strata, or inspect economics. The identity assignment proves feasibility when canonical labels came from the same complete paths, so failure indicates invalid inputs or implementation.
5. Assigned numeric label `k` exits at recipient `r_k` under Section 4; assigned `P0_FALLBACK` uses canonical P0.

Self-assignment is allowed because forbidding it can make constrained strata infeasible and would change the target randomization distribution. Donor identity is retained for audit. The control is a timing-label permutation, not a permutation of prices, exits, returns, or entire outcome rows.

Generate exactly **1,000** assignments with NumPy-compatible `PCG64`, master seed **`20240924`**. Process strata in the fixed order `(2024, 2025)` then `(BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT)`, and assignments in integer order `0..999`. The seed and ensemble size are chosen prospectively and may not be changed, filtered, or supplemented after economics. All assignments are reported; no best, median-looking, or otherwise favorable assignment becomes the control.

The primary random-control estimand is the G1-minus-control paired mean difference averaged equally over all 1,000 assignments. For nonlinear metrics, compute the metric within each assignment first and then average the 1,000 assignment-level values; do not compute a nonlinear metric from averaged exits or prices.

### 5.4 `S4_FIRST_T2_COIN_FLIP_V1`

This optional-but-preregistered negative control makes exactly one decision at `r_1`. Draw `B ~ Bernoulli(0.5)` independently by trade using NumPy-compatible `PCG64`, seed **`20240926`**, in canonical population order `(entry_execution_ts, symbol, trade_id)`. If `B = 1`, exit at `r_1` under Section 4. If `B = 0`, commit once to canonical P0; do not flip again at later snapshots.

The one-time interpretation cleanly tests an arbitrary state-unaware intervention decision without turning longer paths into more chances to exit. Probability 0.5 is fixed and untuned. Only the single frozen assignment is used because S4 is intuitive descriptive context, not a formal gate.

## 6. Short paths and incompatibility

- S1 always has ordinal one because population membership requires at least one eligible snapshot.
- S2 uses P0 for `L = 1`.
- S3 never assigns `k > L`; constrained matching preserves the donor-label multiset exactly. There is no clipping to `L`, substitution with first/last snapshot, rejection based on economics, cross-stratum borrowing, or conversion to P0.
- S4 acts only at ordinal one and therefore has no short-path incompatibility.

Any disagreement between recorded `L`, ordered eligible rows, or canonical G1 ordinal is an engineering/provenance failure and yields `INSUFFICIENT EVIDENCE`; it is not repaired during economic replay.

## 7. Costs and accounting

Use exactly the accepted C5 cost cases and ledger definitions:

| ID | Entry fee | Exit fee | Adverse entry slippage | Adverse exit slippage | Role |
|---|---:|---:|---:|---:|---|
| `C0` | 0 bp | 0 bp | 0 bp | 0 bp | frictionless diagnostic |
| `C_BASE` | 10 bp | 10 bp | 2 bp | 2 bp | primary |
| `C_S5` | 10 bp | 10 bp | 5 bp | 5 bp | sensitivity |
| `C_S10` | 10 bp | 10 bp | 10 bp | 10 bp | stress sensitivity |

Use the accepted fixed 1,000 USDT replay notional and exact executed-notional fee/slippage accounting. Preserve raw price return, gross return, entry/exit fees, entry/exit slippage, total transaction cost, and net return separately. This is fixed-notional replay, not a portfolio equity curve; there is no compounding, capital recycling, concurrency optimization, or replacement entry. `C_BASE` alone governs the hierarchy. Other cases cannot rescue it.

## 8. Frozen comparison hierarchy and multiplicity

The primary endpoint at every gate is paired mean `C_BASE` net-return difference. Apply this fixed gatekeeping order:

1. **Gate 1 (H1):** `S1_EXIT_FIRST_T2_V1 - P0_HELD_V1`.
2. **Gate 2 (H2):** only if Gate 1 has `STRONG_POSITIVE` evidence, formally test `G1_Q75_EXIT_V1 - S1_EXIT_FIRST_T2_V1`.
3. **Gate 3 (H3):** only if Gates 1 and 2 both have `STRONG_POSITIVE` evidence, formally test `G1_Q75_EXIT_V1 - S3_G1_TIMING_PERMUTATION_V1` using the assignment-averaged estimand and its primary market-sampling interval.

`STRONG_POSITIVE` means point estimate `> 0` and the applicable equal-tailed 95% interval is entirely `> 0`. An interval touching zero does not pass. Fixed-sequence gatekeeping controls selection among the three claims without choosing the most favorable comparison.

Always report, but never use to reopen or rescue a failed gate:

- S2 versus P0 and G1 versus S2;
- each gate's point estimate and interval even when not formally reached, clearly labeled descriptive;
- the accepted C5 G1-versus-P0 and P1-versus-G1 results as immutable context only;
- P1 versus every new control as descriptive context only; and
- S4 comparisons, if its preregistered implementation is valid.

No family-wise claim is made for diagnostic metrics, costs, years, or symbols. They are fully disclosed and cannot become alternative primary endpoints.

## 9. Metrics

Reuse accepted C5 definitions and denominator/null rules without modification. For every policy/control and required contrast, report where applicable:

- `C_BASE` arithmetic mean net trade return (net expectancy) and paired difference;
- raw and gross return; median net return; win/zero/loss decomposition;
- fixed-notional gross and net P&L, explicitly not a portfolio backtest;
- common capture gap, held peak surrender, common/held capture fractions, and at-least-50%-of-common-peak preservation;
- green-to-red incidence;
- holding duration, summed exposure, union wall-clock exposure, trigger/exit/fallback frequency, executed legs/notional, and unresolved counts;
- winner truncation, immutable P0 `+2%`, `+3%`, and `+5%` winner cohorts, subsequent opportunity-foregone rates and magnitudes;
- downside deviation, loss magnitude, 5th/10th percentiles, worst trade, and 10% expected shortfall; and
- entry/exit fees, entry/exit slippage, and total costs under `C0`, `C_BASE`, `C_S5`, and `C_S10`.

Future information is structurally isolated and used only for evaluation. It may never enter eligibility, timing-label construction, permutation compatibility, coin flips, decisions, execution, or exclusions. Common-horizon metrics remain identical in opportunity definition across policies; policy-held metrics end at that policy's exit. Negative gaps/surrenders are retained and denominators are explicit.

## 10. Market/trade sampling uncertainty

All contrasts are paired by whole `trade_id`; snapshot rows are never independent observations. Reuse exactly the accepted C5 primary four-entry-week moving-block bootstrap:

1. attach each whole trade to the UTC week of immutable entry execution;
2. retain the contiguous week span including empty positions;
3. form every non-circular four-consecutive-week candidate block;
4. sample blocks with replacement until the observed span length is reached, truncate excess week positions, and retain integer trade multiplicity without deduplication; and
5. keep all policy/control outcomes and all symbols for a selected trade together.

Use exactly **2,000** replicates, NumPy-compatible **`PCG64`**, seed **`20240923`**, and equal-tailed 95% endpoints at 0.025/0.975 using Type-7 / NumPy `quantile(..., method="linear")`. Reuse the accepted whole-calendar-month trade-cluster bootstrap as the sole uncertainty sensitivity, with the same replicate count, RNG family, seed, and interval method. It cannot replace the primary block result.

For ordinary deterministic contrasts, bootstrap the paired statistic directly. For S3's primary market-sampling interval, within every bootstrap replicate compute each of the 1,000 assignment-specific paired statistics using the same sampled trade multiplicities, then average equally across assignments. This interval estimates market/trade sampling uncertainty for the assignment-averaged random-control estimand.

If the accepted C5 block-support conditions fail, the affected interval is unavailable and evidence is `INSUFFICIENT`; no row-IID, snapshot-IID, ordinary trade-IID, symbol-IID, naive standard error, or substitute interval is allowed.

## 11. Random-control assignment uncertainty

Random assignment uncertainty must be shown separately from market/trade uncertainty:

- At the observed 439-trade panel, report all 1,000 assignment-specific G1-minus-S3 primary-endpoint estimates, their mean, standard deviation, min/max, and Type-7 2.5%, 25%, 50%, 75%, and 97.5% quantiles.
- Report the fraction of assignments with a positive G1-minus-S3 point estimate. This is descriptive randomization stability, not a p-value and not a separate gate.
- Report the Section 10 market-sampling interval around the assignment-averaged estimand.
- Report a combined assignment-plus-market sensitivity: for each bootstrap replicate `b`, select assignment index `J_b` from NumPy-compatible `PCG64` with frozen seed **`20240925`**, uniformly from `0..999` with replacement, and compute the paired statistic for bootstrap sample `b` under assignment `J_b`; form the Type-7 equal-tailed 95% interval across the 2,000 values. This sensitivity cannot replace the primary market interval or rescue Gate 3.

All assignment tables, edge priorities or reproducible priority-stream positions, donor-recipient mappings, compatibility checks, seeds, generator versions, and hashes must be retained. No assignment may be discarded because of its economic result. For the frozen conflict rule, assignment evidence supports Gate 3 only when both (a) the observed-panel Type-7 95% assignment interval and (b) the combined assignment-plus-market 95% interval are entirely above zero. If Gate 3's primary market interval passes but either auxiliary interval touches or crosses zero, the overall interpretation is `MIXED`; these auxiliary intervals cannot independently make Gate 3 pass.

## 12. Year, symbol, and support reporting

Report pooled, 2024, 2025, and each of the five named symbols separately for every policy, control, primary contrast, and mandatory diagnostic. Also report trade-weighted pooled and equal-weight-symbol summaries so symbol-count imbalance is visible.

The year split is diagnostic only. The large accepted 2024/2025 immediate-trigger difference justifies stratification of S3; it does not authorize year-specific policies, thresholds, probabilities, or interpretation gates. Symbol stratification in S3 prevents the random control from borrowing a symbol's timing-label distribution from another symbol; it does not authorize symbol-specific rules.

Reuse the accepted C5 support principle: fewer than 50 distinct replay-authorized trades in a symbol makes formal symbol uncertainty and suitability `INSUFFICIENT SUPPORT`; still report counts and descriptive point estimates and retain those trades in pooled analysis. Neither year must separately reach 50. Five symbols and two years are heterogeneity views, not independent replications or additional chances to pass.

## 13. Frozen evidence labels and interpretation

For each reached gate, classify its primary endpoint:

- `STRONG_POSITIVE`: point estimate `> 0` and 95% primary interval entirely `> 0`;
- `DIRECTIONAL_ONLY`: point estimate `> 0` and interval includes/touches zero;
- `NULL_OR_OPPOSING`: point estimate `<= 0` and interval is not entirely below zero;
- `STRONG_NEGATIVE`: interval entirely `< 0`;
- `INSUFFICIENT`: required engineering, pairing, or interval validity is unavailable.

Then assign exactly one overall C6 interpretation in this precedence order:

1. **`INSUFFICIENT_EVIDENCE`** — any validity failure prevents Gate 1, or a reached gate lacks its required primary interval.
2. **`COUNTS_AGAINST_SIMPLE_T2_EXPLANATION`** — Gate 1 is `STRONG_NEGATIVE` or `NULL_OR_OPPOSING`. H2/H3, S2, S4, P1, and secondary metrics cannot rescue the failed primary gate.
3. **`SIMPLE_T2_EXIT_EXPLAINS_OBSERVED_VALUE`** — Gate 1 is `STRONG_POSITIVE`, but Gate 2 is not `STRONG_POSITIVE` and is not `STRONG_NEGATIVE`. This means simple immediate T2 exit has clear value and incremental G1 value is not established; it does not claim statistical equivalence or a numeric percentage explained.
4. **`MIXED`** — Gate 1 is `DIRECTIONAL_ONLY`; or Gate 1 is `STRONG_POSITIVE` and any of these holds: Gate 2 is `STRONG_NEGATIVE`; Gate 3 is reached but `STRONG_NEGATIVE`; either frozen S3 auxiliary interval fails to remain entirely above zero when Gate 3's primary interval passes; or mandatory year/symbol/safety evidence contains a frozen adverse-interval breach while the primary hierarchy is otherwise favorable.
5. **`MODEL_TIMING_ADDS_ECONOMIC_VALUE`** — Gates 1 and 2 are `STRONG_POSITIVE`, while reached Gate 3 is `DIRECTIONAL_ONLY` or `NULL_OR_OPPOSING`. This establishes G1 value beyond exiting immediately, but not selection value over timing-matched random assignment.
6. **`MODEL_SELECTION_BEATS_RANDOM_TIMING`** — Gates 1, 2, and 3 are all `STRONG_POSITIVE`, both frozen S3 auxiliary intervals are entirely above zero, and no mandatory adverse safety breach applies. This is the strongest C6 attribution label.

These labels are mutually exclusive by precedence. A favorable S2, S4, P1, cost sensitivity, subgroup, capture, surrender, holding-time, or P&L result cannot change the label dictated by the hierarchy. `SIMPLE_T2_EXIT_EXPLAINS_OBSERVED_VALUE` deliberately avoids an unsupported “most” percentage; any descriptive fraction of the accepted C5 difference must be reported without becoming a decision threshold.

Mandatory safety evidence reuses accepted C5 interval directions for 10% expected shortfall, green-to-red, preservation, milestone truncation, and opportunity foregone. No new numeric winner-truncation or downside threshold is invented. A safety interval entirely adverse to the candidate claim is a breach; touching zero is not. All point estimates remain visible.

## 14. Stopping and advancement logic

C6 stops formal testing at the first hierarchy gate that is not `STRONG_POSITIVE`; later contrasts remain prespecified descriptive results only. Analysis does not stop data reporting: the complete frozen panel, diagnostics, costs, years, symbols, and randomization distribution must still be disclosed.

Only `MODEL_SELECTION_BEATS_RANDOM_TIMING` supports the narrow conclusion that G1 state-dependent assignment adds value beyond timing-matched randomness. `MODEL_TIMING_ADDS_ECONOMIC_VALUE` supports further research on model-dependent timing but not a selection-skill claim. `SIMPLE_T2_EXIT_EXPLAINS_OBSERVED_VALUE` supports considering the simple control for separately governed validation, not retroactive replacement of C5 or deployment. `MIXED`, `COUNTS_AGAINST_SIMPLE_T2_EXPLANATION`, and `INSUFFICIENT_EVIDENCE` do not advance a C6 model-selection claim.

No label authorizes deployment, live/paper trading, access to sealed data, policy refit, threshold/delay search, or symbol/year-specific adoption. `C_S5` and `C_S10` survival must be disclosed but cannot upgrade a `C_BASE` label; failure under either is a limitation. No secondary control can rescue a failed primary hypothesis.

## 15. Anti-overfitting and reproducibility safeguards

The following are prohibited:

- any delay grid, including trying ordinals 1, 2, 3, 4, 5, and selecting by economics;
- any additional fixed delay without a new prospective contract and new temporal governance;
- changing S2's one-snapshot fallback, S3 strata/compatibility/algorithm/ensemble size/seeds, or S4 probability/one-time behavior after economics;
- selecting one S3 assignment, changing seeds, increasing randomizations selectively, or rejecting compatible mappings based on results;
- score thresholds, model refits, recalibration, prediction generation, alternate scores, or use of P1 to redefine G1 controls;
- tuning by year, symbol, month, quarter, cost, path length, trigger status, volatility, winner cohort, or outcome;
- using future path, economic output, P0 result, MFE, target, or winner flag in policy/control construction;
- changing population, costs, execution, pairing, endpoint, bootstrap, interval, support, safety, or interpretation rules after replay;
- cherry-picking gross results, favorable costs/subgroups/assignments, resolved trades, or secondary metrics; and
- treating repeated snapshots as independent or claiming capital recycling.

Before any separately authorized historical replay, implementation would require synthetic-only tests for exact ordinals, S2 fallback, P0 precedence, missing opens, constrained-label conservation and compatibility, infeasibility fail-closed behavior, canonical ordering, RNG streams, S4 one-time behavior, sealed-boundary rejection, cost arithmetic, whole-trade bootstrap attachment, and byte-reproducible reruns. That implementation is outside this contract-design task.

Future authorized artifacts must record accepted input/canonical-table hashes, this contract hash, environment/library versions, exact configuration, policy/control registry, every random mapping and hash, all bootstrap samples/multiplicities, output hashes, and an immutable attempt ledger. Any scientifically material amendment creates a new contract version and cannot use observed C6 economics to choose its rules.

## 16. Sealed-data rule

The 2026 confirmation period remains sealed. C6 design, implementation, replay, randomization, validation, hashing, and reporting may not enumerate, list, open, inspect, count, hash, infer from metadata, or consume any 2026 market row, partition, file, directory, manifest entry, prediction, outcome, or derived artifact.

Only a synthetic unit-test literal may express the sealed boundary; it must contain no real market observation or derived value. A future confirmation requires a separate reviewed contract and explicit authorization after a complete freeze. Any sealed-data contact invalidates C6 and must be reported; it cannot be cured by deleting the resulting output.

## 17. Contract freeze and scope termination

The SHA-256 reported at delivery is the hash of the exact bytes of this file after final validation. Any later byte change invalidates that hash and requires explicit review and a new hash before implementation could be considered.

This task terminates after contract creation, SHA-256 calculation, `git diff --check`, and read-only `git status`. It performs no C6 implementation or execution and makes no economic calculation.
