from pathlib import Path

import numpy as np
import pytest

from binance_data_foundation.c9_dynamic_state import (
    apply_isotonic,
    apply_platt,
    fit_isotonic,
    fit_platt,
    isotonic_support,
    reject_2026,
    reliability,
    trajectory_summary,
)


def rows(labels, states_per_trade=2):
    output = []
    for i, label in enumerate(labels):
        for state in range(states_per_trade):
            output.append({"trade_id": f"t{i}", "label": label, "state_ms": (state + 1) * 300_000,
                "entry_ms": 0, "terminal_ms": 1_000_000, "symbol": "BTCUSDT"})
    return output


@pytest.mark.parametrize("path", ["data/2026/x", Path("metadata_2026.json"), "/sealed/2026Q1/a"])
def test_rejects_any_2026_path(path):
    with pytest.raises(PermissionError): reject_2026(path)


def test_platt_is_trade_weighted_and_corrects_compressed_scores():
    rr = rows([0] * 8 + [1] * 8)
    p = np.repeat(np.asarray([.4] * 8 + [.6] * 8), 2)
    model = fit_platt(rr, p); calibrated = apply_platt(model, p)
    assert model["slope"] > 1
    assert np.mean((calibrated - np.repeat([0] * 8 + [1] * 8, 2)) ** 2) < np.mean((p - np.repeat([0] * 8 + [1] * 8, 2)) ** 2)


def test_weighted_pav_is_monotone_and_bounded():
    rr = rows([0, 1, 0, 1], states_per_trade=1)
    p = np.asarray([.1, .2, .3, .4])
    model = fit_isotonic(rr, p); got = apply_isotonic(model, np.asarray([0, .15, .25, .5]))
    assert np.all(np.diff(got) >= 0) and np.all((got >= 0) & (got <= 1))


def test_isotonic_support_is_predeclared_at_trade_level():
    rr = rows([0] * 225 + [1] * 75, states_per_trade=1)
    p = np.linspace(.01, .99, len(rr))
    assert isotonic_support(rr, p)["eligible"]
    assert not isotonic_support(rr[:-1], p[:-1])["eligible"]


def test_reliability_and_trajectory_use_whole_trade_weights():
    rr = rows([0, 1], states_per_trade=3)
    p = np.asarray([.2, .3, .4, .4, .6, .8])
    rel = reliability(rr, p)
    assert rel["ece"] >= 0 and sum(x["trade_weight_mass"] for x in rel["bins"]) == pytest.approx(1)
    result = trajectory_summary(rr, p)
    assert result["trade_trajectory_summary"]["P0_FIRST"]["directions"] == {"upward": 1}
    assert result["trade_trajectory_summary"]["T2_FIRST"]["directions"] == {"upward": 1}
