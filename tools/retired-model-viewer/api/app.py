"""FastAPI surface for the read-only Binance retired-model viewer."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .data import DataIntegrityError, SYMBOLS, get_trade, integrity_summary, query_ohlcv, query_trades

app = FastAPI(title="Binance Retired E1/P0 Viewer API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?", allow_methods=["GET"], allow_headers=["*"])

@app.get("/health")
async def health():
    try: return integrity_summary()
    except DataIntegrityError as exc: raise HTTPException(503, str(exc)) from exc

@app.get("/symbols")
async def symbols(): return list(SYMBOLS)

@app.get("/trades")
async def trades(symbol: str|None=None, year: int|None=None, outcome: str|None=None,
           positive_mfe_negative_exit: bool=False, min_mfe: float|None=Query(default=None, ge=0)):
    try: return query_trades(symbol, year, outcome, positive_mfe_negative_exit, min_mfe)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    except DataIntegrityError as exc: raise HTTPException(503, str(exc)) from exc

@app.get("/trades/{trade_id}")
async def trade(trade_id: str):
    try: found = get_trade(trade_id)
    except DataIntegrityError as exc: raise HTTPException(503, str(exc)) from exc
    if found is None: raise HTTPException(404, "trade not found")
    return found

@app.get("/ohlcv/{symbol}")
async def ohlcv(symbol: str, start: str, end: str, interval: str="5m"):
    try: rows = query_ohlcv(symbol, start, end, interval)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    except DataIntegrityError as exc: raise HTTPException(503, str(exc)) from exc
    if not rows: raise HTTPException(404, "no OHLCV bars in requested range")
    return rows
