# C11 Dynamic Post-T2 State Model — Prospective Contract

Status: frozen before outcome evaluation. C11 is prognosis only and stops before C12.

## Question and population

C11 estimates `P(CONTINUATION_FIRST before DETERIORATION_FIRST | completed information at the current post-T2 minute)`. The source is exactly the 845 C7/C10 first-T2 trades (415 in 2024, 430 in 2025). C10 event identities, ordering, and geometry are authoritative. The expected terminal counts are 335 `CONTINUATION_FIRST`, 508 `DETERIORATION_FIRST`, 2 `P0_FIRST`, and 0 `AMBIGUOUS`.

The primary binary population contains only the 843 continuation/deterioration trades. `P0_FIRST` and any unexpected `AMBIGUOUS` trades remain in reconciliation and descriptive reports but are never relabeled, fitted, or evaluated. Trades without a valid snapshot remain in accounting.

## Frozen geometry and information set

At first T2, let `E` be entry and `P_T2` the causal running peak through the minute preceding the T2 decision timestamp. The frozen levels are `P_T2 * 1.005` and `(E + P_T2) / 2`. They never trail. C10's same-minute and P0 precedence rules remain unchanged.

The architecture is C10 A: completed 5-minute context plus completed 1-minute state. Snapshot timestamps begin strictly after first T2 and precede terminal time. The existing C10 aggregation and feature formulas are reused without modification. No incomplete bar, same-bar high/low, gap filling, future terminal fact, or information at/after terminal is available to features.

Continuous M1 features are C10 `CONTEXT_FEATURES`. Continuous M2 features are `CONTEXT_FEATURES + FAST_FEATURES`. Both include the same four frozen symbol indicators. Families are: 5m returns/momentum; 5m volatility/range/activity/trend; 1m momentum; 1m volatility/range/activity; return since T2; return from entry; new peak since T2; drawdown from peak; distances to each frozen boundary; path efficiency; elapsed log-minutes; and 1m/5m directional agreement. This schema is frozen before evaluation; no outcome-driven additions or subsets are allowed.

## Models, folds, and weighting

M0 is training trade-weighted prevalence. M1 and M2 are fixed L2-regularized binary logistic regressions using C10's deterministic optimizer, `C=1`, unpenalized intercept, and training-only weighted standardization. Each trade has total weight one in every fit and metric. No model family, regularization, feature, or threshold search is permitted.

Development uses 2024 only with C10's chronological folds: train Q1/H1 and validate Q3; train Q1–Q3 and validate Q4. Training trades must terminate before the validation boundary. Whole trades remain intact. Pooled out-of-fold predictions define 2024 comparisons.

Calibration applies only to M2. For each outer fold, calibration data are predictions from earlier expanding chronological inner splits, with all preprocessing and model fitting confined to their training periods. Candidates are uncalibrated, Platt, and isotonic. Isotonic is eligible only when every outer fold independently has at least 300 trades, 75 events, 75 non-events, and 100 distinct scores. Select isotonic only if eligible and both pooled Brier and log loss are strictly below Platt. Otherwise select Platt. If the selected recalibration worsens either proper score relative to uncalibrated M2, retain uncalibrated M2. After this rule is applied in 2024, refit M2 on all eligible 2024 rows, fit the selected calibrator only from 2024 inner out-of-time scores, and evaluate once on 2025.

## Metrics and uncertainty

Primary metrics are trade-weighted Brier score, log loss, calibration intercept, and calibration slope. Secondary metrics are weighted AUC, fixed-width probability-band ECE using ten bins `[0,.1), …, [.9,1]`, prevalence, and probability distributions. Comparisons are M1 versus M0, M2 versus M1, and calibrated versus uncalibrated M2.

Uncertainty uses paired moving-block bootstrap of whole trades grouped by entry week, four-week blocks, 2,000 deterministic replicates, seed 20260930. No row-IID intervals are allowed.

Trajectory summaries use selected calibrated probabilities and report first eligible state, elapsed bands (1–5, 6–15, 16–30, 31–60, 61–120, and 121+ minutes), last causal pre-terminal state, direction, per-minute changes, persistence, reversals, time in the fixed probability bands, and band-to-band transitions by eventual outcome. These are descriptive, never action thresholds.

Feature interpretation uses standardized M2 coefficients and prospectively declared family-level signed and absolute coefficient mass. Associations are predictive, not causal.

## Guardrails and practical meaning

A one-minute state is information available only after that minute completes; any later policy would act subsequently. C11 assumes neither sub-minute foresight nor instantaneous fill and models no execution. It calculates no P&L, economics, action threshold, trading/exit rule, or optimized policy. It does not alter C7/C8/C9/C10 scientific behavior, access 2026 paths or metadata, or start C12.

Artifacts must include manifests and hashes; event/population reconciliation; schema; folds; M0/M1/M2 and calibration metrics; calibration decision and frozen procedure; bands; trajectories; feature interpretation; P0 cases; 2025 stability; uncertainty; and final summary. Focused tests and one final full repository suite are required. Nothing is staged, committed, or pushed.
