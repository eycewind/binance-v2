import hashlib, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation import c13_warning_economics as c13
from binance_data_foundation import c13f_frozen_science_repair as c13f
from binance_data_foundation import c7_t1 as c7


class Market:
    def __init__(self, ms):
        self.ms=np.asarray(ms); n=len(ms)
        self.open=np.asarray([100+(i%6)*2 for i in range(n)],float)
        self.low=self.open-1; self.high=self.open+2; self.close=self.open+1
    def index(self,t):
        x=np.flatnonzero(self.ms==t); return int(x[0]) if len(x)==1 else None


def synthetic_case(monkeypatch):
    population=[]; trades=[]; binary=[]; scored=[]; probs=[]; markets={}; base=datetime(2024,1,1,tzinfo=timezone.utc)
    for si,symbol in enumerate(c13.SYMBOLS):
        all_ms=[]
        for week in range(5):
            start=int((base+timedelta(weeks=week,minutes=si*10)).timestamp()*1000); all_ms.extend(start+i*60_000 for i in range(6))
            tid=f"{symbol}-{week}"; entry=datetime.fromtimestamp(start/1000,tz=timezone.utc).isoformat(); p0=datetime.fromtimestamp((start+5*60_000)/1000,tz=timezone.utc).isoformat()
            population.append({"trade_id":tid,"symbol":symbol,"entry_year":2024,"entry_execution_ts":entry,"entry_price":100.,"p0_execution_ts":p0,"p0_raw_exit_price":110.})
            if week==0:
                trades.append({"trade_id":tid,"t0_ms":start+60_000,"terminal":"DETERIORATION_FIRST","terminal_ms":start+5*60_000,"deterioration_level":102.})
                for j,p in enumerate((.19,.10,.05)):
                    row={"trade_id":tid,"symbol":symbol,"year":2024,"state_ms":start+(j+1)*60_000,"terminal_ms":start+5*60_000,"t0_ms":start+60_000,"label":0}
                    binary.append(row);scored.append(row);probs.append(p)
        markets[symbol]=Market(all_ms)
    data={"trades":trades,"binary_rows":binary,"scored_rows":scored,"probabilities":np.asarray(probs)}
    return population,data,markets


def test_c13_seed_repair_and_c7_immutability():
    weeks={f"t{i}":(datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(weeks=i)).isoformat() for i in range(5)}
    assert len(c13.moving_block_samples(weeks,20261013,2000))==2000
    with pytest.raises(ValueError,match="C13"):c13.moving_block_samples(weeks,17,2000)
    assert len(c7.moving_block_samples(weeks,20260927,2000))==2000
    with pytest.raises(ValueError,match="frozen bootstrap"):c7.moving_block_samples(weeks,20261013,2000)


def test_full_synthetic_pipeline_documents_hash_schema_and_lifecycle(monkeypatch,tmp_path):
    population,data,markets=synthetic_case(monkeypatch); result=c13.execute(population,data,markets)
    assert result["trigger_counts"]=={"W1":5,"D2_CONTROL":5}
    ready={"original_c13_contract_sha256":"a"*64,"c13f_contract_sha256":"b"*64}
    docs=c13f.documents(ready,"C13F-SYNTHETIC",result,data,population);c13f.validate_documents(docs)
    hashes={}
    for name,value in docs.items():
        path=tmp_path/f"{name}.json";c13.write_json(path,value);hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(hashes)==len(c13f.DOCUMENTS) and all(len(x)==64 for x in hashes.values())
    lifecycle=["START","ECONOMIC_READ","ECONOMIC_EMISSION","PASS"]
    assert lifecycle==["START","ECONOMIC_READ","ECONOMIC_EMISSION","PASS"]
    assert result["bootstrap"]["seed"]==20261013 and result["bootstrap"]["replicates"]==2000
    assert set(result["bootstrap"]["contrasts"] )=={"W1-P0","D2_CONTROL-P0","W1-D2_CONTROL"}
    assert result["safety"] and result["breadth"] and result["classification"]


def test_history_gate_preserves_consumed_attempts():
    repo=Path(__file__).resolve().parents[1]; got=c13f.history(repo)
    assert got[c13f.C13_ATTEMPT]["economic_result_emitted"] is False
    assert got[c13f.C13R_ATTEMPT]["lifecycle"]==["START","ECONOMIC_READ","FAIL"]


def test_authorization_and_consumed_guard(monkeypatch,tmp_path):
    with pytest.raises(PermissionError):c13f.run_once(tmp_path,"NO")
    ledger=tmp_path/c13f.OUTPUT_REL/"attempt_ledger.jsonl";ledger.parent.mkdir(parents=True);ledger.write_text(json.dumps({"economic_read":True})+"\n")
    monkeypatch.setattr(c13f,"preflight",lambda repo:pytest.fail("must not preflight"))
    with pytest.raises(RuntimeError,match="consumed"):c13f.run_once(tmp_path,c13f.AUTHORIZATION)
