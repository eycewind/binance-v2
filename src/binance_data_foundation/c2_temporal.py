from __future__ import annotations

import csv
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .c2_candidate_run import EXPECTED_COMMON_HORIZON_HASH
from .c2_common import ENTRY_COLUMNS, STUDY_END_MS, hash_rows, iso, iter_gzip_csv, research_partitions, valid_minute, write_json
from .c2_p0 import EXPECTED_FROZEN_ENTRY_HASH, HORIZON_COLUMNS, _complete_path
from .ingest import sha256_file


THRESHOLDS = (("0_5pct", .005), ("1pct", .01), ("2pct", .02), ("3pct", .03), ("5pct", .05))
EXPECTED_CANDIDATE_PAIRED_HASH = "43de8894095963bda5aee47d8d24f6dec34a3b9cc7def1eec80256156baff5f1"
CANDIDATE_TIMESTAMP_FIELDS = (
    "entry_signal_ts", "entry_decision_ts", "entry_execution_ts", "entry_execution_ms",
    "exit_signal_ts", "exit_decision_ts", "exit_execution_ts", "common_horizon_end_ts",
    "common_horizon_end_ms", "policy_activated_ms",
)
ROW_COLUMNS = ("trade_id", "symbol", "partition", "entry_execution_ts", "entry_execution_ms",
               "common_horizon_end_ts", "common_horizon_end_ms", "p0_raw_return", "common_horizon_mfe",
               "common_horizon_mae", "time_to_first_green_seconds") + tuple(
    f"{label}_{suffix}" for label, _ in THRESHOLDS for suffix in
    ("hit", "first_passage_ms", "first_passage_seconds", "pre_hit_mae", "touch_minute_low_ambiguous")
) + ("after_1pct_first_event", "after_1pct_event_ms", "after_1pct_elapsed_seconds",
     "after_1pct_total_seconds", "after_1pct_post_milestone_mae",
     "after_1pct_to_2pct_seconds", "after_1pct_to_3pct_seconds", "after_1pct_to_5pct_seconds",
     "after_1pct_to_entry_seconds",
     "after_2pct_first_event", "after_2pct_event_ms", "after_2pct_elapsed_seconds",
     "after_2pct_total_seconds", "after_2pct_post_milestone_mae",
     "after_2pct_to_3pct_seconds", "after_2pct_to_5pct_seconds", "after_2pct_to_1pct_seconds",
     "after_2pct_to_entry_seconds")


def analyze_path(entry_ms: int, entry_price: float, horizon_ms: int, horizon_price: float,
                 rows: list[dict]) -> dict:
    """Describe a fixed post-entry path. It makes no exit decision."""
    if entry_ms >= STUDY_END_MS or horizon_ms >= STUDY_END_MS:
        raise ValueError("2026 timestamps are outside the accepted analysis boundary")
    ordered = sorted(rows, key=lambda row: int(row["open_time_ms"]))
    if any(int(row["open_time_ms"]) <= entry_ms or int(row["open_time_ms"]) >= horizon_ms for row in ordered):
        raise ValueError("path rows must be strictly after entry and before H")
    points = [(int(row["open_time_ms"]), float(row["high"]), float(row["low"]), True) for row in ordered]
    points.append((horizon_ms, horizon_price, horizon_price, False))
    result: dict[str, object] = {}
    first_green = next((ts for ts, high, _low, _ohlc in points if high > entry_price), None)
    result["time_to_first_green_seconds"] = None if first_green is None else (first_green-entry_ms)//1000
    hits: dict[str, int | None] = {}
    for label, threshold in THRESHOLDS:
        target = entry_price * (1 + threshold)
        index = next((i for i, (_ts, high, _low, _ohlc) in enumerate(points) if high >= target), None)
        hit_ms = None if index is None else points[index][0]
        prior_lows = [low for _ts, _high, low, _ohlc in points[:index or 0]]
        pre_mae = min([0.0] + [low / entry_price - 1 for low in prior_lows]) if index is not None else None
        ambiguous = bool(index is not None and points[index][3] and points[index][2] < entry_price)
        hits[label] = hit_ms
        result.update({f"{label}_hit": hit_ms is not None, f"{label}_first_passage_ms": hit_ms,
                       f"{label}_first_passage_seconds": None if hit_ms is None else (hit_ms-entry_ms)//1000,
                       f"{label}_pre_hit_mae": pre_mae,
                       f"{label}_touch_minute_low_ambiguous": ambiguous})
    result.update(_transition("1pct", hits["1pct"], (("reaches_2pct", 1.02), ("reaches_3pct", 1.03),
                                                     ("reaches_5pct", 1.05)), entry_ms, entry_price,
                              horizon_ms, horizon_price, ordered))
    result.update(_transition("2pct", hits["2pct"], (("reaches_3pct", 1.03), ("reaches_5pct", 1.05)),
                              entry_ms, entry_price, horizon_ms, horizon_price, ordered, fallback=("returns_1pct", 1.01)))
    result.update(_event_clocks("1pct", hits["1pct"], (("2pct", 1.02, "high"), ("3pct", 1.03, "high"),
                                                       ("5pct", 1.05, "high"), ("entry", 1.0, "low")),
                                entry_price, horizon_ms, horizon_price, ordered))
    result.update(_event_clocks("2pct", hits["2pct"], (("3pct", 1.03, "high"), ("5pct", 1.05, "high"),
                                                       ("1pct", 1.01, "low"), ("entry", 1.0, "low")),
                                entry_price, horizon_ms, horizon_price, ordered))
    return result


def _event_clocks(label:str, milestone_ms:int|None, events:tuple[tuple[str,float,str],...], entry_price:float,
                  horizon_ms:int,horizon_price:float,rows:list[dict])->dict:
    result={}
    for name,multiple,side in events:
        elapsed=None
        if milestone_ms is not None and milestone_ms < horizon_ms:
            milestone_row=next((r for r in rows if int(r["open_time_ms"])==milestone_ms),None)
            # A higher nested level must follow the milestone by price continuity. A lower touch in
            # the milestone OHLC has unknowable ordering and therefore cannot establish a return.
            if side=="high" and milestone_row is not None and float(milestone_row["high"]) >= entry_price*multiple:
                elapsed=0
            else:
                later=[r for r in rows if int(r["open_time_ms"])>milestone_ms]
                match=next((int(r["open_time_ms"]) for r in later if
                            (float(r["high"])>=entry_price*multiple if side=="high" else float(r["low"])<=entry_price*multiple)),None)
                if match is None and ((horizon_price>=entry_price*multiple) if side=="high" else (horizon_price<=entry_price*multiple)):
                    match=horizon_ms
                if match is not None: elapsed=(match-milestone_ms)//1000
        result[f"after_{label}_to_{name}_seconds"]=elapsed
    return result


def _transition(label: str, milestone_ms: int | None, upward: tuple[tuple[str, float], ...], entry_ms: int,
                entry_price: float, horizon_ms: int, horizon_price: float, rows: list[dict],
                fallback: tuple[str, float] = ("returns_entry", 1.0)) -> dict:
    prefix = f"after_{label}"
    if milestone_ms is None:
        return {f"{prefix}_first_event": "milestone_not_reached", f"{prefix}_event_ms": None,
                f"{prefix}_elapsed_seconds": None, f"{prefix}_total_seconds": None,
                f"{prefix}_post_milestone_mae": None}
    if milestone_ms >= horizon_ms:
        return {f"{prefix}_first_event": "none_before_H", f"{prefix}_event_ms": None,
                f"{prefix}_elapsed_seconds": None, f"{prefix}_total_seconds": None,
                f"{prefix}_post_milestone_mae": 0.0}
    milestone_row = next((row for row in rows if int(row["open_time_ms"]) == milestone_ms), None)
    if milestone_row is not None:
        up = [name for name, multiple in upward if float(milestone_row["high"]) >= entry_price * multiple]
        down = float(milestone_row["low"]) <= entry_price * fallback[1]
        if up:
            event = "same_minute_ambiguous" if down else up[0]
            return {f"{prefix}_first_event": event, f"{prefix}_event_ms": milestone_ms,
                    f"{prefix}_elapsed_seconds": 0, f"{prefix}_total_seconds": (milestone_ms-entry_ms)//1000,
                    f"{prefix}_post_milestone_mae": 0.0}
    later = [row for row in rows if int(row["open_time_ms"]) > milestone_ms]
    points = [(int(r["open_time_ms"]), float(r["high"]), float(r["low"]), True) for r in later]
    points.append((horizon_ms, horizon_price, horizon_price, False))
    observed_lows: list[float] = []
    for ts, high, low, is_ohlc in points:
        up = [name for name, multiple in upward if high >= entry_price * multiple]
        down = low <= entry_price * fallback[1]
        if up and down and is_ohlc:
            event = "same_minute_ambiguous"
        elif up:
            event = up[0]  # nearest nested threshold is necessarily crossed first
        elif down:
            event = fallback[0]
        else:
            observed_lows.append(low)
            continue
        mae = min([0.0] + [x / entry_price - 1 for x in observed_lows])
        return {f"{prefix}_first_event": event, f"{prefix}_event_ms": ts,
                f"{prefix}_elapsed_seconds": (ts-milestone_ms)//1000,
                f"{prefix}_total_seconds": (ts-entry_ms)//1000,
                f"{prefix}_post_milestone_mae": mae}
    mae = min([0.0] + [x / entry_price - 1 for x in observed_lows])
    return {f"{prefix}_first_event": "none_before_H", f"{prefix}_event_ms": None,
            f"{prefix}_elapsed_seconds": None, f"{prefix}_total_seconds": None,
            f"{prefix}_post_milestone_mae": mae}


def build_temporal_analysis(normalized_dir: Path, artifact_dir: Path, *,
                            deterministic_offline_rebuild_verified: bool = False,
                            verification_evidence: dict | None = None) -> dict:
    entries = list(csv.DictReader((artifact_dir/"frozen_entries.csv").open(newline="", encoding="utf-8")))
    horizons = list(csv.DictReader((artifact_dir/"common_horizons_p0.csv").open(newline="", encoding="utf-8")))
    if hash_rows(entries, ENTRY_COLUMNS) != EXPECTED_FROZEN_ENTRY_HASH:
        raise ValueError("frozen-entry semantic hash mismatch")
    if hash_rows(horizons, HORIZON_COLUMNS) != EXPECTED_COMMON_HORIZON_HASH:
        raise ValueError("common-horizon semantic hash mismatch")
    horizon_by_id = {row["trade_id"]: row for row in horizons}
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        if int(entry["entry_execution_ms"]) >= STUDY_END_MS:
            raise ValueError("2026 entry rejected")
        by_symbol[entry["symbol"]].append(entry)
    records = []
    for symbol in sorted(by_symbol):
        minute_lookup = {}
        for row in iter_gzip_csv(normalized_dir/f"{symbol}_1m.csv.gz"):
            ts = int(row["open_time_ms"])
            if ts >= STUDY_END_MS:
                raise ValueError("2026 normalized input rejected")
            if valid_minute(row): minute_lookup[ts] = row
        for entry in by_symbol[symbol]:
            h = horizon_by_id[entry["trade_id"]]
            horizon_ms = int(h["common_horizon_end_ms"])
            if horizon_ms >= STUDY_END_MS:
                raise ValueError("2026 horizon rejected")
            path, missing = _complete_path(int(entry["entry_execution_ms"]), horizon_ms, minute_lookup)
            if missing is not None: raise ValueError(f"accepted path gap at {missing}")
            metrics = analyze_path(int(entry["entry_execution_ms"]), float(entry["entry_price"]), horizon_ms,
                                   float(h["p0_raw_exit_price"]), path)
            records.append({"trade_id":entry["trade_id"], "symbol":symbol,
                "partition":"sanity_calibration" if int(entry["entry_execution_ms"]) < 1711929600000 else "headline_evaluation",
                "entry_execution_ts":entry["entry_execution_ts"], "entry_execution_ms":entry["entry_execution_ms"],
                "common_horizon_end_ts":h["common_horizon_end_ts"], "common_horizon_end_ms":horizon_ms,
                "p0_raw_return":float(h["p0_raw_exit_price"])/float(entry["entry_price"])-1,
                "common_horizon_mfe":float(h["common_horizon_mfe"]), "common_horizon_mae":float(h["common_horizon_mae"]), **metrics})
    records.sort(key=lambda r:(int(r["entry_execution_ms"]),r["symbol"],r["trade_id"]))
    row_path=artifact_dir/"temporal_path_records.csv"; _write_csv(row_path, records)
    outputs = {
        "temporal_first_passage_summary.json": _first_passage_summary(records),
        "temporal_transition_1pct.json": _transition_summary(records, "1pct"),
        "temporal_transition_2pct.json": _transition_summary(records, "2pct"),
        "temporal_drawdown_summary.json": _drawdown_summary(records),
        "temporal_group_summaries.json": _group_summary(records),
        "temporal_candidate_diagnostics.json": _candidate_diagnostics(records, artifact_dir),
        "temporal_observations.json": _observations(),
    }
    for name,value in outputs.items(): write_json(artifact_dir/name,value)
    result={"row_count":len(records),"row_semantic_hash":hash_rows(records,ROW_COLUMNS),
            "row_file_hash":sha256_file(row_path),"output_hashes":{name:sha256_file(artifact_dir/name) for name in outputs}}
    _manifest(artifact_dir, result, deterministic_offline_rebuild_verified, verification_evidence)
    return result


def _first_passage_summary(rows: list[dict]) -> dict:
    result={label:{"threshold":threshold,"total":len(rows),"reached":_count(rows,f"{label}_hit"),
        "never_reached":{"count":len(rows)-_count(rows,f"{label}_hit")["count"],"fraction":1-_count(rows,f"{label}_hit")["fraction"]},
        "first_passage_seconds":_dist([r[f"{label}_first_passage_seconds"] for r in rows if r[f"{label}_hit"]]),
        "pre_hit_mae":_dist([r[f"{label}_pre_hit_mae"] for r in rows if r[f"{label}_hit"]]),
        "p0_return_reached":_dist([r["p0_raw_return"] for r in rows if r[f"{label}_hit"]]),
        "p0_return_not_reached":_dist([r["p0_raw_return"] for r in rows if not r[f"{label}_hit"]])} for label,threshold in THRESHOLDS}
    green=[r["time_to_first_green_seconds"] for r in rows if r["time_to_first_green_seconds"] is not None]
    result["time_to_first_green"]={"observed":len(green),"censored":len(rows)-len(green),"seconds":_dist(green)}
    return result


def _transition_summary(rows:list[dict],label:str)->dict:
    eligible=[r for r in rows if r[f"{label}_hit"]]; key=f"after_{label}"
    targets=("2pct","3pct","5pct","entry") if label=="1pct" else ("3pct","5pct","1pct","entry")
    return {"milestone":label,"eligible":len(eligible),"first_event_counts":_rates(Counter(r[f"{key}_first_event"] for r in eligible),len(eligible)),
            "individual_event_clocks":{target:{"observed":sum(r[f"{key}_to_{target}_seconds"] is not None for r in eligible),
                "censored":sum(r[f"{key}_to_{target}_seconds"] is None for r in eligible),
                "elapsed_seconds":_dist([r[f"{key}_to_{target}_seconds"] for r in eligible if r[f"{key}_to_{target}_seconds"] is not None])} for target in targets},
            "by_first_event":{event:{"count":len(group),"elapsed_seconds":_dist([r[f"{key}_elapsed_seconds"] for r in group if r[f"{key}_elapsed_seconds"] is not None]),
                "total_seconds":_dist([r[f"{key}_total_seconds"] for r in group if r[f"{key}_total_seconds"] is not None]),
                "post_milestone_mae":_dist([r[f"{key}_post_milestone_mae"] for r in group if r[f"{key}_post_milestone_mae"] is not None]),
                "final_p0_raw_return":_dist([r["p0_raw_return"] for r in group])}
                for event,group in _groups(eligible,lambda r:r[f"{key}_first_event"]).items()}}


def _drawdown_summary(rows:list[dict])->dict:
    out={}
    for label,threshold in THRESHOLDS:
        hit=[r for r in rows if r[f"{label}_hit"]]; values=[r[f"{label}_pre_hit_mae"] for r in hit]
        out[label]={"threshold":threshold,"successful_trades":len(hit),"pre_hit_mae":_dist(values),
                    "went_at_or_below_before_success":{str(x):{"count":sum(v <= x for v in values),"fraction":sum(v <= x for v in values)/len(values) if values else None} for x in (-.005,-.01,-.02)},
                    "touch_minute_low_ordering_ambiguous":_count(hit,f"{label}_touch_minute_low_ambiguous")}
    return out


def _group_summary(rows:list[dict])->dict:
    specs={"by_symbol":lambda r:r["symbol"],"by_partition":lambda r:r["partition"],
           "by_month":lambda r:r["entry_execution_ts"][:7],"by_quarter":lambda r:r["entry_execution_ts"][:5]+"Q"+str((int(r["entry_execution_ts"][5:7])-1)//3+1)}
    return {name:{group:_first_passage_summary(items) for group,items in _groups(rows,fn).items()} for name,fn in specs.items()}


def _candidate_diagnostics(rows:list[dict],artifact_dir:Path)->dict:
    temporal={r["trade_id"]:r for r in rows}; selected=[]
    candidate_rows = _load_validated_candidate_rows(artifact_dir/"c2a_paired_trade_records.csv")
    for r in candidate_rows:
        if r["exit_policy"] != "P0" and r["cost_scenario"] == "C0": selected.append(r)
    out={}
    for policy,group in _groups(selected,lambda r:r["exit_policy"]).items():
        cats={"rescued":[r for r in group if _bool(r["rescued"])],"damaged":[r for r in group if _bool(r["damaged"])],
              "equal":[r for r in group if _bool(r["candidate_equal_to_p0"])],
              "large_mfe_truncated_prematurely":[r for r in group if float(r["common_horizon_mfe"])>=.02 and _bool(r["premature_appreciation_0_5pct"])]}
        out[policy]={name:_temporal_category(items,temporal) for name,items in cats.items()}
    return {"governance": _candidate_cohort_governance(), "diagnostics_by_policy": out}


def _load_validated_candidate_rows(path: Path, *,
                                   expected_file_hash: str = EXPECTED_CANDIDATE_PAIRED_HASH,
                                   expected_semantic_hash: str = EXPECTED_CANDIDATE_PAIRED_HASH) -> list[dict]:
    # The byte-level check deliberately precedes CSV parsing: an unaccepted candidate table
    # must not expose candidate-derived outcomes to this diagnostic at all.
    if sha256_file(path) != expected_file_hash:
        raise ValueError("candidate paired input file hash mismatch before diagnostics")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = tuple(reader.fieldnames or ())
        candidate_rows = list(reader)
    if hash_rows(candidate_rows, columns) != expected_semantic_hash:
        raise ValueError("candidate paired input semantic hash mismatch before diagnostics")
    # Validate the complete accepted table before selecting rows or consuming any outcome,
    # label, return, holding-duration, or future-path field.
    for row_number, row in enumerate(candidate_rows, start=2):
        for field in CANDIDATE_TIMESTAMP_FIELDS:
            _validate_pre_holdout_timestamp(row.get(field, ""), field, row_number)
    return candidate_rows


def _validate_pre_holdout_timestamp(value: object, field: str, row_number: int | None = None) -> None:
    if value is None or str(value).strip() == "":
        return
    location = f" at candidate row {row_number}" if row_number is not None else ""
    try:
        if field.endswith("_ms"):
            timestamp_ms = int(str(value))
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("timezone is required")
            timestamp_ms = int(parsed.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"invalid candidate timestamp {field}{location}") from exc
    if timestamp_ms >= STUDY_END_MS:
        raise ValueError(f"2026 candidate timestamp rejected: {field}{location}")


def _candidate_cohort_governance() -> dict:
    return {
        "status": "retrospective_descriptive_diagnostics_only",
        "definitions": {
            "rescued": "p0_raw_return <= 0 and candidate raw_price_return > 0; the P0 outcome may occur after candidate exit",
            "damaged": "p0_raw_return > 0 and candidate raw_price_return <= 0; the P0 outcome may occur after candidate exit",
            "later_foregone_gain": "max(0, max(candidate-exit-exclusive future 1m highs before the common horizon and the common-horizon execution price) / candidate exit price - 1); uses the future path after candidate exit through the common horizon",
            "large_mfe_truncated_prematurely": "common_horizon_mfe >= 0.02 and later foregone gain >= 0.005; uses future common-horizon information",
        },
        "warnings": [
            "rescued and damaged may depend on P0 outcomes occurring after candidate exit",
            "later foregone gain uses the future path after candidate exit through the common horizon",
            "large-MFE prematurely truncated uses future common-horizon information",
            "these labels are retrospective descriptive diagnostics only",
            "these labels must not be used as causal features",
            "these labels must not be used as policy-selection evidence",
            "these labels do not prove candidate superiority",
        ],
    }


def _temporal_category(items:list[dict],temporal:dict[str,dict])->dict:
    joined=[temporal[r["trade_id"]] for r in items]
    return {"count":len(items),"time_to_first_green_seconds":_dist([r["time_to_first_green_seconds"] for r in joined if r["time_to_first_green_seconds"] is not None]),
            "time_to_1pct_seconds":_dist([r["1pct_first_passage_seconds"] for r in joined if r["1pct_hit"]]),
            "time_to_2pct_seconds":_dist([r["2pct_first_passage_seconds"] for r in joined if r["2pct_hit"]]),
            "common_horizon_mfe":_dist([r["common_horizon_mfe"] for r in joined]),
            "candidate_holding_seconds":_dist([float(r["holding_duration_seconds"]) for r in items]),
            "foregone_subsequent_gain":_dist([float(r["foregone_subsequent_gain"]) for r in items])}


def _observations()->dict:
    return {"status":"hypothesis_generating_only",
            "candidate_cohort_governance":_candidate_cohort_governance(),
            "exploratory_findings":[
              "Positive continuation and reversal are closely balanced after milestones: after +1%, the first resolved event was +2% for 432 trades and return to entry for 385; after +2%, it was +3% for 279 and return to +1% for 264.",
              "Rescued trades reached early milestones sooner than damaged trades for every accepted candidate; this is associative and must not be converted into a timing rule on these data.",
              "Damaged and large-MFE prematurely truncated trades retained substantial later appreciation, especially for P3, whose median candidate holding time was much shorter than its median time to +1% or +2% in those cohorts.",
              "Threshold reach rates and time-to-+1% differ by symbol, with SOL highest/fastest and BTC lowest/slower in this five-symbol sample; symbols are not independent replications.",
              "The sanity and headline partitions differ at larger thresholds, so any future temporal-regime hypothesis requires pre-registration rather than retrospective subdivision."
            ],
            "candidate_hypotheses_for_future_contract":[
              "Pre-register whether early milestone arrival distinguishes continuation from reversal using one fixed timing definition and dependence-aware validation.",
              "Pre-register whether a candidate-policy early exit followed by delayed milestone attainment identifies a reproducible premature-exit regime.",
              "Pre-register a temporal stability analysis across calendar blocks without choosing thresholds or parameters from the present results."
            ],
            "prohibited":["selecting a new TP","selecting a new SL","selecting a new trail distance","selecting a new activation threshold","selecting a new momentum rule","ranking thresholds","optimizing parameters on these data"],
            "future_contract_requirement":"Any temporal hypothesis must be pre-registered and frozen before confirmation.",
            "holdout_note":"2026 data are reserved as untouched confirmation data. No 2026 prices, entries, paths, exits, or outcomes were inspected. Any future rule inspired by this analysis must be frozen before accessing 2026 data."}


def _manifest(artifact_dir:Path,result:dict,verified:bool=False,evidence:dict|None=None)->None:
    files=(Path(__file__),Path(__file__).with_name("c2_temporal_cli.py"),Path("tests/test_c2_temporal.py"))
    manifest={"run_id":"C2A_TEMPORAL_PATH_KINETICS_V1","created_at_utc":datetime.now(timezone.utc).isoformat(),
      "code_revision":subprocess.run(["git","rev-parse","HEAD"],check=True,capture_output=True,text=True).stdout.strip(),
      "contract_sha256":sha256_file(Path("contracts/C2_asymmetric_exit_experiment_CONTRACT.md")),
      "frozen_entry_hash":EXPECTED_FROZEN_ENTRY_HASH,"common_horizon_hash":EXPECTED_COMMON_HORIZON_HASH,
      "candidate_paired_hash":sha256_file(artifact_dir/"c2a_paired_trade_records.csv"),"research_partitions":research_partitions(),
      "input_boundary":{"end_exclusive_utc":iso(STUDY_END_MS),"reject_timestamps_at_or_after_boundary":True,"2026_accessed":False},
      "thresholds":[x[1] for x in THRESHOLDS],"analysis_only":True,"new_exit_rules":False,"parameter_tuning":False,
      "deterministic_offline_rebuild_verified":verified,
      "deterministic_offline_rebuild_evidence":evidence,
      "reproducibility_scope":{"core_outputs_and_hashes":"must reproduce",
                               "temporal_manifest.json":"not expected to be byte-identical when created_at_utc is regenerated"},
      "implementation_hashes":{str(p):sha256_file(p) for p in files},**result}
    write_json(artifact_dir/"temporal_manifest.json",manifest)


def _dist(values:list[float|int])->dict:
    x=sorted(float(v) for v in values)
    if not x:return {"count":0,"mean":None,"median":None,"p05":None,"p25":None,"p75":None,"p95":None}
    return {"count":len(x),"mean":statistics.fmean(x),"median":statistics.median(x),
            **{f"p{int(p*100):02d}":_quantile(x,p) for p in (.05,.25,.75,.95)}}


def _quantile(x:list[float],p:float)->float:
    i=(len(x)-1)*p; lo,hi=math.floor(i),math.ceil(i); return x[lo] if lo==hi else x[lo]+(x[hi]-x[lo])*(i-lo)


def _count(rows:list[dict],key:str)->dict:
    n=sum(_bool(r[key]) for r in rows); return {"count":n,"fraction":n/len(rows) if rows else None}


def _rates(counts:Counter,total:int)->dict:return {k:{"count":v,"fraction":v/total if total else None} for k,v in sorted(counts.items())}
def _bool(v:object)->bool:return v is True or str(v).lower()=="true"
def _groups(rows:list[dict],fn)->dict:
    out=defaultdict(list)
    for row in rows:out[fn(row)].append(row)
    return dict(sorted(out.items()))
def _write_csv(path:Path,rows:list[dict])->None:
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=ROW_COLUMNS,lineterminator="\n");w.writeheader();w.writerows(({k:r.get(k) for k in ROW_COLUMNS} for r in rows))
