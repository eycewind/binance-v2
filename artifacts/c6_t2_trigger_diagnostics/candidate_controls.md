# Candidate C6 controls (definitions only)

These controls are proposed for later preregistration; none was run or evaluated economically here.

- `EXIT_FIRST_T2`: decide at the first frozen T2-eligible completed 5-minute snapshot and execute with the existing next-1-minute-open semantics. This directly isolates entry into the T2 risk set from model timing.
- `EXIT_SECOND_T2`: decide at the second available frozen T2-eligible snapshot. Specify *available*, rather than consecutive wall-clock bars, unless a later contract explicitly requires continuous eligibility.
- `FIXED_DELAY_T2`: choose one predeclared ordinal delay using scientific design criteria fixed before economics; do not select the delay from returns.
- `RANDOM_CONTROL`: on each eligible snapshot, apply a preregistered deterministic RNG stream, fixed seed, stable trade/row ordering, and an explicitly frozen stopping rule.
- `BASE_RATE_RANDOM_CONTROL`: freeze the probability from development-era trigger-timing frequencies only, with no economic-outcome input, and apply the same deterministic RNG requirements.

The first and second controls are especially interpretable when immediate triggering dominates. Fixed-delay and random controls can distinguish deterministic risk-set entry from exposure-duration and generic stopping effects. No candidate is selected here.
