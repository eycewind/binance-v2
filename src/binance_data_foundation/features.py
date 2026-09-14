from __future__ import annotations

import csv
import math
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path


FEATURE_COLUMNS = [
    "symbol",
    "open_time_utc",
    "ret_1_log",
    "ret_5_log",
    "vol_20_ret_1_log",
    "available_after_utc",
]


def compute_symbol_features(rows: list[dict]) -> list[dict]:
    rows = sorted(rows, key=lambda r: int(r["open_time_ms"]))
    symbols = {r["symbol"] for r in rows}
    if len(symbols) > 1:
        raise ValueError(f"compute_symbol_features requires one symbol, got {sorted(symbols)}")
    timestamps = [int(r["open_time_ms"]) for r in rows]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate open_time_ms in feature input")
    out: list[dict] = []
    closes: deque[float] = deque(maxlen=6)
    rets: deque[float] = deque(maxlen=20)
    previous_open_ms: int | None = None
    valid_run = 0

    for row in rows:
        open_ms = int(row["open_time_ms"])
        close = float(row["close"])
        contiguous = previous_open_ms is None or open_ms - previous_open_ms == 60_000
        positive = close > 0
        if not contiguous:
            closes.clear()
            rets.clear()
            valid_run = 0
        ret_1 = math.nan
        ret_5 = math.nan
        vol_20 = math.nan
        if positive and math.isfinite(close) and closes and closes[-1] > 0:
            ret_1 = math.log(close / closes[-1])
        if positive and math.isfinite(close) and len(closes) >= 5 and closes[-5] > 0:
            ret_5 = math.log(close / closes[-5])
        if math.isfinite(ret_1):
            rets.append(ret_1)
        else:
            rets.clear()
        valid_run = valid_run + 1 if positive and math.isfinite(close) else 0
        if len(rets) == 20 and valid_run >= 21:
            mean = sum(rets) / 20
            vol_20 = math.sqrt(sum((x - mean) ** 2 for x in rets) / 19)
        if positive and math.isfinite(close):
            closes.append(close)
        else:
            closes.clear()
        previous_open_ms = open_ms
        out.append(
            {
                "symbol": row["symbol"],
                "open_time_utc": row["open_time_utc"],
                "ret_1_log": _fmt(ret_1),
                "ret_5_log": _fmt(ret_5),
                "vol_20_ret_1_log": _fmt(vol_20),
                "available_after_utc": _iso_ms(open_ms + 60_000),
            }
        )
    return out


def compute_features_csv(normalized_dir: Path, output: Path, input_paths: list[Path] | None = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    paths = sorted(input_paths) if input_paths is not None else sorted(normalized_dir.glob("*_1m_normalized.csv"))
    for path in paths:
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        all_rows.extend(compute_symbol_features(rows))
    tmp = output.with_suffix(output.suffix + ".tmp")
    with tmp.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    os.replace(tmp, output)
    return output


def _fmt(value: float) -> str:
    return "" if not math.isfinite(value) else f"{value:.17g}"


def _iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
