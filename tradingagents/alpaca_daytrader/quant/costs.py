"""Conservative implementation cost model."""

from __future__ import annotations

from tradingagents.alpaca_daytrader.quant.schemas import MarketState, QuantConfig


class CostModel:
    """Estimates spread, slippage, and simple impact costs in portfolio-weight units."""

    def estimate_symbol_cost(
        self,
        symbol: str,
        order_notional: float,
        market_state: MarketState,
        config: QuantConfig,
    ) -> float:
        spread_bps = market_state.spreads_bps.get(symbol, config.execution.max_spread_bps)
        liquidity = market_state.liquidity.get(symbol, 0.0)
        spread_cost = spread_bps / 10_000.0
        if liquidity <= 0:
            return spread_cost + 0.01
        participation = min(1.0, abs(order_notional) / max(liquidity, 1.0))
        slippage = 0.5 * spread_cost
        impact = max(0.0, participation - config.execution.max_participation_rate) ** 2
        return spread_cost + slippage + impact

    def estimate_book_cost(
        self,
        weights: dict[str, float],
        market_state: MarketState,
        portfolio_value: float,
        config: QuantConfig,
    ) -> float:
        return sum(
            self.estimate_symbol_cost(symbol, weight * portfolio_value, market_state, config)
            * abs(weight)
            for symbol, weight in weights.items()
        )
