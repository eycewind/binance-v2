from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from .c2_common import iso, valid_minute


@dataclass(frozen=True)
class AggregationResult:
    bars: tuple[dict, ...]
    exclusions: tuple[dict, ...]


def aggregate_minutes(rows: Iterable[dict], timeframe_minutes: int) -> AggregationResult:
    if timeframe_minutes not in (5, 60):
        raise ValueError("timeframe_minutes must be 5 or 60")
    materialized = sorted((dict(row) for row in rows), key=lambda r: int(r["open_time_ms"]))
    symbols = {row["symbol"] for row in materialized}
    if len(symbols) > 1:
        raise ValueError("aggregate_minutes requires one symbol")
    if not materialized:
        return AggregationResult((), ())
    duration_ms = timeframe_minutes * 60_000
    groups: dict[int, list[dict]] = {}
    for row in materialized:
        ts = int(row["open_time_ms"])
        bucket = ts - ts % duration_ms
        groups.setdefault(bucket, []).append(row)
    bars: list[dict] = []
    exclusions: list[dict] = []
    for bucket in range(min(groups), max(groups) + duration_ms, duration_ms):
        kind, record = _aggregate_group(groups.get(bucket, []), bucket, timeframe_minutes)
        (bars if kind == "bar" else exclusions).append(record)
    return AggregationResult(tuple(bars), tuple(exclusions))


def stream_aggregates(rows: Iterable[dict], timeframe_minutes: int) -> Iterator[tuple[str, dict]]:
    if timeframe_minutes not in (5, 60):
        raise ValueError("timeframe_minutes must be 5 or 60")
    duration_ms = timeframe_minutes * 60_000
    bucket: int | None = None
    pending: list[dict] = []
    symbol: str | None = None
    last_ts: int | None = None
    for original in rows:
        row = dict(original)
        if symbol is None:
            symbol = row["symbol"]
        elif row["symbol"] != symbol:
            raise ValueError("stream_aggregates requires one symbol")
        ts = int(row["open_time_ms"])
        if last_ts is not None and ts < last_ts:
            raise ValueError("source minutes must be ordered")
        current = ts - ts % duration_ms
        if bucket is None:
            bucket = current
        while current > bucket:
            yield _aggregate_group(pending, bucket, timeframe_minutes)
            pending = []
            bucket += duration_ms
        pending.append(row)
        last_ts = ts
    if bucket is not None:
        yield _aggregate_group(pending, bucket, timeframe_minutes)


def _aggregate_invalid_reason(source: list[dict], bucket: int, count: int) -> str | None:
    if len(source) != count:
        return "missing_or_partial_window"
    timestamps = [int(row["open_time_ms"]) for row in source]
    if len(timestamps) != len(set(timestamps)):
        return "duplicate_minute"
    if timestamps != [bucket + i * 60_000 for i in range(count)]:
        return "off_grid_or_missing_minute"
    if any(not valid_minute(row) for row in source):
        return "invalid_source_bar"
    return None


def _aggregate_group(source: list[dict], bucket: int, timeframe_minutes: int) -> tuple[str, dict]:
    reason = _aggregate_invalid_reason(source, bucket, timeframe_minutes)
    if reason:
        return "exclusion", {"open_time_ms": bucket, "reason": reason, "source_rows": len(source)}
    values = [{key: float(row[key]) for key in ("open", "high", "low", "close", "base_volume", "quote_volume")} for row in source]
    duration_ms = timeframe_minutes * 60_000
    return "bar", {
        "symbol": source[0]["symbol"], "timeframe": f"{timeframe_minutes}m" if timeframe_minutes != 60 else "1h",
        "open_time_ms": bucket, "open_time_utc": iso(bucket),
        "available_at_ms": bucket + duration_ms, "available_at_utc": iso(bucket + duration_ms),
        "open": values[0]["open"], "high": max(v["high"] for v in values),
        "low": min(v["low"] for v in values), "close": values[-1]["close"],
        "base_volume": sum(v["base_volume"] for v in values),
        "quote_volume": sum(v["quote_volume"] for v in values),
        "trade_count": sum(int(row["trade_count"]) for row in source), "source_rows": len(source),
    }
