# C1 Binance Empirical Experiment Proposal Contract

Status: proposal only. Do not execute until explicitly accepted.

## Background

C0 discovery found no local Binance research artifacts, no verified environment, and no reusable data/model/backtest code in this repository. The first implementation milestone should build a small, reproducible empirical harness before attempting complex ML or large downloads.

## Objective

Implement and run a bounded first empirical experiment that tests simple predictability and rotation hypotheses across a point-in-time USDT spot universe, with leakage-safe data handling and USDT mark-to-market accounting.

## Scope

- Define a point-in-time eligible Binance USDT spot universe of approximately 30-50 coins.
- Use historical liquidity and listing-age rules that are computable from stored exchange metadata.
- Treat delistings explicitly: delisted symbols remain in historical universes until delisting and cannot be traded afterward.
- Collect only the bounded data needed for the first experiment.
- Implement deterministic feature/label generation, baselines, evaluation, and reporting.
- Include configurable fees, spread, slippage, and execution delay.
- Include a 0.1% per executed leg scenario. A trade `A -> USDT -> B` has two executed legs.

## Out of Scope

- Live trading.
- Full-history exchange-wide downloads.
- Large model searches.
- Futures/perpetuals unless explicitly added by a later contract.
- Credential use or account-specific fee verification.
- Optimizing production performance.

## Architectural Constraints

- Verify the correct Binance project environment before running Python or tests.
- Do not use PSX production environments or data paths.
- Preserve unrelated changes.
- Do not expose credentials.
- All generated datasets and reports must include provenance: source, retrieval time, symbol universe, date range, interval, and code revision.
- Signal timestamps must represent information available before the simulated entry.
- Portfolio accounting must mark all holdings to USDT, including open losing positions.

## Tasks

T1 - Environment and structure.

- Identify or create the approved project environment file.
- Add repository conventions for contracts, deliveries, artifacts, data cache paths, and reports.
- Add a minimal test command and document it.

T2 - Data and universe.

- Build a point-in-time USDT spot universe with approximately 30-50 eligible coins.
- Proposed rules: listed at least 180 days before train start, median daily USDT quote volume above a predefined threshold during a pre-experiment eligibility window, active spot trading status at each timestamp, no leveraged tokens or stablecoin targets unless explicitly allowed.
- Download bounded OHLCV bars for selected horizons. Start with `1h` and `4h`; optionally add `15m` only if storage remains small.
- Record missing data, stale intervals, listing gaps, and delisting treatment.

T3 - Hypothesis tests.

- H1: for each eligible pair, compare own-history baselines against cash and naive return baselines.
- H2: add lagged BTC features and compare against the target-own-history model using identical splits.
- H3: add lagged ETH, SOL, XRP, and BNB features beyond BTC and target history.
- H4: implement a simple relative-price rotation baseline and compare against cash, BTC buy-and-hold, and an eligible-universe equal-weight portfolio.

T4 - Windows and leakage controls.

- Use chronological windows only. Proposed first split: train 2022-01-01 through 2023-12-31, validation 2024-01-01 through 2024-12-31, test 2025-01-01 through 2026-06-30, adjusted if listing coverage requires.
- Predefine horizons: 1 bar, 4 bars, 24 hours, and 7 days where compatible with interval choice.
- Prevent overlapping-label leakage in metrics or use overlap-aware standard errors.
- Fit scalers, selectors, and thresholds on train only; choose model/hyperparameters on validation only; touch test once.

T5 - Costs and execution.

- Simulate signal availability at bar close and executable entry no earlier than the next bar.
- Evaluate no-cost, 0.1% per leg, and sensitivity scenarios for spread/slippage/delay.
- Report turnover, number of executed legs, rejected trades, stale-price skips, drawdowns, Sharpe-like summary, total return, and benchmark-relative return.

## Completion Criteria

- Delivery contains data inventory, universe file, reproducible commands, environment verification, test results, and report paths.
- Each hypothesis is marked ADVANCE, REJECT, or INSUFFICIENT EVIDENCE using predefined criteria.
- Backtest equity curves use USDT mark-to-market accounting.
- C0 limitations are either resolved or carried forward explicitly.

## Delivery Requirements

- Produce `contracts/C1_binance_empirical_experiment/DELIVERY.md`.
- Produce artifacts under `artifacts/c1_binance_empirical_experiment/`.
- Include an evidence-linked inventory, command log, universe definition, data-quality report, metrics report, and proposed next contract.

## Executor Notes

- Start with simple baselines: last-return sign, moving-average momentum/mean-reversion, regularized linear/logistic models, and naive rotation.
- Avoid complex ML until baselines and accounting are trustworthy.
- Missing historical evidence from C0 should remain unknown unless new repository evidence is found.
