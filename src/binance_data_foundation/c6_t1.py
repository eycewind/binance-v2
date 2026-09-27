"""C6 T1 readiness and governed, authorization-gated C6 T2 executor.

Import and readiness construction never execute economics.  The production
loader is reachable only through the explicit one-shot authorization barrier.
"""
from __future__ import annotations

import hashlib
import csv
import fcntl
import gzip
import json
import math
import os
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

from .c5_t1 import COSTS as C5_COST_CASES, cost_ledger as c5_cost_ledger
from .c6_execution_freeze_pin import EXECUTION_FREEZE_SHA256

CONTRACT_SHA256 = "4ef0452314a4c289823896c641660836e9177afe6667bc7bf12de18cc52c09a0"
CANONICAL_C5_SHA256 = "094c81c306f1084146db55cee3c6f38178e58a0e72e55e056bb0dd1eb6c46884"
T2_EXECUTION_FLAG = "AUTHORIZE_C6_T2_ONE_SHOT"
EXECUTION_FREEZE_REL = "artifacts/c6_simple_t2_exit_controls/t2_execution_freeze.json"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
YEARS = (2024, 2025)
CONTROL_REGISTRY = (
    "P0_HELD_V1", "G1_Q75_EXIT_V1", "P1_Q75_EXIT_V1",
    "S1_EXIT_FIRST_T2_V1", "S2_EXIT_SECOND_T2_V1",
    "S3_G1_TIMING_PERMUTATION_V1", "S4_FIRST_T2_COIN_FLIP_V1",
)
ALIASES = {"EXIT_FIRST_T2": "S1_EXIT_FIRST_T2_V1", "EXIT_SECOND_T2": "S2_EXIT_SECOND_T2_V1",
           "RANDOM_TIMING_CONTROL": "S3_G1_TIMING_PERMUTATION_V1", "COIN_FLIP_CONTROL": "S4_FIRST_T2_COIN_FLIP_V1"}
PRIMARY_HIERARCHY = (
    ("S1_EXIT_FIRST_T2_V1", "P0_HELD_V1"),
    ("G1_Q75_EXIT_V1", "S1_EXIT_FIRST_T2_V1"),
    ("G1_Q75_EXIT_V1", "S3_G1_TIMING_PERMUTATION_V1"),
)
LABELS = ("INSUFFICIENT_EVIDENCE", "COUNTS_AGAINST_SIMPLE_T2_EXPLANATION",
          "SIMPLE_T2_EXIT_EXPLAINS_OBSERVED_VALUE", "MIXED",
          "MODEL_TIMING_ADDS_ECONOMIC_VALUE", "MODEL_SELECTION_BEATS_RANDOM_TIMING")
BOOTSTRAP = {"unit": "whole_trade", "block": "four-entry-week moving blocks", "block_length_entry_weeks": 4,
             "replicates": 2000, "generator": "PCG64", "seed": 20240923,
             "interval": [0.025, 0.975], "quantile_method": "Type-7 / linear",
             "sole_sensitivity": "whole-calendar-month trade-cluster bootstrap with same replicates/generator/seed/interval"}
COSTS = {"C0": {"fee_per_leg": 0.0, "adverse_slippage_per_leg": 0.0},
         "C_BASE": {"fee_per_leg": .001, "adverse_slippage_per_leg": .0002},
         "C_S5": {"fee_per_leg": .001, "adverse_slippage_per_leg": .0005},
         "C_S10": {"fee_per_leg": .001, "adverse_slippage_per_leg": .001}}

UPSTREAM = {
    "canonical_c5_trade_results": ("artifacts/c5_economic_exit_policy/t2/trade_results.csv", CANONICAL_C5_SHA256),
    "c5_t1_readiness": ("artifacts/c5_economic_exit_policy/t1_readiness.json", "8c63b9e39b0b5365014c05c74bc1c57907ad9072109d3dbc8c2c430c385f6b4a"),
    "c5_replay_manifest": ("artifacts/c5_economic_exit_policy/t2/replay_manifest.json", "4d3a6089dca013aea0817bf11bfe219f1e06b83f16a8fffcb3540bc6e0caea77"),
    "t2_snapshots_2024": ("artifacts/c4_sequential_exit_state/local/t2_snapshots.csv", "b0dc7444d97fc17f1c81510c68509d47ff374bb16bd7578956b9f5dcb519a417"),
    "g1_p1_outputs_2024": ("artifacts/c4_sequential_exit_state/development_predictions_2024.csv", "1c6b80e0cbb17c7a31c686c9688d3200a1d4e78a1d0fe90c8ef5cf4a42129381"),
    "g1_p1_outputs_2025": ("artifacts/c4_sequential_exit_state/locked_2025/predictions.csv", "ad087ebf7469d5682ed20f522967e7b9400d3452e9e60f433bfef6330a7deb2a"),
    "diagnostic_provenance": ("artifacts/c6_t2_trigger_diagnostics/provenance.json", "45ae60b193d3c21562c9426e88177f7a537c3b007d04ce85f640e343ac712724"),
    "diagnostic_reproducibility": ("artifacts/c6_t2_trigger_diagnostics/reproducibility.json", "20a0352ac7139f6900c4198a779e3c93749b720d71e7b3b6622e96f51f6f79de"),
    "diagnostic_path_lengths": ("artifacts/c6_t2_trigger_diagnostics/t2_path_length.json", "df262e4175647ffe47bb33d3ebcfce21020a48f76bcf9aa110ba36dcf58dd74a"),
}

def approved_path(path: Path | str, *, must_exist: bool = True) -> Path:
    """Apply the lexical barrier, then reject a forbidden resolved target."""
    reject_sealed_path(path)
    try:
        resolved = Path(path).resolve(strict=must_exist)
    except FileNotFoundError:
        raise
    reject_sealed_path(resolved)
    return resolved

def sha256(path: Path) -> str:
    path = approved_path(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()

def provenance_gate(repo: Path, upstream: Mapping[str, tuple[str, str]] = UPSTREAM) -> dict:
    # Every caller-controlled string is rejected lexically before any filesystem API.
    reject_sealed_path(repo)
    for rel, _expected in upstream.values():
        reject_sealed_path(rel)
        reject_sealed_path(os.path.join(os.fspath(repo), os.fspath(rel)))
    repo = approved_path(repo)
    contract = approved_path(repo / "contracts/C6_simple_t2_exit_controls_CONTRACT.md")
    if not contract.is_file() or sha256(contract) != CONTRACT_SHA256:
        raise RuntimeError("C6 contract hash mismatch")
    checked = {}
    for name, (rel, expected) in upstream.items():
        try: path = approved_path(repo / rel)
        except FileNotFoundError as exc: raise RuntimeError(f"missing accepted upstream artifact: {rel}") from exc
        if not path.is_file(): raise RuntimeError(f"missing accepted upstream artifact: {rel}")
        actual = sha256(path)
        if actual != expected: raise RuntimeError(f"upstream provenance mismatch: {name}")
        checked[name] = {"path": rel, "sha256": actual}
    # Structural manifests only: never parse the canonical economic table.
    readiness = json.loads(approved_path(repo / upstream["c5_t1_readiness"][0]).read_text())
    pop = readiness["four_population_layers"]["replay_authorized_complete_path"]
    expected = {"pooled": {"trades": 439, "snapshots": 38745},
                "by_year": {"2024": {"trades": 155}, "2025": {"trades": 284}},
                "by_symbol": {"BTCUSDT": {"trades": 74}, "ETHUSDT": {"trades": 85},
                              "SOLUSDT": {"trades": 106}, "XRPUSDT": {"trades": 87}, "BNBUSDT": {"trades": 87}}}
    if any(pop["pooled"].get(k) != v for k,v in expected["pooled"].items()):
        raise RuntimeError("replay population mismatch: pooled")
    for scope in ("by_year", "by_symbol"):
        for key, vals in expected[scope].items():
            got = pop[scope][key]
            if any(got.get(k) != v for k, v in vals.items()): raise RuntimeError(f"replay population mismatch: {scope}/{key}")
    return {"status": "PASS", "artifacts": checked, "population": pop,
            "canonical_economic_rows_opened": False, "sealed_paths_enumerated": False}

@dataclass(frozen=True)
class Snapshot:
    row_id: str
    completed_boundary: datetime

@dataclass(frozen=True)
class P0Exit:
    execution_ts: datetime
    raw_open: float

@dataclass(frozen=True)
class ControlExit:
    decision_ts: datetime | None
    execution_ts: datetime
    raw_open: float
    trigger_row_id: str | None
    label: int | str
    executable: bool
    failure: str | None = None

def execute_timing_label(path: Sequence[Snapshot], label: int | str,
                         minute_opens: Mapping[datetime, Sequence[float]], p0: P0Exit) -> ControlExit:
    """Execute one frozen label. The boundary is the immediate next interval open."""
    ordered = sorted(path, key=lambda x: (x.completed_boundary, x.row_id))
    if len({x.row_id for x in ordered}) != len(ordered): raise ValueError("duplicate T2 snapshot identity")
    if label == "P0_FALLBACK": return ControlExit(None, p0.execution_ts, p0.raw_open, None, label, True)
    k = int(label)
    if k < 1 or k > len(ordered): raise ValueError("impossible trigger ordinal")
    snap = ordered[k - 1]; ts = snap.completed_boundary
    if ts >= p0.execution_ts: return ControlExit(None, p0.execution_ts, p0.raw_open, None, "P0_FALLBACK", True)
    values = minute_opens.get(ts)
    if values is None: return ControlExit(ts, ts, math.nan, snap.row_id, k, False, "missing_immediate_next_1m_open")
    if len(values) != 1 or not math.isfinite(float(values[0])) or float(values[0]) <= 0:
        return ControlExit(ts, ts, math.nan, snap.row_id, k, False, "invalid_or_duplicate_immediate_next_1m_open")
    return ControlExit(ts, ts, float(values[0]), snap.row_id, k, True)

def exit_first_t2(path, minute_opens, p0):
    if not path: raise ValueError("S1 requires at least one replay-authorized snapshot")
    return execute_timing_label(path, 1, minute_opens, p0)

def exit_second_t2(path, minute_opens, p0):
    if not path: raise ValueError("zero-snapshot trade is outside the frozen population")
    return execute_timing_label(path, 2 if len(path) >= 2 else "P0_FALLBACK", minute_opens, p0)

@dataclass(frozen=True)
class TimingTrade:
    trade_id: str
    year: int
    symbol: str
    path_length: int
    g1_label: int | str

def derive_g1_timing_label(*, executed_before_p0: bool, trigger_ordinal: int | None, path_length: int) -> int | str:
    """Derive S3's donor label from accepted G1 timing identity fields only."""
    if path_length < 1: raise ValueError("replay-authorized path must be nonempty")
    if not executed_before_p0:
        if trigger_ordinal is not None: raise ValueError("fallback G1 row cannot carry a trigger ordinal")
        return "P0_FALLBACK"
    if trigger_ordinal is None or not 1 <= int(trigger_ordinal) <= path_length:
        raise ValueError("accepted G1 trigger ordinal is incompatible with its path")
    return int(trigger_ordinal)

def _hungarian(cost: list[list[int]]) -> list[int]:
    """Square minimum assignment, returning column per row (exact Python integers)."""
    n = len(cost); u = [0] * (n + 1); v = [0] * (n + 1); p = [0] * (n + 1); way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i; j0 = 0; minv = [None] * (n + 1); used = [False] * (n + 1)
        while True:
            used[j0] = True; i0 = p[j0]; delta = None; j1 = 0
            for j in range(1, n + 1):
                if used[j]: continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if minv[j] is None or cur < minv[j]: minv[j], way[j] = cur, j0
                if delta is None or minv[j] < delta: delta, j1 = minv[j], j
            if delta is None: raise RuntimeError("no complete compatible assignment")
            for j in range(n + 1):
                if used[j]: u[p[j]] += delta; v[j] -= delta
                elif j: minv[j] -= delta
            j0 = j1
            if p[j0] == 0: break
        while True:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
            if j0 == 0: break
    ans = [-1] * n
    for j in range(1, n + 1): ans[p[j] - 1] = j - 1
    return ans

def _one_stratum(trades: Sequence[TimingTrade], rng: np.random.Generator, stream_start: int) -> tuple[list[dict],dict]:
    recipients = sorted(trades, key=lambda x: x.trade_id)
    donors = sorted(trades, key=lambda x: (0 if isinstance(x.g1_label, int) else 1,
                                            -int(x.g1_label) if isinstance(x.g1_label, int) else 0, x.trade_id))
    n = len(trades); priorities = [[None] * n for _ in range(n)]
    # Required stream order is donor then recipient; incompatible edges consume no draw.
    draws=0
    for di, donor in enumerate(donors):
        for ri, recipient in enumerate(recipients):
            if donor.g1_label == "P0_FALLBACK" or int(donor.g1_label) <= recipient.path_length:
                priorities[di][ri] = int(rng.bit_generator.random_raw()); draws += 1
    # Rows are recipients. Add an exact lexicographic donor-ID tie breaker beneath total priority.
    base = n + 1; scale = base ** n; donor_rank = {d.trade_id: i for i, d in enumerate(sorted(donors, key=lambda x:x.trade_id))}
    forbidden = (1 << 64) * n * scale + scale
    cost = []
    for ri in range(n):
        row=[]
        for di, donor in enumerate(donors):
            priority = priorities[di][ri]
            row.append(forbidden if priority is None else priority * scale + donor_rank[donor.trade_id] * base ** (n - 1 - ri))
        cost.append(row)
    assigned = _hungarian(cost)
    if any(priorities[di][ri] is None for ri, di in enumerate(assigned)):
        raise RuntimeError("no complete compatible assignment")
    rows=[{"trade_id": r.trade_id, "donor_trade_id": donors[assigned[i]].trade_id,
             "label": donors[assigned[i]].g1_label, "path_length": r.path_length,
             "edge_priority_uint64": priorities[assigned[i]][i]} for i, r in enumerate(recipients)]
    audit={"year":recipients[0].year,"symbol":recipients[0].symbol,"compatible_edge_draws":draws,
           "priority_stream_start_inclusive":stream_start,"priority_stream_end_exclusive":stream_start+draws,
           "donor_order":[d.trade_id for d in donors],"recipient_order":[r.trade_id for r in recipients]}
    return rows,audit

def timing_permutations(trades: Sequence[TimingTrade], count: int = 1000, seed: int = 20240924) -> list[dict]:
    if count != 1000 or seed != 20240924: raise ValueError("frozen S3 count/seed required")
    if any(t.year not in YEARS or t.symbol not in SYMBOLS or t.path_length < 1 for t in trades): raise ValueError("invalid stratum/path")
    ids=[t.trade_id for t in trades]
    if len(ids) != len(set(ids)): raise ValueError("duplicate recipient/donor trade_id")
    for t in trades:
        if t.g1_label != "P0_FALLBACK" and (not isinstance(t.g1_label, int) or not 1 <= t.g1_label <= t.path_length):
            raise ValueError("invalid or impossible donor timing label")
    rng = np.random.Generator(np.random.PCG64(seed)); strata = defaultdict(list)
    for t in trades: strata[(t.year, t.symbol)].append(t)
    out=[]; stream_position=0
    for assignment in range(count):
        rows=[]; audit=[]
        for year in YEARS:
            for symbol in SYMBOLS:
                if strata[(year, symbol)]:
                    sr,sa=_one_stratum(strata[(year, symbol)],rng,stream_position); rows.extend(sr); audit.append(sa)
                    stream_position=sa["priority_stream_end_exclusive"]
        out.append({"assignment": assignment,"generator":"PCG64","master_seed":seed,
                    "retry_count":0,"result_filtering":False,"strata_audit":audit,"rows":rows})
    return out

def validate_permutations(trades: Sequence[TimingTrade], assignments: Sequence[dict]) -> dict:
    ids=[t.trade_id for t in trades]
    if len(ids) != len(set(ids)): raise RuntimeError("duplicate expected trade_id")
    if len(assignments) != 1000 or [a.get("assignment") for a in assignments] != list(range(1000)):
        raise RuntimeError("assignment indices must be exactly 0..999")
    source = {(y,s):Counter(t.g1_label for t in trades if (t.year,t.symbol)==(y,s)) for y in YEARS for s in SYMBOLS}
    by_id={t.trade_id:t for t in trades}; fallback=0
    for a in assignments:
        if a.get("generator") != "PCG64" or a.get("master_seed") != 20240924:
            raise RuntimeError("assignment RNG metadata mismatch")
        if a.get("retry_count") != 0 or a.get("result_filtering") is not False:
            raise RuntimeError("assignment retries/result filtering prohibited")
        if len(a["rows"]) != len(trades): raise RuntimeError("assignment count mismatch")
        recipient_ids=[r.get("trade_id") for r in a["rows"]]
        donor_ids=[r.get("donor_trade_id") for r in a["rows"]]
        if len(recipient_ids) != len(set(recipient_ids)) or set(recipient_ids) != set(ids):
            raise RuntimeError("recipient assignment is not an exact bijection")
        if len(donor_ids) != len(set(donor_ids)) or set(donor_ids) != set(ids):
            raise RuntimeError("donor assignment is not an exact bijection")
        got=defaultdict(Counter)
        for r in a["rows"]:
            t=by_id[r["trade_id"]]; got[(t.year,t.symbol)][r["label"]]+=1
            donor=by_id[r["donor_trade_id"]]
            if (t.year,t.symbol) != (donor.year,donor.symbol): raise RuntimeError("cross-stratum assignment")
            if r["label"] != donor.g1_label: raise RuntimeError("donor timing label changed")
            if r.get("path_length") != t.path_length: raise RuntimeError("recipient path length metadata changed")
            if r["label"] == "P0_FALLBACK": fallback += 1
            elif not isinstance(r["label"],int) or not 1 <= r["label"] <= t.path_length: raise RuntimeError("incompatible ordinal")
        if any(got[k] != source[k] for k in source): raise RuntimeError("stratum timing distribution changed")
    # Structural validity is necessary but not sufficient: authenticate the exact
    # frozen PCG64 stream, edge priorities, audits, matching and tie-break output.
    expected = timing_permutations(trades)
    if canonical_bytes(assignments) != canonical_bytes(expected):
        raise RuntimeError("S3 assignments differ from frozen deterministic reconstruction")
    blob=canonical_bytes(assignments)
    return {"assignments":len(assignments), "rows_per_assignment":len(trades), "strata_preserved":True,
            "timing_multisets_preserved":True, "feasibility_rate":1.0, "fallback_assignments":fallback,
            "byte_sha256":hashlib.sha256(blob).hexdigest()}

def coin_flip_labels(trades: Sequence[Mapping[str, object]], seed: int = 20240926) -> list[dict]:
    if seed != 20240926: raise ValueError("frozen S4 seed required")
    ordered=sorted(trades,key=lambda x:(x["entry_execution_ts"],x["symbol"],x["trade_id"]))
    rng=np.random.Generator(np.random.PCG64(seed))
    return [{"trade_id":str(t["trade_id"]), "label":1 if int(rng.binomial(1,.5)) else "P0_FALLBACK",
             "decisions":1} for t in ordered]

def moving_block_samples(entry_weeks: Mapping[str, str], replicates: int = 2000, seed: int = 20240923) -> list[list[str]]:
    if replicates != 2000 or seed != 20240923: raise ValueError("frozen market bootstrap required")
    dates={t:datetime.fromisoformat(w).date() for t,w in entry_weeks.items()}; lo=min(dates.values()); hi=max(dates.values())
    lo-=timedelta(days=lo.weekday()); hi-=timedelta(days=hi.weekday()); span=(hi-lo).days//7+1
    if span < 4: raise ValueError("insufficient four-week block support")
    at=defaultdict(list)
    for t,d in dates.items(): at[(d-lo).days//7].append(t)
    blocks=[range(i,i+4) for i in range(span-3)]
    if sum(any(at[j] for j in block) for block in blocks) < 2: raise ValueError("fewer than two nonempty candidate blocks")
    rng=np.random.Generator(np.random.PCG64(seed)); out=[]
    for _ in range(replicates):
        positions=[]
        while len(positions)<span: positions.extend(blocks[int(rng.integers(len(blocks)))])
        sample=[t for pos in positions[:span] for t in sorted(at[pos])]
        if not sample: raise RuntimeError("empty bootstrap sample")
        out.append(sample)
    return out

def calendar_month_samples(entry_times: Mapping[str,str], replicates: int = 2000, seed: int = 20240923) -> list[list[str]]:
    """Accepted whole-calendar-month trade-cluster uncertainty sensitivity."""
    if replicates != 2000 or seed != 20240923: raise ValueError("frozen calendar-month bootstrap required")
    groups=defaultdict(list)
    for trade,ts in entry_times.items(): groups[datetime.fromisoformat(ts).strftime("%Y-%m")].append(trade)
    months=sorted(groups)
    if len(months)<2: raise ValueError("fewer than two calendar-month clusters")
    rng=np.random.Generator(np.random.PCG64(seed)); out=[]
    for _ in range(replicates):
        selected=rng.integers(len(months),size=len(months))
        sample=[t for i in selected for t in sorted(groups[months[int(i)]])]
        if not sample: raise RuntimeError("empty calendar-month sample")
        out.append(sample)
    return out

def uncertainty_fixture(differences: np.ndarray, trade_ids: Sequence[str], samples: Sequence[Sequence[str]], seed: int = 20240925) -> dict:
    """Synthetic nesting: rows=assignments, columns=whole trades."""
    if seed != 20240925: raise ValueError("frozen combined uncertainty seed required")
    x=np.asarray(differences,float)
    if x.shape != (1000,len(trade_ids)) or len(samples) != 2000: raise ValueError("frozen dimensions required")
    pos={t:i for i,t in enumerate(trade_ids)}
    assignment=x.mean(axis=1); market=[]
    for sample in samples: market.append(float(np.mean([x[:,pos[t]].mean() for t in sample])))
    rng=np.random.Generator(np.random.PCG64(seed)); combined=[]; chosen=[]
    for sample in samples:
        j=int(rng.integers(1000)); chosen.append(j); combined.append(float(np.mean([x[j,pos[t]] for t in sample])))
    q=lambda a,p:np.quantile(a,p,method="linear").tolist()
    return {"assignment_summary":{"mean":float(assignment.mean()),"sd":float(assignment.std(ddof=1)),
            "min":float(assignment.min()),"max":float(assignment.max()),"quantiles":q(assignment,[.025,.25,.5,.75,.975]),
            "fraction_positive":float(np.mean(assignment>0))}, "market_interval":q(market,[.025,.975]),
            "combined_interval":q(combined,[.025,.975]), "combined_assignment_indices":chosen}

def evidence_label(point: float | None, interval: Sequence[float] | None, valid: bool = True) -> str:
    if not valid or point is None or interval is None: return "INSUFFICIENT"
    lo,hi=map(float,interval)
    if lo > 0 and point > 0: return "STRONG_POSITIVE"
    if hi < 0: return "STRONG_NEGATIVE"
    if point > 0: return "DIRECTIONAL_ONLY"
    return "NULL_OR_OPPOSING"

def reached_gates(labels: Sequence[str]) -> tuple[bool,bool,bool]:
    return (True, len(labels)>0 and labels[0]=="STRONG_POSITIVE",
            len(labels)>1 and labels[0]==labels[1]=="STRONG_POSITIVE")

def interpret(g1: str, g2: str | None=None, g3: str | None=None, *, auxiliary_positive=True,
              adverse_safety_breach=False) -> str:
    if g1 == "INSUFFICIENT" or (g1=="STRONG_POSITIVE" and g2 in (None,"INSUFFICIENT")) or (g1==g2=="STRONG_POSITIVE" and g3 in (None,"INSUFFICIENT")):
        return LABELS[0]
    if g1 in ("STRONG_NEGATIVE","NULL_OR_OPPOSING"): return LABELS[1]
    if g1 == "DIRECTIONAL_ONLY": return LABELS[3]
    if g2 == "STRONG_POSITIVE":
        # A mandatory adverse safety interval prevents either favorable advancement label.
        if adverse_safety_breach: return LABELS[3]
        if g3 == "STRONG_POSITIVE":
            return LABELS[5] if auxiliary_positive else LABELS[3]
        if g3 == "STRONG_NEGATIVE": return LABELS[3]
        return LABELS[4]
    if g2 == "STRONG_NEGATIVE": return LABELS[3]
    return LABELS[2]

def reporting_governance() -> dict:
    return {"primary":"pooled", "mandatory_years":[2024,2025], "mandatory_symbols":list(SYMBOLS),
            "year_specific_tuning":False, "symbol_specific_tuning":False,
            "symbol_support":{"minimum_distinct_trades":50,"below_minimum":"INSUFFICIENT SUPPORT; still descriptive and retained pooled"}}

def reject_sealed_path(path: Path | str) -> None:
    """Reject a reference by name only; never resolve, stat, or enumerate it."""
    raw=os.fspath(path).replace("\\","/")
    components=[p.casefold() for p in raw.split("/") if p not in ("", ".")]
    for component in components:
        stem=component.rsplit(".",1)[0]
        tokens=[t for t in re.split(r"[^a-z0-9]+",stem) if t]
        if ("sealed" in stem or "confirmation" in stem or "2026" in stem or
                any(t == "2026" or re.fullmatch(r"2026q[1-4]",t) for t in tokens)):
            raise PermissionError("sealed confirmation path prohibited")

def _lexically_safe_paths(*paths: Path | str) -> None:
    """Pure string-only safety barrier; deliberately performs no filesystem call."""
    for path in paths: reject_sealed_path(path)

def _ledger_events(path: Path) -> list[dict]:
    if not path.exists(): return []
    events=[]
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try: events.append(json.loads(line))
            except Exception as exc: raise RuntimeError("invalid existing attempt ledger") from exc
    return events

def append_attempt_event(path: Path, event: Mapping[str, object]) -> str:
    _lexically_safe_paths(path, os.fspath(path) + ".lock")
    path=approved_path(path,must_exist=False)
    _lexically_safe_paths(path, os.fspath(path) + ".lock")
    path.parent.mkdir(parents=True,exist_ok=True)
    lock_path=Path(os.fspath(path) + ".lock")
    try:
        lock_handle=lock_path.open("a+b")
    except Exception as exc:
        raise RuntimeError("cannot acquire attempt-ledger lock") from exc
    try:
        try: fcntl.flock(lock_handle.fileno(),fcntl.LOCK_EX)
        except Exception as exc: raise RuntimeError("cannot acquire attempt-ledger lock") from exc
        return _append_attempt_event_locked(path,event)
    finally:
        try: fcntl.flock(lock_handle.fileno(),fcntl.LOCK_UN)
        finally: lock_handle.close()

def _append_attempt_event_locked(path: Path, event: Mapping[str, object]) -> str:
    common={"attempt_id","event","time","configuration_hash","source_hash","input_hashes","random_seeds","contract_sha256","readiness_sha256","status","output_hashes"}
    kind=event.get("event")
    allowed=common | ({"failure_reason"} if kind == "FAIL" else set())
    if set(event) != allowed or kind not in {"START","PASS","FAIL"} or event.get("status") != kind:
        raise ValueError("invalid attempt event schema/status")
    attempt=str(event["attempt_id"]); prior=[x for x in _ledger_events(path) if str(x.get("attempt_id"))==attempt]
    if kind == "START":
        if prior: raise RuntimeError("attempt already exists")
        if event["output_hashes"]: raise ValueError("START cannot contain output hashes")
    else:
        if len(prior) != 1 or prior[0].get("event") != "START": raise RuntimeError("terminal event requires exactly one open START")
        if kind == "PASS" and not event["output_hashes"]: raise ValueError("PASS requires output hashes")
        if kind == "FAIL" and not str(event.get("failure_reason","")).strip(): raise ValueError("FAIL requires failure reason")
    line=canonical_bytes(dict(event))
    with path.open("ab") as f: f.write(line); f.flush(); os.fsync(f.fileno())
    return hashlib.sha256(line).hexdigest()

_PRODUCTION_EXECUTION_CAPABILITY = object()

def _as_bool(value: object) -> bool:
    return value is True or str(value).casefold() == "true"

def _number(value: object) -> float | None:
    if value in (None, "", "None", "null"): return None
    return float(value)

def _metric_float(value: object) -> float:
    if isinstance(value,bool) or str(value).casefold() in ("true","false"):
        return float(_as_bool(value))
    return float(value)

def _cost_row(base: Mapping[str, object], policy: str, raw_exit: float,
              exit_ms: int, triggered: bool, case_name: str) -> dict:
    entry=float(base["raw_entry_price"]); quantity=1000.0/entry
    ledger=c5_cost_ledger(entry,[(raw_exit,quantity)],C5_COST_CASES[case_name],quantity)
    raw_return=raw_exit/entry-1
    return {**base,"policy_id":policy,"cost_scenario":case_name,"raw_exit_price":raw_exit,
            "exit_execution_ms":exit_ms,"triggered":triggered,"executable":True,
            "holding_duration_seconds":(exit_ms-int(base["entry_execution_ms"]))/1000,
            "raw_price_return":raw_return,"gross_return":ledger["gross_return"],"net_return":ledger["net_return"],
            "entry_fee_quote":ledger["entry_fee_quote"],"exit_fee_quote":ledger["exit_fee_quote"],
            "entry_slippage_quote":ledger["entry_slippage_quote"],"exit_slippage_quote":ledger["exit_slippage_quote"],
            "slippage_cost_quote":ledger["slippage_cost_quote"],"total_transaction_cost_quote":ledger["total_transaction_cost_quote"],
            "fixed_replay_legs":ledger["fixed_replay_legs"],"fixed_replay_notional":1000.0}

def _evaluate_exit(trade: Mapping[str,object], exit_ms: int, raw_exit: float) -> dict:
    entry=float(trade["raw_entry_price"]); entry_ms=int(trade["entry_execution_ms"]);p0_ms=int(trade["p0_execution_ms"])
    minute_highs={int(k):float(v) for k,v in trade.get("minute_highs",{}).items()}
    held=[entry,raw_exit,*[v for ms,v in minute_highs.items() if entry_ms<ms<exit_ms]]
    common_mfe=float(trade.get("common_mfe",max([entry,float(trade["p0_price"]),*minute_highs.values()])/entry-1))
    held_mfe=max(held)/entry-1;raw_return=raw_exit/entry-1
    future=[v for ms,v in minute_highs.items() if exit_ms<ms<p0_ms]
    if exit_ms<p0_ms:future.append(float(trade["p0_price"]))
    future_max=max(future) if future else None;common_valid=common_mfe>=.005-1e-15;held_valid=held_mfe>=.005-1e-15
    out={"common_mfe":common_mfe,"held_mfe":held_mfe,"common_capture_fraction":raw_return/common_mfe if common_valid else None,
         "held_capture_fraction":raw_return/held_mfe if held_valid else None,"common_capture_gap":common_mfe-raw_return,
         "held_peak_surrender":held_mfe-raw_return,"fraction_positive_mfe_surrendered":(common_mfe-raw_return)/common_mfe if common_valid else None,
         "green_to_red":held_mfe>0 and raw_return<0,"preserved_at_least_half_peak":raw_return>=.5*common_mfe if common_valid else None,
         "early_exit":exit_ms<p0_ms,"opportunity_foregone":future_max/raw_exit-1 if future_max is not None else None,
         "remaining_future_mfe_from_entry":future_max/entry-1 if future_max is not None else None}
    for pct in (2,3,5):out[f"subsequent_plus_{pct}"]=future_max>=entry*(1+pct/100) if future_max is not None else None
    return out

def _summary(rows: Sequence[Mapping[str, object]]) -> dict:
    usable=[r for r in rows if r.get("executable",True)]
    if not usable: return {"trades":len(rows),"usable":0}
    net=np.asarray([float(r["net_return"]) for r in usable]); raw=np.asarray([float(r["raw_price_return"]) for r in usable])
    q10=float(np.quantile(net,.1,method="linear")); es=net[net<=q10]
    return {"trades":len(rows),"usable":len(usable),"raw_mean_return":float(raw.mean()),
            "net_expectancy":float(net.mean()),"median_net_return":float(np.median(net)),
            "fixed_notional_net_pnl":float(net.sum()*1000),"win_rate":float(np.mean(net>0)),
            "zero_rate":float(np.mean(net==0)),"loss_rate":float(np.mean(net<0)),
            "downside_deviation":float(np.sqrt(np.mean(np.minimum(net,0)**2))),
            "p05":float(np.quantile(net,.05,method="linear")),"p10":q10,"worst_trade":float(net.min()),
            "expected_shortfall_10":float(es.mean()),"holding_seconds":float(np.mean([float(r["holding_duration_seconds"]) for r in usable])),
            "entry_fee":float(sum(float(r.get("entry_fee_quote",0)) for r in usable)),
            "exit_fee":float(sum(float(r.get("exit_fee_quote",0)) for r in usable)),
            "slippage":float(sum(float(r.get("slippage_cost_quote",0)) for r in usable)),
            "total_cost":float(sum(float(r.get("total_transaction_cost_quote",0)) for r in usable)),
            **{k:float(np.mean([_metric_float(r[k]) for r in usable if r.get(k) not in (None,"")])) if any(r.get(k) not in (None,"") for r in usable) else None
               for k in ("common_mfe","held_mfe","common_capture_fraction","held_capture_fraction","common_capture_gap",
                         "held_peak_surrender","fraction_positive_mfe_surrendered","green_to_red","preserved_at_least_half_peak",
                         "opportunity_foregone","remaining_future_mfe_from_entry","subsequent_plus_2","subsequent_plus_3","subsequent_plus_5")}}

def _average_summaries(items: Sequence[Mapping[str,object]]) -> dict:
    keys=set().union(*(x.keys() for x in items));out={}
    for key in keys:
        values=[float(x[key]) for x in items if isinstance(x.get(key),(int,float))]
        out[key]=float(np.mean(values)) if values else None
    return out

def _paired_interval(values: Mapping[str,float], weeks: Mapping[str,str]) -> dict:
    samples=moving_block_samples(weeks)
    point=float(np.mean([values[t] for t in sorted(values)]))
    reps=[float(np.mean([values[t] for t in sample])) for sample in samples]
    return {"point_estimate":point,"ci95":np.quantile(reps,[.025,.975],method="linear").tolist(),
            "replicates":2000,"generator":"PCG64","seed":20240923,"samples":samples}

def _safety_panel(left: Mapping[str,Mapping[str,object]], right: Mapping[str,Mapping[str,object]],
                  samples: Sequence[Sequence[str]]) -> dict:
    directions={"expected_shortfall_10":"higher","green_to_red":"lower","preserved_at_least_half_peak":"higher",
                "opportunity_foregone":"lower","subsequent_plus_2":"lower","subsequent_plus_3":"lower","subsequent_plus_5":"lower"}
    panel={};breach=False
    for metric,direction in directions.items():
        def statistic(ids):
            if metric=="expected_shortfall_10":
                def es(rows):
                    a=np.asarray([float(rows[t]["net_return"]) for t in ids]);q=np.quantile(a,.1,method="linear");return float(a[a<=q].mean())
                return es(left)-es(right)
            vals=[]
            for t in ids:
                if left[t].get(metric) not in (None,"") and right[t].get(metric) not in (None,""):
                    vals.append(_metric_float(left[t][metric])-_metric_float(right[t][metric]))
            return float(np.mean(vals)) if vals else math.nan
        ids=sorted(left.keys()&right.keys());point=statistic(ids);reps=np.asarray([statistic(s) for s in samples]);reps=reps[np.isfinite(reps)]
        ci=np.quantile(reps,[.025,.975],method="linear").tolist() if len(reps) else None
        adverse=ci is not None and (ci[1]<0 if direction=="higher" else ci[0]>0)
        panel[metric]={"point_estimate":point,"ci95":ci,"favorable_direction":direction,"adverse_interval_breach":adverse}
        breach=breach or adverse
    return {"metrics":panel,"unacceptable_safety_breach":breach}

def execute_economic_fixture(trades: Sequence[Mapping[str, object]], config: Mapping[str, object]) -> dict:
    """Pure fixed C6 executor used by production after governed loading and by synthetic tests."""
    frozen={k:config[k] for k in _runner_config()}
    if frozen != _runner_config(): raise RuntimeError("non-frozen C6 configuration")
    config=frozen
    ordered=sorted(trades,key=lambda t:(str(t["entry_execution_ts"]),str(t["symbol"]),str(t["trade_id"])))
    timing=[]
    for t in ordered:
        paths=t["path"]
        if not paths: raise RuntimeError("zero-snapshot trade")
        label=derive_g1_timing_label(executed_before_p0=bool(t["g1_executed_before_p0"]),
            trigger_ordinal=t.get("g1_trigger_ordinal"),path_length=len(paths))
        timing.append(TimingTrade(str(t["trade_id"]),int(t["year"]),str(t["symbol"]),len(paths),label))
    assignments=timing_permutations(timing)
    validate_permutations(timing,assignments)
    flips={r["trade_id"]:r["label"] for r in coin_flip_labels(ordered)}
    deterministic_rows=[]; s3_by_assignment=[]
    for t in ordered:
        base={k:t[k] for k in ("trade_id","symbol","year","entry_execution_ts","entry_execution_ms","raw_entry_price","trade_entry_week")}
        base["t2_eligible"]=True
        path=t["path"]; p0_ms=int(t["p0_execution_ms"]); p0_price=float(t["p0_price"])
        def chosen(label):
            if label=="P0_FALLBACK": return p0_ms,p0_price,False
            snap=path[int(label)-1]; ms=int(snap["execution_ms"])
            if ms>=p0_ms:return p0_ms,p0_price,False
            price=_number(snap.get("raw_open"))
            if price is None or not math.isfinite(price) or price<=0: raise RuntimeError("missing or invalid immediate next 1m open")
            return ms,price,True
        labels={"S1_EXIT_FIRST_T2_V1":1,"S2_EXIT_SECOND_T2_V1":2 if len(path)>=2 else "P0_FALLBACK",
                "S4_FIRST_T2_COIN_FLIP_V1":flips[str(t["trade_id"])]}
        for policy,label in labels.items():
            ms,price,trig=chosen(label)
            evaluation=_evaluate_exit(t,ms,price)
            for case in COSTS: deterministic_rows.append({**_cost_row(base,policy,price,ms,trig,case),**evaluation})
    by_trade={str(t["trade_id"]):t for t in ordered}
    s3_summary_by_cost={case:[] for case in COSTS}
    for assignment in assignments:
        rows_by_cost={case:[] for case in COSTS}
        for mapping in assignment["rows"]:
            t=by_trade[mapping["trade_id"]]; base={k:t[k] for k in ("trade_id","symbol","year","entry_execution_ts","entry_execution_ms","raw_entry_price","trade_entry_week")};base["t2_eligible"]=True
            label=mapping["label"]
            if label=="P0_FALLBACK":ms,price,trig=int(t["p0_execution_ms"]),float(t["p0_price"]),False
            else:
                snap=t["path"][int(label)-1];ms=int(snap["execution_ms"]);price=float(snap["raw_open"]);trig=True
                if ms>=int(t["p0_execution_ms"]):ms,price,trig=int(t["p0_execution_ms"]),float(t["p0_price"]),False
            evaluation=_evaluate_exit(t,ms,price)
            for case in COSTS:rows_by_cost[case].append({**_cost_row(base,"S3_G1_TIMING_PERMUTATION_V1",price,ms,trig,case),**evaluation})
        s3_by_assignment.append(rows_by_cost["C_BASE"])
        for case in COSTS:s3_summary_by_cost[case].append(_summary(rows_by_cost[case]))
    accepted=[]
    for t in ordered:
        for row in t["accepted_policy_rows"]:
            if row["policy_id"] in CONTROL_REGISTRY[:3]:accepted.append(dict(row))
    all_deterministic=accepted+deterministic_rows
    index={(str(r["trade_id"]),str(r["policy_id"])):r for r in all_deterministic if r["cost_scenario"]=="C_BASE"}
    weeks={str(t["trade_id"]):str(t["trade_entry_week"]) for t in ordered}
    contrasts=[]
    for left,right in PRIMARY_HIERARCHY[:2]:
        vals={tid:float(index[(tid,left)]["net_return"])-float(index[(tid,right)]["net_return"]) for tid in weeks}
        contrasts.append(_paired_interval(vals,weeks))
    trade_ids=[str(t["trade_id"]) for t in ordered]
    s3=np.asarray([[float(r["net_return"]) for r in rows] for rows in s3_by_assignment])
    g1=np.asarray([float(index[(tid,"G1_Q75_EXIT_V1")]["net_return"]) for tid in trade_ids])
    differences=g1[None,:]-s3
    samples=contrasts[0].pop("samples");contrasts[1].pop("samples")
    uncertainty=uncertainty_fixture(differences,trade_ids,samples)
    g3={"point_estimate":float(differences.mean()),"ci95":uncertainty["market_interval"]}
    labels=[evidence_label(c["point_estimate"],c["ci95"]) for c in contrasts]+[evidence_label(g3["point_estimate"],g3["ci95"])]
    assignment_ci=uncertainty["assignment_summary"]["quantiles"][[.025,.25,.5,.75,.975].index(.025)],uncertainty["assignment_summary"]["quantiles"][-1]
    auxiliary_positive=assignment_ci[0]>0 and uncertainty["combined_interval"][0]>0
    g1_rows={tid:index[(tid,"G1_Q75_EXIT_V1")] for tid in trade_ids};s1_rows={tid:index[(tid,"S1_EXIT_FIRST_T2_V1")] for tid in trade_ids}
    s3_mean_rows={}
    for col,tid in enumerate(trade_ids):
        template=dict(s3_by_assignment[0][col])
        for metric in ("net_return","green_to_red","preserved_at_least_half_peak","opportunity_foregone","subsequent_plus_2","subsequent_plus_3","subsequent_plus_5"):
            vals=[_metric_float(rows[col][metric]) for rows in s3_by_assignment if rows[col].get(metric) not in (None,"")]
            template[metric]=float(np.mean(vals)) if vals else None
        s3_mean_rows[tid]=template
    safety={"G1_minus_S1":_safety_panel(g1_rows,s1_rows,samples),"G1_minus_S3":_safety_panel(g1_rows,s3_mean_rows,samples)}
    safety_breach=any(x["unacceptable_safety_breach"] for x in safety.values()) or any(bool(t.get("adverse_safety_breach",False)) for t in ordered)
    overall=interpret(labels[0],labels[1] if reached_gates(labels)[1] else None,
                      labels[2] if reached_gates(labels)[2] else None,
                      auxiliary_positive=auxiliary_positive,adverse_safety_breach=safety_breach)
    scopes={"pooled":lambda r:True,**{str(y):lambda r,y=y:int(r["year"])==y for y in YEARS},
            **{s:lambda r,s=s:r["symbol"]==s for s in SYMBOLS}}
    summaries={scope:{p:{c:_summary([r for r in all_deterministic if fn(r) and r["policy_id"]==p and r["cost_scenario"]==c])
                    for c in COSTS} for p in (*CONTROL_REGISTRY[:3],"S1_EXIT_FIRST_T2_V1","S2_EXIT_SECOND_T2_V1","S4_FIRST_T2_COIN_FLIP_V1")}
               for scope,fn in scopes.items()}
    return {"control_registry":list(CONTROL_REGISTRY),"hierarchy":[list(x) for x in PRIMARY_HIERARCHY],
            "interpretation":overall,"metrics":{"policy_summaries":summaries,
                "s3_assignment_averaged":{case:_average_summaries(s3_summary_by_cost[case]) for case in COSTS}},
            "statistics":{"gates":[*contrasts,g3],"evidence_labels":labels,"reached":list(reached_gates(labels)),
                          "assignment_uncertainty":uncertainty,"safety":safety,"adverse_safety_breach":safety_breach},
            "s3_assignments":assignments,"s3_authentication":validate_permutations(timing,assignments),
            "s3_structural_inputs":[asdict(t) for t in timing],
            "seeds":dict(config["seeds"])}

def _load_production_trades(canonical_path: Path) -> list[dict]:
    """Load only after all governance/hash/population gates and START have passed."""
    canonical_path=approved_path(canonical_path); repo=canonical_path.parents[3]
    rows=[]
    with canonical_path.open(newline="",encoding="utf-8") as handle: rows=list(csv.DictReader(handle))
    accepted={}
    for row in rows:
        if row.get("policy_id") not in CONTROL_REGISTRY[:3]:continue
        accepted.setdefault(row["trade_id"],[]).append(row)
    snapshot_path=approved_path(repo/UPSTREAM["t2_snapshots_2024"][0]); paths=defaultdict(list)
    with snapshot_path.open(newline="",encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("trade_id") in accepted and _as_bool(row.get("target_eligible")):
                paths[row["trade_id"]].append(row)
    out=[]
    for trade_id,policy_rows in accepted.items():
        p0=next(r for r in policy_rows if r["policy_id"]=="P0_HELD_V1" and r["cost_scenario"]=="C0")
        g1=next(r for r in policy_rows if r["policy_id"]=="G1_Q75_EXIT_V1" and r["cost_scenario"]=="C0")
        snaps=sorted(paths[trade_id],key=lambda r:(int(r["snapshot_ms"]),r["row_id"]))
        ordinal={r["row_id"]:i+1 for i,r in enumerate(snaps)}; p0_ms=int(p0["exit_execution_ms"])
        needed=[]
        for snap in snaps: needed.append((int(snap["snapshot_ms"]),snap))
        out.append({"trade_id":trade_id,"symbol":p0["symbol"],"year":int(p0["year"]),
            "entry_execution_ts":p0["entry_execution_ts"],"entry_execution_ms":int(p0["entry_execution_ms"]),
            "trade_entry_week":p0["trade_entry_week"],"raw_entry_price":float(p0["raw_entry_price"]),
            "p0_execution_ms":p0_ms,"p0_price":float(p0["raw_exit_price"]),"accepted_policy_rows":policy_rows,
            "common_mfe":float(p0["common_mfe"]),
            "g1_executed_before_p0":_as_bool(g1.get("triggered")) and int(g1["exit_execution_ms"])<p0_ms,
            "g1_trigger_ordinal":ordinal.get(g1.get("trigger_row_id")) if _as_bool(g1.get("triggered")) else None,
            "_snapshot_rows":needed})
    ranges={}
    for t in out:
        vals=[int(t["entry_execution_ms"]),int(t["p0_execution_ms"]),*[x[0] for x in t["_snapshot_rows"]]];s=t["symbol"]
        lo,hi=min(vals),max(vals);ranges[s]=(min(lo,ranges.get(s,(lo,hi))[0]),max(hi,ranges.get(s,(lo,hi))[1]))
    minutes=defaultdict(dict)
    for symbol,(lo,hi) in ranges.items():
        path=approved_path(repo/f"data/normalized/c2_history/{symbol}_1m.csv.gz")
        with gzip.open(path,"rt",newline="") as handle:
            for row in csv.DictReader(handle):
                ms=int(row["open_time_ms"])
                if lo<=ms<=hi:minutes[symbol][ms]=(float(row["open"]),float(row["high"]))
    for t in out:
        t["path"]=[{"row_id":r["row_id"],"execution_ms":ms,"raw_open":minutes[t["symbol"]].get(ms,(None,None))[0]} for ms,r in t.pop("_snapshot_rows")]
        t["minute_highs"]={ms:high for ms,(_open,high) in minutes[t["symbol"]].items()
                           if int(t["entry_execution_ms"])<=ms<=int(t["p0_execution_ms"])}
    return out

def execute_economic_replay(canonical_path: Path | None = None, config: Mapping[str, object] | None = None, *, _capability=None) -> dict:
    if _capability is not _PRODUCTION_EXECUTION_CAPABILITY:
        raise PermissionError("C6 economics is callable only through the governed one-shot runner")
    if canonical_path is None or config is None: raise RuntimeError("governed executor inputs missing")
    return execute_economic_fixture(_load_production_trades(canonical_path),config)

def _validate_population_rows(path: Path) -> dict:
    """Future-run preflight: inspect identity columns only after path/hash gates pass."""
    path=approved_path(path)
    trades={}
    with path.open(newline="",encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            trade=str(row["trade_id"]); year=int(row.get("year") or str(row["entry_execution_ts"])[:4]); symbol=str(row["symbol"])
            identity=(year,symbol)
            if trade in trades and trades[trade] != identity: raise RuntimeError("canonical trade identity conflict")
            trades[trade]=identity
    by_year=Counter(y for y,_ in trades.values()); by_symbol=Counter(s for _,s in trades.values())
    expected_year={2024:155,2025:284}; expected_symbol={"BTCUSDT":74,"ETHUSDT":85,"SOLUSDT":106,"XRPUSDT":87,"BNBUSDT":87}
    if len(trades)!=439 or dict(by_year)!=expected_year or dict(by_symbol)!=expected_symbol:
        raise RuntimeError("canonical 439-trade population mismatch")
    return {"trades":len(trades),"by_year":dict(by_year),"by_symbol":dict(by_symbol)}

def _assert_frozen_population(population: Mapping[str,object], snapshots: object) -> None:
    expected_year={2024:155,2025:284}
    expected_symbol={"BTCUSDT":74,"ETHUSDT":85,"SOLUSDT":106,"XRPUSDT":87,"BNBUSDT":87}
    if (population.get("trades") != 439 or snapshots != 38745 or
            population.get("by_year") != expected_year or population.get("by_symbol") != expected_symbol):
        raise RuntimeError("complete frozen population validation failed")

def _runner_config() -> dict:
    return {"control_registry":list(CONTROL_REGISTRY),"hierarchy":[list(x) for x in PRIMARY_HIERARCHY],
            "seeds":{"market_bootstrap":20240923,"random_timing":20240924,"combined_uncertainty":20240925,"coin_flip":20240926},
            "permutations":1000,"costs":COSTS,"formal_stopping":"first_non_STRONG_POSITIVE"}

def _read_execution_freeze(repo: Path) -> dict:
    path=approved_path(repo/EXECUTION_FREEZE_REL)
    if EXECUTION_FREEZE_SHA256 == "PENDING_FINALIZATION" or sha256(path) != EXECUTION_FREEZE_SHA256:
        raise RuntimeError("authoritative C6 T2 execution-freeze hash mismatch")
    freeze=json.loads(path.read_text())
    required={"version","readiness_path","readiness_sha256","contract_sha256","runner_configuration_sha256"}
    if set(freeze) != required or freeze["version"] != "C6_T2_EXECUTION_FREEZE_V1":
        raise RuntimeError("invalid C6 T2 execution freeze")
    if freeze["readiness_path"] != "artifacts/c6_simple_t2_exit_controls/t1_readiness.json":
        raise RuntimeError("invalid frozen readiness path")
    if freeze["contract_sha256"] != CONTRACT_SHA256:
        raise RuntimeError("invalid frozen contract identity")
    if freeze["runner_configuration_sha256"] != hashlib.sha256(canonical_bytes(_runner_config())).hexdigest():
        raise RuntimeError("invalid frozen runner configuration")
    return freeze

def _internal_run_with_test_dependencies(*, repo: Path, ledger_path: Path, output_dir: Path,
                    economic_executor: Callable[[Path, Mapping[str,object]], Mapping[str,object]],
                    execution_flag: str, attempt_id: str | None=None,
                    provenance_fn: Callable[[Path],Mapping[str,object]]=provenance_gate,
                    population_fn: Callable[[Path],Mapping[str,object]]=_validate_population_rows) -> dict:
    """Private synthetic seam; the public production entry point supplies all authorities."""
    if execution_flag != T2_EXECUTION_FLAG: raise PermissionError("explicit C6 T2 execution flag required")
    # No resolve/stat/open/hash occurs until every raw path and fixed child is safe.
    raw_repo=os.fspath(repo)
    fixed_rel=["contracts/C6_simple_t2_exit_controls_CONTRACT.md",
               "artifacts/c6_simple_t2_exit_controls/t1_readiness.json",EXECUTION_FREEZE_REL,
               *[rel for rel,_ in UPSTREAM.values()]]
    _lexically_safe_paths(raw_repo,ledger_path,output_dir,*fixed_rel,
                          *[os.path.join(raw_repo,rel) for rel in fixed_rel])
    repo=approved_path(repo); readiness=approved_path(repo/"artifacts/c6_simple_t2_exit_controls/t1_readiness.json")
    canonical=approved_path(repo/UPSTREAM["canonical_c5_trade_results"][0])
    freeze=_read_execution_freeze(repo)
    if sha256(repo/"contracts/C6_simple_t2_exit_controls_CONTRACT.md") != CONTRACT_SHA256: raise RuntimeError("C6 contract hash mismatch")
    readiness_sha256=str(freeze["readiness_sha256"])
    if sha256(readiness) != readiness_sha256: raise RuntimeError("accepted C6 T1 readiness hash mismatch")
    ready=json.loads(readiness.read_text())
    if not ready.get("T2_ready") or ready.get("blockers") or ready.get("control_registry") != list(CONTROL_REGISTRY): raise RuntimeError("C6 T1 readiness not authorized")
    if ready.get("seeds") != {"coin_flip":20240926,"combined_uncertainty":20240925,"market_bootstrap":20240923,"random_timing":20240924}: raise RuntimeError("frozen seed registry mismatch")
    prov=provenance_fn(repo)
    population=population_fn(canonical)
    snapshots=prov["population"]["pooled"]["snapshots"]
    _assert_frozen_population(population,snapshots)
    population={**population,"snapshots":snapshots}
    config=_runner_config(); source_hash=sha256(Path(__file__)); config_hash=hashlib.sha256(canonical_bytes(config)).hexdigest()
    input_hashes={k:v["sha256"] for k,v in prov["artifacts"].items()}; input_hashes["c6_t1_readiness"]=readiness_sha256
    attempt=attempt_id or uuid.uuid4().hex
    base={"attempt_id":attempt,"time":datetime.now().astimezone().isoformat(),"configuration_hash":config_hash,
          "source_hash":source_hash,"input_hashes":input_hashes,"random_seeds":config["seeds"],
          "contract_sha256":CONTRACT_SHA256,"readiness_sha256":readiness_sha256}
    append_attempt_event(ledger_path,{**base,"event":"START","status":"START","output_hashes":{}})
    try:
        result=dict(economic_executor(canonical,{**config,"population":population}))
        required={"control_registry","hierarchy","interpretation","metrics","statistics","s3_assignments","s3_structural_inputs","seeds"}
        if not required <= set(result) or result["control_registry"] != list(CONTROL_REGISTRY) or result["hierarchy"] != config["hierarchy"]:
            raise RuntimeError("economic executor returned incomplete or non-frozen result")
        if result["seeds"] != config["seeds"]: raise RuntimeError("economic executor seed registry mismatch")
        structural=[TimingTrade(**x) for x in result["s3_structural_inputs"]]
        result["s3_authentication"]=validate_permutations(structural,result["s3_assignments"])
        output_dir=approved_path(output_dir,must_exist=False); output_dir.mkdir(parents=True,exist_ok=False)
        target=output_dir/"c6_t2_results.json"; target.write_bytes(canonical_bytes(result))
        hashes={target.name:sha256(target)}
        append_attempt_event(ledger_path,{**base,"time":datetime.now().astimezone().isoformat(),"event":"PASS","status":"PASS","output_hashes":hashes})
        return {"attempt_id":attempt,"status":"PASS","output_hashes":hashes}
    except Exception as exc:
        append_attempt_event(ledger_path,{**base,"time":datetime.now().astimezone().isoformat(),"event":"FAIL","status":"FAIL","output_hashes":{},"failure_reason":f"{type(exc).__name__}: {exc}"})
        raise

def run_c6_t2_once(*, repo: Path, ledger_path: Path, output_dir: Path,
                    execution_flag: str, attempt_id: str | None=None) -> dict:
    """Closed production entry point; contains no caller-replaceable authority."""
    def governed_executor(canonical,config):
        return execute_economic_replay(canonical,config,_capability=_PRODUCTION_EXECUTION_CAPABILITY)
    return _internal_run_with_test_dependencies(repo=repo,ledger_path=ledger_path,output_dir=output_dir,
        economic_executor=governed_executor,execution_flag=execution_flag,attempt_id=attempt_id,
        provenance_fn=provenance_gate,population_fn=_validate_population_rows)

def synthetic_validation() -> dict:
    # Deliberately fictional identities and path lengths; no repository trade is read.
    trades=[TimingTrade("fixture-a",2024,"BTCUSDT",3,3),TimingTrade("fixture-b",2024,"BTCUSDT",2,2),
            TimingTrade("fixture-c",2024,"BTCUSDT",3,1),TimingTrade("fixture-d",2024,"BTCUSDT",1,"P0_FALLBACK")]
    a=timing_permutations(trades); b=timing_permutations(trades)
    va=validate_permutations(trades,a); vb=validate_permutations(trades,b)
    if canonical_bytes(a) != canonical_bytes(b): raise RuntimeError("S3 rerun not byte-identical")
    va["independent_rerun_byte_identical"] = va["byte_sha256"] == vb["byte_sha256"]
    va["fixture_timing_ordinal_distribution_per_assignment"] = {str(k):v for k,v in sorted(Counter(t.g1_label for t in trades).items(),key=lambda x:str(x[0]))}
    va["fixture_stratum_counts"] = {"2024|BTCUSDT": len(trades)}
    return va

def build_readiness(repo: Path, tests: Mapping[str, object]) -> dict:
    prov=provenance_gate(repo); structural=synthetic_validation(); blockers=[]
    if tests.get("status") != "PASS": blockers.append("synthetic test suite did not pass")
    return {"version":"C6_T1_MECHANICAL_READINESS_V1", "contract_sha256":CONTRACT_SHA256,
            "implementation_source_sha256":sha256(repo/"src/binance_data_foundation/c6_t1.py"),
            "test_source_sha256":sha256(repo/"tests/test_c6_t1.py"),
            "runner_configuration_sha256":hashlib.sha256(canonical_bytes(_runner_config())).hexdigest(),
            "upstream_provenance_hashes":prov["artifacts"],
            "replay_population_identity_hashes":{"c5_t1_readiness":prov["artifacts"]["c5_t1_readiness"]["sha256"],
                "t2_snapshots_2024":prov["artifacts"]["t2_snapshots_2024"]["sha256"],
                "g1_p1_outputs_2025":prov["artifacts"]["g1_p1_outputs_2025"]["sha256"]},
            "population":{"trades":439,"snapshots":38745,"by_year":{"2024":155,"2025":284},
                          "by_symbol":{"BTCUSDT":74,"ETHUSDT":85,"SOLUSDT":106,"XRPUSDT":87,"BNBUSDT":87}},
            "control_registry":list(CONTROL_REGISTRY), "control_aliases":ALIASES,
            "seeds":{"random_timing":20240924,"combined_uncertainty":20240925,"market_bootstrap":20240923,"coin_flip":20240926},
            "random_permutations":1000,"randomization_strata":"entry calendar year x symbol; fixed year then symbol order",
            "bootstrap_definition":BOOTSTRAP,"costs":COSTS,"comparison_hierarchy":[list(x) for x in PRIMARY_HIERARCHY],
            "interpretation_labels":list(LABELS),"reporting_governance":reporting_governance(),
            "stopping_rules":{"formal_testing":"stop after first non-STRONG_POSITIVE gate","later_results":"descriptive only; no rescue"},
            "interpretation_rules":{"precedence_frozen":True,"mandatory_adverse_safety_breach_prevents_favorable_advancement":True},
            "structural_random_control_validation":structural,"synthetic_test_status":dict(tests),
            "attempt_ledger":{"format":"append-only JSON Lines","created":False,"economic_attempt_recorded":False,
                "event_semantics":"START precedes execution; terminal PASS/FAIL time is end time; prior lines are never overwritten",
                "lifecycle_validation":"inter-process flock covers read-validation-append-flush; START exactly once; exactly one PASS/FAIL; PASS requires output hashes; FAIL requires failure reason",
                "concurrency_validation":"simultaneous duplicate START and terminal writers: exactly one succeeds",
                "future_event_fields":["attempt_id","event","time","configuration_hash","source_hash","input_hashes","random_seeds","contract_sha256","readiness_sha256","status","output_hashes"]},
            "sealed_path_validation":{"status":"PASS","pure_lexical_before_filesystem":True,"normalized_component_and_stem_checks":True,"tokens":["2026","2026Q*","sealed","confirmation"]},
            "one_shot_runner":{"implemented":True,"executed":False,"explicit_flag_required":T2_EXECUTION_FLAG,
                "provenance_before_execution":True,"production_authorities_injectable":False,
                "authoritative_readiness":{"mechanism":"fixed pre-economic execution-freeze manifest","path":EXECUTION_FREEZE_REL},
                "population_gate":{"trades":439,"snapshots":38745,"year_and_symbol_counts_required":True},
                "terminal_events":["PASS","FAIL"]},
            "one_shot_runner_implemented":True,"production_economic_executor_implemented":True,
            "S3_end_to_end_authentication":True,
            "s3_authentication":{"deterministic_reconstruction":True,"production_acceptance_boundary_enforced":True,
                "authenticates_rng_priorities_stream_audits_matching_and_tie_break":True},
            "economic_replay_performed":False,"real_returns_calculated":False,"real_PnL_calculated":False,
            "MFE_or_winner_truncation_calculated":False,"new_predictions_generated":False,
            "threshold_delay_probability_search":False,"sealed_confirmation_access":False,
            "T2_ready":not blockers,"blockers":blockers}
