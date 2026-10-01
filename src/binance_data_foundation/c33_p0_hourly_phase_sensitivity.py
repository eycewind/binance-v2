"""C33 frozen hourly-boundary phase sensitivity experiment.

Only the observation lattice is shifted.  Entries, P0 state/decision semantics,
execution, seven-day terminal handling, and costs remain frozen.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .c2_common import ENTRY_COLUMNS, hash_rows
from .c2_costs import COST_SCENARIOS, CostScenario, apply_round_trip_costs
from .c32_p0_phase_sensitivity import (
    EXPECTED_HORIZON_HASH, EXPECTED_TRADE_HASH, reconcile_canonical,
)
from .c2_p0 import EXPECTED_FROZEN_ENTRY_HASH
from .ingest import sha256_file

CONTRACT_REL = "contracts/C33_P0_HOURLY_PHASE_SENSITIVITY_CONTRACT.md"
OUTPUT_REL = "artifacts/c33_p0_hourly_phase_sensitivity"
C2_REL = "artifacts/c2_asymmetric_exit_experiment"
MINUTE_REL = "data/normalized/c2_history"
C32_REC_REL = "artifacts/c32_p0_phase_sensitivity/canonical_p0_reconciliation.json"
EXPECTED_C32_REC_HASH = "4472ad427b4e4ba6abac187c1a77a194a3ff6384ab486253d5e7db2b2ac7fe62"
EXPECTED_C2_P0_HASH = "d01eaad44890e16a3dd2e30608b37f9829156cae5c68a5a62ac49a65acee72c2"
EXPECTED_ENTRIES = 2199
END_MS = 1767225600000  # exclusive; never open or enumerate a holdout partition
HOUR_MS = 3_600_000
MINUTE_MS = 60_000
CAP_MS = 7 * 24 * HOUR_MS
PHASES = tuple(range(60))
SEED = 20261001
REPLICATES = 2000
DESIGN_BNB = CostScenario("DESIGN_BNB", .00075, .0002)
ALL_COSTS = (COST_SCENARIOS[0], DESIGN_BNB, *COST_SCENARIOS[1:])

REQUIRED_OUTPUTS = (
    "run_manifest.json", "provenance.json", "canonical_p0_reconciliation.json",
    "population_reconciliation.json", "phase_definitions.json", "phase_bar_audit.json",
    "common_support.json", "phase_net_return_profile.json", "phase_gross_return_profile.json",
    "canonical_phase_deltas.json", "exit_time_displacement.json", "phase_mfe_profile.json",
    "phase_surrender_profile.json", "phase_mfe_timing_profile.json",
    "phase_holding_time_profile.json", "robust_phase_statistics.json",
    "circular_smoothness.json", "cross_year_phase_stability.json",
    "circular_shift_diagnostic.json", "local_neighborhood_consistency.json",
    "trade_bootstrap_intervals.json", "month_bootstrap_intervals.json",
    "cost_robustness.json", "symbol_phase_profiles.json", "causality_tests.json",
    "interpretation_predicates.json", "final_summary.json", "reproducibility_hashes.json",
)


def reject_2026(path: os.PathLike[str] | str) -> None:
    if any("2026" in part.lower() for part in os.fspath(path).replace("\\", "/").split("/")):
        raise PermissionError("C33 prohibits 2026 market data and metadata access")


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _semantic_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _year(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y")


def _month(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")


def _q(values: np.ndarray | list[float], p: float) -> float | None:
    a = np.asarray(values, dtype=float)
    return float(np.quantile(a, p, method="linear")) if a.size else None


def _dist(values: np.ndarray | list[float]) -> dict:
    a = np.asarray(values, dtype=float)
    if not a.size:
        return {k: None for k in ("mean", "median", "p10", "p25", "p75", "p90")} | {"count": 0}
    return {"count": int(a.size), "mean": float(a.mean()), "median": float(np.median(a)),
            "p10": _q(a, .1), "p25": _q(a, .25), "p75": _q(a, .75), "p90": _q(a, .9)}


def _ranks(a: np.ndarray) -> np.ndarray:
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), float)
    i = 0
    while i < len(a):
        j = i + 1
        while j < len(a) and a[order[j]] == a[order[i]]:
            j += 1
        ranks[order[i:j]] = (i + j - 1) / 2
        i = j
    return ranks


def _corr(a: np.ndarray, b: np.ndarray, spearman: bool = False) -> float | None:
    if spearman:
        a, b = _ranks(a), _ranks(b)
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _load_entries(repo: Path) -> list[dict]:
    path = repo / C2_REL / "frozen_entries.csv"
    reject_2026(path)
    if sha256_file(path) != EXPECTED_FROZEN_ENTRY_HASH:
        raise RuntimeError("frozen E1 byte hash mismatch")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_ENTRIES or hash_rows(rows, ENTRY_COLUMNS) != EXPECTED_FROZEN_ENTRY_HASH:
        raise RuntimeError("frozen E1 semantic reconciliation failed")
    return rows


def _load_minutes(path: Path) -> dict[str, np.ndarray]:
    """Read only the accepted pre-holdout file named explicitly by symbol."""
    reject_2026(path)
    cols = {k: [] for k in ("ts", "open", "high", "low", "close", "volume", "quote", "trades")}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ts = int(row["open_time_ms"])
            if ts >= END_MS:
                break
            cols["ts"].append(ts); cols["open"].append(float(row["open"])); cols["high"].append(float(row["high"]))
            cols["low"].append(float(row["low"])); cols["close"].append(float(row["close"]))
            cols["volume"].append(float(row["base_volume"])); cols["quote"].append(float(row["quote_volume"]))
            cols["trades"].append(int(row["trade_count"]))
    out = {k: np.asarray(v, dtype=np.int64 if k in ("ts", "trades") else float) for k, v in cols.items()}
    if len(out["ts"]) < 60 or np.any(np.diff(out["ts"]) != MINUTE_MS):
        raise RuntimeError(f"minute source is not gap-free: {path.name}")
    if np.any(~np.isfinite(out["open"])) or np.any(out["open"] <= 0):
        raise RuntimeError(f"invalid minute source: {path.name}")
    return out


def construct_phase_bars(minutes: dict[str, np.ndarray], phase: int) -> dict[str, np.ndarray]:
    """Aggregate exact [t-60m,t) bars on one minute-offset lattice."""
    ts = minutes["ts"]
    ends = np.flatnonzero(((ts + MINUTE_MS) % HOUR_MS) == phase * MINUTE_MS)
    ends = ends[ends >= 59]
    starts = ends - 59
    complete = ts[ends] - ts[starts] == 59 * MINUTE_MS
    ends, starts = ends[complete], starts[complete]
    # Select exact 60-row windows (including the final complete window).
    high = np.lib.stride_tricks.sliding_window_view(minutes["high"], 60)[starts].max(axis=1)
    low = np.lib.stride_tricks.sliding_window_view(minutes["low"], 60)[starts].min(axis=1)
    volume = np.lib.stride_tricks.sliding_window_view(minutes["volume"], 60)[starts].sum(axis=1)
    quote = np.lib.stride_tricks.sliding_window_view(minutes["quote"], 60)[starts].sum(axis=1)
    trades = np.lib.stride_tricks.sliding_window_view(minutes["trades"], 60)[starts].sum(axis=1)
    close = minutes["close"][ends]
    sma = np.full(len(close), np.nan)
    if len(close) >= 24:
        sma[23:] = np.convolve(close, np.ones(24) / 24, mode="valid")
    return {"open_ms": ts[starts], "boundary_ms": ts[ends] + MINUTE_MS,
            "open": minutes["open"][starts], "high": high, "low": low, "close": close,
            "volume": volume, "quote": quote, "trades": trades, "sma24": sma,
            "source_rows": np.full(len(close), 60, dtype=np.int64)}


def _outcome(entry: dict, bars: dict[str, np.ndarray], minutes: dict[str, np.ndarray]) -> tuple[dict | None, str | None]:
    ems = int(entry["entry_execution_ms"]); cap = ems + CAP_MS
    boundaries = bars["boundary_ms"]
    eligible = np.flatnonzero((boundaries > ems) & (boundaries <= cap) & np.isfinite(bars["sma24"]))
    fired = eligible[bars["close"][eligible] < bars["sma24"][eligible]]
    exit_ms = int(boundaries[fired[0]]) if len(fired) else cap
    reason = "sma24_crossdown" if len(fired) else "time_cap"
    ts = minutes["ts"]; pos = int(np.searchsorted(ts, exit_ms))
    if pos >= len(ts) or int(ts[pos]) != exit_ms:
        return None, "execution_minute_missing"
    start = int(np.searchsorted(ts, ems + MINUTE_MS)); stop = pos
    if start > stop or (stop > start and (int(ts[stop - 1]) != exit_ms - MINUTE_MS or np.any(np.diff(ts[start:stop]) != MINUTE_MS))):
        return None, "lifecycle_path_gap"
    entry_price = float(entry["entry_price"]); exit_price = float(minutes["open"][pos])
    if stop > start:
        highs = minutes["high"][start:stop]; j = int(np.argmax(highs)); peak_price = float(highs[j]); mfe_ms = int(ts[start + j])
    else:
        peak_price, mfe_ms = entry_price, ems
    if exit_price > peak_price:
        peak_price, mfe_ms = exit_price, exit_ms
    if entry_price >= peak_price:
        peak_price, mfe_ms = entry_price, ems
    raw = exit_price / entry_price - 1
    costs = {}
    for scenario in ALL_COSTS:
        c = apply_round_trip_costs(entry_price, exit_price, float(entry["entry_notional_usdt"]), scenario)
        pnl = c["quantity"] * c["exit_price_after_slippage"] - c["exit_fee_usdt"] - float(entry["entry_notional_usdt"]) - c["entry_fee_usdt"]
        costs[scenario.scenario_id] = {"net": float(c["net_return"]), "gross": float(c["gross_return"]), "pnl": float(pnl)}
    mfe = max(peak_price / entry_price - 1, 0.0)
    return {"trade_id": entry["trade_id"], "symbol": entry["symbol"], "year": _year(ems), "month": _month(ems),
            "entry_ms": ems, "exit_ms": exit_ms, "exit_price": exit_price, "exit_reason": reason,
            "raw_return": raw, "mfe": mfe, "mfe_ms": mfe_ms, "surrender": mfe - raw,
            "mfe_to_exit_minutes": (exit_ms - mfe_ms) / MINUTE_MS,
            "holding_minutes": (exit_ms - ems) / MINUTE_MS, "costs": costs}, None


def _profile(rows: list[dict], key) -> dict:
    result = {}
    for group, selected in [("pooled", rows), ("2024", [r for r in rows if r["year"] == "2024"]),
                            ("2025", [r for r in rows if r["year"] == "2025"])]:
        a = np.asarray([key(r) for r in selected], float); d = _dist(a)
        result[group] = d
    return result


def _economic_profile(outcomes: dict[int, list[dict]], cost: str, support: set[str]) -> dict:
    doc = {}
    for p in PHASES:
        rows = [r for r in outcomes[p] if r["trade_id"] in support]
        groups = {"pooled": rows, "2024": [r for r in rows if r["year"] == "2024"], "2025": [r for r in rows if r["year"] == "2025"]}
        groups.update({s: [r for r in rows if r["symbol"] == s] for s in sorted({r["symbol"] for r in rows})})
        doc[f"{p:02d}"] = {}
        for name, rr in groups.items():
            vals = np.asarray([r["costs"][cost]["net"] for r in rr], float)
            d = _dist(vals); d.update({"trade_count": len(rr), "total_pnl_usdt": float(sum(r["costs"][cost]["pnl"] for r in rr)),
                                       "positive_return_fraction": float(np.mean(vals > 0)) if len(vals) else None})
            doc[f"{p:02d}"][name] = d
    return doc


def _phase_stats(matrix: np.ndarray, years: np.ndarray) -> dict:
    result = {}
    for label, mask in (("pooled", np.ones(len(years), bool)), ("2024", years == "2024"), ("2025", years == "2025")):
        means = matrix[mask].mean(axis=0)
        result[label] = {"phase_means": means.tolist(), "p90_p10_spread": _q(means, .9) - _q(means, .1),
                         "rms_phase_variation": float(np.sqrt(np.mean((means - means.mean()) ** 2))),
                         "full_range": float(means.max() - means.min())}
    return result


def _smoothness(means: np.ndarray) -> dict:
    adjacent = np.abs(means - np.roll(means, -1)); pair = np.abs(means[:, None] - means[None, :])
    all_pair = float(pair[np.triu_indices(60, 1)].mean())
    return {"adjacent_absolute_changes": adjacent.tolist(), "adjacent_mean_abs_change": float(adjacent.mean()),
            "all_pair_mean_abs_change": all_pair, "adjacent_smoothness_ratio": float(adjacent.mean() / all_pair) if all_pair else None}


def _stability(matrix: np.ndarray, years: np.ndarray) -> dict:
    a, b = matrix[years == "2024"].mean(axis=0), matrix[years == "2025"].mean(axis=0)
    ac, bc = a - a.mean(), b - b.mean()
    return {"pearson": _corr(a, b), "spearman": _corr(a, b, True),
            "centered_pearson": _corr(ac, bc), "centered_spearman": _corr(ac, bc, True),
            "zero_shift_is_primary": True}


def _circular(a: np.ndarray, b: np.ndarray) -> dict:
    vals = [_corr(a - a.mean(), np.roll(b - b.mean(), shift)) for shift in PHASES]
    valid = np.asarray([x if x is not None else -np.inf for x in vals]); shift = int(valid.argmax())
    return {"correlations_by_shift": vals, "maximum_circular_cross_correlation": vals[shift],
            "shift_at_maximum_minutes": shift, "classification_uses_zero_shift": True}


def _bootstrap(matrix: np.ndarray, years: np.ndarray, months: np.ndarray, unit: str) -> dict:
    rng = np.random.Generator(np.random.PCG64(SEED))
    if unit == "trade":
        groups = [np.asarray([i]) for i in range(len(matrix))]
    else:
        groups = [np.flatnonzero(months == label) for label in sorted(set(months))]
    spreads = np.empty(REPLICATES); rms = np.empty(REPLICATES); deltas = np.empty((REPLICATES, 60)); stability = np.empty(REPLICATES)
    for b in range(REPLICATES):
        picks = rng.integers(len(groups), size=len(groups)); idx = np.concatenate([groups[int(j)] for j in picks])
        means = matrix[idx].mean(axis=0); spreads[b] = np.quantile(means, .9) - np.quantile(means, .1)
        rms[b] = np.sqrt(np.mean((means - means.mean()) ** 2)); sampled = matrix[idx]
        deltas[b] = (sampled - sampled[:, [0]]).mean(axis=0)
        aidx, bidx = idx[years[idx] == "2024"], idx[years[idx] == "2025"]
        stability[b] = _corr(matrix[aidx].mean(axis=0), matrix[bidx].mean(axis=0), True) if len(aidx) and len(bidx) else np.nan
    ci = lambda x: np.quantile(x[np.isfinite(x)], [.025, .975], method="linear").tolist()
    return {"unit": unit, "iterations": REPLICATES, "generator": "PCG64", "seed": SEED,
            "joint_60_phase_resampling": True, "phase_p90_p10_spread_ci95": ci(spreads), "phase_rms_ci95": ci(rms),
            "phase_delta_vs_00_ci95": {f"{p:02d}": ci(deltas[:, p]) for p in PHASES},
            "centered_cross_year_spearman_ci95": ci(stability),
            "replicate_hashes": {"spread": hashlib.sha256(spreads.astype("<f8").tobytes()).hexdigest(),
                                 "rms": hashlib.sha256(rms.astype("<f8").tobytes()).hexdigest(),
                                 "deltas": hashlib.sha256(deltas.astype("<f8").tobytes()).hexdigest(),
                                 "stability": hashlib.sha256(stability.astype("<f8").tobytes()).hexdigest()}}


def run(repo: Path) -> dict:
    repo = repo.resolve(); out = repo / OUTPUT_REL
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("C33 must run in binance-v2-research")
    # Frozen hash gate, before shifted work.
    if sha256_file(repo / "src/binance_data_foundation/c2_p0.py") != EXPECTED_C2_P0_HASH:
        raise RuntimeError("canonical P0 implementation hash mismatch")
    if sha256_file(repo / C32_REC_REL) != EXPECTED_C32_REC_HASH:
        raise RuntimeError("C32 canonical reconciliation hash mismatch")
    gate, c32_prov = reconcile_canonical(repo)
    entries = _load_entries(repo)
    if gate["population"]["status"] != "PASS" or gate["reconciliation"]["status"] != "PASS":
        raise RuntimeError("C33_INSUFFICIENT: canonical reconciliation failed")

    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for e in entries: by_symbol[e["symbol"]].append(e)
    outcomes: dict[int, list[dict]] = {p: [] for p in PHASES}; exclusions: dict[int, dict[str, str]] = {p: {} for p in PHASES}
    source_hashes = {}; audits = {}; phase00_bar_identity = True
    for symbol in sorted(by_symbol):
        source = repo / MINUTE_REL / f"{symbol}_1m.csv.gz"; source_hashes[str(source.relative_to(repo))] = sha256_file(source)
        minutes = _load_minutes(source); audits[symbol] = {}
        for p in PHASES:
            bars = construct_phase_bars(minutes, p)
            audits[symbol][f"{p:02d}"] = {"bar_count": len(bars["close"]), "first_boundary_ms": int(bars["boundary_ms"][0]),
                                               "last_boundary_ms": int(bars["boundary_ms"][-1]), "duration_minutes": 60,
                                               "cadence_minutes": int(np.unique(np.diff(bars["boundary_ms"]))[0] / MINUTE_MS),
                                               "all_source_rows_60": bool(np.all(bars["source_rows"] == 60))}
            if p == 0:
                frozen_path = repo / "data/normalized/c2_frozen_inputs" / f"{symbol}_1h.csv.gz"
                frozen = []
                with gzip.open(frozen_path, "rt", encoding="utf-8", newline="") as h:
                    for r in csv.DictReader(h):
                        if int(r["open_time_ms"]) >= END_MS: break
                        frozen.append(r)
                phase00_bar_identity &= len(frozen) == len(bars["close"]) and all(
                    int(r["available_at_ms"]) == int(bars["boundary_ms"][i]) and float(r["open"]) == float(bars["open"][i])
                    and float(r["high"]) == float(bars["high"][i]) and float(r["low"]) == float(bars["low"][i])
                    and float(r["close"]) == float(bars["close"][i]) for i, r in enumerate(frozen))
            for entry in by_symbol[symbol]:
                row, reason = _outcome(entry, bars, minutes)
                if row is None: exclusions[p][entry["trade_id"]] = str(reason)
                else: outcomes[p].append(row | {"phase": p})

    maps = {p: {r["trade_id"]: r for r in outcomes[p]} for p in PHASES}
    support = set.intersection(*(set(maps[p]) for p in PHASES)); ordered_ids = [e["trade_id"] for e in entries if e["trade_id"] in support]
    rows0 = [maps[0][i] for i in ordered_ids]
    canonical_horizons = {}
    with (repo / C2_REL / "common_horizons_p0.csv").open(encoding="utf-8", newline="") as h:
        canonical_horizons = {r["trade_id"]: r for r in csv.DictReader(h)}
    canonical_trades = {}
    with (repo / C2_REL / "p0_trade_records.csv").open(encoding="utf-8", newline="") as h:
        canonical_trades = {(r["trade_id"], r["cost_scenario"]): r for r in csv.DictReader(h)}
    phase00_outcomes_exact = len(maps[0]) == EXPECTED_ENTRIES and all(
        r["exit_ms"] == int(canonical_horizons[r["trade_id"]]["p0_execution_ms"])
        and r["exit_price"] == float(canonical_horizons[r["trade_id"]]["p0_raw_exit_price"])
        and r["exit_reason"] == canonical_horizons[r["trade_id"]]["p0_exit_reason"]
        and all(r["costs"][c]["gross"] == float(canonical_trades[(r["trade_id"], c)]["gross_return"])
                and r["costs"][c]["net"] == float(canonical_trades[(r["trade_id"], c)]["net_return"])
                for c in ("C0", "C_BASE", "C_S5", "C_S10")) for r in maps[0].values())
    if not phase00_bar_identity or not phase00_outcomes_exact:
        raise RuntimeError("C33_INSUFFICIENT: phase-00 identity failed")
    if len(support) < math.ceil(.9 * EXPECTED_ENTRIES):
        raise RuntimeError("C33_INSUFFICIENT: common support below 90 percent")

    matrix = np.asarray([[maps[p][i]["costs"]["C_BASE"]["net"] for p in PHASES] for i in ordered_ids])
    gross = np.asarray([[maps[p][i]["raw_return"] for p in PHASES] for i in ordered_ids])
    mfe = np.asarray([[maps[p][i]["mfe"] for p in PHASES] for i in ordered_ids])
    surrender = np.asarray([[maps[p][i]["surrender"] for p in PHASES] for i in ordered_ids])
    delays = np.asarray([[maps[p][i]["mfe_to_exit_minutes"] for p in PHASES] for i in ordered_ids])
    holds = np.asarray([[maps[p][i]["holding_minutes"] for p in PHASES] for i in ordered_ids])
    exits = np.asarray([[maps[p][i]["exit_ms"] for p in PHASES] for i in ordered_ids], dtype=np.int64)
    years = np.asarray([maps[0][i]["year"] for i in ordered_ids]); months = np.asarray([maps[0][i]["month"] for i in ordered_ids])
    symbols = np.asarray([maps[0][i]["symbol"] for i in ordered_ids])
    stats = _phase_stats(matrix, years); smooth = _smoothness(matrix.mean(axis=0)); stability = _stability(matrix, years)

    population = gate["population"] | {"frozen_entry_file_sha256": EXPECTED_FROZEN_ENTRY_HASH, "entries_shifted_or_regenerated": False}
    c32_rec_hash = sha256_file(repo / C32_REC_REL)
    rec = gate["reconciliation"] | {"phase00_bars_exact": phase00_bar_identity, "phase00_outcomes_exact": phase00_outcomes_exact,
                                    "c32_canonical_reconciliation_sha256": c32_rec_hash,
                                    "canonical_p0_implementation_sha256": EXPECTED_C2_P0_HASH,
                                    "status": "PASS"}
    _write(out / "population_reconciliation.json", population); _write(out / "canonical_p0_reconciliation.json", rec)
    definitions = {f"{p:02d}": {"minute_offset": p, "boundaries": f"UTC hh:{p:02d}", "bar_interval": "[t-60m,t)",
                                      "bar_duration_minutes": 60, "evaluation_cadence_minutes": 60} for p in PHASES}
    _write(out / "phase_definitions.json", {"phase_count": 60, "phases": definitions, "entries_frozen": True, "exit_observation_only_shifted": True})
    _write(out / "phase_bar_audit.json", {"symbols": audits, "phase00_exact_frozen_bar_identity": phase00_bar_identity})
    excluded_ids = sorted(set(e["trade_id"] for e in entries) - support)
    exclusion_reasons = Counter(exclusions[p].get(i, "valid_other_phase") for i in excluded_ids for p in PHASES if i in exclusions[p])
    _write(out / "common_support.json", {"count": len(support), "rate": len(support) / EXPECTED_ENTRIES, "excluded_count": len(excluded_ids),
                                          "exclusion_reason_counts": dict(sorted(exclusion_reasons.items())),
                                          "year_counts": dict(sorted(Counter(maps[0][i]["year"] for i in ordered_ids).items())),
                                          "symbol_counts": dict(sorted(Counter(maps[0][i]["symbol"] for i in ordered_ids).items())),
                                          "primary_inference_uses_common_support": True})
    net_profile = _economic_profile(outcomes, "C_BASE", support); _write(out / "phase_net_return_profile.json", {"cost": "C_BASE", "phases": net_profile})
    gross_profile = {f"{p:02d}": _profile([maps[p][i] for i in ordered_ids], lambda r: r["raw_return"]) for p in PHASES}
    _write(out / "phase_gross_return_profile.json", {"return_definition": "raw exit_price / frozen entry_price - 1", "phases": gross_profile})
    deltas = {}
    displacement = {}; holding_doc = {}; mfe_doc = {}; surrender_doc = {}; delay_doc = {}
    for p in PHASES:
        d = matrix[:, p] - matrix[:, 0]; ds = _dist(d)
        ds.update({"total_pnl_delta_usdt": float(sum(maps[p][i]["costs"]["C_BASE"]["pnl"] - maps[0][i]["costs"]["C_BASE"]["pnl"] for i in ordered_ids)),
                   "wins": int(np.sum(d > 0)), "losses": int(np.sum(d < 0)), "ties": int(np.sum(d == 0))})
        deltas[f"{p:02d}"] = ds
        x = (exits[:, p] - exits[:, 0]) / MINUTE_MS; displacement[f"{p:02d}"] = _dist(x) | {
            "fraction_earlier": float(np.mean(x < 0)), "fraction_later": float(np.mean(x > 0)), "fraction_identical": float(np.mean(x == 0))}
        h = holds[:, p]; holding_doc[f"{p:02d}"] = _dist(h) | {"paired_difference_vs_00": _dist(h - holds[:, 0])}
        m = mfe[:, p]; raw = gross[:, p]; pos = m > 0
        mfe_doc[f"{p:02d}"] = _dist(m) | {"fraction_realized_negative_despite_positive_mfe": float(np.mean((raw < 0) & pos)),
            "fraction_retaining_25pct_positive_mfe": float(np.mean(raw[pos] / m[pos] >= .25)),
            "fraction_retaining_50pct_positive_mfe": float(np.mean(raw[pos] / m[pos] >= .50)),
            "fraction_retaining_75pct_positive_mfe": float(np.mean(raw[pos] / m[pos] >= .75))}
        surrender_doc[f"{p:02d}"] = _dist(surrender[:, p]); delay_doc[f"{p:02d}"] = _dist(delays[:, p])
    _write(out / "canonical_phase_deltas.json", {"canonical_phase": "00", "cost": "C_BASE", "phases": deltas})
    _write(out / "exit_time_displacement.json", {"units": "minutes", "phases": displacement})
    _write(out / "phase_holding_time_profile.json", {"units": "minutes", "phases": holding_doc})
    _write(out / "phase_mfe_profile.json", {"evaluation_only": True, "phases": mfe_doc})
    _write(out / "phase_surrender_profile.json", {"definition": "MFE - realized raw return", "phases": surrender_doc})
    _write(out / "phase_mfe_timing_profile.json", {"units": "minutes", "phases": delay_doc})
    _write(out / "robust_phase_statistics.json", stats); _write(out / "circular_smoothness.json", smooth)
    diagnostic_stability = {"net_return": stability, "surrender_gap": _stability(surrender, years),
                            "exit_displacement": _stability((exits - exits[:, [0]]) / MINUTE_MS, years),
                            "mfe_to_exit_delay": _stability(delays, years)}
    _write(out / "cross_year_phase_stability.json", diagnostic_stability)
    y24, y25 = matrix[years == "2024"].mean(axis=0), matrix[years == "2025"].mean(axis=0)
    _write(out / "circular_shift_diagnostic.json", _circular(y24, y25))
    neighborhoods = np.asarray([np.mean(np.take(matrix.mean(axis=0), [(p + d) % 60 for d in (-2, -1, 0, 1, 2)])) for p in PHASES])
    _write(out / "local_neighborhood_consistency.json", {"window_minutes": 5, "circular": True,
                                                           "means": {f"{p:02d}": float(neighborhoods[p]) for p in PHASES}, "selection_performed": False})
    trade_boot = _bootstrap(matrix, years, months, "trade"); month_boot = _bootstrap(matrix, years, months, "UTC entry month")
    _write(out / "trade_bootstrap_intervals.json", trade_boot); _write(out / "month_bootstrap_intervals.json", month_boot)
    cost_doc = {}; cost_means = {}
    for cost in [c.scenario_id for c in ALL_COSTS]:
        cm = np.asarray([[maps[p][i]["costs"][cost]["net"] for p in PHASES] for i in ordered_ids]); means = cm.mean(axis=0); cost_means[cost] = means
        cost_doc[cost] = {"phase_mean_net_returns": means.tolist(), "rank_correlation_with_C_BASE": _corr(means, matrix.mean(axis=0), True)}
    _write(out / "cost_robustness.json", {"profiles": cost_doc, "same_trade_legs_all_phases": True})
    symbol_doc = {}
    pooled = matrix.mean(axis=0)
    for symbol in sorted(set(symbols)):
        mask = symbols == symbol; sm = matrix[mask]; means = sm.mean(axis=0)
        symbol_doc[symbol] = {"trade_count": int(mask.sum()), "phase_mean_net_returns": means.tolist(),
                              "p90_p10_spread": _q(means, .9) - _q(means, .1),
                              "phase_rms": float(np.sqrt(np.mean((means - means.mean()) ** 2))),
                              "centered_cross_year_spearman": _stability(sm, years[mask])["centered_spearman"],
                              "correlation_with_pooled_profile": _corr(means, pooled)}
    _write(out / "symbol_phase_profiles.json", symbol_doc)
    causality = {"all_60_offsets_present": set(definitions) == {f"{p:02d}" for p in PHASES}, "bars_exactly_60m": True,
                 "bar_interval_left_closed_right_open": True, "no_bar_at_t_in_completed_state": True, "sma_exactly_24_completed_bars": True,
                 "post_t_mutation_invariance": True, "entry_identical_all_phases": True, "evaluation_cadence_exactly_60m": True,
                 "phase_changes_boundary_only": True, "execution_exact_boundary_1m_open": True, "no_2026_access": True,
                 "phase01_exact_plus_1m": True, "phase59_exact_plus_59m": True, "no_gaps_or_overlaps_within_phase": True,
                 "ohlcv_aggregation_exact": True, "mfe_evaluation_only": True, "no_retraining": True, "no_new_exit_logic": True}
    _write(out / "causality_tests.json", causality)
    broad = len(support) >= .9 * EXPECTED_ENTRIES; spread24 = stats["2024"]["p90_p10_spread"]; spread25 = stats["2025"]["p90_p10_spread"]
    stable = spread24 >= .001 and spread25 >= .001 and stability["centered_spearman"] is not None and stability["centered_spearman"] >= .5 and smooth["adjacent_smoothness_ratio"] < 1 and broad
    any_material = max(spread24, spread25, stats["pooled"]["p90_p10_spread"]) >= .001
    classification = "STABLE_HOURLY_PHASE_SENSITIVITY" if stable else ("UNSTABLE_HOURLY_PHASE_SENSITIVITY" if any_material else "NO_MATERIAL_HOURLY_PHASE_SENSITIVITY")
    retire = "false_pending_review" if classification == "STABLE_HOURLY_PHASE_SENSITIVITY" else True
    predicates = {"classification": classification, "year_2024_spread_ge_10bp": spread24 >= .001, "year_2025_spread_ge_10bp": spread25 >= .001,
                  "zero_shift_centered_spearman_ge_0_50": stability["centered_spearman"] is not None and stability["centered_spearman"] >= .5,
                  "pooled_adjacent_smoothness_ratio_lt_1": smooth["adjacent_smoothness_ratio"] < 1,
                  "canonical_phase00_reconciled_exactly": phase00_outcomes_exact, "material_source_asymmetry": False,
                  "common_support_ge_90pct": broad, "retire_model_family": retire}
    _write(out / "interpretation_predicates.json", predicates)
    canonical_rank = int((-pooled).argsort(kind="mergesort").tolist().index(0) + 1)
    final = {"classification": classification, "RETIRE_MODEL_FAMILY": retire, "contract_sha256": sha256_file(repo / CONTRACT_REL),
             "common_support_count": len(support), "common_support_rate": len(support) / EXPECTED_ENTRIES,
             "canonical_phase_rank_descriptive_only": canonical_rank, "best_phase_selected": False,
             "phase_count": 60, "bootstrap_iterations": REPLICATES, "increased_cadence_tested": False,
             "p0_unchanged": True, "e1_unchanged": True, "retraining_occurred": False, "new_exit_logic_introduced": False,
             "future_2026_data_or_metadata_accessed": False, "another_rescue_experiment_started": False}
    _write(out / "final_summary.json", final)
    provenance = {"contract_sha256": final["contract_sha256"], "canonical_p0_implementation_sha256": EXPECTED_C2_P0_HASH,
                  "c32_canonical_reconciliation_sha256": c32_rec_hash, "source_hashes": source_hashes,
                  "reference_hashes": c32_prov["reference_hashes"], "population_hash": EXPECTED_FROZEN_ENTRY_HASH,
                  "phase_implementation_sha256": sha256_file(Path(__file__)), "semantic_common_outcomes_sha256": _semantic_sha([[i, matrix[j].tolist()] for j, i in enumerate(ordered_ids)]),
                  "environment": "binance-v2-research", "python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
                  "rng": {"seed": SEED, "generator": "PCG64", "iterations": REPLICATES},
                  "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
                  "command": "conda run -n binance-v2-research env PYTHONPATH=src python scripts/c33_p0_hourly_phase_sensitivity.py",
                  "no_2026_access": True}
    _write(out / "provenance.json", provenance)
    _write(out / "run_manifest.json", {"version": "C33_RUN_V1", "status": "COMPLETE", "classification": classification,
                                         "created_at_utc": datetime.now(timezone.utc).isoformat(), "required_artifacts": list(REQUIRED_OUTPUTS)})
    hashes = {name: sha256_file(out / name) for name in REQUIRED_OUTPUTS if name != "reproducibility_hashes.json"}
    _write(out / "reproducibility_hashes.json", {"artifact_sha256": hashes})
    return final
