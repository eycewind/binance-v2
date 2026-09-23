from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CostScenario:
    scenario_id: str
    fee_rate: float
    slippage_rate: float


COST_SCENARIOS = (
    CostScenario("C0", 0.0, 0.0),
    CostScenario("C_BASE", 0.001, 0.0002),
    CostScenario("C_S5", 0.001, 0.0005),
    CostScenario("C_S10", 0.001, 0.001),
)


def apply_round_trip_costs(
    entry_price: float,
    exit_price: float,
    entry_notional_usdt: float,
    scenario: CostScenario,
) -> dict:
    values = (entry_price, exit_price, entry_notional_usdt, scenario.fee_rate, scenario.slippage_rate)
    if not all(math.isfinite(x) for x in values) or min(entry_price, exit_price, entry_notional_usdt) <= 0:
        raise ValueError("prices and notional must be finite and positive")
    if not 0 <= scenario.fee_rate < 1 or not 0 <= scenario.slippage_rate < 1:
        raise ValueError("fee and slippage rates must satisfy 0 <= rate < 1")
    entry_adjusted = entry_price * (1 + scenario.slippage_rate)
    exit_adjusted = exit_price * (1 - scenario.slippage_rate)
    quantity = entry_notional_usdt / entry_adjusted
    entry_quote = quantity * entry_adjusted
    exit_quote = quantity * exit_adjusted
    entry_fee = entry_quote * scenario.fee_rate
    exit_fee = exit_quote * scenario.fee_rate
    total_outlay = entry_quote + entry_fee
    net_exit_proceeds = exit_quote - exit_fee
    return {
        "cost_scenario": scenario.scenario_id,
        "fee_rate": scenario.fee_rate,
        "slippage_rate": scenario.slippage_rate,
        "quantity": quantity,
        "entry_price_after_slippage": entry_adjusted,
        "exit_price_after_slippage": exit_adjusted,
        "raw_price_return": exit_price / entry_price - 1,
        "gross_return": exit_adjusted / entry_adjusted - 1,
        "net_return": (net_exit_proceeds - total_outlay) / total_outlay,
        "entry_fee_usdt": entry_fee,
        "exit_fee_usdt": exit_fee,
        "fees_usdt": entry_fee + exit_fee,
        "slippage_usdt": quantity * ((entry_adjusted - entry_price) + (exit_price - exit_adjusted)),
        "quantity_convention": "quantity=1000_USDT_gross_entry_notional/slippage_adjusted_entry_price; fees apply to slippage-adjusted quote notionals",
    }
