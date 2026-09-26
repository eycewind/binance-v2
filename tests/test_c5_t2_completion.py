from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from binance_data_foundation.c5_t1 import symbol_strength
from binance_data_foundation.c5_t2_completion import (CANONICAL_SHA, METRICS,
    evaluate, load_canonical, month_plan, paired, reconstructed_attempts,
    safety_from, sha256, week_plan)


def _pairs():
    out={}
    start=date(2024,1,1)
    for i in range(10):
        week=start+timedelta(weeks=i)
        common={"trade_entry_week":week.isoformat(),"entry_execution_ts":week.isoformat()+"T00:00:00+00:00",
                "common_capture_gap":.02,"held_peak_surrender":.01,"holding_duration_seconds":100,
                "green_to_red":False,"preserved_at_least_half_peak":True,"early_exit":True,
                "opportunity_foregone":.01,"subsequent_plus_2":False,"subsequent_plus_3":False,"subsequent_plus_5":False}
        out[str(i)]=({**common,"net_return":.02},{**common,"net_return":.01})
    return out


def test_complete_metric_panel_and_replicates_are_preserved() -> None:
    pairs=_pairs();plan=week_plan(pairs);metrics,vectors=evaluate(pairs,plan)
    assert set(metrics)==set(METRICS)
    assert len(plan["sampled_block_indices"])==2000
    assert len(plan["trade_multiplicities"])==2000
    assert all(len(v)==2000 for v in vectors.values())
    assert any(any(n>1 for n in x.values()) for x in plan["trade_multiplicities"])


def test_held_baseline_early_exit_rate_is_structurally_unavailable() -> None:
    pairs=_pairs()
    for _,right in pairs.values():right["early_exit"]=False
    metrics,vectors=evaluate(pairs,week_plan(pairs))
    key="subsequent_plus_2_rate_after_early_exit"
    assert not metrics[key]["available"]
    assert metrics[key]["reason"].startswith("held_baseline")
    assert vectors[key]==[]


def test_calendar_month_whole_trade_cluster_bootstrap() -> None:
    plan=month_plan(_pairs())
    assert plan["construction"].startswith("whole_utc_calendar_month")
    assert len(plan["sampled_month_indices"])==2000
    assert len(plan["trade_multiplicities"])==2000


def test_c_s5_safety_frozen_directions() -> None:
    base={k:{"ci95":[-0.1,0.1]} for k in ("expected_shortfall_10","green_to_red_rate","mean_opportunity_foregone_after_early_exit","subsequent_plus_2_rate_after_early_exit","subsequent_plus_3_rate_after_early_exit","subsequent_plus_5_rate_after_early_exit")}
    assert not safety_from(base)["unacceptable_safety_breach"]
    base["expected_shortfall_10"]={"ci95":[-0.2,-0.01]}
    assert safety_from(base)["unacceptable_safety_breach"]


def test_symbol_strength_conflicting_practical_comparison_is_mixed() -> None:
    assert symbol_strength(80,.01,(-.01,.02),-.001)=="MIXED"
    assert symbol_strength(80,-.01,(-.02,.01),.001)=="MIXED"


def test_attempt_ledger_reconstruction_preserves_known_latest() -> None:
    existing={"attempts":[{"start_timestamp_utc":"known-start","end_timestamp_utc":"known-end","code_sha256":"abc"}]}
    got=reconstructed_attempts(existing)
    assert got["attempt_count"]==4 and len(got["attempts"])==4
    assert got["attempts"][-1]["start_timestamp_utc"]=="known-start"
    assert got["attempts"][0]["start_timestamp_utc"] is None


def test_canonical_trade_results_immutable_and_no_replay_import() -> None:
    path=Path("artifacts/c5_economic_exit_policy/t2/trade_results.csv")
    before=sha256(path);load_canonical(path);after=sha256(path)
    assert before==after==CANONICAL_SHA
    source=Path("src/binance_data_foundation/c5_t2_completion.py").read_text()
    assert "import c5_t2" not in source
    assert "from .c5_t2 import" not in source
    assert "sealed_confirmation_access\":False" in source
