# C1 Binance Data Foundation Delivery

Delivery date: 2026-09-13

Executor: Codex

Contract: `contracts/C1_binance_data_foundation_CONTRACT.md`

Contract SHA-256 before execution: `df9a9d2ce11fcf1e463e2cf772cf6ac6d8d83cb2d68acbad050489143779c5b3`

Contract SHA-256 after execution: `df9a9d2ce11fcf1e463e2cf772cf6ac6d8d83cb2d68acbad050489143779c5b3`

## Summary

C1 stopped at the data-foundation milestone. The superseded empirical-experiment proposal was not executed or modified.

Implemented a minimal native package for checksum-verified Binance public archive ingestion, fixed-sample validation, causal backward-looking features, and deterministic synthetic ledger checks. Downloaded only the authorized 20 daily 1m spot ZIPs plus 20 checksum files. The normalized fixed sample has 28,800 one-minute rows, no duplicate keys, no cadence gaps, and deterministic normalized hashes on offline rerun.

No model fitting, parameter search, pair ranking, real-data strategy backtest, live/paper trading, or C2 contract creation was performed.

## Repository Evidence

- Target path: `/media/ata/Data/personal/binance-v2`
- Branch: `main`
- Commit: `0506ee07188a94ebbd4dc52ed9af79b98a71a9b2`
- Initial status: `?? artifacts/`, `?? contracts/`
- No `AGENTS.md` files were found in the target repo or inspected reference repos.
- Final status is untracked C0/C1 contract/artifact work plus new package files; no files were staged.

## Task Status

T1 - Audit source reuse and capture provenance: PASS.

- Evidence: `artifacts/c1_binance_data_foundation/reuse_audit.md`.
- Binbot inspected at `/tmp/c1-binbot-inspect`, commit `6b49484d0a82ab0737f0d446ab60041892b606f6`, clean.
- PSX inspected at `/media/ata/Data/personal/psx/psx-ml-research`, commit `b46fc51dcb1e380b80c8a68dcc8aad49071793a8`, clean detached HEAD.
- No code was copied verbatim from either reference repo. Concepts adapted: provenance manifests, missing/stale distinction, point-in-time eligibility discipline, and failed-order immutability.
- License blocker: no license files found in the inspected binbot or PSX top-level areas. This prevented direct code copying and supports the native reimplementation decision.

T2 - Environment and reproducible structure: PASS.

- Evidence: `environment.yml`, `pyproject.toml`, `src/binance_data_foundation/`, `tests/`, `artifacts/c1_binance_data_foundation/commands.md`.
- Dedicated env created: `binance-v2-research`.
- Verified interpreter:

```text
CONDA_DEFAULT_ENV=binance-v2-research
python=3.11.16
executable=/home/ata/miniconda3/envs/binance-v2-research/bin/python
```

- Minimal dependencies: Python 3.11 runtime; pytest 9.0.3 for tests.
- Raw cache: `data/raw/binance_vision/`.
- Normalized data: `data/normalized/binance_vision/`.
- Reports/artifacts: `artifacts/c1_binance_data_foundation/`.

T3 - Fixed real-data ingestion sample: PASS.

- Evidence: `artifacts/c1_binance_data_foundation/raw_manifest.json`, `artifacts/c1_binance_data_foundation/data_quality.md`, `artifacts/c1_binance_data_foundation/normalized_hashes.json`.
- Source docs used: `https://github.com/binance/binance-public-data` and `https://data.binance.vision/`.
- Files downloaded: 20 ZIPs and 20 `.CHECKSUM` files.
- Raw footprint: `1.3M`; normalized footprint: `6.7M`; artifact report footprint: `36K`.
- Rows: 5 symbols x 4 days x 1,440 minutes = 28,800 rows.
- All symbol/day files passed checksum and validation.
- Timestamp-unit transition observed and preserved:
  - `2024-12-30` and `2024-12-31`: milliseconds.
  - `2025-01-01` and `2025-01-02`: microseconds.
- Offline rerun reproduced identical normalized hashes:
  - BNBUSDT: `c5fdc5ff629dccfd3abf85d87fcc8f7c7b6eee63597780a7b4f71cc55c73360e`
  - BTCUSDT: `cb8a531f7af9aebb7c3ee61abf5e2643523da7c9cb5b7d1adfda02f5c01637d4`
  - ETHUSDT: `4f455da86f6c5edbfdfd363391b89448932714d07dbae459a54a1ae07f14afb0`
  - SOLUSDT: `43668faa9e4ec3146a2e897b5e7108d9508449d137b2349cf1f082a5d2cc9b53`
  - XRPUSDT: `105a07dd69efd4a524fccf2bc427216c33c99b7fecea4164e3ca418dce5b3b42`

T4 - Feature and timing integrity: PASS.

- Evidence: `src/binance_data_foundation/features.py`, `tests/test_features.py`, `artifacts/c1_binance_data_foundation/features.csv`.
- Implemented only:
  - `ret_1_log = log(close_t / close_t-1)`
  - `ret_5_log = log(close_t / close_t-5)`
  - `vol_20_ret_1_log = sample standard deviation, ddof=1, of the last 20 one-bar log returns`
- Features are computed independently by symbol file and reset across cadence gaps.
- Nonpositive close values make affected log-return features unavailable.
- Feature availability is recorded as `available_after_utc`, equal to the bar close time. These close-derived features cannot support fills inside the same bar.
- Tests cover warm-up, gaps, timestamp-unit parsing, append invariance, nonpositive prices, and deterministic sorting.
- Feature CSV rows: 28,800 data rows plus header. SHA-256: `8634e5d2e4d3589fb7c085a920e29ea5bbbd39e25188a2f3cf18f23aba2229cc`.

T5 - Minimal synthetic ledger validation: PASS.

- Evidence: `src/binance_data_foundation/ledger.py`, `tests/test_ledger.py`, `artifacts/c1_binance_data_foundation/accounting_examples.md`.
- Required case 1 observed:
  - After buy: cash `899.90`, holdings `1`, marked at `90`, equity `989.90`.
  - After sell at `90`: final cash `989.81`.
- Bridge rotation is modeled as separate source sell and destination buy legs, charging fees on each fill.
- Failed orders do not mutate balances or fill logs.
- Missing marks return explicit unresolved valuation rather than freezing or dropping holdings.
- Borrowing and negative balances are rejected by affordability/position checks.

T6 - Historical-universe feasibility and C2 decision inputs: PASS with unresolved universe blocker.

- Evidence: `artifacts/c1_binance_data_foundation/c2_decision_inputs.md`.
- One current Binance `exchangeInfo` summary request returned `3658` spot-permission symbols, `702` USDT pairs, and `490` currently trading USDT pairs. This is current metadata only.
- Historical universe reconstruction remains unresolved, as required by evidence: current metadata does not prove past listing status, archive existence does not prove uninterrupted tradability, and announcements need systematic collection/parsing.
- No future test pairs, thresholds, or performance-based selections were chosen.

## Test Results

```text
conda run -n binance-v2-research pytest -q
...........                                                              [100%]
11 passed in 0.03s
```

## Reproduction Commands

See `artifacts/c1_binance_data_foundation/commands.md`.

Fresh bounded sample:

```bash
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli ingest
```

Cache-only rerun:

```bash
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli ingest --offline
```

Features:

```bash
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli features
```

Tests:

```bash
conda run -n binance-v2-research pytest -q
```

## Deliverables

- `environment.yml`
- `pyproject.toml`
- `.gitignore`
- `src/binance_data_foundation/__init__.py`
- `src/binance_data_foundation/cli.py`
- `src/binance_data_foundation/ingest.py`
- `src/binance_data_foundation/features.py`
- `src/binance_data_foundation/ledger.py`
- `tests/test_ingest.py`
- `tests/test_features.py`
- `tests/test_ledger.py`
- `artifacts/c1_binance_data_foundation/reuse_audit.md`
- `artifacts/c1_binance_data_foundation/commands.md`
- `artifacts/c1_binance_data_foundation/data_quality.md`
- `artifacts/c1_binance_data_foundation/raw_manifest.json`
- `artifacts/c1_binance_data_foundation/data_quality.json`
- `artifacts/c1_binance_data_foundation/normalized_hashes.json`
- `artifacts/c1_binance_data_foundation/features.csv`
- `artifacts/c1_binance_data_foundation/accounting_examples.md`
- `artifacts/c1_binance_data_foundation/c2_decision_inputs.md`

## Limitations and Deviations

- Initial sandboxed ingestion could not resolve `data.binance.vision`; rerun with approved network escalation completed the authorized sample.
- The temporary binbot inspection clone is outside the target repository at `/tmp/c1-binbot-inspect`; it was used read-only.
- No complete historical Binance spot membership source was established. C2 must not claim a point-in-time universe until listing/removal/suspension/migration evidence is collected.
- No reference-repo license files were found, so no source code was copied.
- `data/raw/` and `data/normalized/` are gitignored caches. Reproducibility evidence is recorded via manifests and hashes.

## Correction Supersession Note

Added 2026-09-13: this historical C1 delivery is superseded in part by `contracts/C1_binance_data_foundation_CORRECTIONS_DELIVERY.md`. The correction milestone fixed feature-window indexing, timestamp availability/precision semantics, ingestion failure blocking, provenance wording, resource-bound checks, and synthetic ledger validation/atomicity. The original claims above are preserved for review history rather than rewritten in place.
