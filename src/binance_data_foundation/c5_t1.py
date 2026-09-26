"""C5 T1 mechanical infrastructure.  Historical economic replay is deliberately absent."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

CONTRACT_SHA = "71f431c0f17e4c730c6aa713ce39b164a5c2a3634e333261c236bd92bf6023a3"
ADDENDUM_SHA = "eee71e73d105ff2a48e1832ccc16b27b14a83ac101315639ed3ea1165dbd62ac"
AMENDMENT_SHA = "c50928ab4911a4bf7dd148abad11bd011c0196135a07bca11d41077de92357a2"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
POLICIES = ("P0_HELD_V1", "G1_Q75_EXIT_V1", "P1_Q75_EXIT_V1", "G1_Q90_EXIT_V1", "P1_Q90_EXIT_V1")
COMPARISONS = (("P1_Q75_EXIT_V1", "G1_Q75_EXIT_V1"), ("P1_Q75_EXIT_V1", "P0_HELD_V1"), ("G1_Q75_EXIT_V1", "P0_HELD_V1"), ("P1_Q90_EXIT_V1", "G1_Q90_EXIT_V1"), ("P1_Q90_EXIT_V1", "P0_HELD_V1"), ("G1_Q90_EXIT_V1", "P0_HELD_V1"))
PROBABILITY_COLUMNS = ("p_renewed_peak", "p_substantial_giveback", "p_no_event_60m")
BOOTSTRAP = {"block_length_entry_weeks": 4, "replicates": 2000, "generator": "PCG64", "seed": 20240923, "interval": [0.025, 0.975], "quantile_method": "linear", "unit": "whole_trade"}
REPORT_FIELDS = (
    "gross_return", "entry_fee_quote", "exit_fee_quote", "fee_cost_quote", "entry_slippage_quote",
    "exit_slippage_quote", "slippage_cost_quote", "total_transaction_cost_quote", "net_return",
    "gross_expectancy", "net_expectancy", "fixed_notional_gross_pnl", "fixed_notional_net_pnl",
    "win_rate", "zero_rate", "loss_rate", "downside_deviation", "p05", "p10", "worst_trade",
    "expected_shortfall_10", "mean_holding_time", "median_holding_time", "exit_frequency", "exposure_sum",
    "exposure_union", "common_mfe", "held_mfe", "common_capture_fraction", "held_capture_fraction",
    "common_capture_gap", "held_peak_surrender", "fraction_positive_mfe_surrendered",
    "preserved_at_least_half_peak", "green_to_red", "winner_truncation", "opportunity_foregone",
    "subsequent_plus_2", "subsequent_plus_3", "subsequent_plus_5", "total_trades",
    "t2_eligible_trades", "triggered_exits", "unresolved_exits", "paired_comparison_trades",
)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def semantic_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def verify_governance(repo: Path) -> dict:
    paths = {"contract": repo / "contracts/C5_economic_exit_policy_CONTRACT.md", "addendum": repo / "contracts/C5_economic_exit_policy_ADDENDUM.md", "prediction_population_amendment": repo / "contracts/C5_prediction_population_AMENDMENT.md"}
    expected = {"contract": CONTRACT_SHA, "addendum": ADDENDUM_SHA, "prediction_population_amendment": AMENDMENT_SHA}
    if any(not p.is_file() for p in paths.values()): raise RuntimeError("C5 governance hash mismatch: missing governance document")
    actual = {k: sha256(p) for k, p in paths.items()}
    if actual != expected:
        raise RuntimeError(f"C5 governance hash mismatch: expected={expected}, actual={actual}")
    return actual

UPSTREAM = {
    "c2_entries": ("artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv", "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"),
    "common_horizons_p0": ("artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv", "81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f"),
    "c4_snapshot_schema": ("artifacts/c4_sequential_exit_state/snapshot_schema.json", "ac563f666462e98dc76ec03d242adbf925ecf6091bc67457f0a804571dc4716a"),
    "c4_feature_schema": ("artifacts/c4_sequential_exit_state/feature_schema.json", "ad435c193de8a312816455783b6d55e798095428857e993c0255d408a8bd8325"),
    "c4_preprocessing": ("artifacts/c4_sequential_exit_state/final_preprocessing_2024.json", "36397c9654057e0c1e06c78537ebb9d6911d79be4eb402a1dc3cec8cc0c3bf22"),
    "c4_models": ("artifacts/c4_sequential_exit_state/final_models_2024.json", "aa97e0ccd25fff016f852c2e62be8a05bbda6e8bc919964231731dabe29e21bc"),
    "c4_predictions_2024": ("artifacts/c4_sequential_exit_state/development_predictions_2024.csv", "1c6b80e0cbb17c7a31c686c9688d3200a1d4e78a1d0fe90c8ef5cf4a42129381"),
    "c4_predictions_2025": ("artifacts/c4_sequential_exit_state/locked_2025/predictions.csv", "ad087ebf7469d5682ed20f522967e7b9400d3452e9e60f433bfef6330a7deb2a"),
    "c4_evaluation_manifest": ("artifacts/c4_sequential_exit_state/locked_2025/evaluation_manifest.json", "0b44680fcd411d3377619d5b8345c275064d7c4b81973696282e738e56526b8e"),
    "c4_freeze": ("artifacts/c4_sequential_exit_state/c4_2024_freeze.json", "011c35e91297468e2015442ec2c95079cfdb8cf28bf11a113e2ad6e1ee093fb2"),
}

def provenance_gate(repo: Path, expected: Mapping[str, tuple[str, str]] = UPSTREAM) -> dict:
    governance = verify_governance(repo)
    artifacts = {}
    for name, (relative, frozen) in expected.items():
        path = repo / relative
        if not path.is_file():
            raise RuntimeError(f"missing authoritative upstream artifact: {relative}")
        actual = sha256(path)
        artifacts[name] = {"path": relative, "expected_sha256": frozen, "actual_sha256": actual, "matched": actual == frozen}
        if actual != frozen:
            raise RuntimeError(f"upstream provenance mismatch: {name}")
    freeze = json.loads((repo / UPSTREAM["c4_freeze"][0]).read_text())
    for name in ("snapshot_schema.json", "feature_schema.json", "final_preprocessing_2024.json", "final_models_2024.json", "development_predictions_2024.csv"):
        if freeze["material_artifact_hashes"].get(name) != sha256(repo / "artifacts/c4_sequential_exit_state" / name):
            raise RuntimeError(f"C4 freeze reconciliation mismatch: {name}")
    evaluation = json.loads((repo / UPSTREAM["c4_evaluation_manifest"][0]).read_text())
    if evaluation.get("freeze_sha256") != UPSTREAM["c4_freeze"][1]:
        raise RuntimeError("locked evaluation does not reference accepted C4 freeze")
    return {"status": "PASS", "governance": governance, "artifacts": artifacts, "sealed_paths_enumerated": False}

def _finite_probabilities(row: Mapping[str, object]) -> bool:
    try:
        p = [float(row[c]) for c in PROBABILITY_COLUMNS]
    except (KeyError, TypeError, ValueError):
        return False
    return all(math.isfinite(x) and 0 <= x <= 1 for x in p) and math.isclose(sum(p), 1.0, rel_tol=0, abs_tol=1e-9)

def prediction_coverage(expected_rows: Sequence[Mapping[str, object]], prediction_rows: Sequence[Mapping[str, object]]) -> dict:
    """Validate exact G1/P1 coverage. Expected metadata is outcome/path free."""
    expected = {str(r["row_id"]): r for r in expected_rows}
    if len(expected) != len(expected_rows):
        raise RuntimeError("duplicate eligible snapshot row_id")
    relevant = [r for r in prediction_rows if r.get("model") in ("G1", "P1") and (r.get("target") == "T2" or str(r.get("row_id")) in expected)]
    keys = [(str(r.get("row_id")), str(r.get("model"))) for r in relevant]
    duplicates = sum(v - 1 for v in Counter(keys).values() if v > 1)
    pred = {k: r for k, r in zip(keys, relevant)}
    missing = [(rid, m) for rid in expected for m in ("G1", "P1") if (rid, m) not in pred]
    extra = [k for k in pred if k[0] not in expected]
    mismatch = Counter()
    invalid_probabilities = 0
    for (rid, _model), row in pred.items():
        if rid not in expected:
            continue
        e = expected[rid]
        for key in ("trade_id", "symbol", "snapshot_ms"):
            if key in row and str(row[key]) != str(e[key]):
                mismatch[key] += 1
        if row.get("target") != "T2":
            mismatch["target"] += 1
        if not _finite_probabilities(row):
            invalid_probabilities += 1
    def grouped(field):
        groups=defaultdict(list)
        for r in expected_rows:
            key=str(r["symbol"]) if field=="symbol" else datetime.fromtimestamp(int(r["snapshot_ms"])/1000,timezone.utc).strftime("%Y")
            groups[key].append(str(r["row_id"]))
        return {k:{"eligible_snapshots":len(ids),**{f"{m}_matched":sum((rid,m) in pred for rid in ids) for m in ("G1","P1")},**{f"{m}_missing":sum((rid,m) not in pred for rid in ids) for m in ("G1","P1")}} for k,ids in sorted(groups.items())}
    counts = {"pooled":{"eligible_snapshots":len(expected),"G1_matched":sum((rid,"G1") in pred for rid in expected),"P1_matched":sum((rid,"P1") in pred for rid in expected),"G1_missing":sum((rid,"G1") not in pred for rid in expected),"P1_missing":sum((rid,"P1") not in pred for rid in expected)}, "symbol":grouped("symbol"), "calendar_year":grouped("year")}
    ok = not (duplicates or missing or extra or mismatch or invalid_probabilities)
    return {"status": "PASS" if ok else "FAIL", "eligible_snapshots": counts, "required_prediction_rows": 2 * len(expected), "matched_prediction_rows": 2 * len(expected)-len(missing), "missing_predictions": len(missing), "duplicate_predictions": duplicates, "extra_predictions": len(extra), "mismatches": dict(mismatch), "invalid_probability_rows": invalid_probabilities, "one_to_one": ok}

def state_score(row: Mapping[str, object]) -> float:
    if not _finite_probabilities(row):
        raise ValueError("incomplete, nonfinite, out-of-range, or non-normalized class probabilities")
    return float(row["p_substantial_giveback"]) - float(row["p_renewed_peak"])

def freeze_thresholds(rows: Sequence[Mapping[str, object]]) -> dict:
    output = {}
    for model in ("G1", "P1"):
        selected = sorted((r for r in rows if r.get("target") == "T2" and r.get("model") == model), key=lambda r: str(r["row_id"]))
        ids = [str(r["row_id"]) for r in selected]
        if len(ids) != len(set(ids)) or not ids:
            raise RuntimeError(f"{model} cutoff rows missing or duplicated")
        scores = [state_score(r) for r in selected]
        output[model] = {"source_row_count": len(ids), "row_set_sha256": semantic_hash(ids), "score_vector_sha256": semantic_hash(scores), "method": "Type-7 linear", "global_not_symbol_specific": True, "Q75": float(np.quantile(scores, .75, method="linear")), "Q90": float(np.quantile(scores, .90, method="linear"))}
        output[model]["cutoff_sha256"] = semantic_hash({"Q75": output[model]["Q75"], "Q90": output[model]["Q90"]})
    return output

def t2_active(entry_price: float, running_peak: float, current_price: float, frozen_eligible: bool, completed_5m: bool = True) -> bool:
    peak_gain = running_peak / entry_price - 1
    barrier = (entry_price + running_peak) / 2
    return bool(frozen_eligible and completed_5m and peak_gain >= .01 and current_price / entry_price - 1 > 0 and current_price > barrier)

@dataclass(frozen=True)
class Snapshot:
    row_id: str; timestamp: datetime; score: float; active: bool = True; completed_5m: bool = True

@dataclass(frozen=True)
class Exit:
    decision_ts: datetime | None; execution_ts: datetime; raw_exit_price: float; reason: str; trigger_row_id: str | None; executable: bool; censor_reason: str | None = None

def replay_synthetic(snapshots: Sequence[Snapshot], cutoff: float, minute_opens: Mapping[datetime, Sequence[float]], horizon: datetime, p0_ts: datetime, p0_price: float) -> Exit:
    """Causal single-trade mechanism; callers cannot supply outcomes or future metrics."""
    for s in sorted(snapshots, key=lambda x: x.timestamp):
        if s.timestamp >= horizon or not (s.active and s.completed_5m and s.timestamp.minute % 5 == 0) or s.score < cutoff:
            continue
        execution = s.timestamp
        if execution >= p0_ts:
            break
        values = minute_opens.get(execution)
        if values is None:
            return Exit(s.timestamp, execution, math.nan, "POLICY", s.row_id, False, "missing_immediate_next_1m_open")
        if len(values) != 1 or not math.isfinite(float(values[0])) or float(values[0]) <= 0:
            return Exit(s.timestamp, execution, math.nan, "POLICY", s.row_id, False, "invalid_or_duplicate_immediate_next_1m_open")
        return Exit(s.timestamp, execution, float(values[0]), "POLICY", s.row_id, True)
    return Exit(None, p0_ts, p0_price, "P0_FALLBACK", None, True)

@dataclass(frozen=True)
class CostCase:
    fee_rate: float; slippage_rate: float; approximate_round_trip_bp: int

COSTS = {"C0": CostCase(0, 0, 0), "C_BASE": CostCase(.001, .0002, 24), "C_S5": CostCase(.001, .0005, 30), "C_S10": CostCase(.001, .001, 40)}

def cost_ledger(raw_entry: float, raw_exits: Sequence[tuple[float, float]], case: CostCase, quantity: float) -> dict:
    """Each (raw price, quantity) exit is independently charged."""
    entry_price = raw_entry * (1 + case.slippage_rate); entry_notional = entry_price * quantity
    exits = []
    for raw, qty in raw_exits:
        price = raw * (1 - case.slippage_rate); notional = price * qty
        exits.append({"raw_price": raw, "quantity": qty, "executed_price": price, "executed_notional": notional, "fee_quote": notional * case.fee_rate, "slippage_quote": raw * qty - notional})
    entry_fee = entry_notional * case.fee_rate
    entry_slippage = entry_notional - raw_entry * quantity
    proceeds = sum(x["executed_notional"] - x["fee_quote"] for x in exits)
    net_cash = proceeds - entry_notional - entry_fee
    gross_cash = sum(x["executed_notional"] for x in exits) - entry_notional
    return {"entry_executed_notional": entry_notional, "entry_fee_quote": entry_fee, "entry_slippage_quote": entry_slippage, "exit_transactions": exits, "exit_fee_quote": sum(x["fee_quote"] for x in exits), "exit_slippage_quote": sum(x["slippage_quote"] for x in exits), "slippage_cost_quote": entry_slippage + sum(x["slippage_quote"] for x in exits), "total_transaction_cost_quote": entry_fee + sum(x["fee_quote"] + x["slippage_quote"] for x in exits) + entry_slippage, "gross_return": gross_cash / entry_notional, "net_return": net_cash / entry_notional, "fixed_replay_legs": 1 + len(exits)}

def metric_row_schema() -> dict:
    return {scope: list(REPORT_FIELDS) for scope in ("pooled_trade_weighted", "pooled_equal_weight_symbol", *SYMBOLS)}

def compute_metric_summary(rows: Sequence[Mapping[str, object]], fixed_notional: float = 1000.0) -> dict:
    """Aggregate synthetic or later-authorized canonical trade rows; no file access."""
    if not rows: return {k: None for k in REPORT_FIELDS}
    def vals(key): return np.asarray([float(r[key]) for r in rows if r.get(key) is not None],float)
    gross,net=vals("gross_return"),vals("net_return"); losses=net[net<0]; q10=float(np.quantile(net,.10,method="linear"))
    es=net[net<=q10]
    out={"gross_return":float(np.mean(gross)),"net_return":float(np.mean(net)),"gross_expectancy":float(np.mean(gross)),"net_expectancy":float(np.mean(net)),"fixed_notional_gross_pnl":float(np.sum(gross)*fixed_notional),"fixed_notional_net_pnl":float(np.sum(net)*fixed_notional),"win_rate":float(np.mean(net>0)),"zero_rate":float(np.mean(net==0)),"loss_rate":float(np.mean(net<0)),"downside_deviation":float(np.sqrt(np.mean(np.minimum(net,0)**2))),"p05":float(np.quantile(net,.05,method="linear")),"p10":q10,"worst_trade":float(np.min(net)),"expected_shortfall_10":float(np.mean(es)),"total_trades":len(rows),"t2_eligible_trades":len({r["trade_id"] for r in rows if r.get("t2_eligible")}),"triggered_exits":sum(bool(r.get("triggered")) for r in rows)}
    for key in ("entry_fee_quote","exit_fee_quote","entry_slippage_quote","exit_slippage_quote","slippage_cost_quote","total_transaction_cost_quote"):
        out[key]=float(np.sum(vals(key))) if len(vals(key)) else 0.0
    out["fee_cost_quote"]=out["entry_fee_quote"]+out["exit_fee_quote"]
    for key in REPORT_FIELDS:
        if key not in out:
            x=vals(key); out[key]=float(np.mean(x)) if len(x) else None
    return out

def support_classification(eligible_trades: int) -> str:
    return "SUFFICIENT" if eligible_trades >= 50 else "INSUFFICIENT SUPPORT"

def concentration(contributions_p0: Mapping[str, float], contributions_g1: Mapping[str, float], eligible: Mapping[str, int], intervals_g1: Mapping[str, tuple[float, float] | None], pooled_supports: bool) -> dict:
    p0 = {s: float(contributions_p0.get(s, 0)) for s in SYMBOLS}; g1 = {s: float(contributions_g1.get(s, 0)) for s in SYMBOLS}
    positive_total = sum(max(x, 0) for x in p0.values())
    shares = {s: (max(v, 0) / positive_total if positive_total > 0 else None) for s, v in p0.items()}
    favorable_p0 = [s for s in SYMBOLS if eligible.get(s, 0) >= 50 and p0[s] > 0]
    favorable_g1 = [s for s in SYMBOLS if eligible.get(s, 0) >= 50 and g1[s] > 0]
    adverse = [s for s in SYMBOLS if eligible.get(s, 0) >= 50 and intervals_g1.get(s) is not None and intervals_g1[s][1] < 0]
    largest = max((x for x in shares.values() if x is not None), default=None)
    broad = pooled_supports and positive_total > 0 and len(favorable_p0) >= 4 and len(favorable_g1) >= 4 and not adverse and largest <= .5
    label = "BROAD / MULTI-SYMBOL ECONOMIC VALUE" if broad else "CONCENTRATED ECONOMIC VALUE" if pooled_supports else "NOT CLASSIFIED"
    return {"classification": label, "signed_p1_minus_p0": p0, "signed_p1_minus_g1": g1, "positive_only_shares": shares, "total_negative_contribution_magnitude": sum(max(-x, 0) for x in p0.values()), "largest_symbol_positive_share": largest, "favorable_symbols_p0": favorable_p0, "favorable_symbols_g1": favorable_g1, "unfavorable_symbols_p0": [s for s,v in p0.items() if v < 0], "unfavorable_symbols_g1": [s for s,v in g1.items() if v < 0], "adverse_interval_symbols": adverse, "signed_total_p0": sum(p0.values()), "signed_total_g1": sum(g1.values())}

def moving_block_bootstrap(values: Mapping[str, float], entry_weeks: Mapping[str, str], config: Mapping[str, int] = BOOTSTRAP) -> dict:
    trades = sorted(values)
    if set(trades) != set(entry_weeks): raise ValueError("paired values and entry weeks differ")
    weeks = [datetime.fromisoformat(entry_weeks[t]).date() for t in trades]
    lo, hi = min(weeks), max(weeks); lo -= timedelta(days=lo.weekday()); hi -= timedelta(days=hi.weekday())
    span = (hi-lo).days//7+1
    if span < 4: return {"available": False, "reason": "span_shorter_than_four_entry_weeks"}
    at = defaultdict(list)
    for t in trades: at[(datetime.fromisoformat(entry_weeks[t]).date()-lo).days//7].append(t)
    blocks = [list(range(i, i+4)) for i in range(span-3)]
    if sum(any(at[j] for j in b) for b in blocks) < 2: return {"available": False, "reason": "fewer_than_two_nonempty_candidate_blocks"}
    rng=np.random.Generator(np.random.PCG64(int(config["seed"]))); reps=[]; samples=[]
    for _ in range(int(config["replicates"])):
        positions=[]; picked=[]
        while len(positions)<span:
            i=int(rng.integers(len(blocks))); picked.append(i); positions.extend(blocks[i])
        selected=[t for j in positions[:span] for t in at[j]]
        if not selected: raise RuntimeError("empty bootstrap replicate")
        reps.append(float(np.mean([values[t] for t in selected]))); samples.append(picked)
    return {"available": True, "point_estimate": float(np.mean(list(values.values()))), "ci95": np.quantile(reps,[.025,.975],method="linear").tolist(), "replicates": reps, "sampled_block_indices": samples, "multiplicity_preserved": True}

def symbol_strength(eligible: int, path_delta: float | None, path_ci: tuple[float,float] | None, practical_delta: float | None) -> str:
    if eligible < 50 or path_delta is None or path_ci is None: return "INSUFFICIENT SUPPORT"
    if practical_delta is None or path_delta == 0 or practical_delta == 0 or (path_delta > 0) != (practical_delta > 0): return "MIXED"
    if path_delta > 0 and path_ci[0] > 0 and practical_delta is not None and practical_delta > 0: return "STRONG SUPPORT"
    if path_delta > 0 and path_ci[0] <= 0 <= path_ci[1]: return "DIRECTIONAL SUPPORT"
    if path_delta < 0 and path_ci[1] < 0: return "COUNTS AGAINST"
    return "MIXED"

def deployment_label(eligible: int, path_delta: float | None, practical_delta: float | None, path_ci: tuple[float,float] | None, practical_ci: tuple[float,float] | None, safety_breach: bool, safety_available: bool) -> str:
    if eligible < 50 or path_delta is None or practical_delta is None: return "INSUFFICIENT SUPPORT"
    if safety_breach or (path_ci and path_ci[1] < 0) or (practical_ci and practical_ci[1] < 0): return "NOT SUPPORTED"
    if path_delta > 0 and practical_delta > 0 and safety_available: return "SUITABLE FOR FURTHER VALIDATION"
    return "MIXED / HOLD"

def overall_classification(valid: bool, path_delta: float | None, practical_delta: float | None, path_ci: tuple[float,float] | None, practical_ci: tuple[float,float] | None, safety_breach: bool, safety_available: bool, c_s5_survives: bool, breadth: str) -> str:
    if not valid or None in (path_delta, practical_delta, path_ci, practical_ci): return "INSUFFICIENT EVIDENCE"
    if safety_breach or path_ci[1] < 0 or practical_ci[1] < 0 or not c_s5_survives: return "COUNTS AGAINST"
    if path_delta > 0 and practical_delta > 0 and path_ci[0] > 0 and safety_available:
        return "SUPPORTS BROAD ECONOMIC EXIT VALUE" if breadth.startswith("BROAD") else "SUPPORTS BUT CONCENTRATED"
    return "MIXED"

def q90_can_advance(q75_label: str, q90_label: str) -> bool:
    return q75_label in ("SUPPORTS BROAD ECONOMIC EXIT VALUE", "SUPPORTS BUT CONCENTRATED")

def _prediction_rows(path: Path, metadata: Mapping[str, Mapping[str, object]]) -> list[dict]:
    out=[]
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("target") != "T2" or row.get("model") not in ("G1", "P1"): continue
            item={k:row.get(k) for k in ("row_id","trade_id","target","model",*PROBABILITY_COLUMNS)}
            item.update({k:v for k,v in metadata.get(row["row_id"],{}).items() if k in ("symbol","snapshot_ms")})
            out.append(item)
    return out

def audit_repository_coverage(repo: Path) -> tuple[dict, list[dict]]:
    expected_by_id={}; metadata={}
    with (repo/"artifacts/c4_sequential_exit_state/local/t2_snapshots.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["target_eligible"] == "True":
                item={k:row[k] for k in ("row_id","trade_id","symbol","snapshot_ms")}; expected_by_id[item["row_id"]]=item; metadata[item["row_id"]]=item
    locked=json.loads((repo/"artifacts/c4_sequential_exit_state/locked_2025_input.json").read_text())
    for row in locked:
        if row.get("target") == "T2" and row.get("target_eligible") is True:
            item={k:row[k] for k in ("row_id","trade_id","symbol","snapshot_ms")}
            if item["row_id"] in expected_by_id and any(str(expected_by_id[item["row_id"]][k]) != str(item[k]) for k in ("trade_id","symbol","snapshot_ms")):
                raise RuntimeError("eligible snapshot metadata differs across accepted C4 artifacts")
            expected_by_id[item["row_id"]]=item; metadata[item["row_id"]]=item
    predictions=_prediction_rows(repo/UPSTREAM["c4_predictions_2024"][0],metadata)+_prediction_rows(repo/UPSTREAM["c4_predictions_2025"][0],metadata)
    return prediction_coverage(list(expected_by_id.values()),predictions), predictions

def _raw_t2_metadata(repo: Path) -> list[dict]:
    rows=[]
    with (repo/"artifacts/c4_sequential_exit_state/local/t2_snapshots.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["target_eligible"] != "True" or row["snapshot_ts"][:4] not in ("2024","2025"): continue
            rows.append({"row_id":row["row_id"],"trade_id":row["trade_id"],"symbol":row["symbol"],"snapshot_ms":int(row["snapshot_ms"]),"entry_execution_ms":int(row["entry_execution_ms"]),"year":row["snapshot_ts"][:4],"resolved":row["resolved"]=="True","censored":row["censored"]=="True","ambiguous":row["ambiguous"]=="True"})
    if len({r["row_id"] for r in rows}) != len(rows): raise RuntimeError("duplicate raw T2 eligible row identity")
    return rows

def _prediction_file_rows(path: Path, year: str, metadata: Mapping[str, Mapping[str, object]]) -> tuple[list[dict], dict[str,set[str]]]:
    rows=[]; folds=defaultdict(set)
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("target") != "T2" or row.get("model") not in ("G1","P1"): continue
            item={k:row.get(k) for k in ("row_id","trade_id","target","model",*PROBABILITY_COLUMNS)}
            item.update({k:v for k,v in metadata.get(row["row_id"],{}).items() if k in ("symbol","snapshot_ms")});item["year"]=year;rows.append(item)
            if year=="2024": folds[row.get("fold","")].add(row["row_id"])
    return rows,dict(folds)

def _layer_counts(row_ids: set[str], metadata: Mapping[str, Mapping[str,object]]) -> dict:
    def one(ids): return {"snapshots":len(ids),"trades":len({str(metadata[x]["trade_id"]) for x in ids})}
    by_year={y:one({x for x in row_ids if metadata[x]["year"]==y}) for y in ("2024","2025")}
    by_symbol={s:one({x for x in row_ids if metadata[x]["symbol"]==s}) for s in SYMBOLS}
    by_year_symbol={y:{s:one({x for x in row_ids if metadata[x]["year"]==y and metadata[x]["symbol"]==s}) for s in SYMBOLS} for y in ("2024","2025")}
    return {"pooled":one(row_ids),"by_year":by_year,"by_symbol":by_symbol,"by_year_symbol":by_year_symbol}

def whole_path_authorization(raw_row_ids: Sequence[str], g1_row_ids: set[str], p1_row_ids: set[str]) -> dict:
    """Classify one ordered trade path; unavailable predictions can never mean no action."""
    raw=list(raw_row_ids)
    if len(raw)!=len(set(raw)): raise ValueError("duplicate raw path identity")
    if g1_row_ids != p1_row_ids: raise RuntimeError("G1/P1 path identity mismatch")
    present=[x in g1_row_ids for x in raw]
    if all(present): return {"authorized":True,"path_pattern":"complete","reasons":[]}
    indices=[i for i,x in enumerate(present) if x]
    if not indices:return {"authorized":False,"path_pattern":"wholly_unpredicted","reasons":["wholly_unpredicted"]}
    reasons=[]
    if any(not present[i] for i in range(min(indices))):reasons.append("left_truncated")
    if any(not present[i] for i in range(min(indices),max(indices)+1)):reasons.append("internally_gapped")
    if any(not present[i] for i in range(max(indices)+1,len(raw))):reasons.append("right_truncated")
    return {"authorized":False,"path_pattern":"+".join(reasons),"reasons":reasons}

def replay_population_gate(repo: Path) -> dict:
    """Amendment coverage gate. Reads identity/availability metadata only."""
    raw=_raw_t2_metadata(repo); meta={r["row_id"]:r for r in raw}; raw_ids=set(meta)
    model_pop=json.loads((repo/"artifacts/c4_sequential_exit_state/modeling_population_2024.json").read_text())["T2"]
    complete24=set(model_pop["row_ids"])
    locked=json.loads((repo/"artifacts/c4_sequential_exit_state/locked_2025_input.json").read_text())
    complete25={r["row_id"] for r in locked if r.get("target")=="T2" and r.get("target_eligible") is True}
    if not complete24|complete25 <= raw_ids: raise RuntimeError("complete-case rows outside raw eligible population")
    p24,f24=_prediction_file_rows(repo/UPSTREAM["c4_predictions_2024"][0],"2024",meta)
    p25,_=_prediction_file_rows(repo/UPSTREAM["c4_predictions_2025"][0],"2025",meta)
    predictions=p24+p25
    sets={(y,m):{r["row_id"] for r in predictions if r["year"]==y and r["model"]==m} for y in ("2024","2025") for m in ("G1","P1")}
    if any(sets[(y,"G1")] != sets[(y,"P1")] for y in ("2024","2025")): raise RuntimeError("G1/P1 authorized identity mismatch")
    authorized=sets[("2024","G1")]|sets[("2025","G1")]
    if set(f24)!={"fold_A","fold_B"} or len(f24["fold_A"])!=16166 or len(f24["fold_B"])!=14301 or f24["fold_A"]&f24["fold_B"] or f24["fold_A"]|f24["fold_B"] != sets[("2024","G1")]:
        raise RuntimeError("2024 frozen OOF validation population mismatch")
    if sets[("2025","G1")] != complete25: raise RuntimeError("2025 locked prediction population mismatch")
    coverage=prediction_coverage([meta[x] for x in authorized],predictions)
    if coverage["status"]!="PASS": raise RuntimeError("authorized frozen prediction coverage mismatch")
    paths=defaultdict(list)
    for row in raw: paths[(row["year"],row["trade_id"])].append(row)
    replay=set(); excluded=[]
    complete_ids=complete24|complete25
    for (year,trade),seq in sorted(paths.items()):
        seq.sort(key=lambda r:(r["snapshot_ms"],r["row_id"])); ids={r["row_id"] for r in seq}
        classified=whole_path_authorization([r["row_id"] for r in seq],sets[(year,"G1")],sets[(year,"P1")]);reasons=list(classified["reasons"]);pattern=classified["path_pattern"]
        if classified["authorized"]: replay.update(ids); continue
        present=[r["row_id"] in authorized for r in seq]
        missing=[r for r in seq if r["row_id"] not in authorized]
        if year=="2024" and any(r["entry_execution_ms"]<1719792000000 and r["row_id"] in complete24 for r in seq): reasons.append("non_OOF_2024_training_population")
        if any(r["resolved"] and not r["censored"] and not r["ambiguous"] and r["row_id"] not in complete_ids for r in missing): reasons.append("feature_incomplete")
        if any(r["censored"] or not r["resolved"] or r["ambiguous"] for r in missing): reasons.append("censored_or_unresolved_prevents_full_path")
        excluded.append({"year":year,"trade_id":trade,"symbol":seq[0]["symbol"],"path_pattern":pattern,"reasons":sorted(set(reasons)),"raw_eligible_snapshots":len(seq),"covered_snapshots":sum(present)})
    # Exact row equality, not merely counts, is the final whole-path assertion.
    replay_trades={(meta[x]["year"],meta[x]["trade_id"]) for x in replay}
    for key in replay_trades:
        ids={r["row_id"] for r in paths[key]}
        if ids != ids&sets[(key[0],"G1")] or ids != ids&sets[(key[0],"P1")]: raise RuntimeError("incomplete prediction inside replay-authorized trade")
    layers={"raw_T2_eligible":_layer_counts(raw_ids,meta),"complete_case_model_eligible":_layer_counts(complete24|complete25,meta),"authorized_frozen_prediction":_layer_counts(authorized,meta),"replay_authorized_complete_path":_layer_counts(replay,meta)}
    def exclusions(year=None,symbol=None):
        selected=[x for x in excluded if (year is None or x["year"]==year) and (symbol is None or x["symbol"]==symbol)]
        return {"excluded_trades":len(selected),"path_patterns":dict(sorted(Counter(x["path_pattern"] for x in selected).items())),"reason_flags":dict(sorted(Counter(r for x in selected for r in x["reasons"]).items()))}
    exclusion_summary={"pooled":exclusions(),"by_year":{y:exclusions(year=y) for y in ("2024","2025")},"by_symbol":{s:exclusions(symbol=s) for s in SYMBOLS},"by_year_symbol":{y:{s:exclusions(year=y,symbol=s) for s in SYMBOLS} for y in ("2024","2025")}}
    support={s:{"replay_authorized_complete_path_trades":layers["replay_authorized_complete_path"]["by_symbol"][s]["trades"],"classification":"SUFFICIENT SUPPORT FOR C5 SYMBOL-LEVEL INTERPRETATION" if layers["replay_authorized_complete_path"]["by_symbol"][s]["trades"]>=50 else "INSUFFICIENT SUPPORT"} for s in SYMBOLS}
    return {"status":"PASS","whole_path_construction":"PASS","analyst_override":False,"no_action_substitution":False,"in_sample_2024_backfill":False,"year_role":{"2024":"OOF_VALIDATION_ONLY","2025":"LOCKED_FINAL_C4_MODEL","split_role":"DIAGNOSTIC_ONLY_NO_POLICY_SELECTION_OR_TUNING"},"layers":layers,"exclusions":exclusion_summary,"support":support,"authorized_coverage":coverage}

def build_readiness(repo: Path, tests: Mapping[str, object]) -> dict:
    provenance=provenance_gate(repo); population=replay_population_gate(repo)
    thresholds=freeze_thresholds(_prediction_rows(repo/UPSTREAM["c4_predictions_2024"][0],{}))
    blockers=[]
    if population["status"] != "PASS": blockers.append("replay-authorized prediction population failed")
    ready=not blockers and tests.get("status") == "PASS"
    return {"version":"C5_T1_READINESS_V2_COMPLETE_PATH","contract_sha256":CONTRACT_SHA,"addendum_sha256":ADDENDUM_SHA,"prediction_population_amendment_sha256":AMENDMENT_SHA,"upstream_hashes":provenance["artifacts"],"provenance_gate_status":provenance["status"],"prediction_population":population,"prediction_coverage_status":population["status"],"four_population_layers":population["layers"],"complete_path_exclusions":population["exclusions"],"symbol_support":population["support"],"policy_definitions":{"variants":list(POLICIES),"score":"P(substantial_giveback)-P(renewed_peak)","thresholds":thresholds,"Q75_role":"PRIMARY","Q90_role":"SENSITIVITY_ONLY_CANNOT_RESCUE_Q75","threshold_search":False,"symbol_specific_thresholds":False},"activation":{"running_peak_gain_min_inclusive":.01,"current_return_strictly_positive":True,"strictly_above_half_giveback_barrier":True,"frozen_T2_eligible":True,"completed_5m_only":True,"decision":"snapshot_t","execution":"immediate_1m_open_at_t","gap_skipping":False},"cost_definitions":{k:asdict(v) for k,v in COSTS.items()},"bootstrap_definition":BOOTSTRAP,"comparisons":[list(x) for x in COMPARISONS],"report_schema":metric_row_schema(),"support_rule":{"minimum_replay_authorized_complete_path_trades":50,"period":"POOLED_2024_2025","year_split":"DIAGNOSTIC_ONLY"},"breadth_rule":{"favorable_symbols_required":4,"largest_positive_share_max_inclusive":.5,"unchanged":True},"classification_rules":{"strength":["STRONG SUPPORT","DIRECTIONAL SUPPORT","COUNTS AGAINST","MIXED","INSUFFICIENT SUPPORT"],"suitability":["SUITABLE FOR FURTHER VALIDATION","MIXED / HOLD","NOT SUPPORTED","INSUFFICIENT SUPPORT"],"overall":["SUPPORTS BROAD ECONOMIC EXIT VALUE","SUPPORTS BUT CONCENTRATED","MIXED","COUNTS AGAINST","INSUFFICIENT EVIDENCE"]},"test_results":dict(tests),"economic_replay_performed":False,"real_PnL_calculated":False,"real_returns_calculated":False,"MFE_or_winner_truncation_calculated":False,"new_predictions_generated":False,"in_sample_2024_backfill":False,"sealed_confirmation_access":False,"T2_ready":ready,"blockers":blockers}
