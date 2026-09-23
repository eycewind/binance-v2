import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from binance_data_foundation.c2_inputs import (
    AGGREGATE_COLUMNS,
    ENTRY_FIXTURE_ID,
    aggregate_minutes,
    freeze_entries,
    hash_rows,
    hourly_sma24,
    research_partitions,
    stream_aggregates,
    theoretical_row_counts,
    _obtain_month,
    _read_month,
)
from binance_data_foundation.c2_cli import _write_run_manifest


START = 1_704_067_200_000


def minute(i: int, *, symbol: str = "AAAUSDT", price: float | None = None, ts: int | None = None) -> dict:
    value = float(i + 1 if price is None else price)
    return {
        "symbol": symbol, "open_time_ms": START + i * 60_000 if ts is None else ts,
        "open": value, "high": value + 2, "low": max(0.1, value - 1), "close": value + 1,
        "base_volume": 10 + i, "quote_volume": 100 + i, "trade_count": i + 1,
    }


def hour(i: int, close: float, *, symbol: str = "AAAUSDT") -> dict:
    open_ms = START + i * 3_600_000
    return {
        "symbol": symbol, "open_time_ms": open_ms, "available_at_ms": open_ms + 3_600_000,
        "open": close, "high": close, "low": close, "close": close,
        "base_volume": 1, "quote_volume": 1, "trade_count": 1,
    }


def execution_minutes(hours: int, *, symbol: str = "AAAUSDT") -> list[dict]:
    return [minute(i * 60, symbol=symbol, price=100 + i) for i in range(hours + 1)]


def test_exact_five_minute_aggregation_and_availability() -> None:
    rows = [minute(i) for i in range(5)]
    result = aggregate_minutes(rows, 5)
    assert result.exclusions == ()
    assert len(result.bars) == 1
    bar = result.bars[0]
    assert bar["open_time_ms"] == START
    assert bar["available_at_ms"] == START + 5 * 60_000
    assert bar["open"] == 1
    assert bar["high"] == 7
    assert bar["low"] == pytest.approx(0.1)
    assert bar["close"] == 6
    assert bar["base_volume"] == sum(10 + i for i in range(5))
    assert bar["quote_volume"] == sum(100 + i for i in range(5))
    assert bar["trade_count"] == 15


def test_exact_hour_aggregation_and_utc_alignment() -> None:
    result = aggregate_minutes([minute(i) for i in range(60)], 60)
    assert len(result.bars) == 1
    bar = result.bars[0]
    assert bar["open_time_ms"] % 3_600_000 == 0
    assert bar["available_at_ms"] == START + 3_600_000
    assert bar["source_rows"] == 60
    assert bar["close"] == 61


@pytest.mark.parametrize(
    "rows,reason",
    [
        ([minute(i) for i in range(4)], "missing_or_partial_window"),
        ([minute(i) for i in (0, 1, 3, 4)], "missing_or_partial_window"),
        ([minute(0), minute(1), minute(1), minute(3), minute(4)], "duplicate_minute"),
        ([minute(0), minute(1), minute(2, ts=START + 150_000), minute(3), minute(4)], "off_grid_or_missing_minute"),
    ],
)
def test_partial_missing_duplicate_and_off_grid_invalidate(rows: list[dict], reason: str) -> None:
    result = aggregate_minutes(rows, 5)
    assert not result.bars
    assert result.exclusions[0]["reason"] == reason


def test_invalid_ohlc_invalidates_aggregate() -> None:
    rows = [minute(i) for i in range(5)]
    rows[2]["high"] = 0
    result = aggregate_minutes(rows, 5)
    assert not result.bars
    assert result.exclusions[0]["reason"] == "invalid_source_bar"


def test_cross_symbol_isolation() -> None:
    rows = [minute(i) for i in range(5)] + [minute(i, symbol="BBBUSDT") for i in range(5)]
    with pytest.raises(ValueError, match="one symbol"):
        aggregate_minutes(rows, 5)
    with pytest.raises(ValueError, match="one symbol"):
        list(stream_aggregates(rows, 5))


def test_future_mutation_does_not_change_earlier_aggregate() -> None:
    base = [minute(i) for i in range(10)]
    before = aggregate_minutes(base, 5).bars[0]
    changed = [dict(row) for row in base]
    changed[8]["close"] = 9999
    assert aggregate_minutes(changed, 5).bars[0] == before


def test_streaming_and_materialized_aggregation_match() -> None:
    rows = [minute(i) for i in range(12)]
    materialized = aggregate_minutes(rows, 5)
    streamed = list(stream_aggregates(rows, 5))
    assert tuple(record for kind, record in streamed if kind == "bar") == materialized.bars
    assert tuple(record for kind, record in streamed if kind == "exclusion") == materialized.exclusions


def crossing_hours(*, second_cross_offset: int | None = None) -> list[dict]:
    closes = [100.0] * 24 + [101.0]
    if second_cross_offset is not None:
        closes += [100.0] * (second_cross_offset - 1) + [101.0]
    return [hour(i, close) for i, close in enumerate(closes)]


def test_exact_sma24_crossing_and_warmup() -> None:
    hours = crossing_hours()
    sma = hourly_sma24(hours)
    assert sma[22] is None
    assert sma[23] == pytest.approx(100.0)
    assert sma[24] == pytest.approx((23 * 100 + 101) / 24)
    result = freeze_entries(hours, execution_minutes(len(hours)))
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry["entry_fixture_id"] == ENTRY_FIXTURE_ID
    assert entry["entry_execution_ms"] == START + 25 * 3_600_000
    assert float(entry["entry_price"]) == 125
    assert not freeze_entries(hours[:24], execution_minutes(24)).entries


def test_equality_does_not_cross_and_gap_breaks_sma() -> None:
    equal = [hour(i, 100) for i in range(25)]
    assert not freeze_entries(equal, execution_minutes(25)).entries
    gapped = crossing_hours()
    gapped[10] = hour(10, 100)
    gapped[10]["open_time_ms"] += 3_600_000
    gapped[10]["available_at_ms"] += 3_600_000
    assert not freeze_entries(gapped, execution_minutes(25)).entries


def test_exact_execution_boundary_and_missing_is_unexecutable() -> None:
    hours = crossing_hours()
    minutes = execution_minutes(25)
    exact = freeze_entries(hours, minutes)
    assert len(exact.entries) == 1
    missing = freeze_entries(hours, minutes[:-1])
    assert not missing.entries
    assert missing.unexecutable == 1
    assert missing.signals[0]["status"] == "unexecutable"


def test_refractory_suppresses_inside_24h_and_allows_exact_boundary() -> None:
    inside = freeze_entries(crossing_hours(second_cross_offset=23), execution_minutes(60))
    assert len(inside.entries) == 1
    assert inside.suppressed_refractory == 1
    exact = freeze_entries(crossing_hours(second_cross_offset=24), execution_minutes(60))
    assert len(exact.entries) == 2
    assert exact.suppressed_refractory == 0
    assert exact.entries[1]["entry_execution_ms"] - exact.entries[0]["entry_execution_ms"] == 24 * 3_600_000


def test_policy_independent_deterministic_ids_order_and_hash() -> None:
    hours = crossing_hours(second_cross_offset=24)
    minutes = execution_minutes(60)
    first = freeze_entries(hours, minutes)
    second = freeze_entries(list(reversed(hours)), list(reversed(minutes)))
    assert first.entries == second.entries
    assert first.frozen_hash == second.frozen_hash
    assert len({row["trade_id"] for row in first.entries}) == len(first.entries)
    assert list(first.entries) == sorted(first.entries, key=lambda row: (row["entry_execution_ms"], row["symbol"], row["trade_id"]))
    assert all("policy" not in key for row in first.entries for key in row)


def test_future_hour_mutation_does_not_change_earlier_entry() -> None:
    hours = crossing_hours(second_cross_offset=24)
    minutes = execution_minutes(60)
    before = freeze_entries(hours, minutes).entries[0]
    changed = [dict(row) for row in hours]
    changed[-1]["close"] = 10000
    assert freeze_entries(changed, minutes).entries[0] == before


def test_month_reader_enforces_january_2025_microseconds(tmp_path: Path) -> None:
    raw_open = 1_735_689_600_000_000
    raw_close = raw_open + 60_000_000 - 1
    archive = tmp_path / "BTCUSDT-1m-2025-01.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("BTCUSDT-1m-2025-01.csv", f"{raw_open},1,2,0.5,1.5,10,{raw_close},15,7,0,0,0\n")
    rows = list(_read_month(archive, "BTCUSDT", "2025-01"))
    assert rows[0]["raw_time_unit"] == "microseconds"


def test_unexecutable_crossing_does_not_start_refractory_clock() -> None:
    hours = crossing_hours(second_cross_offset=10)
    minutes = execution_minutes(50)
    first_execution = START + 25 * 3_600_000
    minutes = [row for row in minutes if int(row["open_time_ms"]) != first_execution]
    result = freeze_entries(hours, minutes)
    assert result.unexecutable == 1
    assert result.suppressed_refractory == 0
    assert len(result.entries) == 1
    assert result.entries[0]["entry_execution_ms"] == first_execution + 10 * 3_600_000


def test_suppressed_crossing_does_not_extend_refractory_clock() -> None:
    closes = [100.0] * 24 + [101.0] + [100.0] * 9 + [101.0] + [100.0] * 13 + [101.0]
    result = freeze_entries([hour(i, close) for i, close in enumerate(closes)], execution_minutes(60))
    assert result.suppressed_refractory == 1
    assert len(result.entries) == 2
    assert result.entries[1]["entry_execution_ms"] - result.entries[0]["entry_execution_ms"] == 24 * 3_600_000


def test_duplicate_exact_boundary_minute_is_unexecutable() -> None:
    hours = crossing_hours()
    minutes = execution_minutes(25)
    minutes.append(dict(minutes[-1]))
    result = freeze_entries(hours, minutes)
    assert not result.entries
    assert result.unexecutable == 1


def test_invalid_exact_boundary_minute_is_unexecutable() -> None:
    minutes = execution_minutes(25)
    minutes[-1]["high"] = 0
    result = freeze_entries(crossing_hours(), minutes)
    assert not result.entries
    assert result.unexecutable == 1


def test_december_warmup_can_supply_sma_but_not_pre2024_entry() -> None:
    december_start = START - 24 * 3_600_000
    hours = [hour(i, close) for i, close in enumerate([100.0] * 24 + [101.0])]
    for row in hours:
        row["open_time_ms"] += december_start - START
        row["available_at_ms"] += december_start - START
    minutes = execution_minutes(25)
    for row in minutes:
        row["open_time_ms"] += december_start - START
    result = freeze_entries(hours, minutes)
    assert len(result.entries) == 1
    assert result.entries[0]["entry_execution_ms"] == START + 3_600_000
    assert all(row["entry_execution_ms"] >= START for row in result.entries)


def test_semantic_hash_ignores_source_csv_physical_formatting() -> None:
    columns = ("a", "b")
    unix = list(csv.DictReader(io.StringIO("a,b\nx,1\n")))
    physical_variant = list(csv.DictReader(io.StringIO('b,a\r\n"1","x"\r\n')))
    assert hash_rows(unix, columns) == hash_rows(physical_variant, columns)


def test_acquisition_provenance_survives_offline_revalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = tmp_path / "raw"

    def fake_download(url: str, destination: Path, *, max_bytes: int) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if url.endswith(".CHECKSUM"):
            archive = destination.with_suffix("")
            destination.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
        else:
            with zipfile.ZipFile(destination, "w") as handle:
                handle.writestr("fixture.csv", "")

    monkeypatch.setattr("binance_data_foundation.c2_acquisition._download", fake_download)
    first = _obtain_month("BTCUSDT", "2024-01", raw, offline=False, max_download_bytes=1_000_000)
    second = _obtain_month("BTCUSDT", "2024-01", raw, offline=True, max_download_bytes=1_000_000, prior=first)
    assert first["verification"]["mode"] == "online_acquisition"
    assert second["verification"]["mode"] == "offline_cache"
    assert second["initial_acquisition_evidence"] == first["initial_acquisition_evidence"]
    assert second["initial_acquisition_evidence"]["basis"] == "download_observed_by_application"
    assert second["http_retrieval_completed_at_utc"] == "unknown"
    assert "archive_mtime_utc" in second["filesystem_observations"]


def test_research_partitions_are_exact_and_machine_readable() -> None:
    assert research_partitions() == {
        "warmup": {"start_utc": "2023-12-31T00:00:00+00:00", "end_exclusive_utc": "2024-01-01T00:00:00+00:00"},
        "sanity_calibration": {"start_utc": "2024-01-01T00:00:00+00:00", "end_exclusive_utc": "2024-04-01T00:00:00+00:00"},
        "headline_evaluation": {"start_utc": "2024-04-01T00:00:00+00:00", "end_exclusive_utc": "2026-01-01T00:00:00+00:00"},
    }


def test_run_manifest_carries_research_partitions_without_absolute_interpreter_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    partitions = research_partitions()
    (artifact_dir / "history_summary.json").write_text(json.dumps({
        "normalized_hashes": {}, "symbols": ["BTCUSDT"],
        "source_start_utc": partitions["warmup"]["start_utc"],
        "study_start_utc": partitions["sanity_calibration"]["start_utc"],
        "study_end_exclusive_utc": partitions["headline_evaluation"]["end_exclusive_utc"],
        "research_partitions": partitions, "row_counts": {},
    }))
    (artifact_dir / "source_manifest.json").write_text("[]")
    monkeypatch.setattr("binance_data_foundation.c2_cli._hash", lambda _path: "hash")
    monkeypatch.setattr(
        "binance_data_foundation.c2_cli.subprocess.run",
        lambda *args, **kwargs: type("Result", (), {"stdout": "revision\n"})(),
    )
    _write_run_manifest(artifact_dir, {
        "aggregation_version": "v1", "aggregate_hashes": {}, "entry_fixture_id": "fixture",
        "frozen_entry_hash": "frozen", "aggregate_rows": {}, "aggregate_exclusions": {},
        "suppressed_refractory_signals": 0, "unexecutable_signals": 0,
    })
    manifest = json.loads((artifact_dir / "run_manifest.json").read_text())
    assert manifest["research_partitions"] == partitions
    assert not str(manifest["environment"]["interpreter"]).startswith("/")


def test_theoretical_full_range_row_counts() -> None:
    assert theoretical_row_counts() == {
        "1m_per_symbol": 1_054_080,
        "5m_per_symbol": 210_816,
        "1h_per_symbol": 17_568,
    }
