from __future__ import annotations

from dataclasses import dataclass, field
import copy
import math


@dataclass
class Ledger:
    cash_usdt: float
    holdings: dict[str, float] = field(default_factory=dict)
    fills: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not _finite_nonnegative(self.cash_usdt):
            raise ValueError("initial cash must be finite and nonnegative")
        for symbol, qty in self.holdings.items():
            if not symbol:
                raise ValueError("holding symbol is required")
            if not _finite_nonnegative(qty):
                raise ValueError("holdings must be finite and nonnegative")

    def buy(self, symbol: str, units: float, price_usdt: float, fee_rate: float, *, fill_id: str = "") -> bool:
        _require_symbol(symbol)
        _require_positive(units, price_usdt)
        _require_fee(fee_rate)
        fee = units * price_usdt * fee_rate
        total = units * price_usdt + fee
        _require_finite("buy notional/fee/total", fee, total)
        if total - self.cash_usdt > 1e-12:
            return False
        new_cash = self.cash_usdt - total
        if new_cash < 0 and abs(new_cash) <= 1e-12:
            new_cash = 0.0
        if new_cash < 0 or not math.isfinite(new_cash):
            raise ValueError("buy would create invalid cash balance")
        new_units = self.holdings.get(symbol, 0.0) + units
        if not math.isfinite(new_units):
            raise ValueError("buy would create invalid holding balance")
        self.cash_usdt = new_cash
        self.holdings[symbol] = new_units
        self._log(fill_id, "BUY", symbol, units, price_usdt, fee)
        return True

    def sell(self, symbol: str, units: float, price_usdt: float, fee_rate: float, *, fill_id: str = "") -> bool:
        _require_symbol(symbol)
        _require_positive(units, price_usdt)
        _require_fee(fee_rate)
        if self.holdings.get(symbol, 0.0) < units:
            return False
        notional = units * price_usdt
        fee = notional * fee_rate
        _require_finite("sell notional/fee", notional, fee)
        new_cash = self.cash_usdt + notional - fee
        if not math.isfinite(new_cash):
            raise ValueError("sell would create invalid cash balance")
        remaining = self.holdings.get(symbol, 0.0) - units
        if not math.isfinite(remaining) or remaining < -1e-12:
            raise ValueError("sell would create invalid holding balance")
        self.cash_usdt = new_cash
        if abs(remaining) <= 1e-12:
            self.holdings.pop(symbol, None)
        else:
            self.holdings[symbol] = remaining
        self._log(fill_id, "SELL", symbol, units, price_usdt, fee)
        return True

    def equity(self, marks: dict[str, float]) -> dict:
        missing = sorted(sym for sym, qty in self.holdings.items() if qty and sym not in marks)
        if missing:
            return {"status": "unresolved", "cash_usdt": self.cash_usdt, "missing_marks": missing, "equity_usdt": None}
        invalid = sorted(sym for sym, qty in self.holdings.items() if qty and (not math.isfinite(float(marks[sym])) or float(marks[sym]) < 0))
        if invalid:
            return {"status": "error", "cash_usdt": self.cash_usdt, "invalid_marks": invalid, "equity_usdt": None}
        value = self.cash_usdt + sum(qty * marks[sym] for sym, qty in self.holdings.items())
        if not math.isfinite(value):
            return {"status": "error", "cash_usdt": self.cash_usdt, "invalid_marks": [], "equity_usdt": None}
        return {"status": "complete", "cash_usdt": self.cash_usdt, "missing_marks": [], "equity_usdt": value}

    def _log(self, fill_id: str, side: str, symbol: str, units: float, price_usdt: float, fee_usdt: float) -> None:
        self.fills.append(
            {
                "fill_id": fill_id,
                "side": side,
                "symbol": symbol,
                "units": units,
                "price_usdt": price_usdt,
                "fee_usdt": fee_usdt,
            }
        )


def bridge_swap(ledger: Ledger, source: str, destination: str, source_units: float, source_price: float, destination_price: float, fee_rate: float) -> bool:
    if source == destination:
        raise ValueError("source and destination must differ")
    _require_positive(source_units, source_price)
    _require_positive(1.0, destination_price)
    _require_fee(fee_rate)
    temp = copy.deepcopy(ledger)
    before_cash = temp.cash_usdt
    if not temp.sell(source, source_units, source_price, fee_rate, fill_id=f"{source}->USDT"):
        return False
    available = temp.cash_usdt - before_cash
    destination_units = available / (destination_price * (1 + fee_rate))
    _require_finite("destination units", destination_units)
    if destination_units <= 0 or not temp.buy(destination, destination_units, destination_price, fee_rate, fill_id=f"USDT->{destination}"):
        return False
    ledger.cash_usdt = temp.cash_usdt
    ledger.holdings = temp.holdings
    ledger.fills = temp.fills
    return True


def _require_positive(units: float, price_usdt: float) -> None:
    if not math.isfinite(units) or not math.isfinite(price_usdt) or units <= 0 or price_usdt <= 0:
        raise ValueError("units and price must be positive")


def _require_fee(fee_rate: float) -> None:
    if not math.isfinite(fee_rate) or fee_rate < 0 or fee_rate >= 1:
        raise ValueError("fee_rate must satisfy 0 <= fee_rate < 1")


def _require_symbol(symbol: str) -> None:
    if not symbol:
        raise ValueError("symbol is required")


def _finite_nonnegative(value: float) -> bool:
    return math.isfinite(value) and value >= 0


def _require_finite(label: str, *values: float) -> None:
    if not all(math.isfinite(v) for v in values):
        raise ValueError(f"{label} must be finite")
