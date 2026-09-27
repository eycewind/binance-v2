from datetime import datetime,timedelta,timezone
from pathlib import Path
import copy, hashlib, inspect, json
import numpy as np
import pytest
from binance_data_foundation.c7_t1 import *
import binance_data_foundation.c7_t1 as c7

UTC=timezone.utc
def m(t,o,h,l,c): return Minute(t,o,h,l,c)
def path(closes,highs=None,start=None):
    start=start or datetime(2024,1,1,tzinfo=UTC); highs=highs or closes
    return [m(start+timedelta(minutes=i),c,highs[i],min(c,highs[i]),c) for i,c in enumerate(closes)]

def test_repository_provenance_and_source_identity():
    p=provenance(Path('.')); assert len(p)==7
    import csv
    with open(INPUTS['frozen_entries'][0]) as f: rows=list(csv.DictReader(f))
    assert len(rows)==len({r['trade_id'] for r in rows})==2199
    assert {r['symbol'] for r in rows}==set(SYMBOLS)
    assert {dt(r['entry_execution_ts']).year for r in rows}==set(YEARS)

def test_both_year_t2_reconciliation_and_mismatch_failure():
    good={2024:{str(i):str(i) for i in range(415)},2025:{str(i):str(i) for i in range(430)}}
    got=reconcile_t2_identities(good,good); assert got['status']=='PASS' and got['by_year']['2024']['authoritative_count']==415 and got['by_year']['2025']['authoritative_count']==430
    bad={y:dict(v) for y,v in good.items()}; bad[2025]['1']='different'
    assert reconcile_t2_identities(good,bad)['status']=='FAIL'

def test_seal_rejection_is_lexical_and_precedes_io(monkeypatch):
    for x in ('fake/2026/x','fake/SEALED/x','fake/confirmation_rows.csv'):
        with pytest.raises(PermissionError): reject_sealed_path(x)
    calls=[]; monkeypatch.setattr(Path,'open',lambda *a,**k:calls.append(1))
    with pytest.raises(PermissionError): file_hash(Path('synthetic/2026/file'))
    assert not calls

def test_t2_exact_boundaries_strict_d2_positive_r_and_first():
    t=datetime(2024,1,1,tzinfo=UTC); p0=t+timedelta(hours=1)
    # +1% peak qualifies; close above D2 and R>0.
    s=first_t2(t,100,p0,path([100,100,100,100,100.51],[100,100,101,100.8,100.7],t))
    assert s and s.decision_ts==t+timedelta(minutes=5) and s.gain==pytest.approx(.01)
    assert first_t2(t,100,p0,path([100,100,100,100,100.5],[100,100,101,100.8,100.7],t)) is None # equality D2
    assert first_t2(t,100,p0,path([100,100,100,100,100],[100,100,101,100.8,100.7],t)) is None # R not positive / D2
    q=path([100]*5+[101]*5,[100]*5+[101.1]*5,t); assert first_t2(t,100,p0,q).decision_ts==t+timedelta(minutes=10)

def test_no_future_peak_leakage_post_entry_completed_bar_and_gap():
    t=datetime(2024,1,1,0,2,tzinfo=UTC); p0=t+timedelta(hours=1)
    q=path([100,100,100.6,50,50],[100,100,101,200,200],t)
    assert first_t2(t,100,p0,q) is None # first aligned boundary has only 3 post-entry minutes
    g=path([100]*6,start=t); g.pop(2)
    with pytest.raises(ValueError,match='gap'): first_t2(t,100,p0,g)

def test_execution_next_open_strict_before_tie_gap_and_fallback_identity():
    t=datetime(2024,1,1,0,5,tzinfo=UTC); s=T2State(t,101,100.6,.01,.006,100.5)
    p0=t+timedelta(minutes=1); got=choose_exit(s,{t:[102]},p0,99); assert got['kind']=='T2_OVERLAY' and got['raw_exit_price']==102
    miss=choose_exit(s,{t+timedelta(minutes=1):[999]},p0,99); assert not miss['executable']
    tie=choose_exit(s,{t:[102]},t,99); assert tie['kind']=='P0_FALLBACK' and tie['raw_exit_price']==99
    fb=choose_exit(None,{},p0,99); assert fb['execution_ts']==p0 and fb['raw_exit_price']==99

@pytest.mark.parametrize('case',COSTS)
def test_costs_four_cases_actual_notional_separate_fields_two_legs(case):
    x=cost_ledger(100,110,case); assert x['executed_legs']==2 and x['entry_executed_notional']==1000
    assert x['exit_executed_notional']==pytest.approx(110*(1000/(100*(1+COSTS[case]['slippage_rate'])))*(1-COSTS[case]['slippage_rate']))
    assert {'entry_fee_quote','exit_fee_quote','entry_slippage_quote','exit_slippage_quote'}<=x.keys()

def test_bootstraps_multiplicity_seed_type7_and_month():
    base=datetime(2024,1,1,tzinfo=UTC); weeks={str(i):(base+timedelta(weeks=i)).isoformat() for i in range(12)}
    a=moving_block_samples(weeks); assert len(a)==2000 and a==moving_block_samples(weeks)
    assert any(len(x)!=len(set(x)) for x in a)
    with pytest.raises(ValueError,match='seed'): moving_block_samples(weeks,seed=1)
    times={str(i):(base+timedelta(days=35*i)).isoformat() for i in range(12)}; b=month_samples(times)
    assert len(b)==2000 and any(len(x)!=len(set(x)) for x in b)
    assert interval([0,1,2,3])==np.quantile([0,1,2,3],[.025,.975],method='linear').tolist()

def test_winner_availability_all_rules_and_unavailable_drives_insufficient():
    base=datetime(2024,1,1,tzinfo=UTC); weeks={str(i):(base+timedelta(weeks=i//5)).isoformat() for i in range(60)}
    samples=moving_block_samples(weeks); diffs={str(i):.01 for i in range(60)}
    assert winner_availability(set(diffs),weeks,samples,diffs)['available']
    bad=winner_availability(set(list(diffs)[:49]),weeks,samples,diffs); assert not bad['available']
    assert classify(available=False,point=1,week_ci=(.1,2),c_s5_point=1,safety_breach=False,breadth_label='BROAD')=='INSUFFICIENT'

def test_breadth_exact_half_and_labels():
    assert breadth(dict(zip(SYMBOLS,[1,1,1,-1,-1])),1)['label']=='BROAD' # largest exactly 1/3
    assert breadth(dict(zip(SYMBOLS,[3,1,1,-1,-1])),1)['label']=='CONCENTRATED'
    x=breadth(dict(zip(SYMBOLS,[1,1,-1,-1,-1])),0); assert x['label']=='NO_POSITIVE_POOLED_BREADTH'
    exact=breadth(dict(zip(SYMBOLS,[1,1,0.0,-.1,-.1])),1); assert exact['largest_positive_contribution_share']==.5

def test_all_interpretations_precedence_and_ignored_diagnostics():
    kw=dict(available=True,point=1,week_ci=(.1,2),c_s5_point=1,safety_breach=False,breadth_label='BROAD')
    assert classify(**kw)=='SUPPORTS_FULL_POPULATION_T2_OVERLAY'
    assert classify(**{**kw,'point':0})=='COUNTS_AGAINST_FULL_POPULATION_T2_OVERLAY'
    assert classify(**{**kw,'week_ci':(-1,2)})=='MIXED'
    assert classify(**{**kw,'safety_breach':True})=='COUNTS_AGAINST_FULL_POPULATION_T2_OVERLAY'
    assert classify(**{**kw,'c_s5_point':0})=='MIXED'
    assert classify(**kw,month_ci=(-9,-8),c0=-1,c_s10=-1,year=-1,symbol=-1)==classify(**kw)

def test_complete_output_schema_deterministic():
    a=synthetic_report(); validate_report(a); assert canonical_bytes(a)==canonical_bytes(synthetic_report())
    assert len(a)==len(OUTPUT_ARTIFACTS)
    b=dict(a); b.pop('winner_truncation_report')
    with pytest.raises(ValueError): validate_report(b)
    c=synthetic_report(); del c['canonical_paired_trade_table']['rows'][0]['net_return']
    with pytest.raises(ValueError,match='net_return'): validate_report(c)

@pytest.mark.parametrize('breach',['expected_shortfall','green_to_red','preserved_half','winner_cohort'])
def test_each_formal_safety_breach_counts_against(breach):
    assert classify(available=True,point=.01,week_ci=(.001,.02),c_s5_point=.005,safety_breach=True,breadth_label='BROAD',breach=breach)=='COUNTS_AGAINST_FULL_POPULATION_T2_OVERLAY'

def test_classification_complete_precedence_cases():
    base=dict(point=.01,week_ci=(.001,.02),c_s5_point=.005,safety_breach=False,breadth_label='BROAD')
    assert classify(available=True,**base)=='SUPPORTS_FULL_POPULATION_T2_OVERLAY'
    assert classify(available=True,**{**base,'point':0})=='COUNTS_AGAINST_FULL_POPULATION_T2_OVERLAY'
    assert classify(available=False,**base)=='INSUFFICIENT'
    assert classify(available=True,**{**base,'week_ci':(-.01,.02)})=='MIXED'

def test_duplicate_source_minute_rejected():
    rows=[{'open_time_ms':'1','open':'1','high':'1','low':'1','close':'1'}]*2
    with pytest.raises(RuntimeError,match='duplicate source minute'): unique_minute_rows(rows,'BTCUSDT')

def synthetic_population():
    return [
      {'trade_id':'a','symbol':'BTCUSDT','entry_year':2024,'entry_execution_ts':'2024-01-01T00:00:00+00:00','entry_price':'100','p0_execution_ts':'2024-01-01T01:00:00+00:00','p0_raw_exit_price':'101','first_t2_decision_ts':None,'overlay_strictly_before_p0':False,'included':True},
      {'trade_id':'b','symbol':'ETHUSDT','entry_year':2024,'entry_execution_ts':'2024-01-01T00:00:00+00:00','entry_price':'100','p0_execution_ts':'2024-01-01T01:00:00+00:00','p0_raw_exit_price':'99','first_t2_decision_ts':'2024-01-01T00:30:00+00:00','overlay_strictly_before_p0':True,'included':True}]

def production_shaped_fixture():
    population=[]; opens={}; evaluation=[]; base=datetime(2024,1,1,tzinfo=UTC)
    for i in range(60):
        entry=base+timedelta(weeks=i); p0=entry+timedelta(hours=2); trigger=i%3==0; tie=i==1; t2=entry+timedelta(hours=1) if trigger else p0 if tie else None
        tid=f't{i:02d}'; symbol=SYMBOLS[i%len(SYMBOLS)]
        population.append({'trade_id':tid,'symbol':symbol,'entry_year':entry.year,'entry_execution_ts':entry.isoformat(),'entry_price':'100','p0_execution_ts':p0.isoformat(),'p0_raw_exit_price':'106','first_t2_decision_ts':t2.isoformat() if t2 else None,'overlay_strictly_before_p0':trigger,'p0_precedence_tie':tie,'included':True})
        if trigger: opens[(symbol,t2.isoformat())]=104+i/1000
        for policy in POLICIES:
            overlay=policy=='S1_FULL_T2_OVERLAY' and trigger
            evaluation.append({'trade_id':tid,'policy_id':policy,'trigger_status':'T2_REACHING' if overlay else 'P0_FALLBACK' if policy=='S1_FULL_T2_OVERLAY' else 'CANONICAL_P0','common_mfe':.08,'held_mfe':.07 if overlay else .08,'capture_fraction':.5 if overlay else .75,'common_capture_gap':.04 if overlay else .02,'held_peak_surrender':.03 if overlay else .02,'positive_mfe_surrendered_fraction':.5 if overlay else .25,'green_to_red':False,'common_green_to_red':False,'preserved_at_least_half_peak':True,'downside_value':-.01,'p0_winner_2':True,'p0_winner_3':True,'p0_winner_5':True,'truncation_2':overlay,'truncation_3':overlay,'truncation_5':False,'opportunity_foregone':.01 if overlay else 0.,'valid_denominator':True,'null_reason':None})
    return population,opens,evaluation

@pytest.fixture(scope='module')
def full_synthetic_report():
    population,opens,evaluation=production_shaped_fixture()
    report=execute_c7(population,opens,evaluation_rows=evaluation)
    validate_report(report)
    return report

def test_synthetic_production_executor_and_fallback_exact_identity():
    report=execute_c7(synthetic_population(),{('ETHUSDT','2024-01-01T00:30:00+00:00'):102})
    validate_report(report); rows=report['canonical_paired_trade_table']['rows']
    fb=[r for r in rows if r['trade_id']=='a']
    assert len(fb)==8 and report['fallback_audit']['identity_verified']
    enforce_fallback_identity(rows)

def test_fallback_mismatch_fails():
    report=execute_c7(synthetic_population(),{('ETHUSDT','2024-01-01T00:30:00+00:00'):102}); rows=report['canonical_paired_trade_table']['rows']
    next(r for r in rows if r['trade_id']=='a' and r['policy_id']=='S1_FULL_T2_OVERLAY')['net_return']+=1
    with pytest.raises(RuntimeError,match='fallback economic identity mismatch'): enforce_fallback_identity(rows)

@pytest.mark.parametrize('field',['decision_ts','execution_ts','raw_exit_price','executed_quantity','exit_executed_notional','entry_fee','exit_fee','entry_slippage','exit_slippage','total_transaction_cost','raw_return','gross_return','net_return','gross_pnl_usdt','net_pnl_usdt','holding_seconds'])
def test_each_fallback_trade_invariant_fails_closed(field):
    report=execute_c7(synthetic_population(),{('ETHUSDT','2024-01-01T00:30:00+00:00'):102}); rows=copy.deepcopy(report['canonical_paired_trade_table']['rows'])
    row=next(r for r in rows if r['trade_id']=='a' and r['policy_id']=='S1_FULL_T2_OVERLAY' and r['cost_scenario']=='C_BASE'); row[field]=row[field]+'x' if isinstance(row[field],str) else row[field]+1
    with pytest.raises(RuntimeError,match='fallback economic identity mismatch'): enforce_fallback_identity(rows)

@pytest.mark.parametrize('field',['executed_quantity','executed_notional','fee_quote','slippage_quote'])
def test_each_fallback_leg_invariant_fails_closed(field):
    report=execute_c7(synthetic_population(),{('ETHUSDT','2024-01-01T00:30:00+00:00'):102}); legs=copy.deepcopy(report['leg_level_cost_table']['rows']); rows=report['canonical_paired_trade_table']['rows']
    leg=next(r for r in legs if r['trade_id']=='a' and r['policy_id']=='S1_FULL_T2_OVERLAY' and r['cost_scenario']=='C_BASE' and r['leg']=='EXIT'); leg[field]+=1
    with pytest.raises(RuntimeError,match='fallback leg identity mismatch'): enforce_fallback_leg_identity(rows,legs)

def test_fallback_evaluation_invariant_fails_closed():
    population,opens,evaluation=production_shaped_fixture(); report=execute_c7(population,opens,evaluation_rows=evaluation); rows=report['canonical_paired_trade_table']['rows']; damaged=copy.deepcopy(evaluation)
    next(r for r in damaged if r['trade_id']=='t02' and r['policy_id']=='S1_FULL_T2_OVERLAY')['common_mfe']+=1
    with pytest.raises(RuntimeError,match='fallback evaluation identity mismatch'): enforce_fallback_identity(rows,damaged)

def test_full_synthetic_production_report_is_complete(full_synthetic_report):
    r=full_synthetic_report; assert {x['policy_id'] for x in r['canonical_paired_trade_table']['rows']}==set(POLICIES); assert {x['cost_scenario'] for x in r['canonical_paired_trade_table']['rows']}==set(COSTS)
    assert r['trigger_fallback_rates']['trigger_count'] and r['trigger_fallback_rates']['fallback_count']; assert r['p0_precedence_tie_audit']['count']==1
    assert r['week_bootstrap_samples_multiplicities_replicates']['candidate_blocks']; assert isinstance(r['week_bootstrap_samples_multiplicities_replicates']['candidate_blocks'],list)
    assert all(r[f'report_{x}']['population'] for x in (*YEARS,*SYMBOLS)); assert r['reproducibility_hashes']['report_core']!='PENDING_FINAL_SERIALIZATION'

def test_every_top_level_panel_is_required(full_synthetic_report):
    for panel in OUTPUT_ARTIFACTS:
        damaged=copy.deepcopy(full_synthetic_report); damaged.pop(panel)
        with pytest.raises(ValueError,match='missing output sections'): validate_report(damaged)

@pytest.mark.parametrize(('panel','field'),[
 ('denominator_null_ledger','rows'),('p0_precedence_tie_audit','trade_ids'),('t2_non_t2_decomposition','pnl_contributions'),('complete_metrics','valid_denominators'),('week_bootstrap_samples_multiplicities_replicates','candidate_blocks'),('month_bootstrap_sensitivity','replicate_vectors'),('report_2024','path_capture'),('report_2025','safety'),('report_BTCUSDT','winner_truncation'),('equal_weight_symbol_report','metrics'),('safety_report','winner_cohorts'),('winner_truncation_report','truncation_rates'),('summed_union_exposure','union_exposure'),('executed_legs_notional','exit_notional'),('final_classification_predicates','safety_breach'),('reproducibility_hashes','report_core')])
def test_representative_nested_fields_are_required(full_synthetic_report,panel,field):
    damaged=copy.deepcopy(full_synthetic_report); del damaged[panel][field]
    with pytest.raises(ValueError,match='missing fields'): validate_report(damaged)

def test_wrong_candidate_blocks_type_rejected(full_synthetic_report):
    damaged=copy.deepcopy(full_synthetic_report); damaged['week_bootstrap_samples_multiplicities_replicates']['candidate_blocks']='not-an-array'
    with pytest.raises(ValueError,match='candidate_blocks must be array'): validate_report(damaged)

def event(i,k='START',read=False,emit=False):
    return {'attempt_id':i,'event':k,'timestamp':'2040-01-01T00:00:00Z','stage':'T2','purpose':'production','authorization_reference':'x','contract_sha256':CONTRACT_SHA256,'readiness_sha256':'r','execution_freeze_sha256':'f','source_hashes':{},'population_sha256':'p','code_sha256':'c','config_sha256':'g','environment_sha256':'e','output_schema_sha256':'o','seed':SEED,'status':k,'failure_reason':'synthetic' if k in ('FAIL','PREFLIGHT_FAIL') else None,'economic_read':read,'economic_emission':emit,'output_hashes':{'x':'h'} if k=='PASS' else {}}

def test_preflight_failure_retry_requires_all_identical_identities(tmp_path):
    p=tmp_path/'ledger.jsonl'; append_attempt(p,event('pre','PREFLIGHT_FAIL'))
    append_attempt(p,event('same')); append_attempt(p,event('same','FAIL'))
    assert [json.loads(x)['event'] for x in p.read_text().splitlines()]==['PREFLIGHT_FAIL','START','FAIL']

@pytest.mark.parametrize(('field','value'),[('population_sha256','changed'),('code_sha256','changed'),('config_sha256','changed'),('output_schema_sha256','changed'),('seed',SEED+1)])
def test_preflight_failure_changed_identity_rejected_non_economic(tmp_path,field,value):
    p=tmp_path/'ledger.jsonl'; append_attempt(p,event('pre','PREFLIGHT_FAIL')); changed=event('retry'); changed[field]=value
    with pytest.raises(RuntimeError,match='identities changed'): append_attempt(p,changed)
    records=[json.loads(x) for x in p.read_text().splitlines()]
    assert len(records)==1 and records[0]['economic_read'] is False and records[0]['economic_emission'] is False

def test_ledger_start_terminal_preconsume_retry_and_consumed_no_retry(tmp_path):
    p=tmp_path/'ledger.jsonl'; append_attempt(p,event('a')); append_attempt(p,event('a','FAIL'))
    append_attempt(p,event('b')); append_attempt(p,event('b','FAIL',read=True))
    with pytest.raises(RuntimeError,match='consumed'): append_attempt(p,event('c'))
    assert [json.loads(x)['event'] for x in p.read_text().splitlines()]==['START','FAIL','START','FAIL']

def test_ledger_transitions_and_retry_identity_rules(tmp_path):
    p=tmp_path/'ledger.jsonl'; append_attempt(p,event('a')); append_attempt(p,event('a','FAIL'))
    changed=event('b'); changed['seed']=SEED+1
    with pytest.raises(RuntimeError,match='identities changed'): append_attempt(p,changed)
    append_attempt(p,event('b')); append_attempt(p,event('b','ECONOMIC_READ',read=True)); append_attempt(p,event('b','ECONOMIC_EMISSION',read=True,emit=True)); append_attempt(p,event('b','PASS',read=True,emit=True))
    events=[json.loads(x)['event'] for x in p.read_text().splitlines()]
    assert events==['START','FAIL','START','ECONOMIC_READ','ECONOMIC_EMISSION','PASS']
    with pytest.raises(RuntimeError,match='consumed'): append_attempt(p,event('c'))

def test_governance_public_api_no_injection_and_authorization(tmp_path):
    assert set(inspect.signature(run_c7_t2_once).parameters)=={'repo','ledger_path','output_dir','authorization'}
    with pytest.raises(PermissionError): run_c7_t2_once(repo=tmp_path,ledger_path=tmp_path/'l',output_dir=tmp_path/'o',authorization='NO')

def test_unauthorized_rejected_before_preflight(monkeypatch,tmp_path):
    called=[]; monkeypatch.setattr(c7,'_freeze_context',lambda repo:called.append(repo))
    with pytest.raises(PermissionError): run_c7_t2_once(repo=tmp_path,ledger_path=tmp_path/'ledger',output_dir=tmp_path/'out',authorization='NO')
    assert called==[] and not (tmp_path/'ledger').exists()

def test_authorized_preflight_failure_is_ledgered_non_economic(tmp_path):
    ledger=tmp_path/'ledger.jsonl'
    with pytest.raises(Exception): run_c7_t2_once(repo=tmp_path,ledger_path=ledger,output_dir=tmp_path/'out',authorization=AUTHORIZATION)
    events=[json.loads(x) for x in ledger.read_text().splitlines()]
    assert len(events)==1 and events[0]['event']=='PREFLIGHT_FAIL' and events[0]['status']=='PREFLIGHT_FAIL'
    assert events[0]['economic_read'] is False and events[0]['economic_emission'] is False and events[0]['failure_reason']

def test_current_authoritative_readiness_record_and_history_are_concrete():
    ledger=Path('artifacts/c7_full_population_t2_exit_overlay/attempt_ledger.jsonl')
    lines=ledger.read_text().splitlines(); assert len(lines)>=3
    assert hashlib.sha256(('\n'.join(lines[:2])+'\n').encode()).hexdigest()=='e67c96e391fa3cdc3d51df533292055a588734555e8e45488bb6715d92b1b91d'
    identity=authoritative_readiness_identity(Path('.'),ledger); current=json.loads(lines[-1])
    assert all(identity[k]==current[k] for k in IDENTITY_FIELDS)
    assert all(v not in ('UNVERIFIED','T1_BUNDLE_RECORDED_IN_PROVENANCE_MANIFEST') for k,v in identity.items() if k!='source_hashes')
    assert current['economic_read'] is False and current['economic_emission'] is False

def test_stale_readiness_identity_cannot_authorize_t2(tmp_path):
    source=Path('artifacts/c7_full_population_t2_exit_overlay/attempt_ledger.jsonl')
    records=[json.loads(x) for x in source.read_text().splitlines()]
    records[-1]['readiness_sha256']='0'*64
    ledger=tmp_path/'ledger.jsonl'; ledger.write_text(''.join(json.dumps(x,sort_keys=True,separators=(',',':'))+'\n' for x in records))
    with pytest.raises(RuntimeError,match='stale'): authoritative_readiness_identity(Path('.'),ledger)

def _runner_harness(monkeypatch,tmp_path,fail=False):
    rows=[]; base=datetime(2024,1,1,tzinfo=UTC)
    for i,symbol in enumerate(SYMBOLS):
        entry=base+timedelta(days=i); p0=entry+timedelta(hours=1)
        rows.append({'trade_id':str(i),'symbol':symbol,'entry_execution_ts':entry.isoformat(),'p0_execution_ts':p0.isoformat(),'first_t2_decision_ts':None,'overlay_strictly_before_p0':False})
    freeze={'readiness_sha256':'r','population_byte_sha256':'p','code_hashes':{},'config_hashes':{'output_schema.json':'o'}}; pop={'rows':rows}; ledger=tmp_path/'ledger.jsonl'; out=tmp_path/'out'; basepath=tmp_path/'artifacts/c7_full_population_t2_exit_overlay'; basepath.mkdir(parents=True); (basepath/'provenance_manifest.json').write_text(json.dumps({'environment_sha256':'e'}))
    monkeypatch.setattr(c7,'_freeze_context',lambda repo:(freeze,pop,OUTPUT_SCHEMA)); monkeypatch.setattr(c7,'provenance',lambda repo:{})
    identity={'contract_sha256':CONTRACT_SHA256,'readiness_sha256':'r','execution_freeze_sha256':'f','source_hashes':{},'population_sha256':'p','code_sha256':semantic_hash({}),'config_sha256':semantic_hash({'output_schema.json':'o'}),'environment_sha256':'e','output_schema_sha256':'o','seed':SEED}
    monkeypatch.setattr(c7,'authoritative_readiness_identity',lambda repo,ledger_path:identity)
    monkeypatch.setattr(c7,'file_hash',lambda path:'f' if path.name=='t2_execution_freeze.json' else hashlib.sha256(path.read_bytes()).hexdigest())
    order=[]; real_append=c7.append_attempt
    def observed_append(path,event): order.append(event['event']); return real_append(path,event)
    monkeypatch.setattr(c7,'append_attempt',observed_append)
    import io
    def fake_gzip(*args,**kwargs): assert 'ECONOMIC_READ' in order; order.append('PRICE_ACCESS'); return io.StringIO('open_time_ms,open,high,low,close\n')
    monkeypatch.setattr(c7.gzip,'open',fake_gzip)
    def fake_execute(*args,**kwargs):
        assert 'PRICE_ACCESS' in order
        if fail: raise RuntimeError('synthetic executor failure')
        return synthetic_report()
    monkeypatch.setattr(c7,'execute_c7',fake_execute)
    real_write=Path.write_bytes
    def observed_write(path,data):
        if path.suffix=='.json': assert 'ECONOMIC_EMISSION' in order; order.append('SERIALIZE')
        return real_write(path,data)
    monkeypatch.setattr(Path,'write_bytes',observed_write)
    return ledger,out,order

def test_runner_lifecycle_order_and_actual_pass_hashes(monkeypatch,tmp_path):
    ledger,out,order=_runner_harness(monkeypatch,tmp_path)
    run_c7_t2_once(repo=tmp_path,ledger_path=ledger,output_dir=out,authorization=AUTHORIZATION)
    events=[json.loads(x) for x in ledger.read_text().splitlines()]; assert [x['event'] for x in events]==['START','ECONOMIC_READ','ECONOMIC_EMISSION','PASS']
    assert order.index('START')<order.index('ECONOMIC_READ')<order.index('PRICE_ACCESS')<order.index('ECONOMIC_EMISSION')<order.index('SERIALIZE')<order.index('PASS')
    assert events[-1]['output_hashes'] and all(len(x)==64 for x in events[-1]['output_hashes'].values())
    auth=json.loads((out/'authorization.json').read_text()); assert auth['output_hashes'] and 'canonical_paired_trade_table.json' in auth['output_hashes']

def test_failure_after_start_has_exactly_one_fail_and_consumes(monkeypatch,tmp_path):
    ledger,out,order=_runner_harness(monkeypatch,tmp_path,fail=True)
    with pytest.raises(RuntimeError,match='synthetic executor failure'): run_c7_t2_once(repo=tmp_path,ledger_path=ledger,output_dir=out,authorization=AUTHORIZATION)
    events=[json.loads(x) for x in ledger.read_text().splitlines()]; assert [x['event'] for x in events]==['START','ECONOMIC_READ','FAIL']; assert sum(x['event']=='FAIL' for x in events)==1
    with pytest.raises(RuntimeError,match='consumed'): append_attempt(ledger,event('another'))

def test_prediction_fields_structurally_absent_from_decision_interfaces():
    for fn in (first_t2,choose_exit):
        assert not ({'prediction','score','outcome','winner','mfe'} & set(inspect.signature(fn).parameters))
