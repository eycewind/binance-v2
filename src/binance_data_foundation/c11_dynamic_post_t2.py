"""C11 calibrated dynamic post-T2 prognosis (no economics or policy)."""
from __future__ import annotations

import hashlib, json, os, platform, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c10_post_t2 as c10
from . import c9_dynamic_state as c9
from . import c8_timescale as c8

CONTRACT_SHA256 = "cfb7311cf9799a990c1ee3178025ff7fbd50145665bd33e1e7481316081e6758"
SEED, REPLICATES = 20260930, 2000
NAMES = c10.CONTEXT_FEATURES + c10.FAST_FEATURES
FAMILIES = {
    "5m_returns_momentum": ("context_return_1", "context_return_3", "context_return_6"),
    "5m_volatility_range_activity_trend": ("context_volatility_12", "context_range_ratio", "context_activity_ratio", "context_close_vs_sma12", "context_sma12_slope"),
    "1m_momentum": ("fast_return_1", "fast_return_3", "fast_return_6"),
    "1m_volatility_range_activity": ("fast_volatility_12", "fast_range_ratio", "fast_activity_ratio"),
    "return_since_t2": ("return_since_t2",), "return_from_entry": ("return_from_entry",),
    "running_peak_since_t2": ("new_peak_since_t2",), "drawdown_from_peak": ("drawdown_from_running_peak",),
    "continuation_boundary_distance": ("distance_to_continuation",),
    "deterioration_boundary_distance": ("distance_to_deterioration",),
    "path_efficiency": ("path_efficiency",), "elapsed_time": ("elapsed_log1p_minutes",),
    "1m_5m_agreement": ("fast_context_agreement",), "symbol": c10.SYMBOL_FEATURES,
}


def reject_2026(path: str | Path) -> None:
    if any("2026" in part for part in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C11 prohibits 2026 path or metadata access")


def sha256_file(path: Path) -> str:
    reject_2026(path); h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def binary_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        terminal = c10.CLASSES[row["label"]]
        if terminal in ("CONTINUATION_FIRST", "DETERIORATION_FIRST"):
            out.append(row | {"label": int(terminal == "CONTINUATION_FIRST")})
    return out


def fit_model(rows, names=NAMES):
    w = c10.trade_weights(rows); scaler = c10.fit_scaler(rows, names, w)
    fit = c8.fit_logistic(c10.design(rows, names, scaler), np.asarray([r["label"] for r in rows], float), w)
    return {"names": names, "scaler": scaler, "fit": fit}


def predict_model(model, rows):
    return c8.predict(model["fit"], c10.design(rows, model["names"], model["scaler"]))


def fit_all(train, valid):
    w = c10.trade_weights(train); y = np.asarray([r["label"] for r in train], float)
    base = float(w @ y / w.sum()); pred = {"M0": np.full(len(valid), base)}
    fits = {"M0": {"base_rate": base}}
    for name, features in (("M1", c10.CONTEXT_FEATURES), ("M2", NAMES)):
        model = fit_model(train, features); pred[name] = predict_model(model, valid)
        fits[name] = serialize_model(model)
    return pred, fits


def serialize_model(model):
    fit = model["fit"]
    return {"features": list(model["names"]), "scaler": model["scaler"],
            "coefficients": [float(x) for x in fit["coef"]], "converged": fit["converged"],
            "iterations": fit["iterations"], "gradient_max": fit["gradient_max"]}


def period(rows, lo, hi, terminal_before=None):
    return [r for r in rows if lo <= r["entry_ms"] < hi and (terminal_before is None or r["terminal_ms"] < terminal_before)]


def inner_predictions(rows, outer_end):
    specs = [(1704067200000, c9.Q1, c9.Q1, c9.H1, "Q1_to_Q2")]
    if outer_end > c9.Q3: specs.append((1704067200000, c9.H1, c9.H1, c9.Q3, "H1_to_Q3"))
    if outer_end > c9.YEAR_END: specs.append((1704067200000, c9.Q3, c9.Q3, c9.YEAR_END, "Q1Q3_to_Q4"))
    scored, probabilities, definitions = [], [], []
    for lo, cut, vlo, vhi, name in specs:
        train, valid = period(rows, lo, cut, vlo), period(rows, vlo, vhi)
        model = fit_model(train); p = predict_model(model, valid)
        scored.extend(valid); probabilities.extend(p.tolist())
        definitions.append({"name": name, "train_bounds_ms": [lo, cut], "score_bounds_ms": [vlo, vhi],
                            "train": c8.summarize_rows(train), "scored": c8.summarize_rows(valid)})
    return scored, np.asarray(probabilities), definitions


def evaluate(rows, candidates):
    return {name: {**c8.metrics(rows, p), "calibration": c9.reliability(rows, p),
                   "probability_distribution": distribution(p)} for name, p in candidates.items()}


def distribution(values):
    a = np.asarray(values, float)
    return {"n": len(a), "mean": float(a.mean()), "p10": float(np.quantile(a, .1)),
            "median": float(np.median(a)), "p90": float(np.quantile(a, .9)), "min": float(a.min()), "max": float(a.max())}


def trajectory_summary(rows, probabilities):
    by = defaultdict(list)
    for i, row in enumerate(rows): by[row["trade_id"]].append(i)
    elapsed_bands = ((1, 5), (6, 15), (16, 30), (31, 60), (61, 120), (121, None))
    panels, stats, dwell, transitions = defaultdict(list), [], defaultdict(Counter), defaultdict(Counter)
    for tid, ix in by.items():
        ix.sort(key=lambda i: rows[i]["state_ms"]); ps = np.asarray([probabilities[i] for i in ix])
        rr = [rows[i] for i in ix]; outcome = "CONTINUATION_FIRST" if rr[0]["label"] else "DETERIORATION_FIRST"
        panels[(outcome, "first")].append(float(ps[0])); panels[(outcome, "near_terminal")].append(float(ps[-1]))
        for row, p in zip(rr, ps):
            elapsed = int((row["state_ms"] - row["t0_ms"]) / c10.MINUTE)
            for lo, hi in elapsed_bands:
                if elapsed >= lo and (hi is None or elapsed <= hi): panels[(outcome, f"{lo}-{hi or 'plus'}m")].append(float(p)); break
        bins = np.minimum((ps * 10).astype(int), 9)
        for b in bins: dwell[outcome][str(int(b))] += 1
        for a, b in zip(bins[:-1], bins[1:]): transitions[outcome][f"{int(a)}->{int(b)}"] += 1
        delta = np.diff(ps); signs = np.sign(delta[np.abs(delta) > 1e-12]); net = float(ps[-1] - ps[0])
        direction = "upward" if net > 1e-12 else "downward" if net < -1e-12 else "flat"
        target = 1 if direction == "upward" else -1 if direction == "downward" else 0
        stats.append({"trade_id": tid, "outcome": outcome, "states": len(ps), "first": float(ps[0]), "last": float(ps[-1]),
                      "net_change": net, "direction": direction, "mean_change_per_minute": float(delta.mean()) if len(delta) else 0.0,
                      "persistence": float(np.mean(signs == target)) if len(signs) and target else None,
                      "reversals": int(np.sum(signs[1:] != signs[:-1])) if len(signs) > 1 else 0})
    def dist_or_none(x): return distribution(x) if x else None
    out = {}
    for outcome in ("CONTINUATION_FIRST", "DETERIORATION_FIRST"):
        cohort = [x for x in stats if x["outcome"] == outcome]
        keys = ["first"] + [f"{lo}-{hi or 'plus'}m" for lo, hi in elapsed_bands] + ["near_terminal"]
        total = sum(dwell[outcome].values())
        out[outcome] = {"distributions": {k: dist_or_none(panels[(outcome, k)]) for k in keys},
            "trades": len(cohort), "directions": dict(Counter(x["direction"] for x in cohort)),
            "mean_net_change": float(np.mean([x["net_change"] for x in cohort])),
            "mean_rate_per_minute": float(np.mean([x["mean_change_per_minute"] for x in cohort])),
            "mean_reversals": float(np.mean([x["reversals"] for x in cohort])),
            "mean_persistence": float(np.mean([x["persistence"] for x in cohort if x["persistence"] is not None])),
            "probability_band_time_share": {k: v / total for k, v in sorted(dwell[outcome].items())},
            "band_transitions": dict(sorted(transitions[outcome].items()))}
    return {"summary": out, "per_trade": stats, "bands": "fixed deciles; descriptive, not action thresholds"}


def feature_interpretation(model):
    names = list(model["names"]) + list(c10.SYMBOL_FEATURES); beta = model["fit"]["coef"][1:]
    lookup = dict(zip(names, beta)); groups = {}
    for family, features in FAMILIES.items():
        vals = [float(lookup[x]) for x in features]
        groups[family] = {"features": list(features), "signed_sum": sum(vals),
                          "absolute_coefficient_mass": sum(abs(x) for x in vals),
                          "largest_feature": max(features, key=lambda x: abs(lookup[x]))}
    return {"warning": "Predictive associations only; not causal effects.",
            "coefficients": [{"feature": n, "standardized_coefficient": float(v),
                              "association": "continuation" if v > 0 else "deterioration" if v < 0 else "neutral"} for n, v in zip(names, beta)],
            "families": groups}


def reconciliation(trades, rows):
    outcomes = Counter(t["terminal"] for t in trades)
    expected = {"CONTINUATION_FIRST": 335, "DETERIORATION_FIRST": 508, "P0_FIRST": 2}
    if len(trades) != 845 or outcomes != expected: raise RuntimeError(f"C10 outcome mismatch: {outcomes}")
    binary = [t for t in trades if t["terminal"] in expected and t["terminal"] != "P0_FIRST"]
    ids = Counter(r["trade_id"] for r in rows); zero = [t for t in binary if t["trade_id"] not in ids]
    a = np.asarray(list(ids.values()))
    return {"source_trades": len(trades), "source_by_year": dict(Counter(str(t["year"]) for t in trades)),
            "terminal_outcomes": dict(outcomes), "binary_target_trades": len(binary),
            "binary_by_outcome": dict(Counter(t["terminal"] for t in binary)), "trades_with_rows": len(ids),
            "zero_row_trades": len(zero), "zero_rows_by_outcome": dict(Counter(t["terminal"] for t in zero)),
            "rows": len(rows), "rows_per_trade": {"min": int(a.min()), "p25": float(np.quantile(a,.25)),
            "median": float(np.median(a)), "p75": float(np.quantile(a,.75)), "max": int(a.max()), "mean": float(a.mean())}}


def p0_report(trades, markets):
    result = []
    for t in trades:
        if t["terminal"] != "P0_FIRST": continue
        market = markets[t["symbol"]]; i0 = market.index(t["t0_ms"]); i1 = market.index(t["p0_ms"] - c10.MINUTE)
        highest = float(np.max(market.high[i0:i1+1])); lowest = float(np.min(market.low[i0:i1+1]))
        result.append({"trade_id": t["trade_id"], "symbol": t["symbol"], "year": t["year"],
            "minutes_t2_to_p0": (t["p0_ms"] - t["t0_ms"]) / c10.MINUTE,
            "closest_continuation_gap": t["continuation_level"] / highest - 1,
            "closest_deterioration_gap": lowest / t["deterioration_level"] - 1,
            "continuation_boundary_touched": highest >= t["continuation_level"],
            "deterioration_boundary_touched": lowest <= t["deterioration_level"],
            "terminal_close_distance_to_continuation": t["terminal_close"] / t["continuation_level"] - 1,
            "terminal_close_distance_to_deterioration": t["terminal_close"] / t["deterioration_level"] - 1})
    return {"count": len(result), "cases": result, "treatment": "descriptive only; competing P0 termination is not either binary outcome"}


def artifact_hashes(directory):
    return {p.name: sha256_file(p) for p in sorted(directory.iterdir()) if p.is_file() and p.name != "reproducibility_hashes.json"}


def run(repo: Path):
    reject_2026(repo); contract = repo / "contracts/C11_dynamic_post_t2_state_CONTRACT.md"
    if sha256_file(contract) != CONTRACT_SHA256: raise RuntimeError("C11 contract changed after prospective freeze")
    output = repo / "artifacts/c11_dynamic_post_t2_state"; output.mkdir(parents=True, exist_ok=True)
    inputs = [contract, repo / "contracts/C10_post_t2_timescale_adequacy_CONTRACT.md",
        repo / "artifacts/c7_full_population_t2_exit_overlay/population_manifest.json",
        repo / "artifacts/c4_sequential_exit_state/local/t2_snapshots.csv",
        repo / "src/binance_data_foundation/c10_post_t2.py"] + [repo / f"data/normalized/c2_history/{s}_1m.csv.gz" for s in c10.SYMBOLS]
    provenance = {str(p.relative_to(repo)): sha256_file(p) for p in inputs}
    trades = c10.load_c7_population(repo); auth = c10.reconcile_authoritative(repo, trades)
    if auth["status"] != "PASS": raise RuntimeError("authoritative identity reconciliation failed")
    markets = {s: c10.load_market(repo / f"data/normalized/c2_history/{s}_1m.csv.gz") for s in c10.SYMBOLS}
    bars = {(s, m): c10.aggregate(markets[s], m) for s in c10.SYMBOLS for m in (1, 5)}
    trades = [c10.first_event(t, markets[t["symbol"]]) for t in trades]
    all_rows = c10.snapshots(trades, markets, bars, "A"); rows = binary_rows(all_rows)
    rec = reconciliation(trades, rows); p0 = p0_report(trades, markets)
    schema = {"frozen_before_evaluation": True, "architecture": {"context_minutes": 5, "state_minutes": 1},
              "M0": "training trade-weighted prevalence", "M1": list(c10.CONTEXT_FEATURES) + list(c10.SYMBOL_FEATURES),
              "M2": list(NAMES) + list(c10.SYMBOL_FEATURES), "families": {k: list(v) for k,v in FAMILIES.items()},
              "label_not_in_features": True}
    write_json(output/"provenance.json", {"contract_sha256": CONTRACT_SHA256, "inputs": provenance, "no_2026_access": True})
    write_json(output/"event_population_reconciliation.json", {"authoritative": auth, "modeling": rec})
    write_json(output/"feature_schema.json", schema); write_json(output/"p0_edge_cases.json", p0)

    rows24, rows25 = [r for r in rows if r["year"] == 2024], [r for r in rows if r["year"] == 2025]
    pooled_rows, pooled_pred, fold_defs = [], defaultdict(list), {}
    for fold, (_, _, end) in c10.FOLDS.items():
        train, valid = c10.split_fold(rows24, fold); pred, fits = fit_all(train, valid)
        inner_rows, inner_p, inner_defs = inner_predictions(rows24, end)
        platt = c9.fit_platt(inner_rows, inner_p); platt_p = c9.apply_platt(platt, pred["M2"])
        support = c9.isotonic_support(inner_rows, inner_p); iso = c9.fit_isotonic(inner_rows, inner_p) if support["eligible"] else None
        candidates = pred | {"M2_platt": platt_p}
        if iso: candidates["M2_isotonic"] = c9.apply_isotonic(iso, pred["M2"])
        pooled_rows.extend(valid)
        for name, values in candidates.items(): pooled_pred[name].extend(values.tolist())
        fold_defs[fold] = {"bounds_ms": list(c10.FOLDS[fold]), "train": c8.summarize_rows(train), "validation": c8.summarize_rows(valid),
            "inner": inner_defs, "isotonic_support": support, "platt": platt, "models": fits, "metrics": evaluate(valid, candidates)}
    pp = {k: np.asarray(v) for k,v in pooled_pred.items() if len(v) == len(pooled_rows)}; dev = evaluate(pooled_rows, pp)
    selected = "platt"
    if "M2_isotonic" in dev and all(dev["M2_isotonic"][m] < dev["M2_platt"][m] for m in ("brier","log_loss")): selected = "isotonic"
    selected_key = {"platt":"M2_platt", "isotonic":"M2_isotonic"}[selected]
    if any(dev[selected_key][m] > dev["M2"][m] for m in ("brier","log_loss")): selected, selected_key = "uncalibrated", "M2"
    samples24 = c8.moving_block_samples(pooled_rows, seed=SEED, replicates=REPLICATES)
    unc24 = {"M1_vs_M0": c8.paired_uncertainty(pooled_rows, pp["M0"], pp["M1"], samples24),
             "M2_vs_M1": c8.paired_uncertainty(pooled_rows, pp["M1"], pp["M2"], samples24),
             "calibrated_vs_M2": c8.paired_uncertainty(pooled_rows, pp["M2"], pp[selected_key], samples24)}
    decision = {"selected": selected, "isotonic_requires_every_fold_support": True,
                "support": {f: fold_defs[f]["isotonic_support"] for f in fold_defs},
                "rule": "isotonic iff supported in every fold and beats Platt on both proper scores; recalibration retained only if neither proper score worsens"}
    write_json(output/"fold_definitions.json", fold_defs); write_json(output/"baseline_metrics.json", {"M0":dev["M0"]})
    write_json(output/"m1_m2_metrics_2024.json", {k:dev[k] for k in ("M1","M2")})
    write_json(output/"calibration_candidate_decision.json", decision)
    write_json(output/"calibrated_metrics_2024.json", {k:dev[k] for k in dev if k.startswith("M2")})
    write_json(output/"probability_bands_2024.json", {k:v["calibration"] for k,v in dev.items()})
    write_json(output/"whole_trade_uncertainty_2024.json", unc24)
    traj24 = trajectory_summary(pooled_rows, pp[selected_key]); write_json(output/"trajectory_summary_2024.json", {"summary":traj24["summary"],"bands":traj24["bands"]})

    inner_rows, inner_p, inner_defs = inner_predictions(rows24, c9.YEAR_END + 1)
    full = fit_model(rows24); raw25 = predict_model(full, rows25); calibrator = None
    if selected == "platt": calibrator = c9.fit_platt(inner_rows, inner_p); p25 = c9.apply_platt(calibrator, raw25)
    elif selected == "isotonic": calibrator = c9.fit_isotonic(inner_rows, inner_p); p25 = c9.apply_isotonic(calibrator, raw25)
    else: p25 = raw25.copy()
    p25all, fit25 = fit_all(rows24, rows25); metrics25 = evaluate(rows25, p25all | {"M2_calibrated": p25})
    samples25 = c8.moving_block_samples(rows25, seed=SEED, replicates=REPLICATES)
    unc25 = {"M2_vs_M1": c8.paired_uncertainty(rows25,p25all["M1"],raw25,samples25),
             "calibrated_vs_M2":c8.paired_uncertainty(rows25,raw25,p25,samples25)}
    frozen = {"selected":selected,"inner_definitions":inner_defs,"calibrator":calibrator,"M2":serialize_model(full),"selection_rule":decision["rule"]}
    write_json(output/"frozen_calibration_procedure.json",frozen); write_json(output/"stability_2025.json",metrics25)
    write_json(output/"probability_bands_2025.json",{k:v["calibration"] for k,v in metrics25.items()})
    write_json(output/"whole_trade_uncertainty_2025.json",unc25)
    traj25=trajectory_summary(rows25,p25); write_json(output/"trajectory_summary_2025.json",{"summary":traj25["summary"],"bands":traj25["bands"]})
    interpretation=feature_interpretation(full); write_json(output/"feature_interpretation.json",interpretation)
    final={"contract_sha256":CONTRACT_SHA256,"population":rec,"selected_calibration":selected,"metrics_2024":dev,
           "uncertainty_2024":unc24,"metrics_2025":metrics25,"uncertainty_2025":unc25,
           "trajectory_2024":traj24["summary"],"trajectory_2025":traj25["summary"],"feature_interpretation":interpretation,
           "p0_edge_cases":p0,"practical_interpretation":"Completed 1m update; any future policy acts subsequently. No sub-minute foresight or execution modeled.",
           "confirmations":{"pnl_or_economics":False,"trading_or_exit_policy":False,"c7_c8_c9_c10_scientific_modification":False,"accessed_2026":False,"c12_started":False}}
    write_json(output/"final_summary.json",final)
    write_json(output/"run_manifest.json",{"version":"C11_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,
        "python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"})
    write_json(output/"reproducibility_hashes.json",artifact_hashes(output))
    return final
