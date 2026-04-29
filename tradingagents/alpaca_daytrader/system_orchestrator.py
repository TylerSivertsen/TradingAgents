"""Canonical orchestration path for the integrated Alpaca/ORIA system."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import asdict
from typing import Any

from tradingagents.alpaca_daytrader.agents_semantic import SemanticReviewGate
from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.experiments import ExperimentRegistry
from tradingagents.alpaca_daytrader.quant.backtest import QuantBacktester
from tradingagents.alpaca_daytrader.quant.config import load_quant_config
from tradingagents.alpaca_daytrader.quant.orchestrator import QuantOrchestrator
from tradingagents.alpaca_daytrader.quant.walkforward import WalkForwardValidator
from tradingagents.alpaca_daytrader.reporting.reports import RunReporter, TradingRunResult
from tradingagents.alpaca_daytrader.risk.circuit_breakers import CircuitBreakerManager
from tradingagents.alpaca_daytrader.runtime import RuntimeMode, mode_by_name
from tradingagents.alpaca_daytrader.safety import SafetyPolicy, SystemHealthCheck
from tradingagents.alpaca_daytrader.universe.config import load_universe_config
from tradingagents.alpaca_daytrader.universe.discovery import UniverseDiscoveryEngine
from tradingagents.alpaca_daytrader.universe.filters import FocusListManager, MarketScanner
from tradingagents.alpaca_daytrader.universe.reporting import UniverseReporter
from tradingagents.alpaca_daytrader.alpaca_adapter import DryRunAdapter


class TradingSystemOrchestrator:
    """Single command-facing orchestrator for diagnostics, runs, and safety actions."""

    def __init__(self, config: DayTraderConfig) -> None:
        self.config = config
        self.quant_config = load_quant_config(config)
        self.universe_config = load_universe_config()
        self.safety = SafetyPolicy()
        self.health_check = SystemHealthCheck(config)
        self.semantic_gate = SemanticReviewGate()
        self.reporter = RunReporter(config.report_root)
        self.circuit_breakers = CircuitBreakerManager()
        self.registry = ExperimentRegistry()

    def run_once(self, mode: RuntimeMode) -> TradingRunResult:
        health = self.health_check.run_all()
        safety = self.safety.validate(mode, self.config)
        warnings = list(health.warnings) + list(safety.reasons)
        if not safety.allowed or not health.healthy:
            result = TradingRunResult(
                runtime_mode=mode.name,
                safety=asdict(safety),
                health=asdict(health),
                quant_report=None,
                semantic_review=None,
                execution_allowed=False,
                no_trade_reasons=warnings or ["system health check failed"],
                warnings=warnings,
            )
            return self.reporter.write(result)
        dry_run = not mode.can_submit_orders
        quant = QuantOrchestrator(
            self.config,
            self.quant_config,
            universe_config=self.universe_config,
        )
        quant_report = quant.once(dry_run=dry_run, shadow=mode.name == "shadow")
        semantic = self.semantic_gate.review(quant_report)
        if semantic.veto and quant_report.execution_plan.orders:
            quant_report.execution_plan.orders = []
            if quant_report.no_trade is not None:
                quant_report.no_trade.no_trade = True
                quant_report.no_trade.reasons.append("semantic_veto")
        no_trade_reasons = []
        if quant_report.no_trade is not None:
            no_trade_reasons.extend(quant_report.no_trade.reasons)
        if semantic.veto:
            no_trade_reasons.append("semantic_veto")
        result = TradingRunResult(
            runtime_mode=mode.name,
            safety=asdict(safety),
            health=asdict(health),
            quant_report=quant_report,
            semantic_review=semantic,
            execution_allowed=mode.can_submit_orders and not semantic.veto,
            no_trade_reasons=no_trade_reasons,
            warnings=warnings + semantic.warnings,
        )
        return self.reporter.write(result)

    def run_loop(self, mode: RuntimeMode, iterations: int | None = None) -> None:
        count = 0
        while iterations is None or count < iterations:
            self.run_once(mode)
            count += 1

    def run_shadow(self, iterations: int | None = None) -> None:
        self.run_loop(mode_by_name("shadow"), iterations=iterations)

    def run_diagnostics(self) -> dict[str, Any]:
        health = self.health_check.run_all()
        return {
            "runtime": "diagnostics",
            "health": asdict(health),
            "quant": QuantOrchestrator(
                self.config,
                self.quant_config,
                universe_config=self.universe_config,
            ).diagnostics(),
        }

    def run_universe_scan(self) -> dict[str, Any]:
        adapter = DryRunAdapter()
        selection = UniverseDiscoveryEngine().discover(adapter, adapter, self.universe_config)
        scan = MarketScanner().scan(selection.universe, adapter, self.universe_config)
        portfolio = QuantOrchestrator(self.config, self.quant_config, adapter=adapter, universe_config=self.universe_config)._portfolio_state(adapter.get_portfolio())
        focus = FocusListManager().build_focus_list(scan, portfolio, self.universe_config)
        report = UniverseReporter(self.config.report_root).write(selection, scan, focus)
        return {"focus": focus.symbols, "scanned": scan.scanned_count, "rejected": scan.rejected_count, "report": str(report)}

    def run_backtest(self, periods: int = 180, symbols: list[str] | None = None) -> dict[str, Any]:
        quant = QuantOrchestrator(self.config, self.quant_config, universe_config=self.universe_config)
        if symbols:
            from dataclasses import replace

            quant.quant_config = replace(quant.quant_config, symbols=symbols)
        metrics = QuantBacktester().run(quant, periods=periods)
        path = quant.logger.write_backtest_report(metrics)
        self.registry.register({"type": "backtest", "metrics": metrics, "report": str(path)})
        return {"metrics": metrics, "report": str(path)}

    def run_walkforward(self, start: str | None, end: str | None, train_days: int, test_days: int) -> dict[str, Any]:
        quant = QuantOrchestrator(self.config, self.quant_config, universe_config=self.universe_config)
        validator = WalkForwardValidator()
        metrics = validator.run(quant, start, end, train_days, test_days)
        path = validator.write_report(metrics, self.config.report_root)
        self.registry.register({"type": "walkforward", "metrics": metrics, "report": str(path)})
        return {"metrics": metrics, "report": str(path)}

    def emergency_stop(self) -> dict[str, Any]:
        return asdict(self.circuit_breakers.kill())

    def run_tests(self) -> int:
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_alpaca_daytrader.py",
                "tests/test_quant_oria.py",
                "tests/test_market_auditing.py",
                "tests/test_system_orchestrator.py",
                "-q",
            ]
        )
