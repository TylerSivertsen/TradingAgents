"""Orchestrator loop for Alpaca paper-trading research."""

from __future__ import annotations

import time
from pathlib import Path

from tradingagents.alpaca_daytrader.agents import (
    ExecutionAgent,
    MarketDataAgent,
    PortfolioStateAgent,
    ReflectionAgent,
    RiskManagerAgent,
    SentimentAgent,
    StrategyAgent,
    TechnicalAnalysisAgent,
)
from tradingagents.alpaca_daytrader.alpaca_adapter import AlpacaAdapter, DryRunAdapter
from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.logging import DecisionLogger
from tradingagents.alpaca_daytrader.models import OrchestratorResult


class DayTraderOrchestrator:
    def __init__(
        self,
        config: DayTraderConfig,
        adapter: object | None = None,
        logger: DecisionLogger | None = None,
    ) -> None:
        self.config = config
        self.adapter = adapter
        self.logger = logger or DecisionLogger(config.log_root, config.report_root)
        self.portfolio_agent = PortfolioStateAgent()
        self.market_agent = MarketDataAgent()
        self.technical_agent = TechnicalAnalysisAgent(config.fast_window, config.slow_window)
        self.sentiment_agent = SentimentAgent()
        self.strategy_agent = StrategyAgent()
        self.risk_agent = RiskManagerAgent()
        self.execution_agent = ExecutionAgent()
        self.reflection_agent = ReflectionAgent()

    def once(self, dry_run: bool = True) -> OrchestratorResult:
        if not dry_run:
            self.config.validate_for_execution()
        adapter = self._adapter(dry_run)
        portfolio = self.portfolio_agent.analyze(adapter)
        market = self.market_agent.analyze(adapter, self.config.symbols)
        technicals = self.technical_agent.analyze(market)
        sentiment = self.sentiment_agent.analyze(self.config.symbols)
        decisions = self.strategy_agent.propose(portfolio, technicals, sentiment, self.config)
        decisions = self.risk_agent.review(
            decisions,
            portfolio,
            market,
            technicals,
            self.config,
            dry_run=dry_run,
        )
        orders = self.execution_agent.execute(adapter, decisions, dry_run=dry_run)
        reflection = self.reflection_agent.reflect(decisions, orders)
        result = OrchestratorResult(
            portfolio=portfolio,
            market=market,
            technicals=technicals,
            decisions=decisions,
            orders=orders,
            reflection=reflection,
        )
        self.logger.log_portfolio(portfolio)
        self.logger.log_decisions(decisions)
        self.logger.log_orders(orders)
        self.logger.write_report(result)
        return result

    def run(self, dry_run: bool = True, iterations: int | None = None) -> None:
        count = 0
        while iterations is None or count < iterations:
            self.once(dry_run=dry_run)
            count += 1
            if iterations is not None and count >= iterations:
                break
            time.sleep(self.config.poll_seconds)

    def report(self) -> Path | None:
        return self.logger.latest_report()

    def _adapter(self, dry_run: bool) -> object:
        if self.adapter is not None:
            return self.adapter
        if dry_run:
            return DryRunAdapter()
        return AlpacaAdapter(self.config)
