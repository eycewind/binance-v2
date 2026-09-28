# C12 Post-T2 Warning / Lead-Time Adequacy Study — Prospective Contract

Status: frozen before C12 outcome evaluation. C12 is a bounded descriptive diagnostic of the frozen C11 model and stops before C13.

## Scientific question and population

C12 asks whether C11's calibrated running `P(CONTINUATION_FIRST before DETERIORATION_FIRST | completed 5m context + completed 1m evolving state)` provides sufficiently early, persistent warning of the eventual terminal event. It studies timing, persistence, reversals, coverage, and unwarnable fast paths—not economics or an action policy.

The source is exactly 845 first-T2 trades: 335 `CONTINUATION_FIRST`, 508 `DETERIORATION_FIRST`, 2 descriptive-only `P0_FIRST`, and no ambiguous cases. The primary binary denominator is 843. Reports separately identify trades with physical C11 rows, trades scored by the frozen out-of-time procedure, physical zero-row trades, and trades unscored because they belong only to a training interval. No rate silently conditions on survivors.

## Frozen probability source

C11 architecture, features, rows, folds, weighting, model fitting, calibration selection, and 2025 application are reused byte-for-byte through C11 functions. The selected frozen calibration is reproduced rather than redesigned. C12 proceeds only if its regenerated C11 calibration decision, probability metrics, and trajectory summaries exactly reproduce the committed C11 artifacts. Development probabilities are the pooled 2024 out-of-time predictions; evaluation probabilities use the model trained on all eligible 2024 rows and its training-only frozen calibrator on 2025. No model, timeframe, feature, or regularization search is allowed.

## Fixed descriptive states and persistence

Bands are fixed before evaluation: `VERY_DETERIORATION_LIKE` is `p < .20`; `DETERIORATION_LEANING` is `.20 <= p < .40`; `UNCERTAIN` is `.40 <= p < .60`; `CONTINUATION_LEANING` is `.60 <= p < .80`; and `VERY_CONTINUATION_LIKE` is `p >= .80`. Boundaries are left-inclusive except the first, and right-exclusive except the last. These are descriptive states, never exit/hold thresholds.

For each of `<.40`, `<.20`, `>=.60`, and `>=.80`, P1/P2/P3 mean the first run of exactly one, two, or three consecutive completed one-minute observations satisfying the condition. Detection time is the final observation completing the required run; lead time is `(terminal_ms - detection_state_ms) / 60000`, and completed updates remaining is the count of later eligible pre-terminal rows. Only rows strictly before terminal time are admissible. No other persistence lengths or cutoffs may be added.

For deterioration outcomes report warning coverage, first-entry lead-time p10/p25/median/p75/p90, coverage with at least 1/2/5/10/15 minutes, no-warning cases, and the P1/P2/P3 tradeoff. For continuation outcomes report false deterioration warnings, warning-to-continuation lead time, recovery to `>=.60` and `>=.80`, warning/recovery cycles, and maximum contiguous duration in the warning region. Symmetrically report continuation signals and their reversals below `.40`/`.20`, including false continuation states among deterioration outcomes. Rates use all outcome trades in the applicable scored population, with source denominators alongside them.

## Dynamics and timing views

At every causal state, compute 1-row, 3-row, and 5-row probability differences where history exists. Direction consistency over the last 3 and 5 observations is the fraction of non-zero adjacent changes agreeing with the window's net direction; all-zero windows have consistency 1. These quantities are descriptive and receive no optimized cutoff.

Terminal-time strata are fixed as `FAST` (terminal event no more than 5 minutes after the first eligible scored state), `MEDIUM` (more than 5 and no more than 30), and `SLOW` (more than 30); physical `ZERO_ROW` and frozen-procedure-unscored trades are separate. Elapsed-time bins since T2 are `[0,5]`, `(5,15]`, `(15,30]`, `(30,60]`, and `(60,infinity)`. Each elapsed panel reports distinct active trades, outcome composition, probability distributions, and descriptive warning/reversal prevalence.

Core metrics are split by 2024/2025 and descriptively by BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT. Small subgroup differences are not significance claims.

## Interpretation frozen before results

`USEFUL_EARLY_WARNING` requires substantial eligible-deterioration coverage, lead time visibly beyond terminal adjacency relative to the one-minute cadence, retention of useful coverage under P2, false/reversing warnings that do not dominate continuation paths, and direction that does not materially reverse across years or symbols. `LATE_OR_NOISY_WARNING` applies when discrimination exists but warning is predominantly terminal-adjacent, P2 removes most coverage, or false/reversing warnings make simple action scientifically questionable. `INSUFFICIENT` applies if frozen probabilities cannot be reproduced or missing/rapid-transition support prevents reliable diagnostics. These are qualitative scientific categories; no numeric pass threshold will be invented after inspection.

## Guardrails

The two P0-first trajectories are descriptive only and excluded from binary warning rates. C12 calculates no prices, P&L, costs, saved loss, opportunity cost, expectancy, profitability, execution, exit strategy, action threshold, or trading policy. It accesses no 2026 data or metadata, does not modify C7/C8/C9/C10/C11 scientific behavior, does not retrain C11 in response to C12, and does not begin C13. Artifacts are compact deterministic JSON with hashes; focused tests and one final full suite are required. Nothing is staged, committed, or pushed.
