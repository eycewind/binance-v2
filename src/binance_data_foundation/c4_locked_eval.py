from __future__ import annotations

import csv, hashlib, json, math, os, shutil, sys, tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

BOUNDARY_2025_MS=1735689600000; BOUNDARY_2026_MS=1767225600000
TARGETS=("T1","T2"); MODELS=("B0","G0","G1","P1"); COMPARISONS=(("G1","G0"),("P1","G1"))
CLASS_ORDER={"T1":["continuation","adverse_reversal","no_event_60m"],"T2":["renewed_peak","substantial_giveback","no_event_60m"]}
OUTPUT_FILES=("evaluation_manifest.json","population_summary.json","predictions.csv","primary_metrics.json","secondary_metrics.json","bootstrap_comparisons.json","calibration.json","stability.json","interpretation.json","reproducibility.json")

def locked_evaluation_config(calibration_2024):
    cuts={t:{c:calibration_2024[f"{t}_fold_B"][c]["training_cut_points"] for c in calibration_2024[f"{t}_fold_B"]} for t in TARGETS}
    return {"version":"C4_LOCKED_2025_EVALUATION_V1","official_operation":"all_targets_all_models_one_shot",
      "authorized_entry_range_ms":[BOUNDARY_2025_MS,BOUNDARY_2026_MS],"authorized_snapshot_range_ms":[BOUNDARY_2025_MS,BOUNDARY_2026_MS],
      "targets":list(TARGETS),"models":list(MODELS),"population":{"target_eligible":True,"resolved":True,"censored":False,"ambiguous":False,"complete_case":"all frozen P1 columns finite","weighting":"each represented trade has total raw weight one","subgroups":["symbol","snapshot_month_utc","snapshot_quarter_utc"],"unknown_symbols":"reject"},
      "primary_metrics":["equal_trade_multiclass_log_loss","equal_trade_multiclass_brier"],
      "secondary_metrics":["weighted_one_vs_rest_roc_auc","weighted_one_vs_rest_average_precision","macro_roc_auc","macro_average_precision","ranked_probability_score","snapshot_weighted_log_loss","snapshot_weighted_brier","snapshot_weighted_ranked_probability_score","class_incidence","top_class_confusion_counts"],
      "comparisons":["G1-G0","P1-G1"],"bootstrap":{"generator":"PCG64","seed":20240923,"replicates":2000,"block_length_entry_weeks":4,"blocks":"overlapping_non_circular","draws":"ceil(W/4)_with_replacement","empty_block_policy":"reject_and_redraw","attachment":"whole_trade","multiplicity":"preserved_no_deduplication","quantile_method":"linear","hyndman_fan_type":7,"interval_levels":[.025,.975],"sign_convention":"first_minus_second"},
      "calibration":{"models":["P1"],"classes":"all","post_hoc_calibrator":"PROHIBITED","diagnostic_intercept_slope":"reported as an evaluation statistic and never applied to probabilities","bin_source":"frozen_2024_fold_B_training_prediction_weighted_quintiles","cut_points":cuts,"duplicate_cut_points":"reduce_bin_count","reliability_minimum_unique_resolved_trades":30,"unstable_below_unique_event_trades":10,"intercept_slope_minimum_unique_event_trades":50},
      "stability":{"models":["G1","P1"],"comparison":"P1-G1","groups":["symbol","month","quarter"],"weighting":"equal_trade"},
      "interpretation":{"decisive_comparison":"P1-G1","geometry_comparison":"G1-G0 only","categories":["SUPPORTS SEQUENTIAL PATH-STATE SIGNAL","COUNTS AGAINST","MIXED","INSUFFICIENT EVIDENCE"],"support":"both proper-score deltas below zero, both 95% interval upper bounds below zero, both 2024 folds improve, and stability is not single-group dominated","counts_against":"both proper-score deltas above zero and both 95% interval lower bounds above zero","insufficient":"bootstrap unavailable, calibration support materially inadequate, or engineering/provenance validation fails","otherwise":"MIXED","secondary_override":"PROHIBITED"},
      "input_schema":{"required_metadata":["row_id","trade_id","target","trade_entry_week","entry_execution_ms","snapshot_ms","symbol","target_eligible","resolved","censored","ambiguous","event_class"],"predictive_container":"features","feature_columns":"exact frozen P1 superset per target","boundary_validation":"metadata before feature or outcome consumption"},
      "outputs":{"directory":"artifacts/c4_sequential_exit_state/locked_2025","required_files":list(OUTPUT_FILES),"partial_output":"PROHIBITED","required_prediction_models":[f"{t}_{m}" for t in TARGETS for m in MODELS],"required_fields":{"evaluation_manifest.json":["version","freeze_sha256","configuration_sha256","input_sha256","required_files","targets","models"],"population_summary.json":["rows","trades","row_ids_sha256"],"predictions.csv":["row_id","trade_id","target","model","class probabilities"],"primary_metrics.json":["log_loss","brier"],"secondary_metrics.json":["classwise_one_vs_rest","macro_roc_auc","macro_average_precision","equal_trade_ranked_probability_score","snapshot_weighted","top_class_confusion_counts"],"bootstrap_comparisons.json":["point_estimate","ci95","replicates","sampled_block_indices","sign_convention"],"calibration.json":["training_cut_points","bins","calibration_intercept_slope","post_hoc_recalibration"],"stability.json":["symbol","month","quarter"],"interpretation.json":["decision","decisive_comparison","G1-G0_role"],"reproducibility.json":["freeze_sha256","input_sha256","output_hashes","refit","reselection","recalibration","2026_access"]}}}

def _sha(path):
    d=hashlib.sha256()
    with Path(path).open("rb") as h:
        for chunk in iter(lambda:h.read(1024*1024),b""): d.update(chunk)
    return d.hexdigest()
def _sem(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

@dataclass(frozen=True)
class LockedCheckpoint:
    freeze_hash:str; freeze:dict; schema:dict; preprocessing:dict; models:dict; config:dict

def load_locked_checkpoint(repo,artifact,lock_path=None):
    repo=Path(repo); artifact=Path(artifact); fp=artifact/"c4_2024_freeze.json"; lp=Path(lock_path) if lock_path else artifact/"c4_2024_freeze.sha256"
    if not fp.is_file() or not lp.is_file(): raise RuntimeError("missing frozen checkpoint or external freeze lock")
    fields=lp.read_text().strip().split()
    if len(fields)!=2 or fields[1]!="c4_2024_freeze.json": raise RuntimeError("invalid external freeze lock format")
    actual=_sha(fp)
    if fields[0]!=actual: raise RuntimeError("freeze hash mismatch")
    freeze=json.loads(fp.read_text())
    if freeze.get("version")!="C4_2024_FREEZE_V3": raise RuntimeError("unsupported freeze version")
    if freeze.get("seals")!={"2025_predictive_scoring":"NOT PERFORMED","2026_access":False,"economic_or_stage_B_analysis":False}: raise RuntimeError("invalid checkpoint seals")
    if set(freeze.get("required_acceptance_artifacts",()))!=set(freeze.get("material_artifact_hashes",())): raise RuntimeError("incomplete top-level artifact graph")
    for name,digest in freeze["material_artifact_hashes"].items():
        p=artifact/name
        if not p.is_file() or _sha(p)!=digest: raise RuntimeError(f"material artifact mismatch: {name}")
    if set(freeze.get("required_source_dependencies",()))!=set(freeze.get("source_test_hashes",())): raise RuntimeError("incomplete source provenance graph")
    for name,digest in freeze["source_test_hashes"].items():
        p=repo/name
        if not p.is_file() or _sha(p)!=digest: raise RuntimeError(f"source provenance mismatch: {name}")
    env=freeze["environment"]
    if os.environ.get("PYTHONPATH") is not None or os.environ.get("CONDA_DEFAULT_ENV")!=env["conda_env"] or sys.version.split()[0]!=env["python_version"] or np.__version__!=env["numpy_version"]: raise RuntimeError("environment provenance mismatch")
    schema=json.loads((artifact/"feature_schema.json").read_text()); prep=json.loads((artifact/"final_preprocessing_2024.json").read_text()); models=json.loads((artifact/"final_models_2024.json").read_text()); snap=json.loads((artifact/"snapshot_schema.json").read_text())
    if snap["target_definition_versions"]!=freeze["target_definitions"]: raise RuntimeError("target schema mismatch")
    if freeze["class_order"]!=CLASS_ORDER: raise RuntimeError("class order mismatch")
    for t in TARGETS:
        for m in ("G0","G1","P1"):
            key=f"{t}_{m}"; cols=prep[key]["columns"]
            if cols!=models[t]["models"][m]["columns"]: raise RuntimeError(f"frozen column mismatch: {key}")
            expected=[c for c in schema["targets"][t][m] if c.startswith("symbol_") or not prep[key]["parameters"][c]["excluded_zero_iqr"]]
            if expected!=cols: raise RuntimeError(f"feature schema order mismatch: {key}")
            if np.asarray(models[t]["models"][m]["coefficients"]).shape!=(len(cols)+1,2): raise RuntimeError(f"model/class order mismatch: {key}")
    config=freeze.get("locked_2025_evaluation"); expected=locked_evaluation_config(json.loads((artifact/"calibration_2024.json").read_text()))
    if config!=expected or _sem(config)!=freeze.get("locked_2025_evaluation_sha256"): raise RuntimeError("bootstrap, interpretation, or output configuration mismatch")
    return LockedCheckpoint(actual,freeze,schema,prep,models,config)

def validate_readiness(repo,artifact):
    c=load_locked_checkpoint(repo,artifact)
    return {"status":"READY_FOR_LOCKED_2025_INPUT","freeze_sha256":c.freeze_hash,"config_sha256":c.freeze["locked_2025_evaluation_sha256"],"targets":list(TARGETS),"models":list(MODELS),"required_outputs":list(OUTPUT_FILES),"predictive_rows_consumed":0,"predictive_scoring_performed":False,"2026_access":False}

def _validate_2025_metadata(row):
    entry=int(row["entry_execution_ms"]); snap=int(row["snapshot_ms"])
    if not BOUNDARY_2025_MS<=entry<BOUNDARY_2026_MS: raise ValueError("locked evaluator accepts 2025 entries only")
    if not BOUNDARY_2025_MS<=snap<BOUNDARY_2026_MS: raise ValueError("locked evaluator rejects snapshot outside 2025")

def predict_feature_rows(c,target,model,rows):
    if target not in TARGETS or model not in MODELS: raise ValueError("unknown frozen target/model")
    for row in rows: _validate_2025_metadata(row)
    classes=c.freeze["class_order"][target]; frozen=c.models[target]["models"][model]
    if model=="B0": probs=np.tile(np.asarray(frozen["probabilities"]),(len(rows),1))
    else:
        prep=c.preprocessing[f"{target}_{model}"]; cols=prep["columns"]
        if cols!=frozen["columns"]: raise RuntimeError("column order changed after checkpoint load")
        x=np.empty((len(rows),len(cols)))
        for j,col in enumerate(cols):
            if col.startswith("symbol_"): x[:,j]=[r["symbol"]==col[7:] for r in rows]
            else: x[:,j]=[(float(r["features"][col])-prep["parameters"][col]["median"])/prep["parameters"][col]["iqr"] for r in rows]
        design=np.column_stack((np.ones(len(rows)),x)); eta=np.column_stack((design@np.asarray(frozen["coefficients"]),np.zeros(len(rows)))); eta-=eta.max(axis=1,keepdims=True); exp=np.exp(eta); probs=exp/exp.sum(axis=1,keepdims=True)
    return [{"row_id":r["row_id"],"target":target,"model":model,**{f"p_{cl}":float(v) for cl,v in zip(classes,p)}} for r,p in zip(rows,probs)]

def _weights(rows):
    n=Counter(r["trade_id"] for r in rows); return np.asarray([1/n[r["trade_id"]] for r in rows])
def _scores(rows,p,classes,w):
    y=np.asarray([classes.index(r["event_class"]) for r in rows]); wn=w/w.sum(); one=np.eye(3)[y]
    return {"log_loss":float(np.sum(wn*-np.log(np.clip(p[np.arange(len(y)),y],1e-15,1)))),"brier":float(np.sum(wn*np.sum((p-one)**2,axis=1))),"rps":float(np.sum(wn*np.sum((np.cumsum(p,axis=1)[:,:-1]-np.cumsum(one,axis=1)[:,:-1])**2,axis=1)/2))}
def _auc_ap(y,s,w):
    order=sorted(range(len(y)),key=lambda i:(-s[i],i)); pos=sum(w[i] for i in range(len(y)) if y[i]); neg=w.sum()-pos
    if pos==0 or neg==0:return {"roc_auc":None,"average_precision":None,"incidence":float(pos/w.sum())}
    tp=fp=auc=ap=last=0.
    for i in order:
        if y[i]: tp+=w[i]; rec=tp/pos; ap+=(rec-last)*tp/(tp+fp); last=rec
        else: auc+=w[i]*tp; fp+=w[i]
    return {"roc_auc":float(auc/(pos*neg)),"average_precision":float(ap),"incidence":float(pos/w.sum())}
def _secondary(rows,p,classes,w):
    y=np.asarray([classes.index(r["event_class"]) for r in rows]); cw={cl:_auc_ap(y==i,p[:,i],w) for i,cl in enumerate(classes)}; conf={a:{b:0 for b in classes} for a in classes}
    for a,b in zip(y,np.argmax(p,axis=1)):conf[classes[a]][classes[b]]+=1
    return {"role":"SECONDARY_DIAGNOSTIC_ONLY","classwise_one_vs_rest":cw,"macro_roc_auc":float(np.mean([x["roc_auc"] for x in cw.values() if x["roc_auc"] is not None])),"macro_average_precision":float(np.mean([x["average_precision"] for x in cw.values() if x["average_precision"] is not None])),"equal_trade_ranked_probability_score":_scores(rows,p,classes,w)["rps"],"snapshot_weighted":_scores(rows,p,classes,np.ones(len(rows))),"top_class_confusion_counts":conf}
def _trade_losses(rows,a,b,classes,metric):
    y=np.asarray([classes.index(r["event_class"]) for r in rows]); one=np.eye(3)[y]
    d=(-np.log(np.clip(a[np.arange(len(y)),y],1e-15,1))+np.log(np.clip(b[np.arange(len(y)),y],1e-15,1))) if metric=="log_loss" else np.sum((a-one)**2,axis=1)-np.sum((b-one)**2,axis=1)
    out=defaultdict(list)
    for r,x in zip(rows,d):out[r["trade_id"]].append(float(x))
    return {k:float(np.mean(v)) for k,v in out.items()}
def _bootstrap(rows,losses,cfg):
    tw={r["trade_id"]:r["trade_entry_week"] for r in rows}
    for r in rows:
        entry=datetime.fromtimestamp(int(r["entry_execution_ms"])/1000,timezone.utc); monday=(entry.date()).toordinal()-entry.weekday(); supplied=datetime.fromisoformat(str(r["trade_entry_week"])).date().toordinal()
        if supplied!=monday:raise RuntimeError("entry-week metadata mismatch")
    weeks=sorted(set(tw.values()))
    if len(weeks)<4:return {"available":False,"reason":"fewer_than_four_entry_weeks"}
    start=datetime.fromisoformat(weeks[0]).replace(tzinfo=timezone.utc); end=datetime.fromisoformat(weeks[-1]).replace(tzinfo=timezone.utc); span=(end-start).days//7+1; at=defaultdict(list)
    for t,w in tw.items():at[(datetime.fromisoformat(w).replace(tzinfo=timezone.utc)-start).days//7].append(t)
    blocks=[[t for j in range(i,i+4) for t in at[j]] for i in range(span-3)]
    if sum(bool(x) for x in blocks)<2:return {"available":False,"reason":"fewer_than_two_nonempty_blocks"}
    rng=np.random.Generator(np.random.PCG64(cfg["seed"])); reps=[]; sampled=[]
    for _ in range(cfg["replicates"]):
        picks=[]
        for _ in range(math.ceil(span/4)):
            ix=int(rng.integers(len(blocks)))
            while not blocks[ix]:ix=int(rng.integers(len(blocks)))
            picks.append(ix)
        copies=[t for i in picks for t in blocks[i]]; reps.append(float(np.mean([losses[t] for t in copies]))); sampled.append(picks)
    return {"available":True,"point_estimate":float(np.mean(list(losses.values()))),"ci95":np.quantile(reps,[.025,.975],method="linear").tolist(),"replicates":reps,"sampled_block_indices":sampled,"sign_convention":"first_minus_second"}
def _calibration_statistic(outcome,probability,weights):
    z=np.log(np.clip(probability,1e-12,1-1e-12)/np.clip(1-probability,1e-12,1)); design=np.column_stack((np.ones(len(z)),z)); beta=np.asarray([0.,1.]); wn=weights/weights.sum()
    for _ in range(50):
        fitted=1/(1+np.exp(-np.clip(design@beta,-35,35))); grad=design.T@(wn*(fitted-outcome)); h=design.T@(design*(wn*fitted*(1-fitted))[:,None])
        try: step=np.linalg.solve(h,grad)
        except np.linalg.LinAlgError:return {"estimable":False,"intercept":None,"slope":None,"reason":"singular"}
        beta-=step
        if np.max(np.abs(grad))<=1e-8:return {"estimable":True,"intercept":float(beta[0]),"slope":float(beta[1]),"reason":None}
    return {"estimable":False,"intercept":None,"slope":None,"reason":"nonconvergence"}
def _calibration(rows,p,classes,cuts,cfg):
    w=_weights(rows); out={}
    for ci,cl in enumerate(classes):
        cp=sorted(set(cuts[cl])); bi=np.searchsorted(cp,p[:,ci],side="right"); bins=[]
        for b in range(len(cp)+1):
            ix=np.flatnonzero(bi==b)
            if not len(ix):continue
            rs=[rows[i] for i in ix]; ww=w[ix]/w[ix].sum(); trades={r['trade_id'] for r in rs}; events={r['trade_id'] for r in rs if r['event_class']==cl}
            bins.append({"bin":b,"snapshots":len(ix),"unique_resolved_trades":len(trades),"unique_event_trades":len(events),"mean_predicted":float(np.sum(ww*p[ix,ci])),"observed":float(np.sum(ww*np.asarray([r['event_class']==cl for r in rs]))),"supported":len(trades)>=cfg["reliability_minimum_unique_resolved_trades"],"unstable":len(events)<cfg["unstable_below_unique_event_trades"]})
        event_trades=len({r["trade_id"] for r in rows if r["event_class"]==cl}); statistic=_calibration_statistic(np.asarray([r["event_class"]==cl for r in rows],float),p[:,ci],w) if event_trades>=cfg["intercept_slope_minimum_unique_event_trades"] else {"estimable":False,"intercept":None,"slope":None,"reason":"insufficient_unique_event_trades"}
        out[cl]={"training_cut_points":cp,"bins":bins,"post_hoc_recalibration":False,"calibration_intercept_slope":statistic,"unique_event_trades":event_trades}
    return out
def _stability(rows,a,b,classes):
    out={}
    for dim in ("symbol","month","quarter"):
        groups=defaultdict(list)
        for i,r in enumerate(rows):
            dt=datetime.fromtimestamp(int(r["snapshot_ms"])/1000,timezone.utc); key=r["symbol"] if dim=="symbol" else dt.strftime("%Y-%m") if dim=="month" else f"{dt.year}-Q{(dt.month-1)//3+1}"; groups[key].append(i)
        out[dim]={}
        for k,ix in sorted(groups.items()):
            rs=[rows[i] for i in ix]; ii=np.asarray(ix); w=_weights(rs); x=_scores(rs,a[ii],classes,w); y=_scores(rs,b[ii],classes,w); out[dim][k]={"trades":len({r['trade_id'] for r in rs}),"snapshots":len(rs),"log_loss_delta":x["log_loss"]-y["log_loss"],"brier_delta":x["brier"]-y["brier"]}
    return out
def _interpret(primary,boot,stability,cal,target,freeze):
    pair=boot[target]["P1-G1"]
    if any(not pair[m]["available"] for m in ("log_loss","brier")) or not all(cal[target][cl]["bins"] and all(b["supported"] for b in cal[target][cl]["bins"]) for cl in cal[target]):return "INSUFFICIENT EVIDENCE"
    d=[primary[target]["P1"][m]-primary[target]["G1"][m] for m in ("log_loss","brier")]; ci=[pair[m]["ci95"] for m in ("log_loss","brier")]; groups=[g for x in stability[target].values() for g in x.values()]; stable=sum(g["log_loss_delta"]<0 and g["brier_delta"]<0 for g in groups)>1; prior=freeze["interpretation"]["target_decisions"][target]["fold_point_deltas"]
    if all(x<0 for x in d) and all(x[1]<0 for x in ci) and all(x<0 for x in prior) and stable:return "SUPPORTS SEQUENTIAL PATH-STATE SIGNAL"
    if all(x>0 for x in d) and all(x[0]>0 for x in ci):return "COUNTS AGAINST"
    return "MIXED"

def evaluate_locked_2025(repo,artifact,input_path,output_dir=None):
    c=load_locked_checkpoint(repo,artifact); artifact=Path(artifact); output=Path(output_dir) if output_dir else artifact/"locked_2025"
    if output.exists():raise RuntimeError("locked 2025 output already exists")
    input_path=Path(input_path); input_sha256=_sha(input_path); raw=json.loads(input_path.read_text())
    if not isinstance(raw,list):raise ValueError("locked input must be a JSON row list")
    for r in raw:_validate_2025_metadata(r)
    accepted={}; population={}; known={"BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT"}
    for t in TARGETS:
        rows=[]; required=c.schema["targets"][t]["P1"]
        for r in raw:
            if r.get("target")!=t:continue
            if r.get("symbol") not in known:raise ValueError("unknown frozen symbol")
            if not (r.get("target_eligible") is True and r.get("resolved") is True and r.get("censored") is False and r.get("ambiguous") is False):continue
            if r.get("event_class") not in c.freeze["class_order"][t]:raise ValueError("class order/outcome mismatch")
            f=r["features"]
            if any(x not in f or not math.isfinite(float(f[x])) for x in required if not x.startswith("symbol_")):continue
            rows.append(r)
        if not rows:raise RuntimeError(f"no complete locked rows for {t}")
        rows.sort(key=lambda r:(int(r["snapshot_ms"]),r["symbol"],r["trade_id"],r["row_id"])); accepted[t]=rows; population[t]={"rows":len(rows),"trades":len({r['trade_id'] for r in rows}),"row_ids_sha256":_sem([r['row_id'] for r in rows])}
    arrays={}; primary={}; secondary={}; boot={}; cal={}; stability={}; predrows=[]
    for t,rows in accepted.items():
        classes=c.freeze["class_order"][t]; w=_weights(rows); arrays[t]={}; primary[t]={}; secondary[t]={}
        for m in MODELS:
            pred=predict_feature_rows(c,t,m,rows); arrays[t][m]=np.asarray([[x[f"p_{cl}"] for cl in classes] for x in pred]); scored=_scores(rows,arrays[t][m],classes,w); primary[t][m]={k:scored[k] for k in ("log_loss","brier")}; secondary[t][m]=_secondary(rows,arrays[t][m],classes,w)
            for r,x in zip(rows,pred):predrows.append({"row_id":r["row_id"],"trade_id":r["trade_id"],"target":t,"model":m,**{f"p_{cl}":x[f"p_{cl}"] for cl in classes}})
        boot[t]={}
        for a,b in COMPARISONS:boot[t][f"{a}-{b}"]={metric:_bootstrap(rows,_trade_losses(rows,arrays[t][a],arrays[t][b],classes,metric),c.config["bootstrap"]) for metric in ("log_loss","brier")}
        cal[t]=_calibration(rows,arrays[t]["P1"],classes,c.config["calibration"]["cut_points"][t],c.config["calibration"]); stability[t]=_stability(rows,arrays[t]["P1"],arrays[t]["G1"],classes)
    interpretation={t:{"decision":_interpret(primary,boot,stability,cal,t,c.freeze),"decisive_comparison":"P1-G1","G1-G0_role":"current-state/geometry only"} for t in TARGETS}
    values={"population_summary.json":population,"primary_metrics.json":primary,"secondary_metrics.json":secondary,"bootstrap_comparisons.json":boot,"calibration.json":cal,"stability.json":stability,"interpretation.json":interpretation}
    output.parent.mkdir(parents=True,exist_ok=True); temp=Path(tempfile.mkdtemp(prefix="c4-locked-2025-",dir=output.parent))
    try:
        for n,v in values.items():(temp/n).write_text(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+"\n")
        cols=sorted({k for r in predrows for k in r})
        with (temp/"predictions.csv").open("w",newline="") as h:w=csv.DictWriter(h,fieldnames=cols,lineterminator="\n");w.writeheader();w.writerows(predrows)
        manifest={"version":"C4_LOCKED_2025_OUTPUT_V1","freeze_sha256":c.freeze_hash,"configuration_sha256":c.freeze["locked_2025_evaluation_sha256"],"input_sha256":input_sha256,"required_files":list(OUTPUT_FILES),"targets":list(TARGETS),"models":list(MODELS)};(temp/"evaluation_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
        hashes={p.name:_sha(p) for p in temp.iterdir()}; repro={"freeze_sha256":c.freeze_hash,"input_sha256":input_sha256,"output_hashes":hashes,"refit":False,"reselection":False,"recalibration":False,"2026_access":False};(temp/"reproducibility.json").write_text(json.dumps(repro,indent=2,sort_keys=True)+"\n")
        if {p.name for p in temp.iterdir()}!=set(OUTPUT_FILES):raise RuntimeError("partial locked output")
        temp.rename(output)
    except Exception:shutil.rmtree(temp,ignore_errors=True);raise
    return {"status":"LOCKED_2025_EVALUATION_COMPLETE","output_dir":str(output),"interpretation":interpretation}
