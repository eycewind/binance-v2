import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/c6_reporting_completion.py"
RESULT = ROOT / "artifacts/c6_simple_t2_exit_controls/t2/attempts/c6t2-72bd5929bb3c44e2a4ed1576f976a82e/c6_t2_results.json"
LEDGER = ROOT / "artifacts/c6_simple_t2_exit_controls/t2/attempt_ledger.jsonl"
EXPECTED = "4950bd0d6a307fe31fcf71d40386f06e359183fa68671d65db85bac556570344"


def load_module():
    spec = importlib.util.spec_from_file_location("c6_reporting_completion", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_reporting_is_static_and_cannot_invoke_economics():
    tree = ast.parse(SCRIPT.read_text())
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert all("binance_data_foundation" not in ast.unparse(node) for node in imports)
    forbidden = ("run_c6_t2_once", "execute_economic_replay", "execute_economic_fixture",
                 "exit_first_t2", "exit_second_t2", "timing_permutations")
    assert not any(name in SCRIPT.read_text() for name in forbidden)


def test_immutable_identity_and_single_attempt():
    assert hashlib.sha256(RESULT.read_bytes()).hexdigest() == EXPECTED
    events = [json.loads(line) for line in LEDGER.read_text().splitlines()]
    assert len(events) == 2
    assert len({e["attempt_id"] for e in events}) == 1
    assert [e["event"] for e in events] == ["START", "PASS"]


def test_verification_pins_gates_stop_assignments_and_interpretation():
    module = load_module()
    data, events, result = module.verify(ROOT)
    assert result == RESULT and len(events) == 2
    assert data["statistics"]["evidence_labels"][:2] == ["STRONG_POSITIVE", "STRONG_NEGATIVE"]
    assert data["statistics"]["reached"] == [True, True, False]
    assert data["interpretation"] == "MIXED"
    assert len(data["s3_assignments"]) == 1000
