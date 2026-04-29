"""Forecast-utility allocator for orthogonalized strategy books."""

from __future__ import annotations

from tradingagents.alpaca_daytrader.quant.costs import CostModel
from tradingagents.alpaca_daytrader.quant.schemas import (
    AllocationResult,
    MarketState,
    OrthogonalizedBookSet,
    PortfolioState,
    QuantConfig,
    SleeveUtility,
)
from tradingagents.alpaca_daytrader.quant.regime import MarketRegime


class QuantAllocator:
    """Allocates sleeve budgets based on edge, uncertainty, costs, turnover, and risk."""

    def allocate(
        self,
        orthogonalized_books: OrthogonalizedBookSet,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        cost_model: CostModel,
        config: QuantConfig,
        regime: MarketRegime | None = None,
    ) -> AllocationResult:
        utilities: list[SleeveUtility] = []
        positive_total = 0.0
        for book in orthogonalized_books.books:
            cost = 0.25 * cost_model.estimate_book_cost(
                book.target_weights,
                market_state,
                portfolio_state.portfolio_value,
                config,
            )
            regime_multiplier = 1.0
            if regime is not None:
                regime_multiplier = regime.recommended_sleeve_multipliers.get(book.strategy_name, 1.0)
            edge = book.expected_return * book.confidence * regime_multiplier
            uncertainty_penalty = 0.01 * max(book.uncertainty, 0.0)
            turnover_penalty = 0.0001 * max(book.turnover_estimate, 0.0)
            risk_penalty = 0.0001 * sum(abs(value) for value in book.target_weights.values())
            net = edge - uncertainty_penalty - cost - turnover_penalty - risk_penalty
            active = book.active and net > 0 and book.strategy_name != "cash"
            if active:
                positive_total += net
            utilities.append(
                SleeveUtility(
                    strategy_name=book.strategy_name,
                    edge=edge,
                    uncertainty_penalty=uncertainty_penalty,
                    cost_penalty=cost,
                    turnover_penalty=turnover_penalty,
                    risk_penalty=risk_penalty,
                    net_utility=net,
                    budget=0.0,
                    active=active,
                )
            )
        sleeve_budgets: dict[str, float] = {}
        investable = max(0.0, 1.0 - config.min_cash_weight)
        for utility in utilities:
            if positive_total > 0 and utility.active:
                utility.budget = min(config.max_sleeve_weight, investable * utility.net_utility / positive_total)
            else:
                utility.budget = 0.0
            sleeve_budgets[utility.strategy_name] = utility.budget
        used_budget = sum(sleeve_budgets.values())
        cash_weight = max(config.min_cash_weight, 1.0 - used_budget)
        combined = {symbol: 0.0 for symbol in orthogonalized_books.symbols}
        utility_by_name = {utility.strategy_name: utility for utility in utilities}
        for book in orthogonalized_books.books:
            budget = utility_by_name[book.strategy_name].budget
            for symbol, weight in book.target_weights.items():
                combined[symbol] = combined.get(symbol, 0.0) + budget * weight
        return AllocationResult(
            sleeve_utilities=utilities,
            sleeve_budgets=sleeve_budgets,
            cash_weight=cash_weight,
            total_risk_scalar=sum(abs(value) for value in combined.values()),
            combined_target_weights=combined,
            diagnostics={
                "active_sleeves": [u.strategy_name for u in utilities if u.active],
                "inactive_sleeves": [u.strategy_name for u in utilities if not u.active],
                "regime": regime.label if regime else None,
            },
        )
