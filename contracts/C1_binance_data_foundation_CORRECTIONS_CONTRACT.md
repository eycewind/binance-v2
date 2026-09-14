# C1 — Data Foundation Corrections

Status: authorized C1 correction milestone. No C2 execution.

Repository: `/media/ata/Data/personal/binance-v2`.
Save this contract as `contracts/C1_binance_data_foundation_CORRECTIONS_CONTRACT.md`.
Deliver to `contracts/C1_binance_data_foundation_CORRECTIONS_DELIVERY.md`.
Correction evidence: `artifacts/c1_binance_data_foundation/corrections/`.

## Background

Review of the C1 archive reproduced incorrect five-bar returns, invalid-window features, mixed-symbol computation, nonfinite ledger values, a bridge failure that mutates state, and ingestion that accepts invalid values or returns success with no cached data. The reported 11 tests did not cover these cases. C1 is not yet accepted.

These are code-review findings from the supplied implementation, independently exercised in a Python 3.12 review runtime. They are not a reproduction of the user's conda/Python 3.11 test run. This correction milestone must reproduce and fix them in the verified project environment.

## Objective

Correct the existing C1 implementation, add independent regression evidence, and regenerate derived artifacts from the already authorized cache. Establish compliance with the original C1 engineering scope. Do not evaluate trading performance.

## Scope / Out of Scope

In scope: minimal fixes to ingestion, feature computation, ledger, CLI failure handling, provenance and resource-bound enforcement; focused tests; offline regeneration and delivery.

Out of scope: new symbols or dates, new downloads, metadata requests, further repository cloning, model fitting, strategy backtests, pair ranking, dashboards, real/paper trading, account credentials and C2 drafting/execution. Do not refactor unrelated functionality or expand feature sets.

## Architectural Constraints

- Read applicable AGENTS.md and the original `contracts/C1_binance_data_foundation_CONTRACT.md`. Preserve both that contract and this correction contract unchanged; record before/after hashes. The original reported hash is `df9a9d2ce11fcf1e463e2cf772cf6ac6d8d83cb2d68acbad050489143779c5b3`; report any discrepancy without editing to force a match.
- This contract supplements C1. It specifies synthetic bridge atomicity and offline correction work more precisely. Do not reinterpret a synthetic atomic helper as realistic exchange-order atomicity.
- Verify `binance-v2-research`, Python version and `sys.executable` before Python/tests. Preserve the dedicated environment; do not install into base, binbot or psx-ml-research. No new dependency should be necessary.
- Record initial Git status, HEAD and hashes of relevant source/test/config files before modifying them. Preserve unrelated and untracked user work. Do not push or modify reference/production repositories.
- Preserve a copy/hash record of the old C1 delivery and affected evidence before updating generated artifacts. Do not rewrite the historical delivery's original claims: append a clearly dated correction/supersession note linking to the new correction delivery.
- Treat cached ZIPs and published checksum files as immutable. Do not redownload on cache failure. Report exact missing/corrupt inputs and complete independent synthetic work.
- Keep changes within the target repository or task temporary directories. Use flattened contract/delivery paths.

## Tasks and Acceptance Evidence

### R1 — Correct feature windows and prove isolation

Five-bar log return is exactly `log(close[t] / close[t-5])` after five elapsed one-minute bars. The present deque logic shifts to six elapsed bars after the first valid result. Correct this without changing the feature definition.

Required regression evidence:

- For closes `[1,2,3,4,5,6,7,8]`, outputs at indices 5, 6 and 7 equal `log(6/1)`, `log(7/2)` and `log(8/3)` respectively. Test additional consecutive windows using an independent indexed oracle.
- Nonpositive or nonfinite close values invalidate the current observation and break valid runs. A five-bar return needs six consecutive valid closes; 20-return volatility needs 21. Windows crossing a missing minute or invalid observation remain unavailable until rebuilt. `[1,2,0,4,5,6]` must have no five-bar return at index 5.
- Enforce the single-symbol API: reject mixed-symbol rows explicitly rather than computing cross-symbol returns. Test that the multi-file workflow processes two symbols independently and matches separate runs. Reject duplicate timestamps; deterministic sorting of unique rows remains allowed.
- Verify sample standard deviation numerically with independent expected values, including a nonconstant return sequence and a constant-return sequence. Confirm `ddof=1` and warm-up boundaries; a merely nonempty output is insufficient.
- Test both future appends and modifications strictly after a cutoff; earlier outputs must be unchanged. Test gap recovery and invalid-price recovery over sufficient bars.
- Unavailable numeric outputs remain unavailable, not zero. No labels or new fitted transforms.

Acceptance: all specified window, numerical, symbol and causality tests pass; corrected feature hashes are regenerated in R6.

### R2 — Correct timestamp and availability semantics

Retain original integer timestamps and units. Preserve normalized close-time precision, using integer arithmetic to avoid float truncation. Millisecond fields may remain for compatibility but must not be treated as exact microsecond close times.

For one-minute candles, the earliest feature availability is the UTC interval-end boundary (`open_time + 60 seconds`), never the inclusive close timestamp inside that interval. This is a theoretical minimum; no execution fill assumption is introduced.

Validate raw open alignment and close timestamp against the expected one-minute interval in the row's units. For this fixed sample, require milliseconds in the December 2024 files and microseconds in January 2025 files. A magnitude check alone does not prove date/unit consistency. Reject ambiguous or inconsistent rows with a clear diagnostic.

Acceptance: tests cover the 2024/2025 boundary, an actual microsecond-form close ending in `999999`, wrong/mixed units, and malformed close times. Availability equals the next interval boundary exactly for both formats. Update schema/parser version for changed normalized semantics.

### R3 — Ledger input validation and synthetic bridge failure integrity

Validate initial cash and holdings as finite and nonnegative. Fill units and prices must be finite and strictly positive. For this fee-only fixture, define accepted fee rates as finite `0 <= fee_rate < 1`; fee rebates are out of scope. Reject nonfinite computed notionals/fees/balances, including arithmetic overflow, before mutation.

Missing, negative or nonfinite marks produce an explicit unresolved/error valuation, never status `complete` with NaN/Infinity. A finite zero mark is permitted to represent a total loss. Validate marks only as required for held assets. Preserve open losing positions in equity.

Retain boolean rejection for valid but unaffordable buys/insufficient-position sells; malformed inputs may raise a documented ValueError. Every rejected/error operation leaves cash, holdings and fills unchanged. Floating-point tolerances must not allow a real negative balance; test boundary amounts and document any tiny-residual normalization.

Define `bridge_swap` as a synthetic atomic convenience: prevalidate both legs and apply on temporary state, committing only when both succeed. On False or exception, the original ledger is unchanged. This helper must not suggest that actual executed exchange trades can be rolled back. Reject identical source/destination for this two-asset fixture.

Required tests include destination price zero, NaN/Infinity units/prices/fees, negative fees, insufficient holdings, invalid initial state, invalid marks, and arithmetic overflow. Explicitly reproduce the zero-destination bug: starting with 10 A, price A=10 and fee=0.001 must leave the entire original state unchanged after rejection.

Retain and numerically verify the original 899.90 / 989.90 / 989.81 example, zero-fee roundtrip, and all four legs of A->USDT->B->USDT->A. Check expected balances and per-leg fees, not just the number of fills or a final inequality.

Acceptance: explicit input/failure semantics and independent numerical state assertions pass.

### R4 — Make data validation failures block usable outputs

Require finite strictly positive OHLC, valid high/low relationships, finite nonnegative volumes, and integer nonnegative trade counts. Validate symbol, interval, exact daily grid, ordering, duplicates and time semantics. Missing/corrupt/checksum-failed/malformed archives must be individually reported, not passed silently.

Failed validation must not publish affected rows as usable normalized data. Stage outputs before replacement: if the fixed sample is incomplete or invalid, retain existing good outputs, write a failure report, and make the CLI exit nonzero. The feature CLI must reject empty/incomplete or stale/unvalidated input sets by checking the current successful validation manifest and content hashes; it must not produce a misleading success header-only CSV.

Tests must use synthetic temporary archives and monkeypatched/local I/O only. Cover: empty offline cache; one missing archive; checksum mismatch; malformed row; NaN/Infinity; negative trade count; duplicate/gap; invalid OHLC; and full valid fixture. Assert CLI exit status and preservation of earlier good outputs on failure. Test input mutation after validation. Do not call public services.

Acceptance: invalid data and incomplete ingestion cannot be consumed through the normal feature command as validated data. Reports still identify all inspectable failures.

### R5 — Preserve provenance and enforce bounds

Separate immutable original download/retrieval evidence from each cache verification run. Existing manifests may contain a cache-verification time mislabeled as retrieval time: preserve the original artifact as evidence but label the true initial retrieval time unknown unless independent records establish it. Do not invent or backdate timestamps.

Record source revision and working-tree implementation hashes for each run. HEAD alone does not identify untracked code. Hash relevant source/tests/configuration with a deterministic file manifest; exclude mutable output files to avoid a circular hash. Tie normalized and feature hashes to parser/schema version, input hashes and producing run. Record resolved environment versions in an actual artifact, not just a command that could export them.

Implement the original resource bounds: 250 MiB cumulative compressed ZIP downloads and 1 GiB local raw/normalized footprint. Bound reads/writes with streaming checks and temporary files, including decompression/normalization; do not read an unlimited response into memory first. Count existing relevant cache bytes for local footprint. A limit breach must be explicit, non-successful and leave prior valid outputs intact. Test these paths with small configurable test limits and mocked responses; actual correction execution remains offline.

Acceptance: offline reruns preserve original retrieval evidence, update verification records and reproduce identical data/feature content hashes. Resource-limit tests pass without network calls.

### R6 — Offline regeneration, evidence and delivery

After targeted regressions pass, run the full project suite in the verified environment. Revalidate the authorized 20 cached ZIPs/checksums and regenerate the same 28,800-row sample and features. No new data. If the cache is missing/corrupt, mark regeneration BLOCKED and complete other tasks; do not claim reproduced data results.

Run twice from cache and compare normalized and feature content hashes. Changed hashes versus original C1 are expected for corrected feature/timestamp semantics; explain them. Raw ZIP/checksum hashes must remain unchanged. Record exact commands, statuses, row counts, data-quality results and before/after hashes.

Update reuse-audit wording: absence of LICENSE alone does not establish that the user cannot reuse their own code. Record ownership/third-party uncertainty factually. No new source inspection or copying is needed. Keep the reported legacy full-series-quantile finding as a potential issue, not a proven explanation of previous strategy failure.

Run `git diff --check`; also run `git diff --cached --check` if staged changes exist. Record final status and a code/test/config hash manifest including untracked implementation files. Do not stage unrelated work merely to satisfy a check.

## Completion Criteria

For R1–R6, provide PASS/PARTIAL/BLOCKED with exact tests and artifacts. Overall completion requires all regression checks and successful offline regeneration; do not call C1 accepted on the user's behalf. A clean diff or a test count alone is not acceptance evidence. Stop after delivering the corrections.

## Delivery Requirements

Produce the flattened correction delivery and artifacts under the correction root, including:

- Findings-to-fix/test mapping with exact regression names and numerical examples.
- Environment evidence, test output and commands.
- Initial/final contract hashes and source/test/config hash manifests.
- Preserved pre-correction evidence and changed-output explanation.
- Updated data-quality/provenance records and two-run hash comparison.
- Outstanding limitations and a concise source diff summary.

Also create `binance-c1-corrections-review.tar.gz` at the repository root for review. Include both C1 contract files, original delivery plus correction delivery, package source, tests, environment/build definitions, `.gitignore`, and C1 markdown/JSON/text evidence. Include all manifests, hashes and test logs. Exclude raw ZIP caches, normalized/feature datasets, conda environments, Git internals and credentials. List the archive contents and report its absolute path and SHA-256. Do not upload or push it automatically.

## Executor Notes

Complete the authorized correction work without widening research scope. Use small, independent fixtures; avoid tests that merely repeat implementation logic. Preserve the original contract and historical claims with clear supersession notes. Return the correction delivery and review archive path; await review before C2.
