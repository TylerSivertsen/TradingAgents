"""End-to-end ORIA-inspired quant orchestration."""

from __future__ import annotations

import time
from dataclasses import asdict
from dataclasses import replace
from typing import Any

from tradingagents.alpaca_daytrader.alpaca_adapter import AlpacaAdapter, DryRunAdapter
from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.models import MarketSnapshot, PortfolioSnapshot
from tradingagents.alpaca_daytrader.quant.allocator import QuantAllocator
from tradingagents.alpaca_daytrader.quant.config import load_quant_config
from tradingagents.alpaca_daytrader.quant.constraints import OrthogonalizationConstraints
from tradingagents.alpaca_daytrader.quant.costs import CostModel
from tradingagents.alpaca_daytrader.quant.covariance import CovarianceEstimator
from tradingagents.alpaca_daytrader.quant.execution_governor import ExecutionGovernor
from tradingagents.alpaca_daytrader.quant.factors import FactorExposureModel
from tradingagents.alpaca_daytrader.quant.meta_allocator import MetaAllocator
from tradingagents.alpaca_daytrader.quant.no_trade_reasoner import NoTradeReasoner
from tradingagents.alpaca_daytrader.quant.orthogonalization import Orthogonalizer
from tradingagents.alpaca_daytrader.quant.reporting import QuantLogger
from tradingagents.alpaca_daytrader.quant.regime import MarketRegimeClassifier
from tradingagents.alpaca_daytrader.quant.risk_box import RiskBox
from tradingagents.alpaca_daytrader.quant.schemas import (
    ExecutionPlan,
    ExecutionResult,
    MarketState,
    PortfolioState,
    QuantConfig,
    QuantRunReport,
)
from tradingagents.alpaca_daytrader.quant.semantic_review import QuantOrchestrationAgent
from tradingagents.alpaca_daytrader.quant.scoreboard import StrategyScoreboard
from tradingagents.alpaca_daytrader.quant.stress import StressTester
from tradingagents.alpaca_daytrader.quant.strategy_sleeves import StrategySleeve, default_sleeves
from tradingagents.alpaca_daytrader.universe.discovery import UniverseDiscoveryEngine
from tradingagents.alpaca_daytrader.universe.filters import FocusListManager, MarketScanner
from tradingagents.alpaca_daytrader.universe.reporting import UniverseReporter
from tradingagents.alpaca_daytrader.universe.schemas import UniverseConfig
from tradingagents.alpaca_daytrader.explainability.trade_explainer import TradeExplainer


class QuantOrchestrator:
    """Coordinates strategy sleeves, ORIA risk deduplication, allocation, and execution."""

    def __init__(
        self,
        daytrader_config: DayTraderConfig,
        quant_config: QuantConfig | None = None,
        adapter: object | None = None,
        sleeves: list[StrategySleeve] | None = None,
        logger: QuantLogger | None = None,
        universe_config: UniverseConfig | None = None,
    ) -> None:
        self.daytrader_config = daytrader_config
        self.quant_config = quant_config or load_quant_config(daytrader_config)
        self.adapter = adapter
        self.sleeves = sleeves or default_sleeves(self.quant_config)
        self.logger = logger or QuantLogger(daytrader_config.log_root, daytrader_config.report_root)
        self.factor_model = FactorExposureModel()
        self.covariance_estimator = CovarianceEstimator()
        self.orthogonalizer = Orthogonalizer()
        self.allocator = QuantAllocator()
        self.cost_model = CostModel()
        self.risk_box = RiskBox()
        self.execution_governor = ExecutionGovernor()
        self.semantic_agent = QuantOrchestrationAgent()
        self.universe_config = universe_config or UniverseConfig(seed_symbols=self.quant_config.symbols)
        self.universe_discovery = UniverseDiscoveryEngine()
        self.market_scanner = MarketScanner()
        self.focus_manager = FocusListManager()
        self.universe_reporter = UniverseReporter(daytrader_config.report_root)
        self.regime_classifier = MarketRegimeClassifier()
        self.meta_allocator = MetaAllocator()
        self.stress_tester = StressTester()
        self.no_trade_reasoner = NoTradeReasoner()
        self.trade_explainer = TradeExplainer()
        self.scoreboard = StrategyScoreboard()

    def once(self, dry_run: bool = True, shadow: bool = False) -> QuantRunReport:
        adapter = self._adapter(dry_run)
        self._validate_execution(dry_run)
        portfolio = self._portfolio_state(adapter.get_portfolio())
        selection = self.universe_discovery.discover(adapter, adapter, self.universe_config)
        scan = self.market_scanner.scan(selection.universe, adapter, self.universe_config)
        focus = self.focus_manager.build_focus_list(scan, portfolio, self.universe_config)
        focus_symbols = focus.symbols or self.universe_config.seed_symbols or self.quant_config.symbols
        market = self._market_state(adapter.get_market_snapshot(focus_symbols))
        run_config = replace(self.quant_config, symbols=focus_symbols)
        regime = self.regime_classifier.classify(market, market, portfolio, run_config)
        run_config = self.meta_allocator.adjust_config(run_config, regime, portfolio.drawdown_pct)
        raw_books = [
            sleeve.generate_raw_book(market, portfolio, run_config)
            for sleeve in self.sleeves
        ]
        factor_exposure = self.factor_model.compute(market, run_config.symbols, run_config)
        covariance = self.covariance_estimator.estimate(
            market,
            run_config.symbols,
            run_config.covariance_lookback_bars,
        )
        orthogonalized = self.orthogonalizer.orthogonalize(
            raw_books,
            self.factor_model,
            covariance,
            OrthogonalizationConstraints(
                enforce_market_neutral=run_config.enforce_market_neutral,
                neutralize_factors=["market"] if run_config.enforce_market_neutral else [],
            ),
        )
        allocation = self.allocator.allocate(
            orthogonalized,
            market,
            portfolio,
            self.cost_model,
            run_config,
            regime,
            {sleeve.name: self.scoreboard.reliability_multiplier(sleeve.name) for sleeve in self.sleeves},
        )
        risk = self.risk_box.apply(allocation, market, portfolio, run_config)
        stress = self.stress_tester.run(risk.feasible_book, covariance, market, run_config)
        if not stress.passed and risk.feasible_book.target_weights:
            scaled = {
                symbol: weight * stress.recommended_gross_scale
                for symbol, weight in risk.feasible_book.target_weights.items()
            }
            risk.feasible_book.target_weights = scaled
            risk.gross_exposure = sum(abs(value) for value in scaled.values())
            risk.reason_codes.append("STRESS_SCALE")
        execution_plan = self.execution_governor.generate_orders(
            risk.feasible_book,
            portfolio,
            market,
            run_config,
            dry_run=dry_run or shadow,
        )
        no_trade = self.no_trade_reasoner.explain(allocation, risk, execution_plan, focus_empty=not focus.symbols)
        execution_result = self._execute(adapter, execution_plan, dry_run or shadow)
        explanations = [
            self.trade_explainer.explain(order, allocation, risk, regime)
            for order in execution_plan.orders
        ]
        semantic_commentary = self.semantic_agent.review(
            raw_books,
            orthogonalized,
            allocation,
            risk,
            execution_plan,
        )
        report = QuantRunReport(
            market_state=market,
            portfolio_state=portfolio,
            raw_books=raw_books,
            orthogonalized=orthogonalized,
            allocation=allocation,
            risk=risk,
            execution_plan=execution_plan,
            execution_result=execution_result,
            semantic_commentary=semantic_commentary,
            universe_selection=selection,
            scan_result=scan,
            focus_list=focus,
            market_regime=regime,
            stress_result=stress,
            no_trade=no_trade,
            trade_explanations=explanations,
        )
        self._log(report, factor_exposure, covariance)
        self.universe_reporter.write(selection, scan, focus)
        return report

    def run(self, dry_run: bool = True, iterations: int | None = None, shadow: bool = False) -> None:
        count = 0
        while iterations is None or count < iterations:
            report = self.once(dry_run=dry_run, shadow=shadow)
            count += 1
            if report.risk.reason_codes and "DAILY_LOSS" in report.risk.reason_codes:
                break
            if iterations is not None and count >= iterations:
                break
            time.sleep(self.daytrader_config.poll_seconds)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "enabled": self.quant_config.enabled,
            "symbols": self.quant_config.symbols,
            "dynamic_universe": True,
            "max_scan_symbols": self.universe_config.max_scan_symbols,
            "max_focus_symbols": self.universe_config.max_focus_symbols,
            "sleeves": [sleeve.name for sleeve in self.sleeves],
            "paper": self.daytrader_config.paper,
            "dry_run_default": self.quant_config.dry_run_default,
            "factor_model": "market/momentum/volatility/liquidity fallback",
            "covariance": "ewm with shrinkage and diagonal fallback",
        }

    def latest_report(self) -> str | None:
        report = self.logger.latest_report()
        return str(report) if report else None

    def _adapter(self, dry_run: bool) -> object:
        if self.adapter is not None:
            return self.adapter
        if dry_run:
            return DryRunAdapter()
        return AlpacaAdapter(self.daytrader_config)

    def _validate_execution(self, dry_run: bool) -> None:
        if dry_run:
            return
        if not self.daytrader_config.paper and not self.quant_config.allow_live_trading:
            raise ValueError("Live trading refused unless ALLOW_LIVE_TRADING=true.")
        self.daytrader_config.validate_for_execution()

    def _portfolio_state(self, snapshot: PortfolioSnapshot) -> PortfolioState:
        return PortfolioState(
            cash=snapshot.cash,
            portfolio_value=snapshot.portfolio_value,
            positions=snapshot.positions,
            buying_power=snapshot.buying_power,
        )

    def _market_state(self, snapshot: MarketSnapshot) -> MarketState:
        spreads = {symbol: 5.0 for symbol in snapshot.bars}
        liquidity = {}
        for symbol, bars in snapshot.bars.items():
            if bars:
                avg_volume = sum(bar.volume for bar in bars[-20:]) / min(len(bars), 20)
                liquidity[symbol] = avg_volume * bars[-1].close
            else:
                liquidity[symbol] = 0.0
        return MarketState(
            bars=snapshot.bars,
            market_open=snapshot.market_open,
            spreads_bps=spreads,
            liquidity=liquidity,
            timestamp=snapshot.timestamp,
        )

    def _execute(self, adapter: object, plan: ExecutionPlan, dry_run: bool) -> ExecutionResult:
        if dry_run:
            return ExecutionResult(plan=plan, submitted_order_ids=[], messages=["dry-run: no orders submitted"])
        ids: list[str] = []
        messages: list[str] = []
        for order in plan.orders:
            response = adapter.submit_order(order.symbol, order.side, order.quantity)
            order_id = getattr(response, "id", None)
            if order_id is None and isinstance(response, dict):
                order_id = response.get("id")
            if order_id is not None:
                ids.append(str(order_id))
            messages.append(f"submitted {order.side} {order.quantity} {order.symbol}")
        return ExecutionResult(plan=plan, submitted_order_ids=ids, messages=messages)

    def _log(self, report: QuantRunReport, factor_exposure: object, covariance: object) -> None:
        self.logger.log_stage("raw_books", report.raw_books)
        self.logger.log_stage("orthogonalization", report.orthogonalized)
        self.logger.log_stage("allocation", report.allocation)
        self.logger.log_stage("risk", report.risk)
        self.logger.log_stage("execution", report.execution_result)
        self.logger.log_stage("execution", {"no_trade": asdict(report.no_trade) if report.no_trade else None})
        self.logger.log_stage("orthogonalization", {"factor_exposure": asdict(factor_exposure), "covariance": asdict(covariance)})
        self.logger.write_report(report)
