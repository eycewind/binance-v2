# C3 T3-A — Corrected 2024 Model Development and Specification Freeze

Status: corrected predictive Stage A development only. The previous T3-A metrics, models, hashes, and freeze are superseded. No overall C3 scientific verdict is made.

## Repository and scope

- Branch: `research/c3-milestone-state-continuation`
- HEAD: `6661fdaebc4da5acb8429abe5558b6e5abab35a1`; this revision predates and does not identify the untracked T3-A implementation.
- Environment: `binance-v2-research`, Python 3.11.16, `/home/ata/miniconda3/envs/binance-v2-research/bin/python`.
- The accepted T1/T2 inputs and 35-column feature schema were not changed.
- No 2025 feature was transformed or scored; no 2025 label, base rate, prediction, or metric was used. No 2026 path/file/data or economic analysis was accessed.

## Correction

The fixed calendar controls retain the contracted formulas `sin(2*pi*month/12)` and `cos(2*pi*month/12)`. Each now receives training-only median centering and IQR scaling in every fold/model and final fit. Zero-IQR controls are centered without scaling. Validation never influences these parameters. This changes penalized geometry, so all prior logistic artifacts were invalidated and rebuilt.

## Chronological folds

| Target | Fold | Train + / − (rate) | Validation + / − (rate) |
|---|---|---:|---:|
| M1 | A | 95 / 83 (0.5337) | 48 / 57 (0.4571) |
| M1 | B | 143 / 140 (0.5053) | 49 / 49 (0.5000) |
| M2 | A | 66 / 58 (0.5323) | 33 / 39 (0.4583) |
| M2 | B | 99 / 97 (0.5051) | 28 / 32 (0.4667) |

All partitions use milestone timestamps and strict resolution-before-boundary purging. Only complete-case feature-eligible rows with non-null supervised labels enter fitting. M1’s structurally excluded arrivals remain under ten minutes; M2’s remain within five minutes. `path_efficiency_5m` was not changed or imputed.

## Corrected results

Entries are validation ROC AUC / PR AUC / log loss / Brier / Brier skill versus fold B0.

| Target/fold | B0 | L0 C=1 | L1 C=.1 | L1 C=1 | L1 C=10 | L2 C=.1 | L2 C=1 | L2 C=10 |
|---|---|---|---|---|---|---|---|---|
| M1 A | .500/.457/.701/.254/.000 | .480/.444/.988/.365/-.435 | .573/.527/.828/.307/-.208 | .572/.512/1.060/.365/-.438 | .573/.517/1.169/.384/-.510 | .535/.480/.866/.318/-.252 | .508/.474/1.122/.373/-.470 | .505/.471/1.257/.394/-.550 |
| M1 B | .500/.500/.693/.250/.000 | .466/.476/.721/.263/-.053 | .489/.511/.751/.276/-.104 | .490/.528/.790/.290/-.160 | .485/.516/.801/.294/-.175 | .547/.581/.741/.272/-.086 | .527/.578/.781/.287/-.149 | .519/.570/.792/.292/-.167 |
| M2 A | .500/.458/.701/.254/.000 | .632/.593/.779/.284/-.119 | .545/.493/.717/.261/-.028 | .505/.456/.883/.312/-.232 | .492/.443/.999/.336/-.324 | .626/.588/.667/.238/.063 | .569/.496/.806/.284/-.119 | .538/.473/.944/.316/-.245 |
| M2 B | .500/.467/.694/.250/.000 | .632/.559/.700/.253/-.012 | .596/.587/.687/.246/.015 | .604/.586/.725/.261/-.042 | .603/.585/.742/.267/-.066 | .617/.601/.684/.246/.018 | .570/.586/.778/.281/-.123 | .563/.583/.839/.297/-.188 |

B1 retained always-continuation and always-fallback confusion/accuracy only:

| Target/fold | Always continuation TP/FP, accuracy | Always fallback TN/FN, accuracy |
|---|---:|---:|
| M1 A | 48/57, .457 | 57/48, .543 |
| M1 B | 49/49, .500 | 49/49, .500 |
| M2 A | 33/39, .458 | 39/33, .542 |
| M2 B | 28/32, .467 | 32/28, .533 |

All five contracted B2 diagnostics were rebuilt. Entries below are validation log loss / Brier; exact AUC, calibration, reliability, lift, confusion and training-only quintile boundaries remain in `metrics.json`.

| Target/fold | time | local return 15m | realized vol last6 5m | distance H1 SMA24 | BTC−subject 15m |
|---|---|---|---|---|---|
| M1 A | .734/.270 | .705/.255 | .710/.259 | .697/.252 | .717/.262 |
| M1 B | .714/.260 | .738/.272 | .683/.245 | .699/.253 | .727/.266 |
| M2 A | .694/.250 | .745/.275 | .723/.264 | .698/.252 | .723/.265 |
| M2 B | .727/.267 | .697/.252 | .700/.253 | .698/.251 | .695/.251 |

## Corrected selection

Mean Fold-A/Fold-B validation log loss remains minimized at `C=0.1` for L1 and L2, separately for both targets. No tie-break was needed:

| Target/model | C=.1 | C=1 | C=10 | Frozen C |
|---|---:|---:|---:|---:|
| M1 L1 | .78943 | .92502 | .98517 | .1 |
| M1 L2 | .80361 | .95132 | 1.02449 | .1 |
| M2 L1 | .70231 | .80407 | .87048 | .1 |
| M2 L2 | .67560 | .79159 | .89166 | .1 |

## Dependence-aware comparisons

Calendar-month block bootstrap: first model minus second, negative favors first; seed 20240923; 2,000 replications; linear type-7 2.5%/97.5% quantiles; all symbols/events in a sampled month remain together.

- M1 L1(.1)−L0 log loss: Fold A −0.154 [−0.320, −0.044], Fold B +0.031 [+0.003, +0.076]. M1 path-state improvement reverses.
- M1 L2(.1)−L1(.1): Fold A +0.036 [+0.009, +0.084], Fold B −0.010 [−0.032, +0.015]. Incremental context is unstable.
- M2 L1(.1)−L0: Fold A −0.059 [−0.124, +0.082], Fold B −0.012 [−0.037, +0.012]. Point estimates improve in both folds, but both intervals include zero; evidence remains inconclusive.
- M2 L2(.1)−L1(.1): Fold A −0.050 [−0.065, −0.026], Fold B +0.004 [−0.090, +0.118]. Fold-A context improvement is not reliable in Fold B.

The previous qualitative conclusions therefore remain: no stable incremental result is established. `time_from_entry_seconds` remains negative across M1 folds (L1 −0.190/−0.137) and reverses across M2 folds (L1 −0.070/+0.085). Coefficient signs and subgroup performance remain materially fold- and regularization-dependent; these are associations, not causal effects.

## Final 2024 fits

Final selection is milestone in `[2024-01-01,2025-01-01)`, feature eligible, non-null label, and resolution strictly before `2025-01-01T00:00:00Z`.

| Target | Rows | + / − | Ordered row-key SHA-256 |
|---|---:|---:|---|
| M1 | 381 | 192 / 189 | `f8f9946e25d93ca7fb654733e904b02641d62c2cb89407178796580887cebfbc` |
| M2 | 256 | 127 / 129 | `9d8747d9bbfc2755476909195bbd8ea793a8a4e8605dc55157bd02f461d690b0` |

| Final model | C | Artifact SHA-256 |
|---|---:|---|
| M1 L0 | 1.0 | `c9a26dfa02b8e4416fe11ca1511110d53c1fbf3d594186d6537bad4e4ae17a9f` |
| M1 L1 | 0.1 | `47a425c132661e67bea440383a4131a185729d8a78ae3545325be10bb38d4aa0` |
| M1 L2 | 0.1 | `f99bd98dfd351f2a3382b36db3187da2f32de6adf7aa35e726ce968b248491fc` |
| M2 L0 | 1.0 | `1d9b3d5b0ae1a87b613be94b5db42b692659d52524f7b25e071a7d72d46088e4` |
| M2 L1 | 0.1 | `a08ced297571f266cedde3006288d8ed9dfdf63a206fbcf8bab9ded471177aef` |
| M2 L2 | 0.1 | `d4ed0e60a2c748ba5b71513a0bb9ab9a4f36803de4e6adcfebb4fc65a416b508` |

Exact final preprocessing and coefficient order are persisted. The future evaluator must use these fitted models without refitting.

## Locked 2025 protocol

The freeze defines—but has not opened—the evaluation population as feature-eligible, non-null supervised milestone rows with milestone timestamp in `[2025-01-01,2026-01-01)` and resolution strictly before `2026-01-01T00:00:00Z`. Equality at the resolution boundary is excluded. It freezes exact final models, preprocessing, symbol order and full one-hot convention, calendar formula/scaling, solver/objective/tolerance/iterations, probability and metric clipping, calibration method (none), metrics, bootstrap rules, input hashes, and source/test hashes. No model-selection, refitting, preprocessing, calibration, or threshold decision remains for the future executor.

## Provenance, ledger, and reproducibility

- Source hashes: `c3_t3a.py` `432a1110...acfb`; CLI `6c4f34c3...2c34`; tests `2220b2ab...6f93`.
- Contract: `d1df751c...d3f2d`; feature schema file: `1259d04b...41347`; semantic schema: `190a434f...1818`.
- Per-run attempt ledger: 56/56 unique authorized attempts—B0 4, B1 4, B2 20, L0 4, L1 12, L2 12. It is explicitly an immutable complete per-run ledger, not a cumulative append-only history.
- Two independent offline rebuilds match each other and the published core hashes. Evidence is persisted in `independent_rebuild.json`; embedded evidence hash `223cad37...c56`.
- Core file hashes are recorded in `reproducibility_manifest.json`. The corrected freeze file hash is `bf90102a...9c68`.

## Verification and repository state

- `pytest -q -p no:cacheprovider tests/test_c3_t3a.py tests/test_c3_milestone.py`: 40 passed.
- `git diff --check`: passed.
- Nothing was staged, committed, or pushed.
- No overall C3 verdict, exit strategy, action threshold, P&L, backtest, or economic interpretation was produced.
