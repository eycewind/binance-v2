We are restarting Binance research using our existing CONTRACT / DELIVERY / ARTIFACTS workflow.

Background:
Our PSX strategy is already running and collecting live evidence. Keep this work isolated from PSX production. Earlier Binance research reportedly concentrated on BTCUSDT and did not produce satisfactory results. Verify that history from repository evidence; do not assume the recollection is complete.

Objective:
Complete an initial discovery and research-design milestone that establishes what we already have and defines a reproducible multi-coin investigation.

T1 — Discover the existing project and conventions

* Read applicable AGENTS.md files, README, contracts, deliveries and artifact indexes.
* Record repository path, branch, commit and working-tree status.
* Identify the actual CONTRACT/ARTIFACTS conventions and next available contract identifier. Do not overwrite or renumber existing contracts.
* Identify the correct Binance conda environment from project evidence. Activate and verify it before running Python, tests or dependency changes. Do not assume the PSX environment is appropriate.
* Preserve unrelated changes. Do not expose credentials.

T2 — Audit previous research

* Inventory datasets, symbols, date ranges, bar intervals, spot/futures coverage, models, targets, splits, costs and backtest results.
* Identify reusable loaders, validation code and portfolio accounting.
* Distinguish verified findings, suspected failure causes and missing evidence.
* Cite file paths and relevant commands/results for each material conclusion.

T3 — Assess the reference strategy
Inspect https://github.com/ccxt/binance-trade-bot and record the inspected commit if accessible.

* Explain the implemented default strategy, including ratio initialization/updates, switching conditions, fees and backtest execution assumptions.
* Separate README claims from behaviour verified in code.
* Distinguish relative-price mean reversion from predictive lead–lag.
* Explain why increasing coin quantities need not increase USDT portfolio equity.
* Treat it as a potential comparison baseline, not established evidence of profitability.
  Do not run its live trading entry point.

T4 — Specify the first empirical experiment
Keep these hypotheses separate:
H1: Some eligible pairs are more predictable using their own history than BTCUSDT.
H2: Lagged BTC information improves prediction beyond the target's own history.
H3: ETH/SOL/XRP/BNB add information beyond BTC and the target's own history.
H4: Relative-price rotation produces positive net returns and compares favourably with simple benchmarks.

Propose a bounded first experiment covering:

* A point-in-time USDT spot universe, approximately 30–50 eligible coins, with historical liquidity/listing-age rules and explicit delisting treatment.
* Data sources, existing coverage, missing data and estimated download/storage requirements.
* A small predefined set of horizons and chronological train/validation/test windows.
* Simple baselines before complex ML.
* Protection against leakage, survivorship bias, multiple testing, stale prices and overlapping labels.
* Signal availability and executable entry timing.
* USDT mark-to-market accounting, including open losing positions.
* Configurable fees, spread, slippage and execution-delay sensitivity. Include 0.1% per executed leg as an explicit research scenario, not a verified account fee. A → USDT → B has two executed legs.
* Comparisons against cash, BTC buy-and-hold and a clearly specified eligible-universe portfolio.
* Explicit criteria for advancing, rejecting a hypothesis or declaring insufficient evidence.

Delivery:
Use the repository's established structure. If none exists, use contracts/C0_binance_discovery/CONTRACT.md and DELIVERY.md, with supporting files under artifacts/c0_binance_discovery/.

The contract must contain Background, Objective, Scope/Out of Scope, Architectural Constraints, Tasks, Completion Criteria, Delivery Requirements and Executor Notes.

Produce the completed discovery delivery, an evidence-linked inventory, and a draft next implementation contract. Record commands, environment, source revisions, limitations and deviations. Mark each task PASS/BLOCKED with evidence; missing historical evidence must remain explicitly unknown.

Scope of this kickoff is discovery and experiment specification. Do not launch full-history downloads, model searches, live trading or production changes. Finish all discovery work possible with available access, then return the delivery and proposed implementation contract for review.
