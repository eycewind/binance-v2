"""C9 chronology-safe calibration and dynamic pre-T2 prognosis."""
from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c8_timescale as c8

CONTRACT_SHA256 = "99d3b9eabb52967f072f017b57d08cb22f9813898f9e8f6e1e9603a37d21b3fd"
SEED = 20260928
REPLICATES = 2000
ARCHITECTURE = "B"
Q1, H1, Q3, YEAR_END = 1711929600000, 1719792000000, 1727740800000, 1735689600000

FAMILIES = {
    "1h_trend_context": tuple(c8.SLOW_FEATURES),
    "current_return": ("current_return",),
    "running_peak_mfe": ("running_mfe",),
    "drawdown_from_running_peak": ("drawdown_from_running_peak",),
    "distance_to_t2_geometry": ("distance_to_t2_barrier",),
    "5m_momentum": ("fast_return_1", "fast_return_3", "fast_return_6"),
    "5m_volatility_range": ("fast_volatility_12", "fast_range_ratio"),
    "path_efficiency": ("path_efficiency",),
    "elapsed_time": ("elapsed_log1p_minutes",),
    "fast_slow_directional_agreement": ("fast_slow_agreement",),
    "activity": ("fast_activity_ratio",),
    "symbol": tuple(c8.SYMBOL_FEATURES),
}


def reject_2026(path: str | Path) -> None:
    parts = str(path).replace("\\", "/").lower().split("/")
    if any("2026" in part for part in parts):
        raise PermissionError("C9 prohibits 2026 path or metadata access")


def sha256_file(path: Path) -> str:
    reject_2026(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def _fit_base(train: list[dict]) -> dict:
    names = c8.SLOW_FEATURES + c8.FAST_FEATURES
    weights = c8.trade_weights(train)
    scaler = c8.fit_scaler(train, names, weights)
    y = np.asarray([row["label"] for row in train], float)
    fit = c8.fit_logistic(c8.design(train, names, scaler), y, weights)
    return {"names": names, "scaler": scaler, "fit": fit}


def _predict_base(model: dict, rows: list[dict]) -> np.ndarray:
    return c8.predict(model["fit"], c8.design(rows, model["names"], model["scaler"]))


def _period(rows: list[dict], lo: int, hi: int, require_terminal_before: int | None = None) -> list[dict]:
    return [row for row in rows if lo <= row["entry_ms"] < hi and
            (require_terminal_before is None or row["terminal_ms"] < require_terminal_before)]


def inner_predictions(rows_2024: list[dict], outer_end: int) -> tuple[list[dict], np.ndarray, list[dict]]:
    """Expanding, strictly out-of-time calibration scores available before outer_end."""
    specs = [(1704067200000, Q1, Q1, H1, "Q1_to_Q2")]
    if outer_end > Q3:
        specs.append((1704067200000, H1, H1, Q3, "H1_to_Q3"))
    if outer_end > YEAR_END:
        specs.append((1704067200000, Q3, Q3, YEAR_END, "Q1Q3_to_Q4"))
    scored, probs, definitions = [], [], []
    for train_lo, train_hi, valid_lo, valid_hi, name in specs:
        train = _period(rows_2024, train_lo, train_hi, valid_lo)
        valid = _period(rows_2024, valid_lo, valid_hi)
        model = _fit_base(train)
        p = _predict_base(model, valid)
        scored.extend(valid); probs.extend(p.tolist())
        definitions.append({"name": name, "train_bounds_ms": [train_lo, train_hi],
            "score_bounds_ms": [valid_lo, valid_hi], "train": c8.summarize_rows(train),
            "scored": c8.summarize_rows(valid)})
    return scored, np.asarray(probs), definitions


def fit_platt(rows: list[dict], probabilities: np.ndarray) -> dict:
    y = np.asarray([row["label"] for row in rows], float)
    w = c8.trade_weights(rows); w /= w.sum()
    p = np.clip(probabilities, 1e-9, 1 - 1e-9)
    z = np.log(p / (1 - p)); x = np.column_stack((np.ones(len(z)), z))
    beta = np.asarray([0.0, 1.0]); converged = False
    for iteration in range(1, 201):
        q = 1 / (1 + np.exp(-np.clip(x @ beta, -35, 35)))
        grad = x.T @ (w * (q - y))
        hess = x.T @ (x * (w * q * (1 - q))[:, None])
        step = np.linalg.solve(hess + np.eye(2) * 1e-12, grad)
        beta -= step
        if np.max(np.abs(step)) < 1e-10:
            converged = True; break
    if not np.all(np.isfinite(beta)):
        raise RuntimeError("non-finite Platt fit")
    return {"intercept": float(beta[0]), "slope": float(beta[1]),
            "converged": converged, "iterations": iteration}


def apply_platt(model: dict, probabilities: np.ndarray) -> np.ndarray:
    p = np.clip(probabilities, 1e-9, 1 - 1e-9)
    z = model["intercept"] + model["slope"] * np.log(p / (1 - p))
    return 1 / (1 + np.exp(-np.clip(z, -35, 35)))


def isotonic_support(rows: list[dict], probabilities: np.ndarray) -> dict:
    labels = {row["trade_id"]: row["label"] for row in rows}
    counts = Counter(labels.values())
    result = {"trades": len(labels), "event_trades": counts[1], "non_event_trades": counts[0],
              "distinct_scores": int(len(np.unique(probabilities)))}
    result["eligible"] = (result["trades"] >= 300 and result["event_trades"] >= 75 and
                          result["non_event_trades"] >= 75 and result["distinct_scores"] >= 100)
    return result


def fit_isotonic(rows: list[dict], probabilities: np.ndarray) -> dict:
    y = np.asarray([row["label"] for row in rows], float)
    w = c8.trade_weights(rows)
    order = np.argsort(probabilities, kind="mergesort")
    x, y, w = np.asarray(probabilities)[order], y[order], w[order]
    blocks = []
    i = 0
    while i < len(x):
        j = i + 1
        while j < len(x) and x[j] == x[i]: j += 1
        blocks.append([float(x[i]), float(x[j-1]), float(np.sum(w[i:j] * y[i:j])), float(np.sum(w[i:j]))])
        while len(blocks) >= 2 and blocks[-2][2] / blocks[-2][3] > blocks[-1][2] / blocks[-1][3]:
            b = blocks.pop(); a = blocks.pop()
            blocks.append([a[0], b[1], a[2] + b[2], a[3] + b[3]])
        i = j
    return {"upper_score": [b[1] for b in blocks], "value": [b[2] / b[3] for b in blocks],
            "blocks": len(blocks)}


def apply_isotonic(model: dict, probabilities: np.ndarray) -> np.ndarray:
    upper, value = np.asarray(model["upper_score"]), np.asarray(model["value"])
    ix = np.searchsorted(upper, probabilities, side="left")
    return value[np.clip(ix, 0, len(value) - 1)]


def reliability(rows: list[dict], probabilities: np.ndarray) -> dict:
    base = c8.calibration(rows, probabilities)
    y = np.asarray([row["label"] for row in rows], float)
    p = np.asarray(probabilities); w = c8.trade_weights(rows); w /= w.sum()
    bins, ece = [], 0.0
    bin_id = np.minimum((p * 10).astype(int), 9)
    for bucket in range(10):
        lo = bucket / 10
        ix = bin_id == bucket
        if not np.any(ix): continue
        mass = float(w[ix].sum()); ww = w[ix] / mass
        mean_p, observed = float(np.sum(ww * p[ix])), float(np.sum(ww * y[ix]))
        ece += mass * abs(mean_p - observed)
        bins.append({"lower": float(lo), "upper": float(lo + .1), "trade_weight_mass": mass,
            "rows": int(ix.sum()), "trades": len({rows[i]["trade_id"] for i in np.flatnonzero(ix)}),
            "mean_probability": mean_p, "observed": observed,
            "absolute_gap": abs(mean_p - observed)})
    return {"intercept": base["intercept"], "slope": base["slope"],
            "estimable": base["estimable"], "ece": float(ece), "bins": bins}


def evaluate(rows: list[dict], candidates: dict[str, np.ndarray]) -> dict:
    return {name: {**c8.metrics(rows, p), "calibration": reliability(rows, p)}
            for name, p in candidates.items()}


def trajectory_summary(rows: list[dict], probabilities: np.ndarray) -> dict:
    by = defaultdict(list)
    for i, row in enumerate(rows): by[row["trade_id"]].append(i)
    distributions = defaultdict(list); trade_stats = []
    for trade_id, indices in by.items():
        indices.sort(key=lambda i: rows[i]["state_ms"])
        ps = np.asarray([probabilities[i] for i in indices]); label = rows[indices[0]]["label"]
        outcome = "T2_FIRST" if label else "P0_FIRST"
        distributions[(outcome, "first")].append(float(ps[0]))
        distributions[(outcome, "last_pre_terminal")].append(float(ps[-1]))
        thirds = np.minimum(2, np.floor(np.arange(len(ps)) * 3 / len(ps)).astype(int))
        for k, name in enumerate(("early", "middle", "late")):
            distributions[(outcome, name)].extend(ps[thirds == k].tolist())
        delta = np.diff(ps); net = float(ps[-1] - ps[0])
        direction = "upward" if net > 1e-12 else "downward" if net < -1e-12 else "flat"
        signs = np.sign(delta[np.abs(delta) > 1e-12])
        reversals = int(np.sum(signs[1:] != signs[:-1])) if len(signs) > 1 else 0
        target_sign = 1 if direction == "upward" else -1 if direction == "downward" else 0
        persistence = float(np.mean(signs == target_sign)) if len(signs) and target_sign else None
        trade_stats.append({"trade_id": trade_id, "outcome": outcome, "states": len(ps),
            "first": float(ps[0]), "last": float(ps[-1]), "net_change": net, "direction": direction,
            "mean_change_per_5m": float(np.mean(delta)) if len(delta) else 0.0,
            "median_change_per_5m": float(np.median(delta)) if len(delta) else 0.0,
            "positive_change_share": float(np.mean(delta > 1e-12)) if len(delta) else 0.0,
            "negative_change_share": float(np.mean(delta < -1e-12)) if len(delta) else 0.0,
            "persistence": persistence, "reversals": reversals})
    def dist(values):
        a = np.asarray(values)
        return {"n": len(a), "mean": float(np.mean(a)), "p10": float(np.quantile(a, .1)),
                "median": float(np.median(a)), "p90": float(np.quantile(a, .9))}
    panels = {outcome: {state: dist(distributions[(outcome, state)])
        for state in ("first", "early", "middle", "late", "last_pre_terminal")}
        for outcome in ("T2_FIRST", "P0_FIRST")}
    aggregate = {}
    for outcome in ("T2_FIRST", "P0_FIRST"):
        cohort = [x for x in trade_stats if x["outcome"] == outcome]
        aggregate[outcome] = {"trades": len(cohort), "directions": dict(Counter(x["direction"] for x in cohort)),
            "mean_net_change": float(np.mean([x["net_change"] for x in cohort])),
            "median_net_change": float(np.median([x["net_change"] for x in cohort])),
            "mean_rate_per_5m": float(np.mean([x["mean_change_per_5m"] for x in cohort])),
            "mean_reversals": float(np.mean([x["reversals"] for x in cohort])),
            "mean_persistence": float(np.mean([x["persistence"] for x in cohort if x["persistence"] is not None]))}
    return {"state_distributions": panels, "trade_trajectory_summary": aggregate,
            "per_trade": trade_stats}


def deterministic_examples(rows: list[dict], probabilities: np.ndarray, trade_stats: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for i, row in enumerate(rows): by[row["trade_id"]].append(i)
    stats = {x["trade_id"]: x for x in trade_stats}; chosen = []
    for label in (1, 0):
        cohort = [t for t, ix in by.items() if rows[ix[0]]["label"] == label]
        median = float(np.median([len(by[t]) for t in cohort]))
        chosen.append(min(cohort, key=lambda t: (abs(len(by[t]) - median), t)))
    remaining = [t for t in by if t not in chosen]
    chosen.append(min(remaining, key=lambda t: (-stats[t]["net_change"], t)))
    remaining = [t for t in remaining if t != chosen[-1]]
    chosen.append(min(remaining, key=lambda t: (stats[t]["net_change"], t)))
    roles = ("median_T2", "median_P0", "largest_upward", "largest_downward")
    output = []
    for role, trade_id in zip(roles, chosen):
        indices = sorted(by[trade_id], key=lambda i: rows[i]["state_ms"])
        output.append({"role": role, "trade_id": trade_id, "symbol": rows[indices[0]]["symbol"],
            "outcome": "T2_FIRST" if rows[indices[0]]["label"] else "P0_FIRST",
            "trajectory": [{"state_ms": rows[i]["state_ms"],
                "elapsed_minutes": int((rows[i]["state_ms"] - rows[i]["entry_ms"]) / c8.MINUTE),
                "probability": float(probabilities[i])} for i in indices]})
    return output


def feature_interpretation(model: dict) -> dict:
    names = list(model["names"]) + list(c8.SYMBOL_FEATURES)
    coefs = model["fit"]["coef"][1:]
    table = [{"feature": name, "standardized_coefficient": float(value),
              "association": "higher_probability" if value > 0 else "lower_probability" if value < 0 else "neutral"}
             for name, value in zip(names, coefs)]
    lookup = dict(zip(names, coefs)); groups = {}
    for family, features in FAMILIES.items():
        vals = [float(lookup[x]) for x in features]
        groups[family] = {"features": list(features), "signed_sum": float(sum(vals)),
            "absolute_coefficient_mass": float(sum(abs(x) for x in vals)),
            "largest_feature": max(features, key=lambda x: abs(lookup[x]))}
    return {"warning": "Predictive associations only; coefficients are not causal effects.",
            "intercept": float(model["fit"]["coef"][0]), "features": table, "families": groups}


def _serialize_base(model: dict) -> dict:
    return {"features": list(model["names"]), "scaler": model["scaler"],
        "coefficients": [float(x) for x in model["fit"]["coef"]],
        "converged": model["fit"]["converged"], "iterations": model["fit"]["iterations"],
        "gradient_max": model["fit"]["gradient_max"]}


def artifact_hashes(directory: Path) -> dict:
    return {p.name: sha256_file(p) for p in sorted(directory.iterdir())
            if p.is_file() and p.name != "reproducibility_hashes.json"}


def run(repo: Path) -> dict:
    reject_2026(repo)
    output = repo / "artifacts/c9_dynamic_pre_t2_state"
    contract = repo / "contracts/C9_dynamic_pre_t2_state_CONTRACT.md"
    if sha256_file(contract) != CONTRACT_SHA256:
        raise RuntimeError("C9 contract changed after prospective freeze")
    inputs = [repo / "artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv",
        repo / "artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv",
        repo / "contracts/C8_pre_t2_timescale_adequacy_CONTRACT.md",
        repo / "src/binance_data_foundation/c8_timescale.py"] + [
        repo / f"data/normalized/c2_history/{symbol}_1m.csv.gz" for symbol in c8.SYMBOLS]
    provenance = {str(path.relative_to(repo)): sha256_file(path) for path in inputs}

    trades = c8.load_trades(repo); markets = {}; bars = {}
    for symbol in c8.SYMBOLS:
        market = c8.load_market(repo / f"data/normalized/c2_history/{symbol}_1m.csv.gz")
        markets[symbol] = market
        bars[(symbol, 5)] = c8.aggregate(market, 5)
        bars[(symbol, 60)] = c8.aggregate(market, 60)
    for trade in trades: trade.update(c8.terminal_for_trade(trade, markets[trade["symbol"]]))
    outcomes = dict(Counter(trade["terminal"] for trade in trades))
    if outcomes != {"T2_FIRST": 845, "P0_FIRST": 1354}:
        raise RuntimeError(f"population mismatch: {outcomes}")
    rows = c8.snapshots(trades, markets, bars, ARCHITECTURE)
    rows_2024 = [row for row in rows if row["year"] == 2024]
    rows_2025 = [row for row in rows if row["year"] == 2025]
    eligible_ids = {row["trade_id"] for row in rows}
    excluded = Counter(trade["terminal"] for trade in trades if trade["trade_id"] not in eligible_ids)
    reconciliation = {"source_population": len(trades), "source_by_year": dict(Counter(str(t["year"]) for t in trades)),
        "source_outcomes": outcomes, "eligible": c8.summarize_rows(rows),
        "eligible_2024": c8.summarize_rows(rows_2024), "eligible_2025": c8.summarize_rows(rows_2025),
        "no_eligible_snapshot": {"trades": len(trades) - len(eligible_ids), "outcomes": dict(excluded)}}
    write_json(output / "provenance.json", {"contract_sha256": CONTRACT_SHA256,
        "source_hashes": provenance, "architecture": {"slow_minutes": 60, "fast_minutes": 5},
        "no_2026_access": True, "economics_computed": False})
    write_json(output / "feature_schema.json", {"continuous": list(c8.SLOW_FEATURES + c8.FAST_FEATURES),
        "symbol_indicators": list(c8.SYMBOL_FEATURES), "families": {k: list(v) for k, v in FAMILIES.items()},
        "source": "frozen C8 architecture B formulas"})
    write_json(output / "population_snapshot_reconciliation.json", reconciliation)

    pooled_rows = []; pooled = defaultdict(list); fold_defs = {}
    for fold, (_, cut, end) in c8.FOLDS.items():
        train, valid = c8.split_fold(rows_2024, fold)
        base = _fit_base(train); base_p = _predict_base(base, valid)
        inner_rows, inner_p, inner_defs = inner_predictions(rows_2024, end)
        platt = fit_platt(inner_rows, inner_p); platt_p = apply_platt(platt, base_p)
        support = isotonic_support(inner_rows, inner_p)
        iso = fit_isotonic(inner_rows, inner_p) if support["eligible"] else None
        iso_p = apply_isotonic(iso, base_p) if iso else None
        pooled_rows.extend(valid); pooled["baseline"].extend(base_p.tolist()); pooled["platt"].extend(platt_p.tolist())
        if iso_p is not None: pooled["isotonic"].extend(iso_p.tolist())
        fold_candidates = {"baseline": base_p, "platt": platt_p}
        if iso_p is not None: fold_candidates["isotonic"] = iso_p
        fold_defs[fold] = {"outer_train": c8.summarize_rows(train), "outer_validation": c8.summarize_rows(valid),
            "bounds_ms": list(c8.FOLDS[fold]), "inner": inner_defs, "isotonic_support": support,
            "platt": platt, "metrics": evaluate(valid, fold_candidates)}
    pooled_np = {name: np.asarray(p) for name, p in pooled.items()}
    # A pooled candidate is evaluable only when its prospective support rule
    # was met independently in every outer fold.
    pooled_np = {name: p for name, p in pooled_np.items() if len(p) == len(pooled_rows)}
    metrics_2024 = evaluate(pooled_rows, pooled_np)
    iso_eligible = "isotonic" in metrics_2024
    selected = "platt"
    if iso_eligible and all(metrics_2024["isotonic"][m] < metrics_2024["platt"][m] for m in ("brier", "log_loss")):
        selected = "isotonic"
    if any(metrics_2024[selected][m] > metrics_2024["baseline"][m] for m in ("brier", "log_loss")):
        selected = "baseline"
    uncertainty_2024 = c8.paired_uncertainty(pooled_rows, pooled_np["baseline"], pooled_np[selected],
        c8.moving_block_samples(pooled_rows, seed=SEED, replicates=REPLICATES))
    traj_2024 = trajectory_summary(pooled_rows, pooled_np[selected])
    candidate_decision = {"available_pooled_candidates": sorted(pooled_np),
        "isotonic_outer_fold_support": {fold: fold_defs[fold]["isotonic_support"] for fold in fold_defs},
        "isotonic_pooled_eligible": "isotonic" in pooled_np, "selected": selected,
        "rule": "isotonic only if every outer fold is supported and both proper scores beat Platt; chosen calibration must not worsen either baseline proper score"}
    write_json(output / "fold_definitions.json", fold_defs)
    write_json(output / "calibration_candidate_decision.json", candidate_decision)
    write_json(output / "development_metrics_2024.json", metrics_2024)
    write_json(output / "probability_bands_2024.json", {k: v["calibration"] for k, v in metrics_2024.items()})
    write_json(output / "whole_trade_uncertainty_2024.json", uncertainty_2024)
    write_json(output / "trajectory_summary_2024.json", {k: v for k, v in traj_2024.items() if k != "per_trade"})

    inner_rows, inner_p, inner_defs = inner_predictions(rows_2024, YEAR_END + 1)
    final_platt = fit_platt(inner_rows, inner_p); final_support = isotonic_support(inner_rows, inner_p)
    final_iso = fit_isotonic(inner_rows, inner_p) if final_support["eligible"] else None
    full_base = _fit_base(rows_2024); p25_base = _predict_base(full_base, rows_2025)
    if selected == "platt": p25 = apply_platt(final_platt, p25_base); calibration_model = final_platt
    elif selected == "isotonic": p25 = apply_isotonic(final_iso, p25_base); calibration_model = final_iso
    else: p25 = p25_base.copy(); calibration_model = None
    metrics_2025 = evaluate(rows_2025, {"baseline": p25_base, "calibrated": p25})
    uncertainty_2025 = c8.paired_uncertainty(rows_2025, p25_base, p25,
        c8.moving_block_samples(rows_2025, seed=SEED, replicates=REPLICATES))
    frozen = {"selected": selected, "selection_rule": "isotonic only if eligible and improves both Platt proper scores; selected must not worsen either baseline score",
        "inner_definitions": inner_defs, "isotonic_support": final_support,
        "calibration_model": calibration_model, "baseline_model": _serialize_base(full_base)}
    write_json(output / "frozen_calibration_procedure.json", frozen)
    write_json(output / "stability_metrics_2025.json", metrics_2025)
    write_json(output / "probability_bands_2025.json", {k: v["calibration"] for k, v in metrics_2025.items()})
    write_json(output / "whole_trade_uncertainty_2025.json", uncertainty_2025)

    interpretation = feature_interpretation(full_base)
    write_json(output / "feature_interpretation.json", interpretation)
    traj_2025 = trajectory_summary(rows_2025, p25)
    write_json(output / "trajectory_summary_2025.json", {k: v for k, v in traj_2025.items() if k != "per_trade"})
    examples = deterministic_examples(rows_2025, p25, traj_2025["per_trade"])
    write_json(output / "deterministic_example_trajectories.json", {"descriptive_only": True, "examples": examples})

    final = {"contract_sha256": CONTRACT_SHA256, "population_snapshot_reconciliation": reconciliation,
        "selected_calibration": selected, "development_2024": {"metrics": metrics_2024,
            "baseline_minus_calibrated_uncertainty": uncertainty_2024},
        "stability_2025": {"metrics": metrics_2025,
            "baseline_minus_calibrated_uncertainty": uncertainty_2025},
        "interpretation": "Running prognosis only. Probabilities and coefficients do not define actions or causal effects.",
        "confirmations": {"economics_computed": False, "c7_or_c8_scientific_behavior_modified": False,
            "accessed_2026": False, "post_t2_modeling": False}}
    write_json(output / "final_summary.json", final)
    write_json(output / "run_manifest.json", {"version": "C9_RUN_V1", "contract_sha256": CONTRACT_SHA256,
        "seed": SEED, "replicates": REPLICATES, "python": sys.version, "numpy": np.__version__,
        "platform": platform.platform(), "architecture": {"slow_minutes": 60, "fast_minutes": 5}})
    write_json(output / "reproducibility_hashes.json", artifact_hashes(output))
    return final
