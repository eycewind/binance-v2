# C1 Accounting Examples

| Case | Step | Cash USDT | Holdings | Mark | Equity / Result |
|---|---|---:|---|---:|---:|
| Required case 1 | Start | 1000.00 | none |  | 1000.00 |
| Required case 1 | Buy 1 AAA at 100, fee 0.001 of notional | 899.90 | AAA 1.0 | 90 | 989.90 |
| Required case 1 | Sell 1 AAA at 90, fee 0.001 of notional | 989.81 | none |  | 989.81 |
| Bridge | AAA -> USDT -> BBB -> USDT -> AAA | 0.00 | AAA 9.96007988 | 10 | 99.6007988 |

Additional tested cases:

- Zero-fee constant-price round trip preserves equity.
- Nonzero-fee constant-price round trip reduces equity.
- Missing marks return `status="unresolved"` with explicit missing symbols.
- Unaffordable buys and failed sells leave balances and fill logs unchanged.
