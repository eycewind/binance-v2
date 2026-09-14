# C1 Corrections Test Output

Commands executed in `binance-v2-research`:

```text
conda run -n binance-v2-research env PYTHONPATH=src pytest -q
......................................                                   [100%]
38 passed in 0.48s
```

Focused regression command:

```text
conda run -n binance-v2-research env PYTHONPATH=src pytest -q tests/test_cli.py tests/test_ledger.py tests/test_ingest.py
.............................                                            [100%]
29 passed in 0.48s
```

Download-budget regression command:

```text
conda run -n binance-v2-research env PYTHONPATH=src pytest -q tests/test_ingest.py
.............                                                            [100%]
13 passed in 0.10s
```

Offline regeneration commands:

```text
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli ingest --offline
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli features
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli ingest --offline
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli features
```

Both offline ingest runs returned `success: true` with `rows_total: 28800`, using the existing 40-file cache only.

Run 1 ingest timestamp: `2026-09-14T10:38:00.212689+00:00`.

Run 2 ingest timestamp: `2026-09-14T10:38:16.661775+00:00`.

Row counts after regeneration:

```text
   5761 data/normalized/binance_vision/BNBUSDT_1m_normalized.csv
   5761 data/normalized/binance_vision/BTCUSDT_1m_normalized.csv
   5761 data/normalized/binance_vision/ETHUSDT_1m_normalized.csv
   5761 data/normalized/binance_vision/SOLUSDT_1m_normalized.csv
   5761 data/normalized/binance_vision/XRPUSDT_1m_normalized.csv
  28801 artifacts/c1_binance_data_foundation/features.csv
  57606 total
```
