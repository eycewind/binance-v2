# C10 Post-T2 Timescale Adequacy Contract

Status: **FROZEN BEFORE OUTCOME EVALUATION**  
Freeze date: 2026-09-28  
Study seed: **20260929**  
Bootstrap replicates: **2000**

## Scope and source population

C10 is a bounded state-description/prognosis study. It does not estimate trading economics, simulate an exit, define a policy, optimize thresholds, or begin C11. The source is exactly the 845 C7 trades whose authoritative first causal T2 timestamp is strictly before canonical P0 (415 in 2024; 430 in 2025). Identities and first-T2 timestamps come from the frozen C7 population manifest and are reconciled to the accepted raw C4 T2 identity table. Every path follows original P0, never S1. No 2026 data or metadata may be accessed.

## Frozen terminal geometry

At authoritative first T2 time `t0`, entry `E` and causal running peak `P0_T2` (maximum of E and one-minute highs from entry through the final minute completed at t0) are frozen. The continuation level is `P0_T2 * 1.005`; deterioration is `(E + P0_T2) / 2`. Starting with the one-minute bar opening at t0, the first bar touching only continuation is CONTINUATION_FIRST; the first touching only deterioration is DETERIORATION_FIRST; a bar touching both is AMBIGUOUS. If neither is touched strictly before canonical P0, the result is P0_FIRST. P0 has precedence over bars opening at or after its execution timestamp. Levels never trail.

AMBIGUOUS trades remain in population accounting and descriptions but are excluded from primary modeling.

## Architectures and causal snapshots

Exactly these candidates are frozen:

- A: 5-minute context, 1-minute state/update (baseline)
- B: 10-minute context, 1-minute state/update
- C: 15-minute context, 1-minute state/update
- D: 5-minute context, 2-minute state/update

UTC-aligned bars must be complete. For each trade, snapshots begin at the first completed update boundary strictly after t0 and stop strictly before its terminal event. Context is the latest completed context bar at the state timestamp. No gaps are forward-filled, and no same-bar, future, or post-terminal values are used. Zero-row trades remain in completeness accounting.

## Frozen features

The identical formulas and lookback counts apply to every architecture; only bar resolution changes.

Context: 1/3/6-bar returns; 12-return volatility; current range divided by the prior 12-bar median range; activity divided by the prior 12-bar median activity; close relative to 12-bar SMA; one-bar change in 12-bar SMA.

Fast/path: 1/3/6-state-bar returns; 12-return volatility; range ratio; activity ratio; return since first T2; return from original entry; new running peak since T2 relative to frozen peak; drawdown from post-T2 running peak; close distance to frozen continuation and deterioration levels; path efficiency (net close displacement since T2 divided by summed absolute close-to-close movement); log1p elapsed minutes since T2; sign agreement of 3-bar context and fast returns.

Symbol indicators are fixed nuisance covariates in M1 and M2. M0 is the training trade-weighted class prevalence. M1 is context plus symbol. M2 is context plus fast/path plus symbol.

## Frozen model and evaluation

M1/M2 use deterministic L2-regularized multinomial softmax regression with one reference class, unpenalized intercepts, `C=1`, maximum 1000 iterations, tolerance `1e-9`, and no hyperparameter search. Preprocessing is weighted mean/SD scaling learned only from training data. Each trade has total weight one within each fit.

Development uses 2024 only with expanding chronological folds:

- fold A: train entries 2024-01-01 through 2024-06-30, validate 2024-07-01 through 2024-09-30;
- fold B: train entries 2024-01-01 through 2024-09-30, validate 2024-10-01 through 2024-12-31.

Training trades whose terminal timestamp reaches or crosses the validation boundary are purged. Trades are never split. Primary scores are multiclass Brier (sum of squared class probability errors) and multinomial log loss, using equal-total-trade row weights. Secondary results include one-vs-rest weighted AUC, calibration bins, class prevalence, probability/confusion summaries, and symbol/duration/fold stability.

Uncertainty is a deterministic four-week moving-block bootstrap over whole trades using seed 20260929 and 2000 replicates. Score improvement is defined as M1 loss minus M2 loss (positive favors M2).

## Prospective completeness and architecture decision

An architecture is complete only if at least 95% of non-ambiguous 2024 source trades have at least one eligible row, and its coverage is no more than 2 percentage points below baseline A. Zero-row outcomes must be reported by terminal class. A candidate cannot benefit merely by deleting short paths.

A non-baseline candidate can replace A only when all conditions hold:

1. M2 improves both primary scores over M1 at the pooled OOF point estimate, and neither 95% interval has an upper endpoint below zero;
2. its M2 is competitive with the best eligible candidate (Brier within 0.002 and log loss within 0.01);
3. it satisfies the completeness rule;
4. M2 improves both scores over M1 in both folds;
5. at least four of five symbols have non-negative Brier improvement, and no duration quartile has both score improvements negative;
6. implementation remains limited to the frozen completed-bar design;
7. to displace A, it improves over A by at least 0.002 Brier and 0.01 log loss, both.

If no non-baseline candidate meets every replacement condition, retain A and conclude that 5m/1m is adequate without evidence justifying a change. Selection is frozen from 2024. On 2025 evaluate only the selected architecture, plus A if selection differs.

## Interpretation and execution practicality

Results describe post-T2 transition prognosis, not actions. A one-minute analysis interval means completed one-minute information only and does not imply sub-minute prediction or execution. Any later policy would require completed state followed by subsequent execution with separately modeled latency and slippage; C10 performs no such simulation.

Artifacts must include the manifest, provenance, frozen candidate/event/feature definitions, population reconciliation, dataset/completeness summaries, folds, metrics, paired uncertainty, descriptions, decision, permitted 2025 stability, hashes, and final summary. Tests cover the causal geometry, aggregation, cutoff, formulas, weights, folds, preprocessing, determinism, reconciliation, and 2026 guard.
