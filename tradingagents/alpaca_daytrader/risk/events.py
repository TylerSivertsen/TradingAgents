"""Event-risk decisions for symbol-level risk controls."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EventRiskDecision:
    symbol: str
    allow_trade: bool = True
    reduce_size: bool = False
    cash_preferred: bool = False
    no_new_positions: bool = False
    close_or_trim_only: bool = False
    reasons: list[str] = field(default_factory=list)


class EventRiskFilter:
    def evaluate(self, symbol: str, diagnostics: dict | None = None) -> EventRiskDecision:
        diagnostics = diagnostics or {}
        reasons: list[str] = []
        if diagnostics.get("halted"):
            reasons.append("recent_halt")
        if abs(float(diagnostics.get("overnight_gap", 0.0))) > 0.10:
            reasons.append("large_overnight_gap")
        if diagnostics.get("earnings_today"):
            reasons.append("earnings_today")
        return EventRiskDecision(
            symbol=symbol,
            allow_trade=not reasons,
            reduce_size=bool(reasons),
            cash_preferred=bool(reasons),
            no_new_positions=bool(reasons),
            close_or_trim_only=bool(reasons),
            reasons=reasons,
        )
