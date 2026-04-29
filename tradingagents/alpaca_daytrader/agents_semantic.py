"""Structured semantic review gate for quant outputs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SemanticReview:
    passed: bool
    confidence: float
    veto: bool
    warnings: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    explanation: str = ""
    required_actions: list[str] = field(default_factory=list)


class SemanticReviewGate:
    """Deterministic fallback for semantic review.

    LLM agents can replace or augment this later, but the gate itself stays
    structured and conservative.
    """

    def review(self, report: object) -> SemanticReview:
        warnings = []
        contradictions = []
        no_trade = getattr(report, "no_trade", None)
        risk = getattr(report, "risk", None)
        if no_trade is not None and getattr(no_trade, "no_trade", False):
            warnings.extend(getattr(no_trade, "reasons", []))
        if risk is not None and getattr(risk, "reason_codes", []):
            warnings.extend(getattr(risk, "reason_codes", []))
        veto = any(code in warnings for code in ("MARKET_CLOSED", "DAILY_LOSS", "DRAWDOWN"))
        return SemanticReview(
            passed=not veto,
            confidence=0.8 if not veto else 0.2,
            veto=veto,
            warnings=warnings,
            contradictions=contradictions,
            explanation="Structured semantic gate passed." if not veto else "Structured semantic gate vetoed unsafe execution.",
            required_actions=["review risk report"] if veto else [],
        )
