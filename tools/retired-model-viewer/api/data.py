"""Read-only access to accepted, frozen E1/P0 research artifacts."""
from __future__ import annotations

import csv, gzip, hashlib, json
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
ENTRY_MODEL = "E1_H1_SMA24_CROSS_V1"
EXIT_MODEL = "P0_H1_SMA24_CROSSDOWN_V1"
EXPECTED_COUNT = 2_199
EXPECTED_ENTRY_SHA256 = "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
PRE_2026_END = datetime(2026, 1, 1, tzinfo=timezone.utc)
MAX_BARS = 50_000

class DataIntegrityError(RuntimeError): pass

def _repo_root() -> Path: return Path(__file__).resolve().parents[3]

def _accepted_path(*parts: str) -> Path:
    path = _repo_root().joinpath(*parts).resolve()
    if _repo_root() not in path.parents: raise DataIntegrityError("accepted data path escaped the repository")
    if any(part == "2026" or part.startswith("2026-") for part in path.parts):
        raise DataIntegrityError("2026 market data and metadata access is prohibited")
    return path

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()

def _parse_ts(value: str, name: str) -> datetime:
    try: parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc: raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

@lru_cache(maxsize=1)
def load_trades() -> tuple[dict[str, Any], ...]:
    base = _accepted_path("artifacts", "c2_asymmetric_exit_experiment")
    entries_path = base / "frozen_entries.csv"
    if _sha256(entries_path) != EXPECTED_ENTRY_SHA256: raise DataIntegrityError("frozen E1 population hash mismatch")
    with entries_path.open(encoding="utf-8", newline="") as handle: entries = list(csv.DictReader(handle))
    with (base / "common_horizons_p0.csv").open(encoding="utf-8", newline="") as handle:
        horizons = {row["trade_id"]: row for row in csv.DictReader(handle)}
    with (base / "p0_trade_records.csv").open(encoding="utf-8", newline="") as handle:
        costs = {row["trade_id"]: row for row in csv.DictReader(handle) if row["cost_scenario"] == "C_BASE"}
    t2_path = _accepted_path("artifacts", "c7_full_population_t2_exit_overlay", "population_manifest.json")
    t2_doc = json.loads(t2_path.read_text(encoding="utf-8"))
    t2 = {row["trade_id"]: row for row in t2_doc["rows"]}
    if not (len(entries) == len(horizons) == len(costs) == len(t2) == EXPECTED_COUNT):
        raise DataIntegrityError("accepted E1/P0 artifacts do not reconcile to 2,199 trades")
    output = []
    for entry in entries:
        trade_id = entry["trade_id"]; horizon = horizons[trade_id]; cost = costs[trade_id]; overlay = t2[trade_id]
        if entry["entry_fixture_id"] != ENTRY_MODEL or horizon["p0_version"] != EXIT_MODEL:
            raise DataIntegrityError("accepted trade has an unexpected model identifier")
        entry_dt = _parse_ts(entry["entry_execution_ts"], "entry_ts")
        exit_dt = _parse_ts(horizon["p0_execution_ts"], "exit_ts")
        if entry_dt >= PRE_2026_END or exit_dt >= PRE_2026_END:
            raise DataIntegrityError("accepted trade crosses the pre-2026 boundary")
        mfe_ts = entry_dt + timedelta(seconds=int(horizon["time_to_held_mfe_seconds"]))
        first_t2 = overlay.get("first_t2_decision_ts")
        output.append({
            "trade_id": trade_id, "symbol": entry["symbol"], "entry_ts": entry_dt.isoformat(),
            "entry_price": float(entry["entry_price"]), "exit_ts": exit_dt.isoformat(),
            "exit_price": float(horizon["p0_raw_exit_price"]), "gross_return": float(cost["gross_return"]),
            "net_return_c_base": float(cost["net_return"]), "mfe_return": float(horizon["held_mfe"]),
            "mfe_ts": mfe_ts.isoformat(), "mae_return": float(horizon["held_mae"]), "mae_ts": None,
            "surrender_gap": float(horizon["held_peak_gain_surrendered"]),
            "holding_minutes": int(horizon["common_horizon_duration_seconds"]) // 60,
            "t2_reached": first_t2 is not None, "t2_ts": first_t2, "year": entry_dt.year,
            "exit_reason": horizon.get("p0_exit_reason") or None, "entry_model": ENTRY_MODEL, "exit_model": EXIT_MODEL,
        })
    return tuple(output)

def query_trades(symbol=None, year=None, outcome=None, positive_mfe_negative_exit=False, min_mfe=None):
    rows = load_trades()
    if symbol:
        symbol = symbol.strip().upper()
        if symbol not in SYMBOLS: raise ValueError("unsupported symbol")
        rows = tuple(r for r in rows if r["symbol"] == symbol)
    if year is not None:
        if year not in (2024, 2025): raise ValueError("year must be 2024 or 2025")
        rows = tuple(r for r in rows if r["year"] == year)
    if outcome:
        if outcome not in ("profitable", "losing"): raise ValueError("outcome must be profitable or losing")
        rows = tuple(r for r in rows if (r["net_return_c_base"] >= 0) == (outcome == "profitable"))
    if positive_mfe_negative_exit: rows = tuple(r for r in rows if r["mfe_return"] > 0 and r["gross_return"] < 0)
    if min_mfe is not None: rows = tuple(r for r in rows if r["mfe_return"] >= min_mfe)
    return [dict(r) for r in rows]

def get_trade(trade_id): return next((dict(r) for r in load_trades() if r["trade_id"] == trade_id), None)

@lru_cache(maxsize=10)
def _bars(symbol, interval):
    if symbol not in SYMBOLS or interval not in ("1m", "5m"): raise ValueError("unsupported symbol or interval")
    folder = "c2_history" if interval == "1m" else "c2_frozen_inputs"
    path = _accepted_path("data", "normalized", folder, f"{symbol}_{interval}.csv.gz")
    rows = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for source in csv.DictReader(handle):
            timestamp = _parse_ts(source["open_time_utc"], "bar timestamp")
            if timestamp >= PRE_2026_END: raise DataIntegrityError("OHLCV source contains a 2026 row")
            rows.append({"ts": timestamp.isoformat(), "ts_ms": int(source["open_time_ms"]),
                "open": float(source["open"]), "high": float(source["high"]), "low": float(source["low"]),
                "close": float(source["close"]), "volume": float(source["base_volume"])})
    return tuple(rows)

@lru_cache(maxsize=5)
def _hourly_sma(symbol):
    path = _accepted_path("data", "normalized", "c2_frozen_inputs", f"{symbol}_1h.csv.gz")
    available, values, window = [], [], []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            at = int(row["available_at_ms"])
            # The last 2025 candle becomes available at the 2026 boundary and
            # is deliberately excluded from this pre-2026 viewer.
            if at >= int(PRE_2026_END.timestamp() * 1000): break
            window.append(float(row["close"])); window = window[-24:]
            available.append(at); values.append(sum(window) / 24 if len(window) == 24 else None)
    return tuple(available), tuple(values)

def query_ohlcv(symbol, start, end, interval="5m"):
    symbol = symbol.strip().upper()
    if symbol not in SYMBOLS: raise ValueError("unsupported symbol")
    if interval not in ("1m", "5m"): raise ValueError("interval must be 1m or 5m")
    start_dt, end_dt = _parse_ts(start, "start"), _parse_ts(end, "end")
    if not start_dt < end_dt: raise ValueError("start must be before end")
    if start_dt >= PRE_2026_END or end_dt > PRE_2026_END: raise ValueError("OHLCV requests must remain strictly pre-2026")
    start_ms, end_ms = int(start_dt.timestamp()*1000), int(end_dt.timestamp()*1000)
    selected = [dict(r) for r in _bars(symbol, interval) if start_ms <= r["ts_ms"] < end_ms]
    if len(selected) > MAX_BARS: raise ValueError(f"query exceeds the {MAX_BARS:,}-bar display limit")
    times, values = _hourly_sma(symbol)
    for row in selected:
        index = bisect_right(times, row["ts_ms"]) - 1
        row["h1_sma24"] = values[index] if index >= 0 else None; row.pop("ts_ms")
    return selected

def integrity_summary():
    return {"status":"ok", "mode":"read-only", "retired":True, "trade_count":len(load_trades()),
        "frozen_entry_sha256":EXPECTED_ENTRY_SHA256, "entry_model":ENTRY_MODEL, "exit_model":EXIT_MODEL,
        "market_data_end_exclusive":PRE_2026_END.isoformat()}
