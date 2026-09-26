"""C6 descriptive diagnostics over frozen C5 decisions and frozen C4 scores.

This module does not replay a policy, generate a prediction, read price data, or
calculate an economic outcome.  Trigger identities come only from the accepted
C5 trade table; C4 rows are joined to provide order, timestamps, and scores.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np

from .c5_t1 import state_score

CANONICAL_SHA = "094c81c306f1084146db55cee3c6f38178e58a0e72e55e056bb0dd1eb6c46884"
CUTOFFS = {"G1": 0.38599566214835807, "P1": 0.3962652238189601}
POLICIES = {"G1": "G1_Q75_EXIT_V1", "P1": "P1_Q75_EXIT_V1"}
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def distribution(values: Iterable[float]) -> dict:
    a = np.asarray(list(values), dtype=float)
    if not len(a):
        return {k: None if k != "count" else 0 for k in ("count", "min", "p25", "median", "p75", "p90", "max", "mean")}
    return {"count": int(len(a)), "min": float(a.min()),
            "p25": float(np.quantile(a, .25, method="linear")), "median": float(np.median(a)),
            "p75": float(np.quantile(a, .75, method="linear")), "p90": float(np.quantile(a, .90, method="linear")),
            "max": float(a.max()), "mean": float(a.mean())}


def ordinal_buckets(ordinals: Iterable[int]) -> dict:
    out = {"first": 0, "second": 0, "third": 0, "fourth": 0, "fifth": 0, "6-10": 0, "11+": 0}
    names = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
    for value in ordinals:
        out[names.get(value, "6-10" if value <= 10 else "11+")] += 1
    return out


def trigger_ordinal(ordered_row_ids: list[str], frozen_trigger_row_id: str | None) -> int | None:
    """Join one frozen trigger identity to a unique, already-ordered path."""
    if len(ordered_row_ids) != len(set(ordered_row_ids)):
        raise ValueError("duplicate path row identity")
    if frozen_trigger_row_id is None:
        return None
    if frozen_trigger_row_id not in ordered_row_ids:
        raise ValueError("frozen trigger identity absent from path")
    return ordered_row_ids.index(frozen_trigger_row_id) + 1


def elapsed_minutes(start_ms: int, decision_ms: int) -> float:
    if decision_ms < start_ms:
        raise ValueError("decision precedes timing origin")
    return (decision_ms - start_ms) / 60000


def _scopes(trades: list[dict]) -> dict[str, list[dict]]:
    return {"pooled": trades,
            "by_year": {y: [t for t in trades if t["year"] == y] for y in ("2024", "2025")},
            "by_symbol": {s: [t for t in trades if t["symbol"] == s] for s in SYMBOLS}}


def _map_scopes(trades: list[dict], fn) -> dict:
    s = _scopes(trades)
    return {"pooled": fn(s["pooled"]), "by_year": {k: fn(v) for k, v in s["by_year"].items()},
            "by_symbol": {k: fn(v) for k, v in s["by_symbol"].items()}}


def _load(repo: Path) -> tuple[list[dict], dict[str, dict[str, dict]]]:
    canonical = repo / "artifacts/c5_economic_exit_policy/t2/trade_results.csv"
    if sha256(canonical) != CANONICAL_SHA:
        raise RuntimeError("canonical C5 trade_results hash mismatch")
    selected = {}
    signatures = defaultdict(set)
    with canonical.open(newline="") as handle:
        for r in csv.DictReader(handle):
            if r["policy_id"] not in POLICIES.values():
                continue
            key = (r["trade_id"], r["policy_id"])
            sig = (r["triggered"], r["trigger_row_id"], r["trigger_snapshot_ts"], r["trigger_score"], r["score_cutoff"])
            signatures[key].add(sig)
            if r["cost_scenario"] == "C0": selected[key] = r
    if any(len(x) != 1 for x in signatures.values()) or len(selected) != 878:
        raise RuntimeError("C5 trigger identity differs across cost scenarios or is incomplete")

    raw = defaultdict(list)
    with (repo / "artifacts/c4_sequential_exit_state/local/t2_snapshots.csv").open(newline="") as handle:
        for r in csv.DictReader(handle):
            if r["target_eligible"] == "True" and r["snapshot_ts"][:4] in ("2024", "2025"):
                raw[r["trade_id"]].append(r)
    pred = defaultdict(dict)
    for path in (repo / "artifacts/c4_sequential_exit_state/development_predictions_2024.csv",
                 repo / "artifacts/c4_sequential_exit_state/locked_2025/predictions.csv"):
        with path.open(newline="") as handle:
            for r in csv.DictReader(handle):
                if r.get("target") == "T2" and r.get("model") in POLICIES:
                    pred[r["row_id"]][r["model"]] = r

    trades = []
    for trade_id in sorted({k[0] for k in selected}):
        first_policy = selected[(trade_id, POLICIES["G1"])]
        path = sorted(raw[trade_id], key=lambda r: (int(r["snapshot_ms"]), r["row_id"]))
        if not path or any(set(pred[r["row_id"]]) != set(POLICIES) for r in path):
            raise RuntimeError(f"incomplete frozen path/prediction join: {trade_id}")
        item = {"trade_id": trade_id, "year": first_policy["year"], "symbol": first_policy["symbol"],
                "entry_ms": int(first_policy["entry_execution_ms"]), "path": path, "models": {}}
        ids = [r["row_id"] for r in path]
        if len(ids) != len(set(ids)):
            raise RuntimeError(f"duplicate snapshot row identity: {trade_id}")
        for model, policy in POLICIES.items():
            frozen = selected[(trade_id, policy)]
            hit = frozen["triggered"] == "True"
            row_id = frozen["trigger_row_id"] or None
            if hit != (row_id is not None) or (row_id is not None and row_id not in ids):
                raise RuntimeError(f"invalid frozen trigger join: {trade_id}/{model}")
            ordinal = trigger_ordinal(ids, row_id)
            scores = [state_score(pred[r["row_id"]][model]) for r in path]
            item["models"][model] = {"triggered": hit, "trigger_row_id": row_id, "ordinal": ordinal,
                                      "trigger_ms": int(path[ordinal-1]["snapshot_ms"]) if ordinal else None,
                                      "scores": scores, "cutoff": float(frozen["score_cutoff"]),
                                      "frozen_trigger_score": float(frozen["trigger_score"]) if hit else None}
            if float(frozen["score_cutoff"]) != CUTOFFS[model]:
                raise RuntimeError("frozen cutoff mismatch")
            if hit and (path[ordinal-1]["snapshot_ts"] != frozen["trigger_snapshot_ts"] or
                        not np.isclose(scores[ordinal-1], float(frozen["trigger_score"]), rtol=0, atol=1e-15)):
                raise RuntimeError(f"frozen trigger timestamp/score mismatch: {trade_id}/{model}")
        trades.append(item)
    if len(trades) != 439 or sum(len(t["path"]) for t in trades) != 38745:
        raise RuntimeError("replay-authorized population mismatch")
    return trades, pred


def build(repo: Path) -> Path:
    trades, _ = _load(repo)
    out = repo / "artifacts/c6_t2_trigger_diagnostics"
    out.mkdir(parents=True, exist_ok=True)
    inputs = ["artifacts/c5_economic_exit_policy/t2/trade_results.csv",
              "artifacts/c5_economic_exit_policy/t1_readiness.json",
              "artifacts/c5_economic_exit_policy/t2/replay_manifest.json",
              "artifacts/c4_sequential_exit_state/local/t2_snapshots.csv",
              "artifacts/c4_sequential_exit_state/development_predictions_2024.csv",
              "artifacts/c4_sequential_exit_state/locked_2025/predictions.csv"]
    provenance = {"version": "C6_EXPLORATORY_T2_TRIGGER_DIAGNOSTIC_V1", "canonical_hash_verified": True,
                  "canonical_expected_sha256": CANONICAL_SHA, "inputs": {p: sha256(repo/p) for p in inputs},
                  "population": {"trades": len(trades), "snapshots": sum(len(t["path"]) for t in trades)},
                  "boundaries": {"c5_replay_run": False, "policy_outcomes_recomputed": False,
                    "predictions_generated": False, "sealed_confirmation_access": False,
                    "policy_or_threshold_search": False, "economic_metrics_calculated": False}}
    _write(out / "provenance.json", provenance)

    def timing(model: str, group: list[dict]) -> dict:
        hits = [t for t in group if t["models"][model]["triggered"]]
        ords = [t["models"][model]["ordinal"] for t in hits]
        since_first = [elapsed_minutes(int(t["path"][0]["snapshot_ms"]), t["models"][model]["trigger_ms"]) for t in hits]
        since_entry = [elapsed_minutes(t["entry_ms"], t["models"][model]["trigger_ms"]) for t in hits]
        return {"total_replay_authorized_trades": len(group), "triggered_trades": len(hits),
                "non_triggered_trades": len(group)-len(hits), "trigger_ordinal_buckets": ordinal_buckets(ords),
                "trigger_ordinal_distribution": distribution(ords),
                "minutes_first_T2_to_trigger_distribution": distribution(since_first),
                "minutes_entry_execution_to_trigger_distribution": distribution(since_entry)}
    trigger_timing = {m: _map_scopes(trades, lambda g, m=m: timing(m, g)) for m in POLICIES}
    _write(out / "trigger_timing.json", trigger_timing)

    def immediate(model: str, group: list[dict]) -> dict:
        n = sum(t["models"][model]["ordinal"] == 1 for t in group)
        return {"trades": len(group), "first_T2_triggers": n, "probability": n/len(group), "percent": 100*n/len(group)}
    _write(out / "immediate_trigger.json", {m: _map_scopes(trades, lambda g, m=m: immediate(m, g)) for m in POLICIES})

    categories = ("both_never_trigger", "both_same_decision_snapshot", "P1_triggers_earlier", "G1_triggers_earlier", "only_P1_triggers", "only_G1_triggers")
    def agreement(group: list[dict]) -> dict:
        labels=[]; diffs=[]
        for t in group:
            g,p=t["models"]["G1"],t["models"]["P1"]
            if not g["triggered"] and not p["triggered"]: label="both_never_trigger"
            elif not g["triggered"]: label="only_P1_triggers"
            elif not p["triggered"]: label="only_G1_triggers"
            else:
                d=(p["trigger_ms"]-g["trigger_ms"])/60000; diffs.append(d)
                label="both_same_decision_snapshot" if d==0 else ("P1_triggers_earlier" if d<0 else "G1_triggers_earlier")
            labels.append(label)
        c=Counter(labels); absolute=[abs(x) for x in diffs]
        return {"trades":len(group), "counts":{k:c[k] for k in categories},
                "percentages":{k:100*c[k]/len(group) for k in categories},
                "P1_minus_G1_minutes_distribution_both_trigger":distribution(diffs),
                "absolute_minutes_distribution_both_trigger":distribution(absolute),
                "median_absolute_timing_difference_minutes":float(np.median(absolute)) if absolute else None,
                "maximum_absolute_timing_difference_minutes":max(absolute) if absolute else None}
    _write(out / "g1_p1_agreement.json", _map_scopes(trades, agreement))

    def scores(model: str, group: list[dict]) -> dict:
        first=[t["models"][model]["scores"][0] for t in group]
        hit=[t["models"][model] for t in group if t["models"][model]["triggered"]]
        trigger=[x["frozen_trigger_score"] for x in hit]
        cutoff=CUTOFFS[model]; above=sum(x >= cutoff for x in first)
        return {"trades":len(group), "frozen_Q75_cutoff":cutoff,
                "first_T2_score_distribution":distribution(first),
                "first_T2_at_or_above_cutoff_count":above,
                "first_T2_at_or_above_cutoff_fraction":above/len(group),
                "trigger_score_distribution":distribution(trigger),
                "margin_above_cutoff_at_trigger_distribution":distribution(x-cutoff for x in trigger)}
    _write(out / "score_at_trigger.json", {m:_map_scopes(trades,lambda g,m=m:scores(m,g)) for m in POLICIES})

    def paths(model: str, group: list[dict]) -> dict:
        later=[t for t in group if (t["models"][model]["ordinal"] or 0)>1]
        details=[]
        for t in later:
            x=t["models"][model]; pre=x["scores"][:x["ordinal"]-1]; cutoff=x["cutoff"]
            crossings=sum(pre[i-1] < cutoff <= pre[i] for i in range(1,len(pre)))
            details.append({"trade_id":t["trade_id"], "eligible_snapshots_before_trigger":len(pre),
                            "began_below_then_crossed_at_trigger":pre[0] < cutoff <= x["scores"][x["ordinal"]-1],
                            "pre_trigger_upward_crossings":crossings, "crossed_more_than_once_before_first_trigger":crossings>1,
                            "maximum_pre_trigger_score":max(pre), "minimum_pre_trigger_score":min(pre)})
        return {"later_triggered_trades":len(later),
                "eligible_snapshots_before_trigger_distribution":distribution(d["eligible_snapshots_before_trigger"] for d in details),
                "began_below_then_crossed_at_trigger_count":sum(d["began_below_then_crossed_at_trigger"] for d in details),
                "crossed_more_than_once_before_first_trigger_count":sum(d["crossed_more_than_once_before_first_trigger"] for d in details),
                "maximum_pre_trigger_score_distribution":distribution(d["maximum_pre_trigger_score"] for d in details),
                "minimum_pre_trigger_score_distribution":distribution(d["minimum_pre_trigger_score"] for d in details),
                "trade_details":details}
    _write(out / "path_before_trigger.json", {m:_map_scopes(trades,lambda g,m=m:paths(m,g)) for m in POLICIES})

    _write(out / "t2_path_length.json", _map_scopes(trades, lambda g:{"trades":len(g), "eligible_snapshot_count_distribution":distribution(len(t["path"]) for t in g)}))

    (out / "candidate_controls.md").write_text("""# Candidate C6 controls (definitions only)\n\nThese controls are proposed for later preregistration; none was run or evaluated economically here.\n\n- `EXIT_FIRST_T2`: decide at the first frozen T2-eligible completed 5-minute snapshot and execute with the existing next-1-minute-open semantics. This directly isolates entry into the T2 risk set from model timing.\n- `EXIT_SECOND_T2`: decide at the second available frozen T2-eligible snapshot. Specify *available*, rather than consecutive wall-clock bars, unless a later contract explicitly requires continuous eligibility.\n- `FIXED_DELAY_T2`: choose one predeclared ordinal delay using scientific design criteria fixed before economics; do not select the delay from returns.\n- `RANDOM_CONTROL`: on each eligible snapshot, apply a preregistered deterministic RNG stream, fixed seed, stable trade/row ordering, and an explicitly frozen stopping rule.\n- `BASE_RATE_RANDOM_CONTROL`: freeze the probability from development-era trigger-timing frequencies only, with no economic-outcome input, and apply the same deterministic RNG requirements.\n\nThe first and second controls are especially interpretable when immediate triggering dominates. Fixed-delay and random controls can distinguish deterministic risk-set entry from exposure-duration and generic stopping effects. No candidate is selected here.\n""")
    first = {m: trigger_timing[m]["pooled"]["trigger_ordinal_buckets"]["first"] for m in POLICIES}
    (out / "interpretation.md").write_text(f"""# Exploratory interpretation\n\nThis diagnostic characterizes frozen C5 behavior only. G1 triggered at its first T2 snapshot for {first['G1']} of 439 trades; P1 did so for {first['P1']} of 439. A slim majority was immediate, while the near-universal total was completed by later first passages that were usually early in the eligible path. The result is therefore rapid eventual triggering, not “almost everyone immediately.” Path-length context is reported separately and no economic calculation was made.\n\nNo result here establishes that exiting at T2 entry, after a delay, or randomly has economic value. No returns, P&L, costs, future outcomes, MFE, P0 outcomes, or winner truncation were used.\n""")
    generated = ["provenance.json", "trigger_timing.json", "immediate_trigger.json", "g1_p1_agreement.json",
                 "score_at_trigger.json", "path_before_trigger.json", "t2_path_length.json", "candidate_controls.md", "interpretation.md"]
    _write(out / "reproducibility.json", {"version":"C6_EXPLORATORY_T2_TRIGGER_DIAGNOSTIC_V1",
          "command":"python -m binance_data_foundation.c6_t2_diagnostics",
          "quantile_method":"linear", "ordering":"snapshot_ms then row_id within immutable trade_id",
          "timing_semantics":"completed 5m snapshot decision timestamp; existing immediate 1m open at same timestamp",
          "generated_artifact_hashes":{name:sha256(out/name) for name in generated}})
    return out


if __name__ == "__main__":
    build(Path.cwd())
