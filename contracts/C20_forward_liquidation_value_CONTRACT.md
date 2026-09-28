# C20 Executable Forward Liquidation Value Contract

Status: prospectively specified before C20 analysis.

## 1. Purpose

C19 established that C18's target:

    DELTA_V_PRE(t)
      = HOLD_TO_P0_NET(t) - EXIT_NOW_NET(t)

is valid accounting but answers a terminal-commitment question:

    EXIT NOW
    versus
    COMMIT TO FROZEN P0.

The intended architecture is instead sequential:

    observe causally at higher resolution after entry,
    continue when justified,
    and reassess later.

C20 therefore studies executable forward liquidation value over bounded,
prospectively fixed horizons.

C20 asks two distinct questions:

1. ECONOMIC ORDERING:
   Does higher frozen C9 p_t2 predict higher executable forward liquidation
   value?

2. ECONOMIC LEVEL:
   Was delayed liquidation economically better than immediate liquidation,
   on average, for the population/horizon being described?

These questions must remain distinct.

C20 is a characterization study.

It does NOT define an exit policy.

## 2. Frozen dependencies

Reuse without scientific modification:

- C7 frozen population and canonical execution semantics
- C8 frozen 60m/5m pre-T2 architecture
- C9 frozen calibrated p_t2 probabilities
- C18 causal pre-T2 snapshot population
- C19 timing/accounting conclusions

No modification of C7-C19 scientific behavior.

No 2026 data or metadata access.

## 3. Population

Use honest frozen-C9 scored causal pre-T2 snapshots from C18.

Expected reference:

- 2,199 frozen trades
- 845 T2_FIRST
- 1,354 P0_FIRST
- 56,217 honest frozen-C9 scored snapshots
- 1,610 scored trades

Reconcile exact counts before analysis.

No unscored state may receive an inferred C9 probability.

## 4. Immediate executable liquidation

For causal state completed at timestamp t:

EXIT_NOW_NET(t)

means liquidation at the immediate next valid 1-minute open after t using
frozen execution and cost semantics.

Requirements:

- completed information only;
- exact next-open execution;
- no intrabar hindsight;
- missing/duplicate/gapped execution evidence fails closed;
- frozen lifecycle terminal execution wins applicable ties.

## 5. Primary forward liquidation targets

Use fixed prospective horizons:

- 5 minutes
- 15 minutes
- 30 minutes
- 60 minutes

For each horizon H define the intended reassessment timestamp:

    r_H = t + H

The forward liquidation action must be based on information available through
r_H and execute at the immediate next valid 1-minute open after r_H.

However, a trade cannot remain hypothetically open beyond its frozen first
lifecycle terminal event.

Therefore define:

    endpoint_H =
        earliest of:
        - reassessment horizon H
        - first frozen lifecycle event after t

where the lifecycle event is:

- T2, if T2 occurs first;
- P0, if P0 occurs first.

If the lifecycle event occurs before the requested horizon, use the frozen
event execution semantics rather than looking beyond that event.

No post-terminal prices may enter the target.

## 6. Executable forward liquidation value

For each horizon H:

FORWARD_NET_H(t)
    = net trade value at the executable endpoint_H liquidation

DELTA_LIQ_H(t)
    = FORWARD_NET_H(t) - EXIT_NOW_NET(t)

Interpretation:

DELTA_LIQ_H > 0:
    delaying liquidation until the bounded executable endpoint was better
    than liquidating immediately.

DELTA_LIQ_H < 0:
    immediate liquidation was better.

DELTA_LIQ_H == 0:
    economically equivalent.

These are future-derived evaluation targets only.

## 7. First-event liquidation target

Also define:

EVENT_NET(t)
    = net trade value at the frozen first lifecycle event after t

DELTA_LIQ_EVENT(t)
    = EVENT_NET(t) - EXIT_NOW_NET(t)

where first lifecycle event is T2 or P0 using frozen event semantics.

This target is included because frozen C9 predicts:

    P(T2 before P0 | causal state).

It must be reported separately from fixed-horizon targets.

It is not a trading policy.

## 8. No future maximum / hindsight opportunity target

Future maximum price, future MFE, best future exit, and hindsight-optimal
liquidation are NOT primary targets.

C20 must not define economic value using:

- maximum future price;
- maximum future return;
- best price within horizon;
- best exit timestamp;
- hindsight-selected endpoint.

Such quantities are unattainable ex ante.

If future MFE is reported at all, it must be explicitly labeled descriptive
hindsight opportunity and kept outside primary conclusions.

## 9. Incremental costs

Use frozen execution-cost semantics.

Primary:
C_BASE

For each comparison, apply the actual liquidation costs associated with:

- EXIT_NOW
- forward/event liquidation

Already-incurred entry-side costs common to both alternatives cancel in the
paired comparison.

Verify this algebraically and in tests.

Descriptive cost sensitivity only:

- C0
- C_S5
- C_S10

Do not choose a cost scenario based on outcomes.

## 10. Primary C9 probability bands

Use frozen honest C9 p_t2 bands:

- <0.20
- 0.20 to <0.40
- 0.40 to <0.60
- 0.60 to <0.80
- >=0.80

For EACH target:

- DELTA_LIQ_5
- DELTA_LIQ_15
- DELTA_LIQ_30
- DELTA_LIQ_60
- DELTA_LIQ_EVENT

report per band:

- snapshots
- unique trades
- mean
- median
- p10
- p25
- p75
- p90
- fraction > 0
- fraction < 0
- exact-zero fraction

Use whole-trade-aware weighting for means/proportions/associations so long
trades do not dominate.

## 11. Economic ordering

Economic ordering asks:

"Does higher p_t2 correspond to higher forward liquidation value?"

For every target report:

- Spearman association between p_t2 and DELTA_LIQ;
- trade-weighted linear correlation;
- bandwise mean DELTA_LIQ;
- bandwise median DELTA_LIQ;
- bandwise fraction DELTA_LIQ > 0;
- highest-minus-lowest probability-band mean.

Do NOT require DELTA_LIQ itself to be positive to establish ordering.

Ordering and absolute economic level are distinct.

## 12. Economic level

Economic level asks:

"Was delayed liquidation better than immediate liquidation on average?"

For every target report:

- overall mean DELTA_LIQ;
- median DELTA_LIQ;
- fraction positive;
- fraction negative;
- exact-zero fraction;
- total paired P&L difference if denominated consistently with frozen
  notional.

A positive mean is evidence that delayed liquidation was better on average
for that population/horizon.

A negative mean is evidence that immediate liquidation was better on average.

This does NOT by itself establish predictive ordering by p_t2.

## 13. Do not select a best horizon

The 5m, 15m, 30m, and 60m targets are fixed characterization horizons.

C20 must not:

- rank them as a strategy choice;
- select the most profitable horizon;
- recommend a horizon based on realized returns;
- tune a horizon.

Report each horizon independently.

## 14. Endpoint composition

For each fixed horizon report what fraction of observations terminate because
of:

- requested horizon reached;
- T2 occurred before horizon;
- P0 occurred before horizon.

This is required for interpretation.

A 60m target may contain substantially more event-terminated observations
than a 5m target.

## 15. Outcome-class decomposition

Report each target separately for frozen eventual classes:

- T2_FIRST
- P0_FIRST

For each report:

- mean/median DELTA_LIQ;
- fraction positive;
- p_t2-band structure;
- endpoint composition.

Purpose:

understand whether ordering is simply inherited from lifecycle classification
or corresponds to executable forward value within classes.

## 16. Time-since-entry decomposition

Use fixed bands:

- 0-30m
- >30-60m
- >60-120m
- >120-240m
- >240m

For each target report:

- mean p_t2;
- mean/median DELTA_LIQ;
- fraction positive;
- p_t2 association.

No timing search.

## 17. Trajectory alignment

Within trades, for each target where enough observations exist, characterize
association between:

    p_t2(t)

and:

    DELTA_LIQ_H(t)

Report:

- eligible trade count;
- mean within-trade correlation;
- median within-trade correlation;
- p10/p90.

This tests whether C18's strong mechanically negative terminal-target
relationship changes under bounded executable horizons.

## 18. Year stability

Report primary ordering and level results separately for:

- 2024
- 2025

No revision after seeing 2025.

2026 remains sealed.

## 19. Symbol stability

Report primary ordering and level metrics separately for:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- BNBUSDT

No symbol-specific rules or exclusions.

## 20. Right-tail / downside decomposition

For each horizon report:

- positive paired contribution;
- negative paired contribution;
- p10/p90;
- worst DELTA_LIQ;
- best DELTA_LIQ;
- concentration of positive contribution by top 1%, 5%, 10%, 20% of trades.

This is characterization only.

Do not derive a policy.

## 21. Frozen interpretation taxonomy

Classify ECONOMIC ORDERING separately from ECONOMIC LEVEL.

### Ordering

ORDERING_SUPPORTED if:

- p_t2 association with DELTA_LIQ is positive in both 2024 and 2025;
- higher probability bands show broadly increasing forward value in both
  years;
- relationship is not driven by one symbol only.

WEAK_ORDERING if:
- association is directionally positive but materially non-monotonic,
  weak, or unstable by year/symbol.

NO_USEFUL_ORDERING if:
- p_t2 does not meaningfully order executable forward liquidation value.

INSUFFICIENT_ORDERING if required alignment cannot be established.

### Level

For each target independently classify:

POSITIVE_FORWARD_LEVEL:
    mean DELTA_LIQ > 0

NEGATIVE_FORWARD_LEVEL:
    mean DELTA_LIQ < 0

NEUTRAL_FORWARD_LEVEL:
    mean effectively zero only if exactly zero under the frozen calculation.

These labels are descriptive and are not policy recommendations.

Do not introduce significance thresholds post hoc.

## 22. C21 implication

C20 must recommend methodology, not a trading rule.

If one or more bounded targets show stable ORDERING_SUPPORTED:

a later checkpoint may test whether frozen p_t2 can support a prospectively
specified sequential decision rule.

If forward levels are positive but ordering is absent:

delayed liquidation may have population-level value, but C9 is not supported
as the selector.

If ordering exists but levels are negative:

C9 may rank relative opportunity while delay remains economically harmful on
average; do not confuse ranking with profitable continuation.

If neither ordering nor positive level is present:

do not proceed to a C9-based sequential policy without reformulating the
decision state.

Do not start C21.

## 23. Artifacts

Write to:

artifacts/c20_forward_liquidation_value/

Required:

- run_manifest.json
- provenance.json
- leakage_firewall.json
- population_reconciliation.json
- target_definition.json
- endpoint_composition.json
- overall_forward_value.json
- probability_band_summary.json
- economic_ordering.json
- economic_level.json
- outcome_class_summary.json
- elapsed_time_summary.json
- trajectory_alignment.json
- year_summary.json
- symbol_summary.json
- right_tail_downside_summary.json
- cost_sensitivity.json
- interpretation_predicates.json
- c21_recommendation.json
- final_summary.json
- reproducibility_hashes.json

Avoid large redundant snapshot dumps.

## 24. Tests

Add focused tests for:

- immediate next-open liquidation
- exact 5m/15m/30m/60m reassessment timing
- next-open execution after reassessment
- T2-before-horizon truncation
- P0-before-horizon truncation
- no post-terminal access
- event target
- paired cost cancellation
- gap/missing evidence
- probability-band assignment
- whole-trade weighting
- year/symbol grouping
- deterministic results
- no future-max target
- no 2026 access

Run focused tests.

Run the full repository suite once if runtime/scientific code is added or
changed.

## 25. Governance

Do not:

- modify C7-C19 scientific behavior
- train or recalibrate a model
- define or evaluate an exit policy
- optimize P&L
- select a best horizon
- search horizons
- search thresholds
- use future maxima or hindsight-best exits as primary targets
- access 2026
- begin C21
- stage, commit, or push

## 26. Final report

Report:

1. contract SHA
2. population reconciliation
3. leakage/timing verification
4. exact executable target equations
5. endpoint composition by horizon
6. overall 5m forward liquidation value
7. overall 15m value
8. overall 30m value
9. overall 60m value
10. first-event value
11. p_t2 bands for every target
12. ordering metrics for every target
13. economic-level classification for every target
14. T2_FIRST decomposition
15. P0_FIRST decomposition
16. elapsed-time results
17. within-trade trajectory alignment
18. 2024 stability
19. 2025 stability
20. symbol stability
21. right-tail/downside structure
22. cost sensitivity
23. frozen ordering classification
24. distinction between ordering and level conclusions
25. implication for C21
26. limitations
27. artifact hashes
28. focused/full test results
29. git diff --check
30. git status --short
31. confirmation no model/recalibration
32. confirmation no policy/P&L optimization
33. confirmation no best-horizon selection
34. confirmation no future-max/hindsight-optimal target
35. confirmation no 2026 access
36. confirmation nothing staged/committed/pushed

STOP after C20.
