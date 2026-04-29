"""Command line entrypoint for python -m tradingagents.alpaca_daytrader."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace

from tradingagents.alpaca_daytrader.alpaca_adapter import AlpacaAdapter, DryRunAdapter
from tradingagents.alpaca_daytrader.config import load_config
from tradingagents.alpaca_daytrader.experiments import ExperimentRegistry
from tradingagents.alpaca_daytrader.orchestrator import DayTraderOrchestrator
from tradingagents.alpaca_daytrader.quant.backtest import QuantBacktester
from tradingagents.alpaca_daytrader.quant.config import load_quant_config
from tradingagents.alpaca_daytrader.quant.orchestrator import QuantOrchestrator
from tradingagents.alpaca_daytrader.quant.walkforward import WalkForwardValidator
from tradingagents.alpaca_daytrader.risk.circuit_breakers import CircuitBreakerManager
from tradingagents.alpaca_daytrader.universe.config import load_universe_config
from tradingagents.alpaca_daytrader.universe.discovery import UniverseDiscoveryEngine
from tradingagents.alpaca_daytrader.universe.filters import FocusListManager, MarketScanner
from tradingagents.alpaca_daytrader.universe.reporting import UniverseReporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Alpaca orchestrated daytrader")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "once"):
        command = subparsers.add_parser(name)
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", default=True)
        mode.add_argument("--execute", action="store_true")
        if name == "run":
            command.add_argument("--iterations", type=int, default=None)
    for name in ("quant-run", "quant-once"):
        command = subparsers.add_parser(name)
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", default=True)
        mode.add_argument("--review", action="store_true")
        mode.add_argument("--execute", action="store_true")
        if name == "quant-run":
            mode.add_argument("--shadow", action="store_true")
        if name == "quant-run":
            command.add_argument("--iterations", type=int, default=None)
    backtest = subparsers.add_parser("quant-backtest")
    backtest.add_argument("--symbols", default=None)
    backtest.add_argument("--start", default=None)
    backtest.add_argument("--end", default=None)
    backtest.add_argument("--periods", type=int, default=180)
    walk = subparsers.add_parser("quant-walkforward")
    walk.add_argument("--start", default=None)
    walk.add_argument("--end", default=None)
    walk.add_argument("--train-days", type=int, default=60)
    walk.add_argument("--test-days", type=int, default=10)
    subparsers.add_parser("report")
    subparsers.add_parser("quant-report")
    subparsers.add_parser("quant-diagnostics")
    subparsers.add_parser("universe-scan")
    subparsers.add_parser("universe-report")
    subparsers.add_parser("kill")
    subparsers.add_parser("cancel-all")
    flatten = subparsers.add_parser("flatten")
    flatten.add_argument("--paper-only", action="store_true", default=True)
    subparsers.add_parser("experiment-list")
    show = subparsers.add_parser("experiment-show")
    show.add_argument("experiment_id")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config()
    quant_config = load_quant_config(config)
    universe_config = load_universe_config()
    orchestrator = DayTraderOrchestrator(config)
    quant_orchestrator = QuantOrchestrator(config, quant_config, universe_config=universe_config)
    circuit_breakers = CircuitBreakerManager()
    registry = ExperimentRegistry()
    if args.command == "report":
        report = orchestrator.report()
        print(report if report else "No reports found.")
        return
    if args.command == "quant-report":
        report = quant_orchestrator.latest_report()
        print(report if report else "No quant reports found.")
        return
    if args.command == "quant-diagnostics":
        print(json.dumps(quant_orchestrator.diagnostics(), indent=2))
        return
    if args.command == "universe-scan":
        adapter = DryRunAdapter()
        selection = UniverseDiscoveryEngine().discover(adapter, adapter, universe_config)
        scan = MarketScanner().scan(selection.universe, adapter, universe_config)
        portfolio = quant_orchestrator._portfolio_state(adapter.get_portfolio())
        focus = FocusListManager().build_focus_list(scan, portfolio, universe_config)
        report = UniverseReporter(config.report_root).write(selection, scan, focus)
        print(json.dumps({"focus": focus.symbols, "scanned": scan.scanned_count, "rejected": scan.rejected_count, "report": str(report)}, indent=2, default=str))
        return
    if args.command == "universe-report":
        report = UniverseReporter(config.report_root).latest()
        print(report if report else "No universe reports found.")
        return
    if args.command == "kill":
        print(json.dumps(asdict(circuit_breakers.kill()), indent=2))
        return
    if args.command == "cancel-all":
        print(circuit_breakers.cancel_all(None))
        return
    if args.command == "flatten":
        print(circuit_breakers.flatten(None, paper_only=args.paper_only))
        return
    if args.command == "experiment-list":
        print(json.dumps(registry.list(), indent=2, default=str))
        return
    if args.command == "experiment-show":
        experiment = registry.show(args.experiment_id)
        print(json.dumps(experiment or {"error": "experiment not found"}, indent=2, default=str))
        return
    if args.command == "quant-backtest":
        if args.symbols:
            quant_orchestrator.quant_config = replace(
                quant_orchestrator.quant_config,
                symbols=[s.strip().upper() for s in args.symbols.split(",") if s.strip()],
            )
        metrics = QuantBacktester().run(quant_orchestrator, periods=args.periods)
        path = quant_orchestrator.logger.write_backtest_report(metrics)
        registry.register({"type": "backtest", "metrics": metrics, "report": str(path)})
        print(json.dumps({"metrics": metrics, "report": str(path)}, indent=2, default=str))
        return
    if args.command == "quant-walkforward":
        metrics = WalkForwardValidator().run(quant_orchestrator, args.start, args.end, args.train_days, args.test_days)
        path = WalkForwardValidator().write_report(metrics, config.report_root)
        registry.register({"type": "walkforward", "metrics": metrics, "report": str(path)})
        print(json.dumps({"metrics": metrics, "report": str(path)}, indent=2, default=str))
        return
    dry_run = not args.execute
    if args.command == "quant-once":
        result = quant_orchestrator.once(dry_run=True if args.review else dry_run)
        if args.review:
            _print_review(result)
            if input("Approve paper orders? [y/N] ").strip().lower() != "y":
                print("Review declined; no orders submitted.")
                return
            exec_orchestrator = QuantOrchestrator(config, quant_config, universe_config=universe_config)
            result = exec_orchestrator.once(dry_run=False)
        print(json.dumps(asdict(result), indent=2, default=str))
        return
    if args.command == "quant-run":
        quant_orchestrator.run(dry_run=dry_run or args.shadow, iterations=args.iterations, shadow=args.shadow)
        return
    if args.command == "once":
        result = orchestrator.once(dry_run=dry_run)
        print(json.dumps(asdict(result), indent=2))
        return
    orchestrator.run(dry_run=dry_run, iterations=args.iterations)


def _print_review(result) -> None:
    print("Recommended trades:")
    if not result.execution_plan.orders:
        print("No orders recommended. Hold cash / maintain current book.")
        return
    for idx, order in enumerate(result.execution_plan.orders, start=1):
        action = "Buy" if order.side == "buy" else "Sell"
        print(f"{idx}. {action} ${order.notional:.2f} {order.symbol} via {order.order_type}")


if __name__ == "__main__":
    main()
