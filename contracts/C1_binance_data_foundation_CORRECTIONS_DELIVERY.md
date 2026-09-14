# C1 Binance Data Foundation Corrections Delivery

Delivery date: 2026-09-14

Repository: `/media/ata/Data/personal/binance-v2`

Correction contract: `contracts/C1_binance_data_foundation_CORRECTIONS_CONTRACT.md`

## Summary

Corrected the C1 implementation and regenerated derived outputs from the existing cache only. No C2 work was started.

Original C1 contract was preserved unchanged at SHA-256 `df9a9d2ce11fcf1e463e2cf772cf6ac6d8d83cb2d68acbad050489143779c5b3`. Correction contract was preserved unchanged at SHA-256 `3c74abbab957877b015da4c60336a1b12708f41800fea49d51e7bffd21a141cd`.

## Status by Requirement

R1 - Feature windows and isolation: PASS.

- Fixed five-bar return to exactly `log(close[t] / close[t-5])`.
- Rejects mixed-symbol rows and duplicate timestamps.
- Invalid/nonfinite/nonpositive closes break valid runs; unavailable values remain blank.
- Regression tests: `test_five_bar_returns_are_indexed_consecutive_windows`, `test_nonpositive_prices_make_features_unavailable`, `test_symbol_isolation_and_duplicate_rejection`, `test_sample_stddev_ddof_one_and_constant_sequence`, `test_gap_resets_windows`, `test_append_or_later_change_does_not_rewrite_prior_features`, `test_future_modification_does_not_rewrite_prior_features`.

R2 - Timestamp and availability semantics: PASS.

- Parser schema updated to `c1-kline-1m-v2`.
- Preserves raw integer timestamps and renders microsecond close timestamps with full precision.
- Feature availability is now `open_time + 60 seconds`, not the inclusive raw close timestamp.
- December 2024 files require milliseconds; January 2025 files require microseconds.
- Regression tests: `test_parse_preserves_raw_microseconds_and_normalizes_ms`, `test_parse_rejects_wrong_units_and_malformed_close_time`, `test_availability_is_next_interval_boundary`.

R3 - Ledger validation and synthetic bridge integrity: PASS.

- Validates initial cash/holdings, units, prices, fee rates, overflow, and marks.
- Malformed inputs raise `ValueError`; unaffordable/insufficient valid orders return `False`.
- Synthetic `bridge_swap` applies on temporary state and commits only after both legs succeed.
- Regression tests include zero destination price atomicity, invalid marks, invalid fees, insufficient holdings, buy notional overflow, sell cash-addition overflow, buy holdings-addition overflow, and the original `899.90 / 989.90 / 989.81` case.

R4 - Data validation blocks usable outputs: PASS.

- Ingestion stages normalized outputs and replaces existing files only after complete successful validation.
- Missing cache, checksum mismatch, malformed rows, invalid OHLC/numeric values, negative trade counts, duplicates/gaps, and resource-limit failures are non-successful and preserve prior outputs.
- Feature CLI checks the current validation manifest and normalized content hashes before producing features. It requires the five expected symbols in the requested normalized directory and rejects manifests from another directory, missing files, extra files, and mutations after validation.
- The CLI passes only the exact verified normalized file list into feature generation; compute-time exceptions write through a staged temp file and preserve an existing feature artifact.
- Regression tests: `test_feature_cli_rejects_manifest_for_another_directory`, `test_feature_cli_rejects_missing_and_extra_normalized_files`, `test_feature_cli_rejects_mutation_after_validation`, `test_feature_cli_failure_preserves_existing_output`, `test_feature_cli_compute_exception_preserves_existing_output`, `test_feature_cli_passes_only_verified_file_list`, `test_ingest_offline_cache_failure_preserves_existing_outputs`, `test_ingest_reports_checksum_mismatch_without_publishing`, `test_ingest_resource_limit_failure_preserves_outputs`, `test_validate_rejects_nan_negative_trades_duplicates_gaps_and_bad_ohlc`.

R5 - Provenance and bounds: PASS.

- Manifest now records `cache_verification_time_utc` and `original_retrieval_time_utc: unknown` instead of inventing retrieval time.
- Source/test/config hashes are recorded in `artifacts/c1_binance_data_foundation/corrections/hash_manifest.md`.
- Streaming download writes via a temporary file; ingestion enforces configurable compressed, decompressed, normalized-write, existing-output and staging-footprint byte limits against remaining budget. Archive and checksum downloads both receive the remaining local-storage budget after accounting for existing raw/normalized files.
- A download resource breach returns explicit `resource_limit`, removes incomplete temp files, preserves existing valid outputs, and stops subsequent archive/checksum requests.
- Resource-boundary regressions: `test_ingest_counts_cached_compressed_file_once`, `test_ingest_local_staging_limit_preserves_existing_output`, `test_ingest_decompression_uses_remaining_local_budget_and_preserves_output`, `test_downloads_cannot_exceed_remaining_local_budget_and_stop_requests`, `test_checksum_download_respects_remaining_local_budget_and_stops_requests`, plus mocked/local checksum and cache-failure tests. No public services are called by these tests.
- Reuse-audit wording should be interpreted factually: absence of a LICENSE creates ownership/third-party uncertainty, not proof that the user cannot reuse their own code.

R6 - Offline regeneration and delivery: PASS.

- Verified environment: Python `3.11.16`, executable `/home/ata/miniconda3/envs/binance-v2-research/bin/python`.
- Ran full suite: `38 passed in 0.48s`.
- Download-budget regressions: `13 passed in 0.10s` for `tests/test_ingest.py`; focused correction set: `29 passed in 0.49s`.
- Revalidated the existing 20 ZIPs/checksums and regenerated 28,800 normalized rows plus 28,800 feature rows from cache only.
- Two offline runs produced identical normalized and feature hashes.
- Raw ZIP/checksum files were not redownloaded or modified.

## Regenerated Hashes

Corrected normalized data:

```text
f55c79b9571eada31643fafc066c716db890c7126bfe0af9ef89e63fc891824a  BNBUSDT
a560fdc4638cfd6e29a07e67dd0a535d47304936f1fd0d03cccad6b427894cd0  BTCUSDT
6e74d30a4d831936d6bbb0588b8061d512819e33d3e931c80e7811588a2f28de  ETHUSDT
18e2044c221c89659d14b3660b5a586f90bb8b81bb15937034142f987bbf8b86  SOLUSDT
70679048e28ba85bdc505e51c9731e3d06da0df0c4bd3ba81aff961314a33b8b  XRPUSDT
```

Corrected features: `1f6b7b267612940d62d108fc29eb4c5c145a6a2f8683d548995fe11c275894a4`.

Original C1 feature hash was `8634e5d2e4d3589fb7c085a920e29ea5bbbd39e25188a2f3cf18f23aba2229cc`; the change is expected from corrected five-bar windows and availability semantics. Original normalized hashes also changed because normalized close-time precision and schema/parser version changed.

## Evidence Files

- `artifacts/c1_binance_data_foundation/corrections/environment_evidence.md`
- `artifacts/c1_binance_data_foundation/corrections/hash_manifest.md`
- `artifacts/c1_binance_data_foundation/corrections/test_output.md`
- `artifacts/c1_binance_data_foundation/raw_manifest.json`
- `artifacts/c1_binance_data_foundation/data_quality.json`
- `artifacts/c1_binance_data_foundation/data_quality.md`
- `artifacts/c1_binance_data_foundation/normalized_hashes.json`
- `artifacts/c1_binance_data_foundation/features.csv`

Review archive: `/media/ata/Data/personal/binance-v2/binance-c1-corrections-review.tar.gz`

## Code Diff Summary

- `features.py`: fixed five-bar indexing, invalid-run handling, duplicate/mixed-symbol rejection, and next-boundary availability.
- `ingest.py`: added parser schema v2, strict timestamp unit/close validation, finite OHLC/volume/trade-count checks, staged output replacement, cache-failure reporting, provenance wording, byte limits, and remaining-local-budget enforcement for archive/checksum downloads.
- `cli.py`: exits nonzero on failed ingest, refuses feature generation from failed/stale/incomplete validation manifests, and binds feature computation to the exact verified input files.
- `ledger.py`: added finite/nonnegative validation, fee bounds, pre-mutation overflow checks including sell cash-addition and buy holdings-addition overflow, mark error states, and atomic synthetic bridge commits.
- Tests expanded from 11 to 38 focused regressions.

## Outstanding Limitations

- No claim is made that C1 is accepted; this delivery provides correction evidence for review.
- Historical universe reconstruction remains unresolved from C1 and is not advanced here.
- The legacy full-series-quantile finding remains a potential issue only, not a proven explanation of prior strategy outcomes.
