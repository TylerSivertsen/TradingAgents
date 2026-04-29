"""Hard risk constraint enforcement for allocated quant books."""

from __future__ import annotations

from tradingagents.alpaca_daytrader.quant.schemas import (
    AllocationResult,
    FeasibleBook,
    MarketState,
    PortfolioState,
    QuantConfig,
    RiskBoxResult,
    RiskConstraintViolation,
)


class RiskBox:
    """Converts an allocated desired book into an inspectable feasible book."""

    def apply(
        self,
        allocation: AllocationResult,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> RiskBoxResult:
        violations: list[RiskConstraintViolation] = []
        clipped: dict[str, tuple[float, float]] = {}
        weights = dict(allocation.combined_target_weights)
        if not market_state.market_open:
            violations.append(RiskConstraintViolation("MARKET_CLOSED", None, "market is closed"))
            weights = {symbol: 0.0 for symbol in weights}
        if portfolio_state.daily_pnl < -config.max_daily_loss_pct * portfolio_state.portfolio_value:
            violations.append(RiskConstraintViolation("DAILY_LOSS", None, "daily loss limit breached"))
            weights = {symbol: 0.0 for symbol in weights}
        if portfolio_state.drawdown_pct > config.max_drawdown_pct:
            violations.append(RiskConstraintViolation("DRAWDOWN", None, "drawdown limit breached"))
            weights = {symbol: 0.0 for symbol in weights}
        for symbol in list(weights):
            before = weights[symbol]
            if symbol in config.no_trade_symbols:
                weights[symbol] = 0.0
                violations.append(RiskConstraintViolation("NO_TRADE", symbol, "symbol blocked", before, 0.0))
            spread = market_state.spreads_bps.get(symbol, 0.0)
            if spread > config.execution.max_spread_bps:
                weights[symbol] = 0.0
                violations.append(RiskConstraintViolation("SPREAD", symbol, "spread too wide", before, 0.0))
            liquidity = market_state.liquidity.get(symbol, 1.0)
            latest_price = market_state.latest_price(symbol) or 0.0
            if liquidity <= 0 or latest_price <= 0:
                weights[symbol] = 0.0
                violations.append(RiskConstraintViolation("LIQUIDITY", symbol, "missing liquidity or price", before, 0.0))
            if abs(weights[symbol]) > config.max_position_weight:
                after = config.max_position_weight if weights[symbol] > 0 else -config.max_position_weight
                weights[symbol] = after
                clipped[symbol] = (before, after)
                violations.append(RiskConstraintViolation("POSITION_SIZE", symbol, "position clipped", before, after))
        gross = sum(abs(value) for value in weights.values())
        if gross > config.max_gross_exposure and gross > 0:
            scale = config.max_gross_exposure / gross
            for symbol, before in list(weights.items()):
                weights[symbol] = before * scale
                clipped[symbol] = (before, weights[symbol])
            violations.append(RiskConstraintViolation("GROSS_EXPOSURE", None, "gross exposure scaled", gross, config.max_gross_exposure))
        net = sum(weights.values())
        if abs(net) > config.max_net_exposure and abs(net) > 0:
            scale = config.max_net_exposure / abs(net)
            for symbol, before in list(weights.items()):
                weights[symbol] = before * scale
                clipped[symbol] = (before, weights[symbol])
            violations.append(RiskConstraintViolation("NET_EXPOSURE", None, "net exposure scaled", net, config.max_net_exposure))
        gross = sum(abs(value) for value in weights.values())
        net = sum(weights.values())
        concentration = {symbol: abs(value) / gross for symbol, value in weights.items()} if gross > 0 else {}
        feasible = FeasibleBook(
            target_weights=weights,
            source_weights=allocation.combined_target_weights,
            approved=not any(v.code in {"MARKET_CLOSED", "DAILY_LOSS", "DRAWDOWN"} for v in violations),
            source_sleeves=[name for name, budget in allocation.sleeve_budgets.items() if budget > 0],
        )
        return RiskBoxResult(
            feasible_book=feasible,
            violations=violations,
            clipped_weights=clipped,
            risk_scalar=gross,
            volatility_estimate=min(config.target_volatility, gross * config.target_volatility),
            gross_exposure=gross,
            net_exposure=net,
            concentration=concentration,
            reason_codes=[violation.code for violation in violations],
        )
