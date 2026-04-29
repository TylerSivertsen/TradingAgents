"""Structured trade explanations from deterministic pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tradingagents.alpaca_daytrader.quant.regime import MarketRegime
from tradingagents.alpaca_daytrader.quant.schemas import AllocationResult, OrderPlan, RiskBoxResult


@dataclass
class TradeExplanation:
    symbol: str
    action: str
    size_pct: float
    primary_sleeve: str
    supporting_sleeves: list[str]
    opposing_sleeves: list[str]
    regime: str
    expected_edge: str
    main_risk: str
    riskbox_adjustment: str
    execution_choice: str
    invalidation_condition: str
    diagnostics: dict[str, Any] = field(default_factory=dict)


class TradeExplainer:
    def explain(self, order: OrderPlan, allocation: AllocationResult, risk: RiskBoxResult, regime: MarketRegime) -> TradeExplanation:
        utilities = sorted(allocation.sleeve_utilities, key=lambda item: item.budget, reverse=True)
        primary = utilities[0].strategy_name if utilities else "unknown"
        clipped = risk.clipped_weights.get(order.symbol)
        adjustment = f"clipped from {clipped[0]:.2%} to {clipped[1]:.2%}" if clipped else "no clip"
        return TradeExplanation(
            symbol=order.symbol,
            action=order.side,
            size_pct=order.risk_metadata.get("target_weight", 0.0),
            primary_sleeve=primary,
            supporting_sleeves=[u.strategy_name for u in utilities[1:3] if u.budget > 0],
            opposing_sleeves=[u.strategy_name for u in utilities if u.net_utility < 0],
            regime=regime.label,
            expected_edge="positive" if utilities and utilities[0].edge > 0 else "uncertain",
            main_risk="elevated volatility" if regime.volatility_state == "high" else "execution and model risk",
            riskbox_adjustment=adjustment,
            execution_choice=f"{order.order_type} order due to spread/liquidity policy",
            invalidation_condition="signal stale, spread widens, or risk box trips",
        )
