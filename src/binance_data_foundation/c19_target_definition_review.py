"""C19 methodology-only review of C18 target and decision timing semantics."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import numpy as np


CONTRACT_SHA256 = "2ad42555f8168c30c1c8e8dd051809cc6126b410a465fede33683c780282341d"
CONTRACT_REL = "contracts/C19_target_definition_decision_timing_review_CONTRACT.md"
OUTPUT_REL = "artifacts/c19_target_definition_decision_timing_review"

FROZEN_INPUTS = (
    "contracts/C18_pre_t2_economic_value_CONTRACT.md",
    "src/binance_data_foundation/c7_t1.py",
    "src/binance_data_foundation/c8_timescale.py",
    "src/binance_data_foundation/c18_pre_t2_economic_value.py",
    "artifacts/c7_full_population_t2_exit_overlay/population_manifest.json",
    "artifacts/c9_dynamic_pre_t2_state/final_summary.json",
    "artifacts/c18_pre_t2_economic_value/run_manifest.json",
    "artifacts/c18_pre_t2_economic_value/provenance.json",
    "artifacts/c18_pre_t2_economic_value/target_definition.json",
    "artifacts/c18_pre_t2_economic_value/trajectory_alignment.json",
    "artifacts/c18_pre_t2_economic_value/interpretation_predicates.json",
    "artifacts/c18_pre_t2_economic_value/final_summary.json",
    "artifacts/c18_pre_t2_economic_value/reproducibility_hashes.json",
)


def reject_2026(path: str | Path) -> None:
    if any("2026" in part for part in os.fspath(path).replace("\\", "/").lower().split("/")):
        raise PermissionError("C19 prohibits 2026 data or metadata access")


def sha256(path: Path) -> str:
    reject_2026(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def build_artifacts(repo: Path) -> dict[str, object]:
    reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("conda environment must be binance-v2-research")
    contract = repo / CONTRACT_REL
    if sha256(contract) != CONTRACT_SHA256:
        raise RuntimeError("C19 contract changed after prospective freeze")

    hashes = {name: sha256(repo / name) for name in FROZEN_INPUTS}
    c18_provenance = json.loads((repo / "artifacts/c18_pre_t2_economic_value/provenance.json").read_text())
    required_c18 = {
        "contracts/C18_pre_t2_economic_value_CONTRACT.md": c18_provenance["inputs"]["contracts/C18_pre_t2_economic_value_CONTRACT.md"],
        "artifacts/c7_full_population_t2_exit_overlay/population_manifest.json": c18_provenance["inputs"]["c7_population"],
        "artifacts/c9_dynamic_pre_t2_state/final_summary.json": c18_provenance["inputs"]["c9_final_summary"],
    }
    frozen_hash_status = "PASS" if all(hashes[name] == expected for name, expected in required_c18.items()) else "FAIL"
    if frozen_hash_status != "PASS":
        raise RuntimeError("frozen C18 provenance mismatch")

    delta_definition = {
        "equation": "DELTA_V_PRE(t) = HOLD_TO_P0_NET(t) - EXIT_NOW_NET(t)",
        "entry": {"raw_price": "frozen entry_price", "quote_notional": 1000.0, "quantity": "1000 / (entry_price * (1 + slippage_rate))"},
        "state_timestamp": "state_ms is the boundary after all state information is complete",
        "exit_now": "raw open at state_ms: the immediate next executable 1-minute open after completion",
        "p0": "frozen canonical p0_execution_ms and p0_raw_exit_price from the C7 population manifest",
        "cost_model": {"primary": "C_BASE", "fee_rate_each_leg": 0.001, "slippage_rate_each_leg": 0.0002},
        "executed_notional": "entry executed quote notional is fixed at 1000; exit executed quote notional is quantity * raw_exit_price * (1-slippage_rate), not re-fixed to 1000",
        "entry_costs": "adverse entry slippage determines common quantity; the 1000 quote debit and 0.1% entry fee are common",
        "exit_costs": "each alternative applies adverse exit slippage then 0.1% fee to its own exit executed notional",
        "ties_and_gaps": "state_ms >= P0 is ineligible (P0 precedence); exact next open, finite positive price, and continuous prior minute are required; otherwise fail closed",
    }
    decomposition = {
        "symbols": {"N": 1000.0, "Pe": "entry raw price", "Pt": "exit-now raw price", "P0": "canonical P0 raw price", "s": "slippage rate", "f": "fee rate", "q": "N/[Pe(1+s)]"},
        "alternative_net_return": "R(P) = [q*P*(1-s)*(1-f) - N - N*f] / N",
        "decomposition": "DELTA = q*(P0-Pt)/N - q*s*(P0-Pt)/N - f*q*(1-s)*(P0-Pt)/N = q*(1-s)*(1-f)*(P0-Pt)/N",
        "terminal_gross_value_difference": "q*(P0-Pt)/N",
        "incremental_exit_slippage_difference": "-q*s*(P0-Pt)/N",
        "incremental_exit_fee_difference": "-f*q*(1-s)*(P0-Pt)/N",
        "common_components_cancelled": ["N quote entry debit", "N*f entry fee", "common acquired quantity q; entry slippage is already embodied in q"],
        "future_cash_flow_equivalence": True,
        "finding": "Conditional on the already-held q, C18 exactly compares the two future net liquidation receipts; no accounting discrepancy was found.",
    }
    mechanical = {
        "mathematical": [
            "Within one trade P0, q, s, f, and N are fixed, so DELTA_V_PRE is affine and strictly decreasing in Pt.",
            "d(DELTA_V_PRE)/dPt = -q*(1-s)*(1-f)/N < 0.",
            "Any state variable that rises with current executable value can be negatively correlated with DELTA_V_PRE even without a causal economic relationship.",
        ],
        "empirical": [
            "Whether p_t2 rises with current executable value or favorable progress is data-dependent.",
            "The magnitude and stability of p_t2/DELTA association are empirical; C18 observed a strongly negative within-trade association.",
        ],
        "interpretation_guard": "Do not infer economic uselessness from a mechanically induced correlation.",
    }
    terminal = {
        "decision": "EXIT NOW versus COMMIT TO HOLD UNTIL FROZEN P0",
        "c18_supports": ["C9 predicts the T2/P0 lifecycle outcome well", "C9 does not usefully align with this terminal-commitment value target", "C9 should not be used directly as an exit signal on C18 evidence"],
        "c18_does_not_support": ["the value of continue-and-reassess", "a sequential exit policy", "selection of a forward horizon", "the claim that p_t2 has no value for any other decision target"],
    }
    sequential = {
        "decision": "EXIT NOW versus CONTINUE FOR NOW, OBSERVE NEW CAUSAL INFORMATION, AND REASSESS LATER",
        "commitment_guard": "Continue now does not imply commitment to P0.",
        "optionality": "Continuation retains the option to act on later causal states; its value includes outcomes induced by those future decisions.",
    }
    policy_dependency = {
        "definition": "SEQUENTIAL_VALUE(t) = value of continuing now under a specified future causal decision rule - value of exiting now",
        "identification": "It cannot be uniquely labeled from historical data until the downstream causal policy is prospectively specified.",
        "prohibition": "Do not construct a policy-free optimal continuation value from future-best exits; that embeds hindsight and optimization.",
    }
    taxonomy = {
        "terminal": {"name": "DELTA_V_P0", "definition": "hold to frozen P0 minus exit now", "status": "C18 target"},
        "fixed_horizon": {"name": "DELTA_V_H", "definition": "executable value after prospectively chosen H minus exit-now value", "candidate_minutes": [5, 15, 30, 60], "status": "definition only; not evaluated or selected"},
        "first_event": {"name": "DELTA_V_EVENT", "definition": "value at first frozen lifecycle event among T2/P0 minus exit now", "advantages": ["bounded by frozen lifecycle", "policy-free terminal comparator"], "limitations": ["event timing varies", "still a terminal commitment to that event", "T2 is a lifecycle label, not necessarily an economically executable exit objective"]},
        "sequential_policy": {"name": "DELTA_V_POLICY", "definition": "value under a prospectively frozen future causal policy minus exit now", "status": "not identifiable until policy is defined"},
    }
    timing = {
        "sequence": ["form state from completed information", "decide after state completion", "execute no earlier than the next valid 1-minute open"],
        "guards": ["no intrabar hindsight", "P0 wins ties prospectively", "missing, duplicate, invalid, or gapped execution evidence fails closed"],
        "frequency_distinction": "Higher-resolution observation does not imply frequent or immediate exits.",
    }
    accounting = {
        "population_rule": "Use per-trade paired differences over the complete frozen population; non-triggered trades retain the exact comparator outcome.",
        "minimum_outputs": ["per-trade paired net-return difference", "total P&L difference", "mean paired difference", "median paired difference", "fraction improved", "fraction worsened", "positive contribution", "negative contribution", "winner/right-tail truncation", "downside protection", "holding/exposure changes", "trigger and fallback counts"],
        "two_sided_requirement": ["avoided losses/preserved gains", "abandoned winners/foregone upside"],
        "implemented_in_c19": False,
    }
    dependence = {
        "primary_unit": "trade",
        "required": ["trade-level paired analysis", "whole-trade bootstrap/resampling where applicable"],
        "robustness": "fixed calendar-block bootstrap when applicable to shared market-regime/time dependence",
        "prohibitions": ["do not treat 1-minute snapshots as independent economic samples", "do not select a policy post hoc from symbol/year decompositions"],
    }
    right_tail = {
        "must_measure": ["downside avoided", "right-tail upside destroyed"],
        "insufficient_alone": ["win rate", "median outcome", "avoided red trades", "state-classification accuracy"],
    }
    probability_value = {
        "event_probability": "P(event | state): prognosis for a lifecycle event",
        "expected_value": "E[incremental economic value | state]: conditional magnitude-weighted economic target",
        "action_benefit_probability": "P(policy action is beneficial | state): sign probability under a defined comparator/policy",
        "conclusion": "A lifecycle-event probability is not automatically an economic decision model; failure against DELTA_V_P0 does not rule out relevance at another prospectively defined decision horizon.",
    }
    reinterpretation = {
        "established": ["C9 predicts the T2/P0 lifecycle outcome well", "C9 does not align with DELTA_V_PRE for terminal commitment", "DELTA_V_PRE mechanically declines as current executable value rises toward or through fixed P0 value", "C18 does not justify using C9 directly as an exit signal", "C18 does not settle sequential continuation"],
        "frozen_classification": "NO_USEFUL_ECONOMIC_ALIGNMENT",
        "accounting_valid": True,
        "repair_required": False,
    }
    recommendation = {
        "direction": "C20 should be a bounded forward-opportunity characterization before any policy experiment.",
        "prospective_targets": ["DELTA_V_H at 5m", "DELTA_V_H at 15m", "DELTA_V_H at 30m", "DELTA_V_H at 60m", "DELTA_V_EVENT if its execution semantics are prospectively justified"],
        "selection_rule": "Characterize all frozen candidates; do not select a best horizon from outcomes.",
        "executed": False,
    }
    verification = {
        "contract_sha": "PASS",
        "frozen_input_hashes": frozen_hash_status,
        "equation_and_cost_semantics": "PASS by source inspection and focused algebra/test",
        "next_open_p0_tie_gap_semantics": "PASS by frozen source inspection and focused tests",
        "common_cost_cancellation": "PASS by symbolic derivation and numeric focused test",
        "no_2026_access": True,
        "model_policy_horizon_evaluation": False,
    }
    files = {
        "run_manifest": {"version": "C19_REVIEW_V1", "contract_sha256": CONTRACT_SHA256, "python": sys.version.split()[0], "numpy": np.__version__, "platform": platform.platform(), "conda_environment": "binance-v2-research", "methodology_only": True},
        "provenance": {"contract_sha256": CONTRACT_SHA256, "frozen_inputs": hashes, "c18_provenance_crosscheck": frozen_hash_status, "no_2026_access": True},
        "delta_v_pre_definition": delta_definition,
        "incremental_cost_decomposition": decomposition,
        "mechanical_relationships": mechanical,
        "terminal_commitment_definition": terminal,
        "sequential_continuation_definition": sequential,
        "sequential_value_policy_dependency": policy_dependency,
        "candidate_target_taxonomy": taxonomy,
        "decision_timing": timing,
        "future_policy_accounting_requirements": accounting,
        "dependence_uncertainty_requirements": dependence,
        "right_tail_requirements": right_tail,
        "probability_vs_value_distinctions": probability_value,
        "c18_reinterpretation": reinterpretation,
        "c20_recommendation": recommendation,
    }
    files["final_summary"] = {
        "contract_sha256": CONTRACT_SHA256,
        "finding": "C18 accounting is valid but answers terminal commitment, while the intended architecture is sequential continuation.",
        "equation": delta_definition["equation"],
        "accounting_valid": True,
        "mechanical_result": mechanical["mathematical"],
        "c18_reinterpretation": reinterpretation,
        "c20_recommendation": recommendation,
        "verification": verification,
        "confirmations": {"contract_modified": False, "model_trained_or_run": False, "policy_economics_calculated": False, "candidate_horizons_evaluated": False, "c20_started": False, "accessed_2026": False, "c7_c18_behavior_modified": False},
    }
    return files


def run(repo: Path) -> dict[str, object]:
    files = build_artifacts(repo)
    out = repo / OUTPUT_REL
    out.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        write_json(out / f"{name}.json", value)
    artifact_hashes = {path.name: sha256(path) for path in sorted(out.glob("*.json")) if path.name != "reproducibility_hashes.json"}
    write_json(out / "reproducibility_hashes.json", artifact_hashes)
    return files["final_summary"]


if __name__ == "__main__":
    run(Path.cwd())
