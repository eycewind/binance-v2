from __future__ import annotations

import csv
import gzip
import io
import json
import os
import shutil
import zipfile
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .c2_common import (
    HISTORY_SCHEMA_VERSION, MAX_COMPRESSED_BYTES, MAX_LOCAL_BYTES, SOURCE_START_MS,
    STUDY_END_MS, STUDY_START_MS, SYMBOLS, iso, research_partitions, tree_size,
    valid_minute, write_json,
)
from .ingest import NORMALIZED_COLUMNS, _download, _parse_kline, sha256_file


MONTHLY_BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
MINUTE_COLUMNS = tuple(NORMALIZED_COLUMNS)


def approved_months() -> tuple[str, ...]:
    months = []
    year, month = 2023, 12
    while (year, month) <= (2025, 12):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return tuple(months)


def theoretical_row_counts() -> dict[str, int]:
    minute_rows = (STUDY_END_MS - SOURCE_START_MS) // 60_000
    return {"1m_per_symbol": minute_rows, "5m_per_symbol": minute_rows // 5, "1h_per_symbol": minute_rows // 60}


def ingest_history(
    raw_dir: Path,
    normalized_dir: Path,
    artifact_dir: Path,
    *,
    offline: bool = False,
    max_compressed_bytes: int = MAX_COMPRESSED_BYTES,
    max_local_bytes: int = MAX_LOCAL_BYTES,
) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = artifact_dir / "source_manifest.json"
    prior = _prior_manifest(manifest_path)
    staging = normalized_dir.parent / f".{normalized_dir.name}.c2-tmp"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    manifest: list[dict] = []
    quality: list[dict] = []
    total_archive_bytes = 0
    success = True
    writers: dict[str, tuple[io.TextIOWrapper, csv.DictWriter]] = {}
    raw_handles: list[gzip.GzipFile] = []
    binary_handles: list[io.BufferedWriter] = []
    row_counts = {symbol: 0 for symbol in SYMBOLS}
    first_ms: dict[str, int | None] = {symbol: None for symbol in SYMBOLS}
    last_ms: dict[str, int | None] = {symbol: None for symbol in SYMBOLS}
    try:
        for symbol in SYMBOLS:
            path = staging / f"{symbol}_1m.csv.gz"
            binary = path.open("wb")
            gz = gzip.GzipFile(filename="", mode="wb", fileobj=binary, mtime=0)
            text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
            writer = csv.DictWriter(text, fieldnames=MINUTE_COLUMNS, lineterminator="\n")
            writer.writeheader()
            binary_handles.append(binary)
            raw_handles.append(gz)
            writers[symbol] = (text, writer)
        for symbol in SYMBOLS:
            for month in approved_months():
                remaining_compressed = max_compressed_bytes - total_archive_bytes
                remaining_local = max_local_bytes - tree_size(raw_dir) - tree_size(normalized_dir) - tree_size(staging)
                item = _obtain_month(
                    symbol, month, raw_dir, offline=offline,
                    max_download_bytes=min(remaining_compressed, remaining_local),
                    prior=prior.get((symbol, month)),
                )
                manifest.append(item)
                if item["status"] != "verified":
                    quality.append(_failed_quality(symbol, month, item["status"], item.get("error", "unavailable")))
                    success = False
                    continue
                total_archive_bytes += int(item["bytes"])
                if total_archive_bytes > max_compressed_bytes:
                    quality.append(_failed_quality(symbol, month, "resource_limit", "compressed archive limit exceeded"))
                    success = False
                    continue
                try:
                    rows = list(_read_month(Path(item["zip_path"]), symbol, month))
                    check = validate_month(rows, symbol, month)
                except Exception as exc:
                    quality.append(_failed_quality(symbol, month, "invalid", str(exc)))
                    success = False
                    continue
                quality.append(check)
                if check["status"] != "pass":
                    success = False
                    continue
                text, writer = writers[symbol]
                for row in rows:
                    open_ms = int(row["open_time_ms"])
                    if SOURCE_START_MS <= open_ms < STUDY_END_MS:
                        writer.writerow({name: row[name] for name in MINUTE_COLUMNS})
                        row_counts[symbol] += 1
                        first_ms[symbol] = open_ms if first_ms[symbol] is None else first_ms[symbol]
                        last_ms[symbol] = open_ms
                text.flush()
                if tree_size(raw_dir) + tree_size(normalized_dir) + tree_size(staging) > max_local_bytes:
                    raise ValueError("local data byte limit exceeded")
    except Exception as exc:
        success = False
        quality.append(_failed_quality("ALL", "ALL", "fail", str(exc)))
    finally:
        for text, _writer in writers.values():
            try:
                text.flush()
                text.close()
            except Exception:
                pass
        for handle in raw_handles + binary_handles:
            try:
                handle.close()
            except Exception:
                pass

    expected_rows = theoretical_row_counts()["1m_per_symbol"]
    for symbol in SYMBOLS:
        if row_counts[symbol] != expected_rows:
            success = False
            quality.append(_failed_quality(symbol, "FILTERED", "fail", f"rows={row_counts[symbol]} expected={expected_rows}"))
    normalized_hashes: dict[str, str] = {}
    if success:
        normalized_hashes = {p.name: sha256_file(p) for p in sorted(staging.glob("*.csv.gz"))}
        if normalized_dir.exists():
            old = normalized_dir.parent / f".{normalized_dir.name}.old"
            if old.exists():
                shutil.rmtree(old)
            os.replace(normalized_dir, old)
            os.replace(staging, normalized_dir)
            shutil.rmtree(old)
        else:
            os.replace(staging, normalized_dir)
    else:
        shutil.rmtree(staging, ignore_errors=True)
    summary = {
        "success": success, "schema_version": HISTORY_SCHEMA_VERSION, "symbols": list(SYMBOLS),
        "source_start_utc": iso(SOURCE_START_MS), "study_start_utc": iso(STUDY_START_MS),
        "study_end_exclusive_utc": iso(STUDY_END_MS), "research_partitions": research_partitions(),
        "theoretical_row_counts": theoretical_row_counts(),
        "expected_archives": len(SYMBOLS) * len(approved_months()),
        "actual_verified_archives": sum(x.get("status") == "verified" for x in manifest),
        "archive_bytes": total_archive_bytes, "normalized_bytes": tree_size(normalized_dir) if success else 0,
        "row_counts": row_counts,
        "first_open_utc": {s: iso(v) if v is not None else None for s, v in first_ms.items()},
        "last_open_utc": {s: iso(v) if v is not None else None for s, v in last_ms.items()},
        "normalized_hashes": normalized_hashes,
    }
    write_json(manifest_path, manifest)
    write_json(artifact_dir / "monthly_validation.json", quality)
    write_json(artifact_dir / "history_summary.json", summary)
    return summary


def validate_month(rows: list[dict], symbol: str, month: str) -> dict:
    year, mon = map(int, month.split("-"))
    expected_count = monthrange(year, mon)[1] * 1440
    start_ms = int(datetime(year, mon, 1, tzinfo=timezone.utc).timestamp() * 1000)
    timestamps = [int(row["open_time_ms"]) for row in rows]
    expected = set(range(start_ms, start_ms + expected_count * 60_000, 60_000))
    actual = set(timestamps)
    issues = []
    duplicate_count = len(timestamps) - len(actual)
    gap_count, extra_count = len(expected - actual), len(actual - expected)
    invalid_count = sum(not valid_minute(row) for row in rows)
    if len(rows) != expected_count: issues.append(f"rows={len(rows)} expected={expected_count}")
    if duplicate_count: issues.append(f"duplicates={duplicate_count}")
    if gap_count: issues.append(f"gaps={gap_count}")
    if extra_count: issues.append(f"off_grid={extra_count}")
    if invalid_count: issues.append(f"invalid={invalid_count}")
    if timestamps != sorted(timestamps): issues.append("unexpected_ordering")
    return {"symbol": symbol, "month": month, "status": "pass" if not issues else "fail",
            "rows": len(rows), "first_open_utc": iso(min(timestamps)) if timestamps else None,
            "last_open_utc": iso(max(timestamps)) if timestamps else None, "gap_count": gap_count,
            "duplicate_count": duplicate_count, "off_grid_count": extra_count,
            "invalid_count": invalid_count, "issues": issues}


def _obtain_month(symbol: str, month: str, raw_dir: Path, *, offline: bool,
                  max_download_bytes: int, prior: dict | None = None) -> dict:
    name = f"{symbol}-1m-{month}.zip"
    url = f"{MONTHLY_BASE_URL}/{symbol}/1m/{name}"
    checksum_url = url + ".CHECKSUM"
    folder = raw_dir / symbol / "1m"
    folder.mkdir(parents=True, exist_ok=True)
    archive, checksum = folder / name, folder / f"{name}.CHECKSUM"
    downloaded_archive = downloaded_checksum = False
    try:
        if not archive.exists():
            if offline: raise FileNotFoundError(f"offline cache miss: {archive}")
            _download(url, archive, max_bytes=max_download_bytes)
            downloaded_archive = True
        remaining = max_download_bytes - archive.stat().st_size
        if not checksum.exists():
            if offline: raise FileNotFoundError(f"offline checksum miss: {checksum}")
            _download(checksum_url, checksum, max_bytes=min(4096, remaining))
            downloaded_checksum = True
        verified_at = datetime.now(timezone.utc).isoformat()
        published = checksum.read_text(encoding="utf-8").split()[0].lower()
        actual = sha256_file(archive)
        acquisition = _acquisition_evidence(prior, archive, checksum, downloaded_archive or downloaded_checksum, verified_at)
        return {
            "symbol": symbol, "month": month, "status": "verified" if actual == published else "checksum_failed",
            "url": url, "checksum_url": checksum_url, "zip_path": str(archive), "checksum_path": str(checksum),
            "sha256": actual, "published_sha256": published, "bytes": archive.stat().st_size,
            "schema_parser_version": HISTORY_SCHEMA_VERSION,
            "verification": {"verified_at_utc": verified_at,
                             "mode": "offline_cache" if offline else ("online_acquisition" if downloaded_archive or downloaded_checksum else "online_cache")},
            "filesystem_observations": {"archive_mtime_utc": _mtime(archive), "checksum_mtime_utc": _mtime(checksum)},
            "initial_acquisition_evidence": acquisition,
            "http_retrieval_completed_at_utc": "unknown",
        }
    except Exception as exc:
        return {"symbol": symbol, "month": month, "status": "missing", "url": url,
                "checksum_url": checksum_url, "error": str(exc)}


def _acquisition_evidence(prior: dict | None, archive: Path, checksum: Path, downloaded: bool, observed_at: str) -> dict:
    if prior and prior.get("initial_acquisition_evidence"):
        evidence = prior["initial_acquisition_evidence"]
        if evidence.get("basis") == "filesystem_mtime_observation" and prior.get("verification", {}).get("mode") == "offline_cache":
            return {**evidence, "basis": "filesystem_mtime_observation_from_t1_cache",
                    "interpretation_is_inference": True,
                    "note": "The paired file mtimes predate the final offline verification and are retained as evidence of cache creation during the T1 acquisition workflow; they are not HTTP completion times."}
        return evidence
    if downloaded:
        return {"basis": "download_observed_by_application", "observed_at_utc": observed_at,
                "http_completion_time_utc": "unknown"}
    if prior and prior.get("original_retrieval_time_utc") == "unknown":
        return {"basis": "filesystem_mtime_observation_from_t1_cache", "observed_at_utc": "unknown",
                "archive_mtime_utc": _mtime(archive), "checksum_mtime_utc": _mtime(checksum),
                "http_completion_time_utc": "unknown", "interpretation_is_inference": True,
                "note": "The paired file mtimes predate the final offline verification and are retained as evidence of cache creation during the T1 acquisition workflow; they are not HTTP completion times."}
    return {"basis": "filesystem_mtime_observation", "observed_at_utc": "unknown",
            "archive_mtime_utc": _mtime(archive), "checksum_mtime_utc": _mtime(checksum),
            "http_completion_time_utc": "unknown",
            "note": "Files predated this verification pass; mtimes are filesystem observations, not HTTP completion times."}


def _prior_manifest(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists(): return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return {(row["symbol"], row["month"]): row for row in rows if "symbol" in row and "month" in row}
    except (OSError, ValueError, TypeError):
        return {}


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def _read_month(path: Path, symbol: str, month: str) -> Iterator[dict]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(names) != 1: raise ValueError(f"expected one csv in {path}")
        with archive.open(names[0]) as source:
            reader = csv.reader((line.decode("utf-8").strip() for line in source))
            for raw in reader:
                if raw and raw[0] != "open_time":
                    yield _parse_kline(raw, symbol, "1m", f"{month}-01")


def _failed_quality(symbol: str, month: str, status: str, issue: str) -> dict:
    return {"symbol": symbol, "month": month, "status": status, "rows": 0,
            "gap_count": None, "duplicate_count": None, "off_grid_count": None,
            "invalid_count": None, "issues": [issue]}
