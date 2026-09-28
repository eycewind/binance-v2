# C8 PRE-T2 Timescale Adequacy Contract

Status: prospectively frozen before model evaluation on 2026-09-28. C8 is a
development-only prognosis study. It is not a trading policy, does not compute
P&L, does not define an exit, and may not read any path containing the token
`2026`.

## Population, endpoint, and candidates

The population is the 2,199 frozen C2 original E1 entries (1,093 in 2024 and
1,106 in 2025) and their immutable P0 timestamps. The terminal endpoint reuses
the C7 causal first-executable-T2 definition exactly: the first completed,
wholly-post-entry UTC-aligned 5-minute state strictly before P0 for which
running peak gain is at least 1%, close is positive versus entry, and close is
strictly above `(entry + running_peak) / 2`, with a valid immediate-next-minute
open strictly before P0. `T2_FIRST=1`; otherwise `P0_FIRST=0`. Expected totals
are 845 and 1,354. Prediction availability and economic fields are forbidden.

Exactly five architectures are compared, recording absolute resolutions:

| ID | completed slow context | completed state/update |
|---|---:|---:|
| A | 30m | 5m |
| B | 60m | 5m |
| C | 120m | 5m |
| D | 60m | 10m |
| E | 60m | 15m |

Rows occur at completed UTC-aligned fast boundaries strictly after entry and
strictly before the terminal T2/P0 timestamp. Aggregates must be contiguous,
complete, and end no later than the row timestamp. No fill, partial bar,
same-bar future, terminal-or-later value, or cross-symbol borrowing is allowed.

## Frozen common feature schema

Lookback counts are identical for every architecture. Let `S` be the slow bar
duration, `F` the fast duration, `C[k]` the close of the kth most recent
completed bar (`k=0` current), `r[k]=C[k]/C[k+1]-1`, `range[k]=(H-L)/O`,
and `activity[k]=quote_volume[k]`. Sample standard deviation uses `ddof=1`.
All ratios require finite positive denominators.

M1 slow features:

* `slow_return_1 = C[0]/C[1]-1`
* `slow_return_3 = C[0]/C[3]-1`
* `slow_return_6 = C[0]/C[6]-1`
* `slow_volatility_12 = sd(r[0:12])`
* `slow_range_ratio = range[0]/median(range[1:13])`
* `slow_activity_ratio = activity[0]/median(activity[1:13])`
* `slow_close_vs_sma12 = C[0]/mean(C[0:12])-1`
* `slow_sma12_slope = mean(C[0:12])/mean(C[1:13])-1`

M2 adds these fast/state features, using the same formulas at every `F`:

* `fast_return_1`, `fast_return_3`, `fast_return_6` analogous to slow returns
* `fast_volatility_12`, `fast_range_ratio`, `fast_activity_ratio` analogous
  to slow features
* `path_efficiency = current_return / sum(abs(consecutive completed-fast-bar
  close returns since the first wholly-post-entry fast bar))`, zero only when
  both numerator and denominator are zero
* `current_return = latest completed fast close / entry - 1`
* `running_mfe = max(entry, all completed source-minute highs before row) /
  entry - 1`
* `drawdown_from_running_peak = latest fast close / running_peak - 1`
* `distance_to_t2_barrier = latest fast close / ((entry+running_peak)/2)-1`
* `elapsed_log1p_minutes = log(1 + elapsed whole minutes)`
* `fast_slow_agreement = sign(fast_return_3) * sign(slow_return_3)`

The model also includes four fixed symbol indicators with BTCUSDT as reference.
Missing required history makes a row ineligible; it is never imputed. The label
is constructed separately and is not passed to feature construction.

## Models and fitting

M0 is the training trade-weighted prevalence. M1 and M2 are binary logistic
regressions with one fixed specification: training-only weighted mean/standard
deviation scaling of continuous features; symbol indicators unscaled; L2
penalty `C=1.0`; intercept unpenalized; deterministic LBFGS, maximum 1,000
iterations, tolerance `1e-9`, no class weights, no model or hyperparameter
search. Each training row has weight `1 / rows_for_its_trade`, normalized only
by the solver if internally required. Evaluation proper scores likewise average
within trade first and then equally across trades. Snapshot count is never N.

## Development, uncertainty, and decisions

2024 uses two fixed expanding chronological folds: A trains entries in H1 and
validates Q3; B trains entries through Q3 and validates Q4. A training trade is
retained only when its terminal event is strictly before the validation entry
cutoff. Whole trades remain intact. Preprocessing is fit on retained training
rows only. Architecture ranking uses pooled out-of-fold 2024 predictions only.

C8 seed `20260928` is frozen here. Paired uncertainty uses 2,000 four-entry-week
moving-block bootstrap replicates over whole validation trades, preserving all
rows and paired model/architecture predictions for a sampled trade. Equal-tail
95% Type-7 intervals are reported for Brier and log-loss differences. No row-IID
interval is permitted.

For M2 minus M1, define proper-score improvement as `M1 - M2` (positive is
better), assessed jointly for Brier and log loss:

* `CLEARLY_USEFUL`: both point improvements positive and both 95% intervals
  strictly positive.
* `DIRECTIONALLY_USEFUL`: both points positive, neither interval strictly
  negative, but clearly-useful is not met.
* `COUNTS_AGAINST`: either metric has a negative point and its 95% interval is
  strictly negative, or both points are negative.
* `NO_CLEAR_INCREMENTAL_VALUE`: all other cases.

A preferred architecture must be at least directionally useful; have no worse
than 0.001 absolute Brier and 0.005 log loss versus the best M2; calibration
slope in `[0.5,1.5]` and intercept in `[-0.25,0.25]` when estimable; at least
four symbols with nonnegative M2-vs-M1 Brier improvement; no elapsed-time
quartile with both proper-score point differences negative; at least 95% of
population trades represented; and positive Brier and log-loss M2-vs-M1 point
improvement in both folds. If multiple candidates qualify within score
tolerances, retain baseline B unless another candidate improves both primary
scores by at least 0.001 Brier and 0.005 log loss. Otherwise report no clear
winner and baseline B adequate.

After this rule is frozen and applied, fit the selected architecture on all
eligible 2024 rows and evaluate it on 2025. If selection is not B, evaluate B
as the sole predeclared reference. All 2025 entries and terminal labels are
development stability evidence, never confirmation and never reselection.

Calibration uses trade-equal-weighted predictions: weighted logistic
calibration intercept/slope on logit predictions plus ten fixed probability
bins. AUC is weighted descriptively. Symbol and elapsed-time slices are
descriptive. Four deterministic trajectories are selected only after scoring:
earliest trade ID among each outcome nearest its outcome-specific median row
count, plus the earliest ID among maximum-confidence correct and incorrect
trade-level cases.

No arbitrary grid, 1m pre-T2 state, 4h context, post-T2 study, trading-policy
economics, exit optimization, C7 modification, staging, commit, or push is
authorized.
