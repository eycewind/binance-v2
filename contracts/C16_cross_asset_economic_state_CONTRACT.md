# C16 Cross-Asset Economic-State Contract

Status: prospectively specified before C16 analysis.

## 1. Purpose

C14 defined the post-T2 economic target:

DELTA_V(t) =
    HOLD_TO_P0_NET(t)
    -
    EXIT_NOW_NET(t)

with:

HOLD_BETTER:
    DELTA_V > 0

EXIT_BETTER:
    DELTA_V < 0

C14 found that the existing local C11 feature representation did not predict
this economic state reliably.

C15 established that the economic state itself is persistent:

- most trades were MONOSTATE;
- median sign transitions per trade was zero;
- HOLD and EXIT states showed strong persistence;
- persistence was stable across 2024 and 2025.

Therefore C16 asks:

"Does contemporaneous causal cross-asset / market context explain economic
state information that is missing from the existing local feature set?"

C16 is a predictive characterization study.

It is NOT a trading-policy experiment.

## 2. Frozen dependencies

Reuse without scientific modification:

- C7 population and canonical P0 execution
- C10 post-T2 causal snapshot architecture
- C11 local feature families
- C14 DELTA_V target construction
- C15 temporal findings

Primary post-T2 target population:

- 845 first-T2 trades
- 843 binary continuation/deterioration source trades
- eligible causal snapshots exactly consistent with C14

Primary cost model:

C_BASE

No 2026 data or metadata may be accessed.

## 3. Leakage firewall

All predictive features must be constructible using information available at
or before completed state timestamp t.

Cross-asset features must use bars completed by t.

No future bar, future close, future return, future MFE/MAE, future recovery,
P0 outcome, DELTA_V, or future event label may enter the feature set.

DELTA_V remains future-derived target information only.

All rolling statistics must be causal.

Add explicit leakage tests.

## 4. Frozen universe

Use only the already-frozen five-symbol universe:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

Do not add coins.

No universe search.

## 5. Frozen feature families

C16 may add ONLY the following cross-asset feature families.

### A. Leader returns

Completed-bar returns for:

BTCUSDT
ETHUSDT

at fixed horizons:

- 5 minutes
- 30 minutes
- 60 minutes

For BTC or ETH trades themselves, the corresponding leader return remains
valid market context.

No additional horizons.

### B. Equal-weight market return

At each snapshot compute equal-weight return across the five-symbol universe
for:

- 5 minutes
- 30 minutes
- 60 minutes

using only completed bars.

### C. Market breadth

For each fixed horizon:

- 5 minutes
- 30 minutes
- 60 minutes

compute:

fraction of the five symbols with positive return.

No weighting optimization.

### D. Relative strength

For the traded symbol compute:

symbol return - BTC return

and:

symbol return - equal-weight universe return

for:

- 5 minutes
- 30 minutes
- 60 minutes

### E. Cross-sectional dispersion

For:

- 5 minutes
- 30 minutes
- 60 minutes

compute standard deviation of the five symbol returns.

Use one fixed formula.

No alternative dispersion estimators.

### F. Market volatility

Use equal-weight aggregate realized absolute-return or variance measure over
fixed causal windows:

- 30 minutes
- 60 minutes

Choose one deterministic implementation before model evaluation and record it
in the artifact.

Do not compare multiple volatility definitions.

### G. BTC co-movement

For the traded symbol versus BTC, compute one causal rolling correlation over
a fixed 60-minute window using completed 1-minute returns.

No correlation-window search.

For BTC itself, use a fixed neutral/self value and explicit indicator if
needed.

## 6. No feature expansion after results

No additional cross-asset features may be added after seeing predictive
results.

Specifically prohibited:

- funding
- order book
- derivatives data
- volume imbalance
- dominance indices
- external sentiment
- macro data
- additional coins
- technical indicators
- alternative timeframes
- nonlinear feature engineering

Those may be future research only.

## 7. Model comparison

Use fixed models:

M0:
    training prevalence

M1:
    existing C11 5m-context-only feature set

M2:
    existing C11 full local 5m-context + 1m-state feature set

M3:
    M2 plus the frozen C16 cross-asset feature set

Use the same fixed logistic procedure as C14.

No model-family search.

No regularization search.

No feature subset search.

No interactions added after evaluation.

## 8. Development / validation split

Use:

2024:
    chronological whole-trade development / out-of-fold evaluation

2025:
    untouched final validation after procedure freeze

Whole trades must remain intact.

Training data must precede validation data.

All preprocessing must be fit on training data only.

Each trade receives total statistical weight one so long trajectories do not
dominate.

No model revision after 2025 evaluation.

2026 remains sealed.

## 9. Primary metrics

For M0/M1/M2/M3 report:

- Brier score
- log loss
- AUC
- calibration intercept
- calibration slope
- ECE

Primary comparison:

M3 versus M2

because C16 asks whether cross-asset context adds information beyond the
existing local state.

## 10. Frozen evidence criteria

Before evaluation, use these classifications.

CROSS_ASSET_SIGNAL_SUPPORTED if:

- M3 improves over M2 on BOTH Brier and log loss in 2024 OOF;
- M3 improves over M2 on BOTH Brier and log loss in untouched 2025;
- M3 AUC > M2 AUC in both 2024 and 2025;
- M3 calibration slope remains positive in both years;
- improvement is not solely attributable to one symbol.

WEAK_CROSS_ASSET_SIGNAL if:

- M3 improves at least one proper score over M2 in both years,
  OR
- M3 improves both proper scores strongly in one year and directionally in
  the other,
but full support criteria fail.

NO_USEFUL_CROSS_ASSET_SIGNAL if:

- M3 does not show stable improvement over M2.

INSUFFICIENT if:

- leakage-safe feature construction, timestamp alignment, or required
  validation cannot be established.

Do not redefine these criteria after results.

## 11. Deterioration-first subgroup

Evaluate the SAME frozen M3 model inside:

DETERIORATION_FIRST

Do not fit a subgroup-specific model.

Report:

- prevalence
- Brier
- log loss
- AUC
- calibration

Compare against M2 within the same subgroup.

This directly tests whether market context helps distinguish economically
recoverable deterioration from economically harmful deterioration.

## 12. Trade-level economic class characterization

C15 showed most trades are economically monostate.

For descriptive analysis only, characterize each trade as:

PREDOMINANTLY_HOLD:
    >80% eligible snapshots are HOLD_BETTER

PREDOMINANTLY_EXIT:
    >80% eligible snapshots are EXIT_BETTER

MIXED:
    otherwise

These thresholds are descriptive only and are frozen prospectively.

Report:

- counts
- year split
- symbol split
- continuation/deterioration composition
- cross-asset context at first eligible post-T2 snapshot

Do NOT train a separate trade-level model.

Purpose:

determine whether the economic class may already be visible around T2.

## 13. T2-entry context

For each trade, record the frozen cross-asset feature set at the first eligible
post-T2 snapshot.

Compare descriptive distributions between:

- PREDOMINANTLY_HOLD
- PREDOMINANTLY_EXIT
- MIXED

Report standardized differences.

No significance-mining or feature selection.

## 14. Feature-family ablation

Do NOT search arbitrary feature subsets.

One fixed descriptive family ablation is permitted:

Starting from M3, remove one C16 feature FAMILY at a time:

- leader returns
- market return
- breadth
- relative strength
- dispersion
- volatility
- BTC co-movement

Evaluate only on 2024 OOF.

Purpose:

understand whether any single family dominates the cross-asset contribution.

Do not use ablation results to redesign M3.

Do not repeat ablation on 2025.

## 15. Symbol robustness

Report M2 and M3 metrics separately for:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

No symbol-specific models.

No symbol exclusions.

No ranking-based policy.

## 16. Year robustness

Report all primary comparisons separately for:

- 2024 OOF
- 2025 untouched

The direction of M3-M2 changes must be explicit.

## 17. Feature association report

For M3 report standardized logistic coefficients grouped by:

- existing local context
- existing 1m state
- each C16 cross-asset family

Interpret only as predictive associations.

Do not claim causality.

## 18. Artifacts

Write to:

artifacts/c16_cross_asset_economic_state/

Required:

- run_manifest.json
- provenance.json
- leakage_firewall.json
- population_reconciliation.json
- cross_asset_feature_schema.json
- feature_alignment_audit.json
- trade_class_summary.json
- t2_context_summary.json
- fold_definitions.json
- model_metrics_2024.json
- calibration_2024.json
- deterioration_subset_2024.json
- family_ablation_2024.json
- frozen_model_procedure.json
- model_metrics_2025.json
- calibration_2025.json
- deterioration_subset_2025.json
- symbol_metrics.json
- feature_associations.json
- interpretation_predicates.json
- final_summary.json
- reproducibility_hashes.json

Avoid large redundant raw dumps.

## 19. Tests

Add focused tests for:

- cross-symbol timestamp alignment
- completed-bar-only feature calculation
- leader returns
- equal-weight market return
- breadth
- relative strength
- dispersion
- volatility
- BTC correlation
- no target-derived features
- no future bars
- whole-trade weighting
- chronological folds
- training-only preprocessing
- deterministic feature generation
- deterministic model results
- no 2026 access

Run focused tests.

Run the full repository suite once.

## 20. Governance

Do not:

- modify C7-C15 scientific behavior
- define or evaluate an exit policy
- optimize P&L
- search thresholds
- search horizons
- add feature families
- search models
- access 2026
- begin C17
- stage, commit, or push

## 21. Final report

Report:

1. contract SHA
2. population/snapshot reconciliation
3. leakage/alignment audit
4. trade economic-class composition
5. T2 cross-asset context characterization
6. exact frozen C16 feature set
7. 2024 M0/M1/M2/M3 metrics
8. 2024 M3-vs-M2 comparison
9. 2024 deterioration-first comparison
10. 2024 fixed family ablation
11. 2025 M0/M1/M2/M3 metrics
12. 2025 M3-vs-M2 comparison
13. 2025 deterioration-first comparison
14. symbol robustness
15. feature-family associations
16. frozen interpretation classification
17. whether cross-asset context adds useful economic-state information
18. limitations
19. implication for C17
20. artifact hashes
21. focused/full tests
22. git diff --check
23. git status --short
24. confirmation no policy/P&L optimization
25. confirmation no model/feature/horizon search
26. confirmation no 2026 access
27. confirmation nothing staged/committed/pushed

STOP after C16.
