# C2 Decision Inputs

## Sources Measured or Inspected

- Binance public-data documentation: `https://github.com/binance/binance-public-data`. It documents daily/monthly public files, spot kline columns, checksum files, and the January 1, 2025 spot timestamp switch to microseconds.
- Binance public archive root: `https://data.binance.vision/`.
- Binance spot API docs/search evidence: current `exchangeInfo` exposes symbol status and permission sets, while status values include `TRADING`, `HALT`, and `BREAK`.
- One current `exchangeInfo?permissions=SPOT&showPermissionSets=true` request returned `3658` spot-permission symbols, `702` USDT-quoted pairs, and `490` currently trading USDT-quoted pairs. This is current metadata only, not historical membership.
- Binance announcements contain listing/removal notices, for example spot pair removal notices. These are evidence candidates for delistings/suspensions, but need systematic archival extraction before use.

## Universe Reconstruction Options

Option A: archive-first candidate set.

- Enumerate `data.binance.vision/data/spot/daily/klines/*/1m/` or monthly index pages for USDT pairs.
- Infer first and last archive dates per symbol and identify missing days.
- Advantage: directly measures available candle files.
- Limitation: archive existence does not prove uninterrupted executable tradability, and missing files may be archive maintenance rather than delisting.

Option B: current exchangeInfo plus historical announcements.

- Start from current `exchangeInfo` for active USDT spot symbols and filters.
- Add listing, trading-start, suspension, migration, and delisting evidence from Binance announcements.
- Advantage: closer to listing/trading intent.
- Limitation: current metadata creates survivorship bias unless delisted and migrated symbols are added from historical notices.

Option C: combined audit trail.

- Use announcements to define listing windows and corporate events.
- Use archive indices to verify minute-file availability by month/day.
- Use candle validation to detect gaps, zero-trade spans, and cadence anomalies.
- Treat universe membership as unresolved until both listing evidence and archive coverage are present for the evaluation date.

## Exclusion Categories

- Non-USDT quote pairs for a USDT-marked study.
- Leveraged tokens and synthetic suffixes such as UP, DOWN, BULL, BEAR, 3L, 3S, 5L, 5S.
- Stablecoin/stable-stable pairs if the future hypothesis excludes them.
- Symbols with unresolved migrations, redenominations, or token swaps until mapped point-in-time.
- Symbols below liquidity, listing-age, or minimum-history thresholds.
- Symbols with prolonged `HALT`, `BREAK`, delisting, or large unresolved archive gaps.

## Scale Estimate for Later Study

Extrapolation from C1 real sample:

- C1 compressed raw footprint: about `1.3 MiB` for 20 daily ZIPs, or roughly `0.065 MiB` per symbol-day.
- C1 normalized footprint: about `6.7 MiB` for 28,800 rows, or roughly `244 bytes` per normalized one-minute row in CSV.
- One symbol-year at 1m has about `525,600` rows, estimated raw compressed size `24 MiB` and normalized CSV size `122 MiB`.
- A 50-symbol, 3-year selected-member minute-bar study would be about `78.8 million` rows, roughly `3.6 GiB` compressed raw and `18 GiB` normalized CSV before derived features. Parquet or Arrow would likely reduce normalized size materially, but that was not measured in C1.
- Daily eligibility history across candidate symbols is cheap compared with minute bars: even 1,000 candidates over 5 years is under 2 million daily rows before metadata joins.

## Outstanding Choices

- Define the target venue and regional availability assumptions; Binance services and pairs vary by region.
- Choose whether current delisted-token announcements are sufficient or whether third-party historical symbol-status snapshots are needed.
- Define a monthly eligibility calendar and whether eligibility is computed at month open, previous close, or after data availability delay.
- Decide raw archive granularity: monthly archives are more efficient for long histories, daily archives simplify point checks and updates.
- Decide whether normalized storage should remain CSV for auditability or move to Parquet/Arrow for scale.
- Specify historical liquidity thresholds using quote volume, trade count, spread proxy, or a combination.

## Blockers for Claiming a Reconstructed Universe

- No complete historical Binance spot symbol-status table was identified in C1.
- Current `exchangeInfo` does not establish past listing status.
- Public archive presence does not establish continuous tradability or executable quotes.
- Announcements need systematic collection and parsing before they can support monthly point-in-time membership.
