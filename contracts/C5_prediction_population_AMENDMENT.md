# C5 — Prediction-Population and Complete-Path Amendment

Status: frozen non-economic governance amendment. This document authorizes only prediction-population provenance reconciliation and C5 T1 readiness mechanics. It does not authorize historical economic replay, return or P&L calculation, policy-trigger evaluation, model scoring, prediction generation, access to sealed confirmation data, or deployment.

Bound documents before this amendment:

- `contracts/C5_economic_exit_policy_CONTRACT.md`, SHA-256 `7379238efd22bded103697248752423f0f8a2f3dbd63edeca48b6ded70b5b060`;
- `contracts/C5_economic_exit_policy_ADDENDUM.md`, SHA-256 `1ed14533763e8458d419233523a764b22cbc79de9704219a7042e2ce221bc062`.

This amendment controls where it narrows the raw-snapshot coverage requirements in contract Sections 6, 19, and 22 and addendum Sections 2, 8, 11, and 12. All policy, threshold, execution, cost, uncertainty, classification, anti-overfitting, temporal, and sealed-data provisions remain unchanged.

## 1. Verified reconciliation basis

The accepted C4 prediction artifacts cover narrower populations than the raw T2-eligible risk set:

- 2024 contains 60,757 raw eligible snapshots, 59,957 accepted resolved snapshots, 59,752 complete-case model rows, and 30,467 frozen out-of-fold validation prediction rows. The prediction rows are exactly the disjoint union of Fold A validation (16,166) and Fold B validation (14,301). They are not predictions from the final all-2024 model.
- 2025 contains 67,082 raw eligible snapshots and 66,118 locked complete-case prediction rows. The 964 uncovered snapshots comprise 779 right-censored rows and 185 feature-incomplete rows. Prediction row IDs equal locked complete-case row IDs.

These facts do not authorize backfilling. They require a complete-path population rule before first-trigger replay.

## 2. Four immutable population layers

Every C5 readiness and later report must keep these denominators separate, pooled, by calendar year, and by symbol:

1. `raw_T2_eligible`: every accepted frozen T2-eligible snapshot and its distinct trades;
2. `complete_case_model_eligible`: accepted resolved, noncensored, nonambiguous rows satisfying the frozen P1 feature schema and their distinct trades;
3. `authorized_frozen_prediction`: rows having accepted frozen G1 and P1 predictions with exact identity and their distinct trades—2024 OOF validation predictions and 2025 locked predictions only;
4. `replay_authorized_complete_path`: whole trades for which every raw T2-eligible row from the first through final eligible snapshot belongs to layer 3 with exact G1/P1 one-to-one coverage.

The denominators must never be merged or relabeled. Layer 4, not layer 1, is the replay population governed by this amendment.

## 3. 2024 authorization

A 2024 trade is replay-authorized only when it is represented in the accepted frozen OOF validation prediction population; G1 and P1 identities match one-to-one; and its complete ordered raw T2-eligible path is continuously covered from its first through final eligible snapshot. Left truncation, an internal gap, right truncation, or complete absence excludes the whole trade.

Only Fold A and Fold B validation predictions are authorized. Training rows and predictions from the final all-2024 fit are prohibited. No model may be scored on its own 2024 training rows to expand C5 coverage.

## 4. 2025 authorization

A 2025 trade is replay-authorized only when it is represented in the accepted locked prediction population; G1 and P1 identities match one-to-one; and every ordered raw T2-eligible snapshot from first through final eligible snapshot is prediction-covered. Left truncation, an internal gap, right truncation, or a wholly unpredicted path excludes the whole trade.

## 5. Frozen exclusions

Every excluded trade must retain all applicable reason flags and one deterministic path-pattern label. Required reasons are:

- `left_truncated`;
- `internally_gapped`;
- `right_truncated`;
- `wholly_unpredicted`;
- `non_OOF_2024_training_population`;
- `feature_incomplete`;
- `censored_or_unresolved_prevents_full_path`.

An excluded row or trade may not be silently converted to a no-action decision. Missing predictions may not be imputed, regenerated, recalibrated, or backfilled. Analyst override is prohibited.

## 6. Support denominator

The addendum's unchanged threshold of at least 50 distinct trades is applied to pooled 2024-plus-2025 `replay_authorized_complete_path` trades for each symbol. A symbol with at least 50 is `SUFFICIENT SUPPORT FOR C5 SYMBOL-LEVEL INTERPRETATION`; a symbol below 50 is `INSUFFICIENT SUPPORT`.

Year counts are mandatory diagnostics, but neither year must independently reach 50. Low symbol support does not by itself block pooled replay; it blocks formal symbol-level interpretation and the symbol cannot count toward an addendum breadth condition requiring sufficient support. The existing four-of-five breadth, concentration, safety, and advancement rules are not weakened.

## 7. Year provenance and reporting

2024 evidence uses chronological-fold OOF validation predictions. 2025 evidence uses locked predictions from the frozen final C4 model. Every later C5 report must show pooled, 2024, and 2025 results in addition to per-symbol results. The year split is diagnostic robustness evidence only and may not select, tune, replace, or amend a policy, threshold, cost case, or classification.

## 8. Scientific limitation

The C5 development replay population is selected on prediction and complete-path availability. It is narrower than the raw T2 risk set and may differ structurally from excluded trades. C5 conclusions apply first to the replay-authorized complete-path population. Pooled or symbol-level success must not be described as established for every raw T2-eligible trade. No comparison of included and excluded economic outcomes is authorized by this amendment.

## 9. Corrected coverage gate

T1 readiness passes prediction coverage only if all four layers reconcile to accepted artifacts; the 2024 authorized set equals the frozen OOF validation union; the 2025 authorized set equals the locked complete-case prediction set; every layer-4 trade has identical raw-eligible, G1, and P1 row-ID sets; and every incomplete path is excluded with frozen reasons. Any missing, duplicate, extra, target-, trade-, symbol-, or timestamp-mismatched prediction inside layer 4 fails closed.

T2 readiness may be true only when governance and upstream provenance pass, complete-path construction passes, exact layer-4 coverage passes, tests pass, and no other governance blocker remains. This amendment does not itself authorize T2.

## 10. Anti-amendment rule

These population definitions, exclusions, support denominator, and year roles are frozen before economic replay. They may not change in response to any economic result. A future change requires new governance and cannot reuse outcomes for both selection and evaluation.
