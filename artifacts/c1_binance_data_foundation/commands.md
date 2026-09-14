# C1 Commands

Run from `/media/ata/Data/personal/binance-v2`.

## Environment

```bash
conda create -n binance-v2-research python=3.11 -y
conda install -n binance-v2-research pytest -y
conda run -n binance-v2-research python -c 'import os,sys,platform; print("CONDA_DEFAULT_ENV="+str(os.environ.get("CONDA_DEFAULT_ENV"))); print("python="+platform.python_version()); print("executable="+sys.executable)'
```

Verified:

```text
CONDA_DEFAULT_ENV=binance-v2-research
python=3.11.16
executable=/home/ata/miniconda3/envs/binance-v2-research/bin/python
```

Resolved dependency record:

```text
python=3.11.16
pytest=9.0.3
pip=26.2.1
setuptools=83.0.0
packaging=26.3
pluggy=1.6.0
iniconfig=2.3.0
pygments=2.20.0
```

Full conda export is available from:

```bash
conda run -n binance-v2-research conda list --export
```

## Ingestion

Obtain the bounded sample afresh or reuse any verified cache:

```bash
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli ingest
```

Reproduce from cache without network:

```bash
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli ingest --offline
```

Observed offline rerun normalized hashes matched the network run:

```text
BNBUSDT c5fdc5ff629dccfd3abf85d87fcc8f7c7b6eee63597780a7b4f71cc55c73360e
BTCUSDT cb8a531f7af9aebb7c3ee61abf5e2643523da7c9cb5b7d1adfda02f5c01637d4
ETHUSDT 4f455da86f6c5edbfdfd363391b89448932714d07dbae459a54a1ae07f14afb0
SOLUSDT 43668faa9e4ec3146a2e897b5e7108d9508449d137b2349cf1f082a5d2cc9b53
XRPUSDT 105a07dd69efd4a524fccf2bc427216c33c99b7fecea4164e3ca418dce5b3b42
```

## Features

```bash
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.cli features
```

Observed output: `artifacts/c1_binance_data_foundation/features.csv`, SHA-256 `8634e5d2e4d3589fb7c085a920e29ea5bbbd39e25188a2f3cf18f23aba2229cc`.

## Tests and Checks

```bash
conda run -n binance-v2-research pytest -q
git diff --check
```

Observed tests:

```text
11 passed in 0.03s
```

## Metadata Request

One bounded public metadata request was used for feasibility notes:

```bash
conda run -n binance-v2-research python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('https://api.binance.com/api/v3/exchangeInfo?permissions=SPOT&showPermissionSets=true', timeout=60)); sy=d['symbols']; usdt=[s for s in sy if s.get('quoteAsset')=='USDT']; print({'serverTime':d.get('serverTime'),'symbols':len(sy),'usdt_pairs':len(usdt),'trading_usdt_pairs':sum(s.get('status')=='TRADING' for s in usdt),'sample_usdt_symbols':[s['symbol'] for s in usdt[:10]]})"
```

Observed summary:

```text
{'serverTime': 1789313306122, 'symbols': 3658, 'usdt_pairs': 702, 'trading_usdt_pairs': 490, 'sample_usdt_symbols': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'BCCUSDT', 'NEOUSDT', 'LTCUSDT', 'QTUMUSDT', 'ADAUSDT', 'XRPUSDT', 'EOSUSDT']}
```
