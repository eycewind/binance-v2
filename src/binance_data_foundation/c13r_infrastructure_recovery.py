"""Governed infrastructure recovery for the interrupted, frozen C13 run."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import c10_post_t2 as c10
from . import c12_post_t2_warning as c12
from . import c13_warning_economics as c13

AUTHORIZATION = "AUTHORIZE_C13R_ONE_SHOT"
OUTPUT_REL = "artifacts/c13r_c13_infrastructure_recovery"
CONTRACT_REL = "contracts/C13R_c13_infrastructure_recovery_CONTRACT.md"
C13_READY_REL = "artifacts/c13_post_t2_warning_economics/readiness_freeze.json"
C13_LEDGER_REL = "artifacts/c13_post_t2_warning_economics/attempt_ledger.jsonl"
INTERRUPTED_ATTEMPT = "C13-bbfde36f-2da4-4d32-8dd5-0467a2482f6b"
IDENTITY_KEYS = (
    "contract_sha256", "source_hashes", "population_sha256",
    "probability_provenance_sha256", "code_sha256", "config_sha256",
    "environment_sha256", "output_schema_sha256", "seed", "replicates",
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _read_json(path: Path):
    return json.loads(path.read_text())


def _ledger_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _historical_gate(repo: Path) -> dict:
    rows = _ledger_rows(repo / C13_LEDGER_REL)
    own = [x for x in rows if x.get("attempt_id") == INTERRUPTED_ATTEMPT]
    events = [x.get("event") for x in own]
    if events != ["START", "ECONOMIC_READ"]:
        raise RuntimeError("interrupted C13 historical lifecycle mismatch")
    if not own[1].get("economic_read"):
        raise RuntimeError("original C13 economic read is not recorded")
    forbidden = {"ECONOMIC_EMISSION", "PASS", "FAIL"}
    if forbidden.intersection(events):
        raise RuntimeError("original C13 unexpectedly has an economic result")
    original_files = sorted(
        str(p.relative_to(repo / c13.OUTPUT_REL))
        for p in (repo / c13.OUTPUT_REL).rglob("*") if p.is_file()
    )
    if original_files != ["attempt_ledger.jsonl", "readiness_freeze.json"]:
        raise RuntimeError("original C13 output state is not interruption-only")
    return {"attempt_id": INTERRUPTED_ATTEMPT, "events": events,
            "files": original_files, "economic_result_emitted": False}


def verify_frozen_identities(repo: Path) -> tuple[dict, dict]:
    frozen = _read_json(repo / C13_READY_REL)
    current = c13.preflight(repo)
    mismatches = {key: {"frozen": frozen.get(key), "current": current.get(key)}
                  for key in IDENTITY_KEYS if frozen.get(key) != current.get(key)}
    for rel, expected in frozen.get("source_hashes", {}).items():
        actual = _sha(repo / rel)
        if actual != expected:
            mismatches[f"source_hashes.{rel}"] = {"frozen": expected, "current": actual}
    if mismatches:
        raise RuntimeError("frozen C13 identity mismatch: " + ", ".join(sorted(mismatches)))
    return frozen, current


def preflight(repo: Path) -> dict:
    c13.reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("conda environment must be binance-v2-research")
    history = _historical_gate(repo)
    frozen, current = verify_frozen_identities(repo)
    population = _read_json(repo / "artifacts/c7_full_population_t2_exit_overlay/population_manifest.json")["rows"]
    t2 = sum(bool(x["overlay_strictly_before_p0"]) for x in population)
    provenance = _read_json(repo / "artifacts/c12_post_t2_warning_leadtime/c11_probability_reproduction.json")
    if len(population) != 2199 or t2 != 845 or len(population) - t2 != 1354:
        raise RuntimeError("C13 population counts mismatch")
    if provenance.get("status") != "PASS":
        raise RuntimeError("C11/C12 honest prediction provenance is not PASS")
    guard_verified = False
    try:
        c13.reject_2026("data/2026/guard_probe.csv")
    except PermissionError:
        guard_verified = True
    if not guard_verified:
        raise RuntimeError("2026 guard failed")
    test_evidence_path = repo / OUTPUT_REL / "test_evidence.json"
    if not test_evidence_path.exists():
        raise RuntimeError("C13R test evidence is required before economic access")
    test_evidence = _read_json(test_evidence_path)
    if test_evidence.get("focused", {}).get("status") != "PASS" or test_evidence.get("full_suite", {}).get("status") != "PASS":
        raise RuntimeError("C13R focused/full test evidence is not PASS")
    return {
        "status": "READY", "label": "C13R exact recovery replication of interrupted C13",
        "c13_history": history, "c13_frozen_identities": {k: frozen[k] for k in IDENTITY_KEYS},
        "identity_check": "PASS", "population": {"total": 2199, "t2": 845, "no_t2": 1354},
        "honest_prediction_provenance": "PASS", "guard_2026": "PASS",
        "environment": {"conda_env": os.environ.get("CONDA_DEFAULT_ENV"),
                        "python_version": sys.version.split()[0], "python": sys.executable,
                        "numpy": np.__version__, "platform": platform.platform()},
        "c13r_contract_sha256": _sha(repo / CONTRACT_REL),
        "test_evidence_sha256": _sha(test_evidence_path), "test_evidence": test_evidence,
        "c13_current_preflight_sha256": c13.semantic_hash(current),
        "seed": frozen["seed"], "replicates": frozen["replicates"], "economic_read": False,
    }


def _documents(repo: Path, ready: dict, attempt: str, result: dict, data: dict, population: list[dict]) -> dict:
    return {
        "run_manifest": {"version": "C13R_RUN_V1", "attempt_id": attempt, "status": "PASS",
                         "label": ready["label"], "one_shot": True,
                         "c13_contract_sha256": ready["c13_frozen_identities"]["contract_sha256"],
                         "c13r_contract_sha256": ready["c13r_contract_sha256"]},
        "provenance": ready,
        "source_population_reconciliation": {"total": len(population),
            "by_year": dict(Counter(str(x["entry_year"]) for x in population)),
            "t2": len(data["trades"]), "no_t2": len(population) - len(data["trades"]),
            "outcomes": dict(Counter(x["terminal"] for x in data["trades"]))},
        "prediction_availability": c12.population(data["trades"], data["binary_rows"], data["scored_rows"]),
        "policy_registry": {"P0": "canonical unchanged", "W1": {"threshold": "strictly <0.20", "persistence": 3}, "D2_CONTROL": "frozen midpoint boundary"},
        "execution_rules": {"completed_information_only": True, "execution": "immediate next 1m open", "P0_wins_ties": True, "gaps": "fail closed"},
        "cost_config": c13.COSTS, "bootstrap_config": {"seed": c13.SEED, "replicates": c13.REPLICATES, "block_weeks": 4},
        "canonical_paired_trade_table": {"rows": result["table"]},
        "pooled_report": {"bootstrap": result["bootstrap"], "C_BASE": result["sensitivities"]["C_BASE"]},
        "t2_non_t2_decomposition": result["decomposition"], "prediction_availability_decomposition": result["availability"],
        "w1_trigger_diagnostics": {"rows": result["diagnostics"]},
        "d2_control_report": {"trigger_count": result["trigger_counts"]["D2_CONTROL"], "contrast": result["bootstrap"]["contrasts"]["D2_CONTROL-P0"]},
        "year_reports": result["years"], "symbol_reports": result["symbols"],
        "equal_weight_symbol_report": {"W1-P0": result["breadth"]["equal_weight_symbol"]},
        "breadth_report": result["breadth"], "cost_sensitivities": result["sensitivities"],
        "safety_report": result["safety"], "winner_truncation_report": result["winners"],
        "holding_exposure_report": result["exposure"], "classification_predicates": result["classification"]["predicates"],
        "final_classification": {"label": result["classification"]["label"]},
    }


def run_once(repo: Path, authorization: str) -> dict:
    if authorization != AUTHORIZATION:
        raise PermissionError("explicit C13R authorization required")
    out, ledger = repo / OUTPUT_REL, repo / OUTPUT_REL / "attempt_ledger.jsonl"
    if any(x.get("economic_read") for x in _ledger_rows(ledger)):
        raise RuntimeError("C13R one-shot already consumed")
    ready = preflight(repo)
    existing = [p for p in out.rglob("*") if p.is_file()] if out.exists() else []
    allowed = {out / "readiness_freeze.json", out / "test_evidence.json", ledger}
    if any(p not in allowed for p in existing):
        raise RuntimeError("C13R output directory is not pre-economic clean")
    c13.write_json(out / "readiness_freeze.json", ready)
    attempt = f"C13R-{uuid.uuid4()}"
    now = lambda: datetime.now(timezone.utc).isoformat()
    _append(ledger, {"attempt_id": attempt, "event": "START", "timestamp": now(), "economic_read": False})
    try:
        _append(ledger, {"attempt_id": attempt, "event": "ECONOMIC_READ", "timestamp": now(), "economic_read": True})
        data = c12.generate_frozen_panel(repo)
        reproduction = c12.reproduce_c11(repo, data)
        if reproduction["status"] != "PASS":
            raise RuntimeError("C11 reproduction failed")
        population = _read_json(repo / "artifacts/c7_full_population_t2_exit_overlay/population_manifest.json")["rows"]
        markets = {s: c10.load_market(repo / c13.c7.INPUTS[s + "_1m"][0]) for s in c13.SYMBOLS}
        result = c13.execute(population, data, markets)
        docs = _documents(repo, ready, attempt, result, data, population)
        summary = {"label": ready["label"], "attempt_id": attempt, "status": "PASS",
            "interrupted_c13_attempt_id": INTERRUPTED_ATTEMPT, "c13_itself_rerun": False,
            "c13r_contract_sha256": ready["c13r_contract_sha256"],
            "population": docs["source_population_reconciliation"], "availability": docs["prediction_availability"],
            "trigger_counts": result["trigger_counts"], "economics": docs["pooled_report"],
            "decomposition": result["decomposition"], "safety": result["safety"], "winners": result["winners"],
            "years": result["years"], "symbols": result["symbols"], "breadth": result["breadth"],
            "classification": result["classification"], "cost_sensitivities": result["sensitivities"],
            "confirmations": {"real_c13r_economic_attempts": 1, "retry": False, "c13_scientific_change": False,
                              "accessed_2026": False, "c14_started": False}}
        docs["final_summary"] = summary
        temp = Path(tempfile.mkdtemp(prefix="c13r-", dir=out)); hashes = {}
        try:
            for name, value in docs.items():
                c13.write_json(temp / f"{name}.json", value)
                hashes[f"{name}.json"] = _sha(temp / f"{name}.json")
            c13.write_json(temp / "reproducibility_hashes.json", hashes)
            for path in temp.iterdir():
                shutil.move(str(path), out / path.name)
        finally:
            shutil.rmtree(temp)
        _append(ledger, {"attempt_id": attempt, "event": "ECONOMIC_EMISSION", "timestamp": now(), "economic_read": True, "output_hashes": hashes})
        _append(ledger, {"attempt_id": attempt, "event": "PASS", "timestamp": now(), "economic_read": True, "output_hashes": hashes})
        return summary
    except Exception as exc:
        _append(ledger, {"attempt_id": attempt, "event": "FAIL", "timestamp": now(), "economic_read": True,
                         "failure": f"{type(exc).__name__}: {exc}"})
        raise
