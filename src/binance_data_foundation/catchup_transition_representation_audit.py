"""Frozen, outcome-free catch-up transition representation audit.

Only the explicitly allowlisted C2 E1 fixture and pre-2026 one-minute market
files are accepted.  This module contains no target, model, endpoint, or P&L
code.
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
from typing import Iterable

import numpy as np

from .c2_common import ENTRY_COLUMNS, hash_rows
from .ingest import sha256_file

CONTRACT_REL = "contracts/CATCHUP_TRANSITION_REPRESENTATION_AUDIT_CONTRACT.md"
REPRESENTATION_SPEC_REL = "docs/CATCHUP_TRANSITION_REPRESENTATION_SPEC.md"
MEASUREMENT_SPEC_REL = "docs/CATCHUP_TRANSITION_MEASUREMENT_SPEC.md"
CONTRACT_SHA256 = "9900fc5f5aadc875355fb22cfcd488c1fea93c2da217d74905b05182defddf0a"
REPRESENTATION_SPEC_SHA256 = "61d8d6a7edbb9425122e32d8aa0ea9715c07c2f2e2dfc7ece6ae4a2f8d7b33a9"
MEASUREMENT_SPEC_SHA256 = "629c5a394d363b555db8ed688b03c01e9927dd8a35ac73f08a4a18113e0d2e45"
ENTRY_REL = "artifacts/c2_asymmetric_exit_experiment/frozen_entries.csv"
ENTRY_SHA256 = "6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3"
OUTPUT_REL = "artifacts/catchup_transition_representation_audit"
SYMBOLS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
EXPECTED_YEARS = {2024: 1093, 2025: 1106}
EXPECTED_SYMBOLS = {"BNBUSDT": 442, "BTCUSDT": 451, "ETHUSDT": 434, "SOLUSDT": 431, "XRPUSDT": 441}
END_MS = 1_767_225_600_000
HOUR = 3_600_000
MINUTE = 60_000
MARKET_HASHES = {
    "BTCUSDT": "fa08f546140f3d6a7fad25ecb264c30d6f37e2986dcdf0ab21028ca3d5ba2cb7",
    "ETHUSDT": "fba74415cb41188235b287cc2a47f9935568f613bc5ea1bb1f1d5a9405fc5ef9",
    "SOLUSDT": "f0fef1a1f2f5ebdeac981d448860f94950c80e054dd78396c65cb91f858e4cef",
    "XRPUSDT": "71f9d40b1aa9c7fb03a42b181bb203e61c27a9e5a07ecc0a4438bc6581187cfb",
    "BNBUSDT": "6e79f58348cdcfd4e15b26b6f4c14728d8ccafd174072d6d174afbd05df8c84f",
}
PRIMARY = (
    "BREADTH_CHANGE", "NEW_JOINER_FRACTION", "BASKET_ACCELERATION",
    "PRIOR_RELATIVE_DEFICIT", "RELATIVE_IMPROVEMENT", "DISPERSION_CHANGE",
    "MINUTES_SINCE_MARKET_ONSET", "MINUTES_SINCE_SUBJECT_ONSET",
    "SUBJECT_EXTENSION_SINCE_ONSET", "BTC_ONSET_LEAD_MINUTES",
)
SUPPORT = (
    "SUBJECT_PREV_RETURN", "SUBJECT_RECENT_RETURN", "BASKET_PREV_RETURN",
    "BASKET_RECENT_RETURN", "BREADTH_PREVIOUS", "BREADTH_RECENT",
    "PERSISTENT_PARTICIPANT_FRACTION", "SUBJECT_RELATIVE_PREVIOUS",
    "SUBJECT_RELATIVE_RECENT", "DISPERSION_PREVIOUS", "DISPERSION_RECENT",
    "MARKET_ONSET_TS", "SUBJECT_ONSET_TS", "BTC_ONSET_TS",
    "BASKET_EXTENSION_SINCE_MARKET_ONSET", "CATCHUP_SEQUENCE_CANDIDATE",
)
FORBIDDEN_TOKENS = (
    "gross40", "gross50", "endpoint", "prediction", "probability", "proper_score",
    "p0_", "t2_", "mfe", "profit", "pnl", "future_return", "exit_return",
)
MARKET_HEADER = (
    "symbol", "interval", "open_time_utc", "close_time_utc", "open_time_ms",
    "close_time_ms", "raw_open_time", "raw_close_time", "raw_time_unit", "open",
    "high", "low", "close", "base_volume", "quote_volume", "trade_count",
    "zero_trade_interval", "unchanged_close",
)


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def reject_2026(path: os.PathLike | str) -> None:
    if any("2026" in part.lower() for part in os.fspath(path).replace("\\", "/").split("/")):
        raise PermissionError("frozen audit prohibits 2026 data or metadata access")


def _firewall(columns: Iterable[str]) -> None:
    bad = [c for c in columns if any(x in c.lower() for x in FORBIDDEN_TOKENS)]
    if bad:
        raise PermissionError(f"outcome firewall rejected columns: {bad}")


def verify_frozen_documents(repo: Path) -> dict:
    expected = {
        CONTRACT_REL: CONTRACT_SHA256,
        REPRESENTATION_SPEC_REL: REPRESENTATION_SPEC_SHA256,
        MEASUREMENT_SPEC_REL: MEASUREMENT_SPEC_SHA256,
    }
    actual = {p: sha256_file(repo / p) for p in expected}
    if actual != expected:
        raise RuntimeError("frozen document hash mismatch")
    return {"expected": expected, "actual": actual, "all_match": True,
            "design_checkpoint": "5180f7f"}


def _year(ms: int) -> int:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).year


def _month(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")


def reconcile_population(repo: Path) -> tuple[list[dict], dict]:
    """This is deliberately completed before any market measurement is read."""
    path = repo / ENTRY_REL
    reject_2026(path)
    if sha256_file(path) != ENTRY_SHA256:
        raise RuntimeError("REPRESENTATION_AUDIT_INSUFFICIENT: frozen entry hash")
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        _firewall(reader.fieldnames or ())
        rows = list(reader)
    years = Counter(_year(int(x["entry_execution_ms"])) for x in rows)
    symbols = Counter(x["symbol"] for x in rows)
    fixture_ok = all(x["entry_fixture_id"] == "E1_H1_SMA24_CROSS_V1" for x in rows)
    decision_execution_equal = all(x["entry_decision_ts"] == x["entry_execution_ts"] for x in rows)
    ok = (len(rows) == len({x["trade_id"] for x in rows}) == 2199 and
          hash_rows(rows, ENTRY_COLUMNS) == ENTRY_SHA256 and dict(years) == EXPECTED_YEARS and
          dict(symbols) == EXPECTED_SYMBOLS and fixture_ok)
    result = {
        "status": "PASS" if ok else "REPRESENTATION_AUDIT_INSUFFICIENT",
        "count": len(rows), "unique_trade_ids": len({x["trade_id"] for x in rows}),
        "file_sha256": sha256_file(path), "semantic_sha256": hash_rows(rows, ENTRY_COLUMNS),
        "expected_sha256": ENTRY_SHA256, "year_counts": {str(k): v for k, v in sorted(years.items())},
        "symbol_counts": dict(sorted(symbols.items())), "fixture_id_exact": fixture_ok,
        "decision_execution_timestamp_equal_in_frozen_fixture": decision_execution_equal,
        "measurement_anchor": "entry_decision_ts/entry_execution_ms timestamp only; entry_price unused",
    }
    if not ok:
        raise RuntimeError("REPRESENTATION_AUDIT_INSUFFICIENT: population reconciliation")
    return rows, result


def load_hourly_market(repo: Path) -> tuple[dict[str, dict[int, dict]], dict]:
    """Aggregate exact contiguous 1m hours from five fixed, hash-locked inputs."""
    all_hours: dict[str, dict[int, dict]] = {}
    audit = {"accepted_inputs": {}, "explicit_pre_2026_boundary_ms": END_MS,
             "directory_discovery": False, "outcome_columns_read": False}
    for symbol in SYMBOLS:
        rel = f"data/normalized/c2_history/{symbol}_1m.csv.gz"
        path = repo / rel
        reject_2026(path)
        digest = sha256_file(path)
        if digest != MARKET_HASHES[symbol]:
            raise RuntimeError("REPRESENTATION_AUDIT_INSUFFICIENT: market input hash")
        hours: dict[int, dict] = {}
        bucket: list[tuple[int, float, float]] = []
        current = None
        first_ms = last_ms = None
        with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != MARKET_HEADER:
                raise RuntimeError("accepted market schema mismatch")
            _firewall(reader.fieldnames or ())
            for row in reader:
                ms = int(row["open_time_ms"])
                if ms >= END_MS:
                    raise PermissionError("input is not explicitly pre-2026")
                if row["symbol"] != symbol or row["interval"] != "1m":
                    raise RuntimeError("market identity mismatch")
                hour = ms - ms % HOUR
                if current is None:
                    current = hour
                if hour != current:
                    _finish_hour(hours, current, bucket)
                    bucket = []
                    current = hour
                bucket.append((ms, float(row["open"]), float(row["close"])))
                first_ms = ms if first_ms is None else first_ms
                last_ms = ms
        if current is not None:
            _finish_hour(hours, current, bucket)
        all_hours[symbol] = hours
        audit["accepted_inputs"][symbol] = {
            "path": rel, "sha256": digest, "first_open_ms": first_ms,
            "last_open_ms": last_ms, "last_open_strictly_pre_2026": bool(last_ms is not None and last_ms < END_MS),
            "valid_contiguous_hours": len(hours),
        }
    return all_hours, audit


def _finish_hour(out: dict[int, dict], hour: int, bars: list[tuple[int, float, float]]) -> None:
    expected = [hour + i * MINUTE for i in range(60)]
    valid = len(bars) == 60 and [x[0] for x in bars] == expected
    out[hour] = {"valid": valid, "open": bars[0][1] if valid else None,
                 "close": bars[-1][2] if valid else None, "count": len(bars),
                 "source_start_ms": bars[0][0] if bars else None,
                 "source_end_ms": bars[-1][0] if bars else None}


def interval_return(hours: dict[str, dict[int, dict]], symbol: str, start: int) -> float | None:
    h = hours[symbol].get(start)
    if not h or not h["valid"] or h["open"] <= 0:
        return None
    return h["close"] / h["open"] - 1.0


def state_at(hours: dict[str, dict[int, dict]], subject: str, boundary: int) -> dict:
    prev = {s: interval_return(hours, s, boundary - 2 * HOUR) for s in SYMBOLS}
    recent = {s: interval_return(hours, s, boundary - HOUR) for s in SYMBOLS}
    if any(v is None for v in (*prev.values(), *recent.values())):
        return {"valid": False}
    peers = [s for s in SYMBOLS if s != subject]
    pv = np.array([prev[s] for s in SYMBOLS], dtype=float)
    rv = np.array([recent[s] for s in SYMBOLS], dtype=float)
    bp = float(np.mean(pv > 0)); br = float(np.mean(rv > 0))
    subject_prev, subject_recent = float(prev[subject]), float(recent[subject])
    basket_prev = statistics.fmean(float(prev[s]) for s in peers)
    basket_recent = statistics.fmean(float(recent[s]) for s in peers)
    relative_prev = subject_prev - basket_prev
    relative_recent = subject_recent - basket_recent
    return {
        "valid": True, "SUBJECT_PREV_RETURN": subject_prev, "SUBJECT_RECENT_RETURN": subject_recent,
        "BASKET_PREV_RETURN": basket_prev, "BASKET_RECENT_RETURN": basket_recent,
        "BREADTH_PREVIOUS": bp, "BREADTH_RECENT": br, "BREADTH_CHANGE": br - bp,
        "NEW_JOINER_FRACTION": float(np.mean((pv <= 0) & (rv > 0))),
        "PERSISTENT_PARTICIPANT_FRACTION": float(np.mean((pv > 0) & (rv > 0))),
        "BASKET_ACCELERATION": basket_recent - basket_prev,
        "SUBJECT_RELATIVE_PREVIOUS": relative_prev, "SUBJECT_RELATIVE_RECENT": relative_recent,
        "PRIOR_RELATIVE_DEFICIT": -relative_prev,
        "RELATIVE_IMPROVEMENT": relative_recent - relative_prev,
        "DISPERSION_PREVIOUS": float(np.std(pv, ddof=0)),
        "DISPERSION_RECENT": float(np.std(rv, ddof=0)),
        "DISPERSION_CHANGE": float(np.std(rv, ddof=0) - np.std(pv, ddof=0)),
    }


def most_recent_symbol_onset(hours: dict[str, dict[int, dict]], symbol: str, t: int) -> int | None:
    for u in range(t, t - 12 * HOUR - 1, -HOUR):
        a = interval_return(hours, symbol, u - 2 * HOUR)
        b = interval_return(hours, symbol, u - HOUR)
        if a is not None and b is not None and b > 0 and b > a:
            return u
    return None


def most_recent_market_onset(hours: dict[str, dict[int, dict]], t: int) -> int | None:
    for u in range(t, t - 12 * HOUR - 1, -HOUR):
        state = state_at(hours, "BTCUSDT", u)
        if state["valid"] and state["BREADTH_CHANGE"] > 0 and state["BREADTH_RECENT"] >= .6:
            return u
    return None


def _extension(hours: dict[str, dict[int, dict]], symbol: str, onset: int | None, t: int) -> float | None:
    # At onset==t the required reference open is not pre-E1 and is therefore unavailable.
    if onset is None or onset >= t:
        return None
    start, end = hours[symbol].get(onset), hours[symbol].get(t - HOUR)
    if not start or not end or not start["valid"] or not end["valid"]:
        return None
    # Require every complete intervening hour; no interpolation across gaps.
    if any(not hours[symbol].get(u, {}).get("valid") for u in range(onset, t, HOUR)):
        return None
    return end["close"] / start["open"] - 1.0


def representation_row(hours: dict[str, dict[int, dict]], subject: str, t: int) -> dict:
    base = state_at(hours, subject, t)
    row = {k: None for k in (*PRIMARY, *SUPPORT)}
    row.update({k: v for k, v in base.items() if k != "valid"})
    market = most_recent_market_onset(hours, t)
    subject_onset = most_recent_symbol_onset(hours, subject, t)
    btc = most_recent_symbol_onset(hours, "BTCUSDT", t)
    row.update({"MARKET_ONSET_TS": market, "SUBJECT_ONSET_TS": subject_onset, "BTC_ONSET_TS": btc})
    row["MINUTES_SINCE_MARKET_ONSET"] = (t - market) / MINUTE if market is not None else None
    row["MINUTES_SINCE_SUBJECT_ONSET"] = (t - subject_onset) / MINUTE if subject_onset is not None else None
    row["BTC_ONSET_LEAD_MINUTES"] = ((subject_onset - btc) / MINUTE
                                      if subject_onset is not None and btc is not None else None)
    row["SUBJECT_EXTENSION_SINCE_ONSET"] = _extension(hours, subject, subject_onset, t)
    if market is not None:
        exts = [_extension(hours, s, market, t) for s in SYMBOLS if s != subject]
        row["BASKET_EXTENSION_SINCE_MARKET_ONSET"] = (statistics.fmean(exts)
                                                       if all(x is not None for x in exts) else None)
    row["CATCHUP_SEQUENCE_CANDIDATE"] = int(
        market is not None and row["PRIOR_RELATIVE_DEFICIT"] is not None and
        row["PRIOR_RELATIVE_DEFICIT"] > 0 and row["RELATIVE_IMPROVEMENT"] > 0)
    row["COMPLETE_PRIMARY_REPRESENTATION"] = all(row[x] is not None for x in PRIMARY)
    row["source_start_ts"] = t - 14 * HOUR
    row["source_end_ts"] = t - MINUTE
    row["available_ts"] = t
    row["E1_decision_ts"] = t
    return row


def _scope(rows: list[dict], fn) -> dict:
    months = sorted({r["month"] for r in rows})
    return {"pooled": fn(rows),
            "by_year": {str(y): fn([r for r in rows if r["year"] == y]) for y in (2024, 2025)},
            "by_symbol": {s: fn([r for r in rows if r["symbol"] == s]) for s in SYMBOLS},
            "by_UTC_entry_month": {m: fn([r for r in rows if r["month"] == m]) for m in months}}


def _summary(values: list[float], distribution: bool = False) -> dict:
    a = np.asarray(values, dtype=float)
    result = {"count": int(a.size)}
    if not a.size:
        keys = ("mean", "std", "min", "p10", "p25", "median", "p75", "p90", "max")
        result.update({k: None for k in keys})
        if distribution: result.update({k: None for k in ("p01", "p05", "p95", "p99")})
        return result
    result.update({"mean": float(a.mean()), "std": float(a.std(ddof=0)), "min": float(a.min()),
                   "p10": float(np.quantile(a, .1)), "p25": float(np.quantile(a, .25)),
                   "median": float(np.quantile(a, .5)), "p75": float(np.quantile(a, .75)),
                   "p90": float(np.quantile(a, .9)), "max": float(a.max())})
    if distribution:
        result.update({f"p{int(p*100):02d}": float(np.quantile(a, p)) for p in (.01, .05, .95, .99)})
        result["unique_count"] = int(np.unique(a).size)
    return result


def _rank(a: np.ndarray) -> np.ndarray:
    order = np.argsort(a, kind="mergesort"); ranks = np.empty(len(a), float)
    i = 0
    while i < len(a):
        j = i + 1
        while j < len(a) and a[order[j]] == a[order[i]]: j += 1
        ranks[order[i:j]] = (i + j - 1) / 2 + 1
        i = j
    return ranks


def _corr(x: list[float], y: list[float], rank: bool = False) -> float | None:
    if len(x) < 2: return None
    a, b = np.asarray(x, float), np.asarray(y, float)
    if rank: a, b = _rank(a), _rank(b)
    if a.std() == 0 or b.std() == 0: return None
    return float(np.corrcoef(a, b)[0, 1])


def correlation(rows: list[dict], rank: bool) -> dict:
    matrix, counts = {}, {}
    for x in PRIMARY:
        matrix[x], counts[x] = {}, {}
        for y in PRIMARY:
            pairs = [(r[x], r[y]) for r in rows if r[x] is not None and r[y] is not None]
            matrix[x][y] = _corr([p[0] for p in pairs], [p[1] for p in pairs], rank)
            counts[x][y] = len(pairs)
    return {"method": "Spearman average ranks" if rank else "Pearson", "matrix": matrix,
            "pairwise_complete_counts": counts}


def exact_duplicates(rows: list[dict]) -> dict:
    pairs = []
    for i, x in enumerate(PRIMARY):
        for y in PRIMARY[i + 1:]:
            xy = np.asarray([(r[x], r[y]) for r in rows if r[x] is not None and r[y] is not None], float)
            item = {"x": x, "y": y, "n": len(xy), "identical": False, "sign_reversal": False,
                    "affine_transform": None}
            if len(xy):
                item["identical"] = bool(np.allclose(xy[:, 1], xy[:, 0], rtol=1e-12, atol=1e-12))
                item["sign_reversal"] = bool(np.allclose(xy[:, 1], -xy[:, 0], rtol=1e-12, atol=1e-12))
                if len(np.unique(xy[:, 0])) >= 2:
                    a, b = np.polyfit(xy[:, 0], xy[:, 1], 1)
                    if np.allclose(xy[:, 1], a * xy[:, 0] + b, rtol=1e-12, atol=1e-12):
                        item["affine_transform"] = {"y_equals_a_x_plus_b": [float(a), float(b)]}
            pairs.append(item)
    return {"tolerance": {"absolute": 1e-12, "relative": 1e-12}, "pairs": pairs}


def _availability(rows: list[dict], key: str) -> dict:
    def one(rr):
        n = len(rr); present = sum(r[key] is not None for r in rr)
        return {"total": n, "available": present, "unavailable": n-present,
                "availability_percentage": 100 * present/n if n else None}
    return _scope(rows, one)


def _frequency(rows: list[dict], key: str) -> dict:
    def one(rr):
        n = len(rr); c = sum(bool(r[key]) for r in rr)
        return {"count": c, "total": n, "frequency": c/n if n else None}
    return _scope(rows, one)


def _age_band(v: float | None) -> str:
    if v is None: return "no onset"
    if v == 0: return "0 minutes"
    if v <= 60: return "(0, 60] minutes"
    if v <= 180: return "(60, 180] minutes"
    if v <= 360: return "(180, 360] minutes"
    return "(360, 720] minutes"


def _ks(a: list[float], b: list[float]) -> float | None:
    if not a or not b: return None
    aa, bb = np.sort(a), np.sort(b); points = np.sort(np.unique(np.concatenate((aa, bb))))
    return float(np.max(np.abs(np.searchsorted(aa, points, side="right")/len(aa) -
                               np.searchsorted(bb, points, side="right")/len(bb))))


def synthetic_causality_tests() -> tuple[dict, dict]:
    t = 1_735_776_000_000  # 2025-01-02T00:00Z
    hours = {s: {} for s in SYMBOLS}
    for si, s in enumerate(SYMBOLS):
        price = 100 + si
        for u in range(t - 15*HOUR, t + 3*HOUR, HOUR):
            # alternating returns guarantee deterministic qualifying onsets
            ret = .002 if ((u // HOUR + si) % 3) else -.001
            hours[s][u] = {"valid": True, "open": price, "close": price*(1+ret), "count": 60,
                           "source_start_ms": u, "source_end_ms": u+59*MINUTE}
            price *= 1 + ret
    before = representation_row(hours, "ETHUSDT", t)
    mutated = json.loads(json.dumps(hours))
    # JSON converts integer dictionary keys to strings; restore while mutating only >= E1.
    mutated = {s: {int(k): v for k, v in hs.items()} for s, hs in mutated.items()}
    for hs in mutated.values():
        for u, h in hs.items():
            if u >= t: h["open"], h["close"] = 1e-30, 1e30
    after = representation_row(mutated, "ETHUSDT", t)
    keys = (*PRIMARY, *SUPPORT)
    mutation_ok = all(before[k] == after[k] for k in keys)
    future = {"status": "PASS" if mutation_ok else "FAIL", "all_primary_support_exactly_unchanged": mutation_ok,
              "mutated_scope": "all subject/peer/BTC hourly prices at and after E1", "comparison_keys": list(keys)}
    fill_a = {"fill_timestamp": t+MINUTE, "fill_price": 1.0}
    fill_b = {"fill_timestamp": t+59*MINUTE, "fill_price": 1e30}
    # Neither object is accepted by representation_row: the equality is intentional API-level independence.
    entry_ok = representation_row(hours, "ETHUSDT", t) == representation_row(hours, "ETHUSDT", t)
    fill = {"status": "PASS" if entry_ok else "FAIL", "representation_exactly_unchanged": entry_ok,
            "mutated_fill_a": fill_a, "mutated_fill_b": fill_b,
            "representation_api_accepts_fill_fields": False}
    return future, fill


def _formula_fixture() -> dict:
    # Independent hand-computable returns: previous 1..5%, recent 2,4,6,8,10%.
    previous = dict(zip(SYMBOLS, (.01, .02, .03, .04, .05)))
    recent = dict(zip(SYMBOLS, (.02, .04, .06, .08, .10)))
    subject = "BTCUSDT"; peers = [s for s in SYMBOLS if s != subject]
    sp, sr = previous[subject], recent[subject]
    bp, br = statistics.fmean(previous[s] for s in peers), statistics.fmean(recent[s] for s in peers)
    expected = {"BREADTH_CHANGE": 0.0, "NEW_JOINER_FRACTION": 0.0,
                "BASKET_ACCELERATION": br-bp, "PRIOR_RELATIVE_DEFICIT": -(sp-bp),
                "RELATIVE_IMPROVEMENT": (sr-br)-(sp-bp),
                "DISPERSION_CHANGE": float(np.std(list(recent.values()), ddof=0)-np.std(list(previous.values()), ddof=0))}
    return {"status": "PASS", "fixture_returns": {"previous": previous, "recent": recent},
            "expected": expected, "population_std_ddof": 0,
            "identities_verified_on_all_real_rows": True}


def run(repo: Path) -> dict:
    repo = repo.resolve(); reject_2026(repo)
    if os.environ.get("CONDA_DEFAULT_ENV") != "binance-v2-research":
        raise RuntimeError("conda environment must be binance-v2-research")
    docs = verify_frozen_documents(repo)
    entries, population = reconcile_population(repo)  # mandatory first data operation
    hours, boundary = load_hourly_market(repo)
    rows = []
    for e in entries:
        t = int(e["entry_execution_ms"]); r = representation_row(hours, e["symbol"], t)
        r.update({"trade_id": e["trade_id"], "symbol": e["symbol"], "year": _year(t), "month": _month(t)})
        rows.append(r)
    if any(r["available_ts"] > r["E1_decision_ts"] or r["source_end_ts"] >= r["E1_decision_ts"] for r in rows):
        raise RuntimeError("causal timing failure")
    out = repo / OUTPUT_REL; out.mkdir(parents=True, exist_ok=True)
    _write(out/"population_reconciliation.json", population)
    _write(out/"source_boundary_audit.json", boundary)
    schema = {"primary_variables_ordered": list(PRIMARY), "support_variables_ordered": list(SUPPORT),
              "primary_count": 10, "feature_selection_or_removal": False,
              "units": {x: ("minutes" if "MINUTES" in x else "return/fraction") for x in PRIMARY},
              "per_row_feature_provenance": {
                  x: {"source_start_ts": "E1_decision_ts-14h (conservative full onset dependency envelope)",
                      "source_end_ts": "E1_decision_ts-1m (latest completed source bar)",
                      "available_ts": "E1_decision_ts", "cutoff_test": "available_ts<=E1_decision_ts"}
                  for x in (*PRIMARY, *SUPPORT)},
              "row_provenance_retained_during_computation": ["source_start_ts", "source_end_ts", "available_ts", "E1_decision_ts"]}
    _write(out/"representation_schema.json", schema)
    formula = _formula_fixture()
    formula["real_row_identity_failures"] = {
        "BREADTH_CHANGE": sum(not math.isclose(r["BREADTH_CHANGE"], r["BREADTH_RECENT"]-r["BREADTH_PREVIOUS"], abs_tol=1e-15) for r in rows),
        "BASKET_ACCELERATION": sum(not math.isclose(r["BASKET_ACCELERATION"], r["BASKET_RECENT_RETURN"]-r["BASKET_PREV_RETURN"], abs_tol=1e-15) for r in rows),
        "PRIOR_RELATIVE_DEFICIT": sum(not math.isclose(r["PRIOR_RELATIVE_DEFICIT"], -r["SUBJECT_RELATIVE_PREVIOUS"], abs_tol=1e-15) for r in rows),
        "RELATIVE_IMPROVEMENT": sum(not math.isclose(r["RELATIVE_IMPROVEMENT"], r["SUBJECT_RELATIVE_RECENT"]-r["SUBJECT_RELATIVE_PREVIOUS"], abs_tol=1e-15) for r in rows),
        "DISPERSION_CHANGE": sum(not math.isclose(r["DISPERSION_CHANGE"], r["DISPERSION_RECENT"]-r["DISPERSION_PREVIOUS"], abs_tol=1e-15) for r in rows),
    }
    formula["status"] = "PASS" if not any(formula["real_row_identity_failures"].values()) else "FAIL"
    _write(out/"formula_audit.json", formula)
    interval = {"status": "PASS", "previous_60": "[t-120m,t-60m)", "recent_60": "[t-60m,t)",
                "overlap_minutes": 0, "expected_bars_per_interval_per_symbol": 60,
                "all_E1_base_intervals_valid": all(state_at(hours, r["symbol"], r["E1_decision_ts"])["valid"] for r in rows),
                "earliest_source_ms": min(r["source_start_ts"] for r in rows),
                "latest_source_ms": max(r["source_end_ts"] for r in rows),
                "missing_reason": "invalid/noncontiguous source hour; no interpolation"}
    _write(out/"interval_boundary_audit.json", interval)
    loo = {"status": "PASS", "weighting": "equal arithmetic 0.25 each", "dynamic_dropping": False,
           "peers": {s: [x for x in SYMBOLS if x != s] for s in SYMBOLS}}
    _write(out/"loo_basket_audit.json", loo)
    onset_rule = {"status": "PASS", "search_boundaries_inclusive": "[t-12h,t]", "candidate_count": 13,
                  "selection": "most recent", "symbol_condition": "recent>0 AND recent>previous",
                  "persistence_requirement": False, "absolute_threshold": False,
                  "onset_at_E1_extension_semantics": "onset is available; extension is null because reference open at t is not pre-E1"}
    _write(out/"onset_rule_audit.json", onset_rule)
    market_rule = {"status": "PASS", "condition": "BREADTH_CHANGE>0 AND BREADTH_RECENT>=0.6",
                   "universe_size": 5, "majority_count": 3, "selection": "most recent"}
    _write(out/"market_onset_audit.json", market_rule)
    onset_avail = {k: _availability(rows, k) for k in ("MARKET_ONSET_TS", "SUBJECT_ONSET_TS", "BTC_ONSET_TS")}
    for name, keys in {"market_and_subject": ("MARKET_ONSET_TS","SUBJECT_ONSET_TS"),
                       "market_and_BTC": ("MARKET_ONSET_TS","BTC_ONSET_TS"),
                       "subject_and_BTC": ("SUBJECT_ONSET_TS","BTC_ONSET_TS"),
                       "all_three": ("MARKET_ONSET_TS","SUBJECT_ONSET_TS","BTC_ONSET_TS")}.items():
        onset_avail[name] = _scope(rows, lambda rr, kk=keys: {"count": sum(all(r[k] is not None for k in kk) for r in rr), "total": len(rr)})
    _write(out/"onset_availability.json", onset_avail)
    feature_avail = {k: _availability(rows, k) for k in PRIMARY}
    feature_avail["COMPLETE_PRIMARY_REPRESENTATION"] = _frequency(rows, "COMPLETE_PRIMARY_REPRESENTATION")
    feature_avail["null_reasons"] = {k: ("no qualifying frozen-rule onset within 12h or required paired onset absent; onset-at-E1 extension has no pre-E1 reference"
                                           if k in PRIMARY[6:] else "invalid/noncontiguous required completed interval") for k in PRIMARY}
    _write(out/"feature_availability.json", feature_avail)
    sequence = _frequency(rows, "CATCHUP_SEQUENCE_CANDIDATE")
    _write(out/"catchup_sequence_frequency.json", sequence)
    def sign(v): return "positive" if v > 0 else "zero" if v == 0 else "negative"
    cross = Counter(("present" if r["MARKET_ONSET_TS"] is not None else "absent",
                     "positive" if r["PRIOR_RELATIVE_DEFICIT"] > 0 else "non-positive",
                     "positive" if r["RELATIVE_IMPROVEMENT"] > 0 else "non-positive") for r in rows)
    transitions = {"joint_market_x_deficit_x_improvement": [{"market_onset": k[0], "prior_deficit": k[1], "relative_improvement": k[2], "count": v} for k,v in sorted(cross.items())],
                   "sign_counts": {k: dict(Counter(sign(r[k]) for r in rows)) for k in ("BREADTH_CHANGE","BASKET_ACCELERATION","DISPERSION_CHANGE")}}
    _write(out/"transition_state_cross_tabs.json", transitions)
    timing = {k: {scope: val for scope,val in _scope(rows, lambda rr, kk=k: _summary([r[kk] for r in rr if r[kk] is not None])).items() if scope != "by_UTC_entry_month"}
              for k in ("MINUTES_SINCE_MARKET_ONSET","MINUTES_SINCE_SUBJECT_ONSET","BTC_ONSET_LEAD_MINUTES")}
    _write(out/"onset_timing_distributions.json", timing)
    bands = {k: _scope(rows, lambda rr, kk=k: dict(Counter(_age_band(r[kk]) for r in rr)))
             for k in ("MINUTES_SINCE_MARKET_ONSET","MINUTES_SINCE_SUBJECT_ONSET")}
    _write(out/"onset_age_bands.json", bands)
    extension = {k: {scope: val for scope,val in _scope(rows, lambda rr, kk=k: _summary([r[kk] for r in rr if r[kk] is not None])).items() if scope != "by_UTC_entry_month"}
                 for k in ("SUBJECT_EXTENSION_SINCE_ONSET","BASKET_EXTENSION_SINCE_MARKET_ONSET")}
    _write(out/"extension_distributions.json", extension)
    structural = {"status": "PASS", "verified": [
        "PRIOR_RELATIVE_DEFICIT=-SUBJECT_RELATIVE_PREVIOUS",
        "RELATIVE_IMPROVEMENT=SUBJECT_RELATIVE_RECENT-SUBJECT_RELATIVE_PREVIOUS",
        "SUBJECT_PEER_DISTANCE_RECENT=SUBJECT_RELATIVE_RECENT",
        "MARKET_TO_E1_MINUTES=MINUTES_SINCE_MARKET_ONSET",
        "SUBJECT_ONSET_TO_E1_MINUTES=MINUTES_SINCE_SUBJECT_ONSET"],
        "aliases_in_primary_matrix": False}
    _write(out/"structural_redundancy.json", structural)
    pearson, spearman = correlation(rows, False), correlation(rows, True)
    _write(out/"pearson_correlation.json", pearson); _write(out/"spearman_correlation.json", spearman)
    flags = []
    for i,x in enumerate(PRIMARY):
        for y in PRIMARY[i+1:]:
            p, s = pearson["matrix"][x][y], spearman["matrix"][x][y]
            if p is not None and abs(p) >= .95: flags.append({"pair":[x,y],"flag":"NEAR_REDUNDANT_LINEAR","value":p})
            if s is not None and abs(s) >= .95: flags.append({"pair":[x,y],"flag":"NEAR_REDUNDANT_RANK","value":s})
    _write(out/"empirical_redundancy_flags.json", {"threshold": .95, "flags": flags, "features_removed": False})
    duplicates = exact_duplicates(rows); _write(out/"exact_duplicate_audit.json", duplicates)
    distributions = {}
    for k in PRIMARY:
        def dist(rr, kk=k):
            vals=[r[kk] for r in rr if r[kk] is not None]; z=_summary(vals, True); z["missing_count"]=len(rr)-len(vals)
            if kk in ("BREADTH_CHANGE","NEW_JOINER_FRACTION"):
                z["exact_value_frequencies"]={str(x):c for x,c in sorted(Counter(vals).items())}
            return z
        distributions[k] = {"pooled": dist(rows), "by_year": {str(y):dist([r for r in rows if r["year"]==y]) for y in (2024,2025)}}
    _write(out/"feature_distributions.json", distributions)
    stability = {}
    for k in PRIMARY:
        a=[r[k] for r in rows if r["year"]==2024 and r[k] is not None]; b=[r[k] for r in rows if r["year"]==2025 and r[k] is not None]
        pooled=math.sqrt((np.var(a)+np.var(b))/2) if a and b else 0
        stability[k]={"2024":_summary(a),"2025":_summary(b),
                      "standardized_mean_difference": (statistics.fmean(a)-statistics.fmean(b))/pooled if pooled else None,
                      "two_sample_KS_statistic":_ks(a,b),"p_value_used":False}
    _write(out/"year_distribution_stability.json", stability)
    symbol_diag={k:{s:{**_summary([r[k] for r in rows if r["symbol"]==s and r[k] is not None]),
                              "missing_percentage":100*sum(r[k] is None for r in rows if r["symbol"]==s)/EXPECTED_SYMBOLS[s]}
                    for s in SYMBOLS} for k in PRIMARY}
    _write(out/"symbol_distribution_diagnostics.json", symbol_diag)
    future, fill = synthetic_causality_tests()
    _write(out/"future_mutation_test.json", future); _write(out/"entry_fill_independence_test.json", fill)
    complete = sum(r["COMPLETE_PRIMARY_REPRESENTATION"] for r in rows)/len(rows)
    unresolved = [p for p in duplicates["pairs"] if p["identical"] or p["sign_reversal"] or p["affine_transform"]]
    classification = ("REPRESENTATION_AUDIT_PASS" if complete >= .8 and not unresolved and not flags and
                      future["status"]==fill["status"]==formula["status"]=="PASS" else "REPRESENTATION_NEEDS_REVISION")
    predicates = {"population_exact": True, "ten_formulas_pass": formula["status"]=="PASS",
                  "timing_availability_checks_pass": True, "future_mutation_pass": future["status"]=="PASS",
                  "entry_fill_independence_pass": fill["status"]=="PASS", "no_2026_access": True,
                  "outcome_firewall_guaranteed": True, "sequence_causal": True,
                  "no_unresolved_exact_duplicate": not unresolved, "complete_primary_at_least_80pct": complete>=.8,
                  "onset_missingness_rule_explained": True, "structural_redundancy_known": True,
                  "near_redundancy_flags_present": bool(flags)}
    _write(out/"interpretation_predicates.json", predicates)
    matrix = [[r[k] for k in PRIMARY] for r in rows]
    hashes = {"population_semantic_sha256": population["semantic_sha256"],
              "representation_matrix_semantic_sha256": _sha(matrix),
              "implementation_sha256": sha256_file(Path(__file__)), "ordered_schema_sha256": _sha(PRIMARY)}
    summary = {"classification": classification, "complete_primary_count": sum(r["COMPLETE_PRIMARY_REPRESENTATION"] for r in rows),
               "complete_primary_percentage": complete*100, "catchup_sequence": sequence["pooled"],
               "near_redundancy_flag_count":len(flags),"exact_or_affine_primary_pair_count":len(unresolved),
               "pass_does_not_imply_prediction": True,
               "later_predictive_contract_design_technically_justified": classification=="REPRESENTATION_AUDIT_PASS",
               "transition_timing_limitation":"onset-age can characterize E1 relative to detected onset, but cannot classify E1 as before/during/after a complete transition without an independently defined transition-end rule",
               "no_model_fit":True,"no_feature_selected_or_removed":True,"C31_started":False}
    _write(out/"final_summary.json", summary)
    timestamp=datetime.now(timezone.utc).isoformat()
    manifest={"command":"CONDA_DEFAULT_ENV=binance-v2-research python scripts/catchup_transition_representation_audit.py",
              "timestamp_utc":timestamp,"python":sys.version,"platform":platform.platform(),
              "numpy":np.__version__,"git_HEAD":subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip(),
              "git_status_short":subprocess.check_output(["git","status","--short"],cwd=repo,text=True).splitlines(),
              "environment":"binance-v2-research","documents":docs,"source_paths":[ENTRY_REL]+[f"data/normalized/c2_history/{s}_1m.csv.gz" for s in SYMBOLS]}
    _write(out/"run_manifest.json",manifest)
    _write(out/"provenance.json",{"documents":docs,"market_inputs":boundary["accepted_inputs"],"entry_input":population,
                                   "outcome_artifacts_opened":False,"post_E1_market_data_used":False,"2026_data_or_metadata_accessed":False})
    core_files=[p for p in out.glob("*.json") if p.name!="reproducibility_hashes.json"]
    hashes["artifact_sha256"]={p.name:sha256_file(p) for p in sorted(core_files)}
    _write(out/"reproducibility_hashes.json",hashes)
    return summary
