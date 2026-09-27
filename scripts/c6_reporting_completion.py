#!/usr/bin/env python3
"""Complete C6 reporting strictly from the immutable authorized result."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ATTEMPT = "c6t2-72bd5929bb3c44e2a4ed1576f976a82e"
RESULT_SHA = "4950bd0d6a307fe31fcf71d40386f06e359183fa68671d65db85bac556570344"
CONTRACT_SHA = "4ef0452314a4c289823896c641660836e9177afe6667bc7bf12de18cc52c09a0"
READINESS_SHA = "11d8e7c96bd3c280bf734aaca90a972114d4d620b9d720ee188cf4cd06b86334"
SOURCE_SHA = "306cda35ecf90ddf64fa36db50989c18b0478124251bda0b0c70ea59826cdcdb"
CONFIG_SHA = "e8219260f8254b1d04db512c0a5b32cfd3e7ffaba4d31bedbad8a0f492fc5583"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
YEARS = ("2024", "2025")
POLICIES = (
    "P0_HELD_V1", "G1_Q75_EXIT_V1", "P1_Q75_EXIT_V1",
    "S1_EXIT_FIRST_T2_V1", "S2_EXIT_SECOND_T2_V1",
    "S4_FIRST_T2_COIN_FLIP_V1",
)
S3 = "S3_G1_TIMING_PERMUTATION_V1"
CONTRASTS = (
    ("S1_minus_P0", "S1_EXIT_FIRST_T2_V1", "P0_HELD_V1"),
    ("G1_minus_S1", "G1_Q75_EXIT_V1", "S1_EXIT_FIRST_T2_V1"),
    ("G1_minus_S3", "G1_Q75_EXIT_V1", S3),
    ("S2_minus_P0", "S2_EXIT_SECOND_T2_V1", "P0_HELD_V1"),
    ("G1_minus_S2", "G1_Q75_EXIT_V1", "S2_EXIT_SECOND_T2_V1"),
    ("G1_minus_P0", "G1_Q75_EXIT_V1", "P0_HELD_V1"),
    ("P1_minus_S1", "P1_Q75_EXIT_V1", "S1_EXIT_FIRST_T2_V1"),
    ("P1_minus_S2", "P1_Q75_EXIT_V1", "S2_EXIT_SECOND_T2_V1"),
    ("P1_minus_S3", "P1_Q75_EXIT_V1", S3),
    ("P1_minus_S4", "P1_Q75_EXIT_V1", "S4_FIRST_T2_COIN_FLIP_V1"),
    ("S4_minus_P0", "S4_FIRST_T2_COIN_FLIP_V1", "P0_HELD_V1"),
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def unavailable(reason: str) -> dict:
    return {"status": "IRRECOVERABLE_FROM_IMMUTABLE_OUTPUT", "reason": reason}


def verify(repo: Path) -> tuple[dict, list[dict], Path]:
    result = repo / "artifacts/c6_simple_t2_exit_controls/t2/attempts" / ATTEMPT / "c6_t2_results.json"
    ledger = repo / "artifacts/c6_simple_t2_exit_controls/t2/attempt_ledger.jsonl"
    if sha(result) != RESULT_SHA:
        raise RuntimeError("canonical result hash mismatch")
    events = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    if len(events) != 2 or {e.get("attempt_id") for e in events} != {ATTEMPT}:
        raise RuntimeError("ledger does not contain exactly one economic attempt")
    if [(e.get("event"), e.get("status")) for e in events] != [("START", "START"), ("PASS", "PASS")]:
        raise RuntimeError("authorized attempt lifecycle mismatch")
    for event in events:
        if (event.get("contract_sha256") != CONTRACT_SHA or event.get("readiness_sha256") != READINESS_SHA
                or event.get("source_hash") != SOURCE_SHA or event.get("configuration_hash") != CONFIG_SHA):
            raise RuntimeError("attempt identity mismatch")
    data = json.loads(result.read_text())
    if data.get("interpretation") != "MIXED" or data["statistics"]["evidence_labels"][:2] != ["STRONG_POSITIVE", "STRONG_NEGATIVE"]:
        raise RuntimeError("frozen interpretation or gates changed")
    if data["statistics"]["reached"] != [True, True, False]:
        raise RuntimeError("frozen hierarchy stopping point changed")
    if len(data.get("s3_assignments", [])) != 1000 or data["s3_authentication"].get("assignments") != 1000:
        raise RuntimeError("authorized S3 assignment set missing")
    return data, events, result


def equal_weight(data: dict) -> dict:
    summaries = data["metrics"]["policy_summaries"]
    out = {"definition": "arithmetic mean of five immutable symbol-level net-expectancy summaries; symbols equally weighted",
           "role": "descriptive_only", "cost_cases": {}}
    for cost in ("C0", "C_BASE", "C_S5", "C_S10"):
        rows = {}
        for policy in POLICIES:
            values = [summaries[s][policy][cost]["net_expectancy"] for s in SYMBOLS]
            rows[policy] = {"net_expectancy": sum(values) / len(values), "symbol_values": dict(zip(SYMBOLS, values))}
        rows[S3] = unavailable("immutable result stores S3 economics only as a pooled assignment average")
        out["cost_cases"][cost] = rows
    return out


def contrasts(data: dict, scopes: tuple[str, ...]) -> dict:
    summaries = data["metrics"]["policy_summaries"]
    out = {"endpoint": "C_BASE net expectancy difference", "role": "diagnostic_only", "scopes": {}}
    for scope in scopes:
        rows = {}
        for name, left, right in CONTRASTS:
            if left == S3 or right == S3:
                rows[name] = unavailable("immutable result has no S3 subgroup economic summary")
            else:
                lv = summaries[scope][left]["C_BASE"]["net_expectancy"]
                rv = summaries[scope][right]["C_BASE"]["net_expectancy"]
                rows[name] = {"left": left, "right": right, "left_value": lv, "right_value": rv,
                              "point_estimate": lv - rv, "uncertainty": "UNAVAILABLE"}
        out["scopes"][scope] = rows
    return out


def exposure(data: dict) -> dict:
    summaries = data["metrics"]["policy_summaries"]
    scopes = (*YEARS, *SYMBOLS, "pooled")
    rows = {}
    for scope in scopes:
        rows[scope] = {}
        for policy in POLICIES:
            metric = summaries[scope][policy]["C_BASE"]
            seconds = metric["holding_seconds"] * metric["usable"]
            rows[scope][policy] = {"mean_holding_seconds": metric["holding_seconds"],
                                   "summed_exposure_seconds": seconds,
                                   "summed_exposure_hours": seconds / 3600.0,
                                   "derivation": "immutable mean holding seconds multiplied by immutable usable count"}
    rows["pooled"][S3] = {
        "mean_holding_seconds": data["metrics"]["s3_assignment_averaged"]["C_BASE"]["holding_seconds"],
        "summed_exposure_seconds": data["metrics"]["s3_assignment_averaged"]["C_BASE"]["holding_seconds"] * 439.0,
        "summed_exposure_hours": data["metrics"]["s3_assignment_averaged"]["C_BASE"]["holding_seconds"] * 439.0 / 3600.0,
        "derivation": "immutable assignment-averaged mean holding seconds multiplied by immutable trade count",
    }
    missing_reason = "required per-trade execution indicators/timestamps/notional were not retained in the authorized result"
    return {"recoverable": {"summed_exposure": rows}, "irrecoverable": {
        key: unavailable(missing_reason) for key in (
            "union_exposure", "trigger_count_rate", "exit_count_rate", "fallback_count_rate",
            "executed_entry_leg_count", "executed_exit_leg_count", "executed_notional", "unresolved_count")}}


def s3_diagnostics(data: dict) -> dict:
    identity = {row["trade_id"]: row for row in data["s3_structural_inputs"]}
    scopes = defaultdict(lambda: {"trades": 0, "g1_labels": Counter()})
    for row in data["s3_structural_inputs"]:
        for scope in (str(row["year"]), row["symbol"]):
            scopes[scope]["trades"] += 1
            scopes[scope]["g1_labels"][str(row["g1_label"])] += 1
    # Authenticate use of the stored assignments without generating any mapping.
    assignment_scope_counts = defaultdict(list)
    for assignment in data["s3_assignments"]:
        current = defaultdict(Counter)
        for row in assignment["rows"]:
            base = identity[row["trade_id"]]
            for scope in (str(base["year"]), base["symbol"]):
                current[scope][str(row["label"])] += 1
        for scope in scopes:
            assignment_scope_counts[scope].append(current[scope])
    panels = {}
    for scope, item in sorted(scopes.items()):
        expected = dict(sorted(item["g1_labels"].items()))
        preserved = all(dict(sorted(c.items())) == expected for c in assignment_scope_counts[scope])
        panels[scope] = {"trades": item["trades"], "timing_label_counts_per_assignment": expected,
                         "all_1000_assignments_preserve_stratum_multiset": preserved,
                         "economic_summary": unavailable("S3 per-trade economic outcomes were not retained")}
    return {"role": "descriptive_only", "authorized_assignment_count": 1000,
            "assignment_authentication_sha256": data["s3_authentication"]["byte_sha256"], "panels": panels}


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    data, events, result = verify(repo)
    out = repo / "artifacts/c6_simple_t2_exit_controls/t2/reporting_completion"
    out.mkdir(parents=True, exist_ok=True)
    eq = equal_weight(data)
    year = contrasts(data, YEARS)
    symbol = contrasts(data, SYMBOLS)
    account = exposure(data)
    s3 = s3_diagnostics(data)
    calendar = unavailable("per-trade C6 economic outcomes and entry-month identities were not retained in the authorized result")
    uncertainty = {
        "canonical_pooled_gate_uncertainty": data["statistics"]["gates"],
        "canonical_s3_assignment_uncertainty": data["statistics"]["assignment_uncertainty"],
        "year_and_symbol_uncertainty": unavailable("per-trade outcomes and frozen bootstrap multiplicities were not retained"),
        "calendar_month_sensitivity": calendar,
    }
    outputs = {
        "equal_weight_symbol_summary.json": eq,
        "exposure_frequency_accounting.json": account,
        "s3_year_symbol_panels.json": s3,
        "calendar_month_sensitivity.json": calendar,
        "year_contrasts.json": year,
        "symbol_contrasts.json": symbol,
        "uncertainty_panels.json": uncertainty,
    }
    frozen = {"economic_attempt_count": 1, "economic_replay_rerun": False,
              "formal_hierarchy_stop": "Gate 2", "Gate1": "STRONG_POSITIVE",
              "Gate2": "STRONG_NEGATIVE", "Gate3": "DESCRIPTIVE_ONLY",
              "final_interpretation": "MIXED"}
    recoverability = {
        "completed": ["equal-weight-symbol net-expectancy summaries", "summed exposure from retained means/counts",
                      "non-S3 year/symbol C_BASE point contrasts", "S3 year/symbol structural timing-label panels"],
        "irrecoverable": ["S3 year/symbol economic panels", "whole-calendar-month uncertainty sensitivity",
                          "union exposure", "trigger/exit/fallback frequencies", "executed-leg counts",
                          "executed notional", "unresolved counts", "year/symbol uncertainty panels"],
    }
    outputs["final_reporting_summary.json"] = {**frozen, "recoverability": recoverability,
        "canonical_gate_statistics": data["statistics"]["gates"], "canonical_interpretation": data["interpretation"]}
    for name, value in outputs.items():
        write_json(out / name, value)
    artifact_hashes = {name: sha(out / name) for name in sorted(outputs)}
    repro = {**frozen, "attempt_id": ATTEMPT, "canonical_result_path": str(result.relative_to(repo)),
             "canonical_result_sha256": RESULT_SHA, "contract_sha256": CONTRACT_SHA,
             "readiness_sha256": READINESS_SHA, "source_sha256": SOURCE_SHA,
             "configuration_sha256": CONFIG_SHA, "ledger_event_count": len(events),
             "ledger_events": [e["event"] for e in events], "authorized_s3_assignments_consumed": 1000,
             "new_assignments_generated": False, "policy_or_exit_execution_invoked": False,
             "artifact_hashes": artifact_hashes}
    write_json(out / "reproducibility.json", repro)
    artifact_hashes["reproducibility.json"] = sha(out / "reproducibility.json")
    manifest = {**frozen, "version": "C6_T2_REPORTING_COMPLETION_V1", "attempt_id": ATTEMPT,
                "canonical_result_sha256": RESULT_SHA, "original_attempt_ledger_modified": False,
                "artifact_hashes": dict(sorted(artifact_hashes.items())), "recoverability": recoverability}
    write_json(out / "completion_manifest.json", manifest)


if __name__ == "__main__":
    main()
