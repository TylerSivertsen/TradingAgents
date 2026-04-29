"""Explains why the safest action is no trade."""

from __future__ import annotations

from dataclasses import dataclass, field

from tradingagents.alpaca_daytrader.quant.schemas import AllocationResult, ExecutionPlan, RiskBoxResult


@dataclass
class NoTradeDecision:
    no_trade: bool
    reasons: list[str] = field(default_factory=list)


class NoTradeReasoner:
    def explain(self, allocation: AllocationResult, risk: RiskBoxResult, execution: ExecutionPlan, focus_empty: bool = False) -> NoTradeDecision:
        reasons: list[str] = []
        if focus_empty:
            reasons.append("universe scan found no valid candidates")
        if not any(utility.active for utility in allocation.sleeve_utilities):
            reasons.append("no positive utility")
        if risk.reason_codes:
            reasons.extend(risk.reason_codes)
        if not execution.orders:
            reasons.append("no executable order above minimum size")
        return NoTradeDecision(bool(reasons and not execution.orders), reasons)
