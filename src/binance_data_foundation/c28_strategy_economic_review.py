"""C28 frozen strategy-level economic review.

MFE quantities in this module are descriptive and are never execution rules.
"""
from __future__ import annotations

import csv
import bisect
import hashlib
import json
import math
import os
import platform
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .c2_common import ENTRY_COLUMNS, hash_rows, iter_gzip_csv, valid_minute
from .c2_costs import COST_SCENARIOS, apply_round_trip_costs
from .c2_entries import hourly_sma24
from .ingest import sha256_file

CONTRACT_REL = "contracts/C28_strategy_economic_review_CONTRACT.md"
CONTRACT_SHA256 = "ffba4ae1d4301bcefe8e42000325b28bda66a59c4d2067e41b33ff6ae0df4923"
OUTPUT_REL = "artifacts/c28_strategy_economic_review"
C2_REL = "artifacts/c2_asymmetric_exit_experiment"
ENTRY_SHA256 = "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
EXPECTED_ENTRIES = 2199
START_MS = 1704067200000  # 2024-01-01 UTC
END_MS = 1767225600000    # 2026-01-01 UTC, exclusive
HORIZONS = (6, 24, 72, 168)
PRIMARY_HORIZON = 24
COST_IDS = tuple(x.scenario_id for x in COST_SCENARIOS)
SEED = 20260929
REPLICATES = 2000
NOTIONAL = 1000.0


def reject_2026(path: os.PathLike | str) -> None:
    """Fail closed for any partition/path explicitly labelled as 2026."""
    if any("2026" in part.lower() for part in os.fspath(path).replace("\\", "/").split("/")):
        raise PermissionError("C28 prohibits 2026 data or metadata access")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _load(path: Path) -> object:
    reject_2026(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _semantic_sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _year(ms: int) -> int:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).year


def _month(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")


def _hour(ms: int) -> int:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).hour


def _quantile(values: list[float], q: float) -> float | None:
    return float(np.quantile(np.asarray(values, float), q, method="linear")) if values else None


def return_summary(rows: list[dict], *, return_key: str = "return", pnl_key: str = "pnl_usdt",
                   holding_key: str | None = None) -> dict:
    vals = [float(r[return_key]) for r in rows]
    pnls = [float(r[pnl_key]) for r in rows]
    wins = sum(x > 0 for x in vals); losses = sum(x < 0 for x in vals); ties = len(vals) - wins - losses
    result = {
        "trade_count": len(rows), "total_pnl_usdt": float(sum(pnls)),
        "mean_return": statistics.fmean(vals) if vals else None,
        "median_return": statistics.median(vals) if vals else None,
        "positive_return_fraction": wins / len(vals) if vals else None,
        "negative_return_fraction": losses / len(vals) if vals else None,
        "tie_fraction": ties / len(vals) if vals else None,
        "win_loss_tie_count": {"win": wins, "loss": losses, "tie": ties},
    }
    if holding_key is not None:
        holds = [float(r[holding_key]) for r in rows]
        result.update({"mean_holding_duration_seconds": statistics.fmean(holds) if holds else None,
                       "median_holding_duration_seconds": statistics.median(holds) if holds else None})
    return result


def _cost_outcome(entry: float, exit_: float, cost_id: str, notional: float = NOTIONAL) -> dict:
    scenario = next(x for x in COST_SCENARIOS if x.scenario_id == cost_id)
    c = apply_round_trip_costs(entry, exit_, notional, scenario)
    pnl = c["quantity"] * c["exit_price_after_slippage"] - c["exit_fee_usdt"] - notional - c["entry_fee_usdt"]
    return {"return": float(c["net_return"]), "pnl_usdt": float(pnl)}


def fixed_horizon_outcome(entry_ms: int, entry_price: float, horizon: int,
                          minute_opens: dict[int, float], cost_id: str) -> dict | None:
    """Exit at first valid 1m open at/after decision+H; frozen data are gap-free at boundaries."""
    target = entry_ms + horizon * 3_600_000
    ts = target
    while ts < END_MS and ts not in minute_opens:
        ts += 60_000
    if ts >= END_MS:
        return None
    result = _cost_outcome(entry_price, minute_opens[ts], cost_id)
    return {**result, "exit_ms": ts, "exit_price": minute_opens[ts]}


def reference_pool(entry: dict, candidates: list[dict], all_entry_ms: list[int], horizon: int) -> list[dict]:
    """The single deterministic, frozen same-symbol/month/hour non-signal control."""
    ems = int(entry["entry_execution_ms"]); month = _month(ems); hour = _hour(ems)
    frozen = sorted(all_entry_ms)
    def outside_exclusion(ms: int) -> bool:
        i = bisect.bisect_left(frozen, ms)
        neighbors = frozen[max(0, i - 1):i + 1]
        return all(abs(ms - x) > 24 * 3_600_000 for x in neighbors)
    return [c for c in candidates
            if c["symbol"] == entry["symbol"] and _month(c["decision_ms"]) == month
            and _hour(c["decision_ms"]) == hour and not c["e1_fired"]
            and outside_exclusion(c["decision_ms"])
            and c["entry_valid"] and c["decision_ms"] + horizon * 3_600_000 < END_MS]


def paired_summary(rows: list[dict], cost_id: str) -> dict:
    vals = [r["actual"][cost_id]["return"] - r["reference"][cost_id]["return"] for r in rows]
    pos = sum(x > 0 for x in vals); neg = sum(x < 0 for x in vals); ties = len(vals) - pos - neg
    return {"covered_trade_count": len(vals), "mean_entry_advantage": statistics.fmean(vals) if vals else None,
            "median_entry_advantage": statistics.median(vals) if vals else None,
            "positive_fraction": pos / len(vals) if vals else None,
            "negative_fraction": neg / len(vals) if vals else None, "tie_fraction": ties / len(vals) if vals else None,
            "total_normalized_contribution_usdt": float(sum(vals) * NOTIONAL)}


def bootstrap(rows: list[dict], unit: str, cost_ids: tuple[str, ...] = ("C0", "C_BASE"),
              seed: int = SEED, replicates: int = REPLICATES) -> dict:
    if unit not in ("calendar_month", "whole_entry"):
        raise ValueError("unknown bootstrap unit")
    groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        groups[row["entry_month"] if unit == "calendar_month" else row["trade_id"]].append(i)
    labels = sorted(groups); rng = np.random.Generator(np.random.PCG64(seed))
    samples = np.empty((replicates, len(cost_ids)), float)
    for b in range(replicates):
        indices = [i for j in rng.integers(len(labels), size=len(labels)) for i in groups[labels[int(j)]]]
        for k, cost in enumerate(cost_ids):
            samples[b, k] = statistics.fmean(rows[i]["actual"][cost]["return"] - rows[i]["reference"][cost]["return"] for i in indices)
    return {"unit": unit, "seed": seed, "generator": "PCG64", "replicates": replicates,
            "shared_reference_pool_dependence_eliminated": False,
            "intervals": {cost: {"ci95": np.quantile(samples[:, k], [.025, .975], method="linear").tolist(),
                                  "replicate_sha256": hashlib.sha256(samples[:, k].astype("<f8").tobytes()).hexdigest()}
                          for k, cost in enumerate(cost_ids)}}


def strategy_decision(entry_supported: bool, opportunity_survives: bool, p0_cbase_mean: float) -> str:
    if not entry_supported:
        return "INVESTIGATE_ENTRY_MODEL"
    if not opportunity_survives:
        return "RECONSIDER_STRATEGY_ECONOMICS"
    if p0_cbase_mean <= 0:
        return "INVESTIGATE_PERMANENT_EXIT_TARGET"
    return "REVIEW_COMPLETE_P0_NOT_ECONOMICALLY_BROKEN"


def _load_entries_and_p0(repo: Path) -> tuple[list[dict], list[dict], list[dict]]:
    c2 = repo / C2_REL
    entry_path = c2 / "frozen_entries.csv"
    if sha256_file(entry_path) != ENTRY_SHA256:
        raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    with entry_path.open(encoding="utf-8", newline="") as handle:
        entries = list(csv.DictReader(handle))
    with (c2 / "p0_trade_records.csv").open(encoding="utf-8", newline="") as handle:
        p0 = list(csv.DictReader(handle))
    with (c2 / "common_horizons_p0.csv").open(encoding="utf-8", newline="") as handle:
        horizons = list(csv.DictReader(handle))
    if len(entries) != EXPECTED_ENTRIES or hash_rows(entries, ENTRY_COLUMNS) != ENTRY_SHA256:
        raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    return entries, p0, horizons


def _hourly_inputs(repo: Path, entries: list[dict]) -> tuple[dict[str, list[dict]], dict[str, dict[int, float]], dict[str, set[int]], dict]:
    base = repo / "data/normalized/c2_frozen_inputs"
    symbols = sorted({r["symbol"] for r in entries}); hours_by = {}; opens_by = {}; fired_by = {}; reproduction = []
    for symbol in symbols:
        path = base / f"{symbol}_1h.csv.gz"; reject_2026(path)
        hours = []
        for row in iter_gzip_csv(path):
            available = int(row["available_at_ms"])
            # The bar opened at 2025-12-31 23:00 is valid 2025 execution data
            # even though its completed-state timestamp is the exclusive bound.
            if int(row["open_time_ms"]) >= END_MS:
                break
            if int(row["open_time_ms"]) + 3_600_000 != available:
                raise RuntimeError("invalid completed hourly state")
            hours.append(row)
        sma = hourly_sma24(hours); fired = set()
        for i in range(1, len(hours)):
            if sma[i] is not None and sma[i-1] is not None and float(hours[i]["close"]) > sma[i] and float(hours[i-1]["close"]) <= sma[i-1]:
                fired.add(int(hours[i]["available_at_ms"]))
        opens = {int(r["open_time_ms"]): float(r["open"]) for r in hours if int(r["open_time_ms"]) >= START_MS}
        frozen = sorted(int(e["entry_execution_ms"]) for e in entries if e["symbol"] == symbol)
        last = None
        for ms in sorted(fired):
            if ms < START_MS or ms not in opens:
                continue
            if last is None or ms - last >= 24 * 3_600_000:
                reproduction.append((symbol, ms, opens[ms])); last = ms
        hours_by[symbol] = hours; opens_by[symbol] = opens; fired_by[symbol] = fired
    expected = sorted((e["symbol"], int(e["entry_execution_ms"]), float(e["entry_price"])) for e in entries)
    reproduced = sorted(reproduction)
    exact = len(expected) == len(reproduced) and all(a[:2] == b[:2] and a[2] == b[2] for a, b in zip(expected, reproduced))
    rec = {"status": "PASS" if exact else "INSUFFICIENT_RECONCILIATION", "expected_count": EXPECTED_ENTRIES,
           "reproduced_count": len(reproduced), "frozen_entry_file_sha256": ENTRY_SHA256,
           "semantic_entry_sha256": hash_rows(entries, ENTRY_COLUMNS), "timestamps_prices_and_refractory_exact": exact,
           "year_counts": dict(sorted(Counter(str(_year(int(e["entry_execution_ms"]))) for e in entries).items())),
           "symbol_counts": dict(sorted(Counter(e["symbol"] for e in entries).items()))}
    if not exact:
        raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    return hours_by, opens_by, fired_by, rec


def _p0_rows(entries: list[dict], p0: list[dict]) -> tuple[list[dict], dict]:
    entry_by = {e["trade_id"]: e for e in entries}; rows = []
    for r in p0:
        if r["censored"].lower() != "false":
            continue
        entry = entry_by[r["trade_id"]]; entry_notional = float(entry["entry_notional_usdt"])
        pnl = float(r["quantity"]) * float(r["exit_price_after_slippage"]) - float(r["exit_fee_usdt"]) - entry_notional - float(r["entry_fee_usdt"])
        rows.append({"trade_id": r["trade_id"], "symbol": r["symbol"], "year": _year(int(r["entry_execution_ms"])),
                     "cost": r["cost_scenario"], "return": float(r["net_return"]), "pnl_usdt": pnl,
                     "holding_seconds": float(r["common_horizon_duration_seconds"])})
    counts = Counter(r["cost"] for r in rows)
    exact = set(counts) == set(COST_IDS) and all(counts[c] == EXPECTED_ENTRIES for c in COST_IDS)
    if not exact:
        raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    return rows, {"status": "PASS", "canonical_p0_version": "P0_H1_SMA24_CROSSDOWN_V1",
                  "resolved_entries": EXPECTED_ENTRIES, "cost_row_counts": dict(sorted(counts.items())), "exact": exact}


def _groups(rows: list[dict], cost: str) -> dict:
    rr = [r for r in rows if r["cost"] == cost]
    return {"full_population": return_summary(rr, holding_key="holding_seconds"),
            "by_year": {str(y): return_summary([r for r in rr if r["year"] == y], holding_key="holding_seconds") for y in (2024, 2025)},
            "by_symbol": {s: return_summary([r for r in rr if r["symbol"] == s], holding_key="holding_seconds") for s in sorted({r["symbol"] for r in rr})}}


def _candidate_states(hours_by: dict, opens_by: dict, fired_by: dict) -> dict[str, list[dict]]:
    result = {}
    for symbol, hours in hours_by.items():
        result[symbol] = [{"symbol": symbol, "decision_ms": int(h["available_at_ms"]),
                           "e1_fired": int(h["available_at_ms"]) in fired_by[symbol],
                           "entry_valid": int(h["available_at_ms"]) in opens_by[symbol],
                           "entry_price": opens_by[symbol].get(int(h["available_at_ms"]))}
                          for h in hours if START_MS <= int(h["available_at_ms"]) < END_MS]
    return result


def _reference_analysis(entries: list[dict], candidates_by: dict, opens_by: dict) -> tuple[dict, dict]:
    entry_ms_by = defaultdict(list)
    for e in entries: entry_ms_by[e["symbol"]].append(int(e["entry_execution_ms"]))
    indexed = {}
    for symbol, candidates in candidates_by.items():
        groups = defaultdict(list)
        for candidate in candidates:
            groups[(_month(candidate["decision_ms"]), _hour(candidate["decision_ms"]))].append(candidate)
        indexed[symbol] = groups
    paired = {}; pools = []
    for horizon in HORIZONS:
        rows = []
        for e in entries:
            symbol = e["symbol"]; ems = int(e["entry_execution_ms"])
            pool = reference_pool(e, indexed[symbol][(_month(ems), _hour(ems))], entry_ms_by[symbol], horizon)
            pools.append({"trade_id": e["trade_id"], "symbol": symbol, "year": _year(int(e["entry_execution_ms"])),
                          "horizon": horizon, "pool_size": len(pool)})
            actual = {c: fixed_horizon_outcome(int(e["entry_execution_ms"]), float(e["entry_price"]), horizon, opens_by[symbol], c) for c in COST_IDS}
            if not pool or any(x is None for x in actual.values()):
                continue
            references = {c: [fixed_horizon_outcome(x["decision_ms"], float(x["entry_price"]), horizon, opens_by[symbol], c) for x in pool] for c in COST_IDS}
            if any(any(v is None for v in values) for values in references.values()):
                raise RuntimeError("reference horizon eligibility error")
            refmean = {c: {"return": statistics.fmean(x["return"] for x in references[c]),
                           "pnl_usdt": statistics.fmean(x["pnl_usdt"] for x in references[c])} for c in COST_IDS}
            rows.append({"trade_id": e["trade_id"], "symbol": symbol, "year": _year(int(e["entry_execution_ms"])),
                         "entry_month": _month(int(e["entry_execution_ms"])), "pool_size": len(pool),
                         "actual": actual, "reference": refmean})
        paired[horizon] = rows
    return paired, pools


def _arm_summary(rows: list[dict], arm: str, cost: str) -> dict:
    shaped = [{"return": r[arm][cost]["return"], "pnl_usdt": r[arm][cost]["pnl_usdt"]} for r in rows]
    return return_summary(shaped)


def _advantage_document(horizon: int, rows: list[dict]) -> dict:
    return {"horizon_hours": horizon, "primary": horizon == PRIMARY_HORIZON,
            "covered_trade_count": len(rows), "shared_reference_pools_may_overlap": True,
            "by_cost": {c: {"actual": _arm_summary(rows, "actual", c), "matched_reference": _arm_summary(rows, "reference", c),
                            "paired_advantage": paired_summary(rows, c)} for c in COST_IDS}}


def _coverage(pools: list[dict], paired: dict) -> dict:
    result = {}
    for h in HORIZONS:
        rr = [r for r in pools if r["horizon"] == h]
        def one(ss):
            sizes = [r["pool_size"] for r in ss]
            return {"entries": len(ss), "covered": sum(x > 0 for x in sizes), "zero_pool": sum(x == 0 for x in sizes),
                    "coverage_fraction": sum(x > 0 for x in sizes) / len(sizes) if sizes else None,
                    "min_pool_size": min(sizes) if sizes else None, "median_pool_size": statistics.median(sizes) if sizes else None,
                    "max_pool_size": max(sizes) if sizes else None}
        covered_ids = {r["trade_id"] for r in paired[h]}
        result[f"H{h}"] = {"full_population": {**one(rr), "covered_comparison_population": len(covered_ids)},
                            "by_year": {str(y): one([r for r in rr if r["year"] == y]) for y in (2024, 2025)},
                            "by_symbol": {s: one([r for r in rr if r["symbol"] == s]) for s in sorted({r["symbol"] for r in rr})}}
    return result


def _actual_rows(entries: list[dict], opens_by: dict) -> dict:
    result = {}
    for horizon in HORIZONS:
        rows = []
        for e in entries:
            outcomes = {c: fixed_horizon_outcome(int(e["entry_execution_ms"]), float(e["entry_price"]), horizon, opens_by[e["symbol"]], c) for c in COST_IDS}
            if any(x is None for x in outcomes.values()):
                continue
            rows.append({"trade_id": e["trade_id"], "symbol": e["symbol"], "year": _year(int(e["entry_execution_ms"])),
                         "entry_month": _month(int(e["entry_execution_ms"])), "actual": outcomes})
        result[horizon] = rows
    return result


def _actual_economics(actual_rows: dict) -> dict:
    out = {}
    for h, rows in actual_rows.items():
        out[f"H{h}"] = {c: {"full_population": _arm_summary(rows, "actual", c),
                              "by_year": {str(y): _arm_summary([r for r in rows if r["year"] == y], "actual", c) for y in (2024, 2025)},
                              "by_symbol": {s: _arm_summary([r for r in rows if r["symbol"] == s], "actual", c) for s in sorted({r["symbol"] for r in rows})}}
                         for c in COST_IDS}
    return out


def _retention(entries: list[dict], p0: list[dict], actual_rows: dict) -> dict:
    p0_by = {(r["trade_id"], r["cost_scenario"]): r for r in p0 if r["censored"].lower() == "false"}
    result = {}
    for h, rows in actual_rows.items():
        result[f"H{h}"] = {}
        for cost in ("C0", "C_BASE"):
            values = []
            for r in rows:
                p = p0_by[(r["trade_id"], cost)]; diff = float(p["net_return"]) - r["actual"][cost]["return"]
                p0_pnl = float(p["quantity"]) * float(p["exit_price_after_slippage"]) - float(p["exit_fee_usdt"]) - NOTIONAL - float(p["entry_fee_usdt"])
                values.append({"return": diff, "pnl_usdt": p0_pnl - r["actual"][cost]["pnl_usdt"],
                               "year": r["year"], "symbol": r["symbol"]})
            result[f"H{h}"][cost] = {"full_population": return_summary(values),
                                      "by_year": {str(y): return_summary([x for x in values if x["year"] == y]) for y in (2024, 2025)},
                                      "by_symbol": {s: return_summary([x for x in values if x["symbol"] == s]) for s in sorted({x["symbol"] for x in values})}}
    return result


def _threshold_crossing_times(repo: Path, entries: list[dict], p0: list[dict]) -> dict[float, list[int]]:
    """Retrospectively locate first crossings; these timestamps never drive an exit."""
    p0_c0 = {r["trade_id"]: r for r in p0 if r["cost_scenario"] == "C0"}
    thresholds = (.005, .01, .02, .03); result = {x: [] for x in thresholds}
    for symbol in sorted({e["symbol"] for e in entries}):
        pending = sorted([{"trade_id": e["trade_id"], "entry_ms": int(e["entry_execution_ms"]),
                           "entry_price": float(e["entry_price"]), "exit_ms": int(p0_c0[e["trade_id"]]["common_horizon_end_ms"]),
                           "unresolved": set(thresholds)} for e in entries if e["symbol"] == symbol], key=lambda x: x["entry_ms"])
        active = []; cursor = 0
        path = repo / "data/normalized/c2_history" / f"{symbol}_1m.csv.gz"; reject_2026(path)
        for minute in iter_gzip_csv(path):
            ts = int(minute["open_time_ms"])
            if ts >= END_MS: break
            while cursor < len(pending) and pending[cursor]["entry_ms"] < ts:
                active.append(pending[cursor]); cursor += 1
            if not active: continue
            kept = []
            for trade in active:
                if ts > trade["exit_ms"]: continue
                price = float(minute["high"]) if ts < trade["exit_ms"] else float(minute["open"])
                gain = price / trade["entry_price"] - 1
                for threshold in tuple(trade["unresolved"]):
                    if gain >= threshold:
                        result[threshold].append((ts - trade["entry_ms"]) // 1000); trade["unresolved"].remove(threshold)
                if ts < trade["exit_ms"]: kept.append(trade)
            active = kept
    return result


def _mfe(entries: list[dict], horizons: list[dict], p0: list[dict], crossing_times: dict) -> tuple[dict, dict, dict]:
    h_by = {r["trade_id"]: r for r in horizons}; p0_by = {(r["trade_id"], r["cost_scenario"]): r for r in p0}
    rows = []
    for e in entries:
        h = h_by[e["trade_id"]]; mfe = float(h["held_mfe"]); c0 = float(p0_by[(e["trade_id"], "C0")]["net_return"]); cb = float(p0_by[(e["trade_id"], "C_BASE")]["net_return"])
        rows.append({"trade_id": e["trade_id"], "symbol": e["symbol"], "year": _year(int(e["entry_execution_ms"])),
                     "mfe": mfe, "p0_c0": c0, "p0_cbase": cb})
    thresholds = {}
    for threshold in (.005, .01, .02, .03):
        cohort = [r for r in rows if r["mfe"] >= threshold]; key = f">={threshold:.3f}"
        if len(crossing_times[threshold]) != len(cohort):
            raise RuntimeError("MFE threshold crossing reconstruction mismatch")
        thresholds[key] = {"trade_count": len(cohort), "fraction_of_entries": len(cohort) / len(rows),
                           "year_counts": dict(sorted(Counter(str(r["year"]) for r in cohort).items())),
                           "symbol_counts": dict(sorted(Counter(r["symbol"] for r in cohort).items())),
                           "median_time_to_first_threshold_crossing_seconds": statistics.median(crossing_times[threshold]) if crossing_times[threshold] else None,
                           "crossing_time_note": "retrospectively reconstructed from frozen 1m highs (or exact P0 execution open); descriptive only",
                           "mean_mfe": statistics.fmean(r["mfe"] for r in cohort) if cohort else None,
                           "mean_p0_c0_return": statistics.fmean(r["p0_c0"] for r in cohort) if cohort else None,
                           "median_p0_c0_return": statistics.median(r["p0_c0"] for r in cohort) if cohort else None,
                           "mean_p0_cbase_return": statistics.fmean(r["p0_cbase"] for r in cohort) if cohort else None,
                           "median_p0_cbase_return": statistics.median(r["p0_cbase"] for r in cohort) if cohort else None,
                           "p0_c0_positive_fraction": sum(r["p0_c0"] > 0 for r in cohort) / len(cohort) if cohort else None,
                           "p0_cbase_positive_fraction": sum(r["p0_cbase"] > 0 for r in cohort) / len(cohort) if cohort else None,
                           "mean_mfe_surrender_gap": statistics.fmean(r["mfe"] - r["p0_c0"] for r in cohort) if cohort else None}
    positive = [r for r in rows if r["mfe"] > 0]; ratios = [r["p0_c0"] / r["mfe"] for r in positive]; gaps = [r["mfe"] - r["p0_c0"] for r in positive]
    capture = {"population_mfe_gt_zero": len(positive), "ratio_not_clipped": True, "median": statistics.median(ratios),
               "p25": _quantile(ratios, .25), "p75": _quantile(ratios, .75),
               "fraction_lt_0": sum(x < 0 for x in ratios) / len(ratios), "fraction_gte_0": sum(x >= 0 for x in ratios) / len(ratios),
               **{f"fraction_gte_{q:.2f}": sum(x >= q for x in ratios) / len(ratios) for q in (.25, .5, .75, 1.)},
               "mfe_surrender_gap_mean": statistics.fmean(gaps), "mfe_surrender_gap_median": statistics.median(gaps),
               "warning": "MFE is retrospective/descriptive and is not an executable or capturable exit."}
    descriptive = {"construction": "exact frozen C2 held_mfe through canonical P0 execution", "retrospective_only": True,
                   "never_used_as_exit": True, "threshold_frequencies": {k: {x: v[x] for x in ("trade_count", "fraction_of_entries", "year_counts", "symbol_counts", "median_time_to_first_threshold_crossing_seconds", "crossing_time_note")} for k, v in thresholds.items()}}
    return descriptive, thresholds, capture


def run(repo: Path) -> dict:
    repo = repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("conda environment must be binance-v2-research")
    if sha256_file(repo / CONTRACT_REL) != CONTRACT_SHA256:
        raise RuntimeError("C28 contract changed after prospective freeze")
    entries, p0, horizons = _load_entries_and_p0(repo)
    hours_by, opens_by, fired_by, population = _hourly_inputs(repo, entries)
    p0_rows, p0_rec = _p0_rows(entries, p0)
    candidates = _candidate_states(hours_by, opens_by, fired_by)
    paired, pool_rows = _reference_analysis(entries, candidates, opens_by)
    actual_rows = _actual_rows(entries, opens_by)
    advantages = {h: _advantage_document(h, paired[h]) for h in HORIZONS}; coverage = _coverage(pool_rows, paired)
    p0_economics = {c: _groups(p0_rows, c)["full_population"] for c in COST_IDS}
    p0_year = {c: _groups(p0_rows, c)["by_year"] for c in COST_IDS}; p0_symbol = {c: _groups(p0_rows, c)["by_symbol"] for c in COST_IDS}
    drag = {c: {"mean_return_degradation_from_C0": p0_economics["C0"]["mean_return"] - p0_economics[c]["mean_return"],
                "total_pnl_degradation_from_C0_usdt": p0_economics["C0"]["total_pnl_usdt"] - p0_economics[c]["total_pnl_usdt"]} for c in ("C_BASE", "C_S5", "C_S10")}
    cost_flip = {scope: p0_year["C0"][scope]["mean_return"] > 0 and p0_year["C_BASE"][scope]["mean_return"] <= 0 for scope in ("2024", "2025")}
    cost_flip["full_population"] = p0_economics["C0"]["mean_return"] > 0 and p0_economics["C_BASE"]["mean_return"] <= 0
    actual = _actual_economics(actual_rows); retention = _retention(entries, p0, actual_rows)
    crossing_times = _threshold_crossing_times(repo, entries, p0)
    mfe_desc, mfe_thresholds, mfe_capture = _mfe(entries, horizons, p0, crossing_times)
    h24 = paired[24]
    month_boot = {scope: bootstrap([r for r in h24 if scope == "pooled" or r["year"] == int(scope)], "calendar_month") for scope in ("2024", "2025", "pooled")}
    whole_boot = {scope: bootstrap([r for r in h24 if scope == "pooled" or r["year"] == int(scope)], "whole_entry") for scope in ("2024", "2025", "pooled")}
    h24_adv = {scope: paired_summary([r for r in h24 if scope == "pooled" or r["year"] == int(scope)], "C_BASE") for scope in ("2024", "2025", "pooled")}
    symbol_adv = {s: paired_summary([r for r in h24 if r["symbol"] == s], "C_BASE") for s in sorted({r["symbol"] for r in h24})}
    no_material_negative = month_boot["pooled"]["intervals"]["C_BASE"]["ci95"][1] >= 0
    entry_supported = all(h24_adv[x]["mean_entry_advantage"] > 0 for x in ("2024", "2025", "pooled")) and no_material_negative and all(v["mean_entry_advantage"] > 0 for v in symbol_adv.values())
    actual_h24 = actual["H24"]["C_BASE"]
    actual_boot = _actual_bootstrap(actual_rows[24])
    opportunity = entry_supported and all(actual_h24["by_year"][str(y)]["mean_return"] > 0 for y in (2024, 2025)) and actual_h24["full_population"]["mean_return"] > 0 and actual_boot["ci95"][1] >= 0
    direction = strategy_decision(entry_supported, opportunity, p0_economics["C_BASE"]["mean_return"])
    out = repo / OUTPUT_REL; out.mkdir(parents=True, exist_ok=True)
    definition = {"mechanism_count": 1, "same_symbol": True, "same_utc_calendar_month": True, "same_utc_hour_of_day": True,
                  "requires_e1_not_fire": True, "exclusion_from_any_same_symbol_e1_hours": 24, "exclusion_inclusive": True,
                  "valid_1m_entry_required": True, "future_horizon_data_required": True, "dataset": "frozen 2024-2025 only",
                  "selection": "all eligible controls; equal-weight deterministic mean", "future_matching": False,
                  "overlap": "an eligible reference may serve multiple actual entries"}
    timing = {"hourly_state_timestamp": "available_at_ms of completed hourly bar", "entry": "first valid 1m open at or after hourly available_at_ms (the next minute open after the completed interval)",
              "exit": "first valid 1m open at or after entry decision timestamp plus H", "horizons_hours": list(HORIZONS), "primary": "H24", "mfe_exit": False}
    files = {
        "run_manifest": {"version": "C28_RUN_V1", "contract_sha256": CONTRACT_SHA256, "seed": SEED, "replicates": REPLICATES, "generator": "PCG64", "python": sys.version, "numpy": np.__version__, "platform": platform.platform(), "conda_environment": "binance-v2-research"},
        "provenance": {"contract_sha256": CONTRACT_SHA256, "frozen_entry_sha256": ENTRY_SHA256, "c2_p0_summary_sha256": sha256_file(repo / C2_REL / "p0_summary.json"), "no_2026_access": True},
        "population_reconciliation": {**population, "p0": p0_rec}, "p0_cost_economics": p0_economics,
        "p0_year_results": p0_year, "p0_symbol_results": p0_symbol,
        "p0_cost_drag": {"P0_COST_DRAG": drag["C_BASE"], "degradation_relative_to_C0": drag, "COST_FLIPS_P0": cost_flip, "cost_flip_not_proof_costs_are_only_problem": True},
        "reference_control_definition": definition,
        "reference_pool_reconciliation": {"actual_trade_horizon_rows": len(pool_rows), "expected": EXPECTED_ENTRIES * len(HORIZONS), "exact": len(pool_rows) == EXPECTED_ENTRIES * len(HORIZONS), "pool_sizes_semantic_sha256": _semantic_sha(pool_rows), "zero_pools_retained_outside_layer2": True},
        "reference_pool_coverage": coverage, "fixed_horizon_timing": timing,
        **{f"entry_advantage_h{h}": advantages[h] for h in HORIZONS},
        "entry_advantage_year_results": {f"H{h}": {c: {str(y): paired_summary([r for r in paired[h] if r["year"] == y], c) for y in (2024, 2025)} for c in COST_IDS} for h in HORIZONS},
        "entry_advantage_symbol_results": {f"H{h}": {c: {s: paired_summary([r for r in paired[h] if r["symbol"] == s], c) for s in sorted({r["symbol"] for r in paired[h]})} for c in COST_IDS} for h in HORIZONS},
        "entry_advantage_calendar_month_bootstrap": month_boot, "entry_advantage_whole_entry_bootstrap": whole_boot,
        "actual_entry_fixed_horizon_economics": {**actual, "H24_CBASE_calendar_month_actual_mean_ci95": actual_boot},
        "mfe_descriptive": mfe_desc, "mfe_threshold_results": mfe_thresholds,
        "p0_fixed_horizon_retention": retention, "p0_mfe_retention": mfe_capture,
        "strategy_decision_predicates": {"ENTRY_ADVANTAGE_SUPPORTED": entry_supported, "ENTRY_OPPORTUNITY_SURVIVES_COSTS": opportunity,
                                         "canonical_P0_CBASE_mean_return": p0_economics["C_BASE"]["mean_return"], "frozen_strategy_direction": direction,
                                         "h24_primary": True, "no_model_fitting": True, "no_policy_simulation": True, "no_best_horizon": True},
    }
    files["final_summary"] = {"contract_sha256": CONTRACT_SHA256, "population_reconciliation": population, "p0_economics": p0_economics,
                              "cost_flip": cost_flip, "reference_definition": definition, "reference_coverage": coverage,
                              "H24": advantages[24], "H24_year_advantage_CBASE": h24_adv, "H24_calendar_month_uncertainty": month_boot,
                              "diagnostic_horizons": {f"H{h}": advantages[h] for h in (6, 72, 168)},
                              "actual_H24_CBASE": actual_h24, "actual_H24_CBASE_uncertainty": actual_boot,
                              "ENTRY_ADVANTAGE_SUPPORTED": entry_supported, "ENTRY_OPPORTUNITY_SURVIVES_COSTS": opportunity,
                              "mfe": mfe_desc, "p0_mfe_retention": mfe_capture, "p0_fixed_horizon_retention": retention,
                              "matched_control_limitations": ["shared reference pools", "imperfect regime matching", "month/hour matching granularity", "not a fully identified causal counterfactual"],
                              "frozen_strategy_direction": direction, "C29": "NOT_STARTED",
                              "confirmations": {"alternate_control_horizon_model_policy_search": False, "pnl_optimization": False, "accessed_2026": False, "mfe_used_as_exit": False, "implementation_staged_committed_or_pushed": False}}
    for name, value in files.items(): _write(out / f"{name}.json", value)
    hashes = {p.name: sha256_file(p) for p in sorted(out.glob("*.json")) if p.name != "reproducibility_hashes.json"}
    _write(out / "reproducibility_hashes.json", hashes)
    return files["final_summary"] | {"artifact_hashes": hashes}


def _actual_bootstrap(rows: list[dict], seed: int = SEED, replicates: int = REPLICATES) -> dict:
    groups = defaultdict(list)
    for i, r in enumerate(rows): groups[r["entry_month"]].append(i)
    labels = sorted(groups); rng = np.random.Generator(np.random.PCG64(seed)); values = []
    for _ in range(replicates):
        ix = [i for j in rng.integers(len(labels), size=len(labels)) for i in groups[labels[int(j)]]]
        values.append(statistics.fmean(rows[i]["actual"]["C_BASE"]["return"] for i in ix))
    a = np.asarray(values, float)
    return {"unit": "UTC_entry_calendar_month", "seed": seed, "generator": "PCG64", "replicates": replicates,
            "ci95": np.quantile(a, [.025, .975], method="linear").tolist(), "replicate_sha256": hashlib.sha256(a.astype("<f8").tobytes()).hexdigest()}
