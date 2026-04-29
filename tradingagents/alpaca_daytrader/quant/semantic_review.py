"""Structured semantic review placeholders for quant pipeline auditability."""

from __future__ import annotations

from typing import Any

from tradingagents.alpaca_daytrader.quant.schemas import (
    AllocationResult,
    ExecutionPlan,
    OrthogonalizedBookSet,
    RawDesiredBook,
    RiskBoxResult,
)


class QuantOrchestrationAgent:
    """Coordinates deterministic quant outputs into structured review notes."""

    def review(
        self,
        raw_books: list[RawDesiredBook],
        orthogonalized: OrthogonalizedBookSet,
        allocation: AllocationResult,
        risk: RiskBoxResult,
        execution_plan: ExecutionPlan,
    ) -> dict[str, Any]:
        return {
            "quant_research": {
                "raw_books": len(raw_books),
                "active_raw_sleeves": [book.strategy_name for book in raw_books if any(book.target_weights.values())],
                "warnings": [warning for book in raw_books for warning in book.diagnostics.warnings],
            },
            "orthogonalization_review": {
                "inactive_after_orthogonalization": [
                    book.strategy_name for book in orthogonalized.books if not book.active
                ],
                "warnings": orthogonalized.diagnostics.warnings,
                "removed_exposure": orthogonalized.diagnostics.removed_exposure,
            },
            "allocation_review": {
                "cash_weight": allocation.cash_weight,
                "active_sleeves": allocation.diagnostics.get("active_sleeves", []),
                "utilities": {
                    utility.strategy_name: utility.net_utility
                    for utility in allocation.sleeve_utilities
                },
            },
            "risk_review": {
                "approved": risk.feasible_book.approved,
                "reason_codes": risk.reason_codes,
                "gross_exposure": risk.gross_exposure,
                "net_exposure": risk.net_exposure,
            },
            "execution_review": {
                "orders": len(execution_plan.orders),
                "warnings": execution_plan.warnings,
                "dry_run": execution_plan.dry_run,
            },
        }
