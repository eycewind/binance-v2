# C1 Reuse Audit

## Reference Provenance

No `AGENTS.md` files were found in the target repo, the local PSX repo, or the temporary binbot inspection copy.

Target repo:

- Path: `/media/ata/Data/personal/binance-v2`
- Branch: `main`
- Commit: `0506ee07188a94ebbd4dc52ed9af79b98a71a9b2`
- Initial status: `?? artifacts/`, `?? contracts/`

Legacy binbot:

- Path inspected: `/tmp/c1-binbot-inspect`
- Remote: `https://github.com/eycewind/binbot`
- Branch: `main`
- Commit: `6b49484d0a82ab0737f0d446ab60041892b606f6`
- Dirty status: clean
- License file: none found in inspected checkout.

PSX research:

- Path inspected: `/media/ata/Data/personal/psx/psx-ml-research`
- Remote: `git@github.com:eycewind/psx-ml-research.git`
- Branch: detached `HEAD`
- Commit: `b46fc51dcb1e380b80c8a68dcc8aad49071793a8`
- Dirty status: clean
- License file: none found in top two levels.

## File Hashes Inspected

- `/tmp/c1-binbot-inspect/BatchFeatures.py`: `d72ab8b2b4d8719df4f0e149e3d99b2ca82e4a186a42ef270a0437d355fe8b32`
- `/tmp/c1-binbot-inspect/helper_functions.py`: `b60f44120ee572548e02365adb89a940be44ed4217c2d80fcb2172fc944b36a6`
- `/tmp/c1-binbot-inspect/BinanceClient.py`: `6b944c6a8e533c4e575638868b4af8aadd2c56ae0397ac4d5b678141702b7584`
- `/media/ata/Data/personal/psx/psx-ml-research/src/psx_ml/features/quality.py`: `a2d05131f1c7847fa7dfdf60772807c8fc59cdcb2ed50230e51ddecbef79c536`
- `/media/ata/Data/personal/psx/psx-ml-research/src/psx_ml/features/manifest.py`: `b42ec3434274f535b5269b091ceaa731141c671e4c6808914e23d8753a5862e4`
- `/media/ata/Data/personal/psx/psx-ml-research/src/psx_ml/universe/point_in_time.py`: `5ad98d0600b75947c6ad5074960109c586f136d1764e38f9d331e1dc8d839d82`
- `/media/ata/Data/personal/psx/psx-ml-research/src/psx_ml/splits/walk_forward.py`: `85125e7335545eb9f0df8d6d8625f9e647735b2081b16da85de66a50f9787acc`
- `/media/ata/Data/personal/psx/psx-ml-research/src/psx_ml/live/account_state.py`: `797e2bd58404b8c094f49783fa87216cd0577093cb56e8f3f3961bbe73b6b65b`

## Component Decisions

| Source | Purpose | Dependencies | Timing semantics | Side effects | Tests | Decision |
|---|---|---|---|---|---|---|
| binbot `BatchFeatures.py` | EMA, RSI, MACD, Bollinger, volume, candle, ATR, ROC, lag features, stochastic, Williams %R, regime | pandas, numpy | Mostly backward-looking rolling/ewm/shift; regime uses full-series quantiles, which are not causal for online use | Mutates input DataFrame in place | None found near file | Reject for C1 implementation; use as evidence of available exploratory feature ideas only |
| binbot `helper_functions.py` | Date filtering, SQLite pair discovery, Binance fetching, volume-shock/compression features | pandas, numpy, requests, matplotlib, bottleneck, local `BinanceClient` | Several functions use historical windows; event dataset builders include lookahead labels and controls | Imports trading/data client; fetch path reads API env vars and may call Binance API | None found | Reject for C1 runtime; audit notes inform side-effect boundaries |
| binbot `BinanceClient.py` | Exchange/API/database client | likely Binance client, sqlite, env credentials | Fetches latest server-time ranges; not fixed public archives | Can use API keys and write SQLite | None found | Reject; C1 uses public archive URLs only |
| PSX `features/manifest.py` | File hashing, logical hash, git state, runtime versions, JSON writes | hashlib, json, platform, subprocess, numpy, pyarrow | Provenance only | Writes manifests | Covered indirectly by runtime tests | Adapt concept: deterministic SHA-256 manifests and git/runtime evidence; no pyarrow copied |
| PSX `features/quality.py` and tests | Data-quality flags, missing/stale distinctions | numpy, pyarrow | Keeps missing/stale separate | None material in inspected function | `tests/features/test_price_and_quality.py` | Adapt concept: separate zero-trade and unchanged-close flags; no code copied |
| PSX `universe/point_in_time.py` | Eligibility using observations through date D | sqlite, deque, statistics | Explicit point-in-time trailing window | Reads DB rows | `tests/test_universe.py` | Adapt concept for future C2 methodology only |
| PSX `splits/walk_forward.py` | Purged walk-forward split assignments | numpy, pyarrow | Prevents target overlap into validation | None material | `tests/targets/test_splits.py` | Reuse as methodological pattern for later empirical work, not needed in C1 code |
| PSX `live/account_state.py` and C11 tests | Manual account state and execution tests | pandas, json | Production reconciliation, no trading by itself | Reads JSON | C11 tests cover unfunded/failed execution | Adapt concept: failed orders do not mutate balances; no code copied |

No code was copied verbatim from either reference repository. C1 implementation is native and uses only Python standard library at runtime plus pytest for tests.

## Semantics Checked

- Rolling and shifted binbot features were checked for window direction; simple rolling/shift features are plausibly backward-looking, but full-series quantiles and lookahead event builders are not acceptable for C1 causal features.
- Symbol boundaries are not enforced by binbot feature methods themselves; they operate on one DataFrame and rely on callers to split symbols.
- PSX point-in-time and split code explicitly encodes symbol/date ordering and target-overlap avoidance, which is reusable as a design pattern.
- Missing values, stale/unchanged prices, and zero volume/trades are treated as separate evidence categories in PSX tests; C1 preserves that distinction.
