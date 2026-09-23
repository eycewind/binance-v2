from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .c2_candidate_policies import (
    P1_VERSION, P2_VERSION, P3_VERSION, CandidateDecision, decide_p1, decide_p2, decide_p3,
)
from .c2_common import ENTRY_COLUMNS, hash_rows, iso, iter_gzip_csv, research_partitions, valid_minute, write_json
from .c2_costs import COST_SCENARIOS, apply_round_trip_costs
from .c2_p0 import EXPECTED_FROZEN_ENTRY_HASH, HORIZON_COLUMNS, _complete_path
from .c2_path_metrics import evaluate_path
from .ingest import sha256_file


EXPECTED_COMMON_HORIZON_HASH = "81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f"
RUN_ID = "C2A_P0_P1_P2_P3_V1"
BOOTSTRAP_SEED = 20260923
BOOTSTRAP_REPLICATIONS = 2000
POLICIES = (P1_VERSION, P2_VERSION, P3_VERSION)
THRESHOLDS = (("0_5pct", 0.005), ("1pct", 0.01), ("2pct", 0.02), ("3pct", 0.03))
EXTRA_COLUMNS = (
    "holding_duration_seconds",
    "policy_activated_ms", "activation_to_exit_seconds", "gap_through", "negative_sequence_count",
    "p0_raw_return", "raw_return_delta_vs_p0", "net_return_delta_vs_p0",
    "held_surrender_delta_vs_p0", "common_capture_gap_delta_vs_p0", "holding_duration_delta_vs_p0",
    "held_green_then_red_change", "common_positive_exit_red_change", "candidate_better_than_p0",
    "candidate_worse_than_p0", "candidate_equal_to_p0", "rescued", "damaged",
    "exited_before_p0", "foregone_subsequent_gain", "premature_appreciation_0_5pct",
)


def build_candidate_checkpoint(normalized_dir: Path, aggregate_dir: Path, artifact_dir: Path) -> dict:
    entries_path = artifact_dir / "frozen_entries.csv"
    horizons_path = artifact_dir / "common_horizons_p0.csv"
    entries = list(csv.DictReader(entries_path.open(encoding="utf-8", newline="")))
    horizons = list(csv.DictReader(horizons_path.open(encoding="utf-8", newline="")))
    if hash_rows(entries, ENTRY_COLUMNS) != EXPECTED_FROZEN_ENTRY_HASH:
        raise ValueError("frozen-entry semantic hash mismatch")
    if hash_rows(horizons, HORIZON_COLUMNS) != EXPECTED_COMMON_HORIZON_HASH:
        raise ValueError("common-horizon semantic hash mismatch")
    entry_by_id = {row["trade_id"]: row for row in entries}
    horizon_by_id = {row["trade_id"]: row for row in horizons}
    if entry_by_id.keys() != horizon_by_id.keys():
        raise ValueError("frozen entries and common horizons are not paired")
    p0_rows = list(csv.DictReader((artifact_dir / "p0_trade_records.csv").open(encoding="utf-8", newline="")))
    p0_by_key = {(row["trade_id"], row["cost_scenario"]): row for row in p0_rows}
    p0_columns = tuple(p0_rows[0])
    candidate_rows: list[dict] = []
    decisions: list[tuple[dict, dict, CandidateDecision]] = []
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        by_symbol[entry["symbol"]].append(entry)
    for symbol in sorted(by_symbol):
        minute_lookup = {int(row["open_time_ms"]): row for row in iter_gzip_csv(normalized_dir / f"{symbol}_1m.csv.gz") if valid_minute(row)}
        bars5 = {int(row["open_time_ms"]): row for row in iter_gzip_csv(aggregate_dir / f"{symbol}_5m.csv.gz")}
        for entry in by_symbol[symbol]:
            horizon = horizon_by_id[entry["trade_id"]]
            if str(horizon["censored"]).lower() == "true":
                for policy in POLICIES:
                    decision = CandidateDecision(policy, None, None, None, None, None, True, "paired_common_horizon_censored")
                    decisions.append((entry, horizon, decision))
                    candidate_rows.extend(_censored_records(entry, horizon, decision, p0_columns))
                continue
            entry_ms, entry_price = int(entry["entry_execution_ms"]), float(entry["entry_price"])
            horizon_ms, horizon_price = int(horizon["common_horizon_end_ms"]), float(horizon["p0_raw_exit_price"])
            policy_decisions = (
                decide_p1(entry_ms, entry_price, horizon_ms, horizon_price, minute_lookup),
                decide_p2(entry_ms, entry_price, horizon_ms, horizon_price, bars5, minute_lookup),
                decide_p3(entry_ms, horizon_ms, horizon_price, bars5, minute_lookup),
            )
            common_rows, missing = _complete_path(entry_ms, horizon_ms, minute_lookup)
            if missing is not None:
                raise ValueError(f"accepted common horizon has path gap at {missing}")
            for decision in policy_decisions:
                decisions.append((entry, horizon, decision))
                if decision.censored or decision.execution_ms is None or decision.exit_price is None:
                    candidate_rows.extend(_censored_records(entry, horizon, decision, p0_columns))
                    continue
                held_rows, held_missing = _complete_path(entry_ms, decision.execution_ms, minute_lookup)
                if held_missing is not None:
                    failed = CandidateDecision(decision.policy_version, decision.signal_ms, decision.decision_ms, None, None,
                                               None, True, f"held_path_gap_at_{held_missing}")
                    candidate_rows.extend(_censored_records(entry, horizon, failed, p0_columns))
                    continue
                metrics = evaluate_path(
                    entry_ms=entry_ms, entry_price=entry_price, exit_ms=decision.execution_ms,
                    exit_price=decision.exit_price, minute_rows=held_rows,
                    common_exit_ms=horizon_ms, common_exit_price=horizon_price, common_minute_rows=common_rows,
                )
                _assert_common_metrics(metrics, horizon)
                foregone = _foregone_gain(decision.execution_ms, decision.exit_price, horizon_ms, horizon_price, common_rows)
                for scenario in COST_SCENARIOS:
                    costs = apply_round_trip_costs(entry_price, decision.exit_price, float(entry["entry_notional_usdt"]), scenario)
                    p0 = p0_by_key[(entry["trade_id"], scenario.scenario_id)]
                    candidate_rows.append(_candidate_record(entry, horizon, decision, metrics, costs, p0, foregone))
    trade_columns = p0_columns + tuple(column for column in EXTRA_COLUMNS if column not in p0_columns)
    normalized_p0 = []
    for original in p0_rows:
        row = dict(original); horizon = horizon_by_id[row["trade_id"]]
        row.update({"holding_duration_seconds": horizon["common_horizon_duration_seconds"],
                    "p0_raw_return": row["raw_price_return"], "raw_return_delta_vs_p0": 0.0,
                    "net_return_delta_vs_p0": 0.0, "held_surrender_delta_vs_p0": 0.0,
                    "common_capture_gap_delta_vs_p0": 0.0, "holding_duration_delta_vs_p0": 0,
                    "held_green_then_red_change": 0, "common_positive_exit_red_change": 0,
                    "candidate_better_than_p0": False, "candidate_worse_than_p0": False,
                    "candidate_equal_to_p0": True, "rescued": False, "damaged": False,
                    "exited_before_p0": False, "foregone_subsequent_gain": 0.0,
                    "premature_appreciation_0_5pct": False})
        normalized_p0.append(row)
    combined = [{column: row.get(column, "") for column in trade_columns} for row in normalized_p0 + candidate_rows]
    combined.sort(key=lambda row: (int(row["entry_execution_ms"]), row["symbol"], row["trade_id"], row["exit_policy_version"], row["cost_scenario"]))
    table_path = artifact_dir / "c2a_paired_trade_records.csv"
    _write_csv(table_path, combined, trade_columns)
    resolved = [row for row in combined if str(row["censored"]).lower() == "false"]
    summary = _policy_summary(resolved, decisions)
    cohorts = _cohort_summary(resolved)
    groups = _group_summaries(resolved)
    dependence = _dependence_summary(resolved)
    write_json(artifact_dir / "candidate_policy_summary.json", summary)
    write_json(artifact_dir / "candidate_cohorts.json", cohorts)
    write_json(artifact_dir / "candidate_group_summaries.json", groups)
    write_json(artifact_dir / "candidate_dependence.json", dependence)
    result = {
        "run_id": RUN_ID, "frozen_entry_hash": EXPECTED_FROZEN_ENTRY_HASH,
        "common_horizon_hash": EXPECTED_COMMON_HORIZON_HASH,
        "paired_trade_rows": len(combined), "paired_trade_semantic_hash": hash_rows(combined, trade_columns),
        "paired_trade_file_hash": sha256_file(table_path),
        "summary_hashes": {name: sha256_file(artifact_dir / name) for name in (
            "candidate_policy_summary.json", "candidate_cohorts.json", "candidate_group_summaries.json", "candidate_dependence.json")},
    }
    _write_manifest(artifact_dir, result, summary)
    return result


def _candidate_record(entry: dict, horizon: dict, decision: CandidateDecision, metrics: dict, costs: dict, p0: dict, foregone: float) -> dict:
    raw = float(costs["raw_price_return"]); p0_raw = float(p0["raw_price_return"])
    candidate_green_red = bool(metrics["held_green_then_red"])
    p0_green_red = str(p0["held_green_then_red"]).lower() == "true"
    candidate_common_red = bool(metrics["common_opportunity_positive_exit_red"])
    p0_common_red = str(p0["common_opportunity_positive_exit_red"]).lower() == "true"
    policy = decision.policy_version.split("_", 1)[0]
    row = {
        "run_id": RUN_ID, "trade_id": entry["trade_id"], "symbol": entry["symbol"], "entry_fixture_id": entry["entry_fixture_id"],
        "entry_signal_ts": entry["entry_signal_ts"], "entry_decision_ts": entry["entry_decision_ts"],
        "entry_execution_ts": entry["entry_execution_ts"], "entry_execution_ms": entry["entry_execution_ms"],
        "entry_price": entry["entry_price"], "entry_notional_usdt": entry["entry_notional_usdt"],
        "exit_policy": policy, "exit_policy_version": decision.policy_version,
        "exit_signal_ts": iso(decision.signal_ms) if decision.signal_ms is not None else "",
        "exit_decision_ts": iso(decision.decision_ms) if decision.decision_ms is not None else "",
        "exit_execution_ts": iso(decision.execution_ms), "exit_price": format(float(decision.exit_price), ".17g"),
        "exit_reason": decision.exit_reason, "entry_timeframe": "1h",
        "signal_timeframe": "1m_standing" if policy == "P1" else "5m",
        "exit_observation_timeframe": "1m" if policy == "P1" else "5m", "source_timeframe": "1m",
        "execution_price_assumption": "barrier_or_gap_open" if policy == "P1" else "exact_boundary_1m_open",
        "common_horizon_end_ts": horizon["common_horizon_end_ts"], "censored": False, "censor_reason": "",
        "data_quality_flag": "complete", **costs, **metrics,
        "ambiguity_flag": decision.ambiguity_flag if decision.ambiguity_flag != "none" else metrics["ambiguity_flag"],
        "policy_activated_ms": decision.activated_ms if decision.activated_ms is not None else "",
        "activation_to_exit_seconds": (decision.execution_ms - decision.activated_ms) // 1000 if decision.activated_ms is not None else "",
        "gap_through": decision.gap_through, "negative_sequence_count": decision.negative_sequence_count,
        "p0_raw_return": p0_raw, "raw_return_delta_vs_p0": raw - p0_raw,
        "net_return_delta_vs_p0": float(costs["net_return"]) - float(p0["net_return"]),
        "held_surrender_delta_vs_p0": float(metrics["held_peak_gain_surrendered"]) - float(p0["held_peak_gain_surrendered"]),
        "common_capture_gap_delta_vs_p0": float(metrics["common_opportunity_capture_gap"]) - float(p0["common_opportunity_capture_gap"]),
        "holding_duration_delta_vs_p0": int(metrics["holding_duration_seconds"]) - int(horizon["common_horizon_duration_seconds"]),
        "held_green_then_red_change": int(candidate_green_red) - int(p0_green_red),
        "common_positive_exit_red_change": int(candidate_common_red) - int(p0_common_red),
        "candidate_better_than_p0": raw > p0_raw, "candidate_worse_than_p0": raw < p0_raw,
        "candidate_equal_to_p0": raw == p0_raw, "rescued": p0_raw <= 0 < raw, "damaged": p0_raw > 0 >= raw,
        "exited_before_p0": int(decision.execution_ms) < int(horizon["common_horizon_end_ms"]),
        "foregone_subsequent_gain": foregone, "premature_appreciation_0_5pct": foregone >= 0.005,
    }
    return row


def _censored_records(entry: dict, horizon: dict, decision: CandidateDecision, p0_columns: tuple[str, ...]) -> list[dict]:
    rows = []
    for scenario in COST_SCENARIOS:
        row = {column: "" for column in p0_columns + EXTRA_COLUMNS}
        row.update({"run_id": RUN_ID, "trade_id": entry["trade_id"], "symbol": entry["symbol"],
                    "entry_fixture_id": entry["entry_fixture_id"], "entry_execution_ts": entry["entry_execution_ts"],
                    "entry_execution_ms": entry["entry_execution_ms"], "entry_price": entry["entry_price"],
                    "exit_policy": decision.policy_version.split("_", 1)[0], "exit_policy_version": decision.policy_version,
                    "cost_scenario": scenario.scenario_id, "common_horizon_end_ts": horizon["common_horizon_end_ts"],
                    "censored": True, "censor_reason": decision.censor_reason, "data_quality_flag": "right_censored",
                    "ambiguity_flag": decision.ambiguity_flag, "gap_through": decision.gap_through})
        rows.append(row)
    return rows


def _assert_common_metrics(metrics: dict, horizon: dict) -> None:
    for key in ("common_horizon_mfe", "common_horizon_mae", "time_to_common_horizon_mfe_seconds"):
        if not math.isclose(float(metrics[key]), float(horizon[key]), rel_tol=0, abs_tol=1e-14):
            raise ValueError(f"immutable common metric mismatch: {key}")


def _foregone_gain(exit_ms: int, exit_price: float, horizon_ms: int, horizon_price: float, rows: list[dict]) -> float:
    if exit_ms >= horizon_ms: return 0.0
    prices = [horizon_price]
    prices.extend(float(row["high"]) for row in rows if exit_ms < int(row["open_time_ms"]) < horizon_ms)
    return max(max(prices) / exit_price - 1, 0.0)


def _policy_summary(rows: list[dict], decisions: list[tuple[dict, dict, CandidateDecision]]) -> dict:
    result = {"bootstrap_seed_fixed_before_results": BOOTSTRAP_SEED, "policies": {}}
    for version in POLICIES:
        policy = version.split("_", 1)[0]
        d = [decision for _entry, _h, decision in decisions if decision.policy_version == version]
        c0 = [r for r in rows if r["exit_policy_version"] == version and r["cost_scenario"] == "C0"]
        diagnostics = {"exit_reasons": dict(sorted(Counter(x.exit_reason for x in d if x.exit_reason).items())),
                       "censored": sum(x.censored for x in d)}
        if policy == "P1":
            diagnostics.update({"ambiguous_both_hit": sum(x.ambiguity_flag == "ambiguous_both_hit_conservative" for x in d),
                                "gap_through": sum(x.gap_through for x in d)})
        if policy == "P2":
            diagnostics.update({"activated": sum(x.activated_ms is not None for x in d),
                                "never_activated": sum(x.activated_ms is None for x in d),
                                "activation_to_exit_seconds": _dist([(x.execution_ms-x.activated_ms)//1000 for x in d if x.activated_ms is not None and x.execution_ms is not None])})
        if policy == "P3": diagnostics["negative_sequences_at_exit"] = dict(sorted(Counter(x.negative_sequence_count for x in d).items()))
        result["policies"][policy] = {"version": version, "diagnostics": diagnostics,
            "raw_return": _dist([float(r["raw_price_return"]) for r in c0]),
            "held_surrender": _dist([float(r["held_peak_gain_surrendered"]) for r in c0]),
            "common_capture_gap": _dist([float(r["common_opportunity_capture_gap"]) for r in c0]),
            "holding_duration_seconds": _dist([float(r["holding_duration_seconds"]) for r in c0]),
            "held_green_then_red": _count_rate(c0, "held_green_then_red"),
            "common_opportunity_positive_exit_red": _count_rate(c0, "common_opportunity_positive_exit_red"),
            "paired_raw": _paired(c0, "raw_return_delta_vs_p0"),
            "rescued": _count_rate(c0, "rescued"), "damaged": _count_rate(c0, "damaged"),
            "premature_appreciation_0_5pct": _count_rate(c0, "premature_appreciation_0_5pct"),
            "foregone_subsequent_gain": _dist([float(r["foregone_subsequent_gain"]) for r in c0]),
            "costs": {scenario.scenario_id: _cost_summary([r for r in rows if r["exit_policy_version"] == version and r["cost_scenario"] == scenario.scenario_id]) for scenario in COST_SCENARIOS}}
    return result


def _paired(rows: list[dict], delta_key: str) -> dict:
    return {"delta": _dist([float(r[delta_key]) for r in rows]),
            "better": sum(_bool(r["candidate_better_than_p0"]) for r in rows),
            "worse": sum(_bool(r["candidate_worse_than_p0"]) for r in rows),
            "equal": sum(_bool(r["candidate_equal_to_p0"]) for r in rows)}


def _cost_summary(rows: list[dict]) -> dict:
    return {"count": len(rows), "raw_return": _dist([float(r["raw_price_return"]) for r in rows]),
            "gross_return": _dist([float(r["gross_return"]) for r in rows]), "net_return": _dist([float(r["net_return"]) for r in rows]),
            "net_delta_vs_p0": _dist([float(r["net_return_delta_vs_p0"]) for r in rows]),
            "fees_usdt": _dist([float(r["fees_usdt"]) for r in rows]),
            "rescued": _count_rate(rows,"rescued"), "damaged": _count_rate(rows,"damaged"),
            "premature_appreciation_0_5pct": _count_rate(rows,"premature_appreciation_0_5pct")}


def _cohort_summary(rows: list[dict]) -> dict:
    p0 = {r["trade_id"]: r for r in rows if r["exit_policy"] == "P0" and r["cost_scenario"] == "C0"}
    result = {}
    for label, threshold in THRESHOLDS:
        eligible = {tid for tid, row in p0.items() if float(row["common_horizon_mfe"]) + 1e-15 >= threshold}
        failure = {tid for tid in eligible if float(p0[tid]["raw_price_return"]) <= 0}
        result[label] = {"mfe_threshold": threshold, "all_opportunity": {}, "baseline_failure": {}}
        for version in POLICIES:
            for name, ids in (("all_opportunity", eligible), ("baseline_failure", failure)):
                result[label][name][version] = {}
                for scenario in COST_SCENARIOS:
                    selected = [r for r in rows if r["exit_policy_version"] == version and r["cost_scenario"] == scenario.scenario_id and r["trade_id"] in ids]
                    result[label][name][version][scenario.scenario_id] = {
                        "trade_count": len(selected), "rescued": _count_rate(selected, "rescued"),
                        "damaged": _count_rate(selected, "damaged"), "candidate_raw_return": _dist([float(r["raw_price_return"]) for r in selected]),
                        "candidate_net_return": _dist([float(r["net_return"]) for r in selected]),
                        "paired_net_delta": _dist([float(r["net_return_delta_vs_p0"]) for r in selected]),
                        "held_surrender": _dist([float(r["held_peak_gain_surrendered"]) for r in selected]),
                        "common_capture_gap": _dist([float(r["common_opportunity_capture_gap"]) for r in selected]),
                        "holding_duration_delta": _dist([float(r["holding_duration_delta_vs_p0"]) for r in selected]),
                        "premature_appreciation_0_5pct": _count_rate(selected, "premature_appreciation_0_5pct"),
                    }
    return result


def _group_summaries(rows: list[dict]) -> dict:
    result = {"by_symbol": {}, "by_partition": {}, "by_month": {}, "by_week": {}}
    cands = [r for r in rows if r["exit_policy"] != "P0"]
    groupers = {
        "by_symbol": lambda r: r["symbol"],
        "by_partition": lambda r: "sanity_calibration" if r["entry_execution_ts"] < "2024-04-01" else "headline_evaluation",
        "by_month": lambda r: r["entry_execution_ts"][:7],
        "by_week": lambda r: datetime.fromisoformat(r["entry_execution_ts"]).strftime("%G-W%V"),
    }
    for name, keyfn in groupers.items():
        keys = sorted({keyfn(r) for r in cands})
        for key in keys:
            result[name][key] = {}
            for version in POLICIES:
                result[name][key][version] = {}
                for scenario in COST_SCENARIOS:
                    selected = [r for r in cands if keyfn(r) == key and r["exit_policy_version"] == version and r["cost_scenario"] == scenario.scenario_id]
                    result[name][key][version][scenario.scenario_id] = _cost_summary(selected)
    return result


def _dependence_summary(rows: list[dict]) -> dict:
    headline = [r for r in rows if r["exit_policy"] != "P0" and r["entry_execution_ts"] >= "2024-04-01"]
    result = {"seed": BOOTSTRAP_SEED, "replications": BOOTSTRAP_REPLICATIONS,
              "block": "entry_calendar_month_with_all_symbols_kept_together", "intervals": {},
              "monthly_symbol_raw_return_correlations": _symbol_correlations(rows)}
    for version in POLICIES:
        result["intervals"][version] = {}
        for scenario in COST_SCENARIOS:
            selected = [r for r in headline if r["exit_policy_version"] == version and r["cost_scenario"] == scenario.scenario_id]
            result["intervals"][version][scenario.scenario_id] = _block_bootstrap(selected, BOOTSTRAP_SEED + sum(map(ord, version + scenario.scenario_id)))
    return result


def _block_bootstrap(rows: list[dict], seed: int) -> dict:
    months = sorted({r["entry_execution_ts"][:7] for r in rows}); rng = random.Random(seed)
    by_month = {m: [r for r in rows if r["entry_execution_ts"].startswith(m)] for m in months}
    entry_estimates=[]; symbol_estimates=[]
    for _ in range(BOOTSTRAP_REPLICATIONS):
        sampled = [rng.choice(months) for _ in months]
        sample = [r for m in sampled for r in by_month[m]]
        entry_estimates.append(statistics.fmean(float(r["net_return_delta_vs_p0"]) for r in sample))
        symbol_means = [statistics.fmean(float(r["net_return_delta_vs_p0"]) for r in sample if r["symbol"] == symbol) for symbol in sorted({r["symbol"] for r in sample})]
        symbol_estimates.append(statistics.fmean(symbol_means))
    observed_entry = statistics.fmean(float(r["net_return_delta_vs_p0"]) for r in rows)
    observed_symbol = statistics.fmean(statistics.fmean(float(r["net_return_delta_vs_p0"]) for r in rows if r["symbol"] == s) for s in sorted({r["symbol"] for r in rows}))
    return {"equal_weight_entry": {"estimate": observed_entry, "ci95": [_quantile(entry_estimates,.025),_quantile(entry_estimates,.975)]},
            "equal_weight_symbol_primary": {"estimate": observed_symbol, "ci95": [_quantile(symbol_estimates,.025),_quantile(symbol_estimates,.975)]}}


def _symbol_correlations(rows: list[dict]) -> dict:
    p0 = [r for r in rows if r["exit_policy"] == "P0" and r["cost_scenario"] == "C0"]
    months=sorted({r["entry_execution_ts"][:7] for r in p0}); symbols=sorted({r["symbol"] for r in p0})
    series={s:[statistics.fmean(float(r["raw_price_return"]) for r in p0 if r["symbol"]==s and r["entry_execution_ts"].startswith(m)) for m in months] for s in symbols}
    return {a:{b:_corr(series[a],series[b]) for b in symbols} for a in symbols}


def _corr(a:list[float],b:list[float])->float:
    ma,mb=statistics.fmean(a),statistics.fmean(b); num=sum((x-ma)*(y-mb) for x,y in zip(a,b)); den=math.sqrt(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b)); return num/den if den else 0.0


def _dist(values:list[float])->dict:
    if not values:return {"count":0,"mean":None,"median":None,"p05":None,"p95":None}
    return {"count":len(values),"mean":statistics.fmean(values),"median":statistics.median(values),"p05":_quantile(values,.05),"p95":_quantile(values,.95)}


def _quantile(values:list[float],p:float)->float:
    x=sorted(values); i=(len(x)-1)*p; lo,hi=math.floor(i),math.ceil(i); return x[lo] if lo==hi else x[lo]+(x[hi]-x[lo])*(i-lo)


def _bool(value:object)->bool:return str(value).lower()=="true"
def _count_rate(rows:list[dict],key:str)->dict:
    count=sum(_bool(r[key]) for r in rows); return {"count":count,"rate":count/len(rows) if rows else None}
def _write_csv(path:Path,rows:list[dict],columns:tuple[str,...])->None:
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=columns,lineterminator="\n");w.writeheader();w.writerows(rows)


def _write_manifest(artifact_dir:Path,result:dict,summary:dict)->None:
    contract=Path("contracts/C2_asymmetric_exit_experiment_CONTRACT.md")
    paths=[Path(__file__),Path(__file__).with_name("c2_candidate_policies.py"),Path(__file__).with_name("c2_candidate_cli.py"),Path("tests/test_c2_candidate_policies.py")]
    manifest={"run_id":RUN_ID,"created_at_utc":datetime.now(timezone.utc).isoformat(),
        "code_revision":subprocess.run(["git","rev-parse","HEAD"],check=True,capture_output=True,text=True).stdout.strip(),
        "contract_sha256":sha256_file(contract),"frozen_entry_hash":EXPECTED_FROZEN_ENTRY_HASH,"common_horizon_hash":EXPECTED_COMMON_HORIZON_HASH,
        "policy_versions":list(POLICIES),"parameters":{"P1":{"tp":.02,"sl":.01},"P2":{"activation":.01,"trail":.01},"P3":{"consecutive_negative_5m_returns":2}},
        "causal_assumptions":{"P2_entry_containing_5m_bar":"excluded because its entry-minute high has unknown pre/post-fill ordering","P3_entry_5m_close":"eligible at completion; close is observed after entry fill"},
        "cost_scenarios":[{"id":x.scenario_id,"fee_rate":x.fee_rate,"slippage_rate":x.slippage_rate} for x in COST_SCENARIOS],
        "research_partitions":research_partitions(),"bootstrap":{"seed":BOOTSTRAP_SEED,"replications":BOOTSTRAP_REPLICATIONS,"block":"calendar_month"},
        "implementation_hashes":{str(p.relative_to(Path.cwd())) if p.is_absolute() else str(p):sha256_file(p) for p in paths},
        "output_hashes":result["summary_hashes"],"paired_trade_semantic_hash":result["paired_trade_semantic_hash"],"paired_trade_file_hash":result["paired_trade_file_hash"],
        "candidate_censor_counts":{policy:summary["policies"][policy]["diagnostics"]["censored"] for policy in ("P1","P2","P3")},
        "explicitly_not_implemented":["C2-B","ML","parameter tuning","volatility-aware exits","1-minute signal policies"]}
    write_json(artifact_dir/"candidate_manifest.json",manifest)
