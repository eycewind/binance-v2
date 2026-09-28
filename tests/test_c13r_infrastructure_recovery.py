import json
from pathlib import Path

import pytest

from binance_data_foundation import c13r_infrastructure_recovery as c13r


def test_recovery_constants_are_isolated():
    assert c13r.OUTPUT_REL == "artifacts/c13r_c13_infrastructure_recovery"
    assert c13r.INTERRUPTED_ATTEMPT == "C13-bbfde36f-2da4-4d32-8dd5-0467a2482f6b"
    assert c13r.c13.SEED == 20261013 and c13r.c13.REPLICATES == 2000


def test_historical_gate_accepts_only_interrupted_state(tmp_path: Path):
    out = tmp_path / "artifacts/c13_post_t2_warning_economics"
    out.mkdir(parents=True)
    rows = [
        {"attempt_id": c13r.INTERRUPTED_ATTEMPT, "event": "START", "economic_read": False},
        {"attempt_id": c13r.INTERRUPTED_ATTEMPT, "event": "ECONOMIC_READ", "economic_read": True},
    ]
    (out / "attempt_ledger.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
    (out / "readiness_freeze.json").write_text("{}\n")
    assert c13r._historical_gate(tmp_path)["economic_result_emitted"] is False
    rows.append({"attempt_id": c13r.INTERRUPTED_ATTEMPT, "event": "PASS", "economic_read": True})
    (out / "attempt_ledger.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
    with pytest.raises(RuntimeError, match="lifecycle"):
        c13r._historical_gate(tmp_path)


def test_identity_mismatch_blocks_before_economic_read(monkeypatch, tmp_path: Path):
    frozen = {key: "same" for key in c13r.IDENTITY_KEYS}
    frozen["source_hashes"] = {}
    ready = tmp_path / c13r.C13_READY_REL
    ready.parent.mkdir(parents=True)
    ready.write_text(json.dumps(frozen))
    current = dict(frozen); current["seed"] = "changed"
    monkeypatch.setattr(c13r.c13, "preflight", lambda repo: current)
    with pytest.raises(RuntimeError, match="identity mismatch"):
        c13r.verify_frozen_identities(tmp_path)


def test_authorization_and_consumed_attempt_block(monkeypatch, tmp_path: Path):
    with pytest.raises(PermissionError, match="authorization"):
        c13r.run_once(tmp_path, "NO")
    ledger = tmp_path / c13r.OUTPUT_REL / "attempt_ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"event": "ECONOMIC_READ", "economic_read": True}) + "\n")
    monkeypatch.setattr(c13r, "preflight", lambda repo: pytest.fail("preflight must not run"))
    with pytest.raises(RuntimeError, match="consumed"):
        c13r.run_once(tmp_path, c13r.AUTHORIZATION)

