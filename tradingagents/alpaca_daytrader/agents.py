"""Specialized agents used by the Alpaca daytrader orchestrator."""

from __future__ import annotations

from statistics import mean

from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.models import (
    MarketSnapshot,
    OrderResult,
    PortfolioSnapshot,
    TechnicalSnapshot,
    TradeDecision,
)


class PortfolioStateAgent:
    def analyze(self, adapter: object) -> PortfolioSnapshot:
        return adapter.get_portfolio()


class MarketDataAgent:
    def analyze(self, adapter: object, symbols: list[str]) -> MarketSnapshot:
        return adapter.get_market_snapshot(symbols)


class TechnicalAnalysisAgent:
    def __init__(self, fast_window: int, slow_window: int) -> None:
        self.fast_window = fast_window
        self.slow_window = slow_window

    def analyze(self, market: MarketSnapshot) -> dict[str, TechnicalSnapshot]:
        output: dict[str, TechnicalSnapshot] = {}
        for symbol, bars in market.bars.items():
            closes = [bar.close for bar in bars]
            if len(closes) < self.slow_window:
                output[symbol] = TechnicalSnapshot(
                    symbol=symbol,
                    close=closes[-1] if closes else None,
                    fast_sma=None,
                    slow_sma=None,
                    momentum=None,
                    status="missing_data",
                )
                continue
            fast = mean(closes[-self.fast_window :])
            slow = mean(closes[-self.slow_window :])
            output[symbol] = TechnicalSnapshot(
                symbol=symbol,
                close=closes[-1],
                fast_sma=fast,
                slow_sma=slow,
                momentum=closes[-1] - closes[-2],
                status="ok",
            )
        return output


class SentimentAgent:
    def analyze(self, symbols: list[str]) -> dict[str, float]:
        return {symbol: 0.0 for symbol in symbols}


class StrategyAgent:
    def propose(
        self,
        portfolio: PortfolioSnapshot,
        technicals: dict[str, TechnicalSnapshot],
        sentiment: dict[str, float],
        config: DayTraderConfig,
    ) -> list[TradeDecision]:
        decisions: list[TradeDecision] = []
        for symbol, tech in technicals.items():
            if tech.status != "ok" or tech.close is None or tech.fast_sma is None or tech.slow_sma is None:
                decisions.append(TradeDecision(symbol=symbol, action="hold", reason="missing technical data"))
                continue
            qty = max(1, int(config.max_notional_per_order // tech.close))
            notional = qty * tech.close
            held_qty = portfolio.positions.get(symbol, 0.0)
            if tech.fast_sma > tech.slow_sma and tech.momentum and tech.momentum > 0 and sentiment[symbol] >= -0.25:
                action = "buy"
                reason = "positive intraday trend and neutral sentiment"
            elif tech.fast_sma < tech.slow_sma and held_qty > 0:
                action = "sell"
                qty = int(min(qty, held_qty))
                notional = qty * tech.close
                reason = "trend weakening against held position"
            else:
                action = "hold"
                qty = 0
                notional = 0.0
                reason = "no actionable signal"
            decisions.append(
                TradeDecision(
                    symbol=symbol,
                    action=action,
                    qty=qty,
                    notional=notional,
                    reason=reason,
                )
            )
        return decisions


class RiskManagerAgent:
    def review(
        self,
        decisions: list[TradeDecision],
        portfolio: PortfolioSnapshot,
        market: MarketSnapshot,
        technicals: dict[str, TechnicalSnapshot],
        config: DayTraderConfig,
        dry_run: bool,
    ) -> list[TradeDecision]:
        max_exposure = portfolio.portfolio_value * config.max_portfolio_exposure_pct
        min_cash = portfolio.portfolio_value * config.min_cash_reserve_pct
        reviewed: list[TradeDecision] = []
        for decision in decisions:
            decision.dry_run = dry_run
            if decision.action == "hold":
                decision.approved = False
                reviewed.append(decision)
                continue
            if not market.market_open:
                decision.rejections.append("market closed")
            if technicals[decision.symbol].status != "ok":
                decision.rejections.append("missing data")
            if decision.notional > config.max_notional_per_order:
                decision.rejections.append("order notional exceeds limit")
            if decision.notional > max_exposure:
                decision.rejections.append("portfolio exposure limit exceeded")
            if decision.action == "buy" and portfolio.cash - decision.notional < min_cash:
                decision.rejections.append("insufficient funds after cash reserve")
            if decision.action == "sell" and portfolio.positions.get(decision.symbol, 0.0) < decision.qty:
                decision.rejections.append("insufficient position")
            decision.approved = not decision.rejections
            reviewed.append(decision)
        return reviewed


class ExecutionAgent:
    def execute(self, adapter: object, decisions: list[TradeDecision], dry_run: bool) -> list[OrderResult]:
        orders: list[OrderResult] = []
        for decision in decisions:
            if not decision.approved:
                orders.append(
                    OrderResult(
                        symbol=decision.symbol,
                        action=decision.action,
                        submitted=False,
                        dry_run=dry_run,
                        message="; ".join(decision.rejections) or "no approved trade",
                    )
                )
                continue
            if dry_run:
                orders.append(
                    OrderResult(
                        symbol=decision.symbol,
                        action=decision.action,
                        submitted=False,
                        dry_run=True,
                        message=f"dry-run order skipped for {decision.qty} shares",
                    )
                )
                continue
            order = adapter.submit_order(decision.symbol, decision.action, decision.qty)
            order_id = getattr(order, "id", None)
            if order_id is None and isinstance(order, dict):
                order_id = order.get("id")
            orders.append(
                OrderResult(
                    symbol=decision.symbol,
                    action=decision.action,
                    submitted=True,
                    dry_run=False,
                    message="submitted",
                    order_id=str(order_id) if order_id is not None else None,
                )
            )
        return orders


class ReflectionAgent:
    def reflect(self, decisions: list[TradeDecision], orders: list[OrderResult]) -> str:
        approved = sum(1 for decision in decisions if decision.approved)
        submitted = sum(1 for order in orders if order.submitted)
        rejected = sum(1 for decision in decisions if decision.rejections)
        return (
            f"Reviewed {len(decisions)} symbols; approved {approved}, "
            f"submitted {submitted}, rejected {rejected}. Research only; not financial advice."
        )
