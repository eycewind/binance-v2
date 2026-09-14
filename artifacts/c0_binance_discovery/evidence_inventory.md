# C0 Evidence-Linked Inventory

## Repository and conventions

- Repository path: `/media/ata/Data/personal/binance-v2`.
- Branch: `main`.
- Commit: `0506ee07188a94ebbd4dc52ed9af79b98a71a9b2`.
- Remote: `git@github.com:eycewind/binance-v2.git`.
- Working tree at discovery start: `contracts/` was untracked; no tracked contract/delivery/artifact convention existed beyond `README.md`.
- Files present before delivery work: `README.md` and `contracts/C0_binance_discovery_CONTRACT.md`.
- `AGENTS.md`: none found under the inspected parent tree.
- Established structure: no prior deliveries or artifact indexes found. This delivery uses `contracts/C0_binance_discovery/DELIVERY.md` and `artifacts/c0_binance_discovery/`.
- Next available contract identifier: `C1`, because only C0 exists in repository evidence.

Evidence: `artifacts/c0_binance_discovery/commands.md`.

## Environment

- No `pyproject.toml`, `requirements*.txt`, `environment*.yml`, `Pipfile`, `poetry.lock`, source package, or tests were present.
- `conda env list` showed the shell was active in `binbot`, and several unrelated environments exist, including PSX environments.
- There is no project evidence identifying a correct Binance conda environment.
- No Python commands, tests, installs, or dependency changes were run.

Status: blocked for environment verification until project evidence or user direction identifies the intended Binance environment.

## Previous Binance research audit

No repository evidence was found for:

- Datasets or local/raw market data.
- Symbols, date ranges, bar intervals, spot/futures coverage.
- Models, targets, features, splits, backtest configs, costs, or performance results.
- BTCUSDT-only historical experiments.
- Reusable loaders, validators, portfolio accounting code, or report artifacts.

Verified finding: the recollection that earlier research focused on BTCUSDT remains unverified in this checkout. It may be true elsewhere, but there is no local evidence here.

Suspected failure causes: unknown. No notebooks, logs, configs, or result files exist to support causal claims.

Missing evidence: all prior research artifacts, environment definition, data provenance, and evaluation logs.

## Reference baseline

- External repository inspected: `ccxt/binance-trade-bot`.
- Commit pinned with `git ls-remote`: `55f8cbbe082bd083a722cba697f708a07f5add16`.
- Audit file: `artifacts/c0_binance_discovery/reference_strategy_audit.md`.
- Source URL: <https://github.com/ccxt/binance-trade-bot/tree/55f8cbbe082bd083a722cba697f708a07f5add16>

Material conclusion: default behavior is a relative-price rotation / mean-reversion strategy, not predictive lead-lag. It can increase coin quantities while losing USDT equity, so any comparison must use USDT mark-to-market accounting.
