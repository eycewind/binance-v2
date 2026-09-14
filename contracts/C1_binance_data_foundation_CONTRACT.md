# C1 — Binance Data Foundation and Validation

Status: scoped execution contract. Supersedes the unexecuted C1 empirical-experiment proposal. Preserve that proposal as historical, superseded material; do not execute it.

Target repository: `/media/ata/Data/personal/binance-v2`.
Contract destination: `contracts/C1_binance_data_foundation_CONTRACT.md`.
Delivery destination: `contracts/C1_binance_data_foundation_DELIVERY.md`.
Artifact root: `artifacts/c1_binance_data_foundation/`.

## Background

C0 inspected a fresh checkout and found no previous research there. This does not establish absence of earlier work elsewhere. The user now identifies two reference repositories:

- Legacy Binance/binbot-v1: https://github.com/eycewind/binbot — user reports useful feature computation code and a mainly single-pair research history; verify specifics from source.
- Recent PSX research: https://github.com/eycewind/psx-ml-research — inspect for reusable data-validation, split, provenance and accounting patterns.

Neither repository has been independently inspected by this contract's author. Their contents, reuse suitability and prior performance remain unverified. References are read-only inputs, not runtime dependencies on production checkouts.

## Objective

Establish a reproducible, tested data foundation and identify reusable legacy components. Deliver evidence and resource estimates needed for the author/user to define a later empirical experiment. C1 does not determine whether any trading hypothesis is profitable.

## Scope / Out of Scope

In scope: bounded source audit; dedicated environment; public archive ingestion; a fixed small real-data sample; causal feature computation; synthetic accounting tests; historical-universe feasibility assessment; reproducible delivery.

Out of scope: model fitting, parameter search, statistical hypothesis evaluation, pair ranking by performance, real-data strategy backtests, equity curves, live or paper trading, account credentials, futures, production modifications, exchange-wide candle downloads, and implementation of the reference rotation bot. Do not create or execute the next contract; provide decision inputs only.

## Architectural Constraints

- Read applicable AGENTS.md and preserve unrelated changes. Record initial branch, commit and status. Do not push, merge, or commit unrelated work.
- Hash this contract before and after execution. Do not edit it. Document deviations; do not silently relax acceptance criteria.
- Keep contracts and deliveries directly under `contracts/`; artifacts may use subdirectories.
- Explicitly authorized environment: create a dedicated conda environment named `binance-v2-research` if absent, using Python 3.11 and a minimal compatible dependency set. If it already exists, inspect ownership/configuration before changing it. Do not mutate an unrelated environment with that name; report the conflict.
- Record `CONDA_DEFAULT_ENV`, Python version and `sys.executable` before tests or project Python commands. Do not install into `base`, `binbot`, or `psx-ml-research`. Provide an environment definition and resolved dependency record.
- Read-only source inspection in reference repositories is allowed without activating their environments. Execute adapted code and tests only in the new project's verified environment. Never import legacy trading entry points or modules with uncontrolled side effects.
- Prefer existing local reference checkouts; use current authenticated Git access to obtain a separate inspection copy if necessary. Do not modify reference repositories, ask for API keys, or print secrets. If access fails, record the exact limitation and continue independent work.
- All new code/data/reports belong under the target repository or task temporary directories. No PSX production writes or services.
- Implementation organization is executor discretion; scientific scope, fixed sample and acceptance rules are not.

## Tasks and Acceptance Evidence

### T1 — Audit source reuse and capture provenance

Inspect both reference repositories and their applicable instructions. Record actual local path, remote, HEAD commit, branch and dirty status. A remote HEAD lookup alone is not proof of the inspected source revision. Record relevant file hashes when inspecting uncommitted code.

Produce `reuse_audit.md`: source path/function, purpose, dependencies, inputs/outputs, timing semantics, side effects, existing tests, reuse/adapt/reject decision and reason. Prioritize feature computation in binbot, then causal transformations, splits, data validation and provenance in PSX. Check rolling/centered windows, shifts, resampling, normalization, missing values and symbol boundaries. Do not infer past failure causes without results/configuration evidence.

Port only small justified components needed below. Avoid copying the complete older application or its dependency stack. Record source attribution and relevant license information for copied code. If neither source is accessible, mark the source-audit requirement BLOCKED, implement the standalone foundation, and carry the missing audit forward. Do not claim complete C1 acceptance.

Acceptance: evidence-linked audit for each accessible repository; precise blockers for inaccessible sources; every reused component mapped to source and new tests.

### T2 — Environment and reproducible structure

Create minimal package/scripts, tests, environment definition and documented commands. Separate raw cache, normalized data and artifacts. Exclude caches and secrets from Git. Record contract hash and source provenance.

Acceptance: documented environment creation/activation and one command each for ingestion, validation and tests; verified interpreter; resolved versions. No broad framework or dashboard is required.

### T3 — Fixed real-data ingestion sample

Use Binance public spot daily archives from https://data.binance.vision/ with format guidance at https://github.com/binance/binance-public-data.

The complete real-data sample is fixed:

- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT.
- Interval: 1 minute.
- UTC window: `[2024-12-30 00:00:00, 2025-01-03 00:00:00)`.
- At most 20 daily kline ZIPs and their published checksum files. Do not substitute dates or symbols when a file is unavailable; report missing coverage.
- Maximum real-data footprint: 250 MiB downloaded compressed data and 1 GiB local raw/normalized data. Stop further downloading on reaching either bound and document it.

These five symbols are engineering fixtures, not a validated trading universe or evidence about followers.

Verify published checksums before ingestion. Preserve immutable raw files and a manifest with URL, retrieval time, SHA-256, bytes, schema/parser version and source revision. Reuse verified cached data on rerun. Normalize timestamps explicitly: these archives cross Binance's January 2025 spot transition from milliseconds to microseconds. Preserve the raw timestamp values/units in provenance; reject ambiguous interpretation rather than guessing silently.

Retain UTC open/close times, OHLC, base volume, quote volume and trade count. Detect duplicate keys, unexpected ordering, invalid OHLC, negative volumes, timestamp cadence errors and gaps. Zero-trade intervals and unchanged prices must be flagged separately; unchanged price alone does not prove a stale executable quote. Do not forward-fill missing prices or invent bars.

Acceptance: data-quality report by symbol/day; expected complete grid of 5,760 one-minute bars per symbol, 28,800 total, with every discrepancy explained. Content-equivalent reruns must produce identical normalized-data hashes; retrieval logs may differ. Missing archives prevent full T3 PASS but not the remaining synthetic tests.

### T4 — Feature and timing integrity

Implement only simple backward-looking transformations: one-bar log returns, five-bar trailing log returns, and 20-bar sample standard deviation of one-bar log returns (`ddof=1`). Compute independently by symbol on contiguous valid bars, with warm-up values unavailable. Windows crossing a gap are unavailable. Nonpositive prices cannot enter logarithms.

Document that a bar's close-derived feature becomes available only after that bar closes; it cannot support a fill inside that bar. No labels, forecasts, fitted scalers or model scores are required.

Use legacy computation only where it meets these semantics. Test against hand-computable fixtures, not just against the same implementation in another wrapper. Tests must cover warm-up, gaps, symbol isolation, timestamp-unit boundaries and invariance of earlier features when later data are appended or changed. Preserve unavailable values; never replace them with zero for convenience.

Acceptance: exact documented feature definitions and passing independent numerical and causality tests. No predictive interpretation of sample features.

### T5 — Minimal synthetic ledger validation

Implement a small deterministic accounting component or fixture harness, not a strategy engine. Support USDT cash, asset units, executed fill prices, quote-denominated fees, and USDT mark-to-market equity. Failed orders must not change balances. Missing marks must produce explicit incomplete/unavailable valuation; never drop holdings or freeze an old mark silently. Do not allow borrowing or negative balances.

Required hand-checked cases:

1. Cash 1,000 USDT; buy exactly 1 unit at 100 with fee 0.001 of notional: cash 899.90, holdings 1; marked at 90, equity 989.90. Sell at 90 with the same fee: final cash 989.81.
2. A -> USDT -> B is two fills, charging a fee on each. B -> USDT -> A adds two more. Log each leg; compare with independently calculated expected balances.
3. Zero-fee constant-price round trip preserves equity; nonzero fees reduce it.
4. An open losing holding remains in equity. A missing price is explicitly unresolved. An unaffordable buy and failed fill leave balances unchanged.

Acceptance: passing tests and a short accounting example table. This is accounting verification only, with no real-data trades or performance report.

### T6 — Historical-universe feasibility and C2 decision inputs

Document how a future monthly point-in-time universe could be reconstructed. Separate historical membership evidence from current exchange metadata; current status does not establish past status, and an archive's existence does not establish uninterrupted tradability. Identify evidence for listing dates, suspensions, delistings, symbol migrations and exclusion categories. Distinguish a measured source from an unverified proposal.

Use documentation and at most 100 small public metadata/index HTTP requests (excluding T3); do not download additional candles. Inspect only a bounded index sample. If historical coverage is unresolved, say so; do not fabricate a complete universe.

Estimate bytes, rows, runtime and source coverage for a later study, including the cost of daily eligibility history across candidate symbols separately from minute bars for selected members. Clearly label extrapolations. Explain survivorship risks and what evidence is still needed. Do not select actual future test pairs, tune thresholds, or inspect performance to make these decisions.

Deliver `c2_decision_inputs.md` covering proposed universe reconstruction options, data limits, outstanding research choices, potential reuse and blockers. Historical-universe methodology may remain unresolved without failing a correctly executed feasibility task; unresolved evidence must prohibit claiming a reconstructed universe.

## Completion Criteria

C1 completion means reliable engineering evidence, not a profitable result. Mark each task PASS, PARTIAL, or BLOCKED with links. Overall PASS requires T1–T6 acceptance evidence; access/data failures cannot be relabeled PASS. Complete independent authorized tasks despite blockers. Stop at the stated milestone without progressing into empirical research.

## Delivery Requirements

Produce the flattened delivery file and artifacts containing:

- `reuse_audit.md`, `commands.md`, environment verification and resolved versions.
- Raw-data manifest, normalized data hashes and `data_quality.md`.
- Test results and synthetic accounting evidence.
- Historical-source feasibility notes and `c2_decision_inputs.md`.
- Initial/final Git status, code revision plus working-tree changes, contract hashes, file list, limitations and deviations.

Run `git diff --check`; if changes are staged, also run `git diff --cached --check`. Do not stage unrelated changes merely to run a gate. Distinguish untracked files from tracked diffs. Give exact commands to reproduce results from the cache and to obtain the bounded sample afresh.

## Executor Notes

This contract is authoritative for C1. The previous empirical proposal remains superseded. Do not change this contract to match implementation outcomes. Request clarification only for a genuine conflict that prevents authorized work, after completing independent tasks. Report evidence rather than confidence claims. The user/author will define C2 after reviewing this delivery.
