# Binance Retired E1/P0 Model Viewer

> **RETIRED MODEL — ANALYSIS / REFERENCE ONLY.** This application is a read-only archival viewer. It does not produce recommendations, recompute signals in the browser, tune the model, retrain anything, write to a database, or contact Binance.

## Purpose

The viewer visually audits the formally retired `E1_H1_SMA24_CROSS_V1` entry model and `P0_H1_SMA24_CROSSDOWN_V1` exit model over the accepted, frozen 2,199-trade population for BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT. It retains the useful interactive chart, selectors, range controls, zoom, and pan concepts of the PSX signal viewer while replacing all PSX and browser-side signal-generation logic.

## Architecture and data integrity

- `api/`: FastAPI GET-only service and focused tests.
- `src/`: Vite/React visualization. React receives accepted trade records; it contains no E1/P0 generator or what-if controls.
- Trade identity: `artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv`, verified against SHA-256 `6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3`.
- P0 exits, MFE/MAE and surrender: accepted C2 `common_horizons_p0.csv`.
- Gross and C_BASE net returns: accepted C2 `p0_trade_records.csv` (`C_BASE` is 10 bp fee plus 2 bp adverse slippage per executed leg).
- Optional first-T2 timestamp: accepted C7 `population_manifest.json`.
- OHLCV: accepted C2 local normalized 1m history and frozen 5m inputs. The default is 5m; 1m is selectable.
- H1 SMA24: reconstructed by the backend from accepted frozen 1h closes and exposed only from each completed bar's `available_at_ms`. It is an overlay, not a signal recomputation.

All paths are resolved relative to the repository root, derived from `api/data.py`; there is no required data-path environment variable. Only explicit accepted filenames are opened. Requests at or beyond `2026-01-01T00:00:00Z` are rejected, and source rows/availability at that boundary are fail-closed. The service has no mutating route and performs no file or database writes.

The accepted C2 artifacts contain authoritative MFE timing but not MAE timing. Therefore `mae_return` is present, `mae_ts` is `null`, and the UI does not invent an MAE marker. Exit reason and first-T2 time are shown when present.

## Start the backend

Use the required Conda environment and verify its interpreter before installing the viewer's three runtime/test packages:

```bash
cd /media/ata/Data/personal/binance-v2/tools/retired-model-viewer
conda activate binance-v2-research
which python
python --version
python -m pip install -r api/requirements.txt
python -m uvicorn api.app:app --reload --port 8000
```

Verify with `curl http://127.0.0.1:8000/health`.

## Start the frontend

In a second terminal:

```bash
cd /media/ata/Data/personal/binance-v2/tools/retired-model-viewer
npm install
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

Open `http://localhost:5173/`. For a production bundle, run `npm run build` and optionally `npm run preview`.

## API

- `GET /health` — integrity/mode/model summary and frozen population hash.
- `GET /symbols` — the fixed five-symbol universe.
- `GET /trades` — accepted trades. Filters: `symbol`, `year`, `outcome=profitable|losing`, `positive_mfe_negative_exit=true`, and decimal `min_mfe` (for example `0.01`).
- `GET /trades/{trade_id}` — one accepted trade.
- `GET /ohlcv/{symbol}?start=...&end=...&interval=5m|1m` — bounded pre-2026 local OHLCV with causal H1 SMA24 overlay.

## Tests

From the viewer directory after installing backend requirements:

```bash
conda activate binance-v2-research
python -m pytest api/test_app.py -q
npm run build
git -C /media/ata/Data/personal/binance-v2 diff --check
```

The backend tests cover health, symbols, exact 2,199 population reconciliation, trade lookup, OHLCV, 2026 rejection, source immutability, and absence of mutating HTTP methods.

## Troubleshooting

- `ModuleNotFoundError: fastapi`: activate `binance-v2-research` and install `api/requirements.txt` with that environment's `python -m pip`.
- API network error in the browser: confirm the backend is listening on port 8000 and `VITE_API_URL` matches it.
- Port already in use: choose another backend port and set the same port in `VITE_API_URL`.
- Integrity error or a trade count other than 2,199: restore/verify the accepted C2 artifacts; do not regenerate or edit them for this viewer.
- Empty OHLCV result: keep the requested range within the accepted 2024–2025 display window and use one of the five supported symbols.
- Large 1m query rejected: narrow the requested time span; the endpoint caps responses at 50,000 bars for browser safety.

This viewer is not a live trading tool. It must remain read-only, offline from Binance, and limited to accepted pre-2026 market data.
