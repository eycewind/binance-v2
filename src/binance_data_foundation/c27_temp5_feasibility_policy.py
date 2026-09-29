"""C27 frozen TEMP5 feasibility gate (and guarded policy entry point)."""
from __future__ import annotations

import hashlib, json, math, os, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import c7_t1 as c7
from . import c8_timescale as c8
from . import c22_causal_decision_state as c22
from . import c23_incremental_c9_ablation as c23
from . import c24_probability_economic_ordering as c24

CONTRACT_SHA256 = "ff495e32f6d115080ae4a6fd09330ec14dfab6c9df9f9a0b00d517a5e2129b8a"
CONTRACT_REL = "contracts/C27_temp5_feasibility_policy_CONTRACT.md"
OUTPUT_REL = "artifacts/c27_temp5_feasibility_policy"
C25_REL = "artifacts/c25_q1_sequential_exit"
C26_REL = "artifacts/c26_q1_action_semantics"
TARGET = "DELTA_LIQ_5"
SEED = 20260929
REPLICATES = 2000
YEARS = (2024, 2025)
COSTS = ("C0", "C_BASE", "C_S5", "C_S10")


def reject_2026(path) -> None:
    if any("2026" in part for part in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C27 prohibits 2026 data or metadata access")


def sha(path: Path) -> str:
    reject_2026(path); h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def semantic_sha(value) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def load(path: Path):
    reject_2026(path); return json.loads(path.read_text())


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n")


def incremental_roundtrip_friction(entry_price: float, sell_price: float, buy_price: float, cost: str,
                                   notional: float=1000.) -> dict:
    """Actual extra sell/buy leg costs, in original-entry return units.

    The position is the quantity bought by the frozen entry convention.  Sale
    fees are deducted from sale proceeds.  The complete proceeds then fund one
    buy, including its fee, so no original quantity is restored for free.
    """
    if cost not in COSTS or notional != 1000.: raise ValueError("frozen cost/notional required")
    if min(entry_price,sell_price,buy_price) <= 0 or not all(map(math.isfinite,(entry_price,sell_price,buy_price))):
        raise ValueError("invalid execution price")
    fee=c7.COSTS[cost]["fee_rate"]; slip=c7.COSTS[cost]["slippage_rate"]
    original_qty=notional/(entry_price*(1+slip))
    sell_raw_notional=original_qty*sell_price
    sell_executed_notional=sell_raw_notional*(1-slip)
    sell_fee=sell_executed_notional*fee
    cash_after_sell=sell_executed_notional-sell_fee
    buy_executed_notional=cash_after_sell/(1+fee)
    buy_fee=buy_executed_notional*fee
    buy_execution_price=buy_price*(1+slip)
    reentry_qty=buy_executed_notional/buy_execution_price
    sell_slippage=sell_raw_notional-sell_executed_notional
    buy_slippage=reentry_qty*(buy_execution_price-buy_price)
    total=sell_slippage+sell_fee+buy_slippage+buy_fee
    return {"original_quantity":original_qty,"sell_raw_notional":sell_raw_notional,
            "sell_executed_notional":sell_executed_notional,"sell_slippage_quote":sell_slippage,
            "sell_fee_quote":sell_fee,"cash_after_sell":cash_after_sell,
            "buy_executed_notional":buy_executed_notional,"buy_fee_quote":buy_fee,
            "buy_slippage_quote":buy_slippage,"reentry_quantity":reentry_qty,
            "incremental_friction_quote":total,"incremental_friction_return":total/notional}


def feasibility_summary(rows, cost: str) -> dict:
    signed=np.asarray([-r[TARGET] for r in rows],float)
    gross=np.maximum(0,signed)
    friction=np.asarray([r["friction"][cost]["incremental_friction_return"] for r in rows],float)
    margin=signed-friction
    return {"trigger_count":len(rows),"mean_signed_avoidable_5":float(signed.mean()),
            "median_signed_avoidable_5":float(np.median(signed)),"mean_gross_avoidable_5":float(gross.mean()),
            "mean_incremental_friction":float(friction.mean()),"median_incremental_friction":float(np.median(friction)),
            "mean_feasibility_margin_5":float(margin.mean()),"median_feasibility_margin_5":float(np.median(margin)),
            "fraction_margin_gt_0":float((margin>0).mean()),"fraction_margin_eq_0":float((margin==0).mean()),
            "fraction_margin_lt_0":float((margin<0).mean())}


def bootstrap(rows, unit: str, seed: int=SEED, replicates: int=REPLICATES) -> dict:
    groups=defaultdict(list)
    for i,r in enumerate(rows): groups[r["trade_id"] if unit=="whole_trade" else r["entry_month"]].append(i)
    if unit not in ("whole_trade","calendar_month"): raise ValueError("unknown bootstrap unit")
    labels=sorted(groups); rng=np.random.Generator(np.random.PCG64(seed)); samples=[]
    for _ in range(replicates):
        ix=[i for j in rng.integers(len(labels),size=len(labels)) for i in groups[labels[int(j)]]]
        rr=[rows[i] for i in ix]; signed=np.asarray([-r[TARGET] for r in rr])
        friction=np.asarray([r["friction"]["C_BASE"]["incremental_friction_return"] for r in rr]); margin=signed-friction
        samples.append((signed.mean(),friction.mean(),margin.mean(),(margin>0).mean()))
    a=np.asarray(samples,float); names=("mean_signed_avoidable_5","mean_incremental_friction","mean_feasibility_margin_5","fraction_margin_gt_0")
    return {"unit":unit,"construction":"resample complete first-Q1 trades" if unit=="whole_trade" else "resample UTC entry-calendar-month blocks with whole attached trades",
            "seed":seed,"generator":"PCG64","replicates":replicates,"paired_quantities_preserved":True,
            "calendar_months":labels if unit=="calendar_month" else None,
            "intervals":{name:{"ci95":np.quantile(a[:,j],[.025,.975],method="linear").tolist(),
                               "replicate_sha256":hashlib.sha256(a[:,j].astype("<f8").tobytes()).hexdigest()} for j,name in enumerate(names)}}


def gate(yearly, whole, month) -> dict:
    predicates={}
    for y in YEARS:
        key=str(y); predicates[f"{y}_mean_margin_positive"]=yearly[key]["C_BASE"]["mean_feasibility_margin_5"]>0
        predicates[f"{y}_whole_trade_no_clear_negative"]=whole[key]["intervals"]["mean_feasibility_margin_5"]["ci95"][1]>=0
        predicates[f"{y}_calendar_month_no_clear_negative"]=month[key]["intervals"]["mean_feasibility_margin_5"]["ci95"][1]>=0
    passed=all(predicates.values())
    return {"FEASIBILITY_GATE":"PASS" if passed else "FAIL","classification":None if passed else "STOP_TEMPORARY_EXIT_CANDIDATE",
            "predicates":predicates,"stage_b_authorized":passed}


def run(repo: Path) -> dict:
    repo=repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV")!="binance-v2-research": raise RuntimeError("conda environment must be binance-v2-research")
    if sha(repo/CONTRACT_REL)!=CONTRACT_SHA256: raise RuntimeError("C27 contract changed after prospective freeze")
    out=repo/OUTPUT_REL; out.mkdir(parents=True,exist_ok=True); c25=repo/C25_REL; c26=repo/C26_REL
    ledger=load(c25/"policy_trade_ledger.json"); ledger_by={r["trade_id"]:r for r in ledger}
    c25_pop=load(c25/"population_reconciliation.json"); c25_q1=load(c25/"q1_boundary_reproduction.json")
    c25_full=load(c25/"full_population_results.json"); c26_pop=load(c26/"population_reconciliation.json")
    c26_first=load(c26/"first_q1_reconciliation.json"); c26_final=load(c26/"final_summary.json")
    rows,_=c22.build_causal_rows(repo); rows24=[r for r in rows if r["year"]==2024]; rows25=[r for r in rows if r["year"]==2025]
    train24,valid24=c8.split_fold(rows24,"fold_B"); datasets={2024:(train24,valid24),2025:(rows24,rows25)}
    first_by_year={}; boundaries={}; prediction_hashes={}
    trades={r["trade_id"]:r for r in c8.load_trades(repo)}
    for year,(training,valid) in datasets.items():
        pt=c23.fit_candidates(training,training,TARGET)[0]["S+C9"]["binary"]
        pv=c23.fit_candidates(training,valid,TARGET)[0]["S+C9"]["binary"]
        boundary=float(c24.bin_boundaries(pt,training)["cut_values"][0]); boundaries[str(year)]=boundary
        selected=[dict(r,probability=float(p),entry_month=datetime.fromtimestamp(r["entry_ms"]/1000,timezone.utc).strftime("%Y-%m")) for r,p in zip(valid,pv) if p<=boundary]
        first=[min((r for r in selected if r["trade_id"]==tid),key=lambda r:r["state_ms"]) for tid in sorted({r["trade_id"] for r in selected})]
        if boundary!=c25_q1[str(year)]["boundary"] or (len(selected),len(first))!=(c25_q1[str(year)]["validation_q1_snapshots"],c25_q1[str(year)]["validation_q1_trades"]): raise RuntimeError("INSUFFICIENT_Q1_RECONCILIATION")
        for r in first:
            frozen=ledger_by[r["trade_id"]]
            if frozen["first_q1_timestamp_ms"]!=r["state_ms"] or frozen["q1_probability"]!=r["probability"]: raise RuntimeError("INSUFFICIENT_TRIGGER_RECONCILIATION")
            tr=trades[r["trade_id"]]; r["friction"]={cost:incremental_roundtrip_friction(float(tr["entry_price"]),float(r["exit_now_price"]),float(r["forward_price_5"]),cost) for cost in COSTS}
        first_by_year[year]=first; prediction_hashes[str(year)]={"training":c24._prediction_sha(pt),"validation":c24._prediction_sha(pv)}
    first=[r for y in YEARS for r in first_by_year[y]]
    exact=(len(ledger)==len(ledger_by)==c25_pop["original_entries"]==2199 and c26_pop["status"]=="PASS" and c26_first["count"]==len(first)==698 and
           Counter(str(r["year"]) for r in first)==Counter({"2024":157,"2025":541}) and abs(sum(r["paired_pnl_difference"] for r in ledger)-c25_full["total_pnl_difference"])<1e-9)
    if not exact: raise RuntimeError("INSUFFICIENT_RECONCILIATION")
    yearly={str(y):{c:feasibility_summary(first_by_year[y],c) for c in COSTS} for y in YEARS}
    whole={str(y):bootstrap(first_by_year[y],"whole_trade") for y in YEARS}; month={str(y):bootstrap(first_by_year[y],"calendar_month") for y in YEARS}
    gate_result=gate(yearly,whole,month)
    reconciliation={"status":"PASS","original_trade_count":2199,"C25_exact":True,"C26_exact":True,"C25_total_pnl_difference":c25_full["total_pnl_difference"],"first_q1_count":698,"year_counts":{"2024":157,"2025":541}}
    trigger={"status":"PASS","count":698,"year_counts":{"2024":157,"2025":541},"one_trigger_per_trade":len({r["trade_id"] for r in first})==698,"timestamps_and_probabilities_exact_C25":True,"counts_exact_C26":True}
    definition={"signed_avoidable_5":"-frozen C_BASE DELTA_LIQ_5","gross_avoidable_5":"max(0, -DELTA_LIQ_5)","incremental_friction":"actual quote cost of the additional temporary sell and one re-entry, divided by original 1000 USDT; sale proceeds net of frozen slippage and fee fund the buy executed with frozen slippage and fee","margin":"signed_avoidable_5 - incremental_friction","actual_notional_each_leg":True,"later_P0_outcome_used":False}
    timing={"trigger":"first honest pre-T2 Q1 completed 5m state t","temporary_sell":"next valid 1m open strictly after t (open timestamp t)","duration_anchor":"state t, not sell fill","t_reassess":"earliest eligible completed 5m state >= t+5m","reentry":"one attempt at next valid 1m open after t_reassess","one_interruption_maximum":True,"lifecycle_precedence_while_flat":True}
    manifest={"version":"C27_RUN_V1","contract_sha256":CONTRACT_SHA256,"seed":SEED,"replicates":REPLICATES,"generator":"PCG64","python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"conda_environment":"binance-v2-research","stage_executed":"A_ONLY" if not gate_result["stage_b_authorized"] else "A"}
    provenance={"contract_sha256":CONTRACT_SHA256,"C25_reproducibility_hashes_sha256":sha(c25/"reproducibility_hashes.json"),"C26_reproducibility_hashes_sha256":sha(c26/"reproducibility_hashes.json"),"C25_ledger_sha256":sha(c25/"policy_trade_ledger.json"),"prediction_hashes":prediction_hashes,"target":TARGET,"no_2026_access":True}
    files={"run_manifest":manifest,"provenance":provenance,"population_reconciliation":reconciliation,"trigger_reconciliation":trigger,
           "q1_score_boundary_reconciliation":{"status":"PASS","target":TARGET,"model":"S+C9","boundaries":boundaries,"tie_convention":"probability <= frozen upper boundary"},
           "timing_contract":timing,"feasibility_definition":definition,"feasibility_2024":yearly["2024"],"feasibility_2025":yearly["2025"],
           "feasibility_cost_robustness":yearly,"feasibility_whole_trade_bootstrap":whole,"feasibility_calendar_month_bootstrap":month,"feasibility_gate":gate_result}
    if gate_result["stage_b_authorized"]:
        raise RuntimeError("Stage A passed; frozen Stage B implementation is required before execution")
    predicates={**gate_result,"no_tuning_or_search":True,"stage_b_executed":False,"C28_started":False}
    files["interpretation_predicates"]=predicates
    files["final_summary"]={"contract_sha256":CONTRACT_SHA256,"reconciliation":reconciliation,"first_q1_population":trigger,"timing_semantics":timing,"transaction_cost_definition":definition,"feasibility":yearly,"whole_trade_uncertainty":whole,"calendar_month_uncertainty":month,**gate_result,"reason":"C_BASE mean feasibility margin is not positive in both years; the frozen sell/re-entry friction exceeds mean signed five-minute avoidable value.","confirmations":{"stage_b_run":False,"tuning_or_search":False,"accessed_2026":False,"C28_started":False,"staged_committed_or_pushed":False}}
    for name,value in files.items(): write(out/f"{name}.json",value)
    hashes={p.name:sha(p) for p in sorted(out.glob("*.json")) if p.name!="reproducibility_hashes.json"}; write(out/"reproducibility_hashes.json",hashes)
    return files["final_summary"]|{"artifact_hashes":hashes}
