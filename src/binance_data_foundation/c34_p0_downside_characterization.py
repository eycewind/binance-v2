"""C34: frozen P0 market-state downside-risk characterization.

This module deliberately has no E1/trade-state input.  It reads the five
explicitly named, accepted pre-2026 sources and treats P0 as an hourly market
event.  Future prices are used only after event/reference membership and
matching have been fixed from causal state.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .c2_entries import hourly_sma24
from .ingest import sha256_file

CONTRACT_REL = "contracts/C34_P0_DOWNSIDE_RISK_CHARACTERIZATION_CONTRACT.md"
CONTRACT_SHA256 = "3824b467c5e64e31bb400fe3eefcd084f70d98be7ec5f378a0d39479e98e195b"
OUTPUT_REL = "artifacts/c34_p0_downside_characterization"
HOURLY_REL = "data/normalized/c2_frozen_inputs"
MINUTE_REL = "data/normalized/c2_history"
P0_VERSION = "P0_H1_SMA24_CROSSDOWN_V1"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
HORIZONS = (1, 3, 6, 12, 24, 48)
THRESHOLD_HORIZONS = (3, 6, 12, 24, 48)
THRESHOLDS = (.005, .01, .02, .03)
HOUR_MS = 3_600_000
MINUTE_MS = 60_000
START_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z
END_MS = 1_767_225_600_000    # 2026-01-01T00:00:00Z, exclusive
SEED = 20261001
REPLICATES = 2000
FEATURES = ("current_1h_return", "trailing_24h_realized_volatility", "close_over_sma24_minus_1")
REQUIRED_OUTPUTS = (
    "run_manifest.json", "provenance.json", "p0_definition_reconciliation.json",
    "event_population.json", "event_spacing.json", "reference_population.json",
    "matched_reference.json", "forward_return_profiles.json", "forward_mae_profiles.json",
    "forward_mfe_profiles.json", "downside_thresholds.json", "upside_thresholds.json",
    "downside_asymmetry.json", "yearly_results.json", "symbol_results.json",
    "month_results.json", "trade_bootstrap_intervals.json", "month_bootstrap_intervals.json",
    "interpretation_predicates.json", "final_summary.json", "reproducibility_hashes.json",
)


def reject_2026(path: os.PathLike[str] | str) -> None:
    """Fail closed on future-labelled paths without probing their existence."""
    if any("2026" in part.lower() for part in os.fspath(path).replace("\\", "/").split("/")):
        raise PermissionError("C34 prohibits 2026 data and metadata access")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _semantic_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def _year(ms: int) -> str:
    return _iso(ms)[:4]


def _month(ms: int) -> str:
    return _iso(ms)[:7]


def _q(a: np.ndarray, p: float) -> float | None:
    return float(np.quantile(a, p, method="linear")) if len(a) else None


def distribution(values: list[float] | np.ndarray) -> dict:
    a = np.asarray(values, dtype=float)
    if not len(a):
        return {"count": 0, "mean": None, "median": None, "p05": None, "p10": None,
                "p25": None, "p75": None, "p90": None, "p95": None,
                "negative_fraction": None, "positive_fraction": None}
    return {"count": int(len(a)), "mean": float(a.mean()), "median": float(np.median(a)),
            "p05": _q(a, .05), "p10": _q(a, .10), "p25": _q(a, .25),
            "p75": _q(a, .75), "p90": _q(a, .90), "p95": _q(a, .95),
            "negative_fraction": float(np.mean(a < 0)), "positive_fraction": float(np.mean(a > 0))}


def load_hours(path: Path) -> list[dict]:
    reject_2026(path)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if int(r["open_time_ms"]) < END_MS]
    if any(int(r["available_at_ms"]) != int(r["open_time_ms"]) + HOUR_MS for r in rows):
        raise RuntimeError(f"noncanonical hourly availability: {path.name}")
    return rows


def load_minutes(path: Path) -> dict[str, np.ndarray]:
    reject_2026(path)
    out = {k: [] for k in ("ts", "open", "high", "low")}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ts = int(row["open_time_ms"])
            if ts >= END_MS:
                break
            out["ts"].append(ts); out["open"].append(float(row["open"])); out["high"].append(float(row["high"])); out["low"].append(float(row["low"]))
    result = {k: np.asarray(v, dtype=np.int64 if k == "ts" else float) for k, v in out.items()}
    if len(result["ts"]) < 2 or np.any(np.diff(result["ts"]) != MINUTE_MS):
        raise RuntimeError(f"accepted minute source is not contiguous: {path.name}")
    return result


def causal_hour_rows(symbol: str, hours: list[dict]) -> list[dict]:
    """Return every 2024-25 hour with causal state and exact cross-down flag."""
    sma = hourly_sma24(hours)
    close = np.asarray([float(r["close"]) for r in hours])
    result = []
    for i in range(24, len(hours)):
        t = int(hours[i]["available_at_ms"])
        if not START_MS <= t < END_MS or sma[i] is None or sma[i - 1] is None:
            continue
        # Twenty-four one-hour close-to-close returns ending at the current close.
        prior = close[i - 24:i + 1]
        rets = prior[1:] / prior[:-1] - 1
        result.append({"symbol": symbol, "t_ms": t, "year": _year(t), "month": _month(t),
                       "is_p0": bool(close[i - 1] >= sma[i - 1] and close[i] < sma[i]),
                       "current_1h_return": float(close[i] / close[i - 1] - 1),
                       "trailing_24h_realized_volatility": float(np.sqrt(np.sum(rets * rets))),
                       "close_over_sma24_minus_1": float(close[i] / sma[i] - 1)})
    return result


def evaluate_forward(row: dict, minutes: dict[str, np.ndarray]) -> dict | None:
    """Evaluate fixed paths from exact boundary open; never used for membership."""
    ts = minutes["ts"]; t = int(row["t_ms"]); start = int(np.searchsorted(ts, t))
    if start >= len(ts) or int(ts[start]) != t or start + 48 * 60 >= len(ts):
        return None
    ref = float(minutes["open"][start]); out = dict(row); out["reference_price"] = ref
    for h in HORIZONS:
        end = start + h * 60
        # Minute bars [t,t+H) cover the continuous path in (t,t+H]; also
        # include the exact endpoint open for explicit endpoint consistency.
        lows = minutes["low"][start:end]; highs = minutes["high"][start:end]
        jlo, jhi = int(np.argmin(lows)), int(np.argmax(highs))
        endpoint = float(minutes["open"][end])
        lo, hi = float(lows[jlo]), float(highs[jhi])
        out[f"return_{h}h"] = endpoint / ref - 1
        out[f"mae_{h}h"] = min(lo / ref - 1, endpoint / ref - 1, 0.0)
        out[f"mfe_{h}h"] = max(hi / ref - 1, endpoint / ref - 1, 0.0)
        out[f"time_to_mae_{h}h_minutes"] = float(jlo) if lo / ref - 1 <= min(endpoint / ref - 1, 0.0) else float(h * 60)
        out[f"time_to_mfe_{h}h_minutes"] = float(jhi) if hi / ref - 1 >= max(endpoint / ref - 1, 0.0) else float(h * 60)
        if out[f"mae_{h}h"] == 0.0: out[f"time_to_mae_{h}h_minutes"] = 0.0
        if out[f"mfe_{h}h"] == 0.0: out[f"time_to_mfe_{h}h_minutes"] = 0.0
        if h in THRESHOLD_HORIZONS:
            for threshold in THRESHOLDS:
                dn = np.flatnonzero(lows / ref - 1 <= -threshold)
                up = np.flatnonzero(highs / ref - 1 >= threshold)
                tag = str(int(threshold * 1000)).zfill(2)
                out[f"down_{tag}_{h}h"] = bool(len(dn)); out[f"down_time_{tag}_{h}h_minutes"] = float(dn[0]) if len(dn) else None
                out[f"up_{tag}_{h}h"] = bool(len(up)); out[f"up_time_{tag}_{h}h_minutes"] = float(up[0]) if len(up) else None
    return out


def match_state(events: list[dict], controls: list[dict]) -> tuple[list[dict], dict]:
    """Deterministic outcome-blind 1:1 nearest neighbor, with replacement.

    Within each symbol/year/month candidate pool, each feature is scaled by
    the candidate population standard deviation (zero scales become one).
    Squared standardized Euclidean distance is minimized; timestamp is the
    deterministic tie-break. Outcomes are neither accepted nor referenced.
    """
    pools: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in controls: pools[(r["symbol"], r["year"], r["month"])].append(r)
    pairs, distances = [], []
    for event in sorted(events, key=lambda r: (r["t_ms"], r["symbol"])):
        candidates = sorted(pools[(event["symbol"], event["year"], event["month"])], key=lambda r: r["t_ms"])
        if not candidates: raise RuntimeError("no matched-state candidate")
        x = np.asarray([[r[f] for f in FEATURES] for r in candidates]); target = np.asarray([event[f] for f in FEATURES])
        scale = x.std(axis=0); scale[scale == 0] = 1.0
        d = np.sum(((x - target) / scale) ** 2, axis=1); j = int(np.argmin(d)); control = candidates[j]
        pair = {"pair_id": f"{event['symbol']}|{event['t_ms']}", "event": event, "control": control,
                "distance": float(math.sqrt(d[j]))}
        pairs.append(pair); distances.append(pair["distance"])
    audit = {"algorithm": "1:1 nearest neighbor with replacement", "strata": ["symbol", "calendar year", "UTC month"],
             "features": list(FEATURES), "scaling": "candidate-pool population standard deviation; zero replaced by 1",
             "distance": "Euclidean on standardized causal features", "tie_break": "earliest t_ms",
             "outcomes_used": False, "pair_count": len(pairs), "unique_control_count": len({p["control"]["symbol"] + str(p["control"]["t_ms"]) for p in pairs}),
             "distance_profile": distribution(distances)}
    return pairs, audit


def _profile(rows: list[dict], prefix: str) -> dict:
    return {f"{h}h": distribution([r[f"{prefix}_{h}h"] for r in rows]) | ({
        "time_to_extreme_minutes": distribution([r[f"time_to_{prefix}_{h}h_minutes"] for r in rows])
    } if prefix in ("mae", "mfe") else {}) for h in HORIZONS}


def threshold_profile(rows: list[dict], side: str) -> dict:
    out = {}
    for h in THRESHOLD_HORIZONS:
        out[f"{h}h"] = {}
        for threshold in THRESHOLDS:
            tag = str(int(threshold * 1000)).zfill(2); hits = [r for r in rows if r[f"{side}_{tag}_{h}h"]]
            out[f"{h}h"][f"{threshold:.3f}"] = {"count": len(rows), "hits": len(hits), "incidence": len(hits) / len(rows) if rows else None,
                "median_time_to_threshold_minutes_among_hits": float(np.median([r[f"{side}_time_{tag}_{h}h_minutes"] for r in hits])) if hits else None}
    return out


def measures(a: list[dict], b: list[dict]) -> dict:
    out = {}
    for h in HORIZONS:
        ar=np.asarray([r[f"return_{h}h"] for r in a]); br=np.asarray([r[f"return_{h}h"] for r in b]);
        am=np.asarray([r[f"mae_{h}h"] for r in a]); bm=np.asarray([r[f"mae_{h}h"] for r in b]);
        af=np.asarray([r[f"mfe_{h}h"] for r in a]); bf=np.asarray([r[f"mfe_{h}h"] for r in b]);
        item={"event_count":len(a),"reference_count":len(b),"delta_mean_return":float(ar.mean()-br.mean()),"delta_median_return":float(np.median(ar)-np.median(br)),
              "delta_mean_mae":float(am.mean()-bm.mean()),"delta_median_mae":float(np.median(am)-np.median(bm)),
              "delta_mean_mfe":float(af.mean()-bf.mean()),"delta_median_mfe":float(np.median(af)-np.median(bf)),
              "event_downside_asymmetry":float(abs(am.mean())-af.mean()),"reference_downside_asymmetry":float(abs(bm.mean())-bf.mean()),
              "downside_asymmetry_difference":float((abs(am.mean())-af.mean())-(abs(bm.mean())-bf.mean())),
              "event_probability_abs_mae_gt_mfe":float(np.mean(abs(am)>af)),"reference_probability_abs_mae_gt_mfe":float(np.mean(abs(bm)>bf))}
        for threshold in THRESHOLDS:
            tag=str(int(threshold*1000)).zfill(2); key=f"down_{tag}_{h}h"
            if key in a[0]: item[f"delta_probability_down_{threshold:.3f}"]=float(np.mean([r[key] for r in a])-np.mean([r[key] for r in b]))
        out[f"{h}h"]=item
    return out


def bootstrap(pairs: list[dict], unit: str) -> dict:
    """Paired event or whole-UTC-month bootstrap from one frozen PCG64 stream."""
    groups = [[p] for p in pairs] if unit == "event" else [list(v) for _,v in sorted(_group_pairs(pairs, lambda p: p["event"]["month"]).items())]
    rng=np.random.Generator(np.random.PCG64(SEED)); reps={k:[] for k in ("delta_return_24h","delta_mae_24h","delta_probability_down_0.010","delta_probability_down_0.020","downside_asymmetry_difference")}
    for _ in range(REPLICATES):
        chosen=[p for j in rng.integers(len(groups),size=len(groups)) for p in groups[int(j)]]
        e=[p["event"] for p in chosen]; c=[p["control"] for p in chosen]; m=measures(e,c)["24h"]
        reps["delta_return_24h"].append(m["delta_mean_return"]); reps["delta_mae_24h"].append(m["delta_mean_mae"])
        reps["delta_probability_down_0.010"].append(m["delta_probability_down_0.010"]); reps["delta_probability_down_0.020"].append(m["delta_probability_down_0.020"])
        reps["downside_asymmetry_difference"].append(m["downside_asymmetry_difference"])
    return {"unit":unit,"iterations":REPLICATES,"generator":"PCG64","seed":SEED,"paired":True,"quantile_method":"linear Type-7",
            "group_count":len(groups),"intervals":{k:{"point_estimate":float(np.mean(v)),"ci95":[_q(np.asarray(v),.025),_q(np.asarray(v),.975)],"replicate_sha256":hashlib.sha256(np.asarray(v,dtype="<f8").tobytes()).hexdigest()} for k,v in reps.items()}}


def _group_pairs(rows, key):
    out=defaultdict(list)
    for r in rows: out[key(r)].append(r)
    return out


def run(repo: Path) -> dict:
    repo=repo.resolve(); contract=repo/CONTRACT_REL
    if sha256_file(contract) != CONTRACT_SHA256: raise RuntimeError("frozen C34 contract hash mismatch")
    out=repo/OUTPUT_REL; source_hashes={}; events=[]; controls=[]; raw_event_counts=Counter(); excluded_no_48h=Counter()
    for symbol in SYMBOLS:
        hp=repo/HOURLY_REL/f"{symbol}_1h.csv.gz"; mp=repo/MINUTE_REL/f"{symbol}_1m.csv.gz"
        reject_2026(hp); reject_2026(mp); source_hashes[str(hp.relative_to(repo))]=sha256_file(hp); source_hashes[str(mp.relative_to(repo))]=sha256_file(mp)
        states=causal_hour_rows(symbol,load_hours(hp)); minutes=load_minutes(mp)
        for state in states:
            if state["is_p0"]: raw_event_counts[(state["year"],state["symbol"],state["month"])]+=1
            outcome=evaluate_forward(state,minutes)
            if outcome is None:
                if state["is_p0"]: excluded_no_48h[(state["year"],state["symbol"],state["month"])]+=1
                continue
            (events if state["is_p0"] else controls).append(outcome)
    events.sort(key=lambda r:(r["t_ms"],r["symbol"])); controls.sort(key=lambda r:(r["t_ms"],r["symbol"])); pairs,match_audit=match_state(events,controls)
    matched=[p["control"] for p in pairs]
    def counts(rows,key): return dict(sorted(Counter(key(r) for r in rows).items()))
    total_detected=sum(raw_event_counts.values())
    pop={"p0_version":P0_VERSION,"total_events":total_detected,"fixed_48h_analyzable_events":len(events),
         "excluded_without_complete_48h_pre_2026_path":sum(excluded_no_48h.values()),
         "by_year":dict(sorted(Counter({y:sum(v for (yy,_,_),v in raw_event_counts.items() if yy==y) for y in ("2024","2025")}).items())),
         "by_symbol":dict(sorted(Counter({s:sum(v for (_,ss,_),v in raw_event_counts.items() if ss==s) for s in SYMBOLS}).items())),
         "by_month":dict(sorted(Counter({m:sum(v for (_,_,mm),v in raw_event_counts.items() if mm==m) for m in sorted({k[2] for k in raw_event_counts})}).items())),
         "by_year_symbol_month":{"|".join(k):v for k,v in sorted(raw_event_counts.items())},
         "fixed_48h_analyzable_by_year":counts(events,lambda r:r["year"]),"fixed_48h_analyzable_by_symbol":counts(events,lambda r:r["symbol"]),"fixed_48h_analyzable_by_month":counts(events,lambda r:r["month"])}
    spacing=[]
    for symbol in SYMBOLS:
        x=sorted(r["t_ms"] for r in events if r["symbol"]==symbol); spacing.extend((b-a)/HOUR_MS for a,b in zip(x,x[1:]))
    spacing_doc={"units":"hours","no_refractory_period":True,"pooled":distribution(spacing),"by_symbol":{s:distribution(np.diff(sorted(r["t_ms"] for r in events if r["symbol"]==s))/HOUR_MS) for s in SYMBOLS}}
    rec={"status":"PASS","p0_version":P0_VERSION,"rule":"previous completed H1 close >= previous inclusive causal SMA24 AND current completed H1 close < current inclusive causal SMA24",
         "h1":"UTC-aligned 60-minute bars; available at end boundary","sma24":"arithmetic mean of 24 contiguous completed H1 closes ending with current bar","evaluation_cadence":"every completed hour","reference_price":"exact 1-minute open at decision boundary","e1_or_trade_state_used":False,"refractory_period":False}
    refdoc={"eligible_non_p0_count":len(controls),"eligibility":"same universe and 2024-25 period; causal features complete; exact reference minute and complete 48h pre-2026 path; not P0 at t","by_year":counts(controls,lambda r:r["year"]),"by_symbol":counts(controls,lambda r:r["symbol"]),"by_month":counts(controls,lambda r:r["month"])}
    _write(out/"p0_definition_reconciliation.json",rec); _write(out/"event_population.json",pop); _write(out/"event_spacing.json",spacing_doc); _write(out/"reference_population.json",refdoc); _write(out/"matched_reference.json",match_audit)
    _write(out/"forward_return_profiles.json",{"event":_profile(events,"return"),"eligible_non_p0":_profile(controls,"return"),"matched":_profile(matched,"return")})
    _write(out/"forward_mae_profiles.json",{"event":_profile(events,"mae"),"eligible_non_p0":_profile(controls,"mae"),"matched":_profile(matched,"mae")})
    _write(out/"forward_mfe_profiles.json",{"event":_profile(events,"mfe"),"eligible_non_p0":_profile(controls,"mfe"),"matched":_profile(matched,"mfe")})
    _write(out/"downside_thresholds.json",{"event":threshold_profile(events,"down"),"eligible_non_p0":threshold_profile(controls,"down"),"matched":threshold_profile(matched,"down")})
    _write(out/"upside_thresholds.json",{"event":threshold_profile(events,"up"),"eligible_non_p0":threshold_profile(controls,"up"),"matched":threshold_profile(matched,"up")})
    unmatched=measures(events,controls); matched_cmp=measures(events,matched)
    _write(out/"downside_asymmetry.json",{"unmatched":{h:{k:v for k,v in d.items() if "asymmetry" in k or "abs_mae" in k} for h,d in unmatched.items()},"matched":{h:{k:v for k,v in d.items() if "asymmetry" in k or "abs_mae" in k} for h,d in matched_cmp.items()}})
    yearly={}; symbol_doc={}; month_doc={}
    for y in ("2024","2025"):
        ep=[r for r in events if r["year"]==y]; cp=[p["control"] for p in pairs if p["event"]["year"]==y]
        yearly[y]={"event_count":len(ep),"unmatched":measures(ep,[r for r in controls if r["year"]==y]),"matched":measures(ep,cp)}
    for s in SYMBOLS:
        ep=[r for r in events if r["symbol"]==s]; cp=[p["control"] for p in pairs if p["event"]["symbol"]==s]
        symbol_doc[s]={"event_count":len(ep),"unmatched":measures(ep,[r for r in controls if r["symbol"]==s]),"matched":measures(ep,cp)}
    for m in sorted(set(r["month"] for r in events)):
        ep=[r for r in events if r["month"]==m]; cp=[p["control"] for p in pairs if p["event"]["month"]==m]
        month_doc[m]={"event_count":len(ep),"matched_24h":measures(ep,cp)["24h"]}
    _write(out/"yearly_results.json",yearly); _write(out/"symbol_results.json",symbol_doc); _write(out/"month_results.json",month_doc)
    trade={g:bootstrap([p for p in pairs if g=="pooled" or p["event"]["year"]==g],"event") for g in ("pooled","2024","2025")}
    month={g:bootstrap([p for p in pairs if g=="pooled" or p["event"]["year"]==g],"UTC_month") for g in ("pooled","2024","2025")}
    _write(out/"trade_bootstrap_intervals.json",trade); _write(out/"month_bootstrap_intervals.json",month)
    y24=yearly["2024"]["matched"]["24h"]; y25=yearly["2025"]["matched"]["24h"]; pooled_ci=month["pooled"]["intervals"]["delta_mae_24h"]["ci95"]
    symbols_worse=sum(d["matched"]["24h"]["delta_mean_mae"]<0 for d in symbol_doc.values()); months_worse=sum(d["matched_24h"]["delta_mean_mae"]<0 for d in month_doc.values())
    pred={"worse_mae_both_years":y24["delta_mean_mae"]<0 and y25["delta_mean_mae"]<0,"lower_return_both_years":y24["delta_mean_return"]<0 and y25["delta_mean_return"]<0,
          "higher_down_1pct_both_years":y24["delta_probability_down_0.010"]>0 and y25["delta_probability_down_0.010"]>0,"pooled_month_bootstrap_delta_mae_excludes_zero":pooled_ci[1]<0 or pooled_ci[0]>0,
          "symbol_breadth":{"worse_count":symbols_worse,"total":len(SYMBOLS),"not_explained_by_one_symbol":symbols_worse>=3},"month_breadth":{"worse_count":months_worse,"total":len(month_doc),"not_explained_by_one_isolated_month":months_worse>1 and months_worse/len(month_doc)>=.5}}
    reproducible=all((pred["worse_mae_both_years"],pred["lower_return_both_years"],pred["higher_down_1pct_both_years"],pred["pooled_month_bootstrap_delta_mae_excludes_zero"],pred["symbol_breadth"]["not_explained_by_one_symbol"],pred["month_breadth"]["not_explained_by_one_isolated_month"]))
    directional=sum((y24["delta_mean_mae"]<0,y25["delta_mean_mae"]<0,y24["delta_mean_return"]<0,y25["delta_mean_return"]<0,y24["delta_probability_down_0.010"]>0,y25["delta_probability_down_0.010"]>0))>=4
    classification="REPRODUCIBLE_P0_DOWNSIDE_SIGNAL" if reproducible else ("WEAK_P0_DOWNSIDE_SIGNAL" if directional else "NO_USEFUL_P0_DOWNSIDE_SIGNAL")
    pred.update({"directional_predicates_true_of_six":sum((y24["delta_mean_mae"]<0,y25["delta_mean_mae"]<0,y24["delta_mean_return"]<0,y25["delta_mean_return"]<0,y24["delta_probability_down_0.010"]>0,y25["delta_probability_down_0.010"]>0)),"classification":classification,"predicate_operationalization_frozen_before_outcome_execution":True})
    _write(out/"interpretation_predicates.json",pred)
    final={"classification":classification,"contract_sha256":CONTRACT_SHA256,"p0_version":P0_VERSION,"total_events":total_detected,"fixed_48h_analyzable_events":len(events),"eligible_non_p0_count":len(controls),"matched_pair_count":len(pairs),
           "unmatched_comparison":unmatched,"matched_comparison":matched_cmp,"no_strategy_constructed":True,"no_e1_or_trade_state_used":True,"no_2026_data_or_metadata_accessed":True,"nothing_staged_committed_or_pushed_by_run":True}
    _write(out/"final_summary.json",final)
    provenance={"contract_sha256":CONTRACT_SHA256,"source_hashes":source_hashes,"implementation_sha256":sha256_file(Path(__file__)),"environment":"binance-v2-research","python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"git_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip(),"rng":{"generator":"PCG64","seed":SEED,"iterations":REPLICATES},"no_2026_access":True}
    _write(out/"provenance.json",provenance); _write(out/"run_manifest.json",{"version":"C34_RUN_V1","status":"COMPLETE","classification":classification,"created_at_utc":datetime.now(timezone.utc).isoformat(),"required_artifacts":list(REQUIRED_OUTPUTS),"row_level_artifacts_written":False})
    hashes={name:sha256_file(out/name) for name in REQUIRED_OUTPUTS if name!="reproducibility_hashes.json"}; _write(out/"reproducibility_hashes.json",{"artifact_sha256":hashes,"verified_after_write":all(sha256_file(out/name)==digest for name,digest in hashes.items())})
    return final
