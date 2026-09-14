from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = "https://data.binance.vision/data/spot/daily/klines"
SCHEMA_VERSION = "c1-kline-1m-v2"
MAX_COMPRESSED_BYTES = 250 * 1024 * 1024
MAX_LOCAL_DATA_BYTES = 1024 * 1024 * 1024
NORMALIZED_COLUMNS = [
    "symbol",
    "interval",
    "open_time_utc",
    "close_time_utc",
    "open_time_ms",
    "close_time_ms",
    "raw_open_time",
    "raw_close_time",
    "raw_time_unit",
    "open",
    "high",
    "low",
    "close",
    "base_volume",
    "quote_volume",
    "trade_count",
    "zero_trade_interval",
    "unchanged_close",
]


class ResourceLimitError(ValueError):
    """Raised when a configured byte budget would be exceeded."""


@dataclass(frozen=True)
class SampleSpec:
    symbols: tuple[str, ...]
    dates: tuple[str, ...]
    interval: str = "1m"

    @staticmethod
    def fixed() -> "SampleSpec":
        return SampleSpec(
            symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"),
            dates=("2024-12-30", "2024-12-31", "2025-01-01", "2025-01-02"),
        )


def ingest_sample(
    spec: SampleSpec,
    raw_dir: Path,
    normalized_dir: Path,
    artifact_dir: Path,
    *,
    offline: bool = False,
    max_compressed_bytes: int = MAX_COMPRESSED_BYTES,
    max_local_bytes: int = MAX_LOCAL_DATA_BYTES,
) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    quality = []
    by_symbol: dict[str, list[dict]] = {symbol: [] for symbol in spec.symbols}
    raw_bytes_seen = 0
    success = True
    stop_requests = False
    initial_local_bytes = _tree_size(raw_dir) + _tree_size(normalized_dir)
    if initial_local_bytes > max_local_bytes:
        success = False
        quality.append({"symbol": "ALL", "day": "ALL", "status": "fail", "issue": f"local data byte limit exceeded: {initial_local_bytes}>{max_local_bytes}"})
        stop_requests = True
    for symbol in spec.symbols:
        for day in spec.dates:
            if stop_requests:
                break
            remaining_compressed = max_compressed_bytes - raw_bytes_seen
            remaining_local_for_download = max_local_bytes - _tree_size(raw_dir) - _tree_size(normalized_dir)
            result = _obtain_archive(
                symbol,
                spec.interval,
                day,
                raw_dir,
                offline=offline,
                max_compressed_download_bytes=max(0, remaining_compressed),
                max_local_download_bytes=remaining_local_for_download,
            )
            manifest.append(result)
            if result["status"] != "verified":
                quality.append({"symbol": symbol, "day": day, "status": result["status"], "issue": result.get("error", "unavailable")})
                success = False
                if result["status"] == "resource_limit":
                    stop_requests = True
                    break
                continue
            raw_bytes_seen += int(result.get("bytes") or 0)
            if raw_bytes_seen > max_compressed_bytes:
                quality.append({"symbol": symbol, "day": day, "status": "fail", "issue": f"compressed byte limit exceeded: {raw_bytes_seen}>{max_compressed_bytes}"})
                success = False
                continue
            current_local_bytes = _tree_size(raw_dir) + _tree_size(normalized_dir)
            if current_local_bytes > max_local_bytes:
                quality.append({"symbol": symbol, "day": day, "status": "fail", "issue": f"local data byte limit exceeded: {current_local_bytes}>{max_local_bytes}"})
                success = False
                continue
            remaining_local_bytes = max_local_bytes - current_local_bytes
            try:
                rows = _read_zip(Path(result["zip_path"]), symbol, spec.interval, day, max_uncompressed_bytes=remaining_local_bytes)
                day_quality = validate_rows(rows, symbol, day)
            except Exception as exc:
                quality.append({"symbol": symbol, "day": day, "status": "fail", "issue": str(exc)})
                success = False
                continue
            quality.append(day_quality)
            if day_quality["status"] == "pass":
                by_symbol[symbol].extend(rows)
            else:
                success = False
        if stop_requests:
            break
    hashes = {}
    rows_total = sum(len(v) for v in by_symbol.values())
    expected_rows = len(spec.symbols) * len(spec.dates) * 1440
    if rows_total != expected_rows:
        success = False
        quality.append({"symbol": "ALL", "day": "ALL", "status": "fail", "issue": f"incomplete validated rows: {rows_total} expected={expected_rows}"})
    if success:
        staging = normalized_dir.parent / f".{normalized_dir.name}.tmp"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        try:
            for symbol, rows in by_symbol.items():
                path = staging / f"{symbol}_{spec.interval}_normalized.csv"
                remaining_local_bytes = max_local_bytes - _tree_size(raw_dir) - _tree_size(normalized_dir) - _tree_size(staging)
                if remaining_local_bytes <= 0:
                    raise ValueError(f"local data byte limit exceeded: remaining={remaining_local_bytes}")
                _write_normalized(path, rows, max_bytes=remaining_local_bytes)
                used_bytes = _tree_size(raw_dir) + _tree_size(normalized_dir) + _tree_size(staging)
                if used_bytes > max_local_bytes:
                    raise ValueError(f"local data byte limit exceeded: {used_bytes}>{max_local_bytes}")
                hashes[str(normalized_dir / path.name)] = sha256_file(path)
        except Exception as exc:
            shutil.rmtree(staging)
            success = False
            quality.append({"symbol": "ALL", "day": "ALL", "status": "fail", "issue": str(exc)})
            hashes = {}
        else:
            normalized_dir.mkdir(parents=True, exist_ok=True)
            for path in staging.glob("*_normalized.csv"):
                shutil.move(str(path), normalized_dir / path.name)
            shutil.rmtree(staging)
    else:
        hashes = _existing_hashes(normalized_dir)
    report = {
        "schema_version": SCHEMA_VERSION,
        "cache_verification_time_utc": datetime.now(timezone.utc).isoformat(),
        "original_retrieval_time_utc": "unknown",
        "manifest_path": str(artifact_dir / "raw_manifest.json"),
        "data_quality_path": str(artifact_dir / "data_quality.json"),
        "normalized_hashes": hashes,
        "rows_total": rows_total,
        "success": success,
    }
    _write_json(artifact_dir / "raw_manifest.json", manifest)
    _write_json(artifact_dir / "data_quality.json", quality)
    _write_json(artifact_dir / "normalized_hashes.json", hashes)
    if not success:
        _write_json(artifact_dir / "ingestion_failure.json", report)
    _write_quality_md(artifact_dir / "data_quality.md", quality, hashes)
    return report


def validate_rows(rows: list[dict], symbol: str, day: str) -> dict:
    issues: list[str] = []
    if len(rows) != 1440:
        issues.append(f"row_count={len(rows)} expected=1440")
    keys = [r["open_time_ms"] for r in rows]
    if len(keys) != len(set(keys)):
        issues.append("duplicate_open_time")
    if keys != sorted(keys):
        issues.append("unexpected_ordering")
    expected_start = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)
    expected_keys = list(range(expected_start, expected_start + 1440 * 60_000, 60_000))
    gaps = sorted(set(expected_keys) - set(keys))
    extras = sorted(set(keys) - set(expected_keys))
    if gaps:
        issues.append(f"missing_minutes={len(gaps)}")
    if extras:
        issues.append(f"unexpected_minutes={len(extras)}")
    invalid_ohlc = 0
    invalid_numeric = 0
    negative_volume = 0
    negative_trade_count = 0
    zero_trades = 0
    unchanged = 0
    previous_close = None
    units = set()
    expected_unit = "milliseconds" if day < "2025-01-01" else "microseconds"
    for row in rows:
        o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
        base_volume = float(row["base_volume"])
        quote_volume = float(row["quote_volume"])
        trade_count = int(row["trade_count"])
        if not all(math.isfinite(x) and x > 0 for x in (o, h, l, c)):
            invalid_numeric += 1
        if not math.isfinite(base_volume) or not math.isfinite(quote_volume) or base_volume < 0 or quote_volume < 0:
            negative_volume += 1
        if trade_count < 0:
            negative_trade_count += 1
        if h < max(o, c) or l > min(o, c) or l > h:
            invalid_ohlc += 1
        if trade_count == 0:
            zero_trades += 1
        if previous_close is not None and c == previous_close:
            unchanged += 1
        previous_close = c
        units.add(row["raw_time_unit"])
    wrong_units = sorted(unit for unit in units if unit != expected_unit)
    if wrong_units:
        issues.append(f"wrong_time_units={wrong_units} expected={expected_unit}")
    if invalid_ohlc:
        issues.append(f"invalid_ohlc={invalid_ohlc}")
    if invalid_numeric:
        issues.append(f"invalid_numeric={invalid_numeric}")
    if negative_volume:
        issues.append(f"invalid_volume={negative_volume}")
    if negative_trade_count:
        issues.append(f"negative_trade_count={negative_trade_count}")
    return {
        "symbol": symbol,
        "day": day,
        "status": "pass" if not issues else "fail",
        "rows": len(rows),
        "issues": issues,
        "zero_trade_intervals": zero_trades,
        "unchanged_close_intervals": unchanged,
        "raw_time_units": sorted(units),
        "gaps": len(gaps),
    }


def _obtain_archive(
    symbol: str,
    interval: str,
    day: str,
    raw_dir: Path,
    *,
    offline: bool,
    max_compressed_download_bytes: int,
    max_local_download_bytes: int,
) -> dict:
    name = f"{symbol}-{interval}-{day}.zip"
    zip_url = f"{BASE_URL}/{symbol}/{interval}/{name}"
    checksum_url = zip_url + ".CHECKSUM"
    zip_path = raw_dir / symbol / interval / name
    checksum_path = raw_dir / symbol / interval / f"{name}.CHECKSUM"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not zip_path.exists():
            if offline:
                raise FileNotFoundError(f"offline cache miss: {zip_path}")
            archive_budget = min(max_compressed_download_bytes, max_local_download_bytes)
            _download(zip_url, zip_path, max_bytes=archive_budget)
            max_local_download_bytes -= zip_path.stat().st_size
        if not checksum_path.exists():
            if offline:
                raise FileNotFoundError(f"offline checksum miss: {checksum_path}")
            checksum_budget = min(4096, max_local_download_bytes)
            _download(checksum_url, checksum_path, max_bytes=checksum_budget)
        published = checksum_path.read_text(encoding="utf-8").split()[0]
        actual = sha256_file(zip_path)
        if published.lower() != actual.lower():
            return _manifest_row(symbol, interval, day, zip_url, checksum_url, zip_path, checksum_path, "checksum_failed", actual, published)
        return _manifest_row(symbol, interval, day, zip_url, checksum_url, zip_path, checksum_path, "verified", actual, published)
    except ResourceLimitError as exc:
        return {
            "symbol": symbol,
            "interval": interval,
            "day": day,
            "url": zip_url,
            "checksum_url": checksum_url,
            "retrieval_time_utc": datetime.now(timezone.utc).isoformat(),
            "status": "resource_limit",
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "symbol": symbol,
            "interval": interval,
            "day": day,
            "url": zip_url,
            "checksum_url": checksum_url,
            "retrieval_time_utc": datetime.now(timezone.utc).isoformat(),
            "status": "missing",
            "error": str(exc),
        }


def _read_zip(path: Path, symbol: str, interval: str, day: str, *, max_uncompressed_bytes: int | None = None) -> list[dict]:
    rows = []
    uncompressed_seen = 0
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected exactly one csv in {path}")
        with zf.open(names[0]) as raw:
            def decoded_lines():
                nonlocal uncompressed_seen
                for line in raw:
                    uncompressed_seen += len(line)
                    if max_uncompressed_bytes is not None and uncompressed_seen > max_uncompressed_bytes:
                        raise ValueError(f"decompressed byte limit exceeded: {uncompressed_seen}>{max_uncompressed_bytes}")
                    yield line.decode("utf-8").strip()

            text = decoded_lines()
            reader = csv.reader(text)
            for row in reader:
                if not row or row[0] == "open_time":
                    continue
                parsed = _parse_kline(row, symbol, interval, day)
                rows.append(parsed)
    return rows


def _parse_kline(row: list[str], symbol: str, interval: str, day: str | None = None) -> dict:
    if len(row) < 11:
        raise ValueError(f"unexpected kline row length {len(row)}")
    raw_open = int(row[0])
    raw_close = int(row[6])
    unit = _time_unit(raw_open, raw_close)
    if day is not None:
        expected_unit = "milliseconds" if day < "2025-01-01" else "microseconds"
        if unit != expected_unit:
            raise ValueError(f"{day} expected {expected_unit}, got {unit}")
    factor = 1000 if unit == "microseconds" else 1
    open_ms, open_rem = divmod(raw_open, factor)
    close_ms, close_rem = divmod(raw_close, factor)
    if open_rem != 0:
        raise ValueError(f"open timestamp is not aligned to millisecond precision: {raw_open}")
    expected_raw_close = raw_open + 60 * factor * 1000 - 1
    if raw_close != expected_raw_close:
        raise ValueError(f"malformed close timestamp: {raw_close} expected {expected_raw_close}")
    trade_count = int(row[8])
    o, h, l, c = (float(row[k]) for k in (1, 2, 3, 4))
    base_volume = float(row[5])
    quote_volume = float(row[7])
    return {
        "symbol": symbol,
        "interval": interval,
        "open_time_utc": _iso_ms(open_ms),
        "close_time_utc": _iso_raw(raw_close, unit),
        "open_time_ms": open_ms,
        "close_time_ms": close_ms,
        "raw_open_time": raw_open,
        "raw_close_time": raw_close,
        "raw_time_unit": unit,
        "open": str(o),
        "high": str(h),
        "low": str(l),
        "close": str(c),
        "base_volume": str(base_volume),
        "quote_volume": str(quote_volume),
        "trade_count": trade_count,
        "zero_trade_interval": trade_count == 0,
        "unchanged_close": False,
    }


def _time_unit(*values: int) -> str:
    if all(1_000_000_000_000_000 <= v < 10_000_000_000_000_000 for v in values):
        return "microseconds"
    if all(1_000_000_000_000 <= v < 10_000_000_000_000 for v in values):
        return "milliseconds"
    raise ValueError(f"ambiguous timestamp unit: {values}")


def _write_normalized(path: Path, rows: list[dict], *, max_bytes: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["symbol"], r["open_time_ms"]))
    previous_by_symbol: dict[str, str] = {}
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=NORMALIZED_COLUMNS)
        writer.writeheader()
        if max_bytes is not None and f.tell() > max_bytes:
            raise ValueError(f"normalized write byte limit exceeded: {f.tell()}>{max_bytes}")
        for row in rows:
            row = dict(row)
            previous = previous_by_symbol.get(row["symbol"])
            row["unchanged_close"] = previous is not None and row["close"] == previous
            previous_by_symbol[row["symbol"]] = row["close"]
            writer.writerow({k: row[k] for k in NORMALIZED_COLUMNS})
            if max_bytes is not None and f.tell() > max_bytes:
                raise ValueError(f"normalized write byte limit exceeded: {f.tell()}>{max_bytes}")


def _download(url: str, path: Path, *, max_bytes: int) -> None:
    if max_bytes <= 0:
        raise ResourceLimitError(f"download byte limit exceeded before request: 0>{max_bytes}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with urllib.request.urlopen(url, timeout=60) as response:
        bytes_seen = 0
        try:
            with tmp.open("wb") as f:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    if bytes_seen + len(block) > max_bytes:
                        raise ResourceLimitError(f"download byte limit exceeded: {bytes_seen + len(block)}>{max_bytes}")
                    f.write(block)
                    bytes_seen += len(block)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, path)


def _manifest_row(symbol: str, interval: str, day: str, zip_url: str, checksum_url: str, zip_path: Path, checksum_path: Path, status: str, actual: str, published: str) -> dict:
    return {
        "symbol": symbol,
        "interval": interval,
        "day": day,
        "url": zip_url,
        "checksum_url": checksum_url,
        "cache_verification_time_utc": datetime.now(timezone.utc).isoformat(),
        "original_retrieval_time_utc": "unknown",
        "status": status,
        "zip_path": str(zip_path),
        "checksum_path": str(checksum_path),
        "sha256": actual,
        "published_sha256": published,
        "bytes": zip_path.stat().st_size if zip_path.exists() else None,
        "schema_parser_version": SCHEMA_VERSION,
    }


def _write_quality_md(path: Path, quality: list[dict], hashes: dict[str, str]) -> None:
    lines = ["# C1 Data Quality", "", "| Symbol | Day | Status | Rows | Gaps | Zero trades | Unchanged closes | Time units | Issues |", "|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for q in quality:
        lines.append(
            f"| {q.get('symbol')} | {q.get('day')} | {q.get('status')} | {q.get('rows', '')} | {q.get('gaps', '')} | {q.get('zero_trade_intervals', '')} | {q.get('unchanged_close_intervals', '')} | {','.join(q.get('raw_time_units', []))} | {'; '.join(q.get('issues', [])) or q.get('issue', '')} |"
        )
    lines += ["", "## Normalized Hashes", ""]
    for p, h in sorted(hashes.items()):
        lines.append(f"- `{p}`: `{h}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def _iso_raw(value: int, unit: str) -> str:
    divisor = 1_000_000 if unit == "microseconds" else 1000
    seconds, remainder = divmod(value, divisor)
    dt = datetime.fromtimestamp(seconds, timezone.utc)
    if unit == "microseconds":
        dt = dt.replace(microsecond=remainder)
    else:
        dt = dt.replace(microsecond=remainder * 1000)
    return dt.isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _tree_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _existing_hashes(normalized_dir: Path) -> dict[str, str]:
    if not normalized_dir.exists():
        return {}
    return {str(path): sha256_file(path) for path in sorted(normalized_dir.glob("*_1m_normalized.csv"))}
