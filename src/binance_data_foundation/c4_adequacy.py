from __future__ import annotations

import csv
import bisect
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .c2_common import ENTRY_COLUMNS, STUDY_END_MS, SYMBOLS, hash_rows, iso, write_json
from .c2_p0 import HORIZON_COLUMNS
from .c3_milestone import DenseSeries, EXPECTED_COMMON_HORIZON_HASH, EXPECTED_FROZEN_ENTRY_HASH, EXPECTED_NORMALIZED_HASHES, _load_gzip_series, _read_csv_verified
from .ingest import sha256_file

MINUTE, FIVE_MINUTES, HOUR = 60_000, 300_000, 3_600_000
DATASET_VERSION = "C4_SEQUENTIAL_EXIT_STATE_DATASET_V1"
SNAPSHOT_VERSION = "C4_COMPLETED_5M_LANDMARK_V1"
T1 = "C4_T1_CONT_PLUS1_VS_REV_MINUS075_H60_V1"
T2 = "C4_T2_GIVEBACK50_VS_NEWPEAK050_H60_V1"
TARGET_VERSIONS = {"T1": T1, "T2": T2}
ACCEPTED_CORE_HASHES = {
    "T1": "c9e519e0d2881f261850b13fff87c02403d28821fbcc083421c4c4b398e1c811",
    "T2": "b0dc7444d97fc17f1c81510c68509d47ff374bb16bd7578956b9f5dcb519a417",
}
ADEQUACY_DECISIONS = {"T1": "ADEQUATE FOR MODELING", "T2": "ADEQUATE FOR MODELING"}
ADEQUACY_THRESHOLDS = {
    "minimum_unique_resolved_trades_per_class": 150,
    "minimum_total_resolved_trades": 300,
    "minimum_entry_weeks": 40,
    "minimum_months": 9,
    "required_symbol_count": 5,
    "minimum_class_entry_weeks": 40,
    "minimum_class_months": 9,
    "require_each_class_in_all_symbols": True,
    "minimum_class_symbol_unique_resolved_trades": 20,
    "maximum_single_trade_snapshot_concentration": 0.05,
    "maximum_entry_week_concentration": 0.15,
    "maximum_snapshot_month_concentration": 0.20,
    "maximum_overall_censoring": 0.20,
    "maximum_subgroup_censoring": 0.20,
    "subgroup_censoring_minimum_eligible_rows": 100,
    "maximum_ambiguity": 0.01,
    "minimum_nonempty_four_entry_week_bootstrap_blocks_per_split": 2,
    "reliability_bin_minimum_unique_resolved_trades": 30,
    "class_bin_unstable_below_unique_event_trades": 10,
    "calibration_intercept_slope_minimum_unique_event_trades": 50,
}
PREDECESSORS = {"C2_accepted_revision": "ab08b62", "C2_frozen_entry_hash": EXPECTED_FROZEN_ENTRY_HASH,
    "C2_common_horizon_hash": EXPECTED_COMMON_HORIZON_HASH,
    "C3_execution_revision": "8cdfe4be2064e4c8aa98642eb655da07066d9832",
    "C3_input_manifest_hash": "cb5dd90fdffaca618a1b504e686206012d73b725d21e83ee1ff1091155e9fd3f"}
BOOTSTRAP_CONFIG = {"generator": "PCG64", "seed": 20240923, "replicates": 2000, "block_length_entry_weeks": 4, "blocks": "overlapping_non_circular", "draws": "ceil(W/4)_with_replacement", "empty_block_policy": "reject_and_redraw", "attachment": "whole_trade", "multiplicity": "preserved_no_deduplication", "quantile_method": "linear", "hyndman_fan_type": 7, "interval_levels": [0.025, 0.975]}

AUDIT_COLUMNS = (
    "dataset_version", "target_id", "trade_id", "snapshot_id", "row_id", "symbol", "entry_fixture_id",
    "entry_execution_ts", "entry_execution_ms", "entry_price", "snapshot_ts", "snapshot_ms",
    "snapshot_interval_start_ts", "snapshot_close", "elapsed_minutes", "elapsed_5m_bars",
    "common_horizon_end_ts", "common_horizon_end_ms", "nominal_target_end_ts", "observable_target_end_ts",
    "target_eligible", "target_ineligible_reason", "upper_barrier", "lower_barrier", "running_peak",
    "running_mfe", "current_return", "drawdown_from_running_peak", "peak_gain_retained_fraction",
    "already_beyond_giveback_state", "t1_upper_distance_assertion", "t1_lower_distance_assertion",
    "event_class", "resolution_ts", "resolution_price", "event_timing", "resolved", "ambiguous",
    "ambiguity_reason", "censored", "censor_reason", "raw_trade_weight", "temporal_partition",
    "trade_entry_week", "snapshot_week", "snapshot_month", "snapshot_quarter", "forward_start_ms", "forward_end_ms"
)

def _week(ms: int) -> str:
    d = datetime.fromtimestamp(ms / 1000, timezone.utc)
    monday = d.date().fromordinal(d.date().toordinal() - d.weekday())
    return monday.isoformat()

def _month(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")

def _quarter(ms: int) -> str:
    d = datetime.fromtimestamp(ms / 1000, timezone.utc)
    return f"{d.year}-Q{(d.month - 1)//3 + 1}"

def _partition(entry_ms: int) -> str:
    if entry_ms < 1704067200000:
        return "pre_2024_excluded"
    if entry_ms < 1719792000000:
        return "2024_fold_A_train"
    if entry_ms < 1727740800000:
        return "2024_fold_A_validate_fold_B_train"
    if entry_ms < 1735689600000:
        return "2024_fold_B_validate"
    if entry_ms < STUDY_END_MS:
        return "2025_locked"
    raise ValueError("entry timestamp at or after sealed boundary")

def load_inputs(repo: Path):
    base = repo / "artifacts/c2_asymmetric_exit_experiment"
    entries_path, horizons_path = base / "frozen_entries.csv", base / "common_horizons_p0.csv"
    entries = _read_csv_verified(entries_path, EXPECTED_FROZEN_ENTRY_HASH, ENTRY_COLUMNS, "entry_execution_ms")
    horizons = _read_csv_verified(horizons_path, EXPECTED_COMMON_HORIZON_HASH, HORIZON_COLUMNS, "common_horizon_end_ms")
    by_id = {r["trade_id"]: r for r in horizons}
    if {r["trade_id"] for r in entries} != set(by_id):
        raise ValueError("entry/horizon trade mismatch")
    allow = [
        {"path": str(entries_path.relative_to(repo)), "role": "frozen_entries", "sha256": EXPECTED_FROZEN_ENTRY_HASH},
        {"path": str(horizons_path.relative_to(repo)), "role": "common_horizons", "sha256": EXPECTED_COMMON_HORIZON_HASH},
    ]
    minutes = {}
    for symbol in SYMBOLS:
        path = repo / "data/normalized/c2_history" / f"{symbol}_1m.csv.gz"
        minutes[symbol] = _load_gzip_series(path, EXPECTED_NORMALIZED_HASHES[symbol], MINUTE)
        allow.append({"path": str(path.relative_to(repo)), "role": "normalized_1m", "sha256": EXPECTED_NORMALIZED_HASHES[symbol]})
    return entries, by_id, minutes, allow

def _resolve(series: DenseSeries, t: int, h: int, h_price: float | None, upper: float, lower: float, upper_name: str, lower_name: str) -> dict:
    q = min(t + HOUR, h)
    m = t
    while m + MINUTE <= q:
        bar = series.get(m)
        if bar is None:
            return {"event_class": "", "resolution_ms": None, "resolution_price": None, "event_timing": "", "resolved": False, "ambiguous": False, "ambiguity_reason": "", "censored": True, "censor_reason": "chronology_gap"}
        o, hi, lo = bar["open"], bar["high"], bar["low"]
        if o >= upper and o > lower:
            return _event(upper_name, m, o, "open")
        if o <= lower and o < upper:
            return _event(lower_name, m, o, "open")
        if hi >= upper and lo <= lower:
            return {"event_class": "", "resolution_ms": m + MINUTE, "resolution_price": None, "event_timing": "ordinary_interval", "resolved": False, "ambiguous": True, "ambiguity_reason": "ambiguous_same_minute", "censored": False, "censor_reason": ""}
        if hi >= upper:
            return _event(upper_name, m + MINUTE, upper, "ordinary_interval")
        if lo <= lower:
            return _event(lower_name, m + MINUTE, lower, "ordinary_interval")
        m += MINUTE
    if q == h:
        if h_price is None or not math.isfinite(h_price):
            return {"event_class": "", "resolution_ms": None, "resolution_price": None, "event_timing": "", "resolved": False, "ambiguous": False, "ambiguity_reason": "", "censored": True, "censor_reason": "unavailable_exact_H_point"}
        if h_price >= upper:
            return _event(upper_name, h, h_price, "exact_H_point")
        if h_price <= lower:
            return _event(lower_name, h, h_price, "exact_H_point")
    if h < t + HOUR:
        return {"event_class": "", "resolution_ms": h, "resolution_price": h_price, "event_timing": "exact_H_point", "resolved": False, "ambiguous": False, "ambiguity_reason": "", "censored": True, "censor_reason": "right_censored_at_common_horizon"}
    return _event("no_event_60m", q, None, "complete_window")

def _event(name, ms, price, timing):
    return {"event_class": name, "resolution_ms": ms, "resolution_price": price, "event_timing": timing, "resolved": True, "ambiguous": False, "ambiguity_reason": "", "censored": False, "censor_reason": ""}

def _snapshot_id(trade_id: str, t: int) -> str:
    return "C4S-" + hashlib.sha256(f"{DATASET_VERSION}|{trade_id}|{t}".encode()).hexdigest()[:20]

def build_tables(entries, horizons, minutes):
    tables = {"T1": [], "T2": []}
    for entry in entries:
        e = int(entry["entry_execution_ms"])
        if e >= STUDY_END_MS: raise ValueError("entry boundary rejection")
        horizon = horizons[entry["trade_id"]]
        h = int(horizon["common_horizon_end_ms"])
        if h >= STUDY_END_MS: raise ValueError("horizon boundary rejection")
        if h <= e: continue
        series, price = minutes[entry["symbol"]], float(entry["entry_price"])
        h_price = float(horizon["p0_raw_exit_price"]) if horizon.get("p0_raw_exit_price") else None
        t = ((e + FIVE_MINUTES - 1) // FIVE_MINUTES) * FIVE_MINUTES
        if t == e: t += FIVE_MINUTES
        peak = -math.inf
        gap = False
        # Consume source values only after all trade timestamps pass the sealed-boundary checks.
        m = e if e % MINUTE == 0 else ((e // MINUTE) + 1) * MINUTE
        while t < h and t < STUDY_END_MS:
            while m < t:
                bar = series.get(m)
                if bar is None: gap = True
                elif not gap: peak = max(peak, bar["high"])
                m += MINUTE
            last = series.get(t - MINUTE)
            complete_start = t - FIVE_MINUTES
            complete = complete_start >= e and all(series.get(x) is not None for x in range(complete_start, t, MINUTE))
            if complete and last is not None:
                close = last["close"]
                causal_peak = max(peak, last["high"])
                common = _base_row(entry, horizon, t, close, causal_peak, price)
                for key in ("T1", "T2"):
                    row = dict(common); row["target_id"] = TARGET_VERSIONS[key]
                    if gap:
                        row.update({"target_eligible": False, "target_ineligible_reason": "pre_snapshot_chronology_gap", "upper_barrier": None, "lower_barrier": None})
                        row.update(_blank_outcome())
                    else:
                        _target(row, key, series, t, h, h_price, price, causal_peak, close)
                    if "resolution_ts" not in row:
                        row["resolution_ts"] = ""
                    tables[key].append(row)
            t += FIVE_MINUTES
    for key, rows in tables.items():
        rows.sort(key=lambda r: (r["snapshot_ms"], r["symbol"], r["trade_id"], r["target_id"]))
        counts = Counter(r["trade_id"] for r in rows if r["target_eligible"] and r["resolved"])
        for row in rows:
            n = counts.get(row["trade_id"], 0)
            row["raw_trade_weight"] = 1 / n if row["target_eligible"] and row["resolved"] and n else None
    return tables

def _base_row(entry, horizon, t, close, peak, ep):
    sid = _snapshot_id(entry["trade_id"], t); e = int(entry["entry_execution_ms"]); h = int(horizon["common_horizon_end_ms"])
    mfe, ret = peak / ep - 1, close / ep - 1
    return {"dataset_version": DATASET_VERSION, "trade_id": entry["trade_id"], "snapshot_id": sid, "row_id": sid, "symbol": entry["symbol"], "entry_fixture_id": entry["entry_fixture_id"], "entry_execution_ts": entry["entry_execution_ts"], "entry_execution_ms": e, "entry_price": ep, "snapshot_ts": iso(t), "snapshot_ms": t, "snapshot_interval_start_ts": iso(t-FIVE_MINUTES), "snapshot_close": close, "elapsed_minutes": (t-e)/MINUTE, "elapsed_5m_bars": (t-e)//FIVE_MINUTES, "common_horizon_end_ts": horizon["common_horizon_end_ts"], "common_horizon_end_ms": h, "nominal_target_end_ts": iso(t+HOUR), "observable_target_end_ts": iso(min(t+HOUR,h)), "running_peak": peak, "running_mfe": mfe, "current_return": ret, "drawdown_from_running_peak": close/peak-1, "peak_gain_retained_fraction": ret/mfe if mfe>0 else None, "already_beyond_giveback_state": False, "t1_upper_distance_assertion": None, "t1_lower_distance_assertion": None, "temporal_partition": _partition(e), "trade_entry_week": _week(e), "snapshot_week": _week(t), "snapshot_month": _month(t), "snapshot_quarter": _quarter(t), "forward_start_ms": t, "forward_end_ms": min(t+HOUR,h)}

def _target(row, key, series, t, h, h_price, ep, peak, close):
    if key == "T1":
        upper, lower = close*1.01, close*.9925; eligible, reason = True, ""
        row["t1_upper_distance_assertion"], row["t1_lower_distance_assertion"] = .01, .0075
        names = ("continuation", "adverse_reversal")
    else:
        gain, ret = peak/ep-1, close/ep-1; lower, upper = (ep+peak)/2, peak*1.005
        beyond = close <= lower; row["already_beyond_giveback_state"] = beyond
        eligible = gain >= .01 and ret > 0 and not beyond
        reason = "" if eligible else ("peak_gain_below_1pct" if gain < .01 else "current_return_not_positive" if ret <= 0 else "already_beyond_giveback_state")
        names = ("renewed_peak", "substantial_giveback")
    row.update({"target_eligible": eligible, "target_ineligible_reason": reason, "upper_barrier": upper, "lower_barrier": lower})
    row.update(_resolve(series,t,h,h_price,upper,lower,*names) if eligible else _blank_outcome())
    row["resolution_ts"] = iso(row.pop("resolution_ms")) if row.get("resolution_ms") is not None else ""

def _blank_outcome():
    return {"event_class": "", "resolution_ms": None, "resolution_price": None, "event_timing": "", "resolved": False, "ambiguous": False, "ambiguity_reason": "", "censored": False, "censor_reason": ""}

def _dist(values):
    if not values: return {k: None for k in ("min","p25","median","mean","p75","p90","max")}
    a=np.asarray(values,float)
    return {"min":float(a.min()),"p25":float(np.quantile(a,.25,method="linear")),"median":float(np.quantile(a,.5,method="linear")),"mean":float(a.mean()),"p75":float(np.quantile(a,.75,method="linear")),"p90":float(np.quantile(a,.9,method="linear")),"max":float(a.max())}

def _overlap(rows):
    eligible=[r for r in rows if r["target_eligible"]]; by=defaultdict(list)
    for r in eligible: by[r["trade_id"]].append(r)
    adjacent=0; adj_overlap=0; shared=[]; all_pairs=0; all_overlap=0; longest={}
    for trade, rs in by.items():
        rs.sort(key=lambda x:x["snapshot_ms"]); run=best=1
        for a,b in zip(rs,rs[1:]):
            adjacent+=1; s=max(0,min(a["forward_end_ms"],b["forward_end_ms"])-max(a["forward_start_ms"],b["forward_start_ms"]))//MINUTE
            shared.append(s); adj_overlap+=s>0; run=run+1 if b["snapshot_ms"]-a["snapshot_ms"]==FIVE_MINUTES else 1; best=max(best,run)
        longest[trade]=best
        starts=[x["forward_start_ms"] for x in rs]
        all_pairs += len(rs)*(len(rs)-1)//2
        for i,a in enumerate(rs):
            all_overlap += max(0, bisect.bisect_left(starts, a["forward_end_ms"], i+1)-i-1)
    return {"adjacent_pairs":adjacent,"adjacent_overlapping_pairs":adj_overlap,"adjacent_overlap_fraction":adj_overlap/adjacent if adjacent else None,"shared_forward_minutes_distribution":_dist(shared),"all_within_trade_pairs":all_pairs,"all_pair_overlap_fraction":all_overlap/all_pairs if all_pairs else None,"longest_sequential_landmark_run_per_trade":longest,"longest_run_distribution":_dist(list(longest.values()))}

def _summarize(rows, key, threshold_panel_hash):
    parts={"2024_development":lambda r:r["temporal_partition"].startswith("2024_"),"2025_locked":lambda r:r["temporal_partition"]=="2025_locked"}
    result={"target_id":TARGET_VERSIONS[key],"adequacy_decision":ADEQUACY_DECISIONS[key],"threshold_panel_sha256":threshold_panel_hash,"partitions":{}}
    for name,pred in parts.items():
        rs=[r for r in rows if pred(r)]; elig=[r for r in rs if r["target_eligible"]]; resolved=[r for r in elig if r["resolved"]]; amb=[r for r in elig if r["ambiguous"]]; cens=[r for r in elig if r["censored"]]
        bytrade=Counter(r["trade_id"] for r in elig); byclass=Counter(r["event_class"] for r in resolved)
        class_trades={c:len({r["trade_id"] for r in resolved if r["event_class"]==c}) for c in sorted(byclass)}
        concentration=lambda field: max(Counter(r[field] for r in elig).values(),default=0)/len(elig) if elig else None
        result["partitions"][name]={"total_snapshots":len(rs),"eligible_snapshots":len(elig),"resolved_snapshots":len(resolved),"ambiguous_snapshots":len(amb),"censored_snapshots":len(cens),"unique_eligible_trades":len(bytrade),"unique_resolved_trades":len({r['trade_id'] for r in resolved}),"resolved_event_counts":dict(byclass),"unique_resolved_trades_by_class":class_trades,"snapshots_per_trade":_dist(list(bytrade.values())),"entry_weeks":len({r['trade_entry_week'] for r in elig}),"snapshot_weeks":len({r['snapshot_week'] for r in elig}),"months":len({r['snapshot_month'] for r in elig}),"quarters":len({r['snapshot_quarter'] for r in elig}),"symbols":dict(Counter(r['symbol'] for r in elig)),"entry_cohorts":dict(Counter(r['trade_entry_week'] for r in elig)),"censoring_incidence":len(cens)/len(elig) if elig else None,"ambiguity_incidence":len(amb)/len(elig) if elig else None,"top_trade_share":max(bytrade.values(),default=0)/len(elig) if elig else None,"top_entry_week_share":concentration('trade_entry_week'),"top_month_share":concentration('snapshot_month')}
    return result

def _censoring(tables):
    detail=[]; frac_summary=[]
    for key,rows in tables.items():
        groups=defaultdict(list)
        for r in rows:
            if r["target_eligible"]: groups[(r["temporal_partition"],r["symbol"],r["trade_id"])].append(r)
        for (split,symbol,trade),rs in groups.items():
            n=len(rs); rec={"target":key,"temporal_split":split,"symbol":symbol,"trade_id":trade,"eligible_landmark_count":n,"resolved_landmark_count":sum(x['resolved'] for x in rs),"censored_landmark_count":sum(x['censored'] for x in rs),"ambiguous_landmark_count":sum(x['ambiguous'] for x in rs)}
            for x in ("resolved","censored","ambiguous"): rec[f"{x}_fraction_of_eligible"]=rec[f"{x}_landmark_count"]/n
            detail.append(rec)
        for g,rs in _group(detail,lambda x:(x['target'],x['temporal_split'],x['symbol'])).items():
            if g[0]!=key: continue
            frac_summary.append({"target":g[0],"temporal_split":g[1],"symbol":g[2],**{f"{f}_fraction_of_eligible":_dist([x[f'{f}_fraction_of_eligible'] for x in rs]) for f in ('resolved','censored','ambiguous')}})
    dims={}
    for dim,fn in {"elapsed_time_band":lambda r:"0-6h" if r['elapsed_minutes']<=360 else "6-24h" if r['elapsed_minutes']<=1440 else "24-72h" if r['elapsed_minutes']<=4320 else ">72h","symbol":lambda r:r['symbol'],"trade":lambda r:r['trade_id'],"entry_cohort":lambda r:r['trade_entry_week'],"snapshot_week":lambda r:r['snapshot_week'],"snapshot_month":lambda r:r['snapshot_month'],"quarter":lambda r:r['snapshot_quarter'],"reason":lambda r:r['censor_reason'] or ('ambiguous_same_minute' if r['ambiguous'] else 'resolved')}.items():
        dims[dim]=[{"target":k,"temporal_partition":p,"group":g,"eligible":len(v),"censored":sum(x['censored'] for x in v),"ambiguous":sum(x['ambiguous'] for x in v)} for (k,p,g),v in _group([r for k,rs in tables.items() for r in rs if r['target_eligible']],lambda r:(("T1" if r['target_id']==T1 else "T2"),r['temporal_partition'],fn(r))).items()]
    return {"per_trade":detail,"fraction_summaries":frac_summary,"by_dimension":dims}

def _group(items,key):
    out=defaultdict(list)
    for x in items: out[key(x)].append(x)
    return out

def bootstrap_structure(rows):
    trades={r['trade_id']:r['trade_entry_week'] for r in rows if r['target_eligible'] and r['resolved']}
    weeks=sorted(set(trades.values()))
    if not weeks: return {"available":False,"reason":"no_resolved_trades","config":BOOTSTRAP_CONFIG}
    start=np.datetime64(weeks[0]); end=np.datetime64(weeks[-1]); positions=[str(x) for x in np.arange(start,end+np.timedelta64(7,'D'),np.timedelta64(7,'D'),dtype='datetime64[D]')]
    blocks=[positions[i:i+4] for i in range(max(0,len(positions)-3))]
    week_trades=defaultdict(list)
    for trade,week in trades.items(): week_trades[week].append(trade)
    block_trades=[[t for w in b for t in week_trades[w]] for b in blocks]
    nonempty=[i for i,b in enumerate(block_trades) if b]
    available=len(positions)>=4 and len(nonempty)>=2
    rng=np.random.Generator(np.random.PCG64(BOOTSTRAP_CONFIG['seed'])); k=math.ceil(len(positions)/4)
    seq=[]; mult=[]
    if available:
        for _ in range(BOOTSTRAP_CONFIG['replicates']):
            chosen=[nonempty[int(rng.integers(len(nonempty)))] for _ in range(k)]; seq.append(chosen)
            c=Counter(t for ix in chosen for t in block_trades[ix]); mult.append(dict(sorted(c.items())))
    payload={"available":available,"eligible_trades":len(trades),"entry_weeks":len(weeks),"W":len(positions),"blocks_drawn_per_replicate":k,"week_positions":positions,"blocks":blocks,"nonempty_block_indices":nonempty,"config":BOOTSTRAP_CONFIG,"sampled_block_indices":seq,"trade_multiplicities":mult,"trades_never_split":True,"multiplicities_preserved":True}
    payload["sequence_sha256"]=hashlib.sha256(json.dumps(seq,separators=(',',':')).encode()).hexdigest(); payload["multiplicity_sha256"]=hashlib.sha256(json.dumps(mult,separators=(',',':'),sort_keys=True).encode()).hexdigest()
    return payload

def _write_csv(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=AUDIT_COLUMNS,extrasaction='ignore',lineterminator='\n'); w.writeheader(); w.writerows(rows)

def _json_hash(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def adequacy_decision():
    panel_hash = _json_hash(ADEQUACY_THRESHOLDS)
    return {
        "schema_version": "C4_DATA_ADEQUACY_DECISION_V1",
        "review_basis": "performance_blind_snapshot_event_count_coverage_censoring_dependence",
        "threshold_panel": ADEQUACY_THRESHOLDS,
        "threshold_panel_sha256": panel_hash,
        "target_decisions": ADEQUACY_DECISIONS,
        "modeling_authorization": "AUTHORIZE C4 MODELING AFTER ENVIRONMENT REPRODUCIBILITY GATE",
        "limitations": {
            "T1_censoring": "material but acceptable",
            "T2_censoring": "acceptable",
            "T2_inference_population": "selected positive peak-gain risk set only",
            "snapshot_rows_are_iid": False,
            "authorized_modeling_scope": "2024-only development and freeze",
            "predictive_scoring_2025_authorized": False,
        },
    }

BOOTSTRAP_PARTITIONS = {
    "fold_A_train": lambda r: r["temporal_partition"] == "2024_fold_A_train",
    "fold_A_validate": lambda r: r["temporal_partition"] == "2024_fold_A_validate_fold_B_train",
    "fold_B_train": lambda r: r["temporal_partition"] in ("2024_fold_A_train", "2024_fold_A_validate_fold_B_train"),
    "fold_B_validate": lambda r: r["temporal_partition"] == "2024_fold_B_validate",
    "final_2024_modeling": lambda r: r["temporal_partition"].startswith("2024_"),
    "locked_2025_evaluation_definition_only": lambda r: r["temporal_partition"] == "2025_locked",
}

def bootstrap_structures(rows):
    return {name: bootstrap_structure([r for r in rows if pred(r)]) for name,pred in BOOTSTRAP_PARTITIONS.items()}

def run(repo: Path, artifact: Path):
    entries,horizons,minutes,allow=load_inputs(repo); tables=build_tables(entries,horizons,minutes)
    artifact.mkdir(parents=True,exist_ok=True); local=artifact/'local'; local.mkdir(exist_ok=True)
    decision=adequacy_decision(); threshold_panel_hash=decision["threshold_panel_sha256"]
    decision_path=artifact/'adequacy_decision.json'; write_json(decision_path,decision)
    hashes={}; summaries={}
    for key,rows in tables.items():
        p=local/f"{key.lower()}_snapshots.csv"; _write_csv(p,rows); hashes[key]={"row_count":len(rows),"file_sha256":sha256_file(p),"semantic_sha256":hash_rows(rows,AUDIT_COLUMNS)}
        if hashes[key]["file_sha256"] != ACCEPTED_CORE_HASHES[key]: raise AssertionError(f"{key} accepted core hash changed")
        summaries[key]=_summarize(rows,key,threshold_panel_hash)
    overlap={k:_overlap(v) for k,v in tables.items()}; censor=_censoring(tables); boot={k:bootstrap_structures(v) for k,v in tables.items()}
    contract=repo/'contracts/C4_sequential_exit_state_CONTRACT.md'
    input_manifest={"manifest_version":"C4_ADEQUACY_INPUT_V1","contract_sha256":sha256_file(contract),"predecessor_hashes":PREDECESSORS,"explicit_allowlist":allow,"boundary_end_exclusive_utc":"2026-01-01T00:00:00Z","verification":{"all_hashes_verified":True,"timestamps_rejected_before_market_values":True,"2026_paths_enumerated":False,"2026_market_data_accessed":False}}
    schema={"schema_version":"C4_SNAPSHOT_AUDIT_SCHEMA_V1","snapshot_definition_version":SNAPSHOT_VERSION,"target_definition_versions":TARGET_VERSIONS,"columns":list(AUDIT_COLUMNS),"model_matrix_created":False}
    weight={}
    for k,v in tables.items():
        sums=defaultdict(float)
        for r in v:
            if r['raw_trade_weight'] is not None: sums[r['trade_id']]+=r['raw_trade_weight']
        error=max((abs(x-1) for x in sums.values()),default=0)
        weight[k]={"represented_trades":len(sums),"max_abs_trade_sum_error":error,"numeric_tolerance":1e-12,"validated":error<=1e-12}
    bootstrap_config_hash=_json_hash(BOOTSTRAP_CONFIG)
    bootstrap_details=local/'bootstrap_structure_details.json'
    write_json(bootstrap_details,{"configuration_hash":bootstrap_config_hash,"targets":boot})
    compact_boot={}
    for key,partitions in boot.items():
        compact_boot[key]={}
        for name,value in partitions.items():
            compact_boot[key][name]={k:v for k,v in value.items() if k not in ('sampled_block_indices','trade_multiplicities','blocks','week_positions')}
            compact_boot[key][name].update({"week_position_count":len(value.get('week_positions',[])),"block_count":len(value.get('blocks',[])),"sampled_replicate_count":len(value.get('sampled_block_indices',[])),"sample_block_indices":value.get('sampled_block_indices',[])[:3],"sample_trade_multiplicities":value.get('trade_multiplicities',[])[:1]})
    outputs={"input_manifest.json":input_manifest,"snapshot_schema.json":schema,"t1_adequacy_summary.json":summaries['T1'],"t2_adequacy_summary.json":summaries['T2'],"censoring_summary.json":censor,"overlap_summary.json":overlap,"bootstrap_structure.json":{"configuration_hash":bootstrap_config_hash,"detail_path":"local/bootstrap_structure_details.json","detail_file_sha256":sha256_file(bootstrap_details),"targets":compact_boot},}
    for name,obj in outputs.items(): write_json(artifact/name,obj)
    source_paths=[repo/'src/binance_data_foundation/c4_adequacy.py',repo/'src/binance_data_foundation/c4_adequacy_cli.py',repo/'tests/test_c4_adequacy.py',repo/'environment.yml',repo/'requirements-dev.txt']
    dependency_provenance={"environment.yml":sha256_file(repo/'environment.yml'),"requirements-dev.txt":sha256_file(repo/'requirements-dev.txt'),"conda_env":os.environ.get('CONDA_DEFAULT_ENV',''),"python_path":sys.executable,"numpy_version":np.__version__,"numpy_path":np.__file__,"PYTHONPATH":os.environ.get('PYTHONPATH')}
    repro={"manifest_version":"C4_ADEQUACY_REPRODUCIBILITY_V1","contract_sha256":sha256_file(contract),"predecessor_hashes":PREDECESSORS,"snapshot_definition_version":SNAPSHOT_VERSION,"target_definition_versions":TARGET_VERSIONS,"core_tables":hashes,"summary_semantic_hashes":{n:_json_hash(o) for n,o in outputs.items()},"adequacy_decision":{"path":"adequacy_decision.json","file_sha256":sha256_file(decision_path),"threshold_panel_sha256":threshold_panel_hash},"bootstrap_configuration_hash":bootstrap_config_hash,"equal_trade_weight_validation":weight,"source_test_hashes":{str(p.relative_to(repo)):sha256_file(p) for p in source_paths},"environment":dependency_provenance|{"provenance_sha256":_json_hash(dependency_provenance)},"repository":{"revision":subprocess.run(['git','rev-parse','HEAD'],cwd=repo,text=True,capture_output=True,check=True).stdout.strip(),"dirty_state_at_run":subprocess.run(['git','status','--short'],cwd=repo,text=True,capture_output=True,check=True).stdout.splitlines()},"confirmations":{"predictive_models_run":False,"predictive_metrics_computed":False,"2025_predictive_scoring_run":False,"economic_analysis_run":False,"2026_paths_enumerated":False,"2026_market_data_accessed":False}}
    write_json(artifact/'reproducibility_manifest.json',repro)
    return {"hashes":hashes,"summaries":summaries,"weights":weight,"bootstrap":{k:{x:y for x,y in v.items() if x not in ('sampled_block_indices','trade_multiplicities','blocks','week_positions')} for k,v in boot.items()}}

def verify_rebuild(repo: Path, artifact: Path):
    with tempfile.TemporaryDirectory(prefix='c4-adequacy-') as d:
        first=run(repo,artifact); second=run(repo,Path(d));
        a=json.loads((artifact/'reproducibility_manifest.json').read_text()); b=json.loads((Path(d)/'reproducibility_manifest.json').read_text())
        ok=a['core_tables']==b['core_tables'] and a['summary_semantic_hashes']==b['summary_semantic_hashes'] and a['bootstrap_configuration_hash']==b['bootstrap_configuration_hash']
        ab=json.loads((artifact/'bootstrap_structure.json').read_text())['targets']; bb=json.loads((Path(d)/'bootstrap_structure.json').read_text())['targets']
        boot_ok=all(ab[t][p]['sequence_sha256']==bb[t][p]['sequence_sha256'] and ab[t][p]['multiplicity_sha256']==bb[t][p]['multiplicity_sha256'] for t in ('T1','T2') for p in BOOTSTRAP_PARTITIONS)
        result={"independent_offline_rebuilds":2,"core_hashes_reproduced_exactly":ok,"first_core_tables":a['core_tables'],"second_core_tables":b['core_tables'],"bootstrap_sequences_reproduced":boot_ok}
        write_json(artifact/'independent_rebuild.json',result)
        if not ok: raise AssertionError("independent rebuild mismatch")
        return first|{"independent_rebuild":result}
