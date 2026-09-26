import pytest

from binance_data_foundation.c6_t2_diagnostics import (
    distribution, elapsed_minutes, ordinal_buckets, trigger_ordinal,
)


def test_ordinal_construction_and_buckets():
    assert ordinal_buckets([1, 2, 3, 4, 5, 6, 10, 11]) == {
        "first": 1, "second": 1, "third": 1, "fourth": 1, "fifth": 1, "6-10": 2, "11+": 1}


def test_deterministic_linear_summaries():
    assert distribution([4, 1, 3, 2]) == {"count": 4, "min": 1.0, "p25": 1.75,
        "median": 2.5, "p75": 3.25, "p90": 3.7, "max": 4.0, "mean": 2.5}


def test_frozen_identity_join_and_timing_semantics():
    # An immutable trigger row's ordinal and elapsed time use snapshot_ms, not
    # assumptions of contiguous five-minute eligibility.
    path = [{"row_id":"a", "snapshot_ms":"1000"}, {"row_id":"b", "snapshot_ms":"601000"}]
    ids = [r["row_id"] for r in sorted(path, key=lambda r:(int(r["snapshot_ms"]),r["row_id"]))]
    assert trigger_ordinal(ids, "b") == 2
    assert trigger_ordinal(ids, None) is None
    assert elapsed_minutes(int(path[0]["snapshot_ms"]), int(path[1]["snapshot_ms"])) == 10
    with pytest.raises(ValueError, match="absent"):
        trigger_ordinal(ids, "c")
    with pytest.raises(ValueError, match="duplicate"):
        trigger_ordinal(["a", "a"], "a")
