"""C10 bounded post-T2 timescale adequacy study (no economics or policy)."""
from __future__ import annotations

import csv, hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .c8_timescale import Market, Bars, aggregate, load_market, weighted_auc

CONTRACT_SHA256 = "fc350a8f97be3b70312013934fa00013008632411882d9bd2902a437a039daca"
SEED, REPLICATES, MINUTE = 20260929, 2000, 60_000
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
CLASSES = ("CONTINUATION_FIRST", "DETERIORATION_FIRST", "P0_FIRST")
ARCHITECTURES = {"A": (5, 1), "B": (10, 1), "C": (15, 1), "D": (5, 2)}
FOLDS = {
    "fold_A": (1704067200000, 1719792000000, 1727740800000),
    "fold_B": (1704067200000, 1727740800000, 1735689600000),
}
CONTEXT_FEATURES = ("context_return_1", "context_return_3", "context_return_6",
    "context_volatility_12", "context_range_ratio", "context_activity_ratio",
    "context_close_vs_sma12", "context_sma12_slope")
FAST_FEATURES = ("fast_return_1", "fast_return_3", "fast_return_6",
    "fast_volatility_12", "fast_range_ratio", "fast_activity_ratio",
    "return_since_t2", "return_from_entry", "new_peak_since_t2",
    "drawdown_from_running_peak", "distance_to_continuation",
    "distance_to_deterioration", "path_efficiency", "elapsed_log1p_minutes",
    "fast_context_agreement")
SYMBOL_FEATURES = tuple("symbol_" + s for s in SYMBOLS[1:])


def reject_2026(path: str | Path) -> None:
    if any("2026" in x for x in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C10 prohibits 2026 path or metadata access")


def sha256_file(path: Path) -> str:
    reject_2026(path); h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def load_c7_population(repo: Path) -> list[dict]:
    path = repo / "artifacts/c7_full_population_t2_exit_overlay/population_manifest.json"
    reject_2026(path); doc = json.loads(path.read_text())
    out = []
    for r in doc["rows"]:
        if not r["overlay_strictly_before_p0"]: continue
        tr = {"trade_id": r["trade_id"], "symbol": r["symbol"], "year": r["entry_year"],
            "entry_ms": _ms(r["entry_execution_ts"]), "entry_price": float(r["entry_price"]),
            "t0_ms": _ms(r["first_t2_decision_ts"]), "p0_ms": _ms(r["p0_execution_ts"])}
        if not tr["t0_ms"] < tr["p0_ms"]: raise ValueError("T2 not strictly before P0")
        out.append(tr)
    out.sort(key=lambda x: (x["entry_ms"], x["symbol"], x["trade_id"]))
    if len(out) != 845 or Counter(x["year"] for x in out) != {2024: 415, 2025: 430}:
        raise ValueError("C7 first-T2 population mismatch")
    return out


def reconcile_authoritative(repo: Path, trades: list[dict]) -> dict:
    path = repo / "artifacts/c4_sequential_exit_state/local/t2_snapshots.csv"; reject_2026(path)
    first = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["target_eligible"] == "True" and r["trade_id"] not in first:
                first[r["trade_id"]] = int(r["snapshot_ms"])
    mismatches = [t["trade_id"] for t in trades if first.get(t["trade_id"]) != t["t0_ms"]]
    return {"source_t2_trades": len(trades), "by_year": dict(Counter(str(t["year"]) for t in trades)),
        "authoritative_first_eligible_identities": len(first), "identity_or_timestamp_mismatches": len(mismatches),
        "mismatch_trade_ids": mismatches, "status": "PASS" if not mismatches else "FAIL"}


def freeze_geometry(trade: dict, market: Market) -> dict:
    i0, i1 = market.index(trade["entry_ms"]), market.index(trade["t0_ms"] - MINUTE)
    if i0 is None or i1 is None or i1 < i0: raise ValueError("T2 causal path unavailable")
    peak = max(trade["entry_price"], float(np.max(market.high[i0:i1 + 1])))
    return {"p0_t2": peak, "continuation_level": peak * 1.005,
        "deterioration_level": (trade["entry_price"] + peak) / 2}


def first_event(trade: dict, market: Market) -> dict:
    g = freeze_geometry(trade, market); i = market.index(trade["t0_ms"])
    if i is None: raise ValueError("post-T2 path unavailable")
    while int(market.ms[i]) < trade["p0_ms"]:
        up = float(market.high[i]) >= g["continuation_level"]
        down = float(market.low[i]) <= g["deterioration_level"]
        terminal_ms = int(market.ms[i] + MINUTE)
        if up and down: return trade | g | {"terminal": "AMBIGUOUS", "terminal_ms": terminal_ms,
            "terminal_close": float(market.close[i])}
        if up: return trade | g | {"terminal": "CONTINUATION_FIRST", "terminal_ms": terminal_ms,
            "terminal_close": float(market.close[i])}
        if down: return trade | g | {"terminal": "DETERIORATION_FIRST", "terminal_ms": terminal_ms,
            "terminal_close": float(market.close[i])}
        i += 1
    pi = market.index(trade["p0_ms"] - MINUTE)
    return trade | g | {"terminal": "P0_FIRST", "terminal_ms": trade["p0_ms"],
        "terminal_close": float(market.close[pi])}


def _bar_features(b: Bars, t: int, prefix: str) -> dict | None:
    i = b.at(t)
    if i is None or i < 13: return None
    c = b.close; rets = c[i-11:i+1] / c[i-12:i] - 1
    ranges = (b.high[i-12:i+1] - b.low[i-12:i+1]) / b.open[i-12:i+1]
    rmed, vmed = float(np.median(ranges[:-1])), float(np.median(b.volume[i-12:i]))
    if rmed <= 0 or vmed <= 0: return None
    x = {f"{prefix}_return_1": c[i]/c[i-1]-1, f"{prefix}_return_3": c[i]/c[i-3]-1,
        f"{prefix}_return_6": c[i]/c[i-6]-1, f"{prefix}_volatility_12": float(np.std(rets, ddof=1)),
        f"{prefix}_range_ratio": ranges[-1]/rmed, f"{prefix}_activity_ratio": b.volume[i]/vmed}
    if prefix == "context":
        now, prior = float(np.mean(c[i-11:i+1])), float(np.mean(c[i-12:i]))
        x |= {"context_close_vs_sma12": c[i]/now-1, "context_sma12_slope": now/prior-1}
    return x if all(math.isfinite(float(v)) for v in x.values()) else None


def feature_row(trade: dict, t: int, market: Market, context: Bars, fast: Bars) -> dict | None:
    context_end = (t // (context.minutes * MINUTE)) * context.minutes * MINUTE
    c, f = _bar_features(context, context_end, "context"), _bar_features(fast, t, "fast")
    if c is None or f is None: return None
    fi = fast.at(t); i0, i1 = market.index(trade["t0_ms"]), market.index(t - MINUTE)
    if fi is None or i0 is None or i1 is None or i1 < i0: return None
    prior_i = market.index(trade["t0_ms"] - MINUTE); t2_close = float(market.close[prior_i])
    post_peak = max(trade["p0_t2"], float(np.max(market.high[i0:i1+1])))
    width = fast.minutes * MINUTE
    first_end = ((trade["t0_ms"] + width - 1) // width) * width
    if first_end <= trade["t0_ms"]: first_end += width
    pi = fast.at(first_end)
    if pi is None or pi > fi: return None
    path = np.r_[t2_close, fast.close[pi:fi+1]]
    movement = float(np.sum(np.abs(path[1:] / path[:-1] - 1)))
    current = float(fast.close[fi]); net = current / t2_close - 1
    f |= {"return_since_t2": net, "return_from_entry": current/trade["entry_price"]-1,
        "new_peak_since_t2": post_peak/trade["p0_t2"]-1,
        "drawdown_from_running_peak": current/post_peak-1,
        "distance_to_continuation": current/trade["continuation_level"]-1,
        "distance_to_deterioration": current/trade["deterioration_level"]-1,
        "path_efficiency": 0.0 if movement == 0 else net/movement,
        "elapsed_log1p_minutes": math.log1p((t-trade["t0_ms"])/MINUTE),
        "fast_context_agreement": float(np.sign(f["fast_return_3"])*np.sign(c["context_return_3"]))}
    out = c | f
    return out if all(math.isfinite(float(v)) for v in out.values()) else None


def snapshots(trades, markets, bars, arch):
    cm, fm = ARCHITECTURES[arch]; rows = []; width = fm * MINUTE
    for tr in trades:
        t = ((tr["t0_ms"] + width - 1) // width) * width
        if t <= tr["t0_ms"]: t += width
        while t < tr["terminal_ms"]:
            feat = feature_row(tr, t, markets[tr["symbol"]], bars[(tr["symbol"], cm)], bars[(tr["symbol"], fm)])
            if feat is not None and tr["terminal"] != "AMBIGUOUS":
                rows.append({"trade_id": tr["trade_id"], "symbol": tr["symbol"], "year": tr["year"],
                    "entry_ms": tr["entry_ms"], "t0_ms": tr["t0_ms"], "state_ms": t,
                    "terminal_ms": tr["terminal_ms"], "label": CLASSES.index(tr["terminal"]), "features": feat})
            t += width
    return rows


def trade_weights(rows):
    counts = Counter(r["trade_id"] for r in rows)
    return np.asarray([1/counts[r["trade_id"]] for r in rows], float)


def fit_scaler(rows, names, weights):
    w = weights/weights.sum(); out = {}
    for name in names:
        x = np.asarray([r["features"][name] for r in rows]); mean = float(w @ x)
        sd = float(np.sqrt(w @ ((x-mean)**2)))
        if sd <= 0: raise ValueError(f"zero training scale: {name}")
        out[name] = {"mean": mean, "sd": sd}
    return out


def design(rows, names, scaler):
    x = np.ones((len(rows), 1+len(names)+len(SYMBOL_FEATURES)))
    for j, n in enumerate(names, 1): x[:, j] = [(r["features"][n]-scaler[n]["mean"])/scaler[n]["sd"] for r in rows]
    for j, n in enumerate(SYMBOL_FEATURES, 1+len(names)): x[:, j] = [r["symbol"] == n[7:] for r in rows]
    return x


def _softmax(x, beta):
    z = np.column_stack((x @ beta, np.zeros(len(x)))); z -= np.max(z, axis=1, keepdims=True)
    e = np.exp(z); return e/e.sum(axis=1, keepdims=True)


def _objective(x, y, w, beta, penalty):
    p = np.clip(_softmax(x, beta), 1e-15, 1); return float(-np.sum(w*np.log(p[np.arange(len(y)), y])) + .5*np.sum(penalty*beta*beta))


def fit_multinomial(x, y, weights, C=1.0, max_iter=1000, tol=1e-9):
    w = weights/weights.sum(); beta = np.zeros((x.shape[1], len(CLASSES)-1)); penalty = np.ones_like(beta)/C; penalty[0] = 0
    history = []; converged = False
    for iteration in range(1, max_iter+1):
        p = _softmax(x, beta); target = np.eye(len(CLASSES))[y, :len(CLASSES)-1]
        grad = x.T @ (w[:,None]*(p[:,:-1]-target)) + penalty*beta
        if np.max(np.abs(grad)) <= tol: converged = True; break
        q = grad.ravel(); alphas=[]
        for s, yy, rho in reversed(history):
            a=rho*np.dot(s,q); alphas.append(a); q-=a*yy
        scale=1.0 if not history else np.dot(history[-1][0],history[-1][1])/np.dot(history[-1][1],history[-1][1])
        d=scale*q
        for (s,yy,rho),a in zip(history,reversed(alphas)): d += s*(a-rho*np.dot(yy,d))
        d=-d.reshape(beta.shape); old=_objective(x,y,w,beta,penalty); gd=float(np.sum(grad*d)); step=1.0
        for _ in range(40):
            candidate=beta+step*d
            if _objective(x,y,w,candidate,penalty) <= old+1e-4*step*gd: break
            step *= .5
        nb=beta+step*d; npred=_softmax(x,nb)
        ng=x.T@(w[:,None]*(npred[:,:-1]-target))+penalty*nb
        s=(nb-beta).ravel(); yy=(ng-grad).ravel(); sy=float(np.dot(s,yy))
        if sy>1e-14: history.append((s,yy,1/sy)); history=history[-10:]
        beta=nb
    return {"coef": beta, "converged": converged, "iterations": iteration, "gradient_max": float(np.max(np.abs(grad)))}


def losses(rows, probs):
    y=np.asarray([r["label"] for r in rows]); oh=np.eye(len(CLASSES))[y]; p=np.clip(np.asarray(probs),1e-15,1)
    return np.sum((p-oh)**2,axis=1), -np.log(p[np.arange(len(y)),y])


def metrics(rows, probs):
    b,ll=losses(rows,probs); w=trade_weights(rows); wn=w/w.sum(); y=np.asarray([r["label"] for r in rows])
    auc={CLASSES[k]:weighted_auc(y==k,np.asarray(probs)[:,k],w) for k in range(len(CLASSES))}
    confusion=np.zeros((3,3),int)
    for a,p in zip(y,np.argmax(probs,axis=1)): confusion[a,p]+=1
    return {"brier":float(wn@b),"log_loss":float(wn@ll),"rows":len(rows),"trades":len(set(r["trade_id"] for r in rows)),
        "prevalence":{CLASSES[k]:float(wn@(y==k)) for k in range(3)},"ovr_auc":auc,
        "mean_probability":{CLASSES[k]:float(wn@np.asarray(probs)[:,k]) for k in range(3)},"row_confusion":confusion.tolist()}


def split_fold(rows, fold):
    start,cut,end=FOLDS[fold]
    return ([r for r in rows if start<=r["entry_ms"]<cut and r["terminal_ms"]<cut],
            [r for r in rows if cut<=r["entry_ms"]<end])


def fit_predict(train, valid):
    w=trade_weights(train); y=np.asarray([r["label"] for r in train]); rates=np.bincount(y,weights=w,minlength=3)/w.sum()
    pred={"M0":np.tile(rates,(len(valid),1))}; fits={"M0":{"base_rate":rates.tolist()}}
    for model,names in (("M1",CONTEXT_FEATURES),("M2",CONTEXT_FEATURES+FAST_FEATURES)):
        scaler=fit_scaler(train,names,w); fit=fit_multinomial(design(train,names,scaler),y,w)
        pred[model]=_softmax(design(valid,names,scaler),fit["coef"])
        fits[model]={"converged":fit["converged"],"iterations":fit["iterations"],"gradient_max":fit["gradient_max"],"scaler":scaler,"coef":fit["coef"].tolist()}
    return pred,fits


def summarize_rows(rows):
    c=Counter(r["trade_id"] for r in rows); a=np.asarray(list(c.values()))
    labels={r["trade_id"]:CLASSES[r["label"]] for r in rows}
    return {"rows":len(rows),"unique_trades":len(c),"class_counts":dict(Counter(labels.values())),
        "rows_per_trade":None if not len(a) else {"min":int(a.min()),"p25":float(np.quantile(a,.25)),"median":float(np.median(a)),"p75":float(np.quantile(a,.75)),"max":int(a.max()),"mean":float(a.mean())}}


def moving_block_samples(rows, seed=SEED, replicates=REPLICATES):
    times={r["trade_id"]:r["entry_ms"] for r in rows}; dates={t:datetime.fromtimestamp(ms/1000,timezone.utc).date() for t,ms in times.items()}
    lo=min(dates.values()); lo-=timedelta(days=lo.weekday()); hi=max(dates.values()); hi-=timedelta(days=hi.weekday())
    span=(hi-lo).days//7+1; at=defaultdict(list)
    for t,d in dates.items(): at[(d-lo).days//7].append(t)
    block_width=min(4,span); blocks=[range(i,i+block_width) for i in range(span-block_width+1)]; rng=np.random.Generator(np.random.PCG64(seed)); out=[]
    for _ in range(replicates):
        pos=[]
        while len(pos)<span: pos.extend(blocks[int(rng.integers(len(blocks)))])
        out.append([t for j in pos[:span] for t in sorted(at[j])])
    return out


def paired_uncertainty(rows, worse, better, samples=None):
    bw,lw=losses(rows,worse); bb,lb=losses(rows,better); samples=samples or moving_block_samples(rows); out={}
    for name,arr in (("brier",bw-bb),("log_loss",lw-lb)):
        vals=defaultdict(list)
        for r,v in zip(rows,arr): vals[r["trade_id"]].append(float(v))
        tm={t:float(np.mean(v)) for t,v in vals.items()}; reps=np.asarray([np.mean([tm[t] for t in s]) for s in samples])
        out[name]={"point":float(np.mean(list(tm.values()))),"ci95":[float(x) for x in np.quantile(reps,[.025,.975])],
            "replicate_sha256":hashlib.sha256(reps.astype("<f8").tobytes()).hexdigest()}
    return out


def _trade_mean(rows, values):
    d=defaultdict(list)
    for r,v in zip(rows,values): d[r["trade_id"]].append(float(v))
    return float(np.mean([np.mean(v) for v in d.values()]))


def stability(rows,p1,p2):
    b1,l1=losses(rows,p1); b2,l2=losses(rows,p2); elapsed=np.asarray([(r["state_ms"]-r["t0_ms"])/MINUTE for r in rows]); cuts=np.quantile(elapsed,[.25,.5,.75])
    groups={f"symbol:{s}":[i for i,r in enumerate(rows) if r["symbol"]==s] for s in SYMBOLS}
    groups|={f"duration_q{k+1}":np.flatnonzero(np.searchsorted(cuts,elapsed,side="right")==k).tolist() for k in range(4)}
    return {name:{"trades":len({rows[i]["trade_id"] for i in ix}),"brier_improvement":_trade_mean([rows[i] for i in ix],(b1-b2)[ix]),"log_loss_improvement":_trade_mean([rows[i] for i in ix],(l1-l2)[ix])} for name,ix in groups.items() if ix}


def evaluate(rows):
    allv=[]; preds={m:[] for m in ("M0","M1","M2")}; folds={}
    for f in FOLDS:
        train,valid=split_fold(rows,f); pp,fit=fit_predict(train,valid)
        folds[f]={"train":summarize_rows(train),"validation":summarize_rows(valid),"models":{m:metrics(valid,p) for m,p in pp.items()},"fit":fit}
        allv.extend(valid)
        for m in preds: preds[m].extend(pp[m].tolist())
    p={m:np.asarray(v) for m,v in preds.items()}; samples=moving_block_samples(allv)
    return {"folds":folds,"oof":{m:metrics(allv,p[m]) for m in p},"uncertainty":{"M1_minus_M0":paired_uncertainty(allv,p["M0"],p["M1"],samples),"M2_minus_M1":paired_uncertainty(allv,p["M1"],p["M2"],samples)},"stability":stability(allv,p["M1"],p["M2"]),"_rows":allv,"_pred":p}


def completeness(trades,rows,arch):
    tids=Counter(r["trade_id"] for r in rows); eligible=[t for t in trades if t["terminal"]!="AMBIGUOUS"]
    zero=[t for t in eligible if t["trade_id"] not in tids]; a=np.asarray(list(tids.values()))
    by_year={}
    for year in (2024,2025):
        source=[t for t in eligible if t["year"]==year]; present={r["trade_id"] for r in rows if r["year"]==year}; missing=[t for t in source if t["trade_id"] not in present]
        by_year[str(year)]={"non_ambiguous_trades":len(source),"trades_with_rows":len(present),"zero_row_trades":len(missing),"coverage":len(present)/len(source),"zero_rows_by_terminal":dict(Counter(t["terminal"] for t in missing))}
    return {"architecture":arch,"source_t2_trades":len(trades),"non_ambiguous_trades":len(eligible),"trades_with_rows":len(tids),"zero_row_trades":len(zero),
        "zero_rows_by_terminal":dict(Counter(t["terminal"] for t in zero)),"ambiguous_count":sum(t["terminal"]=="AMBIGUOUS" for t in trades),
        "missing_data_exclusions":0,"rows":len(rows),"coverage":len(tids)/len(eligible),"by_year":by_year,"rows_per_trade":None if not len(a) else {"min":int(a.min()),"p25":float(np.quantile(a,.25)),"median":float(np.median(a)),"p75":float(np.quantile(a,.75)),"max":int(a.max()),"mean":float(a.mean())},"class_counts":dict(Counter(t["terminal"] for t in eligible))}


def select(results, complete):
    eligible_arch=[a for a in ARCHITECTURES if complete[a]["eligible"]]
    comparison_pool=eligible_arch or list(ARCHITECTURES)
    bestb=min(results[a]["oof"]["M2"]["brier"] for a in comparison_pool); bestl=min(results[a]["oof"]["M2"]["log_loss"] for a in comparison_pool)
    checks={}
    for a,r in results.items():
        u=r["uncertainty"]["M2_minus_M1"]; st=r["stability"]
        useful=all(u[m]["point"]>0 and u[m]["ci95"][1]>=0 for m in ("brier","log_loss"))
        fold_ok=all(r["folds"][f]["models"]["M1"][m]>r["folds"][f]["models"]["M2"][m] for f in FOLDS for m in ("brier","log_loss"))
        broad=sum(st.get(f"symbol:{s}",{}).get("brier_improvement",-1)>=0 for s in SYMBOLS)>=4 and all(not(st[f"duration_q{i}"]["brier_improvement"]<0 and st[f"duration_q{i}"]["log_loss_improvement"]<0) for i in range(1,5))
        competitive=r["oof"]["M2"]["brier"]<=bestb+.002 and r["oof"]["M2"]["log_loss"]<=bestl+.01
        checks[a]={"useful_increment":useful,"both_folds":fold_ok,"breadth":broad,"competitive":competitive,"complete":complete[a]["eligible"]}
    candidates=[]
    for a in ("B","C","D"):
        better=(results["A"]["oof"]["M2"]["brier"]-results[a]["oof"]["M2"]["brier"]>=.002 and results["A"]["oof"]["M2"]["log_loss"]-results[a]["oof"]["M2"]["log_loss"]>=.01)
        checks[a]["materially_better_than_A"]=better
        if all(checks[a].values()): candidates.append(a)
    chosen=min(candidates,key=lambda a:(results[a]["oof"]["M2"]["brier"],results[a]["oof"]["M2"]["log_loss"],a)) if candidates else "A"
    return {"selected":chosen,"clear_winner":bool(candidates),"reason":"non_baseline_satisfies_all_prospective_rules" if candidates else "no_candidate_justifies_replacing_A; 5m/1m_is_adequate","checks":checks}


def dist(values):
    a=np.asarray(values,float); return {"n":len(a),"mean":float(a.mean()),"p10":float(np.quantile(a,.1)),"median":float(np.median(a)),"p90":float(np.quantile(a,.9)),"max":float(a.max())}


def descriptions(trades):
    def panel(items):
        return {"trades":len(items),"counts":dict(Counter(t["terminal"] for t in items)),"proportions":{k:sum(t["terminal"]==k for t in items)/len(items) for k in (*CLASSES,"AMBIGUOUS")},
            "time_to_event_minutes":dist([(t["terminal_ms"]-t["t0_ms"])/MINUTE for t in items]),"path_duration_minutes":dist([(t["p0_ms"]-t["t0_ms"])/MINUTE for t in items]),
            "terminal_close_distance_from_t2_peak":dist([t["terminal_close"]/t["p0_t2"]-1 for t in items])}
    return {"overall":panel(trades),"by_year":{str(y):panel([t for t in trades if t["year"]==y]) for y in (2024,2025)},"by_symbol":{s:panel([t for t in trades if t["symbol"]==s]) for s in SYMBOLS},"descriptive_only":True}


def artifact_hashes(directory):
    return {p.name:sha256_file(p) for p in sorted(directory.iterdir()) if p.is_file() and p.name!="reproducibility_hashes.json"}


def run(repo: Path):
    reject_2026(repo); contract=repo/"contracts/C10_post_t2_timescale_adequacy_CONTRACT.md"
    if sha256_file(contract)!=CONTRACT_SHA256: raise RuntimeError("C10 contract changed after freeze")
    artifact=repo/"artifacts/c10_post_t2_timescale_adequacy"; artifact.mkdir(parents=True,exist_ok=True)
    inputs=[repo/"artifacts/c7_full_population_t2_exit_overlay/population_manifest.json",repo/"artifacts/c4_sequential_exit_state/local/t2_snapshots.csv"]+[repo/f"data/normalized/c2_history/{s}_1m.csv.gz" for s in SYMBOLS]
    provenance={str(p.relative_to(repo)):sha256_file(p) for p in inputs}
    trades=load_c7_population(repo); rec=reconcile_authoritative(repo,trades)
    if rec["status"]!="PASS": raise RuntimeError("authoritative T2 reconciliation failed")
    markets={s:load_market(repo/f"data/normalized/c2_history/{s}_1m.csv.gz") for s in SYMBOLS}; bars={}
    for s in SYMBOLS:
        for m in (1,2,5,10,15): bars[(s,m)]=aggregate(markets[s],m)
    trades=[first_event(t,markets[t["symbol"]]) for t in trades]
    rows={a:snapshots(trades,markets,bars,a) for a in ARCHITECTURES}
    comp={a:completeness(trades,rows[a],a) for a in ARCHITECTURES}; base24=comp["A"]["by_year"]["2024"]["coverage"]
    for a in ARCHITECTURES:
        coverage24=comp[a]["by_year"]["2024"]["coverage"]
        comp[a]["eligible"]=coverage24>=.95 and coverage24>=base24-.02
    write_json(artifact/"provenance.json",{"contract_sha256":CONTRACT_SHA256,"inputs":provenance,"no_2026":True})
    write_json(artifact/"candidate_config.json",{"architectures":ARCHITECTURES,"baseline":"A","additional_candidates":False})
    write_json(artifact/"event_definition.json",{"peak":"frozen causal running peak at first T2","continuation":"P0_T2 * 1.005","deterioration":"(E + P0_T2) / 2","p0_precedence":True,"same_minute_both":"AMBIGUOUS"})
    write_json(artifact/"feature_schema.json",{"context":CONTEXT_FEATURES,"fast_state":FAST_FEATURES,"symbols":SYMBOL_FEATURES,"M0":"trade-weighted training prevalence","M1":CONTEXT_FEATURES+SYMBOL_FEATURES,"M2":CONTEXT_FEATURES+FAST_FEATURES+SYMBOL_FEATURES})
    write_json(artifact/"population_reconciliation.json",rec)
    write_json(artifact/"completeness_report.json",comp)
    write_json(artifact/"dataset_summary.json",{a:{"all":summarize_rows(rows[a]),"2024":summarize_rows([r for r in rows[a] if r["year"]==2024]),"2025":summarize_rows([r for r in rows[a] if r["year"]==2025])} for a in ARCHITECTURES})
    desc=descriptions(trades); write_json(artifact/"post_t2_descriptive_transitions.json",desc)
    results={a:evaluate([r for r in rows[a] if r["year"]==2024]) for a in ARCHITECTURES}
    serial={a:{k:v for k,v in r.items() if not k.startswith("_")} for a,r in results.items()}
    write_json(artifact/"architecture_model_metrics_2024.json",{a:{"folds":r["folds"],"oof":r["oof"]} for a,r in serial.items()})
    write_json(artifact/"paired_uncertainty_2024.json",{a:r["uncertainty"] for a,r in serial.items()})
    write_json(artifact/"fold_definitions_2024.json",{a:{f:{"bounds_ms":FOLDS[f],"train":r["folds"][f]["train"],"validation":r["folds"][f]["validation"]} for f in FOLDS} for a,r in serial.items()})
    decision=select(results,comp); write_json(artifact/"architecture_decision.json",decision)
    selected=decision["selected"]; train=[r for r in rows[selected] if r["year"]==2024]; valid=[r for r in rows[selected] if r["year"]==2025]
    pp,fits=fit_predict(train,valid); stab={"architecture":selected,"models":{m:metrics(valid,p) for m,p in pp.items()},"M2_vs_M1":paired_uncertainty(valid,pp["M1"],pp["M2"]),"fits":fits,"train":summarize_rows(train),"evaluation":summarize_rows(valid)}
    write_json(artifact/"stability_2025.json",stab)
    baseline=None
    if selected!="A":
        bt=[r for r in rows["A"] if r["year"]==2024]; bv=[r for r in rows["A"] if r["year"]==2025]; bp,bf=fit_predict(bt,bv)
        baseline={"architecture":"A","models":{m:metrics(bv,p) for m,p in bp.items()},"M2_vs_M1":paired_uncertainty(bv,bp["M1"],bp["M2"]),"fits":bf}
    write_json(artifact/"baseline_A_2025.json",baseline)
    final={"contract_sha256":CONTRACT_SHA256,"architectures":ARCHITECTURES,"population":rec,"events":desc["overall"],"completeness":comp,"metrics_2024":{a:r["oof"] for a,r in serial.items()},"incremental_2024":{a:r["uncertainty"]["M2_minus_M1"] for a,r in serial.items()},"stability_2024":{a:r["stability"] for a,r in serial.items()},"decision":decision,"stability_2025":stab,"baseline_A_2025":baseline,"scientific_interpretation":"Post-T2 state prognosis only; no action, economics, or exit simulation.","execution_practicality":"1m means completed 1m information only; any later policy requires subsequent execution with separately modeled latency/slippage.","confirmations":{"pnl_or_economics":False,"trading_policy":False,"c7_c8_c9_scientific_modification":False,"accessed_2026":False,"c11_started":False}}
    write_json(artifact/"final_summary.json",final)
    write_json(artifact/"run_manifest.json",{"version":"C10_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research"})
    write_json(artifact/"reproducibility_hashes.json",artifact_hashes(artifact))
    return final
