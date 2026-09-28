"""C17 frozen entry-to-T2 path economic-class characterization."""
from __future__ import annotations

import hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import c7_t1 as c7
from . import c8_timescale as c8
from . import c9_dynamic_state as c9
from . import c10_post_t2 as c10
from . import c11_dynamic_post_t2 as c11
from . import c12_post_t2_warning as c12
from . import c14_post_t2_economic_state as c14
from . import c15_economic_state_temporal_structure as c15

CONTRACT_SHA256 = "fc6b5534b2f4eb5eb6147a58888a5754635f7be654cceceb64f9bf5db823b2b3"
CONTRACT_REL = "contracts/C17_entry_to_t2_path_class_CONTRACT.md"
OUTPUT_REL = "artifacts/c17_entry_to_t2_path_class"
SEED = 20260928

FAMILIES = {
    "timing": ("entry_to_t2_minutes", "entry_to_first_0p5pct_minutes", "entry_to_first_0p5pct_missing",
               "entry_to_first_1pct_minutes", "entry_to_first_1pct_missing"),
    "excursion": ("pre_t2_mfe", "pre_t2_mae", "pre_t2_range"),
    "efficiency": ("entry_to_t2_path_efficiency",),
    "peak_drawdown": ("pre_t2_new_running_highs", "pre_t2_max_drawdown", "last_pre_t2_peak_to_t2_minutes"),
    "time_above_entry": ("pre_t2_fraction_close_above_entry", "pre_t2_fraction_close_within_0p5pct_peak"),
    "volatility": ("pre_t2_return_std",),
    "late_momentum": ("final_5m_return", "final_5m_return_missing", "final_15m_return", "final_15m_return_missing",
                      "final_30m_return", "final_30m_return_missing"),
    "acceleration": ("final_5m_minus_preceding_5m", "acceleration_5m_missing",
                     "final_15m_minus_preceding_15m", "acceleration_15m_missing"),
}
PATH_FEATURES = tuple(n for family in FAMILIES.values() for n in family)
ALL_FEATURES = c11.NAMES + PATH_FEATURES
PROHIBITED = c14.PROHIBITED + ("economic_class", "class_label", "post_first", "future_return", "future_recovery", "future_continuation", "future_deterioration")


def reject_2026(path):
    if any("2026" in x for x in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C17 prohibits 2026 data or metadata access")


def sha(path: Path) -> str:
    reject_2026(path); h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def assert_feature_firewall(names):
    bad = [n for n in names if any(x in n.lower() for x in PROHIBITED)]
    if bad: raise ValueError("future/target-derived feature prohibited: " + ", ".join(bad))


def path_features(trade: dict, market) -> dict:
    """Causal descriptors from complete [entry, T2) one-minute bars only."""
    i0, i1 = market.index(trade["entry_ms"]), market.index(trade["t0_ms"] - c10.MINUTE)
    if i0 is None or i1 is None or i1 < i0: raise ValueError("entry-to-T2 path unavailable")
    ms = market.ms[i0:i1 + 1]
    if len(ms) == 0 or np.any(np.diff(ms) != c10.MINUTE): raise ValueError("entry-to-T2 path has gaps")
    entry = float(trade["entry_price"]); high = market.high[i0:i1 + 1]; low = market.low[i0:i1 + 1]; close = market.close[i0:i1 + 1]
    seed_close = np.r_[entry, close]
    returns = seed_close[1:] / seed_close[:-1] - 1
    running_peak = entry; new_highs = 0; max_dd = 0.0; last_peak_ms = trade["entry_ms"]
    within = []
    for t, h, lo, cl in zip(ms, high, low, close):
        if h > running_peak:
            running_peak = float(h); new_highs += 1; last_peak_ms = int(t + c10.MINUTE)
        max_dd = min(max_dd, float(lo / running_peak - 1))
        within.append(float(cl) >= .995 * running_peak)
    def milestone(level):
        hit = np.flatnonzero(high >= entry * level)
        return None if not len(hit) else float((int(ms[int(hit[0])]) + c10.MINUTE - trade["entry_ms"]) / c10.MINUTE)
    def horizon(h):
        return None if len(close) < h else float(close[-1] / seed_close[-1-h] - 1)
    def acceleration(h):
        if len(close) < 2*h: return None
        return float(close[-1] / close[-1-h] - 1 - (close[-1-h] / seed_close[-1-2*h] - 1))
    m05, m1 = milestone(1.005), milestone(1.01)
    h5, h15, h30 = horizon(5), horizon(15), horizon(30)
    a5, a15 = acceleration(5), acceleration(15)
    movement = float(np.sum(np.abs(returns)))
    values = {
        "entry_to_t2_minutes": float((trade["t0_ms"] - trade["entry_ms"]) / c10.MINUTE),
        "entry_to_first_0p5pct_minutes": m05, "entry_to_first_0p5pct_missing": float(m05 is None),
        "entry_to_first_1pct_minutes": m1, "entry_to_first_1pct_missing": float(m1 is None),
        "pre_t2_mfe": float(np.max(high) / entry - 1), "pre_t2_mae": float(np.min(low) / entry - 1),
        "pre_t2_range": float((np.max(high) - np.min(low)) / entry),
        "entry_to_t2_path_efficiency": 0.0 if movement == 0 else float(abs(close[-1] / entry - 1) / movement),
        "pre_t2_new_running_highs": float(new_highs), "pre_t2_max_drawdown": float(max_dd),
        "last_pre_t2_peak_to_t2_minutes": float((trade["t0_ms"] - last_peak_ms) / c10.MINUTE),
        "pre_t2_fraction_close_above_entry": float(np.mean(close > entry)),
        "pre_t2_fraction_close_within_0p5pct_peak": float(np.mean(within)),
        "pre_t2_return_std": float(np.std(returns, ddof=0)),
        "final_5m_return": h5, "final_5m_return_missing": float(h5 is None),
        "final_15m_return": h15, "final_15m_return_missing": float(h15 is None),
        "final_30m_return": h30, "final_30m_return_missing": float(h30 is None),
        "final_5m_minus_preceding_5m": a5, "acceleration_5m_missing": float(a5 is None),
        "final_15m_minus_preceding_15m": a15, "acceleration_15m_missing": float(a15 is None),
    }
    if set(values) != set(PATH_FEATURES): raise AssertionError("path schema mismatch")
    return values


def build_rows(repo: Path):
    data = c12.generate_frozen_panel(repo)
    manifest = json.loads((repo / "artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())
    source = {x["trade_id"]: x for x in manifest["rows"]}; trades = {t["trade_id"]: t for t in data["trades"]}
    eligible = []; excluded = Counter()
    for row in data["binary_rows"]:
        tr = trades[row["trade_id"]]
        target = c14.target_for_snapshot(row, tr, data["markets"][row["symbol"]], float(source[row["trade_id"]]["p0_raw_exit_price"]))
        if not target["eligible"]: excluded[target["reason"]] += 1; continue
        eligible.append(row | target | {"event_label": tr["terminal"], "p0_ms": tr["p0_ms"]})
    classes, summary, by = c16_classify(eligible)
    rows = []
    for tid, rr in sorted(by.items()):
        first = min(rr, key=lambda r: r["state_ms"]); tr = trades[tid]
        feat = dict(first["features"]); feat.update(path_features(tr, data["markets"][first["symbol"]]))
        rows.append({k: first[k] for k in ("trade_id", "symbol", "year", "entry_ms", "t0_ms", "state_ms", "terminal_ms", "event_label")} |
                    {"economic_class": classes[tid], "label": int(classes[tid] == "PREDOMINANTLY_HOLD"), "features": feat})
    return data, eligible, rows, excluded, summary


def c16_classify(rows):
    by = defaultdict(list)
    for r in rows: by[r["trade_id"]].append(r)
    classes = {}
    for tid, rr in by.items():
        hold_rate = float(np.mean([r["economic_state"] == "HOLD_BETTER" for r in rr]))
        exit_rate = float(np.mean([r["economic_state"] == "EXIT_BETTER" for r in rr]))
        classes[tid] = "PREDOMINANTLY_HOLD" if hold_rate > .8 else "PREDOMINANTLY_EXIT" if exit_rate > .8 else "MIXED"
    summary = {g: {"count": sum(v == g for v in classes.values()),
                   "year": dict(Counter(str(by[t][0]["year"]) for t, v in classes.items() if v == g)),
                   "symbol": dict(Counter(by[t][0]["symbol"] for t, v in classes.items() if v == g)),
                   "event": dict(Counter(by[t][0]["event_label"] for t, v in classes.items() if v == g))}
               for g in ("PREDOMINANTLY_HOLD", "PREDOMINANTLY_EXIT", "MIXED")}
    return classes, summary, by


def fit(rows, names):
    impute = {}; prepared = []
    for n in names:
        vals = [r["features"][n] for r in rows if r["features"][n] is not None]
        impute[n] = float(np.median(vals)) if vals else 0.0
    for r in rows: prepared.append(r | {"features": r["features"] | {n: impute[n] if r["features"][n] is None else r["features"][n] for n in names}})
    w = c10.trade_weights(prepared); wn = w / w.sum(); scaler = {}
    for n in names:
        x = np.asarray([r["features"][n] for r in prepared]); mean = float(wn @ x); sd = float(np.sqrt(wn @ ((x-mean)**2)))
        scaler[n] = {"mean": mean, "sd": sd if sd > 0 else 1.0}
    model = c8.fit_logistic(c10.design(prepared, names, scaler), np.asarray([r["label"] for r in prepared]), w)
    return {"names": names, "imputation": impute, "scaler": scaler, "model": model}


def predict(model, rows):
    prepared = [r | {"features": r["features"] | {n: model["imputation"][n] if r["features"][n] is None else r["features"][n] for n in model["names"]}} for r in rows]
    return c8.predict(model["model"], c10.design(prepared, model["names"], model["scaler"]))


def metrics(rows, p):
    if not rows: return None
    return c8.metrics(rows, np.asarray(p)) | {"calibration": c9.reliability(rows, np.asarray(p))}


def split_fold(rows, fold): return c10.split_fold(rows, fold)


def evaluate_2024(rows, m2_names=ALL_FEATURES):
    pooled = []; pred = defaultdict(list); defs = {}; models = []
    for fold, bounds in c10.FOLDS.items():
        train, valid = split_fold(rows, fold); rate = float(np.mean([r["label"] for r in train]))
        m1, m2 = fit(train, c11.NAMES), fit(train, m2_names)
        pooled.extend(valid); pred["M0"].extend(np.full(len(valid), rate)); pred["M1"].extend(predict(m1, valid)); pred["M2"].extend(predict(m2, valid)); models.append(m2)
        defs[fold] = {"bounds_ms": list(bounds), "training_trades": len(train), "validation_trades": len(valid),
                      "whole_trades": True, "training_before_validation": max(r["entry_ms"] for r in train) < min(r["entry_ms"] for r in valid),
                      "preprocessing_training_only": True}
    pp = {k: np.asarray(v) for k, v in pred.items()}
    return pooled, pp, {k: metrics(pooled, v) for k, v in pp.items()}, defs, models


def evaluate_2025(rows24, rows25):
    fitted = {"M1": fit(rows24, c11.NAMES), "M2": fit(rows24, ALL_FEATURES)}; rate = float(np.mean([r["label"] for r in rows24]))
    pp = {"M0": np.full(len(rows25), rate)} | {k: predict(v, rows25) for k, v in fitted.items()}
    return pp, {k: metrics(rows25, v) for k, v in pp.items()}, fitted


def comparison(mm):
    return {x: {"M1": mm["M1"][x], "M2": mm["M2"][x], "M2_minus_M1": mm["M2"][x]-mm["M1"][x],
                "improved": mm["M2"][x] < mm["M1"][x] if x in ("brier", "log_loss") else mm["M2"][x] > mm["M1"][x]}
            for x in ("brier", "log_loss", "auc")}


def subset(rows, pp, event="DETERIORATION_FIRST"):
    ix = np.asarray([r["event_label"] == event for r in rows]); rr = [r for r in rows if r["event_label"] == event]
    return {"trades": len(rr), "prevalence": float(np.mean([r["label"] for r in rr])) if rr else None,
            "models": {k: metrics(rr, v[ix]) for k, v in pp.items() if k in ("M1", "M2")}}


def symbols(rows, pp):
    out = {}
    for s in c10.SYMBOLS:
        ix = np.asarray([r["symbol"] == s for r in rows]); rr = [r for r in rows if r["symbol"] == s]
        out[s] = {k: metrics(rr, pp[k][ix]) for k in ("M1", "M2")}
    return out


def distribution(values):
    a = np.asarray(values, float)
    return {"n": len(a), "mean": float(a.mean()), "median": float(np.median(a)), "p10": float(np.quantile(a,.1)), "p90": float(np.quantile(a,.9))} if len(a) else None


def run(repo: Path):
    reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    contract = repo / CONTRACT_REL
    if sha(contract) != CONTRACT_SHA256: raise RuntimeError("C17 contract changed after prospective freeze")
    assert_feature_firewall(ALL_FEATURES + c10.SYMBOL_FEATURES)
    data, eligible, all_rows, excluded, classes = build_rows(repo)
    if len(all_rows) != len({r["trade_id"] for r in all_rows}): raise RuntimeError("one-row-per-trade invariant failed")
    binary = [r for r in all_rows if r["economic_class"] != "MIXED"]
    rows24 = [r for r in binary if r["year"] == 2024]; rows25 = [r for r in binary if r["year"] == 2025]
    pooled, pp24, m24, folds, fold_models = evaluate_2024(rows24); pp25, m25, fitted = evaluate_2025(rows24, rows25)
    comp24, comp25 = comparison(m24), comparison(m25); d24, d25 = subset(pooled, pp24), subset(rows25, pp25)
    ablation = {}
    for family, names in FAMILIES.items():
        _, _, mm, _, _ = evaluate_2024(rows24, tuple(n for n in ALL_FEATURES if n not in names))
        ablation[family] = {"removed": list(names), "metrics": mm["M2"], "versus_full_M2": {x: mm["M2"][x]-m24["M2"][x] for x in ("brier","log_loss","auc")}}
    sym24, sym25 = symbols(pooled, pp24), symbols(rows25, pp25)
    mixed = [r for r in all_rows if r["economic_class"] == "MIXED"]
    mixed_pred = {"2024_OOF": {"note": "MIXED trades are not in binary OOF validation cohorts; no OOF probabilities emitted"},
                  "2025": {k: distribution(predict(fitted[k], [r for r in mixed if r["year"] == 2025])) for k in ("M1","M2")}}
    full24 = {k: fit(rows24, c11.NAMES if k == "M1" else ALL_FEATURES) for k in ("M1","M2")}
    mixed_pred["2024_frozen_full_development_descriptive"] = {k: distribution(predict(full24[k], [r for r in mixed if r["year"] == 2024])) for k in ("M1","M2")}
    class_path = {}
    for g in ("PREDOMINANTLY_HOLD","PREDOMINANTLY_EXIT","MIXED"):
        rr = [r for r in all_rows if r["economic_class"] == g]
        class_path[g] = {n: distribution([r["features"][n] for r in rr if r["features"][n] is not None]) for n in PATH_FEATURES}
    coef = fitted["M2"]["model"]["coef"]; names = ["intercept"] + list(ALL_FEATURES) + list(c10.SYMBOL_FEATURES)
    assoc_groups = {"frozen_local_state": [], **{k: [] for k in FAMILIES}, "symbol": []}
    for n, v in zip(names[1:], coef[1:]):
        group = "frozen_local_state" if n in c11.NAMES else "symbol" if n in c10.SYMBOL_FEATURES else next(k for k,a in FAMILIES.items() if n in a)
        assoc_groups[group].append({"feature": n, "coefficient": float(v)})
    assoc = {"warning":"predictive associations only; no causal interpretation", "intercept":float(coef[0]), "groups":assoc_groups}
    proper = lambda c: all(c[x]["improved"] for x in ("brier","log_loss"))
    auc_both = comp24["auc"]["improved"] and comp25["auc"]["improved"]
    slopes = m24["M2"]["calibration"]["slope"] is not None and m24["M2"]["calibration"]["slope"] > 0 and m25["M2"]["calibration"]["slope"] is not None and m25["M2"]["calibration"]["slope"] > 0
    robust_symbols = sum(sym24[s]["M2"]["brier"] < sym24[s]["M1"]["brier"] and sym25[s]["M2"]["brier"] < sym25[s]["M1"]["brier"] for s in c10.SYMBOLS) > 1
    supported = proper(comp24) and proper(comp25) and auc_both and slopes and robust_symbols
    weak = (any(comp24[x]["improved"] for x in ("brier","log_loss")) and any(comp25[x]["improved"] for x in ("brier","log_loss"))) or (proper(comp24) and any(comp25[x]["improved"] for x in ("brier","log_loss"))) or (proper(comp25) and any(comp24[x]["improved"] for x in ("brier","log_loss")))
    label = "PATH_SIGNAL_SUPPORTED" if supported else "WEAK_PATH_SIGNAL" if weak else "NO_USEFUL_PATH_SIGNAL"
    rec = {"source_first_t2_trades":845,"binary_source_trades":843,"causal_physical_snapshots":len(data["binary_rows"]),"eligible_target_snapshots":len(eligible),
           "eligible_target_trades":len(all_rows),"one_row_trade_rows":len(all_rows),"primary_binary_trades":len(binary),"mixed_trades":len(mixed),
           "by_year":dict(Counter(str(r["year"]) for r in all_rows)),"excluded_snapshots":dict(excluded)}
    schema = {"frozen_before_evaluation":True,"M1":list(c11.NAMES)+list(c10.SYMBOL_FEATURES),"M2":list(ALL_FEATURES)+list(c10.SYMBOL_FEATURES),
              "families":{k:list(v) for k,v in FAMILIES.items()},"definitions":{"bar_interval":"completed 1m bars with opens in [entry_ms,t0_ms)","range":"(maximum high - minimum low) / entry price","efficiency":"absolute final completed close/entry return divided by cumulative absolute 1m returns seeded at entry price","new_high":"strict bar high above prior running peak initialized at entry price","drawdown":"minimum low/running peak - 1","volatility":"population SD (ddof=0) of 1m close returns seeded at entry price","late_return":"final completed close divided by close h minutes earlier, entry price may be the boundary seed","imputation":"training median; zero only if a training feature is wholly missing; explicit missing indicators"}}
    audit = {"status":"PASS","trades":len(all_rows),"entry_inclusive":True,"t2_exclusive":True,"last_permitted_bar_open":"t0_ms-60000","contiguous_minutes_required":True,"first_snapshot_only":all(r["state_ms"]==min(x["state_ms"] for x in eligible if x["trade_id"]==r["trade_id"]) for r in all_rows)}
    predicates = {"classification":label,"criteria":{"proper_scores_both_years":proper(comp24) and proper(comp25),"auc_both_years":auc_both,"positive_M2_calibration_slope_both_years":slopes,"not_dependent_on_one_symbol":robust_symbols},"comparison_2024":comp24,"comparison_2025":comp25}
    out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True)
    artifacts={
      "run_manifest":{"version":"C17_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":os.environ.get("CONDA_DEFAULT_ENV")},
      "provenance":{"contract_sha256":CONTRACT_SHA256,"dependencies":{"c7_population":sha(repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json"),"c11_final":sha(repo/"artifacts/c11_dynamic_post_t2_state/final_summary.json"),"c14_final":sha(repo/"artifacts/c14_post_t2_economic_state/final_summary.json"),"c15_final":sha(repo/"artifacts/c15_economic_state_temporal_structure/final_summary.json"),"c16_final":sha(repo/"artifacts/c16_cross_asset_economic_state/final_summary.json")},"no_2026_access":True},
      "leakage_firewall":{"status":"PASS","features_checked":list(ALL_FEATURES),"target_builder_separate":True,"first_snapshot_only":True,"post_first_snapshot_predictors":False,"target_derived_predictors":False},
      "population_reconciliation":rec,"trade_class_definition":{"hold":">80% HOLD_BETTER","exit":">80% EXIT_BETTER","mixed":"otherwise","counts":classes},
      "path_feature_schema":schema,"path_reconstruction_audit":audit,"fold_definitions":folds,"model_metrics_2024":m24,"calibration_2024":{k:v["calibration"] for k,v in m24.items()},
      "deterioration_subset_2024":d24,"family_ablation_2024":ablation,"frozen_model_procedure":{"M0":"training class prevalence","M1":"fixed C11 local state logistic","M2":"same logistic plus frozen path descriptors","fixed_L2_penalty":1.0,"training_only_preprocessing":True,"search":False},
      "model_metrics_2025":m25,"calibration_2025":{k:v["calibration"] for k,v in m25.items()},"deterioration_subset_2025":d25,
      "mixed_trade_summary":{"counts":classes["MIXED"],"predicted_probabilities":mixed_pred,"path_feature_distributions_by_class":class_path},
      "symbol_metrics":{"2024_OOF":sym24,"2025":sym25},"feature_associations":assoc,"interpretation_predicates":predicates}
    artifacts["final_summary"]={"contract_sha256":CONTRACT_SHA256,"population":rec,"trade_classes":classes,"leakage_firewall":artifacts["leakage_firewall"],"path_reconstruction":audit,"path_feature_schema":schema,"metrics_2024":m24,"comparison_2024":comp24,"deterioration_2024":d24,"ablation_2024":ablation,"metrics_2025":m25,"comparison_2025":comp25,"deterioration_2025":d25,"mixed_trades":artifacts["mixed_trade_summary"],"symbol_robustness":artifacts["symbol_metrics"],"feature_associations":assoc,"classification":label,"entry_to_t2_path_contains_useful_information":supported,"limitations":["observational predictive characterization, not causal evidence","economic class is a realized future-derived label and never a predictor","2024 OOF uses frozen chronological cohorts; 2025 is a single untouched validation","small symbol/subgroup cells can make AUC or calibration unstable"],"implication_for_c18":"C17 stops here; C18 requires a separately frozen prospective contract.","confirmations":{"one_row_per_trade":True,"policy_or_pnl_optimization":False,"feature_model_or_horizon_search":False,"accessed_2026":False,"started_c18":False}}
    for name,value in artifacts.items(): write(out/f"{name}.json",value)
    hashes={p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"}; write(out/"reproducibility_hashes.json",hashes)
    return artifacts["final_summary"]
