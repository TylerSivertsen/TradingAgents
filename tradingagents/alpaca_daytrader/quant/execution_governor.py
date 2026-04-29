"""Execution planning for feasible ORIA target books."""

from __future__ import annotations

from datetime import datetime, timezone

from tradingagents.alpaca_daytrader.quant.schemas import (
    ExecutionPlan,
    FeasibleBook,
    MarketState,
    OrderPlan,
    PortfolioState,
    QuantConfig,
)


class ExecutionGovernor:
    """Converts feasible target weights into staged Alpaca order plans."""

    def generate_orders(
        self,
        feasible_book: FeasibleBook,
        portfolio_state: PortfolioState,
        market_state: MarketState,
        config: QuantConfig,
        dry_run: bool = True,
    ) -> ExecutionPlan:
        warnings: list[str] = []
        orders: list[OrderPlan] = []
        if not feasible_book.approved:
            return ExecutionPlan([], dry_run=dry_run, warnings=["risk box did not approve execution"])
        if not market_state.market_open:
            return ExecutionPlan([], dry_run=dry_run, warnings=["market closed"])
        for symbol, target_weight in feasible_book.target_weights.items():
            price = market_state.latest_price(symbol)
            if price is None or price <= 0:
                warnings.append(f"{symbol}: missing price")
                continue
            current_qty = portfolio_state.positions.get(symbol, 0.0)
            current_notional = current_qty * price
            target_notional = target_weight * portfolio_state.portfolio_value
            delta = target_notional - current_notional
            if abs(delta) < config.execution.min_order_notional:
                continue
            side = "buy" if delta > 0 else "sell"
            remaining = abs(delta)
            spread = market_state.spreads_bps.get(symbol, config.execution.max_spread_bps)
            order_type = "limit" if config.execution.prefer_limit_orders or spread > config.execution.max_spread_bps / 2 else "market"
            if order_type == "market" and not config.execution.allow_market_orders:
                order_type = "limit"
            while remaining >= config.execution.min_order_notional and len(orders) < config.execution.max_orders_per_cycle:
                chunk = min(remaining, config.execution.max_order_notional)
                quantity = int(chunk // price)
                if quantity <= 0:
                    break
                notional = quantity * price
                limit_price = None
                if order_type == "limit":
                    slip = max(spread, 1.0) / 20_000.0
                    limit_price = price * (1.0 + slip if side == "buy" else 1.0 - slip)
                orders.append(
                    OrderPlan(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        notional=notional,
                        order_type=order_type,
                        time_in_force="day",
                        limit_price=limit_price,
                        stop_loss=price * (1.0 - config.execution.stop_loss_pct) if config.execution.stop_loss_pct and side == "buy" else None,
                        take_profit=price * (1.0 + config.execution.take_profit_pct) if config.execution.take_profit_pct and side == "buy" else None,
                        reason="move current position toward feasible target weight",
                        source_sleeves=feasible_book.source_sleeves,
                        risk_metadata={"target_weight": target_weight, "dry_run": dry_run},
                    )
                )
                remaining -= notional
            if len(orders) >= config.execution.max_orders_per_cycle:
                warnings.append("max orders per cycle reached")
                break
        return ExecutionPlan(orders=orders, dry_run=dry_run, warnings=warnings)

    def reject_stale_orders(self, plan: ExecutionPlan, max_age_minutes: float = 60.0) -> ExecutionPlan:
        # Current order plans are generated immediately after signals; this hook keeps
        # a deterministic place for future valid_until checks.
        _ = datetime.now(timezone.utc)
        return plan
