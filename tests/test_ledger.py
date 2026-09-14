import pytest

from binance_data_foundation.ledger import Ledger, bridge_swap


def test_required_buy_sell_case() -> None:
    ledger = Ledger(1000)
    assert ledger.buy("AAA", 1, 100, 0.001)
    assert ledger.cash_usdt == pytest.approx(899.90)
    assert ledger.equity({"AAA": 90})["equity_usdt"] == pytest.approx(989.90)
    assert ledger.sell("AAA", 1, 90, 0.001)
    assert ledger.cash_usdt == pytest.approx(989.81)


def test_bridge_rotation_charges_each_leg_and_logs() -> None:
    ledger = Ledger(0, {"AAA": 10})
    assert bridge_swap(ledger, "AAA", "BBB", 10, 10, 5, 0.001)
    assert len(ledger.fills) == 2
    b_units = ledger.holdings["BBB"]
    assert b_units == pytest.approx((100 - 0.1) / (5 * 1.001))
    assert bridge_swap(ledger, "BBB", "AAA", b_units, 5, 10, 0.001)
    assert len(ledger.fills) == 4
    assert ledger.fills[0]["fee_usdt"] == pytest.approx(0.1)
    assert ledger.fills[1]["fee_usdt"] == pytest.approx((100 - 0.1) / 1.001 * 0.001)
    assert ledger.holdings["AAA"] < 10


def test_zero_fee_roundtrip_preserves_equity_nonzero_fee_reduces() -> None:
    free = Ledger(1000)
    assert free.buy("AAA", 5, 100, 0)
    assert free.sell("AAA", 5, 100, 0)
    assert free.cash_usdt == pytest.approx(1000)
    paid = Ledger(1000)
    assert paid.buy("AAA", 5, 100, 0.001)
    assert paid.sell("AAA", 5, 100, 0.001)
    assert paid.cash_usdt < 1000


def test_missing_mark_unaffordable_buy_and_failed_fill_are_explicit() -> None:
    ledger = Ledger(100)
    assert not ledger.buy("AAA", 1, 100, 0.001)
    assert ledger.cash_usdt == pytest.approx(100)
    assert ledger.holdings == {}
    assert ledger.buy("AAA", 1, 90, 0)
    assert ledger.equity({})["status"] == "unresolved"
    before = (ledger.cash_usdt, dict(ledger.holdings), list(ledger.fills))
    assert not ledger.sell("AAA", 2, 90, 0)
    assert (ledger.cash_usdt, ledger.holdings, ledger.fills) == before


def test_invalid_initial_state_and_fill_inputs_raise_without_mutation() -> None:
    with pytest.raises(ValueError):
        Ledger(float("nan"))
    with pytest.raises(ValueError):
        Ledger(0, {"AAA": -1})
    ledger = Ledger(100)
    before = (ledger.cash_usdt, dict(ledger.holdings), list(ledger.fills))
    for args in [
        ("AAA", float("nan"), 1, 0),
        ("AAA", 1, float("inf"), 0),
        ("AAA", 1, 1, -0.1),
        ("AAA", 1, 1, 1),
    ]:
        with pytest.raises(ValueError):
            ledger.buy(*args)
        assert (ledger.cash_usdt, ledger.holdings, ledger.fills) == before


def test_invalid_marks_are_error_and_zero_mark_is_complete() -> None:
    ledger = Ledger(100, {"AAA": 2})
    assert ledger.equity({"AAA": 0})["status"] == "complete"
    assert ledger.equity({"AAA": 0})["equity_usdt"] == pytest.approx(100)
    assert ledger.equity({"AAA": -1})["status"] == "error"
    assert ledger.equity({"AAA": float("nan")})["status"] == "error"


def test_bridge_swap_is_atomic_on_zero_destination_price_and_failures() -> None:
    ledger = Ledger(0, {"AAA": 10})
    before = (ledger.cash_usdt, dict(ledger.holdings), list(ledger.fills))
    with pytest.raises(ValueError):
        bridge_swap(ledger, "AAA", "BBB", 10, 10, 0, 0.001)
    assert (ledger.cash_usdt, ledger.holdings, ledger.fills) == before
    assert not bridge_swap(ledger, "AAA", "BBB", 11, 10, 5, 0.001)
    assert (ledger.cash_usdt, ledger.holdings, ledger.fills) == before
    with pytest.raises(ValueError):
        bridge_swap(ledger, "AAA", "AAA", 1, 10, 10, 0.001)
    assert (ledger.cash_usdt, ledger.holdings, ledger.fills) == before


def test_overflow_rejected_before_mutation() -> None:
    ledger = Ledger(float("1e308"))
    before = (ledger.cash_usdt, dict(ledger.holdings), list(ledger.fills))
    with pytest.raises(ValueError):
        ledger.buy("AAA", float("1e308"), float("1e308"), 0)
    assert (ledger.cash_usdt, ledger.holdings, ledger.fills) == before


def test_sell_cash_addition_overflow_is_rejected_before_mutation() -> None:
    ledger = Ledger(float("1e308"), {"AAA": 2})
    before = (ledger.cash_usdt, dict(ledger.holdings), list(ledger.fills))
    with pytest.raises(ValueError, match="cash balance"):
        ledger.sell("AAA", 1, float("1e308"), 0)
    assert (ledger.cash_usdt, ledger.holdings, ledger.fills) == before


def test_buy_holding_addition_overflow_is_rejected_before_mutation() -> None:
    ledger = Ledger(float("1e308"), {"AAA": float("1e308")})
    before = (ledger.cash_usdt, dict(ledger.holdings), list(ledger.fills))
    with pytest.raises(ValueError, match="holding balance"):
        ledger.buy("AAA", float("1e308"), 1e-308, 0)
    assert (ledger.cash_usdt, ledger.holdings, ledger.fills) == before
