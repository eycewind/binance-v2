"""C29 fixed-horizon executable-opportunity prevalence audit.

MFE is retrospective and is not used as a C29 target, policy, or opportunity label.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .c2_common import ENTRY_COLUMNS, hash_rows, iter_gzip_csv
from .c2_costs import COST_SCENARIOS, CostScenario, apply_round_trip_costs
from .c2_entries import hourly_sma24
from .ingest import sha256_file

CONTRACT_REL = "contracts/C29_opportunity_prevalence_CONTRACT.md"
CONTRACT_SHA256 = "8d0ee3cd336b95a61147622d66f6b8ec30787c7e07d26e41348debd52dccb19d"
ENTRY_REL = "artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv"
ENTRY_SHA256 = "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
OUTPUT_REL = "artifacts/c29_opportunity_prevalence"
EXPECTED_ENTRIES = 2199
EXPECTED_YEARS = {2024: 1093, 2025: 1106}
EXPECTED_SYMBOLS = {"BNBUSDT": 442, "BTCUSDT": 451, "ETHUSDT": 434, "SOLUSDT": 431, "XRPUSDT": 441}
HORIZONS = (3, 6, 12, 24)
COST_IDS = ("C0", "C_BASE", "C_S5", "C_S10")
DESIGN_BNB = CostScenario("DESIGN_BNB", .00075, .0002)
ALL_COST_IDS = ("C0", "DESIGN_BNB", "C_BASE", "C_S5", "C_S10")
HURDLES = {"GROSS40": .004, "GROSS50": .005}
POSITIVE_LADDER = (.002, .004, .005, .0075, .01, .015, .02)
NEGATIVE_LADDER = (-.002, -.004, -.005, -.0075, -.01, -.015, -.02)
SEED = 20260929
REPLICATES = 2000
NOTIONAL = 1000.0
END_MS = 1767225600000


def reject_2026(path: os.PathLike | str) -> None:
    if any("2026" in p.lower() for p in os.fspath(path).replace("\\", "/").split("/")):
        raise PermissionError("C29 prohibits 2026 data or metadata access")


def _year(ms: int) -> int: return datetime.fromtimestamp(ms / 1000, timezone.utc).year
def _month(ms: int) -> str: return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")
def _q(v: list[float], p: float): return float(np.quantile(v, p, method="linear")) if v else None
def _semantic(v: object) -> str: return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def opportunity_label(value: float, hurdle: float) -> bool:
    return value >= hurdle


def cost_outcome(entry: float, exit_: float, cost_id: str) -> dict:
    scenarios = {x.scenario_id: x for x in COST_SCENARIOS} | {DESIGN_BNB.scenario_id: DESIGN_BNB}
    c = apply_round_trip_costs(entry, exit_, NOTIONAL, scenarios[cost_id])
    pnl = c["quantity"] * c["exit_price_after_slippage"] - c["exit_fee_usdt"] - NOTIONAL - c["entry_fee_usdt"]
    return {"return": float(c["net_return"]), "pnl_usdt": float(pnl)}


def return_summary(rows: list[dict], cost: str) -> dict:
    values = [r["returns"][cost] for r in rows]; pnls = [r["pnls"][cost] for r in rows]
    return {"trade_count": len(rows), "mean": statistics.fmean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "p10": _q(values, .1), "p25": _q(values, .25), "p75": _q(values, .75), "p90": _q(values, .9),
            "positive_fraction": sum(x > 0 for x in values) / len(values) if values else None,
            "negative_fraction": sum(x < 0 for x in values) / len(values) if values else None,
            "exact_zero_fraction": sum(x == 0 for x in values) / len(values) if values else None,
            "total_pnl_usdt": float(sum(pnls))}


def _scoped(rows: list[dict], fn) -> dict:
    return {"full_population": fn(rows),
            "by_year": {str(y): fn([r for r in rows if r["year"] == y]) for y in (2024, 2025)},
            "by_symbol": {s: fn([r for r in rows if r["symbol"] == s]) for s in EXPECTED_SYMBOLS}}


def _load_and_reconcile(repo: Path) -> tuple[list[dict], dict, dict[str, dict[int, float]]]:
    path = repo / ENTRY_REL
    if sha256_file(path) != ENTRY_SHA256: raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    with path.open(encoding="utf-8", newline="") as f: entries = list(csv.DictReader(f))
    years = Counter(_year(int(e["entry_execution_ms"])) for e in entries); symbols = Counter(e["symbol"] for e in entries)
    basic = (len(entries) == len({e["trade_id"] for e in entries}) == EXPECTED_ENTRIES and
             hash_rows(entries, ENTRY_COLUMNS) == ENTRY_SHA256 and dict(years) == EXPECTED_YEARS and dict(symbols) == EXPECTED_SYMBOLS)
    opens = {}; reproduction = []
    for symbol in EXPECTED_SYMBOLS:
        source = repo / "data/normalized/c2_frozen_inputs" / f"{symbol}_1h.csv.gz"; reject_2026(source)
        hours = [r for r in iter_gzip_csv(source) if int(r["open_time_ms"]) < END_MS]
        if any(int(r["open_time_ms"]) + 3_600_000 != int(r["available_at_ms"]) for r in hours):
            raise RuntimeError("invalid completed-hour timing")
        opens[symbol] = {int(r["open_time_ms"]): float(r["open"]) for r in hours}
        sma = hourly_sma24(hours); fired = []
        for i in range(1, len(hours)):
            if sma[i] is not None and sma[i-1] is not None and float(hours[i]["close"]) > sma[i] and float(hours[i-1]["close"]) <= sma[i-1]:
                fired.append(int(hours[i]["available_at_ms"]))
        last = None
        for ms in fired:
            if ms not in opens[symbol]: continue
            if last is None or ms - last >= 24 * 3_600_000:
                if _year(ms) in (2024, 2025): reproduction.append((symbol, ms, opens[symbol][ms]))
                last = ms
    expected = sorted((e["symbol"], int(e["entry_execution_ms"]), float(e["entry_price"])) for e in entries)
    reproduced = sorted(reproduction); exact = basic and expected == reproduced
    rec = {"status": "PASS" if exact else "INSUFFICIENT_RECONCILIATION", "original_trade_count": len(entries),
           "unique_trade_count": len({e["trade_id"] for e in entries}), "frozen_entry_file_sha256": sha256_file(path),
           "semantic_entry_sha256": hash_rows(entries, ENTRY_COLUMNS), "expected_entry_sha256": ENTRY_SHA256,
           "year_counts": {str(k): v for k, v in sorted(years.items())}, "symbol_counts": dict(sorted(symbols.items())),
           "timestamps_prices_and_24h_refractory_exact": expected == reproduced, "reproduced_count": len(reproduced)}
    if not exact: raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    return entries, rec, opens


def build_rows(entries: list[dict], opens: dict[str, dict[int, float]]) -> tuple[dict[int, list[dict]], dict]:
    out = {}; coverage = {}
    for h in HORIZONS:
        rows = []; unavailable = []
        for e in entries:
            decision = int(e["entry_execution_ms"]); target = decision + h * 3_600_000
            # Exact C28 convention; frozen boundaries must exist. No search and no synthetic fill.
            if target >= END_MS or target not in opens[e["symbol"]]:
                unavailable.append(e); continue
            entry = float(e["entry_price"]); exit_ = opens[e["symbol"]][target]
            outcomes = {c: cost_outcome(entry, exit_, c) for c in ALL_COST_IDS}
            c0 = outcomes["C0"]["return"]
            rows.append({"trade_id": e["trade_id"], "symbol": e["symbol"], "year": _year(decision), "entry_month": _month(decision),
                         "entry_decision_ms": decision, "entry_fill_ms": decision, "horizon_end_ms": target, "exit_fill_ms": target,
                         "entry_price": entry, "exit_price": exit_, "returns": {c: outcomes[c]["return"] for c in ALL_COST_IDS},
                         "pnls": {c: outcomes[c]["pnl_usdt"] for c in ALL_COST_IDS},
                         "labels": {k: opportunity_label(c0, v) for k, v in HURDLES.items()}})
        out[h] = rows
        coverage[f"H{h}"] = {"original_trade_count": len(entries), "valid_executable_trade_count": len(rows),
                              "unavailable_trade_count": len(unavailable),
                              "valid_by_year": dict(sorted(Counter(str(r["year"]) for r in rows).items())),
                              "valid_by_symbol": dict(sorted(Counter(r["symbol"] for r in rows).items()))}
    return out, coverage


def prevalence(rows: list[dict], label: str) -> dict:
    def one(rr):
        n = len(rr); count = sum(r["labels"][label] for r in rr)
        return {"valid_count": n, "opportunity_count": count, "prevalence": count / n if n else None}
    result = _scoped(rows, one)
    result["by_entry_month"] = {m: one([r for r in rows if r["entry_month"] == m]) for m in sorted({r["entry_month"] for r in rows})}
    return result


def magnitude(rows: list[dict], label: str, positive: bool) -> dict:
    rr = [r for r in rows if r["labels"][label] is positive]; vals = [r["returns"]["C0"] for r in rr]
    hurdle = HURDLES[label]
    return {"group": "at_or_above_hurdle" if positive else "below_hurdle", "trade_count": len(rr),
            "mean_C0": statistics.fmean(vals) if vals else None, "median_C0": statistics.median(vals) if vals else None,
            "p25_C0": _q(vals, .25), "p75_C0": _q(vals, .75), "p90_C0": _q(vals, .9),
            "mean_excess_above_hurdle": statistics.fmean([x-hurdle for x in vals]) if vals else None,
            "median_excess_above_hurdle": statistics.median([x-hurdle for x in vals]) if vals else None,
            "total_gross_pnl_usdt": float(sum(r["pnls"]["C0"] for r in rr))}


def cost_survival(rows: list[dict], label: str) -> dict:
    rr = [r for r in rows if r["labels"][label]]
    return {c: {k: v for k, v in return_summary(rr, c).items() if k in ("trade_count", "mean", "median", "positive_fraction", "total_pnl_usdt")}
            for c in ("DESIGN_BNB", "C_BASE", "C_S5", "C_S10")}


def threshold_ladder(rows: list[dict], thresholds: tuple[float, ...], positive: bool) -> dict:
    result = {}
    for t in thresholds:
        key = (">=" if positive else "<=") + f"{t:+.4f}"
        def one(rr):
            n = len(rr); count = sum((r["returns"]["C0"] >= t) if positive else (r["returns"]["C0"] <= t) for r in rr)
            return {"valid_count": n, "count": count, "prevalence": count/n if n else None}
        result[key] = {"full_population": one(rows), "by_year": {str(y): one([r for r in rows if r["year"] == y]) for y in (2024, 2025)}}
    return result


def asymmetry(rows: list[dict]) -> dict:
    out = {}
    for cost in ("C0", "DESIGN_BNB", "C_BASE"):
        values = [r["returns"][cost] for r in rows]; pos = [x for x in values if x > 0]; neg = [x for x in values if x < 0]
        pos_total = sum(pos) * NOTIONAL; neg_total = sum(neg) * NOTIONAL
        item = {"mean_positive_return": statistics.fmean(pos) if pos else None, "mean_negative_return": statistics.fmean(neg) if neg else None,
                "total_positive_contribution_usdt": pos_total, "total_negative_contribution_usdt": neg_total,
                "positive_to_absolute_negative_contribution_ratio": pos_total / abs(neg_total) if neg_total else None}
        for label in HURDLES:
            contribution = sum(max(r["returns"][cost], 0) for r in rows if r["labels"][label]) * NOTIONAL
            item[f"positive_contribution_fraction_from_{label}"] = contribution / pos_total if pos_total else None
        out[cost] = item
    return out


def concentration(rows: list[dict], label: str) -> dict:
    rr = [r for r in rows if r["labels"][label]]; vals = sorted((max(r["returns"]["C0"], 0) * NOTIONAL for r in rr), reverse=True); total = sum(vals)
    def share(n): return sum(vals[:min(n, len(vals))]) / total if total else None
    cumulative = 0.; n50 = 0
    for x in vals:
        cumulative += x; n50 += 1
        if cumulative >= total * .5: break
    return {"opportunity_count": len(rr), "top_1_trade_share": share(1), "top_5_trades_share": share(5), "top_10_trades_share": share(10),
            "top_1_percent_share": share(max(1, int(np.ceil(len(vals)*.01)))) if vals else None,
            "top_5_percent_share": share(max(1, int(np.ceil(len(vals)*.05)))) if vals else None,
            "top_10_percent_share": share(max(1, int(np.ceil(len(vals)*.10)))) if vals else None,
            "trades_required_for_50_percent": n50 if vals else 0,
            "months_with_at_least_one": len({r["entry_month"] for r in rr})}


def bootstrap(rows: list[dict], unit: str, seed: int = SEED, replicates: int = REPLICATES) -> dict:
    if unit not in ("whole_trade", "UTC_entry_calendar_month"): raise ValueError(unit)
    groups = defaultdict(list)
    for i, r in enumerate(rows): groups[r["trade_id"] if unit == "whole_trade" else r["entry_month"]].append(i)
    labels = sorted(groups); rng = np.random.Generator(np.random.PCG64(seed)); samples = np.empty((replicates, 5))
    for b in range(replicates):
        indices = [i for j in rng.integers(len(labels), size=len(labels)) for i in groups[labels[int(j)]]]
        samples[b] = [statistics.fmean(rows[i]["returns"][c] for i in indices) for c in ("C0", "DESIGN_BNB", "C_BASE")] + [statistics.fmean(rows[i]["labels"][l] for i in indices) for l in HURDLES]
    names = ("mean_C0", "mean_DESIGN_BNB", "mean_C_BASE", "GROSS40_prevalence", "GROSS50_prevalence")
    return {"unit": unit, "seed": seed, "generator": "PCG64", "replicates": replicates,
            "complete_trades_and_all_horizons_preserved": True,
            "intervals": {name: {"ci95": np.quantile(samples[:, i], [.025, .975], method="linear").tolist(),
                                  "replicate_sha256": hashlib.sha256(samples[:, i].astype("<f8").tobytes()).hexdigest()} for i, name in enumerate(names)}}


def _bootstrap_document(all_rows: dict[int, list[dict]], unit: str) -> dict:
    # Resampling keys are generated once per horizon population; each row carries all cost/label outcomes.
    return {f"H{h}": {scope: bootstrap([r for r in all_rows[h] if scope == "pooled" or r["year"] == int(scope)], unit)
                       for scope in ("2024", "2025", "pooled")} for h in HORIZONS}


def run(repo: Path) -> dict:
    repo = repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    if sha256_file(repo / CONTRACT_REL) != CONTRACT_SHA256: raise RuntimeError("C29 contract changed after prospective freeze")
    entries, reconciliation, opens = _load_and_reconcile(repo)
    rows, coverage = build_rows(entries, opens)
    economics = {f"H{h}": {c: _scoped(rows[h], lambda rr, cc=c: return_summary(rr, cc)) for c in ALL_COST_IDS} for h in HORIZONS}
    for h in HORIZONS:
        key = f"H{h}"; c0 = economics[key]["C0"]["full_population"]
        economics[key]["cost_drag_from_C0"] = {
            c: {"mean_return_drag": c0["mean"] - economics[key][c]["full_population"]["mean"],
                "total_pnl_drag_usdt": c0["total_pnl_usdt"] - economics[key][c]["full_population"]["total_pnl_usdt"]}
            for c in ("DESIGN_BNB", "C_BASE", "C_S5", "C_S10")}
    prevalence_doc = {f"H{h}": {l: prevalence(rows[h], l) for l in HURDLES} | {"GROSS40_GROSS50_intersection_count": sum(r["labels"]["GROSS40"] and r["labels"]["GROSS50"] for r in rows[h])} for h in HORIZONS}
    magnitude_doc = {f"H{h}": {l: {"positive": magnitude(rows[h], l, True), "below": magnitude(rows[h], l, False)} for l in HURDLES} for h in HORIZONS}
    survival = {f"H{h}": {l: cost_survival(rows[h], l) for l in HURDLES} for h in HORIZONS}
    positive = {f"H{h}": threshold_ladder(rows[h], POSITIVE_LADDER, True) for h in HORIZONS}
    negative = {f"H{h}": threshold_ladder(rows[h], NEGATIVE_LADDER, False) for h in HORIZONS}
    asym = {f"H{h}": asymmetry(rows[h]) for h in HORIZONS}
    concentration_doc = {f"H{h}": {l: concentration(rows[h], l) for l in HURDLES} for h in HORIZONS}
    month_doc = {f"H{h}": {m: {"valid_count": len(rr), **{l: {"count": sum(r["labels"][l] for r in rr), "prevalence": sum(r["labels"][l] for r in rr)/len(rr), "gross_contribution_usdt": sum(r["pnls"]["C0"] for r in rr if r["labels"][l])} for l in HURDLES}} for m in sorted({r["entry_month"] for r in rows[h]}) for rr in [[r for r in rows[h] if r["entry_month"] == m]]} for h in HORIZONS}
    year_stability = {f"H{h}": {str(y): {"valid_count": len(rr), "mean_whole_C0": return_summary(rr, "C0")["mean"], "mean_DESIGN_BNB": return_summary(rr, "DESIGN_BNB")["mean"], "mean_C_BASE": return_summary(rr, "C_BASE")["mean"], **{l: {"prevalence": prevalence(rr, l)["full_population"]["prevalence"], "mean_gross_opportunity_return": magnitude(rr, l, True)["mean_C0"]} for l in HURDLES}} for y in (2024, 2025) for rr in [[r for r in rows[h] if r["year"] == y]]} for h in HORIZONS}
    symbol_stability = {f"H{h}": {s: {"valid_count": len(rr), "mean_C0": return_summary(rr, "C0")["mean"], "mean_DESIGN_BNB": return_summary(rr, "DESIGN_BNB")["mean"], "mean_C_BASE": return_summary(rr, "C_BASE")["mean"], **{f"{l}_prevalence": prevalence(rr, l)["full_population"]["prevalence"] for l in HURDLES}, **{f"{l}_net_C_BASE_mean": return_summary([r for r in rr if r["labels"][l]], "C_BASE")["mean"] for l in HURDLES}} for s in EXPECTED_SYMBOLS for rr in [[r for r in rows[h] if r["symbol"] == s]]} for h in HORIZONS}
    whole_boot = _bootstrap_document(rows, "whole_trade"); month_boot = _bootstrap_document(rows, "UTC_entry_calendar_month")
    p1 = sum(all(prevalence([r for r in rows[h] if r["year"] == y], "GROSS40")["full_population"]["opportunity_count"] > 0 for y in (2024, 2025)) for h in HORIZONS) >= 2
    p2 = any(all(prevalence([r for r in rows[h] if r["year"] == y], "GROSS50")["full_population"]["opportunity_count"] > 0 for y in (2024, 2025)) for h in HORIZONS)
    p3 = all(survival[f"H{h}"][l]["C_BASE"]["mean"] > 0 for h in HORIZONS for l in HURDLES if any(r["labels"][l] for r in rows[h]))
    p4 = all(concentration_doc[f"H{h}"][l]["months_with_at_least_one"] > 1 and len({r["symbol"] for r in rows[h] if r["labels"][l]}) > 1 for h in HORIZONS for l in HURDLES if any(r["labels"][l] for r in rows[h]))
    p5 = all(any(month_boot[f"H{h}"][str(y)]["intervals"][f"{l}_prevalence"]["ci95"][0] > 0 for h in HORIZONS for l in HURDLES) for y in (2024, 2025))
    classification = "OPPORTUNITY_VARIATION_PRESENT" if all((p1, p2, p3, p4, p5)) else "OPPORTUNITY_TOO_SPARSE_OR_FRAGILE"
    predicates = {"gross40_both_years_at_least_two_horizons": p1, "gross50_both_years_at_least_one_horizon": p2, "opportunity_C_BASE_means_positive": p3, "not_confined_to_one_month_or_symbol": p4, "each_year_has_dependence_aware_positive_lower_bound": p5, "classification": classification}
    timing = {"entry_decision_timestamp_rule": "available_at_ms of the completed E1 hourly bar", "entry_fill_timestamp_rule": "next valid executable 1-minute open; frozen entries fill exactly at decision timestamp", "horizon_anchor": "entry decision timestamp", "horizon_end_timestamp_rule": "entry decision timestamp plus exactly H hours", "exit_fill_rule": "first valid executable 1-minute open at or after endpoint; all included fills occur exactly at endpoint", "no_interpolation": True, "no_synthetic_fills": True, "mfe_exit": False, "horizons_hours": list(HORIZONS)}
    cost_doc = {x.scenario_id: {"explicit_fee_per_leg": x.fee_rate, "adverse_execution_per_leg": x.slippage_rate, "accounting": "frozen c2 apply_round_trip_costs"} for x in COST_SCENARIOS}
    cost_doc["DESIGN_BNB"] = {"explicit_fee_per_leg": .00075, "adverse_execution_per_leg": .0002, "indicative_round_trip_friction_bp": 19, "prespecified_not_fitted": True, "local_to_C29": True}
    fixed_rows = {f"H{h}": rows[h] for h in HORIZONS}
    files = {"run_manifest": {"version": "C29_RUN_V1", "contract_sha256": CONTRACT_SHA256, "seed": SEED, "replicates": REPLICATES, "generator": "PCG64", "python": sys.version, "numpy": np.__version__, "platform": platform.platform(), "conda_environment": "binance-v2-research"},
             "provenance": {"contract_sha256": CONTRACT_SHA256, "frozen_entry_sha256": ENTRY_SHA256, "C28_timing_convention": True, "no_2026_access": True},
             "population_reconciliation": reconciliation, "execution_timing": timing, "cost_scenarios": cost_doc, "horizon_coverage": coverage,
             "fixed_horizon_returns": fixed_rows, "full_population_economics": economics, "opportunity_prevalence": prevalence_doc,
             "opportunity_magnitude": magnitude_doc, "opportunity_cost_survival": survival, "threshold_ladder_positive": positive,
             "threshold_ladder_negative": negative, "contribution_asymmetry": asym, "opportunity_concentration": concentration_doc,
             "entry_month_results": month_doc, "year_stability": year_stability, "symbol_stability": symbol_stability,
             "whole_trade_bootstrap": whole_boot, "calendar_month_bootstrap": month_boot, "interpretation_predicates": predicates}
    files["final_summary"] = {"contract_sha256": CONTRACT_SHA256, "population_reconciliation": reconciliation, "execution_timing": timing,
        "horizon_coverage": coverage, "whole_population_economics": {h: ({c: economics[h][c]["full_population"] for c in ALL_COST_IDS} | {"cost_drag_from_C0": economics[h]["cost_drag_from_C0"]}) for h in economics},
        "opportunity_prevalence": {h: {l: prevalence_doc[h][l]["by_year"] | {"pooled": prevalence_doc[h][l]["full_population"]} for l in HURDLES} for h in prevalence_doc},
        "interpretation_predicates": predicates, "classification": classification,
        "MFE_limitation": "MFE is retrospective and is not used as a C29 target, policy, or opportunity label.",
        "no_preferred_holding_horizon": "No preferred holding horizon was selected.",
        "later_entry_state_prediction_study_justified": classification == "OPPORTUNITY_VARIATION_PRESENT",
        "confirmations": {"model_fitted": False, "threshold_horizon_or_policy_search": False, "pnl_optimization": False, "accessed_2026": False, "C30_started": False}}
    out = repo / OUTPUT_REL; out.mkdir(parents=True, exist_ok=True)
    for name, value in files.items(): _write(out / f"{name}.json", value)
    hashes = {p.name: sha256_file(p) for p in sorted(out.glob("*.json")) if p.name != "reproducibility_hashes.json"}
    _write(out / "reproducibility_hashes.json", hashes)
    return files["final_summary"] | {"artifact_hashes": hashes}


if __name__ == "__main__":
    result = run(Path.cwd())
    print(json.dumps({"classification": result["classification"], "contract_sha256": result["contract_sha256"]}, sort_keys=True))
