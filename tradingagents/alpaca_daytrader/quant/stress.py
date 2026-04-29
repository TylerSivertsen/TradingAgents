"""Portfolio-level stress tests before execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from tradingagents.alpaca_daytrader.quant.schemas import CovarianceEstimate, FeasibleBook, MarketState, QuantConfig


@dataclass
class StressScenarioResult:
    name: str
    estimated_loss_pct: float
    passed: bool


@dataclass
class StressTestResult:
    scenarios: list[StressScenarioResult]
    passed: bool
    recommended_gross_scale: float
    warnings: list[str] = field(default_factory=list)


class StressTester:
    def run(
        self,
        feasible_book: FeasibleBook,
        covariance: CovarianceEstimate,
        market_state: MarketState,
        config: QuantConfig,
    ) -> StressTestResult:
        gross = sum(abs(v) for v in feasible_book.target_weights.values())
        largest = max([abs(v) for v in feasible_book.target_weights.values()] or [0.0])
        scenarios = [
            StressScenarioResult("SPY -1%", gross * 0.01, gross * 0.01 <= config.max_daily_loss_pct),
            StressScenarioResult("SPY -2%", gross * 0.02, gross * 0.02 <= config.max_daily_loss_pct),
            StressScenarioResult("largest position -5%", largest * 0.05, largest * 0.05 <= config.max_daily_loss_pct),
            StressScenarioResult("spread doubles", gross * 0.002, True),
            StressScenarioResult("liquidity halves", gross * 0.003, True),
        ]
        passed = all(item.passed for item in scenarios)
        return StressTestResult(scenarios, passed, 0.5 if not passed else 1.0, [] if passed else ["stress limit exceeded"])
