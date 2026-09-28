# C14 Post-T2 Economic State Characterization Contract

Status: prospectively frozen before C14 target construction, characterization, or model evaluation.

## Scope

C14 is a bounded economic-state study, not a trading-policy experiment. It reuses the frozen C7 first-T2 population, C_BASE ledger, C10 5m-context/1m-state causal snapshots, C11 feature families, and C11 calibrated out-of-time `p_cont`. C7-C13F scientific behavior is immutable. No 2026 path or metadata may be accessed. C15 is out of scope.

The source population is 845 first-T2 trades: 335 continuation-first, 508 deterioration-first, and 2 P0-first. No-T2 trades remain explicitly outside the post-T2 modeling scope. P0-first and zero-row/unavailable cases are reconciled but are not silently converted to binary observations.

## Snapshot and target rules

Each candidate is a completed causal 1-minute state at timestamp `t`. Its candidate execution is the open timestamped `t`, i.e. the immediate next 1-minute interval after the completed information. It is eligible only when that execution is strictly before canonical P0, the immediate open is unique, finite, and positive, and the preceding minute plus execution minute provide continuous evidence. P0 wins ties. Gap or missing evidence fails closed.

For each eligible snapshot and cost case, both alternatives use the frozen C7 two-leg ledger with the same entry price and cost case:

* `EXIT_NOW_NET(t)` uses the immediate next 1-minute open.
* `HOLD_TO_P0_NET(t)` uses the frozen canonical P0 raw exit price.
* `DELTA_V(t) = HOLD_TO_P0_NET(t) - EXIT_NOW_NET(t)`.

C_BASE (10 bp fee and 2 bp adverse slippage on each executed leg) is primary. C0, C_S5, and C_S10 are descriptive sensitivities only. `HOLD_BETTER` means strictly positive DELTA_V, `EXIT_BETTER` strictly negative, and exact zero is separately reported. No deadband is allowed.

## Leakage firewall

The causal feature object is constructed solely by frozen C10 code using observations completed through `t`. Target construction is a separate function that receives no feature object. DELTA_V, P0 outcome, future MFE/MAE, recovery, future peaks/highs, eventual P0 return, and future continuation/deterioration paths are prohibited feature names and inputs. Future excursion diagnostics run only after primary characterization and evaluation are complete and are marked `EVALUATION_ONLY`.

## Fixed characterization

Frozen C11 `p_cont` bands are `<0.20`, `0.20-0.40`, `0.40-0.60`, `0.60-0.80`, and `>=0.80`. Fixed elapsed bands are `0-5m`, `>5-15m`, `>15-30m`, `>30-60m`, and `>60m`. Summaries report rows and unique trades, distribution, signs, years, and symbols; trade-normalized weights are primary. The event/economic-state cross-tab uses frozen continuation-first and deterioration-first labels. Time remaining to P0 and to the C10 terminal event is descriptive only.

## Fixed models and validation

The binary target is HOLD_BETTER. M0 is the training trade-weighted prevalence. M1 is a fixed L2 logistic model using existing C11 5m context features. M2 is the same fixed logistic procedure using all existing C11 5m context plus 1m state features. Symbol indicators remain as in C11. The continuous model is one fixed L2 ridge-style linear model using the M2 schema and a fixed penalty of 1.0. No feature, model, hyperparameter, threshold, horizon, or regularization search is permitted.

Development uses the existing C10 chronological 2024 folds with whole trades intact, training strictly before validation and preprocessing fit only on training rows. Each trade has total weight one. After pooling 2024 out-of-fold results, the unchanged procedure is fit on all 2024 and evaluated once on 2025. The same models are evaluated within deterioration-first; no subgroup model is fit.

Binary primary metrics are trade-weighted Brier score, log loss, and calibration intercept/slope. Secondary metrics are AUC, ECE, and fixed probability bands. Continuous metrics are trade-weighted MAE, RMSE, correlation, and sign accuracy; sign accuracy is not profitability.

## Prospectively frozen interpretation

`ECONOMIC_STATE_IS_PREDICTABLE` requires M2 to beat M0 on both Brier and log loss in pooled 2024 OOF and untouched 2025, plus M2 AUC strictly above 0.5 overall and within deterioration-first in both years. `WEAK_ECONOMIC_STATE_SIGNAL` applies when M2 beats M0 on at least one proper score in both years or all four overall/subgroup AUCs exceed 0.5, but the predictable rule fails. `NO_USEFUL_ECONOMIC_STATE_SIGNAL` applies otherwise. `INSUFFICIENT` applies if leakage-safe target construction, causal execution eligibility, or required evaluation cannot be established. These are characterization rules, not action thresholds.

## Trajectories and diagnostics

Per-trade realized DELTA_V and predicted probability trajectories are summarized using deterministic selections only: within each year/outcome/economic-sign group, choose the lexicographically first trade among those closest to the median eligible state count. Future MFE, future MAE, regained first-T2 peak, new post-T2 high, time to recovery, and eventual P0 return are evaluation-only and cannot redefine a state or model.

## Reproducibility and stopping

The run emits only the bounded artifacts named in the request, including hashes. Focused tests and the full repository suite run in `binance-v2-research`. Nothing is staged, committed, or pushed. Stop after C14 and do not begin C15.
