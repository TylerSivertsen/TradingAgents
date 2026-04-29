# Quant Pipeline Audit

## Findings

- The ORIA chain is connected: sleeves -> covariance/factors -> orthogonalizer -> allocator -> RiskBox -> stress -> execution governor.
- Universe discovery now feeds a focus list into the quant orchestrator.
- Empty focus lists degrade to no-trade behavior in tests.
- Covariance has diagonal fallback for insufficient/singular data.
- Orthogonalization handles degenerate books and marks them inactive.
- Allocator can allocate to cash when no utility is positive.
- RiskBox enforces market hours, loss/drawdown, position/gross/net caps, spread/liquidity, no-trade symbols.
- ExecutionGovernor stages orders from feasible RiskBox output.

## Limitations

- Stress tests currently append `STRESS_SCALE` but do not fully recompute all RiskBox metrics after scaling.
- Alpha decay fields exist on `RawDesiredBook`, but valid-until enforcement is a placeholder.
- Scoreboard/calibration are present but minimally integrated.

## Repair Direction

- Add canonical run result and no-trade as first-class success.
- Add semantic veto gate before final execution.
- Add coherent run report JSON/Markdown output.
