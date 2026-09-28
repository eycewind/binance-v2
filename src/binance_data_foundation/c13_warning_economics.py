"""C13 governed, one-shot post-T2 warning economics."""
from __future__ import annotations

import csv, gzip, hashlib, json, math, os, platform, shutil, sys, tempfile, uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from . import c7_t1 as c7
from . import c10_post_t2 as c10
from . import c12_post_t2_warning as c12

SEED, REPLICATES = 20261013, 2000
SYMBOLS = c7.SYMBOLS
COSTS = c7.COSTS
POLICIES = ("P0", "W1", "D2_CONTROL")
AUTHORIZATION = "AUTHORIZE_C13_ONE_SHOT"
CONTRACT_REL = "contracts/C13_post_t2_warning_economics_CONTRACT.md"
OUTPUT_REL = "artifacts/c13_post_t2_warning_economics"
MINUTE = 60_000

def reject_2026(path: str | Path) -> None:
    raw=os.fspath(path).replace("\\","/").lower()
    if any("2026" in x for x in raw.split("/") if x):
        raise PermissionError("C13 prohibits 2026 data or metadata paths")

def file_hash(path: Path) -> str:
    reject_2026(path); h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def semantic_hash(value) -> str:
    return hashlib.sha256((json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()).hexdigest()

def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n")

def first_p3(probabilities: Sequence[float]) -> int | None:
    run=0
    for i,p in enumerate(probabilities):
        run=run+1 if float(p)<.20 else 0
        if run==3:return i
    return None

def causal_exit(decision_ms:int|None,p0_ms:int,market, *, require_prior_ms:int|None=None) -> dict:
    if decision_ms is None:return {"triggered":False,"execution_ms":p0_ms,"reason":"NO_TRIGGER"}
    if decision_ms>=p0_ms:return {"triggered":False,"execution_ms":p0_ms,"reason":"P0_TIE_OR_PRECEDENCE"}
    i=market.index(decision_ms)
    if i is None:return {"triggered":False,"execution_ms":p0_ms,"reason":"MISSING_NEXT_OPEN"}
    if require_prior_ms is not None and (decision_ms-require_prior_ms)!=MINUTE:
        return {"triggered":False,"execution_ms":p0_ms,"reason":"DISCONTINUOUS_DECISION_PATH"}
    price=float(market.open[i])
    if not math.isfinite(price) or price<=0:return {"triggered":False,"execution_ms":p0_ms,"reason":"INVALID_NEXT_OPEN"}
    return {"triggered":True,"execution_ms":decision_ms,"exit_price":price,"reason":"TRIGGER"}

def w1_choice(panel:dict|None,p0_ms:int,market) -> dict:
    if panel is None:return {"triggered":False,"execution_ms":p0_ms,"reason":"UNAVAILABLE_PROBABILITY"}
    i=first_p3(panel["p"])
    if i is None:return {"triggered":False,"execution_ms":p0_ms,"reason":"NO_W1_TRIGGER"}
    rows=panel["rows"]
    if i<2 or rows[i-2]["state_ms"]+MINUTE!=rows[i-1]["state_ms"] or rows[i-1]["state_ms"]+MINUTE!=rows[i]["state_ms"]:
        return {"triggered":False,"execution_ms":p0_ms,"reason":"DISCONTINUOUS_P3"}
    out=causal_exit(int(rows[i]["state_ms"]),p0_ms,market,require_prior_ms=int(rows[i-1]["state_ms"]))
    out.update({"detection_index":i,"decision_ms":int(rows[i]["state_ms"]),"p3":[float(x) for x in panel["p"][i-2:i+1]]})
    return out

def d2_choice(trade:dict,p0_ms:int,market) -> dict:
    i=market.index(trade["t0_ms"])
    if i is None:return {"triggered":False,"execution_ms":p0_ms,"reason":"MISSING_POST_T2"}
    prev=trade["t0_ms"]
    while i<len(market.ms) and int(market.ms[i])+MINUTE<=p0_ms:
        ms=int(market.ms[i])
        if ms!=prev:return {"triggered":False,"execution_ms":p0_ms,"reason":"GAP_FAIL_CLOSED"}
        if float(market.low[i])<=float(trade["deterioration_level"]):
            return causal_exit(ms+MINUTE,p0_ms,market,require_prior_ms=ms)
        prev=ms+MINUTE;i+=1
    return {"triggered":False,"execution_ms":p0_ms,"reason":"NO_D2_TOUCH"}

def bootstrap(ids:Sequence[str],entry_iso:Mapping[str,str],contrasts:Mapping[str,Mapping[str,float]]) -> dict:
    samples=c7.moving_block_samples({k:entry_iso[k] for k in ids},seed=SEED,replicates=REPLICATES)
    out={}
    for name,diffs in contrasts.items():
        reps=[float(np.mean([diffs[k] for k in sample])) for sample in samples]
        out[name]={"point":float(np.mean([diffs[k] for k in ids])),"ci95":c7.interval(reps)}
    return {"method":"four-entry-week moving-block bootstrap","block_length_weeks":4,"seed":SEED,"replicates":REPLICATES,"contrasts":out,"samples_sha256":semantic_hash(samples)}

def _summary(rows):
    a=np.asarray([r["net_return"] for r in rows],float); raw=np.asarray([r["raw_return"] for r in rows],float)
    return {"count":len(rows),"mean_net_return":float(a.mean()) if len(a) else None,"total_net_pnl_usdt":float(a.sum()*1000),"mean_raw_return":float(raw.mean()) if len(raw) else None,"worst_net_return":float(a.min()) if len(a) else None}

def _difference(rows, a, b):
    by={(r["trade_id"],r["policy"],r["cost"]):r for r in rows}
    return {tid:by[(tid,a,"C_BASE")]["net_return"]-by[(tid,b,"C_BASE")]["net_return"] for tid in sorted({r["trade_id"] for r in rows})}

def execute(population, data, markets) -> dict:
    pop_by={r["trade_id"]:r for r in population}; t2_by={t["trade_id"]:t for t in data["trades"]}
    panels=c12.trade_panels(data["scored_rows"],data["probabilities"]); physical={r["trade_id"] for r in data["binary_rows"]}; scored=set(panels)
    table=[]; diagnostics=[]; choices={}
    for tid,src in pop_by.items():
        p0_ms=int(datetime.fromisoformat(src["p0_execution_ts"]).timestamp()*1000); market=markets[src["symbol"]]
        p0={"triggered":False,"execution_ms":p0_ms,"exit_price":float(src["p0_raw_exit_price"]),"reason":"CANONICAL_P0"}
        tr=t2_by.get(tid)
        if tr is None:w={**p0,"reason":"NO_T2"};d={**p0,"reason":"NO_T2"};category="NO_T2"
        else:
            w=w1_choice(panels.get(tid),p0_ms,market); d=d2_choice(tr,p0_ms,market)
            if not w["triggered"]:w["exit_price"]=p0["exit_price"]
            if not d["triggered"]:d["exit_price"]=p0["exit_price"]
            if tr["terminal"]=="P0_FIRST" and tid not in scored:category="P0_FIRST_EDGE"
            elif tid not in physical:category="ZERO_ROW_RAPID_TRANSITION"
            elif tid not in scored:category="TRAINING_ONLY_UNAVAILABLE"
            elif w["triggered"]:category="HONEST_SCORED_W1_TRIGGER"
            else:category="HONEST_SCORED_NO_TRIGGER"
            if w["triggered"]:
                ix=w["detection_index"]; row=panels[tid]["rows"][ix]; pi=market.index(w["decision_ms"]-MINUTE)
                later=np.asarray(panels[tid]["p"][ix+1:])
                end=market.index(p0_ms-MINUTE); subsequent=float(np.max(market.high[pi+1:end+1])/float(src["entry_price"])-1) if pi is not None and end is not None and end>pi else None
                diagnostics.append({"trade_id":tid,"outcome":tr["terminal"],"minutes_after_t2":(w["decision_ms"]-tr["t0_ms"])/MINUTE,"lead_minutes_to_c10_event":(tr["terminal_ms"]-w["decision_ms"])/MINUTE,"p3":w["p3"],"price_return_at_trigger":float(market.close[pi])/float(src["entry_price"])-1,"subsequent_mfe_original_path":subsequent,"recovered_ge_0.60":bool(np.any(later>=.60)),"recovered_ge_0.80":bool(np.any(later>=.80))})
        choices[tid]={"category":category,"outcome":tr["terminal"] if tr else "NO_T2","W1":w,"D2_CONTROL":d,"P0":p0}
        for policy,ch in (("P0",p0),("W1",w),("D2_CONTROL",d)):
            exit_ms=int(ch["execution_ms"]); exit_price=float(ch["exit_price"])
            for cost in COSTS:
                ledger=c7.cost_ledger(float(src["entry_price"]),exit_price,cost)
                table.append({"trade_id":tid,"symbol":src["symbol"],"year":int(src["entry_year"]),"entry_execution_ts":src["entry_execution_ts"],"entry_price":float(src["entry_price"]),"p0_execution_ts":src["p0_execution_ts"],"policy":policy,"cost":cost,"availability_category":category,"outcome":choices[tid]["outcome"],"triggered":bool(ch["triggered"]),"trigger_reason":ch["reason"],"execution_ms":exit_ms,"exit_price":exit_price,"raw_return":ledger["raw_return"],"net_return":ledger["net_return"],"net_pnl_usdt":ledger["net_return"]*1000,"holding_seconds":exit_ms-int(datetime.fromisoformat(src["entry_execution_ts"]).timestamp()*1000)})
    ids=sorted(pop_by); entry_iso={x:pop_by[x]["entry_execution_ts"] for x in ids}
    diffs={"W1-P0":_difference(table,"W1","P0"),"D2_CONTROL-P0":_difference(table,"D2_CONTROL","P0"),"W1-D2_CONTROL":_difference(table,"W1","D2_CONTROL")}
    boot=bootstrap(ids,entry_iso,diffs)
    base=[r for r in table if r["cost"]=="C_BASE"]
    availability={}
    for cat in ("NO_T2","ZERO_ROW_RAPID_TRANSITION","TRAINING_ONLY_UNAVAILABLE","P0_FIRST_EDGE","HONEST_SCORED_NO_TRIGGER","HONEST_SCORED_W1_TRIGGER"):
        cc=[x for x in ids if choices[x]["category"]==cat]; availability[cat]={"count":len(cc),"w1_p0_mean":float(np.mean([diffs["W1-P0"][x] for x in cc])) if cc else None,"exact_zero":all(diffs["W1-P0"][x]==0 for x in cc)}
    def group_report(selected):
        ss=set(selected); vals=[diffs["W1-P0"][x] for x in ss]
        return {"count":len(ss),"w1_p0_mean":float(np.mean(vals)) if vals else None,"w1_p0_total_pnl":float(sum(vals)*1000)}
    decomposition={"all":group_report(ids),"t2":group_report(t2_by),"no_t2":group_report(set(ids)-set(t2_by)),"honest_oot_scored":group_report(scored),"w1_triggered":group_report(x for x in ids if choices[x]["W1"]["triggered"]),"honest_scored_no_trigger":group_report(scored-{x for x in ids if choices[x]["W1"]["triggered"]}),"zero_row":group_report(set(t2_by)-physical),"training_only_unavailable":group_report(physical-scored-{x for x in t2_by if t2_by[x]["terminal"]=="P0_FIRST"}),"continuation_first":group_report(x for x,t in t2_by.items() if t["terminal"]=="CONTINUATION_FIRST"),"deterioration_first":group_report(x for x,t in t2_by.items() if t["terminal"]=="DETERIORATION_FIRST"),"p0_first":group_report(x for x,t in t2_by.items() if t["terminal"]=="P0_FIRST")}
    sensitivities={}
    for cost in COSTS:
        rr=[r for r in table if r["cost"]==cost]; by={(x["trade_id"],x["policy"]):x for x in rr}
        sensitivities[cost]={p:{"mean_net_return":float(np.mean([by[(x,p)]["net_return"] for x in ids])),"total_net_pnl_usdt":float(sum(by[(x,p)]["net_pnl_usdt"] for x in ids))} for p in POLICIES}
        sensitivities[cost]["W1-P0"]={"mean":float(np.mean([by[(x,"W1")]["net_return"]-by[(x,"P0")]["net_return"] for x in ids]))}
    p0raw={r["trade_id"]:r["raw_return"] for r in table if r["policy"]=="P0" and r["cost"]=="C0"}
    winners={}
    samples=c7.moving_block_samples(entry_iso,seed=SEED,replicates=REPLICATES)
    for threshold in (.02,.03,.05):
        cohort={x for x in ids if p0raw[x]>=threshold}; reps=[float(np.mean([diffs["W1-P0"][x] for x in s if x in cohort])) for s in samples]
        truncated=[x for x in cohort if choices[x]["W1"]["triggered"] and choices[x]["W1"]["execution_ms"]<int(datetime.fromisoformat(pop_by[x]["p0_execution_ts"]).timestamp()*1000)]
        winners[str(threshold)]={"count":len(cohort),"mean_paired_difference":float(np.mean([diffs["W1-P0"][x] for x in cohort])),"ci95":c7.interval(reps),"fraction_truncated":len(truncated)/len(cohort),"opportunity_foregone_mean":float(np.mean([max(0.,p0raw[x]-(next(r for r in table if r["trade_id"]==x and r["policy"]=="W1" and r["cost"]=="C0")["raw_return"])) for x in cohort]))}
    # Path/capture safety, evaluated on the original causal minute path.
    safety_rows=[]
    for tid in ids:
        src=pop_by[tid]; m=markets[src["symbol"]]; entry=float(src["entry_price"]); start=int(datetime.fromisoformat(src["entry_execution_ts"]).timestamp()*1000); p0=int(datetime.fromisoformat(src["p0_execution_ts"]).timestamp()*1000); wi=choices[tid]["W1"]["execution_ms"]
        i0=m.index(start); ip=m.index(p0-MINUTE); iw=m.index(wi-MINUTE)
        common=max(entry,float(np.max(m.high[i0:ip+1])))/entry-1; held=max(entry,float(np.max(m.high[i0:iw+1])))/entry-1; wr=next(r for r in table if r["trade_id"]==tid and r["policy"]=="W1" and r["cost"]=="C0")["raw_return"]
        safety_rows.append({"trade_id":tid,"common_mfe":common,"held_mfe":held,"realized_capture":wr,"capture_fraction":wr/common if common>0 else None,"held_peak_surrender":held-wr,"green_to_red":held>0 and wr<0,"preserved_half_peak":wr>=.5*held if held>0 else True})
    wbase=[r for r in base if r["policy"]=="W1"]; net=np.asarray([r["net_return"] for r in wbase]); q=np.quantile(net,.1)
    safety={"common_path_mfe_mean":float(np.mean([r["common_mfe"] for r in safety_rows])),"realized_capture_mean":float(np.mean([r["realized_capture"] for r in safety_rows])),"held_peak_surrender_mean":float(np.mean([r["held_peak_surrender"] for r in safety_rows])),"green_to_red_count":sum(r["green_to_red"] for r in safety_rows),"preserved_half_peak_rate":float(np.mean([r["preserved_half_peak"] for r in safety_rows])),"expected_shortfall_lower_10pct":float(net[net<=q].mean()),"worst_trade":float(net.min())}
    years={str(y):group_report(x for x in ids if int(pop_by[x]["entry_year"])==y) for y in (2024,2025)}
    symbols={s:group_report(x for x in ids if pop_by[x]["symbol"]==s) for s in SYMBOLS}; points={s:symbols[s]["w1_p0_mean"] for s in SYMBOLS}; broad=c7.breadth(points,boot["contrasts"]["W1-P0"]["point"]); broad["label"]={"BROAD":"BROAD_POSITIVE","CONCENTRATED":"CONCENTRATED_POSITIVE","NO_POSITIVE_POOLED_BREADTH":"NO_POSITIVE"}[broad["label"]]
    triggered=[x for x in ids if choices[x]["W1"]["triggered"]]; d2tr=[x for x in ids if choices[x]["D2_CONTROL"]["triggered"]]
    holds={p:[r["holding_seconds"] for r in base if r["policy"]==p] for p in POLICIES}
    exposure={p:{"mean_holding_seconds":float(np.mean(v)),"summed_exposure_seconds":float(sum(v)),"union_exposure_seconds":None,"union_note":"single-position union not defined by frozen source; summed exposure reported"} for p,v in holds.items()}
    primary=boot["contrasts"]["W1-P0"]; mandatory_breach=any(v["ci95"][1]<0 for v in winners.values())
    available=(len(ids)==2199 and len(t2_by)==845 and len(scored)==608 and all(len(v["ci95"])==2 for v in boot["contrasts"].values()))
    if not available:label="INSUFFICIENT"
    elif primary["point"]<=0 or primary["ci95"][1]<0 or sensitivities["C_S5"]["W1-P0"]["mean"]<=0 or mandatory_breach:label="COUNTS AGAINST CONSERVATIVE PROBABILITY EXIT"
    elif primary["ci95"][0]>0 and broad["label"]=="BROAD_POSITIVE":label="SUPPORTS CONSERVATIVE PROBABILITY EXIT"
    else:label="MIXED"
    return {"table":table,"choices":choices,"diagnostics":diagnostics,"bootstrap":boot,"availability":availability,"decomposition":decomposition,"sensitivities":sensitivities,"winners":winners,"safety":safety,"safety_rows":safety_rows,"years":years,"symbols":symbols,"breadth":broad,"exposure":exposure,"trigger_counts":{"W1":len(triggered),"D2_CONTROL":len(d2tr)},"classification":{"label":label,"predicates":{"evidence_available":available,"primary_point_positive":primary["point"]>0,"primary_ci_entirely_positive":primary["ci95"][0]>0,"primary_ci_entirely_negative":primary["ci95"][1]<0,"C_S5_positive":sensitivities["C_S5"]["W1-P0"]["mean"]>0,"mandatory_safety_breach":mandatory_breach,"breadth":broad["label"]}}}

def source_hashes(repo:Path) -> dict:
    paths=[repo/CONTRACT_REL,repo/"src/binance_data_foundation/c13_warning_economics.py",repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json",repo/"artifacts/c12_post_t2_warning_leadtime/c11_probability_reproduction.json",repo/"artifacts/c12_post_t2_warning_leadtime/population_reconciliation.json",repo/"src/binance_data_foundation/c12_post_t2_warning.py",repo/"src/binance_data_foundation/c11_dynamic_post_t2.py",repo/"src/binance_data_foundation/c10_post_t2.py"]
    paths += [repo/c7.INPUTS[s+"_1m"][0] for s in SYMBOLS]
    return {str(p.relative_to(repo)):file_hash(p) for p in paths}

def preflight(repo:Path) -> dict:
    reject_2026(repo); pop=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())
    rows=pop["rows"]
    if len(rows)!=2199 or Counter(int(x["entry_year"]) for x in rows)!={2024:1093,2025:1106}:raise RuntimeError("population mismatch")
    if sum(bool(x["overlay_strictly_before_p0"]) for x in rows)!=845:raise RuntimeError("T2 mismatch")
    old=json.loads((repo/"artifacts/c12_post_t2_warning_leadtime/population_reconciliation.json").read_text())
    required={"source_first_t2_trades":845,"primary_binary_trades":843,"physical_row_trades":792,"physical_zero_row_trades":51,"frozen_out_of_time_scored_trades":608}
    if any(old.get(k)!=v for k,v in required.items()):raise RuntimeError("C12 availability mismatch")
    hashes=source_hashes(repo)
    return {"status":"READY","contract_sha256":hashes[CONTRACT_REL],"source_hashes":hashes,"population_sha256":semantic_hash(rows),"probability_provenance_sha256":hashes["artifacts/c12_post_t2_warning_leadtime/c11_probability_reproduction.json"],"code_sha256":hashes["src/binance_data_foundation/c13_warning_economics.py"],"config_sha256":semantic_hash({"policies":POLICIES,"costs":COSTS,"seed":SEED,"replicates":REPLICATES}),"environment_sha256":semantic_hash({"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda":"binance-v2-research"}),"output_schema_sha256":semantic_hash(sorted(("run_manifest","provenance","source_population_reconciliation","prediction_availability","policy_registry","execution_rules","cost_config","bootstrap_config","readiness_freeze","canonical_paired_trade_table","pooled_report","t2_non_t2_decomposition","prediction_availability_decomposition","w1_trigger_diagnostics","d2_control_report","year_reports","symbol_reports","equal_weight_symbol_report","breadth_report","cost_sensitivities","safety_report","winner_truncation_report","holding_exposure_report","classification_predicates","final_classification","reproducibility_hashes","final_summary"))),"seed":SEED,"replicates":REPLICATES,"economic_read":False}

def run_once(repo:Path,authorization:str) -> dict:
    if authorization!=AUTHORIZATION:raise PermissionError("explicit C13 authorization required")
    out=repo/OUTPUT_REL; ledger=out/"attempt_ledger.jsonl"
    if ledger.exists() and any(json.loads(x).get("economic_read") for x in ledger.read_text().splitlines() if x.strip()):raise RuntimeError("C13 one-shot already consumed")
    ready=preflight(repo); attempt=f"C13-{uuid.uuid4()}"; now=lambda:datetime.now(timezone.utc).isoformat()
    out.mkdir(parents=True,exist_ok=True); write_json(out/"readiness_freeze.json",ready)
    with ledger.open("a") as f:f.write(json.dumps({"attempt_id":attempt,"event":"START","timestamp":now(),"economic_read":False})+"\n")
    try:
        with ledger.open("a") as f:f.write(json.dumps({"attempt_id":attempt,"event":"ECONOMIC_READ","timestamp":now(),"economic_read":True})+"\n")
        data=c12.generate_frozen_panel(repo)
        reproduction=c12.reproduce_c11(repo,data)
        if reproduction["status"]!="PASS":raise RuntimeError("C11 reproduction failed")
        pop=json.loads((repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json").read_text())["rows"]
        markets={s:c10.load_market(repo/c7.INPUTS[s+"_1m"][0]) for s in SYMBOLS}
        result=execute(pop,data,markets)
        docs={
          "run_manifest":{"version":"C13_RUN_V1","attempt_id":attempt,"status":"PASS","one_shot":True,"contract_sha256":ready["contract_sha256"]},
          "provenance":ready,"source_population_reconciliation":{"total":len(pop),"by_year":dict(Counter(str(x["entry_year"]) for x in pop)),"t2":len(data["trades"]),"no_t2":len(pop)-len(data["trades"]),"outcomes":dict(Counter(x["terminal"] for x in data["trades"]))},
          "prediction_availability":c12.population(data["trades"],data["binary_rows"],data["scored_rows"]),
          "policy_registry":{"P0":"canonical unchanged","W1":{"threshold":"strictly <0.20","persistence":3},"D2_CONTROL":"frozen midpoint boundary"},
          "execution_rules":{"completed_information_only":True,"execution":"immediate next 1m open","P0_wins_ties":True,"gaps":"fail closed"},"cost_config":COSTS,"bootstrap_config":{"seed":SEED,"replicates":REPLICATES,"block_weeks":4},
          "canonical_paired_trade_table":{"rows":result["table"]},"pooled_report":{"bootstrap":result["bootstrap"],"C_BASE":result["sensitivities"]["C_BASE"]},"t2_non_t2_decomposition":result["decomposition"],"prediction_availability_decomposition":result["availability"],"w1_trigger_diagnostics":{"rows":result["diagnostics"]},"d2_control_report":{"trigger_count":result["trigger_counts"]["D2_CONTROL"],"contrast":result["bootstrap"]["contrasts"]["D2_CONTROL-P0"]},"year_reports":result["years"],"symbol_reports":result["symbols"],"equal_weight_symbol_report":{"W1-P0":result["breadth"]["equal_weight_symbol"]},"breadth_report":result["breadth"],"cost_sensitivities":result["sensitivities"],"safety_report":result["safety"],"winner_truncation_report":result["winners"],"holding_exposure_report":result["exposure"],"classification_predicates":result["classification"]["predicates"],"final_classification":{"label":result["classification"]["label"]}}
        docs["final_summary"]={"attempt_id":attempt,"status":"PASS","contract_sha256":ready["contract_sha256"],"population":docs["source_population_reconciliation"],"availability":docs["prediction_availability"],"trigger_counts":result["trigger_counts"],"economics":docs["pooled_report"],"decomposition":result["decomposition"],"safety":result["safety"],"winners":result["winners"],"years":result["years"],"symbols":result["symbols"],"breadth":result["breadth"],"classification":result["classification"],"confirmations":{"real_economic_runs":1,"rerun":False,"threshold_model_timeframe_search":False,"c7_c12_scientific_modification":False,"accessed_2026":False,"c14_started":False}}
        temp=Path(tempfile.mkdtemp(prefix="c13-",dir=out)); hashes={}
        try:
            for name,obj in docs.items():write_json(temp/f"{name}.json",obj);hashes[f"{name}.json"]=file_hash(temp/f"{name}.json")
            write_json(temp/"reproducibility_hashes.json",hashes)
            for p in temp.iterdir():shutil.move(str(p),out/p.name)
        finally:shutil.rmtree(temp)
        with ledger.open("a") as f:f.write(json.dumps({"attempt_id":attempt,"event":"PASS","timestamp":now(),"economic_read":True,"output_hashes":hashes})+"\n")
        return docs["final_summary"]
    except Exception as exc:
        with ledger.open("a") as f:f.write(json.dumps({"attempt_id":attempt,"event":"FAIL","timestamp":now(),"economic_read":True,"failure":f"{type(exc).__name__}: {exc}"})+"\n")
        raise
