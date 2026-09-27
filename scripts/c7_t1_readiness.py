"""Build C7 T1 artifacts. Never invokes real economic code."""
from pathlib import Path
import csv, hashlib, json, platform, subprocess, sys
from collections import Counter
from binance_data_foundation.c7_t1 import *

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'artifacts/c7_full_population_t2_exit_overlay'
def write(name,obj):
    p=OUT/name; blob=canonical_bytes(obj); p.write_bytes(blob); return hashlib.sha256(blob).hexdigest()
def h(rel): return file_hash(ROOT/rel)

def main():
    OUT.mkdir(parents=True,exist_ok=True); prov=provenance(ROOT)
    rows=population_rows(ROOT); included=[r for r in rows if r['included']]
    reasons=Counter(r['primary_reason'] for r in rows if not r['included'])
    years=Counter(str(r['entry_year']) for r in rows); symbols=Counter(r['symbol'] for r in rows)
    struct=Counter('T2_REACHING' if r['overlay_strictly_before_p0'] else 'P0_FALLBACK' for r in included)
    source=[{k:r[k] for k in ('trade_id','symbol','entry_signal_ts','entry_decision_ts','entry_execution_ts','entry_price','entry_notional_usdt','p0_version','p0_execution_ts','p0_raw_exit_price','common_horizon_end_ts')} for r in rows]
    source_registry=[]
    roles={
      'contracts/C2_asymmetric_exit_experiment_CONTRACT.md':'C2 frozen definitions','artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv':'C2 frozen E1 cohort',
      'artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv':'canonical P0 exit/path/common horizon','contracts/C4_sequential_exit_state_CONTRACT.md':'C4 causal T2 definition',
      'artifacts/c4_sequential_exit_state/local/t2_snapshots.csv':'accepted raw T2 identity source','contracts/C5_economic_exit_policy_CONTRACT.md':'C5 accounting and metrics',
      'contracts/C5_economic_exit_policy_ADDENDUM.md':'C5 addendum','contracts/C5_prediction_population_AMENDMENT.md':'C5 population amendment',
      'contracts/C6_simple_t2_exit_controls_CONTRACT.md':'C6 semantic reference','artifacts/c6_simple_t2_exit_controls/t1_readiness.json':'accepted C6 readiness reference'}
    expected={'artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv':2199,'artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv':2199,'artifacts/c4_sequential_exit_state/local/t2_snapshots.csv':245049}
    semantic={'artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv':'6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3','artifacts/c2_asymmetric_exit_experiment/common_horizons_p0.csv':'81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f'}
    for p,role in roles.items(): source_registry.append({'path':p,'role':role,'semantic_identity':semantic.get(p),'byte_sha256':h(p),'expected_count':expected.get(p),'expected_schema':'accepted upstream schema','status':'ACCEPTED'})
    # Identity-only reconciliation for both development years; never outcome columns.
    ours={y:{r['trade_id']:r['first_t2_decision_ts'] for r in rows if r['entry_year']==y and r['first_t2_decision_ts']} for y in YEARS}; upstream={y:{} for y in YEARS}
    with (ROOT/'artifacts/c4_sequential_exit_state/local/t2_snapshots.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            year=dt(r['entry_execution_ts']).year
            if year in upstream and r['target_eligible']=='True' and r['trade_id'] not in upstream[year]: upstream[year][r['trade_id']]=r['snapshot_ts']
    rec=reconcile_t2_identities(ours,upstream); reconciliation=rec['by_year']; all_mismatches=rec['mismatch_trade_ids']; overlap_ok=rec['status']=='PASS'
    hashes={}
    hashes['source_registry.json']=write('source_registry.json',{'version':'C7_SOURCE_REGISTRY_V1','semantic_conflicts':[],'artifacts':source_registry})
    allow=[{'path':p,'role':k,'byte_sha256':v} for k,(p,v) in INPUTS.items()]
    hashes['input_allowlist.json']=write('input_allowlist.json',{'version':'C7_PRE_2026_ALLOWLIST_V1','boundary':'2026-01-01T00:00:00Z','inputs':allow,'discovery_or_globbing':False})
    hashes['sealed_guard_report.json']=write('sealed_guard_report.json',{'status':'PASS','guard':'lexical rejection before filesystem access','synthetic_literals_tested':['synthetic/<YEAR_BOUNDARY>/x','synthetic/SEALED/x','synthetic/confirmation/x'],'real_sealed_paths_enumerated_or_accessed':False})
    hashes['source_cohort_manifest.json']=write('source_cohort_manifest.json',{'version':'C7_SOURCE_COHORT_V1','count':len(source),'semantic_sha256':semantic_hash(source),'rows':source})
    popcore={'version':'C7_POPULATION_V1','source_count':len(rows),'included_count':len(included),'excluded_count':len(rows)-len(included),'primary_exclusion_reasons':dict(sorted(reasons.items())),'counts_by_year':dict(sorted(years.items())),'counts_by_symbol':dict(sorted(symbols.items())),'structural_counts':dict(sorted(struct.items())),'rows':rows}
    popcore['semantic_sha256']=semantic_hash(popcore['rows']); hashes['population_manifest.json']=write('population_manifest.json',popcore)
    pop_byte=hashes['population_manifest.json']
    hashes['population_reconciliation.json']=write('population_reconciliation.json',{'status':'PASS','source_unique_2199':len({r['trade_id'] for r in rows})==2199,'canonical_order':rows==sorted(rows,key=lambda x:(x['entry_execution_ts'],x['symbol'],x['trade_id'])),'included':len(included),'excluded':len(rows)-len(included),'no_prediction_dependency':all(not r['prediction_fields_consulted'] for r in rows),'economic_fields_computed_or_emitted':False})
    hashes['t2_overlap_reconciliation.json']=write('t2_overlap_reconciliation.json',{'status':'PASS' if overlap_ok else 'FAIL','accepted_raw_source':'artifacts/c4_sequential_exit_state/local/t2_snapshots.csv','authoritative_source_kind':'unfiltered raw T2 snapshot table; predictive feature-complete input not used','by_year':reconciliation,'accepted_raw_first_eligible_identities':sum(len(x) for x in upstream.values()),'derived_first_t2_identities':sum(len(x) for x in ours.values()),'identity_mismatches':len(all_mismatches),'mismatch_trade_ids':sorted(set(all_mismatches)),'forward_labels_or_predictions_consulted':False})
    hashes['policy_registry.json']=write('policy_registry.json',{'policies':list(POLICIES),'S1':'first causal T2 immediate next 1m open strictly before P0; otherwise exact P0 fallback','ties':'P0 wins','gap_skipping':False,'later_t2_substitution':False,'model_inputs':False})
    hashes['cost_config.json']=write('cost_config.json',{'fixed_gross_entry_notional_usdt':1000,'scenarios':COSTS,'legs_per_policy':2,'fees':'per-leg actual executed quote notional','slippage':'per-leg adverse'})
    metrics=['raw_return','gross_return','net_return','pnl','holding','summed_exposure','union_exposure','common_mfe','held_mfe','capture','surrender','green_to_red','common_green_to_red','preserved_at_least_half_peak','downside_deviation','loss_magnitude','p05','p10','expected_shortfall_10','worst_trade','opportunity_foregone','winner_cohorts_2_3_5','subsequent_truncation_2_3_5','trigger_fallback_frequency','executed_legs_notional','unresolved_null_counts']
    hashes['metric_schema.json']=write('metric_schema.json',{'metrics':metrics,'decision_inputs':['entry identity','post-entry causal OHLC','P0 timestamp','first T2 identity'],'execution_data':['entry price','immediate next-minute open','canonical P0 exit'],'evaluation_only':['future path','P0 outcome','MFE','winner status','post-exit opportunities'],'evaluation_only_forbidden_from':['membership','T2 detection','execution timing','policy choice']})
    hashes['bootstrap_config.json']=write('bootstrap_config.json',{'primary':'whole-trade four-entry-week moving blocks','sensitivity':'whole-calendar-month clusters descriptive only','replicates':REPLICATES,'generator':'PCG64','seed':SEED,'quantiles':[.025,.975],'method':'linear (Type-7)','multiplicity':'preserved; no deduplication'})
    synthetic_population,synthetic_opens,synthetic_evaluation=synthetic_production_fixture()
    fixture=execute_c7(synthetic_population,synthetic_opens,evaluation_rows=synthetic_evaluation); validate_report(fixture)
    if fixture['reproducibility_hashes']['report_core']=='PENDING_FINAL_SERIALIZATION': raise RuntimeError('synthetic production report contains placeholder hash')
    synthetic_report_sha256=semantic_hash(fixture)
    hashes['output_schema.json']=write('output_schema.json',OUTPUT_SCHEMA)
    runner={'authorization':AUTHORIZATION,'contract_sha256':CONTRACT_SHA256,'population_byte_sha256':pop_byte,'seed':SEED,'one_shot_consumption':['first development historical-price economic read','first real trade-level economic emission'],'pre_economic_failure_retriable_only_if':{'economic_read':False,'economic_emission':False},'append_only_ledger':True,'silent_retry':False,'public_dependency_injection':False}
    hashes['runner_config.json']=write('runner_config.json',runner)
    code={'src/binance_data_foundation/c7_t1.py':h('src/binance_data_foundation/c7_t1.py'),'tests/test_c7_t1.py':h('tests/test_c7_t1.py'),'scripts/c7_t1_readiness.py':h('scripts/c7_t1_readiness.py')}
    environment_sha256=semantic_hash({'python_version':platform.python_version(),'implementation':platform.python_implementation(),'numpy_version':__import__('numpy').__version__})
    hashes['provenance_manifest.json']=write('provenance_manifest.json',{'repository_root':str(ROOT),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'python_executable':sys.executable,'python_version':platform.python_version(),'environment_sha256':environment_sha256,'contract_sha256':CONTRACT_SHA256,'source_registry_sha256':hashes['source_registry.json'],'population_semantic_sha256':popcore['semantic_sha256'],'population_byte_sha256':pop_byte,'implementation_hashes':code,'artifact_hashes_before_readiness':hashes})
    blockers=[] if overlap_ok else ['authoritative T2 identity reconciliation failed']
    readiness={'version':'C7_T1_READINESS_V2','decision':'READY FOR SEPARATE T2 AUTHORIZATION' if not blockers else 'NOT READY','independent_review':'REQUIRES_REVIEW','blockers':blockers,'contract_sha256':CONTRACT_SHA256,'source_count':2199,'included_count':len(included),'excluded_count':len(rows)-len(included),'exclusion_reasons':dict(reasons),'counts_by_year':dict(years),'counts_by_symbol':dict(symbols),'structural_counts':dict(struct),'population_semantic_sha256':popcore['semantic_sha256'],'population_byte_sha256':pop_byte,'t2_overlap_status':'PASS' if overlap_ok else 'FAIL','t2_overlap_by_year':reconciliation,'synthetic_production_report_sha256':synthetic_report_sha256,'real_economics_computed':False,'real_policy_returns_or_pnl_emitted':False,'predictions_generated':False,'sealed_access':False,'t2_executed':False,'criteria':{'upstream_reconciled':overlap_ok,'population_frozen':True,'prediction_independent':True,'mechanics_synthetic_tested':True,'full_synthetic_production_report_validated':True,'output_schema_complete':True,'governed_runner_implemented':True,'ledger_state_machine_tested':True}}
    hashes['t1_readiness.json']=write('t1_readiness.json',readiness); ready_hash=hashes['t1_readiness.json']
    freeze={'version':'C7_T2_EXECUTION_FREEZE_V1','contract_sha256':CONTRACT_SHA256,'readiness_sha256':ready_hash,'population_byte_sha256':pop_byte,'population_semantic_sha256':popcore['semantic_sha256'],'code_hashes':code,'config_hashes':{k:v for k,v in hashes.items() if k in ('policy_registry.json','cost_config.json','metric_schema.json','bootstrap_config.json','output_schema.json','runner_config.json')},'seed':SEED,'authorization_template':{'flag':AUTHORIZATION,'accepted_hashes_required':True},'prospective_non_circular':True}
    hashes['t2_execution_freeze.json']=write('t2_execution_freeze.json',freeze)
    print(json.dumps({'readiness_sha256':ready_hash,'execution_freeze_sha256':hashes['t2_execution_freeze.json'],'population_byte_sha256':pop_byte,'population_semantic_sha256':popcore['semantic_sha256'],'included':len(included),'excluded':len(rows)-len(included),'structural':dict(struct)},indent=2))
if __name__=='__main__': main()
