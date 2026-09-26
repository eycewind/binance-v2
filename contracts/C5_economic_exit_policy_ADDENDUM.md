# C5 — Reviewed Pre-Execution Classification Addendum

Status: pre-execution governance addendum. This document freezes previously unresolved C5 economic-classification rules. It does not authorize implementation, historical replay, P&L calculation, deployment, or access to sealed confirmation data.

Bound contract: `contracts/C5_economic_exit_policy_CONTRACT.md`

Pre-addendum contract SHA-256: `e836c3ac834b6beb49a87b1efa5dd0fb4f157725810ac68efb57bbea509de0de`

This addendum is scientifically controlling where it narrows or resolves Sections 14–18 and 22 of the bound contract. All other contract provisions remain unchanged. The five-policy family, frozen T2 eligibility, global score and quantiles, execution timing, costs, paired design, bootstrap, development-era governance, seal, and anti-overfitting prohibitions remain binding.

The later non-economic `contracts/C5_prediction_population_AMENDMENT.md`, bound to this addendum's SHA-256 `1ed14533763e8458d419233523a764b22cbc79de9704219a7042e2ce221bc062`, controls the replay population, complete-path exclusions, pooled support-count denominator, year roles, and corrected coverage gate. The threshold remains 50; only its population denominator is clarified before economic replay.

## 1. Fixed scope and primary policy

The five variants remain exactly:

1. `P0_HELD_V1`;
2. `G1_Q75_EXIT_V1`;
3. `P1_Q75_EXIT_V1`;
4. `G1_Q90_EXIT_V1`; and
5. `P1_Q90_EXIT_V1`.

Q75 remains the sole primary intensity and the only variant eligible for a T3 policy freeze. Q90 is a mandatory sparse-intervention sensitivity used to diagnose robustness and winner preservation. Q90 cannot replace Q75 because it has better observed P&L, better symbol results, or a more favorable interval. No Q75/Q90 choice may be made separately by symbol. If Q75 fails the advancement rule, Q90 cannot rescue or advance C5 V1; a favorable Q90 result is descriptive evidence for a separately governed future experiment only.

All symbol analysis applies the identical global, model-specific Q75/Q90 cutoffs already defined by the contract. No symbol-specific threshold, recalibration, refit, score, feature, or policy selection is permitted.

## 2. Per-symbol support

For each named symbol, the primary support count is the number of distinct frozen E1 `trade_id` values that contribute at least one causally eligible frozen T2 snapshot under the accepted risk-set rules. Repeated snapshots never increase this count. Always report the raw distinct-eligible-trade count, total frozen trades, triggered trades, paired-comparison trades, represented entry weeks, and usable bootstrap blocks.

- `>= 50` distinct T2-eligible trades is sufficient for formal symbol-level directional interpretation, subject to the required paired data being available.
- `< 50` distinct T2-eligible trades requires the symbol-level formal evidence and deployment-suitability label `INSUFFICIENT SUPPORT`.

Insufficient support is not economic failure and does not make a point estimate zero or unfavorable. Such a symbol remains in every pooled economic calculation and its descriptive results remain visible. The threshold is frozen and cannot change after replay.

## 3. Symbol-level directional economic evidence

All classifications use Q75, `C_BASE`, net expectancy, and the unchanged common policy. Let:

```text
Delta_path = mean net return(P1_Q75) - mean net return(G1_Q75)
Delta_practical = mean net return(P1_Q75) - mean net return(P0)
```

Both are paired on their applicable trade panels. Gross-only results cannot determine a classification.

For a symbol with at least 50 distinct eligible trades and available paired point estimates:

- `DIRECTIONALLY FAVORABLE`: `Delta_path > 0` and `Delta_practical > 0`.
- `DIRECTIONALLY UNFAVORABLE`: either key delta is below zero and its valid 95% paired block-bootstrap interval is entirely below zero. This is the frozen meaning of a negative estimate large/clear enough to reverse the intended benefit.
- `MIXED`: the two point estimates disagree in sign; either is exactly zero; both are negative without an entirely-negative interval; or neither favorable nor directionally unfavorable rule is met.
- `INSUFFICIENT SUPPORT`: fewer than 50 distinct eligible trades, either paired point estimate is unavailable, or the data required to form the comparisons are formally unavailable.

A confidence interval crossing zero is uncertainty, not failure. A positive point estimate whose interval crosses zero can still be directional evidence. No raw/gross result, win rate, capture metric, or subgroup overrides the two net comparisons.

## 4. Symbol-level statistical strength

Statistical strength is reported separately from directional evidence and deployment suitability. It uses only paired trade-level uncertainty under the contract's four-entry-week moving-block bootstrap: 2,000 `PCG64` replicates, seed `20240923`, and Type-7 equal-tailed 95% intervals. Row-IID or ordinary trade-IID intervals are prohibited.

For `Delta_path`:

- `STRONG SUPPORT`: point estimate `> 0` and the 95% paired block-bootstrap interval is entirely `> 0`.
- `DIRECTIONAL SUPPORT`: point estimate `> 0` and the interval includes zero.
- `COUNTS AGAINST`: point estimate `< 0` and the interval is entirely `< 0`.
- `MIXED`: the interval is available but the path comparison conflicts with the practical comparison, the point estimate is exactly zero, or the primary economic evidence is otherwise internally unstable under the fixed rules.
- `INSUFFICIENT SUPPORT`: fewer than 50 distinct eligible trades or the paired bootstrap is formally/numerically unavailable.

An interval including zero must not be relabeled failure. `STRONG SUPPORT` describes statistical strength; it is not required for the developmental suitability label below.

## 5. Frozen safety-breach rule

No new arbitrary numeric winner-truncation or downside hurdle is introduced. For Q75 and `C_BASE`, an `UNACCEPTABLE SAFETY BREACH` exists for a symbol when any one of these paired P1-minus-matched-G1 95% block-bootstrap intervals is entirely in the adverse direction:

- net-return 10% expected shortfall is lower for P1;
- the green-to-red indicator rate is higher for P1;
- the rate of early exits followed by a subsequent entry-relative `+2%`, `+3%`, or `+5%` opportunity is higher for P1; or
- mean opportunity foregone after early exit is higher for P1.

For metrics where higher is adverse, an entirely positive P1-minus-G1 interval is adverse; for expected shortfall, an entirely negative interval is adverse. Exact-zero boundaries are not breaches. If a required safety interval is unavailable, safety is `INSUFFICIENT`, not passed, for symbol suitability and overall advancement. P1-versus-P0 safety metrics remain mandatory descriptive diagnostics, but the immutable held baseline has no comparable policy-triggered early-exit rate and therefore is not used to impose an impossible zero-truncation requirement.

This rule freezes the first-replay safety decision without mining a magnitude threshold. It does not permit ignoring a harmful point estimate: every point estimate and interval remains reported even when it does not meet the breach rule.

## 6. Symbol-level deployment suitability

Deployment suitability here means suitability of the unchanged common Q75 policy for further validation. It does not authorize live or paper deployment.

For each symbol assign exactly one:

- `SUITABLE FOR FURTHER VALIDATION` requires at least 50 eligible trades, `Delta_path > 0`, `Delta_practical > 0`, no unacceptable safety breach, and all required safety classifications available. This is the frozen meaning of acceptable `C_BASE` net expectancy: net-of-cost benefit over both matched G1 and P0. No additional absolute-profit or minimum-return hurdle applies.
- `MIXED / HOLD` applies with sufficient support when evidence is mixed, either net comparison is nonpositive without meeting `NOT SUPPORTED`, or safety is insufficient without a demonstrated breach.
- `NOT SUPPORTED` applies with sufficient support when either key net comparison has a valid 95% paired interval entirely below zero or an unacceptable safety breach is present.
- `INSUFFICIENT SUPPORT` applies when fewer than 50 distinct eligible trades or either required paired point estimate is unavailable.

A CI entirely above zero strengthens `SUITABLE FOR FURTHER VALIDATION` and must be reported as `STRONG SUPPORT`, but exclusion of zero is not required for this developmental label. Per-symbol suitability remains separate from the overall C5 classification.

## 7. Breadth and concentration

For Q75 under `C_BASE`, compute each symbol's signed paired fixed-notional contribution to total P1-minus-P0 net improvement. Also compute signed contributions for P1-minus-G1. Negative contributions must remain negative.

For P1-minus-P0, define positive-only contribution shares as:

```text
positive_share_s = max(contribution_s, 0)
                   / sum_j max(contribution_j, 0)
```

The share is defined only if the positive-contribution denominator is greater than zero. Do not use positive-only shares in place of signed contributions or net pooled improvement. Report for every symbol:

- signed P1-minus-P0 contribution;
- signed P1-minus-G1 contribution;
- positive P1-minus-P0 contribution share;
- negative contribution magnitude, equal to `max(-contribution_s, 0)`; and
- its inclusion in the net pooled improvement.

Report the sum of signed contributions and reconcile it exactly to the applicable paired pooled fixed-notional improvement. Positive shares may hide offsetting harm if shown alone, so they must always appear beside signed contributions, total negative magnitude, and net pooled improvement.

Classify `BROAD / MULTI-SYMBOL ECONOMIC VALUE` only if all of the following hold:

- at least four of the five named symbols each have at least 50 distinct eligible trades and favorable P1-minus-P0 net-expectancy point estimates;
- at least four of the five named symbols each have at least 50 distinct eligible trades and favorable P1-minus-G1 net-expectancy point estimates;
- no symbol with at least 50 eligible trades has a P1-minus-G1 95% paired interval entirely below zero; and
- no single symbol contributes more than 50% of total positive P1-minus-P0 improvement.

The two sets of four symbols need not be identical, but the overall strategy advancement rule still requires favorable pooled P1-minus-G1 and P1-minus-P0 evidence. A symbol below 50 eligible trades cannot count toward either four-of-five condition; it is not removed from pooled economics.

Classify `CONCENTRATED ECONOMIC VALUE` when the pooled Q75 economics otherwise satisfy the support rule but either:

- one symbol contributes more than 50% of total positive P1-minus-P0 improvement; or
- fewer than four sufficiently supported symbols have favorable P1-minus-P0 point estimates; or
- fewer than four sufficiently supported symbols have favorable P1-minus-G1 point estimates.

If the positive-share denominator is zero, broad value cannot be established. The 50% boundary is inclusive for broad value: a share exactly equal to 50% passes; only `> 50%` is concentrated. This rule is frozen and cannot change after replay.

A supported symbol with a clearly adverse P1-minus-G1 interval prevents `BROAD / MULTI-SYMBOL ECONOMIC VALUE`. If pooled economics otherwise support continuation, the overall result is at most `SUPPORTS BUT CONCENTRATED`; the adverse symbol must be named. Never describe concentrated evidence as “works across the five-symbol universe.”

## 8. Low-support and unavailable-bootstrap handling

If a symbol has fewer than 50 distinct eligible trades:

- report all descriptive gross, cost, net, path, safety, and opportunity metrics;
- report its raw support counts and point estimates where computable;
- do not use its bootstrap output for strong claims;
- classify formal symbol evidence and suitability `INSUFFICIENT SUPPORT`; and
- retain all valid trades from that symbol in pooled economics and pooled uncertainty.

If a symbol has at least 50 eligible trades but its paired bootstrap is numerically or structurally unavailable:

- report the precise failure reason, support counts, and directional point estimates;
- statistical strength is `INSUFFICIENT SUPPORT`;
- it cannot receive `STRONG SUPPORT`;
- its suitability is `MIXED / HOLD` unless a separate available required comparison already establishes `NOT SUPPORTED`; and
- it cannot count toward a breadth condition that explicitly requires a valid interval, but may count toward a favorable-point-estimate condition.

No symbol may be silently dropped, replaced with a naive interval, or excluded from pooled economics because its symbol-level interval is unavailable.

## 9. Materiality and transaction-cost survival

The accepted contract did not contain a justified numeric minimum-return hurdle. None is added. For this first replay, the frozen advancement dimensions are economic direction, survival of `C_BASE` transaction costs, paired uncertainty, winner truncation, downside safety, and concentration.

No post-hoc materiality threshold may be created after replay. `C_BASE` net comparisons, not raw or gross comparisons, determine direction and advancement. `C_S5` survival retains the main contract's role. All four cost cases and the full fee/slippage decomposition remain mandatory.

For overall advancement, `C_S5` survival means that the pooled Q75 P1-minus-G1 and P1-minus-P0 net-expectancy point estimates both remain strictly greater than zero under `C_S5`, and no pooled Section 5 safety breach appears under `C_S5`. A confidence interval entirely above zero is not required for this cost sensitivity. Failure of either directional comparison or a demonstrated safety breach means the primary benefit does not survive `C_S5`.

## 10. Overall C5 classification

The decisive attribution remains P1-Q75 versus matched G1-Q75. P1-Q75 versus P0 remains the practical baseline comparison. Overall classification is separate from every symbol's suitability label.

Assign exactly one overall outcome:

### `SUPPORTS BROAD ECONOMIC EXIT VALUE`

Requires all of the main contract's valid-engineering and primary Q75 requirements, favorable pooled `C_BASE` P1-minus-G1 and P1-minus-P0 point estimates, the paired P1-minus-G1 interval entirely above zero, no overall unacceptable safety breach under the same Section 5 metric/direction rule applied to pooled pairs, survival under `C_S5`, and satisfaction of every `BROAD / MULTI-SYMBOL ECONOMIC VALUE` condition in Section 7.

### `SUPPORTS BUT CONCENTRATED`

Requires the same valid-engineering, pooled economic, attribution, safety, and `C_S5` requirements as broad support, but the Section 7 result is `CONCENTRATED ECONOMIC VALUE`. It does not authorize or imply universal five-symbol suitability, and the report must name the concentration source and unfavorable/insufficient symbols.

### `MIXED`

Applies when evidence is valid but primary comparisons conflict, the pooled P1-minus-G1 point estimate is favorable while its interval includes zero, P1-versus-G1 and P1-versus-P0 disagree, supported symbol evidence materially conflicts without meeting a counts-against rule, cost sensitivity is unstable, or safety is unavailable. `MIXED` does not advance to T3.

### `COUNTS AGAINST`

Applies when the pooled P1-minus-G1 or P1-minus-P0 95% paired interval is entirely below zero, an overall unacceptable safety breach occurs, or the primary net benefit fails transaction-cost survival under the contract's required cost rule. Improved gross return, win rate, capture, or surrender cannot override this result.

### `INSUFFICIENT EVIDENCE`

Applies when provenance, coverage, paired support, primary bootstrap, required safety statistics, reproducibility, or another engineering validity requirement prevents the primary pooled decision. It is not an economic failure.

A favorable pooled result alone cannot produce `SUPPORTS BROAD ECONOMIC EXIT VALUE`. Only the first two labels satisfy the economic evidence gate for possible T3 consideration; only the broad label supports a broad-universe interpretation. Neither authorizes deployment.

## 11. Frozen handling of prediction coverage

Before historical replay, accepted frozen predictions must cover every causally eligible policy snapshot required by the common-policy evaluation. A missing prediction cannot be imputed, regenerated, recalibrated, or treated as an outcome-dependent no-action state. Any unexplained missing eligible prediction blocks replay as a provenance failure. Structurally documented absence that was already part of the accepted frozen prediction schema must be reported and must have one deterministic handling rule recorded in the accepted upstream manifest; if no such accepted rule exists, replay remains blocked pending a non-economic provenance amendment.

This is an input-validity gate, not a classification choice that may be resolved after economic outcomes are seen.

## 12. Readiness effect

This addendum resolves the concentration criterion, 50-trade symbol-support threshold, symbol direction and statistical-strength rules, symbol suitability rules, winner/downside safety decision rule, absence of a numeric return hurdle, low-support bootstrap treatment, overall classification mapping, and Q75/Q90 governance.

No economic classification rule remains open to post-replay discretion. Once the revised main contract and this addendum are reviewed and hashed, C5 is **EXECUTION READY FOR T1 ONLY** under separate authorization. Historical economic replay T2 remains prohibited until T1 acceptance and successful reconciliation of authoritative upstream hashes and complete frozen prediction coverage. “Execution ready” does not itself authorize either stage.

## 13. Anti-amendment rule

None of the thresholds, directions, categories, denominators, or Q75/Q90 roles in this addendum may change after any C5 economic output is observed. A future change requires a new experiment version and governance that does not reuse the same development outcomes for both selection and confirmation.
