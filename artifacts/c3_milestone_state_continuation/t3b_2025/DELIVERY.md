# C3 T3-B — Locked 2025 Evaluation Delivery

## Repository and execution

- Branch `research/c3-milestone-state-continuation`; HEAD `045fec846f2b3e47817555e908e647a7ae159792`; origin `git@github.com:eycewind/binance-v2.git`.
- Clean status before execution; Conda `binance-v2-research`; Python 3.11.16 at `/home/ata/miniconda3/envs/binance-v2-research/bin/python`.
- Both canonical freeze hashes, all referenced accepted-input/source hashes, and all final model/preprocessing hashes were verified before 2025 scoring.
- Frozen models were M1/M2 L0 C=1.0, L1 C=0.1, and L2 C=0.1. No fitting, selection, calibration correction, threshold optimization, or specification change occurred.

## Population

| Target | Eligible supervised rows | Positive | Negative | Evaluation base rate | Frozen B0 probability |
|---|---:|---:|---:|---:|---:|
| M1 | 391 | 218 | 173 | 0.557545 | 0.503937 |
| M2 | 281 | 148 | 133 | 0.526690 | 0.496094 |

M1 had 434 in-period milestone candidates, 21 feature-ineligible rows, and 22 null/non-supervised labels. M2 had 287 candidates, one feature-ineligible row, and five null/non-supervised labels. The accepted tables contain no otherwise eligible row with a resolution at or beyond the strict boundary.

## Frozen-model results

| Target | Model | ROC AUC | PR AUC | Log loss | Brier | Brier skill vs B0 | Cal. intercept | Cal. slope | 0.5 accuracy |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | B0 | 0.5000 | 0.5575 | 0.69227 | 0.24956 | 0.0000 | 0.2312 | ~0 | 0.5575 |
| M1 | L0 | 0.4963 | 0.5582 | 0.69931 | 0.25296 | -0.0136 | 0.2340 | -0.1926 | 0.5013 |
| M1 | L1 | 0.5439 | 0.6181 | 0.71619 | 0.25754 | -0.0320 | 0.2277 | 0.1736 | 0.5422 |
| M1 | L2 | 0.5462 | 0.6321 | 0.71580 | 0.25656 | -0.0280 | 0.2209 | 0.2060 | 0.5371 |
| M2 | B0 | 0.5000 | 0.5267 | 0.69359 | 0.25022 | 0.0000 | 0.1069 | ~0 | 0.4733 |
| M2 | L0 | 0.5007 | 0.5250 | 0.72669 | 0.26420 | -0.0558 | 0.1017 | -0.0956 | 0.5125 |
| M2 | L1 | 0.5087 | 0.5319 | 0.76435 | 0.27685 | -0.1064 | 0.1021 | -0.0546 | 0.5053 |
| M2 | L2 | 0.5245 | 0.5439 | 0.78419 | 0.28227 | -0.1281 | 0.1145 | 0.0304 | 0.5089 |

The 0.5 results are secondary diagnostics only. They were not optimized or interpreted as action thresholds.

## Paired dependence-aware evidence

Differences are first minus second; negative favors the first model. Intervals are the frozen 2,000-replication UTC calendar-month block bootstrap with seed 20240923 and linear type-7 quantiles.

| Target/comparison | Log-loss difference [95% interval] | Brier difference [95% interval] |
|---|---:|---:|
| M1 L1−L0 | +0.01672 [−0.00464, +0.03796] | +0.00456 [−0.00425, +0.01330] |
| M1 L2−L1 | −0.00045 [−0.01133, +0.01118] | −0.00099 [−0.00611, +0.00475] |
| M2 L1−L0 | +0.03765 [+0.01162, +0.06131] | +0.01274 [+0.00129, +0.02273] |
| M2 L2−L1 | +0.02050 [−0.01591, +0.06036] | +0.00563 [−0.00794, +0.01984] |

M1 L1 does not improve either proper score over L0 overall, and both intervals cross zero. M1 L2 is nearly tied with L1 and both intervals cross zero. M2 L1 is worse than L0 on both proper scores with both intervals wholly above zero. M2 L2 is worse in point estimates than L1 and its intervals cross zero.

## Calibration, bins, and stability

M1 L1/L2 calibration slopes are 0.174/0.206; M2 L1/L2 slopes are −0.055/0.030. This is poor 2025 calibration and indicates that the frozen probability spread did not translate reliably to observed risk. Full frozen-bin boundaries and five-bin tables are in `calibration.json`.

M1 L1 improves both proper scores over L0 in 2/5 symbols, 5/12 months, and 1/4 quarters. M2 does so in 1/5 symbols, 1/12 months, and 0/4 quarters. L2 improves both scores over L1 in 3/5 symbols, 6/12 months, and 2/4 quarters for M1; corresponding M2 counts are 1/5, 6/12, and 1/4. Thus effects are inconsistent across symbols and time. No single group supplies more than half the rows: maximum shares are 24.8% symbol, 10.5% month, and 27.4% quarter for M1; 26.7%, 11.4%, and 30.6% for M2. Performance instability is broad rather than attributable only to one oversized group.

The 2024 coefficient models produce only weak or absent ordered 2025 scoring behavior: M1 has some rank separation but degraded proper scores and compressed calibration; M2 has near-null separation, negative/near-zero calibration slopes, and worse proper scores. This is not consistent with a stable transfer of the 2024 coefficient interpretation. No causal sign story is assigned.

## Scientific interpretation

- **M1: MIXED.** Rank metrics and upper-bin continuation show some separation, but L1 worsens both proper scores against L0, uncertainty spans zero, calibration is weak, and symbol/time results reverse. Cross-asset context is effectively tied and unstable.
- **M2: COUNTS AGAINST.** L1 is dependence-aware worse than L0 on both proper scores, calibration is essentially absent, and deterioration is consistent across all four quarters. L2 does not rescue this result.
- **Overall C3:** M1 MIXED; M2 COUNTS AGAINST. The target disagreement is preserved and is not pooled or averaged into a success claim.

## Reproducibility and restrictions

The independent offline rebuild reproduced all seven published core hashes exactly. `independent_rebuild.json` evidence SHA-256 is `7891109b9fa72039796af004284c7ed08c428dff7394617981c3412444bc85eb`.

The full test suite passed: 163 tests. `git diff --check` passed. Nothing was staged, committed, or pushed. No refitting, tuning, model selection, preprocessing recomputation, calibration correction, economic analysis, trading-policy mapping, P&L, or Stage B was run. No 2026 file/path/data was enumerated or accessed.

Unresolved scientific issues are the weak/failed calibration, unstable symbol/month/quarter behavior, and lack of stable incremental cross-asset value. These are reported as findings and did not alter the frozen models or protocol.
