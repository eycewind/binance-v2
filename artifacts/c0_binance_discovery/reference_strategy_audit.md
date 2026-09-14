# Reference Strategy Audit: ccxt/binance-trade-bot

Repository: <https://github.com/ccxt/binance-trade-bot>
Inspected commit: `55f8cbbe082bd083a722cba697f708a07f5add16`
Local inspection copy: `/tmp/c0_binance_trade_bot_ref`

## README claims

The README describes a rotation idea: cryptocurrencies often move together, Bitcoin may lead, and coin ratios may mean-revert. It proposes trading from a relatively "strong" coin into a relatively "weak" coin through a bridge currency, default `USDT`, and eventually holding more units of the original or later coins. Source: <https://github.com/ccxt/binance-trade-bot/blob/55f8cbbe082bd083a722cba697f708a07f5add16/README.md>

These are claims and motivations, not verified profitability evidence.

## Verified code behavior

Default strategy entry point:

- `binance_trade_bot/strategies/default_strategy.py` initializes trade thresholds, sets the current coin from config or random supported coin, and on every scout calls `_jump_to_best_coin` for the current coin.
- If no configured starting coin exists, it buys a randomly selected supported coin to begin trading. This is live-trading behavior and was not executed.

Ratio initialization and updates:

- `AutoTrader.initialize_trade_thresholds()` stores `pair.ratio = from_coin_price / to_coin_price` for every enabled ordered pair lacking a ratio.
- `AutoTrader.update_trade_threshold(coin, coin_price)` updates all pairs whose `to_coin` is the newly bought coin, again as `from_coin_price / coin_price`.
- Therefore each stored ratio is a moving threshold anchored to the moment the bot initialized or last bought that destination coin.

Switching condition:

- `_get_ratios()` computes the current price ratio `coin_price / optional_coin_price`, gets sell and buy fees for the two bridge legs, and scores each possible destination.
- With default `USE_MARGIN = no`, the score is `(current_ratio - transaction_fee * SCOUT_MULTIPLIER * current_ratio) - stored_pair_ratio`.
- `_jump_to_best_coin()` filters to scores above zero and selects the destination pair with the maximum score.
- The trade path is `current coin -> bridge -> destination coin`, implemented by `transaction_through_bridge()`.

Fees:

- Live fee lookup uses Binance trade fee data. If BNB fee payment is available and enough BNB is held, `get_fee()` returns `base_fee * 0.75`; otherwise it returns the base fee.
- Testnet emulates a base fee of `0.001`.
- Backtest `MockBinanceManager.get_fee()` hard-codes `0.00075`.

Execution assumptions:

- Live orders are limit buys/sells at the current cached ticker price, then wait until filled or timed out.
- Default buy/sell timeouts are zero, meaning no premature cancellation by default.
- Backtest gets historical 1-minute klines, uses open price, applies hard-coded fees, and adjusts balances directly. It does not model order book depth, spread, queue priority, partial fills, latency, delistings, stale marks beyond missing-price skips, or Binance filter drift across history.

## Interpretation

The default strategy is relative-price mean reversion across configured coins. It is not a supervised prediction model and does not explicitly test lead-lag causality. The README mentions Bitcoin leadership, but the default code does not use lagged BTC features to forecast other symbols; it only compares current bridge-denominated price ratios against stored thresholds.

Increasing coin quantity is not the same as increasing USDT equity. Example: if the bot trades into more units of a coin that then falls sharply versus USDT, unit count can rise while total mark-to-market portfolio value falls. Any evaluation must mark all holdings, including open losing positions, in USDT.

Conclusion: treat this project as a candidate comparison baseline for relative rotation only. It is not evidence that the approach is profitable.
