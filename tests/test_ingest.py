import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

import binance_data_foundation.ingest as ingest_module
from binance_data_foundation.ingest import SampleSpec, _parse_kline, _time_unit, ingest_sample, validate_rows


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self, size: int) -> bytes:
        if self.offset >= len(self.payload):
            return b""
        end = min(self.offset + size, len(self.payload))
        block = self.payload[self.offset:end]
        self.offset = end
        return block


def _cached_day_bytes(symbol: str, day: str) -> bytes:
    start = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)
    rows = []
    for i in range(1440):
        open_time = start + i * 60_000
        close_time = open_time + 59_999
        rows.append(f"{open_time},10,11,9,10,1,{close_time},10,1,0,0,0\n")
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as zf:
        zf.writestr(f"{symbol}-1m-{day}.csv", "".join(rows))
    return payload.getvalue()


def _write_cached_day(raw: Path, symbol: str, day: str) -> Path:
    folder = raw / symbol / "1m"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{symbol}-1m-{day}.zip"
    zip_path = folder / name
    start = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)
    with zipfile.ZipFile(zip_path, "w") as zf:
        rows = []
        for i in range(1440):
            open_time = start + i * 60_000
            close_time = open_time + 59_999
            rows.append(f"{open_time},10,11,9,10,1,{close_time},10,1,0,0,0\n")
        zf.writestr(f"{symbol}-1m-{day}.csv", "".join(rows))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (folder / f"{name}.CHECKSUM").write_text(f"{digest}  {name}\n", encoding="utf-8")
    return zip_path


def test_timestamp_unit_boundaries() -> None:
    assert _time_unit(1_735_689_600_000, 1_735_689_659_999) == "milliseconds"
    assert _time_unit(1_735_689_600_000_000, 1_735_689_659_999_000) == "microseconds"


def test_parse_preserves_raw_microseconds_and_normalizes_ms() -> None:
    row = [
        "1735689600000000",
        "1.0",
        "2.0",
        "0.5",
        "1.5",
        "10",
        "1735689659999999",
        "15",
        "7",
        "0",
        "0",
        "0",
    ]
    parsed = _parse_kline(row, "BTCUSDT", "1m")
    assert parsed["raw_time_unit"] == "microseconds"
    assert parsed["raw_open_time"] == 1_735_689_600_000_000
    assert parsed["open_time_ms"] == 1_735_689_600_000
    assert parsed["close_time_utc"].endswith("00:00")
    assert ".999999" in parsed["close_time_utc"]
    assert parsed["open_time_utc"] == datetime.fromtimestamp(1_735_689_600, timezone.utc).isoformat()


def test_parse_rejects_wrong_units_and_malformed_close_time() -> None:
    ms_row = [
        "1735603200000",
        "1",
        "2",
        "1",
        "1.5",
        "10",
        "1735603259999",
        "15",
        "7",
        "0",
        "0",
        "0",
    ]
    assert _parse_kline(ms_row, "BTCUSDT", "1m", "2024-12-31")["raw_time_unit"] == "milliseconds"
    with pytest.raises(ValueError, match="expected microseconds"):
        _parse_kline(ms_row, "BTCUSDT", "1m", "2025-01-01")
    bad_close = list(ms_row)
    bad_close[6] = "1735603260000"
    with pytest.raises(ValueError, match="malformed close"):
        _parse_kline(bad_close, "BTCUSDT", "1m", "2024-12-31")


def test_validate_fixed_complete_grid_and_quality_flags() -> None:
    rows = []
    start = 1_735_689_600_000
    for i in range(1440):
        rows.append(
            {
                "symbol": "BNBUSDT",
                "open_time_ms": start + i * 60_000,
                "open": "10",
                "high": "11",
                "low": "9",
                "close": "10",
                "base_volume": "0",
                "quote_volume": "0",
                "trade_count": 0,
                "raw_time_unit": "microseconds",
            }
        )
    q = validate_rows(rows, "BNBUSDT", "2025-01-01")
    assert q["status"] == "pass"
    assert q["rows"] == 1440
    assert q["zero_trade_intervals"] == 1440
    assert q["unchanged_close_intervals"] == 1439


def test_validate_rejects_nan_negative_trades_duplicates_gaps_and_bad_ohlc() -> None:
    rows = []
    start = 1_735_689_600_000
    for i in range(1440):
        rows.append(
            {
                "symbol": "BNBUSDT",
                "open_time_ms": start + i * 60_000,
                "open": "10",
                "high": "11",
                "low": "9",
                "close": "10",
                "base_volume": "0",
                "quote_volume": "0",
                "trade_count": 1,
                "raw_time_unit": "microseconds",
            }
        )
    rows[1]["close"] = "nan"
    rows[2]["trade_count"] = -1
    rows[3]["high"] = "8"
    rows[4]["base_volume"] = "-1"
    rows[5]["open_time_ms"] = rows[4]["open_time_ms"]
    q = validate_rows(rows, "BNBUSDT", "2025-01-01")
    assert q["status"] == "fail"
    assert any("duplicate_open_time" in issue for issue in q["issues"])
    assert any("invalid_numeric" in issue for issue in q["issues"])
    assert any("negative_trade_count" in issue for issue in q["issues"])
    assert any("invalid_ohlc" in issue for issue in q["issues"])
    assert any("invalid_volume" in issue for issue in q["issues"])


def test_ingest_offline_cache_failure_preserves_existing_outputs(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    artifacts = tmp_path / "artifacts"
    normalized.mkdir()
    old = normalized / "BTCUSDT_1m_normalized.csv"
    old.write_text("sentinel\n", encoding="utf-8")
    report = ingest_sample(SampleSpec(("BTCUSDT",), ("2024-12-30",)), raw, normalized, artifacts, offline=True)
    assert report["success"] is False
    assert old.read_text(encoding="utf-8") == "sentinel\n"
    assert (artifacts / "ingestion_failure.json").exists()


def test_ingest_reports_checksum_mismatch_without_publishing(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    artifacts = tmp_path / "artifacts"
    path = raw / "BTCUSDT" / "1m"
    path.mkdir(parents=True)
    name = "BTCUSDT-1m-2024-12-30.zip"
    with zipfile.ZipFile(path / name, "w") as zf:
        zf.writestr("BTCUSDT-1m-2024-12-30.csv", "")
    (path / f"{name}.CHECKSUM").write_text("0" * 64 + f"  {name}\n", encoding="utf-8")
    report = ingest_sample(SampleSpec(("BTCUSDT",), ("2024-12-30",)), raw, normalized, artifacts, offline=True)
    assert report["success"] is False
    quality = json.loads((artifacts / "data_quality.json").read_text(encoding="utf-8"))
    assert any(q["status"] == "checksum_failed" for q in quality)
    assert not list(normalized.glob("*_normalized.csv"))


def test_ingest_resource_limit_failure_preserves_outputs(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    artifacts = tmp_path / "artifacts"
    path = raw / "BTCUSDT" / "1m"
    path.mkdir(parents=True)
    name = "BTCUSDT-1m-2024-12-30.zip"
    zip_path = path / name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("BTCUSDT-1m-2024-12-30.csv", "")
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (path / f"{name}.CHECKSUM").write_text(f"{digest}  {name}\n", encoding="utf-8")
    normalized.mkdir()
    old = normalized / "BTCUSDT_1m_normalized.csv"
    old.write_text("sentinel\n", encoding="utf-8")
    report = ingest_sample(
        SampleSpec(("BTCUSDT",), ("2024-12-30",)),
        raw,
        normalized,
        artifacts,
        offline=True,
        max_compressed_bytes=1,
    )
    assert report["success"] is False
    assert old.read_text(encoding="utf-8") == "sentinel\n"


def test_ingest_counts_cached_compressed_file_once(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    artifacts = tmp_path / "artifacts"
    zip_path = _write_cached_day(raw, "BTCUSDT", "2024-12-30")
    report = ingest_sample(
        SampleSpec(("BTCUSDT",), ("2024-12-30",)),
        raw,
        normalized,
        artifacts,
        offline=True,
        max_compressed_bytes=zip_path.stat().st_size,
    )
    assert report["success"] is True
    assert report["rows_total"] == 1440
    assert (normalized / "BTCUSDT_1m_normalized.csv").exists()


def test_ingest_local_staging_limit_preserves_existing_output(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    artifacts = tmp_path / "artifacts"
    _write_cached_day(raw, "BTCUSDT", "2024-12-30")
    normalized.mkdir()
    old = normalized / "BTCUSDT_1m_normalized.csv"
    old.write_text("sentinel\n", encoding="utf-8")
    report = ingest_sample(
        SampleSpec(("BTCUSDT",), ("2024-12-30",)),
        raw,
        normalized,
        artifacts,
        offline=True,
        max_local_bytes=200_000,
    )
    assert report["success"] is False
    assert old.read_text(encoding="utf-8") == "sentinel\n"
    quality = json.loads((artifacts / "data_quality.json").read_text(encoding="utf-8"))
    assert any("byte limit exceeded" in q.get("issue", "") for q in quality)


def test_ingest_decompression_uses_remaining_local_budget_and_preserves_output(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    artifacts = tmp_path / "artifacts"
    _write_cached_day(raw, "BTCUSDT", "2024-12-30")
    normalized.mkdir()
    old = normalized / "BTCUSDT_1m_normalized.csv"
    old.write_text("sentinel\n", encoding="utf-8")
    existing_bytes = sum(p.stat().st_size for root in (raw, normalized) for p in root.rglob("*") if p.is_file())
    report = ingest_sample(
        SampleSpec(("BTCUSDT",), ("2024-12-30",)),
        raw,
        normalized,
        artifacts,
        offline=True,
        max_local_bytes=existing_bytes + 1,
    )
    assert report["success"] is False
    assert old.read_text(encoding="utf-8") == "sentinel\n"
    quality = json.loads((artifacts / "data_quality.json").read_text(encoding="utf-8"))
    assert any("decompressed byte limit exceeded" in q.get("issue", "") for q in quality)


def test_downloads_cannot_exceed_remaining_local_budget_and_stop_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    artifacts = tmp_path / "artifacts"
    normalized.mkdir()
    old = normalized / "BTCUSDT_1m_normalized.csv"
    old.write_text("sentinel\n", encoding="utf-8")
    payload = _cached_day_bytes("BTCUSDT", "2024-12-30")
    calls: list[str] = []

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        calls.append(url)
        return _FakeResponse(payload)

    monkeypatch.setattr(ingest_module.urllib.request, "urlopen", fake_urlopen)
    report = ingest_sample(
        SampleSpec(("BTCUSDT",), ("2024-12-30", "2024-12-31")),
        raw,
        normalized,
        artifacts,
        offline=False,
        max_local_bytes=len(payload) - 1,
    )
    assert report["success"] is False
    assert len(calls) == 1
    assert calls[0].endswith("BTCUSDT-1m-2024-12-30.zip")
    assert old.read_text(encoding="utf-8") == "sentinel\n"
    assert not list(raw.rglob("*.tmp"))
    assert not list(raw.rglob("*.zip"))
    quality = json.loads((artifacts / "data_quality.json").read_text(encoding="utf-8"))
    assert quality[0]["status"] == "resource_limit"


def test_checksum_download_respects_remaining_local_budget_and_stops_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    artifacts = tmp_path / "artifacts"
    normalized.mkdir()
    old = normalized / "BTCUSDT_1m_normalized.csv"
    old.write_text("sentinel\n", encoding="utf-8")
    zip_payload = _cached_day_bytes("BTCUSDT", "2024-12-30")
    checksum_payload = f"{hashlib.sha256(zip_payload).hexdigest()}  BTCUSDT-1m-2024-12-30.zip\n".encode()
    calls: list[str] = []

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        calls.append(url)
        return _FakeResponse(checksum_payload if url.endswith(".CHECKSUM") else zip_payload)

    monkeypatch.setattr(ingest_module.urllib.request, "urlopen", fake_urlopen)
    report = ingest_sample(
        SampleSpec(("BTCUSDT",), ("2024-12-30", "2024-12-31")),
        raw,
        normalized,
        artifacts,
        offline=False,
        max_local_bytes=len(zip_payload) + len(checksum_payload) - 1,
    )
    assert report["success"] is False
    assert len(calls) == 2
    assert calls[0].endswith("BTCUSDT-1m-2024-12-30.zip")
    assert calls[1].endswith("BTCUSDT-1m-2024-12-30.zip.CHECKSUM")
    assert old.read_text(encoding="utf-8") == "sentinel\n"
    assert not list(raw.rglob("*.tmp"))
    assert not list(raw.rglob("*.CHECKSUM"))
    quality = json.loads((artifacts / "data_quality.json").read_text(encoding="utf-8"))
    assert quality[0]["status"] == "resource_limit"
