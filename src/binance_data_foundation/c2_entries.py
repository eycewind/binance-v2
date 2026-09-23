from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from .c2_common import (
    ENTRY_COLUMNS, ENTRY_FIXTURE_ID, ENTRY_NOTIONAL_USDT,
    canonical_number, hash_rows, iso, valid_minute,
)


@dataclass(frozen=True)
class FrozenEntryResult:
    entries: tuple[dict, ...]
    signals: tuple[dict, ...]
    suppressed_refractory: int
    unexecutable: int
    frozen_hash: str


def freeze_entries(hour_bars: Iterable[dict], minute_rows: Iterable[dict]) -> FrozenEntryResult:
    hours = sorted((dict(row) for row in hour_bars), key=lambda r: (r["symbol"], int(r["open_time_ms"])))
    minutes = [dict(row) for row in minute_rows]
    if len({row["symbol"] for row in hours}) > 1 or len({row["symbol"] for row in minutes}) > 1:
        raise ValueError("freeze_entries requires one symbol per call")
    symbol = hours[0]["symbol"] if hours else (minutes[0]["symbol"] if minutes else "")
    if any(row["symbol"] != symbol for row in hours + minutes):
        raise ValueError("hour and minute symbols must match")
    minute_by_ts: dict[int, dict] = {}
    duplicate_minutes: set[int] = set()
    for row in minutes:
        ts = int(row["open_time_ms"])
        if ts in minute_by_ts:
            duplicate_minutes.add(ts)
        minute_by_ts[ts] = row
    sma = hourly_sma24(hours)
    signals: list[dict] = []
    last_execution: int | None = None
    executable_candidates: list[dict] = []
    suppressed = 0
    unexecutable = 0
    for i in range(1, len(hours)):
        if sma[i] is None or sma[i - 1] is None:
            continue
        if not (float(hours[i]["close"]) > sma[i] and float(hours[i - 1]["close"]) <= sma[i - 1]):
            continue
        decision_ms = int(hours[i]["available_at_ms"])
        minute = minute_by_ts.get(decision_ms)
        valid_execution = minute is not None and decision_ms not in duplicate_minutes and valid_minute(minute)
        if not valid_execution:
            status = "unexecutable"
            unexecutable += 1
        elif last_execution is not None and decision_ms - last_execution < 24 * 3_600_000:
            status = "suppressed_refractory"
            suppressed += 1
        else:
            last_execution = decision_ms
            executable_candidates.append({
                "symbol": symbol, "entry_fixture_id": ENTRY_FIXTURE_ID,
                "entry_signal_ts": iso(decision_ms), "entry_decision_ts": iso(decision_ms),
                "entry_execution_ts": iso(decision_ms), "entry_execution_ms": decision_ms,
                "entry_price": canonical_number(float(minute["open"])),
                "entry_notional_usdt": canonical_number(ENTRY_NOTIONAL_USDT), "entry_timeframe": "1h",
            })
            status = "executable"
        signals.append({"symbol": symbol, "decision_ms": decision_ms, "decision_ts": iso(decision_ms), "status": status})
    executable_candidates.sort(key=lambda r: (int(r["entry_execution_ms"]), r["symbol"]))
    entries = []
    for row in executable_candidates:
        stable = hashlib.sha256(f"{ENTRY_FIXTURE_ID}|{row['symbol']}|{row['entry_execution_ms']}".encode()).hexdigest()[:16]
        entries.append({"trade_id": f"E1-{stable}", **row})
    entries.sort(key=lambda r: (int(r["entry_execution_ms"]), r["symbol"], r["trade_id"]))
    return FrozenEntryResult(tuple(entries), tuple(signals), suppressed, unexecutable, hash_rows(entries, ENTRY_COLUMNS))


def hourly_sma24(hour_bars: Iterable[dict]) -> tuple[float | None, ...]:
    hours = list(hour_bars)
    values: list[float | None] = [None] * len(hours)
    for i in range(23, len(hours)):
        window = hours[i - 23:i + 1]
        expected = [int(window[0]["open_time_ms"]) + j * 3_600_000 for j in range(24)]
        actual = [int(row["open_time_ms"]) for row in window]
        if actual == expected:
            values[i] = sum(float(row["close"]) for row in window) / 24
    return tuple(values)
