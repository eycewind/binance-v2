import hashlib
from pathlib import Path
import pytest
import httpx
from api.app import app
from api.data import EXPECTED_COUNT, EXPECTED_ENTRY_SHA256, load_trades
ROOT=Path(__file__).resolve().parents[3]
@pytest.fixture
def anyio_backend(): return "asyncio"
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
async def request(method,path,**kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client: return await client.request(method,path,**kwargs)
@pytest.mark.anyio
async def test_health():
    body=(await request("GET","/health")).json(); assert body["status"]=="ok"; assert body["mode"]=="read-only"
@pytest.mark.anyio
async def test_symbols(): assert (await request("GET","/symbols")).json()==["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT"]
@pytest.mark.anyio
async def test_exact_frozen_population():
    response=await request("GET","/trades"); assert response.status_code==200; assert len(response.json())==EXPECTED_COUNT==2199; assert (await request("GET","/health")).json()["frozen_entry_sha256"]==EXPECTED_ENTRY_SHA256
@pytest.mark.anyio
async def test_trade_lookup():
    trade=load_trades()[0]; assert (await request("GET",f"/trades/{trade['trade_id']}")).json()==trade; assert (await request("GET","/trades/not-a-trade")).status_code==404
@pytest.mark.anyio
async def test_ohlcv_query():
    response=await request("GET","/ohlcv/BTCUSDT",params={"start":"2024-01-01T00:00:00Z","end":"2024-01-01T02:00:00Z","interval":"5m"}); assert response.status_code==200; rows=response.json(); assert len(rows)==24; assert {"ts","open","high","low","close","volume","h1_sma24"}==set(rows[0])
@pytest.mark.parametrize("start,end",[("2026-01-01T00:00:00Z","2026-01-02T00:00:00Z"),("2025-12-31T00:00:00Z","2026-01-01T00:01:00Z")])
@pytest.mark.anyio
async def test_no_2026_access(start,end): assert (await request("GET","/ohlcv/BTCUSDT",params={"start":start,"end":end})).status_code==422
@pytest.mark.anyio
async def test_read_only_behavior():
    paths=[ROOT/"artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv",ROOT/"artifacts/c2_asymmetric_exit_experiment/p0_trade_records.csv",ROOT/"data/normalized/c2_frozen_inputs/BTCUSDT_5m.csv.gz"]; before={p:digest(p) for p in paths}; await request("GET","/health"); await request("GET","/trades",params={"symbol":"BTCUSDT"}); await request("GET","/ohlcv/BTCUSDT",params={"start":"2024-01-01T00:00:00Z","end":"2024-01-01T01:00:00Z"}); assert {p:digest(p) for p in paths}==before
@pytest.mark.anyio
async def test_mutating_http_methods_unavailable():
    for method in ("POST","PUT","PATCH","DELETE"): assert (await request(method,"/trades",json={})).status_code==405
