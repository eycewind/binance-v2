from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from binance_data_foundation import c4_locked_input as subject, c4_modeling


CLASSES = {
    "T1": ["continuation", "adverse_reversal", "no_event_60m"],
    "T2": ["renewed_peak", "substantial_giveback", "no_event_60m"],
}
CONTINUOUS = ["x", "y", "zero_5m_count_6"]
SCHEMA_COLUMNS = ["symbol_ETHUSDT", "x", "y", "zero_5m_count_6"]
MODEL_COLUMNS = ["symbol_ETHUSDT", "x", "y"]


def _checkpoint():
    prep = {f"{target}_P1": {"columns": MODEL_COLUMNS, "parameters": {
        "x": {"excluded_zero_iqr": False}, "y": {"excluded_zero_iqr": False},
        "zero_5m_count_6": {"excluded_zero_iqr": True}}}
        for target in CLASSES}
    models = {target: {"models": {"P1": {"columns": MODEL_COLUMNS}}} for target in CLASSES}
    schema = {"targets": {target: {"P1": SCHEMA_COLUMNS} for target in CLASSES}}
    freeze = {"locked_2025_evaluation_sha256": subject.EXPECTED_CONFIG_SHA256,
              "feature_schema_sha256": "f" * 64}
    return SimpleNamespace(freeze_hash=subject.EXPECTED_FREEZE_SHA256, freeze=freeze,
                           preprocessing=prep, models=models, schema=schema)


def _row(target, number, **changes):
    base = {
        "row_id": f"row-{number}", "trade_id": f"trade-{number}", "target_id": target,
        "entry_execution_ms": subject.START_2025_MS + 86_400_000,
        "snapshot_ms": subject.START_2025_MS + 86_700_000 + number,
        "symbol": "BTCUSDT", "trade_entry_week": "2024-12-30",
        "snapshot_month": "2025-01", "snapshot_quarter": "2025-Q1",
        "temporal_partition": "2025_locked", "target_eligible": True, "resolved": True,
        "censored": False, "ambiguous": False, "event_class": CLASSES[target][number % 3],
        "entry_price": 100.0, "elapsed_minutes": 60.0, "current_return": 0.01,
        "drawdown_from_running_peak": -0.01, "peak_gain_retained_fraction": 0.5,
        "upper_barrier": 102.0, "lower_barrier": 99.0, "snapshot_close": 101.0,
    }
    base.update(changes)
    return base


def _install_synthetic(monkeypatch, tmp_path, rows_by_target=None, feature_order=CONTINUOUS):
    artifact = tmp_path / "artifacts/c4_sequential_exit_state"
    artifact.mkdir(parents=True)
    (tmp_path / "environment.yml").write_text("synthetic\n")
    (tmp_path / "requirements-dev.txt").write_text("synthetic\n")
    calls = []

    def checkpoint(repo, art):
        calls.append("freeze")
        return _checkpoint()

    def load(repo):
        calls.append("values")
        return (), {}, {}, []

    tables = rows_by_target or {target: [_row(target, offset)]
                                for target, offset in (("T1", 0), ("T2", 3))}
    monkeypatch.setattr(subject, "_checkpoint", checkpoint)
    monkeypatch.setattr(subject, "_source_provenance", lambda repo, art: [])
    monkeypatch.setattr(subject, "load_inputs", load)
    monkeypatch.setattr(subject, "build_tables", lambda *args: tables)

    @contextmanager
    def builder_context():
        def builder(repo, rows):
            features = {row["row_id"]: {name: float(i + 1) for i, name in enumerate(feature_order)}
                        for row in rows}
            return list(rows), features
        yield builder

    monkeypatch.setattr(subject, "_accepted_feature_builder_for_2025", builder_context)
    return artifact, calls


def _prepare(monkeypatch, tmp_path, **kwargs):
    artifact, calls = _install_synthetic(monkeypatch, tmp_path, **kwargs)
    result = subject.prepare_locked_2025_input(tmp_path, artifact)
    return artifact, calls, result


def test_freeze_validation_precedes_predictive_value_loading(monkeypatch, tmp_path):
    artifact = tmp_path / "artifacts/c4_sequential_exit_state"; artifact.mkdir(parents=True)
    monkeypatch.setattr(subject, "_checkpoint", lambda *args: (_ for _ in ()).throw(RuntimeError("bad freeze")))
    monkeypatch.setattr(subject, "load_inputs", lambda *args: pytest.fail("predictive values consumed"))
    with pytest.raises(RuntimeError, match="bad freeze"):
        subject.prepare_locked_2025_input(tmp_path, artifact)


def test_2026_rejected_before_feature_value_consumption():
    class Bomb(dict):
        def __getitem__(self, key):
            if key not in ("entry_execution_ms", "snapshot_ms"):
                raise AssertionError("predictive value consumed")
            return super().__getitem__(key)
    row = Bomb(entry_execution_ms=subject.END_2025_MS, snapshot_ms=subject.END_2025_MS)
    with pytest.raises(ValueError, match="2025 entries only"):
        subject._validate_2025_metadata(row)


def test_exact_feature_columns_and_order(monkeypatch, tmp_path):
    artifact, _, _ = _prepare(monkeypatch, tmp_path)
    rows = json.loads((artifact / subject.INPUT_NAME).read_text())
    assert list(rows[0]["features"]) == CONTINUOUS
    assert rows[0]["features"]["zero_5m_count_6"] == 3.0
    artifact2, _ = _install_synthetic(monkeypatch, tmp_path / "bad", feature_order=["x", "y"])
    with pytest.raises(RuntimeError, match="feature column mismatch"):
        subject.prepare_locked_2025_input(tmp_path / "bad", artifact2)


def test_exact_class_order_is_enforced(monkeypatch, tmp_path):
    rows = {"T1": [_row("T1", 0, event_class="wrong")], "T2": [_row("T2", 3)]}
    artifact, _ = _install_synthetic(monkeypatch, tmp_path, rows)
    with pytest.raises(ValueError, match="class order"):
        subject.prepare_locked_2025_input(tmp_path, artifact)


def test_censored_ambiguous_and_ineligible_rows_excluded(monkeypatch, tmp_path):
    rows = {
        "T1": [_row("T1", 0), _row("T1", 1, censored=True, resolved=False),
               _row("T1", 2, ambiguous=True, resolved=False), _row("T1", 4, target_eligible=False, resolved=False)],
        "T2": [_row("T2", 3)],
    }
    artifact, _, result = _prepare(monkeypatch, tmp_path, rows_by_target=rows)
    assert result["targets"]["T1"]["excluded_rows_by_reason"] == {
        "ambiguous": 1, "censored": 1, "feature_incomplete": 0, "target_ineligible": 1}
    assert len(json.loads((artifact / subject.INPUT_NAME).read_text())) == 2


def test_deterministic_order_ids_and_hash(monkeypatch, tmp_path):
    rows = {"T1": [_row("T1", 2), _row("T1", 0)], "T2": [_row("T2", 3), _row("T2", 1)]}
    artifact, _, first = _prepare(monkeypatch, tmp_path / "one", rows_by_target=rows)
    data = json.loads((artifact / subject.INPUT_NAME).read_text())
    assert [row["row_id"] for row in data] == ["row-0", "row-1", "row-2", "row-3"]
    artifact2, _, second = _prepare(monkeypatch, tmp_path / "two", rows_by_target=rows)
    assert first["input_sha256"] == second["input_sha256"]
    assert (artifact / subject.INPUT_NAME).read_bytes() == (artifact2 / subject.INPUT_NAME).read_bytes()


def test_atomic_write_and_refusal_to_overwrite(monkeypatch, tmp_path):
    artifact, _, result = _prepare(monkeypatch, tmp_path)
    assert Path(result["input_path"]).is_file()
    assert not list(artifact.glob(".*.tmp"))
    original = (artifact / subject.INPUT_NAME).read_bytes()
    with pytest.raises(FileExistsError, match="overwrite is prohibited"):
        subject.prepare_locked_2025_input(tmp_path, artifact)
    assert (artifact / subject.INPUT_NAME).read_bytes() == original


def test_no_prediction_fit_or_evaluation_invoked(monkeypatch, tmp_path):
    from binance_data_foundation import c4_locked_eval, c4_modeling
    for module, names in ((c4_locked_eval, ("evaluate_locked_2025", "predict_feature_rows")),
                          (c4_modeling, ("fit_multinomial", "fit_preprocessing", "predict"))):
        for name in names:
            monkeypatch.setattr(module, name, lambda *a, _name=name, **k: pytest.fail(f"{_name} invoked"))
    _prepare(monkeypatch, tmp_path)


def test_both_targets_and_manifest_hash_agreement(monkeypatch, tmp_path):
    artifact, calls, result = _prepare(monkeypatch, tmp_path)
    rows = json.loads((artifact / subject.INPUT_NAME).read_text())
    manifest = json.loads((artifact / subject.MANIFEST_NAME).read_text())
    digest = hashlib.sha256((artifact / subject.INPUT_NAME).read_bytes()).hexdigest()
    assert calls == ["freeze", "values"]
    assert {row["target"] for row in rows} == {"T1", "T2"}
    assert manifest["input_sha256"] == result["input_sha256"] == digest
    assert manifest["row_count"] == len(rows)
    assert manifest["predictive_scoring_performed"] is False
    assert manifest["2026_access"] is False
    assert manifest["superseded_invalid_input"]["sha256"] == subject.SUPERSEDED_INPUT_SHA256


def test_producer_rows_pass_locked_completeness_contract(monkeypatch, tmp_path):
    artifact, _, _ = _prepare(monkeypatch, tmp_path)
    rows = json.loads((artifact / subject.INPUT_NAME).read_text())
    assert {row["target"] for row in rows} == {"T1", "T2"}
    for row in rows:
        subject.validate_prepared_row_schema(_checkpoint(), row)


def test_authoritative_2024_zero_count_parity():
    repo = Path(__file__).parents[1]
    artifact = repo / "artifacts/c4_sequential_exit_state"
    raw = c4_modeling.load_accepted_2024_rows(
        artifact / "local/t1_snapshots.csv", c4_modeling.ACCEPTED_CORE_HASHES["T1"])
    _, _, minutes, _ = c4_modeling.load_inputs(repo)
    accepted_row = expected = None
    for row in raw:
        candidate = c4_modeling.causal_feature_row(row, minutes[row["symbol"]], minutes["BTCUSDT"])
        if candidate is not None:
            accepted_row, expected = row, candidate
            break
    assert accepted_row is not None and expected is not None
    retained, actual = c4_modeling.build_feature_table(repo, [accepted_row])
    assert retained == [accepted_row]
    assert actual[accepted_row["row_id"]] == expected
    assert actual[accepted_row["row_id"]]["zero_5m_count_6"] == expected["zero_5m_count_6"]
