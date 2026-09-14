# C0 Binance Discovery Delivery

Contract source: `contracts/C0_binance_discovery_CONTRACT.md`
Delivery date: 2026-09-13
Executor: Codex

## Summary

Discovery found a fresh repository with only `README.md` tracked and the C0 kickoff contract untracked. No prior Binance research artifacts, code, data, environment definition, or test suite exist in this checkout. The BTCUSDT-only history mentioned in the contract is therefore unverified and must remain explicitly unknown.

The external `ccxt/binance-trade-bot` reference was inspected at commit `55f8cbbe082bd083a722cba697f708a07f5add16`. Its default strategy is relative-price rotation via a bridge currency, not a direct predictive lead-lag model.

## Task Status

T1 - Discover existing project and conventions: PASS with blockers.

- No `AGENTS.md` files were found.
- Repository path: `/media/ata/Data/personal/binance-v2`.
- Branch/commit: `main` at `0506ee07188a94ebbd4dc52ed9af79b98a71a9b2`.
- Working tree at start: `contracts/` untracked.
- Existing contract: `contracts/C0_binance_discovery_CONTRACT.md`.
- No established delivery/artifact convention existed, so this delivery uses `contracts/C0_binance_discovery/DELIVERY.md` and `artifacts/c0_binance_discovery/`.
- Next available contract identifier: `C1`.
- Environment blocker: no project evidence identifies the Binance conda environment. The active shell conda env was `binbot`, but this is not accepted as verified project evidence. No Python or tests were run.

T2 - Audit previous research: BLOCKED by missing evidence.

- No datasets, symbols, date ranges, intervals, spot/futures coverage, models, targets, splits, costs, or backtest results were present.
- No loaders, validators, or portfolio accounting code were present.
- Previous BTCUSDT-only work is unknown, not verified.

T3 - Assess reference strategy: PASS.

- Inspected `ccxt/binance-trade-bot` at `55f8cbbe082bd083a722cba697f708a07f5add16`.
- The default strategy initializes stored pair ratios from current bridge prices, scans possible switches from the current coin, applies fee-adjusted thresholds, and trades through the bridge.
- README claims about common crypto movement and Bitcoin leadership are motivations, not verified profitability evidence.
- Code behavior is relative-price mean reversion. It does not implement lagged BTC predictive features.
- More units of a destination coin do not imply higher USDT equity; open holdings must be marked to USDT.

T4 - Specify first empirical experiment: PASS as proposal.

The proposed C1 contract defines a bounded first experiment and preserves four separate hypotheses:

- H1: target-own-history predictability differs across eligible pairs.
- H2: lagged BTC adds information beyond target history.
- H3: ETH/SOL/XRP/BNB add information beyond BTC and target history.
- H4: relative-price rotation generates positive net returns versus benchmarks.

## Required Evidence Artifacts

- `artifacts/c0_binance_discovery/commands.md`
- `artifacts/c0_binance_discovery/evidence_inventory.md`
- `artifacts/c0_binance_discovery/reference_strategy_audit.md`
- `contracts/C1_binance_empirical_experiment_PROPOSAL_CONTRACT.md`

## Limitations and Blockers

- The contract path in the prompt contained `contracts/C0_binance_discovery_/_CONTRACT.md`; the actual file is `contracts/C0_binance_discovery_CONTRACT.md`.
- No environment files or project code exist, so the correct Binance Python/conda environment could not be verified from project evidence.
- No historical research files exist in this checkout; prior results and failure causes remain unknown.
- Shell GitHub access required escalation because sandbox DNS failed.
- No full-history downloads, model searches, live trading, production changes, Python commands, or tests were executed.

## Proposed Deviations

- Kept the original C0 contract file unchanged and placed the completed delivery under `contracts/C0_binance_discovery/DELIVERY.md` because no prior structure existed and the existing contract filename is already in use.
- Placed the next contract as `contracts/C1_binance_empirical_experiment_PROPOSAL_CONTRACT.md` and did not execute it.
