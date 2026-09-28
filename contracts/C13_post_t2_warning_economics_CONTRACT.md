# C13 Post-T2 Warning Economics Contract

Status: prospectively frozen before C13 economic access.

## Question and population

C13 tests whether one conservative post-T2 probability warning improves the original P0 strategy after costs without unacceptable right-tail truncation. The primary denominator is every one of the frozen 2,199 E1/C7 entries (1,093 in 2024 and 1,106 in 2025). Expected structure is 845 first-T2 and 1,354 no-T2 trades. The C10 outcomes within first-T2 are frozen at 335 continuation-first, 508 deterioration-first, 2 P0-first, and zero ambiguous.

## Policies

Only P0, W1, and D2_CONTROL are evaluated. P0 is unchanged.

W1 uses only C11/C12 honest out-of-time calibrated probabilities. After first T2, three consecutive completed 1-minute observations with `p_cont < 0.20` establish the warning. It executes at the immediate next available 1-minute open, strictly before P0. P0 wins ties. Missing, duplicate, noncausal, or discontinuous execution evidence fails closed to exact P0. There is no recovery wait, additional confirmation, price rule, trail, re-entry, or partial exit. Training-period or in-sample predictions are forbidden.

D2_CONTROL freezes `D2 = (entry price + causal peak at first T2) / 2`. The first completed post-T2 1-minute bar with low at or below D2 establishes a touch. It executes at the immediate next 1-minute open strictly before P0. P0 wins ties and unavailable execution fails closed. D2 never trails and there is no intrabar fill assumption.

## Costs and estimands

Frozen C7 costs apply to actual executed notional: C0 zero; C_BASE 10 bp fee plus 2 bp adverse slippage per leg; C_S5 10 bp plus 5 bp; C_S10 10 bp plus 10 bp. Primary is the paired mean C_BASE net-return difference W1 minus P0 over all 2,199 entries, plus total paired net P&L. Secondary contrasts are D2_CONTROL minus P0 and W1 minus D2_CONTROL. C_S5 is mandatory robustness; C0 and C_S10 are descriptive.

All unavailable W1 paths are exact P0 fallbacks. Availability categories are no-T2, zero-row rapid transition, training-only/unavailable probability, P0-first edge, honest scored without trigger, and honest scored with a valid trigger. They must reconcile to the full population.

## Safety and uncertainty

Safety reuses C7 concepts: common-path MFE, realized capture, held-peak surrender, green-to-red, preserved-half-peak, lower-tail expected shortfall, worst trade, holding duration, and summed/union exposure. Frozen P0 raw-return winner cohorts are at least +2%, +3%, and +5%; each reports count, paired W1-P0 mean and four-entry-week moving-block interval, truncation fraction, and opportunity foregone.

Whole-trade four-entry-week moving-block bootstrap uses 2,000 replicates and seed `20261013`. No row-IID interval is permitted.

## Breadth and classification

Report 2024, 2025, five frozen symbols, and equal-weight-symbol results. `BROAD_POSITIVE` requires pooled W1-P0 > 0, at least 3/5 positive symbols, equal-weight-symbol > 0, and no symbol above 50% of total positive contribution. A positive pooled result failing that is `CONCENTRATED_POSITIVE`; otherwise `NO_POSITIVE`.

Classification precedence is fixed: INSUFFICIENT for failure of required accounting, honest provenance, causality, costs, safety, or uncertainty; COUNTS AGAINST CONSERVATIVE PROBABILITY EXIT if primary point <= 0, primary interval wholly below zero, C_S5 point <= 0, or a mandatory winner/right-tail interval is clearly adverse; SUPPORTS only when primary point > 0, its interval wholly > 0, C_S5 > 0, no safety breach, and breadth is BROAD_POSITIVE; otherwise MIXED. D2 cannot change the formal W1 label.

## Governance

Implementation, synthetic tests, full repository tests, identities, schemas, and readiness are frozen before economic access. Exactly one real C13 economic attempt is allowed. A pre-economic preflight failure does not consume it. After economic read or emission there is no scientific repair or rerun. C7-C12 scientific behavior is immutable. Thresholds, persistence, policies, models, and timeframes are not searched. All 2026 data and metadata are prohibited. C14 is out of scope. Nothing is staged, committed, or pushed.
