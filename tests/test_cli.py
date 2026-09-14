import csv
import json
import sys
from pathlib import Path

import pytest

from binance_data_foundation import cli
from binance_data_foundation.ingest import sha256_file


def _write_normalized_dir(path: Path, *, rows: int = 5760) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    hashes = {}
    start = 1_735_689_600_000
    for symbol in sorted(cli.EXPECTED_NORMALIZED_SYMBOLS):
        csv_path = path / f"{symbol}_1m_normalized.csv"
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["symbol", "open_time_ms", "open_time_utc", "close"])
            writer.writeheader()
            for i in range(rows):
                writer.writerow(
                    {
                        "symbol": symbol,
                        "open_time_ms": start + i * 60_000,
                        "open_time_utc": f"t{i}",
                        "close": "100",
                    }
                )
        hashes[str(csv_path)] = sha256_file(csv_path)
    return hashes


def _write_artifacts(path: Path, hashes: dict[str, str]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    quality = [{"symbol": symbol, "day": "ALL", "status": "pass"} for symbol in sorted(cli.EXPECTED_NORMALIZED_SYMBOLS)]
    (path / "data_quality.json").write_text(json.dumps(quality), encoding="utf-8")
    (path / "normalized_hashes.json").write_text(json.dumps(hashes), encoding="utf-8")


def _run_features(monkeypatch: pytest.MonkeyPatch, normalized: Path, artifacts: Path, output: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "binance-data-foundation",
            "features",
            "--normalized-dir",
            str(normalized),
            "--artifact-dir",
            str(artifacts),
            "--output",
            str(output),
        ],
    )
    cli.main()


def test_feature_cli_rejects_manifest_for_another_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    requested = tmp_path / "requested"
    other = tmp_path / "other"
    _write_normalized_dir(requested)
    other_hashes = _write_normalized_dir(other)
    artifacts = tmp_path / "artifacts"
    _write_artifacts(artifacts, other_hashes)
    output = tmp_path / "features.csv"
    with pytest.raises(SystemExit, match="manifest does not match"):
        _run_features(monkeypatch, requested, artifacts, output)
    assert not output.exists()


def test_feature_cli_rejects_missing_and_extra_normalized_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    normalized = tmp_path / "normalized"
    hashes = _write_normalized_dir(normalized)
    missing = normalized / "BTCUSDT_1m_normalized.csv"
    missing.unlink()
    artifacts = tmp_path / "artifacts"
    _write_artifacts(artifacts, hashes)
    with pytest.raises(SystemExit, match="missing expected"):
        _run_features(monkeypatch, normalized, artifacts, tmp_path / "missing.csv")

    missing.write_text("symbol,open_time_ms,open_time_utc,close\n", encoding="utf-8")
    (normalized / "DOGEUSDT_1m_normalized.csv").write_text("symbol,open_time_ms,open_time_utc,close\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="unexpected normalized"):
        _run_features(monkeypatch, normalized, artifacts, tmp_path / "extra.csv")


def test_feature_cli_rejects_mutation_after_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    normalized = tmp_path / "normalized"
    hashes = _write_normalized_dir(normalized)
    artifacts = tmp_path / "artifacts"
    _write_artifacts(artifacts, hashes)
    btc = normalized / "BTCUSDT_1m_normalized.csv"
    with btc.open("a", encoding="utf-8") as f:
        f.write("BTCUSDT,999,t-mutated,999\n")
    with pytest.raises(SystemExit, match="stale or mutated"):
        _run_features(monkeypatch, normalized, artifacts, tmp_path / "mutated.csv")


def test_feature_cli_failure_preserves_existing_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    normalized = tmp_path / "normalized"
    hashes = _write_normalized_dir(normalized)
    artifacts = tmp_path / "artifacts"
    _write_artifacts(artifacts, hashes)
    output = tmp_path / "features.csv"
    output.write_text("sentinel\n", encoding="utf-8")
    (normalized / "ETHUSDT_1m_normalized.csv").unlink()
    with pytest.raises(SystemExit):
        _run_features(monkeypatch, normalized, artifacts, output)
    assert output.read_text(encoding="utf-8") == "sentinel\n"


def test_feature_cli_compute_exception_preserves_existing_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    normalized = tmp_path / "normalized"
    hashes = _write_normalized_dir(normalized)
    btc = normalized / "BTCUSDT_1m_normalized.csv"
    rows = btc.read_text(encoding="utf-8").splitlines()
    rows[2] = rows[2].replace("BTCUSDT", "ETHUSDT")
    btc.write_text("\n".join(rows) + "\n", encoding="utf-8")
    hashes[str(btc)] = sha256_file(btc)
    artifacts = tmp_path / "artifacts"
    _write_artifacts(artifacts, hashes)
    output = tmp_path / "features.csv"
    output.write_text("sentinel\n", encoding="utf-8")
    with pytest.raises(ValueError, match="one symbol"):
        _run_features(monkeypatch, normalized, artifacts, output)
    assert output.read_text(encoding="utf-8") == "sentinel\n"


def test_feature_cli_passes_only_verified_file_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    normalized = tmp_path / "normalized"
    hashes = _write_normalized_dir(normalized)
    artifacts = tmp_path / "artifacts"
    _write_artifacts(artifacts, hashes)
    output = tmp_path / "features.csv"
    seen = {}

    def fake_compute_features_csv(normalized_dir: Path, output_path: Path, *, input_paths: list[Path] | None = None) -> Path:
        seen["normalized_dir"] = normalized_dir
        seen["input_paths"] = input_paths
        output_path.write_text("ok\n", encoding="utf-8")
        return output_path

    monkeypatch.setattr(cli, "compute_features_csv", fake_compute_features_csv)
    _run_features(monkeypatch, normalized, artifacts, output)
    assert seen["normalized_dir"] == normalized
    assert seen["input_paths"] == sorted((normalized / f"{symbol}_1m_normalized.csv").resolve() for symbol in cli.EXPECTED_NORMALIZED_SYMBOLS)
