from __future__ import annotations
import hashlib,json,os,sys
from datetime import date,timedelta
from pathlib import Path
import numpy as np,pytest
from binance_data_foundation import c4_modeling
from binance_data_foundation.c4_locked_eval import (OUTPUT_FILES,evaluate_locked_2025,load_locked_checkpoint,locked_evaluation_config,predict_feature_rows,validate_readiness)

def _write(path,value):path.write_text(json.dumps(value,sort_keys=True),encoding="utf-8")
def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def _lock(art): (art/"c4_2024_freeze.sha256").write_text(_sha(art/"c4_2024_freeze.json")+"  c4_2024_freeze.json\n")
def _checkpoint(tmp_path):
    repo=tmp_path/"repo";art=tmp_path/"art";repo.mkdir(parents=True);art.mkdir()
    source=repo/"source.py";source.write_text("accepted\n")
    columns={"G0":["x"],"G1":["x"],"P1":["x"]};schema={"targets":{"T1":columns,"T2":columns}}
    prep={f"{t}_{m}":{"columns":["x"],"parameters":{"x":{"median":0.,"iqr":2.,"excluded_zero_iqr":False}}} for t in ("T1","T2") for m in ("G0","G1","P1")}
    fit={"C":1.,"columns":["x"],"coefficients":[[0.,0.],[1.,-1.]],"converged":True}
    models={t:{"models":{"B0":{"probabilities":[.2,.3,.5]},"G0":fit,"G1":fit,"P1":fit}} for t in ("T1","T2")}
    definitions={"T1":"C4_T1_CONT_PLUS1_VS_REV_MINUS075_H60_V1","T2":"C4_T2_GIVEBACK50_VS_NEWPEAK050_H60_V1"};snapshot={"target_definition_versions":definitions}
    classes={"T1":["continuation","adverse_reversal","no_event_60m"],"T2":["renewed_peak","substantial_giveback","no_event_60m"]};cal={f"{t}_fold_B":{c:{"training_cut_points":[.2,.4,.6,.8]} for c in classes[t]} for t in classes}
    for name,obj in (("feature_schema.json",schema),("final_preprocessing_2024.json",prep),("final_models_2024.json",models),("snapshot_schema.json",snapshot),("calibration_2024.json",cal)):_write(art/name,obj)
    material={n:_sha(art/n) for n in ("feature_schema.json","final_preprocessing_2024.json","final_models_2024.json","snapshot_schema.json","calibration_2024.json")};config=locked_evaluation_config(cal)
    freeze={"version":"C4_2024_FREEZE_V3","seals":{"2025_predictive_scoring":"NOT PERFORMED","2026_access":False,"economic_or_stage_B_analysis":False},"material_artifact_hashes":material,"required_acceptance_artifacts":sorted(material),"source_test_hashes":{"source.py":_sha(source)},"required_source_dependencies":["source.py"],"environment":{"conda_env":os.environ.get("CONDA_DEFAULT_ENV"),"python_version":sys.version.split()[0],"numpy_version":np.__version__},"target_definitions":definitions,"class_order":classes,"locked_2025_evaluation":config,"locked_2025_evaluation_sha256":hashlib.sha256(json.dumps(config,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest(),"interpretation":{"target_decisions":{"T1":{"fold_point_deltas":[-1,-1,-1,-1]},"T2":{"fold_point_deltas":[-1,-1,-1,-1]}}}}
    _write(art/"c4_2024_freeze.json",freeze);_lock(art);return repo,art
def _mutate_freeze(art,fn):
    f=json.loads((art/"c4_2024_freeze.json").read_text());fn(f);_write(art/"c4_2024_freeze.json",f);_lock(art)

def test_readiness_consumes_no_rows(tmp_path):
    repo,art=_checkpoint(tmp_path);got=validate_readiness(repo,art);assert got["predictive_rows_consumed"]==0 and not got["predictive_scoring_performed"] and set(got["required_outputs"])==set(OUTPUT_FILES)
def test_external_lock_and_freeze_content_mismatch(tmp_path):
    repo,art=_checkpoint(tmp_path);(art/"c4_2024_freeze.sha256").write_text("0"*64+"  c4_2024_freeze.json\n")
    with pytest.raises(RuntimeError,match="freeze hash mismatch"):load_locked_checkpoint(repo,art)
    _lock(art);(art/"c4_2024_freeze.json").write_text("{}")
    with pytest.raises(RuntimeError,match="freeze hash mismatch"):load_locked_checkpoint(repo,art)
@pytest.mark.parametrize("name",["final_models_2024.json","final_preprocessing_2024.json","feature_schema.json"])
def test_material_mismatch_guards(tmp_path,name):
    repo,art=_checkpoint(tmp_path);(art/name).write_text("{}")
    with pytest.raises(RuntimeError,match="material artifact mismatch"):load_locked_checkpoint(repo,art)
def test_missing_required_artifact(tmp_path):
    repo,art=_checkpoint(tmp_path);(art/"calibration_2024.json").unlink()
    with pytest.raises(RuntimeError,match="material artifact mismatch"):load_locked_checkpoint(repo,art)
def test_source_and_environment_mismatch(tmp_path,monkeypatch):
    repo,art=_checkpoint(tmp_path);(repo/"source.py").write_text("changed")
    with pytest.raises(RuntimeError,match="source provenance mismatch"):load_locked_checkpoint(repo,art)
    repo,art=_checkpoint(tmp_path/"b");monkeypatch.setenv("PYTHONPATH","forbidden")
    with pytest.raises(RuntimeError,match="environment provenance mismatch"):load_locked_checkpoint(repo,art)
def test_column_order_and_target_definition_mismatch(tmp_path):
    repo,art=_checkpoint(tmp_path);prep=json.loads((art/"final_preprocessing_2024.json").read_text());prep["T1_P1"]["columns"]=["other"];_write(art/"final_preprocessing_2024.json",prep);_mutate_freeze(art,lambda f:f["material_artifact_hashes"].update({"final_preprocessing_2024.json":_sha(art/"final_preprocessing_2024.json")}))
    with pytest.raises(RuntimeError,match="frozen column mismatch"):load_locked_checkpoint(repo,art)
    repo,art=_checkpoint(tmp_path/"b");snap=json.loads((art/"snapshot_schema.json").read_text());snap["target_definition_versions"]["T1"]="changed";_write(art/"snapshot_schema.json",snap);_mutate_freeze(art,lambda f:f["material_artifact_hashes"].update({"snapshot_schema.json":_sha(art/"snapshot_schema.json")}))
    with pytest.raises(RuntimeError,match="target schema mismatch"):load_locked_checkpoint(repo,art)
def test_class_bootstrap_and_interpretation_mutations_rejected(tmp_path):
    for key in ("class","bootstrap","interpretation"):
        repo,art=_checkpoint(tmp_path/key)
        def mutate(f):
            if key=="class":f["class_order"]["T1"]=["adverse_reversal","continuation","no_event_60m"]
            elif key=="bootstrap":f["locked_2025_evaluation"]["bootstrap"]["seed"]=1
            else:f["locked_2025_evaluation"]["interpretation"]["otherwise"]="COUNTS AGAINST"
            if key!="class":f["locked_2025_evaluation_sha256"]=hashlib.sha256(json.dumps(f["locked_2025_evaluation"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
        _mutate_freeze(art,mutate)
        with pytest.raises(RuntimeError,match="class order mismatch|configuration mismatch"):load_locked_checkpoint(repo,art)
def test_2025_rows_not_consumed_until_checkpoint_valid(tmp_path):
    repo,art=_checkpoint(tmp_path);(art/"feature_schema.json").write_text("{}")
    class Bomb(Path):pass
    missing=tmp_path/"must-not-open.json"
    with pytest.raises(RuntimeError,match="material artifact mismatch"):evaluate_locked_2025(repo,art,missing,tmp_path/"out")
def test_boundary_rejected_before_features(tmp_path):
    repo,art=_checkpoint(tmp_path);c=load_locked_checkpoint(repo,art)
    class Bomb(dict):
        def __getitem__(self,key):raise AssertionError("feature consumed")
    row={"entry_execution_ms":1767225600000,"snapshot_ms":1767225600000,"features":Bomb()}
    with pytest.raises(ValueError,match="2025 entries only"):predict_feature_rows(c,"T1","P1",[row])
def test_no_development_or_fit_path_and_all_models_are_automatic(tmp_path,monkeypatch):
    repo,art=_checkpoint(tmp_path);rows=[]
    for t,classes in (("T1",("continuation","adverse_reversal","no_event_60m")),("T2",("renewed_peak","substantial_giveback","no_event_60m"))):
        for i in range(8):rows.append({"target":t,"row_id":f"{t}{i}","trade_id":f"{t}{i}","trade_entry_week":str(date(2025,1,6)+timedelta(days=7*i)),"entry_execution_ms":1736121600000+i*7*86400000,"snapshot_ms":1736121900000+i*7*86400000,"symbol":"BTCUSDT","target_eligible":True,"resolved":True,"censored":False,"ambiguous":False,"event_class":classes[i%3],"features":{"x":float(i)}})
    inp=tmp_path/"input.json";_write(inp,rows)
    for name in ("fit_multinomial","fit_preprocessing","run","verify_two_rebuilds"):
        monkeypatch.setattr(c4_modeling,name,lambda *a,**k:pytest.fail("development path invoked"))
    got=evaluate_locked_2025(repo,art,inp,tmp_path/"out");assert got["status"].endswith("COMPLETE")
    import csv
    pred=list(csv.DictReader((tmp_path/"out"/"predictions.csv").open()));assert {r["target"] for r in pred}=={"T1","T2"} and {r["model"] for r in pred}=={"B0","G0","G1","P1"}
    source=(Path(__file__).parents[1]/"src/binance_data_foundation/c4_locked_eval.py").read_text()
    assert "fit_multinomial" not in source and "fit_preprocessing" not in source and "select_C" not in source and "threshold_optimizer" not in source
