# C9 DYNAMIC PRE-T2 STATE MODEL CONTRACT

Status: prospectively frozen before C9 outcome evaluation on 2026-09-28.
C9 estimates, at each eligible completed pre-terminal state,
`P(T2 occurs before P0 | information available now)`. It is prognosis only:
not an entry filter, exit policy, trading strategy, or economic/P&L study.
No path or metadata containing `2026` may be accessed.

## Frozen population, outcome, and state architecture

C9 reuses the 2,199 frozen C7/C8 E1 trades and exact C7 first-causal-T2
semantics. Expected outcomes are 845 `T2_FIRST` and 1,354 `P0_FIRST`.
Snapshots stop strictly before first T2 or P0. The architecture is frozen at
60 completed minutes of slow context and completed 5-minute evolving state
(C8 architecture B). C9 does not reopen timescale selection.

The feature formulas, eligibility rules, missing-history exclusion, UTC bar
alignment, symbol indicators, scaling, per-trade weights, and baseline M2
logistic specification are exactly those in the frozen C8 contract. The 21
continuous features comprise eight slow-context features and thirteen
fast/path/state features; four symbol indicators use BTCUSDT as reference.
Features are causal and never include outcome, future path, economic, or
prediction-availability fields.

## Chronological development and calibration

Whole trades are the dependence unit. Every fit and metric weights each trade
equally by assigning each of its rows weight `1 / row_count_for_trade`.
Scaling and model fitting use training rows only.

The two outer 2024 folds are frozen from C8: H1 entries train and Q3 entries
validate; entries through Q3 train and Q4 validate. Training trades must have
terminal time strictly before the next scoring interval. To fit calibration
without in-sample scores, each outer training set generates expanding inner
out-of-time predictions:

* Q1 entries train the baseline and Q2 entries are scored;
* H1 entries train and Q3 entries are additionally scored when Q3 precedes the
  applicable outer validation interval;
* entries through Q3 train and Q4 entries are additionally scored only for the
  final all-2024 calibration used for the sealed 2025 stability evaluation.

At each step, the baseline is refit on all outer training rows for outer
validation. Calibration is fit solely to the earlier inner out-of-time scores,
using equal-trade weights. No validation outcomes enter fitting.

Candidates are deliberately limited to:

1. the uncalibrated C8 M2 logistic probability;
2. Platt recalibration `logit(p_cal) = a + b logit(p_base)`, unpenalized;
3. weighted isotonic regression by deterministic PAV, clipped to the training
   calibration target range and linearly constant outside it, only if inner
   support has at least 300 trades, at least 75 trades of each outcome, and at
   least 100 distinct baseline scores.

The final calibrator is chosen once from pooled outer-fold 2024 predictions.
Isotonic is chosen only if eligible and its trade-weighted Brier score and log
loss are both strictly lower than Platt's; otherwise Platt is chosen. A chosen
calibrator must not be worse than baseline on either proper score; otherwise
the uncalibrated baseline is retained. Ties favor the simpler procedure in the
order baseline, Platt, isotonic. The choice is then frozen and applied once to
2025 using all eligible 2024 rows for the baseline fit and all available 2024
expanding out-of-time scores for calibration. Nothing is revised after 2025.

## Metrics and uncertainty

Primary metrics are trade-weighted Brier score, log loss, calibration
intercept, and calibration slope. Secondary metrics are weighted AUC, ten
fixed probability bins `[0,.1), ..., [.9,1]`, and ECE defined before evaluation
as the sum across those bins of bin trade-weight mass times absolute difference
between weighted observed frequency and weighted mean probability.
Probability-band prevalence is reported by fixed bin. Calibration fits and
metrics clip probabilities only numerically at `1e-9` where logarithms require
it.

Paired uncertainty for baseline-minus-calibrated Brier and log loss uses the
C8 four-entry-week moving-block bootstrap with 2,000 replicates and seed
`20260928`, preserving every row belonging to each sampled whole trade.
Equal-tail 95% Type-7 intervals are reported. AUC is expected to be invariant
for monotone Platt/isotonic transformations except for isotonic ties.

## Interpretation and trajectories

Standardized full-2024 baseline coefficients are reported by feature and
summarized as signed and absolute coefficient mass for the predeclared
families: 1h trend/context, current return, running peak/MFE, drawdown from
running peak, distance to T2 geometry, 5m momentum, 5m volatility/range,
path efficiency, elapsed time, fast/slow directional agreement, activity, and
symbol. These are predictive associations, not causal effects.

For each outer-OOF 2024 and final 2025 trajectory, report the first eligible
state; within-trade early/middle/late thirds by normalized row ordinal; and the
last causally valid state before T2/P0. Report distributions by eventual
outcome. Per trade, classify net trajectory as upward, downward, or flat using
last-minus-first probability with fixed tolerance `1e-12`; report mean and
median per-5-minute change, positive/negative change shares, persistence
(share of consecutive changes having the net direction), and reversal count
(sign changes among nonzero consecutive changes). No action threshold is
defined.

Four deterministic 2025 examples are selected after scoring: earliest trade
ID nearest the outcome-specific median eligible row count for each outcome,
then earliest trade ID among the largest absolute upward and downward net
changes not already selected. Their complete causal probability sequences are
descriptive only.

## Required outputs and stopping rule

Artifacts under `artifacts/c9_dynamic_pre_t2_state/` must include provenance,
feature schema, population/snapshot reconciliation, fold and inner-calibration
definitions, candidate and frozen procedure, 2024/2025 metrics, reliability
tables, whole-trade uncertainty, feature interpretation, trajectory summaries,
deterministic examples, final summary, run manifest, and reproducibility
hashes. The contract SHA-256 is verified by the runner before any outcome
evaluation. C9 stops after the 2025 stability report. Post-T2 modeling,
economics, C7/C8 scientific modification, staging, committing, and pushing are
not authorized.
