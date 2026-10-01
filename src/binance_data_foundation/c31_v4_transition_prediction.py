"""C31 frozen V4 transition-representation prediction experiment."""
from __future__ import annotations

import hashlib, json, os, platform, subprocess, sys, warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import c29_opportunity_prevalence as c29
from . import c30_opportunity_prediction as c30
from . import catchup_transition_representation_audit as vbase
from . import catchup_transition_representation_audit_v4 as v4
from .ingest import sha256_file

CONTRACT_REL = "contracts/C31_V4_TRANSITION_REPRESENTATION_PREDICTION_CONTRACT.md"
CONTRACT_SHA256 = "4125ccc1d4756782c91fd2095f7914fb39f933a435d60d39fe26a04329fdaea0"
OUTPUT_REL = "artifacts/c31_v4_transition_prediction"
FEATURES = v4.PRIMARY
TASKS = c30.TASKS
SEED = 20261001
REPLICATES = 2000
MODEL_SPEC = dict(c30.MODEL_SPEC)
EXPECTED_C30 = {
 "H3_GROSS40":((-0.01274,-0.02978),(0.00204,0.00286)),
 "H3_GROSS50":((-0.01197,-0.03061),(0.00353,0.00658)),
 "H6_GROSS40":((-0.01034,-0.02588),(-0.00493,-0.01162)),
 "H6_GROSS50":((-0.00890,-0.02417),(-0.00431,-0.01115)),
 "H12_GROSS40":((-0.01243,-0.02578),(-0.00083,-0.00198)),
 "H12_GROSS50":((-0.01438,-0.02997),(-0.00027,-0.00063)),
 "H24_GROSS40":((-0.00917,-0.01946),(-0.00401,-0.00831)),
 "H24_GROSS50":((-0.01046,-0.02322),(-0.00375,-0.00776)),
}

def _write(path, value): path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def _sha(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _q(a,q): return float(np.quantile(np.asarray(a,float),q,method="linear"))
def _loss(y,p):
    y=np.asarray(y,int); p=np.clip(np.asarray(p,float),1e-15,1-1e-15)
    return float(np.mean((p-y)**2)),float(np.mean(-(y*np.log(p)+(1-y)*np.log(1-p))))
def _dist(p):
    a=np.asarray(p,float)
    return {"min":float(a.min()),"p01":_q(a,.01),"p05":_q(a,.05),"p10":_q(a,.1),"p25":_q(a,.25),"median":_q(a,.5),"p75":_q(a,.75),"p90":_q(a,.9),"p95":_q(a,.95),"p99":_q(a,.99),"max":float(a.max())}

def verify_documents(repo):
    expected={CONTRACT_REL:CONTRACT_SHA256,c30.CONTRACT_REL:c30.CONTRACT_SHA256,c29.CONTRACT_REL:c29.CONTRACT_SHA256,
              v4.V4_SPEC_REL:v4.V4_SPEC_SHA256,v4.CONTRACT_REL:v4.CONTRACT_SHA256}
    actual={p:sha256_file(repo/p) for p in expected}
    if actual != expected: raise RuntimeError("C31_INSUFFICIENT: authoritative document hash mismatch")
    audit_hashes=json.loads((repo/v4.OUTPUT_REL/"reproducibility_hashes_v4.json").read_text())
    bad={name:(digest,sha256_file(repo/v4.OUTPUT_REL/name)) for name,digest in audit_hashes["artifact_sha256"].items() if sha256_file(repo/v4.OUTPUT_REL/name)!=digest}
    if bad: raise RuntimeError("C31_INSUFFICIENT: V4 audit artifact hash mismatch")
    return {"expected":expected,"actual":actual,"all_match":True,"v4_audit_artifacts_all_match":True,
            "v4_audit_final_summary_sha256":sha256_file(repo/v4.OUTPUT_REL/"final_summary_v4.json")}

def build_v4_rows(entries,hours):
    rows=[]
    for e in entries:
        ms=int(e["entry_execution_ms"]); f=v4.representation_row(hours,e["symbol"],ms)
        if not f["COMPLETE_V4_PRIMARY"]: raise RuntimeError("C31_INSUFFICIENT: incomplete V4 row")
        rows.append({"trade_id":e["trade_id"],"symbol":e["symbol"],"entry_ms":ms,
          "entry_month":datetime.fromtimestamp(ms/1000,timezone.utc).strftime("%Y-%m"),
          "features":{k:f[k] for k in FEATURES}})
    if tuple(rows[0]["features"]) != FEATURES: raise RuntimeError("C31_INSUFFICIENT: V4 schema order")
    return rows

def fit_models(folds):
    predictions={t:{} for t in TASKS}; proper={t:{} for t in TASKS}; discr={t:{} for t in TASKS}
    calibr={t:{} for t in TASKS}; pdist={t:{} for t in TASKS}; coef={t:{} for t in TASKS}; conv={t:{} for t in TASKS}; quint={t:{} for t in TASKS}
    for task in TASKS:
      for year in (2024,2025):
        train,valid=folds[task][year]
        xt=np.asarray([[r["features"][f] for f in FEATURES] for r in train],float); xv=np.asarray([[r["features"][f] for f in FEATURES] for r in valid],float)
        yt=np.asarray([r["tasks"][task]["label"] for r in train],int); y=np.asarray([r["tasks"][task]["label"] for r in valid],int)
        scaler=c30.StandardScaler().fit(xt)
        caught=[]
        with warnings.catch_warnings(record=True) as ws:
          warnings.simplefilter("always"); model=c30.LogisticRegression(**{k:v for k,v in MODEL_SPEC.items() if k!="estimator"}).fit(scaler.transform(xt),yt)
          caught=[str(w.message) for w in ws]
        pt=model.predict_proba(scaler.transform(xt))[:,1]; pv=model.predict_proba(scaler.transform(xv))[:,1]
        base=float(yt.mean()); pb=np.full(len(y),base)
        b0=_loss(y,pb); mv=_loss(y,pv)
        predictions[task][year]=[{"trade_id":r["trade_id"],"symbol":r["symbol"],"entry_month":r["entry_month"],"label":int(a),"B0":base,"V4":float(p)} for r,a,p in zip(valid,y,pv)]
        proper[task][str(year)]={"B0":{"brier":b0[0],"log_loss":b0[1]},"M_V4":{"brier":mv[0],"log_loss":mv[1]}}
        discr[task][str(year)]={"B0":{"roc_auc":.5,"pr_auc":float(y.mean())},"M_V4":{"roc_auc":c30.roc_auc_score(y,pv),"pr_auc":c30.average_precision_score(y,pv)}}
        calibr[task][str(year)]={"M_V4":c30._calibration(y,pv)}; pdist[task][str(year)]={"M_V4":_dist(pv)}
        coef[task][str(year)]={"intercept":float(model.intercept_[0]),"standardized_coefficients":dict(zip(FEATURES,map(float,model.coef_[0])))}
        conv[task][str(year)]={"n_iter_":int(model.n_iter_[0]),"converged":bool(model.converged_),"warnings":caught,
          "coefficient_norm":float(np.linalg.norm(model.coef_[0])),"intercept":float(model.intercept_[0]),
          "scaler_mean":dict(zip(FEATURES,map(float,scaler.mean_))),"scaler_scale":dict(zip(FEATURES,map(float,scaler.scale_)))}
        cuts=[float(x) for x in np.quantile(pt,[.2,.4,.6,.8],method="linear")]
        groups=np.searchsorted(cuts,pv,side="right")+1
        quint[task][str(year)]={"training_boundaries":cuts,"validation":{f"Q{i}":{"row_count":int((groups==i).sum()),
          "positive_label_rate":float(y[groups==i].mean()) if (groups==i).any() else None,"mean_predicted_probability":float(pv[groups==i].mean()) if (groups==i).any() else None} for i in range(1,6)}}
    return predictions,proper,discr,calibr,pdist,coef,conv,quint

def attach_c30(predictions,c30pred,proper,discr,calibr,pdist):
    reconciliation={}
    for task in TASKS:
      reconciliation[task]={}
      for year in (2024,2025):
        locked={r["trade_id"]:r for r in c30pred[task][year]}; rr=predictions[task][year]
        if set(locked) != {r["trade_id"] for r in rr}: raise RuntimeError("C31_INSUFFICIENT: comparator row mismatch")
        for r in rr: r["C30"]=float(locked[r["trade_id"]]["probability"])
        y=np.array([r["label"] for r in rr]); p=np.array([r["C30"] for r in rr]); m=_loss(y,p)
        proper[task][str(year)]["M_C30_LOCKED"]={"brier":m[0],"log_loss":m[1]}
        discr[task][str(year)]["M_C30_LOCKED"]={"roc_auc":c30.roc_auc_score(y,p),"pr_auc":c30.average_precision_score(y,p)}
        calibr[task][str(year)]["M_C30_LOCKED"]=c30._calibration(y,p); pdist[task][str(year)]["M_C30_LOCKED"]=_dist(p)
        ref=EXPECTED_C30[task][year-2024]; actual=(proper[task][str(year)]["B0"]["brier"]-m[0],proper[task][str(year)]["B0"]["log_loss"]-m[1])
        ok=all(abs(a-b)<=5.1e-6 for a,b in zip(actual,ref))
        reconciliation[task][str(year)]={"validation_rows":len(rr),"identical_row_ids":True,"accepted_rounded_delta":list(ref),"reproduced_delta":list(actual),"match":ok}
        if not ok: raise RuntimeError("C31_INSUFFICIENT: locked C30 metric mismatch")
    return reconciliation

def comparisons(proper):
    joint={}; signs={}
    for year in (2024,2025):
      vals=[]; cats={"improves_both":[],"improves_one":[],"worsens_both":[],"improves_both_vs_B0":[]}
      for t in TASKS:
        m=proper[t][str(year)]; d={"task":t,"brier_v4_c30":m["M_C30_LOCKED"]["brier"]-m["M_V4"]["brier"],"logloss_v4_c30":m["M_C30_LOCKED"]["log_loss"]-m["M_V4"]["log_loss"],"brier_v4_b0":m["B0"]["brier"]-m["M_V4"]["brier"],"logloss_v4_b0":m["B0"]["log_loss"]-m["M_V4"]["log_loss"]}; vals.append(d)
        a,b=d["brier_v4_c30"]>0,d["logloss_v4_c30"]>0; cats["improves_both" if a and b else "worsens_both" if not a and not b else "improves_one"].append(t)
        if d["brier_v4_b0"]>0 and d["logloss_v4_b0"]>0: cats["improves_both_vs_B0"].append(t)
      joint[str(year)]={"task_deltas":vals,**{f"mean_{k}":float(np.mean([x[k] for x in vals])) for k in ("brier_v4_c30","logloss_v4_c30","brier_v4_b0","logloss_v4_b0")}}
      signs[str(year)]={k:{"count":len(v),"tasks":v} for k,v in cats.items()}
    return joint,signs

def bootstrap(predictions,unit):
    out={"unit":unit,"iterations":REPLICATES,"generator":"PCG64","seed":SEED,"joint_eight_task_resampling":True,"years":{}}
    keys4=("brier_v4_c30","logloss_v4_c30","brier_v4_b0","logloss_v4_b0")
    for year in (2024,2025):
      universe=sorted({r["trade_id"] for t in TASKS for r in predictions[t][year]})
      months={r["trade_id"]:r["entry_month"] for t in TASKS for r in predictions[t][year]}
      keys=universe if unit=="trade" else sorted(set(months.values())); rng=np.random.Generator(np.random.PCG64(SEED+year+(10000 if unit=="UTC_entry_month" else 0)))
      samples={k:[] for k in keys4}; task_samples={t:{k:[] for k in keys4} for t in TASKS}
      maps={t:defaultdict(list) for t in TASKS}
      for t in TASKS:
        for r in predictions[t][year]: maps[t][r["trade_id"] if unit=="trade" else r["entry_month"]].append(r)
      for _ in range(REPLICATES):
        draw=rng.integers(len(keys),size=len(keys)); per={k:[] for k in keys4}
        for t in TASKS:
          rr=[]
          for j in draw: rr.extend(maps[t].get(keys[int(j)],[]))
          y=[r["label"] for r in rr]; c=[r["C30"] for r in rr]; v=[r["V4"] for r in rr]; b=[r["B0"] for r in rr]
          lc,lv,lb=_loss(y,c),_loss(y,v),_loss(y,b); d=dict(zip(keys4,(lc[0]-lv[0],lc[1]-lv[1],lb[0]-lv[0],lb[1]-lv[1])))
          for k,x in d.items(): task_samples[t][k].append(x); per[k].append(x)
        for k in keys4: samples[k].append(float(np.mean(per[k])))
      one=lambda a:{"ci95":[_q(a,.025),_q(a,.975)],"replicates":len(a),"replicate_sha256":hashlib.sha256(np.asarray(a,dtype="<f8").tobytes()).hexdigest()}
      out["years"][str(year)]={"joint":{k:one(v) for k,v in samples.items()},"task":{t:{k:one(v) for k,v in ss.items()} for t,ss in task_samples.items()}}
    return out

def run(repo:Path):
    repo=repo.resolve(); c30.reject_prohibited_path(repo)
    if os.environ.get("CONDA_DEFAULT_ENV")!="binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    documents=verify_documents(repo)
    entries,population,opens=c29._load_and_reconcile(repo); horizon,coverage=c29.build_rows(entries,opens)
    # Reproduce locked C30 before evaluating V4.
    c30rows,c30summary=c30.build_feature_rows(entries,c30._hour_states(c30._load_hourly(repo))); c30rows,labels=c30.attach_outcomes(c30rows,horizon)
    c30folds,c30foldreport=c30.make_folds(c30rows); c30pred,c30metrics,*_=c30.fit_all(c30folds)
    hours,source_boundary=vbase.load_hourly_market(repo); vrows=build_v4_rows(entries,hours); vrows,labels2=c30.attach_outcomes(vrows,horizon); folds,foldreport=c30.make_folds(vrows)
    if labels!=labels2 or foldreport!=c30foldreport: raise RuntimeError("C31_INSUFFICIENT: label/fold reconciliation mismatch")
    pred,proper,discr,calibr,pdist,coef,conv,quint=fit_models(folds); c30rec=attach_c30(pred,c30pred,proper,discr,calibr,pdist)
    joint,signs=comparisons(proper); trade=bootstrap(pred,"trade"); month=bootstrap(pred,"UTC_entry_month")
    stability={f:{"2024_sign":{t:int(np.sign(coef[t]["2024"]["standardized_coefficients"][f])) for t in TASKS},"2025_sign":{t:int(np.sign(coef[t]["2025"]["standardized_coefficients"][f])) for t in TASKS},"agreement_count":int(sum(np.sign(coef[t]["2024"]["standardized_coefficients"][f])==np.sign(coef[t]["2025"]["standardized_coefficients"][f]) for t in TASKS))} for f in FEATURES}
    symbol={t:{str(y):{} for y in (2024,2025)} for t in TASKS}
    for t in TASKS:
      for y in (2024,2025):
       for s in c30.SYMBOLS:
        rr=[r for r in pred[t][y] if r["symbol"]==s]; yy=[r["label"] for r in rr]; lv=_loss(yy,[r["V4"] for r in rr]); lc=_loss(yy,[r["C30"] for r in rr])
        symbol[t][str(y)][s]={"validation_count":len(rr),"brier_v4":lv[0],"brier_c30":lc[0],"delta_brier":lc[0]-lv[0],"log_loss_v4":lv[1],"log_loss_c30":lc[1],"delta_logloss":lc[1]-lv[1],"auc_v4":c30.roc_auc_score(yy,[r["V4"] for r in rr]) if len(set(yy))==2 else None}
    p2025=joint["2025"]; allconv=all(conv[t][str(y)]["converged"] for t in TASKS for y in (2024,2025)); both25=signs["2025"]["improves_both"]["count"]
    supported=(all(joint[str(y)]["mean_brier_v4_c30"]>0 and joint[str(y)]["mean_logloss_v4_c30"]>0 for y in (2024,2025)) and
      len(set(signs["2024"]["improves_both"]["tasks"])&set(signs["2025"]["improves_both"]["tasks"]))>=4 and p2025["mean_brier_v4_b0"]>0 and p2025["mean_logloss_v4_b0"]>0 and
      month["years"]["2025"]["joint"]["brier_v4_c30"]["ci95"][0]>0 and month["years"]["2025"]["joint"]["logloss_v4_c30"]["ci95"][0]>0 and
      not any(t in signs["2024"]["worsens_both"]["tasks"] and t in signs["2025"]["worsens_both"]["tasks"] for t in TASKS) and allconv)
    weak=p2025["mean_brier_v4_c30"]>0 and p2025["mean_logloss_v4_c30"]>0 and both25>=4 and allconv
    if supported: classification="V4_REPRESENTATION_IMPROVEMENT_SUPPORTED"
    elif weak: classification="V4_REPRESENTATION_IMPROVEMENT_WEAK"
    else: classification="NO_USEFUL_V4_REPRESENTATION_IMPROVEMENT"
    predicates={"supported":supported,"weak":weak,"all_fits_converged":allconv,"2025_tasks_improve_both_vs_C30":both25,"classification":classification}
    rec={"coverage":{f"H{h}":coverage[f"H{h}"]["valid_executable_trade_count"] for h in c29.HORIZONS},"all_task_labels_exact":all(x["exact"] for x in labels2.values()),"tasks":labels2}
    baseline={t:{str(y):proper[t][str(y)]["B0"]|{"training_prevalence":pred[t][y][0]["B0"]} for y in (2024,2025)} for t in TASKS}
    final={"classification":classification,"contract_sha256":CONTRACT_SHA256,"v4_spec_sha256":v4.V4_SPEC_SHA256,"population_count":population["original_trade_count"],"horizon_coverage":rec["coverage"],"schema":list(FEATURES),"joint_representation_comparison":joint,"task_sign_summary":signs,"later_policy_research_scientifically_justified":classification!="NO_USEFUL_V4_REPRESENTATION_IMPROVEMENT","representation_improvement_does_not_establish_trading_profitability":True,"confirmations":{"no_2026_data_or_metadata_accessed":True,"no_search_tuning_or_feature_selection":True,"no_policy_or_prediction_driven_PnL":True,"not_staged_committed_or_pushed":True}}
    out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True)
    files={"run_manifest":{"command":"conda run -n binance-v2-research env PYTHONPATH=src python scripts/c31_v4_transition_prediction.py","seed":SEED,"iterations":REPLICATES,"generator":"PCG64","python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"git_HEAD":subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()},"provenance":{"documents":documents,"source_boundary":source_boundary,"C30_implementation_sha256":sha256_file(Path(c30.__file__)),"V4_implementation_sha256":sha256_file(Path(v4.__file__)),"locked_C30_reproduced_before_V4_evaluation":True,"sealed_boundary_accessed":False},"population_reconciliation":population,"label_reconciliation":rec,"representation_reconciliation":{"schema":list(FEATURES),"count":len(vrows),"semantic_matrix_sha256":_sha([[r["features"][f] for f in FEATURES] for r in vrows]),"audit_semantic_matrix_sha256":"9ab75dce3506de77c0b396da1c835dc7841ae782db4dade884d246fb29df5340"},"c30_comparator_reconciliation":c30rec,"fold_reconciliation":foldreport,"model_specification":MODEL_SPEC|{"scaler":"StandardScaler","implementation":"locked deterministic C30 numerical implementation","features":list(FEATURES)},"training_prevalence_baselines":baseline,"proper_scores":proper,"discrimination_metrics":discr,"calibration_results":calibr,"probability_distribution_diagnostics":pdist,"coefficients":coef,"coefficient_stability":stability,"task_sign_summary":signs,"joint_representation_comparison":joint,"trade_bootstrap_intervals":trade,"month_bootstrap_intervals":month,"probability_quintile_diagnostics":quint,"symbol_breadth_diagnostics":symbol,"convergence_audit":conv,"interpretation_predicates":predicates,"final_summary":final}
    for n,x in files.items(): _write(out/f"{n}.json",x)
    hashes={p.name:sha256_file(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"}; hashes.update({"contract_sha256":CONTRACT_SHA256,"population_sha256":population["semantic_entry_sha256"],"C29_contract_sha256":c29.CONTRACT_SHA256,"C30_contract_sha256":c30.CONTRACT_SHA256,"V4_spec_sha256":v4.V4_SPEC_SHA256,"C30_prediction_semantic_sha256":_sha(c30pred),"V4_prediction_semantic_sha256":_sha(pred)})
    _write(out/"reproducibility_hashes.json",hashes)
    return final
