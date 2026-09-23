# C2-A Controlled Replay — Draft Execution Delivery

Status: implementation and offline replay complete; research review required. This is not C2-B, a deployment recommendation, or a profitability claim.

## Execution provenance

- Initial branch: `research/c2-asymmetric-exit`
- Initial HEAD: `5c2089bbe9708d1be25ec427a9a4013bcb64601b`
- Remote: `origin git@github.com:eycewind/binance-v2.git`
- Initial worktree: clean
- Environment: `binance-v2-research`; Python 3.11.16
- Contract SHA-256: `b111cde192d28fd346949186d20b2cf6a1c5d195c4ce6bd19fd26fdb92505494`
- Frozen-entry hash: `6885678a43b0d2f40b34e65adf15247072cdec2bbc8437cafd8cb69d8fba5da3`
- Common-horizon hash: `81e57cfa46f8d39a0448ab6dee2f445c9212f6a29230fe7009c860a580666b7f`
- Paired-table hash: `43de8894095963bda5aee47d8d24f6dec34a3b9cc7def1eec80256156baff5f1`
- Independent offline rebuild: two runs, identical core hashes.

Accepted frozen versions:

- Entry fixture: `E1_H1_SMA24_CROSS_V1`
- Slow baseline: `P0_H1_SMA24_CROSSDOWN_V1`
- Standing bracket: `P1_BRACKET_TP2_SL1_V1`
- Five-minute trailing exit: `P2_M5_TRAIL1_AFTER_GAIN1_V1`
- Five-minute momentum deterioration exit: `P3_M5_MOMENTUM_DETERIORATION_V1`

Required cost scenarios:

- `C0`: 0 bp fee and 0 bp slippage per leg.
- `C_BASE`: 10 bp fee and 2 bp adverse slippage per leg.
- `C_S5`: 10 bp fee and 5 bp adverse slippage per leg.
- `C_S10`: 10 bp fee and 10 bp adverse slippage per leg.

All 2,199 frozen entries resolved for P0, P1, P2, and P3. Each policy has 2,199 resolved replays and zero paired censoring; four cost records per replay produce 35,184 trade-table rows. The maximum number of simultaneously open frozen paths was five. Calendar coverage is 2024-01-01 01:00 UTC through 2025-12-31 20:00 UTC.

## Core results

Mean returns are shown as decimal returns.

| Policy | Cost | Raw | Gross | Net |
|---|---:|---:|---:|---:|
| P0 | C0 | 0.0001661 | 0.0001661 | 0.0001661 |
| P0 | C_BASE | 0.0001661 | -0.0002339 | -0.0022314 |
| P0 | C_S5 | 0.0001661 | -0.0008336 | -0.0028299 |
| P0 | C_S10 | 0.0001661 | -0.0018322 | -0.0038266 |
| P1 | C0 | 0.0000359 | 0.0000359 | 0.0000359 |
| P1 | C_BASE | 0.0000359 | -0.0003640 | -0.0023613 |
| P1 | C_S5 | 0.0000359 | -0.0009636 | -0.0029597 |
| P1 | C_S10 | 0.0000359 | -0.0019622 | -0.0039563 |
| P2 | C0 | -0.0003550 | -0.0003550 | -0.0003550 |
| P2 | C_BASE | -0.0003550 | -0.0007548 | -0.0027513 |
| P2 | C_S5 | -0.0003550 | -0.0013542 | -0.0033495 |
| P2 | C_S10 | -0.0003550 | -0.0023523 | -0.0043456 |
| P3 | C0 | -0.0001138 | -0.0001138 | -0.0001138 |
| P3 | C_BASE | -0.0001138 | -0.0005137 | -0.0025107 |
| P3 | C_S5 | -0.0001138 | -0.0011132 | -0.0031090 |
| P3 | C_S10 | -0.0001138 | -0.0021116 | -0.0041054 |

## Exit quality and opportunity capture

At C0, held-green-then-red counts were P0 1,565, P1 1,467, P2 1,281, and P3 1,110. Common-opportunity-positive/exit-red counts were P0 1,565, P1 1,481, P2 1,281, and P3 1,272. Mean held peak-gain surrender was 0.01708, 0.00840, 0.01079, and 0.00411 respectively; mean common capture gap was 0.01708, 0.01721, 0.01760, and 0.01736. The distinction matters: earlier exits reduced held-path surrender without improving the immutable opportunity-capture comparison.

P1 recorded 488 barrier take-profits, 631 stops, two gap-through executions, one conservative both-hit ambiguity, and 1,078 common-horizon closes. P2 activated 849 times, triggered 833 trails, and closed 1,366 at H. P3 triggered 2,190 momentum exits and closed nine at H.

## Predefined baseline-failure cohorts

The +0.5%, +1%, +2%, and +3% nested P0-failure cohorts contain 695, 381, 153, and 50 trades. C0 profitability-rescue rates for P1/P2/P3 were respectively 17.70%/44.03%/50.36%, 32.28%/80.31%/51.18%, 80.39%/90.20%/53.59%, and 74.00%/90.00%/58.00%. These are retrospective, nested descriptive cohorts and are not independent tests or policy-selection evidence. Cost-specific net rescue, paired deltas, and outside-cohort outcomes are in `candidate_cohorts.json`.

## Premature exits, robustness, and uncertainty

Premature-appreciation counts were P1 652 (29.65%), P2 577 (26.24%), and P3 1,124 (51.11%). Mean foregone subsequent gain was 1.038%, 0.978%, and 1.625%; P3's median was 0.530% while P1 and P2 medians were zero.

At C_BASE, headline equal-weight-symbol paired net-return estimates and monthly-block 95% intervals were: P1 0.0000673 `[-0.0011750, 0.0013570]`; P2 -0.0003525 `[-0.0015170, 0.0008491]`; P3 -0.0000473 `[-0.0016420, 0.0013725]`. Every interval includes zero. Results are heterogeneous by symbol: XRP is negative for all candidates, while BNB and SOL are generally more favorable. The sanity partition is negative for all candidates. Calendar blocks retain all symbols together; no naive per-trade standard errors are used.

## Research interpretation

Overall classification: **MIXED**.

- Exit-quality evidence: `MIXED`.
- Opportunity-capture evidence: `MIXED`.
- Cost sensitivity: `COUNTS AGAINST`.
- Premature-exit damage: `COUNTS AGAINST`.
- Cross-symbol/time robustness: `INSUFFICIENT EVIDENCE`.

P1 remains a standing-bracket diagnostic. P2 and P3 are the direct 5-minute active-exit tests. No winner is selected. The result does not establish deployability, portfolio turnover, or profitability. C2-B would be necessary to make portfolio-level claims, but it is not automatically required after this C2-A result and is not scientifically warranted for the current P1/P2/P3 configurations.

Accepted scientific gates:

- Current P1/P2/P3 portfolio stage: **DO NOT PROCEED TO C2-B**.
- Current P1/P2/P3 development: **DO NOT ADVANCE EXISTING FAST-EXIT POLICIES**.
- Separately pre-registered milestone-state continuation research: **JUSTIFIES FOLLOW-ON MILESTONE-STATE EXPERIMENT**. This delivery does not design or implement that study.

## Artifacts and limitations

The paired trade table separates held and common-horizon fields, raw/gross/net returns, costs, flags, execution reasons, ambiguity, and censoring. The paired table (`c2a_paired_trade_records.csv`) and full-panel detail (`candidate_complete_analysis.json`) are reproducible generated/local artifacts and are intentionally ignored rather than source-controlled. Their hashes are preserved in `candidate_manifest.json` and `candidate_reproducibility.json`; the accepted full-panel SHA-256 is `35de479f718b422a94cef554df522cdfcdea7ce098349178e7906064438ce807`. Compact summaries, manifests, interpretation, and reproducibility evidence remain source-controlled. `candidate_dependence.json` contains dependence-aware intervals; `candidate_manifest.json` contains parameters, environment/interpreter, source hashes, code hashes, output hashes, and rebuild evidence.

No 2026 market outcome was accessed. The input boundary is end-exclusive at 2026-01-01 00:00 UTC and exact-boundary rejection is tested. The untouched 2026 period remains reserved as potential confirmation data for any separately pre-registered follow-on. Temporal diagnostics were not used as inputs, features, thresholds, cohort definitions, or policy-selection evidence. Policy IDs and parameters were unchanged. C2-B was not implemented or run.

## Final repository state and command record

- Final branch: `research/c2-asymmetric-exit`
- Final HEAD: `5c2089bbe9708d1be25ec427a9a4013bcb64601b`
- Final status: eleven unstaged task files (ten tracked modifications plus this untracked delivery); no staged entries.
- Final tracked diff: 10 files changed, 6,183 insertions, and 2,594 deletions; the untracked delivery contains 117 lines. The ignored full-panel artifact is excluded from the Git diff.

The reproducibility command evidence is recorded in `candidate_reproducibility.json` and `candidate_manifest.json`. The explicit execution/validation command record is:

```text
conda run -n binance-v2-research env PYTHONPATH=src pytest -q
conda run -n binance-v2-research env PYTHONPATH=src python -m binance_data_foundation.c2_candidate_cli --verify-rebuild
conda run -n binance-v2-research python -m pip wheel --no-deps --no-build-isolation . -w /tmp/binance-v2-wheelcheck
git diff --check
git status --short
git diff --stat
git diff --numstat
```

The policy replay verification command was completed before finalization and was not rerun for these documentation-only corrections.
