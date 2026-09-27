"""C7 T1 readiness and authorization-gated one-shot mechanics.

Real-data functions in this module are structural only.  Economic functions
accept in-memory rows and are exercised by synthetic tests; production is
behind an exact-hash authorization barrier.
"""
from __future__ import annotations

import csv, fcntl, gzip, hashlib, json, math, os, platform, re, shutil, tempfile, uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

CONTRACT_SHA256="eec99cc1311baea10d2e6b2ea09cb9392fc52c756ac1177085b2c375a3d3c489"
SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT")
YEARS=(2024,2025); SEED=20260927; REPLICATES=2000
AUTHORIZATION="AUTHORIZE_C7_T2_ONE_SHOT"
POLICIES=("P0_FULL","S1_FULL_T2_OVERLAY")
COSTS={"C0":{"fee_rate":0.,"slippage_rate":0.},"C_BASE":{"fee_rate":.001,"slippage_rate":.0002},
       "C_S5":{"fee_rate":.001,"slippage_rate":.0005},"C_S10":{"fee_rate":.001,"slippage_rate":.001}}
INPUTS={
 "frozen_entries":("artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv","6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"),
 "common_horizons_p0":("artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv","81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f"),
 "BTCUSDT_1m":("data/normalized/c2_history/BTCUSDT_1m.csv.gz","fa08f546140f3d6a7fad25ecb264c30d6f37e2986dcdf0ab21028ca3d5ba2cb7"),
 "ETHUSDT_1m":("data/normalized/c2_history/ETHUSDT_1m.csv.gz","fba74415cb41188235b287cc2a47f9935568f613bc5ea1bb1f1d5a9405fc5ef9"),
 "SOLUSDT_1m":("data/normalized/c2_history/SOLUSDT_1m.csv.gz","f0fef1a1f2f5ebdeac981d448860f94950c80e054dd78396c65cb91f858e4cef"),
 "XRPUSDT_1m":("data/normalized/c2_history/XRPUSDT_1m.csv.gz","71f9d40b1aa9c7fb03a42b181bb203e61c27a9e5a07ecc0a4438bc6581187cfb"),
 "BNBUSDT_1m":("data/normalized/c2_history/BNBUSDT_1m.csv.gz","6e79f58348cdcfd4e15b26b6f4c14728d8ccafd174072d6d174afbd05df8c84f")}

def canonical_bytes(x): return (json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def semantic_hash(x): return hashlib.sha256(canonical_bytes(x)).hexdigest()
def file_hash(p:Path)->str:
    reject_sealed_path(p); h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def reject_sealed_path(path:Path|str)->None:
    raw=os.fspath(path).replace("\\","/")
    for c in [x.casefold() for x in raw.split("/") if x not in ("",".")]:
        stem=c.rsplit(".",1)[0]; tokens=[x for x in re.split(r"[^a-z0-9]+",stem) if x]
        if "sealed" in stem or "confirmation" in stem or "2026" in stem or any(x=="2026" or re.fullmatch(r"2026q[1-4]",x) for x in tokens):
            raise PermissionError("sealed confirmation path prohibited")

def provenance(repo:Path)->dict:
    reject_sealed_path(repo)
    contract=repo/"contracts/C7_full_population_t2_exit_overlay_CONTRACT.md"
    if file_hash(contract)!=CONTRACT_SHA256: raise RuntimeError("contract hash mismatch")
    out={}
    for role,(rel,expected) in INPUTS.items():
        reject_sealed_path(rel); p=repo/rel
        if not p.is_file(): raise RuntimeError(f"missing accepted input: {rel}")
        actual=file_hash(p)
        if actual!=expected: raise RuntimeError(f"input hash mismatch: {role}")
        out[role]={"path":rel,"role":role,"byte_sha256":actual,"accepted":True}
    return out

def dt(s): return datetime.fromisoformat(str(s).replace("Z","+00:00"))

def unique_minute_rows(rows:Sequence[Mapping],symbol:str)->dict[int,tuple[float,float,float,float]]:
    out={}
    for r in rows:
        ms=int(r["open_time_ms"])
        if ms in out: raise RuntimeError(f"duplicate source minute: {symbol} {ms}")
        out[ms]=(float(r["open"]),float(r["high"]),float(r["low"]),float(r["close"]))
    return out

def reconcile_t2_identities(derived:Mapping[int,Mapping[str,str]],authoritative:Mapping[int,Mapping[str,str]])->dict:
    result={}; mismatch=[]
    for year,expected in ((2024,415),(2025,430)):
        left=dict(derived.get(year,{})); right=dict(authoritative.get(year,{})); ids=sorted(set(left)|set(right))
        bad=[tid for tid in ids if left.get(tid)!=right.get(tid)]; mismatch.extend(bad)
        result[str(year)]={"expected_count":expected,"authoritative_count":len(right),"derived_count":len(left),"identity_mismatches":len(bad),"mismatch_trade_ids":bad,"status":"PASS" if not bad and len(left)==len(right)==expected else "FAIL"}
    return {"status":"PASS" if not mismatch and all(x["status"]=="PASS" for x in result.values()) else "FAIL","by_year":result,"identity_mismatches":len(mismatch),"mismatch_trade_ids":sorted(set(mismatch))}

@dataclass(frozen=True)
class Minute:
    timestamp:datetime; open:float; high:float; low:float; close:float

@dataclass(frozen=True)
class T2State:
    decision_ts:datetime; running_peak:float; close:float; gain:float; current_return:float; d2:float

def first_t2(entry_ts:datetime, entry_price:float, p0_ts:datetime, minutes:Sequence[Minute])->T2State|None:
    """First frozen causal state. Input must be a contiguous UTC minute path."""
    ordered=sorted(minutes,key=lambda x:x.timestamp)
    if ordered and any(ordered[i].timestamp+timedelta(minutes=1)!=ordered[i+1].timestamp for i in range(len(ordered)-1)):
        raise ValueError("minute path gap")
    peak=entry_price; last=[]
    for m in ordered:
        if m.timestamp < entry_ts or m.timestamp >= p0_ts: continue
        if not all(math.isfinite(x) and x>0 for x in (m.open,m.high,m.low,m.close)) or m.high<max(m.open,m.close,m.low) or m.low>min(m.open,m.close,m.high):
            raise ValueError("invalid OHLC")
        peak=max(peak,m.high)
        last.append(m)
        if len(last)>5: last.pop(0)
        boundary=m.timestamp+timedelta(minutes=1)
        if boundary.minute%5 or boundary.second or boundary.microsecond or boundary<=entry_ts or boundary>=p0_ts: continue
        # UTC-aligned 5m bar is wholly post-entry only when all five minutes exist.
        start=boundary-timedelta(minutes=5)
        if len(last)!=5 or last[0].timestamp!=start or last[0].timestamp<entry_ts: continue
        close=last[-1].close; gain=peak/entry_price-1; ret=close/entry_price-1; d2=(entry_price+peak)/2
        if gain>=.01 and ret>0 and close>d2:
            return T2State(boundary,peak,close,gain,ret,d2)
    return None

def choose_exit(t2:T2State|None, immediate_opens:Mapping[datetime,Sequence[float]], p0_ts:datetime, p0_price:float)->dict:
    if t2 is None or t2.decision_ts>=p0_ts:
        return {"kind":"P0_FALLBACK","execution_ts":p0_ts,"raw_exit_price":p0_price,"executable":True,"reason":"NO_T2_OR_P0_PRECEDENCE"}
    # decision boundary is the open timestamp of the immediate next 1m interval.
    if t2.decision_ts>=p0_ts:
        return {"kind":"P0_FALLBACK","execution_ts":p0_ts,"raw_exit_price":p0_price,"executable":True,"reason":"P0_PRECEDENCE_TIE_OR_NOT_EARLIER"}
    vals=immediate_opens.get(t2.decision_ts)
    if vals is None: return {"kind":"UNRESOLVED","execution_ts":t2.decision_ts,"raw_exit_price":None,"executable":False,"reason":"MISSING_IMMEDIATE_NEXT_1M_OPEN"}
    if len(vals)!=1 or not math.isfinite(float(vals[0])) or float(vals[0])<=0:
        return {"kind":"UNRESOLVED","execution_ts":t2.decision_ts,"raw_exit_price":None,"executable":False,"reason":"INVALID_OR_DUPLICATE_IMMEDIATE_NEXT_1M_OPEN"}
    return {"kind":"T2_OVERLAY","execution_ts":t2.decision_ts,"raw_exit_price":float(vals[0]),"executable":True,"reason":None}

def cost_ledger(entry:float,exit:float,case:str,notional:float=1000.)->dict:
    if case not in COSTS or notional!=1000.: raise ValueError("frozen cost/notional required")
    c=COSTS[case]; ep=entry*(1+c["slippage_rate"]); qty=notional/ep; xp=exit*(1-c["slippage_rate"])
    en=notional; xn=xp*qty; ef=en*c["fee_rate"]; xf=xn*c["fee_rate"]
    raw=exit/entry-1; gross=xn/en-1; net=(xn-xf-en-ef)/en
    return {"raw_return":raw,"gross_return":gross,"net_return":net,"quantity":qty,"entry_executed_notional":en,"exit_executed_notional":xn,
            "entry_fee_quote":ef,"exit_fee_quote":xf,"entry_slippage_quote":ep*qty-entry*qty,"exit_slippage_quote":exit*qty-xn,
            "total_transaction_cost_quote":ef+xf+(ep-entry)*qty+(exit-xp)*qty,"executed_legs":2}

def moving_block_samples(entry_weeks:Mapping[str,str],seed:int=SEED,replicates:int=REPLICATES)->list[list[str]]:
    if seed!=SEED or replicates!=REPLICATES: raise ValueError("frozen bootstrap seed/replicates required")
    dates={k:dt(v).date() for k,v in entry_weeks.items()}; lo=min(dates.values()); hi=max(dates.values()); lo-=timedelta(days=lo.weekday()); hi-=timedelta(days=hi.weekday())
    span=(hi-lo).days//7+1
    if span<4: raise ValueError("fewer than four entry-week positions")
    at=defaultdict(list)
    for k,d in dates.items(): at[(d-lo).days//7].append(k)
    blocks=[range(i,i+4) for i in range(span-3)]
    if sum(any(at[j] for j in b) for b in blocks)<2: raise ValueError("fewer than two nonempty candidate blocks")
    rng=np.random.Generator(np.random.PCG64(seed)); out=[]
    for _ in range(replicates):
        positions=[]
        while len(positions)<span: positions.extend(blocks[int(rng.integers(len(blocks)))])
        out.append([k for pos in positions[:span] for k in sorted(at[pos])])
    return out

def month_samples(entry_times:Mapping[str,str],seed:int=SEED,replicates:int=REPLICATES)->list[list[str]]:
    if seed!=SEED or replicates!=REPLICATES: raise ValueError("frozen bootstrap seed/replicates required")
    groups=defaultdict(list)
    for k,v in entry_times.items(): groups[dt(v).strftime("%Y-%m")].append(k)
    months=sorted(groups)
    if len(months)<2: raise ValueError("fewer than two calendar months")
    rng=np.random.Generator(np.random.PCG64(seed)); return [[k for i in rng.integers(len(months),size=len(months)) for k in sorted(groups[months[int(i)]])] for _ in range(replicates)]

def interval(values:Sequence[float])->list[float]: return np.quantile(np.asarray(values,float),[.025,.975],method="linear").tolist()

def winner_availability(cohort:set[str], entry_weeks:Mapping[str,str], samples:Sequence[Sequence[str]], differences:Mapping[str,float])->dict:
    reasons=[]
    if len(cohort)<50: reasons.append("fewer_than_50_distinct_included_trades")
    try: moving_block_samples({k:v for k,v in entry_weeks.items() if k in cohort})
    except ValueError as e: reasons.append(str(e).replace(" ","_"))
    reps=[]
    for sample in samples:
        vals=[differences[k] for k in sample if k in cohort and k in differences]
        if not vals or not math.isfinite(float(np.mean(vals))): reasons.append("replicate_without_finite_cohort_mean"); break
        reps.append(float(np.mean(vals)))
    return {"available":not reasons,"reasons":sorted(set(reasons)),"distinct_trades":len(cohort),"replicates_finite":len(reps)}

def breadth(symbol_points:Mapping[str,float],pooled:float)->dict:
    vals={s:float(symbol_points[s]) for s in SYMBOLS}; pos={s:max(v,0.) for s,v in vals.items()}; total=sum(pos.values()); largest=max(pos.values())/total if total else None
    broad=sum(v>0 for v in vals.values())>=3 and sum(vals.values())/5>0 and (largest is None or largest<=.5)
    label="BROAD" if broad else "CONCENTRATED" if pooled>0 else "NO_POSITIVE_POOLED_BREADTH"
    return {"label":label,"positive_symbols":sum(v>0 for v in vals.values()),"equal_weight_symbol":sum(vals.values())/5,"largest_positive_contribution_share":largest}

def classify(*,available:bool,point:float,week_ci:Sequence[float],c_s5_point:float,safety_breach:bool,breadth_label:str,**ignored)->str:
    if not available: return "INSUFFICIENT"
    if point<=0 or week_ci[1]<0 or safety_breach: return "COUNTS_AGAINST_FULL_POPULATION_T2_OVERLAY"
    if week_ci[0]>0 and c_s5_point>0 and not safety_breach and breadth_label=="BROAD": return "SUPPORTS_FULL_POPULATION_T2_OVERLAY"
    return "MIXED"

OUTPUT_ARTIFACTS=("authorization","attempt_ledger","provenance_hash_manifest","canonical_paired_trade_table","leg_level_cost_table","evaluation_only_table",
 "inclusion_exclusion_unresolved_accounting","first_t2_audit","p0_precedence_tie_audit","fallback_audit","t2_non_t2_decomposition","complete_metrics","denominator_null_ledger",
 "week_bootstrap_samples_multiplicities_replicates","month_bootstrap_sensitivity","pooled_trade_weighted_report","equal_weight_symbol_report","report_2024","report_2025",
 "report_BTCUSDT","report_ETHUSDT","report_SOLUSDT","report_XRPUSDT","report_BNBUSDT","safety_report","winner_truncation_report","breadth_concentration",
 "cost_sensitivities","summed_union_exposure","trigger_fallback_rates","executed_legs_notional","final_classification_predicates","reproducibility_hashes","human_readable_classification")

TRADE_FIELDS=("trade_id","symbol","year","entry_execution_ts","entry_price","entry_notional_usdt","policy_id","trigger_status","decision_ts","execution_ts","raw_exit_price","cost_scenario","executed_quantity","entry_executed_notional","exit_executed_notional","entry_fee","exit_fee","entry_slippage","exit_slippage","total_transaction_cost","raw_return","gross_return","net_return","gross_pnl_usdt","net_pnl_usdt","holding_seconds")
LEG_FIELDS=("trade_id","policy_id","cost_scenario","leg","executed_quantity","executed_notional","fee_quote","slippage_quote")
EVAL_FIELDS=("trade_id","policy_id","common_mfe","held_mfe","capture_fraction","common_capture_gap","held_peak_surrender","positive_mfe_surrendered_fraction","green_to_red","common_green_to_red","preserved_at_least_half_peak","downside_value","p0_winner_2","p0_winner_3","p0_winner_5","truncation_2","truncation_3","truncation_5","opportunity_foregone","valid_denominator","null_reason")
OUTPUT_SCHEMA={
 "version":"C7_T2_OUTPUT_SCHEMA_V2","type":"object","required":list(OUTPUT_ARTIFACTS),
 "enumerations":{"policies":list(POLICIES),"costs":list(COSTS),"years":list(YEARS),"symbols":list(SYMBOLS)},
 "properties":{
  "authorization":{"required":["attempt_id","authorization_reference","started_at","finished_at","lifecycle","economic_read","economic_emission","failure_reason","output_hashes"]},
  "attempt_ledger":{"required":["events","terminal_count"]},
  "provenance_hash_manifest":{"required":["contract_sha256","source_input_hashes","population_sha256","code_sha256","config_sha256","environment_sha256","output_schema_sha256","seed"]},
  "canonical_paired_trade_table":{"required":["columns","rows"],"row_required":list(TRADE_FIELDS)},
  "leg_level_cost_table":{"required":["columns","rows"],"row_required":list(LEG_FIELDS)},
  "evaluation_only_table":{"required":["columns","rows","forbidden_from_decisions"],"row_required":list(EVAL_FIELDS)},
  "inclusion_exclusion_unresolved_accounting":{"required":["source_count","included_count","excluded_count","unresolved_count","reasons"]},
  "first_t2_audit":{"required":["rows"],"row_required":["trade_id","first_t2_identity","t2_timestamp","immediate_execution_timestamp","p0_timestamp","precedence_state","fallback_reason"]},
  "p0_precedence_tie_audit":{"required":["count","trade_ids"]},"fallback_audit":{"required":["count","identity_verified","mismatches"]},
  "t2_non_t2_decomposition":{"required":["all_eligible","t2_reaching","fallback","counts","percentages","pnl_contributions","reconciliation"]},
  "complete_metrics":{"required":["pooled","years","symbols","equal_weight_symbol","costs","valid_denominators","null_counts"]},
  "denominator_null_ledger":{"required":["rows","unresolved_count","null_count"]},
  "week_bootstrap_samples_multiplicities_replicates":{"required":["generator","seed","replicates","block_length_weeks","candidate_blocks","sampled_block_indices","trade_multiplicities","replicate_vectors","primary_ci","safety_cis","quantile_method"]},
  "month_bootstrap_sensitivity":{"required":["descriptive_only","generator","seed","replicates","sampled_month_indices","trade_multiplicities","replicate_vectors","ci","quantile_method"]},
  "pooled_trade_weighted_report":{"required":["population","policies","costs","metrics"]},"equal_weight_symbol_report":{"required":["symbols","point_estimate","metrics"]},
  "report_2024":{"required":["year","population","decomposition","economics","costs","holding_exposure","path_capture","safety","winner_truncation"]},"report_2025":{"required":["year","population","decomposition","economics","costs","holding_exposure","path_capture","safety","winner_truncation"]},
  **{f"report_{s}":{"required":["symbol","population","decomposition","economics","costs","holding_exposure","path_capture","safety","winner_truncation"]} for s in SYMBOLS},
  "safety_report":{"required":["expected_shortfall","green_to_red","preserved_half","winner_cohorts","adverse_breach","mandatory_available"]},
  "winner_truncation_report":{"required":["thresholds","winner_counts","winner_deltas","truncation_counts","truncation_rates","opportunity_foregone","availability"]},
  "breadth_concentration":{"required":["signed_symbol_contributions","positive_shares","equal_weight_point_estimate","positive_symbol_count","largest_positive_share","breadth_label"]},
  "cost_sensitivities":{"required":["C0","C_BASE","C_S5","C_S10"]},
  "summed_union_exposure":{"required":["mean_holding","median_holding","summed_exposure","union_exposure","union_unavailable_reason"]},
  "trigger_fallback_rates":{"required":["trigger_count","trigger_rate","fallback_count","fallback_rate"]},"executed_legs_notional":{"required":["leg_count","entry_notional","exit_notional"]},
  "final_classification_predicates":{"required":["evidence_available","primary_point_positive","primary_ci_entirely_positive","primary_ci_entirely_negative","safety_breach","c_s5_positive","breadth_label","precedence_order","final_label"]},
  "reproducibility_hashes":{"required":["trade_table","evaluation_table","bootstrap","report_core"]},"human_readable_classification":{"required":["label","statement"]}
 }}

_ARRAY_FIELDS={"rows","events","trade_ids","mismatches","candidate_blocks","sampled_block_indices","trade_multiplicities","sampled_month_indices","thresholds","precedence_order","columns","policies","costs","symbols","lifecycle"}
_OBJECT_FIELDS={"output_hashes","source_input_hashes","reasons","counts","percentages","pnl_contributions","reconciliation","pooled","years","symbols","equal_weight_symbol","costs","valid_denominators","null_counts","replicate_vectors","safety_cis","metrics","decomposition","economics","holding_exposure","path_capture","safety","winner_truncation","winner_cohorts","signed_symbol_contributions","positive_shares","availability","winner_counts","winner_deltas","truncation_counts","truncation_rates"}
_BOOL_FIELDS={"economic_read","economic_emission","identity_verified","descriptive_only","adverse_breach","mandatory_available","evidence_available","primary_point_positive","primary_ci_entirely_positive","primary_ci_entirely_negative","safety_breach","c_s5_positive","forbidden_from_decisions"}
_NUMBER_FIELDS={"seed","replicates","block_length_weeks","terminal_count","population","source_count","included_count","excluded_count","unresolved_count","null_count","year","positive_symbol_count","leg_count","trigger_count","trigger_rate","fallback_count","fallback_rate","entry_notional","exit_notional","mean_holding","median_holding","summed_exposure","union_exposure","point_estimate","largest_positive_share"}
for _spec in OUTPUT_SCHEMA["properties"].values():
    _spec["type"]="object"
    _spec["field_types"]={k:("array" if k in _ARRAY_FIELDS else "object" if k in _OBJECT_FIELDS else "boolean" if k in _BOOL_FIELDS else "number" if k in _NUMBER_FIELDS else "string_or_null" if k in {"failure_reason","union_unavailable_reason"} else "any") for k in _spec["required"]}
    if "row_required" in _spec: _spec["row_field_types"]={k:"any" for k in _spec["row_required"]}
OUTPUT_SCHEMA["properties"]["complete_metrics"]["field_types"].update({"years":"object","symbols":"object","costs":"array"})

def _fixture_value(name):
    if name in {"rows","events","trade_ids","mismatches","candidate_blocks","sampled_block_indices","trade_multiplicities","sampled_month_indices","thresholds","precedence_order","policies","costs","symbols","lifecycle"}: return []
    if name in {"economic_read","economic_emission","identity_verified","descriptive_only","adverse_breach","mandatory_available","evidence_available","primary_point_positive","primary_ci_entirely_positive","primary_ci_entirely_negative","safety_breach","c_s5_positive","forbidden_from_decisions"}: return False
    if name.endswith("count") or name in _NUMBER_FIELDS: return 0
    if name in {"columns"}: return []
    if name.endswith("_sha256") or name in {"trade_table","evaluation_table","bootstrap","report_core"}: return "0"*64
    if name in {"failure_reason","union_unavailable_reason","null_reason"}: return None
    if name in {"output_hashes","source_input_hashes","reasons","counts","percentages","pnl_contributions","reconciliation","pooled","equal_weight_symbol","valid_denominators","null_counts","years","metrics","decomposition","economics","holding_exposure","path_capture","safety","winner_truncation","signed_symbol_contributions","positive_shares","winner_cohorts","safety_cis","replicate_vectors","winner_counts","winner_deltas","truncation_counts","truncation_rates","availability"}: return {}
    return "SYNTHETIC"

def synthetic_report()->dict:
    out={}
    for section,spec in OUTPUT_SCHEMA["properties"].items():
        obj={k:_fixture_value(k) for k in spec["required"]}
        if "row_required" in spec: obj["rows"]=[{k:_fixture_value(k) for k in spec["row_required"]}]
        out[section]=obj
    out["canonical_paired_trade_table"]["columns"]=list(TRADE_FIELDS); out["leg_level_cost_table"]["columns"]=list(LEG_FIELDS); out["evaluation_only_table"]["columns"]=list(EVAL_FIELDS)
    out["complete_metrics"]["symbols"]={}
    out["report_2024"]["year"]=2024; out["report_2025"]["year"]=2025
    for s in SYMBOLS: out[f"report_{s}"]["symbol"]=s
    for c in COSTS: out["cost_sensitivities"][c]={"point_estimate":0.0}
    return out

def validate_report(r:Mapping,schema:Mapping=OUTPUT_SCHEMA)->None:
    missing=set(schema["required"])-set(r)
    if missing: raise ValueError(f"missing output sections: {sorted(missing)}")
    for section,spec in schema["properties"].items():
        if not isinstance(r[section],Mapping): raise ValueError(f"{section} must be object")
        absent=set(spec["required"])-set(r[section])
        if absent: raise ValueError(f"{section} missing fields: {sorted(absent)}")
        for field,kind in spec.get("field_types",{}).items():
            value=r[section][field]
            valid=kind=="any" or (kind=="array" and isinstance(value,list)) or (kind=="object" and isinstance(value,Mapping)) or (kind=="boolean" and isinstance(value,bool)) or (kind=="number" and (value is None or isinstance(value,(int,float)) and not isinstance(value,bool))) or (kind=="string_or_null" and (value is None or isinstance(value,str)))
            if not valid: raise ValueError(f"{section}.{field} must be {kind}")
        if "row_required" in spec:
            if not isinstance(r[section]["rows"],list): raise ValueError(f"{section}.rows must be array")
            for row in r[section]["rows"]:
                absent=set(spec["row_required"])-set(row)
                if absent: raise ValueError(f"{section} row missing fields: {sorted(absent)}")

LEDGER_FIELDS={"attempt_id","event","timestamp","stage","purpose","authorization_reference","contract_sha256","readiness_sha256","execution_freeze_sha256","source_hashes","population_sha256","code_sha256","config_sha256","environment_sha256","output_schema_sha256","seed","status","failure_reason","economic_read","economic_emission","output_hashes"}
IDENTITY_FIELDS=("contract_sha256","readiness_sha256","execution_freeze_sha256","source_hashes","population_sha256","code_sha256","config_sha256","environment_sha256","output_schema_sha256","seed")
def append_attempt(path:Path,event:Mapping)->None:
    reject_sealed_path(path)
    kinds=("PREFLIGHT_FAIL","READINESS_ACCEPTED","START","ECONOMIC_READ","ECONOMIC_EMISSION","PASS","FAIL")
    if set(event)!=LEDGER_FIELDS or event["event"] not in kinds or event["status"]!=event["event"]: raise ValueError("invalid ledger event")
    path.parent.mkdir(parents=True,exist_ok=True); lock=Path(str(path)+".lock")
    with lock.open("a+b") as lf:
        fcntl.flock(lf,fcntl.LOCK_EX)
        prior=[json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
        same=[x for x in prior if x["attempt_id"]==event["attempt_id"]]
        production=[x for x in prior if x.get("stage")=="T2" and x.get("purpose")=="production"]
        consumed=any(x["economic_read"] or x["economic_emission"] for x in production)
        if event["event"]=="READINESS_ACCEPTED":
            if event["stage"]!="T1" or event["economic_read"] or event["economic_emission"] or event["failure_reason"] or not event["output_hashes"]: raise ValueError("invalid readiness acceptance")
        elif event["event"]=="PREFLIGHT_FAIL":
            if same or event["economic_read"] or event["economic_emission"] or not event["failure_reason"]: raise ValueError("invalid preflight failure")
            prior_attempts=[x for x in production if x["event"] in ("PREFLIGHT_FAIL","START")]
            if prior_attempts and any(event[k]!=prior_attempts[0][k] for k in IDENTITY_FIELDS): raise RuntimeError("pre-economic retry identities changed")
        elif event["event"]=="START":
            if same or consumed or any(x["event"]=="START" and not any(y["attempt_id"]==x["attempt_id"] and y["event"] in ("PASS","FAIL") for y in production) for x in production): raise RuntimeError("attempt exists, open, or C7 one-shot consumed")
            prior_attempts=[x for x in production if x["event"] in ("PREFLIGHT_FAIL","START")]
            if prior_attempts and any(event[k]!=prior_attempts[0][k] for k in IDENTITY_FIELDS): raise RuntimeError("pre-economic retry identities changed")
        else:
            starts=[x for x in same if x["event"]=="START"]; terminals=[x for x in same if x["event"] in ("PASS","FAIL")]
            if len(starts)!=1 or terminals: raise RuntimeError("event requires exactly one open START")
            if any(event[k]!=starts[0][k] for k in IDENTITY_FIELDS): raise RuntimeError("attempt identity changed")
            if event["event"]=="ECONOMIC_READ" and (not event["economic_read"] or event["economic_emission"]): raise ValueError("invalid economic-read transition")
            if event["event"]=="ECONOMIC_EMISSION" and (not event["economic_read"] or not event["economic_emission"]): raise ValueError("invalid economic-emission transition")
        if event["event"]=="PASS" and not event["output_hashes"]: raise ValueError("PASS requires outputs")
        if event["event"]=="FAIL" and not event["failure_reason"]: raise ValueError("FAIL requires reason")
        with path.open("ab") as f: f.write(canonical_bytes(dict(event))); f.flush(); os.fsync(f.fileno())

def enforce_fallback_identity(trade_rows:Sequence[Mapping],evaluation_rows:Sequence[Mapping]=())->None:
    economic=("decision_ts","execution_ts","raw_exit_price","cost_scenario","executed_quantity","entry_executed_notional","exit_executed_notional","entry_fee","exit_fee","entry_slippage","exit_slippage","total_transaction_cost","raw_return","gross_return","net_return","gross_pnl_usdt","net_pnl_usdt","holding_seconds")
    grouped=defaultdict(dict)
    for r in trade_rows: grouped[(r["trade_id"],r["cost_scenario"])][r["policy_id"]]=r
    for key,pair in grouped.items():
        s=pair.get("S1_FULL_T2_OVERLAY"); p=pair.get("P0_FULL")
        if s and s.get("trigger_status")=="P0_FALLBACK" and (not p or any(s[x]!=p[x] for x in economic)): raise RuntimeError(f"fallback economic identity mismatch: {key}")
    legs=defaultdict(dict)
    for r in getattr(trade_rows,"legs",()): legs[(r["trade_id"],r["cost_scenario"],r["leg"])][r["policy_id"]]=r
    eg=defaultdict(dict)
    for r in evaluation_rows: eg[r["trade_id"]][r["policy_id"]]=r
    for tid,pair in eg.items():
        s=pair.get("S1_FULL_T2_OVERLAY"); p=pair.get("P0_FULL")
        if s and s.get("trigger_status")=="P0_FALLBACK":
            ignored={"policy_id","trigger_status"}
            if not p or any(s[k]!=p.get(k) for k in s if k not in ignored): raise RuntimeError(f"fallback evaluation identity mismatch: {tid}")

def enforce_fallback_leg_identity(trade_rows:Sequence[Mapping],leg_rows:Sequence[Mapping])->None:
    fallback={r["trade_id"] for r in trade_rows if r["policy_id"]=="S1_FULL_T2_OVERLAY" and r["trigger_status"]=="P0_FALLBACK"}
    grouped=defaultdict(dict)
    for r in leg_rows: grouped[(r["trade_id"],r["cost_scenario"],r["leg"])][r["policy_id"]]=r
    for key,pair in grouped.items():
        if key[0] not in fallback: continue
        s=pair.get("S1_FULL_T2_OVERLAY"); p=pair.get("P0_FULL")
        if not s or not p or any(s[k]!=p.get(k) for k in ("cost_scenario","leg","executed_quantity","executed_notional","fee_quote","slippage_quote")):
            raise RuntimeError(f"fallback leg identity mismatch: {key}")

def _build_evaluation_rows(population:Sequence[Mapping],trades:Sequence[Mapping],market:Mapping[str,Mapping[int,Sequence[float]]])->list[dict]:
    out=[]; c0={(r["trade_id"],r["policy_id"]):r for r in trades if r["cost_scenario"]=="C0"}
    for src in population:
        if not src.get("included",True): continue
        entry=float(src["entry_price"]); start=int(dt(src["entry_execution_ts"]).timestamp()*1000); end=int(dt(src["p0_execution_ts"]).timestamp()*1000)
        points=[(ms,v) for ms,v in market[src["symbol"]].items() if start<=ms<end]; common_peak=max([entry,*[float(v[1]) for _,v in points]]); common_mfe=common_peak/entry-1; p0_raw=float(src["p0_raw_exit_price"])/entry-1
        base=None
        for policy in POLICIES:
            tr=c0[(src["trade_id"],policy)]; exit_ms=int(dt(tr["execution_ts"]).timestamp()*1000); raw=tr["raw_exit_price"]/entry-1; held_peak=max([entry,tr["raw_exit_price"],*[float(v[1]) for ms,v in points if ms<exit_ms]]); held_mfe=held_peak/entry-1; lows=[float(v[2]) for ms,v in points if ms<exit_ms]; future=[float(v[1]) for ms,v in points if ms>=exit_ms]
            row={"trade_id":src["trade_id"],"policy_id":policy,"trigger_status":tr["trigger_status"],"common_mfe":common_mfe,"held_mfe":held_mfe,"capture_fraction":raw/common_mfe if common_mfe>=.005 else None,"common_capture_gap":common_mfe-raw,"held_peak_surrender":held_mfe-raw,"positive_mfe_surrendered_fraction":(common_mfe-raw)/common_mfe if common_mfe>=.005 else None,"green_to_red":held_mfe>0 and raw<0,"common_green_to_red":common_mfe>0 and raw<0,"preserved_at_least_half_peak":raw>=.5*common_mfe if common_mfe>=.005 else None,"downside_value":min(lows)/entry-1 if lows else None,"p0_winner_2":p0_raw>=.02,"p0_winner_3":p0_raw>=.03,"p0_winner_5":p0_raw>=.05,"truncation_2":bool(future) and max(future)>=entry*1.02,"truncation_3":bool(future) and max(future)>=entry*1.03,"truncation_5":bool(future) and max(future)>=entry*1.05,"opportunity_foregone":max(future)/entry-1-raw if future else None,"valid_denominator":common_mfe>=.005,"null_reason":None if common_mfe>=.005 else "COMMON_MFE_BELOW_0_005"}
            if policy=="P0_FULL": base=row
            elif tr["trigger_status"]=="P0_FALLBACK": row={**base,"policy_id":policy,"trigger_status":"P0_FALLBACK"}
            out.append(row)
    return out

def _union_seconds(rows:Sequence[Mapping])->float:
    intervals=sorted((dt(r["entry_execution_ts"]),dt(r["execution_ts"])) for r in rows)
    if not intervals: return 0.0
    total=0.; start,end=intervals[0]
    for a,b in intervals[1:]:
        if a<=end: end=max(end,b)
        else: total+=(end-start).total_seconds(); start,end=a,b
    return total+(end-start).total_seconds()

def _bootstrap_details(entry_times:Mapping[str,str])->tuple[list,list,list]:
    dates={k:dt(v).date() for k,v in entry_times.items()}; lo=min(dates.values()); hi=max(dates.values()); lo-=timedelta(days=lo.weekday()); hi-=timedelta(days=hi.weekday()); span=(hi-lo).days//7+1
    at=defaultdict(list)
    for k,d in dates.items(): at[(d-lo).days//7].append(k)
    candidates=[list(range(i,i+4)) for i in range(span-3)]
    if span<4 or sum(any(at[j] for j in b) for b in candidates)<2: raise ValueError("insufficient entry-week blocks")
    rng=np.random.Generator(np.random.PCG64(SEED)); indices=[]; samples=[]
    for _ in range(REPLICATES):
        positions=[]; chosen=[]
        while len(positions)<span:
            i=int(rng.integers(len(candidates))); chosen.append(i); positions.extend(candidates[i])
        indices.append(chosen); samples.append([k for pos in positions[:span] for k in sorted(at[pos])])
    return candidates,indices,samples

def _month_details(entry_times:Mapping[str,str])->tuple[list,list,list]:
    groups=defaultdict(list)
    for k,v in entry_times.items(): groups[dt(v).strftime("%Y-%m")].append(k)
    months=sorted(groups)
    if len(months)<2: raise ValueError("fewer than two calendar months")
    rng=np.random.Generator(np.random.PCG64(SEED)); indices=[]; samples=[]
    for _ in range(REPLICATES):
        ix=[int(i) for i in rng.integers(len(months),size=len(months))]; indices.append(ix); samples.append([k for i in ix for k in sorted(groups[months[i]])])
    return months,indices,samples

def synthetic_production_fixture()->tuple[list[dict],dict,list[dict]]:
    """Entirely synthetic pre-2026 fixture used only for T1 readiness/tests."""
    population=[]; opens={}; evaluation=[]; base=datetime(2024,1,1,tzinfo=timezone.utc)
    for i in range(60):
        entry=base+timedelta(weeks=i); p0=entry+timedelta(hours=2); trigger=i%3==0; tie=i==1; t2=entry+timedelta(hours=1) if trigger else p0 if tie else None; tid=f"SYNTHETIC-{i:02d}"; symbol=SYMBOLS[i%len(SYMBOLS)]
        population.append({"trade_id":tid,"symbol":symbol,"entry_year":entry.year,"entry_execution_ts":entry.isoformat(),"entry_price":"100","p0_execution_ts":p0.isoformat(),"p0_raw_exit_price":"106","first_t2_decision_ts":t2.isoformat() if t2 else None,"overlay_strictly_before_p0":trigger,"p0_precedence_tie":tie,"included":True})
        if trigger: opens[(symbol,t2.isoformat())]=104+i/1000
        for policy in POLICIES:
            overlay=policy=="S1_FULL_T2_OVERLAY" and trigger
            evaluation.append({"trade_id":tid,"policy_id":policy,"trigger_status":"T2_REACHING" if overlay else "P0_FALLBACK" if policy=="S1_FULL_T2_OVERLAY" else "CANONICAL_P0","common_mfe":.08,"held_mfe":.07 if overlay else .08,"capture_fraction":.5 if overlay else .75,"common_capture_gap":.04 if overlay else .02,"held_peak_surrender":.03 if overlay else .02,"positive_mfe_surrendered_fraction":.5 if overlay else .25,"green_to_red":False,"common_green_to_red":False,"preserved_at_least_half_peak":True,"downside_value":-.01,"p0_winner_2":True,"p0_winner_3":True,"p0_winner_5":True,"truncation_2":overlay,"truncation_3":overlay,"truncation_5":False,"opportunity_foregone":.01 if overlay else 0.,"valid_denominator":True,"null_reason":None})
    return population,opens,evaluation

def execute_c7(population:Sequence[Mapping], immediate_opens:Mapping[tuple[str,str],float], evaluation_rows:Sequence[Mapping]=(),market_minutes:Mapping[str,Mapping[int,Sequence[float]]]|None=None)->dict:
    """Fixed executor. Production supplies frozen rows; tests supply synthetic rows."""
    included=[r for r in population if r.get("included",True)]; trades=[]; legs=[]; audits=[]
    for src in included:
        p0_ts=dt(src["p0_execution_ts"]); overlay_ok=bool(src.get("overlay_strictly_before_p0")); t2_ts=dt(src["first_t2_decision_ts"]) if overlay_ok else None
        t2_price=immediate_opens.get((src["symbol"],src.get("first_t2_decision_ts"))) if t2_ts else None
        if t2_ts and (t2_price is None or not math.isfinite(float(t2_price)) or float(t2_price)<=0): raise RuntimeError("missing/invalid immediate T2 open")
        tie=bool(src.get("p0_precedence_tie")); state="P0_PRECEDENCE_TIE_OR_NOT_EARLIER" if tie else "T2_STRICTLY_EARLIER" if t2_ts else "P0_FALLBACK"
        audits.append({"trade_id":src["trade_id"],"first_t2_identity":src.get("first_t2_decision_ts"),"t2_timestamp":src.get("first_t2_decision_ts"),"immediate_execution_timestamp":src.get("first_t2_decision_ts") if t2_ts else None,"p0_timestamp":src["p0_execution_ts"],"precedence_state":state,"fallback_reason":state if not t2_ts else None})
        for policy in POLICIES:
            overlay=policy=="S1_FULL_T2_OVERLAY" and t2_ts is not None; exit_ts=t2_ts if overlay else p0_ts; exit_price=float(t2_price) if overlay else float(src["p0_raw_exit_price"]); trigger="T2_REACHING" if overlay else "P0_FALLBACK" if policy=="S1_FULL_T2_OVERLAY" else "CANONICAL_P0"
            for case in COSTS:
                c=cost_ledger(float(src["entry_price"]),exit_price,case); holding=(exit_ts-dt(src["entry_execution_ts"])).total_seconds()
                row={"trade_id":src["trade_id"],"symbol":src["symbol"],"year":int(src.get("entry_year",dt(src["entry_execution_ts"]).year)),"entry_execution_ts":src["entry_execution_ts"],"entry_price":float(src["entry_price"]),"entry_notional_usdt":1000.0,"policy_id":policy,"trigger_status":trigger,"decision_ts":src.get("first_t2_decision_ts") if overlay else src["p0_execution_ts"],"execution_ts":exit_ts.isoformat(),"raw_exit_price":exit_price,"cost_scenario":case,"executed_quantity":c["quantity"],"entry_executed_notional":c["entry_executed_notional"],"exit_executed_notional":c["exit_executed_notional"],"entry_fee":c["entry_fee_quote"],"exit_fee":c["exit_fee_quote"],"entry_slippage":c["entry_slippage_quote"],"exit_slippage":c["exit_slippage_quote"],"total_transaction_cost":c["total_transaction_cost_quote"],"raw_return":c["raw_return"],"gross_return":c["gross_return"],"net_return":c["net_return"],"gross_pnl_usdt":c["gross_return"]*1000,"net_pnl_usdt":c["net_return"]*1000,"holding_seconds":holding}
                trades.append(row); legs.extend([{"trade_id":src["trade_id"],"policy_id":policy,"cost_scenario":case,"leg":"ENTRY","executed_quantity":c["quantity"],"executed_notional":c["entry_executed_notional"],"fee_quote":c["entry_fee_quote"],"slippage_quote":c["entry_slippage_quote"]},{"trade_id":src["trade_id"],"policy_id":policy,"cost_scenario":case,"leg":"EXIT","executed_quantity":c["quantity"],"executed_notional":c["exit_executed_notional"],"fee_quote":c["exit_fee_quote"],"slippage_quote":c["exit_slippage_quote"]}])
    if market_minutes is not None: evaluation_rows=_build_evaluation_rows(included,trades,market_minutes)
    evaluation_rows=list(evaluation_rows); enforce_fallback_identity(trades,evaluation_rows); enforce_fallback_leg_identity(trades,legs)
    n=len(included); triggers=sum(bool(x.get("overlay_strictly_before_p0")) for x in included); fallback=n-triggers
    def summary(selected):
        vals=np.asarray([float(x["net_return"]) for x in selected]); raw=np.asarray([float(x["raw_return"]) for x in selected]); gross=np.asarray([float(x["gross_return"]) for x in selected]); holds=np.asarray([float(x["holding_seconds"]) for x in selected])
        loss=vals[vals<0]; q10=float(np.quantile(vals,.1,method="linear")) if len(vals) else None
        return {"count":len(selected),"mean_raw_return":float(raw.mean()) if len(raw) else None,"mean_gross_return":float(gross.mean()) if len(gross) else None,"mean_net_return":float(vals.mean()) if len(vals) else None,"median_net_return":float(np.median(vals)) if len(vals) else None,"win_rate":float(np.mean(vals>0)) if len(vals) else None,"zero_rate":float(np.mean(vals==0)) if len(vals) else None,"loss_rate":float(np.mean(vals<0)) if len(vals) else None,"gross_pnl_usdt":float(sum(x["gross_pnl_usdt"] for x in selected)),"net_pnl_usdt":float(sum(x["net_pnl_usdt"] for x in selected)),"fees_usdt":float(sum(x["entry_fee"]+x["exit_fee"] for x in selected)),"slippage_usdt":float(sum(x["entry_slippage"]+x["exit_slippage"] for x in selected)),"transaction_cost_usdt":float(sum(x["total_transaction_cost"] for x in selected)),"mean_holding_seconds":float(holds.mean()) if len(holds) else None,"median_holding_seconds":float(np.median(holds)) if len(holds) else None,"summed_exposure_seconds":float(holds.sum()),"union_exposure_seconds":_union_seconds(selected),"downside_deviation":float(np.sqrt(np.mean(np.minimum(vals,0.)**2))) if len(vals) else None,"mean_loss":float(loss.mean()) if len(loss) else None,"p05":float(np.quantile(vals,.05,method="linear")) if len(vals) else None,"p10":q10,"expected_shortfall_10":float(vals[vals<=q10].mean()) if len(vals) else None,"worst_trade":float(vals.min()) if len(vals) else None,"executed_legs":2*len(selected),"executed_notional":float(sum(x["entry_executed_notional"]+x["exit_executed_notional"] for x in selected))}
    reports={c:{p:summary([x for x in trades if x["cost_scenario"]==c and x["policy_id"]==p]) for p in POLICIES} for c in COSTS}
    year_metrics={str(y):{c:{p:summary([x for x in trades if x["year"]==y and x["cost_scenario"]==c and x["policy_id"]==p]) for p in POLICIES} for c in COSTS} for y in YEARS}; symbol_metrics={s:{c:{p:summary([x for x in trades if x["symbol"]==s and x["cost_scenario"]==c and x["policy_id"]==p]) for p in POLICIES} for c in COSTS} for s in SYMBOLS}
    paired={}
    for case in COSTS:
        p={x["trade_id"]:x for x in trades if x["policy_id"]=="P0_FULL" and x["cost_scenario"]==case}; s={x["trade_id"]:x for x in trades if x["policy_id"]=="S1_FULL_T2_OVERLAY" and x["cost_scenario"]==case}; paired[case]={k:s[k]["net_return"]-p[k]["net_return"] for k in p}
    diffs=paired["C_BASE"]; p0={x["trade_id"]:x for x in trades if x["policy_id"]=="P0_FULL" and x["cost_scenario"]=="C_BASE"}; s1={x["trade_id"]:x for x in trades if x["policy_id"]=="S1_FULL_T2_OVERLAY" and x["cost_scenario"]=="C_BASE"}; point=float(np.mean(list(diffs.values()))) if diffs else 0.
    ev={(r["trade_id"],r["policy_id"]):r for r in evaluation_rows}; null_rows=[]
    for r in evaluation_rows:
        if not r.get("valid_denominator",False): null_rows.append({"trade_id":r["trade_id"],"policy_id":r["policy_id"],"metric":"capture_fraction","reason":r.get("null_reason")})
    def eval_panel(ids:set[str]):
        rows=[r for r in evaluation_rows if r["trade_id"] in ids]; out={}
        for metric in ("common_mfe","held_mfe","capture_fraction","common_capture_gap","held_peak_surrender","positive_mfe_surrendered_fraction","green_to_red","common_green_to_red","preserved_at_least_half_peak","downside_value","opportunity_foregone"):
            out[metric]={p:{"valid":sum(r.get(metric) is not None for r in rows if r["policy_id"]==p),"null":sum(r.get(metric) is None for r in rows if r["policy_id"]==p),"mean":float(np.mean([float(r[metric]) for r in rows if r["policy_id"]==p and r.get(metric) is not None])) if any(r["policy_id"]==p and r.get(metric) is not None for r in rows) else None} for p in POLICIES}
        return out
    all_ids={r["trade_id"] for r in included}; path_panel=eval_panel(all_ids)
    weeks={r["trade_id"]:r["entry_execution_ts"] for r in included}; ci=[None,None]; week_art={"generator":"PCG64","seed":SEED,"replicates":REPLICATES,"block_length_weeks":4,"candidate_blocks":[],"sampled_block_indices":[],"trade_multiplicities":[],"replicate_vectors":{},"primary_ci":ci,"safety_cis":{},"quantile_method":"Type-7 linear","unavailable_reason":"insufficient entry-week structure"}; month_art={"descriptive_only":True,"generator":"PCG64","seed":SEED,"replicates":REPLICATES,"sampled_month_indices":[],"trade_multiplicities":[],"replicate_vectors":{},"ci":[None,None],"quantile_method":"Type-7 linear","unavailable_reason":"insufficient calendar-month structure"}; samples=[]
    try:
        candidates,block_indices,samples=_bootstrap_details(weeks); reps=[float(np.mean([diffs[k] for k in sample])) for sample in samples]; ci=interval(reps); week_art={"generator":"PCG64","seed":SEED,"replicates":REPLICATES,"block_length_weeks":4,"candidate_blocks":candidates,"sampled_block_indices":block_indices,"trade_multiplicities":samples,"replicate_vectors":{"primary_mean":reps},"primary_ci":ci,"safety_cis":{},"quantile_method":"Type-7 linear"}
        months,month_indices,month_samples_= _month_details(weeks); mreps=[float(np.mean([diffs[k] for k in sample])) for sample in month_samples_]; month_art={"descriptive_only":True,"generator":"PCG64","seed":SEED,"replicates":REPLICATES,"sampled_month_indices":month_indices,"trade_multiplicities":month_samples_,"replicate_vectors":{"primary_mean":mreps},"ci":interval(mreps),"quantile_method":"Type-7 linear","months":months}
    except ValueError as exc:
        week_art["unavailable_reason"]=str(exc); month_art["unavailable_reason"]=str(exc)
    safety_breach=False; safety_available=bool(evaluation_rows) and bool(samples); safety_panel={}; winner_panel={}
    def diff_stat(metric,sample):
        vals=[]
        for k in sample:
            a=ev.get((k,"S1_FULL_T2_OVERLAY"),{}).get(metric); b=ev.get((k,"P0_FULL"),{}).get(metric)
            if a is not None and b is not None: vals.append(float(a)-float(b))
        return float(np.mean(vals)) if vals else math.nan
    if samples and evaluation_rows:
        for metric,direction in (("green_to_red","higher_adverse"),("preserved_at_least_half_peak","lower_adverse")):
            rv=[diff_stat(metric,s) for s in samples]; finite=[x for x in rv if math.isfinite(x)]; mci=interval(finite) if len(finite)==REPLICATES else None; adverse=bool(mci and (mci[0]>0 if direction=="higher_adverse" else mci[1]<0)); safety_panel[metric]={"point_estimate":diff_stat(metric,list(all_ids)),"ci95":mci,"adverse_breach":adverse,"available":mci is not None}; safety_breach|=adverse; safety_available&=mci is not None
        for pct in (2,3,5):
            cohort={r["trade_id"] for r in evaluation_rows if r["policy_id"]=="P0_FULL" and r[f"p0_winner_{pct}"]}; avail=winner_availability(cohort,weeks,samples,diffs); rv=[float(np.mean([diffs[k] for k in s if k in cohort])) for s in samples if any(k in cohort for k in s)]; wci=interval(rv) if avail["available"] else None; adverse=bool(wci and wci[1]<0); winner_panel[str(pct)]={**avail,"point_estimate":float(np.mean([diffs[k] for k in cohort])) if cohort else None,"ci95":wci,"adverse_breach":adverse}; safety_breach|=adverse; safety_available&=avail["available"]
        def es(a): q=np.quantile(a,.1,method="linear"); return float(a[a<=q].mean())
        es_reps=[es(np.asarray([s1[k]["net_return"] for k in sample]))-es(np.asarray([p0[k]["net_return"] for k in sample])) for sample in samples]; es_ci=interval(es_reps); es_bad=es_ci[1]<0; safety_panel["expected_shortfall"]={"point_estimate":es(np.asarray([s1[k]["net_return"] for k in diffs]))-es(np.asarray([p0[k]["net_return"] for k in diffs])),"ci95":es_ci,"adverse_breach":es_bad,"available":True}; safety_breach|=es_bad; week_art["safety_cis"]={"expected_shortfall":es_ci,"green_to_red":safety_panel["green_to_red"]["ci95"],"preserved_half":safety_panel["preserved_at_least_half_peak"]["ci95"],"winner_cohorts":{k:v["ci95"] for k,v in winner_panel.items()}}
    trunc_counts={str(p):sum(bool(r[f"truncation_{p}"]) for r in evaluation_rows if r["policy_id"]=="S1_FULL_T2_OVERLAY") for p in (2,3,5)}; overlay_count=sum(r["policy_id"]=="S1_FULL_T2_OVERLAY" and r.get("trigger_status")=="T2_REACHING" for r in evaluation_rows)
    winner_report={"thresholds":[2,3,5],"winner_counts":{k:v.get("distinct_trades") for k,v in winner_panel.items()},"winner_deltas":winner_panel,"truncation_counts":trunc_counts,"truncation_rates":{k:v/overlay_count if overlay_count else None for k,v in trunc_counts.items()},"opportunity_foregone":{"valid":sum(r.get("opportunity_foregone") is not None for r in evaluation_rows),"mean":float(np.mean([r["opportunity_foregone"] for r in evaluation_rows if r.get("opportunity_foregone") is not None])) if any(r.get("opportunity_foregone") is not None for r in evaluation_rows) else None},"availability":{k:v.get("available") for k,v in winner_panel.items()}}
    sym_means={s:float(np.mean([diffs[k] for k in diffs if p0[k]["symbol"]==s])) if any(p0[k]["symbol"]==s for k in diffs) else 0. for s in SYMBOLS}; sym_contrib={s:float(sum((s1[k]["net_pnl_usdt"]-p0[k]["net_pnl_usdt"]) for k in diffs if p0[k]["symbol"]==s)) for s in SYMBOLS}; br=breadth(sym_means,point); positive=sum(max(v,0) for v in sym_contrib.values())
    decomp_pnl={g:{p:float(sum(r["net_pnl_usdt"] for r in trades if r["cost_scenario"]=="C_BASE" and r["policy_id"]==p and ((g=="T2_REACHING" and r["trade_id"] in {x["trade_id"] for x in included if x.get("overlay_strictly_before_p0")}) or (g=="P0_FALLBACK" and r["trade_id"] in {x["trade_id"] for x in included if not x.get("overlay_strictly_before_p0")})))) for p in POLICIES} for g in ("T2_REACHING","P0_FALLBACK")}
    decomposition={"all_eligible":n,"t2_reaching":triggers,"fallback":fallback,"counts":{"T2_REACHING":triggers,"P0_FALLBACK":fallback},"percentages":{"T2_REACHING":triggers/n if n else None,"P0_FALLBACK":fallback/n if n else None},"pnl_contributions":decomp_pnl,"reconciliation":{"s1_total":sum(x["S1_FULL_T2_OVERLAY"] for x in decomp_pnl.values()),"p0_total":sum(x["P0_FULL"] for x in decomp_pnl.values()),"paired_improvement":float(sum(diffs.values())*1000),"status":"EXACT"}}
    def scope_report(ids:set[str]):
        scoped=[r for r in included if r["trade_id"] in ids]; st=sum(bool(r.get("overlay_strictly_before_p0")) for r in scoped); evp=eval_panel(ids); base_rows=[r for r in trades if r["trade_id"] in ids and r["cost_scenario"]=="C_BASE"]; scope_eval=[r for r in evaluation_rows if r["trade_id"] in ids]
        t2ids={r["trade_id"] for r in scoped if r.get("overlay_strictly_before_p0")}; scope_pnl={g:{p:sum(r["net_pnl_usdt"] for r in base_rows if r["policy_id"]==p and ((g=="T2_REACHING")==(r["trade_id"] in t2ids))) for p in POLICIES} for g in ("T2_REACHING","P0_FALLBACK")}
        scope_safety={m:{p:{"valid":sum(r.get(m) is not None for r in scope_eval if r["policy_id"]==p),"mean":float(np.mean([float(r[m]) for r in scope_eval if r["policy_id"]==p and r.get(m) is not None])) if any(r["policy_id"]==p and r.get(m) is not None for r in scope_eval) else None} for p in POLICIES} for m in ("green_to_red","preserved_at_least_half_peak","downside_value")}
        scope_winners={str(p):{"winner_count":sum(r["policy_id"]=="P0_FULL" and r[f"p0_winner_{p}"] for r in scope_eval),"truncation_count":sum(r["policy_id"]=="S1_FULL_T2_OVERLAY" and r[f"truncation_{p}"] for r in scope_eval)} for p in (2,3,5)}
        return {"population":len(scoped),"decomposition":{"t2_reaching":st,"fallback":len(scoped)-st,"trigger_rate":st/len(scoped) if scoped else None,"fallback_rate":(len(scoped)-st)/len(scoped) if scoped else None,"pnl_contributions":scope_pnl},"economics":{c:{p:summary([r for r in trades if r["trade_id"] in ids and r["cost_scenario"]==c and r["policy_id"]==p]) for p in POLICIES} for c in COSTS},"costs":list(COSTS),"holding_exposure":{p:{"summed_seconds":sum(r["holding_seconds"] for r in base_rows if r["policy_id"]==p),"union_seconds":_union_seconds([r for r in base_rows if r["policy_id"]==p])} for p in POLICIES},"path_capture":evp,"safety":scope_safety,"winner_truncation":scope_winners}
    report=synthetic_report(); report["canonical_paired_trade_table"]={"columns":list(TRADE_FIELDS),"rows":trades}; report["leg_level_cost_table"]={"columns":list(LEG_FIELDS),"rows":legs}; report["evaluation_only_table"]={"columns":list(EVAL_FIELDS),"rows":evaluation_rows,"forbidden_from_decisions":True}; report["first_t2_audit"]={"rows":audits}; ties=[a["trade_id"] for a in audits if a["precedence_state"]=="P0_PRECEDENCE_TIE_OR_NOT_EARLIER"]; report["p0_precedence_tie_audit"]={"count":len(ties),"trade_ids":ties}; report["fallback_audit"]={"count":fallback,"identity_verified":True,"mismatches":[]}; report["inclusion_exclusion_unresolved_accounting"]={"source_count":len(population),"included_count":n,"excluded_count":len(population)-n,"unresolved_count":0,"reasons":dict(Counter(r.get("primary_reason") for r in population if not r.get("included",True)))}; report["t2_non_t2_decomposition"]=decomposition
    report["denominator_null_ledger"]={"rows":null_rows,"unresolved_count":0,"null_count":len(null_rows)}; report["week_bootstrap_samples_multiplicities_replicates"]=week_art; report["month_bootstrap_sensitivity"]=month_art; report["complete_metrics"]={"pooled":reports,"years":year_metrics,"symbols":symbol_metrics,"equal_weight_symbol":{"symbol_means":sym_means,"mean":br["equal_weight_symbol"]},"costs":list(COSTS),"valid_denominators":{"evaluation_rows":len(evaluation_rows)-len(null_rows)},"null_counts":{"capture_fraction":len(null_rows)}}; report["pooled_trade_weighted_report"]={"population":n,"policies":list(POLICIES),"costs":list(COSTS),"metrics":reports}; report["equal_weight_symbol_report"]={"symbols":list(SYMBOLS),"point_estimate":br["equal_weight_symbol"],"metrics":{"symbol_mean_differences":sym_means}}
    report["safety_report"]={"expected_shortfall":safety_panel.get("expected_shortfall"),"green_to_red":safety_panel.get("green_to_red"),"preserved_half":safety_panel.get("preserved_at_least_half_peak"),"winner_cohorts":winner_panel,"adverse_breach":safety_breach,"mandatory_available":safety_available}; report["winner_truncation_report"]=winner_report; report["breadth_concentration"]={"signed_symbol_contributions":sym_contrib,"positive_shares":{s:max(v,0)/positive if positive else None for s,v in sym_contrib.items()},"equal_weight_point_estimate":br["equal_weight_symbol"],"positive_symbol_count":br["positive_symbols"],"largest_positive_share":br["largest_positive_contribution_share"],"breadth_label":br["label"],"total_negative_contribution":sum(min(v,0) for v in sym_contrib.values()),"reconciled_total":sum(sym_contrib.values())}; report["cost_sensitivities"]={c:{"point_estimate":float(np.mean(list(v.values()))) if v else None,"paired_count":len(v)} for c,v in paired.items()}
    base_s1=[r for r in trades if r["cost_scenario"]=="C_BASE" and r["policy_id"]=="S1_FULL_T2_OVERLAY"]; holds=[r["holding_seconds"] for r in base_s1]; report["summed_union_exposure"]={"mean_holding":float(np.mean(holds)) if holds else None,"median_holding":float(np.median(holds)) if holds else None,"summed_exposure":float(sum(holds)),"union_exposure":_union_seconds(base_s1),"union_unavailable_reason":None}; report["trigger_fallback_rates"]={"trigger_count":triggers,"trigger_rate":triggers/n if n else None,"fallback_count":fallback,"fallback_rate":fallback/n if n else None}; report["executed_legs_notional"]={"leg_count":len(legs),"entry_notional":float(sum(x["executed_notional"] for x in legs if x["leg"]=="ENTRY")),"exit_notional":float(sum(x["executed_notional"] for x in legs if x["leg"]=="EXIT"))}
    available=ci[0] is not None and safety_available; c5=report["cost_sensitivities"]["C_S5"]["point_estimate"] or 0.; label=classify(available=available,point=point,week_ci=ci,c_s5_point=c5,safety_breach=safety_breach,breadth_label=br["label"]); report["final_classification_predicates"]={"evidence_available":available,"primary_point_positive":point>0,"primary_ci_entirely_positive":ci[0] is not None and ci[0]>0,"primary_ci_entirely_negative":ci[1] is not None and ci[1]<0,"safety_breach":safety_breach,"c_s5_positive":c5>0,"breadth_label":br["label"],"precedence_order":["INSUFFICIENT","COUNTS_AGAINST_FULL_POPULATION_T2_OVERLAY","SUPPORTS_FULL_POPULATION_T2_OVERLAY","MIXED"],"final_label":label}; report["human_readable_classification"]={"label":label,"statement":"Frozen Section 17 precedence applied."}
    for y in YEARS: report[f"report_{y}"]={"year":y,**scope_report({r["trade_id"] for r in included if int(r.get("entry_year",dt(r["entry_execution_ts"]).year))==y})}
    for s in SYMBOLS: report[f"report_{s}"]={"symbol":s,**scope_report({r["trade_id"] for r in included if r["symbol"]==s})}
    report["authorization"]={"attempt_id":"INTERNAL_EXECUTOR","authorization_reference":"PRODUCTION_WRAPPER_REQUIRED","started_at":None,"finished_at":None,"lifecycle":[],"economic_read":False,"economic_emission":False,"failure_reason":None,"output_hashes":{"trade_table":semantic_hash(trades),"evaluation_table":semantic_hash(evaluation_rows)}}; report["attempt_ledger"]={"events":[],"terminal_count":1}; report["provenance_hash_manifest"]={"contract_sha256":CONTRACT_SHA256,"source_input_hashes":{},"population_sha256":semantic_hash(included),"code_sha256":None,"config_sha256":None,"environment_sha256":None,"output_schema_sha256":semantic_hash(OUTPUT_SCHEMA),"seed":SEED}
    core={k:v for k,v in report.items() if k not in {"authorization","attempt_ledger","reproducibility_hashes"}}; report["reproducibility_hashes"]={"trade_table":semantic_hash(trades),"evaluation_table":semantic_hash(evaluation_rows),"bootstrap":semantic_hash(week_art),"report_core":semantic_hash(core)}
    validate_report(report); return report

def _freeze_context(repo:Path)->tuple[dict,dict,dict]:
    base=repo/"artifacts/c7_full_population_t2_exit_overlay"; freeze=json.loads((base/"t2_execution_freeze.json").read_text())
    if freeze["contract_sha256"]!=CONTRACT_SHA256 or freeze["seed"]!=SEED: raise RuntimeError("freeze/seed mismatch")
    if file_hash(repo/"contracts/C7_full_population_t2_exit_overlay_CONTRACT.md")!=freeze["contract_sha256"]: raise RuntimeError("contract hash mismatch")
    readiness=json.loads((base/"t1_readiness.json").read_text())
    if file_hash(base/"t1_readiness.json")!=freeze["readiness_sha256"] or readiness.get("decision")!="READY FOR SEPARATE T2 AUTHORIZATION": raise RuntimeError("readiness mismatch")
    for rel,expected in freeze["code_hashes"].items():
        if file_hash(repo/rel)!=expected: raise RuntimeError(f"code hash mismatch: {rel}")
    for name,expected in freeze["config_hashes"].items():
        if file_hash(base/name)!=expected: raise RuntimeError(f"config/schema hash mismatch: {name}")
    schema=json.loads((base/"output_schema.json").read_text());
    if schema!=OUTPUT_SCHEMA: raise RuntimeError("output schema semantic mismatch")
    expected_env=semantic_hash({"python_version":platform.python_version(),"implementation":platform.python_implementation(),"numpy_version":np.__version__})
    recorded_env=json.loads((base/"provenance_manifest.json").read_text()).get("environment_sha256")
    if recorded_env!=expected_env: raise RuntimeError("environment hash mismatch")
    provenance(repo)
    if file_hash(base/"population_manifest.json")!=freeze["population_byte_sha256"]: raise RuntimeError("population hash mismatch")
    pop=json.loads((base/"population_manifest.json").read_text())
    if pop.get("semantic_sha256")!=freeze["population_semantic_sha256"] or pop.get("source_count")!=2199 or pop.get("included_count")!=2199 or pop.get("excluded_count")!=0: raise RuntimeError("population semantic/count mismatch")
    return freeze,pop,schema

def _recorded_frozen_identity(repo:Path)->dict:
    """Read the prospective frozen identity without touching market inputs."""
    base=repo/"artifacts/c7_full_population_t2_exit_overlay"
    freeze=json.loads((base/"t2_execution_freeze.json").read_text())
    allow=json.loads((base/"input_allowlist.json").read_text())
    sources={}
    for item in allow["inputs"]:
        role=next((r for r,(p,_) in INPUTS.items() if p==item["path"]),None)
        if role is None: raise RuntimeError(f"unknown frozen input: {item['path']}")
        sources[role]={"path":item["path"],"role":role,"byte_sha256":item["byte_sha256"],"accepted":True}
    return {"contract_sha256":freeze["contract_sha256"],"readiness_sha256":freeze["readiness_sha256"],"execution_freeze_sha256":file_hash(base/"t2_execution_freeze.json"),"source_hashes":sources,"population_sha256":freeze["population_byte_sha256"],"code_sha256":semantic_hash(freeze["code_hashes"]),"config_sha256":semantic_hash(freeze["config_hashes"]),"environment_sha256":json.loads((base/"provenance_manifest.json").read_text())["environment_sha256"],"output_schema_sha256":freeze["config_hashes"]["output_schema.json"],"seed":freeze["seed"]}

def authoritative_readiness_identity(repo:Path,ledger_path:Path)->dict:
    """Select and verify the latest append-only T1 authority for T2."""
    expected=_recorded_frozen_identity(repo)
    records=[json.loads(x) for x in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
    accepted=[x for x in records if x.get("event")=="READINESS_ACCEPTED" and x.get("stage")=="T1"]
    if not accepted: raise RuntimeError("current authoritative T1 readiness record missing")
    current=accepted[-1]
    if any(current.get(k)!=expected[k] for k in IDENTITY_FIELDS): raise RuntimeError("authoritative T1 readiness identity is stale")
    if current.get("status")!="READINESS_ACCEPTED" or current.get("economic_read") or current.get("economic_emission"): raise RuntimeError("invalid authoritative T1 readiness record")
    return expected

def run_c7_t2_once(*,repo:Path,ledger_path:Path,output_dir:Path,authorization:str)->None:
    """Authorization-gated production API; do not call during T1."""
    if authorization!=AUTHORIZATION: raise PermissionError("explicit C7 T2 authorization required")
    attempt_id=f"C7-T2-{uuid.uuid4()}"; now=lambda:datetime.now(timezone.utc).isoformat()
    try:
        reject_sealed_path(ledger_path); reject_sealed_path(repo); reject_sealed_path(output_dir)
    except Exception as exc:
        # A prohibited ledger path cannot itself be touched; otherwise retain the rejected invocation.
        try:
            reject_sealed_path(ledger_path)
            append_attempt(ledger_path,{"attempt_id":attempt_id,"event":"PREFLIGHT_FAIL","timestamp":now(),"stage":"T2","purpose":"production","authorization_reference":authorization,"contract_sha256":CONTRACT_SHA256,"readiness_sha256":"UNVERIFIED","execution_freeze_sha256":"UNVERIFIED","source_hashes":{},"population_sha256":"UNVERIFIED","code_sha256":"UNVERIFIED","config_sha256":"UNVERIFIED","environment_sha256":"UNVERIFIED","output_schema_sha256":"UNVERIFIED","seed":SEED,"status":"PREFLIGHT_FAIL","failure_reason":f"{type(exc).__name__}: {exc}","economic_read":False,"economic_emission":False,"output_hashes":{}})
        except PermissionError: pass
        raise
    base=repo/"artifacts/c7_full_population_t2_exit_overlay"
    identity={"contract_sha256":CONTRACT_SHA256,"readiness_sha256":"UNVERIFIED","execution_freeze_sha256":"UNVERIFIED","source_hashes":{},"population_sha256":"UNVERIFIED","code_sha256":"UNVERIFIED","config_sha256":"UNVERIFIED","environment_sha256":"UNVERIFIED","output_schema_sha256":"UNVERIFIED","seed":SEED}
    try:
        identity=authoritative_readiness_identity(repo,ledger_path)
        freeze,pop,schema=_freeze_context(repo)
        verified={"contract_sha256":CONTRACT_SHA256,"readiness_sha256":freeze["readiness_sha256"],"execution_freeze_sha256":file_hash(base/"t2_execution_freeze.json"),"source_hashes":provenance(repo),"population_sha256":freeze["population_byte_sha256"],"code_sha256":semantic_hash(freeze["code_hashes"]),"config_sha256":semantic_hash(freeze["config_hashes"]),"environment_sha256":json.loads((base/"provenance_manifest.json").read_text())["environment_sha256"],"output_schema_sha256":freeze["config_hashes"]["output_schema.json"],"seed":SEED}
        if verified!=identity: raise RuntimeError("authoritative T1 readiness identity mismatch")
    except Exception as exc:
        rejected={"attempt_id":attempt_id,"event":"PREFLIGHT_FAIL","timestamp":now(),"stage":"T2","purpose":"production","authorization_reference":authorization,**identity,"status":"PREFLIGHT_FAIL","failure_reason":f"{type(exc).__name__}: {exc}","economic_read":False,"economic_emission":False,"output_hashes":{}}
        append_attempt(ledger_path,rejected)
        raise
    common={"attempt_id":attempt_id,"stage":"T2","purpose":"production","authorization_reference":authorization,**identity,"failure_reason":None,"output_hashes":{}}
    started_at=now(); events=[]
    start_event={**common,"event":"START","status":"START","timestamp":started_at,"economic_read":False,"economic_emission":False}; append_attempt(ledger_path,start_event); events.append(start_event)
    read=False; emitted=False
    try:
        needed={(r["symbol"],r["first_t2_decision_ts"]) for r in pop["rows"] if r.get("overlay_strictly_before_p0")}; opens={}; market={s:{} for s in SYMBOLS}
        for symbol in SYMBOLS:
            scoped=[r for r in pop["rows"] if r["symbol"]==symbol]; lo=min(int(dt(r["entry_execution_ts"]).timestamp()*1000) for r in scoped); hi=max(int(dt(r["p0_execution_ts"]).timestamp()*1000) for r in scoped)
            if not read:
                read_event={**common,"event":"ECONOMIC_READ","status":"ECONOMIC_READ","timestamp":now(),"economic_read":True,"economic_emission":False}; append_attempt(ledger_path,read_event); events.append(read_event); read=True
            with gzip.open(repo/INPUTS[symbol+"_1m"][0],"rt",newline="") as f:
                for row in csv.DictReader(f):
                    ms=int(row["open_time_ms"])
                    if ms<lo: continue
                    if ms>=hi: break
                    if ms in market[symbol]: raise RuntimeError(f"duplicate source minute: {symbol} {ms}")
                    market[symbol][ms]=(float(row["open"]),float(row["high"]),float(row["low"]))
                    ts=datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()
                    if (symbol,ts) in needed: opens[(symbol,ts)]=float(row["open"])
        report=execute_c7(pop["rows"],opens,market_minutes=market)
        emission_event={**common,"event":"ECONOMIC_EMISSION","status":"ECONOMIC_EMISSION","timestamp":now(),"economic_read":True,"economic_emission":True}; append_attempt(ledger_path,emission_event); events.append(emission_event); emitted=True
        section_hashes={f"{name}.json":semantic_hash(obj) for name,obj in report.items() if name not in {"authorization","attempt_ledger"}}
        report["authorization"]={"attempt_id":attempt_id,"authorization_reference":authorization,"started_at":started_at,"finished_at":now(),"lifecycle":["START","ECONOMIC_READ","ECONOMIC_EMISSION","PASS"],"economic_read":True,"economic_emission":True,"failure_reason":None,"output_hashes":section_hashes}
        pass_timestamp=now()
        report["attempt_ledger"]={"events":[{k:e[k] for k in ("attempt_id","event","timestamp","economic_read","economic_emission")} for e in events]+[{"attempt_id":attempt_id,"event":"PASS","timestamp":pass_timestamp,"economic_read":True,"economic_emission":True}],"terminal_count":1}
        report["provenance_hash_manifest"]={**{k:v for k,v in identity.items() if k!="source_hashes"},"source_input_hashes":identity["source_hashes"]}
        core={k:v for k,v in report.items() if k not in {"authorization","attempt_ledger","reproducibility_hashes"}}; report["reproducibility_hashes"]["report_core"]=semantic_hash(core)
        validate_report(report,schema)
        output_dir.parent.mkdir(parents=True,exist_ok=True); temp=Path(tempfile.mkdtemp(prefix="c7-t2-",dir=output_dir.parent)); hashes={}
        try:
            for name,obj in report.items():
                if name=="authorization": continue
                p=temp/f"{name}.json"; p.write_bytes(canonical_bytes(obj)); hashes[p.name]=file_hash(p)
            report["authorization"]["output_hashes"]=dict(hashes)
            p=temp/"authorization.json"; p.write_bytes(canonical_bytes(report["authorization"])); hashes[p.name]=file_hash(p)
            if output_dir.exists(): raise RuntimeError("production output directory already exists")
            temp.rename(output_dir)
        finally:
            if temp.exists(): shutil.rmtree(temp)
        pass_event={**common,"event":"PASS","status":"PASS","timestamp":pass_timestamp,"economic_read":True,"economic_emission":True,"output_hashes":hashes}; append_attempt(ledger_path,pass_event)
    except Exception as exc:
        append_attempt(ledger_path,{**common,"event":"FAIL","status":"FAIL","timestamp":now(),"economic_read":read,"economic_emission":emitted,"failure_reason":f"{type(exc).__name__}: {exc}"})
        raise

def population_rows(repo:Path)->list[dict]:
    """Outcome-blind real structural audit using only explicitly allowed inputs."""
    provenance(repo)
    entries={}
    with (repo/INPUTS["frozen_entries"][0]).open(newline="") as f:
        for r in csv.DictReader(f):
            if r["trade_id"] in entries: raise RuntimeError("duplicate source trade")
            entries[r["trade_id"]]=r
    if len(entries)!=2199: raise RuntimeError("source cohort must contain exactly 2199 trades")
    p0={}
    allowed=("trade_id","symbol","entry_fixture_id","entry_execution_ts","entry_price","p0_version","p0_signal_ts","p0_decision_ts","p0_execution_ts","p0_execution_ms","p0_raw_exit_price","p0_exit_reason","common_horizon_end_ts","common_horizon_end_ms","common_horizon_duration_seconds","censored","censor_reason","data_quality_flag")
    with (repo/INPUTS["common_horizons_p0"][0]).open(newline="") as f:
        for raw in csv.DictReader(f): p0[raw["trade_id"]]={k:raw[k] for k in allowed}
    bysym=defaultdict(list)
    for tid,e in entries.items(): bysym[e["symbol"]].append((tid,e,p0.get(tid)))
    results=[]
    for symbol in SYMBOLS:
        trades=bysym[symbol]; needed={}
        for tid,e,p in trades:
            if p: needed[tid]=(int(e["entry_execution_ms"]),int(p["p0_execution_ms"]))
        lo=min(x[0] for x in needed.values()); hi=max(x[1] for x in needed.values()); mins={}; seen_minutes=set()
        path=repo/INPUTS[symbol+"_1m"][0]
        with gzip.open(path,"rt",newline="") as f:
            for r in csv.DictReader(f):
                ms=int(r["open_time_ms"])
                if ms<lo: continue
                if ms>=hi: break
                if ms in seen_minutes: raise RuntimeError(f"duplicate source minute: {symbol} {ms}")
                seen_minutes.add(ms)
                mins[ms]=(float(r["open"]),float(r["high"]),float(r["low"]),float(r["close"]))
        for tid,e,p in trades:
            flags=[]; primary="INCLUDED"; state=None; overlay=False; tie=False
            if e["entry_fixture_id"]!="E1_H1_SMA24_CROSS_V1" or float(e["entry_notional_usdt"])!=1000: flags.append("SOURCE_IDENTITY_INVALID")
            if symbol not in SYMBOLS or dt(e["entry_execution_ts"]).year not in YEARS: flags.append("SOURCE_SCOPE_INVALID")
            if not p or p["censored"]=="True" or p["data_quality_flag"]!="complete": flags.append("P0_INVALID")
            if not flags:
                a=int(e["entry_execution_ms"]); b=int(p["p0_execution_ms"]); expected=list(range(a,b,60000)); vals=[mins.get(x) for x in expected]
                if any(x is None for x in vals): flags.append("CAUSAL_PATH_GAP")
                elif any(not all(math.isfinite(v) and v>0 for v in x) or x[1]<max(x[0],x[2],x[3]) or x[2]>min(x[0],x[1],x[3]) for x in vals): flags.append("INVALID_OHLC")
                else:
                    pathrows=[Minute(datetime.fromtimestamp(ms/1000,timezone.utc),*mins[ms]) for ms in expected]
                    state=first_t2(dt(e["entry_execution_ts"]),float(e["entry_price"]),dt(p["p0_execution_ts"]),pathrows)
                    if state:
                        if state.decision_ts<dt(p["p0_execution_ts"]):
                            v=mins.get(int(state.decision_ts.timestamp()*1000))
                            if v is None: flags.append("MISSING_IMMEDIATE_NEXT_1M_OPEN")
                            else: overlay=True
                        else: tie=True
            if flags: primary=flags[0]
            results.append({"trade_id":tid,"symbol":symbol,"entry_year":dt(e["entry_execution_ts"]).year,"entry_signal_ts":e["entry_signal_ts"],"entry_decision_ts":e["entry_decision_ts"],"entry_execution_ts":e["entry_execution_ts"],"entry_price":e["entry_price"],"entry_notional_usdt":"1000","p0_version":p["p0_version"] if p else None,"p0_execution_ts":p["p0_execution_ts"] if p else None,"p0_raw_exit_price":p["p0_raw_exit_price"] if p else None,"common_horizon_end_ts":p["common_horizon_end_ts"] if p else None,"included":not flags,"reason_flags":flags,"primary_reason":primary,"causal_path_complete":not any(x in flags for x in ("CAUSAL_PATH_GAP","INVALID_OHLC")),"first_t2_decision_ts":state.decision_ts.isoformat() if state else None,"overlay_strictly_before_p0":overlay,"p0_precedence_tie":tie,"prediction_fields_consulted":False})
    return sorted(results,key=lambda x:(x["entry_execution_ts"],x["symbol"],x["trade_id"]))
